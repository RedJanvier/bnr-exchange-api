"""Test fixtures: redirect the data store to a temp dir seeded with sample data."""

from __future__ import annotations

import pytest

from app import config, store
from app.ingest import run


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """Point config at a temp data dir, seed bundled sample data, clear store caches."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "DAILY_DIR", data_dir / "daily")
    monkeypatch.setattr(config, "LATEST_FILE", data_dir / "latest.json")
    monkeypatch.setattr(config, "CURRENCIES_FILE", data_dir / "currencies.json")

    store._file_cache.clear()
    store._dates_cache = None

    run.write_currencies()
    run.run_seed()

    store._file_cache.clear()
    store._dates_cache = None
    yield data_dir
