"""
WebSocket diagnostic — Dzengi demo.
Run: python ws_diagnose.py
"""
import asyncio
import json
import os
import sys
from urllib.parse import urlencode

try:
    import websockets
except ImportError:
    print("pip install websockets"); sys.exit(1)

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

BASE_URL = "wss://demo-api-adapter.dzengi.com/connect"
API_KEY  = os.getenv("DZENGI_API_KEY", "")
SYMBOL   = "BTC/USD_LEVERAGE"
INTERVAL = "1m"

HEADERS = [("X-MBX-APIKEY", API_KEY), ("User-Agent", "Mozilla/5.0")]


async def listen(ws, seconds=5):
    """Collect messages for `seconds` and return them."""
    msgs = []
    deadline = asyncio.get_event_loop().time() + seconds
    while asyncio.get_event_loop().time() < deadline:
        remaining = deadline - asyncio.get_event_loop().time()
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 1.5))
            msgs.append(raw)
            print(f"  << {raw[:300]}")
            if "ohlc" in raw.lower() or ('"O"' in raw and '"C"' in raw):
                print("  *** OHLC DATA RECEIVED — FORMAT WORKS! ***")
        except asyncio.TimeoutError:
            pass
    return msgs


# ─── TEST 1: listen first (maybe server sends greeting) ───────────────────────
async def test_listen_first():
    print("\n" + "="*60)
    print("TEST 1: connect and just LISTEN 4s (no send)")
    print("="*60)
    try:
        async with websockets.connect(BASE_URL, extra_headers=HEADERS, open_timeout=10) as ws:
            print("  Connected — waiting for server greeting...")
            msgs = await listen(ws, 4)
            if not msgs:
                print("  (server sent nothing — no greeting)")
            return msgs
    except Exception as e:
        print(f"  ERROR: {e}")
    return []


# ─── TEST 2: flat JSON (no wrapper) ───────────────────────────────────────────
async def test_flat_json():
    print("\n" + "="*60)
    print("TEST 2: flat JSON body (no destination wrapper)")
    print("="*60)
    payloads = [
        {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"},
        {"symbols": [SYMBOL], "intervals": [INTERVAL]},
        {"correlationId": "1", "symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"},
    ]
    for p in payloads:
        try:
            async with websockets.connect(BASE_URL, extra_headers=HEADERS, open_timeout=10) as ws:
                out = json.dumps(p)
                print(f"\n  >> {out}")
                await ws.send(out)
                await listen(ws, 5)
        except Exception as e:
            print(f"  ERROR: {e}")
        await asyncio.sleep(1)


# ─── TEST 3: URL query params ─────────────────────────────────────────────────
async def test_url_params():
    print("\n" + "="*60)
    print("TEST 3: subscription via URL query parameters")
    print("="*60)
    variants = [
        {"symbols": SYMBOL, "intervals": INTERVAL, "type": "classic"},
        {"symbols": SYMBOL, "interval": INTERVAL, "type": "classic"},
        {"symbol": SYMBOL, "intervals": INTERVAL, "type": "classic"},
    ]
    for params in variants:
        url = BASE_URL + "?" + urlencode(params)
        print(f"\n  URL: {url}")
        try:
            async with websockets.connect(url, extra_headers=HEADERS, open_timeout=10) as ws:
                print("  Connected.")
                await listen(ws, 6)
        except Exception as e:
            print(f"  ERROR: {e}")
        await asyncio.sleep(1)


# ─── TEST 4: destination without wss: prefix ──────────────────────────────────
async def test_no_prefix():
    print("\n" + "="*60)
    print("TEST 4: destination without 'wss:' prefix")
    print("="*60)
    variants = [
        "OHLCMarketData.subscribe",
        "ohlcMarketData.subscribe",
        "/api/v1/OHLCMarketData.subscribe",
        "ohlc.subscribe",
    ]
    for dest in variants:
        msg = {"correlationId": "t4", "destination": dest,
               "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"}}
        print(f"\n  >> destination={dest}")
        try:
            async with websockets.connect(BASE_URL, extra_headers=HEADERS, open_timeout=10) as ws:
                await ws.send(json.dumps(msg))
                await listen(ws, 4)
        except Exception as e:
            print(f"  ERROR: {e}")
        await asyncio.sleep(1)


# ─── TEST 5: wait for greeting, then subscribe ────────────────────────────────
async def test_greet_then_sub():
    print("\n" + "="*60)
    print("TEST 5: wait 2s for greeting, then subscribe")
    print("="*60)
    msg = {"correlationId": "g1", "destination": "wss:OHLCMarketData.subscribe",
           "payload": {"symbols": [SYMBOL], "intervals": [INTERVAL], "type": "classic"}}
    try:
        async with websockets.connect(BASE_URL, extra_headers=HEADERS, open_timeout=10) as ws:
            print("  Connected — waiting 2s for greeting...")
            greeting = await listen(ws, 2)
            print(f"  Greeting msgs: {len(greeting)}")
            out = json.dumps(msg)
            print(f"  >> {out}")
            await ws.send(out)
            await listen(ws, 6)
    except Exception as e:
        print(f"  ERROR: {e}")


async def main():
    if not API_KEY:
        print("WARNING: DZENGI_API_KEY not set\n")
    print(f"WS URL: {BASE_URL}")
    print(f"Symbol: {SYMBOL}  Interval: {INTERVAL}\n")

    await test_listen_first()
    await asyncio.sleep(1)
    await test_flat_json()
    await asyncio.sleep(1)
    await test_url_params()
    await asyncio.sleep(1)
    await test_no_prefix()
    await asyncio.sleep(1)
    await test_greet_then_sub()

    print("\n\nDone. Look for '*** OHLC DATA RECEIVED ***' above.")


asyncio.run(main())
