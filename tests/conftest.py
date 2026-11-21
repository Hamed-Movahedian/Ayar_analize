from pathlib import Path

import pandas as pd
import pytest

from ayar_analysis.models import AnalysisConfig
from ayar_analysis.pipeline import run_analysis


@pytest.fixture
def example_paths() -> tuple[Path, Path]:
    root = Path(__file__).parents[1]
    return root / "examples" / "gold.csv", root / "examples" / "ayar.csv"


@pytest.fixture
def example_result(tmp_path, example_paths):
    gold, ayar = example_paths
    return run_analysis(gold, ayar, tmp_path, AnalysisConfig())


def read_headerless(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        header=None,
        names=["date", "time", "open", "high", "low", "close", "volume"],
    )
