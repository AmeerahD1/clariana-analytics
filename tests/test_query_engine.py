"""
Tests for modules/query_engine.py — valid queries, invalid queries,
destructive SQL rejection.
"""
import pytest
from modules.query_engine import (
    execute_plan,
    validate_sql,
    execute_sql,
)


def test_execute_plan_single_value(sample_df):
    plan = {"operation": "single_value", "metric": "Revenue", "agg": "sum"}
    result = execute_plan(sample_df, plan)
    assert result == sample_df["Revenue"].sum()


def test_execute_plan_group_by(sample_df):
    plan = {
        "operation": "group_by", "metric": "Revenue", "agg": "sum",
        "group_by": "Region", "top_n": None, "sort": "desc",
    }
    result = execute_plan(sample_df, plan)
    assert "Region" in result.columns
    assert "Revenue" in result.columns


def test_execute_plan_invalid_column_raises(sample_df):
    plan = {"operation": "single_value", "metric": "NotAColumn", "agg": "sum"}
    with pytest.raises(ValueError):
        execute_plan(sample_df, plan)


def test_execute_plan_correlation(sample_df):
    plan = {"operation": "correlation", "metric_a": "Revenue", "metric_b": "Quantity"}
    result = execute_plan(sample_df, plan)
    assert -1 <= result <= 1


@pytest.mark.parametrize("bad_sql,expected_reason", [
    ("DROP TABLE dataset", "Only SELECT"),
    ("SELECT * FROM dataset; DELETE FROM dataset", "Multiple statements"),
    ("SELECT * FROM dataset -- ; DROP TABLE dataset", None),  # comment-hidden; should still pass since no real 2nd statement
    ("UPDATE dataset SET Revenue = 0", "Only SELECT"),
    ("", "Empty"),
])
def test_validate_sql_rejects_unsafe_queries(bad_sql, expected_reason):
    error = validate_sql(bad_sql)
    if expected_reason:
        assert error is not None
        assert expected_reason.lower() in error.lower()


def test_validate_sql_accepts_valid_select():
    error = validate_sql("SELECT Region, SUM(Revenue) FROM dataset GROUP BY Region")
    assert error is None


def test_execute_sql_valid_query(sample_df):
    result = execute_sql(sample_df, "SELECT Region, SUM(Revenue) as Revenue FROM dataset GROUP BY Region")
    assert "Region" in result.columns
    assert len(result) == 4  # North, South, East, West


def test_execute_sql_rejects_destructive_query(sample_df):
    with pytest.raises(ValueError):
        execute_sql(sample_df, "DELETE FROM dataset")