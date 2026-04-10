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

## Initialization order

1. start PostgreSQL
2. apply Alembic migrations
3. initialize the admin account
4. start the backend
5. start the frontend

## Upload storage

Uploaded files are stored under:

```text
data/uploads/trading/{user_id}/{run_id}/
```

The cleanup migration removes legacy tables and pre-unified import history from the database, but current upload runs remain persistent until users delete them.
