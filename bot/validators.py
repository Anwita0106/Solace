"""
Validation layer.

Responsible for turning raw, untrusted CLI input (strings) into a
fully-typed, internally consistent `OrderRequest`. No network calls
happen here -- this layer only ever inspects the data it is given.
"""

from __future__ import annotations

import re

from bot.exceptions import ValidationError
from bot.models import OrderRequest, OrderSide, OrderType

# Binance Futures symbols are uppercase alphanumeric, e.g. BTCUSDT, ETHUSDT.
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")

_SUPPORTED_SIDES = {side.value for side in OrderSide}
_SUPPORTED_ORDER_TYPES = {order_type.value for order_type in OrderType}


class OrderValidator:
    """Validates and normalizes raw order input into an `OrderRequest`."""

    @staticmethod
    def validate_symbol(raw_symbol: str) -> str:
        """Validate and normalize a trading symbol (e.g. "btcusdt" -> "BTCUSDT")."""
        if not raw_symbol or not raw_symbol.strip():
            raise ValidationError("Symbol must not be empty.")

        symbol = raw_symbol.strip().upper()
        if not _SYMBOL_PATTERN.match(symbol):
            raise ValidationError(
                f"Invalid symbol format: '{raw_symbol}'. Expected an "
                "uppercase alphanumeric symbol like 'BTCUSDT' (5-20 characters)."
            )
        return symbol

    @staticmethod
    def validate_side(raw_side: str) -> OrderSide:
        """Validate and normalize an order side."""
        if not raw_side or not raw_side.strip():
            raise ValidationError("Side must not be empty.")

        side = raw_side.strip().upper()
        if side not in _SUPPORTED_SIDES:
            supported = ", ".join(sorted(_SUPPORTED_SIDES))
            raise ValidationError(
                f"Unsupported side: '{raw_side}'. Supported sides: {supported}."
            )
        return OrderSide(side)

    @staticmethod
    def validate_order_type(raw_order_type: str) -> OrderType:
        """Validate and normalize an order type."""
        if not raw_order_type or not raw_order_type.strip():
            raise ValidationError("Order type must not be empty.")

        order_type = raw_order_type.strip().upper()
        if order_type not in _SUPPORTED_ORDER_TYPES:
            supported = ", ".join(sorted(_SUPPORTED_ORDER_TYPES))
            raise ValidationError(
                f"Unsupported order type: '{raw_order_type}'. "
                f"Supported order types: {supported}."
            )
        return OrderType(order_type)

    @staticmethod
    def validate_quantity(raw_quantity: str | float) -> float:
        """Validate that quantity parses to a strictly positive float."""
        try:
            quantity = float(raw_quantity)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Quantity must be a number, got: '{raw_quantity}'."
            ) from None

        if quantity <= 0:
            raise ValidationError(
                f"Quantity must be greater than zero, got: {quantity}."
            )
        return quantity

    @staticmethod
    def validate_price(raw_price: str | float | None, order_type: OrderType) -> float | None:
        """Validate price, enforcing that LIMIT orders require a positive price.

        Args:
            raw_price: The raw price value (or None if not supplied).
            order_type: The already-validated order type.

        Returns:
            The validated price for LIMIT orders, or None for MARKET orders
            (any price supplied for a MARKET order is ignored, but a
            negative/zero price is still rejected as bad input).
        """
        if order_type == OrderType.MARKET:
            if raw_price is not None:
                OrderValidator._validate_positive_price(raw_price)
            return None

        # order_type == LIMIT
        if raw_price is None:
            raise ValidationError("Price is required for LIMIT orders.")
        return OrderValidator._validate_positive_price(raw_price)

    @staticmethod
    def _validate_positive_price(raw_price: str | float) -> float:
        try:
            price = float(raw_price)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Price must be a number, got: '{raw_price}'."
            ) from None

        if price <= 0:
            raise ValidationError(f"Price must be greater than zero, got: {price}.")
        return price

    @classmethod
    def validate_order_request(
        cls,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str | float,
        price: str | float | None = None,
    ) -> OrderRequest:
        """Validate all raw order fields and build an `OrderRequest`.

        Raises:
            ValidationError: If any field fails validation.
        """
        validated_symbol = cls.validate_symbol(symbol)
        validated_side = cls.validate_side(side)
        validated_order_type = cls.validate_order_type(order_type)
        validated_quantity = cls.validate_quantity(quantity)
        validated_price = cls.validate_price(price, validated_order_type)

        return OrderRequest(
            symbol=validated_symbol,
            side=validated_side,
            order_type=validated_order_type,
            quantity=validated_quantity,
            price=validated_price,
        )
