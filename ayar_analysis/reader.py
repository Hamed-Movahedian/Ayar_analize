"""Read and validate the headerless seven-column source format."""

from pathlib import Path

import numpy as np
import pandas as pd

from ayar_analysis.models import CSV_COLUMNS, PRICE_COLUMNS, AnalysisError


def _first_row(mask: pd.Series) -> int:
    return int(mask[mask].index[0]) + 1


def read_candles(path: str | Path) -> pd.DataFrame:
    """Return validated numeric OHLCV data indexed by naive local timestamps.

    Input timestamps are already in the market's local time. No timezone
    conversion, sorting, duplicate removal, resampling, or filling is performed.
    """
    path = Path(path)
    try:
        raw = pd.read_csv(
            path,
            header=None,
            dtype=str,
            encoding="utf-8-sig",
            keep_default_na=False,
            skip_blank_lines=False,
            index_col=False,
        )
    except (
        OSError,
        UnicodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        raise AnalysisError(f"Cannot read {path}: {exc}") from exc

    if raw.empty:
        raise AnalysisError(f"{path}: the file contains no candles.")
    if raw.shape[1] != 7:
        raise AnalysisError(
            f"{path}: expected exactly 7 columns without a header; "
            f"found {raw.shape[1]}."
        )
    raw.columns = CSV_COLUMNS
    for column in CSV_COLUMNS:
        raw[column] = raw[column].str.strip()
    missing = raw.isna().any(axis=1) | raw.eq("").any(axis=1)
    if missing.any():
        raise AnalysisError(f"{path}: empty field on row {_first_row(missing)}.")

    valid_format = raw["date"].str.fullmatch(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}") & raw[
        "time"
    ].str.fullmatch(r"[0-9]{2}:[0-9]{2}")
    if not valid_format.all():
        raise AnalysisError(
            f"{path}: row {_first_row(~valid_format)} must use "
            "YYYY.MM.DD,HH:MM (no header)."
        )
    timestamps = pd.to_datetime(
        raw["date"] + " " + raw["time"],
        format="%Y.%m.%d %H:%M",
        errors="coerce",
        exact=True,
    )
    invalid_date = timestamps.isna()
    if invalid_date.any():
        raise AnalysisError(
            f"{path}: invalid date/time on row {_first_row(invalid_date)}."
        )
    duplicates = timestamps.duplicated()
    if duplicates.any():
        raise AnalysisError(
            f"{path}: duplicate timestamp on row {_first_row(duplicates)}."
        )
    if not timestamps.is_monotonic_increasing:
        raise AnalysisError(f"{path}: timestamps must be in ascending order.")

    numeric = raw[PRICE_COLUMNS + ["volume"]].apply(pd.to_numeric, errors="coerce")
    invalid_numeric = ~np.isfinite(numeric).all(axis=1)
    if invalid_numeric.any():
        raise AnalysisError(
            f"{path}: non-finite or non-numeric value on row "
            f"{_first_row(invalid_numeric)}."
        )
    invalid_price = numeric[PRICE_COLUMNS].le(0).any(axis=1)
    if invalid_price.any():
        raise AnalysisError(
            f"{path}: prices must be positive (row {_first_row(invalid_price)})."
        )
    negative_volume = numeric["volume"].lt(0)
    if negative_volume.any():
        raise AnalysisError(
            f"{path}: volume must be nonnegative (row {_first_row(negative_volume)})."
        )
    inconsistent = (
        numeric["low"].gt(numeric["high"])
        | ~numeric["open"].between(numeric["low"], numeric["high"])
        | ~numeric["close"].between(numeric["low"], numeric["high"])
    )
    if inconsistent.any():
        raise AnalysisError(
            f"{path}: inconsistent OHLC prices on row {_first_row(inconsistent)}."
        )
    numeric.index = pd.DatetimeIndex(timestamps, name="timestamp")
    return numeric
