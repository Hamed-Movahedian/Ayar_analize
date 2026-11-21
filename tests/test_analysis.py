import math

import pandas as pd
import pytest

from ayar_analysis.analysis import analyze, normalize_candles, weighted_price
from ayar_analysis.models import AnalysisConfig, AnalysisError, PriceBasis, Timeframe
from ayar_analysis.reader import read_candles


def frame(rows):
    return pd.DataFrame(
        rows,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    ).set_index("timestamp")


def test_typical_volume_weighted_price():
    candles = frame(
        [
            (pd.Timestamp("2025-01-01 11:00"), 10, 13, 7, 10, 1),
            (pd.Timestamp("2025-01-01 11:05"), 20, 23, 17, 20, 3),
        ]
    )
    assert math.isclose(weighted_price(candles, PriceBasis.TYPICAL), 17.5)


def test_session_comparison_uses_ayar_dates_and_exact_gold_intersection():
    gold = frame(
        [
            (pd.Timestamp("2025-01-01 11:00"), 100, 104, 98, 102, 1),
            (pd.Timestamp("2025-01-01 11:05"), 102, 106, 100, 104, 1),
            (pd.Timestamp("2025-01-02 10:55"), 104, 108, 102, 106, 1),
            (pd.Timestamp("2025-01-02 11:00"), 106, 110, 104, 108, 1),
            (pd.Timestamp("2025-01-02 11:05"), 108, 112, 106, 110, 1),
            (pd.Timestamp("2025-01-03 11:00"), 110, 114, 108, 112, 1),
            (pd.Timestamp("2025-01-04 10:00"), 112, 116, 110, 114, 1),
        ]
    )
    ayar = frame(
        [
            (pd.Timestamp("2025-01-01 11:00"), 10, 11, 9, 10, 1),
            (pd.Timestamp("2025-01-01 11:05"), 10, 11, 9, 10, 1),
            (pd.Timestamp("2025-01-03 11:00"), 12, 13, 11, 12, 1),
            (pd.Timestamp("2025-01-03 11:05"), 12, 13, 11, 12, 1),
            (pd.Timestamp("2025-01-04 11:00"), 13, 14, 12, 13, 1),
        ]
    )
    analysis = analyze(
        gold,
        ayar,
        Timeframe(5, "test", 5, 5),
        AnalysisConfig(),
    )
    assert len(analysis.sessions) == 2
    assert len(analysis.table) == 1
    assert analysis.table.iloc[0]["ayar_previous_close"] == 10
    assert analysis.table.iloc[0]["ayar_open"] == 12
    assert len(analysis.sessions[1].gold_aligned) == 1
    assert any(issue.code == "missing_aligned_candles" for issue in analysis.issues)


def test_no_common_trading_day_is_rejected():
    gold = frame([(pd.Timestamp("2025-01-01 11:00"), 100, 101, 99, 100, 1)])
    ayar = frame([(pd.Timestamp("2025-01-02 11:00"), 10, 11, 9, 10, 1)])
    with pytest.raises(AnalysisError, match="No common trading session"):
        analyze(gold, ayar, Timeframe(5, "test", 5, 5), AnalysisConfig())


def test_normalization_preserves_volume_and_drops_unavailable_reference():
    candles = frame([(pd.Timestamp("2025-01-01 11:00"), 10, 12, 8, 11, 7)])
    normalized = normalize_candles(candles, 10)
    assert normalized.iloc[0]["open"] == 1
    assert normalized.iloc[0]["volume"] == 7
    assert normalize_candles(candles, None).empty


def test_timeframe_is_read_from_examples(example_paths):
    gold_path, ayar_path = example_paths
    gold, ayar = read_candles(gold_path), read_candles(ayar_path)
    from ayar_analysis.timeframe import infer_timeframe

    timeframe = infer_timeframe(ayar.index, gold.index)
    assert timeframe.minutes == 5
