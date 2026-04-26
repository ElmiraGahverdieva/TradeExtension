"""
WebSocket diagnostic — tests subscription payload variations against Dzengi demo.
Run: python ws_diagnose.py
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time

try:
    import websockets
except ImportError:
    print("Install websockets: pip install websockets")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

WS_URL = "wss://demo-api-adapter.dzengi.com/connect"
API_KEY = os.getenv("DZENGI_API_KEY", "")
SECRET_KEY = os.getenv("DZENGI_SECRET_KEY", "")
SYMBOL = "BTC/USD_LEVERAGE"
INTERVAL = "1m"

EXTRA_HEADERS = [
    ("X-MBX-APIKEY", API_KEY),
    ("User-Agent", "Mozilla/5.0"),
]


def sign(params: dict) -> dict:
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(SECRET_KEY.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params


FORMATS = [
    # ping without payload key at all
    {
        "name": "ping — no payload field",
        "msgs": [{"correlationId": "p1", "destination": "wss:ping"}],
    },
    # OHLC without type field
    {
        "name": "OHLC — no type field",
        "msgs": [{"correlationId": "s1", "destination": "wss:OHLCMarketData.subscribe",
                  "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL]}}],
    },
    # OHLC classic (already tried, retry cleanly)
    {
        "name": "OHLC — type=classic",
        "msgs": [{"correlationId": "s2", "destination": "wss:OHLCMarketData.subscribe",
                  "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"}}],
    },
    # lowercase destination
    {
        "name": "OHLC — lowercase destination",
        "msgs": [{"correlationId": "s3", "destination": "wss:ohlcMarketData.subscribe",
                  "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"}}],
    },
    # full path destination
    {
        "name": "OHLC — /api/v1/ path",
        "msgs": [{"correlationId": "s4", "destination": "wss:/api/v1/OHLCMarketData.subscribe",
                  "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"}}],
    },
    # signed OHLC request (apiKey+signature in payload)
    {
        "name": "OHLC — signed (apiKey in payload)",
        "msgs": [{"correlationId": "s5", "destination": "wss:OHLCMarketData.subscribe",
                  "payload": sign({"symbols": SYMBOL, "intervals": INTERVAL,
                                   "type": "classic", "apiKey": API_KEY})}],
    },
    # symbol without slash
    {
        "name": "OHLC — symbol BTCUSD_LEVERAGE (no slash)",
        "msgs": [{"correlationId": "s6", "destination": "wss:OHLCMarketData.subscribe",
                  "payload": {"symbols": ["BTCUSD_LEVERAGE"], "intervals": [INTERVAL], "type": "classic"}}],
    },
    # interval as string not array
    {
        "name": "OHLC — interval as string",
        "msgs": [{"correlationId": "s7", "destination": "wss:OHLCMarketData.subscribe",
                  "payload": {"symbols": [SYMBOL], "interval": INTERVAL, "type": "classic"}}],
    },
]


async def test_format(fmt: dict, timeout: float = 7.0):
    print(f"\n{'='*55}")
    print(f"Testing: {fmt['name']}")
    print(f"{'='*55}")
    try:
        async with websockets.connect(WS_URL, extra_headers=EXTRA_HEADERS,
                                      open_timeout=10) as ws:
            print("  Connected.")
            for msg in fmt["msgs"]:
                out = json.dumps(msg)
                print(f"  >> {out[:200]}")
                await ws.send(out)

            deadline = asyncio.get_event_loop().time() + timeout
            got_ohlc = False
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
                    print(f"  << {raw[:300]}")
                    low = raw.lower()
                    if "ohlc" in low or "payload" in low and "open" in low:
                        print("  *** GOT OHLC DATA — THIS FORMAT WORKS! ***")
                        got_ohlc = True
                        break
                    if "ok" in low and "error" not in low:
                        print("  *** GOT OK — waiting for candle data... ***")
                except asyncio.TimeoutError:
                    pass
            if not got_ohlc:
                print("  (no OHLC within timeout)")
    except Exception as exc:
        print(f"  ERROR: {exc}")


async def main():
    if not API_KEY:
        print("WARNING: DZENGI_API_KEY not set\n")
    print(f"WS: {WS_URL}")
    print(f"Symbol: {SYMBOL}  Interval: {INTERVAL}\n")

    for fmt in FORMATS:
        await test_format(fmt)
        await asyncio.sleep(1)

    print("\nDone.")


asyncio.run(main())
