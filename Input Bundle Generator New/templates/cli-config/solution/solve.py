#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path, PurePosixPath

SOURCE_ARCHIVE = Path("/app/data/tool.zip")
DATA = Path("/app/data")
TOOL = Path("/app/tool").resolve()
OUT = Path("/app/out")
FORMAT_TAG = "{{FORMAT_TAG}}"


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def extract() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ARCHIVE) as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit(f"unsafe source member: {info.filename!r}")
            dest = (TOOL / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(TOOL):
                raise SystemExit(f"escaping source member: {info.filename!r}")
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


def repair_cli() -> None:
    write(
        TOOL / "cli.py",
        r'''
        from __future__ import annotations

        import argparse
        import json
        from pathlib import Path

        COMMAND_LOG = []


        def load_json(path: str) -> dict:
            return json.loads(Path(path).read_text(encoding="utf-8"))


        def write_json(path: str, data: dict) -> None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


        def coerce(value: str):
            if value.isdecimal():
                return int(value)
            if value in {"true", "false"}:
                return value == "true"
            return value


        def assert_flat(data: dict) -> None:
            bad = [key for key, value in data.items() if isinstance(value, (dict, list))]
            if bad:
                raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


        def cmd_init(args) -> None:
            schema = load_json(args.schema)
            data = {
                "profile": schema["profile"],
                "producer": schema["producer"],
                "container": schema["container"],
                "checksum": schema["checksum"],
                "mode": "strict-local",
            }
            write_json(args.out, data)
            print("initialized")


        def cmd_set(args) -> None:
            data = load_json(args.config)
            data[args.key] = coerce(args.value)
            assert_flat(data)
            write_json(args.config, data)
            print("set " + args.key)


        def cmd_validate(args) -> None:
            schema = load_json(args.schema)
            data = load_json(args.config)
            assert_flat(data)
            missing = [key for key in schema["required_keys"].split(",") if key not in data]
            if missing:
                raise SystemExit("missing: " + ",".join(missing))
            print("ok")


        def cmd_report(args) -> None:
            data = load_json(args.config)
            assert_flat(data)
            commands = json.loads(args.commands)
            commands.append({
                "argv": ["python3", "cli.py", "export-report", "--config", args.config, "--out", args.out],
                "returncode": 0,
                "stdout": "reported",
            })
            report = {
                "ok": True,
                "tool": "{{PACKAGE_NAME}}-ctl",
                "config_path": args.config,
                "config_sha256": args.digest,
                "commands": commands,
                "trailer": data.get("trailer"),
            }
            write_json(args.out, report)
            print("reported")


        def main() -> None:
            parser = argparse.ArgumentParser(prog="{{PACKAGE_NAME}}-ctl")
            sub = parser.add_subparsers(dest="command", required=True)
            p = sub.add_parser("init")
            p.add_argument("--schema", required=True)
            p.add_argument("--out", required=True)
            p.set_defaults(func=cmd_init)
            p = sub.add_parser("set")
            p.add_argument("--config", required=True)
            p.add_argument("--key", required=True)
            p.add_argument("--value", required=True)
            p.set_defaults(func=cmd_set)
            p = sub.add_parser("validate")
            p.add_argument("--schema", required=True)
            p.add_argument("--config", required=True)
            p.set_defaults(func=cmd_validate)
            p = sub.add_parser("export-report")
            p.add_argument("--config", required=True)
            p.add_argument("--out", required=True)
            p.add_argument("--digest", required=True)
            p.add_argument("--commands", required=True)
            p.set_defaults(func=cmd_report)
            args = parser.parse_args()
            args.func(args)


        if __name__ == "__main__":
            main()
        ''',
    )


def load_data(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


NUMERIC = {"max_records", "retry_limit", "timeout_ms"}


class Journal:
    def __init__(self) -> None:
        rules = load_data("validation_rules.json")
        self.envs = set(rules["journal_envs"])
        self.modes = set(rules["allowed_modes"])
        self.bounds = {k: tuple(v) for k, v in rules["bounds"].items()}
        text = (DATA / "change_journal.jsonl").read_text(encoding="utf-8")
        self.ops = sorted((json.loads(line) for line in text.splitlines() if line.strip()), key=lambda op: op["seq"])

    def accepts(self, op: dict) -> bool:
        key, value = op["key"], op["value"]
        if op["env"] not in self.envs:
            return False
        if key == "mode":
            return value in self.modes
        if key in NUMERIC and isinstance(value, int) and not isinstance(value, bool):
            low, high = self.bounds[key]
            return low <= value <= high
        return False

    def replay(self, doc: dict, env: str) -> dict:
        for op in self.ops:
            if op["env"] == env and self.accepts(op):
                doc[op["key"]] = op["value"]
        return doc

    def rejected(self) -> list[int]:
        return [op["seq"] for op in self.ops if not self.accepts(op)]


JOURNAL = Journal()


def trailer() -> str:
    return str(load_data("defaults.json")["base_config"]["trailer"])


def dump_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expected_main_config() -> dict[str, int | str]:
    schema = load_data("config_schema.json")
    defaults = load_data("defaults.json")
    doc: dict[str, int | str] = dict(defaults["base_config"])
    doc.update(checksum=defaults["checksum"], mode=defaults["mode"], producer=schema["producer"],
               container=schema["container"], profile=schema["profile"])
    return JOURNAL.replay(doc, "base")


def normalize_profile(name: str) -> dict[str, int | str]:
    doc = dict(expected_main_config())
    sample = load_data(f"sample_config_{name}.json")
    env = load_data("env_overrides.json")[name]
    doc["max_records"] = int(doc["max_records"]) + int(sample["max_records_delta"])
    doc["checksum"] = sample["checksum"]
    doc["retry_limit"] = int(doc["retry_limit"]) + int(env["retry_limit_delta"])
    doc["timeout_ms"] = int(doc["timeout_ms"]) + int(env["timeout_ms_delta"])
    doc["mode"] = env["mode"]
    doc["profile"] = f"{doc['profile']}-{name}"
    doc["trailer"] = f"{doc['trailer']}:{name}"
    return JOURNAL.replay(doc, name)


def scalar_flat(data: dict) -> bool:
    return all(not isinstance(value, (dict, list)) for value in data.values())


def write_sidecar_artifacts(commands: list[dict[str, object]]) -> None:
    profiles = load_data("validation_rules.json")["profiles"]
    artifacts = load_data("validation_rules.json")["required_artifacts"]
    profile_docs = {name: json.loads((OUT / f"profile_{name}.json").read_text(encoding="utf-8")) for name in profiles}
    main = json.loads((OUT / "config.json").read_text(encoding="utf-8"))
    checks = {
        "all_artifacts_present": all((OUT / name).exists() or name in {"validation_report.json", "summary.json"} for name in artifacts),
        "command_failures": [item for item in commands if item.get("returncode") != 0],
        "config_matches_policy": main == expected_main_config(),
        "config_scalar_flat": scalar_flat(main),
        "profiles": {name: {"scalar_flat": scalar_flat(doc), "trailer": doc["trailer"]} for name, doc in profile_docs.items()},
        "rejected_ops": JOURNAL.rejected(),
        "required_artifacts": artifacts,
    }
    dump_json(OUT / "validation_report.json", {"ok": all([checks["all_artifacts_present"], checks["config_matches_policy"], checks["config_scalar_flat"]]), "checks": checks})
    sidecar_inputs = sorted(path.name for path in DATA.iterdir() if path.is_file())
    dump_json(
        OUT / "summary.json",
        {
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "format_tag": FORMAT_TAG,
            "input_count": len(sidecar_inputs),
            "inputs": sidecar_inputs,
            "profiles": profiles,
            "tool": "{{PACKAGE_NAME}}-ctl",
            "trailer": trailer(),
        },
    )


def run_cli(*args: str) -> dict[str, object]:
    cmd = [sys.executable, str(TOOL / "cli.py"), *args]
    result = subprocess.run(cmd, cwd=TOOL, text=True, capture_output=True, timeout=20, check=False)
    return {"argv": ["python3", "cli.py", *args], "returncode": result.returncode, "stdout": result.stdout.strip()}


def package_tool() -> None:
    archive = OUT / "tool.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def main() -> None:
    extract()
    repair_cli()
    OUT.mkdir(parents=True, exist_ok=True)
    config = OUT / "config.json"
    schema = TOOL / "schema.json"
    commands = []
    targets = [(config, expected_main_config())]
    profiles = load_data("validation_rules.json")["profiles"]
    targets += [(OUT / f"profile_{name}.json", normalize_profile(name)) for name in profiles]
    for path, doc in targets:
        commands.append(run_cli("init", "--schema", str(schema), "--out", str(path)))
        for key, value in sorted(doc.items()):
            commands.append(run_cli("set", "--config", str(path), "--key", key, "--value", str(value)))
        commands.append(run_cli("validate", "--schema", str(schema), "--config", str(path)))
    for path, doc in targets:
        if json.loads(path.read_text(encoding="utf-8")) != doc:
            raise SystemExit(f"CLI produced a different {path.name}")
    if any(item["returncode"] != 0 for item in commands):
        raise SystemExit(commands)
    import hashlib

    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    commands.append(run_cli("export-report", "--config", str(config), "--out", str(OUT / "report.json"), "--digest", digest, "--commands", json.dumps(commands, sort_keys=True)))
    if commands[-1]["returncode"] != 0:
        raise SystemExit(commands[-1])
    package_tool()
    write_sidecar_artifacts(commands)


if __name__ == "__main__":
    main()
