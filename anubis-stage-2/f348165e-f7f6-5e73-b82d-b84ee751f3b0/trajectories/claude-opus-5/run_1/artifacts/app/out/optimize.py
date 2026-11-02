#!/usr/bin/env python3
"""Reservation quota settlement of a model-serving platform extract."""

import bisect
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import struct
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
import zlib

CLASSES = ("visible", "peak", "steady", "burst", "latency")
STATUSES = ("ok", "cut", "rejected")
ADMISSIBLE = tuple(range(1200, 5001, 100))
OOXML = "http://schemas.openxmlformats.org/"
W_NS = "{" + OOXML + "wordprocessingml/2006/main}"
S_NS = "{" + OOXML + "spreadsheetml/2006/main}"
R_NS = "{" + OOXML + "officeDocument/2006/relationships}"
P_NS = "{" + OOXML + "package/2006/relationships}"
MC_NS = "{" + OOXML + "markup-compatibility/2006}"
CORR_FIELDS = ("contracted_ru", "pool", "retired")


class Rejected(Exception):
    """An extract that breaks an invariant of the service contract."""


# --------------------------------------------------------------- instants


def days_from_civil(y, m, d):
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return yoe + era * 400 + (1 if m <= 2 else 0), m, d


EPOCH = days_from_civil(2026, 1, 1) * 86400
INSTANT_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")


def parse_instant(text):
    m = INSTANT_RE.match(text)
    if not m:
        raise Rejected("malformed instant: %r" % (text,))
    y, mo, d, hh, mm, ss = (int(x) for x in m.groups())
    if not (1 <= mo <= 12 and 1 <= d <= 31 and hh < 24 and mm < 60 and ss < 60):
        raise Rejected("malformed instant: %r" % (text,))
    return days_from_civil(y, mo, d) * 86400 + hh * 3600 + mm * 60 + ss - EPOCH


def format_instant(sec):
    day, rem = divmod(sec + EPOCH, 86400)
    y, mo, d = civil_from_days(day)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
        y, mo, d, rem // 3600, rem // 60 % 60, rem % 60)


# ------------------------------------------------------------ office xml


def _parts(el):
    """The children of el an ECMA-376 consumer understands, in order."""
    out = []
    for ch in el:
        if ch.tag == MC_NS + "AlternateContent":
            fb = ch.find(MC_NS + "Fallback")
            if fb is not None:
                out.extend(_parts(fb))
            continue
        tag = ch.tag
        if not isinstance(tag, str) or not tag.startswith("{" + OOXML):
            continue
        out.append(ch)
    return out


def _find(el, tag):
    for ch in _parts(el):
        if ch.tag == tag:
            return ch
        got = _find(ch, tag)
        if got is not None:
            return got
    return None


def _wtext(el, buf):
    for ch in _parts(el):
        if ch.tag == W_NS + "t":
            buf.append(ch.text or "")
        else:
            _wtext(ch, buf)


