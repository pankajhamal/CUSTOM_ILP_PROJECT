"""Outgoing payment / quote schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SendPaymentRequest(BaseModel):
    """Request to send money from a local wallet to an external receiver."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sender_wallet_address_id": "11111111-1111-1111-1111-111111111111",
                "receiver": "https://rafiki-backend.testnet.test/.well-known/pay/bob",
                "amount": 500,
            }
        }
    )

    sender_wallet_address_id: uuid.UUID = Field(
        description="Local wallet address id (ours) funding the payment."
    )
    receiver: str = Field(
        description="Receiver's wallet address URL (or $pointer) or incoming-payment URL."
    )
    amount: int = Field(gt=0, description="Amount to debit in the sender asset's minor units.")
    description: str | None = Field(default=None, max_length=255)


class QuoteInfo(BaseModel):
    """A Rafiki quote summary returned with a send."""

    quote_id: str
    debit_amount: int
    receive_amount: int
    asset_code: str
    asset_scale: int


class SendPaymentResponse(BaseModel):
    """Result of initiating an outgoing payment."""

    payment_id: str
    status: str
    quote: QuoteInfo
    hold_transaction_id: uuid.UUID
