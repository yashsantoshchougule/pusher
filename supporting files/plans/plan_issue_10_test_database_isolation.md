# Issue 10 — Test database isolation

- Resolve the SQLite path in backend settings and use the same connection and schema initialization for reports and the rest of the API.
- Configure an isolated temporary database in the project's pytest conftest before test module imports. Fail early if the application database was imported before isolation.
- Run cleanup against the test database and prove a second SQLite file keeps its data. Repeat restart and authenticated access checks.
