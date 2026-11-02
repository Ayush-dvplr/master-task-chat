#!/usr/bin/env python3
"""Reference solution for b28ebc90-3080-5d41-9f01-e02549d3efaf.

The shipped daybreak package is extracted from the working papers, each
catalogued defect is repaired in place by a targeted edit to the shipped
source, the repaired tree is delivered as an archive, and the repaired
package is then driven over the same working papers to publish the twenty
eight derived documents.

Nothing here reimplements the routing chain. The whole derivation lives in
the repaired package, which is what the contract asks for: the deliverable is
a package that works, not a script that happens to produce one cycle.

Each repair is written from the stage paper it restores, in this file's own
words, rather than copied from any other tree. Where a rule admits only one
edit (a swapped key order, a wrong record name) the edit is that one.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DATA = Path("/app/data")
WORK = Path("/app/project")
OUT = Path("/app/out")

ALLOCATE = "src/daybreak/allocate.py"
LOADING = "src/daybreak/loading.py"
PUBLISH = "src/daybreak/publish.py"
STAGES = "src/daybreak/stages.py"
UTIL = "src/daybreak/util.py"

REPAIRS = (
    ("DFC-01", LOADING,
     "        if limit is None:\n            continue\n",
     "        if limit is None or rev > limit:\n            continue\n"),
    ("DFC-02", STAGES,
     "    return text is None or str(text).strip() in (\"\", ABSENT, \"0\")\n",
     "    return text is None or str(text).strip() in {\"\", ABSENT}\n"),
    ("DFC-03", STAGES,
     "        start = delta\n        cursor = start\n",
     "        cursor += delta\n        start = cursor\n"),
    ("DFC-04", STAGES,
     "                    if win[\"start_ms\"] <= trigger <= win[\"end_ms\"]:\n",
     "                    if win[\"start_ms\"] <= trigger and trigger < win[\"end_ms\"]:\n"),
    ("DFC-05", STAGES,
     "        if entry[\"remaining\"] > 0 and trigger <= entry[\"expires_ms\"]:\n",
     "        if entry[\"remaining\"] > 0 and entry[\"expires_ms\"] > trigger:\n"),
    ("DFC-06", STAGES,
     "    oneshot = {}\n    for rec in data[\"overrides\"]:\n",
     "    oneshot = {}\n    remaining = data[\"snapshot\"].get(\"oneshot_remaining\", {})\n"
     "    for rec in data[\"overrides\"]:\n"),
    ("DFC-06", STAGES,
     "                 \"remaining\": int(rec.get(\"remaining\", 0))}\n",
     "                 \"remaining\": int(remaining[oid] if oid in remaining\n                                  else rec.get(\"remaining\", 0))}\n"),
    ("DFC-07", STAGES,
     "    first = Fraction(action[\"energy_mwh\"] * intensity, 10000)\n    second = half_even(first * Fraction(scale, 10000))\n",
     "    first = half_even(Fraction(action[\"energy_mwh\"] * intensity, 10000))\n    second = half_even(first * Fraction(scale, 10000))\n"),
    ("DFC-08", ALLOCATE,
     "        if rec[\"demand\"][\"demand_mwh\"] < pool:\n",
     "        if rec[\"demand\"][\"demand_mwh\"] <= pool:\n"),
    ("DFC-09", ALLOCATE,
     "        else:\n            rejected.append(rec)\n            break\n    return taken, rejected, pool\n",
     "        else:\n            rejected.append(rec)\n    return taken, rejected, pool\n"),
    ("DFC-10", ALLOCATE,
     "        candidates = list(by_group[key])\n",
     "        candidates = list(incumbents) + list(by_group[key])\n"),
    ("DFC-11", PUBLISH,
     "    for oid, used in r13[\"consumed\"].items():\n",
     "    for oid, used in r13b[\"consumed\"].items():\n"),
    ("DFC-12", STAGES,
     "            ranked.append((\n                -_tier_of(e[\"dependent\"], tier_index, fallback_tier),\n                e[\"strength_bp\"],\n",
     "            ranked.append((\n                e[\"strength_bp\"],\n                -_tier_of(e[\"dependent\"], tier_index, fallback_tier),\n"),
    ("DFC-13", LOADING,
     "        if len(head) >= 2 and head[0] == \"grid_key\" and live is None:\n            live = rows\n",
     "        if len(head) >= 2 and (head[0], head[1]) == (\"grid_key\", cycle_key):\n            live = rows\n"),
    ("DFC-14", STAGES,
     "    rec = routine_layer.get(rid, {})\n    if \"max_occurrences\" in rec:\n        return rec[\"max_occurrences\"], \"routine\"\n    cap = data[\"memo_caps\"].get(rid)\n    if cap is not None:\n        return cap, \"memo\"\n",
     "    cap = data[\"memo_caps\"].get(rid)\n    if cap is not None:\n        return cap, \"memo\"\n    rec = routine_layer.get(rid, {})\n    if \"max_occurrences\" in rec:\n        return rec[\"max_occurrences\"], \"routine\"\n"),
    ("DFC-15", STAGES,
     "    out = {}\n    cursor = 0\n    for row in data[\"context_spans\"]:\n",
     "    out = {}\n    cursor = int(data[\"header\"][\"origin_ms\"])\n    for row in data[\"context_spans\"]:\n"),
    ("DFC-16", STAGES,
     "    frozen = int(data[\"header\"][\"frozen_revision_window_grid\"])\n",
     "    frozen = int(data[\"snapshot\"][\"frozen_revision_cooldown_register\"])\n"),
    ("DFC-17", STAGES,
     "    live = live_rows(rows, \"window_id\", lambda k: frozen)\n",
     "    per_window = data[\"header\"][\"window_frozen_revisions\"]\n    live = live_rows(rows, \"window_id\", per_window.get)\n"),
    ("DFC-18", PUBLISH,
     "    for iid in by_id:\n        aid = by_id[iid][\"action_id\"]\n",
     "    for iid in r05[\"eligible\"]:\n        aid = by_id[iid][\"action_id\"]\n"),
    ("DFC-19", PUBLISH,
     "        if cur is None or idx != cur[0]:\n",
     "        if cur is None or cur[0] < idx:\n"),
    ("DFC-20", ALLOCATE,
     "        demand = (r09[\"by_instance\"].get(iid)\n                  or r12[\"proposal_index\"][iid][\"demand\"])\n",
     "        if iid not in r09[\"by_instance\"]:\n            continue\n        demand = r09[\"by_instance\"][iid]\n"),
    ("DFC-21", UTIL,
     "    return Path(path).read_bytes().decode(\"utf-8\")\n",
     "    return Path(path).read_bytes().decode(\"utf-8-sig\")\n"),
    ("DFC-22", UTIL,
     "    lines = [ln for ln in read_text(path).split(\"\\n\") if ln.strip() != \"\"]\n"
     "    header = [name.strip() for name in lines[0].split(sep)]\n"
     "    return [dict(zip(header, ln.split(sep))) for ln in lines[1:]]\n",
     "    import csv\n    import io\n"
     "    text = read_text(path)\n"
     "    records = [rec for rec in csv.reader(io.StringIO(text, newline=\"\"),\n"
     "                                         delimiter=sep)\n"
     "               if any(field.strip() for field in rec)]\n"
     "    return [dict(zip(records[0], rec)) for rec in records[1:]]\n"),
    ("DFC-23", STAGES,
     "    applicable.append((\"global\", layers[\"global\"]))\n",
     "    applicable.append((\"global\", layers[\"global\"]))\n"
     "    applicable.sort(key=lambda pair: layers[\"ranks\"][pair[0]])\n"),
    ("DFC-24", ALLOCATE,
     "    cap = 2\n",
     "    cap = int(data[\"directive\"][\"round_cap\"])\n"),
)

NOTES = {
    "DFC-01": "r02 - the live row is the greatest revision at or below the frozen one, not the greatest revision present",
    "DFC-02": "r03 - a written zero settles a field; only a hyphen or an empty cell records absence",
    "DFC-03": "r02 - the window grid records a start difference, so the starts accumulate",
    "DFC-04": "r03 - a window end is exclusive, so a trigger on it belongs to the next window",
    "DFC-05": "r04 - a one shot override applies strictly before its expiry",
    "DFC-06": "r04 - the snapshot remaining count outranks the journal's own field",
    "DFC-07": "r09 - the demand rounds after each of the two products",
    "DFC-08": "r10 - a demand equal to the pool fits and binds it",
    "DFC-09": "r10 - a candidate that does not fit is displaced and the next candidate is still considered",
    "DFC-10": "r12 - every round is offered to the current holders and that round's proposals together",
    "DFC-11": "r13 - a one shot override is consumed by the pass over the survivors of r14",
    "DFC-12": "r07 - least edge strength settles the removal before tier is consulted",
    "DFC-13": "r10 - the live grid is the one whose key cell equals the cycle key",
    "DFC-14": "r03 - the memo cap settles the occurrence cap ahead of the routine layer",
    "DFC-15": "r02 - the context chain takes its first difference from origin_ms, never from zero",
    "DFC-16": "r04 - class floors are live against the cooldown register's own frozen revision in the snapshot",
    "DFC-17": "r02 - each window is live against its own frozen revision, not the grid-wide maximum",
    "DFC-18": "r07 - a dependent's tier is the least tier over its eligible instances",
    "DFC-19": "r14 - prior consumption is the ledger row with the greatest cycle index, wherever it sits",
    "DFC-20": "r14 - a kept fallback proposal draws from its pool exactly once",
    "DFC-21": "r02 - a byte order mark is not part of a paper's first field",
    "DFC-22": "r02 - a double quoted field keeps its separator as text",
    "DFC-23": "r04 - the layers are consulted in the rank order of the directive's part A",
    "DFC-24": "r12 - the round cap is the directive's part C figure, counting r10 as round one",
}

# The top level function of the shipped project each departure sat in.
# A function that departs from two rules takes two rows: the second rule of
# DFC-22 is first met at r04, where cooldown_register.psv carries CR endings.
SECOND_RULES = {
    "DFC-22": "r04 - a carriage return ends a line rather than a field",
}

FUNCTIONS = {
    "DFC-01": "loading.live_rows", "DFC-02": "stages._absent",
    "DFC-03": "stages.window_grid", "DFC-04": "stages.stage_r03",
    "DFC-05": "stages.resolve_policy", "DFC-06": "stages._layer_records",
    "DFC-07": "stages.demand_of", "DFC-08": "allocate._select",
    "DFC-09": "allocate._select", "DFC-10": "allocate.stage_r12",
    "DFC-11": "publish.render", "DFC-12": "stages.stage_r07",
    "DFC-13": "loading.read_workbook", "DFC-14": "stages._routine_cap",
    "DFC-15": "stages.context_grid", "DFC-16": "stages.cooldown_floors",
    "DFC-17": "stages.window_grid", "DFC-18": "publish.run_chain",
    "DFC-19": "publish.render", "DFC-20": "allocate.stage_r14",
    "DFC-21": "util.read_text", "DFC-22": "util.read_delim",
    "DFC-23": "stages.resolve_policy", "DFC-24": "allocate.stage_r12",
}


DOCUMENT_COUNT = 28
REPAIR_RECORDS = ("build_report", "selftest", "defect_register",
                  "verification_notes")


def extract():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(DATA / "project.zip") as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith("/") or ".." in name.split("/"):
                raise SystemExit("unsafe archive member: " + name)
        zf.extractall(WORK)


def repair():
    applied = []
    for code, rel, broken, correct in REPAIRS:
        path = WORK / rel
        text = path.read_text(encoding="utf-8")
        if text.count(broken) != 1:
            raise SystemExit(code + ": anchor is not present exactly once in "
                             + rel)
        path.write_text(text.replace(broken, correct), encoding="utf-8")
        if all(row["defect"] != code for row in applied):
            applied.append({"defect": code, "module": rel,
                            "note": NOTES[code]})
    return applied


def deliver():
    OUT.mkdir(parents=True, exist_ok=True)
    names = []
    for path in sorted(WORK.rglob("*")):
        if path.is_file():
            names.append(str(path.relative_to(WORK)))
    stamp = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(OUT / "package.zip", "w",
                         zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, (WORK / name).read_bytes())
    return names


def run_chain():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORK / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "daybreak",
                           "--data", str(DATA), "--out", str(OUT)],
                          capture_output=True, text=True, env=env,
                          cwd=str(WORK))
    if proc.returncode != 0:
        raise SystemExit("repaired package failed: "
                         + proc.stderr.strip()[-800:])


def selftest():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORK / "src")
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover",
                           "-s", str(WORK / "tests"), "-q"],
                          capture_output=True, text=True, env=env,
                          cwd=str(WORK))
    return {"command": "python3 -m unittest discover -s tests -q",
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "output_tail": proc.stderr.strip().splitlines()[-1:]}


def figures():
    """The start of the last window and the count per suppression reason,
    read from what the repaired package published."""
    rows = (OUT / "suppression_ledger.csv").read_text(
        encoding="utf-8").splitlines()[1:]
    counts = {}
    for row in rows:
        reason = row.split(",")[1]
        counts[reason] = counts.get(reason, 0) + 1
    lines = ["last_window_start_ms " + str(last_window_start())]
    for reason in sorted(counts):
        lines.append("set_aside " + reason + " " + str(counts[reason]))
    return lines


def last_window_start():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORK / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = ("import json, sys\n"
             "from daybreak.loading import load_all\n"
             "from daybreak.stages import window_grid\n"
             "grid = window_grid(load_all(sys.argv[1]))\n"
             "rows = grid.values() if isinstance(grid, dict) else grid\n"
             "last = max(rows, key=lambda w: int(w['ordinal']))\n"
             "print(last['start_ms'])\n")
    proc = subprocess.run([sys.executable, "-c", probe, str(DATA)],
                          capture_output=True, text=True, env=env,
                          cwd=str(WORK))
    if proc.returncode != 0:
        raise SystemExit("window grid probe failed: "
                         + proc.stderr.strip()[-400:])
    return int(proc.stdout.strip().splitlines()[-1])


def main():
    extract()
    applied = repair()
    names = deliver()
    run_chain()
    result = selftest()
    published = sorted(p.name for p in OUT.iterdir()
                       if p.is_file() and p.suffix != ".zip"
                       and p.stem not in REPAIR_RECORDS)
    if len(published) != DOCUMENT_COUNT:
        raise SystemExit("the repaired package published "
                         + str(len(published)) + " documents beside the"
                         " archive rather than " + str(DOCUMENT_COUNT))
    (OUT / "selftest.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + chr(10),
                                       encoding="utf-8")
    (OUT / "build_report.json").write_text(json.dumps({
        "archive": "package.zip",
        "archive_members": len(names),
        "modules_repaired": sorted({row["module"] for row in applied}),
        "defects_repaired": [row["defect"] for row in applied],
        "entry_point": "python3 -m daybreak --data <papers> --out <destination>",
        "documents_published": DOCUMENT_COUNT,
        "third_party_imports": [],
    }, indent=2, sort_keys=True) + chr(10), encoding="utf-8")
    lines = ["# Defect register", "",
             "One row per departure, the stage whose paper states the rule,",
             "the function it sat in, and the rule restored.", "",
             "| defect | stage | function | rule restored |",
             "| --- | --- | --- | --- |"]
    for row in applied:
        stage, rule = row["note"].split(" - ", 1)
        lines.append("| " + row["defect"] + " | " + stage.split()[0] + " | "
                     + FUNCTIONS[row["defect"]] + " | " + rule + " |")
        if row["defect"] in SECOND_RULES:
            stage, rule = SECOND_RULES[row["defect"]].split(" - ", 1)
            lines.append("| " + row["defect"] + " | " + stage + " | "
                         + FUNCTIONS[row["defect"]] + " | " + rule + " |")
    lines += ["", "Defects repaired: " + str(len(applied)) + "."]
    (OUT / "defect_register.md").write_text(chr(10).join(lines) + chr(10),
                                            encoding="utf-8")
    notes = ["# Verification notes", "",
             "- The shipped package was extracted from",
             "  `/app/data/project.zip` and repaired in place at each",
             "  catalogued anchor. No module was replaced wholesale.",
             "- The shipped `tests` tree was carried through unchanged and",
             "  still passes; it exercises the helpers, not the chain, so a",
             "  green suite says nothing about the chain being right.",
             "- The repaired package was driven over `/app/data` through its",
             "  module entry point and published "
             + str(DOCUMENT_COUNT) + " documents.",
             "- Both digests in `run_manifest.txt` were taken over the bytes",
             "  already written, the publication digest over the manifest",
             "  body before the trailers were appended.",
             "- The paper directory was left as it was found and nothing",
             "  outside the destination was written.",
             "",
             "Figures of the cycle in `/app/data`, read back from the",
             "published documents:",
             ""] + figures() + [""]
    (OUT / "verification_notes.md").write_text(chr(10).join(notes),
                                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
