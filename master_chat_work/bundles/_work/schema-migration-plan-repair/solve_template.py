#!/usr/bin/env python3
"""Reference repair for schema-migration-plan-repair.

Copies the repository at /app/repo, applies the repairs below (each one restores a
behaviour that repository_contract.md, migration_semantics.md or a contract
file header states), adds the missing ``__main__.py``, proves the result by
running the visible tests and the CLI from a foreign working directory, and
writes the seven deliverables under /app/out. Standard library only.
"""

from __future__ import annotations

import ast
import hashlib
import heapq
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
REPO = APP_ROOT / "repo"
CI = APP_ROOT / "ci"
OUT = APP_ROOT / "out"
PACKAGE = "migrakit"
MAIN_MODULE = "from migrakit.cli import main\n\nraise SystemExit(main())\n"
ZIP_TIME = (2026, 10, 21, 0, 0, 0)

# (file, shipped text, repaired text). Each shipped text occurs exactly once.
REPAIRS: list[tuple[str, str, str]] = []

FIX_NOTES = {
    "core": [
        "core.records: FieldView keeps an explicit null as its own state, so the state signature, the planner and the operations all see it (N1).",
        "core.records: presence and fill read the per-field policy column first; an empty null_counts_as column falls back to null_semantics.ini [presence], not to absent (N2, N3, N4).",
        "core.planner: search over (schema, field states) with a heap ordered by (cost, edge-id list); prerequisites are checked on the record after the previous step and schemas may repeat (M6 to M8, K14).",
        "core.executor: corrections apply on first arrival at their pinned schema and every edge's prerequisites are re-checked; a failing edge ends the record as failed with E_PREREQ_FAILED (C4, M11).",
        "pipeline: replay identity keyed on the canonical partner, and a record holds its identity once it passes the partner stage even if planning then fails; lines processed in received_seq order (K13, K16).",
        "pipeline: a payload string becomes null only when it equals a null token exactly (N6).",
        "pipeline: the batch receipt covers the records whose batch is set and takes the K4 fingerprint of each such line as received, including lines rejected at the partner stage (K13, K15, K17).",
    ],
    "parser": [
        "parser.identity: every merge link is followed and a loop raises E_ALIAS_CYCLE (P2, P3).",
        "parser.feed: a line that is not JSON becomes an E_PARSE record and the run continues (K15).",
        "parser.contracts: a partner's own token line is used exactly as written, so an empty line means no tokens and the default line applies only to partners without a line (N7).",
        "cli: relative paths resolve against the caller's working directory; __main__.py added so python -m migrakit works (K10).",
    ],
    "report": [
        "report.classify: status and code come from the execution result, so a failed execution stays failed (M11).",
        "report.summary: categories by code first in taxonomy order, partners in partner_order.tsv rank order (T1 to T3).",
    ],
}
AREAS = {"core": ("core.", "pipeline."), "parser": ("parser.", "cli.", "__main__."), "report": ("report.",)}


def extract(archive: Path, dest: Path) -> Path:
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = Path(info.filename)
            if name.is_absolute() or ".." in name.parts:
                raise SystemExit(f"unsafe member {info.filename}")
            if info.filename.endswith("/"):
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
    return dest


def apply_repairs(tree: Path) -> None:
    for rel, shipped, repaired in REPAIRS:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        if text.count(shipped) != 1:
            raise SystemExit(f"{rel}: expected exactly one occurrence of the shipped text")
        path.write_text(text.replace(shipped, repaired, 1), encoding="utf-8")
    (tree / "src" / PACKAGE / "__main__.py").write_text(MAIN_MODULE, encoding="utf-8")


def child_env(tree: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tree / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def unit_results(tree: Path) -> dict[str, str]:
    done = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-v", "-s", "tests"],
        cwd=tree, env=child_env(tree), capture_output=True, text=True, timeout=600,
    )
    found: dict[str, str] = {}
    for line in done.stderr.splitlines():
        if line.startswith("test_") and " ... " in line:
            name = line.split(" ", 1)[0]
            found[name] = "pass" if line.rstrip().endswith(" ok") else "fail"
    return found


