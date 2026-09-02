"""End-to-end API tests against seeded sample data using Starlette's TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_index():
    body = client.get("/").json()
    assert body["base"] == "RWF"
    assert "/latest" in body["endpoints"]


def test_currencies(seeded):
    body = client.get("/currencies").json()
    assert body["USD"] == "US Dollar"
    assert "RWF" in body


def test_latest_default_base_rwf(seeded):
    body = client.get("/latest").json()
    assert body["base"] == "RWF"
    assert body["date"] == "2026-05-22"
    assert "USD" in body["rates"]
    assert body["rates"]["USD"] < 1  # 1 RWF is a small fraction of a USD


def test_latest_with_base_and_symbols(seeded):
    body = client.get("/latest?base=USD&symbols=EUR").json()
    assert body["base"] == "USD"
    assert set(body["rates"]) == {"EUR"}
    assert body["rates"]["EUR"] < 1  # 1 USD < 1 EUR (EUR stronger vs RWF)


def test_amount_scaling(seeded):
    one = client.get("/latest?base=USD&symbols=RWF").json()["rates"]["RWF"]
    hundred = client.get("/latest?base=USD&symbols=RWF&amount=100").json()["rates"]["RWF"]
    assert round(hundred, 2) == round(one * 100, 2)


def test_from_to_aliases(seeded):
    body = client.get("/latest?from=USD&to=EUR").json()
    assert body["base"] == "USD"
    assert set(body["rates"]) == {"EUR"}


def test_single_date_carry_forward(seeded):
    body = client.get("/2026-05-24").json()  # weekend -> carries forward to 22nd
    assert body["date"] == "2026-05-22"


def test_time_series(seeded):
    body = client.get("/2026-05-21..2026-05-22?symbols=USD").json()
    assert body["start_date"] == "2026-05-21"
    assert sorted(body["rates"]) == ["2026-05-21", "2026-05-22"]
    assert "USD" in body["rates"]["2026-05-22"]


def test_rate_type_selection(seeded):
    avg = client.get("/latest?base=USD&symbols=RWF").json()["rates"]["RWF"]
    buying = client.get("/latest?base=USD&symbols=RWF&rate_type=buying").json()["rates"]["RWF"]
    assert buying < avg  # buying rate is below the mid


def test_unknown_currency_404(seeded):
    assert client.get("/latest?base=XXX").status_code == 404


def test_bad_rate_type_422(seeded):
    assert client.get("/latest?rate_type=nonsense").status_code == 422


def test_bad_date_422(seeded):
    assert client.get("/2026-13-99").status_code == 422


def test_unknown_path_404(seeded):
    assert client.get("/not-a-date").status_code == 404


def test_health(seeded):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["days"] >= 2
