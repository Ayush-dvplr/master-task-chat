#!/usr/bin/env python3
"""Reference solution: repair pagerecover, build its archive, recover the book.

The repaired modules are written over the extracted project, the archive is
built from the members the targets file lists, and the documents are produced
by running the archived package. Afterwards every recovered image is checked
again by a second method that does not use the package.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
import zipfile
import zlib
from pathlib import Path

DATA = Path("/app/data")
PROJECT = Path("/app/project")
OUT = Path("/app/out")
PACKAGE = "pagerecover"
REPORTS = (
    "module_core.json",
    "module_metrics.json",
    "dependency_resolution.json",
    "summary.json",
)
FIXED_MODULES = [
    "__init__.py",
    "cli.py",
    "loader.py",
    "pages.py",
    "recovery.py",
    "reports.py",
]
FIX_CATEGORIES = [
    "cli",
    "config",
    "decoding",
    "dependency",
    "packaging",
    "recovery",
    "reporting",
    "validation",
]

REPAIRED_FILES_LINE


def unpack_project() -> None:
    PROJECT.mkdir(parents=True, exist_ok=True)
    for old in PROJECT.iterdir():
        if old.is_dir():
            shutil.rmtree(old)
        else:
            old.unlink()
    with zipfile.ZipFile(DATA / "project.zip") as archive:
        for info in archive.infolist():
            name = info.filename
            if info.is_dir() or not name.startswith("project/"):
                continue
            target = PROJECT / name[len("project/"):]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    for relative, text in REPAIRED_FILES.items():
        target = PROJECT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def run_unit_tests() -> tuple[int, int]:
    env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=PROJECT, env=env, capture_output=True, text=True, check=False,
    )
    ran = re.search(r"^Ran (\d+) tests?", done.stderr, re.MULTILINE)
    total = int(ran.group(1)) if ran else 0
    failed = re.search(r"FAILED \((.*)\)", done.stderr)
    bad = 0
    if failed:
        bad = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", failed.group(1)))
    if done.returncode != 0 or total == 0:
        sys.stderr.write(done.stderr)
        raise SystemExit("unit tests of the repaired project failed")
    return total, total - bad


def ci_commands() -> list[str]:
    commands: list[str] = []
    inside = False
    for raw in (DATA / "ci_config.yaml").read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if not raw.startswith(" "):
            inside = raw.strip() == "commands:"
            continue
        item = raw.strip()
        if inside and item.startswith("- "):
            value = item[2:].strip()
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("''", "'")
            elif value.startswith('"') and value.endswith('"'):
                value = json.loads(value)
            commands.append(value)
    return commands


def build_archive() -> list[str]:
    targets = json.loads((DATA / "expected_targets.json").read_text(encoding="utf-8"))
    flags = json.loads((DATA / "compiler_flags.json").read_text(encoding="utf-8"))
    stamp = tuple(int(part) for part in re.split(r"[-T:]", flags["deterministic_zip_timestamps"]))
    method = zipfile.ZIP_STORED if flags["zip_compression"] == "stored" else zipfile.ZIP_DEFLATED
    members = list(targets["archive_members"])
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT / "package.zip", "w") as archive:
        for name in members:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = method
            info.external_attr = 0o644 << 16
            archive.writestr(info, (PROJECT / name).read_bytes())
    return members


def run_archived(data_dir: Path, out_dir: Path) -> None:
    """Recover a book with the package as it sits in the archive."""
    with tempfile.TemporaryDirectory() as scratch:
        with zipfile.ZipFile(OUT / "package.zip") as archive:
            archive.extractall(scratch)
        launcher = (
            "import runpy, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "sys.argv = ['pagerecover'] + sys.argv[2:]\n"
            "runpy.run_module('pagerecover', run_name='__main__', alter_sys=True)\n"
        )
        done = subprocess.run(
            [sys.executable, "-I", "-B", "-c", launcher, str(Path(scratch) / "src"),
             "recover", "--data", str(data_dir), "--out", str(out_dir)],
            cwd=scratch, capture_output=True, text=True, check=False,
        )
        if done.returncode != 0:
            sys.stderr.write(done.stderr)
            raise SystemExit("archived package failed on " + str(data_dir))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---- second method: an independent reading of the book -----------------


def read_book(data_dir: Path) -> dict:
    """Parse the six book inputs into per image logs, disk pages and owners."""
    images: dict[str, dict] = {}
    section = None
    for raw in (data_dir / "page_map.ini").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        if line.startswith("["):
            section = line[1:-1]
            images[section] = {"slots": {}, "disk": {}, "log": [], "owners": {}}
        else:
            key, value = (part.strip() for part in line.split("=", 1))
            images[section]["slots"][key] = int(value)
    for raw in (data_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines():
        if raw.strip():
            row = json.loads(raw)
            images[row["image"]]["log"].append(row)
    for entry in images.values():
        entry["log"].sort(key=lambda row: row["lsn"])
    blob = (data_dir / "disk_pages.bin").read_bytes()
    at = 4
    while at < len(blob):
        start = at
        size = struct.unpack_from(">H", blob, at)[0]
        image = blob[at + 2:at + 2 + size].decode()
        at += 2 + size
        size = struct.unpack_from(">H", blob, at)[0]
        page = blob[at + 2:at + 2 + size].decode()
        at += 2 + size
        page_lsn, count = struct.unpack_from(">QH", blob, at)
        at += 10
        values = list(struct.unpack_from(">%dq" % count, blob, at))
        at += 8 * count
        crc = struct.unpack_from(">I", blob, at)[0]
        at += 4
        intact = zlib.crc32(blob[start:at - 4]) == crc
        images[image]["disk"].setdefault(page, []).append((page_lsn, values, intact))
    masters = tomllib.loads((data_dir / "checkpoint.toml").read_text(encoding="utf-8"))
    for image, entry in masters["images"].items():
        images[image]["master"] = entry["master_lsn"]
    for raw in (data_dir / "txn_catalog.csv").read_text(encoding="utf-8").splitlines()[1:]:
        if raw.strip():
            image, txn, client = raw.split(",")
            images[image]["owners"][int(txn)] = client
    return images


def finished_and_open(log: list[dict]) -> tuple[set[int], set[int]]:
    """Winners are committed transactions without an end; losers never committed nor ended."""
    seen: set[int] = set()
    committed: set[int] = set()
    ended: set[int] = set()
    for row in log:
        if "txn" in row:
            seen.add(row["txn"])
            if row["type"] == "commit":
                committed.add(row["txn"])
            elif row["type"] == "end":
                ended.add(row["txn"])
    return committed - ended, seen - committed - ended


def closed_form(entry: dict, appended: list[dict]) -> dict:
    """Final slots: disk plus every change newer than the disk page, minus each loser's net effect."""
    winners, losers = finished_and_open(entry["log"])
    pages = {}
    for page, frames in entry["disk"].items():
        page_lsn, values, _ = frames[0]
        pages[page] = {"page_lsn": page_lsn, "slots": list(values)}
    disk_lsn = {page: state["page_lsn"] for page, state in pages.items()}
    for row in entry["log"]:
        for change in row.get("changes", ()):
            target = pages[change["page"]]
            if row["lsn"] > disk_lsn[change["page"]]:
                target["slots"][change["slot"]] += change["delta"]
                target["page_lsn"] = max(target["page_lsn"], row["lsn"])
            if row["txn"] in losers:
                target["slots"][change["slot"]] -= change["delta"]
    for row in appended:
        for change in row.get("changes", ()):
            target = pages[change["page"]]
            target["page_lsn"] = max(target["page_lsn"], row["lsn"])
    return pages


