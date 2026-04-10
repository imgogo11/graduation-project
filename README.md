# Unified Trading Data Management System

This project now keeps a single business path:

- real user registration and login
- user-scoped trading data uploads through `CSV` and `XLSX`
- permanent import history with soft delete
- admin visibility across all users
- unified trading analysis for both stock and commodity datasets

All legacy stock crawler, e-commerce demo, synthetic dataset, and benchmark import paths have been retired from the active system.

## Stack

- Frontend: Vue 3 + TypeScript + Element Plus + ECharts
- Backend: FastAPI + SQLAlchemy + Alembic + Pandas
- Database: PostgreSQL
- Algo engine: C++ + PyBind11

## Current data model

- `users`
- `import_runs`
- `import_manifests`
- `import_artifacts`
- `trading_records`

## Supported upload template

```text
instrument_code,instrument_name,trade_date,open,high,low,close,volume,amount
```

- supported file formats: `.csv`, `.xlsx`
- asset classes: `stock`, `commodity`
- asset class is now only a dataset label; both use the same storage and analysis flow

## Setup

### 1. Install dependencies

```powershell
uv venv .venv --python 3.13
uv sync
cd frontend
npm install
cd ..
```

### 2. Prepare environment

```powershell
Copy-Item .env.template .env
```

Review these variables before running:

- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `UPLOAD_ROOT`

### 3. Start PostgreSQL and apply migrations

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe backend/scripts/init_admin.py
```

The latest migration removes legacy business tables and purges pre-unified import history, so only the current upload-based trading flow remains visible in the system.

### 4. Start backend and frontend

Backend:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8200 --reload
```

Frontend:

```powershell
cd frontend
npm run dev
```

## Main APIs

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/health`
- `GET /api/imports/runs`
- `GET /api/imports/stats`
- `POST /api/imports/trading`
- `DELETE /api/imports/runs/{run_id}`
- `GET /api/trading/instruments`
- `GET /api/trading/records`
- `GET /api/algo/trading/range-max-amount`

## Useful scripts

Initialize the admin account:

```powershell
.\.venv\Scripts\python.exe backend/scripts/init_admin.py
```

Import a local trading file from the command line:

```powershell
.\.venv\Scripts\python.exe backend/scripts/import_data.py --file-path .\frontend\public\trading_import_template.csv --dataset-name demo_run --asset-class stock
```

Export compatibility requirements:

```powershell
.\.venv\Scripts\python.exe backend/scripts/export_requirements.py
```

## Verification

Backend:

```powershell
.\.venv\Scripts\python.exe backend/tests/test_database_pipeline.py
.\.venv\Scripts\python.exe backend/tests/test_algo_trading.py
```

Frontend:

```powershell
cd frontend
npm run build
```
