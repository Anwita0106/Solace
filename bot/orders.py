"""
Order service.

Sits between the CLI and the Binance client: orchestrates validation,
logging, timing, and dry-run short-circuiting. The CLI never talks to
`BinanceFuturesClient` directly -- it only ever talks to this module.
"""

from __future__ import annotations

import logging
from typing import Optional

from bot.client import BinanceFuturesClient
from bot.exceptions import BinanceClientError, OrderExecutionError
from bot.models import OrderRequest, OrderResult, OrderType
from bot.utils import timed_execution

logger = logging.getLogger(__name__)


class OrderService:
    """Coordinates order placement: logging, timing, and dry-run handling.

    Extending the bot with a new order type (e.g. STOP_LIMIT, OCO, TWAP)
    only requires adding a new branch in `_execute` (and a matching
    `BinanceFuturesClient` method) -- the rest of this class, and every
    caller of it, stays unchanged.
    """

    def __init__(self, client: Optional[BinanceFuturesClient]) -> None:
        """Args:
        client: A constructed `BinanceFuturesClient`, or `None` if this
            service will only ever be used in dry-run mode.
        """
        self._client = client

    def place_order(self, order: OrderRequest, dry_run: bool = False) -> OrderResult:
        """Validate-then-submit an order, or simulate it in dry-run mode.

        Args:
            order: A pre-validated `OrderRequest`.
            dry_run: If True, no network call is made; a synthetic
                `OrderResult` describing the *intended* order is returned.

        Returns:
            An `OrderResult` describing the outcome.

        Raises:
            OrderExecutionError: If the order could not be placed or the
                response could not be parsed.
            BinanceClientError: For network/auth/rate-limit/API failures
                (propagated from the client layer for the CLI to report).
        """
        logger.info("Validated order request: %s", order.to_log_dict())

        if dry_run:
            return self._build_dry_run_result(order)

        with timed_execution() as timer:
            try:
                raw_response = self._execute(order)
            except BinanceClientError:
                # Already a well-typed, specific error -- let it propagate
                # to the CLI layer, which knows how to present it.
                raise
            except Exception as exc:  # noqa: BLE001 - never let unexpected errors crash the CLI
                raise OrderExecutionError(
                    f"Order execution failed unexpectedly: {exc}"
                ) from exc

        logger.info(
            "Order executed in %.3fs | response: %s",
            timer.elapsed_seconds,
            raw_response,
        )

        try:
            return OrderResult.from_binance_response(raw_response)
        except Exception as exc:  # noqa: BLE001
            raise OrderExecutionError(
                f"Order was submitted but the response could not be parsed: {exc}"
            ) from exc

    def _execute(self, order: OrderRequest) -> dict:
        """Dispatch to the correct Binance client method based on order type."""
        if self._client is None:
            raise OrderExecutionError(
                "No Binance client is configured; cannot submit a live order."
            )
        if order.order_type == OrderType.MARKET:
            return self._client.create_market_order(
                symbol=order.symbol, side=order.side, quantity=order.quantity
            )
        if order.order_type == OrderType.LIMIT:
            # `price` is guaranteed non-None for LIMIT orders by the validator.
            return self._client.create_limit_order(
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price,  # type: ignore[arg-type]
            )
        # Unreachable while OrderType only has MARKET/LIMIT; guards future additions.
        raise OrderExecutionError(f"Unsupported order type: {order.order_type}")

    @staticmethod
    def _build_dry_run_result(order: OrderRequest) -> OrderResult:
        """Build a synthetic result describing what *would* be submitted."""
        logger.info("Dry-run mode: order was validated but not submitted.")
        return OrderResult(
            order_id="DRY-RUN",
            status="NOT_SUBMITTED",
            executed_qty=None,
            avg_price=order.price,
            raw_response={"dry_run": True, **order.to_log_dict()},
        )
