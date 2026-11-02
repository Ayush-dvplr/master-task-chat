#!/usr/bin/env python3
"""Repair /app/repo in place, archive it and write the documents under /app/out."""
from __future__ import annotations

import configparser
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

APP = Path(os.environ.get("APP_ROOT", "/app"))
REPO = APP / "repo"
CI = APP / "ci"
OUT = APP / "out"

REPAIRED = {
REPAIRED_FILES_HERE
}

DEFECTS = [
    ("pyproject.toml", "Asked for Python 3.13, pulled in requests and pointed the package at lib/; now 3.12, no dependencies, src/ layout and the manifest version."),
    ("src/task/__init__.py", "VERSION was missing; it now carries the manifest version."),
    ("src/task/parser.py", "Missing book files raised a traceback, closed links were kept, override keys were lowercased and slots were ordered as text."),
    ("src/task/core.py", "The network joined cold rooms by shortest paths, which is not the minimum quote, and a site was charged once per booked link instead of once."),
    ("src/task/report.py", "share_bp was rounded to nearest instead of rounded down."),
]


def repair() -> None:
    for rel, text in REPAIRED.items():
        target = REPO / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for cache in list(REPO.rglob("__pycache__")):
        shutil.rmtree(cache)


def archive(config: dict) -> Path:
    spec = config["archive"]
    target = Path(spec["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    method = zipfile.ZIP_DEFLATED if spec["compression"] == "deflated" else zipfile.ZIP_STORED
    members = sorted(
        p for p in REPO.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    with zipfile.ZipFile(target, "w") as bundle:
        for path in members:
            info = zipfile.ZipInfo(path.relative_to(REPO).as_posix(), date_time=tuple(spec["timestamp"]))
            info.compress_type = method
            info.external_attr = (0o100000 | int(spec["mode"], 8)) << 16
            bundle.writestr(info, path.read_bytes())
    return target


def run_book(src: Path, book: Path, out: Path) -> None:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, "-B", "-m", "task", "--book", str(book), "--out", str(out)], env=env, check=True)


def regression_quotes(src: Path) -> dict:
    sys.path.insert(0, str(src))
    from task.core import best_network
    from task.parser import Rejected, load_inline

    found = {}
    for line in (CI / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        try:
            found[case["case"]] = best_network(load_inline(case)).quote
        except Rejected as exc:
            found[case["case"]] = exc.code
    return dict(sorted(found.items()))


def previously_failing() -> list[str]:
    log = (CI / "failing_tests.log").read_text(encoding="utf-8")
    pattern = re.compile(r"^(\w+) \([\w.]+\) \.\.\. (?:FAIL|ERROR)$", re.M)
    return sorted(set(pattern.findall(log)))


def raw_prices(book: Path) -> tuple[dict, dict, dict]:
    """Link costs, site charges and site corridors read straight from the book files."""
    rules = tomllib.loads((book / "access_rules.toml").read_text(encoding="utf-8"))
    ini = configparser.ConfigParser(interpolation=None)
    ini.optionxform = str
    ini.read(book / "activation.ini", encoding="utf-8")
    costs = {}
    for line in (book / "links.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            band = rules["tariff"][row["band"]]
            costs[row["link"]] = (row["a"], row["b"], band["base"] + band["per_km"] * row["km"])
    charges = {}
    with open(book / "sites.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = f"{row['project']}/{row['site']}"
            charges[(row["project"], row["site"])] = int(ini["overrides"].get(key, ini["classes"][row["class"]]))
    corridors = {}
    with open(book / "layout.tsv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            corridors[(row["project"], row["site"])] = row["corridor"]
    return costs, charges, corridors


def self_check(src: Path) -> None:
    costs, charges, corridors = raw_prices(CI)
    core = json.loads((OUT / "module_core.json").read_text(encoding="utf-8"))["projects"]
    report = json.loads((OUT / "module_report.json").read_text(encoding="utf-8"))["projects"]
    for pid, net in core.items():
        ends = {site for link in net["links"] for site in costs[link][:2]}
        assert ends <= set(net["sites"]), pid
        quote = sum(costs[link][2] for link in net["links"]) + sum(charges[(pid, s)] for s in net["sites"])
        assert quote == net["quote"], (pid, quote, net["quote"])
    print("check quotes ok")
    for pid, entry in report.items():
        per_corridor: dict[str, int] = {}
        for site, line in entry["sites"].items():
            assert line["corridor"] == corridors[(pid, site)], (pid, site)
            per_corridor[line["corridor"]] = per_corridor.get(line["corridor"], 0) + line["total"]
        assert per_corridor == {k: v["total"] for k, v in entry["corridors"].items()}, pid
        assert entry["depot"]["total"] + sum(per_corridor.values()) == core[pid]["quote"], pid
    print("check corridors ok")
    fixes = json.loads((OUT / "test_fixes.json").read_text(encoding="utf-8"))
    log = (CI / "failing_tests.log").read_text(encoding="utf-8")
    assert len(fixes["previously_failing"]) == len(set(re.findall(r"^(?:FAIL|ERROR): (\w+) ", log, re.M)))
    print("check previously_failing ok")
    with tempfile.TemporaryDirectory() as again:
        run_book(src, CI, Path(again))
        for name in ("module_core.json", "module_parser.json", "module_report.json", "summary.json"):
            assert (Path(again) / name).read_bytes() == (OUT / name).read_bytes(), name
    print("check rerun ok")
    with tempfile.TemporaryDirectory() as scratch:
        altered = Path(scratch) / "book"
        shutil.copytree(CI, altered)
        rules = altered / "access_rules.toml"
        rules.write_text(re.sub(r"^base = (\d+)$", lambda m: f"base = {int(m.group(1)) + 1}",
                                rules.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
        run_book(src, altered, Path(scratch) / "out")
        moved = json.loads((Path(scratch) / "out" / "module_core.json").read_text(encoding="utf-8"))["projects"]
        assert moved.keys() == core.keys()
        assert all(moved[pid]["quote"] > net["quote"] for pid, net in core.items())
    print("check altered copy ok")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONPATH": str(src), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(src.parent / "tests"), "-p", "test_*.py"],
        env=env, check=True, capture_output=True,
    )
    print("check visible tests ok")


def main() -> int:
    config = json.loads((CI / "build_config.json").read_text(encoding="utf-8"))
    repair()
    target = archive(config)
    unpacked = Path(tempfile.mkdtemp(prefix="patched-"))
    with zipfile.ZipFile(target) as bundle:
        bundle.extractall(unpacked)
    src = unpacked / "src"
    OUT.mkdir(parents=True, exist_ok=True)
    run_book(src, CI, OUT)
    fixes = {"previously_failing": previously_failing(), "regression_quotes": regression_quotes(src)}
    (OUT / "test_fixes.json").write_text(json.dumps(fixes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "defects": [{"file": rel, "summary": text} for rel, text in DEFECTS],
        "checks": [
            "python3 -m unittest discover -s tests on the archived repository: all visible tests pass",
            "every quote in module_core.json recomputed from the raw book files",
            "corridor and depot lines add up to each project's quote",
            "a second run of the command gives byte-identical documents",
        ],
    }
    (OUT / "repair-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"ran the package extracted from {target}")
    self_check(src)
    parsed = json.loads((OUT / "module_parser.json").read_text(encoding="utf-8"))
    print("rejected projects:", ", ".join(f"{pid} {code}" for pid, code in sorted(parsed["rejected"].items())))
    print("method: core.py sweeps the sites in corridor order and keeps, for the depot and the last four positions,")
    print("the cheapest cost of every connection pattern, so the quote is the minimum over all networks")
    shutil.rmtree(unpacked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
