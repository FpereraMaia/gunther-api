"""Quick smoke test for Gmail fetch + CSV parsing. Run from project root:
    python scripts/test_sync.py
"""
import asyncio
import sys

sys.path.insert(0, "src")

from app.infrastructure.banking.gmail.client import GmailClient
from app.infrastructure.banking.importers.c6 import C6Importer
from app.infrastructure.banking.importers.nubank import NubankImporter
from app.shared.config import settings


def test_bank(importer, label: str) -> None:
    print(f"\n── {label} ──────────────────────────────")
    sources = importer.fetch_new_sources(seen_refs=set())
    print(f"Emails found: {len(sources)}")
    for s in sources:
        print(f"  source_ref={s.source_ref}  billing_date={s.billing_date}  size={len(s.data)}B")
        card, txs = importer.parse(s)
        print(f"  card_last4={card!r}  transactions={len(txs)}")
        for tx in txs[:3]:
            inst = f" ({tx.installment_current}/{tx.installment_total})" if tx.installment_current else ""
            print(f"    {tx.date} | {tx.description[:40]:<40} | R$ {tx.amount_brl:>10}{inst}")
        if len(txs) > 3:
            print(f"    ... and {len(txs) - 3} more")


def main() -> None:
    gmail = GmailClient(
        credentials_path=settings.gmail_credentials_path,
        token_path=settings.gmail_token_path,
    )

    test_bank(C6Importer(gmail=gmail, zip_password=settings.c6_zip_password), "C6 Bank")
    test_bank(NubankImporter(gmail=gmail), "Nubank")


if __name__ == "__main__":
    main()
