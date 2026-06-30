from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.infrastructure.security.auth import UserContext, get_user

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


class CashEntry(BaseModel):
    account: str
    balance: float
    currency: str


class CashOnHandResponse(BaseModel):
    owner: str
    as_of: date
    total: float
    currency: str
    breakdown: list[CashEntry]


_MOCK_CASH = [
    CashEntry(account="Checking", balance=4_250.75, currency="BRL"),
    CashEntry(account="Emergency fund", balance=12_000.00, currency="BRL"),
    CashEntry(account="Wallet", balance=320.00, currency="BRL"),
]


@router.get("/cash-on-hand", response_model=CashOnHandResponse)
async def cash_on_hand(
    user: Annotated[UserContext, Depends(get_user)],
) -> CashOnHandResponse:
    return CashOnHandResponse(
        owner=user.username or user.email,
        as_of=date.today(),
        total=sum(e.balance for e in _MOCK_CASH),
        currency="BRL",
        breakdown=_MOCK_CASH,
    )
