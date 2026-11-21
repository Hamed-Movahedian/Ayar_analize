from pathlib import Path

import pytest

from ayar_analysis.models import AnalysisError
from ayar_analysis.reader import read_candles


def write_csv(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_first_row_is_a_candle(tmp_path):
    path = write_csv(
        tmp_path / "candles.csv",
        "2025.01.01,11:00,1,2,0.5,1.5,1\n2025.01.01,11:05,1.5,2.5,1,2,2\n",
    )
    candles = read_candles(path)
    assert len(candles) == 2
    assert candles.iloc[0]["open"] == 1


@pytest.mark.parametrize(
    "text, expected",
    [
        ("date,time,open,high,low,close,volume,extra\n", "exactly 7 columns"),
        (
            "2025.01.01,11:00,1,2,0.5,1.5,1\n2025.01.01,11:00,1,2,0.5,1.5,1\n",
            "duplicate",
        ),
        (
            "2025.01.01,11:05,1,2,0.5,1.5,1\n2025.01.01,11:00,1,2,0.5,1.5,1\n",
            "ascending",
        ),
        ("2025.01.01,11:00,1,2,3,1.5,1\n", "inconsistent"),
    ],
)
def test_invalid_input_is_rejected(tmp_path, text, expected):
    with pytest.raises(AnalysisError, match=expected):
        read_candles(write_csv(tmp_path / "bad.csv", text))
