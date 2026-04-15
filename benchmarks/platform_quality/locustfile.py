from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import uuid

from locust import HttpUser, between, events, task


BENCHMARK_USERNAME = os.getenv("BENCHMARK_USERNAME", "")
BENCHMARK_PASSWORD = os.getenv("BENCHMARK_PASSWORD", "")
BENCHMARK_IMPORT_RUN_ID = os.getenv("BENCHMARK_IMPORT_RUN_ID")
BENCHMARK_SAMPLE = os.getenv("BENCHMARK_SAMPLE", "unknown")
LOCUST_STATUS_OUTPUT = os.getenv("LOCUST_STATUS_OUTPUT")

_status_counts: Counter[str] = Counter()
_security_case_totals: dict[str, dict[str, object]] = {}
_run_context: dict[str, object] | None = None


def _status_label(response, exception) -> str:
    if response is not None:
        return str(response.status_code)
    if exception is not None:
        return "EXC"
    return "UNKNOWN"


def _record_security_case(case_name: str, *, status: str, expected_statuses: list[str]) -> None:
    state = _security_case_totals.setdefault(
        case_name,
        {
            "expected_statuses": expected_statuses,
            "total": 0,
            "matched": 0,
            "status_counts": Counter(),
        },
    )
    state["total"] = int(state["total"]) + 1
    state["status_counts"][status] += 1
    if status in expected_statuses:
        state["matched"] = int(state["matched"]) + 1


def _should_track_status(name: str | None) -> bool:
    return bool(name) and not str(name).startswith("setup/")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):  # noqa: ANN001
    status = _status_label(response, exception)
    if _should_track_status(name):
        _status_counts[status] += 1
    if context and context.get("security_case"):
        expected = [str(item) for item in context.get("expected_statuses", [])]
        _record_security_case(str(context["security_case"]), status=status, expected_statuses=expected)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):  # noqa: ANN001
    if not LOCUST_STATUS_OUTPUT:
        return
    output_path = Path(LOCUST_STATUS_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "sample": BENCHMARK_SAMPLE,
        "status_counts": dict(_status_counts),
        "security_cases": [
            {
                "case": case_name,
                "expected_statuses": state["expected_statuses"],
                "total": int(state["total"]),
                "matched": int(state["matched"]),
                "matched_ratio": round(int(state["matched"]) / int(state["total"]), 6) if int(state["total"]) else 0.0,
                "status_counts": dict(state["status_counts"]),
            }
            for case_name, state in sorted(_security_case_totals.items())
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _expect_response(response, *, expected_statuses: list[int]) -> None:
    if response.status_code in expected_statuses:
        response.success()
    else:
        response.failure(f"Expected {expected_statuses}, got {response.status_code}")


def _resolve_run_context(client, token: str) -> dict[str, object]:
    global _run_context
    if _run_context is not None:
        return _run_context

    headers = _auth_headers(token)
    if BENCHMARK_IMPORT_RUN_ID:
        run_id = int(BENCHMARK_IMPORT_RUN_ID)
    else:
        runs_response = client.get("/api/imports/runs", headers=headers, name="setup/imports_runs")
        runs_response.raise_for_status()
        run_rows = runs_response.json()
        if not run_rows:
            raise RuntimeError("No import runs available for Locust benchmark execution.")
        run_id = int(run_rows[0]["id"])

    risk_ready = False
    status_response = client.get("/api/algo/indexes/status", params={"import_run_id": run_id}, headers=headers, name="setup/index_status")
    if status_response.status_code == 200 and bool(status_response.json().get("is_ready")):
        risk_ready = True
    elif status_response.status_code == 200:
        rebuild_response = client.post("/api/algo/indexes/rebuild", params={"import_run_id": run_id}, headers=headers, name="setup/index_rebuild")
        if rebuild_response.status_code == 200 and bool(rebuild_response.json().get("is_ready")):
            risk_ready = True
        else:
            for _ in range(10):
                poll_response = client.get("/api/algo/indexes/status", params={"import_run_id": run_id}, headers=headers, name="setup/index_status_poll")
                if poll_response.status_code == 200 and bool(poll_response.json().get("is_ready")):
                    risk_ready = True
                    break

    stocks_response = client.get("/api/trading/stocks", params={"import_run_id": run_id}, headers=headers, name="setup/stocks")
    stocks_response.raise_for_status()
    stock_rows = stocks_response.json()
    if not stock_rows:
        raise RuntimeError("No stock rows available for Locust benchmark execution.")
    stock_code = str(stock_rows[0]["stock_code"])

    records_response = client.get(
        "/api/trading/records",
        params={"import_run_id": run_id, "stock_code": stock_code},
        headers=headers,
        name="setup/records",
    )
    records_response.raise_for_status()
    records = records_response.json()
    if not records:
        raise RuntimeError("No trading records available for Locust benchmark execution.")
    start_date = str(records[0]["trade_date"])
    end_date = str(records[-1]["trade_date"])
    kth = min(5, len(records))

    risk_event = None
    if risk_ready:
        risk_response = client.get(
            "/api/algo/risk-radar/events",
            params={"import_run_id": run_id, "top_n": 1},
            headers=headers,
            name="setup/risk_event",
        )
        if risk_response.status_code == 200 and risk_response.json().get("rows"):
            risk_event = risk_response.json()["rows"][0]

    _run_context = {
        "import_run_id": run_id,
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date,
        "k": kth,
        "risk_event": risk_event,
        "risk_ready": risk_ready,
    }
    return _run_context


class AuthenticatedBenchmarkUser(HttpUser):
    wait_time = between(0.2, 0.6)
    token: str
    run_context: dict[str, object]

    def on_start(self) -> None:
        login_response = self.client.post(
            "/api/auth/login",
            json={"username": BENCHMARK_USERNAME, "password": BENCHMARK_PASSWORD},
            name="auth/login",
        )
        login_response.raise_for_status()
        self.token = str(login_response.json()["access_token"])
        self.run_context = _resolve_run_context(self.client, self.token)

    @task(3)
    def list_runs(self) -> None:
        self.client.get("/api/imports/runs", headers=_auth_headers(self.token), name="imports/runs")

    @task(3)
    def list_records(self) -> None:
        self.client.get(
            "/api/trading/records",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
            },
            headers=_auth_headers(self.token),
            name="trading/records",
        )

    @task(2)
    def query_range_max(self) -> None:
        self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
                "start_date": self.run_context["start_date"],
                "end_date": self.run_context["end_date"],
            },
            headers=_auth_headers(self.token),
            name="algo/range_max_amount",
        )

    @task(2)
    def query_range_kth_persistent(self) -> None:
        self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
                "start_date": self.run_context["start_date"],
                "end_date": self.run_context["end_date"],
                "k": self.run_context["k"],
                "method": "persistent_segment_tree",
            },
            headers=_auth_headers(self.token),
            name="algo/range_kth_persistent",
        )

    @task(2)
    def query_range_kth_tdigest(self) -> None:
        self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
                "start_date": self.run_context["start_date"],
                "end_date": self.run_context["end_date"],
                "k": self.run_context["k"],
                "method": "t_digest",
            },
            headers=_auth_headers(self.token),
            name="algo/range_kth_tdigest",
        )

    @task(2)
    def risk_overview(self) -> None:
        if not self.run_context.get("risk_ready"):
            return
        self.client.get(
            "/api/algo/risk-radar/overview",
            params={"import_run_id": self.run_context["import_run_id"]},
            headers=_auth_headers(self.token),
            name="risk_radar/overview",
        )

    @task(1)
    def risk_events(self) -> None:
        if not self.run_context.get("risk_ready"):
            return
        self.client.get(
            "/api/algo/risk-radar/events",
            params={"import_run_id": self.run_context["import_run_id"], "top_n": 10},
            headers=_auth_headers(self.token),
            name="risk_radar/events",
        )

    @task(1)
    def risk_event_context(self) -> None:
        if not self.run_context.get("risk_ready"):
            return
        risk_event = self.run_context.get("risk_event")
        if not risk_event:
            return
        self.client.get(
            "/api/algo/risk-radar/event-context",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": risk_event["stock_code"],
                "trade_date": risk_event["trade_date"],
            },
            headers=_auth_headers(self.token),
            name="risk_radar/event_context",
        )


