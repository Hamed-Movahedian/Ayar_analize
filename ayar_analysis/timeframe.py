"""Infer a common candle interval without interpreting overnight gaps as bars."""

from functools import reduce
from math import gcd

import pandas as pd

from ayar_analysis.models import AnalysisError, Timeframe


def _intraday_deltas(index: pd.DatetimeIndex) -> list[int]:
    same_day = index[1:].normalize() == index[:-1].normalize()
    deltas = (index[1:] - index[:-1]).total_seconds() / 60
    return [int(delta) for delta in deltas[same_day]]


def _observed_gcd(deltas: list[int]) -> int | None:
    return reduce(gcd, deltas) if deltas else None


def infer_timeframe(
    ayar: pd.DatetimeIndex,
    gold: pd.DatetimeIndex,
    override_minutes: int | None = None,
) -> Timeframe:
    """Estimate the common interval using the GCD of within-day gaps.

    Missing bars can make an observed interval a multiple of the true one.
    Different observed GCDs are consequently reported as ambiguous evidence,
    not silently rejected as different source timeframes.
    """
    ayar_deltas = _intraday_deltas(ayar)
    gold_deltas = _intraday_deltas(gold)
    ayar_gcd = _observed_gcd(ayar_deltas)
    gold_gcd = _observed_gcd(gold_deltas)
    observed = [x for x in (ayar_gcd, gold_gcd) if x is not None]
    notes: list[str] = []

    if override_minutes is not None:
        if (
            isinstance(override_minutes, bool)
            or not isinstance(override_minutes, int)
            or override_minutes <= 0
        ):
            raise AnalysisError("The timeframe override must be a positive integer.")
        minutes = override_minutes
        if any(delta % minutes for delta in ayar_deltas + gold_deltas):
            raise AnalysisError(
                f"Observed intraday gaps are not multiples of {minutes} minutes."
            )
        source = "explicit"
    elif observed:
        minutes = reduce(gcd, observed)
        source = "inferred_intraday_gcd"
        if ayar_gcd != gold_gcd:
            notes.append(
                "Source interval evidence differs or is insufficient in one file. "
                "The common GCD is used under the same-timeframe assumption. "
                "Use --timeframe-minutes if the source interval is known."
            )
        if minutes not in ayar_deltas + gold_deltas:
            notes.append(
                "The inferred interval is not directly observed between consecutive "
                "candles; all observed gaps contain missing slots."
            )
    else:
        raise AnalysisError(
            "Cannot infer the timeframe: neither file has two candles on one day. "
            "Provide --timeframe-minutes with the known source interval."
        )

    # Check phase per date as well as interval. Different market opening hours
    # are fine, provided both series lie on a common candle grid on that date.
    combined = ayar.union(gold).sort_values()
    if any(delta % minutes for delta in _intraday_deltas(combined)):
        raise AnalysisError(
            f"The two series are offset from the common {minutes}-minute grid. "
            "Check source timestamps and source timeframes."
        )
    return Timeframe(minutes, source, ayar_gcd, gold_gcd, tuple(notes))
