#!/usr/bin/env python3
"""Reference solution: read the inputs byte by byte, run the broken tool to see how it
misbehaves, replace each faulty function with one that follows the contract in
/app/data/validation_rules.json, check the repair against the history file, and then
drive the repaired CLI to produce every declared artifact.

Most of the shipped faults exit 0 while writing the wrong document, so the diagnosis
step compares what the tool writes with what the contract asks for rather than waiting
for a traceback.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

DATA = Path("/app/data")
SOURCE_ARCHIVE = DATA / "tool.zip"
TOOL = Path("/app/tool").resolve()
OUT = Path("/app/out")
NUMERIC = ("max_records", "retry_limit", "timeout_ms")
REPAIRS: list[str] = []

sys.dont_write_bytecode = True


def first_occurrence(pairs: list[tuple[str, object]]) -> dict:
    """input_rules.duplicate_keys: a repeated key keeps its first value."""
    merged: dict = {}
    for key, value in pairs:
        if key not in merged:
            merged[key] = value
    return merged


def read_input(name: str) -> object:
    """Parse an input under /app/data the way input_rules says: BOM dropped, first key wins."""
    raw = (DATA / name).read_bytes()
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=first_occurrence)


def dump_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def show_raw_inputs() -> None:
    """Look at the bytes before trusting a parser: BOMs and repeated keys hide from json.loads."""
    for path in sorted(DATA.glob("*.json")):
        raw = path.read_bytes()
        notes = []
        if raw.startswith(b"\xef\xbb\xbf"):
            notes.append("starts with a UTF-8 byte order mark")
        repeated: list[str] = []

        def spot(pairs: list[tuple[str, object]], seen=repeated) -> dict:
            names = [key for key, _ in pairs]
            seen.extend(sorted({key for key in names if names.count(key) > 1}))
            return first_occurrence(pairs)

        json.loads(raw.decode("utf-8-sig"), object_pairs_hook=spot)
        if repeated:
            notes.append("repeats key(s) " + ", ".join(repeated))
        if any(byte > 0x7F for byte in raw.lstrip(b"\xef\xbb\xbf")):
            notes.append("carries non-ASCII text")
        print(f"[inputs] {path.name}: {'; '.join(notes) if notes else 'plain'} (first bytes {raw[:8]!r})")


def extract() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE_ARCHIVE) as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode) or len(rel.parts) != 1:
                raise SystemExit(f"unexpected source member: {info.filename!r}")
            (TOOL / rel.name).write_bytes(zf.read(info))


def run_tool(*args: str, tool: Path = TOOL, cwd: Path | None = None) -> dict[str, object]:
    argv = [sys.executable, str(tool / "cli.py"), *args]
    result = subprocess.run(argv, cwd=cwd or tool, text=True, capture_output=True, timeout=30, check=False)
    return {
        "argv": argv,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def observe_failures() -> None:
    """Run every subcommand of the unrepaired tool on scratch copies and say what it does wrong."""
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        config = work / "config.json"
        bare = run_tool()
        print(f"[diagnose] no subcommand: exit={bare['returncode']} stdout={bare['stdout'][:40]!r} "
              f"stderr={bare['stderr'][:40]!r} (contract: exit 2, usage on stderr)")
        run_tool("init", "--schema", str(DATA / "config_schema.json"), "--defaults",
                 str(DATA / "defaults.json"), "--out", str(config))
        seeded = json.loads(config.read_text(encoding="utf-8"))
        print(f"[diagnose] init wrote mode={seeded.get('mode')!r} producer={seeded.get('producer')!r} "
              f"container={seeded.get('container')!r}; defaults.json says strict-local, Zürich-ops, edge-cache")
        run_tool("set", "--config", str(config), "--key", "max_records", "--value", "9007199254740993")
        run_tool("set", "--config", str(config), "--key", "max_records", "--value", "17")
        stored = json.loads(config.read_text(encoding="utf-8")).get("max_records")
        print(f"[diagnose] set 9007199254740993 then 17 left max_records={stored!r}")
        run_tool("set", "--config", str(config), "--key", "retry_limit", "--value", "5")
        run_tool("set", "--config", str(config), "--key", "timeout_ms", "--value", "7148")
        sealed = run_tool("seal", "--config", str(config))
        print(f"[diagnose] seal printed {sealed['stdout']!r} (contract: 16 hex digits over the canonical body)")
        print(f"[diagnose] the file it wrote: {config.read_bytes()[:72]!r}...")
        loose = work / "loose.json"
        loose.write_text(json.dumps({"MAX_RECORDS": "x", "profile": "TASK", "producer": "", "container": "",
                                     "checksum": "", "mode": "", "retry_limit": [], "timeout_ms": True,
                                     "trailer": "harbor:cli-config:junk"}), encoding="utf-8")
        verdict = run_tool("validate", "--schema", str(DATA / "config_schema.json"), "--config", str(loose))
        print(f"[diagnose] validate on an upper-cased, list-valued, unsealed document: "
              f"exit={verdict['returncode']} stdout={verdict['stdout']!r}")
        for name in ("dev", "prod"):
            outcome = run_tool("profile", "--config", str(config), "--overrides", str(DATA / "env_overrides.json"),
                               "--samples", str(DATA), "--name", name, "--out", str(work / f"profile_{name}.json"))
            tail = (outcome["stderr"].splitlines() or ["(no stderr)"])[-1]
            written = work / f"profile_{name}.json"
            body = written.read_text(encoding="utf-8") if written.is_file() else "(nothing written)"
            print(f"[diagnose] profile {name}: exit={outcome['returncode']} {tail[:90]} -> {body[:160]}")
        (work / "commands.json").write_text("[]", encoding="utf-8")
        (work / "repairs.json").write_text("[]", encoding="utf-8")
        run_tool("export-report", "--config", str(config), "--commands", str(work / "commands.json"),
                 "--repairs", str(work / "repairs.json"), "--out", str(work / "report.json"))
        report = json.loads((work / "report.json").read_text(encoding="utf-8"))
        own = report["commands"][-1]["argv"]
        actual = hashlib.sha256(config.read_bytes()).hexdigest()
        print(f"[diagnose] export-report recorded argv[0]={own[0]!r}, config_sha256 matches file: "
              f"{report['config_sha256'] == actual}")


def replace_function(source: str, name: str, new_code: str, causes: list[str]) -> str:
    """Swap one top-level function for its repaired text and record why it changed."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.splitlines(keepends=True)
            for cause in causes:
                print(f"[fix] {cause}")
            REPAIRS.extend(causes)
            return "".join(lines[: node.lineno - 1]) + new_code + "".join(lines[node.end_lineno:])
    raise SystemExit(f"function {name} not found in cli.py")


