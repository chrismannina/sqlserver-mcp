"""Tests for mssql-mcp server."""

from unittest.mock import MagicMock, patch

import pytest

from mssql_mcp import server
from tests.conftest import get_tool_fn

# Extract the underlying functions from FunctionTool wrappers
list_schemas = get_tool_fn(server.list_schemas)
list_tables = get_tool_fn(server.list_tables)
list_views = get_tool_fn(server.list_views)
list_procedures = get_tool_fn(server.list_procedures)
describe_table = get_tool_fn(server.describe_table)
describe_procedure = get_tool_fn(server.describe_procedure)
search_tables = get_tool_fn(server.search_tables)
search_columns = get_tool_fn(server.search_columns)
get_table_sample = get_tool_fn(server.get_table_sample)
get_table_stats = get_tool_fn(server.get_table_stats)
query = get_tool_fn(server.query)
execute_procedure = get_tool_fn(server.execute_procedure)


class TestConnectionString:
    """Tests for connection string building."""

    def test_windows_auth(self, mock_env, mock_pyodbc):
        """Test connection string with Windows authentication."""
        conn_str = server.get_connection_string()

        assert "SERVER=test-server" in conn_str
        assert "DATABASE=test-db" in conn_str
        assert "Trusted_Connection=yes" in conn_str
        assert "Encrypt=yes" in conn_str
        assert "TrustServerCertificate=yes" in conn_str
        assert "UID=" not in conn_str
        assert "PWD=" not in conn_str

    def test_sql_auth(self, mock_env_sql_auth, mock_pyodbc):
        """Test connection string with SQL authentication."""
        conn_str = server.get_connection_string()

        assert "SERVER=test-server" in conn_str
        assert "DATABASE=test-db" in conn_str
        assert "UID=test-user" in conn_str
        assert "PWD=test-password" in conn_str
        assert "Trusted_Connection" not in conn_str

    def test_missing_server(self, monkeypatch, mock_pyodbc):
        """Test error when server is missing."""
        monkeypatch.setenv("MSSQL_DATABASE", "test-db")

        with pytest.raises(ValueError, match="MSSQL_SERVER"):
            server.get_connection_string()

    def test_missing_database(self, monkeypatch, mock_pyodbc):
        """Test error when database is missing."""
        monkeypatch.setenv("MSSQL_SERVER", "test-server")

        with pytest.raises(ValueError, match="MSSQL_DATABASE"):
            server.get_connection_string()

    def test_missing_credentials_sql_auth(self, monkeypatch, mock_pyodbc):
        """Test error when credentials missing for SQL auth."""
        monkeypatch.setenv("MSSQL_SERVER", "test-server")
        monkeypatch.setenv("MSSQL_DATABASE", "test-db")

        with pytest.raises(ValueError, match="MSSQL_USER and MSSQL_PASSWORD"):
            server.get_connection_string()


class TestDriverDetection:
    """Tests for ODBC driver detection."""

    def test_detect_driver_18(self):
        """Test detection of ODBC Driver 18."""
        with patch.object(server.pyodbc, "drivers", return_value=["ODBC Driver 18 for SQL Server"]):
            driver = server._detect_odbc_driver()
            assert driver == "ODBC Driver 18 for SQL Server"

    def test_detect_driver_17(self):
        """Test detection of ODBC Driver 17."""
        with patch.object(server.pyodbc, "drivers", return_value=["ODBC Driver 17 for SQL Server"]):
            driver = server._detect_odbc_driver()
            assert driver == "ODBC Driver 17 for SQL Server"

    def test_no_driver_found(self):
        """Test error when no driver found."""
        with patch.object(server.pyodbc, "drivers", return_value=[]):
            with pytest.raises(ValueError, match="No SQL Server ODBC driver found"):
                server._detect_odbc_driver()


class TestErrorHandling:
    """Tests for error handling."""

    def test_handle_error_authentication(self):
        """Test authentication error classification."""
        error = Exception("Login failed for user 'test'")
        result = server._handle_error("test_op", error)

        assert result["error"] is True
        assert result["error_type"] == "authentication_error"
        assert "Login failed" in result["message"]

    def test_handle_error_not_found(self):
        """Test not found error classification."""
        error = Exception("Invalid object name 'missing_table'")
        result = server._handle_error("test_op", error)

        assert result["error"] is True
        assert result["error_type"] == "not_found"

    def test_handle_error_permission(self):
        """Test permission error classification."""
        error = Exception("The SELECT permission was denied")
        result = server._handle_error("test_op", error)

        assert result["error"] is True
        assert result["error_type"] == "permission_error"

    def test_handle_error_timeout(self):
        """Test timeout error classification."""
        error = Exception("Query timeout expired")
        result = server._handle_error("test_op", error)

        assert result["error"] is True
        assert result["error_type"] == "timeout"

    def test_handle_error_syntax(self):
        """Test syntax error classification."""
        error = Exception("Incorrect syntax near 'FROM'")
        result = server._handle_error("test_op", error)

        assert result["error"] is True
        assert result["error_type"] == "syntax_error"


