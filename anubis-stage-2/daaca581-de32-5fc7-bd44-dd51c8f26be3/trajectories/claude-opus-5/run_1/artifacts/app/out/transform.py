#!/usr/bin/env python3
"""KVEC monthly settlement engine.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>
"""
import sys
import os
import re
import csv
import json
import sqlite3
import unicodedata
import html
import datetime as dt
import configparser
import tomllib
import warnings
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore", module="openpyxl")

import yaml
import openpyxl
import docx
import pypdf
import pyarrow.parquet as pq

getcontext().prec = 60

TZ = ZoneInfo("America/Chicago")
UTC = dt.timezone.utc
D0 = Decimal(0)
Q3 = Decimal("0.001")
Q5 = Decimal("0.00001")
Q6 = Decimal("0.000001")

MONTH_START = dt.date(2025, 11, 1)
MONTH_END = dt.date(2025, 11, 30)
BOUNDARY_DATES = [MONTH_START + dt.timedelta(days=i) for i in range(31)]
SETTLE_DAYS = [MONTH_START + dt.timedelta(days=i) for i in range(30)]
HOLD_CUTOFF = dt.datetime(2025, 12, 3, 17, 0, tzinfo=TZ)

HES_FILE_PREFIX = {
    "aurora": "AUR",
    "borealis": "BOR",
    "cirrus": "CIR",
    "delta": "DLT",
    "fjord": "FJD",
    "cis": "CIS",
}


