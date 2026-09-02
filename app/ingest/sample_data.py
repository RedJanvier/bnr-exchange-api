"""Bundled sample rates so the API, tests, and demo page work before the first live pull.

These values are illustrative (anchored to real BNR figures observed around 2026-05-22, RWF
per 1 unit) and exist only so the service returns something meaningful out of the box in an
environment without network access to ``fxrates.bnr.rw``. The scheduled GitHub Action
(``--daily`` / ``--backfill``) overwrites the data store with authoritative BNR data.
"""

from __future__ import annotations

from datetime import date

from app.ingest.bnr_client import Record

# Mid (average) rate, RWF per 1 unit of the foreign currency, for two sample dates.
_AVERAGES: dict[str, dict[str, float]] = {
    "2026-05-21": {
        "USD": 1463.255, "EUR": 1699.10, "GBP": 1964.80, "JPY": 9.19, "CHF": 1860.20,
        "CAD": 1050.40, "AUD": 940.10, "CNY": 215.10, "INR": 17.10, "ZAR": 88.80,
        "AED": 398.35, "SAR": 389.85, "KES": 11.27, "UGX": 0.3868, "TZS": 0.5615, "BIF": 0.4908,
    },
    "2026-05-22": {
        "USD": 1463.3525, "EUR": 1699.50, "GBP": 1965.30, "JPY": 9.20, "CHF": 1860.70,
        "CAD": 1050.90, "AUD": 940.60, "CNY": 215.20, "INR": 17.12, "ZAR": 88.90,
        "AED": 398.40, "SAR": 389.90, "KES": 11.28, "UGX": 0.3870, "TZS": 0.5620, "BIF": 0.4910,
    },
}

# Typical BNR buying/selling spread around the mid (~0.34%); real files store the true triple.
_SPREAD = 0.00342


def _records() -> tuple[Record, ...]:
    rows: list[Record] = []
    for day_str, averages in _AVERAGES.items():
        day = date.fromisoformat(day_str)
        for code, average in averages.items():
            rows.append(
                Record(
                    code=code,
                    date=day,
                    buying=round(average * (1 - _SPREAD), 4),
                    average=average,
                    selling=round(average * (1 + _SPREAD), 4),
                )
            )
    return tuple(rows)


SAMPLE_RECORDS: tuple[Record, ...] = _records()
