"""create_banking_tables

Revision ID: 31d4648b0fd2
Revises:
Create Date: 2026-06-30 03:48:28.222475

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '31d4648b0fd2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'items',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'bank_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('bank', sa.String(length=50), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=False, server_default='credit_card'),
        sa.Column('card_last4', sa.String(length=10), nullable=False, server_default=''),
        sa.Column('owner_name', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bank', 'card_last4', name='uq_bank_accounts_bank_card'),
    )

    op.create_table(
        'import_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('bank_account_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_ref', sa.String(length=512), nullable=False),
        sa.Column('billing_date', sa.Date(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='success'),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_ref'),
    )

    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('import_job_id', sa.UUID(), nullable=False),
        sa.Column('bank_account_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=False),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('amount_brl', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('amount_usd', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('exchange_rate', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('installment_current', sa.Integer(), nullable=True),
        sa.Column('installment_total', sa.Integer(), nullable=True),
        sa.Column('row_hash', sa.String(length=64), nullable=False),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bank_account_id'], ['bank_accounts.id']),
        sa.ForeignKeyConstraint(['import_job_id'], ['import_jobs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('row_hash'),
    )
    op.create_index('ix_transactions_date', 'transactions', ['date'])
    op.create_index('ix_transactions_category', 'transactions', ['category'])
    op.create_index('ix_transactions_bank_account_id', 'transactions', ['bank_account_id'])


def downgrade() -> None:
    op.drop_index('ix_transactions_bank_account_id', table_name='transactions')
    op.drop_index('ix_transactions_category', table_name='transactions')
    op.drop_index('ix_transactions_date', table_name='transactions')
    op.drop_table('transactions')
    op.drop_table('import_jobs')
    op.drop_table('bank_accounts')
    op.drop_table('items')
