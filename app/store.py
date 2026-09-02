"""Read side of the git-as-DB data store: day files, carry-forward, currency names.

The API reads the JSON files written by ``app.ingest.run``. Files change only when a new
commit is deployed, so results are cached in-process and invalidated by file mtime (which
also keeps local dev correct while re-seeding).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from app import config

# path -> (mtime, parsed json)
_file_cache: dict[Path, tuple[float, dict]] = {}
# (dir mtime -> sorted list of ISO date strings that have a day file)
_dates_cache: tuple[float, list[str]] | None = None


def _read_json(path: Path) -> dict | None:
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    cached = _file_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    _file_cache[path] = (mtime, data)
    return data


def get_currencies() -> dict[str, str]:
    """Return the ``code -> name`` map (empty dict if not yet generated)."""
    return _read_json(config.CURRENCIES_FILE) or {}


def available_dates() -> list[str]:
    """Sorted list of ISO date strings that have a day file. Cached by directory mtime."""
    global _dates_cache
    try:
        mtime = config.DAILY_DIR.stat().st_mtime
    except FileNotFoundError:
        return []
    if _dates_cache and _dates_cache[0] == mtime:
        return _dates_cache[1]
    dates = sorted(p.stem for p in config.DAILY_DIR.glob("*/*.json"))
    _dates_cache = (mtime, dates)
    return dates


def load_day(day: str) -> dict | None:
    """Load the raw day payload for an exact ISO date, or None if absent."""
    return _read_json(config.day_file(day))


def resolve_day(day: str) -> dict | None:
    """Return the day payload for ``day``, carrying forward across weekends/holidays.

    If the exact date has no file, look back up to ``CARRY_FORWARD_DAYS`` for the most recent
    published date and return that (its ``date`` field reflects the date actually used).
    """
    target = date.fromisoformat(day)
    for delta in range(config.CARRY_FORWARD_DAYS + 1):
        payload = load_day((target - timedelta(days=delta)).isoformat())
        if payload:
            return payload
    return None


def latest_day() -> dict | None:
    """Most recent available day payload (prefers latest.json, falls back to a scan)."""
    payload = _read_json(config.LATEST_FILE)
    if payload:
        return payload
    dates = available_dates()
    return load_day(dates[-1]) if dates else None


def days_in_range(start: str, end: str) -> list[str]:
    """ISO dates that have a file within the inclusive ``[start, end]`` window."""
    return [d for d in available_dates() if start <= d <= end]
