"""Oracle: repair the shipped restorekit project and package it.

The repaired modules below replace the broken ones of /app/data/project.zip: content sniffing instead of file
extensions and libmagic, Python 3.12 compatible imports, the identifier, number, timestamp and path rules of the
format guide and path conventions, the chain, replay, scope, quarantine and media rules of the restore
specification revision in force, and the section 11 deliverable formats.

Usage:
  python3 solve.py PROJECT_DIR            extract the shipped project into PROJECT_DIR and repair it
  python3 solve.py --zip PROJECT_DIR ZIP  write PROJECT_DIR as a deterministic source archive
"""

import sys
import zipfile
from pathlib import Path

REPAIRED: dict[str, str] = {}
REPAIRED['pyproject.toml'] = r'''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "restorekit"
version = "2.4.0"
description = "Point-in-time restore planning from a backup catalog feed"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "openpyxl==3.1.5",
    "pyarrow==18.1.0",
    "pypdf==5.1.0",
    "PyYAML==6.0.3",
    "tzdata==2025.2",
]

[tool.setuptools.packages.find]
where = ["src"]
'''
REPAIRED['src/restorekit/__init__.py'] = r'''"""restorekit - point-in-time restore planning from a backup catalog feed."""

__version__ = "2.4.0"
'''
REPAIRED['src/restorekit/__main__.py'] = r'''import sys

from restorekit.cli import main

sys.exit(main())
'''
REPAIRED['src/restorekit/cli.py'] = r'''"""Command line: python -m restorekit restore --feed DIR --out DIR"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from restorekit import engine, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="restorekit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("restore", help="restore a share to the point a restore feed requests")
    r.add_argument("--feed", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    result = engine.Restore(args.feed).run()
    report.write_all(args.out, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
REPAIRED['src/restorekit/docs.py'] = r'''"""Documents of the feed (Markdown, HTML, Word, PDF): control line, prose and tables."""

from __future__ import annotations

import html.parser
import io
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET


@dataclass
class Document:
    control: dict[str, str]
    text: str
    tables: list[tuple[str, list[str], list[list[str]]]] = field(default_factory=list)

    def table(self, caption: str) -> list[dict[str, str]]:
        for cap, cols, rows in self.tables:
            if cap == caption:
                return [dict(zip(cols, r)) for r in rows]
        return []


def _control(text: str) -> dict[str, str]:
    out = {}
    for item in text.split():
        if "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
    return out


def load(fmt: str, data: bytes) -> Document:
    return {"md": _md, "html": _html, "docx": _docx, "pdf": _pdf}[fmt](data)


def _split_md_row(line: str) -> list[str]:
    body = line.strip()[1:-1]
    cells, cur, i = [], "", 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if body[i] == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += body[i]
        i += 1
    cells.append(cur.strip())
    return cells


def _md(data: bytes) -> Document:
    lines = data.decode("utf-8").splitlines()
    m = re.match(r"<!-- restore-control: (.*) -->", lines[0])
    doc = Document(_control(m.group(1)) if m else {}, "")
    prose, i = [], 1
    while i < len(lines):
        ln = lines[i]
        t = re.match(r"\*\*Table: (.*)\*\*$", ln)
        if t and i + 3 < len(lines) and lines[i + 2].startswith("|"):
            cols = _split_md_row(lines[i + 2])
            rows = []
            j = i + 4
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(_split_md_row(lines[j]))
                j += 1
            doc.tables.append((t.group(1), cols, rows))
            i = j
            continue
        prose.append(ln)
        i += 1
    doc.text = "\n".join(prose)
    return doc


class _HTML(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.control: dict[str, str] = {}
        self.tables: list = []
        self.text: list[str] = []
        self.cap = None
        self.cell: list[str] | None = None
        self.row: list[str] | None = None
        self.rows: list = []
        self.cols: list = []
        self.in_cap = False
        self.in_head = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "restore-control":
            self.control = _control(a.get("content", ""))
        elif tag == "table":
            self.cap, self.rows, self.cols = "", [], []
        elif tag == "caption":
            self.in_cap = True
        elif tag == "thead":
            self.in_head = True
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "caption":
            self.in_cap = False
        elif tag == "thead":
            self.in_head = False
        elif tag in ("td", "th") and self.row is not None and self.cell is not None:
            self.row.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.in_head:
                self.cols = self.row
            else:
                self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.tables.append((self.cap, self.cols, self.rows))

    def handle_data(self, d):
        if self.in_cap:
            self.cap += d
        elif self.cell is not None:
            self.cell.append(d)
        else:
            self.text.append(d)


def _html(data: bytes) -> Document:
    p = _HTML()
    p.feed(data.decode("utf-8"))
    return Document(p.control, "\n".join(t for t in p.text if t.strip()), p.tables)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _ptext(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.iter(W + "t"))


def _docx(data: bytes) -> Document:
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    body = ET.fromstring(xml).find(W + "body")
    doc = Document({}, "")
    prose, caption = [], ""
    for el in body:
        if el.tag == W + "p":
            t = _ptext(el)
            if t.startswith("CONTROL ") and not doc.control:
                doc.control = _control(t[8:])
                continue
            if t.startswith("Table: "):
                caption = t[7:]
                continue
            prose.append(t)
        elif el.tag == W + "tbl":
            rows = [[_ptext(tc) for tc in tr.findall(W + "tc")] for tr in el.findall(W + "tr")]
            doc.tables.append((caption, rows[0], rows[1:]))
    doc.text = "\n".join(prose)
    return doc


def _pdf(data: bytes) -> Document:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    lines: list[str] = []
    for page in reader.pages:
        page_lines = page.extract_text().split("\n")
        if page_lines and re.match(r"^Page \d+ of \d+$", page_lines[-1].strip()):
            page_lines = page_lines[:-1]
        lines.extend(page_lines)
    doc = Document({}, "")
    prose = []
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("CONTROL ") and not doc.control:
            doc.control = _control(ln[8:])
            i += 1
            continue
        if ln.startswith("TABLE "):
            cap = ln[6:]
            header = lines[i + 1].rstrip()
            cols = header.split(" | ")
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].rstrip() != "END TABLE":
                cur = lines[j].rstrip()
                if cur != header + " (continued)":
                    rows.append(["" if c == "-" else c for c in cur.split(" | ")])
                j += 1
            doc.tables.append((cap, cols, rows))
            i = j + 1
            continue
        prose.append(ln)
        i += 1
    doc.text = "\n".join(prose)
    return doc
'''
REPAIRED['src/restorekit/engine.py'] = r'''"""Point-in-time restore of one share from a restore feed (restore specification revision 4.2)."""

from __future__ import annotations

import datetime as dt
import email.utils
import re
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from restorekit import feed, globs, paths, values
from restorekit.values import UTC, norm_hash, norm_id

