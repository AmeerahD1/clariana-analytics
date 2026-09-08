"""
Tests for modules/forecasting.py — valid time series, insufficient data.
"""
import pytest
import pandas as pd
from modules.forecasting import run_forecast, prepare_time_series


def test_prepare_time_series_resamples_correctly():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=10, freq="D"),
        "revenue": [100] * 10,
    })
    series = prepare_time_series(df, "date", "revenue", freq="D")
    assert len(series) == 10
    assert series["value"].sum() == 1000


def test_run_forecast_valid_data_returns_expected_shape():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30, freq="D"),
        "revenue": [100 + i * 5 for i in range(30)],  # clear upward trend
    })
    result = run_forecast(df, "date", "revenue", periods=7, freq="D")

    assert len(result["forecast"]) == 7
    assert result["expected_growth_pct"] is not None
    # Upward trend in input should produce positive expected growth
    assert result["expected_growth_pct"] > 0


def test_run_forecast_insufficient_data_raises():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=3, freq="D"),
        "revenue": [100, 200, 150],
    })
    with pytest.raises(ValueError, match="Not enough historical data"):
        run_forecast(df, "date", "revenue", periods=7, freq="D")


def test_run_forecast_confidence_band_widens_with_horizon():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=20, freq="D"),
        "revenue": [100 + (i % 3) * 10 for i in range(20)],  # some noise
    })
    result = run_forecast(df, "date", "revenue", periods=10, freq="D")
    fc = result["forecast"]
    first_band_width = fc.iloc[0]["upper_bound"] - fc.iloc[0]["lower_bound"]
    last_band_width = fc.iloc[-1]["upper_bound"] - fc.iloc[-1]["lower_bound"]
    assert last_band_width >= first_band_width