def record_causes(causes: list[str]) -> None:
    """Name the faults a text edit repairs, as replace_function does for whole functions."""
    for cause in causes:
        print(f"[fix] {cause}")
    REPAIRS.extend(causes)


def replace_text(source: str, old: str, new: str) -> str:
    if old not in source:
        raise SystemExit(f"expected text not found: {old!r}")
    return source.replace(old, new, 1)


LOADERS = '''def keep_first(pairs):
    obj = {}
    for key, value in pairs:
        obj.setdefault(key, value)
    return obj


def load_json(path):
    text = Path(path).read_bytes().decode("utf-8-sig")
    return json.loads(text, object_pairs_hook=keep_first)


def load_object(path):
    doc = load_json(path)
    if not isinstance(doc, dict):
        raise CliError(f"{path} does not hold a JSON object")
    return doc
'''

ENCODE = '''def encode(doc):
    text = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (text + "\\n").encode("utf-8")
'''

TRAILER = '''def body_digest(doc):
    body = {key: value for key, value in doc.items() if key != "trailer"}
    return format(zlib.crc32(encode(body)), "016x")


def config_trailer(doc):
    return f"{TRAILER_PREFIX}:{doc['profile']}:{body_digest(doc)}"
'''

PARSE = '''def parse_integer(text):
    if not INTEGER_TEXT.fullmatch(text):
        raise CliError(f"value {text!r} is not a base-10 integer")
    return int(text)
'''

INIT = '''def cmd_init(args):
    schema = load_object(args.schema)
    defaults = load_object(args.defaults)
    doc = {"profile": schema["profile"]}
    for key in ("producer", "container", "checksum", "mode"):
        doc[key] = defaults[key]
    write_document(args.out, doc)
'''

SET = '''def cmd_set(args):
    if args.key not in NUMERIC_KEYS:
        raise CliError(f"key {args.key!r} is not one of {', '.join(NUMERIC_KEYS)}")
    value = parse_integer(args.value)
    doc = load_object(args.config)
    doc[args.key] = value
    write_document(args.config, doc)
'''

