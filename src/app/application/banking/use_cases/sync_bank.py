from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.banking.importers.base import BankImporter, make_row_hash
from app.infrastructure.database.banking.repository import BankingRepository

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    bank: str
    sources_found: int = 0
    sources_imported: int = 0
    transactions_inserted: int = 0
    errors: list[str] = field(default_factory=list)


async def sync_bank(
    importer: BankImporter, session: AsyncSession, owner_name: str = ""
) -> SyncResult:
    repo = BankingRepository(session)
    result = SyncResult(bank=importer.bank)

    existing_jobs = await repo.list_import_jobs(bank=importer.bank)
    seen_refs = {j.source_ref for j in existing_jobs}

    # Gmail API is synchronous — run in thread to not block the event loop
    sources = await asyncio.to_thread(importer.fetch_new_sources, seen_refs)
    result.sources_found = len(sources)

    for source in sources:
        try:
            # ZIP decryption + CSV parsing is also sync
            card_last4, transactions = await asyncio.to_thread(importer.parse, source)

            account = await repo.get_or_create_account(importer.bank, card_last4, owner_name)

            job = await repo.create_import_job(
                bank_account_id=account.id,
                source_type="gmail",
                source_ref=source.source_ref,
                billing_date=source.billing_date,
                row_count=len(transactions),
            )

            rows = [
                {
                    "id": uuid.uuid4(),
                    "import_job_id": job.id,
                    "bank_account_id": account.id,
                    "date": tx.date,
                    "description": tx.description,
                    "category": tx.category,
                    "amount_brl": float(tx.amount_brl),
                    "amount_usd": float(tx.amount_usd) if tx.amount_usd else None,
                    "exchange_rate": float(tx.exchange_rate) if tx.exchange_rate else None,
                    "installment_current": tx.installment_current,
                    "installment_total": tx.installment_total,
                    "row_hash": make_row_hash(importer.bank, source.billing_date, tx),
                    "raw": tx.raw,
                }
                for tx in transactions
            ]

            inserted = await repo.bulk_insert_transactions(rows)
            result.sources_imported += 1
            result.transactions_inserted += inserted

            logger.info(
                "sync_bank.imported",
                extra={
                    "bank": importer.bank,
                    "source_ref": source.source_ref,
                    "inserted": inserted,
                    "skipped": len(rows) - inserted,
                },
            )
        except Exception as exc:
            msg = f"{source.source_ref}: {exc}"
            logger.exception("sync_bank.error", extra={"bank": importer.bank, "error": msg})
            result.errors.append(msg)

    await session.commit()
    return result
