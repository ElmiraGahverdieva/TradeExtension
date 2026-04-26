"""Quick diagnostic: discover real symbol names and test endpoints."""
import asyncio
import aiohttp
import json
import sys

BASE_URL = "https://demo-api-adapter.dzengi.com"
TIMEOUT = aiohttp.ClientTimeout(total=10)


async def get(session, url, params=None):
    print(f"  -> GET {url} {params or ''}", flush=True)
    try:
        async with session.get(url, params=params, timeout=TIMEOUT) as r:
            text = await r.text()
            print(f"  <- {r.status}", flush=True)
            return r.status, text
    except asyncio.TimeoutError:
        print("  <- TIMEOUT (10s)", flush=True)
        return None, None
    except Exception as e:
        print(f"  <- ERROR: {e}", flush=True)
        return None, None


async def main():
    print("Starting API check...", flush=True)
    print(f"Base URL: {BASE_URL}\n", flush=True)

    async with aiohttp.ClientSession() as s:

        # 1. exchangeInfo
        print("=== 1. exchangeInfo ===", flush=True)
        status, text = await get(s, f"{BASE_URL}/api/v1/exchangeInfo")
        if status == 200:
            try:
                data = json.loads(text)
                symbols = data.get("symbols", data)
                if isinstance(symbols, list):
                    print(f"Total symbols: {len(symbols)}")
                    print("First 15 symbol names:")
                    for sym in symbols[:15]:
                        name = sym.get("symbol") if isinstance(sym, dict) else sym
                        print(f"  {name}")
                else:
                    print(text[:1000])
            except Exception:
                print(text[:1000])
        elif text:
            print(f"Body: {text[:300]}")
        print()

        # 2. klines — try different symbol formats
        print("=== 2. klines (trying symbol formats) ===", flush=True)
        for sym in ["BTCUSDT", "BTC/USDT", "BTCUSD", "BTC-USDT", "XBT/USDT"]:
            status, text = await get(
                s, f"{BASE_URL}/api/v1/klines",
                {"symbol": sym, "interval": "15m", "limit": "3"}
            )
            if status == 200:
                print(f"  *** WORKS: symbol={sym} ***")
                break
            elif text:
                print(f"  error: {text[:100]}")
        print()

        # 3. ticker price
        print("=== 3. ticker/price ===", flush=True)
        status, text = await get(s, f"{BASE_URL}/api/v1/ticker/price")
        if text:
            print(f"Body: {text[:500]}")
        print()

    print("Done.", flush=True)


asyncio.run(main())
