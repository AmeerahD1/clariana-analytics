"""
Tests for modules/visualization.py — supported chart types, empty result handling.
"""
import pandas as pd
from modules.visualization import choose_chart_type, render_chart


def test_choose_chart_type_scalar_result_returns_none():
    plan = {"operation": "single_value"}
    assert choose_chart_type(plan, 12345.67) is None


def test_choose_chart_type_empty_dataframe_returns_none():
    plan = {"operation": "group_by"}
    empty_df = pd.DataFrame(columns=["Region", "Revenue"])
    assert choose_chart_type(plan, empty_df) is None


def test_choose_chart_type_group_by_small_result_is_pie():
    plan = {"operation": "group_by"}  # no top_n key present
    df = pd.DataFrame({"Region": ["North", "South"], "Revenue": [100, 200]})
    assert choose_chart_type(plan, df) == "pie"


def test_choose_chart_type_group_by_with_top_n_is_bar():
    plan = {"operation": "group_by", "top_n": 1}
    df = pd.DataFrame({"Region": ["North"], "Revenue": [100]})
    assert choose_chart_type(plan, df) == "bar"


def test_choose_chart_type_correlation_returns_none():
    plan = {"operation": "correlation"}
    assert choose_chart_type(plan, 0.85) is None


def test_render_chart_returns_none_for_none_chart_type():
    plan = {"operation": "group_by"}
    df = pd.DataFrame({"Region": ["North"], "Revenue": [100]})
    assert render_chart(plan, df, None) is None


def test_render_chart_produces_figure_for_bar():
    plan = {"operation": "group_by", "top_n": 1}
    df = pd.DataFrame({"Region": ["North", "South"], "Revenue": [100, 200]})
    fig = render_chart(plan, df, "bar")
    assert fig is not None


def test_render_chart_handles_missing_columns_gracefully():
    # group_by/filtered_group_by charts index result.columns[1] for the
    # metric — a single-column result has no second column to read, which
    # should be caught and logged internally (Phase 19), never raised.
    plan = {"operation": "group_by"}
    df = pd.DataFrame({"OnlyOneColumn": [1, 2, 3]})
    result = render_chart(plan, df, "bar")
    assert result is None


def test_render_chart_multi_metric_with_no_metric_columns_still_returns_a_figure():
    # A degenerate multi_metric_group_by plan (no metric columns beyond the
    # group column) doesn't raise — Plotly happily builds an empty chart.
    # This documents that behavior rather than asserting a crash that
    # doesn't actually occur.
    plan = {"operation": "multi_metric_group_by"}
    df = pd.DataFrame({"OnlyOneColumn": [1, 2, 3]})
    result = render_chart(plan, df, "bar")
    assert result is not None