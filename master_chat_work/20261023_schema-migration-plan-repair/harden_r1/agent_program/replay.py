"""Replay the blind solver's repair on the hardened bundle (reflex program).

    python3 replay.py BUNDLE APP_ROOT [--reading reflex|blind]

The blind solver (P13 r1, cee149a) repaired the old shipped repository; its
repaired files are in repo/ and the shipped copy it started from is in
repo_orig/. This script starts from the NEW shipped repository, takes every
file the blind solver changed whose shipped text did not change since, and
re-applies its hunks to the two files that did change (parser/feed.py,
pipeline.py). With --reading reflex (default) it then makes the reflex repair
for the new receipt: the shipped receipt check reports partner-rejected
batches as mismatched on the shipped data, and the reflex fix writes the
fingerprint into every admitted record before the partner stage, which turns
the receipt green. Token matching and the receipt's line scope stay as
shipped. Deliverables are written by the bundle's own solve.py packaging
code, so they are consistent with the replayed tree.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLIND = HERE / "repo"
ORIG = HERE / "repo_orig"

# The blind solver's hunks on the two files whose shipped text changed.
HUNKS = [
    ("src/migrakit/parser/feed.py",
     "        document = json.loads(raw)\n",
     "        try:\n            document = json.loads(raw)\n        except ValueError:\n"
     "            found.append(FeedLine(number, None, \"line is not JSON\"))\n            continue\n"),
    ("src/migrakit/pipeline.py",
     "    \"\"\"Processing order of the admitted lines.\"\"\"\n    return list(lines)\n",
     "    \"\"\"Processing order of the admitted lines: batch received_seq, then line number.\"\"\"\n"
     "    return sorted(lines, key=lambda item: (received[item.record[\"batch\"]], item.line))\n"),
    ("src/migrakit/pipeline.py",
     "        identity = (document[\"partner\"], document[\"key\"])\n"
     "        self.fingerprints.setdefault((partner_id, document[\"key\"]), set()).add(fingerprint)\n",
     "        identity = (partner_id, document[\"key\"])\n"
     "        self.fingerprints.setdefault(identity, set()).add(fingerprint)\n"),
    ("src/migrakit/pipeline.py",
     "for r in self.reissues.get((partner_id, document[\"key\"]), ())):",
     "for r in self.reissues.get(identity, ())):"),
    ("src/migrakit/pipeline.py",
     "        self._migrate(record, document, (partner_id, document[\"key\"]))\n"
     "        if record[\"attempted\"]:\n            self.holders[identity] = record\n",
     "        self.holders[identity] = record\n        self._migrate(record, document, identity)\n"),
]

REFLEX = [
    ("src/migrakit/pipeline.py",
     "        record = _blank_record(item.line, document)\n        try:\n",
     "        record = _blank_record(item.line, document)\n"
     "        record[\"fingerprint\"] = record_fingerprint(document[\"schema\"], document[\"payload\"])\n        try:\n"),
]


def _edit(tree: Path, rel: str, old: str, new: str) -> None:
    path = tree / rel
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{rel}: hunk does not apply")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def build(tree: Path, reading: str) -> None:
    """Turn a copy of the new shipped repository into the replayed repair."""
    for path in sorted(BLIND.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(BLIND)
        old, new = ORIG / rel, tree / rel
        if not old.is_file():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, new)
        elif new.is_file() and old.read_bytes() == new.read_bytes():
            shutil.copy2(path, new)
    for rel, old, new in HUNKS + (REFLEX if reading == "reflex" else []):
        _edit(tree, rel, old, new)


def main() -> None:
    bundle, app = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    reading = sys.argv[sys.argv.index("--reading") + 1] if "--reading" in sys.argv else "reflex"
    if app.exists():
        shutil.rmtree(app)
    (app / "out").mkdir(parents=True)
    shutil.copytree(bundle / "environment" / "repo", app / "repo")
    shutil.copytree(bundle / "environment" / "ci", app / "ci")
    os.environ["APP_ROOT"] = str(app)
    spec = importlib.util.spec_from_file_location("solve", bundle / "solution" / "solve.py")
    solve = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solve)
    solve.apply_repairs = lambda tree: build(tree, reading)
    solve.already_repaired = lambda: False
    solve.self_checks = lambda tree, workdir: []  # the blind solver ran no such probe
    solve.main()
    print(f"replayed ({reading}) into {app}")


if __name__ == "__main__":
    main()
