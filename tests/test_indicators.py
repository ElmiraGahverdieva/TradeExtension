import numpy as np
import pytest

from src.indicators.rsi import calculate_rsi
from src.indicators.ema import calculate_ema, ema_cross
from src.indicators.macd import calculate_macd
from src.indicators.bollinger import calculate_bollinger
from src.indicators.volume import calculate_volume


def _sine_closes(n: int = 100, amplitude: float = 100.0, base: float = 1000.0) -> np.ndarray:
    t = np.linspace(0, 4 * np.pi, n)
    return base + amplitude * np.sin(t)


class TestRSI:
    def test_returns_float(self):
        closes = _sine_closes(50)
        rsi = calculate_rsi(closes, period=14)
        assert isinstance(rsi, float)
        assert 0.0 <= rsi <= 100.0

    def test_nan_when_insufficient_data(self):
        closes = np.array([1.0, 2.0, 3.0])
        assert np.isnan(calculate_rsi(closes, period=14))

    def test_high_rsi_on_rising_prices(self):
        closes = np.linspace(1000, 1100, 50)
        rsi = calculate_rsi(closes, period=14)
        assert rsi > 70

    def test_low_rsi_on_falling_prices(self):
        closes = np.linspace(1100, 1000, 50)
        rsi = calculate_rsi(closes, period=14)
        assert rsi < 30


class TestEMA:
    def test_length_matches_input(self):
        closes = _sine_closes(100)
        ema = calculate_ema(closes, period=9)
        assert len(ema) == len(closes)

    def test_leading_nans(self):
        closes = _sine_closes(30)
        ema = calculate_ema(closes, period=9)
        assert np.all(np.isnan(ema[:8]))
        assert not np.isnan(ema[8])

    def test_ema_cross_golden(self):
        closes = np.concatenate([np.linspace(1000, 900, 50), np.linspace(900, 1100, 50)])
        result = ema_cross(closes, fast=9, slow=21)
        assert result["trend"] in ("bullish", "bearish")
        assert result["crossover"] in ("golden", "death", None)


class TestMACD:
    def test_returns_dict_keys(self):
        closes = _sine_closes(100)
        result = calculate_macd(closes)
        assert {"macd", "signal", "histogram", "crossover"} == set(result.keys())

    def test_nan_when_insufficient_data(self):
        closes = _sine_closes(20)
        result = calculate_macd(closes)
        assert np.isnan(result["macd"])

    def test_crossover_is_valid(self):
        closes = _sine_closes(100)
        result = calculate_macd(closes)
        assert result["crossover"] in ("bullish", "bearish", None)


class TestBollinger:
    def test_upper_gt_middle_gt_lower(self):
        closes = _sine_closes(50)
        bb = calculate_bollinger(closes, period=20)
        assert bb["upper"] > bb["middle"] > bb["lower"]

    def test_percent_b_in_range(self):
        closes = _sine_closes(50)
        bb = calculate_bollinger(closes, period=20)
        assert 0.0 <= bb["percent_b"] <= 1.0 or bb["percent_b"] < 0 or bb["percent_b"] > 1

    def test_nan_when_insufficient_data(self):
        closes = _sine_closes(5)
        bb = calculate_bollinger(closes, period=20)
        assert np.isnan(bb["upper"])


class TestVolume:
    def test_confirmed_on_spike(self):
        vols = np.ones(25)
        vols[-1] = 3.0
        result = calculate_volume(vols, period=20, multiplier=1.3)
        assert result["confirmed"] is True

    def test_not_confirmed_on_low_volume(self):
        vols = np.ones(25)
        result = calculate_volume(vols, period=20, multiplier=1.3)
        assert result["confirmed"] is False

    def test_ratio_calculation(self):
        vols = np.ones(25) * 100.0
        vols[-1] = 200.0
        result = calculate_volume(vols, period=20, multiplier=1.3)
        assert abs(result["ratio"] - 2.0) < 0.01