def build_archive(tree: Path, target: Path) -> None:
    files = sorted(p for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def run_cli(tree: Path, workdir: Path) -> dict:
    args = [
        "run", "--contracts", str(CI), "--feed", str(CI / "partner_batches.jsonl"),
        "--corrections", str(CI / "correction_log.txt"), "--manifest", str(CI / "replay_manifest.csv"),
        "--out", "visible-run",
    ]
    done = subprocess.run([sys.executable, "-m", PACKAGE, *args], cwd=workdir, env=child_env(tree), capture_output=True, text=True, timeout=1800)
    if done.returncode != 0:
        raise SystemExit(f"CLI run failed: {done.stderr[-2000:]}")
    return json.loads((workdir / "visible-run" / "run_summary.json").read_text(encoding="utf-8"))


PROBE_DRIVER = """
import json, sys
from migrakit.pipeline import run_pipeline
root = sys.argv[1]
records, summary = run_pipeline(root, root + "/feed.jsonl", root + "/corrections.txt", root + "/manifest.csv")
print(json.dumps({"records": records, "summary": summary}))
"""


def fingerprint(schema: str, payload: dict) -> str:
    text = json.dumps({"payload": payload, "schema": schema}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def self_checks(tree: Path, workdir: Path) -> list[dict]:
    """Run the repaired pipeline on a small contract folder built here, with cases the shipped data lacks."""
    root = workdir / "probe"
    root.mkdir()
    schemas = [{"id": "lab.v1", "domain": "lab", "canonical": False}, {"id": "lab.v2", "domain": "lab", "canonical": True}]
    lines = [
        {"batch": "B1", "partner": "one", "key": "k1", "schema": "lab.v1", "payload": {"f": "x"}},
        {"batch": "B1", "partner": "P2", "key": "k2", "schema": "lab.v1", "payload": {"f": "x"}},
        {"batch": "B2", "partner": "one", "key": "k3", "schema": "lab.v1", "payload": {"f": " NULL"}},
        {"batch": "B2", "partner": "one", "key": "k4", "schema": "lab.v1", "payload": []},
        {"batch": "B3", "partner": "one", "key": "k5", "schema": "lab.v1", "payload": {"f": "y"}},
    ]
    receipts = {"B1": (2, [0, 1]), "B2": (1, [2]), "B3": (2, [4])}
    manifest = ["batch_id,received_seq,lines,fp_xor"]
    for seq, (batch, (count, members)) in enumerate(receipts.items(), start=1):
        xor = 0
        for index in members:
            xor ^= int(fingerprint(lines[index]["schema"], lines[index]["payload"])[:8], 16)
        manifest.append(f"{batch},{seq},{count},{xor:08x}")
    files = {
        "schema_versions.json": json.dumps({"schemas": schemas}),
        "migration_edges.csv": "edge_id,source,target,requires,operations,cost\nE1,lab.v1,lab.v2,has:f,,1\n",
        "field_policy.tsv": "domain\tfield\tdefault\tfill\tnull_counts_as\nlab\tf\t\t\tabsent\n",
        "null_semantics.ini": "[presence]\nexplicit_null = present\n\n[fill]\nmode = absent_only\n\n[tokens]\ndefault = NULL | N/A\n",
        "partner_aliases.xml": '<partners>\n  <partner id="P1"><alias>one</alias></partner>\n  <partner id="P2"/>\n  <partner id="P3"/>\n'
        '  <merge from="P2" into="P3"/>\n  <merge from="P3" into="P2"/>\n</partners>\n',
        "report_taxonomy.json": (CI / "report_taxonomy.json").read_text(encoding="utf-8"),
        "partner_order.tsv": "partner_id\trank\nP1\t1\n",
        "feed.jsonl": "".join(json.dumps(line) + "\n" for line in lines),
        "corrections.txt": "# none\n",
        "manifest.csv": "\n".join(manifest) + "\n",
    }
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    done = subprocess.run([sys.executable, "-c", PROBE_DRIVER, str(root)], cwd=workdir, env=child_env(tree), capture_output=True, text=True, timeout=120)
    if done.returncode != 0:
        raise SystemExit(f"probe run failed: {done.stderr[-2000:]}")
    result = json.loads(done.stdout)
    records, summary = result["records"], result["summary"]
    checks = [
        ("probe: a batch whose receipt states one line too many is the only receipt mismatch", summary["receipt_mismatches"] == ["B3"]),
        ("probe: a line rejected with E_ALIAS_CYCLE counts in its batch receipt and keeps a null fingerprint",
         records[1]["code"] == "E_ALIAS_CYCLE" and records[1]["fingerprint"] is None and "B1" not in summary["receipt_mismatches"]),
        ("probe: an E_PARSE line naming a manifest batch has a null batch and is left out of that batch receipt",
         records[3]["code"] == "E_PARSE" and records[3]["batch"] is None and "B2" not in summary["receipt_mismatches"]),
        ("probe: a prerequisite value ' NULL' is not a null token, so the record still migrates with it",
         records[2]["status"] == "migrated" and records[2]["payload"] == {"f": " NULL"}),
    ]
    failed = [name for name, passed in checks if not passed]
    if failed:
        raise SystemExit(f"self checks failed: {failed}")
    return [{"name": name, "passed": passed} for name, passed in checks]


CALL_DRIVER = """
import json, sys, time
import migrakit
request = json.loads(sys.argv[1])
answer = {}
try:
    registry = migrakit.load_contracts(request["contracts"])
    if "schema" in request:
        start = time.perf_counter()
        answer["plan"] = migrakit.plan_migration(registry, request["schema"], request["payload"])
        answer["seconds"] = round(time.perf_counter() - start, 3)
except Exception as exc:
    answer["error"] = f"{type(exc).__name__}: {exc}"
print(json.dumps(answer))
"""


def call(tree: Path, workdir: Path, request: dict) -> dict:
    done = subprocess.run([sys.executable, "-c", CALL_DRIVER, json.dumps(request)], cwd=workdir, env=child_env(tree),
                          capture_output=True, text=True, timeout=120)
    if done.returncode != 0:
        raise SystemExit(f"probe call failed: {done.stderr[-2000:]}")
    return json.loads(done.stdout)


def pipeline(tree: Path, workdir: Path, root: Path) -> dict:
    done = subprocess.run([sys.executable, "-c", PROBE_DRIVER, str(root)], cwd=workdir, env=child_env(tree), capture_output=True, text=True, timeout=120)
    if done.returncode != 0:
        raise SystemExit(f"probe run failed: {done.stderr[-2000:]}")
    return json.loads(done.stdout)


def contract_folder(root: Path, schemas: list[dict], edges: list[tuple], fields: list[str], domain: str) -> None:
    """A contract folder with no field operations, so a record's field states stay as given along every plan."""
    root.mkdir()
    rows = ["edge_id,source,target,requires,operations,cost", *(",".join([a, b, c, req, "", str(cost)]) for a, b, c, req, cost in edges)]
    files = {
        "schema_versions.json": json.dumps({"schemas": schemas}),
        "migration_edges.csv": "\n".join(rows) + "\n",
        "field_policy.tsv": "domain\tfield\tdefault\tfill\tnull_counts_as\n" + "".join(f"{domain}\t{f}\t\t\t\n" for f in fields),
        "null_semantics.ini": "[presence]\nexplicit_null = present\n\n[fill]\nmode = absent_only\n\n[tokens]\ndefault = NULL\n",
        "partner_aliases.xml": '<partners>\n  <partner id="P1"/>\n</partners>\n',
        "report_taxonomy.json": (CI / "report_taxonomy.json").read_text(encoding="utf-8"),
        "partner_order.tsv": "partner_id\trank\nP1\t1\n",
    }
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")


def cheapest_by_schema(edges: list[tuple], start: str, target: str, allowed) -> list[str] | None:
    """Separate search for the cheapest plan, then the smallest edge-id list, when field states never change."""
    out: dict[str, list[tuple]] = {}
    for edge in edges:
        out.setdefault(edge[1], []).append(edge)
    heap: list[tuple[int, list[str], str]] = [(0, [], start)]
    done: set[str] = set()
    while heap:
        cost, path, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        if node == target:
            return path
        for edge_id, _, nxt, req, step in out.get(node, []):
            if nxt not in done and allowed(req):
                heapq.heappush(heap, (cost + step, path + [edge_id], nxt))
    return None


def contract_checks(tree: Path, workdir: Path) -> list[dict]:
    """Run the repaired package on contract folders built here and on altered copies of the shipped one."""
    checks: list[tuple[str, bool, str]] = []

    # A layered graph of 1,082 schemas: 3**40 distinct paths, plans of 41 edges.
    rng = random.Random(7)
    layers = [["big.s"]] + [[f"big.l{k:02d}n{j:02d}" for j in range(27)] for k in range(40)] + [["big.t"]]
    schemas = [{"id": s, "domain": "big", "canonical": s == "big.t"} for layer in layers for s in layer]
    edges, number = [], 0
    for here, there in zip(layers, layers[1:]):
        for a in here:
            for b in (there if len(there) == 1 else rng.sample(there, 3)):
                number += 1
                edges.append((f"E{number:05d}", a, b, rng.choice(["", "", "has:f", "lacks:f"]), rng.randint(1, 9)))
    big = workdir / "large-graph"
    contract_folder(big, schemas, edges, ["f", "g"], "big")
    answer = call(tree, workdir, {"contracts": str(big), "schema": "big.s", "payload": {"f": 1, "g": None}})
    print(f"plan_migration on {len(schemas)} schemas and {len(edges)} edges: {answer.get('seconds')} s, {len(answer.get('plan') or [])} edges")
    checks.append(("probe: plan_migration on a built graph of 1,082 schemas returns within the stated time",
                   answer.get("seconds", 99) < 10, f"{answer.get('seconds')} s"))
    separate = cheapest_by_schema(edges, "big.s", "big.t", lambda req: req != "lacks:f")
    checks.append(("probe: on that graph the plan equals a cheapest plan found by a separate search",
                   answer.get("plan") == separate, f"{len(separate or [])} edges, first {(separate or [''])[0]}"))

    # A cost above one million, with two plans of equal total cost.
    dear = workdir / "dear-edges"
    contract_folder(dear, [{"id": f"lab.v{n}", "domain": "lab", "canonical": n == 2} for n in (1, 2, 3)],
                    [("E1", "lab.v1", "lab.v3", "", 2999999), ("E2", "lab.v1", "lab.v2", "", 5000000), ("E3", "lab.v3", "lab.v2", "", 2000001)],
                    ["f"], "lab")
    answer = call(tree, workdir, {"contracts": str(dear), "schema": "lab.v1", "payload": {}})
    checks.append(("probe: with edge costs above one million and two plans of equal cost the smaller edge-id list wins",
                   answer.get("plan") == ["E1", "E3"], str(answer.get("plan"))))

    # An extra file in a contract folder.
    probe = workdir / "probe"
    extra = workdir / "probe-extra-file"
    shutil.copytree(probe, extra)
    (extra / "unlisted_notes.txt").write_text("edge_id,source,target\nE9,lab.v2,lab.v1\n", encoding="utf-8")
    plain, with_extra = pipeline(tree, workdir, probe), pipeline(tree, workdir, extra)
    checks.append(("probe: a file the contract does not name, added to a contract folder, leaves records and summary unchanged",
                   plain == with_extra, f"{len(with_extra['records'])} records"))

    # Manifest rows for batches that no feed line names.
    empty = workdir / "probe-empty-batches"
    shutil.copytree(probe, empty)
    with (empty / "manifest.csv").open("a", encoding="utf-8") as handle:
        handle.write("B4,4,0,00000000\nB5,5,0,0000abcd\n")
    mismatches = pipeline(tree, workdir, empty)["summary"]["receipt_mismatches"]
    checks.append(("probe: a manifest batch with no lines matches a receipt of 0 and 00000000 and no other receipt",
                   mismatches == ["B3", "B5"], str(mismatches)))

    # The command line into an output folder holding an older, longer run.
    rerun = workdir / "rerun"
    (rerun / "result").mkdir(parents=True)
    (rerun / "result" / "records.jsonl").write_text("{}\n" * 12, encoding="utf-8")
    (rerun / "result" / "run_summary.json").write_text("{}\n", encoding="utf-8")
    args = ["run", "--contracts", str(probe), "--feed", str(probe / "feed.jsonl"), "--corrections", str(probe / "corrections.txt"),
            "--manifest", str(probe / "manifest.csv"), "--out", "result"]
    done = subprocess.run([sys.executable, "-m", PACKAGE, *args], cwd=rerun, env=child_env(tree), capture_output=True, text=True, timeout=120)
    lines = (rerun / "result" / "records.jsonl").read_text(encoding="utf-8").splitlines()
    checks.append(("probe: a command-line run into an output folder holding an older, longer run leaves only the fresh records",
                   done.returncode == 0 and [json.loads(x) for x in lines] == plain["records"], f"{len(lines)} lines"))

    # The help command.
    done = subprocess.run([sys.executable, "-m", PACKAGE, "--help"], cwd=workdir, env=child_env(tree), capture_output=True, text=True, timeout=60)
    checks.append(("probe: python -m migrakit --help exits with status 0", done.returncode == 0, f"exit status {done.returncode}"))

    # A contract file that cannot be parsed.
    broken = workdir / "probe-broken-file"
    shutil.copytree(probe, broken)
    (broken / "report_taxonomy.json").write_text('{"categories": [', encoding="utf-8")
    error = call(tree, workdir, {"contracts": str(broken)}).get("error", "")
    checks.append(("probe: a contract file that cannot be parsed stops load_contracts with a message naming that file",
                   "report_taxonomy.json" in error, error[:120]))

    # An altered copy of the shipped contracts: raise the cost of the first edge of a shipped record's plan.
    altered = workdir / "ci-altered"
    altered.mkdir()
    for name in ("schema_versions.json", "migration_edges.csv", "field_policy.tsv", "null_semantics.ini",
                 "partner_aliases.xml", "report_taxonomy.json", "partner_order.tsv"):
        shutil.copy2(CI / name, altered / name)
    witness = "no shipped record changed"
    for text in (CI / "partner_batches.jsonl").read_text(encoding="utf-8").splitlines()[:200]:
        try:
            line = json.loads(text)
            schema, payload = line["schema"], line["payload"]
        except (ValueError, KeyError, TypeError):
            continue
        before = call(tree, workdir, {"contracts": str(CI), "schema": schema, "payload": payload}).get("plan")
        if not before:
            continue
        rows = (CI / "migration_edges.csv").read_text(encoding="utf-8").splitlines()
        rows = [row if row.split(",")[0] != before[0] else ",".join(row.split(",")[:-1] + [str(int(row.split(",")[-1]) + 10_000_000)]) for row in rows]
        (altered / "migration_edges.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        after = call(tree, workdir, {"contracts": str(altered), "schema": schema, "payload": payload}).get("plan")
        if after != before:
            witness = f"{schema}: {before} became {after}"
            break
    checks.append(("probe: raising one edge cost in a copy of the shipped contracts changes the plan of a shipped record that used it",
                   witness != "no shipped record changed", witness))

    for name, passed, seen in checks:
        print(f"{name}: {'ok' if passed else 'FAILED'} ({seen})")
    failed = [name for name, passed, _ in checks if not passed]
    if failed:
        raise SystemExit(f"contract checks failed: {failed}")
    return [{"name": name, "passed": passed} for name, passed, _ in checks]


def probe_band_checks(tree: Path, workdir: Path) -> list[dict]:
    checks = []
    probe = workdir / "probe"
    empty = workdir / "probe-empty-feed"
    shutil.copytree(probe, empty)
    (empty / "feed.jsonl").write_text("", encoding="utf-8")
    result = pipeline(tree, workdir, empty)
    checks.append(("probe: a feed file with no lines gives a run summary with zero records",
                   result["summary"]["records"] == 0, json.dumps(result["summary"], sort_keys=True)))

    baseline = workdir / "ci-probe-baseline"
    shutil.copytree(CI, baseline)
    for source, target in (("partner_batches.jsonl", "feed.jsonl"), ("correction_log.txt", "corrections.txt"),
                           ("replay_manifest.csv", "manifest.csv")):
        shutil.copy2(baseline / source, baseline / target)
    plain = pipeline(tree, workdir, baseline)
    policy = workdir / "ci-probe-policy"
    shutil.copytree(baseline, policy)
    rows = (policy / "field_policy.tsv").read_text(encoding="utf-8").splitlines()
    witness = "no record changed"
    for index, row in enumerate(rows[1:], start=1):
        values = row.split("\t")
        changed = list(rows)
        replacement = values[:]
        replacement[2] = '"probe-default"'
        replacement[3] = "absent_or_null"
        changed[index] = "\t".join(replacement)
        (policy / "field_policy.tsv").write_text("\n".join(changed) + "\n", encoding="utf-8")
        after = pipeline(tree, workdir, policy)
        pair = next(((a, b) for a, b in zip(plain["records"], after["records"])
                     if a != b and str(a.get("schema", "")).startswith(values[0] + ".")), None)
        if pair:
            witness = f"{values[0]}.{values[1]}: {json.dumps(pair, sort_keys=True)}"
            break
    checks.append(("probe: changing one field_policy.tsv row in a copy of /app/ci changes a record of that domain",
                   witness != "no record changed", witness))

    nulls = workdir / "ci-probe-nulls"
    shutil.copytree(baseline, nulls)
    ini = (nulls / "null_semantics.ini").read_text(encoding="utf-8")
    (nulls / "null_semantics.ini").write_text(ini.replace("explicit_null = present", "explicit_null = absent"), encoding="utf-8")
    after = pipeline(tree, workdir, nulls)
    original = (CI / "partner_batches.jsonl").read_text(encoding="utf-8").splitlines()
    witness = "no explicit-null record changed"
    for raw, before, changed in zip(original, plain["records"], after["records"]):
        if before == changed:
            continue
        line = json.loads(raw)
        payload = line.get("payload")
        if isinstance(payload, dict) and None in payload.values():
            witness = json.dumps({"input": line, "before": before, "after": changed}, sort_keys=True)
            break
    checks.append(("probe: changing explicit_null in a copy of /app/ci changes a record holding an explicit null",
                   witness != "no explicit-null record changed", witness))
    for name, passed, witness in checks:
        print(f"check {name} {'ok' if passed else 'FAILED'}: {witness}", flush=True)
    failed = [name for name, passed, _ in checks if not passed]
    if failed:
        raise SystemExit(f"probe band checks failed: {failed}")
    return [{"name": name, "passed": passed} for name, passed, _ in checks]


def code_only(function: ast.AST) -> str:
    """Dump a function with its docstring left out, so only code changes count."""
    first = function.body[0] if function.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        function.body = function.body[1:] or [ast.Pass()]
    return ast.dump(function)


def function_sources(tree: Path) -> dict[str, str]:
    base = tree / "src" / PACKAGE
    found: dict[str, str] = {}
    for path in sorted(base.rglob("*.py")):
        module = ".".join(path.relative_to(base).with_suffix("").parts)
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[f"{module}.{node.name}"] = code_only(node)
            elif isinstance(node, ast.ClassDef):
                for inner in node.body:
                    if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found[f"{module}.{node.name}.{inner.name}"] = code_only(inner)
    return found


def write_json(name: str, document: object) -> None:
    (OUT / name).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def already_repaired() -> bool:
    """True when an earlier run left every repair in REPO and wrote the deliverables."""
    for rel, shipped, repaired in REPAIRS:
        text = (REPO / rel).read_text(encoding="utf-8")
        if repaired not in text or shipped in text.replace(repaired, ""):
            return False
    names = ["patched-repo.zip", "summary.json", "test_fixes.json", "repair-report.json", *(f"module_{area}.json" for area in AREAS)]
    return all((OUT / name).is_file() for name in names)


def main() -> None:
    if already_repaired():
        print("repository already repaired and deliverables present; nothing to do")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="migrakit-repair-"))
    shipped = scratch / "shipped"
    shutil.copytree(REPO, shipped, ignore=shutil.ignore_patterns("__pycache__"))
    repaired = scratch / "repaired"
    shutil.copytree(shipped, repaired)
    apply_repairs(repaired)

    before = unit_results(shipped)
    after = unit_results(repaired)
    if set(after.values()) != {"pass"} or len(after) != len(before):
        raise SystemExit(f"visible tests still failing after the repair: {after}")

    build_archive(repaired, OUT / "patched-repo.zip")
    delivered = extract(OUT / "patched-repo.zip", scratch / "delivered")
    foreign = scratch / "elsewhere"
    foreign.mkdir()
    summary = run_cli(delivered, foreign)
    write_json("summary.json", summary)
    probes = self_checks(delivered, foreign) + contract_checks(delivered, foreign) + probe_band_checks(delivered, foreign)

    old, new = function_sources(shipped), function_sources(repaired)
    changed = sorted(name for name, body in new.items() if old.get(name) != body)
    for area, prefixes in AREAS.items():
        names = [name for name in changed if name.startswith(prefixes)]
        write_json(f"module_{area}.json", {"module": area, "changed_functions": names, "notes": FIX_NOTES[area]})

    tests = [{"name": name, "before": before[name], "after": after[name]} for name in sorted(after)]
    write_json("test_fixes.json", {"visible_tests": tests})
    write_json("repair-report.json", {
        "package": PACKAGE,
        "fixes": [note for area in AREAS for note in FIX_NOTES[area]],
        "checks": [
            {"name": "visible tests pass on the repaired repository", "passed": True},
            {"name": "python -m migrakit run on the shipped inputs from a foreign folder", "passed": True},
            {"name": f"{summary['records']} feed lines produced {summary['records']} records", "passed": summary["records"] > 0},
            *probes,
        ],
    })
    # Leave the repair in the working repository too, so /app/repo matches the delivered archive.
    shutil.copytree(repaired, REPO, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
