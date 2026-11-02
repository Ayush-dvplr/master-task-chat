#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DATA = Path("/app/data")
SERVICE = Path("/app/service")
OUT = Path("/app/out")
BASE = "http://127.0.0.1:8765"
ARTIFACTS = [
    "/app/out/final_state.json",
    "/app/out/report.json",
    "/app/out/scenario_alpha.json",
    "/app/out/scenario_beta.json",
    "/app/out/scenario_mode.json",
    "/app/out/transcript_summary.json",
    "/app/out/summary.json",
]


def replay_plan() -> list[dict]:
    data = Path("/app/data")
    with open(data / "approvals.csv", newline="", encoding="utf-8") as fh:
        cleared = {row["approval_id"] for row in csv.DictReader(fh) if row["status"] == "approved"}
    channels = set(json.loads((data / "auth_policy.json").read_text(encoding="utf-8"))["allowed_channels"])
    log = [json.loads(line) for line in (data / "request_log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    done: set[str] = set()
    plan = []
    for req in sorted(log, key=lambda item: item["seq"]):
        if req["approval"] not in cleared or req["channel"] not in channels:
            continue
        if req["action"] not in ("add", "multiply", "set") or req["key"] not in ("alpha", "beta", "mode_code"):
            continue
        if not isinstance(req["amount"], int) or isinstance(req["amount"], bool) or req["idempotency_key"] in done:
            continue
        done.add(req["idempotency_key"])
        plan.append({k: req[k] for k in ("channel", "action", "key", "amount")})
    return plan


def extract() -> None:
    for name in ("simulator.py", "client.py"):
        if not (SERVICE / name).is_file():
            raise SystemExit(f"missing {SERVICE / name}")


def request_json(path: str, payload: dict | None = None) -> dict:
    if payload is None:
        with urllib.request.urlopen(BASE + path, timeout=5) as response:
            return json.loads(response.read().decode())
    data = json.dumps(payload).encode()
    request = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def seed_config() -> dict:
    return json.loads((DATA / "seed_config.json").read_text(encoding="utf-8"))


def trailer() -> str:
    return str(seed_config()["trailer"])


def hidden_amounts() -> dict[str, int]:
    config = seed_config()
    return {
        "alpha_bonus": int(config["alpha_bonus"]),
        "beta_bonus": int(config["beta_bonus"]),
    }


def run_cli(action: str, key: str, amount: int) -> dict:
    cmd = [sys.executable, str(SERVICE / "client.py"), "--base", BASE, action, key, str(amount)]
    result = subprocess.run(cmd, cwd=SERVICE, text=True, capture_output=True, timeout=10, check=False)
    return {"channel": "cli", "action": action, "key": key, "amount": amount, "returncode": result.returncode, "stdout": result.stdout.strip()}


def run_api(action: str, key: str, amount: int) -> dict:
    body = {"action": action, "key": key, "amount": amount}
    response = request_json("/apply", body)
    return {"channel": "api", "action": action, "key": key, "amount": amount, "returncode": 0, "response": response}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_channels(transcript: list[dict], key: str) -> list[str]:
    return sorted({row["channel"] for row in transcript if row.get("key") == key})


def scenario_payload(entry: dict, value: int, transcript: list[dict]) -> dict:
    key = entry["key"]
    return {
        "description": entry["description"],
        "key": key,
        "name": entry["name"],
        "operation_count": sum(1 for row in transcript if row.get("key") == key),
        "source_channels": source_channels(transcript, key),
        "trailer": trailer(),
        "value": value,
    }


def main() -> None:
    extract()
    OUT.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    state: dict | None = None
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SERVICE / "simulator.py"),
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ],
            cwd=SERVICE,
            start_new_session=True,
            text=True,
        )
        for _ in range(50):
            try:
                if request_json("/health").get("ok") is True:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise SystemExit("service did not become ready")
        transcript = []
        for op in replay_plan():
            if op["channel"] == "cli":
                transcript.append(run_cli(op["action"], op["key"], int(op["amount"])))
            else:
                transcript.append(run_api(op["action"], op["key"], int(op["amount"])))
        extras = hidden_amounts()
        transcript.append(run_cli("add", "alpha", extras["alpha_bonus"]))
        transcript.append(run_api("add", "beta", extras["beta_bonus"]))
        state = request_json("/state")
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
    if state is None:
        raise RuntimeError("service returned no final state")
    wanted = json.loads(Path("/app/data/expected_schema.json").read_text(encoding="utf-8"))["final_state_required"]
    final = {key: state[key] if key in state else seed_config()[key] for key in wanted}
    state_path = OUT / "final_state.json"
    write_json(state_path, final)
    digest = hashlib.sha256(state_path.read_bytes()).hexdigest()
    report = {"ok": True, "base_url": BASE, "state_sha256": digest, "interactions": transcript, "trailer": trailer()}
    write_json(OUT / "report.json", report)

    entries = json.loads(Path("/app/data/scenarios.json").read_text(encoding="utf-8"))
    scenarios = {
        f"scenario_{entry['name']}.json": scenario_payload(entry, int(state[entry["key"]]), transcript)
        for entry in entries
    }
    for filename, payload in scenarios.items():
        write_json(OUT / filename, payload)

    transcript_summary = {
        "all_returncodes_zero": all(row.get("returncode") == 0 for row in transcript),
        "channels": sorted({row["channel"] for row in transcript}),
        "operation_count": len(transcript),
        "signature": [f'{row["channel"]}:{row["action"]}:{row["key"]}' for row in transcript],
        "trailer": trailer(),
    }
    write_json(OUT / "transcript_summary.json", transcript_summary)

    summary = {
        "artifact_count": len(ARTIFACTS),
        "artifacts": ARTIFACTS,
        "inputs": sorted(p.name for p in Path("/app/data").iterdir() if p.is_file()),
        "scenario_files": sorted(scenarios),
        "state_sha256": digest,
        "trailer": trailer(),
    }
    write_json(OUT / "summary.json", summary)


if __name__ == "__main__":
    main()
