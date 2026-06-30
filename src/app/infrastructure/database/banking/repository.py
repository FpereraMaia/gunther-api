from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.banking.entities import BankAccount, ImportJob, Transaction
from app.infrastructure.database.banking.models import BankAccountModel, ImportJobModel, TransactionModel


class BankingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── BankAccount ───────────────────────────────────────────────────────────

    async def get_or_create_account(self, bank: str, card_last4: str, owner_name: str) -> BankAccount:
        result = await self._s.execute(
            select(BankAccountModel).where(
                BankAccountModel.bank == bank,
                BankAccountModel.card_last4 == card_last4,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = BankAccountModel(bank=bank, card_last4=card_last4, owner_name=owner_name)
            self._s.add(model)
            await self._s.flush()
            await self._s.refresh(model)
        return self._account_to_entity(model)

    async def list_accounts(self) -> list[BankAccount]:
        rows = (await self._s.execute(select(BankAccountModel).order_by(BankAccountModel.bank))).scalars()
        return [self._account_to_entity(m) for m in rows]

    # ── ImportJob ─────────────────────────────────────────────────────────────

    async def source_ref_exists(self, source_ref: str) -> bool:
        row = (await self._s.execute(
            select(ImportJobModel.id).where(ImportJobModel.source_ref == source_ref)
        )).scalar_one_or_none()
        return row is not None

    async def create_import_job(
        self,
        bank_account_id: uuid.UUID,
        source_type: str,
        source_ref: str,
        billing_date: date,
        row_count: int,
        status: str = "success",
    ) -> ImportJob:
        model = ImportJobModel(
            bank_account_id=bank_account_id,
            source_type=source_type,
            source_ref=source_ref,
            billing_date=billing_date,
            row_count=row_count,
            status=status,
        )
        self._s.add(model)
        await self._s.flush()
        await self._s.refresh(model)
        return self._job_to_entity(model)

    async def list_import_jobs(self, bank: str | None = None) -> list[ImportJob]:
        q = select(ImportJobModel).join(BankAccountModel)
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        rows = (await self._s.execute(q.order_by(ImportJobModel.billing_date.desc()))).scalars()
        return [self._job_to_entity(m) for m in rows]

    # ── Transaction ───────────────────────────────────────────────────────────

    async def bulk_insert_transactions(self, rows: list[dict]) -> int:
        """Insert rows, skipping duplicates by row_hash. Returns inserted count."""
        if not rows:
            return 0
        stmt = insert(TransactionModel).values(rows).on_conflict_do_nothing(index_elements=["row_hash"])
        result = await self._s.execute(stmt)
        return result.rowcount

    async def list_transactions(
        self,
        bank: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        category: str | None = None,
        card_last4: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Transaction], int]:
        from sqlalchemy import func as sqlfunc

        q = select(TransactionModel).join(BankAccountModel)
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        if card_last4:
            q = q.where(BankAccountModel.card_last4 == card_last4)
        if from_date:
            q = q.where(TransactionModel.date >= from_date)
        if to_date:
            q = q.where(TransactionModel.date <= to_date)
        if category:
            q = q.where(TransactionModel.category == category)

        total = (await self._s.execute(
            select(sqlfunc.count()).select_from(q.subquery())
        )).scalar_one()

        rows = (await self._s.execute(
            q.order_by(TransactionModel.date.desc()).offset(offset).limit(limit)
        )).scalars()
        return [self._tx_to_entity(m) for m in rows], total

    async def get_summary(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        bank: str | None = None,
    ) -> list[dict]:
        from sqlalchemy import func as sqlfunc

        q = (
            select(
                BankAccountModel.bank,
                TransactionModel.category,
                sqlfunc.sum(TransactionModel.amount_brl).label("total"),
                sqlfunc.count(TransactionModel.id).label("count"),
            )
            .join(BankAccountModel)
            .where(TransactionModel.amount_brl > 0)
            .group_by(BankAccountModel.bank, TransactionModel.category)
            .order_by(sqlfunc.sum(TransactionModel.amount_brl).desc())
        )
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        if from_date:
            q = q.where(TransactionModel.date >= from_date)
        if to_date:
            q = q.where(TransactionModel.date <= to_date)

        rows = (await self._s.execute(q)).all()
        return [{"bank": r.bank, "category": r.category, "total": float(r.total), "count": r.count} for r in rows]

    # ── Converters ────────────────────────────────────────────────────────────

    @staticmethod
    def _account_to_entity(m: BankAccountModel) -> BankAccount:
        return BankAccount(
            id=m.id, bank=m.bank, account_type=m.account_type,
            card_last4=m.card_last4, owner_name=m.owner_name,
            created_at=m.created_at, updated_at=m.updated_at,
        )

    @staticmethod
    def _job_to_entity(m: ImportJobModel) -> ImportJob:
        return ImportJob(
            id=m.id, bank_account_id=m.bank_account_id,
            source_type=m.source_type, source_ref=m.source_ref,
            billing_date=m.billing_date, row_count=m.row_count,
            status=m.status, imported_at=m.imported_at,
            created_at=m.created_at, updated_at=m.updated_at,
        )

    @staticmethod
    def _tx_to_entity(m: TransactionModel) -> Transaction:
        return Transaction(
            id=m.id, import_job_id=m.import_job_id, bank_account_id=m.bank_account_id,
            date=m.date, description=m.description, category=m.category,
            amount_brl=Decimal(str(m.amount_brl)),
            amount_usd=Decimal(str(m.amount_usd)) if m.amount_usd else None,
            exchange_rate=Decimal(str(m.exchange_rate)) if m.exchange_rate else None,
            installment_current=m.installment_current, installment_total=m.installment_total,
            row_hash=m.row_hash, raw=m.raw,
            created_at=m.created_at, updated_at=m.updated_at,
        )
