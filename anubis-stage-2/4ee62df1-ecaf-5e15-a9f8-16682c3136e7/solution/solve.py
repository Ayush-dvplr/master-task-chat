#!/usr/bin/env python3
"""Reference oracle for 4ee62df1-ecaf-5e15-a9f8-16682c3136e7.

Extracts the shipped tool, replaces its broken cli.py with a repaired CLI that
implements every subcommand from the written contract, and produces the
delivered artifacts by driving that CLI. Standard library only, offline and
deterministic.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

DATA = Path("/app/data")
OUT = Path("/app/out")
TOOL = Path("/app/tool")
WORK = Path("/tmp/oracle_work")
ZONES = ("core", "edge", "dmz", "mgmt")
ARTIFACTS = ["config.json", "report.json", "tool.zip", "aggregates.json", "aggregates.csv",
             "aggregates.tsv", "aggregates.xml", "aggregates.ini", "aggregates.env",
             "aggregates.md", "aggregates.txt", "validation_report.json", "summary.json",
             "profile_core.json", "profile_edge.json", "profile_dmz.json", "profile_mgmt.json",
             "rejected_ops.json", "zone_totals.json", "corpus_index.json", "posture.json",
             "manifest.sha256"]
NOT_IN_MANIFEST = {"tool.zip", "report.json", "manifest.sha256"}

CLI_SOURCE = r'''#!/usr/bin/env python3
"""sealb-ctl: offline security policy compiler.

