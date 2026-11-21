"""Shared data contracts; no file I/O or calculations."""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

import pandas as pd

CSV_COLUMNS = ["date", "time", "open", "high", "low", "close", "volume"]
NORMALIZED_COLUMNS = ["time", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]
METRIC_NAMES = [
    "previous_close",
    "previous_vwap",
    "open",
    "vwap",
    "gap_close_pct",
    "gap_vwap_pct",
]
TABLE_COLUMNS = ["date"] + [
    f"{asset}_{metric}" for asset in ("gold", "ayar") for metric in METRIC_NAMES
]


class AnalysisError(ValueError):
    """An actionable input or analysis error that the CLI can display."""


class PriceBasis(StrEnum):
    TYPICAL = "typical"
    CLOSE = "close"
    OHLC4 = "ohlc4"


@dataclass(frozen=True)
class AnalysisConfig:
    price_basis: PriceBasis = PriceBasis.TYPICAL
    timeframe_minutes: int | None = None
    strict: bool = False
    normalized_header: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "price_basis", PriceBasis(self.price_basis))
        if self.timeframe_minutes is not None and (
            isinstance(self.timeframe_minutes, bool)
            or not isinstance(self.timeframe_minutes, int)
            or self.timeframe_minutes <= 0
        ):
            raise AnalysisError("timeframe_minutes must be a positive integer.")


@dataclass(frozen=True)
class Timeframe:
    minutes: int
    source: str
    ayar_observed_gcd: int | None
    gold_observed_gcd: int | None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Issue:
    date: str
    asset: str
    code: str
    message: str


@dataclass(frozen=True)
class SessionStats:
    open: float | None
    close: float | None
    vwap: float | None
    candle_count: int


@dataclass
class TradingSession:
    date: date
    jalali_date: str
    start: pd.Timestamp
    end: pd.Timestamp
    ayar: pd.DataFrame
    gold_aligned: pd.DataFrame
    ayar_stats: SessionStats
    gold_stats: SessionStats


@dataclass
class Analysis:
    timeframe: Timeframe
    sessions: list[TradingSession]
    table: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)


@dataclass(frozen=True)
class RunResult:
    directory: Path
    table_path: Path
    report_path: Path
    timeframe_minutes: int
    trading_days: int
    table_rows: int
    normalized_files: int
    issue_count: int
