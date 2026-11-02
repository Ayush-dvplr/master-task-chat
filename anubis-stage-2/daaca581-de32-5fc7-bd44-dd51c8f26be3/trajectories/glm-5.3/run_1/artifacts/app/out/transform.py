#!/usr/bin/env python3
"""KVEC monthly settlement transform.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>
"""
import sys, os, re, json, csv, io, sqlite3, unicodedata, mailbox
import collections
from collections import defaultdict, Counter
from datetime import datetime, timedelta, date, timezone
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from fractions import Fraction
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import yaml
from openpyxl import load_workbook
from docx import Document
import pypdf
import pyarrow.parquet as pq

getcontext().prec = 60
TZ = ZoneInfo("America/Chicago")

# ---------------------------------------------------------------- utilities

CYR = {"К": "K", "А": "A", "С": "C"}


def norm_raw(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = "".join(CYR.get(ch, ch) for ch in s)
    s = re.sub(r"\s+", "", s)
    return s.upper()


def norm_meter(s):
    s = norm_raw(s)
    m = re.match(r"^KV(\d+)$", s)
    if m:
        return "KV" + m.group(1).zfill(7)
    return s


def norm_account(s):
    s = norm_raw(s)
    m = re.match(r"^AC(\d+)$", s)
    if m:
        return "AC" + m.group(1).zfill(8)
    return s


def norm_fixture(s):
    s = norm_raw(s)
    m = re.match(r"^FX(\d+)$", s)
    if m:
        return "FX" + m.group(1).zfill(6)
    return s


def norm_feeder(s):
    s = norm_raw(s)
    m = re.match(r"^F(?:DR)?-?(\d+)$", s)
    if m:
        return "F" + m.group(1).zfill(2)
    return s


def norm_sp(s):
    s = norm_raw(s)
    m = re.match(r"^SP-?(\d+)$", s)
    if m:
        return "SP" + m.group(1).zfill(9)
    return s


def norm_eui(s):
    s = norm_raw(s).replace(":", "")
    m = re.match(r"^([0-9A-F]+)$", s)
    if m:
        return s.zfill(16)
    return s

def norm_legacy(s):
    s = norm_raw(s)
    m = re.match(r"^L-?(\d+)$", s)
    if m:
        return "L-" + m.group(1).zfill(6)
    return s


def parse_date(s):
    """Return YYYY-MM-DD string from many formats."""
    if s is None:
        return ""
    if isinstance(s, datetime):
        return s.date().isoformat()
    if isinstance(s, date):
        return s.isoformat()
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        # excel date serial
        if 20000 < float(s) < 80000:
            dt = excel_serial_date(s)
            return dt.date().isoformat() if dt else ""
        return ""
    s = str(s).strip()
    if not s:
        return ""
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return "%s-%s-%s" % (m.group(3), m.group(1).zfill(2), m.group(2).zfill(2))
    return s


def excel_serial_date(v):
    """Excel 1900 date-system serial (Lotus compatible) -> datetime (naive local)."""
    if v is None:
        return None
    total = float(v)
    # round to nearest second
    secs = int(Decimal(repr(total)) * Decimal(86400))
    n = secs // 86400
    rem = secs % 86400
    if n >= 61:
        base = datetime(1899, 12, 30)
    else:
        base = datetime(1899, 12, 31)
    return base + timedelta(days=n, seconds=rem)


def to_instant(dt):
    """naive local datetime -> epoch seconds (int)."""
    return int(dt.replace(tzinfo=TZ).timestamp())


def local_dt_of(ts):
    return datetime.fromtimestamp(ts, TZ)


def local_date_of(ts):
    return datetime.fromtimestamp(ts, TZ).date()


def utc_str(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rhe(value, ndigits):
    """round half even to ndigits (value may be Decimal/Fraction/int/str)."""
    if isinstance(value, Fraction):
        d = Decimal(value.numerator) / Decimal(value.denominator)
    elif isinstance(value, Decimal):
        d = value
    elif isinstance(value, float):
        d = Decimal(repr(value))
    else:
        d = Decimal(str(value))
    q = Decimal(1).scaleb(-ndigits)
    return d.quantize(q, rounding=ROUND_HALF_EVEN)


def rhe_int(value):
    if isinstance(value, Fraction):
        d = Decimal(value.numerator) / Decimal(value.denominator)
    elif isinstance(value, Decimal):
        d = value
    elif isinstance(value, float):
        d = Decimal(repr(value))
    else:
        d = Decimal(str(value))
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def rhe_frac(value, ndigits):
    """Fraction -> Fraction rounded half even at ndigits decimals."""
    q = rhe(value, ndigits)
    return Fraction(q)


def dec(value, thousands=False):
    """parse a numeric string.

    thousands=True  -> ',' and '.' are US style: '945,743.8' -> 945743.8
    otherwise       -> a decimal comma is honoured when the string has no '.':
                       '13,97027' -> 13.97027; several commas mean thousands.
    """
    if value is None:
        return None
    if isinstance(value, (int,)):
        return Decimal(value)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    s = str(value).strip()
    if s == "":
        return None
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "," in s:
        if thousands or ("." in s) or (s.count(",") > 1):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except Exception:
        return None
    return -d if neg else d


def read_records(path):
    """Yield text records terminated by LF or bare CR."""
    with open(path, "rb") as f:
        raw = f.read()
    for rec in re.split(br"[\r\n]", raw):
        yield rec


def decode_line(b):
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("cp1252")
    if s.startswith("\ufeff"):
        s = s[1:]
    return s


def text_of(path):
    with open(path, "rb") as f:
        raw = f.read()
    return decode_line(raw)


# ---------------------------------------------------------------- simple file formats


def parse_kv_file(path):
    """Parse an ini/toml-like file with [section] headers and key = value lines.

    Returns dict section_name -> dict of key/value strings (raw, lower-cased keys).
    Handles headers without ':' and renamed keys (value carried as-is).
    """
    out = {}
    cur = None
    for line in text_of(path).split("\n"):
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        m = re.match(r"^\[([^\]]*)\]$", line)
        if m:
            cur = m.group(1).strip()
            if cur not in out:
                out[cur] = {}
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip().lower()
            v = v.strip().strip('"')
            if cur is not None:
                out[cur][k] = v
            else:
                out.setdefault("__root__", {})[k] = v
    return out


def parse_docx_tables(path):
    """Return (paragraphs, [tables]) where each table is a list of rows of cell text."""
    doc = Document(path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    tables = []
    for t in doc.tables:
        rows = []
        for r in t.rows:
            rows.append([c.text.strip() for c in r.cells])
        tables.append(rows)
    return paras, tables


def pdf_text(path):
    r = pypdf.PdfReader(path)
    parts = []
    for p in r.pages:
        try:
            parts.append(p.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def html_rows(path):
    """Yield lists of cell texts from an html table file."""
    html = text_of(path)
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cells = []
        for m in re.finditer(r"<t([dh])[^>]*>(.*?)</t\1>", tr, re.S):
            txt = re.sub(r"<[^>]+>", "", m.group(2))
            txt = re.sub(r"\s+", " ", txt).strip()
            cells.append(txt)
        if cells:
            rows.append(cells)
    return rows


def xlsx_rows(path, sheet_names=None):
    wb = load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        if sheet_names is not None and ws.title not in sheet_names:
            continue
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(list(r))
        out.append((ws.title, rows))
    wb.close()
    return out


def csv_rows(path, encoding="utf-8-sig", comment="#"):
    txt = text_of(path)
    lines = [l for l in txt.split("\n") if l.strip() and not l.startswith(comment)]
    if not lines:
        return []
    rdr = csv.reader(io.StringIO("\n".join(lines)))
    return [row for row in rdr if row]


def csv_dicts(path, encoding="utf-8-sig"):
    """Rows of a csv file as dicts; records may end with LF or bare CR."""
    recs = []
    for rec in read_records(path):
        s = decode_line(rec)
        if not s.strip() or s.startswith("#"):
            continue
        recs.append(s)
    if not recs:
        return iter([])
    rows = list(csv.reader(io.StringIO("\n".join(recs))))
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        d = {}
        for i, h in enumerate(hdr):
            d[h.strip()] = r[i] if i < len(r) else ""
        out.append(d)
    return out


def read_records(path):
    """Yield text records terminated by LF or bare CR."""
    with open(path, "rb") as f:
        raw = f.read()
    for rec in re.split(br"[\r\n]", raw):
        yield rec


def decode_line(b):
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("cp1252")
    if s.startswith("\ufeff"):
        s = s[1:]
    return s


def text_of(path):
    with open(path, "rb") as f:
        raw = f.read()
    return decode_line(raw)


def csv_dicts(path, encoding="utf-8-sig"):
    """Rows of a csv file as dicts; records may end with LF or bare CR."""
    recs = []
    for rec in read_records(path):
        s = decode_line(rec)
        if not s.strip() or s.startswith("#"):
            continue
        recs.append(s)
    if not recs:
        return iter([])
    rows = list(csv.reader(io.StringIO("\n".join(recs))))
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        d = {}
        for i, h in enumerate(hdr):
            d[h.strip()] = r[i] if i < len(r) else ""
        out.append(d)
    return out


# ---------------------------------------------------------------- settlement constants

MONTH_START = date(2025, 11, 1)
MONTH_END = date(2025, 11, 30)
DAYS = [MONTH_START + timedelta(days=i) for i in range(30)]
DAYS_ISO = [d.isoformat() for d in DAYS]
BOUNDARY_DATES = [MONTH_START + timedelta(days=i) for i in range(31)]  # 11-01 .. 12-01
BOUNDARY_DATES_ISO = [d.isoformat() for d in BOUNDARY_DATES]
DAYTYPES = ("WEEKDAY", "WEEKEND", "HOLIDAY", "CPP")
TERRITORIES = ("TE", "TN", "TS", "TW")
FEEDERS = ["F%02d" % i for i in range(1, 13)]
RELEASE_CUTOFF = int(datetime(2025, 12, 3, 17, 0, tzinfo=TZ).timestamp())


def interval_ends_local():
    """All interval-ending instants (epoch) for (11-01 00:00, 12-01 00:00] local."""
    out = []
    t = to_instant(datetime(2025, 11, 1, 0, 15))
    end = to_instant(datetime(2025, 12, 1, 0, 0))
    while t <= end:
        out.append(t)
        t += 900
    return out


# ---------------------------------------------------------------- loader


class Ctx(object):
    pass


def load_all(data_dir):
    c = Ctx()
    c.dir = data_dir
    load_manual(c)
    load_connectivity(c)
    load_static_tables(c)
    load_account_data(c)
    load_rates(c)
    load_calendar(c)
    load_lighting(c)
    load_scada(c)
    return c


def load_manual(c):
    paras, tables = parse_docx_tables(os.path.join(c.dir, "kvec_settlement_procedures_manual.docx"))
    c.manual_paras = paras
    # Table F: feeder | substation | territory | loss_pct
    table_f = {}
    for rows in tables:
        if not rows or rows[0][:2] != ["feeder", "substation"]:
            continue
        for r in rows[1:]:
            f = norm_feeder(r[0])
            table_f[f] = {
                "substation": r[1].strip().lower(),
                "territory": r[2].strip().upper(),
                "loss_pct": dec(r[3]),
            }
        break
    c.table_f = table_f
    # Appendix R: meter_id | read_time | effective_from (two tables, differing order)
    sched = defaultdict(list)
    for rows in tables:
        if not rows:
            continue
        hdr = [h.strip().lower() for h in rows[0]]
        if set(hdr) == {"meter_id", "read_time", "effective_from"}:
            for r in rows[1:]:
                d = dict(zip(hdr, [x.strip() for x in r]))
                m = norm_meter(d["meter_id"])
                sched[m].append((parse_date(d["effective_from"]), d["read_time"].strip()))
    c.schedule = sched
    # revision 4 draft: errata index (erratum | table | key | value | effective_from | cr)
    _, dtables = parse_docx_tables(os.path.join(c.dir, "settlement_procedures_manual_rev4_draft.docx"))
    errata = []
    for rows in dtables:
        if not rows:
            continue
        hdr = [h.strip().lower() for h in rows[0]]
        if "erratum" in hdr and "cr" in hdr:
            for r in rows[1:]:
                d = dict(zip(hdr, [x.strip() for x in r]))
                errata.append(d)
    c.draft_errata = errata
    # CAB decisions from the operations mailbox
    cab = {}
    holds = defaultdict(list)   # (meter, read_date) -> list of hold notices
    releases = defaultdict(list)
    mb = mailbox.mbox(os.path.join(c.dir, "mdm_ops_mailbox_2025-11.mbox"))
    for msg in mb:
        try:
            subj = str(make_header(decode_header(msg["Subject"])))
        except Exception:
            subj = str(msg["Subject"] or "")
        payload = msg.get_payload()
        if isinstance(payload, list):
            payload = payload[0].get_payload()
        body = payload if isinstance(payload, str) else ""
        m = re.match(r"CAB decision (CR-\d+): (APPROVED|REJECTED)", subj)
        if m:
            cab[m.group(1)] = m.group(2)
            continue
        ntype = nmeter = ndate = None
        for line in body.split("\n"):
            if line.startswith("Notice type:"):
                ntype = line.split(":", 1)[1].strip().upper()
            elif line.startswith("Meter:"):
                nmeter = norm_meter(line.split(":", 1)[1])
            elif line.startswith("Read date:"):
                ndate = parse_date(line.split(":", 1)[1])
        if ntype == "HOLD" and nmeter and ndate:
            holds[(nmeter, ndate)].append(msg)
        elif ntype == "RELEASE" and nmeter and ndate:
            releases[(nmeter, ndate)].append(msg)
    c.cab = cab
    held = set()
    for key, msgs in holds.items():
        ok = False
        for msg in msgs:
            pass
        for rmsg in releases.get(key, []):
            try:
                dt = parsedate_to_datetime(str(rmsg["Date"]))
            except Exception:
                continue
            if int(dt.timestamp()) <= RELEASE_CUTOFF:
                ok = True
                break
        if not ok:
            held.add(key)
    c.held_reads = held

    # approved draft errata
    c.approved_r_errata = []
    c.approved_l_errata = []
    for d in c.draft_errata:
        cr = d.get("cr", "")
        if c.cab.get(cr) != "APPROVED":
            continue
        eff = parse_date(d.get("effective_from", ""))
        if d.get("table", "").strip().upper() == "R":
            c.approved_r_errata.append({
                "meter": norm_meter(d.get("key", "")),
                "read_time": d.get("value", "").strip(),
                "effective_from": eff,
                "erratum": d.get("erratum", ""),
            })
        elif d.get("table", "").strip().upper() == "L":
            c.approved_l_errata.append({
                "feeder": norm_feeder(d.get("key", "")),
                "loss_pct": dec(d.get("value", "")),
                "effective_from": eff,
                "erratum": d.get("erratum", ""),
            })
    # schedule including errata (errata outrank register rows with the same date)
    c.schedule_all = defaultdict(list)
    for m, entries in c.schedule.items():
        c.schedule_all[m].extend(entries)
    for e in c.approved_r_errata:
        c.schedule_all[e["meter"]].append((e["effective_from"], e["read_time"], 1))
    for m in list(c.schedule_all):
        c.schedule_all[m] = [(eff, rt) for eff, rt, *_ in
                             [(a, b, *rest) for a, b, *rest in _normalize_sched(c.schedule_all[m])]]
    # loss factors amended
    c.loss_pct = {}
    for f, info in c.table_f.items():
        c.loss_pct[f] = info["loss_pct"]
    for e in c.approved_l_errata:
        f = e["feeder"]
        cur = c.loss_pct.get(f)
        if cur is None or e["effective_from"] <= "2025-11-30":
            c.loss_pct[f] = e["loss_pct"]
    c.territory = {f: c.table_f[f]["territory"] for f in c.table_f}


def _normalize_sched(entries):
    """entries: list of (eff, read_time) or (eff, read_time, is_erratum)."""
    out = []
    for e in entries:
        if len(e) == 3:
            out.append((e[0], e[1], e[2]))
        else:
            out.append((e[0], e[1], 0))
    return out


def load_connectivity(c):
    """Appendix T of the data contract."""
    path = os.path.join(c.dir, "settlement_data_contract.md")
    txt = text_of(path)
    i = txt.find("## Appendix T")
    if i >= 0:
        txt = txt[i:]
    conn = {}
    for line in txt.split("\n"):
        if not line.startswith("|") or "---" in line:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 2 or parts[0].lower() == "meter_id":
            continue
        a, b = norm_raw(parts[0]), norm_raw(parts[1])
        if re.match(r"^F(?:DR)?-?\d+$", a):
            f, m = norm_feeder(a), norm_meter(b)
        elif re.match(r"^F(?:DR)?-?\d+$", b):
            f, m = norm_feeder(b), norm_meter(a)
        else:
            continue
        if not m.startswith("KV"):
            continue
        conn[m] = f
    c.connectivity = conn


def load_static_tables(c):
    d = c.dir
    # ---- clock offsets
    offs = {}
    p = os.path.join(d, "meter_clock_offsets.toml")
    for rec in read_records(p):
        s = decode_line(rec).strip()
        m = re.match(r'meter_id\s*=\s*"?([^"]+)"?', s)
        if m:
            cur_meter = norm_meter(m.group(1))
            continue
        m = re.match(r'offset_s\s*=\s*(-?\d+)', s)
        if m and cur_meter is not None:
            offs[cur_meter] = int(m.group(1))
    c.clock_offsets = offs
    # ---- register rollover digits
    digits = {}
    default_digits = 6
    txt = text_of(os.path.join(d, "register_rollover.toml"))
    cur = None
    for line in txt.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\[defaults\]$", line)
        if m:
            cur = "default"
            continue
        m = re.match(r"^\[\[register\]\]$", line)
        if m:
            cur = "reg"
            continue
        m = re.match(r'meter_id\s*=\s*"?([^"]+)"?', line)
        if m:
            cur = norm_meter(m.group(1))
            continue
        m = re.match(r"digits\s*=\s*(\d+)", line)
        if m:
            if cur == "default":
                default_digits = int(m.group(1))
            else:
                digits[cur] = int(m.group(1))
    c.rollover_digits = defaultdict(lambda: default_digits)
    for k, v in digits.items():
        c.rollover_digits[k] = v
    # ---- register scaling (delta decimals)
    scal = parse_kv_file(os.path.join(d, "register_scaling.ini"))
    decimals = {}
    for sec, kv in scal.items():
        if sec.startswith("KV"):
            m = re.match(r"^KV(\d+)$", norm_raw(sec))
            if m:
                mm = "KV" + m.group(1).zfill(7)
                if "decimals" in kv:
                    decimals[mm] = int(kv["decimals"])
        else:
            mm = norm_meter(sec)
            if mm.startswith("KV") and "decimals" in kv:
                decimals[mm] = int(kv["decimals"])
    c.scaling_decimals = decimals
    # ---- delta est policy
    dp = parse_kv_file(os.path.join(d, "delta_ingest.ini"))
    est_policy = {}
    for sec, kv in dp.items():
        sp = None
        m = re.match(r"^spid:?(.*)$", sec.strip())
        if m:
            sp = norm_sp(m.group(1))
        if sp is None:
            m = re.match(r"^(SP-?\d+)$", norm_raw(sec))
            if m:
                sp = norm_sp(m.group(1))
        if sp:
            pol = kv.get("est_policy") or kv.get("policy") or ""
            est_policy[sp] = pol.strip().upper()
    c.est_policy = est_policy
    # ---- legacy dial constants and layout
    lay = parse_kv_file(os.path.join(d, "cis_legacy_layout.ini"))
    dial = {}
    for sec, kv in lay.items():
        s = re.sub(r"^LEGACY:?", "", norm_raw(sec))
        m = re.match(r"^L-?(\d+)$", s)
        if m:
            lid = "L-" + m.group(1).zfill(6)
            v = kv.get("dial_constant") or kv.get("kh") or kv.get("register_kwh") or "1"
            dv = dec(v)
            dial[lid] = int(dv) if dv is not None else 1
    c.dial_constant = dial
    c.legacy_layout = lay
    # ---- registry (district dbs)
    reg = defaultdict(list)
    for fn in ("mdm_registry_north.db", "mdm_registry_east.db", "mdm_registry_southwest.db"):
        con = sqlite3.connect(os.path.join(d, fn))
        try:
            for r in con.execute(
                    "select meter_id, account_id, multiplier, hes, valid_from, valid_to from meter_attr_history"):
                reg[norm_meter(r[0])].append({
                    "account": norm_account(r[1]),
                    "multiplier": int(r[2]) if r[2] is not None else 1,
                    "hes": norm_raw(r[3]),
                    "valid_from": parse_date(r[4]),
                    "valid_to": parse_date(r[5]),
                })
        finally:
            con.close()
    for m in reg:
        reg[m].sort(key=lambda x: x["valid_from"])
    c.registry = reg
    # ---- dw registry snapshot: sp_meter_xref only
    xref = defaultdict(list)
    con = sqlite3.connect(os.path.join(d, "dw_registry_snapshot_2025-12-03.db"))
    try:
        for r in con.execute("select spid, meter_id, valid_from_utc, valid_to_utc, status from sp_meter_xref"):
            sp = norm_sp(r[0])
            vf = r[2]
            vt = r[3]
            def pinst(s):
                if not s:
                    return None
                s = s.strip()
                if s.endswith("Z"):
                    s = s[:-1]
                try:
                    dt = datetime.fromisoformat(s)
                except Exception:
                    return None
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            xref[sp].append({
                "meter": norm_meter(r[1]),
                "from": pinst(vf),
                "to": pinst(vt),
                "status": norm_raw(r[4]),
            })
    finally:
        con.close()
    c.sp_xref = xref
    # ---- migration wave 3 crosswalk (legacy id -> meter)
    cross = {}
    for title, rows in xlsx_rows(os.path.join(d, "meter_registry_migration_wave3.xlsx")):
        if title.strip().lower() != "crosswalk":
            continue
        hdr = None
        for r in rows:
            if hdr is None:
                cand = [str(x).strip().lower() if x else "" for x in r]
                if "legacy_id" in cand and "meter_id" in cand:
                    hdr = cand
                    continue
                continue
            dd = dict(zip(hdr, r))
            lid = norm_legacy(str(dd.get("legacy_id") or ""))
            mid = norm_meter(str(dd.get("meter_id") or ""))
            st = norm_raw(str(dd.get("link_status") or ""))
            if st == "ACTIVE" and mid.startswith("KV"):
                cross[lid] = mid
    c.legacy_crosswalk = cross
    # ---- cirrus device links per period
    dev_link = {}
    for line in read_records(os.path.join(d, "cirrus_daily_usage_2025-11.jsonl")):
        s = decode_line(line).strip()
        if not s:
            continue
        try:
            o = json.loads(s)
        except Exception:
            continue
        if "_comment" in o:
            continue
        dev = o.get("device") or o.get("device_eui") or o.get("dev")
        mid = o.get("meter_id") or o.get("meter")
        per = o.get("period", o.get("period_no"))
        st = (o.get("status") or o.get("state") or "").upper()
        if not dev or mid is None or per is None:
            continue
        dev = norm_eui(str(dev))
        mid = norm_meter(str(mid))
        key = (dev, int(per))
        if st == "VOID":
            continue
        if key in dev_link and dev_link[key] != mid:
            # later row for the same device/period wins only if a revision is present
            if "revision" not in o:
                continue
        dev_link[key] = mid
    c.cirrus_link = dev_link
    # ---- collector events
    clock_sync = {}
    resets = defaultdict(list)
    for rec in read_records(os.path.join(d, "collector_events_2025-11.log")):
        s = decode_line(rec).strip()
        m = re.match(r"^(\S+) collector\[\d+\] (\S+) meter=(\S+)(.*)$", s)
        if not m:
            continue
        ts = m.group(1)
        try:
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        t = int(dt.timestamp())
        ev = m.group(2)
        meter = norm_meter(m.group(3))
        rest = m.group(4)
        if ev == "CLOCK_SYNC":
            clock_sync[meter] = t
        elif ev == "REGISTER_RESET":
            pre = re.search(r"pre_reset_kwh=([\d.,]+)", rest)
            post = re.search(r"post_reset_kwh=([\d.,]+)", rest)
            if pre and post:
                resets[meter].append({
                    "t": t,
                    "pre": dec(pre.group(1)),
                    "post": dec(post.group(1)),
                })
    c.clock_sync = clock_sync
    c.register_resets = resets
    # ---- field service orders
    exchanges = []
    ct_changes = []
    for line in read_records(os.path.join(d, "field_service_orders.jsonl")):
        s = decode_line(line).strip()
        if not s or s.startswith("#"):
            continue
        try:
            o = json.loads(s)
        except Exception:
            continue
        typ = (o.get("type") or "").upper()
        st = (o.get("status") or "").upper()
        at = o.get("completed_at") or o.get("ts")
        if not at:
            continue
        try:
            dt = datetime.fromisoformat(at)
        except Exception:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        t = int(dt.timestamp())
        if typ == "EXCHANGE" and st == "COMPLETED":
            exchanges.append({
                "t": t,
                "old": norm_meter(o["old_meter"]),
                "new": norm_meter(o["new_meter"]),
                "old_imp": dec(o.get("old_final_import_kwh")),
                "old_exp": dec(o.get("old_final_export_kwh")),
                "new_imp": dec(o.get("new_initial_import_kwh")),
                "new_exp": dec(o.get("new_initial_export_kwh")),
            })
        elif typ == "CT_CHANGE" and st == "COMPLETED":
            ct_changes.append({
                "t": t,
                "meter": norm_meter(o["meter"]),
                "old_ratio": o.get("old_ratio"),
                "new_ratio": o.get("new_ratio"),
                "register": dec(o.get("register_at_change_kwh")),
            })
    c.exchanges = exchanges
    c.ct_changes = ct_changes
    # ---- ct ratio verifications
    ctv = []
    for title, rows in xlsx_rows(os.path.join(d, "ct_ratio_verification_2025.xlsx")):
        if not rows:
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "meter_id" in cand and "action" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            act = norm_raw(str(dd.get("action") or ""))
            if act != "CORRECT_RATIO":
                continue
            measured = str(dd.get("measured_ratio") or "")
            m = re.match(r"^\s*(\d+)\s*:\s*5", measured)
            if not m:
                continue
            ctv.append({
                "meter": norm_meter(str(dd.get("meter_id") or "")),
                "verified_on": parse_date(dd.get("verified_on")),
                "multiplier": int(m.group(1)),
            })
    c.ct_verifications = ctv
    # ---- meter accuracy tests
    acc = defaultdict(list)
    _, tables = parse_docx_tables(os.path.join(d, "meter_accuracy_test_results_2025.docx"))
    for rows in tables:
        if not rows:
            continue
        hdr = [h.strip().lower() for h in rows[0]]
        if "test_id" not in hdr:
            continue
        for r in rows[1:]:
            dd = dict(zip(hdr, [x.strip() for x in r]))
            if (dd.get("result") or "").upper() != "FAIL":
                continue
            td = parse_date(dd.get("test_date"))
            if not td.startswith("2025-11"):
                continue
            pct = dec(dd.get("as_found_error_pct"))
            tid = str(dd.get("test_id") or "")
            acc[norm_meter(dd.get("meter_id"))].append((td, tid, pct))
    c.accuracy_fail = {}
    for m, lst in acc.items():
        lst2 = sorted(lst, key=lambda x: (x[0], x[1]))
        c.accuracy_fail[m] = lst2[-1]  # (date, test_id, pct)
    # ---- disconnection register
    disc = defaultdict(list)
    _, tables = parse_docx_tables(os.path.join(d, "disconnection_register_2025.docx"))
    for rows in tables:
        if not rows:
            continue
        hdr = [h.strip().lower() for h in rows[0]]
        if "event" not in hdr or "meter_id" not in hdr:
            continue
        for r in rows[1:]:
            dd = dict(zip(hdr, [x.strip() for x in r]))
            ref = norm_raw(dd.get("order_ref") or "")
            if ref.startswith("SOX"):
                continue
            disc[norm_meter(dd.get("meter_id"))].append(
                (parse_date(dd.get("event_date")), norm_raw(dd.get("event"))))
    for m in disc:
        disc[m].sort()
    c.disconnections = disc
    # ---- net metering enrollments
    nm = defaultdict(list)
    for row in csv_dicts(os.path.join(d, "netmetering_enrollments.csv")):
        st = norm_raw(row.get("status"))
        nm[norm_meter(row.get("meter_id"))].append({
            "account": norm_account(row.get("account_id")),
            "status": st,
            "from": parse_date(row.get("effective_from")),
            "to": parse_date(row.get("effective_to")),
        })
    c.net_metering = nm
    # ---- export meter inspections
    insp = defaultdict(list)
    for title, rows in xlsx_rows(os.path.join(d, "export_meter_inspections_2025.xlsx")):
        if not rows:
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "meter_id" in cand and "result" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            insp[norm_meter(str(dd.get("meter_id") or ""))].append(
                (parse_date(dd.get("inspected_on")), norm_raw(str(dd.get("result") or ""))))
    for m in insp:
        insp[m].sort()
    c.inspections = insp
    # ---- mdm october close reads
    close = {}
    for row in csv_dicts(os.path.join(d, "mdm_october_close_reads.csv")):
        m = norm_meter(row.get("meter_id"))
        close[m] = {
            "local": row.get("boundary_local") or "",
            "imp": dec(row.get("register_import_kwh")),
            "exp": dec(row.get("register_export_kwh")),
            "status": norm_raw(row.get("status")),
        }
    c.close_reads = close
    # ---- void register
    voids = set()
    for row in csv_dicts(os.path.join(d, "mdm_void_register.csv")):
        if norm_raw(row.get("reinstated")) == "N":
            voids.add((norm_raw(row.get("hes")), norm_meter(row.get("meter_id")),
                       parse_date(row.get("read_date"))))
    c.void_reads = voids
    # ---- read corrections
    corr = defaultdict(list)
    for row in csv_dicts(os.path.join(d, "mdm_read_corrections.csv")):
        corr[(norm_meter(row.get("meter_id")), parse_date(row.get("read_date")))].append({
            "imp": dec(row.get("corrected_import_kwh")),
            "exp": dec(row.get("corrected_export_kwh")),
            "revision": int(dec(row.get("revision")) or 0),
            "status": norm_raw(row.get("status")),
        })
    c.corrections = corr
    # ---- vee estimates and reviews
    est = defaultdict(list)
    for line in read_records(os.path.join(d, "mdm_vee_estimates.tsv")):
        s = decode_line(line).strip()
        if not s or s.startswith("estimate_id"):
            continue
        p = s.split("\t")
        if len(p) < 6:
            continue
        est[(norm_meter(p[1]), parse_date(p[2]))].append({
            "id": p[0],
            "imp": dec(p[3]),
            "exp": dec(p[4]),
            "version": int(dec(p[5]) or 0),
        })
    c.estimates = est
    review = {}
    for title, rows in xlsx_rows(os.path.join(d, "vee_estimate_review_2025.xlsx")):
        if not rows:
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "estimate_id" in cand and "review_status" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            eid = str(dd.get("estimate_id") or "")
            st = norm_raw(str(dd.get("review_status") or ""))
            ro = parse_date(dd.get("reviewed_on"))
            if eid not in review:
                review[eid] = []
            review[eid].append((ro, st))
    c.estimate_reviews = review
    # ---- batch control log
    batches = {}
    for rec in read_records(os.path.join(d, "mdm_batch_control.log")):
        s = decode_line(rec).strip()
        m = re.match(r"^\S+ mdm-ingest\[\d+\]: BATCH (\S+) file=(\S+) status=(\S+) rows=(\d+)(.*)$", s)
        if not m:
            continue
        fname = m.group(2)
        status = m.group(3)
        rest = m.group(5)
        rr = re.search(r"rejected_rows=(\d+)-(\d+)", rest)
        batches[fname] = {
            "batch": m.group(1),
            "status": status,
            "rows": int(m.group(4)),
            "rejected_from": int(rr.group(1)) if rr else None,
            "rejected_to": int(rr.group(2)) if rr else None,
        }
    c.batch_control = batches
    # ---- vendor manifest
    man = json.load(open(os.path.join(d, "hes_batch_manifest_2025-11.json"), "rb"))
    mrec = {}
    for o in man.get("records", []):
        if o.get("kind") != "batch":
            continue
        fn = o.get("file")
        if not fn:
            continue
        ent = {
            "count": int(o.get("record_count") or 0),
            "status": norm_raw(o.get("status") or ""),
            "superseded": bool(o.get("superseded")),
            "withdrawn": o.get("withdrawn_rows"),
        }
        if fn in mrec:
            # later entry replaces superseded ones
            prev = mrec[fn]
            if prev["superseded"] and not ent["superseded"]:
                mrec[fn] = ent
            elif ent["superseded"] and not prev["superseded"]:
                pass
            else:
                mrec[fn] = ent
        else:
            mrec[fn] = ent
    c.manifest = mrec
    # ---- ingest debug log quarantines
    quar = defaultdict(list)
    for rec in read_records(os.path.join(d, "hes_ingest_debug.log")):
        s = decode_line(rec).strip()
        if "QUARANTINE" not in s and "UNQUARANTINE" not in s:
            continue
        m = re.match(r"^(\S+)\s+(QUARANTINE|UNQUARANTINE)\s+meter=(\S+)\s+read_date=(\S+)(.*)$", s)
        if not m:
            continue
        kind = m.group(2)
        meter = norm_meter(m.group(3))
        rd = parse_date(m.group(4))
        hes = ""
        mh = re.search(r"\bhes=(\S+)", m.group(5))
        if mh:
            hes = norm_raw(mh.group(1))
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            ts = int(dt.timestamp())
        except Exception:
            ts = 0
        quar[(meter, rd, hes)].append((ts, kind))
    c.quarantine = quar
    # ---- known issues
    issues = {}
    ki = text_of(os.path.join(d, "hes_known_issues.md"))
    for line in ki.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 6 or parts[0].lower() == "issue" or "---" in parts[0]:
            continue
        # columns may be reordered; find by content
        code = hes = meter = rd = status = None
        for p in parts:
            pu = p.upper()
            if pu in ("STUCK_REGISTER", "WH_AS_KWH", "SWAP_REGISTERS"):
                code = pu
            elif pu in ("OPEN", "CLOSED"):
                status = pu
            elif re.match(r"^(AUR|BOR|CIR|DLT|FJD|CIS)$", pu):
                hes = pu
            elif re.match(r"^KV", pu):
                meter = norm_meter(p)
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", p):
                rd = p
        if code and status == "OPEN" and meter and rd and hes:
            issues[(meter, rd, hes)] = code
    c.known_issues = issues
    # ---- customer portal disputes
    disp = defaultdict(list)
    html = text_of(os.path.join(d, "customer_portal_usage_export.html"))
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", x).strip()
                 for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) >= 5 and cells[0].startswith("DSP"):
            disp[norm_meter(cells[1])].append((parse_date(cells[2]), parse_date(cells[3]),
                                               norm_raw(cells[4])))
    c.disputes = disp


def load_account_data(c):
    d = c.dir
    # ---- account master (month-end extract of record)
    master = {}
    for row in csv_dicts(os.path.join(d, "cis_account_master.csv")):
        acct = norm_account(row.get("account_id"))
        master[acct] = {
            "class": norm_raw(row.get("customer_class")),
            "status": norm_raw(row.get("status")),
            "final_date": parse_date(row.get("final_date")),
            "rate_snapshot": norm_raw(row.get("rate_code_snapshot")),
        }
    c.account_master = master
    # ---- next-month extract: only late-posted merges
    late_merges = []
    for row in csv_dicts(os.path.join(d, "cis_account_master_2025-12.csv")):
        if norm_raw(row.get("late_posted")) != "Y":
            continue
        succ = norm_account(row.get("merged_into"))
        eff = parse_date(row.get("merge_effective"))
        if succ and eff and eff <= "2025-11-30":
            late_merges.append((norm_account(row.get("account_id")), succ, eff))
    c.late_merges = late_merges
    # ---- merge register
    merges = []
    mj = json.load(open(os.path.join(d, "account_merges_2025.json"), "rb"))
    for o in mj.get("merges", []):
        pred = o.get("predecessor") or o.get("from_account")
        succ = o.get("successor") or o.get("to_account")
        eff = o.get("effective_date") or o.get("effective")
        st = norm_raw(o.get("status") or o.get("state"))
        if st != "COMPLETED":
            continue
        merges.append((norm_account(pred), norm_account(succ), parse_date(eff)))
    merges.extend(late_merges)
    c.merges = merges
    # merge map: predecessor -> list of (eff, successor)
    mm = defaultdict(list)
    for pred, succ, eff in merges:
        mm[pred].append((eff, succ))
    c.merge_map = mm
    # ---- rate history
    hist = defaultdict(list)
    reversed_ids = set()
    for title, rows in xlsx_rows(os.path.join(d, "account_rate_history.xlsx")):
        if not rows:
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "account_id" in cand and "effective_from" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            acct = norm_account(str(dd.get("account_id") or ""))
            rc = norm_raw(str(dd.get("rate_code") or ""))
            eff = parse_date(dd.get("effective_from"))
            eid = dd.get("entry_id")
            eid = int(eid) if eid is not None and str(eid).strip() != "" else 0
            hist[acct].append((eff, eid, rc))
    for title, rows in xlsx_rows(os.path.join(d, "account_rate_history_restated.xlsx")):
        if title.strip().lower() != "reversals":
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "entry_id" in cand and "account_id" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            eid = dd.get("entry_id")
            try:
                reversed_ids.add(int(eid))
            except (TypeError, ValueError):
                pass
    c.rate_history = hist
    c.reversed_entry_ids = reversed_ids
    # ---- crosswalk: legacy aliases and migrations
    cw = json.load(open(os.path.join(d, "rate_code_crosswalk_2026.json"), "rb"))
    alias = {}
    migrations = defaultdict(list)
    for o in cw.get("records", []):
        kind = norm_raw(o.get("kind"))
        if kind == "LEGACY_ALIAS":
            st = norm_raw(o.get("status"))
            if st == "ACTIVE":
                alias[norm_raw(o.get("alias"))] = norm_raw(o.get("rate_code"))
        elif kind == "MIGRATION":
            st = norm_raw(o.get("status"))
            if st == "WITHDRAWN":
                continue
            acct = norm_account(o.get("account_id") or o.get("account") or "")
            rc = norm_raw(o.get("new_rate_code") or o.get("to_rate_code") or "")
            eff = parse_date(o.get("effective_from") or o.get("effective") or "")
            if acct and rc and eff:
                migrations[acct].append((eff, rc))
    c.legacy_alias = alias
    c.migrations = migrations


def load_rates(c):
    d = c.dir
    base = {}
    dollar_codes = set()
    books = ["tariff_book_residential_q4.docx", "tariff_book_industrial_q4.docx",
             "tariff_book_commercial_q4.pdf", "tariff_book_agri_lighting_q4.pdf"]
    for fn in books:
        path = os.path.join(d, fn)
        if not os.path.exists(path):
            continue
        book_dollar = set()
        if fn.endswith(".docx"):
            paras, tables = parse_docx_tables(path)
            notes = paras
        else:
            txt = pdf_text(path)
            paras = []
            tables = [[l.split(" | ") for l in txt.split("\n") if " | " in l]]
            notes = [l.strip() for l in txt.split("\n")]
        for p in notes:
            m = re.search(r"stated in dollars per kWh[^:]*:\s*(.+?)\.?\s*$", p)
            if m:
                for code in m.group(1).split(","):
                    code = norm_raw(code)
                    if code:
                        book_dollar.add(code)
        for rows in tables:
            if not rows:
                continue
            hdr = None
            for r in rows:
                cells = [x.strip() for x in r]
                if hdr is None:
                    cand = [x.lower() for x in cells]
                    if "rate_code" in cand and "rate" in cand:
                        hdr = cand
                        continue
                    continue
                dd = dict(zip(hdr, cells))
                rc = norm_raw(dd.get("rate_code") or "")
                dt = parse_date(dd.get("date") or "")
                dtp = norm_raw(dd.get("daytype") or "")
                val = dec(dd.get("rate"))
                if rc and dt and dtp in DAYTYPES and val is not None:
                    if rc in book_dollar:
                        val = val * Decimal(100)
                    base[(rc, dt, dtp)] = rhe(val, 5)
    c.base_rates = base
    # ---- errata
    errata = {}
    sup = set()
    rowsall = []
    for cells in html_rows(os.path.join(d, "tariff_errata_register.html")):
        rowsall.append(cells)
    recs = []
    for cells in rowsall:
        if not cells:
            continue
        if norm_raw(cells[0]) == "ERRATUM" or norm_raw(cells[0]) == "STATUS":
            continue
        if not cells[0].upper().startswith("TE-"):
            continue
        if len(cells) >= 8 and re.match(r"^[A-Z]{3}-\d{2}$", norm_raw(cells[1])):
            dd = dict(zip(["erratum", "rate_code", "date", "daytype", "rate", "issued", "status",
                           "supersedes"], cells[:8]))
        else:
            dd = dict(zip(["status", "erratum", "supersedes", "rate_code", "date", "daytype",
                           "issued", "rate"], cells[:8]))
        recs.append(dd)
    approved = []
    for dd in recs:
        if norm_raw(dd.get("status")) != "APPROVED":
            continue
        sname = norm_raw(dd.get("supersedes"))
        if sname:
            sup.add(sname)
        approved.append(dd)
    eff_errata = {}
    for dd in approved:
        if dd.get("erratum") in sup:
            continue
        key = (norm_raw(dd.get("rate_code")), parse_date(dd.get("date")), norm_raw(dd.get("daytype")))
        cur = eff_errata.get(key)
        cand = (parse_date(dd.get("issued")), num_of(dd.get("erratum")), dd.get("erratum"),
                dec(dd.get("rate")))
        if cur is None or (cand[0], cand[1]) > (cur[0], cur[1]):
            eff_errata[key] = cand
    c.tariff_errata = {k: v[3] for k, v in eff_errata.items()}
    # ---- riders
    riders = defaultdict(list)
    txt = pdf_text(os.path.join(d, "rider_schedule_2025.pdf"))
    lieap_mills = False
    if re.search(r"R-LIEAP are stated in mills", txt):
        lieap_mills = True
    for line in txt.split("\n"):
        line = line.strip()
        if line.count("|") != 5:
            continue
        p = [x.strip() for x in line.split("|")]
        if norm_raw(p[0]) == "RIDER" or not p[0].startswith("R-"):
            continue
        st = norm_raw(p[5])
        if st != "ACTIVE":
            continue
        val = dec(p[4])
        if val is None:
            continue
        if norm_raw(p[0]) == "R-LIEAP" and lieap_mills:
            val = val / Decimal(10)
        riders[(norm_raw(p[0]), norm_raw(p[1]))].append((parse_date(p[2]), parse_date(p[3]),
                                                         rhe(val, 5)))
    c.riders = riders
    rb = defaultdict(list)
    for (rname, rrc), spans in riders.items():
        rb[rrc].append((rname, spans))
    c.riders_by_rate = rb
    # ---- rider applicability
    appl = defaultdict(list)
    for cells in html_rows(os.path.join(d, "rider_applicability_matrix.html")):
        if not cells or norm_raw(cells[0]) == "RATE_CODE":
            continue
        if len(cells) < 5:
            continue
        if not re.match(r"^[A-Z]{3}-\d{2}$", norm_raw(cells[0])):
            continue
        rc = norm_raw(cells[0])
        rd = norm_raw(cells[1])
        terr = norm_raw(cells[2])
        eff = parse_date(cells[3])
        ap = norm_raw(cells[4])
        appl[(rc, rd, terr)].append((eff, ap))
    c.rider_applicability = appl
    # ---- storm recovery rider (Table S of the 2026 residential filing)
    storm = defaultdict(list)
    txt = pdf_text(os.path.join(d, "tariff_book_residential_2026.pdf"))
    i = txt.find("Table S.")
    if i >= 0:
        seg = txt[i:]
        for line in seg.split("\n"):
            line = line.strip()
            if line.count("|") != 3:
                continue
            p = [x.strip() for x in line.split("|")]
            if norm_raw(p[0]) == "RATE_CODE" or not re.match(r"^[A-Z]{3}-\d{2}$", norm_raw(p[0])):
                continue
            if norm_raw(p[3]) != "APPROVED":
                continue
            eff = parse_date(p[1])
            val = rhe(dec(p[2]), 5)
            storm[norm_raw(p[0])].append((eff, val))
    c.storm_rider = storm
    # ---- export credit rates
    credit = {}
    paras, tables = parse_docx_tables(os.path.join(d, "net_metering_export_credit_rider.docx"))
    credit_dollar = set()
    for p in paras:
        m = re.search(r"stated in dollars per kWh[^:]*:\s*(.+?)\.?\s*$", p)
        if m:
            for code in m.group(1).split(","):
                code = norm_raw(code)
                if code:
                    credit_dollar.add(code)
    for rows in tables:
        if not rows:
            continue
        hdr = None
        for r in rows:
            cells = [x.strip() for x in r]
            if hdr is None:
                cand = [x.lower() for x in cells]
                if "rate_code" in cand and "credit_rate" in cand:
                    hdr = cand
                    continue
                continue
            dd = dict(zip(hdr, cells))
            rc = norm_raw(dd.get("rate_code") or "")
            dt = parse_date(dd.get("date") or "")
            dtp = norm_raw(dd.get("daytype") or "")
            val = dec(dd.get("credit_rate"))
            if rc and dt and dtp in DAYTYPES and val is not None:
                if rc in credit_dollar:
                    val = val * Decimal(100)
                credit[(rc, dt, dtp)] = rhe(val, 5)
    c.credit_rates = credit


def num_of(s):
    m = re.search(r"(\d+)$", str(s))
    return int(m.group(1)) if m else 0


def load_calendar(c):
    d = c.dir
    events = []
    txt = text_of(os.path.join(d, "territory_rate_calendar.ics"))
    lines = []
    for rec in read_records(os.path.join(d, "territory_rate_calendar.ics")):
        lines.append(decode_line(rec).rstrip("\r"))
    # unfold continuation lines
    unfolded = []
    for ln in lines:
        if ln.startswith(" ") and unfolded:
            unfolded[-1] = unfolded[-1] + ln[1:]
        else:
            unfolded.append(ln)
    cur = {}
    for ln in unfolded:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            if cur:
                events.append(cur)
            cur = {}
        elif ":" in ln and cur is not None:
            k, v = ln.split(":", 1)
            k = k.split(";")[0].strip().upper()
            cur[k] = v.strip()
    cal = []
    for ev in events:
        cat = norm_raw(ev.get("CATEGORIES", ""))
        terr = norm_raw(ev.get("X-KVEC-TERRITORY", ""))
        st = norm_raw(ev.get("STATUS", ""))
        try:
            ds = datetime.strptime(ev.get("DTSTART", ""), "%Y%m%d").date()
            de = datetime.strptime(ev.get("DTEND", ""), "%Y%m%d").date()
        except Exception:
            continue
        cal.append((terr, cat, st, ds, de))
    c.calendar_events = cal
    # day type per (territory, date)
    dt_map = {}
    hol = defaultdict(set)
    cpp = defaultdict(set)
    for terr, cat, st, ds, de in cal:
        if st != "CONFIRMED":
            continue
        if cat not in ("HOLIDAY", "CPP"):
            continue
        tgt = hol if cat == "HOLIDAY" else cpp
        t = ds
        while t < de:
            tgt[terr].add(t)
            t += timedelta(days=1)
    c.holiday_days = hol
    c.cpp_days = cpp

    # ---- UFE allocation exemptions
    exempt = []
    txt = pdf_text(os.path.join(d, "ufe_allocation_exemptions_register.pdf"))
    for line in txt.split("\n"):
        line = line.strip()
        if line.count("|") != 4:
            continue
        p = [x.strip() for x in line.split("|")]
        if norm_raw(p[0]) in ("ACCOUNT", "STATUS"):
            continue
        if norm_raw(p[0]) in ("ACTIVE", "WITHDRAWN"):
            st, acct, basis, frm, to = p[0], p[1], p[2], p[3], p[4]
        else:
            acct, frm, to, st, basis = p[0], p[1], p[2], p[3], p[4]
        if norm_raw(st) != "ACTIVE":
            continue
        if not acct.startswith("AC"):
            continue
        exempt.append((norm_account(acct), parse_date(frm), parse_date(to)))
    c.ufe_exemptions = exempt


def load_lighting(c):
    d = c.dir
    inv = json.load(open(os.path.join(d, "unmetered_supply_inventory.json"), "rb"))
    fixtures = {}
    for o in inv.get("fixtures", inv if isinstance(inv, list) else []):
        fid = norm_fixture(o.get("fixture_id"))
        fixtures[fid] = {
            "account": norm_account(o.get("account_id")),
            "feeder": norm_feeder(o.get("feeder")),
            "watts": dec(o.get("nominal_watts")),
            "profile": norm_raw(o.get("burn_profile")),
            "installed": parse_date(o.get("installed")),
            "removed": parse_date(o.get("removed")),
        }
    c.fixtures = fixtures
    # ---- fixture audit findings
    audit = defaultdict(list)
    for title, rows in xlsx_rows(os.path.join(d, "unmetered_fixture_audit_2025.xlsx")):
        if not rows:
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "fixture_id" in cand and "finding" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            fid = norm_fixture(str(dd.get("fixture_id") or ""))
            finding = norm_raw(str(dd.get("finding") or ""))
            eff = parse_date(dd.get("effective_date") or dd.get("audit_date"))
            watts = dd.get("audited_watts")
            audit[fid].append((eff, finding, dec(watts)))
    for fid in audit:
        audit[fid].sort(key=lambda x: (x[0], x[1]))
    c.fixture_audit = audit
    # ---- photocell burn hours
    burn = {}
    ph = json.load(open(os.path.join(d, "photocell_burn_hours.json"), "rb"))
    for o in ph.get("rows", []):
        f = norm_feeder(o.get("feeder"))
        dt = parse_date(o.get("date"))
        burn[(f, dt)] = dec(o.get("hours"))
    c.burn_hours = burn
    # ---- burn hour exceptions
    exc = {}
    for title, rows in xlsx_rows(os.path.join(d, "lighting_burn_hour_exceptions_2025.xlsx")):
        if not rows:
            continue
        hdr = None
        for r in rows:
            cand = [str(x).strip().lower() if x is not None else "" for x in r]
            if "fixture_id" in cand and "hours" in cand:
                hdr = cand
                continue
            if hdr is None:
                continue
            dd = dict(zip(hdr, r))
            fid = norm_fixture(str(dd.get("fixture_id") or ""))
            dt = parse_date(dd.get("date"))
            if not fid or not dt:
                continue
            exc[(fid, dt)] = rhe(dec(dd.get("hours")), 2)
    c.burn_exceptions = exc


def load_scada(c):
    d = c.dir
    hist = defaultdict(dict)   # feeder -> instant -> (wh Decimal, quality str, source)
    # ---- north: demand kW
    for row in csv_dicts(os.path.join(d, "substation_north_scada_2025-11.csv")):
        f = norm_feeder(row.get("feeder"))
        ts_local = row.get("interval_end_local") or ""
        tz = norm_raw(row.get("tz") or "")
        try:
            dt = datetime.strptime(ts_local.strip(), "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if tz == "CST":
            dt = dt.replace(tzinfo=ZoneInfo("America/Chicago"), fold=1)
        else:
            dt = dt.replace(tzinfo=ZoneInfo("America/Chicago"))
        t = int(dt.timestamp())
        kw = dec(row.get("kw_avg"))
        q = norm_raw(row.get("quality"))
        wh = rhe(kw * Decimal(250), 0) if kw is not None else None
        hist[f][t] = (wh, q, "HISTORIAN")
    # ---- east: energy kWh per interval
    ej = json.load(open(os.path.join(d, "substation_east_scada_2025-11.json"), "rb"))
    for o in ej.get("intervals", []):
        f = norm_feeder(o.get("feeder") or o.get("fdr"))
        tval = o.get("end_utc", o.get("t"))
        try:
            t = int(tval)
        except (TypeError, ValueError):
            continue
        q = norm_raw(o.get("q") or o.get("quality"))
        kwh = dec(o.get("kwh") or o.get("value"))
        wh = rhe(kwh * Decimal(1000), 0) if kwh is not None else None
        hist[f][t] = (wh, q, "HISTORIAN")
    # ---- south: historian log (MWh in v1 records, kWh in v2 records)
    fmt = 1
    for rec in read_records(os.path.join(d, "substation_south_historian.log")):
        s = decode_line(rec).strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("FORMAT"):
            m = re.search(r"FORMAT\s+v(\d)", s)
            if m:
                fmt = int(m.group(1))
            continue
        if fmt == 2:
            if s.startswith("HIST|"):
                p = [x.strip() for x in s.split("|")]
                if len(p) < 5:
                    continue
                f = norm_feeder(p[1])
                try:
                    dt = datetime.strptime(p[2], "%Y-%m-%d %H:%M:%SZ").replace(
                        tzinfo=timezone.utc)
                    t = int(dt.timestamp())
                except Exception:
                    continue
                q = norm_raw(p[4])
                kwh = dec(p[3])
                wh = rhe(kwh * Decimal(1000), 0) if kwh is not None else None
                hist[f][t] = (wh, q, "HISTORIAN")
            continue
        m = re.match(r"^(\S+)\s+HIST\s+(\S+)\s+MWH=(\S+)\s+Q=(\S+)", s)
        if not m:
            continue
        try:
            dt = datetime.fromisoformat(m.group(1))
        except Exception:
            continue
        if dt.tzinfo is None:
            continue
        t = int(dt.timestamp())
        f = norm_feeder(m.group(2))
        mwh = dec(m.group(3))
        q = norm_raw(m.group(4))
        wh = rhe(mwh * Decimal(1000000), 0) if mwh is not None else None
        hist[f][t] = (wh, q, "HISTORIAN")
    # ---- west: monthly report pdf (kWh, quality); column order varies
    txt = pdf_text(os.path.join(d, "substation_west_monthly_report.pdf"))
    for line in txt.split("\n"):
        line = line.strip()
        if line.count("|") != 4:
            continue
        p = [x.strip() for x in line.split("|")]
        f = off = kwhs = q = dtstr = None
        for x in p:
            if re.match(r"^[Ff]\d{2}$", x) and f is None:
                f = norm_feeder(x)
            elif re.match(r"^[+-]\d{2}:\d{2}$", x) and off is None:
                off = x
            elif (re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", x) or
                  re.match(r"^\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}$", x)) and dtstr is None:
                dtstr = x
            elif (re.match(r"^-?[\d.,]+$", x) or x == "---") and kwhs is None:
                kwhs = x
            elif re.match(r"^[A-Za-z_]+$", x) and q is None:
                q = norm_raw(x)
        if f is None or dtstr is None:
            continue
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$", dtstr)
        if m:
            naive = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), int(m.group(5)))
        else:
            m2 = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4}) (\d{2}):(\d{2})$", dtstr)
            if not m2:
                continue
            naive = datetime(int(m2.group(3)), int(m2.group(1)), int(m2.group(2)),
                             int(m2.group(4)), int(m2.group(5)))
        mo = re.match(r"^([+-])(\d{2}):(\d{2})$", off or "")
        if mo:
            sign = -1 if mo.group(1) == "-" else 1
            t = int((naive - timedelta(hours=int(mo.group(2)),
                                       minutes=int(mo.group(3))) * sign).replace(
                tzinfo=timezone.utc).timestamp())
        else:
            t = int(naive.replace(tzinfo=TZ).timestamp())
        if kwhs in (None, "---", ""):
            wh = None
        else:
            kwh = dec(kwhs)
            wh = rhe(kwh * Decimal(1000), 0) if kwh is not None else None
        hist[f][t] = (wh, q or "", "HISTORIAN")
    c.historian = hist
    # ---- alarm journal
    alarms = defaultdict(list)
    for rec in read_records(os.path.join(d, "scada_alarm_journal.log")):
        s = decode_line(rec).strip()
        m = re.match(r"^(\S+) ALARM feeder=(\S+) type=(\S+) state=(\S+)", s)
        if not m:
            continue
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            t = int(dt.timestamp())
        except Exception:
            continue
        f = norm_feeder(m.group(2))
        typ = norm_raw(m.group(3))
        state = norm_raw(m.group(4))
        if typ != "COMM_FAIL":
            continue
        alarms[f].append((t, state))
    # pair RAISED/CLEARED into invalid windows per feeder
    windows = defaultdict(list)
    for f, lst in alarms.items():
        lst2 = sorted(lst)
        open_t = None
        for t, state in lst2:
            if state == "RAISED" and open_t is None:
                open_t = t
            elif state == "CLEARED" and open_t is not None:
                windows[f].append((open_t, t))
                open_t = None
        if open_t is not None:
            windows[f].append((open_t, None))
    c.alarm_windows = windows
    c.alarms = alarms
    # ---- scada errata
    err = {}
    supr = set()
    recs = []
    for line in text_of(os.path.join(d, "scada_errata_notice.md")).split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        p = [x.strip() for x in line.strip("|").split("|")]
        if len(p) < 6:
            continue
        if norm_raw(p[0]) == "ERRATUM" or p[0].startswith("---"):
            continue
        # identify fields by content (column order varies)
        eid = f = iend = issued = wh = st = sup = None
        seens = []
        for x in p:
            xu = norm_raw(x)
            if re.match(r"^F\d{2}$", xu) and f is None:
                f = xu
            elif re.match(r"^SE-\d+$", xu):
                seens.append(xu)
            elif re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", xu) and iend is None:
                iend = xu
            elif xu in ("APPROVED", "WITHDRAWN") and st is None:
                st = xu
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", xu) and issued is None:
                issued = xu
            elif re.match(r"^[\d.,\-]+$", xu) and wh is None and x.strip():
                wh = dec(x)
        if len(seens) >= 1:
            eid = seens[0]
        if len(seens) >= 2:
            sup = seens[-1]
        if st != "APPROVED" or not f or not iend or eid is None:
            continue
        if sup:
            supr.add(sup)
        recs.append((eid, f, iend, wh, issued, sup))
    for eid, f, iend, wh, issued, sup in recs:
        if eid in supr:
            continue
        try:
            dt = datetime.strptime(iend.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            t = int(dt.timestamp())
        except Exception:
            continue
        key = (f, t)
        cand = (parse_date(issued), num_of(eid), wh)
        cur = err.get(key)
        if cur is None or (cand[0], cand[1]) > (cur[0], cur[1]):
            err[key] = cand
    c.scada_errata = {k: v[2] for k, v in err.items()}
    # ---- east monthly report section 4: relay test replacement values
    relay = {}
    txt = pdf_text(os.path.join(d, "substation_east_monthly_report.pdf"))
    i = txt.find("Section 4.")
    if i >= 0:
        seg = txt[i:]
        for line in seg.split("\n"):
            line = line.strip()
            if line.count("|") != 3:
                continue
            p = [x.strip() for x in line.split("|")]
            if not re.match(r"^F\d{2}$", norm_raw(p[0])):
                continue
            if norm_raw(p[3]) != "DONE":
                continue
            try:
                dt = datetime.strptime(p[1].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                t = int(dt.timestamp())
            except Exception:
                continue
            kwh = dec(p[2])
            if kwh is None:
                continue
            relay[(norm_feeder(p[0]), t)] = rhe(kwh * Decimal(1000), 0)
    c.relay_test = relay
    # ---- analytics gap fill
    gap = {}
    for row in csv_dicts(os.path.join(d, "scada_15min_gapfill_2025-11.csv")):
        f = norm_feeder(row.get("feeder"))
        try:
            dt = datetime.strptime((row.get("interval_end_utc") or "").strip(),
                                    "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            t = int(dt.timestamp())
        except Exception:
            continue
        mv = norm_raw(row.get("model_version"))
        st = norm_raw(row.get("status"))
        if mv != "V3" or st != "PUBLISHED":
            continue
        wh = dec(row.get("wh_est"))
        gap[(f, t)] = rhe(wh, 0) if wh is not None else None
    c.gapfill = gap


# ---------------------------------------------------------------- head-end parsing


class Batch(object):
    def __init__(self, fname, hes):
        self.file = fname
        self.hes = hes
        self.rows = []          # parsed data rows in file order
        self.data_rows = 0      # count of data records in the file


def load_head_end_profiles(c):
    d = c.dir
    aur = yaml.safe_load(open(os.path.join(d, "aurora_hes_profile.yaml"), "rb"))
    cir = yaml.safe_load(open(os.path.join(d, "cirrus_hes_profile.yaml"), "rb"))
    fj = yaml.safe_load(open(os.path.join(d, "fjord_hes_profile.yaml"), "rb"))
    # firmware / multiplier histories keyed by meter or device
    c.aurora_firmware = _hist_by_key(aur.get("firmware_history", []), "meter_id")
    c.cirrus_firmware = _hist_by_key(cir.get("firmware_history", []), "device")
    c.fjord_mult = _hist_by_key(fj.get("multiplier_applied_entries", []), "meter_id")
    # fjord 2026 profile entries in force (November pilot)
    fj26 = yaml.safe_load(open(os.path.join(d, "fjord_hes_profile_2026.yaml"), "rb"))
    extra = _hist_by_key(fj26.get("multiplier_applied_entries", []), "meter_id")
    for m, lst in extra.items():
        c.fjord_mult.setdefault(m, []).extend(lst)
    rules = ((aur.get("units", {}) or {}).get("firmware_rules", []))
    c.aurora_unit_rules = [(r.get("match", "*"), r.get("unit", "kWh")) for r in rules]
    # borealis channel map
    chmap = defaultdict(list)
    txt = text_of(os.path.join(d, "borealis_channel_map.toml"))
    cur = None
    for line in txt.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^meter_id\s*=\s*"?([^"]+)"?', line)
        if m:
            cur = norm_meter(m.group(1))
            continue
        m = re.match(r"^import_channel\s*=\s*(\d+)", line)
        if m and cur:
            chmap[cur].append({"imp": int(m.group(1))})
            continue
        m = re.match(r"^export_channel\s*=\s*(\d+)", line)
        if m and cur and chmap[cur]:
            chmap[cur][-1]["exp"] = int(m.group(1))
            continue
        m = re.match(r'^effective_from\s*=\s*"?([^"]+)"?', line)
        if m and cur and chmap[cur]:
            chmap[cur][-1]["eff"] = parse_date(m.group(1))
    cchannel = {}
    for m, lst in chmap.items():
        cchannel[m] = [(e.get("eff", ""), e) for e in lst]
    c.channel_map = cchannel


def _hist_by_key(entries, key):
    out = defaultdict(list)
    for e in entries:
        if not isinstance(e, dict):
            continue
        k = e.get(key) or e.get("meter_id") or e.get("device") or e.get("meter")
        eff = e.get("effective_from") or e.get("since")
        if k is None or eff is None:
            continue
        out[norm_raw(str(k)) if key == "device" else norm_meter(str(k))].append(
            (parse_date(eff), e))
    return out


def _fw_match(pattern, fw):
    rx = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(rx, fw) is not None


def latest_entry(entries, day, extract):
    """entries: list of (eff_date, obj) or (eff, *rest); pick latest eff <= day."""
    best = None
    for e in entries:
        eff, o = e[0], e[1]
        if eff <= day:
            if best is None or eff >= best[0]:
                best = (eff, o)
    return extract(best[1]) if best else None


def round3(v):
    if v is None:
        return None
    return rhe(v, 3)


def parse_aurora(c, fname):
    """Yield dicts: meter, ts (reported epoch), seq, imp, exp (kWh Decimals)."""
    out = []
    hdr = None
    n = 0
    for rec in read_records(os.path.join(c.dir, fname)):
        s = decode_line(rec)
        if not s.strip():
            continue
        if s.startswith("#"):
            continue
        cells = next(csv.reader(io.StringIO(s)))
        cells = [x.strip() for x in cells]
        low = [x.lower() for x in cells]
        if "meter_id" in low:
            hdr = low
            continue
        n += 1
        if hdr is None:
            continue
        d = dict(zip(hdr, cells))
        meter = norm_meter(d.get("meter_id") or "")
        ts_raw = (d.get("read_local") or "").strip()
        dt = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                dt = datetime.strptime(ts_raw, fmt)
                break
            except ValueError:
                continue
        if dt is None or not meter:
            out.append(None)
            continue
        imp = dec(d.get("register_import"), thousands=True)
        exp = dec(d.get("register_export"), thousands=True)
        if imp is not None and imp == -1:
            imp = None
        if exp is not None and exp == -1:
            exp = None
        seq = int(dec(d.get("seq")) or 0)
        # unit conversion by firmware on the local date of the reported timestamp
        day = dt.date().isoformat()
        fw = latest_entry(c.aurora_firmware.get(meter, []), day, lambda o: o.get("firmware"))
        unit = "kWh"
        if fw:
            for pat, u in c.aurora_unit_rules:
                if _fw_match(pat, fw):
                    unit = u
                    break
        if unit == "Wh":
            imp = imp / Decimal(1000) if imp is not None else None
            exp = exp / Decimal(1000) if exp is not None else None
        out.append({
            "meter": meter, "ts": to_instant(dt), "seq": seq,
            "imp": round3(imp), "exp": round3(exp),
        })
    return out, n


def parse_borealis(c, fname):
    out = []
    txt = text_of(os.path.join(c.dir, fname))
    pat = re.compile(r'<(Read|Rd)\s+([^>]*?)>(.*?)</(?:Read|Rd)>', re.S)
    n = 0
    for m in pat.finditer(txt):
        attrs = m.group(2)
        body = m.group(3)
        meter = ts = seq = None
        for am in re.finditer(r'(\w+)="([^"]*)"', attrs):
            k = am.group(1).lower()
            if k == "meter" or k == "m":
                meter = norm_meter(am.group(2))
            elif k == "ts" or k == "t":
                ts = am.group(2)
            elif k == "seq" or k == "sq":
                seq = int(am.group(2))
        n += 1
        if not meter or not ts:
            out.append(None)
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            out.append(None)
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        t = int(dt.timestamp())
        day = local_date_of(t).isoformat()
        chs = []
        for cm in re.finditer(r'<Ch ([^>]*?)(?:/>|>([^<]*)</Ch>)', body):
            attrs2 = cm.group(1)
            unit = q = chn = None
            for am in re.finditer(r'(\w+)="([^"]*)"', attrs2):
                if am.group(1) == "n":
                    chn = int(am.group(2))
                elif am.group(1) == "unit":
                    unit = am.group(2)
                elif am.group(1) == "q":
                    q = am.group(2)
            val = cm.group(2)
            if q == "MISSING":
                chs.append((chn, unit, None))
            else:
                chs.append((chn, unit, dec(val)))
        cmap = {}
        for cm in chs:
            cmap[cm[0]] = (cm[1], cm[2])
        imp = exp = None
        entry = latest_entry(c.channel_map.get(meter, []), day,
                             lambda o: (o.get("imp"), o.get("exp")))
        if entry:
            ich, ech = entry
            if ich in cmap:
                u, v = cmap[ich]
                if v is not None:
                    imp = v / Decimal(1000) if (u or "").upper() == "WH" else v
            if ech in cmap:
                u, v = cmap[ech]
                if v is not None:
                    exp = v / Decimal(1000) if (u or "").upper() == "WH" else v
        out.append({
            "meter": meter, "ts": t, "seq": seq,
            "imp": round3(imp), "exp": round3(exp),
        })
    return out, n


def parse_cirrus(c, fname, period):
    out = []
    n = 0
    schema = 1
    for rec in read_records(os.path.join(c.dir, fname)):
        s = decode_line(rec).strip()
        if not s:
            continue
        try:
            o = json.loads(s)
        except Exception:
            continue
        if "_schema" in o:
            schema = int(o["_schema"])
            continue
        n += 1
        dev = norm_eui(str(o.get("dev") if schema == 1 else o.get("device") or ""))
        meter = c.cirrus_link.get((dev, period))
        tsv = o.get("ts") if schema == 1 else o.get("t")
        try:
            t = int(tsv)
        except (TypeError, ValueError):
            out.append(None)
            continue
        seq = int(dec(o.get("seq") if schema == 1 else o.get("sequence")) or 0)
        imp = o.get("imp") if schema == 1 else o.get("import")
        exp = o.get("exp") if schema == 1 else o.get("export")
        day = local_date_of(t).isoformat()
        fw = latest_entry(c.cirrus_firmware.get(dev, []), day, lambda x: x.get("firmware"))
        sep = "."
        if fw and fw.startswith("CX-4.1"):
            sep = ","
        imp = _cirrus_val(imp, sep)
        exp = _cirrus_val(exp, sep)
        out.append({
            "meter": meter, "ts": t, "seq": seq,
            "imp": round3(imp), "exp": round3(exp),
        })
    return out, n


def _cirrus_val(v, sep):
    if v is None:
        return None
    if isinstance(v, (int,)):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    s = str(v).strip()
    if s == "" or s.upper() == "ERR":
        return None
    if sep == ",":
        s = s.replace(".", "").replace(",", ".")
    return dec(s)


def parse_delta(c, fname):
    out = []
    tbl = pq.read_table(os.path.join(c.dir, fname))
    data = tbl.to_pydict()
    n = len(data.get("spid", []))
    for i in range(n):
        sp = norm_sp(str(data["spid"][i]))
        raw_imp = data["import_raw"][i]
        raw_exp = data["export_raw"][i]
        est = data["est_flag"][i]
        serial = data["read_serial"][i]
        seq = data["load_id"][i]
        dt = excel_serial_date(serial)
        if dt is None:
            out.append(None)
            continue
        t = to_instant(dt)
        if est == 1 and c.est_policy.get(sp) != "ACCEPT":
            out.append({"sp": sp, "ts": t, "seq": seq, "imp": None, "exp": None})
            continue
        # resolve spid to meter using rows valid at the read instant
        meter = None
        for row in c.sp_xref.get(sp, []):
            if row["status"] == "VOID":
                continue
            vf = row["from"]
            vt = row["to"]
            if vf is not None and vf > t:
                continue
            if vt is not None and vt <= t:
                continue
            meter = row["meter"]
            break
        imp = exp = None
        if meter:
            dd = c.scaling_decimals.get(meter, 3)
            scale = Decimal(10) ** dd
            if raw_imp is not None and raw_imp != -1:
                imp = Decimal(raw_imp) / scale
            if raw_exp is not None and raw_exp != -1:
                exp = Decimal(raw_exp) / scale
        out.append({"meter": meter, "ts": t, "seq": seq,
                    "imp": round3(imp), "exp": round3(exp)})
    return out, n


FJORD_ALIASES = {
    "seq": "seq", "meter": "meter", "meter_id": "meter", "ts_ms": "ts_ms",
    "epoch_ms": "ts_ms", "import_kwh": "import_kwh", "imp": "import_kwh",
    "export_kwh": "export_kwh", "exp": "export_kwh", "flags": "flags", "flg": "flags",
}


def parse_fjord(c, fname):
    out = []
    n = 0
    revs = []
    hdr = None
    for rec in read_records(os.path.join(c.dir, fname)):
        s = decode_line(rec).strip("\r")
        if not s.strip():
            continue
        if s.startswith("#"):
            continue
        parts = s.split("\t")
        while len(parts) > 1 and parts[-1] == "":
            parts.pop()
        if parts and parts[0].lower() in ("seq", "meter"):
            hdr = [FJORD_ALIASES.get(p.strip().lower(), p.strip().lower()) for p in parts]
            continue
        if parts and parts[0] == "REV":
            # REV  meter  seq  read_date
            if len(parts) >= 4:
                revs.append((norm_meter(parts[1]), parse_date(parts[3]), int(dec(parts[2]) or 0)))
            continue
        n += 1
        if hdr is None or len(parts) < 5:
            out.append(None)
            continue
        d = dict(zip(hdr, parts))
        meter = norm_meter(d.get("meter") or "")
        tsms = dec(d.get("ts_ms"))
        if not meter or tsms is None:
            out.append(None)
            continue
        t = int(tsms) // 1000
        seq = int(dec(d.get("seq")) or 0)
        imp = dec(d.get("import_kwh"))
        exp = dec(d.get("export_kwh"))
        if imp is not None and imp == Decimal("9999999.999"):
            imp = None
        if exp is not None and exp == Decimal("9999999.999"):
            exp = None
        out.append({"meter": meter, "ts": t, "seq": seq, "imp": imp, "exp": exp,
                    "_mult": None})
    return out, n, revs


def parse_cis_legacy(c, fname):
    out = []
    n = 0
    layout = 1
    for rec in read_records(os.path.join(c.dir, fname)):
        s = decode_line(rec).rstrip("\r")
        if not s.strip():
            continue
        tag = s[0]
        if tag == "H":
            continue
        if tag == "L":
            m = re.match(r"^L(\d)", s)
            if m:
                layout = int(m.group(1))
            continue
        if tag == "T":
            continue
        if tag != "D":
            continue
        n += 1
        if layout == 1:
            lid = norm_legacy(s[1:10])
            dstr = s[10:17]
            tstr = s[17:21]
            imp = s[21:31]
            exp = s[31:41]
            seq = s[41:51]
        else:
            dstr = s[1:8]
            tstr = s[8:12]
            seq = s[12:22]
            lid = norm_legacy(s[22:31])
            imp = s[31:42]
            exp = s[42:53]
        meter = c.legacy_crosswalk.get(lid)
        # ordinal date
        m = re.match(r"^(\d{4})(\d{3})$", dstr.strip())
        if not m:
            out.append(None)
            continue
        try:
            d0 = date(int(m.group(1)), 1, 1) + timedelta(days=int(m.group(2)) - 1)
        except Exception:
            out.append(None)
            continue
        hhmm = tstr.strip()
        if hhmm == "2400":
            dt = datetime(d0.year, d0.month, d0.day) + timedelta(days=1)
        else:
            hh = int(hhmm[:-2]) if hhmm[:-2] else 0
            mm = int(hhmm[-2:]) if len(hhmm) >= 2 else 0
            dt = datetime(d0.year, d0.month, d0.day, hh, mm)
        t = to_instant(dt)
        dial = c.dial_constant.get(lid, 1)
        imp = _fw_field(imp, dial)
        exp = _fw_field(exp, dial, no_register=True)
        out.append({"meter": meter, "ts": t, "seq": int(dec(seq) or 0),
                    "imp": round3(imp), "exp": round3(exp)})
    return out, n


def _fw_field(field, dial, no_register=False):
    """Fixed-width register field: implied 3 decimals, blanks are zeros,
    all nines means missing; a fully blank export field means no register."""
    s = (field or "").strip()
    if no_register and s == "":
        return None
    if s != "" and set(s) == {"9"}:
        return None
    s = (field or "").replace(" ", "0")
    val = dec(s)
    if val is None:
        return None
    return val / Decimal(1000) * Decimal(dial)


# ---------------------------------------------------------------- candidate collection


HES_FILE_MAP = [
    ("aurora_reads_2025-11_p%d.csv", "AUR", "aurora"),
    ("borealis_reads_2025-11_p%d.xml", "BOR", "borealis"),
    ("cirrus_reads_2025-11_p%d.jsonl", "CIR", "cirrus"),
    ("delta_reads_2025-11_p%d.parquet", "DLT", "delta"),
    ("fjord_reads_2025-11_p%d.tsv", "FJD", "fjord"),
]
CIS_FILES = ["cis_legacy_reads_2025-11_%s.txt" % ch for ch in ("a", "b", "c")]


def all_read_files(c):
    out = []
    for pattern, hes, kind in HES_FILE_MAP:
        for p in range(1, 20):
            fn = pattern % p
            if not os.path.exists(os.path.join(c.dir, fn)):
                break
            out.append((fn, hes, kind, p))
    for fn in CIS_FILES:
        if os.path.exists(os.path.join(c.dir, fn)):
            out.append((fn, "CIS", "cis", None))
    # the fjord resend
    if os.path.exists(os.path.join(c.dir, "fjord_reads_2025-11_p4b.tsv")):
        out.append(("fjord_reads_2025-11_p4b.tsv", "FJD", "fjord_resend", 4))
    return out


def read_time_for(c, meter, day):
    entries = c.schedule_all.get(meter, [])
    best = None
    for eff, rt in entries:
        if eff <= day:
            if best is None or eff > best[0] or (eff == best[0] and rt != best[1]):
                best = (eff, rt)
    return best[1] if best else None


class Settlement(object):
    def __init__(self, c):
        self.c = c
        self.boundary_inst = {}      # (read_time, date) -> epoch
        self.meter_boundaries = {}   # meter -> {date: instant}
        self.service_dates = {}      # meter -> set of dates
        self.boundary_values = {}    # (meter, date) -> dict
        self.meter_energy = {}      # meter -> {date: [imp_wh, exp_wh]}
        self.account_energy = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
        self.feeder_energy = defaultdict(lambda: [0, 0, 0, 0, 0])
        self.candidates_by_boundary = defaultdict(list)

    # -- boundary instants ------------------------------------------------
    def instant_for(self, read_time, day):
        key = (read_time, day)
        if key in self.boundary_inst:
            return self.boundary_inst[key]
        if read_time == "23:00":
            dt = datetime(day.year, day.month, day.day, 23, 0) - timedelta(days=1)
        else:
            dt = datetime(day.year, day.month, day.day, 0, 0)
        t = to_instant(dt)
        self.boundary_inst[key] = t
        return t

    def build_boundaries(self):
        c = self.c
        # exchange info
        old_of = defaultdict(list)
        new_of = defaultdict(list)
        for e in c.exchanges:
            old_of[e["old"]].append(e["t"])
            new_of[e["new"]].append(e["t"])
        self.old_of = old_of
        self.new_of = new_of
        for meter in c.registry:
            rows = c.registry[meter]
            # service dates
            sdates = set()
            for D in BOUNDARY_DATES:
                covered = False
                for r in rows:
                    if r["valid_from"] <= D.isoformat() and (
                            r["valid_to"] is None or r["valid_to"] == "" or
                            D.isoformat() < r["valid_to"]):
                        covered = True
                        break
                if old_of.get(meter):
                    xmax = max(local_date_of(t) for t in old_of[meter])
                    if D > xmax:
                        covered = False
                    elif D == xmax:
                        covered = True
                if new_of.get(meter):
                    xmin = min(local_date_of(t) for t in new_of[meter])
                    if D <= xmin:
                        covered = False
                if covered:
                    sdates.add(D)
            if not sdates:
                continue
            bmap = {}
            for D in sdates:
                rt = read_time_for(c, meter, D.isoformat())
                if rt is None:
                    continue
                bmap[D] = self.instant_for(rt, D)
            if bmap:
                self.service_dates[meter] = sdates
                self.meter_boundaries[meter] = bmap

    # -- candidates -------------------------------------------------------
    def collect(self):
        c = self.c
        # per-file control info
        control = {}
        for fn, hes, kind, period in all_read_files(c):
            control[fn] = {"hes": hes, "kind": kind, "period": period,
                           "batch": c.batch_control.get(fn),
                           "manifest": c.manifest.get(fn)}
        self.control = control
        # fjord reversals (from the resend)
        revs = set()
        for fn, info in control.items():
            if info["kind"] != "fjord_resend":
                continue
            rows, n, rlist = parse_fjord(c, fn)
            for meter, rd, seq in rlist:
                revs.add((meter, rd))
        self.fjord_reversals = revs
        # parse every file and filter
        for fn, info in control.items():
            hes = info["hes"]
            batch = info["batch"]
            man = info["manifest"]
            rejected = set()
            withdrawn = set()
            if batch:
                if batch["status"] == "REJECTED":
                    rejected = None   # all rows
                elif batch["status"] == "PARTIAL" and batch["rejected_from"] is not None:
                    rejected = set(range(batch["rejected_from"], batch["rejected_to"] + 1))
            if man and man["withdrawn"]:
                m = re.match(r"^(\d+)-(\d+)$", str(man["withdrawn"]).strip())
                if m:
                    withdrawn = set(range(int(m.group(1)), int(m.group(2)) + 1))
            if info["kind"] == "aurora":
                rows, n = parse_aurora(c, fn)
            elif info["kind"] == "borealis":
                rows, n = parse_borealis(c, fn)
            elif info["kind"] == "cirrus":
                rows, n = parse_cirrus(c, fn, info["period"])
            elif info["kind"] == "delta":
                rows, n = parse_delta(c, fn)
            elif info["kind"] == "fjord":
                rows, n, _ = parse_fjord(c, fn)
            elif info["kind"] == "fjord_resend":
                rows, n, _ = parse_fjord(c, fn)
            elif info["kind"] == "cis":
                rows, n = parse_cis_legacy(c, fn)
            else:
                rows, n = [], 0
            self.control[fn]["data_rows"] = n
            for idx, row in enumerate(rows, start=1):
                if not row or not row.get("meter"):
                    continue
                if rejected is None or idx in rejected or idx in withdrawn:
                    continue
                self._add_candidate(fn, hes, idx, row)

    def _add_candidate(self, fn, hes, idx, row):
        c = self.c
        meter = row["meter"]
        ts = row["ts"]
        offset = c.clock_offsets.get(meter, 0)
        sync = c.clock_sync.get(meter)
        true_ts = ts - offset if (sync is None or (ts - offset) < sync) else ts
        # exchange window
        for t in self.old_of.get(meter, []):
            if true_ts >= t:
                return
        for t in self.new_of.get(meter, []):
            if true_ts < t:
                return
        # fjord multiplier applied flag
        imp, exp = row["imp"], row["exp"]
        if hes == "FJD":
            day = local_date_of(true_ts).isoformat()
            applied = latest_entry(c.fjord_mult.get(meter, []), day,
                                    lambda o: o.get("multiplier_applied"))
            if applied:
                mult = self.multiplier_at(meter, true_ts)
                if mult:
                    if imp is not None:
                        imp = imp / Decimal(mult)
                    if exp is not None:
                        exp = exp / Decimal(mult)
                    imp = round3(imp)
                    exp = round3(exp)
        if imp is None and exp is None:
            return
        bmap = self.meter_boundaries.get(meter)
        if not bmap:
            return
        for D, bt in bmap.items():
            if abs(true_ts - bt) <= 900:
                key = (meter, D)
                self.candidates_by_boundary[key].append({
                    "ts": true_ts, "dist": abs(true_ts - bt), "seq": row["seq"],
                    "imp": imp, "exp": exp, "hes": hes, "file": fn, "idx": idx,
                })
                return

    def multiplier_at(self, meter, t):
        """multiplier in force at instant t (epoch seconds)."""
        c = self.c
        events = []  # (instant, priority, multiplier)
        for r in c.registry.get(meter, []):
            vf = r["valid_from"]
            if not vf:
                continue
            inst = to_instant(datetime.strptime(vf, "%Y-%m-%d"))
            events.append((inst, 0, r["multiplier"]))
        for ch in c.ct_changes:
            if ch["meter"] == meter:
                m = re.match(r"^\s*(\d+)\s*:\s*5", ch["new_ratio"] or "")
                if m:
                    events.append((ch["t"], 2, int(m.group(1))))
        for v in c.ct_verifications:
            if v["meter"] == meter:
                inst = to_instant(datetime.strptime(v["verified_on"], "%Y-%m-%d"))
                events.append((inst, 1, v["multiplier"]))
        best = None
        for inst, pri, mult in events:
            if inst <= t:
                if best is None or (inst, pri) > (best[0], best[1]):
                    best = (inst, pri, mult)
        if best is None:
            # fall back to the earliest registry row
            rows = c.registry.get(meter, [])
            if rows:
                return rows[0]["multiplier"]
            return 1
        return best[2]

    # -- boundary resolution ---------------------------------------------
    def resolve_boundaries(self):
        c = self.c
        for meter, bmap in self.meter_boundaries.items():
            for D in bmap:
                key = (meter, D)
                diso = D.isoformat()
                # (1) validated correction
                corr = None
                for cr in c.corrections.get((meter, diso), []):
                    if cr["status"] == "VALIDATED":
                        if corr is None or cr["revision"] > corr["revision"]:
                            corr = cr
                # (2) actual read
                actual = None
                kind = None
                cands = []
                if diso == "2025-11-01":
                    cr = c.close_reads.get(meter)
                    if cr is not None:
                        actual = {"imp": round3(cr["imp"]), "exp": round3(cr["exp"]),
                                  "dist": 0, "seq": 0, "hes": "", "file": "", "idx": 0}
                        kind = "CLOSE"
                else:
                    cands = self.candidates_by_boundary.get(key, [])
                    if cands:
                        # exclusions
                        surv = []
                        for cd in cands:
                            if self._excluded(meter, D, cd):
                                continue
                            surv.append(cd)
                        if surv:
                            surv.sort(key=lambda x: (x["dist"], -x["seq"]))
                            actual = surv[0]
                            kind = "HEADEND"
                # (3) vee estimate
                est = None
                if actual is None or actual["imp"] is None:
                    est = self._approved_estimate(meter, D)
                imp = exp = None
                src = "MISSING"
                if corr is not None:
                    imp, exp, src = corr["imp"], corr["exp"], "CORRECTION"
                elif actual is not None:
                    imp, exp = actual["imp"], actual["exp"]
                    src = "ACTUAL" if (kind == "HEADEND" or
                                       (kind == "CLOSE" and c.close_reads[meter]["status"] == "ACTUAL")) else "ESTIMATE"
                elif est is not None:
                    imp, exp, src = est["imp"], est["exp"], "ESTIMATE"
                self.boundary_values[key] = {
                    "imp": imp, "exp": exp, "src": src,
                    "instant": bmap[D], "candidates": len(cands) if diso != "2025-11-01" else 0,
                }

    def _approved_estimate(self, meter, D):
        c = self.c
        best = None
        for e in c.estimates.get((meter, D.isoformat()), []):
            reviews = c.estimate_reviews.get(e["id"], [])
            if not reviews:
                continue
            latest = max(reviews, key=lambda x: x[0])
            if latest[1] != "APPROVED":
                continue
            if best is None or e["version"] > best["version"]:
                best = e
        return best

    def _excluded(self, meter, D, cand):
        c = self.c
        diso = D.isoformat()
        hes = cand["hes"]
        if (hes, meter, diso) in c.void_reads:
            return True
        if (meter, diso) in c.held_reads:
            return True
        if (meter, diso, hes) in self.quarantined:
            return True
        if (meter, diso) in self.fjord_reversals and hes == "FJD":
            return True
        # disputes: latest decision for (meter, date)
        dl = c.disputes.get(meter, [])
        decisions = [d for d in dl if d[1] == diso]
        if decisions:
            latest = max(decisions, key=lambda x: (x[0], x[2]))
            if latest[2] == "UPHELD":
                return True
        # known issues
        code = c.known_issues.get((meter, diso, hes))
        if code == "STUCK_REGISTER":
            return True
        if code == "WH_AS_KWH":
            if cand["imp"] is not None:
                cand["imp"] = round3(cand["imp"] / Decimal(1000))
            if cand["exp"] is not None:
                cand["exp"] = round3(cand["exp"] / Decimal(1000))
        elif code == "SWAP_REGISTERS":
            cand["imp"], cand["exp"] = cand["exp"], cand["imp"]
        return False

    def build_quarantine(self):
        c = self.c
        q = set()
        for key, lst in c.quarantine.items():
            lst2 = sorted(lst)
            has_q = False
            for ts, kind in lst2:
                if kind == "QUARANTINE":
                    has_q = True
                elif kind == "UNQUARANTINE":
                    has_q = False
            if has_q:
                q.add(key)
        self.quarantined = q

    # -- register arithmetic ----------------------------------------------
    def compute_energy(self):
        c = self.c
        self.boundary_state = {}   # (meter, date) -> 'OK' | 'INVALIDATED'
        for meter, bmap in self.meter_boundaries.items():
            anchors_imp = []
            anchors_exp = []
            for D in bmap:
                bv = self.boundary_values.get((meter, D))
                if bv is None:
                    continue
                if bv["imp"] is not None:
                    anchors_imp.append((bv["instant"], bv["imp"], D, "boundary"))
                if bv["exp"] is not None:
                    anchors_exp.append((bv["instant"], bv["exp"], D, "boundary"))
            # exchange anchors
            for e in c.exchanges:
                if e["old"] == meter:
                    if e["old_imp"] is not None:
                        anchors_imp.append((e["t"], round3(e["old_imp"]), None, "exchange"))
                    if e["old_exp"] is not None:
                        anchors_exp.append((e["t"], round3(e["old_exp"]), None, "exchange"))
                if e["new"] == meter:
                    if e["new_imp"] is not None:
                        anchors_imp.append((e["t"], round3(e["new_imp"]), None, "exchange"))
                    if e["new_exp"] is not None:
                        anchors_exp.append((e["t"], round3(e["new_exp"]), None, "exchange"))
            # ct change anchors (import register only)
            for ch in c.ct_changes:
                if ch["meter"] == meter and ch["register"] is not None:
                    anchors_imp.append((ch["t"], round3(ch["register"]), None, "ct"))
            # register resets
            for r in c.register_resets.get(meter, []):
                anchors_imp.append((r["t"], r["pre"], None, "reset_pre"))
                anchors_imp.append((r["t"], r["post"], None, "reset_post"))
                anchors_exp.append((r["t"], r["pre"], None, "reset_pre"))
                anchors_exp.append((r["t"], r["post"], None, "reset_post"))
            energy = defaultdict(lambda: [0, 0])   # date -> [imp_wh, exp_wh]
            for which, anchors in ((0, anchors_imp), (1, anchors_exp)):
                # stable sort by instant, boundaries before resets at the same instant
                anchors = sorted(anchors, key=lambda a: (a[0], 0 if a[3] == "boundary" else 1))
                prev_val = None
                prev_key = None
                digits = c.rollover_digits.get(meter, 6)
                cap = Decimal(10) ** digits
                for t, val, D, atype in anchors:
                    if atype == "reset_pre":
                        if prev_val is not None:
                            delta = val - prev_val
                            self._add_segment(energy, meter, prev_key, t, delta, which)
                        continue
                    if atype == "reset_post":
                        prev_val = val
                        prev_key = None
                        continue
                    if prev_val is None:
                        prev_val = val
                        prev_key = (t, D, atype)
                        continue
                    delta = val - prev_val
                    if delta < 0:
                        if prev_val >= cap * Decimal("0.9") and val < cap * Decimal("0.1"):
                            delta = delta + cap
                        elif atype == "boundary":
                            if which == 0:
                                self.boundary_state[(meter, D)] = "INVALIDATED"
                            continue
                    self._add_segment(energy, meter, prev_key, t, delta, which)
                    prev_val = val
                    prev_key = (t, D, atype)
            # accuracy correction
            acc = c.accuracy_fail.get(meter)
            if acc:
                test_date, tid, pct = acc
                denom = Decimal(100) + pct
                if denom != 0:
                    for d in energy:
                        if d.isoformat() < test_date:
                            wh = energy[d][0]
                            energy[d][0] = rhe_int(Fraction(wh) * 100 / Fraction(denom))
            self.meter_energy[meter] = energy

    def _add_segment(self, energy, meter, prev_key, end_t, delta, which):
        """delta in kWh; multiplier in force 1s before end_t; date = local date of end_t-1s."""
        if delta == 0:
            return
        mult = self.multiplier_at(meter, end_t - 1)
        wh = rhe(delta * Decimal(1000) * Decimal(mult), 0)
        d = local_date_of(end_t - 1)
        energy[d][which] += int(wh)

    # -- billing ----------------------------------------------------------
    def resolve_account(self, meter, day):
        """registry row valid on day, then merges in force."""
        c = self.c
        acct = None
        for r in c.registry.get(meter, []):
            if r["valid_from"] <= day and (not r["valid_to"] or day < r["valid_to"]):
                acct = r["account"]
        if acct is None:
            return None
        seen = set()
        cur = acct
        while True:
            nxt = None
            best_eff = None
            for eff, succ in c.merge_map.get(cur, []):
                if eff <= day and cur not in seen:
                    if best_eff is None or eff > best_eff:
                        best_eff = eff
                        nxt = succ
            if nxt is None or nxt in seen:
                break
            seen.add(cur)
            cur = nxt
        return cur

    def is_vacant(self, acct, day):
        c = self.c
        info = c.account_master.get(acct)
        if not info:
            return False
        if info["status"] == "FINAL" and info["final_date"] and info["final_date"] <= day:
            return True
        return False

    def is_disconnected(self, meter, day):
        c = self.c
        evs = c.disconnections.get(meter, [])
        latest = None
        for d, ev in evs:
            if d <= day:
                if latest is None or (d, ev) > latest:
                    latest = (d, ev)
        return bool(latest and latest[1] == "DISCONNECT")

    def export_credited(self, meter, day):
        """True when an approved net metering application covers the day and the
        latest export inspection on or before the day is PASS."""
        c = self.c
        ok = False
        for app in c.net_metering.get(meter, []):
            if app["status"] != "APPROVED":
                continue
            if app["from"] <= day and (not app["to"] or day < app["to"]):
                ok = True
                break
        if not ok:
            return False
        insp = c.inspections.get(meter, [])
        latest = None
        for d, res in insp:
            if d <= day:
                if latest is None or d > latest[0]:
                    latest = (d, res)
        return bool(latest and latest[1] == "PASS")

    def rate_code_for(self, acct, day):
        c = self.c
        entries = [e for e in c.rate_history.get(acct, [])
                   if e[0] <= day and e[1] not in c.reversed_entry_ids]
        rc = None
        if entries:
            entries.sort(key=lambda x: (x[0], x[1]))
            rc = entries[-1][2]
        # migrations effective inside the settlement month outrank a history entry
        # with the same effective date
        for eff, mrc in c.migrations.get(acct, []):
            if eff <= day:
                if eff >= "2025-11-01" and eff <= "2025-11-30":
                    if rc is None or eff >= (entries[-1][0] if entries else ""):
                        rc = mrc
            elif eff <= "2025-12-31":
                continue
        if rc is None:
            info = c.account_master.get(acct)
            rc = info["rate_snapshot"] if info else ""
        if rc in c.legacy_alias:
            rc = c.legacy_alias[rc]
        return rc

    def daytype_of(self, territory, day):
        c = self.c
        if day in c.holiday_days.get(territory, set()):
            return "HOLIDAY"
        if day in c.cpp_days.get(territory, set()):
            return "CPP"
        if day.weekday() >= 5:
            return "WEEKEND"
        return "WEEKDAY"

    def base_rate(self, rc, day, daytype):
        c = self.c
        val = c.tariff_errata.get((rc, day.isoformat(), daytype))
        if val is None:
            val = c.base_rates.get((rc, day.isoformat(), daytype))
        return val

    def rider_adder(self, rc, day, territory):
        c = self.c
        total = Decimal(0)
        for rname, spans in c.riders_by_rate.get(rc, []):
            val = None
            for frm, to, adder in spans:
                if frm <= day.isoformat() < to:
                    if val is None or frm > val[0]:
                        val = (frm, adder)
            if val is None:
                continue
            # applicability
            applies = None
            for eff, ap in c.rider_applicability.get((rc, rname, territory), []):
                if eff <= day.isoformat():
                    if applies is None or eff > applies[0]:
                        applies = (eff, ap)
            if applies and applies[1] == "Y":
                total += val[1]
        # storm recovery rider
        sv = None
        for eff, adder in c.storm_rider.get(rc, []):
            if eff <= day.isoformat() and eff <= "2025-11-30":
                if sv is None or eff > sv[0]:
                    sv = (eff, adder)
        if sv is not None:
            total += sv[1]
        return total

    def credit_rate(self, rc, day, daytype):
        c = self.c
        return c.credit_rates.get((rc, day.isoformat(), daytype))

    def compute_billing(self):
        c = self.c
        self.meter_billing = {}       # meter -> per-day dict
        self.acct_days = defaultdict(lambda: defaultdict(lambda: {
            "imp": 0, "exp": 0, "deemed": 0, "terr": None, "fterr": None, "exp_terr": None}))
        for meter, energy in self.meter_energy.items():
            feeder = c.connectivity.get(meter)
            territory = c.territory.get(feeder) if feeder else None
            per_day = {}
            for day in DAYS:
                wh = energy.get(day)
                if wh is None:
                    continue
                imp_wh, exp_wh = wh
                if imp_wh == 0 and exp_wh == 0:
                    continue
                acct = self.resolve_account(meter, day.isoformat())
                vacant = self.is_vacant(acct, day.isoformat()) if acct else False
                disc = self.is_disconnected(meter, day.isoformat())
                billed = acct is not None and not vacant and not disc
                credited = billed and self.export_credited(meter, day.isoformat())
                per_day[day] = {
                    "acct": acct, "billed": billed, "imp": imp_wh,
                    "exp": exp_wh if credited else 0,
                    "exp_all": exp_wh, "territory": territory, "feeder": feeder,
                }
                if acct is not None:
                    cell = self.acct_days[acct][day]
                    if billed:
                        cell["imp"] += imp_wh
                        cell["terr"] = territory
                        cell["feeder"] = feeder
                        if credited:
                            cell["exp"] += exp_wh
                            cell["exp_terr"] = territory
            self.meter_billing[meter] = per_day
        # deemed energy
        self.fixture_days = {}
        for fid, fx in c.fixtures.items():
            feeder = fx["feeder"]
            territory = c.territory.get(feeder)
            per_day = {}
            for day in DAYS:
                if day.isoformat() < fx["installed"]:
                    continue
                if fx["removed"] and day.isoformat() >= fx["removed"]:
                    continue
                # audit REMOVED effective on or before d
                removed = False
                for eff, finding, watts in c.fixture_audit.get(fid, []):
                    if finding == "REMOVED" and eff <= day.isoformat():
                        removed = True
                        break
                if removed:
                    continue
                watts = None
                for eff, finding, w in c.fixture_audit.get(fid, []):
                    if finding == "WATTAGE_CHANGE" and eff <= day.isoformat():
                        if watts is None or eff >= watts[0]:
                            watts = (eff, w)
                if watts is not None and watts[1] is not None:
                    w = watts[1]
                else:
                    w = fx["watts"]
                if w is None:
                    continue
                # hours
                exc = c.burn_exceptions.get((fid, day.isoformat()))
                if exc is not None:
                    hours = exc
                else:
                    if fx["profile"] == "ALL_DAY":
                        hours = Decimal(24)
                    else:
                        base = c.burn_hours.get((feeder, day.isoformat()))
                        if base is None:
                            continue
                        hours = base
                        if fx["profile"] == "PART_NIGHT":
                            hours = hours - Decimal(6)
                            if hours < 0:
                                hours = Decimal(0)
                    hours = rhe(hours, 2)
                wh = rhe(w * hours, 0)
                per_day[day] = int(wh)
            self.fixture_days[fid] = per_day
        # attach deemed to accounts
        self.fixture_acct = {}
        for fid, per_day in self.fixture_days.items():
            fx = c.fixtures[fid]
            acct = fx["account"]
            # merges
            seen = set()
            cur = acct
            while True:
                nxt = None
                best_eff = None
                for eff, succ in c.merge_map.get(cur, []):
                    if eff <= "2025-11-30" and cur not in seen:
                        if best_eff is None or eff > best_eff:
                            best_eff = eff
                            nxt = succ
                if nxt is None or nxt in seen:
                    break
                seen.add(cur)
                cur = nxt
            acct = cur
            self.fixture_acct[fid] = acct
            for day, wh in per_day.items():
                if wh <= 0:
                    continue
                if self.is_vacant(acct, day.isoformat()):
                    continue
                cell = self.acct_days[acct][day]
                cell["deemed"] += wh
                cell["fterr"] = c.territory.get(fx["feeder"])

    # -- feeder injection --------------------------------------------------
    def compute_injection(self):
        c = self.c
        ends = interval_ends_local()
        self.interval_rows = {}      # (feeder, t) -> (wh, source)
        for f in FEEDERS:
            hf = c.historian.get(f, {})
            for t in ends:
                key = (f, t)
                if key in c.scada_errata:
                    self.interval_rows[key] = (int(c.scada_errata[key]), "ERRATUM")
                    continue
                east = c.table_f.get(f, {}).get("substation") == "east"
                if east and key in c.relay_test:
                    self.interval_rows[key] = (int(c.relay_test[key]), "RELAY_TEST")
                    continue
                val = hf.get(t)
                valid = False
                if val is not None:
                    wh, q, src = val
                    if wh is not None and q in ("GOOD", "G"):
                        start = t - 900
                        bad = False
                        for (r, cl) in c.alarm_windows.get(f, []):
                            if r < t and (cl is None or cl > start):
                                bad = True
                                break
                        valid = not bad
                if valid:
                    self.interval_rows[key] = (int(wh), "HISTORIAN")
                elif key in c.gapfill and c.gapfill[key] is not None:
                    self.interval_rows[key] = (int(c.gapfill[key]), "GAPFILL")
        self.injection = defaultdict(int)
        for (f, t), (wh, src) in self.interval_rows.items():
            self.injection[f] += wh

    # -- charges ----------------------------------------------------------
    def compute_charges(self):
        c = self.c
        self.account_rows = {}
        for acct, days in self.acct_days.items():
            energy = Fraction(0)
            rider = Fraction(0)
            credit = Fraction(0)
            imp_total = 0
            exp_total = 0
            deemed_total = 0
            last_day = None
            last_rc = ""
            for day in DAYS:
                cell = days.get(day)
                if cell is None:
                    continue
                imp = cell["imp"]
                exp = cell["exp"]
                deemed = cell["deemed"]
                if imp == 0 and exp == 0 and deemed == 0:
                    continue
                rc = self.rate_code_for(acct, day.isoformat())
                terr = cell["fterr"] if (deemed and cell["fterr"]) else cell["terr"]
                if terr is None and deemed:
                    terr = cell["fterr"]
                if terr is None:
                    terr = cell["terr"]
                if terr is None:
                    continue
                dt = self.daytype_of(terr, day)
                if imp or deemed:
                    br = self.base_rate(rc, day, dt)
                    if br is not None:
                        energy += Fraction(imp + deemed) * Fraction(br) / 1000
                    ra = self.rider_adder(rc, day, terr)
                    if ra is not None:
                        rider += Fraction(imp + deemed) * Fraction(ra) / 1000
                if exp:
                    cr = self.credit_rate(rc, day, dt)
                    if cr is not None:
                        credit += Fraction(exp) * Fraction(cr) / 1000
                imp_total += imp
                exp_total += exp
                deemed_total += deemed
                last_day = day
                last_rc = rc
            if imp_total or exp_total or deemed_total:
                energy_cents = rhe_int(energy)
                rider_cents = rhe_int(rider)
                credit_cents = rhe_int(credit)
                self.account_rows[acct] = {
                    "rate_code": last_rc,
                    "billed_import_wh": imp_total,
                    "billed_export_wh": exp_total,
                    "deemed_wh": deemed_total,
                    "energy_cents": energy_cents,
                    "rider_cents": rider_cents,
                    "export_credit_cents": -credit_cents,
                }

    # -- UFE ---------------------------------------------------------------
    def compute_ufe(self):
        c = self.c
        total_injection = sum(self.injection.values())
        total_export = sum(r["billed_export_wh"] for r in self.account_rows.values())
        total_import = sum(r["billed_import_wh"] for r in self.account_rows.values())
        total_deemed = sum(r["deemed_wh"] for r in self.account_rows.values())
        loss = 0
        self.feeder_losses = {}
        for f in FEEDERS:
            lp = c.loss_pct.get(f)
            if lp is None:
                self.feeder_losses[f] = 0
                continue
            l = rhe_int(Fraction(self.injection.get(f, 0)) * Fraction(lp) / 100)
            self.feeder_losses[f] = l
            loss += l
        ufe = total_injection + total_export - loss - total_import - total_deemed
        # allocation weights
        exempt = set()
        for acct, frm, to in c.ufe_exemptions:
            if frm <= "2025-11-30" and (not to or to > "2025-11-30"):
                exempt.add(acct)
        weights = {}
        W = 0
        for acct, r in self.account_rows.items():
            if acct in exempt:
                continue
            w = r["billed_import_wh"] + r["deemed_wh"]
            if w <= 0:
                continue
            weights[acct] = w
            W += w
        ufe_alloc = {}
        if ufe != 0 and W > 0:
            mag = abs(ufe)
            floor_sum = 0
            rems = []
            for acct in sorted(weights):
                w = weights[acct]
                fl = (mag * w) // W
                rem = (mag * w) % W
                ufe_alloc[acct] = int(fl)
                floor_sum += int(fl)
                rems.append((rem, acct))
            left = mag - floor_sum
            rems.sort(key=lambda x: (-x[0], x[1]))
            for i in range(min(left, len(rems))):
                ufe_alloc[rems[i][1]] += 1
            sign = -1 if ufe < 0 else 1
            for acct in ufe_alloc:
                ufe_alloc[acct] *= sign
        # ufe price
        total_energy_cents = sum(r["energy_cents"] for r in self.account_rows.values())
        total_rider_cents = sum(r["rider_cents"] for r in self.account_rows.values())
        denom = total_import + total_deemed
        if denom > 0:
            price = Fraction(total_energy_cents + total_rider_cents) * 1000 / denom
        else:
            price = Fraction(0)
        price = rhe(price, 6)
        for acct, r in self.account_rows.items():
            uw = ufe_alloc.get(acct, 0)
            r["ufe_wh"] = uw
            r["ufe_charge_cents"] = rhe_int(Fraction(uw) * Fraction(price) / 1000)
            r["total_cents"] = (r["energy_cents"] + r["rider_cents"] +
                                r["export_credit_cents"] + r["ufe_charge_cents"])
        self.ufe_wh = ufe
        self.ufe_price = price
        self.totals = {
            "injection": total_injection,
            "loss": loss,
            "billed_import": total_import,
            "billed_export": total_export,
            "deemed": total_deemed,
        }

    # -- meter summary ------------------------------------------------------
    def build_meter_rows(self):
        c = self.c
        rows = []
        for meter in sorted(self.meter_boundaries):
            bmap = self.meter_boundaries[meter]
            energy = self.meter_energy.get(meter, {})
            billing = self.meter_billing.get(meter, {})
            imp_wh = 0
            billed = 0
            exp_wh = 0
            for day in DAYS:
                wh = energy.get(day)
                if wh:
                    imp_wh += wh[0]
                pb = billing.get(day)
                if pb:
                    if pb["billed"]:
                        billed += pb["imp"]
                    exp_wh += pb["exp"]
            unbilled = imp_wh - billed
            corrected = estimated = missing = invalidated = 0
            resolved_any = False
            for D in bmap:
                bv = self.boundary_values.get((meter, D))
                state = self.boundary_state.get((meter, D))
                if state == "INVALIDATED":
                    invalidated += 1
                    resolved_any = True
                    continue
                if bv is None:
                    continue
                if bv["src"] == "CORRECTION":
                    corrected += 1
                    resolved_any = True
                elif bv["src"] == "ESTIMATE":
                    estimated += 1
                    resolved_any = True
                elif bv["src"] == "ACTUAL":
                    resolved_any = True
                elif bv["src"] == "MISSING":
                    if bv["imp"] is None:
                        missing += 1
            if not resolved_any:
                continue
            feeder = c.connectivity.get(meter, "")
            rows.append([
                meter, feeder, imp_wh, billed, unbilled, exp_wh,
                corrected, estimated, missing, invalidated,
            ])
        return rows

    def build_read_resolution_rows(self):
        c = self.c
        rows = []
        for meter in sorted(self.meter_boundaries):
            bmap = self.meter_boundaries[meter]
            for D in sorted(bmap):
                diso = D.isoformat()
                key = (meter, D)
                state = self.boundary_state.get(key)
                bv = self.boundary_values.get(key)
                if state == "INVALIDATED":
                    val = bv["imp"] if bv else None
                    rows.append([meter, diso, "INVALIDATED",
                                 _fmt3(val) if val is not None else ""])
                    continue
                if bv is None:
                    rows.append([meter, diso, "MISSING", ""])
                    continue
                if bv["src"] == "CORRECTION":
                    rows.append([meter, diso, "CORRECTION", _fmt3(bv["imp"])])
                elif bv["src"] == "ESTIMATE":
                    rows.append([meter, diso, "ESTIMATE", _fmt3(bv["imp"])])
                elif bv["src"] == "MISSING" and bv["imp"] is None:
                    rows.append([meter, diso, "MISSING", ""])
        rows.sort(key=lambda r: (r[0], r[1]))
        return rows


def _fmt3(v):
    if v is None:
        return ""
    return "{0:.3f}".format(v)


# ---------------------------------------------------------------- outputs


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    c = load_all(data_dir)
    load_head_end_profiles(c)
    c.aurora_profile = yaml.safe_load(open(os.path.join(data_dir, "aurora_hes_profile.yaml"), "rb"))
    c.aurora_units = (c.aurora_profile.get("units", {}) or {})
    s = Settlement(c)
    s.build_quarantine()
    s.build_boundaries()
    s.collect()
    s.resolve_boundaries()
    s.compute_energy()
    s.compute_billing()
    s.compute_injection()
    s.compute_charges()
    s.compute_ufe()

    # ---- account_settlement.csv
    header = ["account_id", "rate_code", "billed_import_wh", "billed_export_wh", "deemed_wh",
              "energy_cents", "rider_cents", "export_credit_cents", "ufe_wh", "ufe_charge_cents",
              "total_cents"]
    rows = []
    for acct in sorted(s.account_rows):
        r = s.account_rows[acct]
        rows.append([acct, r["rate_code"], r["billed_import_wh"], r["billed_export_wh"],
                     r["deemed_wh"], r["energy_cents"], r["rider_cents"],
                     r["export_credit_cents"], r["ufe_wh"], r["ufe_charge_cents"],
                     r["total_cents"]])
    write_csv(os.path.join(out_dir, "account_settlement.csv"), header, rows)

    # ---- meter_summary.csv
    header = ["meter_id", "feeder", "import_wh", "billed_import_wh", "unbilled_wh", "export_wh",
              "corrected_boundaries", "estimated_boundaries", "missing_boundaries",
              "invalidated_boundaries"]
    write_csv(os.path.join(out_dir, "meter_summary.csv"), header, s.build_meter_rows())

    # ---- read_resolution.csv
    header = ["meter_id", "boundary_date", "source", "import_kwh"]
    write_csv(os.path.join(out_dir, "read_resolution.csv"), header,
              s.build_read_resolution_rows())

    # ---- interval_injection.csv
    header = ["feeder", "interval_end_utc", "injection_wh", "source"]
    rows = []
    for (f, t) in sorted(s.interval_rows, key=lambda k: (k[0], k[1])):
        wh, src = s.interval_rows[(f, t)]
        rows.append([f, utc_str(t), wh, src])
    write_csv(os.path.join(out_dir, "interval_injection.csv"), header, rows)

    # ---- lighting_deemed.csv
    header = ["fixture_id", "account_id", "burn_days", "deemed_wh"]
    rows = []
    for fid in sorted(s.fixture_days):
        per_day = s.fixture_days[fid]
        total = 0
        days = 0
        for day in DAYS:
            wh = per_day.get(day, 0)
            if wh and wh > 0:
                total += wh
                days += 1
        if total > 0:
            rows.append([fid, s.fixture_acct.get(fid, ""), days, total])
    write_csv(os.path.join(out_dir, "lighting_deemed.csv"), header, rows)

    # ---- daytype_calendar.csv
    header = ["territory", "date", "daytype"]
    rows = []
    for terr in TERRITORIES:
        for day in DAYS:
            rows.append([terr, day.isoformat(), s.daytype_of(terr, day)])
    write_csv(os.path.join(out_dir, "daytype_calendar.csv"), header, rows)

    # ---- feeder_balance.json
    fb = {"feeders": {}}
    for f in FEEDERS:
        inj = s.injection.get(f, 0)
        loss = s.feeder_losses.get(f, 0)
        billed_imp = 0
        billed_exp = 0
        unbilled = 0
        deemed = 0
        for meter, billing in s.meter_billing.items():
            if c.connectivity.get(meter) != f:
                continue
            for day, pb in billing.items():
                if pb["billed"]:
                    billed_imp += pb["imp"]
                    billed_exp += pb["exp"]
                else:
                    unbilled += pb["imp"]
        for fid, per_day in s.fixture_days.items():
            if c.fixtures[fid]["feeder"] != f:
                continue
            for day, wh in per_day.items():
                if wh > 0:
                    deemed += wh
        fb["feeders"][f] = {
            "injection_wh": inj,
            "loss_wh": loss,
            "billed_import_wh": billed_imp,
            "billed_export_wh": billed_exp,
            "deemed_wh": deemed,
            "unbilled_wh": unbilled,
            "residual_wh": inj + billed_exp - loss - billed_imp - deemed,
        }
    write_json(os.path.join(out_dir, "feeder_balance.json"), fb)

    # ---- control_report.json
    batches = []
    for fn in sorted(s.control):
        info = s.control[fn]
        batch = info["batch"]
        man = info["manifest"]
        data_rows = info.get("data_rows", 0)
        if info["kind"] == "fjord_resend":
            # REV records are data records too
            data_rows = info.get("data_rows", 0) + len(s.fjord_reversals)
        status = batch["status"] if batch else ""
        rejected_rows = 0
        if batch:
            if batch["status"] == "REJECTED":
                rejected_rows = data_rows
            elif batch["rejected_from"] is not None:
                rejected_rows = batch["rejected_to"] - batch["rejected_from"] + 1
        withdrawn_rows = 0
        if man and man["withdrawn"]:
            m = re.match(r"^(\d+)-(\d+)$", str(man["withdrawn"]).strip())
            if m:
                withdrawn_rows = int(m.group(2)) - int(m.group(1)) + 1
        batches.append({
            "file": fn,
            "data_rows": data_rows,
            "manifest_rows": man["count"] if man else 0,
            "mdm_status": status,
            "rejected_rows": rejected_rows,
            "withdrawn_rows": withdrawn_rows,
        })
    write_json(os.path.join(out_dir, "control_report.json"), {"batches": batches})

    # ---- settlement_summary.json
    tot = s.totals
    summary = {
        "account_count": len(s.account_rows),
        "meter_count": len(s.build_meter_rows()),
        "injection_wh": tot["injection"],
        "loss_wh": tot["loss"],
        "billed_import_wh": tot["billed_import"],
        "billed_export_wh": tot["billed_export"],
        "deemed_wh": tot["deemed"],
        "unbilled_wh": 0,
        "ufe_wh": s.ufe_wh,
        "ufe_price_cents_per_kwh": "{0:.6f}".format(s.ufe_price),
        "energy_cents": sum(r["energy_cents"] for r in s.account_rows.values()),
        "rider_cents": sum(r["rider_cents"] for r in s.account_rows.values()),
        "export_credit_cents": sum(r["export_credit_cents"] for r in s.account_rows.values()),
        "ufe_charge_cents": sum(r["ufe_charge_cents"] for r in s.account_rows.values()),
        "total_cents": sum(r["total_cents"] for r in s.account_rows.values()),
    }
    unbilled = 0
    for meter, billing in s.meter_billing.items():
        for day, pb in billing.items():
            if not pb["billed"]:
                unbilled += pb["imp"]
    summary["unbilled_wh"] = unbilled
    write_json(os.path.join(out_dir, "settlement_summary.json"), summary)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("usage: transform.py <DATA_DIR> <OUT_DIR>\n")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])