# ----------------------------------------------------------------- utilities
def rhe(x):
    """Round half-even to integer."""
    return int(Decimal(x).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def q(x, exp):
    return Decimal(x).quantize(exp, rounding=ROUND_HALF_EVEN)


CYR = {"\u041a": "K", "\u0410": "A", "\u0421": "C", "\u043a": "K", "\u0430": "A", "\u0441": "C"}


def norm_id(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = "".join(CYR.get(c, c) for c in s)
    s = re.sub(r"\s+", "", s)
    return s.upper()


def _pad(s, prefix, width):
    m = re.fullmatch(prefix + r"(\d+)", s)
    if m:
        return prefix + m.group(1).zfill(width)
    return s


def norm_meter(s):
    return _pad(norm_id(s), "KV", 7)


def norm_account(s):
    return _pad(norm_id(s), "AC", 8)


def norm_fixture(s):
    return _pad(norm_id(s), "FX", 6)


def norm_sp(s):
    return _pad(norm_id(s).replace("-", ""), "SP", 9)


def norm_feeder(s):
    s = norm_id(s)
    m = re.search(r"(\d+)", s)
    if m:
        return "F%02d" % int(m.group(1))
    return s


def norm_eui(s):
    return norm_id(s).replace(":", "").replace("-", "")


def norm_legacy(s):
    s = norm_id(s).replace("-", "")
    m = re.fullmatch(r"L(\d+)", s)
    if m:
        return "L-" + m.group(1).zfill(6)
    return s


EXCEL_EPOCH = dt.date(1899, 12, 30)


def parse_date(v):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return EXCEL_EPOCH + dt.timedelta(days=int(v))
    s = str(v).strip()
    if not s or s.upper() in ("-", "--", "---", "NONE", "NULL", "N/A", "OPEN"):
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(?:[T ]|$)", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r"(\d+)(?:\.\d+)?", s)
    if m:
        return EXCEL_EPOCH + dt.timedelta(days=int(m.group(1)))
    raise ValueError("bad date %r" % (v,))


def parse_naive(s):
    """Naive local timestamp from several printed layouts."""
    s = str(s).strip().replace("T", " ")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})[ ]+(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        y, mo, da, hh, mi, ss = m.groups()
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})[ ]+(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
        if not m:
            raise ValueError("bad timestamp %r" % (s,))
        mo, da, y, hh, mi, ss = m.groups()
    return dt.datetime(int(y), int(mo), int(da), int(hh), int(mi), int(ss or 0))


def parse_utc(v):
    """Instant from an epoch number or an ISO timestamp (UTC when naive)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return dt.datetime.fromtimestamp(int(v), UTC)
    s = str(v).strip()
    if re.fullmatch(r"-?\d+", s):
        return dt.datetime.fromtimestamp(int(s), UTC)
    when = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC)


def dec_auto(v):
    """Decimal from a document value; decimal commas tolerated."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int,)):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    s = str(v).strip().replace("+", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return Decimal(s)


def file_lines(path):
    """Split a text file into records on LF or bare CR; decode per line."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    out = []
    for raw in re.split(rb"\r\n|\n|\r", data):
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("cp1252"))
    if out and out[-1] == "":
        out.pop()
    return out


def csv_dicts(path, delimiter=","):
    lines = [l for l in file_lines(path) if l.strip() and not l.startswith("#")]
    return list(csv.DictReader(lines, delimiter=delimiter))


def pipe_rows(lines, header_sets):
    """Yield dicts from pipe-delimited tables, tracking header-order changes."""
    sets = [frozenset(h) for h in header_sets]
    cur = None
    for line in lines:
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(c and set(c) <= set("-: ") for c in cells):
            continue
        key = frozenset(c.lower() for c in cells)
        if key in sets:
            cur = [c.lower() for c in cells]
            continue
        if cur is None or len(cells) != len(cur):
            continue
        yield dict(zip(cur, cells))


def pdf_lines(path):
    reader = pypdf.PdfReader(path)
    out = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        out.extend(txt.split("\n"))
    return out


def docx_tables(path):
    """Yield (list of dicts) per table in a .docx, plus all paragraph text."""
    document = docx.Document(path)
    paras = [p.text for p in document.paragraphs]
    tables = []
    for table in document.tables:
        rows = [[c.text.strip() for c in r.cells] for r in table.rows]
        if not rows:
            continue
        head = [h.lower() for h in rows[0]]
        tables.append([dict(zip(head, r)) for r in rows[1:] if len(r) == len(head)])
    return paras, tables


def docx_lines(path):
    """Paragraphs and pipe-joined table rows of a .docx, in document order."""
    document = docx.Document(path)
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    out = []
    for child in document.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            out.append(Paragraph(child, document).text)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                out.append(" | ".join(c.text.strip() for c in row.cells))
    return out


TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<(t[hd])[^>]*>(.*?)</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")


def html_rows(path):
    """Yield dicts for every <tr> data row, tracking <th> header rows."""
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", "replace")
    cur = None
    for m in TR_RE.finditer(text):
        cells = CELL_RE.findall(m.group(0))
        if not cells:
            continue
        kinds = {k.lower() for k, _ in cells}
        vals = [html.unescape(TAG_RE.sub("", v)).strip() for _, v in cells]
        if "th" in kinds:
            cur = [v.lower() for v in vals]
            continue
        if cur is None or len(vals) != len(cur):
            continue
        yield dict(zip(cur, vals))


def local_dt(date, hh, mm=0, ss=0):
    return dt.datetime(date.year, date.month, date.day, hh, mm, ss, tzinfo=TZ)


def to_utc(d):
    return d.astimezone(UTC)


def local_date_of(instant):
    return instant.astimezone(TZ).date()


def ratio_mult(s):
    s = str(s).strip()
    m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*$", s)
    if m:
        return int(m.group(1))
    return int(Decimal(s))


# --------------------------------------------------------------------- loader
class Data:
    def __init__(self, root):
        self.root = root

    def p(self, name):
        return os.path.join(self.root, name)

    def exists(self, name):
        return os.path.exists(self.p(name))


def load_manual(d):
    """Table F, Appendix R schedule register from the revision 3 manual."""
    paras, tables = docx_tables(d.p("kvec_settlement_procedures_manual.docx"))
    feeders = {}
    schedule = {}
    for tab in tables:
        if not tab:
            continue
        keys = set(tab[0])
        if {"feeder", "substation", "territory", "loss_pct"} <= keys:
            for r in tab:
                feeders[norm_feeder(r["feeder"])] = {
                    "substation": r["substation"].strip().lower(),
                    "territory": r["territory"].strip().upper(),
                    "loss_pct": dec_auto(r["loss_pct"]),
                }
        elif {"meter_id", "read_time", "effective_from"} <= keys:
            for r in tab:
                m = norm_meter(r["meter_id"])
                schedule.setdefault(m, []).append(
                    (parse_date(r["effective_from"]), 0, r["read_time"].strip())
                )
    return feeders, schedule


def load_rev4_errata(d, mailbox_decisions):
    """Approved errata from the revision 4 draft errata index."""
    _paras, tables = docx_tables(d.p("settlement_procedures_manual_rev4_draft.docx"))
    out = []
    for tab in tables:
        if not tab:
            continue
        if {"erratum", "table", "key", "value", "effective_from", "cr"} <= set(tab[0]):
            for r in tab:
                cr = r["cr"].strip().upper()
                if mailbox_decisions.get(cr) != "APPROVED":
                    continue
                out.append(r)
    return out


def load_mailbox(d):
    """Return (hold set, release map, CAB decisions)."""
    lines = file_lines(d.p("mdm_ops_mailbox_2025-11.mbox"))
    holds = set()
    releases = {}
    decisions = {}
    cur = {}
    date = None

    def flush():
        if not cur:
            return
        typ = cur.get("notice type", "").strip().upper()
        if typ in ("HOLD", "RELEASE"):
            meter = norm_meter(cur.get("meter", ""))
            rd = parse_date(cur.get("read date", "").strip())
            if typ == "HOLD":
                holds.add((meter, rd))
            else:
                prev = releases.get((meter, rd))
                if prev is None or (date is not None and date < prev):
                    releases[(meter, rd)] = date
        cur.clear()

    for line in lines:
        if line.startswith("From ") and " @" not in line[:6]:
            flush()
            date = None
            continue
        if line.lower().startswith("date:"):
            try:
                from email.utils import parsedate_to_datetime

                date = parsedate_to_datetime(line.split(":", 1)[1].strip())
            except Exception:
                date = None
            continue
        if line.lower().startswith("subject:"):
            subj = line.split(":", 1)[1].strip()
            m = re.search(r"CAB decision (CR-\d+):\s*([A-Z]+)", subj)
            if m:
                decisions[m.group(1).upper()] = m.group(2).upper()
            continue
        m = re.match(r"^(Notice type|Meter|Read date|Decision):\s*(.*)$", line)
        if m:
            cur[m.group(1).lower()] = m.group(2)
            continue
        m = re.match(r"^Change advisory board decision for (CR-\d+)", line)
        if m:
            cur["cr"] = m.group(1).upper()
    flush()
    return holds, releases, decisions


def load_registry(d):
    rows = []
    for name in ("mdm_registry_north.db", "mdm_registry_east.db", "mdm_registry_southwest.db"):
        if not d.exists(name):
            continue
        con = sqlite3.connect(d.p(name))
        for r in con.execute(
            "select meter_id, account_id, multiplier, hes, valid_from, valid_to, change_reason"
            " from meter_attr_history"
        ):
            rows.append(r)
        con.close()
    reg = {}
    for meter_id, account_id, multiplier, hes, vf, vt in [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]:
        m = norm_meter(meter_id)
        reg.setdefault(m, []).append(
            {
                "account": norm_account(account_id),
                "multiplier": int(multiplier),
                "hes": (hes or "").strip().upper(),
                "valid_from": parse_date(vf),
                "valid_to": parse_date(vt) if vt else None,
            }
        )
    for m in reg:
        reg[m].sort(key=lambda r: r["valid_from"])
    return reg


def load_sp_xref(d):
    out = {}
    name = "dw_registry_snapshot_2025-12-03.db"
    if not d.exists(name):
        return out
    con = sqlite3.connect(d.p(name))
    for spid, meter, vf, vt, status in con.execute(
        "select spid, meter_id, valid_from_utc, valid_to_utc, status from sp_meter_xref"
    ):
        if (status or "").strip().upper() == "VOID":
            continue
        out.setdefault(norm_sp(spid), []).append(
            (
                dt.datetime.fromisoformat(vf.replace("Z", "+00:00")) if vf else None,
                dt.datetime.fromisoformat(vt.replace("Z", "+00:00")) if vt else None,
                norm_meter(meter),
            )
        )
    con.close()
    return out


def load_crosswalk_legacy(d):
    """ACTIVE legacy id -> meter from the migration workbook Crosswalk sheet."""
    out = {}
    wb = openpyxl.load_workbook(d.p("meter_registry_migration_wave3.xlsx"), data_only=True, read_only=True)
    for ws in wb.worksheets:
        if ws.title.strip().lower() != "crosswalk":
            continue
        head = None
        for row in ws.iter_rows(values_only=True):
            vals = list(row)
            if head is None:
                low = [str(v).strip().lower() if v is not None else "" for v in vals]
                if "legacy_id" in low and "meter_id" in low:
                    head = low
                continue
            rec = dict(zip(head, vals))
            if str(rec.get("link_status", "")).strip().upper() != "ACTIVE":
                continue
            out[norm_legacy(rec["legacy_id"])] = norm_meter(rec["meter_id"])
    wb.close()
    return out


def sheet_dicts(path, want=None):
    """All rows of all sheets of a workbook as dicts (per-sheet header row)."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        head = None
        for row in ws.iter_rows(values_only=True):
            vals = list(row)
            if head is None:
                low = [str(v).strip().lower() if v is not None else "" for v in vals]
                if want is None or want <= set(low):
                    head = low
                continue
            if all(v is None for v in vals):
                continue
            out.append(dict(zip(head, vals)))
    wb.close()
    return out


def load_yaml(path):
    loader = yaml.CSafeLoader if getattr(yaml, "__with_libyaml__", False) else yaml.SafeLoader
    with open(path, "rb") as fh:
        return yaml.load(fh, Loader=loader)


def as_int(v):
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    s = re.sub(r"[,\s]", "", str(v))
    m = re.search(r"-?\d+", s)
    return int(m.group(0)) if m else 0


def g(rec, *names):
    for n in names:
        if n in rec and rec[n] is not None:
            return rec[n]
    return None


def read_ini(path):
    cp = configparser.ConfigParser(strict=False)
    cp.read(path, encoding="utf-8")
    return cp


def sect_id(name, keyword):
    """Section identifier with an optional leading keyword and separator."""
    s = norm_id(name)
    kw = keyword.upper()
    if s.startswith(kw):
        s = s[len(kw):]
    return s.lstrip(":=_")


def effective_pick(entries, date):
    """entries: list of (effective_from, rank, payload); latest <= date wins."""
    best = None
    for eff, rank, payload in entries:
        if eff <= date and (best is None or (eff, rank) >= (best[0], best[1])):
            best = (eff, rank, payload)
    return best[2] if best else None


# ------------------------------------------------------------ head-end files
class ReadRow:
    __slots__ = ("file", "hes", "ordinal", "key", "reported", "seq", "imp", "exp",
                 "est", "period", "meter")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def parse_aurora(path, profile, ordinal_start=0):
    fmts = profile.get("timestamp_formats") or ["%Y-%m-%d %H:%M:%S"]
    missing = set(str(x) for x in (profile.get("missing_values") or []))
    tscol = profile.get("timestamp_column", "read_local")
    rows = []
    header = None
    ordinal = ordinal_start
    for line in file_lines(path):
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        cells = next(csv.reader([line]))
        if header is None or (len(cells) == len(header) and set(cells) == set(header)):
            header = cells
            continue
        rec = dict(zip(header, cells))
        ordinal += 1
        ts = rec.get(tscol, "").strip()
        when = None
        for f in fmts:
            try:
                when = dt.datetime.strptime(ts, f)
                break
            except ValueError:
                continue
        if when is None:
            continue
        reported = when.replace(tzinfo=TZ)
        rows.append(
            ReadRow(
                file=os.path.basename(path), hes="AUR", ordinal=ordinal,
                key=norm_meter(rec.get("meter_id", "")), reported=reported,
                seq=int(str(rec.get("seq", "0")).strip() or 0),
                imp=_aur_val(rec.get("register_import"), missing),
                exp=_aur_val(rec.get("register_export"), missing),
                est=False,
            )
        )
    return rows, ordinal - ordinal_start


def _aur_val(s, missing):
    if s is None:
        return None
    s = s.strip()
    if s in missing:
        return None
    s = s.replace(",", "")
    if not s:
        return None
    return Decimal(s)


ATTR_RE = re.compile(r"([A-Za-z_:][\w:.-]*)\s*=\s*\"([^\"]*)\"")
READ_RE = re.compile(r"<(Read|Rd)\b([^>]*)>(.*?)</\1>", re.S)
CH_RE = re.compile(r"<Ch\b([^>]*)>([^<]*)</Ch>", re.S)


def parse_borealis(path, chanmap, ordinal_start=0):
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8", "replace")
    rows = []
    ordinal = ordinal_start
    for m in READ_RE.finditer(text):
        attrs = dict(ATTR_RE.findall(m.group(2)))
        ordinal += 1
        meter = norm_meter(attrs.get("meter") or attrs.get("m") or "")
        ts = attrs.get("ts") or attrs.get("t") or ""
        try:
            reported = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if reported.tzinfo is None:
            reported = reported.replace(tzinfo=TZ)
        seq = attrs.get("seq") or attrs.get("sq") or "0"
        chans = {}
        for cm in CH_RE.finditer(m.group(3)):
            ca = dict(ATTR_RE.findall(cm.group(1)))
            if (ca.get("q") or "").upper() == "MISSING":
                continue
            txt = cm.group(2).strip()
            if not txt:
                continue
            unit = (ca.get("unit") or "kWh").strip()
            val = dec_auto(txt)
            if unit.lower() == "wh":
                val = val / 1000
            elif unit.lower() != "kwh":
                continue
            try:
                chans[int(ca.get("n"))] = val
            except (TypeError, ValueError):
                continue
        cfg = effective_pick(chanmap.get(meter, []), local_date_of(reported))
        if cfg is None:
            imp = exp = None
        else:
            imp = chans.get(cfg[0])
            exp = chans.get(cfg[1])
        rows.append(
            ReadRow(file=os.path.basename(path), hes="BOR", ordinal=ordinal, key=meter,
                    reported=reported, seq=int(seq), imp=imp, exp=exp, est=False)
        )
    return rows, ordinal - ordinal_start


def parse_cirrus(path, firmware, period, ordinal_start=0):
    rows = []
    ordinal = ordinal_start
    schema = 1
    for line in file_lines(path):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if "_schema" in rec:
            schema = int(rec["_schema"])
            continue
        ordinal += 1
        dev = norm_eui(rec.get("dev") or rec.get("device") or rec.get("device_eui") or "")
        ts = rec.get("ts", rec.get("t"))
        if ts is None:
            continue
        reported = dt.datetime.fromtimestamp(int(ts), UTC)
        sep = "."
        fw = effective_pick(firmware.get(dev, []), local_date_of(reported))
        if fw is not None:
            sep = fw
        imp = _cir_val(rec.get("imp", rec.get("import")), sep)
        exp = _cir_val(rec.get("exp", rec.get("export")), sep)
        seq = rec.get("seq", rec.get("sequence", rec.get("sq", 0)))
        rows.append(
            ReadRow(file=os.path.basename(path), hes="CIR", ordinal=ordinal, key=dev,
                    reported=reported, seq=int(seq or 0), imp=imp, exp=exp, est=False,
                    period=period)
        )
    return rows, ordinal - ordinal_start


def _cir_val(v, sep):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return Decimal(repr(v)) if isinstance(v, float) else Decimal(v)
    s = str(v).strip()
    if not s or s.upper() == "ERR":
        return None
    if sep == ",":
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    return Decimal(s)


def parse_delta(path, scaling_default, ordinal_start=0):
    table = pq.read_table(path)
    cols = {name: table.column(name).to_pylist() for name in table.column_names}
    n = table.num_rows
    rows = []
    ordinal = ordinal_start
    for i in range(n):
        ordinal += 1
        spid = norm_sp(cols["spid"][i])
        serial = cols["read_serial"][i]
        if serial is None:
            continue
        secs = int(Decimal(repr(float(serial))) * 86400 + Decimal("0.5"))
        naive = dt.datetime(1899, 12, 30) + dt.timedelta(seconds=secs)
        reported = naive.replace(tzinfo=TZ)
        rows.append(
            ReadRow(file=os.path.basename(path), hes="DLT", ordinal=ordinal, key=spid,
                    reported=reported, seq=int(cols["load_id"][i] or 0),
                    imp=cols["import_raw"][i], exp=cols["export_raw"][i],
                    est=bool(cols.get("est_flag", [0] * n)[i]))
        )
    return rows, ordinal - ordinal_start


def parse_cis(path, layouts, dials, ordinal_start=0):
    rows = []
    ordinal = ordinal_start
    layout = layouts.get(1)
    for line in file_lines(path):
        if not line:
            continue
        kind = line[0].upper()
        if kind == "L":
            m = re.match(r"L(\d+)", line)
            if m:
                layout = layouts.get(int(m.group(1)), layout)
            continue
        if kind != "D":
            continue
        ordinal += 1
        if layout is None:
            continue

        def fld(name):
            span = layout.get(name)
            if span is None:
                return ""
            return line[span[0] - 1:span[1]]

        legacy = norm_legacy(fld("legacy_id"))
        ds = fld("date").strip()
        ts = fld("time").strip()
        if len(ds) != 7 or not ds.isdigit():
            continue
        day = dt.date(int(ds[:4]), 1, 1) + dt.timedelta(days=int(ds[4:]) - 1)
        tv = int(ts or 0)
        if tv == 2400:
            reported = local_dt(day + dt.timedelta(days=1), 0, 0)
        else:
            reported = local_dt(day, tv // 100, tv % 100)
        dial = dials.get(legacy, 1)
        imp = _cis_val(fld("import"), dial)
        exp = _cis_val(fld("export"), dial)
        seq = fld("seq").strip() or "0"
        rows.append(
            ReadRow(file=os.path.basename(path), hes="CIS", ordinal=ordinal, key=legacy,
                    reported=reported, seq=int(seq), imp=imp, exp=exp, est=False)
        )
    return rows, ordinal - ordinal_start


def _cis_val(raw, dial):
    s = raw.strip()
    if not s:
        return None
    if set(s) == {"9"}:
        return None
    if not s.isdigit():
        return None
    return Decimal(s) * dial / 1000


FJORD_ALIASES = {"SEQ": "seq", "METER_ID": "meter", "EPOCH_MS": "ts_ms", "IMP": "import_kwh",
                 "EXP": "export_kwh", "FLG": "flags"}
FJORD_COLS = {"meter", "ts_ms", "import_kwh", "export_kwh", "flags", "seq"}


def parse_fjord(path, aliases, missing, ordinal_start=0):
    rows = []
    revs = []
    ordinal = ordinal_start
    header = None
    for line in file_lines(path):
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        cells = line.split("\t")
        mapped = [aliases.get(c.strip(), c.strip()) for c in cells]
        if set(mapped) >= FJORD_COLS and len(set(mapped)) == len(mapped):
            header = mapped
            continue
        if cells[0].strip().upper() == "REV":
            ordinal += 1
            revs.append((norm_meter(cells[1]), parse_date(cells[3].strip())))
            continue
        if header is None:
            continue
        ordinal += 1
        rec = dict(zip(header, cells))
        ts = rec.get("ts_ms", "").strip()
        if not ts:
            continue
        reported = dt.datetime.fromtimestamp(int(ts) // 1000, UTC)
        rows.append(
            ReadRow(file=os.path.basename(path), hes="FJD", ordinal=ordinal,
                    key=norm_meter(rec.get("meter", "")), reported=reported,
                    seq=int((rec.get("seq") or "0").strip() or 0),
                    imp=_fj_val(rec.get("import_kwh"), missing),
                    exp=_fj_val(rec.get("export_kwh"), missing), est=False)
        )
    return rows, revs, ordinal - ordinal_start


def _raw_scaled(raw, missing, scale):
    if raw is None:
        return None
    val = Decimal(str(raw))
    if val == Decimal(missing):
        return None
    return val / scale


def _fj_val(s, missing):
    if s is None:
        return None
    s = s.strip()
    if not s or s in missing:
        return None
    return dec_auto(s)


# ------------------------------------------------------------------- engine
class Settlement:
    def __init__(self, data_dir):
        self.d = Data(data_dir)
        self.load_reference()

    # ---------------------------------------------------------- reference
    def load_reference(self):
        d = self.d
        self.holds, self.releases, cab = load_mailbox(d)
        self.feeders, self.schedule = load_manual(d)
        for e in load_rev4_errata(d, cab):
            tab = e["table"].strip().upper()
            if tab == "L":
                f = norm_feeder(e["key"])
                if f in self.feeders:
                    self.feeders[f]["loss_pct"] = dec_auto(e["value"])
            elif tab == "R":
                m = norm_meter(e["key"])
                self.schedule.setdefault(m, []).append(
                    (parse_date(e["effective_from"]), 1, e["value"].strip())
                )

        self.meter_feeder = {}
        for r in pipe_rows(file_lines(d.p("settlement_data_contract.md")),
                           [{"meter_id", "feeder"}]):
            self.meter_feeder[norm_meter(r["meter_id"])] = norm_feeder(r["feeder"])

        self.reg = load_registry(d)
        self.meters = sorted(self.reg)
        self.sp_xref = load_sp_xref(d)
        self.legacy_map = load_crosswalk_legacy(d)

        cp = read_ini(d.p("register_scaling.ini"))
        self.decimals = {}
        for sec in cp.sections():
            key = norm_meter(sect_id(sec, "meter"))
            if not key.startswith("KV"):
                continue
            self.decimals[key] = as_int(g(cp[sec], "decimals", "resolution"))

        roll = tomllib.load(open(d.p("register_rollover.toml"), "rb"))
        self.roll_default = int(roll.get("defaults", {}).get("digits", 6))
        self.digits = {}
        for r in roll.get("register", []):
            self.digits[norm_meter(g(r, "meter_id", "meter"))] = \
                int(g(r, "digits", "dial_digits"))

        off = tomllib.load(open(d.p("meter_clock_offsets.toml"), "rb"))
        self.offsets = {}
        for r in off.get("offset", []):
            self.offsets[norm_meter(g(r, "meter_id", "meter"))] = \
                int(g(r, "offset_s", "ahead_s"))

        self.load_events()
        self.load_orders()
        self.load_multipliers()
        self.load_accuracy()
        self.load_controls()
        self.load_mdm_tables()
        self.load_accounts()
        self.load_tariffs()
        self.load_calendar()
        self.load_lighting()

    def load_events(self):
        self.clock_sync = {}
        self.resets = {}
        for line in file_lines(self.d.p("collector_events_2025-11.log")):
            if " CLOCK_SYNC " in line:
                m = re.search(r"^(\S+) .*CLOCK_SYNC meter=(\S+)", line)
                if m:
                    t = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                    self.clock_sync[norm_meter(m.group(2))] = t
            elif " REGISTER_RESET " in line:
                m = re.search(
                    r"^(\S+) .*REGISTER_RESET meter=(\S+) pre_reset_kwh=(\S+) post_reset_kwh=(\S+)",
                    line)
                if m:
                    t = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                    self.resets.setdefault(norm_meter(m.group(2)), []).append(
                        (t, q(dec_auto(m.group(3)), Q3), q(dec_auto(m.group(4)), Q3)))

    def load_orders(self):
        self.exch_out = {}
        self.exch_in = {}
        self.exch_final = {}
        self.exch_init = {}
        self.ct_orders = {}
        for line in file_lines(self.d.p("field_service_orders.jsonl")):
            if not line.strip():
                continue
            o = json.loads(line)
            if (o.get("status") or "").upper() != "COMPLETED":
                continue
            typ = (o.get("type") or "").upper()
            when = o.get("completed_at") or o.get("ts")
            if not when:
                continue
            t = dt.datetime.fromisoformat(when)
            if typ == "EXCHANGE":
                om = norm_meter(o["old_meter"])
                nm = norm_meter(o["new_meter"])
                self.exch_out[om] = t
                self.exch_in[nm] = t
                self.exch_final[om] = (
                    q(dec_auto(o.get("old_final_import_kwh")), Q3) if o.get("old_final_import_kwh") is not None else None,
                    q(dec_auto(o.get("old_final_export_kwh")), Q3) if o.get("old_final_export_kwh") is not None else None,
                )
                self.exch_init[nm] = (
                    q(dec_auto(o.get("new_initial_import_kwh")), Q3) if o.get("new_initial_import_kwh") is not None else None,
                    q(dec_auto(o.get("new_initial_export_kwh")), Q3) if o.get("new_initial_export_kwh") is not None else None,
                )
            elif typ == "CT_CHANGE":
                m = norm_meter(o["meter"])
                self.ct_orders.setdefault(m, []).append(
                    (t, ratio_mult(o["new_ratio"]),
                     q(dec_auto(o.get("register_at_change_kwh")), Q3)
                     if o.get("register_at_change_kwh") is not None else None))

    def load_multipliers(self):
        events = {}
        for m, rows in self.reg.items():
            for r in rows:
                events.setdefault(m, []).append(
                    (to_utc(local_dt(r["valid_from"], 0)), 0, r["multiplier"]))
        for r in sheet_dicts(self.d.p("ct_ratio_verification_2025.xlsx"),
                             {"verification_id", "meter_id", "verified_on", "action"}):
            if str(r.get("action", "")).strip().upper() != "CORRECT_RATIO":
                continue
            m = norm_meter(r["meter_id"])
            events.setdefault(m, []).append(
                (to_utc(local_dt(parse_date(r["verified_on"]), 0)), 1,
                 ratio_mult(r["measured_ratio"])))
        for m, lst in self.ct_orders.items():
            for t, mult, _val in lst:
                events.setdefault(m, []).append((t, 2, mult))
        self.mult_events = {}
        for m, lst in events.items():
            lst.sort(key=lambda x: (x[0], x[1]))
            self.mult_events[m] = lst

    def multiplier_at(self, meter, instant):
        lst = self.mult_events.get(meter)
        if not lst:
            return 1
        best = 1
        for t, _rank, mult in lst:
            if t <= instant:
                best = mult
            else:
                break
        return best

    def load_accuracy(self):
        _p, tables = docx_tables(self.d.p("meter_accuracy_test_results_2025.docx"))
        best = {}
        for tab in tables:
            for r in tab:
                if "meter_id" not in r:
                    continue
                if (r.get("result") or "").strip().upper() != "FAIL":
                    continue
                date = parse_date(r["test_date"])
                if not (MONTH_START <= date <= MONTH_END):
                    continue
                m = norm_meter(r["meter_id"])
                key = (date, r["test_id"].strip())
                if m not in best or key > best[m][0]:
                    best[m] = (key, date, dec_auto(r["as_found_error_pct"]))
        self.accuracy = {m: (v[1], v[2]) for m, v in best.items()}

    # ------------------------------------------------------- batch control
    def load_controls(self):
        d = self.d
        self.batch_status = {}
        self.batch_rejected = {}
        self.batch_rows_claim = {}
        for line in file_lines(d.p("mdm_batch_control.log")):
            if " BATCH " not in line or "file=" not in line:
                continue
            fm = re.search(r"file=(\S+)", line)
            st = re.search(r"status=(\S+)", line)
            rr = re.search(r"rejected_rows=(\d+)-(\d+)", line)
            rows = re.search(r"rows=(\d+)", line)
            if not fm or not st:
                continue
            f = fm.group(1)
            self.batch_status[f] = st.group(1).upper()
            if rows:
                self.batch_rows_claim[f] = int(rows.group(1))
            if rr:
                self.batch_rejected[f] = (int(rr.group(1)), int(rr.group(2)))

        man = json.load(open(d.p("hes_batch_manifest_2025-11.json")))
        batches = {}
        for r in man.get("records", []):
            if r.get("kind") != "batch":
                continue
            batches.setdefault(r["file"], []).append(r)
        self.manifest = {}
        for f, lst in batches.items():
            live = [r for r in lst if not r.get("superseded")]
            self.manifest[f] = (live or lst)[-1]

        self.quarantine = {}
        for line in file_lines(d.p("hes_ingest_debug.log")):
            if "QUARANTINE" not in line:
                continue
            m = re.search(r"^(\S+) (UN)?QUARANTINE meter=(\S+) read_date=(\S+) hes=(\S+)", line)
            if not m:
                continue
            t = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
            key = (norm_meter(m.group(3)), parse_date(m.group(4)), m.group(5).strip().upper())
            prev = self.quarantine.get(key)
            if prev is None or t >= prev[0]:
                self.quarantine[key] = (t, m.group(2) is None)

        self.known_issues = {}
        for r in pipe_rows(file_lines(d.p("hes_known_issues.md")),
                           [{"issue", "code", "hes", "meter_id", "read_date", "status"}]):
            if r["status"].strip().upper() != "OPEN":
                continue
            key = (norm_meter(r["meter_id"]), parse_date(r["read_date"]),
                   r["hes"].strip().upper())
            self.known_issues[key] = r["code"].strip().upper()

        self.voids = set()
        for r in csv_dicts(d.p("mdm_void_register.csv")):
            if (r.get("reinstated") or "").strip().upper() != "N":
                continue
            self.voids.add((r["hes"].strip().upper(), norm_meter(r["meter_id"]),
                            parse_date(r["read_date"])))

        disputes = {}
        for r in html_rows(d.p("customer_portal_usage_export.html")):
            if "decision" not in r or "meter_id" not in r:
                continue
            key = (norm_meter(r["meter_id"]), parse_date(r["read_date"]))
            dec_date = parse_date(r["decided"])
            prev = disputes.get(key)
            if prev is None or dec_date >= prev[0]:
                disputes[key] = (dec_date, r["decision"].strip().upper())
        self.disputes = {k for k, v in disputes.items() if v[1] == "UPHELD"}

        cp = read_ini(d.p("delta_ingest.ini"))
        self.est_policy = {}
        for sec in cp.sections():
            key = norm_sp(sect_id(sec, "spid"))
            if not key.startswith("SP"):
                continue
            self.est_policy[key] = str(
                g(cp[sec], "est_policy", "policy") or "REJECT").strip().upper()

    # --------------------------------------------------------- mdm tables
    def load_mdm_tables(self):
        d = self.d
        self.corrections = {}
        for r in csv_dicts(d.p("mdm_read_corrections.csv")):
            if (r.get("status") or "").strip().upper() != "VALIDATED":
                continue
            key = (norm_meter(r["meter_id"]), parse_date(r["read_date"]))
            rev = int(r["revision"])
            prev = self.corrections.get(key)
            if prev is None or rev > prev[0]:
                self.corrections[key] = (rev, dec_auto(r["corrected_import_kwh"]),
                                         dec_auto(r["corrected_export_kwh"]))

        reviews = {}
        for r in sheet_dicts(d.p("vee_estimate_review_2025.xlsx"),
                             {"estimate_id", "review_status", "reviewed_on"}):
            eid = str(r["estimate_id"]).strip().upper()
            rd = parse_date(r["reviewed_on"])
            prev = reviews.get(eid)
            if prev is None or rd >= prev[0]:
                reviews[eid] = (rd, str(r["review_status"]).strip().upper())
        self.estimates = {}
        for r in csv_dicts(d.p("mdm_vee_estimates.tsv"), delimiter="\t"):
            eid = r["estimate_id"].strip().upper()
            rev = reviews.get(eid)
            if rev is None or rev[1] != "APPROVED":
                continue
            key = (norm_meter(r["meter_id"]), parse_date(r["read_date"]))
            ver = int(r["version"])
            prev = self.estimates.get(key)
            if prev is None or ver > prev[0]:
                self.estimates[key] = (ver, dec_auto(r["est_import_kwh"]),
                                       dec_auto(r["est_export_kwh"]))

        self.october = {}
        for r in csv_dicts(d.p("mdm_october_close_reads.csv")):
            self.october[norm_meter(r["meter_id"])] = (
                dec_auto(r["register_import_kwh"]), dec_auto(r["register_export_kwh"]),
                (r.get("status") or "").strip().upper())

    # ------------------------------------------------------------ accounts
    def load_accounts(self):
        d = self.d
        self.master = {}
        for r in csv_dicts(d.p("cis_account_master.csv")):
            self.master[norm_account(r["account_id"])] = r

        merges = []
        mj = json.load(open(d.p("account_merges_2025.json")))
        for m in mj.get("merges", []):
            status = (m.get("status") or m.get("state") or "").upper()
            if status != "COMPLETED":
                continue
            merges.append((parse_date(m.get("effective_date") or m.get("effective")),
                           norm_account(m.get("predecessor") or m.get("from_account")),
                           norm_account(m.get("successor") or m.get("to_account"))))
        for r in csv_dicts(d.p("cis_account_master_2025-12.csv")):
            if (r.get("late_posted") or "").strip().upper() != "Y":
                continue
            if not r.get("merged_into") or not r.get("merge_effective"):
                continue
            eff = parse_date(r["merge_effective"])
            if eff > MONTH_END:
                continue
            merges.append((eff, norm_account(r["account_id"]),
                           norm_account(r["merged_into"])))
        self.merges = {}
        for eff, pre, suc in merges:
            self.merges.setdefault(pre, []).append((eff, suc))
        for pre in self.merges:
            self.merges[pre].sort()

        rev_ids = set()
        wb = openpyxl.load_workbook(d.p("account_rate_history_restated.xlsx"),
                                    data_only=True, read_only=True)
        for ws in wb.worksheets:
            if ws.title.strip().lower() != "reversals":
                continue
            head = None
            for row in ws.iter_rows(values_only=True):
                vals = list(row)
                if head is None:
                    low = [str(v).strip().lower() if v is not None else "" for v in vals]
                    if "entry_id" in low:
                        head = low
                    continue
                rec = dict(zip(head, vals))
                if rec.get("entry_id") is not None:
                    rev_ids.add(int(rec["entry_id"]))
        wb.close()

        self.rate_hist = {}
        for r in sheet_dicts(d.p("account_rate_history.xlsx"),
                             {"account_id", "entry_id", "effective_from", "rate_code"}):
            eid = int(r["entry_id"])
            if eid in rev_ids:
                continue
            acct = norm_account(r["account_id"])
            self.rate_hist.setdefault(acct, []).append(
                (parse_date(r["effective_from"]), 0, eid, str(r["rate_code"]).strip().upper()))

        cw = json.load(open(d.p("rate_code_crosswalk_2026.json")))
        self.aliases = {}
        for r in cw.get("records", []):
            if r.get("kind") == "legacy_alias":
                if (r.get("status") or "").upper() == "ACTIVE":
                    self.aliases[str(r["alias"]).strip().upper()] = \
                        str(r["rate_code"]).strip().upper()
        for r in cw.get("records", []):
            if r.get("kind") != "migration":
                continue
            status = (r.get("status") or r.get("state") or "").upper()
            if status == "WITHDRAWN":
                continue
            eff = parse_date(r.get("effective_from") or r.get("effective"))
            if eff is None or eff > MONTH_END:
                continue
            acct = norm_account(r.get("account_id") or r.get("account"))
            code = str(r.get("new_rate_code") or r.get("to_rate_code")).strip().upper()
            self.rate_hist.setdefault(acct, []).append((eff, 1, 0, code))
        for a in self.rate_hist:
            self.rate_hist[a].sort(key=lambda x: (x[0], x[1], x[2]))

        self.disconnects = {}
        _p, tables = docx_tables(d.p("disconnection_register_2025.docx"))
        for tab in tables:
            for r in tab:
                if "meter_id" not in r or "event" not in r:
                    continue
                if (r.get("order_ref") or "").strip().upper().startswith("SOX"):
                    continue
                self.disconnects.setdefault(norm_meter(r["meter_id"]), []).append(
                    (parse_date(r["event_date"]), r["event"].strip().upper()))
        for m in self.disconnects:
            self.disconnects[m].sort()

        self.netmeter = {}
        for r in csv_dicts(d.p("netmetering_enrollments.csv")):
            if (r.get("status") or "").strip().upper() != "APPROVED":
                continue
            self.netmeter.setdefault(norm_meter(r["meter_id"]), []).append(
                (parse_date(r["effective_from"]),
                 parse_date(r["effective_to"]) if r.get("effective_to") else None))

        self.inspections = {}
        for r in sheet_dicts(d.p("export_meter_inspections_2025.xlsx"),
                             {"meter_id", "inspected_on", "result"}):
            self.inspections.setdefault(norm_meter(r["meter_id"]), []).append(
                (parse_date(r["inspected_on"]), str(r["result"]).strip().upper()))
        for m in self.inspections:
            self.inspections[m].sort(key=lambda x: (x[0], 1 if x[1] == "FAIL" else 0))

        self.exempt = set()
        lines = pdf_lines(d.p("ufe_allocation_exemptions_register.pdf"))
        for r in pipe_rows(lines, [{"account", "from", "to", "status", "basis"}]):
            if r["status"].strip().upper() != "ACTIVE":
                continue
            frm = parse_date(r["from"])
            to = parse_date(r["to"]) if r["to"].strip() else None
            if frm <= MONTH_END and (to is None or MONTH_END < to):
                self.exempt.add(norm_account(r["account"]))

    def resolve_account(self, acct, date):
        seen = set()
        while acct and acct not in seen:
            seen.add(acct)
            best = None
            for eff, suc in self.merges.get(acct, []):
                if eff <= date:
                    best = suc
            if best is None:
                return acct
            acct = best
        return acct

    def rate_code(self, acct, date):
        best = None
        for eff, rank, eid, code in self.rate_hist.get(acct, []):
            if eff <= date:
                best = code
            else:
                break
        if best is None:
            rec = self.master.get(acct)
            best = (rec.get("rate_code_snapshot") or "").strip().upper() if rec else ""
        return self.aliases.get(best, best)

    # ------------------------------------------------------------- tariffs
    def load_tariffs(self):
        d = self.d
        self.base_rate = {}
        books = [
            ("tariff_book_residential_q4.docx", "docx"),
            ("tariff_book_industrial_q4.docx", "docx"),
            ("tariff_book_commercial_q4.pdf", "pdf"),
            ("tariff_book_agri_lighting_q4.pdf", "pdf"),
        ]
        for name, kind in books:
            lines = docx_lines(d.p(name)) if kind == "docx" else pdf_lines(d.p(name))
            self._load_book(lines, self.base_rate, "rate")

        errata = []
        for r in html_rows(d.p("tariff_errata_register.html")):
            if "erratum" not in r or "rate" not in r:
                continue
            errata.append(r)
        approved = [e for e in errata if e["status"].strip().upper() == "APPROVED"]
        superseded = set()
        for e in approved:
            for name in re.split(r"[,\s]+", e.get("supersedes", "").strip()):
                if name:
                    superseded.add(name.strip().upper())
        best = {}
        for e in approved:
            eid = e["erratum"].strip().upper()
            if eid in superseded:
                continue
            date = parse_date(e["date"])
            if not (MONTH_START <= date <= MONTH_END):
                continue
            key = (e["rate_code"].strip().upper(), date, e["daytype"].strip().upper())
            num = int(re.sub(r"\D", "", eid) or 0)
            rank = (parse_date(e["issued"]), num)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, q(dec_auto(e["rate"]), Q5))
        for key, (_r, val) in best.items():
            self.base_rate[key] = val

        self.credit_rate = {}
        self._load_book(docx_lines(d.p("net_metering_export_credit_rider.docx")),
                        self.credit_rate, "credit_rate")

        lines = pdf_lines(d.p("rider_schedule_2025.pdf"))
        mills = set()
        for l in lines:
            if "mills per kWh" in l:
                mills |= set(re.findall(r"R-[A-Z]+", l))
        self.riders = {}
        for r in pipe_rows(lines, [{"rider", "rate_code", "from", "to", "adder", "status"}]):
            if r["status"].strip().upper() != "ACTIVE":
                continue
            frm = parse_date(r["from"])
            to = parse_date(r["to"]) if r["to"].strip() else None
            if frm > MONTH_END or (to is not None and to <= MONTH_START):
                continue
            adder = dec_auto(r["adder"])
            rider = r["rider"].strip().upper()
            if rider in mills:
                adder = adder / 10
            self.riders.setdefault(r["rate_code"].strip().upper(), []).append(
                (frm, to, rider, q(adder, Q5)))

        self.applicability = {}
        for r in html_rows(d.p("rider_applicability_matrix.html")):
            if "applies" not in r:
                continue
            key = (r["rate_code"].strip().upper(), r["rider"].strip().upper(),
                   r["territory"].strip().upper())
            self.applicability.setdefault(key, []).append(
                (parse_date(r["effective_from"]), r["applies"].strip().upper()))
        for k in self.applicability:
            self.applicability[k].sort()

        self.storm = {}
        for r in pipe_rows(pdf_lines(d.p("tariff_book_residential_2026.pdf")),
                           [{"rate_code", "effective_from", "adder", "status"}]):
            if r["status"].strip().upper() != "APPROVED":
                continue
            eff = parse_date(r["effective_from"])
            if eff > MONTH_END:
                continue
            self.storm.setdefault(r["rate_code"].strip().upper(), []).append(
                (eff, q(dec_auto(r["adder"]), Q5)))
        for k in self.storm:
            self.storm[k].sort()
        self._adder_cache = {}

    def _load_book(self, lines, target, valcol):
        dollars = set()
        for l in lines:
            if "dollars per kWh" in l:
                dollars |= set(re.findall(r"[A-Z]{3}-\d{2}", l))
        for r in pipe_rows(lines, [{"rate_code", "date", "daytype", valcol}]):
            date = parse_date(r["date"])
            if not (MONTH_START <= date <= MONTH_END):
                continue
            val = dec_auto(r[valcol])
            code = r["rate_code"].strip().upper()
            if code in dollars:
                val = val * 100
            target[(code, date, r["daytype"].strip().upper())] = q(val, Q5)

    def rider_adder(self, code, territory, date):
        key = (code, territory, date)
        hit = self._adder_cache.get(key)
        if hit is not None:
            return hit
        total = D0
        for frm, to, rider, adder in self.riders.get(code, []):
            if not (frm <= date and (to is None or date < to)):
                continue
            flags = self.applicability.get((code, rider, territory))
            flag = None
            if flags:
                for eff, val in flags:
                    if eff <= date:
                        flag = val
                    else:
                        break
            if flag == "Y":
                total += adder
        best = None
        for eff, adder in self.storm.get(code, []):
            if eff <= date:
                best = adder
        if best is not None:
            total += best
        self._adder_cache[key] = total
        return total

    # ------------------------------------------------------------ calendar
    def load_calendar(self):
        lines = file_lines(self.d.p("territory_rate_calendar.ics"))
        unfolded = []
        for l in lines:
            if l.startswith(" ") and unfolded:
                unfolded[-1] += l[1:]
            else:
                unfolded.append(l)
        events = []
        cur = None
        for l in unfolded:
            if l.strip() == "BEGIN:VEVENT":
                cur = {}
            elif l.strip() == "END:VEVENT":
                if cur is not None:
                    events.append(cur)
                cur = None
            elif cur is not None and ":" in l:
                name, val = l.split(":", 1)
                cur[name.split(";")[0].strip().upper()] = val.strip()
        self.daytype = {}
        holi = set()
        cpp = set()
        for e in events:
            if e.get("STATUS", "").upper() != "CONFIRMED":
                continue
            terr = e.get("X-KVEC-TERRITORY", "").strip().upper()
            cat = e.get("CATEGORIES", "").strip().upper()
            try:
                start = parse_date(e["DTSTART"])
                end = parse_date(e["DTEND"])
            except (KeyError, ValueError):
                continue
            day = start
            while day < end:
                if MONTH_START <= day <= MONTH_END:
                    if cat == "HOLIDAY":
                        holi.add((terr, day))
                    elif cat == "CPP":
                        cpp.add((terr, day))
                day += dt.timedelta(days=1)
        self.territories = sorted({f["territory"] for f in self.feeders.values()})
        for terr in self.territories:
            for day in SETTLE_DAYS:
                if (terr, day) in holi:
                    val = "HOLIDAY"
                elif (terr, day) in cpp:
                    val = "CPP"
                elif day.weekday() >= 5:
                    val = "WEEKEND"
                else:
                    val = "WEEKDAY"
                self.daytype[(terr, day)] = val

    # ------------------------------------------------------------ lighting
    def load_lighting(self):
        d = self.d
        self.fixtures = []
        for f in json.load(open(d.p("unmetered_supply_inventory.json")))["fixtures"]:
            self.fixtures.append({
                "fixture_id": norm_fixture(g(f, "fixture_id", "fixture")),
                "account": norm_account(g(f, "account_id", "account")),
                "feeder": norm_feeder(g(f, "feeder", "fdr")),
                "watts": as_int(g(f, "nominal_watts", "watts")),
                "profile": str(g(f, "burn_profile", "profile")).strip().upper(),
                "installed": parse_date(g(f, "installed", "in_service")),
                "removed": parse_date(g(f, "removed", "out_of_service")),
            })
        self.fixtures.sort(key=lambda x: x["fixture_id"])

        self.audits = {}
        for r in sheet_dicts(d.p("unmetered_fixture_audit_2025.xlsx"),
                             {"fixture_id", "finding", "effective_date"}):
            self.audits.setdefault(norm_fixture(r["fixture_id"]), []).append(
                (parse_date(r["effective_date"]), str(r["finding"]).strip().upper(),
                 r.get("audited_watts")))
        for k in self.audits:
            self.audits[k].sort(key=lambda x: x[0])

        self.burn_hours = {}
        for r in json.load(open(d.p("photocell_burn_hours.json")))["rows"]:
            date = parse_date(r["date"])
            if MONTH_START <= date <= MONTH_END:
                self.burn_hours[(norm_feeder(r["feeder"]), date)] = dec_auto(r["hours"])

        self.burn_exceptions = {}
        for r in sheet_dicts(d.p("lighting_burn_hour_exceptions_2025.xlsx"),
                             {"fixture_id", "date", "hours"}):
            date = parse_date(r["date"])
            if MONTH_START <= date <= MONTH_END:
                self.burn_exceptions[(norm_fixture(r["fixture_id"]), date)] = \
                    dec_auto(r["hours"])

    # ---------------------------------------------------------- boundaries
    def build_boundaries(self):
        self.window = {}
        self.srv_range = {}
        self.binstant = {}
        for m, rows in self.reg.items():
            start = min(r["valid_from"] for r in rows)
            ends = [r["valid_to"] for r in rows]
            end = None if any(e is None for e in ends) else max(ends)
            w0 = to_utc(local_dt(start, 0))
            w1 = None if end is None else to_utc(local_dt(end + dt.timedelta(days=1), 0))
            t = self.exch_out.get(m)
            if t is not None and (w1 is None or t < w1):
                w1 = t
            t = self.exch_in.get(m)
            if t is not None and t > w0:
                w0 = t
            self.window[m] = (w0, w1)
            dates = [d for d in BOUNDARY_DATES
                     if start < d and (end is None or d <= end)]
            self.srv_range[m] = dates
            sched = self.schedule.get(m, [])
            for d in dates:
                rt = effective_pick(sched, d) or "00:00"
                if rt.startswith("23"):
                    inst = to_utc(local_dt(d - dt.timedelta(days=1), 23))
                else:
                    inst = to_utc(local_dt(d, 0))
                self.binstant[(m, d)] = inst

    # --------------------------------------------------------------- reads
    def head_end_files(self):
        names = sorted(os.listdir(self.d.root))
        out = []
        for n in names:
            if re.match(r"^(aurora|borealis|cirrus|delta|fjord)_reads_\d{4}-\d{2}_p\d+[a-z]?\."
                        r"(csv|xml|jsonl|parquet|tsv)$", n):
                out.append(n)
            elif re.match(r"^cis_legacy_reads_\d{4}-\d{2}_[a-z]\.txt$", n):
                out.append(n)
        return out

    def load_reads(self):
        d = self.d
        self.data_rows = {}
        rows = []
        self.fjord_revs = set()

        aur_profile = load_yaml(d.p("aurora_hes_profile.yaml"))
        aur_fw = {}
        for e in aur_profile.get("firmware_history", []):
            aur_fw.setdefault(norm_meter(g(e, "meter_id", "meter")), []).append(
                (parse_date(g(e, "effective_from", "since")), 0, str(e["firmware"])))
        aur_rules = []
        for r in (aur_profile.get("units", {}).get("firmware_rules") or []):
            aur_rules.append((r["match"], r["unit"]))
        aur_default = aur_profile.get("units", {}).get("default", "kWh")

        bor = tomllib.load(open(d.p("borealis_channel_map.toml"), "rb"))
        chanmap = {}
        for e in bor.get("channel_map", []):
            ch = e.get("channels") or {}
            imp_ch = g(e, "import_channel") if "import_channel" in e else ch.get("import")
            exp_ch = g(e, "export_channel") if "export_channel" in e else ch.get("export")
            chanmap.setdefault(norm_meter(g(e, "meter_id", "meter")), []).append(
                (parse_date(g(e, "effective_from", "since")), 0,
                 (int(imp_ch), int(exp_ch))))

        cir_profile = load_yaml(d.p("cirrus_hes_profile.yaml"))
        cir_rules = []
        for r in (cir_profile.get("decimal_separator", {}).get("firmware_rules") or []):
            cir_rules.append((r["match"], r["separator"]))
        cir_default = cir_profile.get("decimal_separator", {}).get("default", ".")
        cir_fw = {}
        for e in cir_profile.get("firmware_history", []):
            sep = cir_default
            for pat, s in cir_rules:
                if re.fullmatch(pat, str(e["firmware"])):
                    sep = s
                    break
            cir_fw.setdefault(norm_eui(g(e, "device", "device_eui")), []).append(
                (parse_date(g(e, "effective_from", "since")), 0, sep))

        self.cir_link = {}
        for line in file_lines(d.p("cirrus_daily_usage_2025-11.jsonl")):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "_comment" in rec:
                continue
            if str(rec.get("status") or rec.get("state") or "").upper() == "VOID":
                continue
            dev = norm_eui(rec.get("device") or rec.get("device_eui"))
            per = int(rec.get("period") if rec.get("period") is not None else rec.get("period_no"))
            self.cir_link[(dev, per)] = norm_meter(rec.get("meter_id") or rec.get("meter"))

        cp = read_ini(d.p("cis_legacy_layout.ini"))
        layouts = {}
        for sec in cp.sections():
            m = re.fullmatch(r"layout\.(\d+)", sec)
            if not m:
                continue
            spec = {}
            for k, v in cp[sec].items():
                mm = re.match(r"\s*(\d+)\s*-\s*(\d+)", v)
                if mm:
                    spec[k] = (int(mm.group(1)), int(mm.group(2)))
            layouts[int(m.group(1))] = spec
        dials = {}
        for sec in cp.sections():
            key = norm_legacy(sect_id(sec, "legacy"))
            if not key.startswith("L-"):
                continue
            dials[key] = as_int(g(cp[sec], "dial_constant", "kh") or 1)

        dcp = read_ini(d.p("delta_ingest.ini"))
        delta_missing = dcp["settings"].get("missing_raw", "-1").strip()

        fj_profile = load_yaml(d.p("fjord_hes_profile.yaml"))
        fj_aliases = dict(FJORD_ALIASES)
        fj_aliases.update({str(k): str(v) for k, v in (fj_profile.get("header_aliases") or {}).items()})
        fj_missing = set(str(x) for x in (fj_profile.get("missing_values") or []))
        fj_mult = {}
        for e in (fj_profile.get("multiplier_applied_entries") or []):
            fj_mult.setdefault(norm_meter(g(e, "meter_id", "meter")), []).append(
                (parse_date(g(e, "effective_from", "since")), 0,
                 bool(e["multiplier_applied"])))
        if d.exists("fjord_hes_profile_2026.yaml"):
            fj2 = load_yaml(d.p("fjord_hes_profile_2026.yaml"))
            for e in (fj2.get("multiplier_applied_entries") or []):
                eff = parse_date(g(e, "effective_from", "since"))
                if eff > MONTH_END:
                    continue
                fj_mult.setdefault(norm_meter(g(e, "meter_id", "meter")), []).append(
                    (eff, 1, bool(e["multiplier_applied"])))

        for name in self.head_end_files():
            path = d.p(name)
            per = 0
            pm = re.search(r"_p(\d+)", name)
            if pm:
                per = int(pm.group(1))
            if name.startswith("aurora"):
                recs, n = parse_aurora(path, aur_profile)
                for r in recs:
                    fw = effective_pick(aur_fw.get(r.key, []), local_date_of(r.reported))
                    unit = aur_default
                    if fw is not None:
                        for pat, u in aur_rules:
                            if re.fullmatch(pat, fw):
                                unit = u
                                break
                    if unit.lower() == "wh":
                        if r.imp is not None:
                            r.imp = r.imp / 1000
                        if r.exp is not None:
                            r.exp = r.exp / 1000
            elif name.startswith("borealis"):
                recs, n = parse_borealis(path, chanmap)
            elif name.startswith("cirrus"):
                recs, n = parse_cirrus(path, cir_fw, per)
            elif name.startswith("delta"):
                recs, n = parse_delta(path, 3)
            elif name.startswith("cis_legacy"):
                recs, n = parse_cis(path, layouts, dials)
            else:
                recs, revs, n = parse_fjord(path, fj_aliases, fj_missing)
                if self.batch_status.get(name) == "REJECTED":
                    for mm, dd in revs:
                        self.fjord_revs.add((mm, dd))
            self.data_rows[name] = n
            rows.extend(recs)

        self.delta_missing = delta_missing
        self.fj_mult = fj_mult
        self.raw_rows = rows

    def resolve_rows(self):
        """Attach meters, apply clock correction, bind to boundaries."""
        cands = {}
        delta_missing = self.delta_missing
        for r in self.raw_rows:
            if r.hes == "CIR":
                meter = self.cir_link.get((r.key, r.period))
            elif r.hes == "CIS":
                meter = self.legacy_map.get(r.key)
            elif r.hes == "DLT":
                meter = None
                for vf, vt, mm in self.sp_xref.get(r.key, []):
                    if (vf is None or vf <= r.reported) and (vt is None or r.reported < vt):
                        meter = mm
                        break
            else:
                meter = r.key
            if meter is None or meter not in self.reg:
                continue
            r.meter = meter

            if r.hes == "DLT":
                scale = Decimal(10) ** self.decimals.get(meter, 3)
                r.imp = _raw_scaled(r.imp, delta_missing, scale)
                r.exp = _raw_scaled(r.exp, delta_missing, scale)

            offset = self.offsets.get(meter, 0)
            corrected = r.reported - dt.timedelta(seconds=offset)
            sync = self.clock_sync.get(meter)
            true_t = corrected if (sync is None or corrected < sync) else r.reported

            w0, w1 = self.window[meter]
            if true_t < w0 or (w1 is not None and true_t >= w1):
                continue

            if r.hes == "FJD":
                applied = effective_pick(self.fj_mult.get(meter, []), local_date_of(r.reported))
                if applied:
                    mult = self.multiplier_at(meter, true_t)
                    if mult != 1:
                        if r.imp is not None:
                            r.imp = r.imp / mult
                        if r.exp is not None:
                            r.exp = r.exp / mult

            best = None
            for date in self.srv_range[meter]:
                inst = self.binstant[(meter, date)]
                diff = abs((true_t - inst).total_seconds())
                if diff <= 900 and (best is None or diff < best[0]):
                    best = (diff, date)
            if best is None:
                continue
            diff, date = best

            if self.excluded(r, meter, date):
                continue
            imp, exp = r.imp, r.exp
            issue = self.known_issues.get((meter, date, r.hes))
            if issue == "STUCK_REGISTER":
                continue
            if issue == "WH_AS_KWH":
                imp = None if imp is None else imp / 1000
                exp = None if exp is None else exp / 1000
            elif issue == "SWAP_REGISTERS":
                imp, exp = exp, imp
            if imp is None:
                continue
            imp = q(imp, Q3)
            exp = None if exp is None else q(exp, Q3)
            key = (meter, date)
            rank = (-diff, r.seq)
            prev = cands.get(key)
            if prev is None or rank > prev[0]:
                cands[key] = (rank, imp, exp)
        self.selected = {k: (v[1], v[2]) for k, v in cands.items()}

    def excluded(self, r, meter, date):
        if (r.hes, meter, date) in self.voids:
            return True
        if (meter, date) in self.disputes:
            return True
        status = self.batch_status.get(r.file)
        if status == "REJECTED":
            return True
        if status == "PARTIAL":
            rng = self.batch_rejected.get(r.file)
            if rng and rng[0] <= r.ordinal <= rng[1]:
                return True
        man = self.manifest.get(r.file)
        if man and man.get("withdrawn_rows"):
            lo, hi = [int(x) for x in str(man["withdrawn_rows"]).split("-")]
            if lo <= r.ordinal <= hi:
                return True
        if (meter, date) in self.holds:
            rel = self.releases.get((meter, date))
            if rel is None or rel > HOLD_CUTOFF:
                return True
        qe = self.quarantine.get((meter, date, r.hes))
        if qe is not None and qe[1]:
            return True
        if r.hes == "DLT" and r.est:
            if self.est_policy.get(r.key) != "ACCEPT":
                return True
        if r.hes == "FJD" and (meter, date) in self.fjord_revs \
                and re.search(r"_p4\.tsv$", r.file):
            return True
        return False

    # ----------------------------------------------------- boundary values
    def resolve_values(self):
        self.bvalue = {}
        for m in self.meters:
            for date in self.srv_range[m]:
                if date == MONTH_START:
                    oc = self.october.get(m)
                    if oc is None:
                        src, imp, exp = "MISSING", None, None
                    else:
                        imp, exp = oc[0], oc[1]
                        src = "ESTIMATE" if oc[2] == "ESTIMATED" else "ACTUAL"
                        if imp is None:
                            src = "MISSING"
                else:
                    c = self.corrections.get((m, date))
                    s = self.selected.get((m, date))
                    e = self.estimates.get((m, date))
                    if c is not None and c[1] is not None:
                        src, imp, exp = "CORRECTION", c[1], c[2]
                    elif s is not None:
                        src, imp, exp = "ACTUAL", s[0], s[1]
                    elif e is not None and e[1] is not None:
                        src, imp, exp = "ESTIMATE", e[1], e[2]
                    else:
                        src, imp, exp = "MISSING", None, None
                self.bvalue[(m, date)] = (
                    None if imp is None else q(imp, Q3),
                    None if exp is None else q(exp, Q3),
                    src,
                )

    # ----------------------------------------------------- register energy
    def compute_energy(self):
        self.daily = {}
        self.invalidated = {}
        one = dt.timedelta(seconds=1)
        for m in self.meters:
            dates = self.srv_range[m]
            if not dates:
                continue
            dig = self.digits.get(m, self.roll_default)
            cap = Decimal(10) ** dig
            high = cap * 9 / 10
            low = cap / 10
            anchors = [(self.binstant[(m, d)], 0, "B", d) for d in dates]
            if m in self.exch_out:
                anchors.append((self.exch_out[m], 1, "V", self.exch_final[m]))
            if m in self.exch_in:
                anchors.append((self.exch_in[m], 1, "V", self.exch_init[m]))
            for t, _mult, val in self.ct_orders.get(m, []):
                anchors.append((t, 1, "C", val))
            for t, pre, post in self.resets.get(m, []):
                anchors.append((t, 1, "R", (pre, post)))
            anchors.sort(key=lambda a: (a[0], a[1]))

            daily = {}
            for reg in (0, 1):
                prev = None
                for inst, _o, kind, payload in anchors:
                    if kind == "B":
                        val = self.bvalue[(m, payload)][reg]
                        if val is None:
                            continue
                    elif kind == "V":
                        val = payload[reg]
                        if val is None:
                            continue
                    elif kind == "C":
                        if reg == 1 or payload is None:
                            continue
                        val = payload
                    else:
                        if reg == 1:
                            continue
                        pre, post = payload
                        if prev is None:
                            prev = post
                            continue
                        delta = pre - prev
                        if delta < 0 and prev >= high and pre < low:
                            delta += cap
                        self._emit(daily, m, inst - one, reg, delta)
                        prev = post
                        continue
                    if prev is None:
                        prev = val
                        continue
                    delta = val - prev
                    if delta < 0:
                        if prev >= high and val < low:
                            delta += cap
                        elif kind == "B":
                            if reg == 0:
                                self.invalidated[(m, payload)] = val
                            continue
                    self._emit(daily, m, inst - one, reg, delta)
                    prev = val

            acc = self.accuracy.get(m)
            if acc is not None:
                tdate, err = acc
                factor = Decimal(100) / (Decimal(100) + err)
                for date in daily:
                    if date < tdate and daily[date][0]:
                        daily[date][0] = rhe(Decimal(daily[date][0]) * factor)
            if daily:
                self.daily[m] = daily

    def _emit(self, daily, meter, end_instant, reg, delta):
        mult = self.multiplier_at(meter, end_instant)
        wh = int((delta * 1000).to_integral_value(rounding=ROUND_HALF_EVEN)) * mult
        date = local_date_of(end_instant)
        cell = daily.get(date)
        if cell is None:
            cell = daily[date] = [0, 0]
        cell[reg] += wh

    # ------------------------------------------------------------ billing
    def registry_account(self, meter, date):
        for r in self.reg[meter]:
            if r["valid_from"] <= date and (r["valid_to"] is None or date < r["valid_to"]):
                return r["account"]
        return None

    def is_disconnected(self, meter, date):
        state = None
        for d, ev in self.disconnects.get(meter, []):
            if d <= date:
                state = ev
            else:
                break
        return state == "DISCONNECT"

    def export_credited(self, meter, date):
        apps = self.netmeter.get(meter)
        if not apps:
            return False
        ok = False
        for frm, to in apps:
            if frm <= date and (to is None or date < to):
                ok = True
                break
        if not ok:
            return False
        result = None
        for d, res in self.inspections.get(meter, []):
            if d <= date:
                result = res
            else:
                break
        return result == "PASS"

    def compute_billing(self):
        self.meter_stats = {}
        self.acct_day = {}
        self.feeder_stats = {}
        for f in self.feeders:
            self.feeder_stats[f] = {"billed_import_wh": 0, "billed_export_wh": 0,
                                    "deemed_wh": 0, "unbilled_wh": 0}
        for m in self.meters:
            daily = self.daily.get(m)
            feeder = self.meter_feeder.get(m)
            terr = self.feeders[feeder]["territory"] if feeder in self.feeders else None
            imp_total = bil_total = exp_total = 0
            if daily:
                for date in sorted(daily):
                    imp, exp = daily[date]
                    if date < MONTH_START or date > MONTH_END:
                        continue
                    imp_total += imp
                    acct0 = self.registry_account(m, date)
                    acct = self.resolve_account(acct0, date) if acct0 else None
                    billed = acct is not None
                    if billed:
                        rec = self.master.get(acct)
                        if rec and (rec.get("status") or "").strip().upper() == "FINAL":
                            fd = parse_date(rec.get("final_date")) if rec.get("final_date") else None
                            if fd is not None and fd <= date:
                                billed = False
                    if billed and self.is_disconnected(m, date):
                        billed = False
                    if not billed:
                        if feeder in self.feeder_stats:
                            self.feeder_stats[feeder]["unbilled_wh"] += imp
                        continue
                    bil_total += imp
                    cred = exp if (exp and self.export_credited(m, date)) else 0
                    exp_total += cred
                    cell = self.acct_day.setdefault((acct, date, terr), [0, 0, 0])
                    cell[0] += imp
                    cell[1] += cred
                    if feeder in self.feeder_stats:
                        self.feeder_stats[feeder]["billed_import_wh"] += imp
                        self.feeder_stats[feeder]["billed_export_wh"] += cred
            counts = [0, 0, 0, 0]
            resolved = 0
            for date in self.srv_range[m]:
                src = self.bvalue[(m, date)][2]
                if (m, date) in self.invalidated:
                    counts[3] += 1
                elif src == "CORRECTION":
                    counts[0] += 1
                elif src == "ESTIMATE":
                    counts[1] += 1
                elif src == "MISSING":
                    counts[2] += 1
                if src != "MISSING":
                    resolved += 1
            if resolved:
                self.meter_stats[m] = {
                    "feeder": feeder or "",
                    "import_wh": imp_total,
                    "billed_import_wh": bil_total,
                    "unbilled_wh": imp_total - bil_total,
                    "export_wh": exp_total,
                    "counts": counts,
                }

    # ----------------------------------------------------------- lighting
    def compute_lighting(self):
        self.lighting = []
        for fx in self.fixtures:
            fid = fx["fixture_id"]
            feeder = fx["feeder"]
            terr = self.feeders[feeder]["territory"] if feeder in self.feeders else None
            audits = self.audits.get(fid, [])
            total = 0
            days = 0
            last = None
            for date in SETTLE_DAYS:
                if fx["installed"] is None or fx["installed"] > date:
                    continue
                if fx["removed"] is not None and date >= fx["removed"]:
                    continue
                watts = fx["watts"]
                removed = False
                for eff, finding, aw in audits:
                    if eff > date:
                        break
                    if finding == "REMOVED":
                        removed = True
                    elif finding == "WATTAGE_CHANGE" and aw is not None:
                        watts = int(aw)
                if removed:
                    continue
                hours = self.burn_exceptions.get((fid, date))
                if hours is None:
                    if fx["profile"] == "ALL_DAY":
                        hours = Decimal(24)
                    else:
                        base = self.burn_hours.get((feeder, date))
                        if base is None:
                            continue
                        hours = base
                        if fx["profile"] == "PART_NIGHT":
                            hours = hours - 6
                            if hours < 0:
                                hours = D0
                hours = q(hours, Decimal("0.01"))
                wh = rhe(Decimal(watts) * hours)
                if wh <= 0:
                    continue
                total += wh
                days += 1
                last = date
                acct = self.resolve_account(fx["account"], date)
                cell = self.acct_day.setdefault((acct, date, terr), [0, 0, 0])
                cell[2] += wh
                if feeder in self.feeder_stats:
                    self.feeder_stats[feeder]["deemed_wh"] += wh
            if total > 0:
                self.lighting.append((fid, self.resolve_account(fx["account"], last),
                                      days, total))

    # -------------------------------------------------------------- scada
    def compute_injection(self):
        d = self.d
        start = to_utc(local_dt(MONTH_START, 0))
        end = to_utc(local_dt(MONTH_END + dt.timedelta(days=1), 0))
        step = dt.timedelta(minutes=15)
        instants = []
        t = start + step
        while t <= end:
            instants.append(t)
            t += step

        hist = {}
        for r in csv_dicts(d.p("substation_north_scada_2025-11.csv")):
            f = norm_feeder(r["feeder"])
            naive = parse_naive(r["interval_end_local"])
            off = 5 if r["tz"].strip().upper() == "CDT" else 6
            key = (f, naive.replace(tzinfo=UTC) + dt.timedelta(hours=off))
            val = (r.get("kw_avg") or "").strip()
            good = (r.get("quality") or "").strip().upper() == "GOOD"
            if not good or not val or val in ("---", "NaN"):
                hist[key] = None
            else:
                hist[key] = rhe(q(dec_auto(val), Decimal("0.01")) * 250)

        east = json.load(open(d.p("substation_east_scada_2025-11.json")))
        for r in east["intervals"]:
            f = norm_feeder(r.get("feeder") or r.get("fdr"))
            ts = g(r, "end_utc", "t", "interval_end_utc")
            key = (f, parse_utc(ts))
            qual = str(r.get("q") or r.get("quality") or "").strip().upper()
            val = r.get("kwh") if "kwh" in r else r.get("value")
            if qual != "G" or val is None:
                hist[key] = None
            else:
                hist[key] = int((dec_auto(val) * 1000).to_integral_value(ROUND_HALF_EVEN))

        for line in file_lines(d.p("substation_south_historian.log")):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("FORMAT"):
                continue
            if line.startswith("HIST|"):
                parts = line.split("|")
                if len(parts) < 5:
                    continue
                f = norm_feeder(parts[1])
                when = parse_naive(parts[2].strip().rstrip("Z")).replace(tzinfo=UTC)
                val, qual = parts[3].strip(), parts[4].strip().upper()
                key = (f, when)
                if qual != "GOOD" or val in ("NaN", "", "---"):
                    hist[key] = None
                else:
                    hist[key] = int((dec_auto(val) * 1000).to_integral_value(ROUND_HALF_EVEN))
                continue
            toks = line.split()
            if len(toks) < 5 or toks[1] != "HIST":
                continue
            when = parse_utc(toks[0])
            f = norm_feeder(toks[2])
            mwh = toks[3].split("=", 1)[1]
            qual = toks[4].split("=", 1)[1].strip().upper()
            key = (f, when)
            if qual != "GOOD" or mwh in ("NaN", "", "---"):
                hist[key] = None
            else:
                hist[key] = int((dec_auto(mwh) * 1000000).to_integral_value(ROUND_HALF_EVEN))

        west_lines = pdf_lines(d.p("substation_west_monthly_report.pdf"))
        for r in pipe_rows(west_lines, [{"feeder", "end_local", "offset", "kwh", "quality"}]):
            f = norm_feeder(r["feeder"])
            naive = parse_naive(r["end_local"])
            om = re.match(r"([+-])(\d{2}):(\d{2})", r["offset"].strip())
            delta = dt.timedelta(hours=int(om.group(2)), minutes=int(om.group(3)))
            if om.group(1) == "-":
                when = naive.replace(tzinfo=UTC) + delta
            else:
                when = naive.replace(tzinfo=UTC) - delta
            key = (f, when)
            val = r["kwh"].strip()
            if r["quality"].strip().upper() != "GOOD" or val in ("---", "", "NaN"):
                hist[key] = None
            else:
                hist[key] = int((dec_auto(val) * 1000).to_integral_value(ROUND_HALF_EVEN))

        alarms = {}
        for line in file_lines(d.p("scada_alarm_journal.log")):
            m = re.match(r"^(\S+) ALARM feeder=(\S+) type=(\S+) state=(\S+)", line)
            if not m or m.group(3) != "COMM_FAIL":
                continue
            when = parse_utc(m.group(1))
            f = norm_feeder(m.group(2))
            lst = alarms.setdefault(f, [])
            if m.group(4) == "RAISED":
                lst.append([when, None])
            else:
                for a in reversed(lst):
                    if a[1] is None:
                        a[1] = when
                        break

        er = {}
        rows = list(pipe_rows(file_lines(d.p("scada_errata_notice.md")),
                              [{"erratum", "feeder", "interval_end", "wh", "status",
                                "issued", "supersedes"}]))
        approved = [r for r in rows if r["status"].strip().upper() == "APPROVED"]
        superseded = set()
        for r in approved:
            for name in re.split(r"[,\s]+", r.get("supersedes", "").strip()):
                if name:
                    superseded.add(name.strip().upper())
        best = {}
        for r in approved:
            eid = r["erratum"].strip().upper()
            if eid in superseded:
                continue
            when = parse_utc(r["interval_end"])
            key = (norm_feeder(r["feeder"]), when)
            rank = (parse_date(r["issued"]), int(re.sub(r"\D", "", eid) or 0))
            if key not in best or rank > best[key][0]:
                best[key] = (rank, as_int(r["wh"]))
        for key, (_r, val) in best.items():
            er[key] = val

        relay = {}
        for r in pipe_rows(pdf_lines(d.p("substation_east_monthly_report.pdf")),
                           [{"feeder", "interval_end_utc", "kwh", "test_status"},
                            {"feeder", "end_local", "offset", "kwh"}]):
            if "test_status" not in r or r["test_status"].strip().upper() != "DONE":
                continue
            when = parse_utc(r["interval_end_utc"])
            relay[(norm_feeder(r["feeder"]), when)] = int(
                (dec_auto(r["kwh"]) * 1000).to_integral_value(ROUND_HALF_EVEN))

        gap = {}
        for r in csv_dicts(d.p("scada_15min_gapfill_2025-11.csv")):
            if (r.get("model_version") or "").strip().lower() != "v3":
                continue
            if (r.get("status") or "").strip().upper() != "PUBLISHED":
                continue
            when = parse_utc(r["interval_end_utc"])
            gap[(norm_feeder(r["feeder"]), when)] = as_int(r["wh_est"])

        self.intervals = []
        self.injection = {}
        for f in sorted(self.feeders):
            is_east = self.feeders[f]["substation"] == "east"
            flist = alarms.get(f, [])
            total = 0
            for t in instants:
                key = (f, t)
                if key in er:
                    val, src = er[key], "ERRATUM"
                elif is_east and key in relay:
                    val, src = relay[key], "RELAY_TEST"
                else:
                    val = hist.get(key)
                    blocked = False
                    if val is not None:
                        s = t - step
                        for a0, a1 in flist:
                            if a0 < t and (a1 is None or a1 > s):
                                blocked = True
                                break
                    if val is not None and not blocked:
                        src = "HISTORIAN"
                    else:
                        val = gap.get(key, 0)
                        src = "GAPFILL"
                total += val
                self.intervals.append((f, t, val, src))
            self.injection[f] = total

    # ------------------------------------------------------------ charges
    def compute_charges(self):
        self.accounts = {}
        for (acct, date, terr), (imp, cred, deemed) in self.acct_day.items():
            if imp == 0 and cred == 0 and deemed == 0:
                continue
            code = self.rate_code(acct, date)
            daytype = self.daytype.get((terr, date), "WEEKDAY")
            base = self.base_rate.get((code, date, daytype), D0)
            adder = self.rider_adder(code, terr, date)
            credit = self.credit_rate.get((code, date, daytype), D0)
            a = self.accounts.get(acct)
            if a is None:
                a = self.accounts[acct] = {
                    "energy": D0, "rider": D0, "credit": D0,
                    "imp": 0, "exp": 0, "deemed": 0, "last": None,
                }
            billable = imp + deemed
            a["energy"] += Decimal(billable) * base / 1000
            a["rider"] += Decimal(billable) * adder / 1000
            a["credit"] += Decimal(cred) * credit / 1000
            a["imp"] += imp
            a["exp"] += cred
            a["deemed"] += deemed
            if a["last"] is None or date > a["last"]:
                a["last"] = date
        for acct, a in self.accounts.items():
            a["energy_cents"] = rhe(a["energy"])
            a["rider_cents"] = rhe(a["rider"])
            a["export_credit_cents"] = -rhe(a["credit"])
            a["rate_code"] = self.rate_code(acct, a["last"])

    # ---------------------------------------------------------------- ufe
    def compute_ufe(self):
        self.loss = {}
        total_inj = 0
        total_loss = 0
        for f in sorted(self.feeders):
            inj = self.injection[f]
            loss = rhe(Decimal(inj) * self.feeders[f]["loss_pct"] / 100)
            self.loss[f] = loss
            total_inj += inj
            total_loss += loss
        total_imp = sum(a["imp"] for a in self.accounts.values())
        total_exp = sum(a["exp"] for a in self.accounts.values())
        total_deemed = sum(a["deemed"] for a in self.accounts.values())
        ufe = total_inj + total_exp - total_loss - total_imp - total_deemed
        self.totals = {
            "injection_wh": total_inj, "loss_wh": total_loss,
            "billed_import_wh": total_imp, "billed_export_wh": total_exp,
            "deemed_wh": total_deemed, "ufe_wh": ufe,
        }
        weights = []
        W = 0
        for acct in sorted(self.accounts):
            a = self.accounts[acct]
            w = a["imp"] + a["deemed"]
            if w <= 0 or acct in self.exempt:
                a["ufe_wh"] = 0
                continue
            weights.append((acct, w))
            W += w
        mag = abs(ufe)
        alloc = {}
        if W > 0 and mag > 0:
            rema = []
            given = 0
            for acct, w in weights:
                share = mag * w
                base = share // W
                alloc[acct] = base
                given += base
                rema.append((share - base * W, acct))
            rema.sort(key=lambda x: (-x[0], x[1]))
            for i in range(mag - given):
                alloc[rema[i][1]] += 1
        sign = -1 if ufe < 0 else 1
        for acct, w in weights:
            self.accounts[acct]["ufe_wh"] = sign * alloc.get(acct, 0)

        energy_sum = sum(a["energy_cents"] for a in self.accounts.values())
        rider_sum = sum(a["rider_cents"] for a in self.accounts.values())
        denom = total_imp + total_deemed
        if denom:
            price = q(Decimal(energy_sum + rider_sum) * 1000 / Decimal(denom), Q6)
        else:
            price = Decimal("0.000000")
        self.ufe_price = price
        for acct, a in self.accounts.items():
            a["ufe_charge_cents"] = rhe(Decimal(a.get("ufe_wh", 0)) * price / 1000)
            a["total_cents"] = (a["energy_cents"] + a["rider_cents"]
                                + a["export_credit_cents"] + a["ufe_charge_cents"])

    # ------------------------------------------------------ control report
    def control_report(self):
        out = []
        for name in sorted(self.head_end_files()):
            rows = self.data_rows.get(name, 0)
            status = self.batch_status.get(name, "")
            rejected = 0
            if status == "REJECTED":
                rejected = rows
            elif status == "PARTIAL":
                rng = self.batch_rejected.get(name)
                if rng:
                    lo = max(1, rng[0])
                    hi = min(rows, rng[1])
                    rejected = max(0, hi - lo + 1)
            man = self.manifest.get(name)
            withdrawn = 0
            man_rows = 0
            if man:
                man_rows = int(man.get("record_count") or 0)
                if man.get("withdrawn_rows"):
                    lo, hi = [int(x) for x in str(man["withdrawn_rows"]).split("-")]
                    lo = max(1, lo)
                    hi = min(rows, hi)
                    withdrawn = max(0, hi - lo + 1)
            out.append({
                "file": name,
                "data_rows": rows,
                "manifest_rows": man_rows,
                "mdm_status": status,
                "rejected_rows": rejected,
                "withdrawn_rows": withdrawn,
            })
        return {"batches": out}

    # ------------------------------------------------------------- driver
    def run(self):
        self.build_boundaries()
        self.load_reads()
        self.resolve_rows()
        self.resolve_values()
        self.compute_energy()
        self.compute_billing()
        self.compute_lighting()
        self.compute_injection()
        self.compute_charges()
        self.compute_ufe()

    # ------------------------------------------------------------- output
    def write(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)

        def write_csv(name, header, rows):
            with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(",".join(header) + "\n")
                for r in rows:
                    fh.write(",".join(str(x) for x in r) + "\n")

        def write_json(name, obj):
            with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as fh:
                fh.write(json.dumps(obj, indent=2, sort_keys=True))
                fh.write("\n")

        rows = []
        for acct in sorted(self.accounts):
            a = self.accounts[acct]
            if a["imp"] == 0 and a["exp"] == 0 and a["deemed"] == 0:
                continue
            rows.append([acct, a["rate_code"], a["imp"], a["exp"], a["deemed"],
                         a["energy_cents"], a["rider_cents"], a["export_credit_cents"],
                         a.get("ufe_wh", 0), a["ufe_charge_cents"], a["total_cents"]])
        write_csv("account_settlement.csv",
                  ["account_id", "rate_code", "billed_import_wh", "billed_export_wh",
                   "deemed_wh", "energy_cents", "rider_cents", "export_credit_cents",
                   "ufe_wh", "ufe_charge_cents", "total_cents"], rows)
        acct_rows = rows

        mrows = []
        for m in sorted(self.meter_stats):
            s = self.meter_stats[m]
            mrows.append([m, s["feeder"], s["import_wh"], s["billed_import_wh"],
                          s["unbilled_wh"], s["export_wh"]] + s["counts"])
        write_csv("meter_summary.csv",
                  ["meter_id", "feeder", "import_wh", "billed_import_wh", "unbilled_wh",
                   "export_wh", "corrected_boundaries", "estimated_boundaries",
                   "missing_boundaries", "invalidated_boundaries"], mrows)

        rrows = []
        for m in self.meters:
            for date in self.srv_range[m]:
                imp, _exp, src = self.bvalue[(m, date)]
                if (m, date) in self.invalidated:
                    rrows.append([m, date.isoformat(), "INVALIDATED",
                                  format(self.invalidated[(m, date)], ".3f")])
                elif src == "CORRECTION":
                    rrows.append([m, date.isoformat(), "CORRECTION", format(imp, ".3f")])
                elif src == "ESTIMATE":
                    rrows.append([m, date.isoformat(), "ESTIMATE", format(imp, ".3f")])
                elif src == "MISSING":
                    rrows.append([m, date.isoformat(), "MISSING", ""])
        rrows.sort(key=lambda r: (r[0], r[1]))
        write_csv("read_resolution.csv",
                  ["meter_id", "boundary_date", "source", "import_kwh"], rrows)

        irows = [[f, t.strftime("%Y-%m-%dT%H:%M:%SZ"), v, s]
                 for f, t, v, s in self.intervals]
        write_csv("interval_injection.csv",
                  ["feeder", "interval_end_utc", "injection_wh", "source"], irows)

        write_csv("lighting_deemed.csv",
                  ["fixture_id", "account_id", "burn_days", "deemed_wh"],
                  sorted(self.lighting, key=lambda r: r[0]))

        drows = []
        for terr in sorted(self.territories):
            for date in SETTLE_DAYS:
                drows.append([terr, date.isoformat(), self.daytype[(terr, date)]])
        write_csv("daytype_calendar.csv", ["territory", "date", "daytype"], drows)

        feeders = {}
        for f in sorted(self.feeders):
            st = self.feeder_stats[f]
            inj = self.injection[f]
            loss = self.loss[f]
            feeders[f] = {
                "injection_wh": inj,
                "loss_wh": loss,
                "billed_import_wh": st["billed_import_wh"],
                "billed_export_wh": st["billed_export_wh"],
                "deemed_wh": st["deemed_wh"],
                "unbilled_wh": st["unbilled_wh"],
                "residual_wh": inj + st["billed_export_wh"] - loss
                - st["billed_import_wh"] - st["deemed_wh"],
            }
        write_json("feeder_balance.json", {"feeders": feeders})
        write_json("control_report.json", self.control_report())

        unbilled = sum(s["unbilled_wh"] for s in self.meter_stats.values())
        summary = {
            "account_count": len(acct_rows),
            "meter_count": len(mrows),
            "injection_wh": self.totals["injection_wh"],
            "loss_wh": self.totals["loss_wh"],
            "billed_import_wh": sum(r[2] for r in acct_rows),
            "billed_export_wh": sum(r[3] for r in acct_rows),
            "deemed_wh": sum(r[4] for r in acct_rows),
            "unbilled_wh": unbilled,
            "ufe_wh": sum(r[8] for r in acct_rows),
            "ufe_price_cents_per_kwh": format(self.ufe_price, ".6f"),
            "energy_cents": sum(r[5] for r in acct_rows),
            "rider_cents": sum(r[6] for r in acct_rows),
            "export_credit_cents": sum(r[7] for r in acct_rows),
            "ufe_charge_cents": sum(r[9] for r in acct_rows),
            "total_cents": sum(r[10] for r in acct_rows),
        }
        write_json("settlement_summary.json", summary)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    engine = Settlement(argv[1])
    engine.run()
    engine.write(argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

