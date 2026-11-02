"""Override-removal probe (G9): drop each correction source and show the outputs move.

Usage: python3 -B override_probe.py DATA_DIR SOLVE_PY SCRATCH
Variants: no_revised (empty revised availability table), no_notice_closures
(empty closure table), no_calendar_closed (calendar CLOSED rows removed).
Prints one PROBE line per variant with the files that changed.
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datagen as g  # noqa: E402


def run(data, out):
    subprocess.run([sys.executable, "-B", SOLVE, data, out], check=True)
    return {n: json.load(open(os.path.join(out, n))) for n in sorted(os.listdir(out))}


def notice(path, closures, revised):
    g.write_docx(path, [("p", "Disruption notice"), ("p", "Base closures"),
                        ("tbl", [["base", "from", "days"]] + closures),
                        ("p", "Revised availability"), ("tbl", [["tail", "available_from"]] + revised)])


DATA, SOLVE, SCR = sys.argv[1:4]
base = run(DATA, os.path.join(SCR, "base_out"))
t = {k: [list(r.values()) for r in v] for k, v in g._docx_tables(os.path.join(DATA, "disruption_notice.docx")).items()}
variants = {
    "no_revised": ("notice", t["base/from"], []),
    "no_notice_closures": ("notice", [], t["tail/available_from"]),
    "no_calendar_closed": ("calendar", None, None),
}
for name, (kind, c, r) in variants.items():
    d = os.path.join(SCR, name)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(DATA, d)
    if kind == "notice":
        notice(os.path.join(d, "disruption_notice.docx"), c, r)
    else:
        p = os.path.join(d, "base_calendar.jsonl")
        keep = [x for x in open(p) if json.loads(x)["status"] != "CLOSED"]
        open(p, "w").writelines(keep)
    got = run(d, os.path.join(SCR, name + "_out"))
    moved = [n for n in base if base[n] != got[n]]
    print("PROBE", name, "changed:", ",".join(moved) or "NONE")
