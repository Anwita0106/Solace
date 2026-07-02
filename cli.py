#!/usr/bin/env python3
"""
CLI entry point for the Binance USDT-M Futures Testnet Trading Bot.

This layer is intentionally "dumb": it only parses input, delegates to
the validation layer, delegates to the order service, and formats
output. It never talks to Binance directly.

Examples:
    MARKET order:
        python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

    LIMIT order:
        python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 65000

    Interactive mode:
        python cli.py --interactive

    Dry run (validate + preview, no order placed):
        python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import NoReturn, Optional

from bot.client import BinanceFuturesClient
from bot.config import load_config
from bot.exceptions import (
    BinanceClientError,
    ConfigurationError,
    OrderExecutionError,
    ValidationError,
)
from bot.logging_config import setup_logging
from bot.models import OrderRequest, OrderResult, OrderType
from bot.orders import OrderService
from bot.utils import failure, heading, success, warning

logger = logging.getLogger(__name__)

_BANNER_WIDTH = 50
_SEPARATOR = "=" * _BANNER_WIDTH


@dataclass
class RawOrderInput:
    """Unvalidated order fields, as collected from argparse or interactive prompts."""

    symbol: str
    side: str
    order_type: str
    quantity: str
    price: Optional[str] = None


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Binance USDT-M Futures Testnet Trading Bot",
    )
    parser.add_argument("--symbol", type=str, help="Trading symbol, e.g. BTCUSDT")
    parser.add_argument(
        "--side", type=str, choices=["BUY", "SELL", "buy", "sell"], help="Order side"
    )
    parser.add_argument(
        "--type",
        dest="order_type",
        type=str,
        choices=["MARKET", "LIMIT", "market", "limit"],
        help="Order type",
    )
    parser.add_argument("--quantity", type=str, help="Order quantity")
    parser.add_argument(
        "--price", type=str, default=None, help="Order price (required for LIMIT orders)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt step-by-step for order details instead of using flags",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the order and print what would be sent, without submitting it",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print DEBUG-level logs to the console in addition to the log file",
    )
    return parser


def prompt_interactive_order() -> RawOrderInput:
    """Collect order fields step-by-step from the user."""
    print(heading("\nInteractive Order Entry"))
    print("-" * _BANNER_WIDTH)

    symbol = input("Symbol (e.g. BTCUSDT): ").strip()
    side = input("Side (BUY/SELL): ").strip()
    order_type = input("Order type (MARKET/LIMIT): ").strip()
    quantity = input("Quantity: ").strip()

    price: Optional[str] = None
    if order_type.strip().upper() == OrderType.LIMIT.value:
        price = input("Price: ").strip()

    return RawOrderInput(
        symbol=symbol, side=side, order_type=order_type, quantity=quantity, price=price
    )


def raw_input_from_args(args: argparse.Namespace) -> RawOrderInput:
    """Build a `RawOrderInput` from parsed CLI flags, enforcing required fields."""
    missing = [
        flag
        for flag, value in (
            ("--symbol", args.symbol),
            ("--side", args.side),
            ("--type", args.order_type),
            ("--quantity", args.quantity),
        )
        if not value
    ]
    if missing:
        raise ValidationError(
            "Missing required argument(s): "
            + ", ".join(missing)
            + ". Run with --interactive for step-by-step entry, or --help for usage."
        )

    return RawOrderInput(
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
    )


def print_order_summary(order: OrderRequest, dry_run: bool) -> None:
    """Print the 'Order Request Summary' block."""
    print(_SEPARATOR)
    print(heading("Binance Futures Testnet Trading Bot"))
    print(_SEPARATOR)
    print(heading("Order Summary"))
    print(f"Symbol   : {order.symbol}")
    print(f"Side     : {order.side.value}")
    print(f"Type     : {order.order_type.value}")
    print(f"Quantity : {order.quantity}")
    if order.order_type == OrderType.LIMIT:
        print(f"Price    : {order.price}")
    if dry_run:
        print(warning("Mode     : DRY RUN (no order will be submitted)"))
    print("-" * _BANNER_WIDTH)


def print_order_result(result: OrderResult, dry_run: bool) -> None:
    """Print the 'Order Response' block and a success message."""
    if dry_run:
        print(success("Dry Run Complete -- nothing was submitted to Binance."))
        print(f"Would submit: {result.raw_response}")
        print(_SEPARATOR)
        return

    print(success("Order Successful"))
    print(f"Order ID      : {result.order_id}")
    print(f"Status        : {result.status}")
    print(f"Executed Qty  : {result.executed_qty if result.executed_qty is not None else 'N/A'}")
    print(f"Average Price : {result.avg_price if result.avg_price is not None else 'N/A'}")
    print(_SEPARATOR)


def print_error(message: str) -> None:
    """Print a consistently formatted failure message."""
    print(failure("Order Failed"))
    print(failure(f"Reason: {message}"))
    print(_SEPARATOR)


def run(argv: Optional[list[str]] = None) -> int:
    """Main CLI logic. Returns a process exit code (0 success, 1 failure)."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    setup_logging(verbose=args.verbose)
    logger.debug("Parsed CLI arguments: %s", vars(args))

    try:
        raw_input = (
            prompt_interactive_order() if args.interactive else raw_input_from_args(args)
        )

        from bot.validators import OrderValidator

        order = OrderValidator.validate_order_request(
            symbol=raw_input.symbol,
            side=raw_input.side,
            order_type=raw_input.order_type,
            quantity=raw_input.quantity,
            price=raw_input.price,
        )
    except ValidationError as exc:
        logger.warning("Validation failed: %s", exc)
        print_order_input_error(str(exc))
        return 1

    print_order_summary(order, dry_run=args.dry_run)

    try:
        config = load_config()
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        print_error(str(exc))
        return 1

    try:
        # In dry-run mode we deliberately avoid constructing the Binance
        # client at all, so a dry run is guaranteed to be network-free --
        # not just because OrderService happens to skip using it.
        client = None if args.dry_run else BinanceFuturesClient(config)
        service = OrderService(client)
        print("Submitting order..." if not args.dry_run else "Validating order (dry run)...")
        result = service.place_order(order, dry_run=args.dry_run)
    except (BinanceClientError, OrderExecutionError) as exc:
        logger.error("Order failed: %s", exc, exc_info=True)
        print_error(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001 - absolute last line of defense
        logger.error("Unexpected error: %s", exc, exc_info=True)
        print_error(f"Unexpected error: {exc}")
        return 1

    print_order_result(result, dry_run=args.dry_run)
    return 0


def print_order_input_error(message: str) -> None:
    """Print a formatted error for bad CLI/interactive input (pre-summary)."""
    print(_SEPARATOR)
    print(heading("Binance Futures Testnet Trading Bot"))
    print(_SEPARATOR)
    print(failure("Invalid Input"))
    print(failure(f"Reason: {message}"))
    print(_SEPARATOR)


def main() -> NoReturn:
    """Console-script entry point."""
    sys.exit(run())


if __name__ == "__main__":
    main()
