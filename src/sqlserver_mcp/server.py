"""MCP server for Microsoft SQL Server using pyodbc."""

import logging
import os
import sys
from contextlib import contextmanager
from typing import Any

import pyodbc
from fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("sqlserver-mcp")

# Configure logging
_debug = os.environ.get("MSSQL_DEBUG", "").lower() == "true"
logging.basicConfig(
    level=logging.DEBUG if _debug else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Configuration from environment
DEFAULT_QUERY_TIMEOUT = 30  # seconds
DEFAULT_MAX_ROWS = 1000


def _get_config() -> dict[str, Any]:
    """Get configuration from environment variables."""
    return {
        "server": os.environ.get("MSSQL_SERVER"),
        "database": os.environ.get("MSSQL_DATABASE"),
        "windows_auth": os.environ.get("MSSQL_WINDOWS_AUTH", "").lower() == "true",
        "user": os.environ.get("MSSQL_USER"),
        "password": os.environ.get("MSSQL_PASSWORD"),
        "driver": os.environ.get("MSSQL_DRIVER"),
        "query_timeout": int(os.environ.get("MSSQL_QUERY_TIMEOUT", DEFAULT_QUERY_TIMEOUT)),
        "max_rows": int(os.environ.get("MSSQL_MAX_ROWS", DEFAULT_MAX_ROWS)),
    }


# Connection pool (singleton)
_connection: pyodbc.Connection | None = None


def get_connection_string() -> str:
    """Build the ODBC connection string from environment variables."""
    config = _get_config()

    if not config["server"]:
        raise ValueError("MSSQL_SERVER environment variable is required")
    if not config["database"]:
        raise ValueError("MSSQL_DATABASE environment variable is required")

    driver = config["driver"] or _detect_odbc_driver()

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={config['server']}",
        f"DATABASE={config['database']}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
    ]

    if config["windows_auth"]:
        parts.append("Trusted_Connection=yes")
    else:
        if not config["user"] or not config["password"]:
            raise ValueError(
                "MSSQL_USER and MSSQL_PASSWORD are required when not using Windows authentication"
            )
        parts.append(f"UID={config['user']}")
        parts.append(f"PWD={config['password']}")

    return ";".join(parts)


def _detect_odbc_driver() -> str:
    """Detect the best available ODBC driver for SQL Server."""
    preferred_drivers = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13.1 for SQL Server",
        "ODBC Driver 13 for SQL Server",
        "SQL Server Native Client 11.0",
        "SQL Server",
    ]

    available_drivers = pyodbc.drivers()

    for driver in preferred_drivers:
        if driver in available_drivers:
            return driver

    for driver in available_drivers:
        if "sql server" in driver.lower():
            return driver

    raise ValueError(
        "No SQL Server ODBC driver found. Please install ODBC Driver 17 or 18 for SQL Server."
    )


def _get_pooled_connection() -> pyodbc.Connection:
    """Get or create a pooled connection with health check."""
    global _connection

    config = _get_config()

    # Check if existing connection is healthy
    if _connection is not None:
        try:
            _connection.execute("SELECT 1")
            logger.debug("Reusing existing connection")
            return _connection
        except Exception:
            logger.debug("Connection unhealthy, reconnecting")
            try:
                _connection.close()
            except Exception:
                pass
            _connection = None

    # Create new connection
    conn_str = get_connection_string()
    logger.debug(f"Creating new connection to {config['server']}/{config['database']}")
    _connection = pyodbc.connect(conn_str, timeout=config["query_timeout"])
    _connection.timeout = config["query_timeout"]
    return _connection


@contextmanager
def get_connection():
    """Context manager for database connections with pooling."""
    conn = _get_pooled_connection()
    try:
        yield conn
    except Exception as e:
        # On error, invalidate the connection
        global _connection
        _connection = None
        raise e


def _format_rows(cursor: pyodbc.Cursor, rows: list[Any]) -> list[dict[str, Any]]:
    """Convert cursor rows to list of dictionaries."""
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def _handle_error(operation: str, error: Exception) -> dict[str, Any]:
    """Create a structured error response."""
    error_msg = str(error)
    logger.error(f"{operation} failed: {error_msg}")

    # Classify common errors
    if "Login failed" in error_msg:
        error_type = "authentication_error"
    elif "Cannot open database" in error_msg:
        error_type = "database_error"
    elif "Invalid object name" in error_msg:
        error_type = "not_found"
    elif "permission" in error_msg.lower():
        error_type = "permission_error"
    elif "timeout" in error_msg.lower():
        error_type = "timeout"
    elif "syntax" in error_msg.lower():
        error_type = "syntax_error"
    else:
        error_type = "database_error"

    return {
        "error": True,
        "error_type": error_type,
        "message": error_msg,
    }


