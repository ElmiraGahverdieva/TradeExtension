"""
TradeExtension — main entry point.

Startup sequence:
  1. Load historical klines via REST (200 candles per symbol) to warm up indicators.
  2. Connect WebSocket and stream live closed candles.
  3. On each closed candle run SignalEngine; if signal fires — dispatch notification.
"""
import asyncio
import logging
import os
import sys

from src import config
from src.api.rest_client import DzengiRestClient
from src.api.ws_client import DzengiWsClient
from src.strategy.signal_engine import SignalEngine
from src.notifications import dispatch

_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"


def _setup_logging():
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(level=config.LOG_LEVEL, format=_LOG_FORMAT, handlers=handlers)


logger = logging.getLogger(__name__)

engine = SignalEngine()


async def _load_history(rest: DzengiRestClient):
    logger.info("Loading historical klines for %s × %s …", config.SYMBOLS, config.TIMEFRAMES)
    for symbol in config.SYMBOLS:
        for tf in config.TIMEFRAMES:
            try:
                klines = await rest.get_klines(symbol, tf, config.CANDLE_BUFFER_SIZE)
                buf = engine.get_buffer(symbol, tf)
                buf.load_klines(klines)
                logger.info("  %s [%s]: loaded %d candles", symbol, tf, len(klines))
            except Exception as exc:
                logger.error("Failed to load history for %s [%s]: %s", symbol, tf, exc)
            await asyncio.sleep(0.4)


async def _on_candle(symbol: str, candle: dict):
    logger.info("Candle %-20s O=%-9.2f H=%-9.2f L=%-9.2f C=%.2f",
                symbol, candle["open"], candle["high"], candle["low"], candle["close"])
    signal = engine.on_new_candle(symbol, candle)
    if signal:
        await dispatch(signal)


async def _volume_refresh_loop():
    """Refresh candle buffers from REST every minute to keep volume data current."""
    await asyncio.sleep(65)
    while True:
        try:
            async with DzengiRestClient() as rest:
                for symbol in config.SYMBOLS:
                    for tf in config.TIMEFRAMES:
                        klines = await rest.get_klines(symbol, tf, config.CANDLE_BUFFER_SIZE)
                        buf = engine.get_buffer(symbol, tf)
                        buf.clear()
                        buf.load_klines(klines)
                        await asyncio.sleep(0.4)
        except Exception as exc:
            logger.warning("Volume refresh failed: %s", exc)
        await asyncio.sleep(60)


async def main():
    _setup_logging()

    logger.info("TradeExtension starting")
    logger.info("  ENV:      %s", os.getenv("DZENGI_ENV", "demo"))
    logger.info("  Symbols:  %s", config.SYMBOLS)
    logger.info("  TF:       %s", config.TIMEFRAME)
    logger.info("  REST:     %s", config.REST_BASE_URL)
    logger.info("  WS:       %s", config.WS_URL)

    async with DzengiRestClient() as rest:
        await _load_history(rest)

    ws = DzengiWsClient(config.SYMBOLS, config.TIMEFRAMES, _on_candle)
    logger.info("Starting WebSocket stream …")
    await asyncio.gather(
        ws.run(),
        _volume_refresh_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