def expected_appended(entry: dict) -> list[dict]:
    """Rebuild the appended records from the set of loser updates no CLR has compensated."""
    winners, losers = finished_and_open(entry["log"])
    last: dict[int, int] = {}
    pending: dict[int, list[dict]] = {txn: [] for txn in losers}
    covered: set[tuple[int, int]] = set()
    for row in entry["log"]:
        if "txn" in row:
            last[row["txn"]] = row["lsn"]
        if row["type"] == "clr" and row["undo_next"] is not None:
            covered.add((row["txn"], row["undo_next"]))
    for row in entry["log"]:
        if row["type"] == "update" and row["txn"] in losers:
            if (row["txn"], row["prev"]) not in covered:
                pending[row["txn"]].append(row)
    lsn = entry["log"][-1]["lsn"] + 1
    out: list[dict] = []

    def close(txn: int) -> None:
        nonlocal lsn
        out.append({"lsn": lsn, "type": "end", "txn": txn, "prev": last[txn]})
        last[txn] = lsn
        lsn += 1

    for txn in sorted(winners):
        close(txn)
    for txn in sorted(losers):
        if not pending[txn]:
            close(txn)
    queue = sorted(
        ((update, txn) for txn, rows in pending.items() for update in rows),
        key=lambda pair: -pair[0]["lsn"],
    )
    for update, txn in queue:
        out.append({
            "lsn": lsn, "type": "clr", "txn": txn, "prev": last[txn],
            "changes": [{"page": c["page"], "slot": c["slot"], "delta": -c["delta"]}
                        for c in update["changes"]],
            "undo_next": update["prev"],
        })
        last[txn] = lsn
        lsn += 1
        pending[txn].remove(update)
        if not pending[txn]:
            close(txn)
    return out


