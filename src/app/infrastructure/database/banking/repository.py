from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import CursorResult, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.banking.entities import BankAccount, ImportJob, Transaction, TransactionDetail
from app.infrastructure.banking.importers.categorizer import TRANSFER_CATEGORIES
from app.infrastructure.database.banking.models import (
    BankAccountModel,
    ImportJobModel,
    TransactionModel,
)


class BankingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── BankAccount ───────────────────────────────────────────────────────────

    async def get_or_create_account(
        self,
        bank: str,
        card_last4: str,
        owner_name: str,
        account_type: str = "credit_card",
    ) -> BankAccount:
        result = await self._s.execute(
            select(BankAccountModel).where(
                BankAccountModel.bank == bank,
                BankAccountModel.card_last4 == card_last4,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = BankAccountModel(
                bank=bank, card_last4=card_last4, owner_name=owner_name, account_type=account_type
            )
            self._s.add(model)
            await self._s.flush()
            await self._s.refresh(model)
        return self._account_to_entity(model)

    async def list_accounts(self) -> list[BankAccount]:
        rows = (
            await self._s.execute(select(BankAccountModel).order_by(BankAccountModel.bank))
        ).scalars()
        return [self._account_to_entity(m) for m in rows]

    async def list_accounts_by_ids(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, BankAccount]:
        if not ids:
            return {}
        rows = (
            await self._s.execute(select(BankAccountModel).where(BankAccountModel.id.in_(ids)))
        ).scalars()
        return {m.id: self._account_to_entity(m) for m in rows}

    # ── ImportJob ─────────────────────────────────────────────────────────────

    async def source_ref_exists(self, source_ref: str) -> bool:
        row = (
            await self._s.execute(
                select(ImportJobModel.id).where(ImportJobModel.source_ref == source_ref)
            )
        ).scalar_one_or_none()
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

    async def list_import_jobs_with_bank(
        self, bank: str | None = None
    ) -> list[tuple[ImportJob, str]]:
        q = select(ImportJobModel, BankAccountModel.bank).join(BankAccountModel)
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        q = q.order_by(ImportJobModel.billing_date.desc())
        rows = (await self._s.execute(q)).all()
        return [(self._job_to_entity(row.ImportJobModel), row.bank) for row in rows]

    # ── Transaction ───────────────────────────────────────────────────────────

    async def bulk_insert_transactions(self, rows: list[dict[str, Any]]) -> int:
        """Insert rows, skipping duplicates by row_hash. Returns inserted count."""
        if not rows:
            return 0
        stmt = (
            insert(TransactionModel)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["row_hash"])
        )
        result = cast(CursorResult[Any], await self._s.execute(stmt))
        return result.rowcount

    async def list_uncategorized_transactions(self, bank: str) -> list[tuple[uuid.UUID, str]]:
        rows = (
            await self._s.execute(
                select(TransactionModel.id, TransactionModel.description)
                .join(BankAccountModel)
                .where(BankAccountModel.bank == bank)
                .where(TransactionModel.category.is_(None))
            )
        ).all()
        return [(r.id, r.description) for r in rows]

    async def update_transaction_category(self, transaction_id: uuid.UUID, category: str) -> None:
        await self._s.execute(
            update(TransactionModel)
            .where(TransactionModel.id == transaction_id)
            .values(category=category)
        )

    async def list_transactions(
        self,
        bank: str | None = None,
        account_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        category: str | None = None,
        card_last4: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Transaction], int]:
        q = select(TransactionModel).join(BankAccountModel)
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        if account_type:
            q = q.where(BankAccountModel.account_type == account_type)
        if card_last4:
            q = q.where(BankAccountModel.card_last4 == card_last4)
        if from_date:
            q = q.where(TransactionModel.date >= from_date)
        if to_date:
            q = q.where(TransactionModel.date <= to_date)
        if category:
            q = q.where(TransactionModel.category == category)

        total = (await self._s.execute(select(func.count()).select_from(q.subquery()))).scalar_one()

        rows = (
            await self._s.execute(
                q.order_by(TransactionModel.date.desc()).offset(offset).limit(limit)
            )
        ).scalars()
        return [self._tx_to_entity(m) for m in rows], total

    async def get_summary(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        bank: str | None = None,
        account_type: str | None = None,
    ) -> list[dict[str, Any]]:
        q = (
            select(
                BankAccountModel.bank,
                TransactionModel.category,
                func.sum(TransactionModel.amount_brl).label("total"),
                func.count(TransactionModel.id).label("tx_count"),
            )
            .join(BankAccountModel)
            .where(TransactionModel.amount_brl > 0)
            .group_by(BankAccountModel.bank, TransactionModel.category)
            .order_by(func.sum(TransactionModel.amount_brl).desc())
        )
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        if account_type:
            q = q.where(BankAccountModel.account_type == account_type)
        if from_date:
            q = q.where(TransactionModel.date >= from_date)
        if to_date:
            q = q.where(TransactionModel.date <= to_date)

        rows = (await self._s.execute(q)).all()
        return [
            {"bank": r.bank, "category": r.category, "total": float(r.total), "count": r.tx_count}
            for r in rows
        ]

    async def get_summary_by_description(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        bank: str | None = None,
        account_type: str | None = None,
        category: str | None = None,
        min_total: float | None = None,
    ) -> list[dict[str, Any]]:
        q = (
            select(
                BankAccountModel.bank,
                TransactionModel.description,
                TransactionModel.category,
                func.sum(TransactionModel.amount_brl).label("total"),
                func.count(TransactionModel.id).label("tx_count"),
            )
            .join(BankAccountModel)
            .where(TransactionModel.amount_brl > 0)
            .group_by(
                BankAccountModel.bank, TransactionModel.description, TransactionModel.category
            )
            .order_by(func.sum(TransactionModel.amount_brl).desc())
        )
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        if account_type:
            q = q.where(BankAccountModel.account_type == account_type)
        if category:
            q = q.where(TransactionModel.category == category)
        if from_date:
            q = q.where(TransactionModel.date >= from_date)
        if to_date:
            q = q.where(TransactionModel.date <= to_date)
        if min_total:
            q = q.having(func.sum(TransactionModel.amount_brl) >= min_total)

        rows = (await self._s.execute(q)).all()
        return [
            {
                "bank": r.bank,
                "description": r.description,
                "category": r.category,
                "total": round(float(r.total), 2),
                "count": r.tx_count,
            }
            for r in rows
        ]

    async def get_monthly_cash_flow(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        bank: str | None = None,
        account_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Income vs. expense per month (positive amount_brl = spend convention)."""
        month = func.date_trunc("month", TransactionModel.date).label("month")
        q = (
            select(
                month,
                func.sum(func.greatest(TransactionModel.amount_brl, 0)).label("expense"),
                func.sum(func.greatest(-TransactionModel.amount_brl, 0)).label("income"),
                func.count(TransactionModel.id).label("tx_count"),
            )
            .join(BankAccountModel)
            .group_by(month)
            .order_by(month)
        )
        if bank:
            q = q.where(BankAccountModel.bank == bank)
        if account_type:
            q = q.where(BankAccountModel.account_type == account_type)
        if from_date:
            q = q.where(TransactionModel.date >= from_date)
        if to_date:
            q = q.where(TransactionModel.date <= to_date)

        rows = (await self._s.execute(q)).all()
        return [
            {
                "month": r.month.date(),
                "income": round(float(r.income), 2),
                "expense": round(float(r.expense), 2),
                "net": round(float(r.income) - float(r.expense), 2),
                "count": r.tx_count,
            }
            for r in rows
        ]

    async def get_spend_vs_transfers(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        bank: str | None = None,
        account_type: str | None = None,
    ) -> dict[str, Any]:
        """Splits real spend from transfers (see `TRANSFER_CATEGORIES`)."""
        not_transfer = or_(
            TransactionModel.category.is_(None),
            TransactionModel.category.notin_(TRANSFER_CATEGORIES),
        )

        def _apply_filters(q: Any) -> Any:
            if bank:
                q = q.where(BankAccountModel.bank == bank)
            if account_type:
                q = q.where(BankAccountModel.account_type == account_type)
            if from_date:
                q = q.where(TransactionModel.date >= from_date)
            if to_date:
                q = q.where(TransactionModel.date <= to_date)
            return q

        category_q = _apply_filters(
            select(
                TransactionModel.category,
                func.sum(TransactionModel.amount_brl).label("total"),
                func.count(TransactionModel.id).label("tx_count"),
            )
            .join(BankAccountModel)
            .where(TransactionModel.amount_brl > 0)
            .where(not_transfer)
            .group_by(TransactionModel.category)
            .order_by(func.sum(TransactionModel.amount_brl).desc())
        )
        by_category = [
            {"category": r.category, "total": round(float(r.total), 2), "count": r.tx_count}
            for r in (await self._s.execute(category_q)).all()
        ]

        transfer_q = _apply_filters(
            select(
                func.coalesce(func.sum(TransactionModel.amount_brl), 0).label("total"),
                func.count(TransactionModel.id).label("tx_count"),
            )
            .join(BankAccountModel)
            .where(TransactionModel.amount_brl > 0)
            .where(TransactionModel.category.in_(TRANSFER_CATEGORIES))
        )
        transfer_row = (await self._s.execute(transfer_q)).one()

        return {
            "spend_total": round(sum(c["total"] for c in by_category), 2),
            "spend_count": sum(c["count"] for c in by_category),
            "transfer_total": round(float(transfer_row.total), 2),
            "transfer_count": transfer_row.tx_count,
            "by_category": by_category,
        }

    async def get_transaction_detail(self, transaction_id: uuid.UUID) -> TransactionDetail | None:
        row = (
            await self._s.execute(
                select(TransactionModel, ImportJobModel, BankAccountModel)
                .join(ImportJobModel, TransactionModel.import_job_id == ImportJobModel.id)
                .join(BankAccountModel, TransactionModel.bank_account_id == BankAccountModel.id)
                .where(TransactionModel.id == transaction_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return TransactionDetail(
            transaction=self._tx_to_entity(row.TransactionModel),
            account=self._account_to_entity(row.BankAccountModel),
            import_job=self._job_to_entity(row.ImportJobModel),
        )

    # ── Converters ────────────────────────────────────────────────────────────

    @staticmethod
    def _account_to_entity(m: BankAccountModel) -> BankAccount:
        return BankAccount(
            id=m.id,
            bank=m.bank,
            account_type=m.account_type,
            card_last4=m.card_last4,
            owner_name=m.owner_name,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _job_to_entity(m: ImportJobModel) -> ImportJob:
        return ImportJob(
            id=m.id,
            bank_account_id=m.bank_account_id,
            source_type=m.source_type,
            source_ref=m.source_ref,
            billing_date=m.billing_date,
            row_count=m.row_count,
            status=m.status,
            imported_at=m.imported_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    @staticmethod
    def _tx_to_entity(m: TransactionModel) -> Transaction:
        return Transaction(
            id=m.id,
            import_job_id=m.import_job_id,
            bank_account_id=m.bank_account_id,
            date=m.date,
            description=m.description,
            category=m.category,
            amount_brl=Decimal(str(m.amount_brl)),
            amount_usd=Decimal(str(m.amount_usd)) if m.amount_usd else None,
            exchange_rate=Decimal(str(m.exchange_rate)) if m.exchange_rate else None,
            installment_current=m.installment_current,
            installment_total=m.installment_total,
            row_hash=m.row_hash,
            raw=m.raw,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