class TestListSchemas:
    """Tests for list_schemas tool."""

    def test_list_schemas_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful schema listing."""
        mock_cursor.description = [("schema_name",), ("owner_name",)]
        mock_cursor.fetchall.return_value = [
            ("dbo", "dbo"),
            ("sales", "admin"),
        ]

        result = list_schemas()

        assert len(result) == 2
        assert result[0]["schema_name"] == "dbo"
        assert result[1]["schema_name"] == "sales"


class TestListTables:
    """Tests for list_tables tool."""

    def test_list_tables_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful table listing."""
        mock_cursor.description = [("TABLE_SCHEMA",), ("TABLE_NAME",), ("TABLE_TYPE",)]
        mock_cursor.fetchall.return_value = [
            ("dbo", "Users", "BASE TABLE"),
            ("dbo", "Orders", "BASE TABLE"),
        ]

        result = list_tables()

        assert len(result) == 2
        assert result[0]["TABLE_NAME"] == "Users"

    def test_list_tables_with_schema(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test table listing filtered by schema."""
        mock_cursor.description = [("TABLE_SCHEMA",), ("TABLE_NAME",), ("TABLE_TYPE",)]
        mock_cursor.fetchall.return_value = [
            ("sales", "Customers", "BASE TABLE"),
        ]

        result = list_tables(schema="sales")

        assert len(result) == 1
        assert result[0]["TABLE_SCHEMA"] == "sales"


class TestListViews:
    """Tests for list_views tool."""

    def test_list_views_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful view listing."""
        mock_cursor.description = [("TABLE_SCHEMA",), ("TABLE_NAME",), ("TABLE_TYPE",)]
        mock_cursor.fetchall.return_value = [
            ("dbo", "vw_ActiveUsers", "VIEW"),
        ]

        result = list_views()

        assert len(result) == 1
        assert result[0]["TABLE_NAME"] == "vw_ActiveUsers"


class TestListProcedures:
    """Tests for list_procedures tool."""

    def test_list_procedures_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful procedure listing."""
        mock_cursor.description = [
            ("schema_name",), ("procedure_name",), ("create_date",),
            ("modify_date",), ("parameter_count",)
        ]
        mock_cursor.fetchall.return_value = [
            ("dbo", "sp_GetUser", "2024-01-01", "2024-01-02", 2),
        ]

        result = list_procedures()

        assert len(result) == 1
        assert result[0]["procedure_name"] == "sp_GetUser"


class TestDescribeTable:
    """Tests for describe_table tool."""

    def test_describe_table_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful table description."""
        # Mock column query
        mock_cursor.description = [
            ("COLUMN_NAME",), ("DATA_TYPE",), ("CHARACTER_MAXIMUM_LENGTH",),
            ("NUMERIC_PRECISION",), ("NUMERIC_SCALE",), ("IS_NULLABLE",), ("COLUMN_DEFAULT",)
        ]
        mock_cursor.fetchall.side_effect = [
            [("id", "int", None, 10, 0, "NO", None), ("name", "varchar", 255, None, None, "YES", None)],
            [("id",)],  # Primary keys
            [],  # Foreign keys
            [],  # Indexes
        ]

        result = describe_table("Users")

        assert result["table_name"] == "Users"
        assert len(result["columns"]) == 2
        assert result["primary_keys"] == ["id"]

    def test_describe_table_not_found(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test table not found."""
        mock_cursor.description = [("COLUMN_NAME",)]
        mock_cursor.fetchall.return_value = []

        result = describe_table("NonExistent")

        assert result["error"] is True
        assert result["error_type"] == "not_found"


class TestQuery:
    """Tests for query tool."""

    def test_query_select_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful SELECT query."""
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.__iter__ = lambda self: iter([
            (1, "Alice"),
            (2, "Bob"),
        ])

        result = query("SELECT * FROM Users")

        assert result["columns"] == ["id", "name"]
        assert len(result["rows"]) == 2
        assert result["rows"][0]["id"] == 1

    def test_query_with_limit(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test query with row limit."""
        mock_cursor.description = [("id",)]
        mock_cursor.__iter__ = lambda self: iter([(i,) for i in range(100)])

        result = query("SELECT * FROM LargeTable", limit=10)

        assert len(result["rows"]) == 10
        assert result["truncated"] is True

    def test_query_insert(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test INSERT query."""
        mock_cursor.description = None
        mock_cursor.rowcount = 5

        result = query("INSERT INTO Users (name) VALUES ('Test')")

        assert result["row_count"] == 5
        assert "affected" in result["message"]

    def test_query_with_params(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test query with parameters."""
        mock_cursor.description = [("name",)]
        mock_cursor.__iter__ = lambda self: iter([("Alice",)])

        result = query("SELECT name FROM Users WHERE id = ?", params=[1])

        mock_cursor.execute.assert_called_with("SELECT name FROM Users WHERE id = ?", [1])


class TestSearchTables:
    """Tests for search_tables tool."""

    def test_search_tables_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful table search."""
        mock_cursor.description = [("TABLE_SCHEMA",), ("TABLE_NAME",), ("TABLE_TYPE",)]
        mock_cursor.fetchall.return_value = [
            ("dbo", "Customers", "BASE TABLE"),
            ("dbo", "CustomerOrders", "BASE TABLE"),
        ]

        result = search_tables("%Customer%")

        assert len(result) == 2


class TestSearchColumns:
    """Tests for search_columns tool."""

    def test_search_columns_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful column search."""
        mock_cursor.description = [
            ("TABLE_SCHEMA",), ("TABLE_NAME",), ("COLUMN_NAME",),
            ("DATA_TYPE",), ("IS_NULLABLE",)
        ]
        mock_cursor.fetchall.return_value = [
            ("dbo", "Users", "email", "varchar", "YES"),
            ("dbo", "Contacts", "email_address", "nvarchar", "NO"),
        ]

        result = search_columns("%email%")

        assert len(result) == 2


class TestGetTableSample:
    """Tests for get_table_sample tool."""

    def test_get_sample_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful sample retrieval."""
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [
            (1, "Alice"),
            (2, "Bob"),
        ]

        result = get_table_sample("Users", rows=5)

        assert result["table_name"] == "Users"
        assert len(result["rows"]) == 2

    def test_get_sample_max_100(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test that sample is capped at 100 rows."""
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = []

        get_table_sample("Users", rows=500)

        # Check that TOP 100 was used, not TOP 500
        call_args = mock_cursor.execute.call_args[0][0]
        assert "TOP 100" in call_args


class TestGetTableStats:
    """Tests for get_table_stats tool."""

    def test_get_stats_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful stats retrieval."""
        mock_cursor.fetchone.return_value = (
            "dbo", "Users", 1000, 8192, 4096, "2024-01-01", "2024-01-02"
        )

        result = get_table_stats("Users")

        assert result["row_count"] == 1000
        assert result["total_space_kb"] == 8192
        assert result["total_space_mb"] == 8.0

    def test_get_stats_not_found(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test table not found."""
        mock_cursor.fetchone.return_value = None

        result = get_table_stats("NonExistent")

        assert result["error"] is True
        assert result["error_type"] == "not_found"


class TestExecuteProcedure:
    """Tests for execute_procedure tool."""

    def test_execute_procedure_success(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test successful procedure execution."""
        mock_cursor.description = [("result",)]
        mock_cursor.fetchall.return_value = [("success",)]
        mock_cursor.nextset.return_value = False

        result = execute_procedure("sp_Test")

        assert result["procedure"] == "dbo.sp_Test"
        assert len(result["result_sets"]) == 1

    def test_execute_procedure_with_params(self, mock_env, mock_pyodbc, mock_connection, mock_cursor):
        """Test procedure execution with parameters."""
        mock_cursor.description = None
        mock_cursor.nextset.return_value = False

        execute_procedure("sp_UpdateUser", params={"@userId": 1, "@name": "Test"})

        call_args = mock_cursor.execute.call_args[0][0]
        assert "@userId = ?" in call_args
        assert "@name = ?" in call_args


class TestConnectionPooling:
    """Tests for connection pooling."""

    def test_connection_reuse(self, mock_env, mock_pyodbc, mock_connection):
        """Test that connections are reused."""
        # First call creates connection
        with server.get_connection() as conn1:
            pass

        # Second call reuses connection
        with server.get_connection() as conn2:
            pass

        # pyodbc.connect should only be called once
        assert mock_pyodbc.connect.call_count == 1

    def test_connection_health_check_failure(self, mock_env, mock_pyodbc, mock_connection):
        """Test reconnection on health check failure."""
        # First call succeeds
        with server.get_connection():
            pass

        # Make health check fail
        mock_connection.execute.side_effect = Exception("Connection lost")

        # Should create new connection
        with server.get_connection():
            pass

        assert mock_pyodbc.connect.call_count == 2
