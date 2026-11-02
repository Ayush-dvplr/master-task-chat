#!/usr/bin/env python3
"""KVEC November 2025 settlement pipeline.

Usage: python3 transform.py [DATA_DIR] [OUT_DIR] [--tolerant]

Reads every source under DATA_DIR, applies the settlement data contract and the
procedures manual, and writes the nine deliverables into OUT_DIR.  With
--tolerant a missing source file is treated as empty instead of failing.
"""
import csv
import io
import json
import mailbox
import re
import sqlite3
import sys
import tomllib
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from configparser import ConfigParser
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from email.header import decode_header, make_header
from pathlib import Path

TOLERANT = False
DATA = Path("/app/data")
NOV1 = date(2025, 11, 1)
DEC1 = date(2025, 12, 1)
NOV30 = date(2025, 11, 30)
SETTLE_DAYS = [NOV1 + timedelta(days=i) for i in range(30)]
BDATES = [NOV1 + timedelta(days=i) for i in range(31)]
FEEDER_IDS = [f"F{i:02d}" for i in range(1, 13)]
TERRS = ["TE", "TN", "TS", "TW"]
RIDER_IDS = ["R-FUEL", "R-ENV", "R-TRANS", "R-DSM", "R-NUC", "R-LIEAP"]
D3 = Decimal("0.001")
D5 = Decimal("0.00001")


class Missing(Exception):
    pass


def path(name):
    p = DATA / name
    if not p.is_file():
        if TOLERANT:
            raise Missing(name)
        raise SystemExit(f"required source missing: {name}")
    return p


def guarded(fn, default):
    try:
        return fn()
    except Missing:
        return default


# ------------------------------------------------------------------ time
def nth_sunday(year, month, n):
    d = date(year, month, 1)
    while d.weekday() != 6:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def dst_window(year):
    start = datetime(year, *nth_sunday(year, 3, 2).timetuple()[1:3], 8, 0, tzinfo=timezone.utc)
    end = datetime(year, *nth_sunday(year, 11, 1).timetuple()[1:3], 7, 0, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def offset_at(ts):
    year = datetime.fromtimestamp(ts, tz=timezone.utc).year
    a, b = dst_window(year)
    return -18000 if a <= ts < b else -21600


def to_utc(naive, fold=0):
    """Local America/Chicago wall time -> epoch seconds."""
    base = int(naive.replace(tzinfo=timezone.utc).timestamp())
    cands = [base + 18000, base + 21600]
    valid = [c for c in cands if c - (base) == -offset_at(c)]
    if not valid:
        return base + 21600
    if len(valid) == 2:
        return valid[1] if fold else valid[0]
    return valid[0]


def to_local(ts):
    return datetime.fromtimestamp(ts + offset_at(ts), tz=timezone.utc).replace(tzinfo=None)


def local_date(ts):
    return to_local(ts).date()


def day_start(d):
    return to_utc(datetime(d.year, d.month, d.day))


def parse_iso(s):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        return to_utc(dt)
    return int(dt.timestamp())


def parse_date(s):
    s = str(s).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return date.fromisoformat(s)
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        return datetime.strptime(s, "%m/%d/%Y").date()
    if re.fullmatch(r"\d{8}", s):
        return datetime.strptime(s, "%Y%m%d").date()
    if re.fullmatch(r"\d{1,2}-[A-Za-z]{3}-\d{4}", s):
        return datetime.strptime(s, "%d-%b-%Y").date()
    raise ValueError(f"unrecognised date {s!r}")


def xl_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(v))
    return parse_date(v)


# ------------------------------------------------------------------ ids
CYR = str.maketrans({"\u041a": "K", "\u0410": "A", "\u0421": "C", "\u043a": "k", "\u0430": "a", "\u0441": "c"})


def clean(s):
    s = unicodedata.normalize("NFKC", str(s)).translate(CYR)
    return re.sub(r"\s+", "", s).upper()


def canon(s, prefix, width):
    s = clean(s)
    m = re.fullmatch(prefix + r"(\d+)", s)
    if not m:
        return s
    return prefix + m.group(1).zfill(width)


def meter_id(s):
    return canon(s, "KV", 7)


def acct_id(s):
    return canon(s, "AC", 8)


def fixture_id(s):
    return canon(s, "FX", 6)


def feeder_id(s):
    s = clean(s).replace("FDR-", "F").replace("FDR", "F")
    m = re.fullmatch(r"F-?(\d+)", s)
    return f"F{int(m.group(1)):02d}" if m else s


def spid(s):
    return clean(s).replace("-", "")


def eui(s):
    return clean(s).replace(":", "")


def legacy(s):
    s = clean(s)
    m = re.fullmatch(r"L-?(\d+)", s)
    return f"L-{m.group(1)}" if m else s


def num(s):
    """Decimal from a printed number: thousands commas removed, decimal comma accepted."""
    s = str(s).strip().replace(" W", "")
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    return Decimal(s)


def q(v, places):
    return Decimal(v).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


def rhe(v):
    return int(Decimal(v).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


# ------------------------------------------------------------------ readers
def ntext(p, encoding="utf-8"):
    """File text with LF, CRLF and bare-CR record terminators normalised to LF."""
    return p.read_bytes().decode(encoding).replace("\r\n", "\n").replace("\r", "\n")


def read_lines_mixed(p):
    out = []
    for raw in p.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n"):
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("cp1252"))
    if out and out[-1] == "":
        out.pop()
    if out and out[0].startswith("\ufeff"):
        out[0] = out[0][1:]
    return out


def csv_rows(p):
    text = "\n".join(read_lines_mixed(p))
    return list(csv.reader(io.StringIO(text)))


def csv_dicts(p):
    rows = [r for r in csv_rows(p) if r and not r[0].startswith("#")]
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:]]


def docx_tables(p):
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(p) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", ns)
    items = []
    for el in body:
        tag = el.tag.split("}")[1]
        if tag == "p":
            items.append(("p", "".join(t.text or "" for t in el.iter(f"{{{ns['w']}}}t"))))
        elif tag == "tbl":
            rows = []
            for tr in el.findall("w:tr", ns):
                rows.append(["".join(t.text or "" for t in tc.iter(f"{{{ns['w']}}}t")) for tc in tr.findall("w:tc", ns)])
            items.append(("t", rows))
    return items


def pdf_lines(p):
    from pypdf import PdfReader
    out = []
    for page in PdfReader(str(p)).pages:
        out.extend(page.extract_text().split("\n"))
    return out


def pipe_table(lines, required):
    """Rows of ' | '-separated text tables; header lines (containing all required columns) reset the order."""
    head = None
    out = []
    for ln in lines:
        if " | " not in ln and "|" not in ln:
            continue
        cells = [c.strip() for c in ln.split("|")]
        up = [c.upper() for c in cells]
        if all(x in up for x in required):
            head = up
            continue
        if head and len(cells) == len(head):
            out.append(dict(zip(head, cells)))
    return out


def md_tables(p, required):
    head = None
    out = []
    for ln in ntext(p).split("\n"):
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if set(cells) <= {"---", ""}:
            continue
        if all(x in cells for x in required):
            head = cells
            continue
        if head and len(cells) == len(head):
            out.append(dict(zip(head, cells)))
    return out


def html_tables(p):
    text = ntext(p)
    tables = []
    for t in re.findall(r"<table>(.*?)</table>", text, re.S):
        head = re.findall(r"<th>(.*?)</th>", t)
        rows = []
        for tr in re.findall(r"<tr>(.*?)</tr>", t, re.S):
            cells = re.findall(r"<td>(.*?)</td>", tr)
            if cells:
                rows.append(dict(zip(head, [unescape(c) for c in cells])))
        tables.append((head, rows))
    return tables


