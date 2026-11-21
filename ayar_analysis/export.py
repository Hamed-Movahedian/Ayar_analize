"""UTF-8 CSV/JSON output and publication of a complete, isolated run directory."""

import json
import shutil
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ayar_analysis.analysis import normalize_candles
from ayar_analysis.models import (
    NORMALIZED_COLUMNS,
    Analysis,
    AnalysisConfig,
    AnalysisError,
    RunResult,
)


def _write_candles(candles: pd.DataFrame, path: Path, header: bool) -> None:
    data = candles.copy()
    data.insert(0, "time", data.index.strftime("%H:%M"))
    data.to_csv(
        path,
        columns=NORMALIZED_COLUMNS,
        index=False,
        header=header,
        encoding="utf-8",
        lineterminator="\n",
    )


def export_analysis(
    analysis: Analysis,
    output_root: str | Path,
    config: AnalysisConfig,
    sources: dict,
) -> RunResult:
    """Build a run privately, then rename it into place after every write succeeds."""
    if config.strict and analysis.issues:
        first = analysis.issues[0]
        raise AnalysisError(
            f"Strict mode: {len(analysis.issues)} data quality issue(s). "
            f"First: {first.date} {first.asset}: {first.message}"
        )
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    sessions = analysis.sessions
    start = sessions[0].jalali_date
    end = sessions[-1].jalali_date
    table_name = f"{start}__{end}.csv"
    now = datetime.now(UTC)
    run_name = f"{start}__{end}__{now:%Y%m%dT%H%M%S%fZ}"
    final = root / run_name
    staging = Path(tempfile.mkdtemp(prefix=".ayar-", dir=root))
    exports: list[dict] = []

    try:
        analysis.table.to_csv(
            staging / table_name,
            index=False,
            encoding="utf-8",
            na_rep="",
            lineterminator="\n",
        )
        for previous, current in zip(sessions, sessions[1:], strict=False):
            day_directory = staging / "normalized" / current.jalali_date
            day_directory.mkdir(parents=True)
            for asset in ("ayar", "gold"):
                candles = current.ayar if asset == "ayar" else current.gold_aligned
                stats = getattr(previous, f"{asset}_stats")
                for reference in ("close", "vwap"):
                    denominator = getattr(stats, reference)
                    normalized = normalize_candles(candles, denominator)
                    filename = f"{asset}_by_previous_{reference}.csv"
                    path = day_directory / filename
                    _write_candles(normalized, path, config.normalized_header)
                    status = (
                        "unavailable_reference"
                        if denominator is None
                        else "no_matching_candles"
                        if candles.empty
                        else "ok"
                    )
                    exports.append(
                        {
                            "path": path.relative_to(staging).as_posix(),
                            "date": current.jalali_date,
                            "asset": asset,
                            "reference": f"previous_{reference}",
                            "reference_date": previous.jalali_date,
                            "denominator": denominator,
                            "rows": len(normalized),
                            "status": status,
                        }
                    )

        report = {
            "schema_version": 1,
            "created_at_utc": now.isoformat(),
            "sources": sources,
            "configuration": asdict(config),
            "timeframe": asdict(analysis.timeframe),
            "policies": {
                "session": "First through last Ayar candle, inclusive, per local date; "
                "at least one gold candle must fall inside that interval",
                "boundary_prices": "Ayar uses exact start open and end close. "
                "Gold uses exact values when present; otherwise previous-day close "
                "falls back to the last close before the end boundary and current-day "
                "open falls forward to the first open after the start boundary.",
                "vwap": "sum(candle_price * volume) / sum(volume)",
                "gold_vwap_selection": "All gold candles in the Ayar session window",
                "gold_normalized_selection": "Exact timestamp intersection with Ayar",
                "missing_data": "Blank table cells; empty unavailable candle exports",
                "normalization": "OHLC / previous reference; volume unchanged",
                "percent_change": "100 * (current_open / previous_reference - 1)",
            },
            "reference_day_excluded": sessions[0].jalali_date,
            "table": {"path": table_name, "rows": len(analysis.table)},
            "sessions": [
                {
                    "date": session.jalali_date,
                    "gregorian_date": session.date.isoformat(),
                    "start": session.start.isoformat(),
                    "end": session.end.isoformat(),
                    "ayar": asdict(session.ayar_stats),
                    "gold": asdict(session.gold_stats),
                    "gold_aligned_candles": len(session.gold_aligned),
                }
                for session in sessions
            ],
            "issues": [asdict(issue) for issue in analysis.issues],
            "normalized_files": exports,
        }
        (staging / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        staging.rename(final)
    except BaseException:
        # Only the private temporary directory created by this call is removed.
        shutil.rmtree(staging)
        raise

    return RunResult(
        final,
        final / table_name,
        final / "report.json",
        analysis.timeframe.minutes,
        len(sessions),
        len(analysis.table),
        len(exports),
        len(analysis.issues),
    )
