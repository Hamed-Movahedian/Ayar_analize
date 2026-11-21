"""Gregorian-to-Jalali presentation only; calculation timestamps stay Gregorian."""

from datetime import date

import jdatetime


def jalali_date(value: date) -> str:
    converted = jdatetime.date.fromgregorian(date=value)
    return f"{converted.year:04d}-{converted.month:02d}-{converted.day:02d}"
