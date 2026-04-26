import numpy as np
from src.indicators.ema import calculate_ema


def calculate_macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """Return MACD values for the latest candle.

    Returns:
        {
            "macd": float,
            "signal": float,
            "histogram": float,
            "crossover": "bullish" | "bearish" | None,
        }
    """
    if len(closes) < slow + signal:
        nan = float("nan")
        return {"macd": nan, "signal": nan, "histogram": nan, "crossover": None}

    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)

    macd_line = ema_fast - ema_slow
    # Drop leading NaNs before computing signal EMA
    valid_start = slow - 1
    macd_valid = macd_line[valid_start:]
    signal_arr = calculate_ema(macd_valid, signal)

    macd_val = macd_line[-1]
    signal_val = signal_arr[-1]
    histogram = macd_val - signal_val

    crossover = None
    if len(macd_valid) >= 2 and len(signal_arr) >= 2:
        prev_macd = macd_valid[-2]
        prev_signal = signal_arr[-2]
        if not np.isnan(prev_signal) and not np.isnan(signal_val):
            if prev_macd <= prev_signal and macd_val > signal_val:
                crossover = "bullish"
            elif prev_macd >= prev_signal and macd_val < signal_val:
                crossover = "bearish"

    return {
        "macd": macd_val,
        "signal": signal_val,
        "histogram": histogram,
        "crossover": crossover,
    }
