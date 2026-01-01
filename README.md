# mssql-mcp

MCP (Model Context Protocol) server for Microsoft SQL Server using pyodbc.

## Installation

```bash
uvx mssql-mcp
```

Or install from source:

```bash
uv pip install .
```

## Configuration

Set the following environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `MSSQL_SERVER` | Yes | SQL Server hostname or IP address |
| `MSSQL_DATABASE` | Yes | Database name |
| `MSSQL_WINDOWS_AUTH` | No | Set to `true` for Windows authentication |
| `MSSQL_USER` | Conditional | Username (required if not using Windows auth) |
| `MSSQL_PASSWORD` | Conditional | Password (required if not using Windows auth) |
| `MSSQL_DRIVER` | No | ODBC driver name (auto-detected if not set) |

### Connection Security

All connections use:
- `Encrypt=yes` - Encrypted connections
- `TrustServerCertificate=yes` - Trust the server certificate

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

#### Windows Authentication

```json
{
  "mcpServers": {
    "mssql": {
      "command": "uvx",
      "args": ["mssql-mcp"],
      "env": {
        "MSSQL_SERVER": "your-server.database.windows.net",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_WINDOWS_AUTH": "true"
      }
    }
  }
}
```

#### SQL Server Authentication

```json
{
  "mcpServers": {
    "mssql": {
      "command": "uvx",
      "args": ["mssql-mcp"],
      "env": {
        "MSSQL_SERVER": "your-server.database.windows.net",
        "MSSQL_DATABASE": "your-database",
        "MSSQL_USER": "your-username",
        "MSSQL_PASSWORD": "your-password"
      }
    }
  }
}
```

### Running Directly

```bash
# Windows Authentication
MSSQL_SERVER=localhost MSSQL_DATABASE=mydb MSSQL_WINDOWS_AUTH=true mssql-mcp

# SQL Server Authentication
MSSQL_SERVER=localhost MSSQL_DATABASE=mydb MSSQL_USER=sa MSSQL_PASSWORD=secret mssql-mcp
```

## Tools

### list_tables

List all tables in the database.

**Parameters:**
- `schema` (optional): Filter tables by schema name

**Example:**
```
List all tables in the dbo schema
```

### describe_table

Get detailed information about a table's structure including columns, primary keys, foreign keys, and indexes.

**Parameters:**
- `table_name` (required): Name of the table
- `schema` (optional, default: "dbo"): Schema name

**Example:**
```
Describe the Users table structure
```

### query

Execute a SQL query and return results.

**Parameters:**
- `sql` (required): The SQL query to execute
- `params` (optional): List of parameters for parameterized queries

**Example:**
```
Run a query to get the top 10 customers by order count
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
