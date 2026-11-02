"""Drive the repaired sentinel-ctl to build every delivered artifact.

Usage: python3 build_artifacts.py [--data /app/data] [--tool /app/tool] [--out /app/out] [--work /app/work]
The resolve scratch files go to --work so that --out holds only the seven artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def dump(data):
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--tool", default="/app/tool")
    ap.add_argument("--out", default="/app/out")
    ap.add_argument("--work", default="/app/work")
    a = ap.parse_args()
    data, tool, out, work = Path(a.data), Path(a.tool), Path(a.out), Path(a.work)
    out.mkdir(parents=True, exist_ok=True)
    resolve_dir = work / "resolve"
    resolve_dir.mkdir(parents=True, exist_ok=True)
    cli = str(tool / "cli.py")
    py = sys.executable

    failures = []

    def run(args, log):
        argv = [py, cli] + args
        proc = subprocess.run(argv, capture_output=True, text=True)
        entry = {"argv": argv, "returncode": proc.returncode, "stdout": proc.stdout}
        if log is not None:
            log.append(entry)
        if proc.returncode != 0:
            failures.append({"argv": argv, "returncode": proc.returncode, "stderr": proc.stderr})
            sys.stderr.write(proc.stderr)
            raise SystemExit("command failed: " + " ".join(argv))
        return proc.stdout

    schema_path = str(data / "config_schema.json")
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    config_keys = list(schema["required_keys"])

    # config.json
    commands = []
    run(["resolve", "--data-dir", str(data), "--out", str(resolve_dir)], commands)
    resolved = json.loads((resolve_dir / "policy_resolved.json").read_text(encoding="utf-8"))
    curve = json.loads((resolve_dir / "threshold_curve.json").read_text(encoding="utf-8"))
    trace = json.loads((resolve_dir / "dependency_trace.json").read_text(encoding="utf-8"))
    config_path = out / "config.json"
    run(["init", "--schema", schema_path, "--out", str(config_path)], commands)
    for key in config_keys:
        run(["set", "--config", str(config_path), "--key", key, "--value", str(resolved[key])], commands)
    run(["validate", "--schema", schema_path, "--config", str(config_path)], commands)

    # profiles
    env = json.loads((data / "env_overrides.json").read_text(encoding="utf-8"))
    rules = json.loads((data / "validation_rules.json").read_text(encoding="utf-8"))
    profiles = list(rules.get("profiles", ["dev", "prod"]))
    trailer = resolved["trailer"]
    profile_docs = {}
    for name in profiles:
        sample = json.loads((data / ("sample_config_" + name + ".json")).read_text(encoding="utf-8"))
        values = {
            "checksum": resolved["checksum"],
            "container": resolved["container"],
            "producer": resolved["producer"],
            "mode": env[name]["mode"],
            "profile": schema["profile"] + "-" + name,
            "max_records": resolved["max_records"] + int(sample["max_records_delta"]),
            "retry_limit": resolved["retry_limit"] + int(env[name]["retry_limit_delta"]),
            "timeout_ms": resolved["timeout_ms"] + int(env[name]["timeout_ms_delta"]),
            "trailer": trailer + ":" + name,
        }
        ppath = out / ("profile_" + name + ".json")
        run(["init", "--schema", schema_path, "--out", str(ppath)], None)
        for key in sorted(values):
            run(["set", "--config", str(ppath), "--key", key, "--value", str(values[key])], None)
        run(["validate", "--schema", schema_path, "--config", str(ppath)], None)
        profile_docs[name] = json.loads(ppath.read_text(encoding="utf-8"))

    # report.json
    digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    run(["export-report", "--config", str(config_path), "--out", str(out / "report.json"),
         "--digest", digest, "--commands", json.dumps(commands, sort_keys=True)], None)

    # tool.zip: same member layout as the source archive, byte-deterministic
    with zipfile.ZipFile(data / "tool.zip") as src:
        members = [info.filename for info in src.infolist()]
    with zipfile.ZipFile(out / "tool.zip", "w") as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, (tool / name).read_bytes())

    # validation_report.json
    required = list(rules["required_artifacts"])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_config = {k: resolved[k] for k in resolved if k not in ("param_key", "tenant", "effective_version", "risk_threshold")}
    checks = {
        "all_artifacts_present": False,
        "config_matches_policy": config == expected_config,
        "config_scalar_flat": all(not isinstance(v, (dict, list)) for v in config.values()),
        "command_failures": failures,
        "required_artifacts": required,
        "profiles": {name: {"trailer": profile_docs[name]["trailer"]} for name in profiles},
    }
    summary = {
        "artifact_count": len(required),
        "artifacts": required,
        "profiles": profiles,
        "format_tag": schema["profile"],
        "trailer": trailer,
        "input_count": 0,
        "inputs": [],
    }
    inputs = sorted(p.name for p in data.iterdir() if p.is_file())
    summary["inputs"] = inputs
    summary["input_count"] = len(inputs)
    (out / "summary.json").write_text(dump(summary), encoding="utf-8")
    report_doc = {
        "ok": False,
        "checks": checks,
        "policy_resolved": resolved,
        "threshold_curve": curve,
        "dependency_trace": trace,
    }
    (out / "validation_report.json").write_text(dump(report_doc), encoding="utf-8")
    checks["all_artifacts_present"] = all((out / name).is_file() for name in required)
    report_doc["ok"] = (checks["all_artifacts_present"] and checks["config_matches_policy"]
                        and checks["config_scalar_flat"] and not failures)
    (out / "validation_report.json").write_text(dump(report_doc), encoding="utf-8")
    print(json.dumps({"ok": report_doc["ok"], "config_sha256": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
