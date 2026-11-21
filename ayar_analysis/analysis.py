"""Pure session statistics, comparison, and candle normalization."""

import numpy as np
import pandas as pd

from ayar_analysis.calendar import jalali_date
from ayar_analysis.models import (
    PRICE_COLUMNS,
    TABLE_COLUMNS,
    Analysis,
    AnalysisConfig,
    AnalysisError,
    Issue,
    PriceBasis,
    SessionStats,
    Timeframe,
    TradingSession,
)


def weighted_price(candles: pd.DataFrame, basis: PriceBasis) -> float | None:
    """Volume-weighted candle-price estimate (not trade-by-trade VWAP)."""
    if candles.empty or not candles["volume"].gt(0).any():
        return None
    columns = {
        PriceBasis.TYPICAL: ["high", "low", "close"],
        PriceBasis.CLOSE: ["close"],
        PriceBasis.OHLC4: PRICE_COLUMNS,
    }[basis]
    # Divide before summing to avoid overflow for large but finite inputs.
    prices = (candles[columns].astype(float) / len(columns)).sum(axis=1)
    weights = candles["volume"].astype(float)
    weights = weights / weights.max()
    weights = weights / weights.sum()
    value = float((prices * weights).sum())
    return value if np.isfinite(value) and value > 0 else None


def _session_stats(
    candles: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    basis: PriceBasis,
    asset: str,
    day: str,
    issues: list[Issue],
) -> SessionStats:
    def boundary(timestamp: pd.Timestamp, field: str) -> float | None:
        if timestamp in candles.index:
            return float(candles.at[timestamp, field])

        fallback: pd.DataFrame
        if asset == "gold" and field == "close":
            fallback = candles.loc[candles.index < timestamp]
            if not fallback.empty:
                return float(fallback.iloc[-1][field])
        elif asset == "gold" and field == "open":
            fallback = candles.loc[candles.index > timestamp]
            if not fallback.empty:
                return float(fallback.iloc[0][field])

        if timestamp not in candles.index:
            issues.append(
                Issue(
                    day,
                    asset,
                    f"missing_{field}_boundary",
                    f"No candle at Ayar session {field} boundary {timestamp}. "
                    "The value is unavailable; no filling was applied.",
                )
            )
            return None

    opening = boundary(start, "open")
    closing = boundary(end, "close")
    vwap = weighted_price(candles, basis)
    if vwap is None:
        issues.append(
            Issue(
                day,
                asset,
                "unavailable_vwap",
                "VWAP is unavailable: no candles, zero total volume, "
                "or a non-finite calculation.",
            )
        )
    return SessionStats(opening, closing, vwap, len(candles))


def percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous <= 0:
        return None
    return (current / previous - 1) * 100


def _comparison(previous: SessionStats, current: SessionStats) -> dict:
    return {
        "previous_close": previous.close,
        "previous_vwap": previous.vwap,
        "open": current.open,
        "vwap": current.vwap,
        "gap_close_pct": percent_change(current.open, previous.close),
        "gap_vwap_pct": percent_change(current.open, previous.vwap),
    }


def analyze(
    gold: pd.DataFrame,
    ayar: pd.DataFrame,
    timeframe: Timeframe,
    config: AnalysisConfig,
) -> Analysis:
    """Build sessions whose Ayar interval contains a gold candle.

    Gold VWAP uses every gold candle in the inclusive Ayar session interval.
    Gold normalized candles use the exact intersection of the two timestamps.
    These are deliberately separate selections.
    """
    issues: list[Issue] = []
    sessions: list[TradingSession] = []
    for day, ayar_day in ayar.groupby(ayar.index.date, sort=True):
        start, end = ayar_day.index[0], ayar_day.index[-1]
        gold_window = gold.loc[start:end]
        if gold_window.empty:
            continue
        aligned = gold_window.loc[gold_window.index.isin(ayar_day.index)]
        day_text = jalali_date(day)
        missing_count = len(ayar_day) - len(aligned)
        if missing_count:
            issues.append(
                Issue(
                    day_text,
                    "gold",
                    "missing_aligned_candles",
                    f"Gold has no candle at {missing_count} Ayar timestamps. "
                    "Only exact matches are exported for gold.",
                )
            )
        sessions.append(
            TradingSession(
                day,
                day_text,
                start,
                end,
                ayar_day,
                aligned,
                _session_stats(
                    ayar_day, start, end, config.price_basis, "ayar", day_text, issues
                ),
                _session_stats(
                    gold_window,
                    start,
                    end,
                    config.price_basis,
                    "gold",
                    day_text,
                    issues,
                ),
            )
        )

    if not sessions:
        raise AnalysisError(
            "No common trading session exists: no gold candle falls inside "
            "any Ayar trading interval."
        )

    rows = []
    for previous, current in zip(sessions, sessions[1:], strict=False):
        row = {"date": current.jalali_date}
        for asset in ("gold", "ayar"):
            metrics = _comparison(
                getattr(previous, f"{asset}_stats"), getattr(current, f"{asset}_stats")
            )
            row.update({f"{asset}_{key}": value for key, value in metrics.items()})
        rows.append(row)
    table = pd.DataFrame(rows, columns=TABLE_COLUMNS)
    return Analysis(timeframe, sessions, table, issues)


def normalize_candles(candles: pd.DataFrame, denominator: float | None) -> pd.DataFrame:
    """Divide OHLC only, preserving timestamps and volume exactly.

    An unavailable reference produces an empty file, recorded explicitly in
    the run report. It never yields a row of invented or partially empty OHLC.
    """
    if denominator is None or not np.isfinite(denominator) or denominator <= 0:
        return candles.iloc[:0].copy()
    result = candles.copy()
    for column in PRICE_COLUMNS:
        result[column] = result[column].astype(float) / denominator
    if not np.isfinite(result[PRICE_COLUMNS]).all().all():
        from ayar_analysis.models import AnalysisError

        raise AnalysisError("Normalization overflowed; inspect source price scales.")
    return result