REASONS = ["OUT_OF_SCOPE", "DISPOSED", "EXCLUDED_PATTERN", "SYMLINK_ESCAPE", "QUARANTINED", "UNRECOVERABLE"]
CAT_CANON = {
    "set": ["set_id", "backup_set", "bset", "set"], "seq": ["seq", "sequence"], "entry": ["entry_id", "eid", "entry"],
    "type": ["etype", "entry_type", "op", "type"], "path": ["path", "src_path", "object"],
    "new_path": ["new_path", "rename_to"], "target": ["target", "link_target"], "kind": ["kind", "obj_kind"],
    "owner": ["owner", "principal"], "sha256": ["sha256", "content_hash", "digest"], "container": ["container", "ct_id"],
    "file_id": ["file_id", "inode"], "client": ["client", "agent_client"], "committed": ["committed", "commit_flag"],
    "voids": ["voids", "void_target"], "attrs": ["attrs", "win_attrs"],
}
TS_KINDS = ("utc", "iso", "epoch", "ms", "ft", "local", "xl")
ERRATA_FORM = {"sha256": re.compile(r"[0-9a-f]{64}"), "size": re.compile(r"\d+"),
               "mtime": re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z"), "container": re.compile(r"(CT|RC)-\d{7}")}


class FeedError(Exception):
    pass


@dataclass
class Entry:
    eid: str
    sid: str
    seq: int
    etype: str
    path: str = ""
    new_path: str = ""
    target: str = ""
    kind: str = ""
    size: int | None = None
    mtime: object = None
    mode: int | None = None
    attrs: str | None = None
    owner: str = ""
    sha256: str = ""
    container: str = ""
    file_id: str = ""
    client: str = ""
    committed: bool = True
    voids: str = ""
    canon: str = ""
    canon_new: str = ""
    canon_target: str = ""
    rejected: str = ""


@dataclass
class SetInfo:
    sid: str
    job: str
    type: str
    status: str
    server: str
    queued: dt.datetime
    consolidates: str
    snapshot: dt.datetime | None = None
    crash: bool = False


@dataclass
class Obj:
    path: str
    kind: str
    entry: Entry
    target: str = ""


@dataclass
class Context:
    files: list
    by_stream: dict = field(default_factory=dict)


def _first(row: dict, names: list[str]):
    for n in names:
        if n in row and row[n] not in ("", None):
            return row[n]
    return None


def _iso(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


class Restore:
    def __init__(self, feed_dir: Path) -> None:
        pre = feed.load_feed(feed_dir, {})
        self.files = pre
        guide = self.one("FMTGUIDE")
        layouts: dict[str, list] = {}
        for row in guide.doc.table("Fixed-width layouts"):
            layouts.setdefault(row["layout"], []).append((row["column"], int(row["width"])))
        self.files = [feed.load(f.path, layouts) if f.fmt == "fixed" else f for f in pre]
        values.Folds.table = {chr(int(r["codepoint"][2:], 16)): r["fold"]
                              for r in self.one("PATHCONV").doc.table("Confusable fold table") if r["scope"] == "identifier"}

    # ------------------------------------------------------------------ feed access
    def all(self, stream: str, status: str | None = None) -> list:
        return [f for f in self.files if f.stream == stream and (status is None or f.status == status)]

    def one(self, stream: str, status: str | None = None):
        found = self.all(stream, status)
        if not found:
            raise FeedError(f"no {stream} file in feed")
        return found[0]

    # ------------------------------------------------------------------ request and documents
    def load_request(self) -> None:
        params = {r["key"]: r["value"] for r in self.one("RRQ").doc.table("Request parameters")}
        self.feed_id = params["feed"]
        self.files = [f for f in self.files if f.control.get("feed") == self.feed_id]
        self.share = params["share"]
        self.shares = {s["share"]: s for s in self.one("SHARE").tables["shares"]}
        me = self.shares[self.share]
        self.site_tz = me["site_tz"]
        self.array = me["array"]
        wall = dt.datetime.strptime(params["restore_point_local"], "%Y-%m-%d %H:%M:%S")
        self.rp = wall.replace(tzinfo=ZoneInfo(self.site_tz), fold=0).astimezone(UTC)
        self.rp_date = wall.date().isoformat()
        self.request_date = params["request_date"]
        rd = dt.date.fromisoformat(self.request_date)
        self.req_end = dt.datetime.combine(rd, dt.time(23, 59, 59)).replace(tzinfo=ZoneInfo(self.site_tz)).astimezone(UTC)
        self.target_volume = params["target_volume"]
        self.dispositions = self.one("RRQ").doc.table("Records disposition holds")
        reg = self.one("DOCREG").doc.table("Document control register")
        self.in_force: dict[tuple, str] = {}
        for row in reg:
            ok = row["status"] in ("APPROVED", "IN FORCE") and row["effective"] and row["effective"] <= self.rp_date
            self.in_force[(row["stream"], row["revision"], row["section"])] = "yes" if ok else "no"

    def doc_in_force(self, stream: str, revision: str, section: str = "ALL") -> bool:
        v = self.in_force.get((stream, revision, section))
        if v is None and section != "ALL":
            v = self.in_force.get((stream, revision, "ALL"))
        return v == "yes"

    def doc_rev(self, stream: str, revision: str):
        for f in self.all(stream):
            if f.control.get("revision") == revision:
                return f
        return None

    # ------------------------------------------------------------------ hosts, clients and roots
    def load_hosts(self) -> None:
        self.host_tz, self.host_os = {}, {}
        for h in self.one("HOST", "ORIGINAL").tables["hosts"]:
            self.host_tz[h["host"].upper()] = h["tz"]
            self.host_os[h["host"].upper()] = h["os"]
        self.host_fs = {h["hostname"].upper(): h["filesystem"] for h in self.one("HOST", "CMDB-EXPORT").tables["hosts"]}
        self.clientx = self.one("FMTGUIDE").doc.table("Client crosswalk")
        self.roots: dict[tuple, list[str]] = {}
        for s in self.one("ROOT").tables["sections"]:
            self.roots.setdefault((s["host"].upper(), s["share"].upper()), []).append(s["path"])
        self.servers = {}
        for s in self.one("SRV").tables["servers"]:
            self.servers[s["name"]] = {"tz": s["tz"], "builds": sorted(((_iso(b["installed"]), b["log_timestamps"]) for b in s["builds"]))}

    def client_host(self, code: str, when: dt.datetime) -> str | None:
        day = when.astimezone(ZoneInfo(self.site_tz)).date().isoformat()
        for row in self.clientx:
            if row["client"] == code and row["valid_from"] <= day and (not row["valid_to"] or day <= row["valid_to"]):
                return row["host"].upper()
        return None

    # ------------------------------------------------------------------ sets
    def load_sets(self) -> None:
        defs = {}
        for f in self.all("JOBDEF"):
            for j in f.tables["rows"]:
                defs[j["name"].strip().upper()] = j
        xwalk = []
        for f in self.all("SPEC"):
            rev = f.control.get("revision", "")
            if self.doc_in_force("SPEC", rev, "Appendix J"):
                xwalk += f.doc.table("Job rename crosswalk")

        def share_of(job: str, queued: dt.datetime) -> str:
            j = defs.get(job)
            if j and j["status"] == "ACTIVE" and j["share"]:
                return j["share"]
            day = queued.astimezone(ZoneInfo(self.site_tz)).date().isoformat()
            for x in xwalk:
                if x["old_name"].upper() == job and day < x["effective"]:
                    n = defs.get(x["new_name"].upper())
                    if n and n["share"]:
                        return n["share"]
            return ""

        self.entry_totals: dict[str, int] = {}
        for f in self.all("JOB", "REPORTING"):
            for row in f.tables.get("Sets", []):
                self.entry_totals[norm_id(row["set_id"])] = int(row["catalog_entries"])
        self.sets: dict[str, SetInfo] = {}
        for f in self.all("JOB", "ORIGINAL"):
            for row in f.tables["rows"]:
                kind = next(k for k in row if k.startswith("queued_")).split("_", 1)[1]
                server = row["server"].strip()
                tz = self.servers.get(server, {}).get("tz", "UTC")
                queued = values.parse_ts(row[f"queued_{kind}"], kind, tz)
                job = row["job_name"].strip().upper()
                if share_of(job, queued) != self.share:
                    continue
                sid = norm_id(row["set_id"])
                self.sets[sid] = SetInfo(sid, job, row["set_type"].strip().upper(), row["status"].strip().upper(), server, queued,
                                         norm_id(row.get("consolidates", "")))
        self._read_logs()
        for s in self.sets.values():
            if s.type == "SYNTH":
                s.snapshot = self.sets[s.consolidates].snapshot if s.consolidates in self.sets else self.snap.get(s.consolidates)
            else:
                s.snapshot = self.snap.get(s.sid)
            if s.sid in self.status_change:
                s.status = self.status_change[s.sid][1]
        self._crash()

    def _log_time(self, text: str, server: str) -> dt.datetime:
        info = self.servers[server]
        if re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$", text):
            return _iso(text)
        wall = dt.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        return wall.replace(tzinfo=ZoneInfo(info["tz"]), fold=0).astimezone(UTC)

    def _read_logs(self) -> None:
        self.snap: dict[str, dt.datetime] = {}
        self.status_change: dict[str, tuple] = {}
        gaps: dict[str, list] = {}
        line_re = re.compile(r"^(\S+(?: \d\d:\d\d:\d\d)?) (\S+) (\w+) \[([\w-]+)\] (.*)$")

        def take(t: dt.datetime, comp: str, msg: str) -> None:
            m = re.match(r"snapshot \{[^}]*\} created set=(\S+)", msg)
            if m and comp == "vss":
                self.snap[norm_id(m.group(1))] = t
            m = re.match(r"set=(\S+) status changed \S+ -> (\S+)", msg)
            if m and comp == "catalog-check":
                sid = norm_id(m.group(1))
                if sid not in self.status_change or self.status_change[sid][0] <= t:
                    self.status_change[sid] = (t, m.group(2))

        for f in self.all("LOG", "ORIGINAL"):
            for ln in f.lines:
                m = line_re.match(ln)
                if not m or m.group(2) not in self.servers:
                    continue
                t = self._log_time(m.group(1), m.group(2))
                take(t, m.group(4), m.group(5))
                g = re.match(r"lines from (\S+) to (\S+) were not retained", m.group(5))
                if g and m.group(4) == "logrotate":
                    gaps.setdefault(m.group(2), []).append((_iso(g.group(1)), _iso(g.group(2))))
        for f in self.all("LOG", "MIRROR"):
            for ln in f.lines:
                m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\dZ) (\S+) (\w+) \[([\w-]+)\] (.*)$", ln)
                if not m:
                    continue
                t = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
                if any(a <= t < b for a, b in gaps.get(m.group(2), [])):
                    take(t, m.group(4), m.group(5))

    def _crash(self) -> None:
        actual: dict[str, list] = {}
        for f in self.all("LOG", "ORIGINAL"):
            for ln in f.lines:
                m = re.match(r"^(\S+Z) (\S+) maintenance uid=(\S+) actual-(start|end)$", ln)
                if m:
                    actual.setdefault(m.group(3), [None, None])[0 if m.group(4) == "start" else 1] = _iso(m.group(1))
        windows = []
        for ev in self.one("CAL").tables["events"]:
            if ev.get("X-ARRAY", ("",))[0] != self.array or ev.get("STATUS", ("",))[0] != "CONFIRMED":
                continue
            if ev.get("X-IMPACT", ("",))[0] != "SNAPSHOT-CONSISTENCY":
                continue
            uid = ev["UID"][0]
            if uid in actual and None not in actual[uid]:
                windows.append(tuple(actual[uid]))
            else:
                windows.append((self._ics_time(*ev["DTSTART"]), self._ics_time(*ev["DTEND"])))
        for s in self.sets.values():
            s.crash = s.snapshot is not None and any(a <= s.snapshot < b for a, b in windows)

    @staticmethod
    def _ics_time(value: str, params: str) -> dt.datetime:
        if value.endswith("Z"):
            return dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        tz = re.search(r"TZID=([^;:]+)", params).group(1)
        return dt.datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(tz), fold=0).astimezone(UTC)

    # ------------------------------------------------------------------ chain
    def select_chain(self) -> None:
        order = sorted(self.sets.values(), key=lambda s: (s.snapshot, s.sid))
        eligible = [s for s in order if s.snapshot <= self.rp and s.status in ("COMPLETED", "PARTIAL") and not s.crash]
        base = max((s for s in eligible if s.type in ("FULL", "SYNTH")), key=lambda s: (s.snapshot, s.sid))
        diffs = [s for s in eligible if s.type == "DIFF" and s.snapshot > base.snapshot]
        diff = max(diffs, key=lambda s: (s.snapshot, s.sid)) if diffs else None
        anchor = diff or base
        chain = [base] + ([diff] if diff else [])
        skipped, broken = [], False
        for s in order:
            if s is base or s is diff:
                continue
            if s.snapshot > self.rp:
                reason = "AFTER_RP"
            elif s.status in ("FAILED", "CANCELLED"):
                reason = s.status
            elif s.crash:
                reason = "CRASH_INCONSISTENT"
                if s.snapshot > anchor.snapshot:
                    broken = True
            elif s.snapshot <= base.snapshot:
                reason = "BEFORE_BASE"
            elif s.snapshot <= anchor.snapshot:
                reason = "SUPERSEDED_BY_DIFF"
            elif broken:
                reason = "CHAIN_BROKEN"
            elif s.type == "INCR":
                chain.append(s)
                continue
            else:
                reason = "SUPERSEDED_BY_DIFF"
            skipped.append((s, reason))
        self.chain, self.skipped = chain, skipped

    # ------------------------------------------------------------------ catalog
    def load_catalog(self) -> None:
        wanted = set(self.sets)
        entries: dict[str, Entry] = {}
        original_ids: dict[str, set] = {}
        for f in self.all("CAT", "ORIGINAL"):
            ids = set()
            for raw in self._cat_rows(f):
                e = self._entry(raw, f)
                if e is None:
                    continue
                ids.add(e.eid)
                if e.sid in wanted:
                    entries[e.eid] = e
            original_ids[f.part] = ids
        for f in self.all("CAT", "RESEND"):
            for raw in self._cat_rows(f):
                e = self._entry(raw, f)
                if e is None or e.eid in original_ids.get(f.part, set()):
                    continue
                if e.sid in wanted:
                    entries[e.eid] = e
        self._errata(entries)
        self.entries_by_set: dict[str, list[Entry]] = {}
        for e in entries.values():
            self.entries_by_set.setdefault(e.sid, []).append(e)
        for lst in self.entries_by_set.values():
            lst.sort(key=lambda e: e.seq)

    @staticmethod
    def _cat_rows(f) -> list[dict]:
        rows = []
        for name, lst in f.tables.items():
            rows.extend(lst)
        return rows

    def _entry(self, row: dict, f) -> Entry | None:
        sid = norm_id(_first(row, CAT_CANON["set"]))
        eid = norm_id(_first(row, CAT_CANON["entry"]))
        if not sid or not eid:
            return None
        if sid not in self.sets:
            return Entry(eid, sid, 0, "")
        locale = f.control.get("locale", "plain")
        e = Entry(eid, sid, int(_first(row, CAT_CANON["seq"])), str(_first(row, CAT_CANON["type"])).strip().upper())
        for fld in ("path", "new_path", "target", "kind", "owner", "client", "attrs"):
            v = _first(row, CAT_CANON[fld])
            setattr(e, fld, "" if v is None else str(v))
        e.client = e.client.strip()
        e.kind = e.kind.strip().lower()
        e.sha256 = norm_hash(_first(row, CAT_CANON["sha256"]))
        e.container = norm_id(_first(row, CAT_CANON["container"]))
        e.voids = norm_id(_first(row, CAT_CANON["voids"]))
        fid = _first(row, CAT_CANON["file_id"])
        e.file_id = "" if fid is None else str(int(float(fid)) if isinstance(fid, float) else fid).strip()
        c = _first(row, CAT_CANON["committed"])
        e.committed = True if c is None else values.truthy(c)
        e.size = values.size_of(row, locale)
        e.mode = values.parse_mode(row)
        snap = self.sets[sid].snapshot
        host = self.client_host(e.client, snap) if e.client else None
        tkey = next((k for k in row if re.match(r"^(mtime|modified)_(\w+)$", k)), None)
        if tkey is None and f.fmt == "fixed":
            tkey = next((k for k in row if k.startswith("mtime")), None)
        if tkey is not None and e.etype in ("F", "L"):
            kind = tkey.split("_", 1)[1]
            fat = host is not None and self.host_fs.get(host, "") in ("FAT32", "exFAT")
            tz = "UTC" if fat else self.host_tz.get(host or "", "UTC")
            v = row[tkey]
            if fat and kind in ("utc", "iso") and isinstance(v, str) and not v.strip().startswith("0000-00-00"):
                # FAT/exFAT clients record wall-clock digits: any written offset (or Z) is ignored.
                m = re.match(r"\s*(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)", v)
                if m:
                    v, kind = f"{m.group(1)} {m.group(2)}", "local"
            t = values.parse_ts(v, kind, tz, f.extra.get("date1904", False)) if v not in ("", None) else None
            if t is None and f.fmt == "parquet":
                t = "SENTINEL"
            if isinstance(t, dt.datetime) and fat:
                t = values.as_wall_in(t, self.host_tz.get(host, "UTC"))
            e.mtime = t
        e.host = host
        return e

    def _errata(self, entries: dict[str, Entry]) -> None:
        best: dict[tuple, tuple] = {}
        for f in self.all("ERR"):
            rev = f.control.get("revision", "")
            if not self.doc_in_force("ERR", rev):
                continue
            for row in f.doc.table("Catalog errata"):
                if row["status"] != "APPROVED" or not ERRATA_FORM[row["field"]].fullmatch(row["value"]):
                    continue
                k = (norm_id(row["entry"]), row["field"])
                if k not in best or int(rev) > best[k][0]:
                    best[k] = (int(rev), row["value"])
        for (eid, fld), (_, value) in best.items():
            e = entries.get(eid)
            if e is None:
                continue
            if fld == "sha256":
                e.sha256 = norm_hash(value)
            elif fld == "size":
                e.size = int(value)
            elif fld == "mtime":
                e.mtime = _iso(value)
            elif fld == "container":
                e.container = norm_id(value)

    # ------------------------------------------------------------------ replay
    def canonicalize(self, e: Entry) -> None:
        host = e.host
        if host is None:
            e.rejected = "outside"
            return
        windows = self.host_os.get(host) == "windows"
        roots = self.roots.get((host, self.share.upper()), [])
        try:
            if e.etype != "X":
                e.canon = paths.canonical(e.path, roots, windows)
            if e.etype == "R":
                e.canon_new = paths.canonical(e.new_path, roots, windows)
            if e.etype == "H":
                e.canon_target = paths.canonical(e.target, roots, windows)
        except paths.Unsafe:
            e.rejected = "unsafe"
        except paths.Outside:
            e.rejected = "outside"

    def replay(self) -> None:
        self.dirs: dict[str, str] = {"": ""}
        self.objs: dict[str, Obj] = {}
        self.recon_sets = []
        self.applied_ids: set[str] = set()
        for s in self.chain:
            es = self.entries_by_set.get(s.sid, [])
            voided = {e.voids for e in es if e.etype == "X"}
            counts = {"set": s.sid, "expected": self.entry_totals.get(s.sid), "entries": len(es), "applied": 0, "voided": 0, "uncommitted": 0, "rejected": 0}
            for e in es:
                if e.eid in voided:
                    counts["voided"] += 1
                    continue
                if e.etype == "X":
                    continue
                if not e.committed:
                    counts["uncommitted"] += 1
                    continue
                self.canonicalize(e)
                if e.rejected:
                    counts["rejected"] += 1
                    continue
                self.apply(e)
                counts["applied"] += 1
                self.applied_ids.add(e.eid)
            self.recon_sets.append(counts)

    def _parent_display(self, path: str) -> str:
        parent = path.rpartition("/")[0]
        if parent == "":
            return ""
        pk = paths.key(parent)
        if pk not in self.dirs:
            self.dirs[pk] = self._parent_display(parent) + "/" + parent.rpartition("/")[2]
        return self.dirs[pk]

    def _display(self, path: str) -> str:
        return self._parent_display(path) + "/" + path.rpartition("/")[2]

    def apply(self, e: Entry) -> None:
        k = paths.key(e.canon)
        t = e.etype
        if t == "D":
            if k not in self.dirs:
                self.dirs[k] = self._display(e.canon)
        elif t == "F":
            o = self.objs.get(k)
            if o is not None and o.kind == "file":
                o.entry = e
            else:
                self.objs[k] = Obj(self._display(e.canon), "file", e)
        elif t == "H":
            src = self.objs.get(paths.key(e.canon_target))
            if src is not None and src.kind == "file":
                self.objs[k] = Obj(self._display(e.canon), "file", src.entry)
        elif t == "L":
            self.objs[k] = Obj(self._display(e.canon), "link", e, e.target)
        elif t == "W":
            if e.kind == "dir":
                self.dirs.pop(k, None)
                for d in [d for d in self.dirs if d.startswith(k + "/")]:
                    del self.dirs[d]
                for o in [o for o in self.objs if o.startswith(k + "/")]:
                    del self.objs[o]
            else:
                self.objs.pop(k, None)
        elif t == "R":
            nk = paths.key(e.canon_new)
            if e.kind == "dir":
                if k not in self.dirs:
                    return
                old = self.dirs.pop(k)
                new = self._display(e.canon_new)
                self.dirs[nk] = new
                for d in [d for d in self.dirs if d.startswith(k + "/")]:
                    disp = new + self.dirs.pop(d)[len(old):]
                    self.dirs[paths.key(disp)] = disp
                for ok in [o for o in self.objs if o.startswith(k + "/")]:
                    o = self.objs.pop(ok)
                    o.path = new + o.path[len(old):]
                    self.objs[paths.key(o.path)] = o
            else:
                o = self.objs.pop(k, None)
                if o is not None:
                    o.path = self._display(e.canon_new)
                    self.objs[nk] = o

    # ------------------------------------------------------------------ registers used after replay
    def load_media(self) -> None:
        self.inventory = {}
        for f in self.all("MEDIA", "ORIGINAL"):
            for sheet, rows in f.tables.items():
                for row in rows:
                    m = norm_id(row["media_id"])
                    self.inventory[m] = {"status": str(row["status"]).strip().upper(), "gen": str(row.get("generation") or "")}
        self.barcode = {}
        for f in self.all("MEDIA", "PREVIEW"):
            for row in f.tables.get("Media", []):
                if row.get("barcode"):
                    self.barcode[str(row["barcode"]).strip().upper()] = norm_id(row["media_id"])
        self.copies: dict[str, list[dict]] = {}
        self.created: dict[str, dt.datetime] = {}
        for f in self.all("CMAP"):
            of_record_rc = f.status == "FINAL"
            if f.status not in ("ORIGINAL", "FINAL"):
                continue
            locale = f.control.get("locale", "plain")
            for row in f.tables["rows"]:
                c = norm_id(row["container"])
                if c.startswith("RC-") != of_record_rc:
                    continue
                size = values.parse_int(row["size_bytes"], locale) if "size_bytes" in row else values.parse_int(row["size_text"], locale)
                created = row["created"] if "created" in row else values.EPOCH + dt.timedelta(milliseconds=row["created_ms"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                ref = str(row["media_ref"]).strip().upper()
                media = self.barcode.get(ref, norm_id(ref)) if int(row["copy"]) == 2 else norm_id(ref)
                self.copies.setdefault(c, []).append({"copy": int(row["copy"]), "media": media, "size": size})
                self.created[c] = created
        self.repack = {}
        for row in self.one("REPACK").tables["repack"]:
            if _iso(row["repacked_at"]) <= self.req_end:
                self.repack[norm_id(row["old_container"])] = norm_id(row["new_container"])
        self.damaged = set()
        for f in self.all("MERR"):
            rev = f.control.get("revision", "")
            corrections = {}
            for g in self.all("MERR"):
                if self.doc_in_force("MERR", g.control.get("revision", ""), "Section 2"):
                    for c in g.doc.table("Corrections to revision A"):
                        if c["field"] == "media":
                            corrections[c["errata"]] = norm_id(c["now"])
            if not self.doc_in_force("MERR", rev):
                continue
            for row in f.doc.table("Media errata"):
                if row["status"] == "APPROVED" and row["defect"] in ("DAMAGED", "UNREADABLE"):
                    self.damaged.add(corrections.get(row["errata"], norm_id(row["media"])))
        self.destroyed = set()
        self.recalls = []
        rerun_named = set()
        for m in self.one("MAIL").tables["messages"]:
            when = email.utils.parsedate_to_datetime(m["date"]).astimezone(UTC)
            subj = m["subject"]
            if subj.startswith("Destruction notice:") and when <= self.req_end:
                self.destroyed.add(norm_id(subj.split(":", 1)[1]))
            elif subj.startswith("Recall completed:") and when <= self.req_end:
                mm = re.search(r"checked in at (\S+?)\.", m["body"])
                if mm:
                    self.recalls.append((when, norm_id(subj.split(":", 1)[1]), mm.group(1)))
            elif subj.startswith("Checksum rerun request"):
                for c, cp in re.findall(r"^(\S+) copy (\d+)$", m["body"], re.M):
                    rerun_named.add((norm_id(c), int(cp)))
        self.mismatch = set()
        for row in self.one("CHK", "ORIGINAL").tables["rows"]:
            if row["result"].strip().upper() == "MISMATCH":
                self.mismatch.add((norm_id(row["container"]), int(row["copy"])))
        for f in self.all("CHK", "RERUN"):
            for row in f.tables["rows"]:
                k = (norm_id(row["container"]), int(row["copy"]))
                if k in rerun_named:
                    if row["result"].strip().upper() == "MATCH":
                        self.mismatch.discard(k)
                    else:
                        self.mismatch.add(k)
        self.copy_done = set()
        for row in self.one("COPY").doc.table("Copy jobs"):
            if row["status"] == "COMPLETED" and _iso(row["completed_utc"]) <= self.req_end:
                self.copy_done.add((norm_id(row["container"]), int(row["copy"])))
        vault = {}
        for s in self.one("SLOT").tables["sections"]:
            vault[norm_id(s["media"])] = s["vault"]
        for row in self.one("DASH").doc.table("Media"):
            m = norm_id(row["media_id"])
            if row["vault"] == "VLT-OFF3" and m not in vault:
                vault[m] = "VLT-OFF3"
        moves = list(self.recalls)
        for row in self.one("XFER").doc.table("Transfers"):
            t = _iso(row["received_utc"])
            if t <= self.req_end:
                moves.append((t, norm_id(row["media"]), row["to_vault"]))
        for _, m, v in sorted(moves):
            vault[m] = v
        self.vault = vault
        self.vault_prio = {}
        for row in self.one("MEDIAPROC").doc.table("Vault service calendar"):
            if row["date"] == self.request_date:
                self.vault_prio[row["vault"]] = int(row["priority"])

    def usable(self, container: str, cp: dict) -> bool:
        inv = self.inventory.get(cp["media"])
        if inv is None or inv["status"] == "EXPIRED" or inv["gen"] == "LTO-6":
            return False
        if cp["media"] in self.damaged or cp["media"] in self.destroyed:
            return False
        if (container, cp["copy"]) in self.mismatch:
            return False
        if cp["copy"] >= 2 and (container, cp["copy"]) not in self.copy_done:
            return False
        return True

    def pick_copy(self, container: str) -> tuple[str, dict | None]:
        c = self.repack.get(container, container)
        for cp in sorted(self.copies.get(c, []), key=lambda x: x["copy"]):
            if self.usable(c, cp):
                return c, cp
        return c, None

    def load_av(self) -> None:
        cut = re.search(r"The engine cutover is (\S+?)\.?$", self.one("QPROC").doc.text, re.M)
        self.cutover = _iso(cut.group(1).rstrip("."))
        vendor = {r["engine"]: r["vendor"] for r in self.one("QPROC").doc.table("Engine registry")}
        withdrawals = []
        for row in self.one("ADV").doc.table("Withdrawn signatures"):
            a, b = row["revisions"].split("-")
            withdrawals.append((row["vendor"], row["signature"], int(a), int(b), _iso(row["withdrawn_utc"])))
        self.infected: set[tuple] = set()

        def rows_of(f):
            for lst in f.tables.values():
                yield from lst

        for f in self.all("AV"):
            if f.status not in ("ORIGINAL", "PRELIMINARY"):
                continue
            for row in rows_of(f):
                if str(row["verdict"]).upper() != "INFECTED":
                    continue
                c = norm_id(row["container"])
                created = self.created.get(c)
                if created is None:
                    continue
                if (created >= self.cutover) != (f.status == "ORIGINAL"):
                    continue
                v = vendor.get(row["engine"])
                rev = int(row["sig_rev"])
                if any(v == wv and row["signature"] == ws and a <= rev <= b and t <= self.req_end for wv, ws, a, b, t in withdrawals):
                    continue
                self.infected.add((norm_hash(row["sha256"]), c))

    def load_identity(self) -> None:
        self.idmap = {}
        for row in self.one("IDMAP", "ORIGINAL").tables["accounts"]:
            self.idmap.setdefault(row["principal"], []).append(row)
        self.domains = {p.rsplit("-", 1)[0] for p in self.idmap}
        self.ad = {}
        for f in self.all("IDMAP", "EXPORT"):
            for row in f.tables.get("ad_users", []):
                self.ad[row["sid"]] = row["account"]
        self.changes = {}
        for row in self.one("IDCHG").doc.table("Identity changes"):
            if row["status"] == "APPROVED":
                t = _iso(row["effective_utc"])
                if t <= self.rp and (row["principal"] not in self.changes or self.changes[row["principal"]][0] < t):
                    self.changes[row["principal"]] = (t, row["account"])
        self.local = {}
        for s in self.one("LACCT").tables["sections"]:
            host = s["_section"].split(":", 1)[1].upper()
            for k, v in s.items():
                if k != "_section":
                    self.local[(host, k)] = v

    def owner(self, e: Entry) -> str:
        p = (e.owner or "").strip()
        if p in ("N/A", "-", "null", ""):
            return "UNMAPPED"
        if p.startswith("uid:"):
            return self.local.get(((e.host or ""), p[4:]), "UNMAPPED")
        if p in self.changes:
            return self.changes[p][1]
        for row in self.idmap.get(p, []):
            if _iso(row["valid_from"]) <= self.rp and (row["valid_to"] is None or self.rp < _iso(row["valid_to"])):
                return row["account"]
        if p.rsplit("-", 1)[0] not in self.domains and p in self.ad:
            return self.ad[p]
        return "UNMAPPED"

    def load_scope(self) -> None:
        spec = None
        for f in self.all("SPEC"):
            if self.doc_in_force("SPEC", f.control.get("revision", "")):
                spec = f
        prof = next(r for r in spec.doc.table("Share restore profiles") if r["share"] == self.share)
        self.includes = [x.strip() for x in prof["include_prefixes"].split(";") if x.strip()]
        self.holds = sorted((h for h in self.dispositions if h["share"] == self.share and h["action"] == "DESTROY"
                             and h["effective"] <= self.rp_date), key=lambda h: h["hold"])
        cats = [f for f in self.all("EXCL")]
        in_force = max((f for f in cats if f.control.get("effective_from", "0000") <= self.rp_date),
                       key=lambda f: int(f.control.get("revision", "0")))
        withdrawn = set()
        for f in cats:
            for w in f.tables.get("withdrawal", []):
                if w["effective"] <= self.rp_date:
                    withdrawn.add(w["id"])
        self.patterns = sorted((p for p in in_force.tables.get("pattern", [])
                                if p["scope"] in ("ALL", self.share) and p["from"] <= self.rp_date
                                and (not p["to"] or p["to"] > self.rp_date) and p["id"] not in withdrawn),
                               key=lambda p: int(p["id"].split("-")[1]))
        vol = next(v for v in self.one("VOL").tables["volume"] if v["id"] == self.target_volume)
        self.volume = vol

    # ------------------------------------------------------------------ restore decisions
    def custody(self) -> str:
        import hashlib
        src = {f.part: f.control.get("source_custody") for f in self.all("CAT", "CORRECTED")}
        lines = []
        for f in self.files:
            c = f.control["custody"]
            if c == "N/A":
                c = src[f.part]
            lines.append(f"{f.stream}|{f.part}|{f.status}|{f.control['records']}|{c}")
        return hashlib.sha256("".join(x + "\n" for x in sorted(lines)).encode("utf-8")).hexdigest()

    def allocation(self, size: int) -> int:
        v = self.volume
        if size <= v["resident_max"]:
            return 0
        c = v["large_cluster"] if size >= v["large_threshold"] else v["small_cluster"]
        return -(-size // c) * c

    def decide(self) -> None:
        order_sets = {s.sid: s for s in self.sets.values()}
        ok = {s.sid for s in self.chain} | {s.sid for s, r in self.skipped if r in ("BEFORE_BASE", "SUPERSEDED_BY_DIFF")}
        hist: dict[str, list] = {}
        for sid in ok:
            es = self.entries_by_set.get(sid, [])
            voided = {e.voids for e in es if e.etype == "X"}
            for e in es:
                if e.etype != "F" or e.eid in voided or not e.committed:
                    continue
                self.canonicalize(e)
                if e.rejected:
                    continue
                st = order_sets[sid]
                hist.setdefault(paths.key(e.canon), []).append(((st.snapshot, st.sid, e.seq), e))
        rows, excl, rolled = [], [], 0
        for o in sorted(self.objs.values(), key=lambda o: (paths.key(o.path), o.path)):
            kind = "file" if o.kind == "file" else "symlink"
            reason, detail, link_target = None, "", ""
            if not any(paths.under(o.path, inc) for inc in self.includes):
                reason = "OUT_OF_SCOPE"
            if reason is None:
                hs = [h for h in self.holds if paths.under(o.path, h["prefix"])]
                if hs:
                    reason, detail = "DISPOSED", hs[0]["hold"]
            if reason is None:
                for p in self.patterns:
                    if globs.match(p["pattern"], o.path):
                        reason, detail = "EXCLUDED_PATTERN", p["id"]
                        break
            if reason is None and kind == "symlink":
                host = o.entry.host
                lt = paths.resolve_link(o.target, o.path, self.roots.get((host, self.share.upper()), []), self.host_os.get(host) == "windows")
                if lt is None:
                    reason = "SYMLINK_ESCAPE"
                else:
                    link_target = lt
            chosen = o.entry
            if reason is None and kind == "file" and (chosen.sha256, chosen.container) in self.infected:
                st = order_sets[chosen.sid]
                mine = (st.snapshot, st.sid, chosen.seq)
                cands = sorted((c for c in hist.get(paths.key(o.path), []) if c[0] < mine), key=lambda c: c[0], reverse=True)
                chosen = next((c[1] for c in cands if (c[1].sha256, c[1].container) not in self.infected), None)
                if chosen is None:
                    reason, detail = "QUARANTINED", o.entry.sha256
                else:
                    rolled += 1
            cont, cp = "", None
            if reason is None and kind == "file":
                cont, cp = self.pick_copy(chosen.container)
                if cp is None:
                    reason, detail = "UNRECOVERABLE", cont
            if reason:
                excl.append({"path": o.path, "kind": kind, "reason": reason, "detail": detail})
                continue
            e = chosen
            mt = e.mtime
            if mt == "SENTINEL" or mt is None:
                mt = order_sets[e.sid].snapshot
            row = {"path": o.path, "kind": kind, "size": e.size if kind == "file" else 0, "allocated": 0,
                   "sha256": e.sha256 if kind == "file" else "", "mode": values.mode_out(e.mode, e.attrs),
                   "mtime_utc": values.iso_z(mt), "owner": self.owner(e), "source_set": e.sid,
                   "container": cont, "media": cp["media"] if cp else "", "copy": cp["copy"] if cp else 0,
                   "hardlink_group": "", "link_target": link_target, "_gk": (e.client, e.file_id) if kind == "file" else None,
                   "_size": cp["size"] if cp else 0}
            if kind == "file":
                row["allocated"] = self.allocation(e.size)
            rows.append(row)
        groups: dict = {}
        for row in rows:
            if row["_gk"] is not None:
                groups.setdefault(row["_gk"], []).append(row)
        n = 0
        for row in rows:
            g = groups.get(row["_gk"]) if row["_gk"] is not None else None
            if g and len(g) > 1 and g[0] is row:
                n += 1
                for i, m in enumerate(g):
                    m["hardlink_group"] = f"HL-{n:04d}"
                    if i:
                        m["allocated"] = 0
        self.rows, self.excl, self.rolled, self.groups = rows, excl, rolled, n

    # ------------------------------------------------------------------ deliverables
    def pull_list(self) -> list[dict]:
        by: dict[str, dict] = {}
        for row in self.rows:
            if row["kind"] != "file":
                continue
            m = by.setdefault(row["media"], {"copy": row["copy"], "containers": {}})
            m["containers"][row["container"]] = row["_size"]
        out = []
        from decimal import ROUND_HALF_EVEN, Decimal
        for media, m in by.items():
            rb = sum(m["containers"].values())
            gib = (Decimal(rb) / Decimal(1073741824)).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
            out.append({"media_id": media, "vault": self.vault.get(media, ""), "copy": m["copy"],
                        "containers": len(m["containers"]), "read_bytes": rb, "read_gib": f"{gib:.3f}"})
        out.sort(key=lambda x: (self.vault_prio.get(x["vault"], 99), x["media_id"]))
        return out

    def run(self) -> dict:
        self.load_request()
        self.load_hosts()
        self.load_sets()
        self.select_chain()
        self.load_catalog()
        self.replay()
        self.load_media()
        self.load_av()
        self.load_identity()
        self.load_scope()
        self.decide()
        pull = self.pull_list()
        digest = self.custody()
        counts = {r: 0 for r in REASONS}
        for x in self.excl:
            counts[x["reason"]] += 1
        chain = {"share": self.share, "restore_point_utc": values.iso_z(self.rp),
                 "effective_point_utc": values.iso_z(self.chain[-1].snapshot),
                 "chain": [{"set": s.sid, "type": s.type, "snapshot_utc": values.iso_z(s.snapshot),
                            "role": "base" if i == 0 else ("diff" if s.type == "DIFF" else "incremental")}
                           for i, s in enumerate(self.chain)],
                 "skipped": [{"set": s.sid, "type": s.type, "snapshot_utc": values.iso_z(s.snapshot), "reason": r}
                             for s, r in sorted(self.skipped, key=lambda x: (x[0].snapshot, x[0].sid))],
                 "custody_digest": digest}
        recon = {"sets": self.recon_sets, "objects_at_effective_point": len(self.objs), "restored": len(self.rows),
                 "excluded": counts, "rolled_back": self.rolled, "bytes_restored": sum(r["size"] for r in self.rows),
                 "bytes_allocated": sum(r["allocated"] for r in self.rows), "hardlink_groups": self.groups,
                 "media": len(pull), "containers": sum(p["containers"] for p in pull),
                 "read_bytes": sum(p["read_bytes"] for p in pull), "custody_digest": digest}
        return {"manifest": self.rows, "exclusions": self.excl, "pull": pull, "chain": chain, "recon": recon, "digest": digest}
'''
REPAIRED['src/restorekit/feed.py'] = r'''"""Reading a restore feed: format detection by content, control blocks and raw tables."""

from __future__ import annotations

import configparser
import csv
import io
import json
import mailbox
import sqlite3
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from restorekit import docs


@dataclass
class FeedFile:
    path: Path
    fmt: str
    control: dict[str, str]
    tables: dict[str, list] = field(default_factory=dict)   # name -> list of row dicts, in file order
    lines: list[str] = field(default_factory=list)
    doc: docs.Document | None = None
    extra: dict = field(default_factory=dict)

    @property
    def stream(self) -> str:
        return self.control.get("stream", "")

    @property
    def part(self) -> str:
        return self.control.get("part", "")

    @property
    def status(self) -> str:
        return self.control.get("status", "")


def parse_control(text: str) -> dict[str, str]:
    out = {}
    for item in text.strip().split():
        if "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
    return out


def sniff(data: bytes) -> str:
    if data.startswith(b"PK"):
        try:
            names = set(zipfile.ZipFile(io.BytesIO(data)).namelist())
        except zipfile.BadZipFile:
            return "unknown"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "word/document.xml" in names:
            return "docx"
        return "zip"
    if data.startswith(b"PAR1"):
        return "parquet"
    if data.startswith(b"SQLite format 3\x00"):
        return "sqlite"
    if data.startswith(b"%PDF"):
        return "pdf"
    head = data[:4096].lstrip(b"\xef\xbb\xbf").decode("utf-8", "replace")
    first = head.split("\n", 1)[0].strip()
    if first.startswith("#control"):
        lines = head.splitlines()
        second = lines[1] if len(lines) > 1 else ""
        if second.startswith("#layout"):
            return "fixed"
        ctl = parse_control(first[len("#control"):])
        if ctl.get("stream") == "LOG":
            return "log"
        return "tsv" if "\t" in second else "csv"
    if first.startswith("BEGIN:VCALENDAR"):
        return "ics"
    if first.startswith("From "):
        return "mbox"
    if first.startswith("<?xml"):
        return "xml"
    if first.lower().startswith("<!doctype html") or first.lower().startswith("<html"):
        return "html"
    if first.startswith("<!-- restore-control:"):
        return "md"
    if first.startswith("{"):
        try:
            json.loads(data.decode("utf-8"))
            return "json"
        except ValueError:
            return "jsonl"
    if first.startswith("[control]"):
        try:
            tomllib.loads(data.decode("utf-8"))
            return "toml"
        except tomllib.TOMLDecodeError:
            return "ini"
    if first.startswith("control:"):
        return "yaml"
    return "unknown"


def _text_lines(data: bytes) -> list[str]:
    """Decode a line-oriented file: BOM, CRLF and '#encoding' sections."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    out = []
    enc = "utf-8"
    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        line = raw.decode(enc)
        if line.strip() == "#encoding latin-1":
            enc = "latin-1"
            continue
        if line.strip() == "#encoding utf-8":
            enc = "utf-8"
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    return out


def _unescape_tsv(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            out.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def read_delimited(data: bytes, delim: str) -> tuple[dict, list[dict]]:
    lines = _text_lines(data)
    control = parse_control(lines[0][len("#control"):])
    rows: list[dict] = []
    header: list[str] | None = None
    body: list[str] = []

    def flush() -> None:
        if header is None or not body:
            return
        if delim == ",":
            reader = csv.reader(io.StringIO("\n".join(body)))
            parsed = list(reader)
        else:
            parsed = [[_unescape_tsv(x) for x in ln.split("\t")] for ln in body]
        for cells in parsed:
            if len(cells) == len(header) + 1 and cells[-1] == "":
                cells = cells[:-1]
            rows.append(dict(zip(header, cells)))

    for ln in lines[1:]:
        if ln.startswith("#schema "):
            flush()
            body = []
            spec = ln[len("#schema "):]
            header = next(csv.reader([spec])) if delim == "," else spec.split("\t")
            continue
        if ln.startswith("#"):
            continue
        if header is None:
            header = next(csv.reader([ln])) if delim == "," else ln.split("\t")
            continue
        body.append(ln)
    flush()
    return control, rows


def read_fixed(data: bytes, layouts: dict[str, list[tuple[str, int]]]) -> tuple[dict, list[dict]]:
    lines = _text_lines(data)
    control = parse_control(lines[0][len("#control"):])
    rows = []
    layout = None
    for ln in lines[1:]:
        if ln.startswith("#layout"):
            layout = layouts.get(ln.split()[1])
            continue
        if ln.startswith("#") or layout is None:
            continue
        pos, row = 0, {}
        for name, width in layout:
            row[name] = ln[pos:pos + width].strip()
            pos += width
        rows.append(row)
    return control, rows


def _xml_rows(root: ET.Element) -> tuple[dict, list[dict]]:
    control = {}
    rows = []
    for el in root:
        if el.tag == "control":
            control = dict(el.attrib)
        elif len(el.attrib) and not len(el):
            rows.append(dict(el.attrib))
        else:
            rows.append({c.tag: (c.text or "") for c in el})
    return control, rows


def load(path: Path, layouts: dict | None = None) -> FeedFile | None:
    data = path.read_bytes()
    fmt = sniff(data)
    if fmt in ("csv", "tsv"):
        control, rows = read_delimited(data, "," if fmt == "csv" else "\t")
        return FeedFile(path, fmt, control, {"rows": rows})
    if fmt == "fixed":
        control, rows = read_fixed(data, layouts or {})
        return FeedFile(path, fmt, control, {"rows": rows})
    if fmt == "log":
        lines = _text_lines(data)
        return FeedFile(path, fmt, parse_control(lines[0][len("#control"):]), lines=lines[1:])
    if fmt == "jsonl":
        lines = [ln for ln in data.decode("utf-8").splitlines() if ln.strip()]
        head = json.loads(lines[0])
        return FeedFile(path, fmt, {k: str(v) for k, v in head["control"].items()}, {"rows": [json.loads(x) for x in lines[1:]]})
    if fmt == "json":
        doc = json.loads(data.decode("utf-8"))
        control = {k: str(v) for k, v in doc.pop("control").items()}
        return FeedFile(path, fmt, control, {k: v for k, v in doc.items() if isinstance(v, list)})
    if fmt == "xml":
        root = ET.fromstring(data)
        control, rows = _xml_rows(root)
        return FeedFile(path, fmt, control, {"rows": rows})
    if fmt == "parquet":
        import pyarrow.parquet as pq
        table = pq.read_table(io.BytesIO(data))
        meta = table.schema.metadata or {}
        control = parse_control(meta.get(b"restore-control", b"").decode())
        return FeedFile(path, fmt, control, {"rows": table.to_pylist()})
    if fmt == "xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        tables, control = {}, {}
        for ws in wb.worksheets:
            vals = [list(r) for r in ws.iter_rows(values_only=True)]
            if not vals:
                continue
            header = [str(h) for h in vals[0]]
            rows = [dict(zip(header, r)) for r in vals[1:] if any(v is not None for v in r)]
            if ws.title == "_control":
                control = {str(r["key"]): str(r["value"]) for r in rows}
            else:
                tables[ws.title] = rows
        f = FeedFile(path, fmt, control, tables)
        f.extra["date1904"] = wb.epoch.year == 1904
        wb.close()
        return f
    if fmt == "sqlite":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        tables = {n: [dict(r) for r in con.execute(f'SELECT * FROM "{n}" ORDER BY rowid')] for n in names}
        con.close()
        control = {r["key"]: r["value"] for r in tables.pop("_control", [])}
        return FeedFile(path, fmt, control, tables)
    if fmt == "yaml":
        doc = yaml.safe_load(data.decode("utf-8"))
        control = {k: str(v) for k, v in doc.pop("control").items()}
        return FeedFile(path, fmt, control, {k: v for k, v in doc.items()})
    if fmt == "toml":
        doc = tomllib.loads(data.decode("utf-8"))
        control = {k: str(v) for k, v in doc.pop("control").items()}
        return FeedFile(path, fmt, control, {k: v for k, v in doc.items()})
    if fmt == "ini":
        cp = configparser.ConfigParser(interpolation=None, delimiters=("=",))
        cp.optionxform = str
        cp.read_string(data.decode("utf-8"))
        control = dict(cp["control"])
        sections = {s: dict(cp[s]) for s in cp.sections() if s != "control"}
        return FeedFile(path, fmt, control, {"sections": [dict(v, _section=k) for k, v in sections.items()]})
    if fmt == "ics":
        return _load_ics(path, data)
    if fmt == "mbox":
        return _load_mbox(path)
    if fmt in ("md", "html", "docx", "pdf"):
        d = docs.load(fmt, data)
        return FeedFile(path, fmt, d.control, doc=d)
    return None


def _load_ics(path: Path, data: bytes) -> FeedFile:
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\n ", "").replace("\n\t", "")
    control, events, cur = {}, [], None
    for ln in text.splitlines():
        if ln.startswith("X-RESTORE-CONTROL:"):
            control = parse_control(ln.split(":", 1)[1])
        elif ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            events.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            name, value = ln.split(":", 1)
            prop, _, params = name.partition(";")
            cur[prop] = (value, params)
    return FeedFile(path, "ics", control, {"events": events})


def _load_mbox(path: Path) -> FeedFile:
    box = mailbox.mbox(str(path), create=False)
    msgs = []
    control = {}
    for m in box:
        ctl = m.get("X-Restore-Control")
        if ctl:
            control = parse_control(ctl)
            continue
        body = m.get_payload(decode=True)
        body = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(m.get_payload())
        msgs.append({"date": m.get("Date", ""), "subject": m.get("Subject", ""), "body": body})
    box.close()
    return FeedFile(path, "mbox", control, {"messages": msgs})


def load_feed(feed_dir: Path, layouts: dict) -> list[FeedFile]:
    out = []
    for p in sorted(feed_dir.iterdir()):
        if not p.is_file():
            continue
        f = load(p, layouts)
        if f is not None and f.control:
            out.append(f)
    return out
'''
REPAIRED['src/restorekit/globs.py'] = r'''"""Exclusion pattern dialect (restore specification revision 4.1, section 7)."""

from __future__ import annotations

import functools
import re
import unicodedata


@functools.lru_cache(maxsize=4096)
def _segment(seg: str) -> re.Pattern:
    out, i = "", 0
    while i < len(seg):
        c = seg[i]
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif c == "[":
            j = seg.find("]", i + 1)
            if j == -1:
                out += re.escape(c)
            else:
                body = seg[i + 1:j]
                neg = body.startswith("!")
                if neg:
                    body = body[1:]
                out += "[" + ("^" if neg else "") + "".join("\\" + ch if ch in "\\^]" else ch for ch in body) + "]"
                i = j
        else:
            out += re.escape(c)
        i += 1
    return re.compile(out)


def _match_comps(pat: str, comps: list[str]) -> bool:
    if "/" not in pat:
        return bool(comps) and _segment(pat).fullmatch(comps[-1]) is not None
    segs = [s for s in pat.strip("/").split("/") if s]

    @functools.lru_cache(maxsize=None)
    def m(i: int, j: int) -> bool:
        if i == len(segs):
            return j == len(comps)
        if segs[i] == "**":
            return any(m(i + 1, k) for k in range(j, len(comps) + 1))
        return j < len(comps) and _segment(segs[i]).fullmatch(comps[j]) is not None and m(i + 1, j + 1)

    return m(0, 0)


def match(pattern: str, path: str) -> bool:
    pat = unicodedata.normalize("NFC", pattern).casefold()
    comps = [c for c in unicodedata.normalize("NFC", path).casefold().split("/") if c]
    if pat.endswith("/"):
        pat = pat.rstrip("/")
        return any(_match_comps(pat, comps[:i]) for i in range(1, len(comps)))
    return _match_comps(pat, comps)
'''
REPAIRED['src/restorekit/paths.py'] = r'''"""Raw catalog paths to canonical share paths, identity keys and link targets."""

from __future__ import annotations

import re
import unicodedata


def key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def under(path: str, prefix: str) -> bool:
    a, b = key(path), key(prefix.rstrip("/"))
    return a == b or a.startswith(b + "/")


class Unsafe(Exception):
    pass


class Outside(Exception):
    pass


def _strip_root(raw: str, roots: list[str], windows: bool) -> str | None:
    best = None
    for root in roots:
        r = root.replace("\\", "/") if windows else root
        s = raw.replace("\\", "/") if windows else raw
        a, b = (s.lower(), r.lower()) if windows else (s, r)
        if a == b or a.startswith(b + "/"):
            if best is None or len(r) > len(best[0]):
                best = (r, s[len(r):])
    return None if best is None else best[1]


def _components(rest: str, windows: bool, base: list[str] | None = None) -> list[str]:
    comps = list(base or [])
    for c in rest.split("/"):
        if windows and c not in (".", ".."):
            c = c.rstrip(". ")
        if c in ("", "."):
            continue
        if c == "..":
            if not comps:
                raise Unsafe(rest)
            comps.pop()
            continue
        comps.append(unicodedata.normalize("NFC", c))
    return comps


def canonical(raw: str, roots: list[str], windows: bool) -> str:
    rest = _strip_root(raw, roots, windows)
    if rest is None:
        raise Outside(raw)
    return "/" + "/".join(_components(rest, windows))


def resolve_link(target: str, link_path: str, roots: list[str], windows: bool) -> str | None:
    rest = _strip_root(target, roots, windows)
    if rest is not None:
        try:
            return "/" + "/".join(_components(rest, windows))
        except Unsafe:
            return None
    t = target.replace("\\", "/") if windows else target
    if t.startswith("/") or (windows and re.match(r"^[A-Za-z]:", t)):
        return None
    base = [c for c in link_path.split("/")[:-1] if c]
    out = list(base)
    for c in t.split("/"):
        if c in ("", "."):
            continue
        if c == "..":
            if not out:
                return None
            out.pop()
        else:
            out.append(unicodedata.normalize("NFC", c))
    return "/" + "/".join(out)
'''
REPAIRED['src/restorekit/report.py'] = r'''"""Writing the restore deliverables (restore specification section 11)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

MANIFEST = ["path", "kind", "size", "allocated", "sha256", "mode", "mtime_utc", "owner", "source_set", "container",
            "media", "copy", "hardlink_group", "link_target"]
EXCLUSIONS = ["path", "kind", "reason", "detail"]
PULL = ["media_id", "vault", "copy", "containers", "read_bytes", "read_gib"]


def _csv(path: Path, columns: list[str], rows: list[dict], digest: str) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(columns)
    for row in rows:
        w.writerow([row[c] for c in columns])
    buf.write(f"#custody={digest} rows={len(rows)}\n")
    path.write_bytes(buf.getvalue().encode("utf-8"))


def write_all(out: Path, result: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    d = result["digest"]
    _csv(out / "restore_manifest.csv", MANIFEST, result["manifest"], d)
    _csv(out / "exclusions.csv", EXCLUSIONS, result["exclusions"], d)
    _csv(out / "media_pull_list.csv", PULL, result["pull"], d)
    (out / "restore_chain.json").write_text(json.dumps(result["chain"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "reconciliation.json").write_text(json.dumps(result["recon"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
'''
REPAIRED['src/restorekit/values.py'] = r'''"""Value notations of the feed: identifiers, numbers, timestamps, modes and sentinels."""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
FT_EPOCH = dt.datetime(1601, 1, 1, tzinfo=UTC)
XL_1900 = dt.datetime(1899, 12, 30, tzinfo=UTC)
XL_1904 = dt.datetime(1904, 1, 1, tzinfo=UTC)
ID_WIDTH = {"BS": 5, "E": 7, "CT": 7, "RC": 7, "MD": 5}


class Folds:
    """Identifier fold table (PATHCONV Appendix C, identifier scope)."""

    table: dict[str, str] = {}


def norm_id(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = "".join(Folds.table.get(c, c) for c in s).upper().replace("_", "-")
    m = re.fullmatch(r"([A-Z]+)-?0*(\d+)", s)
    if not m or m.group(1) not in ID_WIDTH:
        return s
    return f"{m.group(1)}-{int(m.group(2)):0{ID_WIDTH[m.group(1)]}d}"


def norm_hash(value) -> str:
    s = str(value or "").strip().lower()
    return s[7:] if s.startswith("sha256:") else s


def parse_int(value, locale: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    sep = {"en_US": ",", "de_DE": ".", "fr_FR": "\u202f"}.get(locale)
    if sep:
        s = s.replace(sep, "")
    return int(s)


def parse_dec(value, locale: str) -> Decimal:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    s = str(value).strip()
    if locale in ("de_DE", "fr_FR"):
        s = s.replace("\u202f", "").replace(".", "").replace(",", ".")
    elif locale == "en_US":
        s = s.replace(",", "")
    return Decimal(s)


def size_of(row: dict, locale: str) -> int | None:
    for key in ("size", "size_bytes", "bytes"):
        if key in row and row[key] not in ("", None):
            return parse_int(row[key], locale)
    if "size_kib" in row and row["size_kib"] not in ("", None):
        v = parse_dec(row["size_kib"], locale) * 1024
        return int(v)
    return None


SENTINEL_TEXT = ("0000-00-00",)


def parse_ts(value, kind: str, tz: str | None = None, date1904: bool = False):
    """Returns an aware UTC datetime, 'SENTINEL', or None for an empty cell."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if kind in ("utc", "iso", "local"):
        s = str(value).strip()
        if s.startswith("0000-00-00"):
            return "SENTINEL"
        if kind == "local":
            wall = dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            return wall.replace(tzinfo=ZoneInfo(tz or "UTC"), fold=0).astimezone(UTC)
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t.astimezone(UTC)
    n = int(value) if not isinstance(value, float) else value
    if kind == "epoch":
        return "SENTINEL" if n == 0 else EPOCH + dt.timedelta(seconds=n)
    if kind == "ms":
        return "SENTINEL" if n == -1 else EPOCH + dt.timedelta(milliseconds=n)
    if kind == "ft":
        return "SENTINEL" if n == 0 else FT_EPOCH + dt.timedelta(microseconds=n // 10)
    if kind == "xl":
        if float(n) == 0:
            return "SENTINEL"
        base = XL_1904 if date1904 else XL_1900
        return base + dt.timedelta(seconds=round(float(n) * 86400))
    raise ValueError(kind)


def as_wall_in(t: dt.datetime, tz: str) -> dt.datetime:
    """FAT rule: the digits of the value are the client's wall-clock time."""
    wall = t.astimezone(UTC).replace(tzinfo=None)
    return wall.replace(tzinfo=ZoneInfo(tz), fold=0).astimezone(UTC)


def iso_z(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_mode(row: dict) -> int | None:
    for key in ("mode_oct", "mode_sym", "mode_dec", "st_mode"):
        v = row.get(key)
        if v in (None, ""):
            continue
        s = str(v).strip()
        if key == "mode_dec":
            return int(s)
        if key == "mode_oct":
            return int(s, 8)
        if key == "st_mode":
            return int(s, 8) & 0o7777
        bits = 0
        trip = s[1:10]
        for i, (shift, special) in enumerate(((6, 0o4000), (3, 0o2000), (0, 0o1000))):
            r, w, x = trip[i * 3:i * 3 + 3]
            bits |= (4 if r == "r" else 0) << shift
            bits |= (2 if w == "w" else 0) << shift
            if x in ("x", "s", "t"):
                bits |= 1 << shift
            if x in ("s", "S", "t", "T"):
                bits |= special
        return bits
    return None


def mode_out(mode: int | None, attrs: str | None) -> str:
    if mode is None:
        return "0444" if "R" in (attrs or "") else "0644"
    return f"{(mode & 0o7777) & ~0o6000:04o}"


def truthy(v) -> bool:
    return str(v).strip().lower() in ("y", "1", "true")
'''


def extract_and_repair(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile("/app/data/project.zip") as z:
        names = z.namelist()
        root = names[0].split("/", 1)[0] + "/"
        for name in names:
            if name.endswith("/"):
                continue
            rel = name[len(root):] if name.startswith(root) else name
            dest = project / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(name))
    for rel, text in REPAIRED.items():
        dest = project / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def write_zip(project: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(project.rglob("*")):
            if p.is_dir() or "__pycache__" in p.parts or p.suffix == ".pyc":
                continue
            info = zipfile.ZipInfo("restorekit-2.4.0/" + p.relative_to(project).as_posix(), (2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, p.read_bytes())


if __name__ == "__main__":
    if sys.argv[1] == "--zip":
        write_zip(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        extract_and_repair(Path(sys.argv[1]))
