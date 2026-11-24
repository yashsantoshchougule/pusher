"""Fixed-size loopback benchmark for check_local_sandbox.py --benchmark."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep

import httpx
import psutil

ROOT = Path(__file__).resolve().parents[3]
BUDGET_MB = 500
WINDOW_SECONDS = 15


def emit(data):
    print(json.dumps(data), flush=True)


def loopback_ports():
    with socket.socket() as runner, socket.socket() as target:
        runner.bind(("127.0.0.1", 0))
        target.bind(("127.0.0.1", 0))
        return runner.getsockname()[1], target.getsockname()[1]


@contextmanager
def service(port, path, target_origin):
    env = {
        **os.environ,
        "PUSHER_MODE": "local_dev",
        "PUSHER_OFFLINE_DEV": "true",
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "PUSHER_DB_PATH": str(path),
        "PUSHER_SANDBOX_ORIGINS": json.dumps([target_origin]),
        "SUPABASE_URL": "",
        "SUPABASE_JWKS_URL": "",
    }
    child = subprocess.Popen([
        sys.executable, "-s", "-B", "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", str(port), "--no-access-log", "--log-level", "warning",
    ], cwd=ROOT, env=env)
    try:
        deadline = monotonic() + 15
        with httpx.Client(trust_env=False, timeout=1) as client:
            while monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError(f"Loopback service on port {port} exited during startup.")
                try:
                    response = client.get(f"http://127.0.0.1:{port}/")
                    if response.is_success and response.json().get("service") == "Pusher Backend Engine":
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                sleep(0.1)
            else:
                raise TimeoutError(f"Loopback service on port {port} did not become ready.")
        yield psutil.Process(child.pid)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def connections(process, port):
    try:
        return sum(
            item.status == psutil.CONN_ESTABLISHED and bool(item.laddr) and item.laddr.port == port
            for item in process.net_connections(kind="tcp")
        )
    except (psutil.AccessDenied, NotImplementedError):
        return None


def measure(client, target, processes, target_port, requested, trial):
    started = client.post("/api/load/start", json={
        "target_url": target, "is_sandbox": True, "traffic_mode": "steady_crowd",
        "target_vus": requested, "duration_sec": WINDOW_SECONDS + 5,
        "cache_bust": False, "ram_limit_mb": BUDGET_MB,
    }).raise_for_status().json()
    run_id = started["run_id"]
    peak_vus = 0
    peak_connections = None
    peak_rss = dict.fromkeys(processes, 0.0)
    peak_cpu = dict.fromkeys(processes, 0.0)
    for process in processes.values():
        process.cpu_percent()
    stopped_early = False
    stop_ms = None
    start_time = monotonic()
    deadline = start_time + WINDOW_SECONDS
    try:
        while monotonic() < deadline:
            sleep(min(0.5, max(0, deadline - monotonic())))
            status = client.get("/api/load/status").raise_for_status().json()
            if status["run_id"] != run_id:
                raise RuntimeError("The first reported status did not belong to the benchmark run.")
            if not status["is_running"]:
                stopped_early = True
                break
            peak_vus = max(peak_vus, status["active_vus"])
            for name, process in processes.items():
                peak_rss[name] = max(peak_rss[name], process.memory_info().rss / 1024**2)
                peak_cpu[name] = max(peak_cpu[name], process.cpu_percent())
            count = connections(processes["target"], target_port)
            if count is not None:
                peak_connections = max(peak_connections or 0, count)
    finally:
        elapsed = monotonic() - start_time
        if not stopped_early:
            stop_started = monotonic()
            response = client.post("/api/load/stop", json={"run_id": run_id})
            stop_elapsed = (monotonic() - stop_started) * 1000
            if response.status_code == 409:
                last = client.get("/api/load/status").raise_for_status().json()
                if last.get("run_id") != run_id or last.get("is_running") is not False:
                    response.raise_for_status()
                stopped_early = True
            else:
                snapshot = response.raise_for_status().json()["snapshot"]
                if snapshot["run_id"] != run_id or snapshot["is_running"]:
                    raise RuntimeError("Stop did not confirm a drained benchmark run.")
                stop_ms = round(stop_elapsed, 1)

    report = client.get(f"/api/reports/{run_id}/export").raise_for_status().json()
    if report["run_id"] != run_id:
        raise RuntimeError("Report did not match the benchmark run.")
    return {
        "requested_vus": requested,
        "trial": trial,
        "observation_seconds": round(elapsed, 2),
        "stopped_early": stopped_early,
        "report_peak_vus": report["peak_vus"],
        "sampled_peak_vus": peak_vus,
        "average_rps": report["avg_rps"],
        "peak_rps": report["peak_rps"],
        "p95_ms": report["p95_ms"],
        "error_pct": report["error_pct"],
        "requests": report["total_requests"],
        "verdict": report["verdict"],
        "stop_http_ms": stop_ms,
        "target_peak_established_tcp": peak_connections,
        "peak_rss_mib": {name: round(value, 1) for name, value in peak_rss.items()},
        "peak_cpu_pct_of_one_core": {name: round(value, 1) for name, value in peak_cpu.items()},
    }


def benchmark():
    runner_port, target_port = loopback_ports()
    target_origin = f"http://127.0.0.1:{target_port}"
    target_url = target_origin + "/api/sandbox/target"
    runner_url = f"http://127.0.0.1:{runner_port}"
    with TemporaryDirectory(prefix="pusher-local-capacity-", ignore_cleanup_errors=True) as directory:
        directory = Path(directory)
        with service(target_port, directory / "target.sqlite", target_origin) as target:
            with service(runner_port, directory / "runner.sqlite", target_origin) as runner:
                with httpx.Client(base_url=runner_url, trust_env=False, timeout=5) as client:
                    assert client.get("/api/session").raise_for_status().json()["offline"]
                    limits = client.get("/api/system/limits").raise_for_status().json()
                    assert client.post("/api/target/verify", json={
                        "target_url": target_url, "is_sandbox": True,
                    }).raise_for_status().json()["is_verified"]
                    max_vus = min(limits["max_worker_vus"], int(
                        (BUDGET_MB - limits["base_engine_ram_mb"]) / limits["ram_per_vu_mb"]
                    ))
                    emit({
                        "platform": platform.system(), "logical_cpus": psutil.cpu_count(),
                        "python": platform.python_version(), "host_ram_mib": limits["total_system_ram_mb"],
                        "ram_budget_mb": BUDGET_MB, "worker_limit": limits["max_worker_vus"],
                        "observation_seconds": WINDOW_SECONDS,
                    })
                    for requested in (10, 25, 50):
                        if BUDGET_MB > limits["max_safe_ram_mb"] or requested > max_vus:
                            emit({"requested_vus": requested, "skipped": "Above the published runner limits."})
                            continue
                        for trial in range(1, 4):
                            emit(measure(client, target_url, {"runner": runner, "target": target}, target_port, requested, trial))
