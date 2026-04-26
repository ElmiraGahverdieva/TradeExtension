import hashlib
import hmac
import time
import logging
from urllib.parse import urlencode
from typing import Any, Optional

import aiohttp

from src import config

logger = logging.getLogger(__name__)


class DzengiRestClient:
    """Async REST client for Dzengi.com API v1."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            base_url=config.REST_BASE_URL,
            headers={"X-MBX-APIKEY": config.API_KEY},
        )
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(
            config.SECRET_KEY.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params

    async def _get(self, path: str, params: dict | None = None, signed: bool = False) -> Any:
        p = params or {}
        if signed:
            p = self._sign(p)
        async with self._session.get(path, params=p) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_exchange_info(self) -> dict:
        return await self._get("/api/v1/exchangeInfo")

    async def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list:
        """Return list of OHLCV candles.

        Each item: [open_time, open, high, low, close, volume, close_time, ...]
        """
        data = await self._get(
            "/api/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        return data

    async def get_ticker_price(self, symbol: str) -> dict:
        return await self._get("/api/v1/ticker/price", {"symbol": symbol})

    async def get_ticker_24hr(self, symbol: str) -> dict:
        return await self._get("/api/v1/ticker/24hr", {"symbol": symbol})

    async def get_depth(self, symbol: str, limit: int = 20) -> dict:
        return await self._get("/api/v1/depth", {"symbol": symbol, "limit": limit})

    async def get_account(self) -> dict:
        return await self._get("/api/v1/account", signed=True)

    async def get_open_orders(self, symbol: str | None = None) -> list:
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._get("/api/v1/openOrders", params, signed=True)

    async def get_positions(self) -> list:
        return await self._get("/api/v1/tradingPositions", signed=True)
