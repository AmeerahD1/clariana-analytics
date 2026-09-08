"""
Tests for modules/data_profiler.py — missing values, duplicates, data types.
"""
import pandas as pd
from modules.data_profiler import get_overview, get_data_quality, get_numerical_stats, get_categorical_analysis


def test_overview_counts_columns_by_type(sample_df):
    overview = get_overview(sample_df)
    assert overview["rows"] == 20
    assert "Revenue" in overview["numeric_columns"]
    assert "Product" in overview["categorical_columns"]
    assert "Order_Date" in overview["datetime_columns"]


def test_data_quality_detects_missing_values():
    df = pd.DataFrame({"A": [1, 2, None, 4], "B": [1, 2, 3, 4]})
    quality = get_data_quality(df)
    assert quality["missing_total"] == 1
    assert quality["missing_pct_of_all_cells"] > 0


def test_data_quality_detects_duplicates():
    df = pd.DataFrame({"A": [1, 1, 2], "B": [1, 1, 2]})
    quality = get_data_quality(df)
    assert quality["duplicate_rows"] == 1


def test_data_quality_flags_constant_column():
    df = pd.DataFrame({"A": [1, 1, 1], "B": [1, 2, 3]})
    quality = get_data_quality(df)
    assert any("only one unique value" in note for note in quality["suspicious_columns"])


def test_numerical_stats_only_numeric_columns(sample_df):
    stats = get_numerical_stats(sample_df)
    assert "Revenue" in stats["Column"].values
    assert "Product" not in stats["Column"].values


def test_categorical_analysis_returns_top_values(sample_df):
    analysis = get_categorical_analysis(sample_df)
    assert "Product" in analysis
    assert analysis["Product"]["unique_count"] == 4