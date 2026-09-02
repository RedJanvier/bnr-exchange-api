# BNR Exchange Rate API

A free, open exchange-rate API for the **Rwandan Franc (RWF)**, sourced from the official
[National Bank of Rwanda](https://www.bnr.rw/exchangeRate) (BNR). Inspired by
[frankfurter](https://frankfurter.dev) — same ergonomics (`/latest`, dated lookups, time
series, base/symbols/amount), pointed at Rwandan data.

- **Official data** — BNR reference (mid) rates, plus buying/selling.
- **No key, no limits** — a static, cache-friendly read API.
- **Fresh daily** — a scheduled GitHub Action pulls new rates each business-day afternoon
  and commits them into the repo (the data is versioned in git).
- **Batteries included** — interactive docs at `/docs` and a demo converter at `/demo`.

> ⚠️ **Disambiguation:** "BNR" can also mean *Banca Naţională a României* (Romanian Leu).
> This project is the **Rwandan** central bank (`fxrates.bnr.rw`), serving RWF.

---

## Quick start

```sh
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000/latest   ·   /docs   ·   /demo
```

The repo ships with a small bundle of **sample** rates so everything works immediately.
Real data is populated by the scheduled job (see [Data & scheduling](#data--scheduling)).

---

## API

All responses are JSON. Default **base is `RWF`**. Rates follow the frankfurter convention:
`rates[X]` is the value of **1 unit of `base`** expressed in currency `X`.

**Query parameters** (for `/latest`, `/{date}`, and ranges):

| Param        | Alias  | Default   | Meaning                                             |
| ------------ | ------ | --------- | --------------------------------------------------- |
| `base`       | `from` | `RWF`     | Base currency.                                      |
| `symbols`    | `to`   | all       | Comma-separated target currencies.                  |
| `amount`     |        | `1`       | Amount of `base` to convert.                        |
| `rate_type`  |        | `average` | `average` (mid), `buying`, or `selling`.            |

### Endpoints

| Endpoint              | Description                                                        |
| --------------------- | ----------------------------------------------------------------- |
| `GET /latest`         | Most recently published rates.                                    |
| `GET /{YYYY-MM-DD}`   | Rates for a date. Weekends/holidays **carry forward** the last published rate (the returned `date` reflects the one used). |
| `GET /{start}..{end}` | Time series over an inclusive date range (max ~5 years).          |
| `GET /currencies`     | Supported `code → name` map.                                      |
| `GET /health`         | Dataset summary (coverage, currency count).                       |
| `GET /` · `/docs`     | Service metadata · interactive Swagger UI.                        |

### Examples

```sh
# 100 USD in RWF
curl "/latest?base=USD&symbols=RWF&amount=100"
```
```json
{ "amount": 100.0, "base": "USD", "date": "2026-05-22", "rates": { "RWF": 146335.0 } }
```

```sh
# EUR and GBP against the Franc on a specific day
curl "/2026-05-22?base=RWF&symbols=EUR,GBP"
# Time series for USD
curl "/2026-05-21..2026-05-22?symbols=USD"
```

Errors use `{"detail": "..."}` with `404` (unknown currency / no data for date) or `422`
(bad date, bad `rate_type`, oversized range).

---

## Architecture

```
GitHub Actions (cron 17:00 CAT, Mon–Fri)
  └─ python -m app.ingest.run --daily
       └─ GET fxrates.bnr.rw/currency_history  (one request per currency)
       └─ writes data/daily/YYYY/YYYY-MM-DD.json + data/latest.json
       └─ commits to the repo  ── git is the database ──┐
                                                        ▼
FastAPI (app/main.py) ── reads data/ ──▶ /latest, /{date}, ranges, /currencies, /demo, /docs
```

**Git-as-DB:** there's no database or always-on ingestion service. Rates are plain JSON files
committed to the repo; the API just reads and reshapes them. This keeps the data auditable and
versioned, and the API trivially cacheable and cheap to host (including serverless).

### Project structure

```
app/
  main.py            # FastAPI routes (frankfurter-style) + CORS + /demo mount
  store.py           # read/cache day files; 14-day carry-forward
  convert.py         # RWF-pivot cross-rate math + response shaping
  config.py          # data-store paths & constants
  ingest/
    bnr_client.py    # BNR HTTP client + parser (ported from frankfurter's bnrrw adapter)
    run.py           # CLI: --daily | --backfill | --seed  (writes data/)
    sample_data.py   # bundled illustrative rates for a zero-network start
data/
  currencies.json    # code → name
  latest.json        # newest day snapshot
  daily/2026/*.json  # one file per date: {date, provider, pivot, rates:{CODE:{buying,average,selling}}}
web/                 # static demo page (converter + rate table)
tests/               # pytest: parser, conversion/carry-forward, API
.github/workflows/   # scrape.yml (daily cron) · ci.yml (ruff + pytest)
Dockerfile · vercel.json · api/index.py
```

### Data model

BNR quotes **RWF per 1 unit** of each foreign currency; RWF is the pivot. A day file:

```json
{
  "date": "2026-05-22",
  "provider": "BNR",
  "pivot": "RWF",
  "rates": { "USD": { "buying": 1458.35, "average": 1463.35, "selling": 1468.36 }, "…": {} }
}
```

Conversion: with `r[X]` = RWF per 1 unit of X (and `r[RWF] = 1`),
`rate(base → quote) = amount × r[base] / r[quote]`.

---

## Data & scheduling

- **Source:** `https://fxrates.bnr.rw/currency_history/` — a public, unauthenticated JSON API
  (one currency per request). No scraping of HTML required.
- **Currencies (16):** USD, EUR, GBP, JPY, CHF, CAD, AUD, CNY, INR, ZAR, AED, SAR, KES, UGX,
  TZS, BIF (against RWF).
- **Cadence:** BNR publishes on **business days**, in the afternoon (~16:00–18:00 CAT). The
  `scrape.yml` cron runs **15:00 UTC = 17:00 CAT, Mon–Fri** to catch the same day's rate.
  Weekends/holidays have no new rate — the API carries the last published one forward.
- **Backfill / manual runs:** trigger the **Scrape BNR rates** workflow via
  *workflow_dispatch* → `mode: backfill` (optional `start`/`end`) to load history from
  `2026-01-01` onward. Locally: `python -m app.ingest.run --backfill --start 2026-01-01`.

> The committed `data/` starts as a small **sample** set (see `app/ingest/sample_data.py`).
> After the first `scrape` run (scheduled or dispatched), it is replaced/extended with
> authoritative BNR data.

---

## Development

```sh
pip install -r requirements-dev.txt
ruff check .        # lint
pytest              # parser, conversion, carry-forward, and API tests
python -m app.ingest.run --seed   # (re)write bundled sample data
```

The parser and its edge cases (mid = `average_rate`, thousands-comma numbers like
`"1,253.60"`, `dd-Mon-yy` dates, skipping empty/non-positive rows) are ported from — and
tested against — the reference [`lineofflight/frankfurter`](https://github.com/lineofflight/frankfurter)
`bnrrw` adapter.

## Deployment

- **Docker:** `docker build -t bnr-exchange-api . && docker run -p 8080:8080 bnr-exchange-api`.
  Data is baked into the image; redeploy to pick up newer committed rates.
- **Serverless (Vercel):** `vercel.json` + `api/index.py` serve the FastAPI app directly; the
  committed `data/` travels with the deployment. Set `BNR_DATA_DIR` if you relocate the data.
- The API is stateless and cache-friendly — front it with a CDN for near-zero cost.

## Attribution

Exchange-rate data © [National Bank of Rwanda](https://www.bnr.rw/). This is an unofficial,
community project and is not affiliated with or endorsed by BNR. Design inspired by
[frankfurter](https://frankfurter.dev).
