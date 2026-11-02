#!/usr/bin/env python3
"""Reference oracle: repair the shipped runledger project, archive it, run it on the stage-1 feed.

Every repair below replaces a defective passage of the shipped project with the
behaviour the approved specification, its incorporated documents and the
approved errata require.  The ledger itself is computed by the repaired package
from /app/data alone.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DATA = Path("/app/data")
PROJECT = Path("/app/project")
OUT = Path("/app/out")
ZIP_TIME = (2026, 3, 1, 0, 0, 0)

# (file in the project, defective passage, repaired passage)
REPAIRS = [
    ("src/runledger/ledger.py",
     "    seen = {shards[k][\"hash\"] for k in included}",
     "    seen = {norm_hash(h) for h in opening.get(\"seen_hashes\", [])} | {shards[k][\"hash\"] for k in included}"),
    ("src/runledger/ledger.py",
     "            ema = beta * ema + (1 - beta) * Decimal(row[\"loss\"])",
     "            ema = q(beta * ema + (1 - beta) * Decimal(row[\"loss\"]), 6)"),
    ("src/runledger/ledger.py",
     "        if a[\"overflow\"]:\n            cum -= a[\"tokens\"]\n            row[\"cumulative_tokens\"] = str(cum)\n            continue\n        for key, tok in a[\"records\"]:\n            if key is not None and status.get(key) == \"included\":\n                credited[key] += tok\n            else:\n                leaked += tok",
     "        for key, tok in a[\"records\"]:\n            if key is not None and status.get(key) == \"included\":\n                credited[key] += tok\n            else:\n                leaked += tok"),
    ("src/runledger/ledger.py",
     "    total = _ceil(budget / params.tps_final)",
     "    total = opening.get(\"total_steps\")\n    if total is None:\n        total = _ceil(budget / params.tps_final)"),
    ("src/runledger/ledger.py",
     "               \"lr\": \"\" if a[\"step\"] is None else format(lr_at(att - int(opening.get(\"next_attempt\", 1)) + 1 + int(opening.get(\"optimizer_step\", 0)), params, total), \".6e\"),",
     "               \"lr\": \"\" if a[\"step\"] is None else format(lr_at(a[\"step\"], params, total), \".6e\"),"),
    ("src/runledger/ledger.py",
     "        for frm, to, rstep in []:\n            pivot",
     "        for frm, to, rstep in facts[\"rollbacks\"]:\n            pivot"),
    ("src/runledger/ledger.py",
     "        loss = None if a[\"overflow\"] else q(a[\"loss\"] / len(a[\"records\"]) / 1000000, 6)",
     "        loss = None if a[\"overflow\"] else q(a[\"loss\"] / a[\"tokens\"], 6)"),
    ("src/runledger/ledger.py",
     "            if loss is not None:\n                a[\"loss\"] += Decimal(loss) / tok * 1000000",
     "            if loss is not None:\n                a[\"loss\"] += Decimal(loss)"),
    ("src/runledger/ledger.py",
     "        for b, v in content[shards[k][\"hash\"]].items():",
     "        if st != \"included\":\n            continue\n        for b, v in content[shards[k][\"hash\"]].items():"),
    ("src/runledger/ledger.py",
     "        keep = 1",
     "        keep = params.keep_k.get(shards[members[0]][\"source\"], 1)"),
    ("src/runledger/ledger.py",
     "\"records_closed\": int(opening.get(\"records_closed\", 0)) + chain[\"closing\"]}",
     "\"records_closed\": int(opening.get(\"records_closed\", 0)) + chain[\"closing\"],\n              \"run_control\": rc}"),
    ("src/runledger/ledger.py",
     "    order = lambda k: (shards[k][\"ingest_ts\"][::-1], k)",
     "    order = lambda k: (shards[k][\"ingest_ts\"], k)"),
    ("src/runledger/ledger.py",
     "        if False:",
     "        if k not in status and s[\"hash\"] in seen:"),
    ("src/runledger/ledger.py",
     "        if any(v > params.bench[b][\"exclude\"] for b, v in contam.get(k, {}).items() for v in [Decimal(v)] if b in params.bench):",
     "        if any(v >= params.bench[b][\"exclude\"] for b, v in content[s[\"hash\"]].items() if b in params.bench):"),
    ("src/runledger/feed.py",
     "            if key not in best:\n                best[key] = (t, score)",
     "            if key not in best or t > best[key][0]:\n                best[key] = (t, score)"),
    ("src/runledger/feed.py",
     "    pass  # H1 crosswalk",
     "    for ff in feed.stream(\"evals\", \"superseded\"):\n        for _, name, r in rows_of(ff, P):\n            if \"h1_run_id\" in r and \"ckpt_id\" in r:\n                h1_map[str(r[\"h1_run_id\"]).strip()] = str(r[\"ckpt_id\"]).strip()"),
    ("src/runledger/feed.py",
     "    pass  # tombstones",
     "    for ff in feed.stream(\"checkpoints\", \"mirror\"):\n        for _, name, r in rows_of(ff, P, sections={\"tombstones\"}):\n            tomb.add(str(r[\"ckpt_id\"]).strip())"),
    ("src/runledger/feed.py",
     "            ok[c].add(int(r[\"rank\"]))",
     "            if str(r[\"rank_status\"]).strip() == \"ok\":\n                ok[c].add(int(r[\"rank\"]))"),
    ("src/runledger/feed.py",
     "    pass  # host map",
     "    for ff in feed.stream(\"trainlog\", \"aggregate\"):\n        for _, name, r in rows_of(ff, P, sections={\"hosts\"}):\n            hosts[str(r[\"host\"]).strip()] = str(r[\"node\"]).strip()"),
    ("src/runledger/feed.py",
     "            pass  # replay window",
     "            if window is not None and not (window[0] <= t < window[1]):\n                continue"),
    ("src/runledger/feed.py",
     "            if any(s < t < e for s, e in windows.get(node, [])):\n                replays += 1\n                continue",
     "            if any(s <= t < e for s, e in windows.get(node, [])):\n                replays += 1\n                continue"),
    ("src/runledger/feed.py",
     "    zone = ev.get(f\"{prop}.TZID\", \"UTC\")",
     "    zone = ev.get(f\"{prop}.TZID\", node_tz)"),
    ("src/runledger/feed.py",
     "def _msgid(v) -> str:\n    return str(v)",
     "def _msgid(v) -> str:\n    return str(v).strip().strip(\"<>\").strip().lower()"),
    ("src/runledger/conventions.py",
     "def provisional(first_cell) -> bool:\n    return False",
     "def provisional(first_cell) -> bool:\n    return isinstance(first_cell, str) and first_cell.rstrip().endswith(DAGGER)"),
    ("src/runledger/feed.py",
     "    pass  # retractions",
     "    for ff in feed.stream(\"contamination\", \"rerun\"):\n        for _, name, r in rows_of(ff, P, sections={\"retracts\"}):\n            retracted.add(str(r[\"retracts\"]).strip())"),
    ("src/runledger/feed.py",
     "    pass  # dissolved clusters",
     "    for ff in feed.stream(\"neardup\", \"v1\"):\n        for _, name, r in rows_of(ff, P, sections={\"dissolved\"}):\n            dissolved.add(str(r[\"cluster_id\"]).strip())"),
    ("src/runledger/feed.py",
     "            if \"doc_id\" in r:\n                continue",
     "            if \"doc_id\" in r:\n                k = doc_index.get(str(r[\"doc_id\"]).strip())\n                if k is None:\n                    continue"),
    ("src/runledger/feed.py",
     "    pass  # vendor revocations",
     "    for ff in feed.stream(\"license\", \"vendor\"):\n        for ctx, name, r in rows_of(ff, P, sections={\"revocation\"}):\n            revoked.add(K.norm(r[\"shard_key\"]))"),
    ("src/runledger/feed.py",
     "            if archive:\n                continue",
     "            if archive and str(r.get(\"storage_class\", \"\")).strip() != \"glacier\":\n                continue"),
    ("src/runledger/feed.py",
     "            tokens = int(Decimal(reg[\"raw\"]) * P.ratios.get(src, {}).get(reg[\"rev\"], Decimal(1)) + Decimal(\"0.5\"))",
     "            tokens = int(q(Decimal(reg[\"raw\"]) * P.ratios.get(src, {}).get(reg[\"rev\"], Decimal(1)), 0))"),
    ("src/runledger/feed.py",
     "        elif k in r6:",
     "        elif src in P.adopted and k in r6:"),
    ("src/runledger/feed.py",
     "            if carried:\n                continue",
     "            if carried and status != \"APPROVED-CARRIED\":\n                continue"),
    ("src/runledger/feed.py",
     "            k = K.norm(r[\"shard_key\"])  # correction applies from its approval",
     "            if d > cut:\n                continue\n            k = K.norm(r[\"shard_key\"])"),
    ("src/runledger/feed.py",
     "            if k and k not in last_void:",
     "            if k and (k not in last_void or seq > last_void[k][0]):"),
    ("src/runledger/feed.py",
     "        cand = per_file.get(home, [])",
     "        cand = [(ctx, r) for ctx, r in per_file.get(home, []) if str(r.get(\"row_status\", \"\")).strip().upper() != \"VOID\"]"),
    ("src/runledger/feed.py",
     "        home = list(per_file)[-1]",
     "        home = routing.get(k) if len(per_file) > 1 else next(iter(per_file))"),
    ("src/runledger/feed.py",
     "    legacy = {}",
     "    legacy = {}\n    for ff in feed.stream(\"registry\", \"snapshot\"):\n        for ctx, _, r in rows_of(ff, P):\n            if r.get(\"legacy_id\"):\n                legacy[str(r[\"legacy_id\"]).strip().lower()] = K.norm(r[\"shard_key\"])"),
    ("src/runledger/feed.py",
     "            if scope is None:\n                out.append(ff)",
     "            if ff.control.get(\"scope\") == scope:\n                out.append(ff)"),
    ("src/runledger/readers.py",
     "            if header is None:",
     "            if header is None or (all(c in header_names for c in row) and len(row) == len(header)):"),
    ("src/runledger/conventions.py",
     "        return naive.replace(tzinfo=UTC)",
     "        return naive.replace(tzinfo=ZoneInfo(tz), fold=0).astimezone(UTC)"),
    ("src/runledger/conventions.py",
     "    base = dt.datetime(1900, 1, 1, tzinfo=UTC)",
     "    base = dt.datetime(1899, 12, 30, tzinfo=UTC) if int(system) == 1900 else dt.datetime(1904, 1, 1, tzinfo=UTC)"),
    ("src/runledger/conventions.py",
     "    s = str(text).strip().rstrip(\"%\")\n    value = Decimal(_num_text(s, comma))",
     "    s = str(text).strip()\n    if s.endswith(\"%\"):\n        return Decimal(_num_text(s[:-1], comma)) / 100\n    value = Decimal(_num_text(s, comma))"),
    ("src/runledger/conventions.py",
     "    mult = 1\n    value = Decimal(s) * mult * scale",
     "    mult = 1\n    if s.endswith((\"k\", \"K\")):\n        mult, s = 1000, s[:-1]\n    elif s.endswith(\"M\"):\n        mult, s = 1_000_000, s[:-1]\n    value = Decimal(s) * mult * scale"),
    ("src/runledger/conventions.py",
     "        s = s.strip()\n",
     "        s = \"\".join(self.homoglyphs.get(c, c) for c in s)\n"),
    ("src/runledger/conventions.py",
     "        out.append(raw.decode(\"utf-8\"))",
     "        try:\n            out.append(raw.decode(\"utf-8\"))\n        except UnicodeDecodeError:\n            out.append(raw.decode(\"cp1252\"))"),
    ("src/runledger/ledger.py",
     "STATUSES = [\"included\", \"unapproved\", \"license\", \"duplicate_prior_stage\", \"contamination\", \"duplicate\", \"near_duplicate\"",
     "STATUSES = [\"included\", \"unapproved\", \"license\", \"duplicate_prior_stage\", \"contamination\", \"duplicate\", \"near_duplicate\"]"),
    ("src/runledger/conventions.py",
     "from zoneinfo import ZoneInfo\n\nfrom .feed import FeedError  # noqa: F401\n",
     "from zoneinfo import ZoneInfo\n"),
    ("src/runledger/readers.py",
     "import tomli as tomllib\n",
     "import tomllib\n"),
    ("pyproject.toml",
     "package-dir = {\"\" = \"source\"}",
     "package-dir = {\"\" = \"src\"}"),
    ("pyproject.toml",
     "requires-python = \">=3.13\"",
     "requires-python = \">=3.12\""),
]


def repair() -> None:
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    with zipfile.ZipFile(DATA / "project.zip") as zf:
        zf.extractall(PROJECT)
    for rel, broken, fixed in REPAIRS:
        path = PROJECT / rel
        text = path.read_text(encoding="utf-8")
        if text.count(broken) != 1:
            raise SystemExit(f"repair target not found exactly once in {rel}")
        path.write_text(text.replace(broken, fixed), encoding="utf-8")


def archive() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT / "package.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PROJECT.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            info = zipfile.ZipInfo(path.relative_to(PROJECT).as_posix(), date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def run_ledger(tolerant: bool) -> None:
    env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"), PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
    cmd = [sys.executable, "-m", "runledger", "reconcile", "--feed", str(DATA), "--resume", str(DATA / "stage0_close.json"),
           "--out", str(OUT)]
    if tolerant:
        cmd.append("--tolerant")
    subprocess.run(cmd, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tolerant", action="store_true", help="skip listed feed files that are absent")
    args = parser.parse_args()
    repair()
    archive()
    run_ledger(args.tolerant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
