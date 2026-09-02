"""Shared paths and constants for the data store (git-as-DB layout)."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = parent of the ``app`` package. Overridable via BNR_DATA_DIR for tests/deploys.
_REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BNR_DATA_DIR", _REPO_ROOT / "data"))
DAILY_DIR = DATA_DIR / "daily"
LATEST_FILE = DATA_DIR / "latest.json"
CURRENCIES_FILE = DATA_DIR / "currencies.json"

WEB_DIR = _REPO_ROOT / "web"

PROVIDER = "BNR"
PIVOT = "RWF"

# Backfill start for this project. History is available earlier (~2012) but the brief is
# "from the start of this year".
DEFAULT_BACKFILL_START = "2026-01-01"

# How many days back the API scans to carry a rate forward across weekends/holidays.
CARRY_FORWARD_DAYS = 14

# Supported rate types in a day file's per-currency object; the API default is "average".
RATE_TYPES = ("buying", "average", "selling")
DEFAULT_RATE_TYPE = "average"


def day_file(day: str) -> Path:
    """Path to the JSON file for an ISO date string ``YYYY-MM-DD`` (bucketed by year)."""
    year = day[:4]
    return DAILY_DIR / year / f"{day}.json"
