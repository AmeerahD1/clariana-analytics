"""
Simple, explainable forecasting: linear trend extrapolation over a
resampled time series, with a confidence interval derived from how much
actual historical points scattered around the fitted trend line.

Deliberately NOT a black-box model — the whole point is that every number
here can be explained in one sentence: "we fit a straight line through
resampled totals and projected it forward."
"""
import numpy as np
import pandas as pd


def get_numeric_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=np.number).columns.tolist()


def get_date_columns(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include="datetime64").columns.tolist()


def prepare_time_series(df: pd.DataFrame, date_col: str, metric_col: str, freq: str = "D") -> pd.DataFrame:
    """Resamples the metric to the given frequency, summing within each period."""
    series = (
        df.dropna(subset=[date_col, metric_col])
        .set_index(date_col)
        .resample(freq)[metric_col]
        .sum()
        .reset_index()
    )
    series.columns = ["date", "value"]
    return series


def run_forecast(df: pd.DataFrame, date_col: str, metric_col: str, periods: int, freq: str = "D") -> dict:
    """
    Fits a linear trend to the historical resampled series and projects it
    forward `periods` steps. Returns a dict with historical data, forecast
    data, and metadata — never a false sense of precision.

    Raises ValueError if there isn't enough data to forecast meaningfully.
    """
    series = prepare_time_series(df, date_col, metric_col, freq)
    series = series.dropna()

    if len(series) < 5:
        raise ValueError(
            f"Not enough historical data points ({len(series)}) to forecast reliably. "
            "At least 5 time periods are recommended."
        )

    x = np.arange(len(series))
    y = series["value"].values

    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    residuals = y - fitted
    residual_std = residuals.std()

    future_x = np.arange(len(series), len(series) + periods)
    forecast_values = slope * future_x + intercept

    growth_factor = np.linspace(1.0, 1.5, periods)
    margin = 1.96 * residual_std * growth_factor

    last_date = series["date"].max()
    future_dates = pd.date_range(start=last_date, periods=periods + 1, freq=freq)[1:]

    forecast_df = pd.DataFrame({
        "date": future_dates,
        "forecast": forecast_values,
        "lower_bound": forecast_values - margin,
        "upper_bound": forecast_values + margin,
    })

    total_historical = y.sum()
    avg_historical_per_period = y.mean()
    avg_forecast_per_period = forecast_values.mean()
    # Compare average-per-period, not raw totals — the historical and
    # forecast windows usually cover a different number of periods, so
    # comparing raw sums would be biased toward "decline" whenever the
    # forecast horizon is shorter than the historical window, even on a
    # genuine upward trend.
    growth_pct = (
        ((avg_forecast_per_period - avg_historical_per_period) / avg_historical_per_period * 100)
        if avg_historical_per_period else None
    )

    return {
        "historical": series,
        "forecast": forecast_df,
        "slope": float(slope),
        "residual_std": float(residual_std),
        "expected_growth_pct": float(growth_pct) if growth_pct is not None else None,
        "periods": periods,
        "metric_col": metric_col,
    }