"""
Tests for modules/data_loader.py — CSV loading, Excel loading, invalid files.
"""
import pandas as pd
from modules.data_loader import load_file, MAX_FILE_SIZE_MB


def test_load_valid_csv(mock_csv_file):
    df, error = load_file(mock_csv_file)
    assert error is None
    assert df is not None
    assert list(df.columns) == ["Order_ID", "Revenue"]
    assert len(df) == 3


def test_load_none_file():
    df, error = load_file(None)
    assert df is None
    assert error == "No file was uploaded."


def test_load_unsupported_file_type(mock_unsupported_file):
    df, error = load_file(mock_unsupported_file)
    assert df is None
    assert "Unsupported file type" in error


def test_load_empty_file(mock_empty_csv_file):
    df, error = load_file(mock_empty_csv_file)
    assert df is None
    assert "empty" in error.lower()


def test_load_malformed_csv(mock_malformed_csv_file):
    df, error = load_file(mock_malformed_csv_file)
    assert df is None
    assert error is not None  # exact wording may vary by pandas version


def test_file_size_limit_enforced():
    from tests.conftest import MockUploadedFile
    oversized_content = b"a" * (MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
    big_file = MockUploadedFile("big.csv", oversized_content)
    df, error = load_file(big_file)
    assert df is None
    assert "too large" in error.lower()