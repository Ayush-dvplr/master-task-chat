#!/usr/bin/env python3
"""Repair warrant-ctl, run it over the corpus and write every deliverable."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

DATA = Path("/app/data")
TOOL = Path("/app/tool")
OUT = Path("/app/out")

# (module, legacy text, repaired text, defect) in the order they are applied
FIXES = [
    (
        'audit.py',
        '            "active": results[env]["active"],',
        '            "active": results[env]["active_tickets"],',
        'the summary read a result key the compiler never produced',
    ),
    (
        'cli.py',
        '    for name, func in (("compile", cmd_compile), ("audit", cmd_audit)):',
        '    for name, func in (("compile", cmd_compile), ("audit", cmd_audit), ("summarize", cmd_summarize)):',
        'the summarize subcommand was not registered',
    ),
    (
        'engine.py',
        '            if value < self.E:\n                continue',
        '            if value <= self.E:\n                continue',
        'keys whose value equals as_of were listed',
    ),
    (
        'engine.py',
        '                loser = b\n                standing.pop(loser, None)\n                elev.pop(loser, None)',
        '                if a in standing and b in standing:\n                    sod_log.append((env, pid, pair["rule"], "standing_conflict", None))\n                    continue\n                if a in standing:\n                    loser = b\n                elif b in standing:\n                    loser = a\n                else:\n                    sa = min(x[0] for x in elev[a])\n                    sb = min(x[0] for x in elev[b])\n                    loser = a if sa > sb else b if sb > sa else max(a, b)\n                elev.pop(loser, None)',
        'separation of duties always suspended the second permission, standing or not',
    ),
    (
        'engine.py',
        '        return last is not None and last[2] == "keep" and last[0] > self.E - days * 86400',
        '        return last is not None and last[2] == "keep" and last[0] >= self.E - days * 86400',
        'a review exactly attestation_max_age_days old was treated as stale',
    ),
    (
        'engine.py',
        '            self.led.mark(src, "accepted")\n            self.attest[(subject, row["permission"], row["env"])].append((at, rid, row["decision"]))',
        '            self.led.mark(src, "accepted")\n            if reviewer != subject:\n                self.attest[(subject, row["permission"], row["env"])].append((at, rid, row["decision"]))',
        'self reviews counted as attestations',
    ),
    (
        'engine.py',
        '            nxt = wtime.add_days(day, step)\n            for perm',
        '            nxt = wtime.add_days(day, step)\n            for _ in range(800):\n                s, e = self.shift_window(spec, nxt)\n                if s > end or self.holder(rot, nxt) != who:\n                    break\n                end = max(end, e)\n                nxt = wtime.add_days(nxt, step)\n            for perm',
        'back to back shifts of the same holder were not carried forward',
    ),
    (
        'engine.py',
        '            try:\n                self.instant(row["effective_at"])\n                at = self.instant(row["recorded_at"])\n            except wtime.BadTime:\n                self.led.mark(src, "rejected", rid, "bad_timestamp")\n                continue\n            scope = row["scope"]',
        '            try:\n                at = self.instant(row["effective_at"])\n            except wtime.BadTime:\n                self.led.mark(src, "rejected", rid, "bad_timestamp")\n                continue\n            scope = row["scope"]',
        'security revocations took effect when recorded instead of at effective_at',
    ),
    (
        'engine.py',
        'any(lo <= start <= hi for lo, hi in freeze[env])',
        'any(lo <= start < hi for lo, hi in freeze[env])',
        'freeze windows were closed at their end',
    ),
    (
        'engine.py',
        '            start = t["frm"] if t["frm"] is not None else t["rec"]\n            until = min(requested_until, start + hours * 3600)',
        '            base = t["frm"] if t["frm"] is not None else t["rec"]\n            start = max(base, qualifying[k - 1][0]) if k > 0 else base\n            until = min(requested_until if requested_until is not None else INF, start + hours * 3600)',
        'grants started at their requested start without waiting for approvals and crashed on open ends',
    ),
    (
        'engine.py',
        '                self.held.append((env, rid, t["state"]))',
        '                if requested_until is None or requested_until > self.E:\n                    self.held.append((env, rid, t["state"]))',
        'held grants included requests whose window had already ended',
    ),
    (
        'engine.py',
        '            for decided, aid, who, decision in sorted(t["approvals"]):\n                if who == t["ben"]:\n                    continue\n                if decision == "reject":\n                    vetoed = True\n                elif decision == "approve":\n                    qualifying.append((decided, aid))',
        '            for decided, aid, who, decision in sorted(t["approvals"]):\n                if not who.startswith("emp:") or who in (t["ben"], t["req"]):\n                    continue\n                if not self.emp_active(who, decided):\n                    continue\n                if decision == "reject":\n                    vetoed = True\n                elif decision == "approve" and who not in [q[1] for q in qualifying]:\n                    qualifying.append((decided, who))',
        'approvals were counted per approval with only the beneficiary excluded and no employment check',
    ),
    (
        'engine.py',
        '            corr[row["ticket"]].append((int(row["recorded_at"]), int(row["revision"]), src, until))\n        for ticket, rows in corr.items():\n            rows.sort()',
        '            corr[row["ticket"]].append((int(row["revision"]), int(row["recorded_at"]), src, until))\n        for ticket, rows in corr.items():\n            rows.sort()',
        'grant corrections were chosen by recorded instant instead of revision',
    ),
    (
        'engine.py',
        '            for r in rows[:-1]:\n                self.led.mark(r["_src"], "collapsed")\n            row = rows[-1]',
        '            top_gen = max(int(r["export_generation"]) for r in rows)\n            top = sorted((r for r in rows if int(r["export_generation"]) == top_gen), key=lambda r: r["_src"])\n            for r in rows:\n                if int(r["export_generation"]) != top_gen:\n                    self.led.mark(r["_src"], "collapsed")\n            bodies = {json.dumps({k: v for k, v in r.items() if k != "_src"}, sort_keys=True) for r in top}\n            if len(bodies) > 1:\n                for r in top:\n                    self.led.mark(r["_src"], "unresolved", rid, "conflicting_duplicate")\n                continue\n            for r in top[1:]:\n                self.led.mark(r["_src"], "collapsed")\n            row = top[0]',
        'duplicate tickets kept the last record without generation or conflict handling',
    ),
    (
        'engine.py',
        '        best: dict[str, int] = {}\n        queue = list(self.user_edges.get(pid, []))\n        while queue:\n            g, cap = queue.pop(0)\n            if g in best:\n                continue\n            best[g] = cap\n            for nxt, edge_cap in self.group_edges.get(g, []):\n                queue.append((nxt, min(cap, edge_cap)))\n        return best',
        '        best: dict[str, int] = {}\n        heap = [(-cap, g) for g, cap in self.user_edges.get(pid, [])]\n        heapq.heapify(heap)\n        while heap:\n            neg, g = heapq.heappop(heap)\n            cap = -neg\n            if g in best:\n                continue\n            best[g] = cap\n            for nxt, edge_cap in self.group_edges.get(g, []):\n                if nxt not in best:\n                    heapq.heappush(heap, (-min(cap, edge_cap), nxt))\n        return best',
        'nested groups were walked breadth first so the first path set the bound instead of the widest',
    ),
    (
        'engine.py',
        '                if lo <= self.E <= hi:\n                    table[row["group_id"]].append((role, hi))',
        '                if lo <= self.E < hi:\n                    table[row["group_id"]].append((role, hi))',
        'bindings were treated as in effect at their end instant',
    ),
    (
        'engine.py',
        '            if added <= self.E <= removed:',
        '            if added <= self.E < removed:',
        'memberships were treated as in effect at their removal instant',
    ),
    (
        'engine.py',
        '            src, rid = row["_src"], row["removal_id"]',
        '            src, rid = row["_src"], row["removal_id"]\n            if not self.visible(src, rid, row["recorded_at"]):\n                continue',
        'membership removals recorded after the cutoff were applied',
    ),
    (
        'engine.py',
        '        return any(item[2] == "enroll" and item[0] <= t for item in self.mfa_events.get(pid, []))',
        '        last = None\n        for item in sorted(self.mfa_events.get(pid, [])):\n            if item[0] <= t:\n                last = item\n        return last is not None and last[2] == "enroll"',
        'any past enrolment counted although a later reset ends it',
    ),
    (
        'engine.py',
        '            if prior is not None:\n                self.led.mark(prior[4], "collapsed")\n            governing[row["event_id"]] = entry\n',
        '            if prior is None or entry[:2] > prior[:2]:\n                if prior is not None:\n                    self.led.mark(prior[4], "collapsed")\n                governing[row["event_id"]] = entry\n            else:\n                self.led.mark(src, "collapsed")\n',
        'HR corrections were applied in file order instead of by recorded instant',
    ),
    (
        'engine.py',
        '        for key, cands in by_handle.items():\n            cands.reverse()\n            for loser in cands[1:]:',
        '        for key, cands in by_handle.items():\n            cands.sort(key=lambda c: (c[0], c[1]))\n            for loser in cands[1:]:',
        'the last IdP record seen won instead of the highest generation and shard priority',
    ),
    (
        'engine.py',
        '        hi = self.zones.local_midnight(tz, end)',
        '        hi = self.zones.local_midnight(tz, wtime.add_days(end, 1))',
        'contract cover stopped at the start of the end date',
    ),
    (
        'engine.py',
        '            out.update(spec.get("permissions", []))',
        '            for perm in spec.get("permissions", []):\n                if self.c.permissions[perm]["scope"] in (env, "both"):\n                    out.add(perm)',
        'role expansion ignored the permission scope of the profile',
    ),
    (
        'engine.py',
        '            key = row["alias"].strip()\n            target = ident.norm_handle(row["handle"])\n            if self.handle_owner.get(target) is None:',
        '            key = ident.norm_handle(row["alias"])\n            target = ident.norm_handle(row["handle"])\n            if key in self.handle_owner:\n                self.led.mark(src, "accepted")\n                continue\n            if self.handle_owner.get(target) is None:',
        'alias rows naming an existing account handle were loaded into the alias table',
    ),
    (
        'engine.py',
        '        raw = handle.strip() if isinstance(handle, str) else ""\n        target = self.alias.get(raw)\n        if target is not None:\n            return self.handle_owner.get(target)\n        return self.handle_owner.get(ident.norm_handle(handle))',
        '        key = ident.norm_handle(handle)\n        if key in self.handle_owner:\n            return self.handle_owner[key]\n        target = self.alias.get(key)\n        if target is not None:\n            return self.handle_owner.get(target)\n        return None',
        'handle resolution consulted the alias table before the account and compared aliases case sensitively',
    ),
    (
        'engine.py',
        '            if not self.visible(src, rid, row["recorded_at"], unit="s"):',
        '            if not self.visible(src, rid, row["recorded_at"], unit="ms"):',
        'self-service revocation recorded_at was read as seconds instead of milliseconds',
    ),
    (
        'policy.py',
        '        config[flat] = journal[flat][-1] if journal[flat] else layers[flat][-1]',
        '        if spec.get("class") == "ceiling":\n            config[flat] = min(values)\n        else:\n            config[flat] = journal[flat][-1] if journal[flat] else layers[flat][-1]',
        'ceiling keys took the newest value instead of the smallest',
    ),
    (
        'policy.py',
        '        entries.append((eff, int(row["seq"]), key, row["value"]))\n    entries.sort(key=lambda item: item[1])',
        '        entries.append((eff, int(row["seq"]), key, row["value"]))\n    entries.sort()',
        'journal entries were applied in seq order instead of effective order',
    ),
    (
        'policy.py',
        '        reason = None\n',
        '        if rec > cutoff:\n            stats["invisible"] += 1\n            continue\n        reason = None\n',
        'journal entries recorded after the cutoff were applied',
    ),
    (
        'corpus.py',
        'def _jsonl(path: Path) -> list[dict]:\n    rows = []\n    if not path.is_file():\n        return rows\n    for line in',
        'def _jsonl(path: Path) -> list[dict]:\n    rows = []\n    for line in',
        'the JSONL loader returned no rows for a missing file',
    ),
    (
        'corpus.py',
        'def _csv(path: Path, delimiter: str = ",") -> list[dict]:\n    if not path.is_file():\n        return []\n    with path.open(encoding="utf-8", newline="") as fh:',
        'def _csv(path: Path, delimiter: str = ",") -> list[dict]:\n    with path.open(encoding="utf-8", newline="") as fh:',
        'the CSV loader returned no rows for a missing file',
    ),
    (
        'corpus.py',
        '        self.files = sorted(name for name in listed if (self.root / name).is_file())\n        listed = self.files\n',
        '        missing = [name for name in listed if not (self.root / name).is_file()]\n        if missing:\n            raise CorpusError("missing corpus files: " + ", ".join(sorted(missing)))\n        self.files = sorted(listed)\n',
        'a missing manifest file was skipped instead of stopping the run',
    ),
    (
        'wtime.py',
        '    def local_midnight(self, zone: str, ymd: tuple[int, int, int]) -> int:\n        # HR effective dates are calendar days on the payroll clock (UTC)\n        y, mo, d = ymd\n        return _civil(y, mo, d)\n',
        '    def local_midnight(self, zone: str, ymd: tuple[int, int, int]) -> int:\n        y, mo, d = ymd\n        return self.get(zone).to_utc(_civil(y, mo, d))\n',
        'HR and contract dates were read as UTC days instead of on the site clock',
    ),
    (
        'wtime.py',
        "    def to_utc(self, local: int) -> int:\n        # rota times are published in each site's standard time\n        return local - self.std\n",
        '    def to_utc(self, local: int) -> int:\n        hits = [local - o for o in sorted({self.std, self.dst}) if self.offset_at(local - o) == o]\n        if hits:\n            return min(hits)\n        return local - self.std\n',
        'local wall times were converted with the standard offset only, ignoring the zone transitions',
    ),
    (
        'wtime.py',
        'def parse_instant(text) -> int:\n    if not isinstance(text, str):\n        raise BadTime(repr(text))\n    try:\n        value = datetime.fromisoformat(text.strip().replace("z", "Z"))\n    except ValueError:\n        raise BadTime(text) from None\n    if value.tzinfo is None:\n        # exports without an offset are written by the UTC batch hosts\n        value = value.replace(tzinfo=timezone.utc)\n    return int(value.timestamp())\n',
        'def parse_instant(text) -> int:\n    if not isinstance(text, str):\n        raise BadTime(repr(text))\n    m = _INSTANT.match(text)\n    if not m:\n        raise BadTime(text)\n    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))\n    base = _civil(y, mo, d, h, mi, s)\n    off = m.group(7)\n    if off == "Z":\n        return base\n    oh, om = int(off[1:3]), int(off[4:6])\n    if oh > 23 or om > 59:\n        raise BadTime(text)\n    delta = oh * 3600 + om * 60\n    return base - delta if off[0] == "+" else base + delta\n',
        'parse_instant accepted any isoformat variant and read offset-less times as UTC instead of rejecting them',
    ),
]


def extract() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    root = TOOL.resolve()
    with zipfile.ZipFile(DATA / "tool.zip") as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit(f"unsafe member {info.filename!r}")
            dest = (root / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(root):
                raise SystemExit(f"escaping member {info.filename!r}")
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


def repair() -> list[dict]:
    done = []
    for module, legacy, fixed, defect in FIXES:
        path = TOOL / module
        text = path.read_text(encoding="utf-8")
        if text.count(legacy) != 1:
            raise SystemExit(f"{module}: expected one legacy block, found {text.count(legacy)}")
        path.write_text(text.replace(legacy, fixed), encoding="utf-8")
        done.append({"module": module, "defect": defect})
    return sorted(done, key=lambda d: (d["module"], d["defect"]))


def run(commands: list[dict], *args: str) -> None:
    proc = subprocess.run([sys.executable, str(TOOL / "cli.py"), *args], capture_output=True, text=True, check=False)
    commands.append({"argv": ["python3", "cli.py", *args], "returncode": proc.returncode})
    if proc.returncode != 0:
        raise SystemExit(f"warrant-ctl {args[0]} failed: {proc.stderr.strip()}")


def package() -> None:
    with zipfile.ZipFile(OUT / "tool.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    extract()
    repairs = repair()
    OUT.mkdir(parents=True, exist_ok=True)
    data, cfg = str(DATA), str(OUT / "config.json")
    commands: list[dict] = []
    run(commands, "resolve-config", "--data", data, "--out", cfg)
    for profile in ("dev", "prod"):
        run(commands, "compile", "--data", data, "--config", cfg, "--profile", profile,
            "--out", str(OUT / f"profile_{profile}.json"))
    run(commands, "audit", "--data", data, "--config", cfg, "--out", str(OUT / "validation_report.json"))
    run(commands, "summarize", "--data", data, "--config", cfg, "--out", str(OUT / "summary.json"))
    report = {
        "tool": "warrant-ctl",
        "commands": commands,
        "config_sha256": sha(OUT / "config.json"),
        "profile_dev_sha256": sha(OUT / "profile_dev.json"),
        "profile_prod_sha256": sha(OUT / "profile_prod.json"),
        "repairs": repairs,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package()


if __name__ == "__main__":
    main()
