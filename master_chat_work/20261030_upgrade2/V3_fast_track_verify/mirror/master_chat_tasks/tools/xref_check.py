#!/usr/bin/env python3
"""Read-only cross-file consistency check for one Harbor bundle.

Reads WORK/XREF.md, which must contain one fenced ```json block:
  {"entries": [{"key": "task name", "value": "vendor-archive-roundtrip-recovery",
                "files": ["task.toml", "instruction.md"], "retired": ["old-name"]}]}
- value: must appear (as a literal substring) in every listed file (paths relative to the bundle).
- retired: old values that must appear in NO text file of the bundle.
Also checks every sha256 recorded in solution/TRUTH.md against the file it names.

Usage: xref_check.py <bundle_dir> <xref_md>
Exit 0 = clean, 1 = findings, 2 = usage/parse error. Writes nothing.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

TEXT_SUFFIXES = {".md", ".toml", ".py", ".sh", ".json", ".txt", ".csv", ".yaml", ".yml", ".ini", ".cfg", ""}


def text_files(bundle: Path):
    for p in sorted(bundle.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES and p.stat().st_size < 20_000_000:
            try:
                yield p, p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue


def load_entries(xref: Path):
    m = re.search(r"```json\s*(\{.*?\})\s*```", xref.read_text(encoding="utf-8"), re.S)
    if not m:
        raise ValueError("no ```json block in XREF.md")
    return json.loads(m.group(1))["entries"]


def check_truth_shas(bundle: Path):
    truth = bundle / "solution" / "TRUTH.md"
    if not truth.exists():
        return []
    out = []
    for line in truth.read_text(encoding="utf-8").splitlines():
        h = re.search(r"\b([0-9a-f]{64})\b", line)
        f = re.search(r"`([^`]+\.[A-Za-z0-9]+)`", line)
        if not (h and f):
            continue
        rel = f.group(1).lstrip("/")
        cands = [bundle / rel] + list(bundle.rglob(Path(rel).name))
        target = next((c for c in cands if c.is_file()), None)
        if target is None:
            out.append(f"TRUTH sha: file not found for `{rel}`")
        elif hashlib.sha256(target.read_bytes()).hexdigest() != h.group(1):
            out.append(f"TRUTH sha mismatch: {target.relative_to(bundle)}")
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    bundle, xref = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        entries = load_entries(xref)
    except Exception as e:  # parse error is a usage error, reported
        print(f"XREF parse error: {e}")
        return 2
    texts = dict(text_files(bundle))
    findings = []
    for e in entries:
        for rel in e.get("files", []):
            p = bundle / rel
            if not p.is_file():
                findings.append(f"[{e['key']}] listed file missing: {rel}")
            elif e["value"] not in p.read_text(encoding="utf-8", errors="replace"):
                findings.append(f"[{e['key']}] value {e['value']!r} not found in {rel}")
        for old in e.get("retired", []):
            for p, t in texts.items():
                if old in t:
                    findings.append(f"[{e['key']}] retired value {old!r} still in {p.relative_to(bundle)}")
    findings += check_truth_shas(bundle)
    for f in findings:
        print("FAIL", f)
    print(f"xref_check: {len(entries)} entries, {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
