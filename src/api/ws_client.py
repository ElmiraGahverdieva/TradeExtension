import asyncio
import json
import logging
from collections import defaultdict, deque
from typing import Callable, Awaitable

import websockets

from src import config

logger = logging.getLogger(__name__)

CandleCallback = Callable[[str, dict], Awaitable[None]]


class DzengiWsClient:
    """WebSocket client for Dzengi.com real-time market data.

    Subscribes to OHLC streams for each configured symbol and calls
    `on_candle` with (symbol, candle_dict) whenever a new closed candle arrives.
    """

    def __init__(self, symbols: list[str], interval: str, on_candle: CandleCallback):
        self._symbols = symbols
        self._interval = interval
        self._on_candle = on_candle
        self._running = False

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self._connect()
            except (websockets.ConnectionClosed, OSError) as exc:
                logger.warning("WS disconnected: %s — reconnecting in 5s", exc)
                await asyncio.sleep(5)

    async def stop(self):
        self._running = False

    async def _connect(self):
        async with websockets.connect(config.WS_URL) as ws:
            logger.info("WS connected to %s", config.WS_URL)
            await self._subscribe(ws)
            ping_task = asyncio.create_task(self._ping_loop(ws))
            try:
                async for raw in ws:
                    await self._handle(raw)
            finally:
                ping_task.cancel()

    async def _subscribe(self, ws):
        for symbol in self._symbols:
            msg = {
                "method": "SUBSCRIBE",
                "params": [
                    f"wss:OHLCMarketData.subscribe",
                    f"symbol={symbol}",
                    f"intervals={self._interval}",
                ],
                "id": hash(symbol) & 0xFFFF,
            }
            await ws.send(json.dumps(msg))
            logger.debug("Subscribed to %s %s", symbol, self._interval)

    async def _ping_loop(self, ws):
        while True:
            await asyncio.sleep(config.WS_PING_INTERVAL)
            try:
                await ws.ping()
            except Exception:
                break

    async def _handle(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Dzengi sends OHLC update as an event with symbol and OHLC fields
        if not isinstance(data, dict):
            return
        if data.get("e") != "kline" and "k" not in data:
            return

        candle = data.get("k", data)
        symbol = data.get("s") or candle.get("s", "")
        is_closed = candle.get("x", False)

        if not is_closed:
            return

        parsed = {
            "symbol": symbol,
            "open_time": candle.get("t"),
            "open": float(candle.get("o", 0)),
            "high": float(candle.get("h", 0)),
            "low": float(candle.get("l", 0)),
            "close": float(candle.get("c", 0)),
            "volume": float(candle.get("v", 0)),
            "close_time": candle.get("T"),
            "interval": candle.get("i", self._interval),
        }

        await self._on_candle(symbol, parsed)