def recheck(data_dir: Path, out_dir: Path) -> dict[str, int]:
    """Compare every recovered image with the second method; return counts by check id."""
    images = read_book(data_dir)
    core = load(out_dir / "module_core.json")["images"]
    metrics = load(out_dir / "module_metrics.json")["images"]
    resolution = load(out_dir / "dependency_resolution.json")["images"]
    summary = load(out_dir / "summary.json")["images"]
    counts = {"R1": 0, "R2": 0, "R3": 0, "R4": 0}
    for image_id, entry in images.items():
        if core[image_id]["status"] != "recovered":
            continue
        appended = resolution[image_id]["appended"]
        if closed_form(entry, appended) != core[image_id]["pages"]:
            raise SystemExit(f"R1: recovered image {image_id} disagrees with the closed form")
        counts["R1"] += 1
        if expected_appended(entry) != appended:
            raise SystemExit(f"R2: appended records of {image_id} disagree")
        counts["R2"] += 1
        winners, losers = finished_and_open(entry["log"])
        totals: dict[str, dict[str, int]] = {}
        for txn in winners | losers:
            client = entry["owners"][txn]
            slot = totals.setdefault(client, {"winners": 0, "losers": 0, "compensated": 0})
            slot["winners" if txn in winners else "losers"] += 1
        for row in appended:
            if row["type"] == "clr":
                client = entry["owners"][row["txn"]]
                totals[client]["compensated"] += sum(abs(c["delta"]) for c in row["changes"])
        if totals != summary[image_id]["clients"]:
            raise SystemExit(f"R3: client totals of {image_id} disagree")
        counts["R3"] += 1
        start = metrics[image_id]["redo_start_lsn"]
        disk_lsn = {page: frames[0][0] for page, frames in entry["disk"].items()}
        rows = [r for r in entry["log"] if r["type"] in ("update", "clr")
                and start is not None and r["lsn"] >= start]
        applied = sum(1 for r in rows for c in r["changes"] if r["lsn"] > disk_lsn[c["page"]])
        if (len(rows), applied) != (metrics[image_id]["redo_records"],
                                    metrics[image_id]["redo_changes_applied"]):
            raise SystemExit(f"R4: redo counts of {image_id} disagree")
        counts["R4"] += 1
    return counts


def altered_rerun() -> None:
    """Double every delta of one image on a copy of the book and check that its figures move."""
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / "book"
        copy.mkdir()
        for name in ("page_map.ini", "disk_pages.bin", "checkpoint.toml",
                     "txn_catalog.csv", "audit_queries.json"):
            shutil.copy(DATA / name, copy / name)
        core = load(OUT / "module_core.json")["images"]
        target = next(i for i in sorted(core) if core[i]["status"] == "recovered"
                      and load(OUT / "dependency_resolution.json")["images"][i]["appended"])
        lines = []
        for raw in (DATA / "journal.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(raw)
            if row["image"] == target:
                for change in row.get("changes", ()):
                    change["delta"] *= 2
            lines.append(json.dumps(row))
        (copy / "journal.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        out = Path(scratch) / "out"
        run_archived(copy, out)
        moved = load(out / "summary.json")["images"][target]
        before = load(OUT / "summary.json")["images"][target]
        if moved["image_sha256"] == before["image_sha256"] or moved["clients"] == before["clients"]:
            raise SystemExit("J9: altered deltas did not move the dependent figures")
        recheck(copy, out)


def main() -> None:
    unpack_project()
    tests_run, tests_passed = run_unit_tests()
    members = build_archive()
    run_archived(DATA, OUT)
    core = load(OUT / "module_core.json")["images"]
    statuses = [entry["status"] for entry in core.values()]
    manifest = load(DATA / "dependency_manifest.json")
    version = manifest["required_version"]
    selftest = {
        "ok": tests_passed == tests_run,
        "package": PACKAGE,
        "version": version,
        "archive": str(OUT / "package.zip"),
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "ci_commands": ci_commands(),
        "reports": [str(OUT / name) for name in REPORTS],
        "images_total": len(statuses),
        "images_recovered": statuses.count("recovered"),
        "images_rejected": statuses.count("rejected"),
    }
    build_report = {
        "ok": True,
        "package": PACKAGE,
        "version": version,
        "layout": "src",
        "python": "3.12",
        "fixed_modules": FIXED_MODULES,
        "fix_categories": FIX_CATEGORIES,
    }
    (OUT / "selftest.json").write_text(json.dumps(selftest, indent=2) + "\n", encoding="utf-8")
    (OUT / "build_report.json").write_text(json.dumps(build_report, indent=2) + "\n", encoding="utf-8")
    counts = recheck(DATA, OUT)
    for check_id in ("R1", "R2", "R3", "R4"):
        print(f"check {check_id} ok ({counts[check_id]} images)")
    altered_rerun()
    print("check R5 ok")
    rejected = sorted((i, e["error"]) for i, e in core.items() if e["status"] == "rejected")
    for image_id, code in rejected:
        print(f"rejected {image_id} {code}")
    print("check R6 ok")
    print(f"archive members: {len(members)}")


if __name__ == "__main__":
    main()
