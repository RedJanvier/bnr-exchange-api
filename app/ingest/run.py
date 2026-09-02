"""Ingestion CLI: fetch BNR rates and write them into the git-tracked data store.

Usage::

    python -m app.ingest.run --daily                 # refresh the last ~10 days (default)
    python -m app.ingest.run --backfill              # from DEFAULT_BACKFILL_START to today
    python -m app.ingest.run --backfill --start 2026-01-01 --end 2026-06-30
    python -m app.ingest.run --seed                  # write bundled sample data (no network)

Data is written as one JSON file per date under ``data/daily/<year>/<date>.json`` plus a
``data/latest.json`` snapshot and a ``data/currencies.json`` name map. Writes are an
**upsert**: a re-fetched date overwrites its file, so late corrections self-heal (git keeps
the history). The scheduled GitHub Action runs ``--daily`` on weekday afternoons (Kigali).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, timedelta

from app import config
from app.ingest import bnr_client
from app.ingest.bnr_client import Record
from app.ingest.sample_data import SAMPLE_RECORDS

_DAILY_LOOKBACK_DAYS = 10


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _day_payload(day: date, by_code: dict[str, Record]) -> dict:
    return {
        "date": day.isoformat(),
        "provider": config.PROVIDER,
        "pivot": config.PIVOT,
        "rates": {
            code: {
                "buying": record.buying,
                "average": record.average,
                "selling": record.selling,
            }
            for code, record in sorted(by_code.items())
        },
    }


def write_records(records: list[Record]) -> list[str]:
    """Group records by date and upsert one file per date. Returns the dates written."""
    by_date: dict[date, dict[str, Record]] = defaultdict(dict)
    for record in records:
        by_date[record.date][record.code] = record

    written: list[str] = []
    for day, by_code in sorted(by_date.items()):
        _write_json(config.day_file(day.isoformat()), _day_payload(day, by_code))
        written.append(day.isoformat())

    if written:
        _refresh_latest()
    return written


def _refresh_latest() -> None:
    """Point ``latest.json`` at the newest day file on disk."""
    day_files = sorted(config.DAILY_DIR.glob("*/*.json"))
    if not day_files:
        return
    with day_files[-1].open(encoding="utf-8") as handle:
        _write_json(config.LATEST_FILE, json.load(handle))


def write_currencies() -> None:
    """(Re)write the code -> name map for the currencies we serve."""
    codes = (config.PIVOT, *bnr_client.CURRENCIES)
    names = {code: bnr_client.CURRENCY_NAMES[code] for code in codes}
    _write_json(config.CURRENCIES_FILE, dict(sorted(names.items())))


def run_backfill(start: date, end: date) -> list[str]:
    print(f"Backfilling BNR rates {start} .. {end} for {len(bnr_client.CURRENCIES)} currencies")
    records = bnr_client.fetch_range(start, end)
    written = write_records(records)
    print(f"Wrote {len(written)} day file(s); {len(records)} records total")
    return written


def run_daily() -> list[str]:
    end = date.today()
    start = end - timedelta(days=_DAILY_LOOKBACK_DAYS)
    return run_backfill(start, end)


def run_seed() -> list[str]:
    print("Seeding bundled sample data (no network)")
    written = write_records(list(SAMPLE_RECORDS))
    print(f"Wrote {len(written)} day file(s) from sample data")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch BNR exchange rates into the data store.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--daily", action="store_true", help="refresh the last ~10 days (default)")
    mode.add_argument("--backfill", action="store_true", help="fetch a full date range")
    mode.add_argument("--seed", action="store_true", help="write bundled sample data, no network")
    parser.add_argument("--start", help="YYYY-MM-DD (backfill start; default this year)")
    parser.add_argument("--end", help="YYYY-MM-DD (backfill end; default today)")
    args = parser.parse_args(argv)

    write_currencies()

    if args.seed:
        run_seed()
    elif args.backfill:
        start = date.fromisoformat(args.start or config.DEFAULT_BACKFILL_START)
        end = date.fromisoformat(args.end) if args.end else date.today()
        run_backfill(start, end)
    else:  # default: --daily
        run_daily()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
