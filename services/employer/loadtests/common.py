from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SERVICE_URLS = {
    "auth": "http://localhost:8001",
    "candidate": "http://localhost:8002",
    "employer": "http://localhost:8003",
    "file": "http://localhost:8004",
    "search": "http://localhost:8005",
    "bot": "http://localhost:8010",
}


@dataclass(slots=True)
class LoadTestConfig:
    service_name: str
    profile_name: str
    profile: dict[str, Any]
    service_urls: dict[str, str]
    internal_token: str
    webhook_secret: str | None
    request_timeout_sec: float


class ServiceContextCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, Any] = {}

    def get_or_create(self, key: str, factory):
        if key in self._values:
            return self._values[key]

        with self._lock:
            if key not in self._values:
                self._values[key] = factory()
            return self._values[key]


def _load_json_file(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_config(service_name: str) -> LoadTestConfig:
    profile_name = os.getenv("LOADTEST_PROFILE_NAME", "baseline")
    loadtests_dir = Path(__file__).resolve().parent
    profile_path = Path(
        os.getenv(
            "LOADTEST_PROFILE_PATH",
            str(loadtests_dir / "profiles" / f"{profile_name}.json"),
        )
    )
    profile = _load_json_file(profile_path)

    service_urls = dict(DEFAULT_SERVICE_URLS)
    if os.getenv("LOADTEST_SERVICE_URLS"):
        service_urls.update(json.loads(os.environ["LOADTEST_SERVICE_URLS"]))

    return LoadTestConfig(
        service_name=service_name,
        profile_name=profile_name,
        profile=profile,
        service_urls=service_urls,
        internal_token=os.getenv("LOADTEST_INTERNAL_TOKEN", "change-me-internal-service-token"),
        webhook_secret=os.getenv("LOADTEST_WEBHOOK_SECRET", "change-me-webhook-secret"),
        request_timeout_sec=float(os.getenv("LOADTEST_REQUEST_TIMEOUT_SEC", "10")),
    )


def profile_wait_time(config: LoadTestConfig):
    from locust import between

    min_wait = float(config.profile.get("wait_time_min_sec", 0.2))
    max_wait = float(config.profile.get("wait_time_max_sec", 1.0))
    return between(min_wait, max_wait)


def render_request_headers(
    config: LoadTestConfig,
    *,
    access_token: str | None = None,
    internal: bool = False,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = {
        "X-Loadtest-Service": config.service_name,
        "X-Loadtest-Profile": config.profile_name,
    }
    if internal:
        headers["Authorization"] = f"Bearer {config.internal_token}"
    elif access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if extra:
        headers.update(extra)
    return headers


def expect_status(response, expected_statuses: int | tuple[int, ...], description: str) -> None:
    expected = (expected_statuses,) if isinstance(expected_statuses, int) else expected_statuses
    if response.status_code in expected:
        response.success()
        return
    response.failure(
        f"{description}: unexpected status={response.status_code} body={response.text[:500]}"
    )


def request_json(
    method: str,
    url: str,
    *,
    expected_statuses: int | tuple[int, ...],
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    import requests

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=timeout,
    )
    expected = (expected_statuses,) if isinstance(expected_statuses, int) else expected_statuses
    if response.status_code not in expected:
        raise RuntimeError(
            f"Request failed: {method} {url} status={response.status_code} body={response.text[:500]}"
        )
    if not response.content:
        return {}
    return response.json()


def _unique_telegram_id(prefix: int) -> int:
    suffix = int(time.time() * 1000) % 1_000_000
    return prefix * 1_000_000 + suffix + random.randint(1, 999)


def generate_telegram_id(prefix: int = 700) -> int:
    return _unique_telegram_id(prefix)


def bot_login(
    config: LoadTestConfig,
    *,
    role: str,
    telegram_id: int,
    username: str,
    first_name: str,
    last_name: str,
) -> dict[str, Any]:
    return request_json(
        "POST",
        f"{config.service_urls['auth']}/api/v1/auth/login/bot",
        expected_statuses=200,
        headers=render_request_headers(config, internal=True),
        json_body={
            "telegram_id": telegram_id,
            "role": role,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "photo_url": "https://example.com/loadtest-avatar.jpg",
        },
        timeout=config.request_timeout_sec,
    )


def ensure_candidate_profile(config: LoadTestConfig) -> dict[str, Any]:
    telegram_id = _unique_telegram_id(771)
    session = bot_login(
        config,
        role="candidate",
        telegram_id=telegram_id,
        username=f"candidate_{telegram_id}",
        first_name="Load",
        last_name="Candidate",
    )
    access_token = session["access_token"]

    candidate = request_json(
        "POST",
        f"{config.service_urls['candidate']}/api/v1/candidates",
        expected_statuses=201,
        headers=render_request_headers(config, access_token=access_token),
        json_body={
            "display_name": f"Load Candidate {telegram_id}",
            "headline_role": "Python Backend Engineer",
            "location": "Novosibirsk",
            "work_modes": ["remote", "hybrid"],
            "contacts_visibility": "on_request",
            "contacts": {
                "telegram": f"@candidate_{telegram_id}",
                "email": f"candidate_{telegram_id}@example.com",
            },
            "status": "active",
            "salary_min": 180000,
            "salary_max": 260000,
            "currency": "RUB",
            "english_level": "B2",
            "about_me": "Load-test candidate profile for latency and stability checks.",
            "skills": [
                {"skill": "python", "kind": "hard", "level": 5},
                {"skill": "fastapi", "kind": "hard", "level": 4},
                {"skill": "postgresql", "kind": "hard", "level": 4},
            ],
            "education": [{"level": "bachelor", "institution": "NSU", "year": 2021}],
            "experiences": [
                {
                    "company": "Load Labs",
                    "position": "Backend Engineer",
                    "start_date": "2022-01-01",
                    "end_date": "2025-01-01",
                    "responsibilities": "APIs, async services, PostgreSQL",
                }
            ],
            "projects": [
                {
                    "title": "Recruiter Platform",
                    "description": "Synthetic candidate fixture for performance testing.",
                    "links": ["https://example.com/recruiter-platform"],
                }
            ],
        },
        timeout=config.request_timeout_sec,
    )
    return {
        "telegram_id": telegram_id,
        "access_token": access_token,
        "candidate_id": candidate["id"],
    }


def ensure_employer_profile(config: LoadTestConfig) -> dict[str, Any]:
    telegram_id = _unique_telegram_id(881)
    session = bot_login(
        config,
        role="employer",
        telegram_id=telegram_id,
        username=f"employer_{telegram_id}",
        first_name="Load",
        last_name="Employer",
    )
    access_token = session["access_token"]

    employer = request_json(
        "POST",
        f"{config.service_urls['employer']}/api/v1/employers",
        expected_statuses=201,
        headers=render_request_headers(config, access_token=access_token),
        json_body={
            "telegram_id": telegram_id,
            "company": f"Load Employer {telegram_id}",
            "contacts": {
                "email": f"employer_{telegram_id}@example.com",
                "telegram": f"@employer_{telegram_id}",
            },
        },
        timeout=config.request_timeout_sec,
    )
    return {
        "telegram_id": telegram_id,
        "access_token": access_token,
        "employer_id": employer["id"],
    }


def ensure_search_index_document(config: LoadTestConfig, candidate_id: str) -> dict[str, Any]:
    import requests

    url = f"{config.service_urls['search']}/api/v1/internal/index/candidates/{candidate_id}"
    headers = render_request_headers(config, internal=True)
    read_timeout = max(min(config.request_timeout_sec, 10.0), 3.0)
    setup_timeout = max(config.request_timeout_sec * 3, 30.0)
    deadline = time.monotonic() + setup_timeout

    while time.monotonic() < deadline:
        try:
            response = requests.get(url, headers=headers, timeout=read_timeout)
        except requests.RequestException:
            time.sleep(0.5)
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code != 404:
            raise RuntimeError(
                f"Request failed: GET {url} status={response.status_code} body={response.text[:500]}"
            )
        time.sleep(0.5)

    request_json(
        "POST",
        url,
        expected_statuses=200,
        headers=headers,
        timeout=setup_timeout,
    )

    deadline = time.monotonic() + setup_timeout
    while time.monotonic() < deadline:
        try:
            response = requests.get(url, headers=headers, timeout=read_timeout)
        except requests.RequestException:
            time.sleep(0.5)
            continue
        if response.status_code == 200:
            return response.json()
        if response.status_code != 404:
            raise RuntimeError(
                f"Request failed: GET {url} status={response.status_code} body={response.text[:500]}"
            )
        time.sleep(0.5)

    raise RuntimeError(f"Search document was not indexed in time for candidate_id={candidate_id}")


def resolve_locust_executable(service_root: Path) -> str:
    venv_locust = (service_root / ".venv" / "bin" / "locust").resolve()
    if venv_locust.exists():
        return str(venv_locust)
    system_locust = shutil.which("locust")
    if system_locust:
        return system_locust
    raise RuntimeError("Locust executable not found. Install service dev dependencies first.")


def _build_healthcheck_url(host: str) -> str:
    normalized = host.rstrip("/")
    if normalized.endswith("/api/v1/health"):
        return normalized
    return f"{normalized}/api/v1/health"


def wait_for_service_ready(host: str, *, timeout_sec: float, request_timeout_sec: float) -> None:
    import requests

    healthcheck_url = _build_healthcheck_url(host)
    deadline = time.monotonic() + timeout_sec
    last_error: str | None = None
    read_timeout = max(1.0, min(request_timeout_sec, 5.0))

    while time.monotonic() < deadline:
        try:
            response = requests.get(healthcheck_url, timeout=read_timeout)
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(1.0)
            continue

        if 200 <= response.status_code < 300:
            return

        last_error = f"status={response.status_code} body={response.text[:200]}"
        time.sleep(1.0)

    details = f": {last_error}" if last_error else ""
    raise RuntimeError(f"Service is not ready at {healthcheck_url}{details}")


def run_headless_locust(service_name: str) -> int:
    parser = argparse.ArgumentParser(description=f"Run {service_name} loadtests")
    parser.add_argument("--profile", default="baseline", choices=("smoke", "baseline", "stress"))
    parser.add_argument("--host", default=None)
    parser.add_argument("--users", type=int, default=None)
    parser.add_argument("--spawn-rate", type=float, default=None)
    parser.add_argument("--run-time", default=None)
    parser.add_argument("--stop-timeout", type=int, default=None)
    parser.add_argument("--internal-token", default="change-me-internal-service-token")
    parser.add_argument("--webhook-secret", default="change-me-webhook-secret")
    parser.add_argument("--request-timeout-sec", type=float, default=10.0)
    parser.add_argument("--readiness-timeout-sec", type=float, default=90.0)
    parser.add_argument("--skip-readiness-check", action="store_true")
    parser.add_argument("locust_args", nargs="*")
    args = parser.parse_args()

    loadtests_dir = Path(__file__).resolve().parent
    service_root = loadtests_dir.parent
    profile_path = loadtests_dir / "profiles" / f"{args.profile}.json"
    profile = _load_json_file(profile_path)

    if args.users is not None:
        profile["users"] = args.users
    if args.spawn_rate is not None:
        profile["spawn_rate"] = args.spawn_rate
    if args.run_time is not None:
        profile["run_time"] = args.run_time
    if args.stop_timeout is not None:
        profile["stop_timeout"] = args.stop_timeout

    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(service_root) if not pythonpath else f"{service_root}{os.pathsep}{pythonpath}"
    )
    env.update(
        {
            "LOADTEST_PROFILE_NAME": args.profile,
            "LOADTEST_PROFILE_PATH": str(profile_path),
            "LOADTEST_INTERNAL_TOKEN": args.internal_token,
            "LOADTEST_WEBHOOK_SECRET": args.webhook_secret,
            "LOADTEST_REQUEST_TIMEOUT_SEC": str(args.request_timeout_sec),
        }
    )

    host = str(args.host or profile.get("host", DEFAULT_SERVICE_URLS[service_name]))
    if not args.skip_readiness_check:
        wait_for_service_ready(
            host,
            timeout_sec=args.readiness_timeout_sec,
            request_timeout_sec=args.request_timeout_sec,
        )

    command = [
        resolve_locust_executable(service_root),
        "-f",
        "loadtests/locustfile.py",
        "--headless",
        "--users",
        str(profile["users"]),
        "--spawn-rate",
        str(profile["spawn_rate"]),
        "--run-time",
        str(profile["run_time"]),
        "--host",
        host,
        "--stop-timeout",
        str(profile.get("stop_timeout", 15)),
    ]
    command.extend(args.locust_args)
    print(f"[loadtest] running {service_name}: {' '.join(command)}")
    completed = subprocess.run(command, cwd=service_root, env=env, check=False)
    return completed.returncode
