"""Pytest fixtures for mssql-mcp tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


def get_tool_fn(tool):
    """Extract the underlying function from a FastMCP FunctionTool."""
    # FastMCP wraps functions in FunctionTool objects
    # The original function is accessible via .fn attribute
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment variables for testing."""
    monkeypatch.setenv("MSSQL_SERVER", "test-server")
    monkeypatch.setenv("MSSQL_DATABASE", "test-db")
    monkeypatch.setenv("MSSQL_WINDOWS_AUTH", "true")


@pytest.fixture
def mock_env_sql_auth(monkeypatch):
    """Set up environment variables for SQL authentication."""
    monkeypatch.setenv("MSSQL_SERVER", "test-server")
    monkeypatch.setenv("MSSQL_DATABASE", "test-db")
    monkeypatch.setenv("MSSQL_USER", "test-user")
    monkeypatch.setenv("MSSQL_PASSWORD", "test-password")


@pytest.fixture
def mock_cursor():
    """Create a mock cursor."""
    cursor = MagicMock()
    cursor.description = [
        ("col1",), ("col2",), ("col3",)
    ]
    cursor.fetchall.return_value = [
        ("val1", "val2", "val3"),
        ("val4", "val5", "val6"),
    ]
    cursor.fetchone.return_value = ("val1", "val2", "val3")
    cursor.rowcount = 2
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """Create a mock connection."""
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    conn.execute.return_value = None  # For health check
    return conn


@pytest.fixture
def mock_pyodbc(mock_connection) -> Generator[MagicMock, None, None]:
    """Mock pyodbc.connect to return mock connection."""
    with patch("mssql_mcp.server.pyodbc") as mock:
        mock.connect.return_value = mock_connection
        mock.drivers.return_value = ["ODBC Driver 18 for SQL Server"]
        yield mock


@pytest.fixture(autouse=True)
def reset_connection():
    """Reset the global connection before each test."""
    import mssql_mcp.server as server
    server._connection = None
    yield
    server._connection = None
