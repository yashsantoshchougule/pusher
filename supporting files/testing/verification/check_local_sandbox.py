"""Exercise the offline API over loopback using a disposable SQLite database."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import httpx
import psutil
import uvicorn


async def measure_sandbox(client, target, server):
    process = psutil.Process()
    for requested_vus in (1, 5, 10):
        started = (await client.post("/api/load/start", json={
            "target_url": target, "is_sandbox": True, "traffic_mode": "steady_crowd",
            "target_vus": requested_vus, "duration_sec": 8, "cache_bust": False,
        })).raise_for_status().json()
        run_id = started["run_id"]
        samples = []
        try:
            for _ in range(8):
                await asyncio.sleep(0.3)
                status = (await client.get("/api/load/status")).raise_for_status().json()
                assert status["run_id"] == run_id and status["is_running"]
                rss = process.memory_info().rss / (1024 * 1024)
                connections = len(server.server_state.connections)
                samples.append((status["active_vus"], rss, connections))
        finally:
            stop_started = perf_counter()
            response = await client.post("/api/load/stop", json={"run_id": run_id})
            stop_ms = (perf_counter() - stop_started) * 1000
            stopped = response.raise_for_status().json()["snapshot"]
            assert stopped["run_id"] == run_id and not stopped["is_running"]
        report = (await client.get(f"/api/reports/{run_id}/export")).raise_for_status().json()
        assert report["verdict"] == "MANUAL_ABORT"
        assert report["peak_vus"] == requested_vus and report["status_2xx"] > 0
        print(json.dumps({
            "requested_vus": requested_vus,
            "peak_sampled_vus": max(sample[0] for sample in samples),
            "combined_peak_sampled_rss_mib": round(max(sample[1] for sample in samples), 1),
            "peak_sandbox_tcp_connections_including_control": max(sample[2] for sample in samples),
            "report_peak_rps": report["peak_rps"],
            "total_requests": report["total_requests"],
            "stop_http_ms": round(stop_ms, 1),
        }))


async def check_sandbox(measure=False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    with TemporaryDirectory(prefix="pusher-sandbox-check-", ignore_cleanup_errors=True) as directory:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            os.environ.update(
                PUSHER_MODE="local_dev", PUSHER_OFFLINE_DEV="true", HOST="127.0.0.1",
                PORT=str(port), PUSHER_DB_PATH=str(Path(directory) / "smoke.sqlite"),
            )
            server = uvicorn.Server(uvicorn.Config("backend.main:app", port=port, lifespan="off", log_level="warning"))
            service = asyncio.create_task(server.serve(sockets=[listener]))
            try:
                async with asyncio.timeout(10):
                    while not server.started:
                        if service.done():
                            await service
                            raise RuntimeError("The sandbox server stopped before it started.")
                        await asyncio.sleep(0.05)
                base = f"http://127.0.0.1:{port}"
                async with httpx.AsyncClient(base_url=base, trust_env=False) as client:
                    session = (await client.get("/api/session")).raise_for_status().json()
                    assert session["offline"]
                    target = base + "/api/sandbox/target"
                    verified = (await client.post("/api/target/verify", json={
                        "target_url": target, "is_sandbox": True,
                    })).raise_for_status().json()
                    assert verified["is_verified"]
                    preset = (await client.get("/api/journey/sandbox-defaults")).raise_for_status().json()["steps"]

                    saved = (await client.post("/api/journey/save", json={
                        "steps": preset, "use_journey": True,
                    })).raise_for_status().json()
                    assert saved["use_journey"]
                    assert saved["steps"][0]["body"] is None and saved["steps"][0]["requires_body"]
                    assert (await client.post("/api/journey/dry-run", json={})).status_code == 422
                    runtime_steps = [
                        {**persisted, "headers": original["headers"], "body": original["body"]}
                        for persisted, original in zip(saved["steps"], preset, strict=True)
                    ]
                    journey = (await client.post("/api/journey/dry-run", json={
                        "steps": runtime_steps,
                    })).raise_for_status().json()
                    assert journey["all_passed"] and len(journey["steps"]) == 3
                    started = (await client.post("/api/load/start", json={
                        "target_url": target, "is_sandbox": True, "traffic_mode": "steady_crowd",
                        "target_vus": 1, "duration_sec": 1,
                        "use_journey": True, "journey_steps": runtime_steps,
                    })).raise_for_status().json()
                    async with asyncio.timeout(5):
                        while (await client.get("/api/load/status")).raise_for_status().json()["is_running"]:
                            await asyncio.sleep(0.05)
                    history = (await client.get("/api/history")).raise_for_status().json()
                    assert history["runs"][0]["run_id"] == started["run_id"]
                    assert history["runs"][0]["total_requests"] > 0
                    export = (await client.get(
                        f"/api/reports/{started['run_id']}/export"
                    )).raise_for_status().json()
                    assert export["run_id"] == started["run_id"]
                    assert export["verdict"] == "PASSED"
                    assert export["peak_vus"] == 1
                    assert len(export["step_metrics"]) == 3
                    assert all(step["passed"] > 0 for step in export["step_metrics"])
                    if measure:
                        await measure_sandbox(client, target, server)
            finally:
                server.should_exit = True
                await asyncio.wait_for(service, timeout=10)
    print("Offline sandbox smoke check passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--measure", action="store_true", help="Run bounded 1, 5, and 10 VU loopback measurements.")
    mode.add_argument("--benchmark", action="store_true", help="Run repeated 10, 25, and 50 VU measurements on a separate loopback target.")
    args = parser.parse_args()
    if args.benchmark:
        from check_local_capacity import benchmark

        benchmark()
    else:
        asyncio.run(check_sandbox(args.measure))
