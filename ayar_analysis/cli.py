"""Command-line interface; all analytical behavior lives in other modules."""

import argparse
import sys
from pathlib import Path

from ayar_analysis.models import AnalysisConfig, AnalysisError, PriceBasis
from ayar_analysis.pipeline import run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare daily Ayar/gold OHLCV and export normalized candles."
    )
    parser.add_argument("--gold", type=Path, required=True, help="18-karat gold CSV")
    parser.add_argument("--ayar", type=Path, required=True, help="Ayar fund CSV")
    parser.add_argument(
        "--output", type=Path, default=Path("output"), help="Parent folder for new runs"
    )
    parser.add_argument(
        "--price-basis",
        choices=[basis.value for basis in PriceBasis],
        default=PriceBasis.TYPICAL.value,
        help="VWAP candle price: typical=(H+L+C)/3 (default), close, or ohlc4",
    )
    parser.add_argument(
        "--timeframe-minutes",
        type=int,
        help="Known candle interval; otherwise infer it from within-day gaps",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail before exporting if missing data or undefined VWAP is found",
    )
    parser.add_argument(
        "--normalized-header",
        action="store_true",
        help="Add column headers to normalized CSVs (default: headerless)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = AnalysisConfig(
            price_basis=PriceBasis(args.price_basis),
            timeframe_minutes=args.timeframe_minutes,
            strict=args.strict,
            normalized_header=args.normalized_header,
        )
        result = run_analysis(args.gold, args.ayar, args.output, config)
    except (AnalysisError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Timeframe: {result.timeframe_minutes} minutes")
    print(f"Trading days: {result.trading_days} (first day is reference only)")
    print(f"Daily table: {result.table_path} ({result.table_rows} rows)")
    print(f"Normalized CSV files: {result.normalized_files}")
    print(f"Data quality issues: {result.issue_count}")
    print(f"Run report: {result.report_path}")
    return 0
