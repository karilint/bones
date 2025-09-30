# Bones Django Project

This repository contains a Django 4 project configured to run against a Microsoft SQL Server
instance in local development. Environment variables are stored in a `.env` file that is
loaded automatically by `settings.py`.

## Prerequisites

* Python 3.10+
* A local Microsoft SQL Server instance (Developer or Express edition works well)
* The Microsoft ODBC Driver for SQL Server (version 17 or 18)
* `virtualenv` or another tool for managing isolated Python environments

## Initial setup

1. **Create and activate a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate (Unix/Bash)
   .\.venv\Scripts\Activate.ps1 (windows/Powershell)
   ```

2. **Install the required Python packages**

   ```bash
   pip install -r app/requirements.txt
   ```

3. **Provision a SQL Server database**

   * Create a new database for the application, e.g. `bones`.
   * Create a SQL Server login (SQL authentication) with ownership of the new database.
   * Ensure the login has permission to create tables and run migrations.

4. **Create a `.env` file at the project root**

   ```ini
   DEBUG=1
   SECRET_KEY=replace-with-a-secure-value
   ALLOWED_HOSTS=localhost,127.0.0.1
   MSSQL_HOST=localhost
   MSSQL_PORT=1433
   MSSQL_DB=bones
   MSSQL_USER=app_user
   MSSQL_PASSWORD=super_secure_password
   MSSQL_ENCRYPT=no
   MSSQL_TRUST_CERT=yes
   MSSQL_TDS_VERSION=8.0
   ```

   Adjust the values to match your local SQL Server configuration. If you are connecting to a
   remote host from macOS or Windows, you may need to set `MSSQL_HOST=host.docker.internal`.

5. **Apply database migrations**

   ```bash
   cd app
   python manage.py migrate
   ```

6. **Run the development server**

   ```bash
   python manage.py runserver
   ```

   The site will be available at <http://127.0.0.1:8000/>.

## Testing

Automated tests run against an in-project SQLite database to keep the suite lightweight. No
additional configuration is required—`python manage.py test` will switch to SQLite automatically.

## Application architecture

The Django app is organised around reusable navigation, list, detail, master-detail, dashboard, and
history archetypes. The new [architecture overview](docs/architecture.md) summarises how forms,
filters, templates, and view layers collaborate and links back to the shared
[Django app guidelines](https://github.com/karilint/bones/blob/main/docs/django_app_guidelines.md)
for quick reference.

## Environment variables

`settings.py` loads configuration values from the `.env` file if present. The following variables
are used for the SQL Server connection:

| Variable | Description |
| --- | --- |
| `MSSQL_HOST` | SQL Server hostname or IP address. |
| `MSSQL_PORT` | SQL Server port (defaults to `1433`). |
| `MSSQL_DB` | Database name. |
| `MSSQL_USER` | SQL Server login. |
| `MSSQL_PASSWORD` | Login password. |
| `MSSQL_ENCRYPT` | `yes`/`no` flag passed to the driver `Encrypt` parameter. |
| `MSSQL_TRUST_CERT` | `yes`/`no` flag passed to the driver `TrustServerCertificate` parameter. |
| `MSSQL_TDS_VERSION` | Optional TDS protocol version (for FreeTDS clients). |
| `MSSQL_DRIVER` | Optional override for the ODBC driver name (defaults to `ODBC Driver 18 for SQL Server`). |

`DEBUG`, `SECRET_KEY`, and other standard Django settings can also be provided through the `.env`
file.

## Production notes

This project was originally scaffolded for container-based deployment, but Docker is not required
for local development. If you intend to deploy with Docker, ensure that the container has access to
your SQL Server instance and that the ODBC drivers are installed.
