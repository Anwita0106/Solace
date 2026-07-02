"""
Application configuration.

Credentials and other environment-dependent settings are read from a
`.env` file (via python-dotenv) so that secrets never end up
hardcoded in source control.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from bot.exceptions import ConfigurationError

# Binance USDT-M Futures Testnet endpoint (must never point at mainnet).
FUTURES_TESTNET_BASE_URL = "https://testnet.binancefuture.com"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIRECTORY = PROJECT_ROOT / "logs"
LOG_FILE_PATH = LOG_DIRECTORY / "trading.log"


@dataclass(frozen=True)
class BotConfig:
    """Immutable runtime configuration for the trading bot."""

    api_key: str
    api_secret: str
    base_url: str = FUTURES_TESTNET_BASE_URL
    testnet: bool = True
    request_timeout_seconds: int = 10

    @property
    def has_credentials(self) -> bool:
        """Whether both API key and secret are non-empty."""
        return bool(self.api_key) and bool(self.api_secret)


def load_config(env_file: str | None = None) -> BotConfig:
    """Load configuration from environment variables / a `.env` file.

    Args:
        env_file: Optional explicit path to a `.env` file. Defaults to
            the `.env` file in the project root, if present.

    Returns:
        A populated `BotConfig` instance.

    Raises:
        ConfigurationError: If required API credentials are missing.
            Note: credential *presence* is validated here; credential
            *validity* can only be confirmed by Binance itself at
            request time (handled by the client/exception layers).
    """
    dotenv_path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        # Still allow real environment variables (e.g. exported in CI)
        # even if no .env file is present.
        load_dotenv()

    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "").strip()

    if not api_key or not api_secret:
        raise ConfigurationError(
            "Missing Binance Testnet API credentials. Set "
            "BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET in a "
            ".env file (see .env.example) or as environment variables."
        )

    timeout_raw = os.getenv("REQUEST_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError:
        timeout_seconds = 10

    return BotConfig(
        api_key=api_key,
        api_secret=api_secret,
        base_url=FUTURES_TESTNET_BASE_URL,
        testnet=True,
        request_timeout_seconds=timeout_seconds,
    )
