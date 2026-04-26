import asyncio
import json
import logging
from typing import Callable, Awaitable, List

import websockets

from src import config

logger = logging.getLogger(__name__)

CandleCallback = Callable[[str, dict], Awaitable[None]]


class DzengiWsClient:
    """WebSocket client for Dzengi.com real-time OHLC market data.

    Subscription format confirmed from Swagger:
      {"type": "wss:OHLCMarketData.subscribe", "symbols": [...], "intervals": [...]}

    Incoming event format:
      {"status":"OK","correlationId":"...","payload":{
        "Destination":"ohlc.event",
        "Payload":{"T":1234,"O":1.0,"H":1.1,"L":0.9,"C":1.05,"symbol":"BTC/USD_LEVERAGE","interval":"1m"}
      }}
    """

    def __init__(self, symbols: List[str], interval: str, on_candle: CandleCallback):
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
        extra = [
            ("X-MBX-APIKEY", config.API_KEY),
            ("User-Agent", "Mozilla/5.0"),
        ]
        async with websockets.connect(config.WS_URL, extra_headers=extra) as ws:
            logger.info("WS connected to %s", config.WS_URL)
            await self._subscribe(ws)
            ping_task = asyncio.create_task(self._ping_loop(ws))
            try:
                async for raw in ws:
                    await self._handle(raw)
            finally:
                ping_task.cancel()

    async def _subscribe(self, ws):
        msg = {
            "type": "wss:OHLCMarketData.subscribe",
            "symbols": self._symbols,
            "intervals": [self._interval],
        }
        await ws.send(json.dumps(msg))
        logger.info("Subscribed: %s %s", self._symbols, self._interval)

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

        status = data.get("status")
        if status == "ERROR":
            logger.error("WS error: %s", data)
            return

        payload = data.get("payload", {})
        if payload.get("Destination") != "ohlc.event":
            logger.debug("WS non-ohlc msg: %s", raw[:100])
            return

        p = payload.get("Payload", {})
        symbol = p.get("symbol", "")
        if not symbol:
            return

        candle = {
            "symbol": symbol,
            "open_time": p.get("T"),
            "open": float(p.get("O", 0)),
            "high": float(p.get("H", 0)),
            "low": float(p.get("L", 0)),
            "close": float(p.get("C", 0)),
            "volume": 0.0,
            "close_time": p.get("T"),
            "interval": p.get("interval", self._interval),
        }

        logger.debug("Candle %s O=%.4f H=%.4f L=%.4f C=%.4f",
                     symbol, candle["open"], candle["high"], candle["low"], candle["close"])
        await self._on_candle(symbol, candle)
