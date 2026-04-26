import numpy as np


def calculate_ema(closes: np.ndarray, period: int) -> np.ndarray:
    """Return EMA array of the same length as `closes`."""
    if len(closes) < period:
        return np.full(len(closes), float("nan"))

    k = 2.0 / (period + 1)
    ema = np.empty(len(closes))
    ema[:] = float("nan")
    ema[period - 1] = np.mean(closes[:period])

    for i in range(period, len(closes)):
        ema[i] = closes[i] * k + ema[i - 1] * (1 - k)

    return ema


def ema_cross(closes: np.ndarray, fast: int, slow: int) -> dict:
    """Return EMA cross state for the last two candles.

    Returns:
        {
            "fast": float,
            "slow": float,
            "trend": "bullish" | "bearish" | "neutral",
            "crossover": "golden" | "death" | None,  # happened on last candle
        }
    """
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)

    n = len(closes)
    if n < 2 or np.isnan(ema_fast[-1]) or np.isnan(ema_slow[-1]):
        return {"fast": float("nan"), "slow": float("nan"), "trend": "neutral", "crossover": None}

    curr_fast, curr_slow = ema_fast[-1], ema_slow[-1]
    prev_fast, prev_slow = ema_fast[-2], ema_slow[-2]

    crossover = None
    if not np.isnan(prev_fast) and not np.isnan(prev_slow):
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            crossover = "golden"
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            crossover = "death"

    trend = "bullish" if curr_fast > curr_slow else "bearish"

    return {
        "fast": curr_fast,
        "slow": curr_slow,
        "trend": trend,
        "crossover": crossover,
    }
