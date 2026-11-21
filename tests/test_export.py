import json

import pandas as pd


def test_example_export_has_expected_files_and_utf8(example_result):
    assert example_result.table_path.name == "1403-12-29__1404-01-03.csv"
    assert example_result.table_path.exists()
    report = json.loads(example_result.report_path.read_text(encoding="utf-8"))
    assert report["reference_day_excluded"] == "1403-12-29"
    assert report["table"]["rows"] == 2
    assert len(report["normalized_files"]) == 8
    assert all(path.exists() for path in example_result.directory.rglob("*.csv"))

    normalized = next(
        example_result.directory.joinpath("normalized").rglob(
            "ayar_by_previous_close.csv"
        )
    )
    values = pd.read_csv(
        normalized,
        header=None,
        names=["time", "open", "high", "low", "close", "volume"],
    )
    assert values.columns.tolist() == ["time", "open", "high", "low", "close", "volume"]
    assert values.iloc[0]["time"] == "11:00"
