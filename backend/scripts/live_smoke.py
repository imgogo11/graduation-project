from __future__ import annotations

import argparse
from collections.abc import Iterable
import time
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live API smoke test against the running trading system backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8200", help="Backend base URL without the /api suffix.")
    parser.add_argument("--username", required=True, help="Business user used for the mainline smoke flow.")
    parser.add_argument("--password", required=True, help="Password for the business user.")
    parser.add_argument("--dataset-name", help="Prefer this dataset when resolving the smoke import run.")
    parser.add_argument("--run-id", type=int, help="Explicit import_run_id to use instead of resolving by dataset.")
    parser.add_argument("--admin-username", help="Optional admin username for admin-only smoke calls.")
    parser.add_argument("--admin-password", help="Optional admin password for admin-only smoke calls.")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval in seconds for index readiness.")
    parser.add_argument("--poll-timeout", type=float, default=60.0, help="Polling timeout in seconds for index readiness.")
    return parser.parse_args()


def login(client: httpx.Client, *, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    response.raise_for_status()
    payload = response.json()
    return str(payload["access_token"])


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def get_json(
    client: httpx.Client,
    path: str,
    *,
    token: str,
    params: dict[str, Any] | None = None,
) -> Any:
    response = client.get(path, headers=auth_headers(token), params=params)
    response.raise_for_status()
    return response.json()


def post_json(
    client: httpx.Client,
    path: str,
    *,
    token: str,
    params: dict[str, Any] | None = None,
) -> Any:
    response = client.post(path, headers=auth_headers(token), params=params)
    response.raise_for_status()
    return response.json()


def resolve_run_id(run_rows: list[dict[str, Any]], *, run_id: int | None, dataset_name: str | None) -> int:
    if run_id is not None:
        for row in run_rows:
            if int(row["id"]) == run_id:
                return run_id
        raise ValueError(f"Import run {run_id} is not visible to the smoke user.")

    if dataset_name:
        for row in run_rows:
            if str(row["dataset_name"]) == dataset_name:
                return int(row["id"])
        raise ValueError(f"Dataset {dataset_name!r} is not visible to the smoke user.")

    if not run_rows:
        raise ValueError("No visible import runs were found for the smoke user.")
    return int(run_rows[0]["id"])


def ensure_ready_index(
    client: httpx.Client,
    *,
    token: str,
    run_id: int,
    admin_token: str | None,
    poll_interval: float,
    poll_timeout: float,
) -> dict[str, Any]:
    status = get_json(client, "/api/algo/indexes/status", token=token, params={"import_run_id": run_id})
    if bool(status.get("is_ready")):
        return status

    if admin_token is None:
        raise RuntimeError("Risk radar index is not ready and no admin credentials were provided for rebuild.")

    post_json(client, "/api/algo/indexes/rebuild", token=admin_token, params={"import_run_id": run_id})
    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        status = get_json(client, "/api/algo/indexes/status", token=token, params={"import_run_id": run_id})
        if bool(status.get("is_ready")):
            return status
        time.sleep(poll_interval)

    raise TimeoutError(f"Risk radar index for import run {run_id} did not become ready within {poll_timeout} seconds.")


def first_item(rows: Iterable[dict[str, Any]], *, description: str) -> dict[str, Any]:
    for row in rows:
        return row
    raise ValueError(f"No rows returned for {description}.")


def main() -> int:
    args = parse_args()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30.0) as client:
        user_token = login(client, username=args.username, password=args.password)
        admin_token = None
        if args.admin_username and args.admin_password:
            admin_token = login(client, username=args.admin_username, password=args.admin_password)

        me = get_json(client, "/api/auth/me", token=user_token)
        if str(me["username"]) != args.username:
            raise RuntimeError("Authenticated user does not match the requested smoke user.")

        run_rows = get_json(client, "/api/imports/runs", token=user_token)
        stats = get_json(client, "/api/imports/stats", token=user_token)
        if int(stats["total_runs"]) <= 0:
            raise RuntimeError("Smoke user does not have any visible import runs.")

        run_id = resolve_run_id(run_rows, run_id=args.run_id, dataset_name=args.dataset_name)
        stocks = get_json(client, "/api/trading/stocks", token=user_token, params={"import_run_id": run_id})
        stock_row = first_item(stocks, description="stock listing")
        stock_code = str(stock_row["stock_code"])

        records = get_json(
            client,
            "/api/trading/records",
            token=user_token,
            params={"import_run_id": run_id, "stock_code": stock_code},
        )
        record_rows = list(records)
        first_record = first_item(record_rows, description="trading records")
        last_record = record_rows[-1]
        start_date = str(first_record["trade_date"])
        end_date = str(last_record["trade_date"])
        kth = min(5, len(record_rows))
        correlation_codes = ",".join(str(row["stock_code"]) for row in stocks[: min(3, len(stocks))])

        scope_params = {
            "import_run_id": run_id,
            "stock_code": stock_code,
            "start_date": start_date,
            "end_date": end_date,
        }
        get_json(client, "/api/trading/analysis/summary", token=user_token, params=scope_params)
        get_json(client, "/api/trading/analysis/quality", token=user_token, params=scope_params)
        get_json(client, "/api/trading/analysis/indicators", token=user_token, params=scope_params)
        get_json(client, "/api/trading/analysis/risk", token=user_token, params=scope_params)
        get_json(client, "/api/trading/analysis/anomalies", token=user_token, params=scope_params)
        get_json(
            client,
            "/api/trading/analysis/cross-section",
            token=user_token,
            params={
                "import_run_id": run_id,
                "start_date": start_date,
                "end_date": end_date,
                "metric": "total_return",
                "top_n": 5,
            },
        )
        get_json(
            client,
            "/api/trading/analysis/correlation",
            token=user_token,
            params={
                "import_run_id": run_id,
                "start_date": start_date,
                "end_date": end_date,
                "stock_codes": correlation_codes,
            },
        )
        get_json(
            client,
            "/api/trading/analysis/compare-scopes",
            token=user_token,
            params={
                "base_run_id": run_id,
                "target_run_id": run_id,
                "base_stock_code": stock_code,
                "target_stock_code": stock_code,
                "base_start_date": start_date,
                "base_end_date": end_date,
                "target_start_date": start_date,
                "target_end_date": end_date,
            },
        )

        get_json(
            client,
            "/api/algo/trading/range-max-amount",
            token=user_token,
            params={
                "import_run_id": run_id,
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        get_json(
            client,
            "/api/algo/trading/range-kth-volume",
            token=user_token,
            params={
                "import_run_id": run_id,
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "k": kth,
                "method": "persistent_segment_tree",
            },
        )
        get_json(
            client,
            "/api/algo/trading/range-kth-volume",
            token=user_token,
            params={
                "import_run_id": run_id,
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "k": kth,
                "method": "t_digest",
            },
        )
        get_json(
            client,
            "/api/algo/trading/joint-anomaly-ranking",
            token=user_token,
            params={
                "import_run_id": run_id,
                "start_date": start_date,
                "end_date": end_date,
                "top_n": 10,
            },
        )

        ensure_ready_index(
            client,
            token=user_token,
            run_id=run_id,
            admin_token=admin_token,
            poll_interval=args.poll_interval,
            poll_timeout=args.poll_timeout,
        )
        overview = get_json(client, "/api/algo/risk-radar/overview", token=user_token, params={"import_run_id": run_id})
        events = get_json(
            client,
            "/api/algo/risk-radar/events",
            token=user_token,
            params={"import_run_id": run_id, "top_n": 10},
        )
        get_json(
            client,
            "/api/algo/risk-radar/stocks",
            token=user_token,
            params={"import_run_id": run_id, "top_n": 10},
        )
        get_json(client, "/api/algo/risk-radar/calendar", token=user_token, params={"import_run_id": run_id})

        event_rows = list(events["rows"])
        if event_rows:
            first_event = event_rows[0]
            get_json(
                client,
                "/api/algo/risk-radar/event-context",
                token=user_token,
                params={
                    "import_run_id": run_id,
                    "stock_code": first_event["stock_code"],
                    "trade_date": first_event["trade_date"],
                },
            )

        if admin_token is not None:
            get_json(client, "/api/admin/users", token=admin_token)
            post_json(client, "/api/algo/indexes/rebuild", token=admin_token, params={"import_run_id": run_id})

        print(
            "live_smoke_ok "
            f"user={args.username} run_id={run_id} stock_code={stock_code} "
            f"records={len(record_rows)} radar_events={len(event_rows)} total_events={overview['total_events']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
