"""
Shared pytest fixtures used across the test suite.
"""
import io
import pytest
import pandas as pd


class MockUploadedFile:
    """Mimics Streamlit's UploadedFile interface (.name, .getvalue())
    so data_loader.py can be tested without a running Streamlit session."""
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """A small, deterministic sales-shaped DataFrame for cross-module tests."""
    return pd.DataFrame({
        "Order_ID": [f"O{i}" for i in range(1, 21)],
        "Order_Date": pd.date_range("2024-01-01", periods=20, freq="D"),
        "Customer_ID": [f"C{i % 5}" for i in range(20)],
        "Product": ["Laptop", "Phone", "Chair", "Desk"] * 5,
        "Category": ["Electronics", "Electronics", "Furniture", "Furniture"] * 5,
        "Quantity": [1, 2, 1, 3] * 5,
        "Revenue": [1000, 500, 200, 400] * 5,
        "Region": ["North", "South", "East", "West"] * 5,
    })


@pytest.fixture
def mock_csv_file():
    csv_content = b"Order_ID,Revenue\nO1,100\nO2,200\nO3,300\n"
    return MockUploadedFile("sample.csv", csv_content)


@pytest.fixture
def mock_empty_csv_file():
    return MockUploadedFile("empty.csv", b"")


@pytest.fixture
def mock_unsupported_file():
    return MockUploadedFile("notes.txt", b"just some text")


@pytest.fixture
def mock_malformed_csv_file():
    # Inconsistent column counts across rows — should trigger a parser error
    bad_content = b"A,B,C\n1,2\n3,4,5,6\n"
    return MockUploadedFile("malformed.csv", bad_content)