SEAL = '''def cmd_seal(args):
    doc = load_object(args.config)
    doc.pop("trailer", None)
    doc["trailer"] = config_trailer(doc)
    write_document(args.config, doc)
    print(doc["trailer"])
'''

VALIDATE = '''def cmd_validate(args):
    schema = load_object(args.schema)
    raw = Path(args.config).read_bytes()
    doc = json.loads(raw.decode("utf-8"), object_pairs_hook=keep_first)
    if not isinstance(doc, dict) or raw != encode(doc):
        raise CliError("configuration is not in canonical encoding")
    expected = set(required_keys(schema))
    if set(doc) != expected:
        missing = sorted(expected - set(doc))
        extra = sorted(set(doc) - expected)
        raise CliError(f"keys differ from the schema: missing {missing}, extra {extra}")
    if doc["profile"] != schema["profile"]:
        raise CliError(f"profile {doc['profile']!r} does not match the schema")
    for key, value in doc.items():
        if key in NUMERIC_KEYS:
            if not isinstance(value, int) or isinstance(value, bool):
                raise CliError(f"{key} must be an integer")
        elif not isinstance(value, str):
            raise CliError(f"{key} must be a string")
    if doc["trailer"] != config_trailer(doc):
        raise CliError("trailer does not match the document")
    print("ok")
'''

PROFILE = '''def profile_chain(overrides, name):
    chain = []
    current = name
    while current is not None:
        if current in chain:
            raise CliError(f"extends cycle through {current!r}")
        entry = overrides.get(current)
        if not isinstance(entry, dict):
            raise CliError(f"no override entry named {current!r}")
        chain.append(current)
        current = entry.get("extends")
    chain.reverse()
    return chain


def sample_delta(samples, name):
    path = Path(samples) / f"sample_config_{name}.json"
    if not path.is_file():
        return 0
    return load_object(path).get("max_records_delta", 0)


def cmd_profile(args):
    config = load_object(args.config)
    overrides = load_object(args.overrides)
    chain = profile_chain(overrides, args.name)
    resolved = {key: config[key] for key in (*NUMERIC_KEYS, "mode")}
    trailer = config["trailer"]
    for name in chain:
        entry = overrides[name]
        resolved["max_records"] += sample_delta(args.samples, name)
        resolved["retry_limit"] += entry.get("retry_limit_delta", 0)
        resolved["timeout_ms"] += entry.get("timeout_ms_delta", 0)
        if "mode" in entry:
            resolved["mode"] = entry["mode"]
        doc = {
            "profile": f"{config['profile']}-{name}",
            "producer": config["producer"],
            "container": config["container"],
            "checksum": config["checksum"],
            **resolved,
        }
        trailer = f"{trailer}:{name}:{body_digest(doc)}"
        doc["trailer"] = trailer
    write_document(args.out, doc)
'''

REPORT = '''def cmd_report(args):
    raw = Path(args.config).read_bytes()
    doc = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=keep_first)
    commands = load_json(args.commands)
    repairs = load_json(args.repairs)
    if not isinstance(commands, list) or not all(isinstance(item, dict) for item in commands):
        raise CliError("--commands must hold a JSON list of command entries")
    if not isinstance(repairs, list) or not all(isinstance(item, str) for item in repairs):
        raise CliError("--repairs must hold a JSON list of strings")
    commands.append({"argv": list(sys.orig_argv), "returncode": 0, "stdout": ""})
    report = {
        "ok": all(item.get("returncode") == 0 for item in commands),
        "tool": PROG,
        "config_path": os.path.abspath(args.config),
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "trailer": doc.get("trailer") if isinstance(doc, dict) else None,
        "commands": commands,
        "repairs": repairs,
    }
    write_document(args.out, report)
'''

MAIN = '''def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except (CliError, OSError, ValueError, KeyError, TypeError) as exc:
        message = " ".join(str(exc).split()) or type(exc).__name__
        print(f"{PROG}: {message}", file=sys.stderr)
        return 1
    return 0
'''


