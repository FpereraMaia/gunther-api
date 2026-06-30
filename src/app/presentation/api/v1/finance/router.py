from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.infrastructure.security.auth import UserContext, get_user

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

_MOCK_CASH = [
    {"account": "Checking", "balance": 4_250.75, "currency": "BRL"},
    {"account": "Emergency fund", "balance": 12_000.00, "currency": "BRL"},
    {"account": "Wallet", "balance": 320.00, "currency": "BRL"},
]


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


@router.get("/cash-on-hand", response_model=CashOnHandResponse)
async def cash_on_hand(
    user: Annotated[UserContext, Depends(get_user)],
) -> CashOnHandResponse:
    return CashOnHandResponse(
        owner=user.username or user.email,
        as_of=date.today(),
        total=sum(e["balance"] for e in _MOCK_CASH),
        currency="BRL",
        breakdown=[CashEntry(**e) for e in _MOCK_CASH],
    )