# =============================================================================
# Discovery Tools
# =============================================================================

@mcp.tool()
def list_schemas() -> list[dict[str, str]] | dict[str, Any]:
    """List all schemas in the database.

    Returns:
        List of schemas with name and owner.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    s.name AS schema_name,
                    p.name AS owner_name
                FROM sys.schemas s
                LEFT JOIN sys.database_principals p ON s.principal_id = p.principal_id
                WHERE s.schema_id < 16384
                ORDER BY s.name
            """
            cursor.execute(query)
            return _format_rows(cursor, cursor.fetchall())
    except Exception as e:
        return _handle_error("list_schemas", e)


@mcp.tool()
def list_tables(schema: str | None = None, include_row_counts: bool = False) -> list[dict[str, Any]] | dict[str, Any]:
    """List all tables in the database.

    Args:
        schema: Optional schema name to filter tables.
        include_row_counts: If True, include approximate row counts (slower).

    Returns:
        List of tables with schema, name, and type.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if include_row_counts:
                query = """
                    SELECT
                        t.TABLE_SCHEMA,
                        t.TABLE_NAME,
                        t.TABLE_TYPE,
                        p.rows AS approximate_row_count
                    FROM INFORMATION_SCHEMA.TABLES t
                    LEFT JOIN sys.tables st ON t.TABLE_NAME = st.name
                        AND SCHEMA_NAME(st.schema_id) = t.TABLE_SCHEMA
                    LEFT JOIN sys.partitions p ON st.object_id = p.object_id AND p.index_id IN (0, 1)
                    WHERE t.TABLE_TYPE = 'BASE TABLE'
                """
                if schema:
                    query += " AND t.TABLE_SCHEMA = ?"
                    query += " ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME"
                    cursor.execute(query, (schema,))
                else:
                    query += " ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME"
                    cursor.execute(query)
            else:
                if schema:
                    query = """
                        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = ?
                        ORDER BY TABLE_SCHEMA, TABLE_NAME
                    """
                    cursor.execute(query, (schema,))
                else:
                    query = """
                        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_TYPE = 'BASE TABLE'
                        ORDER BY TABLE_SCHEMA, TABLE_NAME
                    """
                    cursor.execute(query)

            return _format_rows(cursor, cursor.fetchall())
    except Exception as e:
        return _handle_error("list_tables", e)


@mcp.tool()
def list_views(schema: str | None = None) -> list[dict[str, str]] | dict[str, Any]:
    """List all views in the database.

    Args:
        schema: Optional schema name to filter views.

    Returns:
        List of views with schema and name.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if schema:
                query = """
                    SELECT TABLE_SCHEMA, TABLE_NAME, 'VIEW' AS TABLE_TYPE
                    FROM INFORMATION_SCHEMA.VIEWS
                    WHERE TABLE_SCHEMA = ?
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
                cursor.execute(query, (schema,))
            else:
                query = """
                    SELECT TABLE_SCHEMA, TABLE_NAME, 'VIEW' AS TABLE_TYPE
                    FROM INFORMATION_SCHEMA.VIEWS
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
                cursor.execute(query)

            return _format_rows(cursor, cursor.fetchall())
    except Exception as e:
        return _handle_error("list_views", e)


