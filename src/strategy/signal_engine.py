import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict

import numpy as np

from src import config
from src.indicators.rsi import calculate_rsi
from src.indicators.ema import ema_cross
from src.indicators.macd import calculate_macd
from src.indicators.bollinger import calculate_bollinger
from src.indicators.volume import calculate_volume
from src.indicators.atr import calculate_atr

logger = logging.getLogger(__name__)


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class SignalStrength(Enum):
    STRONG = "STRONG"
    MEDIUM = "MEDIUM"
    WEAK = "WEAK"


@dataclass
class Signal:
    symbol: str
    signal_type: SignalType
    strength: SignalStrength
    price: float
    entry: float
    stop_loss: float
    take_profit: float
    atr: float
    score: int
    max_score: int
    conditions: Dict[str, bool]
    indicators: dict
    timestamp: float


@dataclass
class CandleBuffer:
    """Rolling buffer of OHLCV data for one symbol."""
    symbol: str
    maxlen: int = config.CANDLE_BUFFER_SIZE

    opens: deque = field(default_factory=lambda: deque(maxlen=config.CANDLE_BUFFER_SIZE))
    highs: deque = field(default_factory=lambda: deque(maxlen=config.CANDLE_BUFFER_SIZE))
    lows: deque = field(default_factory=lambda: deque(maxlen=config.CANDLE_BUFFER_SIZE))
    closes: deque = field(default_factory=lambda: deque(maxlen=config.CANDLE_BUFFER_SIZE))
    volumes: deque = field(default_factory=lambda: deque(maxlen=config.CANDLE_BUFFER_SIZE))

    def add(self, candle: dict):
        self.opens.append(candle["open"])
        self.highs.append(candle["high"])
        self.lows.append(candle["low"])
        self.closes.append(candle["close"])
        self.volumes.append(candle["volume"])

    def load_klines(self, klines: list):
        """Populate buffer from REST klines response."""
        for k in klines:
            self.opens.append(float(k[1]))
            self.highs.append(float(k[2]))
            self.lows.append(float(k[3]))
            self.closes.append(float(k[4]))
            self.volumes.append(float(k[5]))

    @property
    def ready(self) -> bool:
        min_len = max(
            config.RSI_PERIOD + 1,
            config.EMA_SLOW + 2,
            config.MACD_SLOW + config.MACD_SIGNAL,
            config.BB_PERIOD,
            config.VOLUME_PERIOD + 1,
        )
        return len(self.closes) >= min_len

    def np_closes(self) -> np.ndarray:
        return np.array(self.closes, dtype=float)

    def np_volumes(self) -> np.ndarray:
        return np.array(self.volumes, dtype=float)


class SignalEngine:
    """Evaluate all indicators and produce a trade signal when confluence is met."""

    def __init__(self):
        self._buffers: Dict[str, CandleBuffer] = {}

    def get_buffer(self, symbol: str) -> CandleBuffer:
        if symbol not in self._buffers:
            self._buffers[symbol] = CandleBuffer(symbol=symbol)
        return self._buffers[symbol]

    def on_new_candle(self, symbol: str, candle: dict) -> Optional[Signal]:
        buf = self.get_buffer(symbol)
        buf.add(candle)

        if not buf.ready:
            logger.debug("%s buffer not ready (%d candles)", symbol, len(buf.closes))
            return None

        return self._evaluate(symbol, buf, candle["close"], candle.get("close_time", 0))

    def _evaluate(self, symbol: str, buf: CandleBuffer, price: float, ts: float) -> Optional[Signal]:
        closes = buf.np_closes()
        volumes = buf.np_volumes()
        highs = np.array(buf.highs, dtype=float)
        lows = np.array(buf.lows, dtype=float)

        rsi = calculate_rsi(closes, config.RSI_PERIOD)
        ema = ema_cross(closes, config.EMA_FAST, config.EMA_SLOW)
        macd = calculate_macd(closes, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL)
        bb = calculate_bollinger(closes, config.BB_PERIOD, config.BB_STD_DEV)
        vol = calculate_volume(volumes, config.VOLUME_PERIOD, config.VOLUME_MULTIPLIER)
        atr = calculate_atr(highs, lows, closes, config.ATR_PERIOD)

        indicators = {"rsi": rsi, "ema": ema, "macd": macd, "bb": bb, "volume": vol, "atr": atr}

        buy_conditions = self._check_buy(rsi, ema, macd, bb, vol)
        sell_conditions = self._check_sell(rsi, ema, macd, bb, vol)

        buy_score = sum(buy_conditions.values())
        sell_score = sum(sell_conditions.values())

        # Volume data is not available via WebSocket (always 0), so max effective score is 4
        volume_available = vol.get("ratio", 0) > 0
        effective_max = 5 if volume_available else 4

        logger.info(
            "%s | RSI=%.1f  EMA=%s  MACD=%s  BB_pct=%.2f  Vol=%s  ATR=%.2f | buy=%d sell=%d",
            symbol, rsi, ema["trend"], macd["crossover"],
            bb.get("percent_b", float("nan")),
            f"{vol.get('ratio', 0):.2f}" if volume_available else "N/A",
            atr, buy_score, sell_score,
        )

        best_score = max(buy_score, sell_score)
        min_required = config.MIN_SIGNALS if volume_available else max(config.MIN_SIGNALS - 1, 2)
        if best_score < min_required:
            return None

        signal_type = SignalType.BUY if buy_score >= sell_score else SignalType.SELL
        conditions = buy_conditions if signal_type == SignalType.BUY else sell_conditions
        score = buy_score if signal_type == SignalType.BUY else sell_score
        strength = SignalStrength.STRONG if score >= (4 if volume_available else 3) else SignalStrength.MEDIUM

        entry = price
        if not np.isnan(atr):
            sl = entry - config.ATR_SL_MULTIPLIER * atr if signal_type == SignalType.BUY \
                else entry + config.ATR_SL_MULTIPLIER * atr
            tp = entry + config.ATR_TP_MULTIPLIER * atr if signal_type == SignalType.BUY \
                else entry - config.ATR_TP_MULTIPLIER * atr
        else:
            sl = tp = float("nan")

        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            price=price,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            atr=atr,
            score=score,
            max_score=effective_max,
            conditions=conditions,
            indicators=indicators,
            timestamp=ts / 1000 if ts > 1e10 else ts,
        )

    @staticmethod
    def _check_buy(rsi, ema, macd, bb, vol) -> Dict[str, bool]:
        return {
            "RSI oversold": not np.isnan(rsi) and rsi < 35,
            "EMA bullish": ema["trend"] == "bullish" or ema["crossover"] == "golden",
            "MACD bullish": macd["crossover"] == "bullish" or (
                not np.isnan(macd.get("histogram", float("nan")))
                and macd["histogram"] > 0
            ),
            "BB lower touch": not np.isnan(bb.get("percent_b", float("nan"))) and bb["percent_b"] <= 0.1,
            "Volume spike": vol.get("confirmed", False),
        }

    @staticmethod
    def _check_sell(rsi, ema, macd, bb, vol) -> Dict[str, bool]:
        return {
            "RSI overbought": not np.isnan(rsi) and rsi > 65,
            "EMA bearish": ema["trend"] == "bearish" or ema["crossover"] == "death",
            "MACD bearish": macd["crossover"] == "bearish" or (
                not np.isnan(macd.get("histogram", float("nan")))
                and macd["histogram"] < 0
            ),
            "BB upper touch": not np.isnan(bb.get("percent_b", float("nan"))) and bb["percent_b"] >= 0.9,
            "Volume spike": vol.get("confirmed", False),
        }
