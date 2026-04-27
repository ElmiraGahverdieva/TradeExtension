import os
from dotenv import load_dotenv

load_dotenv()

_ENV = os.getenv("DZENGI_ENV", "demo").lower()

DEMO_REST_URL = "https://demo-api-adapter.dzengi.com"
LIVE_REST_URL = "https://api-adapter.dzengi.com"
DEMO_WS_URL = "wss://demo-api-adapter.dzengi.com/connect"
LIVE_WS_URL = "wss://api-adapter.dzengi.com/connect"

REST_BASE_URL = DEMO_REST_URL if _ENV == "demo" else LIVE_REST_URL
WS_URL = DEMO_WS_URL if _ENV == "demo" else LIVE_WS_URL

API_KEY = os.getenv("DZENGI_API_KEY", "")
SECRET_KEY = os.getenv("DZENGI_SECRET_KEY", "")

SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "BTC/USD_LEVERAGE,ETH/USD_LEVERAGE").split(",")]
TIMEFRAMES = [s.strip() for s in os.getenv("TIMEFRAMES", "1m,5m,15m,30m,1h").split(",")]
TIMEFRAME = TIMEFRAMES[0] if TIMEFRAMES else "1m"
MIN_SIGNALS = int(os.getenv("MIN_SIGNALS", "3"))

RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
RSI_OVERSOLD = float(os.getenv("RSI_OVERSOLD", "30"))
RSI_OVERBOUGHT = float(os.getenv("RSI_OVERBOUGHT", "70"))

EMA_FAST = int(os.getenv("EMA_FAST", "9"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "21"))

MACD_FAST = int(os.getenv("MACD_FAST", "12"))
MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))

BB_PERIOD = int(os.getenv("BB_PERIOD", "20"))
BB_STD_DEV = float(os.getenv("BB_STD_DEV", "2.0"))

VOLUME_PERIOD = int(os.getenv("VOLUME_PERIOD", "20"))
VOLUME_MULTIPLIER = float(os.getenv("VOLUME_MULTIPLIER", "1.3"))

NOTIFICATION_MODE = os.getenv("NOTIFICATION_MODE", "desktop")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/trading.log")

CANDLE_BUFFER_SIZE = 200
WS_PING_INTERVAL = 20

ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
ATR_SL_MULTIPLIER = float(os.getenv("ATR_SL_MULTIPLIER", "1.5"))
ATR_TP_MULTIPLIER = float(os.getenv("ATR_TP_MULTIPLIER", "2.5"))
