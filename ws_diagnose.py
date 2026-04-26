"""
WebSocket diagnostic — tests multiple subscription formats against Dzengi demo.
Run: python ws_diagnose.py
"""
import asyncio
import json
import os
import sys

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
SYMBOL = "BTC/USD_LEVERAGE"
INTERVAL = "1m"

EXTRA_HEADERS = [
    ("X-MBX-APIKEY", API_KEY),
    ("User-Agent", "Mozilla/5.0"),
]

# Candidate formats to try in order
FORMATS = [
    # Format A: destination + correlationId + payload (most likely based on Swagger)
    {
        "name": "A: destination+correlationId+payload",
        "msgs": [
            {"correlationId": "ping-1", "destination": "wss:ping", "payload": {}},
            {"correlationId": "sub-1", "destination": "wss:OHLCMarketData.subscribe",
             "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"}},
        ],
    },
    # Format B: type as destination key (old format, likely wrong)
    {
        "name": "B: type as destination",
        "msgs": [
            {"type": "wss:OHLCMarketData.subscribe", "symbols": [SYMBOL], "intervals": [INTERVAL]},
        ],
    },
    # Format C: type=subscribe with destination in body
    {
        "name": "C: type=subscribe with route",
        "msgs": [
            {"type": "subscribe", "route": "wss:OHLCMarketData.subscribe",
             "symbols": [SYMBOL], "intervals": [INTERVAL], "candleType": "classic"},
        ],
    },
    # Format D: action field
    {
        "name": "D: action field",
        "msgs": [
            {"action": "wss:OHLCMarketData.subscribe",
             "symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"},
        ],
    },
    # Format E: event field
    {
        "name": "E: event field",
        "msgs": [
            {"event": "subscribe", "destination": "OHLCMarketData",
             "symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"},
        ],
    },
]


async def test_format(fmt: dict, timeout: float = 6.0):
    print(f"\n{'='*60}")
    print(f"Testing: {fmt['name']}")
    print(f"{'='*60}")
    try:
        async with websockets.connect(WS_URL, extra_headers=EXTRA_HEADERS,
                                      open_timeout=10) as ws:
            print("  Connected.")
            for msg in fmt["msgs"]:
                payload = json.dumps(msg)
                print(f"  >> {payload}")
                await ws.send(payload)

            # Collect responses for `timeout` seconds
            deadline = asyncio.get_event_loop().time() + timeout
            got_ohlc = False
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 2.0))
                    print(f"  << {raw[:300]}")
                    if "ohlc" in raw.lower() or "OHLC" in raw or "Payload" in raw:
                        print("  *** GOT OHLC DATA — THIS FORMAT WORKS! ***")
                        got_ohlc = True
                        break
                except asyncio.TimeoutError:
                    pass
            if not got_ohlc:
                print("  (no OHLC data received within timeout)")
    except Exception as exc:
        print(f"  ERROR: {exc}")

    return


async def main():
    if not API_KEY:
        print("WARNING: DZENGI_API_KEY not set — some formats may fail auth\n")

    print(f"Target: {WS_URL}")
    print(f"Symbol: {SYMBOL}  Interval: {INTERVAL}\n")

    # Test all formats sequentially
    for fmt in FORMATS:
        await test_format(fmt)
        await asyncio.sleep(1)

    print("\nDone. Look for '*** GOT OHLC DATA ***' above.")


asyncio.run(main())