@mcp.tool()
def list_procedures(schema: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
    """List all stored procedures in the database.

    Args:
        schema: Optional schema name to filter procedures.

    Returns:
        List of stored procedures with schema, name, and parameter count.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if schema:
                query = """
                    SELECT
                        SCHEMA_NAME(p.schema_id) AS schema_name,
                        p.name AS procedure_name,
                        p.create_date,
                        p.modify_date,
                        (SELECT COUNT(*) FROM sys.parameters pm WHERE pm.object_id = p.object_id) AS parameter_count
                    FROM sys.procedures p
                    WHERE SCHEMA_NAME(p.schema_id) = ?
                    ORDER BY schema_name, procedure_name
                """
                cursor.execute(query, (schema,))
            else:
                query = """
                    SELECT
                        SCHEMA_NAME(p.schema_id) AS schema_name,
                        p.name AS procedure_name,
                        p.create_date,
                        p.modify_date,
                        (SELECT COUNT(*) FROM sys.parameters pm WHERE pm.object_id = p.object_id) AS parameter_count
                    FROM sys.procedures p
                    ORDER BY schema_name, procedure_name
                """
                cursor.execute(query)

            return _format_rows(cursor, cursor.fetchall())
    except Exception as e:
        return _handle_error("list_procedures", e)


# =============================================================================
# Description Tools
# =============================================================================

@mcp.tool()
def describe_table(table_name: str, schema: str = "dbo") -> dict[str, Any]:
    """Get detailed information about a table's structure.

    Args:
        table_name: Name of the table to describe.
        schema: Schema name (default: 'dbo').

    Returns:
        Dictionary containing columns, primary keys, foreign keys, and indexes.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get column information
            columns_query = """
                SELECT
                    c.COLUMN_NAME,
                    c.DATA_TYPE,
                    c.CHARACTER_MAXIMUM_LENGTH,
                    c.NUMERIC_PRECISION,
                    c.NUMERIC_SCALE,
                    c.IS_NULLABLE,
                    c.COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS c
                WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
                ORDER BY c.ORDINAL_POSITION
            """
            cursor.execute(columns_query, (schema, table_name))
            columns = _format_rows(cursor, cursor.fetchall())

            if not columns:
                return {
                    "error": True,
                    "error_type": "not_found",
                    "message": f"Table '{schema}.{table_name}' not found",
                }

            # Get primary key information
            pk_query = """
                SELECT kcu.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                    AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    AND tc.TABLE_SCHEMA = ?
                    AND tc.TABLE_NAME = ?
                ORDER BY kcu.ORDINAL_POSITION
            """
            cursor.execute(pk_query, (schema, table_name))
            primary_keys = [row[0] for row in cursor.fetchall()]

            # Get foreign key information
            fk_query = """
                SELECT
                    fk.name AS constraint_name,
                    cp.name AS column_name,
                    OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS referenced_schema,
                    OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
                    cr.name AS referenced_column
                FROM sys.foreign_keys fk
                INNER JOIN sys.foreign_key_columns fkc
                    ON fk.object_id = fkc.constraint_object_id
                INNER JOIN sys.columns cp
                    ON fkc.parent_object_id = cp.object_id
                    AND fkc.parent_column_id = cp.column_id
                INNER JOIN sys.columns cr
                    ON fkc.referenced_object_id = cr.object_id
                    AND fkc.referenced_column_id = cr.column_id
                WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = ?
                    AND OBJECT_NAME(fk.parent_object_id) = ?
            """
            cursor.execute(fk_query, (schema, table_name))
            foreign_keys = _format_rows(cursor, cursor.fetchall())

            # Get index information
            idx_query = """
                SELECT
                    i.name AS index_name,
                    i.type_desc AS index_type,
                    i.is_unique,
                    i.is_primary_key,
                    STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
                FROM sys.indexes i
                INNER JOIN sys.index_columns ic
                    ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                INNER JOIN sys.columns c
                    ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE OBJECT_SCHEMA_NAME(i.object_id) = ?
                    AND OBJECT_NAME(i.object_id) = ?
                    AND i.name IS NOT NULL
                GROUP BY i.name, i.type_desc, i.is_unique, i.is_primary_key
            """
            cursor.execute(idx_query, (schema, table_name))
            indexes = _format_rows(cursor, cursor.fetchall())

            return {
                "schema": schema,
                "table_name": table_name,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
            }
    except Exception as e:
        return _handle_error("describe_table", e)


@mcp.tool()
def describe_procedure(procedure_name: str, schema: str = "dbo") -> dict[str, Any]:
    """Get detailed information about a stored procedure.

    Args:
        procedure_name: Name of the procedure to describe.
        schema: Schema name (default: 'dbo').

    Returns:
        Dictionary containing parameters and procedure definition.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get procedure info
            proc_query = """
                SELECT
                    SCHEMA_NAME(p.schema_id) AS schema_name,
                    p.name AS procedure_name,
                    p.create_date,
                    p.modify_date
                FROM sys.procedures p
                WHERE SCHEMA_NAME(p.schema_id) = ? AND p.name = ?
            """
            cursor.execute(proc_query, (schema, procedure_name))
            proc_info = cursor.fetchone()

            if not proc_info:
                return {
                    "error": True,
                    "error_type": "not_found",
                    "message": f"Procedure '{schema}.{procedure_name}' not found",
                }

            # Get parameters
            params_query = """
                SELECT
                    pm.name AS parameter_name,
                    TYPE_NAME(pm.user_type_id) AS data_type,
                    pm.max_length,
                    pm.precision,
                    pm.scale,
                    pm.is_output,
                    pm.has_default_value,
                    pm.default_value
                FROM sys.procedures p
                INNER JOIN sys.parameters pm ON p.object_id = pm.object_id
                WHERE SCHEMA_NAME(p.schema_id) = ? AND p.name = ?
                ORDER BY pm.parameter_id
            """
            cursor.execute(params_query, (schema, procedure_name))
            parameters = _format_rows(cursor, cursor.fetchall())

            # Get definition (if available)
            def_query = """
                SELECT OBJECT_DEFINITION(OBJECT_ID(?))
            """
            cursor.execute(def_query, (f"{schema}.{procedure_name}",))
            definition_row = cursor.fetchone()
            definition = definition_row[0] if definition_row and definition_row[0] else None

            return {
                "schema": schema,
                "procedure_name": procedure_name,
                "create_date": str(proc_info[2]) if proc_info[2] else None,
                "modify_date": str(proc_info[3]) if proc_info[3] else None,
                "parameters": parameters,
                "definition": definition,
            }
    except Exception as e:
        return _handle_error("describe_procedure", e)


# =============================================================================
# Search Tools
# =============================================================================

@mcp.tool()
def search_tables(pattern: str, include_views: bool = True) -> list[dict[str, str]] | dict[str, Any]:
    """Search for tables and views matching a pattern.

    Args:
        pattern: Search pattern (use % for wildcards, e.g., '%customer%').
        include_views: Whether to include views in results (default: True).

    Returns:
        List of matching tables/views.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if include_views:
                query = """
                    SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME LIKE ?
                    ORDER BY TABLE_TYPE, TABLE_SCHEMA, TABLE_NAME
                """
            else:
                query = """
                    SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME LIKE ? AND TABLE_TYPE = 'BASE TABLE'
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
            cursor.execute(query, (pattern,))
            return _format_rows(cursor, cursor.fetchall())
    except Exception as e:
        return _handle_error("search_tables", e)


@mcp.tool()
def search_columns(pattern: str, table_pattern: str | None = None) -> list[dict[str, str]] | dict[str, Any]:
    """Search for columns matching a pattern across all tables.

    Args:
        pattern: Column name pattern (use % for wildcards).
        table_pattern: Optional table name pattern to filter.

    Returns:
        List of matching columns with their table and data type.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if table_pattern:
                query = """
                    SELECT
                        TABLE_SCHEMA,
                        TABLE_NAME,
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE COLUMN_NAME LIKE ? AND TABLE_NAME LIKE ?
                    ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
                """
                cursor.execute(query, (pattern, table_pattern))
            else:
                query = """
                    SELECT
                        TABLE_SCHEMA,
                        TABLE_NAME,
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE COLUMN_NAME LIKE ?
                    ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
                """
                cursor.execute(query, (pattern,))

            return _format_rows(cursor, cursor.fetchall())
    except Exception as e:
        return _handle_error("search_columns", e)


# =============================================================================
# Data Tools
# =============================================================================

@mcp.tool()
def get_table_sample(
    table_name: str,
    schema: str = "dbo",
    rows: int = 10
) -> dict[str, Any]:
    """Get sample rows from a table.

    Args:
        table_name: Name of the table.
        schema: Schema name (default: 'dbo').
        rows: Number of rows to return (default: 10, max: 100).

    Returns:
        Dictionary with columns and sample rows.
    """
    try:
        # Cap rows at 100
        rows = min(rows, 100)

        with get_connection() as conn:
            cursor = conn.cursor()

            # Use quoted identifiers for safety
            query = f"SELECT TOP {rows} * FROM [{schema}].[{table_name}]"
            logger.debug(f"Executing: {query}")
            cursor.execute(query)

            if cursor.description:
                return {
                    "schema": schema,
                    "table_name": table_name,
                    "columns": [col[0] for col in cursor.description],
                    "rows": _format_rows(cursor, cursor.fetchall()),
                    "row_count": rows,
                }
            else:
                return {
                    "error": True,
                    "error_type": "not_found",
                    "message": f"Table '{schema}.{table_name}' not found or empty",
                }
    except Exception as e:
        return _handle_error("get_table_sample", e)


@mcp.tool()
def get_table_stats(table_name: str, schema: str = "dbo") -> dict[str, Any]:
    """Get statistics for a table including row count and size.

    Args:
        table_name: Name of the table.
        schema: Schema name (default: 'dbo').

    Returns:
        Dictionary with table statistics.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    s.name AS schema_name,
                    t.name AS table_name,
                    p.rows AS row_count,
                    SUM(a.total_pages) * 8 AS total_space_kb,
                    SUM(a.used_pages) * 8 AS used_space_kb,
                    t.create_date,
                    t.modify_date
                FROM sys.tables t
                INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
                INNER JOIN sys.indexes i ON t.object_id = i.object_id
                INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
                INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
                WHERE s.name = ? AND t.name = ?
                GROUP BY s.name, t.name, p.rows, t.create_date, t.modify_date
            """
            cursor.execute(query, (schema, table_name))
            row = cursor.fetchone()

            if not row:
                return {
                    "error": True,
                    "error_type": "not_found",
                    "message": f"Table '{schema}.{table_name}' not found",
                }

            return {
                "schema": row[0],
                "table_name": row[1],
                "row_count": row[2],
                "total_space_kb": row[3],
                "used_space_kb": row[4],
                "total_space_mb": round(row[3] / 1024, 2) if row[3] else 0,
                "used_space_mb": round(row[4] / 1024, 2) if row[4] else 0,
                "create_date": str(row[5]) if row[5] else None,
                "modify_date": str(row[6]) if row[6] else None,
            }
    except Exception as e:
        return _handle_error("get_table_stats", e)


@mcp.tool()
def query(
    sql: str,
    params: list[Any] | None = None,
    limit: int | None = None
) -> dict[str, Any]:
    """Execute a SQL query and return results.

    Args:
        sql: The SQL query to execute.
        params: Optional list of parameters for parameterized queries.
        limit: Maximum rows to return (default: MSSQL_MAX_ROWS env var or 1000).

    Returns:
        Dictionary containing columns, rows (as dicts), and row count.
    """
    try:
        config = _get_config()
        max_rows = limit if limit is not None else config["max_rows"]

        with get_connection() as conn:
            cursor = conn.cursor()

            logger.debug(f"Executing query: {sql[:100]}...")

            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            # Check if this is a SELECT query (has results)
            if cursor.description:
                columns = [column[0] for column in cursor.description]

                # Fetch with limit
                all_rows = []
                truncated = False
                for i, row in enumerate(cursor):
                    if i >= max_rows:
                        truncated = True
                        break
                    all_rows.append(dict(zip(columns, row)))

                result = {
                    "columns": columns,
                    "rows": all_rows,
                    "row_count": len(all_rows),
                }
                if truncated:
                    result["truncated"] = True
                    result["limit"] = max_rows
                    result["message"] = f"Results truncated to {max_rows} rows"

                return result
            else:
                # For INSERT/UPDATE/DELETE, commit and return affected rows
                conn.commit()
                return {
                    "columns": [],
                    "rows": [],
                    "row_count": cursor.rowcount,
                    "message": f"{cursor.rowcount} row(s) affected",
                }
    except Exception as e:
        return _handle_error("query", e)


@mcp.tool()
def execute_procedure(
    procedure_name: str,
    schema: str = "dbo",
    params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Execute a stored procedure.

    Args:
        procedure_name: Name of the stored procedure.
        schema: Schema name (default: 'dbo').
        params: Dictionary of parameter names to values (e.g., {"@param1": "value"}).

    Returns:
        Dictionary containing result sets and output parameters.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Build EXEC statement
            if params:
                param_list = ", ".join(f"{k} = ?" for k in params.keys())
                sql = f"EXEC [{schema}].[{procedure_name}] {param_list}"
                param_values = list(params.values())
                logger.debug(f"Executing: {sql} with {len(param_values)} params")
                cursor.execute(sql, param_values)
            else:
                sql = f"EXEC [{schema}].[{procedure_name}]"
                logger.debug(f"Executing: {sql}")
                cursor.execute(sql)

            # Collect all result sets
            result_sets = []
            while True:
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    rows = _format_rows(cursor, cursor.fetchall())
                    result_sets.append({
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                    })

                if not cursor.nextset():
                    break

            conn.commit()

            return {
                "procedure": f"{schema}.{procedure_name}",
                "result_sets": result_sets,
                "result_set_count": len(result_sets),
            }
    except Exception as e:
        return _handle_error("execute_procedure", e)


def main():
    """Entry point for the MCP server."""
    logger.info("Starting mssql-mcp server")
    mcp.run()


if __name__ == "__main__":
    main()
