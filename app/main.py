"""BNR Exchange Rate API — a free, open, frankfurter-style API for Rwandan Franc rates.

Data comes from the official National Bank of Rwanda feed, committed into this repo by a
scheduled job (git-as-DB) and read from disk here. RWF is the default base.

Endpoints (query params: ``base``/``from``, ``symbols``/``to``, ``amount``, ``rate_type``):

* ``GET /``                       service metadata
* ``GET /health``                 liveness + dataset summary
* ``GET /currencies``             supported ``code -> name`` map
* ``GET /latest``                 most recent published rates
* ``GET /{YYYY-MM-DD}``           rates for a date (carried forward across weekends/holidays)
* ``GET /{start}..{end}``         time series over an inclusive date range
"""

from __future__ import annotations

import re
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import config, convert, store

app = FastAPI(
    title="BNR Exchange Rate API",
    version="1.0.0",
    description=(
        "Free, open exchange-rate API for the Rwandan Franc (RWF), sourced from the "
        "official National Bank of Rwanda feed. Inspired by frankfurter.dev."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RANGE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})$")
_MAX_RANGE_DAYS = 5 * 366  # ~5 years, guards against unbounded series queries


def _parse_symbols(symbols: str | None, to: str | None) -> list[str] | None:
    raw = symbols or to
    if not raw:
        return None
    codes = [c.strip().upper() for c in raw.split(",") if c.strip()]
    return codes or None


def _valid_rate_type(rate_type: str) -> str:
    if rate_type not in config.RATE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"rate_type must be one of {', '.join(config.RATE_TYPES)}",
        )
    return rate_type


def _check_date(value: str) -> str:
    if not _DATE_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid date '{value}'; use YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Invalid calendar date '{value}'"
        ) from None
    return value


@app.get("/")
def index() -> dict:
    return {
        "name": "BNR Exchange Rate API",
        "description": "Official National Bank of Rwanda exchange rates, RWF-based.",
        "base": config.PIVOT,
        "provider": config.PROVIDER,
        "source": "https://www.bnr.rw/exchangeRate",
        "endpoints": ["/latest", "/{date}", "/{start}..{end}", "/currencies"],
        "docs": "/docs",
        "demo": "/demo",
        "repository": "https://github.com/RedJanvier/bnr-exchange-api",
    }


@app.get("/health")
def health() -> dict:
    dates = store.available_dates()
    return {
        "status": "ok",
        "days": len(dates),
        "earliest": dates[0] if dates else None,
        "latest": dates[-1] if dates else None,
        "currencies": len(store.get_currencies()),
    }


@app.get("/currencies")
def currencies() -> dict[str, str]:
    data = store.get_currencies()
    if not data:
        raise HTTPException(status_code=503, detail="Currency list not yet available")
    return data


@app.get("/latest")
def latest(
    base: str = Query(config.PIVOT),
    from_: str | None = Query(None, alias="from"),
    symbols: str | None = Query(None),
    to: str | None = Query(None),
    amount: float = Query(1.0, gt=0),
    rate_type: str = Query(config.DEFAULT_RATE_TYPE),
) -> dict:
    payload = store.latest_day()
    if not payload:
        raise HTTPException(status_code=503, detail="No rate data available yet")
    return _single_response(payload, base, from_, symbols, to, amount, rate_type)


@app.get("/{period}")
def by_period(
    period: str,
    base: str = Query(config.PIVOT),
    from_: str | None = Query(None, alias="from"),
    symbols: str | None = Query(None),
    to: str | None = Query(None),
    amount: float = Query(1.0, gt=0),
    rate_type: str = Query(config.DEFAULT_RATE_TYPE),
) -> dict:
    range_match = _RANGE_RE.match(period)
    if range_match:
        start, end = range_match.group(1), range_match.group(2)
        return _series_response(start, end, base, from_, symbols, to, amount, rate_type)
    if _DATE_RE.match(period):
        _check_date(period)
        payload = store.resolve_day(period)
        if not payload:
            raise HTTPException(status_code=404, detail=f"No rates for {period}")
        return _single_response(payload, base, from_, symbols, to, amount, rate_type)
    raise HTTPException(status_code=404, detail=f"Not found: /{period}")


def _single_response(payload, base, from_, symbols, to, amount, rate_type) -> dict:
    rate_type = _valid_rate_type(rate_type)
    base = (from_ or base).upper()
    try:
        return convert.build_single(payload, base, _parse_symbols(symbols, to), amount, rate_type)
    except convert.UnknownCurrency as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _series_response(start, end, base, from_, symbols, to, amount, rate_type) -> dict:
    rate_type = _valid_rate_type(rate_type)
    _check_date(start)
    _check_date(end)
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    if (date.fromisoformat(end) - date.fromisoformat(start)).days > _MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Date range too large (max ~5 years)")

    base = (from_ or base).upper()
    payloads = [store.load_day(d) for d in store.days_in_range(start, end)]
    payloads = [p for p in payloads if p]
    if not payloads:
        raise HTTPException(status_code=404, detail=f"No rates in range {start}..{end}")
    try:
        return convert.build_series(
            payloads, start, end, base, _parse_symbols(symbols, to), amount, rate_type
        )
    except convert.UnknownCurrency as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


# Static demo page (mounted last so it never shadows the API routes above).
if config.WEB_DIR.is_dir():
    app.mount("/demo", StaticFiles(directory=str(config.WEB_DIR), html=True), name="demo")
