"""Coordinate input, analysis, and output without coupling their implementations."""

from pathlib import Path

from ayar_analysis.analysis import analyze
from ayar_analysis.export import export_analysis
from ayar_analysis.models import AnalysisConfig, AnalysisError, RunResult
from ayar_analysis.reader import read_candles
from ayar_analysis.timeframe import infer_timeframe


def run_analysis(
    gold_path: str | Path,
    ayar_path: str | Path,
    output_root: str | Path = "output",
    config: AnalysisConfig | None = None,
) -> RunResult:
    config = config or AnalysisConfig()
    gold_path, ayar_path = Path(gold_path).resolve(), Path(ayar_path).resolve()
    if gold_path == ayar_path:
        raise AnalysisError("Gold and Ayar inputs must be different files.")
    gold = read_candles(gold_path)
    ayar = read_candles(ayar_path)
    timeframe = infer_timeframe(ayar.index, gold.index, config.timeframe_minutes)
    analysis = analyze(gold, ayar, timeframe, config)
    return export_analysis(
        analysis,
        output_root,
        config,
        sources={
            "gold": {"path": str(gold_path), "candles": len(gold)},
            "ayar": {"path": str(ayar_path), "candles": len(ayar)},
        },
    )
