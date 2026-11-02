#!/usr/bin/env python3
"""Reference solution for slipway-overhaul-replan-repair.

The shipped slwopt engine is extracted from the working papers, each
catalogued fault is repaired in place by a targeted edit to the shipped
source, the repaired tree is delivered as an archive, and the repaired engine
is then driven over the same working papers to publish the derived documents.

Nothing here reimplements the replan. The whole derivation lives in the
repaired engine, which is what the contract asks for: the deliverable is an
engine that works, not a script that happens to publish one round.
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DATA = Path("/app/data")
WORK = Path("/app/project")
OUT = Path("/app/out")
NL = chr(10)


def _block(*lines):
    """One anchor, written as the lines it spans in the module."""
    return NL.join(lines) + NL


# One entry per catalogued fault: the code, the module it sits in, the anchor
# the shipped engine carries, and the anchor the stage papers put in force.
# Each is asserted to match its file exactly once before it is applied.
REPAIRS = (
    ("DFC-01", "src/slwopt/cells.py",
     _block('            out.append(named("demand", name))'),
     _block("            for other in sorted(graph.readers_of(self.accepted, name,",
            "                                                 self.jobs, precinct)):",
            '                out.append(named("demand", other))')),
    ("DFC-02", "src/slwopt/search.py",
     _block("            [],"),
     _block('            [seen["rule|" + r]["digest"] for r in rules],')),
    ("DFC-03", "src/slwopt/cells.py",
     _block('            trail[-1] = (marker, "revalidated")',
            "            return True"),
     _block('            trail[-1] = (marker, "revalidated")',
            "            return False")),
    ("DFC-04", "src/slwopt/charge.py",
     _block("    held = dict(model.meta.get(name, {}))",
            "    held.update({field: job[field] for field in REGISTER_FIELDS})",
            "    return [held,"),
     _block("    return [{field: job[field] for field in REGISTER_FIELDS},")),
    ("DFC-05", "src/slwopt/mutate.py",
     _block('    if kind == "job_note_revision":',
            '        return [cells.named("norm", payload["job_id"])]'),
     _block('    if kind == "job_note_revision":',
            "        return []")),
    ("DFC-06", "src/slwopt/mutate.py",
     _block('    if kind == "capacity_revision":',
            '        return [cells.named("closure", name) for name in sorted(model.jobs)',
            '                if model.jobs[name]["precinct"] == payload["precinct"]] + [',
            '                    cells.named("solve", payload["precinct"])]',
            '    if kind == "carryover_revision":',
            '        return [cells.named("solve", payload["precinct"])]'),
     _block('    if kind in ("capacity_revision", "carryover_revision"):',
            '        return [cells.named("solve", payload["precinct"])]')),
    ("DFC-07", "src/slwopt/mutate.py",
     _block('    if kind == "edge_withdrawn":',
            "        return []",
            '    if kind == "edge_lodged":',
            '        return [cells.named("closure", payload["requiring_job"])]'),
     _block('    if kind in ("edge_lodged", "edge_withdrawn"):',
            '        return [cells.named("closure", payload["requiring_job"])]')),
    ("DFC-08", "src/slwopt/objective.py",
     _block("    return (total,)"),
     _block("    return (total, weighted, optional, tuple(closed))")),
    ("DFC-09", "src/slwopt/objective.py",
     _block("        if usage[pool] >= available[pool]:"),
     _block("        if usage[pool] > available[pool]:")),
    ("DFC-10", "src/slwopt/normalise.py",
     _block('        elif section == "precinct_shift_minutes" and head.startswith("PCT-"):',
            "            shifts[head] = 480"),
     _block('        elif section == "precinct_shift_minutes" and head.startswith("PCT-"):',
            "            shifts[head] = int(row[1])")),
    ("DFC-11", "src/slwopt/normalise.py",
     _block('        elif section == "pool_weights" and head in POOLS:',
            "            weights[head] = (1, 1)"),
     _block('        elif section == "pool_weights" and head in POOLS:',
            "            weights[head] = (int(row[1]), int(row[2]))")),
    ("DFC-12", "src/slwopt/search.py",
     _block("        rebate = objective.rebate_of(closed, rules, closures, base)"),
     _block("        rebate = objective.rebate_of(closed, rules, closures, base + surcharge)")),
    ("DFC-13", "src/slwopt/search.py",
     _block('        penalty = sum(charges[name]["deferral_penalty_mills"]',
            "                      for name in names if name not in closed)"),
     _block('        penalty = sum(charges[name]["deferral_penalty_mills"]',
            "                      for name in charter if name not in closed)")),
    ("DFC-14", "src/slwopt/normalise.py",
     _block('        if "RESCINDED IN FULL" in line:',
            "            holding = True",
            "            continue",
            '        if line.startswith("APPENDIX") or "IN FORCE FOR ROUND" in line:',
            "            holding = False"),
     _block('        if "IN FORCE FOR ROUND" in line:',
            "            holding = True",
            "            continue",
            '        if line.startswith("APPENDIX"):',
            "            holding = False")),
    ("DFC-15", "src/slwopt/normalise.py",
     _block('    source = "berth_job_register_current.csv"'),
     _block('    source = params["header"]["register_in_force"]')),
)


def extract():
    """Unpack the shipped engine into the working tree."""
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(DATA / "project.zip") as archive:
        archive.extractall(WORK)


def repair():
    """Apply one targeted edit per catalogued fault."""
    for code, relative, shipped, correct in REPAIRS:
        path = WORK / relative
        text = path.read_text(encoding="utf-8")
        if text.count(shipped) != 1:
            raise SystemExit("repair " + code + " does not match "
                             + relative + " exactly once")
        path.write_text(text.replace(shipped, correct), encoding="utf-8")


def deliver():
    """Write the repaired tree back out as the delivered archive."""
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = (1980, 1, 1, 0, 0, 0)
    names = sorted(str(p.relative_to(WORK)).replace(os.sep, "/")
                   for p in WORK.rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(OUT / "patched_engine.zip", "w",
                         zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, (WORK / name).read_bytes())


def publish():
    """Drive the repaired engine over the working papers."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(WORK / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "slwopt",
                           "--data", str(DATA), "--out", str(OUT)],
                          env=env)
    if proc.returncode != 0:
        raise SystemExit("the repaired engine exited " + str(proc.returncode))


def main():
    extract()
    repair()
    deliver()
    publish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