class SecurityProbeUser(HttpUser):
    wait_time = between(0.3, 0.8)
    token: str
    attacker_token: str | None = None
    run_context: dict[str, object]

    def on_start(self) -> None:
        login_response = self.client.post(
            "/api/auth/login",
            json={"username": BENCHMARK_USERNAME, "password": BENCHMARK_PASSWORD},
            name="setup/security_login",
        )
        login_response.raise_for_status()
        self.token = str(login_response.json()["access_token"])
        self.run_context = _resolve_run_context(self.client, self.token)
        attacker_username = f"bench_attacker_{uuid.uuid4().hex[:10]}"
        attacker_password = "codex-attack-123"
        self.client.post(
            "/api/auth/register",
            json={"username": attacker_username, "password": attacker_password},
            name="setup/security_register_attacker",
        )
        attacker_login = self.client.post(
            "/api/auth/login",
            json={"username": attacker_username, "password": attacker_password},
            name="setup/security_login_attacker",
        )
        if attacker_login.status_code == 200:
            self.attacker_token = str(attacker_login.json()["access_token"])

    @task(2)
    def no_auth_runs(self) -> None:
        with self.client.get(
            "/api/imports/runs",
            name="security/no_auth_runs",
            catch_response=True,
            context={"security_case": "no_auth_runs", "expected_statuses": [401]},
        ) as response:
            _expect_response(response, expected_statuses=[401])

    @task(2)
    def invalid_token_me(self) -> None:
        with self.client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
            name="security/invalid_token_me",
            catch_response=True,
            context={"security_case": "invalid_token_me", "expected_statuses": [401]},
        ) as response:
            _expect_response(response, expected_statuses=[401])

    @task(1)
    def cross_user_records(self) -> None:
        if not self.attacker_token:
            return
        with self.client.get(
            "/api/trading/records",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
            },
            headers=_auth_headers(self.attacker_token),
            name="security/cross_user_records",
            catch_response=True,
            context={"security_case": "cross_user_records", "expected_statuses": [404]},
        ) as response:
            _expect_response(response, expected_statuses=[404])

    @task(1)
    def invalid_k(self) -> None:
        with self.client.get(
            "/api/algo/trading/range-kth-volume",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
                "start_date": self.run_context["start_date"],
                "end_date": self.run_context["end_date"],
                "k": 0,
                "method": "persistent_segment_tree",
            },
            headers=_auth_headers(self.token),
            name="security/invalid_k",
            catch_response=True,
            context={"security_case": "invalid_k", "expected_statuses": [400]},
        ) as response:
            _expect_response(response, expected_statuses=[400])

    @task(1)
    def invalid_date_range(self) -> None:
        with self.client.get(
            "/api/algo/trading/range-max-amount",
            params={
                "import_run_id": self.run_context["import_run_id"],
                "stock_code": self.run_context["stock_code"],
                "start_date": self.run_context["end_date"],
                "end_date": self.run_context["start_date"],
            },
            headers=_auth_headers(self.token),
            name="security/invalid_date_range",
            catch_response=True,
            context={"security_case": "invalid_date_range", "expected_statuses": [400]},
        ) as response:
            _expect_response(response, expected_statuses=[400])
