"""Client for the National Bank of Rwanda (BNR) public exchange-rate API.

Data source: https://fxrates.bnr.rw/currency_history/ — a public, unauthenticated
JSON endpoint that serves daily reference rates for a fixed set of currencies against
the Rwandan Franc (RWF). RWF is the pivot: every published value is *RWF per 1 unit of
the foreign currency*.

The parse logic here mirrors the (battle-tested) adapter in the open-source
``lineofflight/frankfurter`` project (``lib/provider/adapters/bnrrw.rb``), including its
handling of the endpoint's quirks:

* numeric fields arrive as **strings**;
* older values carry **thousands separators** (e.g. ``"1,253.60"``);
* ``post_date`` uses a two-digit year in ``%d-%b-%y`` form (e.g. ``"22-May-26"``);
* the array is **not** sorted by date;
* ``buying_rate`` / ``average_rate`` / ``selling_rate`` are published — ``average_rate``
  is the mid/reference rate.

The endpoint serves **one currency per request**, so a full pull iterates the currency
list. It requires no API key. "BNR" also denotes Banca Naţională a României (RON); this
is the *Rwandan* bank — do not confuse the two.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime

import httpx

BASE_URL = "https://fxrates.bnr.rw/currency_history/"

# Foreign currencies served by BNR, verified against the live endpoint by the frankfurter
# project. SDR/XDR returns no data and is omitted. Extend cautiously — probe first and keep
# only codes that return records.
CURRENCIES: tuple[str, ...] = (
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY",
    "INR", "ZAR", "AED", "SAR", "KES", "UGX", "TZS", "BIF",
)

# Human-readable names for the currencies we serve (plus the RWF pivot). Bundled to avoid a
# heavy dependency on a full ISO-4217 library for ~17 codes.
CURRENCY_NAMES: dict[str, str] = {
    "RWF": "Rwandan Franc",
    "USD": "US Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CHF": "Swiss Franc",
    "CAD": "Canadian Dollar",
    "AUD": "Australian Dollar",
    "CNY": "Chinese Yuan",
    "INR": "Indian Rupee",
    "ZAR": "South African Rand",
    "AED": "UAE Dirham",
    "SAR": "Saudi Riyal",
    "KES": "Kenyan Shilling",
    "UGX": "Ugandan Shilling",
    "TZS": "Tanzanian Shilling",
    "BIF": "Burundian Franc",
}

# A realistic browser UA — the endpoint is fronted by Cloudflare. Polite pacing between the
# per-currency requests, matching the reference implementation.
_USER_AGENT = (
    "Mozilla/5.0 (compatible; bnr-exchange-api/1.0; "
    "+https://github.com/RedJanvier/bnr-exchange-api)"
)
_REQUEST_GAP_SECONDS = 0.3
_CODE_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class Record:
    """One currency's rates for one date, as published by BNR (RWF per 1 unit)."""

    code: str
    date: date
    buying: float
    average: float  # the mid / reference rate
    selling: float


def _to_float(value: object) -> float | None:
    """Parse a BNR numeric string, stripping thousands commas. Returns None if unusable."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_date(value: object) -> date | None:
    """Parse a ``%d-%b-%y`` post_date (e.g. ``"22-May-26"``)."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%d-%b-%y").date()
    except (TypeError, ValueError):
        return None


def parse(payload: list[dict]) -> list[Record]:
    """Turn a raw ``currency_history`` JSON array into validated :class:`Record` rows.

    Mirrors the frankfurter adapter: validate the 3-letter code, require a positive
    ``average_rate`` (mid), strip thousands commas, and parse the ``%d-%b-%y`` date.
    Entries failing any check are skipped rather than raising, so one bad row never
    discards a whole response.
    """
    if not isinstance(payload, list):
        raise ValueError(
            f"BNR: expected a JSON array from currency_history, got {type(payload).__name__}"
        )

    records: list[Record] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        code = entry.get("currency_name")
        if not (isinstance(code, str) and _CODE_RE.match(code)):
            continue

        average = _to_float(entry.get("average_rate"))
        if average is None or average <= 0:
            continue

        parsed_date = _parse_date(entry.get("post_date"))
        if parsed_date is None:
            continue

        # buying/selling are best-effort extras; fall back to the mid when absent/unusable.
        buying = _to_float(entry.get("buying_rate"))
        selling = _to_float(entry.get("selling_rate"))
        records.append(
            Record(
                code=code,
                date=parsed_date,
                buying=buying if buying and buying > 0 else average,
                average=average,
                selling=selling if selling and selling > 0 else average,
            )
        )
    return records


def fetch_currency(
    client: httpx.Client, code: str, start: date, end: date
) -> list[Record]:
    """Fetch and parse one currency's history over ``[start, end]``."""
    response = client.get(
        BASE_URL,
        params={
            "currency_name": code,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
        },
    )
    response.raise_for_status()
    return parse(response.json())


def fetch_range(
    start: date,
    end: date,
    currencies: tuple[str, ...] = CURRENCIES,
    *,
    client: httpx.Client | None = None,
) -> list[Record]:
    """Fetch every currency over ``[start, end]``, one request per currency.

    Retries transient Cloudflare/network errors with a short backoff. A caller may pass an
    existing ``httpx.Client`` (e.g. tests); otherwise one is created and closed here.
    """
    owns_client = client is None
    client = client or httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0),
        follow_redirects=True,
    )
    records: list[Record] = []
    try:
        for index, code in enumerate(currencies):
            if index:
                time.sleep(_REQUEST_GAP_SECONDS)
            records.extend(_fetch_currency_with_retry(client, code, start, end))
    finally:
        if owns_client:
            client.close()
    return records


def _fetch_currency_with_retry(
    client: httpx.Client, code: str, start: date, end: date, attempts: int = 4
) -> list[Record]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetch_currency(client, code, start, end)
        except (httpx.HTTPError, ValueError) as error:  # network, 5xx, malformed JSON
            last_error = error
            if attempt < attempts - 1:
                time.sleep(2**attempt)  # 1s, 2s, 4s
    raise RuntimeError(f"BNR: failed to fetch {code} after {attempts} attempts") from last_error
