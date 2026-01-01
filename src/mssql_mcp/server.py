"""MCP server for Microsoft SQL Server using pyodbc."""

import os
from contextlib import contextmanager
from typing import Any

import pyodbc
from fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("mssql-mcp")


def get_connection_string() -> str:
    """Build the ODBC connection string from environment variables.

    Environment variables:
        MSSQL_SERVER: Server hostname or IP (required)
        MSSQL_DATABASE: Database name (required)
        MSSQL_WINDOWS_AUTH: Set to 'true' for Windows authentication
        MSSQL_USER: Username for SQL authentication
        MSSQL_PASSWORD: Password for SQL authentication
        MSSQL_DRIVER: ODBC driver name (optional, auto-detected if not set)
    """
    server = os.environ.get("MSSQL_SERVER")
    database = os.environ.get("MSSQL_DATABASE")
    windows_auth = os.environ.get("MSSQL_WINDOWS_AUTH", "").lower() == "true"
    user = os.environ.get("MSSQL_USER")
    password = os.environ.get("MSSQL_PASSWORD")
    driver = os.environ.get("MSSQL_DRIVER")

    if not server:
        raise ValueError("MSSQL_SERVER environment variable is required")
    if not database:
        raise ValueError("MSSQL_DATABASE environment variable is required")

    # Auto-detect ODBC driver if not specified
    if not driver:
        driver = _detect_odbc_driver()

    # Build connection string
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
    ]

    if windows_auth:
        parts.append("Trusted_Connection=yes")
    else:
        if not user or not password:
            raise ValueError(
                "MSSQL_USER and MSSQL_PASSWORD are required when not using Windows authentication"
            )
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")

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

    # If no preferred driver found, try to find any SQL Server driver
    for driver in available_drivers:
        if "sql server" in driver.lower():
            return driver

    raise ValueError(
        "No SQL Server ODBC driver found. Please install ODBC Driver 17 or 18 for SQL Server."
    )


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn_str = get_connection_string()
    conn = pyodbc.connect(conn_str)
    try:
        yield conn
    finally:
        conn.close()


def _format_rows(cursor: pyodbc.Cursor, rows: list[Any]) -> list[dict[str, Any]]:
    """Convert cursor rows to list of dictionaries."""
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


@mcp.tool()
def list_tables(schema: str | None = None) -> list[dict[str, str]]:
    """List all tables in the database.

    Args:
        schema: Optional schema name to filter tables. If not provided, lists tables from all schemas.

    Returns:
        List of tables with schema and table name.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        if schema:
            query = """
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = ?
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
            cursor.execute(query, (schema,))
        else:
            query = """
                SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                FROM INFORMATION_SCHEMA.TABLES
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
            cursor.execute(query)

        rows = cursor.fetchall()
        return _format_rows(cursor, rows)


@mcp.tool()
def describe_table(table_name: str, schema: str = "dbo") -> dict[str, Any]:
    """Get detailed information about a table's structure.

    Args:
        table_name: Name of the table to describe.
        schema: Schema name (default: 'dbo').

    Returns:
        Dictionary containing columns, primary keys, foreign keys, and indexes.
    """
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


@mcp.tool()
def query(sql: str, params: list[Any] | None = None) -> dict[str, Any]:
    """Execute a SQL query and return results.

    Args:
        sql: The SQL query to execute.
        params: Optional list of parameters for parameterized queries.

    Returns:
        Dictionary containing column names, rows, and row count.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        # Check if this is a SELECT query (has results)
        if cursor.description:
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
            }
        else:
            # For INSERT/UPDATE/DELETE, commit and return affected rows
            conn.commit()
            return {
                "columns": [],
                "rows": [],
                "row_count": cursor.rowcount,
                "message": f"{cursor.rowcount} row(s) affected",
            }


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
