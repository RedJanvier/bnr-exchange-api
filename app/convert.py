"""Cross-rate math and frankfurter-shaped response building.

BNR publishes RWF per 1 unit of each foreign currency (the pivot is RWF). For a stored day
we build ``r[code]`` = RWF per 1 unit (with ``r["RWF"] = 1``) and convert:

    rate(base -> quote) = amount * r[base] / r[quote]

i.e. units of ``quote`` per 1 unit of ``base``. This matches the frankfurter convention where
``rates[X]`` is the value of currency X per 1 unit of ``base``.
"""

from __future__ import annotations

from math import floor, log10

from app import config


class UnknownCurrency(ValueError):
    """Raised when a requested base/symbol is not present in a day's rates."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Unknown or unavailable currency: {code}")


def _round_sig(value: float, sig: int = 6) -> float:
    if value == 0:
        return 0.0
    return round(value, -int(floor(log10(abs(value)))) + (sig - 1))


def pivot_map(payload: dict, rate_type: str) -> dict[str, float]:
    """Build ``{code: RWF-per-unit}`` for a day payload, including the RWF pivot at 1.0."""
    rates: dict[str, float] = {config.PIVOT: 1.0}
    for code, triple in payload.get("rates", {}).items():
        value = triple.get(rate_type)
        if value is not None:
            rates[code] = float(value)
    return rates


def convert_day(
    payload: dict,
    base: str,
    symbols: list[str] | None,
    amount: float,
    rate_type: str,
) -> tuple[str, dict[str, float]]:
    """Return ``(resolved_date, {symbol: value})`` for one day, rebased to ``base``.

    ``base`` is excluded from the output (its rate against itself is ``amount``). When
    ``symbols`` is given, only those are returned; otherwise every available currency.
    """
    r = pivot_map(payload, rate_type)
    base = base.upper()
    if base not in r:
        raise UnknownCurrency(base)

    if symbols:
        wanted = [s.upper() for s in symbols]
        for code in wanted:
            if code not in r:
                raise UnknownCurrency(code)
    else:
        wanted = sorted(r.keys())

    rates = {
        code: _round_sig(amount * r[base] / r[code])
        for code in wanted
        if code != base
    }
    return payload["date"], rates


def build_single(
    payload: dict,
    base: str,
    symbols: list[str] | None,
    amount: float,
    rate_type: str,
) -> dict:
    """Frankfurter-style single-date / latest response."""
    resolved_date, rates = convert_day(payload, base, symbols, amount, rate_type)
    return {
        "amount": amount,
        "base": base.upper(),
        "date": resolved_date,
        "rates": rates,
    }


def build_series(
    payloads: list[dict],
    start: str,
    end: str,
    base: str,
    symbols: list[str] | None,
    amount: float,
    rate_type: str,
) -> dict:
    """Frankfurter-style time-series response: ``rates`` keyed by date."""
    series: dict[str, dict[str, float]] = {}
    for payload in payloads:
        resolved_date, rates = convert_day(payload, base, symbols, amount, rate_type)
        series[resolved_date] = rates
    return {
        "amount": amount,
        "base": base.upper(),
        "start_date": start,
        "end_date": end,
        "rates": dict(sorted(series.items())),
    }
