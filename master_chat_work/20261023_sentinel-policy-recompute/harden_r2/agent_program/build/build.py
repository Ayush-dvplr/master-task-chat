#!/usr/bin/env python3
"""Drive sentinel-ctl and record the real CLI transcript."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

LAUNCHER = "/app/sentinel-ctl"
TOOL = "/app/tool"
DATA = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/app/out")
WORK = Path(sys.argv[3] if len(sys.argv) > 3 else "/app/work")
CONFIG = OUT / "config.json"

transcript = []


def run(*args, record=True):
    argv = ["sentinel-ctl", *args]
    proc = subprocess.run(
        argv, executable=LAUNCHER, capture_output=True, text=True, cwd="/app"
    )
    entry = {"argv": argv, "returncode": proc.returncode, "stdout": proc.stdout.strip()}
    if record:
        transcript.append(entry)
    if proc.returncode != 0:
        sys.exit("failed: " + " ".join(argv) + "\n" + proc.stdout + proc.stderr)
    return entry


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    resolved = json.loads(run("resolve", "--data-dir", DATA, "--out", str(WORK))["stdout"])
    schema = json.loads(Path(DATA, "config_schema.json").read_text())

    run("init", "--schema", DATA + "/config_schema.json", "--out", str(CONFIG))
    for key in schema["required_keys"]:
        run("set", "--config", str(CONFIG), "--key", key, "--value", str(resolved[key]))
    run("validate", "--schema", DATA + "/config_schema.json", "--config", str(CONFIG))

    for name in json.loads(Path(DATA, "validation_rules.json").read_text())["profiles"]:
        run(
            "profile", "--data-dir", DATA, "--config", str(CONFIG),
            "--name", name, "--out", str(OUT / ("profile_" + name + ".json")),
        )

    run("package", "--source", TOOL, "--out", str(OUT / "tool.zip"), record=False)
    digest = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    run(
        "export-report", "--config", str(CONFIG), "--out", str(OUT / "report.json"),
        "--digest", digest, "--commands", json.dumps(transcript, sort_keys=True),
        record=False,
    )
    run("export-summary", "--data-dir", DATA, "--out", str(OUT / "summary.json"), record=False)
    run(
        "export-validation", "--data-dir", DATA, "--resolved", str(WORK),
        "--config", str(CONFIG), "--artifacts-dir", str(OUT),
        "--out", str(OUT / "validation_report.json"),
        "--commands", json.dumps(transcript, sort_keys=True), record=False,
    )
    print("built " + digest)


if __name__ == "__main__":
    main()
