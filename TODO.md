# TODO

## Before PyPI Publish
- [ ] Rename package (name `mssql-mcp` is already taken)
  - Options: `mssql-mcp-server`, `pyodbc-mcp`, `sqlserver-mcp`

## Completed (v0.2.0)
- [x] Error handling with structured responses
- [x] Query timeout support (MSSQL_QUERY_TIMEOUT)
- [x] Row limit for queries (MSSQL_MAX_ROWS)
- [x] Connection pooling with health checks
- [x] Debug logging (MSSQL_DEBUG)
- [x] New discovery tools: list_schemas, list_views, list_procedures
- [x] New exploration tools: get_table_sample, search_tables, search_columns, get_table_stats
- [x] New tools: describe_procedure, execute_procedure
- [x] Pytest test suite (34 tests)
