import numpy as np


def calculate_bollinger(closes: np.ndarray, period: int = 20, std_dev: float = 2.0) -> dict:
    """Return Bollinger Bands values for the latest candle.

    Returns:
        {
            "upper": float,
            "middle": float,
            "lower": float,
            "width": float,       # (upper - lower) / middle — squeeze indicator
            "percent_b": float,   # where price is within the bands (0=lower, 1=upper)
        }
    """
    if len(closes) < period:
        nan = float("nan")
        return {"upper": nan, "middle": nan, "lower": nan, "width": nan, "percent_b": nan}

    window = closes[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window, ddof=0))

    upper = middle + std_dev * std
    lower = middle - std_dev * std
    width = (upper - lower) / middle if middle != 0 else float("nan")

    price = closes[-1]
    band_range = upper - lower
    percent_b = (price - lower) / band_range if band_range != 0 else 0.5

    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "width": width,
        "percent_b": percent_b,
    }
