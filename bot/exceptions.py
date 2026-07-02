"""
Custom exception hierarchy for the trading bot.

Keeping exceptions in one place lets every layer (CLI, validators,
client, order service) raise and catch precise, well-named errors
instead of leaking raw third-party exceptions upward.
"""

from __future__ import annotations


class TradingBotError(Exception):
    """Base class for all trading-bot-specific errors."""


class ConfigurationError(TradingBotError):
    """Raised when required configuration (e.g. API keys) is missing or invalid."""


class ValidationError(TradingBotError):
    """Raised when user-supplied order input fails validation."""


class BinanceClientError(TradingBotError):
    """Raised when the Binance API client cannot complete a request.

    This wraps lower-level errors (network issues, authentication
    failures, rate limits, malformed API responses, etc.) so that
    callers only ever need to catch one exception type.
    """


class AuthenticationError(BinanceClientError):
    """Raised when the Binance API rejects the provided credentials."""


class NetworkError(BinanceClientError):
    """Raised for connection timeouts, DNS failures, and other network issues."""


class RateLimitError(BinanceClientError):
    """Raised when Binance responds with a rate-limit / too-many-requests error."""


class InvalidSymbolError(BinanceClientError):
    """Raised when Binance reports that the trading symbol does not exist."""


class OrderExecutionError(TradingBotError):
    """Raised when an order could not be placed or its response could not be parsed."""
