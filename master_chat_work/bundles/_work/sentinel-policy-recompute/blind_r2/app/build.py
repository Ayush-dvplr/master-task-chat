"""Drive the repaired sentinel-ctl to build every delivered artifact.

Usage: python3 build.py --data /app/data --tool /app/tool --out /app/out --scratch /app/build_scratch
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


def dump(data):
    return json.dumps(data, sort_keys=True, indent=2) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/app/data")
    ap.add_argument("--tool", default="/app/tool")
    ap.add_argument("--out", default="/app/out")
    ap.add_argument("--scratch", default="/app/build_scratch")
    ap.add_argument("--python", default="python3")
    args = ap.parse_args()

    data = Path(args.data)
    tool = Path(args.tool)
    out = Path(args.out)
    scratch = Path(args.scratch)
    out.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    cli = str(tool / "cli.py")
    schema_path = str(data / "config_schema.json")

    def run(*cli_args):
        argv = [args.python, cli, *cli_args]
        proc = subprocess.run(argv, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stderr)
        return {"argv": argv, "returncode": proc.returncode, "stdout": proc.stdout}

    config_cmds = []
    profile_cmds = []

    config_cmds.append(run("resolve", "--data-dir", str(data), "--out", str(scratch)))
    resolved = json.loads((scratch / "policy_resolved.json").read_text(encoding="utf-8"))
    trace = json.loads((scratch / "dependency_trace.json").read_text(encoding="utf-8"))
    curve = json.loads((scratch / "threshold_curve.json").read_text(encoding="utf-8"))

    schema = json.loads((data / "config_schema.json").read_text(encoding="utf-8"))
    required = schema["required_keys"]
    if isinstance(required, str):
        required = [k.strip() for k in required.split(",") if k.strip()]
    identity = ("profile", "producer", "container", "checksum")

    config_path = out / "config.json"
    config_cmds.append(run("init", "--schema", schema_path, "--out", str(config_path)))
    for key in required:
        if key in identity:
            continue
        config_cmds.append(run("set", "--config", str(config_path), "--key", key, "--value", str(resolved[key])))
    config_cmds.append(run("validate", "--schema", schema_path, "--config", str(config_path)))

    env = json.loads((data / "env_overrides.json").read_text(encoding="utf-8"))
    rules = json.loads((data / "validation_rules.json").read_text(encoding="utf-8"))
    profiles = list(rules.get("profiles", ["dev", "prod"]))
    artifacts = list(rules["required_artifacts"])
    format_tag = schema["profile"]
    trailer = resolved["trailer"]
    profile_values = {}
    for name in profiles:
        sample = json.loads((data / ("sample_config_%s.json" % name)).read_text(encoding="utf-8"))
        penv = env[name]
        values = {
            "profile": "%s-%s" % (format_tag, name),
            "mode": penv.get("mode", resolved["mode"]),
            "max_records": resolved["max_records"] + int(sample.get("max_records_delta", 0)),
            "retry_limit": resolved["retry_limit"] + int(penv.get("retry_limit_delta", 0)),
            "timeout_ms": resolved["timeout_ms"] + int(penv.get("timeout_ms_delta", 0)),
            "trailer": "%s:%s" % (trailer, name),
        }
        ppath = out / ("profile_%s.json" % name)
        profile_cmds.append(run("init", "--schema", schema_path, "--out", str(ppath)))
        for key in ("profile", "mode", "max_records", "retry_limit", "timeout_ms", "trailer"):
            profile_cmds.append(run("set", "--config", str(ppath), "--key", key, "--value", str(values[key])))
        profile_cmds.append(run("validate", "--schema", schema_path, "--config", str(ppath)))
        profile_values[name] = json.loads(ppath.read_text(encoding="utf-8"))

    # byte-deterministic tool archive, same member layout as data/tool.zip
    with zipfile.ZipFile(data / "tool.zip") as src:
        members = [(i.filename, i.compress_type) for i in src.infolist()]
    with zipfile.ZipFile(out / "tool.zip", "w") as dst:
        for name, ctype in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ctype
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            dst.writestr(info, (tool / name).read_bytes())

    config_bytes = config_path.read_bytes()
    digest = hashlib.sha256(config_bytes).hexdigest()
    report_cmd = run(
        "export-report",
        "--config", str(config_path),
        "--out", str(out / "report.json"),
        "--digest", digest,
        "--commands", json.dumps(config_cmds, sort_keys=True),
    )

    inputs = sorted(p.name for p in data.iterdir() if p.is_file())
    summary = {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "profiles": profiles,
        "format_tag": format_tag,
        "trailer": trailer,
        "input_count": len(inputs),
        "inputs": inputs,
    }
    (out / "summary.json").write_text(dump(summary), encoding="utf-8")

    config = json.loads(config_bytes)
    all_cmds = config_cmds + profile_cmds + [report_cmd]
    failures = [c["argv"] for c in all_cmds if c["returncode"] != 0]
    matches = set(config) == set(required) and all(config[k] == resolved[k] for k in required)
    flat = all(not isinstance(v, (dict, list)) for v in config.values())
    present = all((out / a).exists() for a in artifacts if a != "validation_report.json")
    checks = {
        "all_artifacts_present": present,
        "config_matches_policy": matches,
        "config_scalar_flat": flat,
        "command_failures": failures,
        "required_artifacts": artifacts,
        "profiles": {name: {"file": "profile_%s.json" % name, "trailer": profile_values[name]["trailer"]} for name in profiles},
    }
    ok = present and matches and flat and not failures
    report = {
        "ok": ok,
        "checks": checks,
        "policy_resolved": resolved,
        "threshold_curve": curve,
        "dependency_trace": trace,
    }
    (out / "validation_report.json").write_text(dump(report), encoding="utf-8")
    print(dump({"ok": ok, "failures": failures, "config": config}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
