"""
Binance Futures Testnet client wrapper.

This is the only module that imports `binance` directly. Every other
layer talks to `BinanceFuturesClient`, so swapping the underlying SDK
(or mocking it in tests) never touches business logic elsewhere.
"""

from __future__ import annotations

import logging
from typing import Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from bot.config import BotConfig
from bot.exceptions import (
    AuthenticationError,
    BinanceClientError,
    InvalidSymbolError,
    NetworkError,
    RateLimitError,
)
from bot.models import OrderSide, OrderType

logger = logging.getLogger(__name__)

# Binance error codes we want to translate into specific exception types.
# See: https://binance-docs.github.io/apidocs/futures/en/#error-codes
_AUTH_ERROR_CODES = {-2014, -2015}  # bad API key / invalid signature / IP restricted
_INVALID_SYMBOL_ERROR_CODES = {-1121}
_RATE_LIMIT_ERROR_CODES = {-1003}
_RATE_LIMIT_HTTP_STATUS = 429


class BinanceFuturesClient:
    """Thin, exception-normalizing wrapper around `python-binance`'s Futures API."""

    def __init__(self, config: BotConfig) -> None:
        """Initialize the underlying SDK client against the Futures Testnet.

        Raises:
            BinanceClientError: If the SDK client itself cannot be constructed.
        """
        self._config = config
        try:
            self._client = Client(
                api_key=config.api_key,
                api_secret=config.api_secret,
                testnet=config.testnet,
                requests_params={"timeout": config.request_timeout_seconds},
                # The SDK otherwise performs an implicit spot-endpoint ping
                # during __init__. We disable that so client construction
                # never makes a network call by itself; connectivity is
                # verified explicitly (against the Futures Testnet) via
                # `verify_connectivity()` when the caller actually wants it.
                ping=False,
            )
            # Ensure we are unambiguously pointed at the Futures Testnet,
            # regardless of the SDK version's default derivation logic.
            self._client.FUTURES_URL = f"{config.base_url}/fapi"
        except Exception as exc:  # noqa: BLE001 - SDK construction failure is fatal
            raise BinanceClientError(
                f"Failed to initialize Binance client: {exc}"
            ) from exc

    def verify_connectivity(self) -> None:
        """Ping the Futures Testnet and check server time, to fail fast on bad setup.

        Raises:
            NetworkError: On connection/timeout issues.
            AuthenticationError: If credentials are rejected.
            BinanceClientError: For any other API-reported problem.
        """
        try:
            self._client.futures_ping()
            self._client.futures_time()
        except (RequestsConnectionError, RequestsTimeout) as exc:
            raise NetworkError(
                f"Could not reach Binance Futures Testnet: {exc}"
            ) from exc
        except BinanceAPIException as exc:
            raise self._translate_api_exception(exc) from exc

    def create_market_order(self, symbol: str, side: OrderSide, quantity: float) -> dict:
        """Submit a MARKET order and return the raw Binance response."""
        return self._submit_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=None,
        )

    def create_limit_order(
        self, symbol: str, side: OrderSide, quantity: float, price: float
    ) -> dict:
        """Submit a LIMIT (GTC) order and return the raw Binance response."""
        return self._submit_order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
        )

    def _submit_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float],
    ) -> dict:
        """Build and submit a futures order, normalizing any failure into
        one of the `BinanceClientError` subtypes.
        """
        order_kwargs: dict = {
            "symbol": symbol,
            "side": side.value,
            "type": order_type.value,
            "quantity": quantity,
        }
        if order_type == OrderType.LIMIT:
            order_kwargs["price"] = price
            order_kwargs["timeInForce"] = "GTC"

        try:
            response: dict = self._client.futures_create_order(**order_kwargs)
            return response
        except (RequestsConnectionError, RequestsTimeout) as exc:
            raise NetworkError(
                f"Network error while submitting order: {exc}"
            ) from exc
        except BinanceRequestException as exc:
            raise BinanceClientError(f"Malformed request to Binance: {exc}") from exc
        except BinanceAPIException as exc:
            raise self._translate_api_exception(exc) from exc
        except Exception as exc:  # noqa: BLE001 - final safety net, never crash
            raise BinanceClientError(
                f"Unexpected error while submitting order: {exc}"
            ) from exc

    @staticmethod
    def _translate_api_exception(exc: BinanceAPIException) -> BinanceClientError:
        """Map a `BinanceAPIException` to a specific, typed exception."""
        code = getattr(exc, "code", None)
        status_code = getattr(exc, "status_code", None)
        message = getattr(exc, "message", str(exc))

        if code in _AUTH_ERROR_CODES:
            return AuthenticationError(
                f"Binance authentication failed (code {code}): {message}. "
                "Check your BINANCE_TESTNET_API_KEY / SECRET in .env."
            )
        if code in _INVALID_SYMBOL_ERROR_CODES:
            return InvalidSymbolError(f"Invalid symbol (code {code}): {message}")
        if code in _RATE_LIMIT_ERROR_CODES or status_code == _RATE_LIMIT_HTTP_STATUS:
            return RateLimitError(
                f"Binance rate limit exceeded (code {code}): {message}. "
                "Slow down request frequency and retry shortly."
            )
        return BinanceClientError(f"Binance API error (code {code}): {message}")
