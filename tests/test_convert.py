"""Cross-rate math and carry-forward tests."""

from __future__ import annotations

import pytest

from app import convert, store

# A minimal day payload: RWF per 1 unit (average), plus buying/selling.
_PAYLOAD = {
    "date": "2026-05-22",
    "provider": "BNR",
    "pivot": "RWF",
    "rates": {
        "USD": {"buying": 1458.0, "average": 1463.0, "selling": 1468.0},
        "EUR": {"buying": 1695.0, "average": 1700.0, "selling": 1705.0},
    },
}


def test_pivot_map_includes_rwf_pivot():
    r = convert.pivot_map(_PAYLOAD, "average")
    assert r["RWF"] == 1.0
    assert r["USD"] == 1463.0
    assert r["EUR"] == 1700.0


def test_rwf_base_returns_reciprocal():
    # base=RWF (default): value of 1 RWF in USD = 1/1463.
    _, rates = convert.convert_day(_PAYLOAD, "RWF", ["USD"], 1.0, "average")
    assert rates["USD"] == pytest.approx(1 / 1463.0, rel=1e-6)


def test_cross_rate_usd_to_eur():
    # 1 USD in EUR = r[USD]/r[EUR] = 1463/1700.
    _, rates = convert.convert_day(_PAYLOAD, "USD", ["EUR"], 1.0, "average")
    assert rates["EUR"] == pytest.approx(1463.0 / 1700.0, rel=1e-6)


def test_amount_scales_linearly():
    _, one = convert.convert_day(_PAYLOAD, "USD", ["RWF"], 1.0, "average")
    _, hundred = convert.convert_day(_PAYLOAD, "USD", ["RWF"], 100.0, "average")
    assert hundred["RWF"] == pytest.approx(one["RWF"] * 100, rel=1e-9)
    assert one["RWF"] == pytest.approx(1463.0, rel=1e-6)


def test_base_excluded_from_rates():
    _, rates = convert.convert_day(_PAYLOAD, "USD", None, 1.0, "average")
    assert "USD" not in rates
    assert set(rates) == {"RWF", "EUR"}


def test_rate_type_selects_column():
    _, buying = convert.convert_day(_PAYLOAD, "USD", ["RWF"], 1.0, "buying")
    assert buying["RWF"] == pytest.approx(1458.0, rel=1e-6)


def test_unknown_currency_raises():
    with pytest.raises(convert.UnknownCurrency):
        convert.convert_day(_PAYLOAD, "XXX", ["USD"], 1.0, "average")
    with pytest.raises(convert.UnknownCurrency):
        convert.convert_day(_PAYLOAD, "USD", ["XXX"], 1.0, "average")


def test_carry_forward_uses_previous_business_day(seeded):
    # 2026-05-23/24 are a weekend with no files; resolve should fall back to 2026-05-22.
    payload = store.resolve_day("2026-05-24")
    assert payload is not None
    assert payload["date"] == "2026-05-22"
