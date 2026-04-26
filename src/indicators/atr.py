import numpy as np


def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Average True Range using Wilder smoothing. Returns NaN if insufficient data."""
    if len(closes) < period + 1:
        return float("nan")

    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1]),
        ),
    )

    # Wilder smoothing
    atr = float(np.mean(tr[:period]))
    for val in tr[period:]:
        atr = (atr * (period - 1) + val) / period

    return atr
