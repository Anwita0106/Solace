

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class OrderSide(str, Enum):
    """Supported order sides."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):


    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class OrderRequest:


    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None

    def to_log_dict(self) -> dict:
        """Return a plain dict suitable for structured logging."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
        }


@dataclass
class OrderResult:
    """Normalized result of a successful order placement."""

    order_id: Any
    status: str
    executed_qty: Optional[float]
    avg_price: Optional[float]
    raw_response: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_binance_response(cls, response: dict) -> "OrderResult":

        avg_price_raw = response.get("avgPrice")
        avg_price: Optional[float]
        try:
            avg_price = float(avg_price_raw) if avg_price_raw is not None else None
            if avg_price == 0.0:
                avg_price = None
        except (TypeError, ValueError):
            avg_price = None

        executed_qty_raw = response.get("executedQty")
        try:
            executed_qty = (
                float(executed_qty_raw) if executed_qty_raw is not None else None
            )
        except (TypeError, ValueError):
            executed_qty = None

        return cls(
            order_id=response.get("orderId"),
            status=response.get("status", "UNKNOWN"),
            executed_qty=executed_qty,
            avg_price=avg_price,
            raw_response=response,
        )
