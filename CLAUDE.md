# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This project was generated from the `octopus` python-web boilerplate. For common patterns (commands, Clean Architecture layers, middleware, exception hierarchy, testing strategy, deployment modes) refer to the boilerplate CLAUDE.md at `boilerplates/python-web/{{cookiecutter.service_name}}/CLAUDE.md`. This file covers only what is specific to gunther_api.

## What this service does

Gunther is a personal finance API. Its primary function is importing bank transactions from Gmail attachments and exposing them for analysis. Supported banks: **C6** (AES-encrypted ZIP → CSV) and **Nubank** (plain CSV).

## Implemented domains

| Domain | Status | Notes |
|---|---|---|
| `banking` | Active | Core feature — Gmail import, transactions, accounts |
| `finance` | Stub | `GET /api/v1/finance/cash-on-hand` returns hardcoded mock data |
| `auth` | Stub | `POST /api/v1/auth/token` raises `NotImplementedError` — User domain not yet scaffolded |

## Gmail / OAuth2 setup (one-time)

The Gmail API uses OAuth2 with credentials stored locally. Before the sync endpoint works, run the auth flow once:

```bash
# Download credentials.json from Google Cloud Console (OAuth 2.0 desktop client)
# Set GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH in .env, then:
PYTHONPATH=src uv run python -c "
from app.shared.config import settings
from app.infrastructure.banking.gmail.client import GmailClient
GmailClient(settings.gmail_credentials_path, settings.gmail_token_path).authorize()
"
```

This opens a browser, completes the OAuth flow, and writes `token.json`. After that, the token auto-refreshes. The token path must be writable by the app container.

## Banking-specific config

Beyond the standard boilerplate config, `.env` requires:

```
GMAIL_CREDENTIALS_PATH=/path/to/credentials.json
GMAIL_TOKEN_PATH=/path/to/token.json
C6_ZIP_PASSWORD=<first 6 digits of CPF>   # C6 encrypts ZIPs with CPF prefix
```

`C6_GMAIL_SENDER` and `NUBANK_GMAIL_SENDER` have correct defaults and rarely need changing.

## Banking architecture

The banking feature does not follow the standard Clean Architecture repository pattern from the boilerplate — there is no `IBankingRepository` Protocol. Instead:

- `infrastructure/banking/importers/base.py` — defines the `BankImporter` Protocol and `ParsedTransaction`/`RawSource` dataclasses
- `infrastructure/banking/importers/c6.py` — `C6Importer`: fetches ZIP from Gmail, decrypts with `pyzipper`, parses semicolon-delimited CSV
- `infrastructure/banking/importers/nubank.py` — `NubankImporter`: fetches CSV from Gmail, applies regex categorizer
- `infrastructure/banking/gmail/client.py` — `GmailClient`: wraps googleapis (synchronous); caller must use `asyncio.to_thread()` to avoid blocking
- `infrastructure/database/banking/repository.py` — `BankingRepository`: all DB ops (accounts, import jobs, transactions, summaries)
- `application/banking/use_cases/sync_bank.py` — `sync_bank()` function (not a class): orchestrates fetch → parse → upsert

The Gmail API client is synchronous (googleapis limitation). `sync_bank` wraps both `fetch_new_sources` and `parse` in `asyncio.to_thread()`.

## Deduplication

Transactions are deduplicated via `row_hash` — a SHA-256 of `(bank, billing_date, tx_date, description, amount_brl_cents, installment_current, installment_total)`. `bulk_insert_transactions` uses PostgreSQL `INSERT ... ON CONFLICT (row_hash) DO NOTHING` and returns the actual inserted count. Re-syncing the same Gmail messages is safe.

## Banking API endpoints

All endpoints require authentication (`Depends(get_user)` via Authentik headers).

```
POST /api/v1/banking/sync?bank=all|c6|nubank   — import new statements from Gmail
POST /api/v1/banking/backfill-categories        — fill null categories on Nubank rows
GET  /api/v1/banking/accounts                  — list bank accounts
GET  /api/v1/banking/statements?bank=          — list import jobs
GET  /api/v1/banking/transactions              — paginated transactions (filter: bank, card_last4, from_date, to_date, category)
GET  /api/v1/banking/summary                   — spend by (bank, category)
GET  /api/v1/banking/summary/by-description    — spend grouped by merchant description
```

## Categorization

`infrastructure/banking/importers/categorizer.py` contains a rule list of `(regex_pattern, category_string)` pairs matched against transaction descriptions. Rules are matched in order; first match wins. Nubank transactions are categorized at parse time; C6 uses the category column from CSV when present. `backfill-categories` retroactively applies the rules to Nubank rows with `category IS NULL`.

When adding new rules, insert them before generic rules that might shadow them (e.g., add a specific restaurant before the generic `restaurante` pattern).

## Unimplemented stubs

- **`POST /api/v1/auth/token`** — raises `NotImplementedError`. To wire it: scaffold the `User` domain and inject `UserRepository` into `LoginUseCase` in `presentation/api/v1/auth/router.py:_get_login_use_case`.
- **`GET /api/v1/finance/cash-on-hand`** — returns hardcoded BRL balances. Real implementation would aggregate from bank accounts or an external source.
