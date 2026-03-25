# sqlserver-mcp

MCP (Model Context Protocol) server for Microsoft SQL Server using pyodbc.

## Features

- 12 tools for database exploration and querying
- Windows and SQL Server authentication
- Connection pooling with health checks
- Query timeout and row limits
- Structured error handling

## Installation

### From GitHub

```bash
uv pip install git+https://github.com/chrismannina/sqlserver-mcp.git --system
```

### From source (for development)

```bash
git clone git@github.com:chrismannina/sqlserver-mcp.git
cd sqlserver-mcp
uv pip install -e ".[dev]" --system
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

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mssql": {
      "command": "sqlserver-mcp",
      "env": {
        "MSSQL_SERVER": "your-server",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_USER": "your-user",
        "MSSQL_PASSWORD": "your-password"
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
      "command": "sqlserver-mcp",
      "env": {
        "MSSQL_SERVER": "your-server",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_USER": "your-user",
        "MSSQL_PASSWORD": "your-password"
      }
    }
  }
}
```

### With OpenCode

Add an `mcp` section to `opencode.json` or `~/.config/opencode/config.json`:

```json
{
  "mcp": {
    "mydb": {
      "type": "local",
      "command": ["sqlserver-mcp"],
      "enabled": true,
      "environment": {
        "MSSQL_SERVER": "your-server",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_USER": "{env:MSSQL_USER}",
        "MSSQL_PASSWORD": "{env:MSSQL_PASSWORD}"
      }
    }
  }
}
```

### Running Directly

```bash
MSSQL_SERVER=your-server MSSQL_DATABASE=your-db MSSQL_USER=user MSSQL_PASSWORD=pass sqlserver-mcp
```

## Tools

### Discovery
- **list_schemas** - List all schemas
- **list_tables** - List tables (optionally by schema, with row counts)
- **list_views** - List views (optionally by schema)
- **list_procedures** - List stored procedures

### Description
- **describe_table** - Table structure (columns, PKs, FKs, indexes)
- **describe_procedure** - Procedure details (parameters, definition)

### Search
- **search_tables** - Find tables/views by pattern (`%` wildcards)
- **search_columns** - Find columns across tables by pattern

### Data
- **get_table_sample** - Sample rows (max 100)
- **get_table_stats** - Row count, space usage, dates
- **query** - Execute SQL with parameterized queries and row limits
- **execute_procedure** - Run stored procedures with parameters

## Development

```bash
uv run --extra dev pytest -v
```

## Requirements

- Python 3.10+
- ODBC Driver for SQL Server (17 or 18 recommended)

### Installing ODBC Driver

**Linux (Ubuntu/Debian):**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

**macOS:**
```bash
brew install microsoft/mssql-release/msodbcsql18
```

**Windows:** Download from [Microsoft](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

## License

MIT
