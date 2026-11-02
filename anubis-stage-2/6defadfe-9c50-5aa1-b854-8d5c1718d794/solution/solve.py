#!/usr/bin/env python3
"""Reference solution: repair the shipped trainyard project, archive it, run it on the stage-1 feed.

Every repair cites the specification clause, erratum or governance rule it
restores.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

DATA = Path("/app/data")
PROJECT = Path("/app/project")
OUT = Path("/app/out")
ARCHIVE_TIME = (2026, 3, 30, 12, 0, 0)

# (file, rule, broken text, repaired text)
REPAIRS = [
    ('pyproject.toml', 'requires-python excludes the Python 3.12 runtime',
     'requires-python = ">=3.13"',
     'requires-python = ">=3.11"'),
    ('pyproject.toml', 'package-dir and package discovery point at a missing lib/ tree',
     'package-dir = {"" = "lib"}',
     'package-dir = {"" = "src"}'),
    ('pyproject.toml', 'package-dir and package discovery point at a missing lib/ tree',
     'where = ["lib"]',
     'where = ["src"]'),
    ('pyproject.toml', 'pypdf, needed by the pdf reader, is not a declared dependency',
     '    "pyarrow==18.1.0",\n',
     '    "pyarrow==18.1.0",\n    "pypdf==5.1.0",\n'),
    ('src/trainyard/readers.py', 'third-party tomli imported instead of the stdlib tomllib',
     'import tomli as tomllib\n',
     'import tomllib\n'),
    ('src/trainyard/conventions.py', 'circular import conventions -> feed -> readers -> conventions',
     'from zoneinfo import ZoneInfo\n\nfrom .feed import FeedError\n\nUTC = timezone.utc',
     'from zoneinfo import ZoneInfo\n\nUTC = timezone.utc'),
    ('src/trainyard/conventions.py', 'circular import conventions -> feed -> readers -> conventions',
     'raise FeedError(f"unrecognised timestamp {s!r}")',
     'raise ValueError(f"unrecognised timestamp {s!r}")'),
    ('src/trainyard/ledger.py', 'unclosed tuple literal (SyntaxError)',
     'DUR_COLS = ("duration_ms", "duration_s", "duration_cs", "elapsed", "elapsed_mmss", "took"\n',
     'DUR_COLS = ("duration_ms", "duration_s", "duration_cs", "elapsed", "elapsed_mmss", "took")\n'),
    ('src/trainyard/conventions.py', 'E6: duration conversion rounds half up instead of half to even',
     'from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP\n',
     'from decimal import Decimal, ROUND_HALF_EVEN\n'),
    ('src/trainyard/conventions.py', 'E6: duration conversion rounds half up instead of half to even',
     '    val = parse_number(num, locale) * UNIT_MS[unit]\n    return int(val.to_integral_value(ROUND_HALF_UP))',
     '    val = parse_number(num, locale) * UNIT_MS[unit]\n    return int(val.to_integral_value(ROUND_HALF_EVEN))'),
    ('src/trainyard/conventions.py', 'E1: pass_rate rounded half up instead of half to even',
     'quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))',
     'quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN))'),
    ('src/trainyard/conventions.py', '3.1: homoglyph table never applied to references',
     '    s = unicodedata.normalize("NFKC", text)\n',
     '    s = unicodedata.normalize("NFKC", text)\n    s = "".join(HOMOGLYPHS.get(ch, ch) for ch in s)\n'),
    ('src/trainyard/conventions.py', '3.6: provisional ~ rows read as live rows',
     '    s = s.lstrip("~")\n',
     '    if s.startswith("~"):\n        return "prov", None\n'),
    ('src/trainyard/conventions.py', '3.4: the 1904 workbook date system is ignored',
     'base = datetime(1899, 12, 30)',
     'base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)'),
    ('src/trainyard/readers.py', '3.6: cp1252 lines decoded with replacement characters',
     'out.append(line.decode("utf-8", errors="replace"))',
     'out.append(line.decode("cp1252"))'),
    ('src/trainyard/readers.py', '3.0: #header rows skipped without switching the column order',
     '        if cells[0].strip() == "#header":\n            continue',
     '        if cells[0].strip() == "#header":\n            header = [c.strip() for c in cells[1:]]\n            continue'),
    ('src/trainyard/feed.py', '2.1: feed index found by file name instead of its control block',
     '    def _find_index(self) -> Path:\n        return self.dir / "feed_index.json"\n        for p in',
     '    def _find_index(self) -> Path:\n        for p in'),
    ('src/trainyard/feed.py', '2.1: index candidates filtered by the .json file suffix',
     '            if p.suffix == ".json":\n'
     '                try:\n'
     '                    obj = json.loads(p.read_text(encoding="utf-8"))\n'
     '                except (ValueError, UnicodeDecodeError):\n'
     '                    continue\n'
     '                if isinstance(obj, dict) and isinstance(obj.get("control"), dict) \\\n'
     '                        and obj["control"].get("role") == "index":\n'
     '                    return p\n',
     '            if not p.is_file() or p.is_symlink():\n'
     '                continue\n'
     '            try:\n'
     '                obj = json.loads(p.read_text(encoding="utf-8"))\n'
     '            except (ValueError, UnicodeDecodeError):\n'
     '                continue\n'
     '            if isinstance(obj, dict) and isinstance(obj.get("control"), dict) \\\n'
     '                    and obj["control"].get("role") == "index":\n'
     '                return p\n'),
    ('src/trainyard/feed.py', '2.4: chain taken in path order instead of chain_pos',
     'self.files = sorted(idx["files"], key=lambda f: f["path"])',
     'self.files = sorted(idx["files"], key=lambda f: f["chain_pos"])'),
    ('src/trainyard/feed.py', '4.1: first revocation action wins instead of the latest',
     '            self.revoked.setdefault(job, act == "revoke")',
     '            self.revoked[job] = act == "revoke"'),
    ('src/trainyard/feed.py', 'G4: in-window renames of the next-quarter registry never loaded',
     '            if frm is None:',
     '            if frm is not None and W0 <= frm < W1:'),
    ('src/trainyard/feed.py', '4.4: failed skew probes (-1) read as measurements',
     '            off = cell(r["offset_ms"])\n',
     '            off = cell(r["offset_ms"])\n            if off == "-1":\n                continue\n'),
    ('src/trainyard/feed.py', 'E10: skew estimates never used for unmeasured hosts',
     '        return 0',
     '        return self.skew_est.get(host, 0)'),
    ('src/trainyard/feed.py', '4.4: latest skew measurement overall instead of the latest at or before the start',
     '            i = len(ms) - 1',
     '            i = bisect.bisect_right(ms, (t, 10 ** 12)) - 1'),
    ('src/trainyard/feed.py', 'G7: CMDB sites override hosts.ini',
     '        self.site = {}\n        self.host_tz = {}\n        for r in rows_of(self.one("hosts").tables[0]):\n            self.site[cell(r["name"]).lower()] = cell(r["site"])\n            self.host_tz[cell(r["name"]).lower()] = cell(r["tz"])\n        for r in rows_of(self.one("hosts_cmdb").tables[0]):\n            self.site[cell(r["name"]).lower()] = cell(r["site"])',
     '        self.site = {}\n        for r in rows_of(self.one("hosts_cmdb").tables[0]):\n            self.site[cell(r["name"]).lower()] = cell(r["site"])\n        self.host_tz = {}\n        for r in rows_of(self.one("hosts").tables[0]):\n            self.site[cell(r["name"]).lower()] = cell(r["site"])\n            self.host_tz[cell(r["name"]).lower()] = cell(r["tz"])'),
    ('src/trainyard/feed.py', '4.8: first maintenance event per UID wins instead of the highest SEQUENCE',
     '            if cur is None:',
     '            if cur is None or seqn > cur[0]:'),
    ('src/trainyard/feed.py', '4.8: cancelled maintenance windows applied',
     '            if status != "TENTATIVE":',
     '            if status == "CONFIRMED":'),
    ('src/trainyard/feed.py', 'G13: uncountersigned actions of the second void register applied',
     '            if cell(r["countersigned"]).lower() in ("yes", "no"):',
     '            if cell(r["countersigned"]).lower() == "yes":'),
    ('src/trainyard/feed.py', '4.7: void actions applied in file order instead of seq',
     '        for _, k, act in acts:',
     '        for _, k, act in sorted(acts):'),
    ('src/trainyard/feed.py', 'E9: confirmed corrections of errata revision B never adopted',
     '            if cell(r["status"]) == "approved":',
     '            if cell(r["status"]) == "confirmed":'),
    ('src/trainyard/feed.py', '4.3: commit order taken from log position instead of Change-Seq',
     '            self.commit_seq[cell(r["commit"]).lower()] = len(self.commit_seq)',
     '            self.commit_seq[cell(r["commit"]).lower()] = int(r["seq"])'),
    ('src/trainyard/feed.py', 'G10: Rewritten-From trailers read from the rebased log, which has none',
     '        for r in rows_of(self.one("commits").tables[0]):\n            old',
     '        for r in rows_of(self.one("commits_mirror").tables[0]):\n            old'),
    ('src/trainyard/feed.py', '6.2: first toolchain pin wins instead of the highest rev',
     '            if k not in pins:',
     '            if k not in pins or rev > pins[k][0]:'),
    ('src/trainyard/feed.py', '4.4: registry tz used instead of the timekeeping history',
     '        tz = self.host_tz.get(host)\n',
     '        for eff, z in self.tzh.get(host, []):\n            if eff <= local_day:\n                tz = z\n'),
    ('src/trainyard/feed.py', '5.4/G9: revoked quarantine entries still applied',
     '            seq = int(cell(r["seq"]))\n',
     '            seq = int(cell(r["seq"]))\n            if seq in revoked:\n                continue\n'),
    ('src/trainyard/ledger.py', 'G5: every row of the mirror re-export trusted',
     '                host = cell(r["host"]).lower()\n',
     '                host = cell(r["host"]).lower()\n                if scope_eph and f.pool.get(host) != "eph":\n                    continue\n'),
    ('src/trainyard/ledger.py', 'G6: every row of the rerun export trusted',
     '                    continue\n                a = int(cell(r["attempt"]))',
     '                    continue\n                if backfill_only and not _truthy(r.get("backfill")):\n                    continue\n                a = int(cell(r["attempt"]))'),
    ('src/trainyard/ledger.py', '4.1: newest revision wins regardless of exporter rank',
     '        return (int(cell(rev) or 0), 0)',
     '        return (self.f.rank[self.f.job_exporter[job]], int(cell(rev) or 0))'),
    ('src/trainyard/ledger.py', '4.1: legacy job codes never mapped through appendix D',
     '        return j',
     '        return self.f.legacy_job.get(j, j)'),
    ('src/trainyard/ledger.py', '4.2: only the literal branch name main accepted',
     '            if x["branch"] != "main":',
     '            if f.branch_class.get(x["branch"]) != "main":'),
    ('src/trainyard/ledger.py', 'G3: lab pool hosts kept',
     '                continue\n            dec',
     '                continue\n            if f.pool.get(x["host"]) == "lab":\n                continue\n            dec'),
    ('src/trainyard/ledger.py', '4.2: decommission judged at the window start instead of the attempt',
     '            if dec is not None and dec < self.W0:',
     '            if dec is not None and dec <= cor:'),
    ('src/trainyard/ledger.py', '4.2: window judged on the uncorrected start and closed at the end',
     '            if not (self.W0 <= x["logged"] <= self.W1):',
     '            if not (self.W0 <= cor < self.W1):'),
    ('src/trainyard/ledger.py', 'E7: maintenance windows closed at the end',
     '            if any(s <= cor <= e for s, e in f.maint_by_site.get(site, [])):',
     '            if any(s <= cor < e for s, e in f.maint_by_site.get(site, [])) or \\\n                    any(s <= cor < e for s, e in f.incidents.get(x["host"], [])):'),
    ('src/trainyard/ledger.py', '4.7: builds re-exported from an earlier stage counted again',
     '            if f.void_state.get(key) == "VOID":',
     '            if f.void_state.get(key) == "VOID" or key in seen:'),
    ('src/trainyard/ledger.py', '4.6: highest attempt decides even when it is infra',
     '            dec = max(rs, key=lambda x: x["attempt"])',
     '            dec = max(concl or rs, key=lambda x: x["attempt"])'),
    ('src/trainyard/ledger.py', '5.2: test registration window not applied',
     '            if reg is None:',
     '            if reg is None or not (reg[0] <= rec["cor"] and (reg[1] is None or rec["cor"] < reg[1])):'),
    ('src/trainyard/ledger.py', 'G12: crash rows without a crash column demoted to failures',
     '            if outcome == "crash" and not has_col:\n                outcome = "fail"',
     '            if outcome == "crash" and not has_col:\n                crash = digest.get((key, a, (malias, name)))'),
    ('src/trainyard/ledger.py', 'E4: flaky evidence from deciding attempts only',
     '            for rec in [b["dec"]]:\n                if rec["status"] not in ("pass", "fail"):',
     '            for rec in b["all"]:\n                if rec["status"] not in ("pass", "fail"):'),
    ('src/trainyard/ledger.py', 'E2: median averages the two middle values',
     '                "median_duration_ms": (durs[(len(durs) - 1) // 2] + durs[len(durs) // 2]) // 2 if durs else None,',
     '                "median_duration_ms": durs[(len(durs) - 1) // 2] if durs else None,'),
    ('src/trainyard/ledger.py', '7.2: carried last_good of the resume state ignored',
     '            lg_ord = None\n            lg_sha = None\n',
     '            lg_ord = carried_seq.get(m)\n            lg_sha = carried.get(m)\n'),
    ('src/trainyard/ledger.py', '7.2: dominant bucket ties broken by first occurrence',
     '                    e["dominant_bucket"] = max(cnt, key=cnt.get)',
     '                    e["dominant_bucket"] = min(k for k, v in cnt.items() if v == top)'),
    ('src/trainyard/ledger.py', '7.1: compile bucket carries the whole error cell',
     '                status, bucket = "red", "compile:" + d["error"]',
     '                status, bucket = "red", "compile:" + d["error"].split(":")[0].strip()'),
    ('src/trainyard/crash.py', 'E5: return addresses looked up without subtracting one',
     '            addr = base + offset',
     '            addr = base + offset - (1 if i > 0 else 0)'),
    ('src/trainyard/crash.py', '6.1: Message-ID crosswalk unused for reports without X-Crash-Id',
     '            cid = cell(r["crash"])',
     '            cid = cell(r["crash"]) or msgid.get(cell(r["message_id"]))'),
    ('src/trainyard/crash.py', '6.1: first report revision wins',
     '            if cid not in best:',
     '            if cid not in best or rev > best[cid][0]:'),
    ('src/trainyard/crash.py', '6.3: noise frames name the crash',
     '            info = self.register.get(sym)\n',
     '            info = self.register.get(sym)\n            if info and info[1] == "noise":\n                continue\n'),
    ('src/trainyard/crash.py', '6.1: crashes with no stack labelled unknown instead of failing',
     '            return "unknown"',
     '            raise FeedError(f"no stack for crash {crash_id}")'),
    ('src/trainyard/deps.py', 'E3: caret on zero versions treated like any other caret',
     '        up = f"{x + 1}.0.0"',
     '        if x > 0:\n            up = f"{x + 1}.0.0"\n        elif y > 0:\n            up = f"0.{y + 1}.0"\n        else:\n            up = f"0.0.{z + 1}"'),
    ('src/trainyard/deps.py', '9.4: prerelease versions satisfy plain ranges',
     '    comps = comparators(c)\n    core, ids = parse_version(v)\n',
     '    comps = comparators(c)\n    core, ids = parse_version(v)\n    if ids is not None and core not in {parse_version(w)[0] for _, w in comps if parse_version(w)[1] is not None}:\n        return False\n'),
    ('src/trainyard/deps.py', 'E8: publication, advisories and amendments at the cut treated as after it',
     '        if parse_iso(r["published_at"]) < cut:',
     '        if parse_iso(r["published_at"]) <= cut:'),
    ('src/trainyard/deps.py', 'E8: publication, advisories and amendments at the cut treated as after it',
     '        if at < cut:\n            yanked',
     '        if at <= cut:\n            yanked'),
    ('src/trainyard/deps.py', 'E8: publication, advisories and amendments at the cut treated as after it',
     '        if parse_iso(r["effective_at"]) < cut:',
     '        if parse_iso(r["effective_at"]) <= cut:'),
    ('src/trainyard/deps.py', 'G14: the withdrawn list of the mirror index never loaded',
     '    withdrawn = set()',
     '    withdrawn = {(pkg(r["package"]), cell(r["version"]))\n                 for r in rows_of(feed.one("packages_v2").table("withdrawn"))}'),
    ('src/trainyard/deps.py', '9.1: package alias register not applied',
     '        return n',
     '        return aliases.get(n, n)'),
    ('src/trainyard/deps.py', '9.5: pin none and expiry at the cut not honoured',
     '        if parse_iso(r["expires"]) >= cut:',
     '        if cell(r["pin"]) != "none" and parse_iso(r["expires"]) > cut:'),
    ('src/trainyard/deps.py', 'G15: pins: snapshot entries never resolved through the snapshot',
     '        pins = dict(lk["pins"])',
     '        pins = {p: (snap.get(m, {}).get(p) if v == "snapshot" else v) for p, v in lk["pins"].items()}'),
    ('src/trainyard/deps.py', '9.3: advisory actions of the dependency audit ignored',
     '    for role in ("advisories",):',
     '    for role in ("advisories", "audit"):'),
    ('src/trainyard/deps.py', '9.5: locked versions used for modules that are not frozen',
     '            if pins.get(p):',
     '            if lk["frozen"] and pins.get(p):'),
    ('src/trainyard/crash.py', '6.3: an unresolved frame offset lower-cased instead of kept as written',
     '                return f"{img}+0x{off.lower()}"',
     '                return f"{img}+0x{off}"'),
    ('src/trainyard/deps.py', '9.4: SemVer build metadata incorrectly participates in precedence',
     '    core, _, pre = v.partition("-")\n'
     '    a, b, c = (int(x) for x in core.split("."))',
     '    main = v.split("+", 1)[0]\n'
     '    core, _, pre = main.partition("-")\n'
     '    a, b, c = (int(x) for x in core.split("."))'),
    ('src/trainyard/feed.py', '3.1/4.3: commit prefixes shorter than nine hexadecimal digits accepted',
     '    def resolve_commit(self, ref: str):\n'
     '        ref = cell(ref).lower()\n'
     '        i = bisect.bisect_left(self.shas, ref)',
     '    def resolve_commit(self, ref: str):\n'
     '        ref = cell(ref).lower()\n'
     '        if len(ref) < 9 or any(ch not in "0123456789abcdef" for ch in ref):\n'
     '            return None\n'
     '        i = bisect.bisect_left(self.shas, ref)'),
    ('src/trainyard/feed.py', '2.1: indexed paths may escape the feed directory',
     '        for f in self.files:\n'
     '            path = self.dir / f["path"]\n'
     '            if f["role"] == "index":',
     '        feed_root = self.dir.resolve()\n'
     '        for f in self.files:\n'
     '            path = self.dir / f["path"]\n'
     '            if path.is_symlink() or not path.resolve().is_relative_to(feed_root):\n'
     '                raise FeedError(f"indexed path escapes feed directory: {f[\'path\']}")\n'
     '            if f["role"] == "index":'),
    ('src/trainyard/feed.py', '2.3: a parsed count that disagrees with the control block is accepted',
     '            self.docs[f["file_id"]] = doc\n'
     '            self.meta[f["file_id"]] = f',
     '            if doc.records != int(doc.control["records"]):\n'
     '                raise FeedError(f"record count mismatch for {f[\'file_id\']}: "\n'
     '                                f"declared {doc.control[\'records\']} read {doc.records}")\n'
     '            self.docs[f["file_id"]] = doc\n'
     '            self.meta[f["file_id"]] = f'),

]


def extract_project() -> None:
    zf = zipfile.ZipFile(DATA / "project.zip")
    for info in zf.infolist():
        parts = Path(info.filename).parts
        if info.is_dir() or len(parts) < 2 or parts[0] != "trainyard-3.2.0":
            continue
        dest = PROJECT.joinpath(*parts[1:])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(info))


def repair() -> None:
    for rel, rule, broken, fixed in REPAIRS:
        path = PROJECT / rel
        text = path.read_text(encoding="utf-8")
        if text.count(broken) != 1:
            raise SystemExit(f"repair not applicable ({rel}: {rule})")
        path.write_text(text.replace(broken, fixed), encoding="utf-8")


def archive() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(PROJECT.rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc" or ".egg-info" in str(p):
                continue
            info = zipfile.ZipInfo(p.relative_to(PROJECT).as_posix(), ARCHIVE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, p.read_bytes())
    (OUT / "package.zip").write_bytes(buf.getvalue())


def run_ledger() -> None:
    env = dict(os.environ, PYTHONPATH=str(PROJECT / "src"))
    subprocess.run([sys.executable, "-m", "trainyard", "reconcile", "--feed", str(DATA),
                    "--resume", str(DATA / "stage0_close.json"), "--out", str(OUT)], env=env, check=True)


def main() -> None:
    if not (DATA / "project.zip").is_file():
        raise SystemExit("project.zip is missing from the feed")
    extract_project()
    repair()
    archive()
    run_ledger()


if __name__ == "__main__":
    main()