def repair_cli() -> None:
    path = TOOL / "cli.py"
    source = path.read_text(encoding="utf-8")
    source = replace_text(source, "import json\nimport sys\n", "import json\nimport os\nimport re\nimport sys\n")
    source = replace_text(
        source,
        'DEFAULT_MODE = "relaxed-local"\n',
        'NUMERIC_KEYS = ("max_records", "retry_limit", "timeout_ms")\n'
        'INTEGER_TEXT = re.compile(r"-?(?:0|[1-9][0-9]*)")\n'
        "\n\n"
        "class CliError(Exception):\n"
        '    """A failure reported as one line on standard error with exit status 1."""\n',
    )
    source = replace_function(source, "load_json", LOADERS, [
        "load_json decoded with read_text, so the byte order mark on sample_config_dev.json made json.loads "
        "raise; input_rules.encoding says the mark is not part of the document",
        "load_json let a repeated key keep its last value, so defaults.json read timeout_ms 7418 and "
        "env_overrides.json read the dev timeout_ms_delta as 125; input_rules.duplicate_keys keeps the first",
    ])
    source = replace_function(source, "encode", ENCODE, [
        "encode used a bare json.dumps: insertion key order, spaced separators and \\u escapes, so documents "
        "were not the canonical_encoding and their bytes depended on set order",
    ])
    source = replace_function(source, "config_trailer", TRAILER, [
        "config_trailer hashed the document with its old trailer still inside, so resealing changed the "
        "digest; the seal_rules digest covers the document with the trailer removed",
        "config_trailer formatted the CRC-32 with 08x; seal_rules ask for 16 lowercase hex digits with leading "
        "zeros, which is what history_2026-07.jsonl carries",
    ])
    source = replace_function(source, "parse_number", PARSE, [
        "parse_number went through float, so 9007199254740993 became 9007199254740992 and texts such as 1e3, "
        "12.0, +7 or 1_000 were accepted; set takes only an exact base-10 integer",
    ])
    source = replace_function(source, "cmd_init", INIT, [
        "cmd_init never read mode from the defaults file and fell back to relaxed-local",
        "cmd_init preferred the schema's producer, container and checksum over the defaults file, so the "
        "configuration got empty producer and container values",
    ])
    source = replace_function(source, "cmd_set", SET, [
        "cmd_set folded the key to lower case and accepted any name; only max_records, retry_limit and "
        "timeout_ms spelled exactly are allowed",
        "cmd_set used setdefault, so a second set of the same key silently kept the old value",
    ])
    source = replace_function(source, "cmd_seal", SEAL, [
        "cmd_seal kept any existing trailer while computing the new one",
    ])
    source = replace_function(source, "cmd_validate", VALIDATE, [
        "cmd_validate compared keys case-insensitively, ignored extra keys, accepted lists, booleans and "
        "strings in numeric fields, only checked the trailer prefix and never checked canonical bytes or the "
        "schema profile, so it printed ok for documents the contract rejects",
    ])
    source = replace_function(source, "cmd_profile", PROFILE, [
        "cmd_profile ignored extends, so prod never received the stage deltas or the stage mode",
        "cmd_profile copied every matching key of an override entry over the result, so the legacy absolute "
        "retry_limit 3 in prod replaced the computed value",
        "cmd_profile took checksum from the sample file (md5 for dev) instead of the configuration",
        "cmd_profile built the trailer as config trailer plus name, without the per-entry digest chain the "
        "seal_rules profile_trailer describes, and crashed on a missing sample file once ancestors are read",
    ])
    source = replace_function(source, "cmd_report", REPORT, [
        "cmd_report recorded sys.argv, which drops the interpreter, as its own argv",
        "cmd_report always wrote ok true even when a recorded command had failed",
        "cmd_report stored --config as given instead of as an absolute path",
        "cmd_report hashed a re-encoding of the parsed document instead of the file's bytes on disk",
    ])
    source = replace_text(source, 'sub = parser.add_subparsers(dest="command")',
                          'sub = parser.add_subparsers(dest="command", required=True)')
    source = replace_text(source, 'p.add_argument("--defaults")', 'p.add_argument("--defaults", required=True)')
    record_causes(["build_parser left init's --defaults optional, so cmd_init ran with no defaults file "
                   "where the contract wants a usage error"])
    source = replace_text(source, 'p.add_argument("--commands")\n    p.add_argument("--repairs")',
                          'p.add_argument("--commands", required=True)\n'
                          '    p.add_argument("--repairs", required=True)')
    record_causes(["build_parser left export-report's --commands and --repairs optional, so cmd_report wrote a "
                   "report with no recorded commands or repairs where the contract wants a usage error"])
    source = replace_function(source, "main", MAIN, [
        "main printed usage on standard output and exited 0 with no subcommand; the contract wants status 2 "
        "and usage on standard error",
        "main let KeyError and JSON errors escape as tracebacks; failures now print one line on standard "
        "error and exit 1",
    ])
    source = replace_text(source, 'if __name__ == "__main__":\n    main()', 'if __name__ == "__main__":\n    sys.exit(main())')
    path.write_text(source, encoding="utf-8")
    compile(source, str(path), "exec")


