"""Drive the repaired sentinel-ctl CLI to deliver the seven /app/out artifacts.

Every artifact value originates from a sentinel-ctl run; this driver only
sequences the subcommands and records the real command transcript.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

TOOL = [sys.executable, "/app/tool/cli.py"]
SCHEMA = "/app/tool/schema.json"
DATA = "/app/data"
OUT = Path("/app/out")
BUILD = Path("/app/build")

commands = []


def run(args, record=True):
    proc = subprocess.run(TOOL + args, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit("sentinel-ctl failed: " + " ".join(args))
    if record:
        commands.append(
            {
                "argv": ["sentinel-ctl"] + args,
                "returncode": proc.returncode,
                "stdout": proc.stdout.strip(),
            }
        )
    return proc.stdout.strip()


OUT.mkdir(parents=True, exist_ok=True)
BUILD.mkdir(parents=True, exist_ok=True)

config_path = OUT / "config.json"
resolved_path = BUILD / "policy_resolved.json"
trace_path = BUILD / "dependency_trace.json"
curve_path = BUILD / "threshold_curve.json"
commands_path = BUILD / "commands.json"

# 1. reconstruct the authoritative policy from the reference material.
run(["resolve", "--data-dir", DATA, "--out", str(BUILD)])
resolved = json.loads(resolved_path.read_text(encoding="utf-8"))

# 2. identity fields, then each compiled scalar from the resolved policy.
run(["init", "--schema", SCHEMA, "--out", str(config_path)])
for key in ("max_records", "retry_limit", "timeout_ms", "trailer"):
    run(["set", "--config", str(config_path), "--key", key, "--value", str(resolved[key])])
run(["validate", "--schema", SCHEMA, "--config", str(config_path)])

# 3. environment profiles, through the same tool.
for name in ("dev", "prod"):
    run(
        [
            "profile",
            "--data-dir",
            DATA,
            "--resolved",
            str(resolved_path),
            "--name",
            name,
            "--out",
            str(OUT / ("profile_" + name + ".json")),
        ]
    )

# 4. byte-deterministic redelivery of the repaired tool.
run(["pack", "--src", "/app/tool", "--out", str(OUT / "tool.zip")])

# 5. run report over the real transcript and the delivered config bytes.
digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
commands_path.write_text(json.dumps(commands, sort_keys=True, indent=2) + "\n", encoding="utf-8")
run(
    [
        "export-report",
        "--config",
        str(config_path),
        "--out",
        str(OUT / "report.json"),
        "--digest",
        digest,
        "--commands",
        json.dumps(commands),
    ],
    record=False,
)

# 6. summary over the reference inputs and delivered artifacts.
run(
    [
        "summarize",
        "--data-dir",
        DATA,
        "--resolved",
        str(resolved_path),
        "--out",
        str(OUT / "summary.json"),
    ],
    record=False,
)

# 7. validation report last: it attests to every other artifact.
run(
    [
        "verify",
        "--data-dir",
        DATA,
        "--resolved",
        str(resolved_path),
        "--curve",
        str(curve_path),
        "--trace",
        str(trace_path),
        "--config",
        str(config_path),
        "--commands",
        str(commands_path),
        "--out-dir",
        str(OUT),
        "--out",
        str(OUT / "validation_report.json"),
    ],
    record=False,
)

print("config_sha256 " + digest)
print("commands recorded " + str(len(commands)))
