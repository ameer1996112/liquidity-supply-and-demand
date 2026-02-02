"""Data models for trade signals (webhook payloads)."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ExitWebhookPayload(BaseModel):
    """Payload for trade exit events."""

    model_config = {"extra": "allow"}

    event_type: Literal["exit"] = Field(..., description="Must be 'exit'")
    zone_id: int = Field(..., description="Zone ID to update")
    outcome: str = Field(..., description="win, loss, breakeven")
    bars_held: int = Field(..., description="Bars position was held")
    close_price: float = Field(..., description="Exit price")
    exit_type: str = Field(..., description="tp, sl, etc.")
    mae_pips: float = Field(..., description="Max adverse excursion in pips")


class EntryWebhookPayload(BaseModel):
    """Payload for trade entry / signal events."""

    model_config = {"extra": "allow"}

    symbol: str = Field(..., min_length=1, description="Instrument symbol")
    side: str = Field(..., description="buy or sell")
    entry: float = Field(..., description="Entry price")
    sl: float = Field(..., description="Stop loss price")
    tp: float = Field(..., description="Take profit price")
    size: float = Field(..., description="Position size")
    event_type: str | None = Field(None, description="If 'exit', use exit payload instead")

    @model_validator(mode="after")
    def side_must_be_buy_or_sell(self) -> "EntryWebhookPayload":
        if str(self.side).lower() not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        return self


def validate_webhook_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate parsed body as either Entry or Exit payload.
    Returns the same dict; raises pydantic.ValidationError on failure.
    """
    if not data or not isinstance(data, dict):
        raise ValueError("Empty or invalid body")
    event_type = data.get("event_type")
    if event_type == "exit":
        ExitWebhookPayload.model_validate(data)
    else:
        EntryWebhookPayload.model_validate(data)
    return data