def load_repaired_module():
    spec = importlib.util.spec_from_file_location("repaired_task_ctl", TOOL / "cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calibrate(cli) -> None:
    """Reproduce every line of the history file with the repaired code before trusting it."""
    lines = (DATA / "history_2026-07.jsonl").read_bytes().splitlines(keepends=True)
    docs = [json.loads(line) for line in lines]
    for line, doc in zip(lines, docs):
        if cli.encode(doc) != line:
            raise SystemExit(f"repaired encode does not reproduce history line {line[:60]!r}")
    config, edge, edge_eu = docs
    with tempfile.TemporaryDirectory() as scratch:
        unsealed = Path(scratch) / "history_config.json"
        unsealed.write_bytes(cli.encode({k: v for k, v in config.items() if k != "trailer"}))
        sealed = run_tool("seal", "--config", str(unsealed))
    checks = [
        (sealed["stdout"], config["trailer"]),
        (f"{config['trailer']}:edge:{cli.body_digest(edge)}", edge["trailer"]),
        (f"{edge['trailer']}:edge-eu:{cli.body_digest(edge_eu)}", edge_eu["trailer"]),
    ]
    for got, want in checks:
        if got != want:
            raise SystemExit(f"history trailer mismatch: computed {got!r}, recorded {want!r}")
    print(f"[calibrate] repaired seal and profile digests reproduce all {len(lines)} history lines")


def drive(cli) -> list[dict[str, object]]:
    OUT.mkdir(parents=True, exist_ok=True)
    config = OUT / "config.json"
    schema = DATA / "config_schema.json"
    base = read_input("defaults.json")["base_config"]
    commands = [run_tool("init", "--schema", str(schema), "--defaults", str(DATA / "defaults.json"),
                         "--out", str(config))]
    for key in NUMERIC:
        commands.append(run_tool("set", "--config", str(config), "--key", key, "--value", str(base[key])))
    commands.append(run_tool("seal", "--config", str(config)))
    commands.append(run_tool("validate", "--schema", str(schema), "--config", str(config)))
    failed = [item for item in commands if item["returncode"] != 0]
    if failed:
        raise SystemExit(f"repaired CLI failed: {failed}")
    on_disk = config.read_bytes()
    print(f"[verify] {config} on disk: {on_disk.decode('utf-8').strip()}")
    if cli.encode(json.loads(on_disk)) != on_disk:
        raise SystemExit("config.json on disk is not canonical")

    recorded = [{key: item[key] for key in ("argv", "returncode", "stdout")} for item in commands]
    with tempfile.TemporaryDirectory() as scratch:
        commands_file = Path(scratch) / "commands.json"
        repairs_file = Path(scratch) / "repairs.json"
        commands_file.write_text(json.dumps(recorded), encoding="utf-8")
        repairs_file.write_text(json.dumps(REPAIRS), encoding="utf-8")
        exported = run_tool("export-report", "--config", str(config), "--commands", str(commands_file),
                            "--repairs", str(repairs_file), "--out", str(OUT / "report.json"))
    if exported["returncode"] != 0:
        raise SystemExit(f"export-report failed: {exported}")
    return recorded


def write_profiles(names: list[str]) -> dict[str, dict]:
    produced = {}
    for name in names:
        target = OUT / f"profile_{name}.json"
        outcome = run_tool("profile", "--config", str(OUT / "config.json"), "--overrides",
                           str(DATA / "env_overrides.json"), "--samples", str(DATA), "--name", name,
                           "--out", str(target))
        if outcome["returncode"] != 0:
            raise SystemExit(f"profile {name} failed: {outcome}")
        produced[name] = json.loads(target.read_text(encoding="utf-8"))
        print(f"[verify] {target}: {target.read_text(encoding='utf-8').strip()}")
    return produced


def package_tool() -> None:
    archive = OUT / "tool.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in TOOL.iterdir() if p.is_file()):
            info = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def check_archive_standalone() -> None:
    """Unpack the delivered archive away from /app/data and run it on inputs of its own."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch) / "unpacked"
        root.mkdir()
        with zipfile.ZipFile(OUT / "tool.zip") as zf:
            zf.extractall(root)
        defaults = Path(scratch) / "defaults.json"
        defaults.write_text(json.dumps({"producer": "p", "container": "c", "checksum": "crc32",
                                        "mode": "m"}), encoding="utf-8")
        config = Path(scratch) / "config.json"
        steps = [
            ("init", "--schema", str(root / "schema.json"), "--defaults", str(defaults), "--out", str(config)),
            ("set", "--config", str(config), "--key", "max_records", "--value", "1"),
            ("set", "--config", str(config), "--key", "retry_limit", "--value", "2"),
            ("set", "--config", str(config), "--key", "timeout_ms", "--value", "3"),
            ("seal", "--config", str(config)),
            ("validate", "--schema", str(root / "schema.json"), "--config", str(config)),
        ]
        for step in steps:
            outcome = run_tool(*step, tool=root, cwd=Path(scratch))
            if outcome["returncode"] != 0:
                raise SystemExit(f"unpacked archive failed on {step[0]}: {outcome}")
        bare = run_tool(tool=root, cwd=Path(scratch))
        if bare["returncode"] != 2 or bare["stdout"]:
            raise SystemExit(f"unpacked archive mishandles a bare invocation: {bare}")
        probe = str(Path(scratch) / "probe.json")
        missing = {
            "init": ("init", "--schema", str(root / "schema.json"), "--out", probe),
            "set": ("set", "--config", str(config), "--key", "max_records"),
            "seal": ("seal",),
            "validate": ("validate", "--config", str(config)),
            "profile": ("profile", "--config", str(config), "--overrides", str(defaults), "--name", "dev",
                        "--out", probe),
            "export-report": ("export-report", "--config", str(config), "--commands", str(defaults),
                              "--out", probe),
        }
        for name, step in missing.items():
            outcome = run_tool(*step, tool=root, cwd=Path(scratch))
            if outcome["returncode"] != 2 or outcome["stdout"] or Path(probe).exists():
                raise SystemExit(f"unpacked archive accepts {name} with a required option left out: {outcome}")
            print(f"[verify] {name} with a required option left out exits 2")
    print("[verify] the unpacked tool.zip runs init, set, seal and validate on its own")


def main() -> None:
    show_raw_inputs()
    extract()
    observe_failures()
    repair_cli()
    cli = load_repaired_module()
    calibrate(cli)

    rules = read_input("validation_rules.json")
    artifacts = rules["required_artifacts"]
    recorded = drive(cli)
    profiles = write_profiles(rules["profiles"])
    package_tool()
    check_archive_standalone()

    config = json.loads((OUT / "config.json").read_text(encoding="utf-8"))
    schema = read_input("config_schema.json")
    defaults = read_input("defaults.json")
    policy = {key: defaults[key] for key in ("producer", "container", "checksum", "mode")}
    policy.update({key: defaults["base_config"][key] for key in NUMERIC})
    policy["profile"] = schema["profile"]
    policy["trailer"] = cli.config_trailer(policy)
    overrides = read_input("env_overrides.json")

    inputs = sorted(path.name for path in DATA.iterdir() if path.is_file())
    dump_json(OUT / "summary.json", {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "format_tag": rules["format_tag"],
        "input_count": len(inputs),
        "inputs": inputs,
        "profiles": rules["profiles"],
        "trailer": config["trailer"],
    })

    # written last, once every other artifact exists, so the presence claim is true when made
    report = json.loads((OUT / "report.json").read_text(encoding="utf-8"))
    checks = {
        "all_artifacts_present": all((OUT / name).is_file() for name in artifacts if name != "validation_report.json"),
        "command_failures": [item for item in report["commands"] if item.get("returncode") != 0],
        "config_matches_policy": config == policy,
        "config_scalar_flat": all(isinstance(value, (str, int)) and not isinstance(value, bool)
                                  for value in config.values()),
        "config_seal_verified": config.get("trailer") == cli.config_trailer(config),
        "profiles": {name: {"trailer": doc["trailer"], "chain": cli.profile_chain(overrides, name)}
                     for name, doc in profiles.items()},
        "required_artifacts": artifacts,
    }
    flags = [checks[key] for key in ("all_artifacts_present", "config_matches_policy",
                                     "config_scalar_flat", "config_seal_verified")]
    dump_json(OUT / "validation_report.json", {"ok": all(flags) and not checks["command_failures"],
                                               "checks": checks})
    print(f"[oracle] {len(recorded) + 1} commands recorded, {len(REPAIRS)} repairs named")
    for name in artifacts:
        print(f"[oracle] wrote {OUT / name}")


if __name__ == "__main__":
    main()
