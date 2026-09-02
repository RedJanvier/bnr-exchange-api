"""Parser tests, ported from frankfurter's bnrrw adapter spec (the reference contract)."""

from __future__ import annotations

from datetime import date

import pytest

from app.ingest import bnr_client


def test_takes_average_rate_as_mid():
    records = bnr_client.parse(
        [{
            "currency_name": "USD",
            "buying_rate": "1458.3525",
            "average_rate": "1463.3525",
            "selling_rate": "1468.3525",
            "post_date": "22-May-26",
        }]
    )
    assert len(records) == 1
    r = records[0]
    assert r.code == "USD"
    assert r.average == 1463.3525
    assert r.buying == 1458.3525
    assert r.selling == 1468.3525
    assert r.date == date(2026, 5, 22)


def test_parses_thousands_commas_older_format():
    records = bnr_client.parse(
        [{
            "currency_name": "USD",
            "buying_rate": "1,254.96",
            "average_rate": "1,267.50",
            "selling_rate": "1,280.05",
            "post_date": "04-Jan-24",
        }]
    )
    assert len(records) == 1
    assert records[0].average == 1267.50
    assert records[0].date == date(2024, 1, 4)


def test_skips_non_positive_rates():
    records = bnr_client.parse(
        [{"currency_name": "USD", "average_rate": "0", "post_date": "22-May-26"}]
    )
    assert records == []


def test_skips_missing_average_rate():
    records = bnr_client.parse(
        [{"currency_name": "USD", "buying_rate": "1458.0", "post_date": "22-May-26"}]
    )
    assert records == []


def test_skips_invalid_currency_code():
    records = bnr_client.parse(
        [{"currency_name": "usd", "average_rate": "1463", "post_date": "22-May-26"}]
    )
    assert records == []


def test_empty_array_returns_empty():
    assert bnr_client.parse([]) == []


def test_non_array_raises():
    with pytest.raises(ValueError):
        bnr_client.parse({"currency_name": "USD"})


def test_buying_selling_fall_back_to_average_when_absent():
    records = bnr_client.parse(
        [{"currency_name": "EUR", "average_rate": "1699.5", "post_date": "22-May-26"}]
    )
    assert len(records) == 1
    assert records[0].buying == 1699.5
    assert records[0].selling == 1699.5
