import numpy as np


def calculate_volume(volumes: np.ndarray, period: int = 20, multiplier: float = 1.3) -> dict:
    """Return volume analysis for the latest candle.

    Returns:
        {
            "current": float,
            "average": float,
            "ratio": float,       # current / average
            "confirmed": bool,    # current > average * multiplier
        }
    """
    if len(volumes) < period:
        nan = float("nan")
        return {"current": nan, "average": nan, "ratio": nan, "confirmed": False}

    current = float(volumes[-1])
    average = float(np.mean(volumes[-period - 1:-1]))  # exclude current candle

    if average == 0:
        ratio = float("nan")
        confirmed = False
    else:
        ratio = current / average
        confirmed = ratio >= multiplier

    return {
        "current": current,
        "average": average,
        "ratio": ratio,
        "confirmed": confirmed,
    }
