"""
Binance USDT-M Futures Testnet Trading Bot
============================================

A small, layered trading bot for placing MARKET and LIMIT orders against
the Binance USDT-M Futures Testnet.

Package layout:
    config.py          Environment / application configuration
    models.py           Typed data models (enums, dataclasses)
    exceptions.py        Custom exception hierarchy
    validators.py        Input validation layer
    client.py            Thin wrapper around the Binance API client
    orders.py            Order orchestration / business logic
    logging_config.py    Centralized logging setup
    utils.py             Small shared helpers (formatting, timing, color)
"""

__version__ = "1.0.0"
