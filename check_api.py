"""Quick diagnostic: discover real symbol names and test endpoints."""
import asyncio
import aiohttp
import json


BASE_URL = "https://demo-api-adapter.dzengi.com"


async def main():
    async with aiohttp.ClientSession() as s:

        # 1. exchangeInfo — list all available symbols
        print("=== /api/v1/exchangeInfo ===")
        try:
            async with s.get(f"{BASE_URL}/api/v1/exchangeInfo") as r:
                print(f"Status: {r.status}")
                if r.status == 200:
                    data = await r.json(content_type=None)
                    symbols = data.get("symbols", data)
                    if isinstance(symbols, list):
                        print(f"Total symbols: {len(symbols)}")
                        print("First 10:")
                        for sym in symbols[:10]:
                            if isinstance(sym, dict):
                                print(f"  {sym.get('symbol') or sym}")
                            else:
                                print(f"  {sym}")
                    else:
                        print(json.dumps(data, indent=2)[:2000])
                else:
                    text = await r.text()
                    print(f"Error body: {text[:500]}")
        except Exception as e:
            print(f"Exception: {e}")

        print()

        # 2. Try klines with a few symbol formats
        for sym in ["BTCUSDT", "BTC/USDT", "BTCUSD", "BTC-USDT"]:
            print(f"=== klines symbol={sym} ===")
            try:
                async with s.get(
                    f"{BASE_URL}/api/v1/klines",
                    params={"symbol": sym, "interval": "15m", "limit": "5"},
                ) as r:
                    print(f"Status: {r.status}")
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        print(f"Got {len(data)} candles — SYMBOL WORKS: {sym}")
                    else:
                        text = await r.text()
                        print(f"Error: {text[:200]}")
            except Exception as e:
                print(f"Exception: {e}")
            print()

        # 3. ticker/price — try a few formats too
        for sym in ["BTCUSDT", "BTC/USDT"]:
            print(f"=== ticker/price symbol={sym} ===")
            try:
                async with s.get(
                    f"{BASE_URL}/api/v1/ticker/price",
                    params={"symbol": sym},
                ) as r:
                    print(f"Status: {r.status}")
                    text = await r.text()
                    print(f"Body: {text[:300]}")
            except Exception as e:
                print(f"Exception: {e}")
            print()


asyncio.run(main())