def unescape(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")


def xlsx_sheets(p):
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        out[ws.title] = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return out


def sheet_dicts(rows, first_col):
    for i, r in enumerate(rows):
        if r and r[0] == first_col or (r and first_col in r):
            head = [str(c) if c is not None else "" for c in r]
            return [dict(zip(head, x)) for x in rows[i + 1:] if any(c is not None for c in x)]
    return []


def ini(p, text=None):
    cp = ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    cp.read_string(text if text is not None else ntext(p))
    return cp


def yaml_load(p):
    import yaml
    return yaml.safe_load(ntext(p))


# ------------------------------------------------------------------ settlement
class Ctx:
    pass


def load_reference(C):
    # connectivity (contract appendix T)
    C.conn = {}
    try:
        text = ntext(path("settlement_data_contract.md"), "utf-8")
    except Missing:
        text = "## Appendix T\n"
    appendix = text.split("## Appendix T", 1)[1]
    head = None
    for ln in appendix.split("\n"):
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells[0] in ("meter_id", "feeder") and cells[1] in ("meter_id", "feeder"):
            head = cells
            continue
        if set(cells) <= {"---"}:
            continue
        row = dict(zip(head, cells))
        C.conn[meter_id(row["meter_id"])] = feeder_id(row["feeder"])
    # manual
    C.territory = {}
    C.loss_pct = {}
    C.schedule = {}
    items = guarded(lambda: docx_tables(path("kvec_settlement_procedures_manual.docx")), [])
    for kind, val in items:
        if kind != "t":
            continue
        head = val[0]
        if head == ["feeder", "substation", "territory", "loss_pct"]:
            for r in val[1:]:
                C.territory[r[0]] = r[2]
                C.loss_pct[r[0]] = Decimal(r[3])
        elif set(head) == {"meter_id", "read_time", "effective_from"}:
            for r in val[1:]:
                row = dict(zip(head, r))
                C.schedule.setdefault(meter_id(row["meter_id"]), []).append((parse_date(row["effective_from"]), 0, row["read_time"]))
    # CAB decisions and draft errata
    C.mail = load_mail()
    approved = {cr for cr, dec in C.mail["cab"].items() if dec == "APPROVED"}

    def draft():
        for kind, val in docx_tables(path("settlement_procedures_manual_rev4_draft.docx")):
            if kind == "t" and val[0][:2] == ["erratum", "table"]:
                for r in val[1:]:
                    row = dict(zip(val[0], r))
                    if row["cr"] not in approved:
                        continue
                    if row["table"] == "R":
                        C.schedule.setdefault(meter_id(row["key"]), []).append((parse_date(row["effective_from"]), 1, row["value"]))
                    elif row["table"] == "L":
                        C.loss_pct[feeder_id(row["key"])] = Decimal(row["value"])
    guarded(draft, None)
    for m in C.schedule:
        C.schedule[m].sort()


def load_mail():
    holds = []
    cab = {}
    try:
        p = path("mdm_ops_mailbox_2025-11.mbox")
    except Missing:
        return {"holds": holds, "cab": cab}
    for msg in mailbox.mbox(str(p)):
        subj = str(make_header(decode_header(msg["Subject"] or "")))
        sent = int(datetime.strptime(msg["Date"].strip(), "%a, %d %b %Y %H:%M:%S %z").timestamp())
        if msg.is_multipart():
            body = ""
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8")
                    break
        else:
            body = msg.get_payload(decode=True).decode("utf-8")
        m = re.match(r"MDM notice: Read (hold|release)\s+(.+?)\s+(\d{4}-\d{2}-\d{2})\s*$", subj)
        if m:
            holds.append({"type": m.group(1).upper(), "meter": meter_id(m.group(2)), "date": date.fromisoformat(m.group(3)), "t": sent})
            continue
        m = re.match(r"CAB decision (CR-\d+): (APPROVED|REJECTED)", subj)
        if m:
            cab[m.group(1)] = m.group(2)
    return {"holds": holds, "cab": cab}


def read_time(C, m, bdate):
    cur = "00:00"
    for frm, _p, val in C.schedule.get(m, []):
        if frm <= bdate:
            cur = val
    return cur


def boundary_instant(C, m, bdate):
    if read_time(C, m, bdate) == "23:00":
        return to_utc(datetime(bdate.year, bdate.month, bdate.day) - timedelta(hours=1))
    return day_start(bdate)


def load_registry(C):
    C.reg = {}
    for dist in ("north", "east", "southwest"):
        def one(dist=dist):
            con = sqlite3.connect(str(path(f"mdm_registry_{dist}.db")))
            for m, a, mult, hes, frm, to, _r in con.execute("SELECT * FROM meter_attr_history"):
                C.reg.setdefault(meter_id(m), []).append({"acct": acct_id(a), "mult": int(mult), "hes": hes.strip(),
                                                         "from": parse_date(frm), "to": parse_date(to) if to else None})
            con.close()
        guarded(one, None)
    C.orders = []

    def orders():
        for ln in ntext(path("field_service_orders.jsonl"), "utf-8").split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            o = json.loads(ln)
            o["t"] = parse_iso(o.get("completed_at") or o.get("ts"))
            C.orders.append(o)
    guarded(orders, None)
    C.exchanges = [o for o in C.orders if o["type"] == "EXCHANGE" and o["status"] == "COMPLETED"]
    C.ct_changes = [o for o in C.orders if o["type"] == "CT_CHANGE" and o["status"] == "COMPLETED"]
    C.removed_at = {meter_id(o["old_meter"]): o["t"] for o in C.exchanges}
    C.installed_at = {meter_id(o["new_meter"]): o["t"] for o in C.exchanges}
    C.ct_verif = []

    def ctv():
        for name, rows in xlsx_sheets(path("ct_ratio_verification_2025.xlsx")).items():
            for row in sheet_dicts(rows, "verification_id"):
                if row["result"] == "FAIL" and row["action"] == "CORRECT_RATIO":
                    C.ct_verif.append((meter_id(row["meter_id"]), xl_date(row["verified_on"]), int(str(row["measured_ratio"]).split(":")[0])))
    guarded(ctv, None)
    C.mult_events = {}
    for m, rows in C.reg.items():
        for row in rows:
            C.mult_events.setdefault(m, []).append((day_start(row["from"]), 0, row["mult"]))
    for o in C.ct_changes:
        C.mult_events.setdefault(meter_id(o["meter"]), []).append((o["t"], 2, int(o["new_ratio"].split(":")[0])))
    for m, d, ratio in C.ct_verif:
        C.mult_events.setdefault(m, []).append((day_start(d), 1, ratio))
    for m in C.mult_events:
        C.mult_events[m].sort()
    C.offsets = {}

    def clock():
        doc = tomllib.loads(ntext(path("meter_clock_offsets.toml"), "utf-8"))
        for x in doc.get("offset", []):
            C.offsets[meter_id(x.get("meter_id") or x.get("meter"))] = int(x.get("offset_s", x.get("ahead_s", 0)))
    guarded(clock, None)
    C.digits = {}

    def roll():
        doc = tomllib.loads(ntext(path("register_rollover.toml"), "utf-8"))
        for x in doc.get("register", []):
            C.digits[meter_id(x.get("meter_id") or x.get("meter"))] = int(x.get("digits", x.get("dial_digits")))
    guarded(roll, None)
    C.events = []

    def coll():
        for ln in ntext(path("collector_events_2025-11.log"), "utf-8").split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.split()
            ts = parse_iso(parts[0])
            kind = parts[2]
            kv = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
            C.events.append({"t": ts, "type": kind, **kv})
    guarded(coll, None)
    C.sync = {}
    C.resets = {}
    for e in C.events:
        if e["type"] == "CLOCK_SYNC":
            C.sync[meter_id(e["meter"])] = e["t"]
        elif e["type"] == "REGISTER_RESET":
            C.resets[meter_id(e["meter"])] = (e["t"], num(e["pre_reset_kwh"]), num(e["post_reset_kwh"]))


def mult_at(C, m, t):
    cur = 1
    for tt, _p, val in C.mult_events.get(m, []):
        if tt <= t:
            cur = val
    return cur


def corrected(C, m, t):
    off = C.offsets.get(m, 0)
    s = C.sync.get(m)
    return t - off if (s is None or t - off < s) else t


def history_value(hist, d, default):
    cur = default
    for frm, val in hist:
        if frm <= d:
            cur = val
    return cur


def load_read_files(C):
    """Returns list of candidate dicts: meter, t (reported), imp, exp, seq, file, ordinal, hes."""
    reads = []
    C.data_rows = {}
    # Aurora
    fw = {}

    def aprof():
        doc = yaml_load(path("aurora_hes_profile.yaml"))
        for x in doc["firmware_history"]:
            fw.setdefault(meter_id(x.get("meter_id") or x.get("meter")), []).append(
                (parse_date(x.get("effective_from") or x.get("since")), x["firmware"]))
        for v in fw.values():
            v.sort()
    guarded(aprof, None)
    for k in range(1, 7):
        fn = f"aurora_reads_2025-11_p{k}.csv"

        def one(fn=fn):
            rows = csv_rows(path(fn))
            head = None
            n = 0
            for r in rows:
                if not r or r[0].startswith("#"):
                    continue
                if "meter_id" in r and "register_import" in r:
                    head = r
                    continue
                n += 1
                row = dict(zip(head, r))
                m = meter_id(row["meter_id"])
                ts_s = row["read_local"].strip()
                for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S"):
                    try:
                        naive = datetime.strptime(ts_s, f)
                        break
                    except ValueError:
                        continue
                t = to_utc(naive)
                firmware = history_value(fw.get(m, []), naive.date(), "AU-3.1")
                wh = firmware.startswith("AU-2")

                def val(s):
                    s = s.strip()
                    if s in ("", "-1"):
                        return None
                    v = num(s)
                    return v / 1000 if wh else v
                reads.append({"meter": m, "t": t, "imp": val(row["register_import"]), "exp": val(row["register_export"]),
                              "seq": int(row["seq"]), "file": fn, "ord": n, "hes": "AUR"})
            C.data_rows[fn] = n
        guarded(one, None)
    # Borealis
    chmap = {}

    def bmap():
        doc = tomllib.loads(ntext(path("borealis_channel_map.toml"), "utf-8"))
        for x in doc["channel_map"]:
            if "channels" in x:
                imp, exp = x["channels"]["import"], x["channels"]["export"]
            else:
                imp, exp = x["import_channel"], x["export_channel"]
            chmap.setdefault(meter_id(x["meter_id"]), []).append((parse_date(x["effective_from"]), (imp, exp)))
        for v in chmap.values():
            v.sort()
    guarded(bmap, None)
    for k in range(1, 7):
        fn = f"borealis_reads_2025-11_p{k}.xml"

        def one(fn=fn):
            root = ET.fromstring(path(fn).read_bytes())
            n = 0
            for el in root.iter():
                tag = el.tag
                if tag not in ("Read", "Rd"):
                    continue
                n += 1
                m = meter_id(el.get("meter") or el.get("m"))
                t = parse_iso(el.get("ts") or el.get("t"))
                seq = int(el.get("seq") or el.get("sq"))
                ich, ech = history_value(chmap.get(m, []), local_date(t), (1, 2))
                vals = {}
                for ch in el.findall("Ch"):
                    if ch.get("q") == "MISSING" or ch.text is None:
                        continue
                    v = num(ch.text)
                    if ch.get("unit") == "Wh":
                        v = v / 1000
                    vals[int(ch.get("n"))] = v
                reads.append({"meter": m, "t": t, "imp": vals.get(ich), "exp": vals.get(ech), "seq": seq, "file": fn, "ord": n, "hes": "BOR"})
            C.data_rows[fn] = n
        guarded(one, None)
    # Cirrus
    cfw = {}

    def cprof():
        doc = yaml_load(path("cirrus_hes_profile.yaml"))
        for x in doc["firmware_history"]:
            cfw.setdefault(eui(x["device"]), []).append((parse_date(x.get("effective_from") or x.get("since")), x["firmware"]))
        for v in cfw.values():
            v.sort()
    guarded(cprof, None)
    link = {}

    def usage():
        for ln in ntext(path("cirrus_daily_usage_2025-11.jsonl"), "utf-8").split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            o = json.loads(ln)
            if "_comment" in o:
                continue
            st = o.get("status") or o.get("state")
            if st == "VOID":
                continue
            link[(eui(o.get("device") or o.get("device_eui")), int(o.get("period") or o.get("period_no")))] = meter_id(o.get("meter_id") or o.get("meter"))
    guarded(usage, None)
    for k in range(1, 7):
        fn = f"cirrus_reads_2025-11_p{k}.jsonl"

        def one(fn=fn, k=k):
            n = 0
            keys = ("dev", "ts", "imp", "exp", "seq")
            for ln in ntext(path(fn), "utf-8").split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                o = json.loads(ln, parse_float=Decimal)
                if "_schema" in o:
                    keys = ("device", "t", "import", "export", "sequence") if int(o["_schema"]) == 2 else ("dev", "ts", "imp", "exp", "seq")
                    continue
                n += 1
                dev = eui(o[keys[0]])
                t = int(o[keys[1]])
                firmware = history_value(cfw.get(dev, []), local_date(t), "CX-3.9.2")

                def val(v):
                    if v is None or v == "ERR":
                        return None
                    if isinstance(v, str):
                        v = v.strip()
                        if firmware.startswith("CX-4.1"):
                            v = v.replace(",", ".")
                        if TOLERANT and "," in v:
                            return None
                        return Decimal(v)
                    return Decimal(str(v))
                m = link.get((dev, k))
                if m is None:
                    continue
                reads.append({"meter": m, "t": t, "imp": val(o[keys[2]]), "exp": val(o[keys[3]]), "seq": int(o[keys[4]]),
                              "file": fn, "ord": n, "hes": "CIR"})
            C.data_rows[fn] = n
        guarded(one, None)
    # Delta
    xref = []

    def dw():
        con = sqlite3.connect(str(path("dw_registry_snapshot_2025-12-03.db")))
        for s, m, fr, to, st in con.execute("SELECT * FROM sp_meter_xref"):
            if st == "VOID":
                continue
            xref.append((spid(s), meter_id(m), parse_iso(fr), parse_iso(to) if to else None))
        con.close()
    guarded(dw, None)
    xr = {}
    for s, m, fr, to in xref:
        xr.setdefault(s, []).append((fr, to, m))
    scaling = {}

    def sc():
        cp = ini(path("register_scaling.ini"))
        for sec in cp.sections():
            name = sec.split(" ", 1)[1] if sec.startswith("meter ") else sec
            v = cp[sec].get("decimals") or cp[sec].get("resolution")
            scaling[meter_id(name)] = int(v)
    guarded(sc, None)
    policy = {}

    def dp():
        cp = ini(path("delta_ingest.ini"))
        for sec in cp.sections():
            if sec.startswith("spid:") or sec.startswith("spid "):
                policy[spid(sec[5:])] = (cp[sec].get("est_policy") or cp[sec].get("policy")).strip()
    guarded(dp, None)
    C.delta_policy = policy
    for k in range(1, 7):
        fn = f"delta_reads_2025-11_p{k}.parquet"

        def one(fn=fn):
            import pyarrow.parquet as pq
            tab = pq.read_table(str(path(fn))).to_pydict()
            n = len(tab["spid"])
            for i in range(n):
                s = spid(tab["spid"][i])
                secs = round(tab["read_serial"][i] * 86400)
                naive = datetime(1899, 12, 30) + timedelta(seconds=secs)
                t = to_utc(naive)
                m = None
                for fr, to, mm in xr.get(s, []):
                    if fr <= t and (to is None or t < to):
                        m = mm
                if m is None:
                    continue
                if tab["est_flag"][i] == 1 and policy.get(s) != "ACCEPT":
                    continue
                dec = scaling.get(m, 3)
                raw = tab["import_raw"][i]
                rexp = tab["export_raw"][i]
                reads.append({"meter": m, "t": t, "imp": None if raw == -1 else Decimal(raw).scaleb(-dec),
                              "exp": None if rexp is None else Decimal(rexp).scaleb(-dec), "seq": tab["load_id"][i],
                              "file": fn, "ord": i + 1, "hes": "DLT"})
            C.data_rows[fn] = n
        guarded(one, None)
    # CIS legacy
    xw = {}

    def mig():
        sheets = xlsx_sheets(path("meter_registry_migration_wave3.xlsx"))
        for row in sheet_dicts(sheets["Crosswalk"], "legacy_id"):
            if row["link_status"] == "ACTIVE":
                xw[legacy(row["legacy_id"])] = meter_id(row["meter_id"])
    guarded(mig, None)
    dial = {}

    def cini():
        cp = ini(path("cis_legacy_layout.ini"))
        for sec in cp.sections():
            if sec.startswith("legacy:") or sec.startswith("legacy "):
                dial[legacy(sec[7:])] = int(cp[sec].get("dial_constant") or cp[sec].get("kh"))
    guarded(cini, None)
    for k in "abc":
        fn = f"cis_legacy_reads_2025-11_{k}.txt"

        def one(fn=fn):
            layout = 1
            n = 0
            for ln in ntext(path(fn), "ascii").split("\n"):
                ln = ln.rstrip("\r")
                if not ln:
                    continue
                if ln[0] == "L":
                    layout = int(ln[1])
                    continue
                if ln[0] != "D":
                    continue
                n += 1
                if layout == 1:
                    lid, ds, tm, imp, exp, seq = ln[1:10], ln[10:17], ln[17:21], ln[21:31], ln[31:41], ln[41:51]
                else:
                    ds, tm, seq, lid, imp, exp = ln[1:8], ln[8:12], ln[12:22], ln[22:31], ln[31:42], ln[42:53]
                lid = legacy(lid)
                d = date(int(ds[:4]), 1, 1) + timedelta(days=int(ds[4:]) - 1)
                naive = datetime(d.year, d.month, d.day) + timedelta(hours=int(tm[:2]), minutes=int(tm[2:]))
                t = to_utc(naive)
                m = xw.get(lid)
                if m is None:
                    continue
                dc = dial.get(lid, 1)

                def val(s):
                    if s.strip() == "" :
                        return None
                    if set(s.strip()) == {"9"} and len(s.strip()) == len(s):
                        return None
                    return Decimal(int(s.replace(" ", "0"))) / 1000 * dc
                reads.append({"meter": m, "t": t, "imp": val(imp), "exp": val(exp), "seq": int(seq), "file": fn, "ord": n, "hes": "CIS"})
            C.data_rows[fn] = n
        guarded(one, None)
    # Fjord
    flags = {}

    def fprof():
        for name, window in (("fjord_hes_profile.yaml", None), ("fjord_hes_profile_2026.yaml", NOV30)):
            def ld(name=name, window=window):
                doc = yaml_load(path(name))
                for x in doc.get("multiplier_applied_entries") or []:
                    d = parse_date(x.get("effective_from") or x.get("since"))
                    if window is not None and d > window:
                        continue
                    flags.setdefault(meter_id(x["meter_id"]), []).append((d, 1 if window else 0, bool(x["multiplier_applied"])))
            guarded(ld, None)
        for v in flags.values():
            v.sort()
    fprof()
    alias = {"SEQ": "seq", "METER_ID": "meter", "EPOCH_MS": "ts_ms", "IMP": "import_kwh", "EXP": "export_kwh", "FLG": "flags"}
    C.reversals = set()
    for k in [1, 2, 3, 4, 5, 6, "4b"]:
        fn = f"fjord_reads_2025-11_p{k}.tsv"

        def one(fn=fn):
            head = None
            n = 0
            for ln in ntext(path(fn), "utf-8").split("\n"):
                ln = ln.rstrip("\r")
                if not ln or ln.startswith("#"):
                    continue
                cells = ln.split("\t")
                if cells[0] in ("meter", "SEQ"):
                    head = [alias.get(c, c) for c in cells]
                    continue
                n += 1
                if cells[0] == "REV":
                    C.reversals.add((meter_id(cells[1]), date.fromisoformat(cells[3])))
                    continue
                if fn.endswith("p4b.tsv"):
                    continue
                row = dict(zip(head, cells))
                m = meter_id(row["meter"])
                t = int(row["ts_ms"]) // 1000
                applied = history_value([(d, f) for d, _p, f in flags.get(m, [])], local_date(t), False)
                div = mult_at(C, m, corrected(C, m, t)) if applied else 1

                def val(s):
                    s = (s or "").strip()
                    if s in ("", "9999999.999"):
                        return None
                    return num(s) / div
                reads.append({"meter": m, "t": t, "imp": val(row.get("import_kwh")), "exp": val(row.get("export_kwh")),
                              "seq": int(row["seq"]), "file": fn, "ord": n, "hes": "FJD"})
            C.data_rows[fn] = n
        guarded(one, None)
    return reads


def load_controls(C):
    C.voids = set()

    def v():
        for row in csv_dicts(path("mdm_void_register.csv")):
            if row["reinstated"].strip() == "N":
                C.voids.add((row["hes"].strip(), meter_id(row["meter_id"]), parse_date(row["read_date"])))
    guarded(v, None)
    C.corr = {}

    def c():
        for row in csv_dicts(path("mdm_read_corrections.csv")):
            if row["status"].strip() != "VALIDATED":
                continue
            k = (meter_id(row["meter_id"]), parse_date(row["read_date"]))
            rev = int(row["revision"])
            if k not in C.corr or rev > C.corr[k][0]:
                exp = row["corrected_export_kwh"].strip()
                C.corr[k] = (rev, q(num(row["corrected_import_kwh"]), 3), q(num(exp), 3) if exp else None)
    guarded(c, None)
    reviews = {}

    def rv():
        for name, rows in xlsx_sheets(path("vee_estimate_review_2025.xlsx")).items():
            for row in sheet_dicts(rows, "estimate_id"):
                reviews.setdefault(clean(row["estimate_id"]), []).append((xl_date(row["reviewed_on"]), row["review_status"]))
    guarded(rv, None)
    latest = {}
    for k, lst in reviews.items():
        lst.sort(key=lambda z: z[0])
        latest[k] = lst[-1][1]
    C.vee = {}

    def ve():
        lines = ntext(path("mdm_vee_estimates.tsv"), "utf-8").split("\n")
        head = lines[0].split("\t")
        for ln in lines[1:]:
            ln = ln.rstrip("\r")
            if not ln:
                continue
            row = dict(zip(head, ln.split("\t")))
            if latest.get(clean(row["estimate_id"])) != "APPROVED":
                continue
            k = (meter_id(row["meter_id"]), parse_date(row["read_date"]))
            ver = int(row["version"])
            if k not in C.vee or ver > C.vee[k][0]:
                exp = row["est_export_kwh"].strip()
                C.vee[k] = (ver, q(num(row["est_import_kwh"]), 3), q(num(exp), 3) if exp else None)
    guarded(ve, None)
    C.batch = {}

    def bl():
        for ln in ntext(path("mdm_batch_control.log"), "utf-8").split("\n"):
            if " BATCH " not in ln or "file=" not in ln:
                continue
            kv = dict(re.findall(r"(\w+)=\s*(\S+)", ln))
            C.batch[kv["file"]] = kv
    guarded(bl, None)
    C.manifest = {}

    def mf():
        doc = json.loads(ntext(path("hes_batch_manifest_2025-11.json"), "utf-8"))
        for b in doc["records"]:
            if b["kind"] != "batch" or b.get("superseded"):
                continue
            C.manifest[b["file"]] = b
    guarded(mf, None)
    C.holds = {}
    for h in sorted(C.mail["holds"], key=lambda h: h["t"]):
        k = (h["meter"], h["date"])
        if h["type"] == "HOLD":
            C.holds[k] = "HELD"
        elif h["t"] <= to_utc(datetime(2025, 12, 3, 17, 0)) and C.holds.get(k) == "HELD":
            C.holds[k] = "RELEASED"
    C.quar = {}

    def dbg():
        for ln in ntext(path("hes_ingest_debug.log"), "utf-8").split("\n"):
            m = re.search(r"\b(QUARANTINE|UNQUARANTINE) meter=(\S+) read_date=(\S+) hes=(\S+)", ln)
            if m:
                C.quar[(meter_id(m.group(2)), date.fromisoformat(m.group(3)), m.group(4))] = m.group(1)
    guarded(dbg, None)
    C.issues = {}

    def ki():
        for row in md_tables(path("hes_known_issues.md"), ["issue", "code", "hes", "meter_id", "read_date", "status"]):
            if row["status"] == "OPEN":
                C.issues[(meter_id(row["meter_id"]), parse_date(row["read_date"]), row["hes"])] = row["code"]
    guarded(ki, None)
    C.disputes = {}

    def dsp():
        for head, rows in html_tables(path("customer_portal_usage_export.html")):
            if "decision" not in head:
                continue
            for row in sorted(rows, key=lambda r: date.fromisoformat(r["decided"])):
                C.disputes[(meter_id(row["meter_id"]), parse_date(row["read_date"]))] = row["decision"]
    guarded(dsp, None)
    C.opening = {}

    def op():
        for row in csv_dicts(path("mdm_october_close_reads.csv")):
            exp = row["register_export_kwh"].strip()
            C.opening[meter_id(row["meter_id"])] = (q(num(row["register_import_kwh"]), 3), q(num(exp), 3) if exp else None)
    guarded(op, None)


def resolve_boundaries(C, reads):
    meters = set(C.reg) | set(C.conn)
    service = {}
    for m in meters:
        if m in C.installed_at:
            d = local_date(C.installed_at[m])
            service[m] = [b for b in range(31) if BDATES[b] > d]
        elif m in C.removed_at:
            d = local_date(C.removed_at[m])
            service[m] = [b for b in range(31) if BDATES[b] <= d]
        else:
            service[m] = list(range(31))
    C.service = service
    inst = {m: {b: boundary_instant(C, m, BDATES[b]) for b in service[m]} for m in meters if m in C.reg}
    cutoff = to_utc(datetime(2025, 12, 3, 17, 0))
    best = {}
    for x in reads:
        m = x["meter"]
        if m not in inst or x["imp"] is None:
            continue
        b_ = C.batch.get(x["file"], {})
        if b_.get("status") == "REJECTED":
            continue
        if b_.get("status") == "PARTIAL":
            a, z = map(int, b_["rejected_rows"].split("-"))
            if a <= x["ord"] <= z:
                continue
        mf = C.manifest.get(x["file"])
        if mf and mf.get("withdrawn_rows"):
            a, z = map(int, mf["withdrawn_rows"].split("-"))
            if a <= x["ord"] <= z:
                continue
        t = corrected(C, m, x["t"])
        if m in C.installed_at and t < C.installed_at[m]:
            continue
        if m in C.removed_at and t >= C.removed_at[m]:
            continue
        hit = None
        for b, bi in inst[m].items():
            if b > 0 and abs(t - bi) <= 900:
                hit = b
                break
        if hit is None:
            continue
        bd = BDATES[hit]
        if (x["hes"], m, bd) in C.voids or C.disputes.get((m, bd)) == "UPHELD":
            continue
        if x["file"] == "fjord_reads_2025-11_p4.tsv" and (m, bd) in C.reversals:
            continue
        if C.holds.get((m, bd)) == "HELD":
            continue
        if C.quar.get((m, bd, x["hes"])) == "QUARANTINE":
            continue
        imp, exp = q(x["imp"], 3), (q(x["exp"], 3) if x["exp"] is not None else None)
        code = C.issues.get((m, bd, x["hes"]))
        if code == "STUCK_REGISTER":
            continue
        if code == "WH_AS_KWH":
            imp = imp / 1000
            exp = exp / 1000 if exp is not None else None
        elif code == "SWAP_REGISTERS":
            imp, exp = exp, imp
        key = (abs(t - inst[m][hit]), -x["seq"])
        if (m, hit) not in best or key < best[(m, hit)][0]:
            best[(m, hit)] = (key, imp, exp)
    val = {}
    src = {}
    for m in inst:
        for b in service[m]:
            bd = BDATES[b]
            if (m, bd) in C.corr:
                _r, i_, e_ = C.corr[(m, bd)]
                val[(m, b)] = (i_, e_)
                src[(m, b)] = "CORRECTION"
            elif b == 0 and m in C.opening:
                val[(m, b)] = C.opening[m]
                src[(m, b)] = "ACTUAL"
            elif (m, b) in best:
                val[(m, b)] = best[(m, b)][1:]
                src[(m, b)] = "ACTUAL"
            elif b > 0 and (m, bd) in C.vee:
                _v, i_, e_ = C.vee[(m, bd)]
                val[(m, b)] = (i_, e_)
                src[(m, b)] = "ESTIMATE"
    C.bval = val
    C.bsrc = src
    C.inst = inst


def energy(C):
    C.imp = {}
    C.exp = {}
    C.invalid = {}
    for m in sorted(C.inst):
        mod = Decimal(10) ** C.digits.get(m, 6)
        anchors = []
        for b in C.service[m]:
            v = C.bval.get((m, b))
            anchors.append((C.inst[m][b], 1, "B", b, v[0] if v else None, v[1] if v else None, None))
        for o in C.exchanges:
            if meter_id(o["old_meter"]) == m:
                anchors.append((o["t"], 1, "X", None, num(o["old_final_import_kwh"]),
                                num(o["old_final_export_kwh"]) if o.get("old_final_export_kwh") else None, None))
            if meter_id(o["new_meter"]) == m:
                anchors.append((o["t"], 0, "X", None, num(o["new_initial_import_kwh"]),
                                num(o["new_initial_export_kwh"]) if o.get("new_initial_export_kwh") else None, None))
        for o in C.ct_changes:
            if meter_id(o["meter"]) == m:
                anchors.append((o["t"], 1, "C", None, num(o["register_at_change_kwh"]), None, None))
        if m in C.resets:
            t, pre, post = C.resets[m]
            anchors.append((t, 1, "R", None, pre, None, post))
        anchors.sort(key=lambda a: (a[0], a[1]))
        for reg, store in ((4, C.imp), (5, C.exp)):
            prev = None
            for a in anchors:
                v = a[reg]
                if v is None:
                    continue
                if prev is None:
                    prev = a[6] if a[2] == "R" else v
                    continue
                d_ = v - prev
                nxt = a[6] if a[2] == "R" else v
                if a[2] != "R" and d_ < 0:
                    if prev >= mod * Decimal("0.9") and v < mod * Decimal("0.1"):
                        d_ += mod
                    elif a[2] == "B":
                        if reg == 4:
                            C.invalid[(m, a[3])] = v
                        continue
                end = a[0]
                day = local_date(end - 1)
                if NOV1 <= day < DEC1:
                    wh = int(d_ * 1000) * mult_at(C, m, end - 1)
                    store[(m, day)] = store.get((m, day), 0) + wh
                prev = nxt
    tests = {}

    def acc():
        for kind, val in docx_tables(path("meter_accuracy_test_results_2025.docx")):
            if kind == "t" and val[0][0] == "test_id":
                for r in val[1:]:
                    row = dict(zip(val[0], r))
                    d = parse_date(row["test_date"])
                    if row["result"] != "FAIL" or not (NOV1 <= d < DEC1):
                        continue
                    m = meter_id(row["meter_id"])
                    key = (d, row["test_id"])
                    if m not in tests or key > tests[m][0]:
                        tests[m] = (key, num(row["as_found_error_pct"]))
    guarded(acc, None)
    for m, ((td, _id), err) in tests.items():
        for d in SETTLE_DAYS:
            if d < td and (m, d) in C.imp:
                C.imp[(m, d)] = rhe(Decimal(C.imp[(m, d)]) * 100 / (100 + err))


def load_accounts(C):
    C.master = {}

    def ms():
        for row in csv_dicts(path("cis_account_master.csv")):
            fd = row["final_date"].strip()
            C.master[acct_id(row["account_id"])] = {"status": row["status"], "final": parse_date(fd) if fd else None,
                                                     "code": row["rate_code_snapshot"].strip()}
    guarded(ms, None)
    merges = []

    def mg():
        doc = json.loads(ntext(path("account_merges_2025.json"), "utf-8"))
        for x in doc["merges"]:
            st = x.get("status") or x.get("state")
            if st != "COMPLETED":
                continue
            merges.append((acct_id(x.get("predecessor") or x.get("from_account")), acct_id(x.get("successor") or x.get("to_account")),
                           parse_date(x.get("effective_date") or x.get("effective"))))
    guarded(mg, None)

    def late():
        for row in csv_dicts(path("cis_account_master_2025-12.csv")):
            if row["late_posted"].strip() == "Y" and row["merged_into"].strip():
                d = parse_date(row["merge_effective"])
                if d <= NOV30:
                    merges.append((acct_id(row["account_id"]), acct_id(row["merged_into"]), d))
    guarded(late, None)
    C.merges = {}
    for p, s, d in merges:
        C.merges.setdefault(p, []).append((d, s))
    C.disc = {}

    def dc():
        for kind, val in docx_tables(path("disconnection_register_2025.docx")):
            if kind == "t" and "order_ref" in val[0]:
                for r in val[1:]:
                    row = dict(zip(val[0], r))
                    if row["order_ref"].startswith("SOX"):
                        continue
                    C.disc.setdefault(meter_id(row["meter_id"]), []).append((parse_date(row["event_date"]), row["event"]))
    guarded(dc, None)
    C.nem = {}

    def nm():
        for row in csv_dicts(path("netmetering_enrollments.csv")):
            if row["status"].strip() != "APPROVED":
                continue
            to = row["effective_to"].strip()
            C.nem.setdefault(meter_id(row["meter_id"]), []).append((parse_date(row["effective_from"]), parse_date(to) if to else None))
    guarded(nm, None)
    C.insp = {}

    def ins():
        for name, rows in xlsx_sheets(path("export_meter_inspections_2025.xlsx")).items():
            for row in sheet_dicts(rows, "meter_id"):
                C.insp.setdefault(meter_id(row["meter_id"]), []).append((xl_date(row["inspected_on"]), row["result"]))
    guarded(ins, None)
    # rate codes
    reversed_ids = set()
    C.aliases = {}

    def rs():
        sheets = xlsx_sheets(path("account_rate_history_restated.xlsx"))
        for row in sheet_dicts(sheets["Reversals"], "entry_id"):
            reversed_ids.add(int(row["entry_id"]))
    guarded(rs, None)
    early = []

    def xw():
        doc = json.loads(ntext(path("rate_code_crosswalk_2026.json"), "utf-8"))
        for a in doc["records"]:
            if a["kind"] == "legacy_alias" and a["status"] == "ACTIVE":
                C.aliases[a["alias"]] = a["rate_code"]
        for x in doc["records"]:
            if x["kind"] != "migration":
                continue
            st = x.get("status") or x.get("state")
            if st == "WITHDRAWN":
                continue
            d = parse_date(x.get("effective_from") or x.get("effective"))
            if NOV1 <= d < DEC1:
                early.append((acct_id(x.get("account_id") or x.get("account")), d, x.get("new_rate_code") or x.get("to_rate_code")))
    guarded(xw, None)
    C.codes = {}

    def rh():
        for name, rows in xlsx_sheets(path("account_rate_history.xlsx")).items():
            for row in sheet_dicts(rows, "entry_id"):
                eid = int(row["entry_id"])
                if eid in reversed_ids:
                    continue
                code = str(row["rate_code"]).strip()
                code = C.aliases.get(code, code)
                C.codes.setdefault(acct_id(row["account_id"]), []).append((xl_date(row["effective_from"]), 0, eid, code))
    guarded(rh, None)
    for a, d, code in early:
        C.codes.setdefault(a, []).append((d, 1, 0, code))
    for a in C.codes:
        C.codes[a].sort()


def resolve_account(C, a, d):
    seen = set()
    while a not in seen:
        seen.add(a)
        cands = [x for x in C.merges.get(a, []) if x[0] <= d]
        if not cands:
            break
        a = max(cands)[1]
    return a


def code_on(C, a, d):
    cur = None
    for frm, _p, _e, code in C.codes.get(a, []):
        if frm <= d:
            cur = code
    return cur or C.master.get(a, {}).get("code")


def load_tariffs(C):
    C.rates = {}
    for fn in ("tariff_book_residential_q4.docx", "tariff_book_industrial_q4.docx"):
        def one(fn=fn):
            items = docx_tables(path(fn))
            dollars = set()
            for kind, val in items:
                if kind == "p" and val.startswith("Note U:"):
                    dollars = set(re.findall(r"[A-Z]{3}-\d{2}", val))
            for kind, val in items:
                if kind == "t" and "rate_code" in val[0]:
                    for r in val[1:]:
                        row = dict(zip(val[0], r))
                        code = clean(row["rate_code"])
                        v = num(row["rate"])
                        if code in dollars:
                            v = v * 100
                        C.rates[(code, parse_date(row["date"]), row["daytype"])] = q(v, 5)
        guarded(one, None)
    for fn in ("tariff_book_commercial_q4.pdf", "tariff_book_agri_lighting_q4.pdf"):
        def one(fn=fn):
            lines = pdf_lines(path(fn))
            dollars = set()
            for ln in lines:
                if ln.startswith("Note U:"):
                    dollars = set(re.findall(r"[A-Z]{3}-\d{2}", ln))
            for row in pipe_table(lines, ["RATE_CODE", "DATE", "DAYTYPE", "RATE"]):
                code = clean(row["RATE_CODE"])
                v = num(row["RATE"])
                if code in dollars:
                    v = v * 100
                C.rates[(code, parse_date(row["DATE"]), row["DAYTYPE"])] = q(v, 5)
        guarded(one, None)
    C.errata = {}

    def te():
        rows = []
        for head, rs in html_tables(path("tariff_errata_register.html")):
            rows += rs
        sup = {r["supersedes"] for r in rows if r["status"] == "APPROVED" and r["supersedes"]}
        for r in rows:
            if r["status"] != "APPROVED" or r["erratum"] in sup:
                continue
            k = (clean(r["rate_code"]), parse_date(r["date"]), r["daytype"])
            key = (date.fromisoformat(r["issued"]), int(r["erratum"].split("-")[1]))
            if k not in C.errata or key > C.errata[k][0]:
                C.errata[k] = (key, q(num(r["rate"]), 5))
    guarded(te, None)
    C.riders = {}

    def rd():
        lines = pdf_lines(path("rider_schedule_2025.pdf"))
        for row in pipe_table(lines, ["RIDER", "RATE_CODE", "FROM", "TO", "ADDER", "STATUS"]):
            if row["STATUS"] != "ACTIVE":
                continue
            v = num(row["ADDER"])
            if row["RIDER"] == "R-LIEAP":
                v = v / 10
            C.riders.setdefault((row["RIDER"], clean(row["RATE_CODE"])), []).append((parse_date(row["FROM"]), parse_date(row["TO"]), q(v, 5)))
    guarded(rd, None)
    C.appl = {}

    def ap():
        for head, rows in html_tables(path("rider_applicability_matrix.html")):
            for r in rows:
                C.appl.setdefault((clean(r["rate_code"]), r["rider"], r["territory"]), []).append((parse_date(r["effective_from"]), r["applies"]))
        for k in C.appl:
            C.appl[k].sort()
    guarded(ap, None)
    C.storm = []

    def st():
        lines = pdf_lines(path("tariff_book_residential_2026.pdf"))
        for row in pipe_table(lines, ["RATE_CODE", "EFFECTIVE_FROM", "ADDER", "STATUS"]):
            d = parse_date(row["EFFECTIVE_FROM"])
            if row["STATUS"] == "APPROVED" and d <= NOV30:
                C.storm.append((clean(row["RATE_CODE"]), d, q(num(row["ADDER"]), 5)))
    guarded(st, None)
    C.export_rates = {}

    def ex():
        items = docx_tables(path("net_metering_export_credit_rider.docx"))
        dollars = set()
        for kind, val in items:
            if kind == "p" and val.startswith("Note C:"):
                dollars = set(re.findall(r"[A-Z]{3}-\d{2}", val))
        for kind, val in items:
            if kind == "t" and "credit_rate" in val[0]:
                for r in val[1:]:
                    row = dict(zip(val[0], r))
                    code = clean(row["rate_code"])
                    v = num(row["credit_rate"])
                    if code in dollars:
                        v = v * 100
                    C.export_rates[(code, parse_date(row["date"]), row["daytype"])] = q(v, 5)
    guarded(ex, None)
    C.daytype = {}
    events = []

    def ics():
        text = ntext(path("territory_rate_calendar.ics"), "utf-8").replace("\n ", "")
        for block in text.split("BEGIN:VEVENT")[1:]:
            ev = {}
            for ln in block.split("\n"):
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    ev[k.split(";")[0]] = v.strip()
            events.append({"kind": ev["CATEGORIES"], "terr": ev["X-KVEC-TERRITORY"].upper(), "status": ev["STATUS"],
                           "start": datetime.strptime(ev["DTSTART"][:8], "%Y%m%d").date(), "end": datetime.strptime(ev["DTEND"][:8], "%Y%m%d").date()})
    guarded(ics, None)
    for t in TERRS:
        for d in SETTLE_DAYS:
            kinds = {e["kind"] for e in events if e["terr"] == t and e["status"] == "CONFIRMED" and e["start"] <= d < e["end"]}
            C.daytype[(t, d)] = "HOLIDAY" if "HOLIDAY" in kinds else "CPP" if "CPP" in kinds else ("WEEKEND" if d.weekday() >= 5 else "WEEKDAY")


def base_rate(C, code, d, dt):
    k = (code, d, dt)
    if k in C.errata:
        return C.errata[k][1]
    if TOLERANT and k not in C.rates:
        return Decimal(0)
    return C.rates[k]


def adders(C, code, d, terr):
    tot = Decimal(0)
    for rd in RIDER_IDS:
        rows = [x for x in C.riders.get((rd, code), []) if x[0] <= d < x[1]]
        if not rows:
            continue
        flag = None
        for frm, f in C.appl.get((code, rd, terr), []):
            if frm <= d:
                flag = f
        if flag == "Y":
            tot += rows[-1][2]
    for c, frm, a in C.storm:
        if c == code and frm <= d:
            tot += a
    return tot


def lighting(C):
    fixtures = {}

    def inv():
        doc = json.loads(ntext(path("unmetered_supply_inventory.json"), "utf-8"))
        for x in doc["fixtures"]:
            fid = fixture_id(x.get("fixture_id") or x.get("fixture"))
            rem = x.get("removed", x.get("out_of_service"))
            fixtures[fid] = {"acct": acct_id(x.get("account_id") or x.get("account")), "feeder": feeder_id(x["feeder"]),
                             "watts": int(num(x.get("nominal_watts", x.get("watts")))), "profile": x.get("burn_profile") or x.get("profile"),
                             "install": parse_date(x.get("installed") or x.get("in_service")), "removal": parse_date(rem) if rem else None}
    guarded(inv, None)
    audits = {}

    def au():
        for name, rows in xlsx_sheets(path("unmetered_fixture_audit_2025.xlsx")).items():
            for row in sheet_dicts(rows, "fixture_id"):
                audits.setdefault(fixture_id(row["fixture_id"]), []).append((xl_date(row["effective_date"]), row["finding"],
                                                                             int(num(row["audited_watts"]))))
    guarded(au, None)
    burn = {}

    def bh():
        doc = json.loads(ntext(path("photocell_burn_hours.json"), "utf-8"))
        for x in doc["rows"]:
            burn[(feeder_id(x["feeder"]), parse_date(x["date"]))] = q(num(x["hours"]), 2)
    guarded(bh, None)
    exc = {}

    def be():
        for name, rows in xlsx_sheets(path("lighting_burn_hour_exceptions_2025.xlsx")).items():
            for row in sheet_dicts(rows, "fixture_id"):
                exc[(fixture_id(row["fixture_id"]), xl_date(row["date"]))] = q(num(row["hours"]), 2)
    guarded(be, None)
    out = []
    for fid in sorted(fixtures):
        fx = fixtures[fid]
        for d in SETTLE_DAYS:
            if d < fx["install"] or (fx["removal"] and d >= fx["removal"]):
                continue
            watts = fx["watts"]
            removed = False
            for eff, finding, w in sorted(audits.get(fid, [])):
                if eff <= d:
                    if finding == "REMOVED":
                        removed = True
                    elif finding == "WATTAGE_CHANGE":
                        watts = w
            if removed:
                continue
            if (fid, d) in exc:
                hours = exc[(fid, d)]
            elif fx["profile"] == "ALL_DAY":
                hours = Decimal("24.00")
            elif fx["profile"] == "PART_NIGHT":
                hours = max(Decimal(0), burn.get((fx["feeder"], d), Decimal(0)) - Decimal("6.00"))
            else:
                hours = burn.get((fx["feeder"], d), Decimal(0))
            wh = rhe(Decimal(watts) * hours)
            if wh > 0:
                out.append((fid, fx["acct"], fx["feeder"], d, wh))
    return out


def scada(C):
    vals = {}
    good = {}

    def north():
        for row in csv_dicts(path("substation_north_scada_2025-11.csv")):
            ts = row["interval_end_local"].strip()
            naive = datetime.strptime(ts, "%m/%d/%Y %H:%M") if "/" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M")
            t = to_utc(naive, fold=1 if row["tz"].strip() == "CST" else 0)
            f = feeder_id(row["feeder"])
            if row["quality"].strip() != "GOOD" or row["kw_avg"].strip() in ("", "-9999"):
                vals[(f, t)] = None
            else:
                vals[(f, t)] = rhe(q(num(row["kw_avg"]), 2) * 250)
    guarded(north, None)

    def east():
        doc = json.loads(ntext(path("substation_east_scada_2025-11.json"), "utf-8"))
        for x in doc["intervals"]:
            f = feeder_id(x.get("feeder") or x.get("fdr"))
            tv = x.get("end_utc", x.get("t"))
            t = parse_iso(tv) if isinstance(tv, str) else int(tv)
            v = x.get("kwh", x.get("value"))
            qual = x.get("q", x.get("quality"))
            vals[(f, t)] = None if (v is None or qual != "G") else int(q(num(v), 3) * 1000)
    guarded(east, None)

    def south():
        for ln in ntext(path("substation_south_historian.log"), "utf-8").split("\n"):
            ln = ln.rstrip("\r")
            if ln.startswith("HIST|"):
                _h, f, ts, v, qual = ln.split("|")
                ts = ts.strip()
                t = parse_iso(ts.replace(" ", "T"))
                vals[(feeder_id(f), t)] = None if (qual != "GOOD" or v == "NaN") else int(q(num(v), 3) * 1000)
            elif ln.startswith("#") or ln.startswith("FORMAT"):
                continue
            elif " HIST " in ln:
                m = re.match(r"(\S+) HIST\s+(.+?)\s+MWH=(\S+) Q=(\S+)", ln)
                t = parse_iso(m.group(1))
                v, qual = m.group(3), m.group(4)
                vals[(feeder_id(m.group(2)), t)] = None if (qual != "GOOD" or v == "NaN") else int(q(num(v), 6) * 1000000)
    guarded(south, None)

    def west():
        lines = pdf_lines(path("substation_west_monthly_report.pdf"))
        for row in pipe_table(lines, ["FEEDER", "END_LOCAL", "OFFSET", "KWH", "QUALITY"]):
            ts = row["END_LOCAL"]
            naive = datetime.strptime(ts, "%m/%d/%Y %H:%M") if "/" in ts else datetime.strptime(ts, "%Y-%m-%d %H:%M")
            off = row["OFFSET"]
            t = int((naive.replace(tzinfo=timezone.utc)).timestamp()) + (18000 if off == "-05:00" else 21600)
            vals[(feeder_id(row["FEEDER"]), t)] = None if (row["QUALITY"] != "GOOD" or row["KWH"] == "---") else int(q(num(row["KWH"]), 3) * 1000)
    guarded(west, None)
    alarms = {}

    def al():
        open_ = {}
        for ln in ntext(path("scada_alarm_journal.log"), "utf-8").split("\n"):
            ln = ln.rstrip("\r")
            if not ln:
                continue
            if ";ALARM;" in ln:
                ts, _a, f, typ, st = ln.split(";")
            else:
                m = re.match(r"(\S+) ALARM feeder=(.+?) type=(\S+) state=(\S+)", ln)
                ts, f, typ, st = m.group(1), m.group(2), m.group(3), m.group(4)
            if typ != "COMM_FAIL":
                continue
            f = feeder_id(f)
            t = parse_iso(ts)
            if st == "RAISED":
                open_.setdefault(f, []).append(t)
            elif open_.get(f):
                alarms.setdefault(f, []).append((open_[f].pop(0), t))
    guarded(al, None)
    serr = {}

    def se():
        rows = md_tables(path("scada_errata_notice.md"), ["erratum", "feeder", "interval_end", "wh", "status", "issued", "supersedes"])
        sup = {r["supersedes"] for r in rows if r["status"] == "APPROVED" and r["supersedes"]}
        for r in rows:
            if r["status"] != "APPROVED" or r["erratum"] in sup:
                continue
            k = (feeder_id(r["feeder"]), parse_iso(r["interval_end"]))
            key = (date.fromisoformat(r["issued"]), int(r["erratum"].split("-")[1]))
            if k not in serr or key > serr[k][0]:
                serr[k] = (key, int(num(r["wh"])))
    guarded(se, None)
    relay = {}

    def rl():
        lines = pdf_lines(path("substation_east_monthly_report.pdf"))
        for row in pipe_table(lines, ["FEEDER", "INTERVAL_END_UTC", "KWH", "TEST_STATUS"]):
            if row["TEST_STATUS"] == "DONE":
                relay[(feeder_id(row["FEEDER"]), parse_iso(row["INTERVAL_END_UTC"]))] = int(q(num(row["KWH"]), 3) * 1000)
    guarded(rl, None)
    gap = {}

    def gf():
        for row in csv_dicts(path("scada_15min_gapfill_2025-11.csv")):
            if row["model_version"] != "v3" or row["status"] != "PUBLISHED":
                continue
            gap[(feeder_id(row["feeder"]), parse_iso(row["interval_end_utc"]))] = int(num(row["wh_est"]))
    guarded(gf, None)
    start = day_start(NOV1)
    end = day_start(DEC1)
    ends = [start + 900 * k for k in range(1, (end - start) // 900 + 1)]
    rows = []
    inj = {f: 0 for f in FEEDER_IDS}
    for f in FEEDER_IDS:
        for t in ends:
            v = vals.get((f, t))
            bad = v is None or any(a < t and c > t - 900 for a, c in alarms.get(f, []))
            if (f, t) in serr:
                w, s = serr[(f, t)][1], "ERRATUM"
            elif (f, t) in relay:
                w, s = relay[(f, t)], "RELAY_TEST"
            elif not bad:
                w, s = v, "HISTORIAN"
            else:
                w, s = gap.get((f, t), 0), "GAPFILL"
            inj[f] += w
            rows.append({"feeder": f, "interval_end_utc": datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "injection_wh": w, "source": s})
    return rows, inj


def exemptions(C):
    ex = set()

    def one():
        lines = pdf_lines(path("ufe_allocation_exemptions_register.pdf"))
        for row in pipe_table(lines, ["ACCOUNT", "FROM", "TO", "STATUS", "BASIS"]):
            to = None if row["TO"] == "-" else parse_date(row["TO"])
            if row["STATUS"] == "ACTIVE" and parse_date(row["FROM"]) <= NOV30 and (to is None or NOV30 < to):
                ex.add(acct_id(row["ACCOUNT"]))
    guarded(one, None)
    return ex


def largest_remainder(total, weights):
    if not weights:
        return {}
    sign = -1 if total < 0 else 1
    amt = abs(total)
    W = sum(weights.values())
    out = {}
    rem = []
    for a, w in weights.items():
        qq, r_ = divmod(amt * w, W)
        out[a] = qq
        rem.append((-r_, a))
    rem.sort()
    for _r, a in rem[:amt - sum(out.values())]:
        out[a] += 1
    return {a: sign * v for a, v in out.items()}


def main(argv):
    global TOLERANT, DATA
    args = [a for a in argv[1:] if not a.startswith("--")]
    TOLERANT = "--tolerant" in argv
    DATA = Path(args[0]) if args else Path("/app/data")
    out = Path(args[1]) if len(args) > 1 else Path("/app/out")
    out.mkdir(parents=True, exist_ok=True)
    C = Ctx()
    load_reference(C)
    load_registry(C)
    reads = load_read_files(C)
    load_controls(C)
    resolve_boundaries(C, reads)
    energy(C)
    load_accounts(C)
    load_tariffs(C)
    acc = {}

    def A(a):
        return acc.setdefault(a, {"imp": 0, "exp": 0, "deemed": 0, "energy": Decimal(0), "rider": Decimal(0), "credit": Decimal(0), "last": None})
    fb = {f: {"billed_import_wh": 0, "billed_export_wh": 0, "deemed_wh": 0, "unbilled_wh": 0} for f in FEEDER_IDS}
    msum = {}
    for m in sorted(C.inst):
        f = C.conn.get(m)
        if TOLERANT and f not in fb:
            continue
        terr = C.territory.get(f)
        rec = {"import_wh": 0, "billed_import_wh": 0, "unbilled_wh": 0, "export_wh": 0}
        for d in SETTLE_DAYS:
            if (m, d) not in C.imp and (m, d) not in C.exp:
                continue
            wi = C.imp.get((m, d), 0)
            we = C.exp.get((m, d), 0)
            rec["import_wh"] += wi
            a0 = None
            for row in C.reg.get(m, []):
                if row["from"] <= d and (row["to"] is None or d < row["to"]):
                    a0 = row["acct"]
            if a0 is None:
                rec["unbilled_wh"] += wi
                fb[f]["unbilled_wh"] += wi
                continue
            a = resolve_account(C, a0, d)
            ms = C.master.get(a, {})
            vacant = ms.get("status") == "FINAL" and ms.get("final") is not None and ms["final"] <= d
            ev = sorted(e for e in C.disc.get(m, []) if e[0] <= d)
            disc = bool(ev) and ev[-1][1] == "DISCONNECT"
            if vacant or disc:
                rec["unbilled_wh"] += wi
                fb[f]["unbilled_wh"] += wi
                continue
            credit = 0
            if we and any(fr <= d and (to is None or d < to) for fr, to in C.nem.get(m, [])):
                last = sorted((x for x in C.insp.get(m, []) if x[0] <= d), key=lambda z: (z[0], z[1] == "FAIL"))
                if last and last[-1][1] == "PASS":
                    credit = we
            rec["billed_import_wh"] += wi
            rec["export_wh"] += credit
            fb[f]["billed_import_wh"] += wi
            fb[f]["billed_export_wh"] += credit
            if wi == 0 and credit == 0:
                continue
            s = A(a)
            code = code_on(C, a, d)
            dt = C.daytype.get((terr, d), "WEEKDAY") if TOLERANT else C.daytype[(terr, d)]
            s["imp"] += wi
            s["exp"] += credit
            s["energy"] += Decimal(wi) * base_rate(C, code, d, dt) / 1000
            s["rider"] += Decimal(wi) * adders(C, code, d, terr) / 1000
            if credit:
                s["credit"] += Decimal(credit) * (C.export_rates.get((code, d, dt), Decimal(0)) if TOLERANT else C.export_rates[(code, d, dt)]) / 1000
            s["last"] = d
        msum[m] = rec
    lit = {}
    for fid, a, f, d, wh in lighting(C):
        terr = C.territory.get(f)
        s = A(a)
        code = code_on(C, a, d)
        dt = C.daytype.get((terr, d), "WEEKDAY") if TOLERANT else C.daytype[(terr, d)]
        s["deemed"] += wh
        s["energy"] += Decimal(wh) * base_rate(C, code, d, dt) / 1000
        s["rider"] += Decimal(wh) * adders(C, code, d, terr) / 1000
        s["last"] = d if s["last"] is None or d > s["last"] else s["last"]
        if f in fb:
            fb[f]["deemed_wh"] += wh
        x = lit.setdefault(fid, [a, 0, 0])
        x[1] += 1
        x[2] += wh
    intervals, inj = scada(C)
    loss = {f: rhe(Decimal(inj[f]) * C.loss_pct.get(f, Decimal(0)) / 100) for f in FEEDER_IDS}
    tot_imp = sum(v["imp"] for v in acc.values())
    tot_deemed = sum(v["deemed"] for v in acc.values())
    tot_exp = sum(v["exp"] for v in acc.values())
    ufe = sum(inj.values()) + tot_exp - sum(loss.values()) - tot_imp - tot_deemed
    ex = exemptions(C)
    cents = {a: (rhe(v["energy"]), rhe(v["rider"]), -rhe(v["credit"])) for a, v in acc.items()}
    alloc = largest_remainder(ufe, {a: v["imp"] + v["deemed"] for a, v in acc.items() if a not in ex and v["imp"] + v["deemed"] > 0})
    e_sum = sum(c[0] for c in cents.values())
    r_sum = sum(c[1] for c in cents.values())
    price = (Decimal(e_sum + r_sum) * 1000 / Decimal(tot_imp + tot_deemed)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
    acc_rows = []
    for a in sorted(acc):
        v = acc[a]
        if v["imp"] == 0 and v["exp"] == 0 and v["deemed"] == 0:
            continue
        u = alloc.get(a, 0)
        uc = rhe(Decimal(u) * price / 1000)
        e, rr, cr = cents[a]
        acc_rows.append([a, code_on(C, a, v["last"]), v["imp"], v["exp"], v["deemed"], e, rr, cr, u, uc, e + rr + cr + uc])
    met_rows = []
    res_rows = []
    for m in sorted(C.inst):
        rng = C.service[m]
        if not any((m, b) in C.bval for b in rng):
            continue
        cnt = {"CORRECTION": 0, "ESTIMATE": 0, "MISSING": 0, "INVALIDATED": 0}
        for b in rng:
            if (m, b) in C.invalid:
                kind, v = "INVALIDATED", C.invalid[(m, b)]
            else:
                kind = C.bsrc.get((m, b), "MISSING")
                v = C.bval[(m, b)][0] if kind in ("CORRECTION", "ESTIMATE") else None
            if kind == "ACTUAL":
                continue
            cnt[kind] += 1
            res_rows.append([m, BDATES[b].isoformat(), kind, "" if v is None else f"{v:.3f}"])
        r_ = msum.get(m, {"import_wh": 0, "billed_import_wh": 0, "unbilled_wh": 0, "export_wh": 0})
        met_rows.append([m, C.conn.get(m), r_["import_wh"], r_["billed_import_wh"], r_["unbilled_wh"], r_["export_wh"],
                         cnt["CORRECTION"], cnt["ESTIMATE"], cnt["MISSING"], cnt["INVALIDATED"]])
    feeders = {}
    for f in FEEDER_IDS:
        t_ = fb[f]
        feeders[f] = {"injection_wh": inj[f], "loss_wh": loss[f], **t_,
                      "residual_wh": inj[f] + t_["billed_export_wh"] - loss[f] - t_["billed_import_wh"] - t_["deemed_wh"]}
    batches = []
    names = sorted(set(C.data_rows))
    for fn in names:
        b_ = C.batch.get(fn, {})
        mf = C.manifest.get(fn, {})
        n = C.data_rows[fn]
        st = b_.get("status", "")
        rej = n if st == "REJECTED" else (lambda z: z[1] - z[0] + 1)(list(map(int, b_["rejected_rows"].split("-")))) if st == "PARTIAL" else 0
        wd = mf.get("withdrawn_rows")
        batches.append({"file": fn, "data_rows": n, "manifest_rows": mf.get("record_count"), "mdm_status": st, "rejected_rows": rej,
                        "withdrawn_rows": (lambda z: z[1] - z[0] + 1)(list(map(int, wd.split("-")))) if wd else 0})
    summary = {"account_count": len(acc_rows), "meter_count": len(met_rows), "injection_wh": sum(inj.values()),
               "loss_wh": sum(loss.values()), "billed_import_wh": tot_imp, "billed_export_wh": tot_exp, "deemed_wh": tot_deemed,
               "unbilled_wh": sum(r_["unbilled_wh"] for r_ in msum.values()), "ufe_wh": ufe, "ufe_price_cents_per_kwh": f"{price:.6f}",
               "energy_cents": e_sum, "rider_cents": r_sum, "export_credit_cents": sum(r[7] for r in acc_rows),
               "ufe_charge_cents": sum(r[9] for r in acc_rows), "total_cents": sum(r[10] for r in acc_rows)}

    def wcsv(name, head, rows):
        (out / name).write_text("\n".join([",".join(head)] + [",".join(str(c) for c in r) for r in rows]) + "\n", encoding="utf-8")

    def wjson(name, obj):
        (out / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    wcsv("account_settlement.csv", ["account_id", "rate_code", "billed_import_wh", "billed_export_wh", "deemed_wh", "energy_cents",
                                    "rider_cents", "export_credit_cents", "ufe_wh", "ufe_charge_cents", "total_cents"], acc_rows)
    wcsv("meter_summary.csv", ["meter_id", "feeder", "import_wh", "billed_import_wh", "unbilled_wh", "export_wh", "corrected_boundaries",
                               "estimated_boundaries", "missing_boundaries", "invalidated_boundaries"], met_rows)
    wcsv("read_resolution.csv", ["meter_id", "boundary_date", "source", "import_kwh"], res_rows)
    wcsv("interval_injection.csv", ["feeder", "interval_end_utc", "injection_wh", "source"],
         [[r["feeder"], r["interval_end_utc"], r["injection_wh"], r["source"]] for r in intervals])
    wcsv("lighting_deemed.csv", ["fixture_id", "account_id", "burn_days", "deemed_wh"], [[k, v[0], v[1], v[2]] for k, v in sorted(lit.items())])
    wcsv("daytype_calendar.csv", ["territory", "date", "daytype"], [[t, d.isoformat(), C.daytype[(t, d)]] for t in TERRS for d in SETTLE_DAYS])
    wjson("feeder_balance.json", {"feeders": feeders})
    wjson("control_report.json", {"batches": batches})
    wjson("settlement_summary.json", summary)


if __name__ == "__main__":
    main(sys.argv)
