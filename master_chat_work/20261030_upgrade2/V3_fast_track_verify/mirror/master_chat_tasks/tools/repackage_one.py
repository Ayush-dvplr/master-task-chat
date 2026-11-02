#!/usr/bin/env python3
"""Repackage ONE task into Output_RFP from one harness run (plan v2 A4).

  repackage_one.py --slug SLUG --run-dir JOB_DIR --task-dir FROZEN_TASK_DIR [--output-root DIR] [--dry-run]

JOB_DIR holds trajectory/<model>/Run N/ (a harness jobs/<slug> folder or a regrade copy).
FROZEN_TASK_DIR is the frozen Tasks_INPUT/<slug> bundle; it is used instead of config.json task.path.
Steps:
  1. refuse unless tree_sha(FROZEN_TASK_DIR) == registry tree_sha of SLUG (intake.py method)
  2. package() from Terminal_2.0_Harbor_Harness/scripts/package_rfp_bundles.py into
     /Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/V3_fast_track_verify/tmp/repack-SLUG-TS/staged only (package() rmtree's out_root/<task>; main() is never called)
  3. sha listings: old.sha256 (current OUTPUT_ROOT/SLUG), staged.sha256, diff.txt
  4. --dry-run stops here. Otherwise copy OUTPUT_ROOT/SLUG to /Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/V3_fast_track_verify/tmp/repack-SLUG-TS/old/SLUG,
     replace OUTPUT_ROOT/SLUG with the staged folder, write after.sha256 and check it equals staged.
OUTPUT_ROOT defaults to Terminal_2.0_Harbor_Harness/Output_RFP. MT_ROOT env overrides the registry root.
"""
import argparse
import hashlib
import importlib.util
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import intake  # noqa: E402  (tree_sha, registry_tree_sha, HERE honour MT_ROOT)

HARNESS = TOOLS.parent.parent / "Terminal_2.0_Harbor_Harness"
PACKAGER = HARNESS / "scripts" / "package_rfp_bundles.py"
IST = timezone(timedelta(hours=5, minutes=30))


def listing(d):
    if not d.is_dir():
        return {}
    out = {}
    for p in sorted(d.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[p.relative_to(d).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def write_listing(path, lst):
    path.write_text("".join(f"{h}  {k}\n" for k, h in lst.items()))


def diff(old, new):
    lines = [f"only_old  {k}" for k in sorted(old.keys() - new.keys())]
    lines += [f"only_new  {k}" for k in sorted(new.keys() - old.keys())]
    lines += [f"changed   {k}" for k in sorted(old.keys() & new.keys()) if old[k] != new[k]]
    return lines


def load_package():
    spec = importlib.util.spec_from_file_location("package_rfp_bundles", PACKAGER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.package


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--run-dir", required=True, help="job dir holding trajectory/<model>/Run N/")
    ap.add_argument("--task-dir", required=True, help="frozen Tasks_INPUT/<slug> bundle")
    ap.add_argument("--output-root", default=str(HARNESS / "Output_RFP"))
    ap.add_argument("--dry-run", action="store_true", help="stage and write listings; do not touch output root")
    a = ap.parse_args()

    run_dir, task_dir, out_root = Path(a.run_dir).resolve(), Path(a.task_dir).resolve(), Path(a.output_root)
    if task_dir.name != a.slug:
        sys.exit(f"REFUSED: --task-dir name {task_dir.name!r} != slug {a.slug!r} (package() names the folder after it)")
    if not (run_dir / "trajectory").is_dir():
        sys.exit(f"REFUSED: {run_dir}/trajectory not found")
    if not task_dir.is_dir():
        sys.exit(f"REFUSED: task dir {task_dir} not found")
    reg = intake.registry_tree_sha(a.slug)
    if not reg:
        sys.exit(f"REFUSED: registry tree_sha empty: set it at freeze (status.py set {a.slug} tree_sha=...)")
    ts = intake.tree_sha(task_dir)
    if ts != reg:
        sys.exit(f"REFUSED: tree_sha {ts} of {task_dir} != registry tree_sha {reg}")
    print(f"tree_sha {ts} == registry")

    work = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/V3_fast_track_verify/tmp") / f"repack-{a.slug}-{datetime.now(IST).strftime('%Y%m%dT%H%M%S')}"
    staged = work / "staged"
    staged.mkdir(parents=True)
    load_package()(task_dir, [run_dir], staged)
    new_dir, cur = staged / a.slug, out_root / a.slug
    old_l, new_l = listing(cur), listing(new_dir)
    write_listing(work / "old.sha256", old_l)
    write_listing(work / "staged.sha256", new_l)
    d = diff(old_l, new_l)
    (work / "diff.txt").write_text("".join(f"{x}\n" for x in d))
    print(f"work {work}\nold {len(old_l)} files ({cur}), staged {len(new_l)} files, {len(d)} differences:")
    print("".join(f"  {x}\n" for x in d), end="")
    if a.dry_run:
        print(f"DRY RUN: nothing copied to {out_root}")
        return
    if cur.exists():
        shutil.copytree(cur, work / "old" / a.slug, symlinks=True)
        print(f"backup {work / 'old' / a.slug}")
        shutil.rmtree(cur)
    out_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(new_dir, cur, symlinks=True)
    after = listing(cur)
    write_listing(work / "after.sha256", after)
    if after != new_l:
        sys.exit(f"ERROR: {cur} differs from staged after copy; restore from {work / 'old' / a.slug}")
    print(f"copied: {cur} == staged ({len(after)} files)")


if __name__ == "__main__":
    main()
