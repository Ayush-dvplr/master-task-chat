"""One mutant per stated rule: patch a copy of the oracle app, rebuild, grade with the local stub.

usage: mutants.py <oracle app> <scratch root> [name ...]
Prints `MUTANT <name> | <rule> | lost <points> | failed <checks>` per mutant, then ALL_DONE.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
P, C, R, M, I = "src/task/parser.py", "src/task/core.py", "src/task/report.py", "src/task/__main__.py", "src/task/__init__.py"

# name: (rule as written in api_contract.md, [(file, old, new)], extra)
MUTANTS = {
    "closed_kept": ("57 closed links removed before any other rule", [(P, 'if rec["link"] in closed:', 'if rec["link"] in ():')], {}),
    "tariff_no_base": ("58-59 cost = base + per_km x km", [(P, 'band["base"] + band["per_km"] * rec["km"]', 'band["per_km"] * rec["km"]')], {}),
    "override_case": ("39-42 override keys exact spelling and case", [(P, "    activation.optionxform = str\n", "")], {}),
    "override_ignored": ("59-60 override charge wins over class charge", [(P, 'overrides.get(f"{pid}/{r[\'site\']}", classes[r["class"]])', 'classes[r["class"]]')], {}),
    "slot_text": ("49-53 slot ranked as a number", [(P, 'int(row["slot"])', 'row["slot"]')], {}),
    "corridor_alpha": ("49-53 corridors ranked by their place in order", [(P, 'enumerate(rules["corridors"]["order"])', 'enumerate(sorted(rules["corridors"]["order"]))')], {}),
    "unknown_before_dup": ("64-69 E_DUP_SITE before E_UNKNOWN_ENDPOINT", [(P, "            ids = [r[\"site\"] for r in rows]\n", "            ids = [r[\"site\"] for r in rows]\n            if any(rec[\"link\"] not in closed and not {rec[\"a\"], rec[\"b\"]} <= set(ids) for rec in link_rows.get(pid, [])):\n                raise Rejected(\"E_UNKNOWN_ENDPOINT\")\n")], {}),
    "no_dup_check": ("67 E_DUP_SITE", [(P, "if len(set(ids)) != len(ids):\n                raise", "if False:\n                raise")], {}),
    "unknown_skipped": ("68-69 E_UNKNOWN_ENDPOINT", [(P, 'raise Rejected("E_UNKNOWN_ENDPOINT")\n        pa', 'continue\n        pa')], {}),
    "no_network_check": ("73-74 E_NO_NETWORK", [(P, "if not project.cold <= reached:", "if False:")], {}),
    "missing_unchecked": ("19-22 E_MISSING_FILE <name>, non-zero exit", [(P, "        if not (root / name).is_file():\n            raise MissingBookFile(name)\n", "        pass\n")], {}),
    "missing_order": ("19-22 first missing file in list order", [(P, "for name in BOOK_FILES:", "for name in reversed(BOOK_FILES):")], {}),
    "missing_exit_zero": ("19-22 missing file gives non-zero exit", [(M, "return 2", "return 0")], {}),
    "kmb": ("87-88 quote is the smallest over all networks (LV-CC-1)", [], {"variant": "kmb"}),
    "perlink": ("80-85 each activated site charged once (LV-CC-3)", [], {"variant": "perlink"}),
    "no_tie_rule": ("88-92 tie: smaller link vector wins", [(C, "    if count > 1:\n        for lid", "    if False:\n        for lid")], {}),
    "tie_larger": ("88-92 tie: smaller link vector wins (reversed scan)", [(C, "for lid, _pa, _pb, _cost in sorted(project.links):", "for lid, _pa, _pb, _cost in sorted(project.links, reverse=True):")], {}),
    "book_smaller_end": ("100 link booked to larger-position end", [(C, "            lines[pb] += cost", "            lines[pa] += cost")], {}),
    "depot_line": ("101-103 depot line = its activation charge", [(R, '"depot": {"total": lines[0], "share_bp": share_bp(lines[0], quote)}', '"depot": {"total": 0, "share_bp": 0}')], {}),
    "corridor_max": ("103-104 corridor total = sum of its activated sites' line totals", [(R, "corridors.get(corridor, 0) + total", "max(corridors.get(corridor, 0), total)")], {}),
    "share_round": ("104-106 share_bp rounded down", [(R, "return total * 10000 // quote", "return round(total * 10000 / quote)")], {}),
    "all_corridors": ("112-115 one entry per corridor with an activated site", [(R, "    for p, total in sorted(lines.items()):\n", "    for c in project.corridors[1:]:\n        corridors.setdefault(c, 0)\n    for p, total in sorted(lines.items()):\n")], {}),
    "all_sites": ("124-127 sites = activated non-depot sites", [(R, "    for p, total in sorted(lines.items()):\n", "    lines = {**{p: 0 for p in range(1, len(project.ids))}, **lines}\n    for p, total in sorted(lines.items()):\n")], {}),
    "sites_no_depot": ("120-123 sites count includes the depot", [(P, '"sites": len(self.ids),', '"sites": len(self.ids) - 1,')], {}),
    "links_open_only": ("120-123 links counts every row incl. closed", [(P, '"links": self.link_rows,', '"links": len(self.links),')], {}),
    "lists_descending": ("112-115 lists ascending", [(R, '"links": list(net.links)', '"links": list(reversed(net.links))')], {}),
    "summary_depot_out": ("128-132 depot_total", [(R, '"depot_total": sum(entry["depot"]["total"] for entry in reports.values()),', '"depot_total": 0,')], {}),
    "rejected_count": ("128-132 projects_rejected", [(R, '"projects_rejected": len(book["rejected"]),', '"projects_rejected": 0,')], {}),
    "writes_book_dir": ("12-17 book folder left unchanged", [(M, "    args.out.mkdir(", "    (args.book / '.quote-cache').write_text('x')\n    args.out.mkdir(")], {}),
    "no_version": ("3-6 task.VERSION equals manifest version", [(I, 'VERSION = "2.18.5"', 'VERSION = "0.0.0"')], {}),
    "pyproject_requests": ("3-6 standard library only (no dependencies)", [("pyproject.toml", "dependencies = []", 'dependencies = ["requests"]')], {}),
    "fixes_fail_only": ("137-143 previously_failing = FAIL or ERROR", [], {"fixes": "fail_only"}),
    "fixes_dup": ("137-143 each name once", [], {"fixes": "dup"}),
    "fixes_codes_null": ("137-143 regression_quotes rejected case gives its code", [], {"fixes": "codes_null"}),
    "zip_mode": ("158-164 archive mode", [], {"zip": {"mode": "0664"}}),
    "zip_time": ("158-164 archive timestamp", [], {"zip": {"timestamp": [2020, 1, 1, 0, 0, 0]}}),
    "zip_deflate": ("158-164 archive compression", [], {"zip": {"compression": "deflated"}}),
    "zip_unsorted": ("158-164 sorted members", [], {"zip": {"reverse": True}}),
    "zip_prefix": ("158-164 repo files at archive root", [], {"zip": {"prefix": "repo/"}}),
    "zip_pycache": ("158-164 no __pycache__ or .pyc", [], {"zip": {"pycache": True}}),
}


def rezip(app: Path, opts: dict) -> None:
    config = dict(json.loads((app / "ci/build_config.json").read_text())["archive"])
    config.update({k: v for k, v in opts.items() if k in ("mode", "timestamp", "compression")})
    out = app / "out/patched-repo.zip"
    out.unlink()
    method = zipfile.ZIP_STORED if config["compression"] == "stored" else zipfile.ZIP_DEFLATED
    repo = app / "repo"
    files = sorted((p for p in repo.rglob("*") if p.is_file() and "__pycache__" not in p.parts),
                   reverse=bool(opts.get("reverse")))
    with zipfile.ZipFile(out, "w") as archive:
        members = [(p.relative_to(repo).as_posix(), p.read_bytes()) for p in files]
        if opts.get("pycache"):
            members.append(("src/task/__pycache__/core.cpython-312.pyc", b"\x00" * 16))
        for name, body in members:
            info = zipfile.ZipInfo(opts.get("prefix", "") + name, tuple(config["timestamp"]))
            info.compress_type = method
            info.external_attr = (0o100000 | int(config["mode"], 8)) << 16
            archive.writestr(info, body)


def edit_fixes(app: Path, how: str) -> None:
    path = app / "out/test_fixes.json"
    doc = json.loads(path.read_text())
    log = (app / "ci/failing_tests.log").read_text()
    if how == "fail_only":
        doc["previously_failing"] = sorted(n for n in doc["previously_failing"] if f"{n} (" in log and
                                           any(l.startswith(n + " (") and l.endswith("... FAIL") for l in log.splitlines()))
    elif how == "dup":
        doc["previously_failing"] = sorted(doc["previously_failing"] + doc["previously_failing"][:1])
    elif how == "codes_null":
        doc["regression_quotes"] = {k: (v if isinstance(v, int) else None) for k, v in doc["regression_quotes"].items()}
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def build(oracle: Path, name: str, target: Path) -> None:
    _rule, patches, extra = MUTANTS[name]
    if "variant" in extra:
        subprocess.run([sys.executable, "-B", str(HERE / "variants.py"), str(oracle), extra["variant"], str(target)], check=True)
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(oracle, target)
    for rel, old, new in patches:
        path = target / "repo" / rel
        text = path.read_text()
        assert text.count(old) == 1, (name, rel, old)
        path.write_text(text.replace(old, new))
    if "fixes" in extra:
        edit_fixes(target, extra["fixes"])
        return
    rezip(target, extra.get("zip", {}))
    if patches:
        for doc in ("module_core.json", "module_parser.json", "module_report.json", "summary.json"):
            (target / "out" / doc).unlink()
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONPATH": str(target / "repo/src"), "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(target / "ci"), "--out", str(target / "out")],
                       env=env, capture_output=True)
        cache = target / "ci/.quote-cache"
        if cache.exists():
            cache.unlink()


def main() -> None:
    oracle, scratch = Path(sys.argv[1]), Path(sys.argv[2])
    names = sys.argv[3:] or list(MUTANTS)
    for name in names:
        target = scratch / name
        build(oracle, name, target)
        run = subprocess.run([sys.executable, "-B", str(HERE / "run_local_tests.py"), str(target)],
                             capture_output=True, text=True)
        rows = [line.split() for line in run.stdout.splitlines() if " w= " in line]
        lost, failed = 0, []
        fired = []
        for check, _w, weight, verdict, *_rest in rows:
            weight, ok = int(weight), verdict == "PASS"
            if weight > 0 and not ok:
                lost += weight
                failed.append(check)
            if weight < 0 and ok:
                fired.append(check)
        print(f"MUTANT {name} | {MUTANTS[name][0]} | lost {lost} | failed {' '.join(failed)} | negatives {' '.join(fired) or '-'}",
              flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
