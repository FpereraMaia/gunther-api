# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This project was generated from the `octopus` python-web boilerplate. For common patterns (commands, Clean Architecture layers, middleware, exception hierarchy, testing strategy, deployment modes) refer to the boilerplate CLAUDE.md at `boilerplates/python-web/{{cookiecutter.service_name}}/CLAUDE.md`. This file covers only what is specific to gunther_api.

## What this service does

Gunther is a personal finance API. Its primary function is importing bank transactions from Gmail attachments and exposing them for analysis. Supported banks: **C6** (AES-encrypted ZIP → CSV, credit card only) and **Nubank** (plain CSV, both credit card invoice and checking-account extract).

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
- `infrastructure/banking/importers/nubank.py` — `NubankImporter`: fetches credit card invoice CSV from Gmail (`Nubank_YYYY-MM-DD.csv`), applies regex categorizer
- `infrastructure/banking/importers/nubank_account.py` — `NubankAccountImporter`: fetches checking-account extract CSV from Gmail (`NU_<account>_<start>_<end>.csv`); same sender/search as the invoice importer, so it filters by filename pattern instead of a separate query
- `infrastructure/banking/gmail/client.py` — `GmailClient`: wraps googleapis (synchronous); caller must use `asyncio.to_thread()` to avoid blocking
- `infrastructure/database/banking/repository.py` — `BankingRepository`: all DB ops (accounts, import jobs, transactions, summaries)
- `application/banking/use_cases/sync_bank.py` — `sync_bank()` function (not a class): orchestrates fetch → parse → upsert

The Gmail API client is synchronous (googleapis limitation). `sync_bank` wraps both `fetch_new_sources` and `parse` in `asyncio.to_thread()`.

**Skipping the `IBankingRepository` Protocol does not mean skipping the repository.** All SQLAlchemy access — `select()`/`update()`/ORM model imports — must live in `BankingRepository`. Routers (`presentation/api/v1/banking/router.py`) and use cases (`application/banking/use_cases/*.py`) call repository methods only; they must never import `infrastructure.database.banking.models` or build queries with `session.execute()` directly. If a repository method doesn't exist yet for what a caller needs, add it to `BankingRepository` rather than querying inline. (This was violated twice in practice — raw queries in router GET handlers and in `backfill_categories.py` — before being fixed by moving the logic into repository methods.)

Import convention in this router: top-level imports by default. The only justified exception is deferring imports of the Gmail/importer stack (`GmailClient`, `C6Importer`, `NubankImporter`) inside their factory functions — they pull in heavy optional deps (`googleapiclient`, `google-auth`, `pyzipper`) that non-sync endpoints shouldn't pay for. Don't add new local imports for anything else without that same justification.

## Deduplication

Transactions are deduplicated via `row_hash` — a SHA-256 of `(bank, billing_date, tx_date, description, amount_brl_cents, installment_current, installment_total)`. `bulk_insert_transactions` uses PostgreSQL `INSERT ... ON CONFLICT (row_hash) DO NOTHING` and returns the actual inserted count. Re-syncing the same Gmail messages is safe.

If a source provides a stable per-transaction id (`ParsedTransaction.external_id`), `make_row_hash` uses that instead of the composite key. This matters for the Nubank account extract: the user can export overlapping date ranges (e.g. re-download "this month" after already importing "this year"), and the same transaction would get a different `billing_date` each time, defeating the composite-key hash. The extract CSV's `Identificador` column is used as `external_id` for exactly this reason. C6 and the Nubank invoice CSV have no such id, so they still use the composite key.

Nubank account accounts are also distinguished from the credit card account by `card_last4`: the invoice importer never exposes one (`card_last4 == ""`), so `NubankAccountImporter` uses the account number parsed from the filename instead — otherwise both would collide on `get_or_create_account("nubank", "", ...)` and merge into one `bank_accounts` row with the wrong `account_type`.

The extract CSV reports incoming money as positive and outgoing as negative. That's the opposite of the "positive = spend" convention `get_summary`/`get_summary_by_description` rely on (`WHERE amount_brl > 0`), so `NubankAccountImporter` flips the sign at parse time. One consequence: "Pagamento de fatura" (paying the Nubank credit card bill from the checking account) shows up as spend under this convention even though the actual purchases are already counted via the credit card import — it's tagged with its own `Pagamento de Fatura` category (rather than the generic `Transferência / Pix` bucket) specifically so it can be filtered out of spend totals in the UI.

## Banking API endpoints

All endpoints require authentication (`Depends(get_user)` via Authentik headers).

```
POST /api/v1/banking/sync?bank=all|c6|nubank|nubank_account   — import new statements from Gmail
POST /api/v1/banking/backfill-categories        — fill null categories on Nubank rows
GET  /api/v1/banking/accounts                  — list bank accounts
GET  /api/v1/banking/statements?bank=          — list import jobs
GET  /api/v1/banking/transactions              — paginated transactions (filter: bank, account_type, card_last4, from_date, to_date, category)
GET  /api/v1/banking/transactions/{id}         — single transaction with full audit trail (raw CSV row, row_hash, import job, account)
GET  /api/v1/banking/summary                   — spend by (bank, category) (filter: bank, account_type, from_date, to_date)
GET  /api/v1/banking/summary/by-description    — spend grouped by merchant description (same filters, plus category, min_total)
GET  /api/v1/banking/summary/spend-vs-transfers — spend by category, with transfers (see below) split out as a separate total instead of mixed in
GET  /api/v1/banking/cash-flow                 — income vs. expense vs. net, grouped by month (filter: bank, account_type, from_date, to_date)
```

`nubank_account` is only a sync-selector key, not a stored `bank` value — both Nubank importers write `bank="nubank"`, so `GET` endpoints' `bank=nubank` filter returns both credit card and checking-account rows together; use `account_type=checking|credit_card` to split them.

`summary/spend-vs-transfers` and `cash-flow` exist because the checking-account import (see above) mixes real spend with money that just moved between the user's own accounts (Pix transfers, paying the Nubank card bill) — without separating them, "how much did I spend" numbers get inflated. `TRANSFER_CATEGORIES` in `categorizer.py` (`Transferência / Pix`, `Pagamento de Fatura`) is the single source of truth for what counts as a transfer; `cash-flow`'s income/expense split does not use it (it's driven by amount sign, not category) since it's answering a different question ("money in vs. out") than spend-vs-transfers ("real spend vs. self-transfers").

## Categorization

`infrastructure/banking/importers/categorizer.py` contains a rule list of `(regex_pattern, category_string)` pairs matched against transaction descriptions. Rules are matched in order; first match wins. Nubank transactions are categorized at parse time; C6 uses the category column from CSV when present. `backfill-categories` retroactively applies the rules to Nubank rows with `category IS NULL`.

When adding new rules, insert them before generic rules that might shadow them (e.g., add a specific restaurant before the generic `restaurante` pattern).

## Unimplemented stubs

- **`POST /api/v1/auth/token`** — raises `NotImplementedError`. To wire it: scaffold the `User` domain and inject `UserRepository` into `LoginUseCase` in `presentation/api/v1/auth/router.py:_get_login_use_case`.
- **`GET /api/v1/finance/cash-on-hand`** — returns hardcoded BRL balances. Real implementation would aggregate from bank accounts or an external source.
