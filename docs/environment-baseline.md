# Environment Baseline

## Required service

- PostgreSQL 15+

## Startup

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
```

## Required environment variables

- `DATABASE_URL`
- `JWT_SECRET`
- `JWT_EXPIRE_MINUTES`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `UPLOAD_ROOT`
- `POSTGRES_PORT=15432` for the host-side PostgreSQL port

The project defaults to host port `15432` instead of `5432`, because some Windows environments reserve the range containing `5432` and reject local binds.

## Frontend development defaults

- `VITE_BACKEND_TARGET=http://127.0.0.1:8200`
- `VITE_DEV_HOST=127.0.0.1`
- `VITE_DEV_PORT=4173`

The frontend dev server defaults to `4173` instead of `5173`, because some Windows environments reserve the `5173` port range and reject local binds.

## Initialization order

1. start PostgreSQL
2. apply Alembic migrations
3. initialize the admin account
4. start the backend
5. start the frontend

After startup, the frontend is expected at `http://127.0.0.1:4173`.

## Upload storage

Uploaded files are stored under:

```text
data/uploads/trading/{user_id}/{run_id}/
```

The cleanup migration removes legacy tables and pre-unified import history from the database, but current upload runs remain persistent until users delete them.
