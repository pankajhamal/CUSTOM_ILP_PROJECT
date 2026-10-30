"""Outgoing payment initiation."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DBSession, RafikiDep
from app.schemas.payment import SendPaymentRequest, SendPaymentResponse
from app.services.payment_service import send_payment

router = APIRouter()


@router.post(
    "/send",
    response_model=SendPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send money to a receiver (reserve hold + quote + outgoing payment)",
)
async def send(
    payload: SendPaymentRequest,
    session: DBSession,
    rafiki: RafikiDep,
) -> SendPaymentResponse:
    """PHASE 3→5: initiate an outgoing payment. Funding/settlement follow via webhooks."""
    return await send_payment(payload=payload, session=session, rafiki=rafiki)