def read_docx_table(path):
    """The rows of the one table of a WordprocessingML document."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    tbl = _find(root, W_NS + "tbl")
    if tbl is None:
        raise Rejected("no table in %s" % os.path.basename(path))
    rows = []
    for tr in _parts(tbl):
        if tr.tag != W_NS + "tr":
            continue
        cells = []
        for tc in _parts(tr):
            if tc.tag != W_NS + "tc":
                continue
            buf = []
            _wtext(tc, buf)
            cells.append("".join(buf).strip())
        rows.append(cells)
    return rows


def _sst(el):
    buf = []
    for t in el.iter(S_NS + "t"):
        buf.append(t.text or "")
    return "".join(buf)


def _cell_value(cell, shared):
    kind = cell.get("t") or "n"
    if kind == "inlineStr":
        node = cell.find(S_NS + "is")
        return "" if node is None else _sst(node)
    node = cell.find(S_NS + "v")
    text = "" if node is None or node.text is None else node.text
    if kind == "s":
        return shared[int(text)]
    return text


def _col_index(ref):
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx_sheet(path, name):
    """The rows of one sheet of a SpreadsheetML workbook, as cell texts."""
    with zipfile.ZipFile(path) as zf:
        book = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid = None
        for sheet in book.iter(S_NS + "sheet"):
            if sheet.get("name") == name:
                rid = sheet.get(R_NS + "id")
        if rid is None:
            raise Rejected("no sheet %s in %s" % (name, os.path.basename(path)))
        target = None
        for rel in rels.iter(P_NS + "Relationship"):
            if rel.get("Id") == rid:
                target = rel.get("Target")
        part = target[1:] if target.startswith("/") else "xl/" + target
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = [_sst(si) for si in sst]
        data = ET.fromstring(zf.read(part))
    return _sheet_rows(data, shared)


def _sheet_rows(data, shared):
    rows = []
    for row in data.iter(S_NS + "row"):
        cells = {}
        pos = -1
        for cell in row.findall(S_NS + "c"):
            ref = cell.get("r")
            pos = _col_index(ref) if ref else pos + 1
            cells[pos] = _cell_value(cell, shared)
        rows.append([cells.get(i, "") for i in range(max(cells) + 1)]
                    if cells else [])
    return rows


# -------------------------------------------------------------------- pdf

OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj")


def _pdf_objects(data):
    objs = {}
    for m in OBJ_RE.finditer(data):
        end = data.find(b"endobj", m.end())
        if end < 0:
            raise Rejected("unterminated PDF object")
        body = data[m.end():end]
        stream = None
        cut = body.find(b"stream")
        if cut >= 0:
            i = cut + 6
            while body[i:i + 1] in (b"\r", b"\n"):
                i += 1
            stream = body[i:body.find(b"endstream", i)]
            body = body[:cut]
        objs[int(m.group(1))] = (body, stream)
    return objs


def _pdf_strings(content):
    out = []
    i, n = 0, len(content)
    esc = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
    while i < n:
        if content[i] != 0x28:
            i += 1
            continue
        i += 1
        depth = 1
        buf = bytearray()
        while i < n and depth:
            ch = content[i]
            if ch == 0x5C:
                i += 1
                nxt = content[i]
                if nxt in esc:
                    buf.append(esc[nxt])
                    i += 1
                elif 0x30 <= nxt <= 0x37:
                    digits = b""
                    while len(digits) < 3 and 0x30 <= content[i] <= 0x37:
                        digits += content[i:i + 1]
                        i += 1
                    buf.append(int(digits, 8) & 0xFF)
                else:
                    buf.append(nxt)
                    i += 1
                continue
            if ch == 0x28:
                depth += 1
            elif ch == 0x29:
                depth -= 1
                if not depth:
                    i += 1
                    break
            buf.append(ch)
            i += 1
        out.append(buf.decode("latin-1"))
    return out


def read_pdf_lines(path):
    """The text lines of the one page of a PDF document."""
    with open(path, "rb") as fh:
        data = fh.read()
    objs = _pdf_objects(data)
    page = None
    for body, _ in objs.values():
        if b"/Type /Page" in body and b"/Type /Pages" not in body:
            page = body
    if page is None:
        raise Rejected("no page in %s" % os.path.basename(path))
    ref = re.search(rb"/Contents\s+(\d+)\s+\d+\s+R", page)
    if not ref:
        raise Rejected("no page contents in %s" % os.path.basename(path))
    body, stream = objs[int(ref.group(1))]
    if stream is None:
        raise Rejected("no content stream in %s" % os.path.basename(path))
    if b"/FlateDecode" in body:
        stream = zlib.decompress(stream)
    return _pdf_strings(stream)


# ---------------------------------------------------------- request logs


def _uvar(data, state):
    value = 0
    shift = 0
    while True:
        if state[0] >= len(data):
            raise Rejected("truncated record")
        byte = data[state[0]]
        state[0] += 1
        value |= (byte & 127) << shift
        shift += 7
        if not byte & 128:
            return value


def _text(data, state):
    if state[0] >= len(data):
        raise Rejected("truncated record")
    size = data[state[0]]
    state[0] += 1
    end = state[0] + size
    if end > len(data):
        raise Rejected("truncated text")
    out = data[state[0]:end].decode("ascii")
    state[0] = end
    return out


def _log_header(data, path):
    if len(data) < 21 or data[:4] != b"RQB1" or data[4] != 1:
        raise Rejected("not an RQB1 log: %s" % os.path.basename(path))
    if data[5] >= len(CLASSES):
        raise Rejected("bad class code: %s" % os.path.basename(path))
    return (CLASSES[data[5]], data[6:8].decode("ascii"),
            struct.unpack(">I", data[8:12])[0],
            struct.unpack(">I", data[12:16])[0])


def log_class(path):
    with open(path, "rb") as fh:
        return _log_header(fh.read(21), path)[0]


def _record_key(data, state, sel, keys):
    if sel & 16:
        back = _uvar(data, state)
        pos = len(keys) - 1 - back
        if pos < 0:
            raise Rejected("bad key back-reference")
        return keys[pos]
    key = _text(data, state)
    if key not in keys:
        keys.append(key)
    return key


def _record_model(data, state, sel, models):
    if sel & 64:
        idx = _uvar(data, state)
        if idx >= len(models):
            raise Rejected("bad model index")
        return models[idx]
    model = _text(data, state)
    if model not in models:
        models.append(model)
    return model


def _record_head(data, state, cls, path):
    sel = data[state[0]]
    state[0] += 1
    if sel == 3:
        return None
    if sel & 128:
        raise Rejected("reserved selector bit: %s" % os.path.basename(path))
    status = (sel >> 2) & 3
    if status == 3:
        raise Rejected("status outside the contract")
    rcls = cls
    if sel & 32:
        if state[0] >= len(data) or data[state[0]] >= len(CLASSES):
            raise Rejected("bad class byte")
        rcls = CLASSES[data[state[0]]]
        state[0] += 1
    return (sel, sel & 3, STATUSES[status], rcls)


def _check_log(recs, count, cls, path):
    if len(recs) != count:
        raise Rejected("record count mismatch: %s" % os.path.basename(path))
    if not recs:
        raise Rejected("empty request log: %s" % os.path.basename(path))
    if any(r["traffic_class"] != cls for r in recs):
        raise Rejected("log names more than one class: %s"
                       % os.path.basename(path))


def parse_log(path):
    """The requests of one RQB1 request log, with its traffic class."""
    with open(path, "rb") as fh:
        data = fh.read()
    cls, prefix, base, count = _log_header(data, path)
    if struct.unpack(">I", data[17:21])[0] != zlib.crc32(
            data[16:17] + data[21:]):
        raise Rejected("checksum mismatch: %s" % os.path.basename(path))
    state = [21]
    keys, models, recs = [], [], []
    run = base
    last = None
    while state[0] < len(data):
        head = _record_head(data, state, cls, path)
        if head is None:
            continue
        sel, mode, status, rcls = head
        num = _uvar(data, state)
        if mode == 2:
            if last is None:
                raise Rejected("repeat record first in log")
            key, model = last
        else:
            key = _record_key(data, state, sel, keys)
            model = _record_model(data, state, sel, models)
        prompt = _uvar(data, state)
        completion = _uvar(data, state)
        zig = _uvar(data, state)
        delta = zig // 2 if zig % 2 == 0 else -((zig + 1) // 2)
        run = (base if mode == 0 else run) + delta
        last = (key, model)
        recs.append({"req_id": "rq-%s%05d" % (prefix, num), "api_key": key,
                     "model": model, "prompt_tok": prompt,
                     "completion_tok": completion, "done_at": run,
                     "status": status, "traffic_class": rcls})
    _check_log(recs, count, cls, path)
    return cls, recs


# ------------------------------------------------------------- the inputs


def read_delimited(path, delim):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=delim, quotechar='"'))
    if not rows:
        raise Rejected("empty sheet: %s" % os.path.basename(path))
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:] if r]


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def find_control(data_dir):
    names = sorted(os.listdir(data_dir))
    if "ctl_r7.json" in names:
        return os.path.join(data_dir, "ctl_r7.json")
    for name in names:
        if name.endswith(".json"):
            path = os.path.join(data_dir, name)
            obj = read_json(path)
            if isinstance(obj, dict) and "cutoff_seq" in obj:
                return path
    raise Rejected("no control file in %s" % data_dir)


def open_register(path):
    uri = "file:" + urllib.parse.quote(path) + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_register(ctx):
    con = open_register(ctx["files"]["register"])
    rows = list(con.execute(
        "select code, traffic_class, pool, contracted_ru, retired from tenant"))
    pools = list(con.execute("select pool_id, traffic_class, grp from pool"))
    aliases = list(con.execute("select api_key, tenant, eff_from from alias"))
    con.close()
    tenants = {}
    for code, cls, pool, ru, retired in rows:
        if (code, cls) in tenants:
            raise Rejected("duplicate tenant row: %s %s" % (code, cls))
        tenants[(code, cls)] = {"pool": pool, "contracted_ru": int(ru),
                                "retired": int(retired)}
    ctx["tenants"] = tenants
    ctx["pool_class"] = {p: c for p, c, _ in pools}
    ctx["pool_grp"] = {p: g for p, _, g in pools}
    seen = set()
    table = {}
    for key, tenant, eff in aliases:
        if (key, eff) in seen:
            raise Rejected("duplicate alias row: %s %s" % (key, eff))
        seen.add((key, eff))
        table.setdefault(key, []).append((parse_instant(eff), tenant))
    for key in table:
        table[key].sort()
    ctx["alias"] = table


def load_pool_params(ctx):
    cross = read_delimited(ctx["files"]["crosswalk"], ",")
    seen = {}
    for row in cross:
        if row["grp"] in seen:
            raise Rejected("group twice in crosswalk: %s" % row["grp"])
        seen[row["grp"]] = row["prof_code"]
    rows = read_docx_table(ctx["files"]["profiles"])
    head = rows[0]
    profiles = {}
    for row in rows[1:]:
        rec = dict(zip(head, row))
        if rec["prof_code"] in profiles:
            raise Rejected("profile code twice: %s" % rec["prof_code"])
        profiles[rec["prof_code"]] = (int(rec["start_step"]),
                                      int(rec["patience"]), int(rec["budget"]))
    params = {}
    for pool, grp in ctx["pool_grp"].items():
        if grp not in seen:
            raise Rejected("group not in crosswalk: %s" % grp)
        code = seen[grp]
        if code not in profiles:
            raise Rejected("profile code not in profiles: %s" % code)
        params[pool] = profiles[code]
    ctx["params"] = params


def load_weights(ctx):
    rows = read_docx_table(ctx["files"]["weights"])
    head = rows[0]
    weights = {}
    for row in rows[1:]:
        rec = dict(zip(head, row))
        weights[rec["model"]] = (int(rec["prompt_weight"]),
                                 int(rec["completion_weight"]))
    ctx["weights"] = weights


def load_rates(ctx):
    rows = read_xlsx_sheet(ctx["files"]["rates"], "rates")
    head = rows[0]
    out = []
    for row in rows[1:]:
        rec = dict(zip(head, row))
        out.append((rec["traffic_class"], rec["eff_from"],
                    int(rec["ru_rate_micro"]), int(rec["over_rate_micro"]),
                    int(rec["round_fee_micro"])))
    ctx["rate_rows"] = out


def load_readings(ctx):
    readings = []
    for line in read_pdf_lines(ctx["files"]["units"]):
        parts = line.split(" ")
        if len(parts) < 5 or parts[0] != "reading":
            continue
        readings.append((parts[1], parse_instant(parts[2]), int(parts[3]),
                         parts[4:]))
    ctx["readings"] = readings


def load_inputs(data_dir):
    ctx = {"data_dir": data_dir}
    control = find_control(data_dir)
    ctl = read_json(control)
    base = os.path.dirname(control)
    ctx["ctl"] = ctl
    ctx["files"] = {k: os.path.join(base, v) for k, v in ctl["files"].items()}
    load_register(ctx)
    load_pool_params(ctx)
    load_weights(ctx)
    load_rates(ctx)
    load_readings(ctx)
    return ctx


# -------------------------------------------------------------- stage one


def _corr_entries(ctx):
    rows = read_delimited(ctx["files"]["amendments"], "\t")
    entries = [("amendment", int(r["seq"]), r["tenant"], r["traffic_class"],
                r["field"], r["value"]) for r in rows]
    with open(ctx["files"]["overrides"], "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            obj = json.loads(line)
            entries.append(("override", int(obj["seq"]), obj["tenant"],
                            obj["traffic_class"], obj["field"],
                            str(obj["value"])))
    return entries


def apply_corrections(ctx):
    cutoff = ctx["ctl"]["cutoff_seq"]
    entries = _corr_entries(ctx)
    tenants = ctx["tenants"]
    status = {}
    winner = {}
    for layer, seq, tenant, cls, field, value in entries:
        if seq > cutoff:
            status[(layer, seq)] = "cutoff"
            continue
        if (tenant, cls) not in tenants:
            status[(layer, seq)] = "unmatched"
            continue
        status[(layer, seq)] = "applied"
        rank = 1 if layer == "override" else 0
        key = (tenant, cls, field)
        cur = winner.get(key)
        if cur is None or (rank, seq) > (cur[0], cur[1]):
            winner[key] = (rank, seq, value)
    for (tenant, cls, field), (_, _, value) in winner.items():
        row = tenants[(tenant, cls)]
        if field == "contracted_ru":
            row["contracted_ru"] = int(value)
        elif field == "pool":
            row["pool"] = value
        elif field == "retired":
            row["retired"] = 1 if value == "yes" else 0
        else:
            raise Rejected("unknown correction field: %s" % field)
    ctx["corrections"] = [(layer, seq, tenant, cls, field,
                           status[(layer, seq)])
                          for layer, seq, tenant, cls, field, _ in entries]
    ctx["corr_counts"] = {name: sum(1 for v in status.values() if v == name)
                          for name in ("applied", "cutoff", "unmatched")}


def form_membership(ctx):
    for (code, cls), row in ctx["tenants"].items():
        if ctx["pool_class"].get(row["pool"]) != cls:
            raise Rejected("tenant %s names pool %s outside class %s"
                           % (code, row["pool"], cls))
    members = {}
    for (code, cls), row in ctx["tenants"].items():
        if not row["retired"]:
            members[(cls, code)] = row
    ctx["members"] = members
    ctx["pool_of"] = {m: row["pool"] for m, row in members.items()}


def load_logs(ctx):
    names = [n for n in sorted(os.listdir(ctx["data_dir"]))
             if n.startswith("ev_") and n.endswith(".rqb")]
    byclass = {}
    for name in names:
        cls, recs = parse_log(os.path.join(ctx["data_dir"], name))
        seen = {}
        for rec in recs:
            if rec["req_id"] in seen:
                raise Rejected("duplicate req_id in %s: %s"
                               % (name, rec["req_id"]))
            seen[rec["req_id"]] = rec
        pool = byclass.setdefault(cls, {})
        for rid, rec in seen.items():
            if rid in pool and pool[rid] != rec:
                raise Rejected("conflicting request %s in class %s"
                               % (rid, cls))
            pool[rid] = rec
    for pool in byclass.values():
        for rec in pool.values():
            if rec["model"] not in ctx["weights"]:
                raise Rejected("model not in the weight table: %s"
                               % rec["model"])
    ctx["requests"] = byclass
    ctx["in_scope"] = [c for c in CLASSES if c in byclass]


def alias_tenant(ctx, key, instant):
    rows = ctx["alias"].get(key)
    if not rows:
        return None
    pos = bisect.bisect_right(rows, (instant, "\uffff")) - 1
    if pos < 0:
        return None
    return rows[pos][1]


def classify(ctx):
    counts = {}
    tokens = {}
    timeline = {}
    bymodel = {}
    orphans = []
    for cls in ctx["in_scope"]:
        start = parse_instant(ctx["ctl"]["windows"][cls][0])
        end = parse_instant(ctx["ctl"]["windows"][cls][1])
        tally = dict(orphan=0, out_of_window=0, rejected=0, counted=0,
                     in_window=0)
        for rid in sorted(ctx["requests"][cls]):
            rec = ctx["requests"][cls][rid]
            reason = _reason(ctx, rec, cls, start, end, tally)
            if reason:
                orphans.append((cls, rid, reason))
                continue
            member = (cls, alias_tenant(ctx, rec["api_key"], rec["done_at"]))
            prompt, completion = ctx["weights"][rec["model"]]
            units = rec["prompt_tok"] * prompt
            if rec["status"] == "ok":
                units += rec["completion_tok"] * completion
            tally["counted"] += 1
            tokens[member] = tokens.get(member, 0) + units
            timeline.setdefault(member, []).append((rec["done_at"], units))
            slot = bymodel.setdefault((cls, rec["model"]), [0, 0])
            slot[0] += 1
            slot[1] += units
        counts[cls] = tally
    ctx["counts"] = counts
    ctx["tokens"] = tokens
    ctx["bymodel"] = bymodel
    ctx["orphans"] = orphans
    ctx["timeline"] = {m: _prefix(v) for m, v in timeline.items()}


def _reason(ctx, rec, cls, start, end, tally):
    if not start < rec["done_at"] <= end:
        tally["out_of_window"] += 1
        return "out_of_window"
    tally["in_window"] += 1
    if rec["status"] == "rejected":
        tally["rejected"] += 1
        return "rejected"
    tenant = alias_tenant(ctx, rec["api_key"], rec["done_at"])
    if tenant is None or (cls, tenant) not in ctx["members"]:
        tally["orphan"] += 1
        return "orphan"
    return None


def _prefix(pairs):
    pairs.sort()
    instants = [p[0] for p in pairs]
    sums = [0]
    for _, units in pairs:
        sums.append(sums[-1] + units)
    return (instants, sums)


def tokens_upto(ctx, member, instant):
    line = ctx["timeline"].get(member)
    if line is None:
        return 0
    return line[1][bisect.bisect_right(line[0], instant)]


# ---------------------------------------------------------- calibration


def _reading_groups(ctx, instant, keys):
    groups = {}
    seen = set()
    for key in keys:
        tenant = alias_tenant(ctx, key, instant)
        if tenant is None:
            continue
        for cls in CLASSES:
            member = (cls, tenant)
            if member in ctx["members"] and member not in seen:
                seen.add(member)
                units = tokens_upto(ctx, member, instant)
                if units:
                    groups.setdefault(ctx["pool_of"][member], []).append(units)
    return groups


def _upr_tables(cons):
    tables = {}
    for idx, (_, _, groups) in enumerate(cons):
        for pool, units in groups.items():
            tables[(idx, pool)] = {x: sum(-(-u // x) for u in units)
                                   for x in ADMISSIBLE}
    return tables


def _upr_order(cons, needy):
    order = []
    for _, _, groups in sorted(cons, key=lambda c: len(c[2])):
        for pool in sorted(groups):
            if pool not in order:
                order.append(pool)
    for pool in sorted(needy):
        if pool not in order:
            order.append(pool)
    return order


def _upr_feasible(assign, cons, tables, bounds):
    for idx, (_, value, groups) in enumerate(cons):
        total, low, high, full = 0, 0, 0, True
        for pool in groups:
            if pool in assign:
                total += tables[(idx, pool)][assign[pool]]
            else:
                full = False
                low += bounds[(idx, pool)][0]
                high += bounds[(idx, pool)][1]
        if full:
            if total != value:
                return False
        elif total + low > value or total + high < value:
            return False
    return True


def _upr_rec(order, depth, assign, cons, tables, bounds, domains, sols):
    if depth == len(order):
        sols.append(dict(assign))
        return
    pool = order[depth]
    for value in domains[pool]:
        assign[pool] = value
        if _upr_feasible(assign, cons, tables, bounds):
            _upr_rec(order, depth + 1, assign, cons, tables, bounds,
                     domains, sols)
        if len(sols) >= 2:
            break
    assign.pop(pool, None)


def calibrate(ctx):
    needy = set()
    for member, units in ctx["tokens"].items():
        if units:
            needy.add(ctx["pool_of"][member])
    cons = [(rid, value, _reading_groups(ctx, instant, keys))
            for rid, instant, value, keys in ctx["readings"]]
    tables = _upr_tables(cons)
    domains = {p: list(ADMISSIBLE) for p in needy}
    for idx, (rid, value, groups) in enumerate(cons):
        if not groups:
            if value != 0:
                raise Rejected("reading %s meets no member" % rid)
        elif len(groups) == 1:
            pool = next(iter(groups))
            domains[pool] = [x for x in domains[pool]
                             if tables[(idx, pool)][x] == value]
    bounds = {}
    for (idx, pool), table in tables.items():
        vals = [table[x] for x in domains[pool]] or [0]
        bounds[(idx, pool)] = (min(vals), max(vals))
    sols = []
    _upr_rec(_upr_order(cons, needy), 0, {}, cons, tables, bounds, domains,
             sols)
    if len(sols) != 1:
        raise Rejected("the meter readings settle no single units per RU")
    ctx["upr"] = sols[0]


# ----------------------------------------------------------- settlement


def _targets(total, demand, standing, dtotal):
    if dtotal == 0:
        return list(standing)
    base, rem = [], []
    for value in demand:
        whole, left = divmod(total * value, dtotal)
        base.append(whole)
        rem.append(left)
    spare = total - sum(base)
    order = sorted(range(len(base)),
                   key=lambda i: (-rem[i], -standing[i], i))
    for i in order[:spare]:
        base[i] += 1
    return base


def _nearest(num, den):
    neg = num < 0
    whole, rem = divmod(-num if neg else num, den)
    if 2 * rem > den:
        whole += 1
    return -whole if neg else whole


def _furthest(targets, standing, moves):
    best, pick = None, 0
    for i, target in enumerate(targets):
        gap = abs(target - standing[i] - moves[i])
        if best is None or gap > best:
            best, pick = gap, i
    return pick


def settle_pool(demand, contracted, step, patience, budget):
    hold = list(contracted)
    total = sum(contracted)
    dtotal = sum(demand)
    history = [tuple(hold)]
    trace = []
    count, prev, rnd = 0, None, 0
    while True:
        targets = _targets(total, demand, hold, dtotal)
        residual = [targets[i] - hold[i] for i in range(len(hold))]
        rtotal = sum(abs(v) for v in residual)
        if rnd >= 1 and rtotal >= prev:
            count += 1
            if count == patience:
                step = max(1, step // 2)
                count = 0
        prev = rtotal
        trace.append((rnd, rtotal, step))
        if rtotal == 0:
            return ("settled", rnd, step, hold, trace)
        moves = [_nearest(v * step, 4) for v in residual]
        drift = sum(moves)
        if drift:
            moves[_furthest(targets, hold, moves)] -= drift
        if not any(moves):
            return ("stalled", rnd, step, hold, trace)
        hold = [hold[i] + moves[i] for i in range(len(hold))]
        state = tuple(hold)
        if state in history:
            cycle = history[history.index(state):]
            return ("cycled", -1, step, list(min(cycle)), trace)
        history.append(state)
        if len(history) - 1 >= budget:
            return ("budget", budget, step, hold, trace)
        rnd += 1


def settle_classes(ctx):
    results = {}
    for cls in ctx["in_scope"]:
        bypool = {}
        for (mcls, code), row in ctx["members"].items():
            if mcls == cls:
                bypool.setdefault(row["pool"], []).append(code)
        pools = []
        for pool in sorted(bypool):
            pools.append(_settle_one(ctx, cls, pool, sorted(bypool[pool])))
        results[cls] = pools
    ctx["settled"] = results


def _settle_one(ctx, cls, pool, codes):
    unit = ctx["upr"].get(pool, 0)
    contracted = [ctx["members"][(cls, c)]["contracted_ru"] for c in codes]
    tokens = [ctx["tokens"].get((cls, c), 0) for c in codes]
    demand = [(-(-t // unit) if unit else 0) for t in tokens]
    step, patience, budget = ctx["params"][pool]
    exit_name, rounds, final, hold, trace = settle_pool(
        demand, contracted, step, patience, budget)
    members = []
    for i, code in enumerate(codes):
        members.append({"tenant": code, "contracted_ru": contracted[i],
                        "demand_ru": demand[i], "settled_ru": hold[i],
                        "token_units": tokens[i]})
    return {"pool": pool, "exit": exit_name, "rounds": rounds,
            "final_step": final, "members": members, "trace": trace,
            "budget": budget, "total": sum(contracted)}


# -------------------------------------------------------------- billing


def pick_rate(ctx, cls):
    day = ctx["ctl"]["windows"][cls][1][:10]
    best = None
    for name, eff, ru, over, fee in ctx["rate_rows"]:
        if name == cls and eff <= day and (best is None or eff >= best[0]):
            best = (eff, ru, over, fee)
    if best is None:
        raise Rejected("no rate row in force for class %s" % cls)
    return {"eff_from": best[0], "ru_rate_micro": best[1],
            "over_rate_micro": best[2], "round_fee_micro": best[3]}


def build_bills(ctx):
    ctx["rates"] = {cls: pick_rate(ctx, cls) for cls in ctx["in_scope"]}
    lines = []
    for cls in ctx["in_scope"]:
        rate = ctx["rates"][cls]
        for pool in ctx["settled"][cls]:
            unit = ctx["upr"].get(pool["pool"], 0)
            rounds = pool["budget"] if pool["rounds"] < 0 else pool["rounds"]
            charge = rate["round_fee_micro"] * rounds
            share, spare = divmod(charge, len(pool["members"]))
            for i, member in enumerate(pool["members"]):
                orch = share + (1 if i < spare else 0)
                lines.append(_bill_line(cls, pool, member, unit, rate, orch))
    ctx["bills"] = lines


def _bill_line(cls, pool, member, unit, rate, orch):
    over = max(0, member["token_units"] - member["settled_ru"] * unit)
    res = member["settled_ru"] * rate["ru_rate_micro"]
    omicro = -(-(over * rate["over_rate_micro"]) // 1000)
    return {"traffic_class": cls, "pool": pool["pool"],
            "tenant": member["tenant"], "settled_ru": member["settled_ru"],
            "token_units": member["token_units"], "overage_units": over,
            "reservation_micro": res, "overage_micro": omicro,
            "orchestration_micro": orch, "total_micro": res + omicro + orch}


def result_object(ctx, cls):
    pools = []
    for pool in ctx["settled"][cls]:
        members = [{"tenant": m["tenant"], "contracted_ru": m["contracted_ru"],
                    "demand_ru": m["demand_ru"], "settled_ru": m["settled_ru"]}
                   for m in pool["members"]]
        pools.append({"pool": pool["pool"], "exit": pool["exit"],
                      "rounds": pool["rounds"],
                      "final_step": pool["final_step"], "members": members})
    units = sum(m["token_units"] for p in ctx["settled"][cls]
                for m in p["members"])
    return {"label": ctx["ctl"]["label"], "traffic_class": cls,
            "counted_requests": ctx["counts"][cls]["counted"],
            "token_units": units, "pools": pools}


def settle(data_dir):
    ctx = load_inputs(data_dir)
    apply_corrections(ctx)
    form_membership(ctx)
    load_logs(ctx)
    classify(ctx)
    calibrate(ctx)
    settle_classes(ctx)
    build_bills(ctx)
    ctx["results"] = {cls: result_object(ctx, cls) for cls in ctx["in_scope"]}
    return ctx


def aggregate(events_path, rules_path):
    """The result object of the traffic class of one request log."""
    cls = log_class(events_path)
    ctx = settle(os.path.dirname(os.path.abspath(rules_path)))
    if cls not in ctx["results"]:
        raise Rejected("class %s is out of scope" % cls)
    return ctx["results"][cls]


# --------------------------------------------------------- report bytes


def jdump(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True)
            + "\n").encode("ascii")


def oneline(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(", ", ": "))


def csv_rows(header, rows):
    out = []
    for row in [header] + rows:
        cells = []
        for cell in row:
            text = str(cell)
            if "," in text or '"' in text or "\n" in text:
                text = '"' + text.replace('"', '""') + '"'
            cells.append(text)
        out.append(",".join(cells))
    return ("\n".join(out) + "\n").encode("utf-8")


def joined_rows(header, rows, sep):
    out = [sep.join(str(c) for c in r) for r in [header] + rows]
    return ("\n".join(out) + "\n").encode("utf-8")


def xml_attr(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def xml_doc(root, elements):
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    if not elements:
        return (head + "<%s/>\n" % root).encode("utf-8")
    lines = [head + "<%s>" % root]
    for name, attrs in elements:
        pairs = " ".join('%s="%s"' % (k, xml_attr(v)) for k, v in attrs)
        lines.append("  <%s %s/>" % (name, pairs))
    lines.append("</%s>" % root)
    return ("\n".join(lines) + "\n").encode("utf-8")


def member_rows(ctx):
    for cls in ctx["in_scope"]:
        for pool in ctx["settled"][cls]:
            for member in pool["members"]:
                yield cls, pool, member


# ------------------------------------------------------- the report set


def report_scenarios(ctx, out):
    for cls in CLASSES:
        name = "scenario_%s.json" % cls
        if cls not in ctx["in_scope"]:
            out[name] = jdump({"traffic_class": cls, "in_scope": False})
            continue
        total = sum(b["total_micro"] for b in ctx["bills"]
                    if b["traffic_class"] == cls)
        out[name] = jdump({"traffic_class": cls, "in_scope": True,
                           "window": list(ctx["ctl"]["windows"][cls]),
                           "result": ctx["results"][cls],
                           "bill_total_micro": total})


def report_perf(ctx, out):
    pools = [p for cls in ctx["in_scope"] for p in ctx["settled"][cls]]
    out["perf_report.json"] = jdump({
        "classes_in_scope": list(ctx["in_scope"]),
        "pool_count": len(pools),
        "member_count": sum(len(p["members"]) for p in pools),
        "counted_requests": sum(ctx["counts"][c]["counted"]
                                for c in ctx["in_scope"])})


def report_bottleneck(ctx, out):
    items = [(cls, p) for cls in ctx["in_scope"] for p in ctx["settled"][cls]]
    longest = []
    if items:
        top = max(p["rounds"] for _, p in items)
        longest = [[cls, p["pool"], p["rounds"]] for cls, p in items
                   if p["rounds"] == top]
    out["bottleneck_analysis.json"] = jdump({
        "longest": longest,
        "unsettled": [[cls, p["pool"], p["exit"]] for cls, p in items
                      if p["exit"] in ("cycled", "budget")],
        "stalled": [[cls, p["pool"]] for cls, p in items
                    if p["exit"] == "stalled"]})


def report_recommendations(ctx, out):
    threshold = ctx["ctl"]["review_shift_ru"]
    actions = []
    for cls, _, member in member_rows(ctx):
        shift = member["settled_ru"] - member["contracted_ru"]
        if shift == 0 or abs(shift) < threshold:
            continue
        actions.append([cls, member["tenant"],
                        "raise" if shift > 0 else "lower", shift])
    out["recommendations.json"] = jdump({"review_shift_ru": threshold,
                                         "actions": actions})


def report_quality(ctx, out):
    retired = [[cls, code] for (code, cls), row in ctx["tenants"].items()
               if cls in ctx["in_scope"] and row["retired"]]
    retired.sort(key=lambda r: (CLASSES.index(r[0]), r[1]))
    out["data_quality.json"] = jdump({
        "orphan_requests": {c: ctx["counts"][c]["orphan"]
                            for c in ctx["in_scope"]},
        "out_of_window": {c: ctx["counts"][c]["out_of_window"]
                          for c in ctx["in_scope"]},
        "rejected_requests": {c: ctx["counts"][c]["rejected"]
                              for c in ctx["in_scope"]},
        "retired_members": retired,
        "corrections": ctx["corr_counts"]})


def report_settlement(ctx, out):
    rows = []
    trace = []
    exits = []
    members = {}
    for cls in ctx["in_scope"]:
        tally = {"settled": 0, "stalled": 0, "cycled": 0, "budget": 0}
        members[cls] = {}
        for pool in ctx["settled"][cls]:
            tally[pool["exit"]] += 1
            rows.append([cls, pool["pool"], len(pool["members"]),
                         pool["exit"], pool["rounds"], pool["final_step"],
                         pool["total"]])
            for rnd, residual, step in pool["trace"]:
                trace.append([cls, pool["pool"], rnd, residual, step])
            members[cls][pool["pool"]] = [m["tenant"] for m in pool["members"]]
        exits.append(("class", [("name", cls)] + [(k, tally[k]) for k in
                      ("settled", "stalled", "cycled", "budget")]))
    out["pool_settlement.csv"] = csv_rows(
        ["traffic_class", "pool", "members", "exit", "rounds", "final_step",
         "pool_total_ru"], rows)
    out["round_trace.psv"] = joined_rows(
        ["traffic_class", "pool", "round", "residual_total", "step"], trace,
        "|")
    out["exit_summary.xml"] = xml_doc("exits", exits)
    out["pool_members.json"] = jdump(members)


def report_holdings(ctx, out):
    rows = []
    shifts = []
    for cls, pool, member in member_rows(ctx):
        rows.append([cls, pool["pool"], member["tenant"],
                     member["contracted_ru"], member["demand_ru"],
                     member["settled_ru"]])
        if member["settled_ru"] != member["contracted_ru"]:
            shifts.append(("shift", [
                ("class", cls), ("pool", pool["pool"]),
                ("tenant", member["tenant"]),
                ("from", member["contracted_ru"]),
                ("to", member["settled_ru"]),
                ("delta", member["settled_ru"] - member["contracted_ru"])]))
    out["tenant_holdings.tsv"] = joined_rows(
        ["traffic_class", "pool", "tenant", "contracted_ru", "demand_ru",
         "settled_ru"], rows, "\t")
    out["holding_shift.xml"] = xml_doc("shifts", shifts)


BILL_COLS = ("traffic_class", "pool", "tenant", "settled_ru", "token_units",
             "overage_units", "reservation_micro", "overage_micro",
             "orchestration_micro", "total_micro")


def report_bills(ctx, out):
    out["tenant_bills.csv"] = csv_rows(
        list(BILL_COLS), [[b[c] for c in BILL_COLS] for b in ctx["bills"]])
    totals = {}
    for cls in ctx["in_scope"]:
        slot = {"lines": 0, "reservation_micro": 0, "overage_micro": 0,
                "orchestration_micro": 0, "total_micro": 0}
        for bill in ctx["bills"]:
            if bill["traffic_class"] != cls:
                continue
            slot["lines"] += 1
            for key in ("reservation_micro", "overage_micro",
                        "orchestration_micro", "total_micro"):
                slot[key] += bill[key]
        totals[cls] = slot
    out["class_billing.json"] = jdump(totals)
    ctx["class_totals"] = totals


def report_invoices(ctx, out):
    lines = []
    for bill in ctx["bills"]:
        lines.append("- class: %s" % bill["traffic_class"])
        lines.append("  tenant: %s" % bill["tenant"])
        lines.append("  total_micro: %d" % bill["total_micro"])
    out["invoice_lines.yaml"] = _text_report(lines)
    blocks = []
    for cls in ctx["in_scope"]:
        rows = ["## %s" % cls, "", "| tenant | total_micro |", "|---|---:|"]
        for bill in ctx["bills"]:
            if bill["traffic_class"] == cls:
                rows.append("| %s | %d |" % (bill["tenant"],
                                             bill["total_micro"]))
        blocks.append("\n".join(rows))
    out["invoice_digest.md"] = _text_report(
        ("\n\n".join(blocks)).split("\n") if blocks else [])
    over = []
    for bill in ctx["bills"]:
        if bill["overage_units"] > 0:
            over.append("%-10s%-12s%12d%14d" % (
                bill["traffic_class"], bill["tenant"], bill["overage_units"],
                bill["overage_micro"]))
    out["overage.txt"] = _text_report(over)


def _text_report(lines):
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode("utf-8")


def report_rates(ctx, out):
    obj = {}
    for cls in ctx["in_scope"]:
        rate = dict(ctx["rates"][cls])
        units = {}
        for pool in ctx["settled"][cls]:
            if any(m["token_units"] for m in pool["members"]):
                units[pool["pool"]] = ctx["upr"][pool["pool"]]
        rate["units_per_ru"] = units
        obj[cls] = rate
    out["rate_application.json"] = jdump(obj)


def report_prior(ctx, out):
    prior = read_json(ctx["files"]["prior"]).get("settled", {})
    rows = []
    for cls in ctx["in_scope"]:
        found = []
        for pool in ctx["settled"][cls]:
            found.extend(pool["members"])
        for member in sorted(found, key=lambda m: m["tenant"]):
            known = prior.get(cls, {})
            if member["tenant"] in known:
                before = int(known[member["tenant"]])
                rows.append([cls, member["tenant"], member["settled_ru"],
                             before, member["settled_ru"] - before])
            else:
                rows.append([cls, member["tenant"], member["settled_ru"],
                             "", ""])
    out["delta_prior.csv"] = csv_rows(
        ["traffic_class", "tenant", "settled_ru", "prior_ru", "delta_ru"],
        rows)


def report_audit(ctx, out):
    rows = []
    for cls in ctx["in_scope"]:
        for (name, model), (count, units) in sorted(ctx["bymodel"].items()):
            if name == cls:
                rows.append([cls, model, count, units])
    out["demand_by_model.tsv"] = joined_rows(
        ["traffic_class", "model", "counted_requests", "token_units"], rows,
        "\t")
    orphans = sorted(ctx["orphans"], key=lambda r: (CLASSES.index(r[0]), r[1]))
    out["orphans.csv"] = csv_rows(["traffic_class", "req_id", "reason"],
                                  [list(r) for r in orphans])
    corr = [c for c in ctx["corrections"] if c[0] == "amendment"]
    corr.sort(key=lambda c: c[1])
    rest = [c for c in ctx["corrections"] if c[0] == "override"]
    rest.sort(key=lambda c: c[1])
    out["corrections_applied.csv"] = csv_rows(
        ["layer", "seq", "tenant", "traffic_class", "field", "status"],
        [list(c) for c in corr + rest])
    out["window_counts.csv"] = csv_rows(
        ["traffic_class", "in_window", "out_of_window"],
        [[c, ctx["counts"][c]["in_window"], ctx["counts"][c]["out_of_window"]]
         for c in ctx["in_scope"]])


def ledger_tables(ctx):
    bills = [(b["traffic_class"], b["tenant"], b["total_micro"])
             for b in ctx["bills"]]
    pools = [(cls, p["pool"], p["exit"], p["rounds"])
             for cls in ctx["in_scope"] for p in ctx["settled"][cls]]
    return {"bills": bills, "pools": pools}


def book_rows(ctx):
    rows = [["traffic_class", "tenant", "reservation_micro", "overage_micro",
             "orchestration_micro", "total_micro"]]
    for bill in ctx["bills"]:
        rows.append([bill["traffic_class"], bill["tenant"],
                     bill["reservation_micro"], bill["overage_micro"],
                     bill["orchestration_micro"], bill["total_micro"]])
    return rows


def report_reconciliation(ctx, out):
    tables = ledger_tables(ctx)
    obj = {}
    for cls in ctx["in_scope"]:
        lines = sum(b["total_micro"] for b in ctx["bills"]
                    if b["traffic_class"] == cls)
        ledger = sum(r[2] for r in tables["bills"] if r[0] == cls)
        total = ctx["class_totals"][cls]["total_micro"]
        shift = 0
        for pool in ctx["settled"][cls]:
            for member in pool["members"]:
                shift += member["settled_ru"] - member["contracted_ru"]
        obj[cls] = {"bill_lines_total": lines, "class_total": total,
                    "ledger_total": ledger,
                    "residual_micro": lines + ledger - 2 * total,
                    "ru_residual": shift}
    out["reconciliation.json"] = jdump(obj)


def ledger_dump(tables):
    lines = []
    for name in sorted(tables):
        lines.append("table %s\n" % name)
        for row in tables[name]:
            lines.append("\t".join(str(v) for v in row) + "\n")
    return "".join(lines).encode("utf-8")


def book_dump(rows):
    return "".join("\t".join(str(v) for v in r) + "\n"
                   for r in rows).encode("utf-8")


# ------------------------------------------------------- writing it out


def write_ledger(path, tables):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE bills (traffic_class TEXT, tenant TEXT, "
                "total_micro INTEGER)")
    con.execute("CREATE TABLE pools (traffic_class TEXT, pool TEXT, "
                "exit TEXT, rounds INTEGER)")
    con.executemany("INSERT INTO bills VALUES (?, ?, ?)", tables["bills"])
    con.executemany("INSERT INTO pools VALUES (?, ?, ?, ?)", tables["pools"])
    con.commit()
    con.close()


def book_bytes(rows):
    sheet = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<worksheet xmlns="' + OOXML + 'spreadsheetml/2006/main">',
             "<sheetData>"]
    for num, row in enumerate(rows, 1):
        cells = []
        for col, value in enumerate(row):
            ref = chr(65 + col) + str(num)
            if isinstance(value, int):
                cells.append('<c r="%s"><v>%d</v></c>' % (ref, value))
            else:
                cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>'
                             % (ref, xml_attr(value)))
        sheet.append('<row r="%d">%s</row>' % (num, "".join(cells)))
    sheet.append("</sheetData></worksheet>")
    parts = [("[Content_Types].xml", BOOK_TYPES), ("_rels/.rels", BOOK_RELS),
             ("xl/workbook.xml", BOOK_WB),
             ("xl/_rels/workbook.xml.rels", BOOK_WBRELS),
             ("xl/worksheets/sheet1.xml", "".join(sheet))]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in parts:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            zf.writestr(info, text)
    return buf.getvalue()


BOOK_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="' + OOXML
    + 'package/2006/content-types"><Default Extension="rels" ContentType="'
    'application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.'
    'openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/'
    'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
BOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="' + OOXML
    + 'package/2006/relationships"><Relationship Id="rId1" Type="' + OOXML
    + 'officeDocument/2006/relationships/officeDocument" Target='
    '"xl/workbook.xml"/></Relationships>')
BOOK_WB = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<workbook xmlns="' + OOXML
    + 'spreadsheetml/2006/main" xmlns:r="' + OOXML
    + 'officeDocument/2006/relationships"><sheets><sheet name="bills" '
    'sheetId="1" r:id="rId1"/></sheets></workbook>')
BOOK_WBRELS = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="' + OOXML
    + 'package/2006/relationships"><Relationship Id="rId1" Type="' + OOXML
    + 'officeDocument/2006/relationships/worksheet" Target='
    '"worksheets/sheet1.xml"/></Relationships>')


def build_reports(ctx):
    out = {}
    report_scenarios(ctx, out)
    report_perf(ctx, out)
    report_bottleneck(ctx, out)
    report_recommendations(ctx, out)
    report_quality(ctx, out)
    report_settlement(ctx, out)
    report_holdings(ctx, out)
    report_bills(ctx, out)
    report_invoices(ctx, out)
    report_rates(ctx, out)
    report_prior(ctx, out)
    report_reconciliation(ctx, out)
    report_audit(ctx, out)
    return out


def write_reports(ctx, out_dir):
    texts = build_reports(ctx)
    tables = ledger_tables(ctx)
    rows = book_rows(ctx)
    digests = {name: hashlib.sha256(data).hexdigest()
               for name, data in texts.items()}
    digests["billing_ledger.sqlite"] = hashlib.sha256(
        ledger_dump(tables)).hexdigest()
    digests["billing_book.xlsx"] = hashlib.sha256(
        book_dump(rows)).hexdigest()
    texts["manifest.json"] = jdump({"reports": digests})
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in sorted(texts):
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(texts[name])
    write_ledger(os.path.join(out_dir, "billing_ledger.sqlite"), tables)
    with open(os.path.join(out_dir, "billing_book.xlsx"), "wb") as fh:
        fh.write(book_bytes(rows))
    return len(texts) + 2


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py DATA_DIR OUT_DIR\n"
                         "       optimize.py EVENTS_LOG RULES_JSON\n")
        return 2
    first, second = argv[1], argv[2]
    if os.path.isdir(first):
        write_reports(settle(first), second)
    else:
        sys.stdout.write(oneline(aggregate(first, second)) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Rejected as exc:
        sys.stderr.write("rejected: %s\n" % exc)
        sys.exit(1)