The configuration must be flat: a single JSON object of scalar values only.
Nested dicts or lists violate the schema. Every derived value is computed from
the files in the data directory; nothing is fixed by the tool.
"""
import argparse
import configparser
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ZONES = ("core", "edge", "dmz", "mgmt")
SPINE_KEYS = ("max_sessions", "retry_budget", "handshake_timeout_ms", "rekey_interval_s")
OPERATORS = ("max", "min", "sum", "count", "first", "last")
SEPARATORS = {"csv": ",", "tsv": "\t", "psv": "|", "scsv": ";", "colon": ":",
              "caret": "^", "at": "@", "bang": "!", "tilde": "~", "dcolon": "::"}
HEADER = ("zone", "value", "flag")
MIRRORS = ("csv", "tsv", "xml", "ini", "env", "md", "txt")


def canonical_text(obj):
    return json.dumps(obj, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False) + "\n"


def write_canonical(obj, path):
    Path(path).write_text(canonical_text(obj), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_int(text):
    """Return the integer only when str(int(text)) reproduces the exact field text."""
    if type(text) is not str:
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number if str(number) == text else None


def json_field(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def comment_or_blank(line):
    head = line.strip()
    return not head or head.startswith("#")


def parse_rows(fmt, text):
    """Split one corpus into (zone, value, flag) field texts, byte for byte."""
    rows = []
    if fmt in SEPARATORS:
        for line in text.splitlines():
            if comment_or_blank(line):
                continue
            fields = tuple(line.split(SEPARATORS[fmt]))
            if len(fields) == 3 and fields != HEADER:
                rows.append(fields)
    elif fmt == "ssv":
        for line in text.splitlines():
            if comment_or_blank(line):
                continue
            fields = tuple(part for part in line.split(" ") if part)
            if len(fields) == 3 and fields != HEADER:
                rows.append(fields)
    elif fmt in ("jsonarr", "jsonl"):
        records = []
        if fmt == "jsonarr":
            try:
                blob = json.loads(text)
            except ValueError:
                blob = []
            records = blob if isinstance(blob, list) else []
        else:
            for line in text.splitlines():
                head = line.strip()
                if head and not head.startswith("//"):
                    try:
                        records.append(json.loads(head))
                    except ValueError:
                        continue
        for record in records:
            if isinstance(record, dict):
                rows.append(tuple(json_field(record.get(k)) for k in HEADER))
    elif fmt in ("xmlflat", "xmlnest"):
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return rows
        for row in root.findall("row"):
            if fmt == "xmlflat":
                rows.append(tuple(row.get(k, "") for k in HEADER))
            else:
                rows.append(tuple(row.findtext(k, "") for k in HEADER))
    elif fmt == "ini":
        parser = configparser.ConfigParser()
        try:
            parser.read_string(text)
        except configparser.Error:
            return rows
        for section in parser.sections():
            rows.append(tuple(parser[section].get(k, "") for k in HEADER))
    elif fmt == "fixed":
        for line in text.splitlines():
            if comment_or_blank(line) or line[:10].strip() == "zone":
                continue
            rows.append((line[0:10].strip(), line[10:30].strip(), line[30:].strip()))
    elif fmt == "mdtable":
        for line in text.splitlines():
            body = line.strip()
            if not body.startswith("|"):
                continue
            cells = tuple(cell.strip() for cell in body.strip("|").split("|"))
            if len(cells) != 3 or cells[0] == "zone" or set(cells[0]) <= set("-: "):
                continue
            rows.append(cells)
    elif fmt == "kvline":
        for line in text.splitlines():
            if comment_or_blank(line):
                continue
            pairs = {}
            for token in line.split():
                if "=" in token:
                    name, _, value = token.partition("=")
                    pairs[name] = value
            if all(k in pairs for k in HEADER):
                rows.append(tuple(pairs[k] for k in HEADER))
    elif fmt == "props":
        groups, order = {}, []
        for line in text.splitlines():
            entry = line.lstrip()
            if not entry.strip() or entry.startswith("#") or "=" not in entry:
                continue
            name, _, value = entry.partition("=")
            if "." not in name:
                continue
            group, _, field = name.partition(".")
            if group not in groups:
                groups[group] = {}
                order.append(group)
            groups[group][field] = value
        rows = [tuple(groups[g].get(k, "") for k in HEADER) for g in order]
    return rows


def counted_value(row, low, high):
    zone, value, flag = row
    if zone not in ZONES or flag != "active":
        return None
    number = canonical_int(value)
    if number is None or not low <= number <= high:
        return None
    return number


def reduce_values(op, values):
    if op == "count":
        return len(values)
    if not values:
        return 0
    if op == "first":
        return values[0]
    if op == "last":
        return values[-1]
    return {"max": max, "min": min, "sum": sum}[op](values)


def render_mirror(kind, aggregates):
    items = sorted(aggregates.items())
    if kind == "csv":
        return "corpus,value\n" + "".join(f"{k},{v}\n" for k, v in items)
    if kind == "tsv":
        return "corpus\tvalue\n" + "".join(f"{k}\t{v}\n" for k, v in items)
    if kind == "ini":
        return "[aggregates]\n" + "".join(f"{k} = {v}\n" for k, v in items)
    if kind == "env":
        return "".join(f"{k.upper()}={v}\n" for k, v in items)
    if kind == "md":
        return "| corpus | value |\n| --- | --- |\n" + "".join(f"| {k} | {v} |\n" for k, v in items)
    if kind == "txt":
        return "".join(f"{k} {v}\n" for k, v in items)
    root = ET.Element("aggregates")
    for k, v in items:
        ET.SubElement(root, "corpus", {"name": k, "value": str(v)})
    return ET.tostring(root, encoding="unicode") + "\n"


class Pipeline:
    """Journal replay and corpus reduction over one data directory."""

    def __init__(self, data, out):
        self.data = Path(data)
        self.out = Path(out)
        self.rules = read_json(self.data / "validation_rules.json")
        self.defaults = read_json(self.data / "defaults.json")
        self.schema = read_json(self.data / "config_schema.json")
        self.overrides = read_json(self.data / "env_overrides.json")
        lines = (self.data / "change_journal.jsonl").read_text(encoding="utf-8").splitlines()
        self.journal = sorted((json.loads(line) for line in lines if line.strip()), key=lambda op: op["seq"])
        self._spine = None
        self._zones = {}

    def seed(self):
        state = {"profile": self.schema["profile"], "producer": self.schema["producer"],
                 "container": self.schema["container"], "checksum": self.defaults["checksum"],
                 "mode": self.defaults["mode"]}
        state.update(self.defaults["base_config"])
        return state

    def is_valid(self, op, state):
        if op.get("env") not in self.rules["journal_envs"]:
            return False
        kind, key, value = op.get("op"), op.get("key"), op.get("value")
        if key not in SPINE_KEYS and key != "mode":
            return False
        if kind == "unset":
            return True
        if kind == "touch":
            if key in SPINE_KEYS and type(value) is not int:
                return False
            return value == state.get(key)
        if kind != "set":
            return False
        if key == "mode":
            return isinstance(value, str) and value in self.rules["allowed_modes"]
        if type(value) is not int:
            return False
        low, high = self.rules["bounds"][key]
        if not low <= value <= high:
            return False
        if key == "max_sessions":
            rekey, handshake = state.get("rekey_interval_s"), state.get("handshake_timeout_ms")
            if type(rekey) is not int or type(handshake) is not int or handshake <= 0:
                return False
            return value <= rekey // handshake
        return True

    def replay(self, env, start):
        state, rejected = dict(start), []
        for op in self.journal:
            if op.get("env") != env:
                if op.get("env") not in self.rules["journal_envs"]:
                    rejected.append(op["seq"])
                continue
            if not self.is_valid(op, state):
                rejected.append(op["seq"])
            elif op["op"] == "unset":
                key = op["key"]
                state[key] = self.defaults["base_config"][key] if key in SPINE_KEYS else self.defaults["mode"]
            elif op["op"] == "set":
                state[op["key"]] = op["value"]
        return state, rejected

    def spine(self):
        if self._spine is None:
            self._spine = self.replay("base", self.seed())
        return self._spine

    def zone(self, zone):
        if zone not in self._zones:
            state = dict(self.spine()[0])
            delta = self.overrides[zone]
            for key in ("retry_budget", "handshake_timeout_ms", "rekey_interval_s"):
                state[key] += int(delta[f"{key}_delta"])
            state["mode"] = delta["mode"]
            state["profile"] = f"{state['profile']}-{zone}"
            self._zones[zone] = self.replay(zone, state)
        return self._zones[zone]

    def rejected(self):
        seqs = set(self.spine()[1])
        for zone in ZONES:
            seqs.update(self.zone(zone)[1])
        return sorted(seqs)

    def touch_rejected(self):
        kinds = {op["seq"]: op.get("op") for op in self.journal}
        return sum(1 for seq in self.rejected() if kinds.get(seq) == "touch")

    def policy(self, env):
        if env == "base":
            return dict(self.spine()[0])
        if env not in ZONES:
            raise ValueError(f"unknown env {env!r}")
        state = dict(self.zone(env)[0])
        digest = hashlib.sha256((self.out / "config.json").read_bytes()).hexdigest()
        state["trailer"] = f"{state['trailer']}:{env}:{digest[:8]}"
        return state

    def shift(self):
        rekey = read_json(self.out / "config.json")["rekey_interval_s"]
        archive = int(hashlib.sha256((self.out / "tool.zip").read_bytes()).hexdigest()[:16], 16)
        return rekey % 97 + len(self.rejected()) % 31 + archive % 53

    def corpora(self):
        bounds = self.rules["corpus_bounds"]
        table = []
        for line in (self.data / "config_contract.md").read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) != 5 or cells[2] not in OPERATORS or "." not in cells[0]:
                continue
            name = cells[0].split(".", 1)[0]
            low, high = bounds[name]
            if (int(cells[3]), int(cells[4])) != (low, high):
                raise ValueError(f"corpus table and validation_rules disagree on {name}")
            table.append({"name": name, "file": cells[0], "format": cells[1], "op": cells[2],
                          "lo": low, "hi": high})
        return sorted(table, key=lambda spec: spec["name"])

    def reduce(self, spec, shift):
        text = (self.data / spec["file"]).read_text(encoding="utf-8")
        counted = []
        for row in parse_rows(spec["format"], text):
            number = counted_value(row, spec["lo"], spec["hi"] + shift)
            if number is not None:
                counted.append((row[0], number))
        return reduce_values(spec["op"], [n for _, n in counted]), counted


def schema_required_keys(schema):
    keys = schema.get("required_keys", [])
    if isinstance(keys, str):
        return [k.strip() for k in keys.split(",") if k.strip()]
    return list(keys)


def cmd_init(args):
    schema = read_json(args.schema)
    write_canonical({k: schema[k] for k in ("profile", "producer", "container")}, args.out)
    print(f"init {args.out}")
    return 0


def cmd_set(args):
    config = read_json(args.config)
    number = canonical_int(args.value)
    config[args.key] = args.value if number is None else number
    write_canonical(config, args.config)
    print(f"set {args.key}={args.value}")
    return 0


def cmd_validate(args):
    config = read_json(args.config)
    if not isinstance(config, dict):
        print("FAIL the configuration must be flat: top level is not an object", file=sys.stderr)
        return 2
    for key in schema_required_keys(read_json(args.schema)):
        if key not in config:
            print(f"FAIL missing key {key}", file=sys.stderr)
            return 2
    for key, value in config.items():
        if isinstance(value, (dict, list)):
            print(f"FAIL nested {key}: the configuration must be flat", file=sys.stderr)
            return 2
    print("ok")
    return 0


def cmd_plan(args):
    try:
        policy = Pipeline(args.data, args.out).policy(args.env)
    except ValueError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(canonical_text(policy))
    return 0


def cmd_compile(args):
    pipe = Pipeline(args.data, args.out)
    shift = pipe.shift()
    aggregates, zone_totals, index = {}, {zone: 0 for zone in ZONES}, []
    for spec in pipe.corpora():
        value, counted = pipe.reduce(spec, shift)
        aggregates[spec["name"]] = value
        for zone, _ in counted:
            zone_totals[zone] += 1
        index.append({"name": spec["name"], "format": spec["format"], "op": spec["op"],
                      "lo": spec["lo"], "hi": spec["hi"], "eligible_rows": len(counted), "value": value})
    out = Path(args.out)
    write_canonical(aggregates, out / "aggregates.json")
    for kind in MIRRORS:
        (out / f"aggregates.{kind}").write_text(render_mirror(kind, aggregates), encoding="utf-8")
    write_canonical(zone_totals, out / "zone_totals.json")
    write_canonical({"count": len(index), "corpora": index}, out / "corpus_index.json")
    print(f"compile corpora={len(index)} shift={shift}")
    return 0


def cmd_aggregate(args):
    pipe = Pipeline(args.data, args.out)
    spec = next((s for s in pipe.corpora() if s["name"] == args.corpus), None)
    if spec is None:
        print(f"FAIL unknown corpus {args.corpus}", file=sys.stderr)
        return 2
    print(pipe.reduce(spec, pipe.shift())[0])
    return 0


def cmd_report(args):
    raw = Path(args.config).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if args.digest and args.digest != digest:
        print("FAIL --digest does not match the config bytes", file=sys.stderr)
        return 2
    commands = read_json(args.commands) if args.commands else []
    commands.append({"argv": ["sealb-ctl", *args.argv], "returncode": 0, "stdout": "export-report ok"})
    report = {"ok": all(c.get("returncode") == 0 for c in commands), "tool": "sealb-ctl",
              "config_path": str(args.config), "config_sha256": digest,
              "trailer": json.loads(raw.decode("utf-8")).get("trailer", ""), "commands": commands}
    write_canonical(report, args.out)
    print("export-report ok")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="sealb-ctl")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("--schema", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(handler=cmd_init)
    p = sub.add_parser("set")
    p.add_argument("--config", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(handler=cmd_set)
    p = sub.add_parser("validate")
    p.add_argument("--schema", required=True)
    p.add_argument("--config", required=True)
    p.set_defaults(handler=cmd_validate)
    p = sub.add_parser("plan")
    p.add_argument("--data", default="/app/data")
    p.add_argument("--out", default="/app/out")
    p.add_argument("--env", required=True)
    p.set_defaults(handler=cmd_plan)
    p = sub.add_parser("compile")
    p.add_argument("--data", default="/app/data")
    p.add_argument("--out", default="/app/out")
    p.set_defaults(handler=cmd_compile)
    p = sub.add_parser("aggregate")
    p.add_argument("--corpus", required=True)
    p.add_argument("--data", default="/app/data")
    p.add_argument("--out", default="/app/out")
    p.set_defaults(handler=cmd_aggregate)
    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--commands")
    p.add_argument("--digest")
    p.set_defaults(handler=cmd_report)
    return parser


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    args.argv = argv
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
'''


def canonical_text(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, separators=(",", ": "), ensure_ascii=False) + "\n"


def write_json(obj, path: Path) -> None:
    path.write_text(canonical_text(obj), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_tool() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    root = TOOL.resolve()
    with zipfile.ZipFile(DATA / "tool.zip") as archive:
        for member in archive.infolist():
            target = (root / member.filename).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(f"refusing archive member outside {root}: {member.filename!r}")
            archive.extract(member, root)


def repair_cli() -> None:
    (TOOL / "cli.py").write_text(CLI_SOURCE, encoding="utf-8")


def pack_tool(dest: Path) -> None:
    members = sorted(p.relative_to(TOOL).as_posix() for p in TOOL.rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in members:
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (TOOL / name).read_bytes())


def run(commands: list | None, *argv) -> str:
    args = [str(a) for a in argv]
    done = subprocess.run([sys.executable, str(TOOL / "cli.py"), *args],
                          capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise SystemExit(f"sealb-ctl {' '.join(args)} failed: {done.stderr.strip()}")
    if commands is not None:
        commands.append({"argv": ["sealb-ctl", *args], "returncode": done.returncode,
                         "stdout": done.stdout.strip()})
    return done.stdout


def load_tool_module():
    spec = importlib.util.spec_from_file_location("sealb_cli", TOOL / "cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    extract_tool()
    repair_cli()

    commands: list[dict] = []
    config = OUT / "config.json"
    schema = TOOL / "schema.json"
    run(commands, "init", "--schema", schema, "--out", config)
    spine_text = run(commands, "plan", "--data", DATA, "--env", "base")
    spine = json.loads(spine_text)
    current = read_json(config)
    for key in sorted(spine):
        if current.get(key) != spine[key]:
            run(commands, "set", "--config", config, "--key", key, "--value", spine[key])
    run(commands, "validate", "--schema", schema, "--config", config)
    if config.read_text(encoding="utf-8") != spine_text:
        raise SystemExit("config.json built through init/set differs from the planned spine")

    pack_tool(OUT / "tool.zip")
    run(commands, "compile", "--data", DATA, "--out", OUT)
    aggregates = read_json(OUT / "aggregates.json")
    for name in sorted(aggregates):
        printed = run(commands, "aggregate", "--corpus", name, "--data", DATA, "--out", OUT)
        if int(printed) != aggregates[name]:
            raise SystemExit(f"aggregate {name} disagrees with compile")
    for zone in ZONES:
        text = run(commands, "plan", "--data", DATA, "--out", OUT, "--env", zone)
        (OUT / f"profile_{zone}.json").write_text(text, encoding="utf-8")

    pipeline = load_tool_module().Pipeline(DATA, OUT)
    rejected = pipeline.rejected()
    write_json({"rejected": rejected, "count": len(rejected)}, OUT / "rejected_ops.json")

    zip_sha = sha256_file(OUT / "tool.zip")
    best = max(aggregates.values())
    write_json({"aggregate_total": sum(aggregates.values()), "corpus_count": len(aggregates),
                "max_corpus": min(n for n, v in aggregates.items() if v == best), "max_value": best,
                "nonzero_corpora": sum(1 for v in aggregates.values() if v > 0),
                "zip_sha256": zip_sha, "config_sha256": sha256_file(config),
                "touch_rejected": pipeline.touch_rejected()}, OUT / "posture.json")

    inputs = sorted(p.name for p in DATA.iterdir() if p.is_file())
    write_json({"tool": "sealb-ctl", "profile_tag": spine["profile"], "trailer": spine["trailer"],
                "profiles": list(ZONES), "artifacts": ARTIFACTS, "artifact_count": len(ARTIFACTS),
                "inputs": inputs, "input_count": len(inputs), "corpus_count": len(aggregates),
                "aggregate_total": sum(aggregates.values())}, OUT / "summary.json")

    write_json(commands, WORK / "commands.json")
    run(None, "export-report", "--config", config, "--commands", WORK / "commands.json",
        "--digest", sha256_file(config), "--out", OUT / "report.json")
    recorded = read_json(OUT / "report.json")["commands"]

    profiles = {z: read_json(OUT / f"profile_{z}.json") for z in ZONES}
    delivered = read_json(config)
    pending = {"validation_report.json", "manifest.sha256"}
    write_json({"ok": True, "checks": {
        "all_artifacts_present": all((OUT / n).is_file() for n in ARTIFACTS if n not in pending),
        "config_matches_policy": delivered == spine,
        "config_scalar_flat": all(not isinstance(v, (dict, list)) for v in delivered.values()),
        "command_failures": [c for c in recorded if c.get("returncode") != 0],
        "rejected_ops": rejected,
        "profiles": {z: {"scalar_flat": all(not isinstance(v, (dict, list)) for v in p.values()),
                         "trailer": p["trailer"]} for z, p in profiles.items()},
        "corpus_count": len(aggregates),
        "aggregate_total": sum(aggregates.values()),
        "commands_through_cli": len(recorded),
        "zip_shift": int(zip_sha[:16], 16) % 53,
    }}, OUT / "validation_report.json")

    lines = [f"{sha256_file(OUT / n)}  {n}" for n in sorted(set(ARTIFACTS) - NOT_IN_MANIFEST)]
    (OUT / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
