"""Round 1: score single-defect variants on the tests channel (stub rewardkit).

    python3 measure_variants.py <oracle app dir> <scratch dir>

Each variant is repo_fixed plus one shipped defect group (or one inline wrong
reading). Its patched-repo.zip replaces the oracle's archive; the other
artifacts stay the oracle's, so the scores isolate run behaviour.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import make_shipped as ms
from verify_visible import GROUPS, tree

WORK = Path(__file__).resolve().parent
INLINE = {
    "W_alias_before_id": ("src/migrakit/parser/identity.py",
        "    if value in registry.partners:\n        partner_id = value\n    elif value in registry.aliases:\n        partner_id = registry.aliases[value]\n",
        "    if value in registry.aliases:\n        partner_id = registry.aliases[value]\n    elif value in registry.partners:\n        partner_id = value\n"),
    "W_corrections_sorted_by_id": ("src/migrakit/core/executor.py",
        "        for correction in pinned.get(schema, ()):",
        "        for correction in sorted(pinned.get(schema, ()), key=lambda c: c[\"id\"]):"),
    "W_tokens_after_planning": ("src/migrakit/pipeline.py",
        "            plan = plan_migration(self.registry, document[\"schema\"], payload)",
        "            plan = plan_migration(self.registry, document[\"schema\"], document[\"payload\"])"),
    # P12 r3 (AL-27): one stated rule broken each.
    "W_cast_int_drops_integral_float": ("src/migrakit/core/operations.py",
        "        if isinstance(value, float) and value.is_integer():\n            return int(value)\n", ""),
    "W_cast_touches_null": ("src/migrakit/core/operations.py",
        "    if view.state(name) == VALUE:\n        record[name] = _convert(record[name], target_type)\n",
        "    if view.state(name) != ABSENT:\n        record[name] = \"None\" if record[name] is None and target_type == \"str\" else _convert(record[name], target_type)\n"),
    "W_cast_converts_booleans": ("src/migrakit/core/operations.py",
        "    if isinstance(value, bool):\n        return value\n", ""),
    "W_fingerprint_ascii_escaped": ("src/migrakit/core/fingerprint.py",
        "        ensure_ascii=False,\n", "        ensure_ascii=True,\n"),
    "W_schema_before_partner": ("src/migrakit/pipeline.py",
        "        record = _blank_record(item.line, document)\n        try:\n",
        "        record = _blank_record(item.line, document)\n        if document[\"schema\"] not in self.registry.schemas:\n"
        "            record[\"code\"] = \"E_UNKNOWN_SCHEMA\"\n            return record\n        try:\n"),
    "W_partner_before_batch": ("src/migrakit/pipeline.py",
        "            rejected[\"code\"] = \"E_PARSE\"\n",
        "            rejected[\"code\"] = \"E_PARSE\"\n            if item.record is not None:\n                try:\n"
        "                    resolve_partner(registry, item.record[\"partner\"])\n                except MigrationError as exc:\n"
        "                    rejected = _blank_record(item.line, item.record)\n                    rejected[\"code\"] = exc.code\n"),
    "W_holder_needs_known_schema": ("src/migrakit/pipeline.py",
        "        self.holders[identity] = record\n        self._migrate(record, document, identity)\n",
        "        self._migrate(record, document, identity)\n        if record[\"code\"] != \"E_UNKNOWN_SCHEMA\":\n            self.holders[identity] = record\n"),
    # Harden P9 r1: one new-lever reading each.
    "W_receipt_make_it_match": ("src/migrakit/pipeline.py",
        "        record = _blank_record(item.line, document)\n        try:\n",
        "        record = _blank_record(item.line, document)\n"
        "        record[\"fingerprint\"] = record_fingerprint(document[\"schema\"], document[\"payload\"])\n        try:\n"),
    "W_receipt_counts_parse_rejects": ("src/migrakit/pipeline.py",
        "        batch = records[item.line][\"batch\"]\n        if batch is None:\n            continue\n        document = item.record\n",
        "        batch = item.batch\n        if batch not in receipts:\n            continue\n"
        "        document = item.record\n        if document is None:\n            counts[batch] = counts.get(batch, 0) + 1\n            continue\n"),
    "W_receipt_skips_rejected": ("src/migrakit/pipeline.py",
        "        batch = records[item.line][\"batch\"]\n        if batch is None:\n            continue\n",
        "        batch = records[item.line][\"batch\"]\n        if batch is None:\n            continue\n"
        "        if records[item.line][\"fingerprint\"] is None:\n            counts[batch] = counts.get(batch, 0) + 1\n            continue\n"),
    "W_receipt_always_empty": ("src/migrakit/pipeline.py",
        "    summary[\"receipt_mismatches\"] = _receipt_mismatches(items, records, receipts)\n",
        "    summary[\"receipt_mismatches\"] = []\n"),
}


def package(src_tree: Path, oracle: Path, app: Path, add_main: bool = True) -> None:
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(oracle, app)
    main = src_tree / "src/migrakit/__main__.py"
    if add_main and not main.exists():
        main.write_text((ms.FIXED / "src/migrakit/__main__.py").read_text())
    archive = app / "out" / "patched-repo.zip"
    archive.unlink()
    with zipfile.ZipFile(archive, "w") as zf:
        for path in sorted(p for p in src_tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            zf.write(path, path.relative_to(src_tree).as_posix())


def score(app: Path, out: Path) -> dict:
    subprocess.run([sys.executable, str(WORK / "run_checks.py"), str(app), str(out)], capture_output=True, text=True, timeout=1200,
                   env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"})
    result = json.loads(out.read_text())
    lost = sorted(n for n, c in result["checks"].items() if c["weight"] > 0 and not c["pass"])
    hit = sorted(n for n, c in result["checks"].items() if c["weight"] < 0 and c["pass"])
    return {"score": round(result["score"], 4), "lost": lost, "negatives_fired": hit}


def edit(dest: Path, rel: str, old: str, new: str) -> None:
    path = dest / rel
    text = path.read_text()
    assert text.count(old) == 1, (rel, old[:60])
    path.write_text(text.replace(old, new))


def inline(name: str, dest: Path) -> None:
    tree(dest, [])
    edit(dest, *INLINE[name])


def main() -> None:
    oracle, scratch = Path(sys.argv[1]), Path(sys.argv[2])
    scratch.mkdir(parents=True, exist_ok=True)
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else ["shipped", *GROUPS, "F15 cli"]
    report = {}
    for name in names:
        dest = scratch / "tree"
        if name == "shipped":
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(ms.SHIPPED, dest)
        elif name in GROUPS or name == "F15 cli":
            tree(dest, GROUPS.get(name, [16]))
        else:
            inline(name, dest)
        package(dest, oracle, scratch / "app", add_main=name not in ("shipped", "F15 cli"))
        report[name] = score(scratch / "app", scratch / "result.json")
        print(name, json.dumps(report[name]), flush=True)
    (scratch / "variants.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
