# mssql-mcp

MCP (Model Context Protocol) server for Microsoft SQL Server using pyodbc.

## Features

- 12 tools for database exploration and querying
- Windows and SQL Server authentication
- Connection pooling with health checks
- Query timeout and row limits
- Structured error handling

## Installation

### From Git (recommended for local use)

```bash
git clone <your-repo-url> mssql-mcp
cd mssql-mcp
uv pip install -e . --system
```

### From PyPI (not yet published)

```bash
uvx mssql-mcp
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MSSQL_SERVER` | Yes | - | SQL Server hostname or IP address |
| `MSSQL_DATABASE` | Yes | - | Database name |
| `MSSQL_WINDOWS_AUTH` | No | `false` | Set to `true` for Windows authentication |
| `MSSQL_USER` | Conditional | - | Username (required if not using Windows auth) |
| `MSSQL_PASSWORD` | Conditional | - | Password (required if not using Windows auth) |
| `MSSQL_DRIVER` | No | auto | ODBC driver name (auto-detected if not set) |
| `MSSQL_QUERY_TIMEOUT` | No | `30` | Query timeout in seconds |
| `MSSQL_MAX_ROWS` | No | `1000` | Default max rows returned by queries |
| `MSSQL_DEBUG` | No | `false` | Enable debug logging to stderr |

### Connection Security

All connections use:
- `Encrypt=yes` - Encrypted connections
- `TrustServerCertificate=yes` - Trust the server certificate

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mssql": {
      "command": "mssql-mcp",
      "env": {
        "MSSQL_SERVER": "your-server",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_WINDOWS_AUTH": "true"
      }
    }
  }
}
```

### With Claude Code

Add to `~/.claude/settings.json` or project `.claude/settings.json`:

```json
{
  "mcpServers": {
    "mssql": {
      "command": "mssql-mcp",
      "env": {
        "MSSQL_SERVER": "your-server",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_WINDOWS_AUTH": "true"
      }
    }
  }
}
```

### Running Directly (PowerShell)

```powershell
$env:MSSQL_SERVER="your-server"; $env:MSSQL_DATABASE="your-db"; $env:MSSQL_WINDOWS_AUTH="true"; mssql-mcp
```

## Tools

### Discovery Tools

#### list_schemas
List all schemas in the database.

#### list_tables
List all tables in the database.
- `schema` (optional): Filter by schema name
- `include_row_counts` (optional): Include approximate row counts

#### list_views
List all views in the database.
- `schema` (optional): Filter by schema name

#### list_procedures
List all stored procedures in the database.
- `schema` (optional): Filter by schema name

### Description Tools

#### describe_table
Get detailed information about a table's structure.
- `table_name` (required): Name of the table
- `schema` (optional, default: "dbo"): Schema name

Returns columns, primary keys, foreign keys, and indexes.

#### describe_procedure
Get detailed information about a stored procedure.
- `procedure_name` (required): Name of the procedure
- `schema` (optional, default: "dbo"): Schema name

Returns parameters and procedure definition.

### Search Tools

#### search_tables
Search for tables and views matching a pattern.
- `pattern` (required): Search pattern (use `%` for wildcards)
- `include_views` (optional, default: true): Include views in results

#### search_columns
Search for columns matching a pattern across all tables.
- `pattern` (required): Column name pattern (use `%` for wildcards)
- `table_pattern` (optional): Filter by table name pattern

### Data Tools

#### get_table_sample
Get sample rows from a table.
- `table_name` (required): Name of the table
- `schema` (optional, default: "dbo"): Schema name
- `rows` (optional, default: 10, max: 100): Number of rows

#### get_table_stats
Get statistics for a table including row count and size.
- `table_name` (required): Name of the table
- `schema` (optional, default: "dbo"): Schema name

#### query
Execute a SQL query and return results.
- `sql` (required): The SQL query to execute
- `params` (optional): List of parameters for parameterized queries
- `limit` (optional): Max rows to return (default: MSSQL_MAX_ROWS)

Returns rows as dictionaries. Results are truncated if they exceed the limit.

#### execute_procedure
Execute a stored procedure.
- `procedure_name` (required): Name of the procedure
- `schema` (optional, default: "dbo"): Schema name
- `params` (optional): Dictionary of parameter names to values

## Development

### Running Tests

```bash
uv pip install -e ".[dev]" --system
pytest
```

## Requirements

- Python 3.10+
- ODBC Driver for SQL Server (17 or 18 recommended)

### Installing ODBC Driver

**Windows:** Download from [Microsoft](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

**macOS:**
```bash
brew install microsoft/mssql-release/msodbcsql18
```

**Linux (Ubuntu/Debian):**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

## License

MIT
