#!/usr/bin/env python3
# Corrected dispatch replan: coefficient rebuild plus three exact programmes.
from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

SENTINELS: set = set()  # filled from the nomenclature contract by load()
REC_PREFIX = "R|"


def rhu(num: int, den: int) -> int:
    # round half up, away from zero
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


def norm_code(value) -> str:
    text = str(value).strip().upper().replace("-", "").replace("_", "").replace(" ", "")
    m = re.match(r"^([A-Z]+)(\d+)$", text)
    if m:
        return m.group(1) + m.group(2).zfill(2)
    return text


def is_sentinel(value) -> bool:
    return str(value).strip() in SENTINELS


def to_int(value) -> int:
    return int(str(value).strip())


def get(row: dict, *names):
    for n in names:
        if n in row:
            return row[n]
    return None


# ---------------------------------------------------------------------------
# format readers
# ---------------------------------------------------------------------------
def _split_lines(path: Path):
    return [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln != ""]


def read_delimited(path: Path, sep: str):
    lines = _split_lines(path)
    header = [h.strip() for h in lines[0].split(sep)]
    out = []
    for ln in lines[1:]:
        cells = ln.split(sep)
        row = {}
        for i, name in enumerate(header):
            row[name] = cells[i] if i < len(cells) else ""
        out.append(row)
    return out


def read_ndjson(path: Path):
    return [json.loads(ln) for ln in _split_lines(path)]


def read_json_records(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict):
        for key in ("records", "period_rows", "rows"):
            if isinstance(doc.get(key), list):
                return doc[key]
        return []
    return doc


def read_xml_rows(path: Path):
    return [dict(child.attrib) for child in ET.parse(str(path)).getroot()]


def read_text_rows(path: Path):
    lines = path.read_text(encoding="utf-8").split("\n")
    cols = None
    out = []
    for ln in lines:
        if not ln.strip():
            continue
        if ln.lstrip().startswith("#"):
            m = re.search(r"fixed column order:\s*(\S+)", ln)
            if m:
                cols = m.group(1).split("|")
            continue
        cells = ln.split("|")
        if cols is None:
            out.append({"line": ln})
        else:
            row = {}
            for i, name in enumerate(cols):
                row[name] = cells[i] if i < len(cells) else ""
            out.append(row)
    return out


def read_text_lines(path: Path):
    return [ln for ln in path.read_text(encoding="utf-8").split("\n")
            if ln.strip() and not ln.strip().startswith("#")]


def read_sqlite_tables(path: Path):
    con = sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)
    tables = {}
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in names:
        cur = con.execute("SELECT * FROM " + name)
        cols = [d[0] for d in cur.description]
        tables[name] = [dict(zip(cols, row)) for row in cur.fetchall()]
    con.close()
    return tables


def read_xlsx_sheets(path: Path):
    zf = zipfile.ZipFile(path)
    wb = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in sroot:
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    sheets = {}
    for m in re.finditer(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        name, rid = m.group(1), m.group(2)
        part = target.get(rid, "")
        if not part.startswith("xl/"):
            part = "xl/" + part
        root = ET.fromstring(zf.read(part))
        rows = []
        for row in root.iter():
            if not row.tag.endswith("}row"):
                continue
            cells = []
            for c in row:
                kind = c.attrib.get("t", "")
                text = ""
                if kind == "inlineStr":
                    text = "".join(t.text or "" for t in c.iter() if t.tag.endswith("}t"))
                elif kind == "s":
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    if v is not None and v.text is not None:
                        idx = int(v.text)
                        text = shared[idx] if idx < len(shared) else ""
                else:
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    text = v.text if v is not None and v.text is not None else ""
                cells.append(text)
            rows.append(cells)
        sheets[name] = rows
    zf.close()
    return sheets


def read_docx_paragraphs(path: Path):
    zf = zipfile.ZipFile(path)
    root = ET.fromstring(zf.read("word/document.xml"))
    zf.close()
    out = []
    for p in root.iter():
        if p.tag.endswith("}p"):
            out.append("".join(t.text or "" for t in p.iter() if t.tag.endswith("}t")))
    return out


def read_pdf_lines(path: Path):
    blob = path.read_bytes()
    texts = []
    for m in re.finditer(rb"/Length\s+(\d+)[^>]*>>\s*stream\r?\n", blob):
        size = int(m.group(1))
        chunk = blob[m.end():m.end() + size]
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            # an unfiltered stream is read as stored
            pass
        for t in re.finditer(rb"\((.*?)\)\s*Tj", chunk, re.S):
            raw = t.group(1)
            raw = raw.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            texts.append(raw.decode("latin-1"))
    return texts


def read_rows(path: Path, fmt: str):
    if fmt == "csv":
        return read_delimited(path, ",")
    if fmt == "tsv":
        return read_delimited(path, "\t")
    if fmt == "psv":
        return read_delimited(path, "|")
    if fmt in ("jsonl", "ndjson"):
        return read_ndjson(path)
    if fmt == "json":
        return read_json_records(path)
    if fmt == "xml":
        return read_xml_rows(path)
    if fmt == "txt":
        return read_text_rows(path)
    return []


def physical_rows(path: Path, fmt: str) -> int:
    if fmt in ("csv", "tsv", "psv"):
        return max(0, len(_split_lines(path)) - 1)
    if fmt in ("jsonl", "ndjson"):
        return len(_split_lines(path))
    if fmt == "json":
        return len(read_json_records(path))
    if fmt == "xml":
        return len(read_xml_rows(path))
    if fmt in ("txt", "md", "yaml", "yml"):
        return len(read_text_lines(path))
    if fmt in ("db", "sqlite"):
        return sum(len(v) for v in read_sqlite_tables(path).values())
    if fmt == "xlsx":
        return sum(max(0, len(rows) - 1) for rows in read_xlsx_sheets(path).values())
    if fmt == "pdf":
        return sum(1 for ln in read_pdf_lines(path) if ln.startswith(REC_PREFIX))
    if fmt == "docx":
        return sum(1 for ln in read_docx_paragraphs(path) if ln.startswith(REC_PREFIX))
    return 0


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------
TABULAR = ("csv", "tsv", "psv", "jsonl", "ndjson", "json", "xml", "txt")


class Ctx:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.manifest = []
        self.by_role = {}
        self.by_src = {}
        self.rejects = []
        self.out_of_scope = 0
        self.void_rows = 0
        self.cutoff = 0
        self.lifecycle = {}
        self.revived = set()


def find_manifest(data_dir: Path):
    for path in sorted(Path(data_dir).iterdir()):
        if path.suffix.lower() in (".db", ".sqlite") and path.is_file():
            try:
                tables = read_sqlite_tables(path)
            except sqlite3.Error:
                continue
            if "sources" in tables:
                return path, tables["sources"]
    raise RuntimeError("no source manifest found")


def load(data_dir: Path) -> Ctx:
    ctx = Ctx(data_dir)
    _, sources = find_manifest(ctx.dir)
    ctx.manifest = [
        {"name": s["name"], "role": s["role"], "fmt": s["fmt"],
         "record_count": int(s["record_count"]), "authority": s["authority"]}
        for s in sources]
    ctx.manifest.sort(key=lambda s: s["name"])
    SENTINELS.clear()
    SENTINELS.update(sentinel_tokens(ctx))
    for src in ctx.manifest:
        path = ctx.dir / src["name"]
        rows = read_rows(path, src["fmt"]) if src["fmt"] in TABULAR else []
        for idx, row in enumerate(rows):
            row["__src"] = src["name"]
            row["__idx"] = idx
        ctx.by_src[src["name"]] = rows
        ctx.by_role.setdefault(src["role"], []).extend(
            rows if src["authority"] in ("primary", "contract") else [])
    return ctx


def config(ctx: Ctx) -> dict:
    cfg = {}
    for src in ctx.manifest:
        if src["fmt"] in ("db", "sqlite"):
            tables = read_sqlite_tables(ctx.dir / src["name"])
            for row in tables.get("cutoff_control", []):
                cfg[row["parameter"]] = row["value"]
    return cfg


def lifecycle_state(ctx: Ctx, cutoff: int) -> dict:
    events = {}
    for row in ctx.by_role.get("row_lifecycle", []):
        seq = to_int(get(row, "seq"))
        if seq > cutoff:
            continue
        action = str(get(row, "action")).strip()
        if action not in ("void", "restore"):
            continue
        uid = str(get(row, "row_uid")).strip()
        events.setdefault(uid, []).append((seq, row["__src"], row["__idx"], action))
    state = {}
    for uid, evs in events.items():
        evs.sort()
        state[uid] = evs[-1][3] == "void"
        # a row restored after a void is live but still carries VOI
        if not state[uid] and any(e[3] == "void" for e in evs):
            ctx.revived.add(uid)
    return state


# ---------------------------------------------------------------------------
# row selection
# ---------------------------------------------------------------------------
class Bucket:
    def __init__(self):
        self.live = []
        self.cut = False
        self.voided = False


def classify(ctx: Ctx, rows, keyfn, valuefn, cutoff, reject_reason="sentinel"):
    # returns {key: Bucket}
    out = {}
    for row in rows:
        key = keyfn(row)
        if key is None:
            continue
        bucket = out.setdefault(key, Bucket())
        value = valuefn(row)
        if is_sentinel(value):
            continue
        seq = to_int(get(row, "effective_seq", "seq"))
        if seq > cutoff:
            bucket.cut = True
            continue
        if to_int(get(row, "void") or 0) == 1:
            bucket.voided = True
            continue
        uid = str(get(row, "row_uid")).strip()
        if ctx.lifecycle.get(uid):
            bucket.voided = True
            continue
        if uid in ctx.revived:
            bucket.voided = True
        rev = to_int(get(row, "rev") or 1)
        bucket.live.append((rev, seq, row["__idx"], row, value))
    return out


def winner(bucket: Bucket):
    if not bucket.live:
        return None
    # canonical order: file name ascending, then row order inside the file
    return max(bucket.live, key=lambda e: (e[0], e[1], e[3]["__src"], e[2]))


def accumulate(ctx: Ctx, rows, keyfn, valuefn, cutoff, idfn=None, signfn=None):
    # additive registers: sum live rows, one row per logical identity
    totals = {}
    seen = set()
    marks = {}
    for row in rows:
        key = keyfn(row)
        if key is None:
            continue
        value = valuefn(row)
        if is_sentinel(value):
            continue
        seq = to_int(get(row, "effective_seq", "seq"))
        if seq > cutoff:
            marks.setdefault(key, set()).add("CUT")
            continue
        ident = idfn(row) if idfn else (key, row["__src"], row["__idx"])
        if ident in seen:
            continue
        seen.add(ident)
        if to_int(get(row, "void") or 0) == 1:
            marks.setdefault(key, set()).add("VOI")
            continue
        uid = str(get(row, "row_uid")).strip()
        if ctx.lifecycle.get(uid):
            marks.setdefault(key, set()).add("VOI")
            continue
        if uid in ctx.revived:
            marks.setdefault(key, set()).add("VOI")
        sign = signfn(row) if signfn else 1
        totals[key] = totals.get(key, 0) + sign * int(value)
        marks.setdefault(key, set()).add("AMD")
    return totals, marks


# ---------------------------------------------------------------------------
# document registers
# ---------------------------------------------------------------------------
def prefixed_rows(lines, source):
    out = []
    for idx, line in enumerate(lines):
        if not line.startswith(REC_PREFIX):
            continue
        parts = line.split("|")
        if len(parts) < 9 or parts[1] != "PARAM":
            continue
        out.append({"name": parts[2], "value": parts[3], "unit": parts[4],
                    "rev": parts[5], "effective_seq": parts[6], "void": parts[7],
                    "row_uid": parts[8], "__src": source, "__idx": idx})
    return out


def source_named(ctx: Ctx, role: str):
    for src in ctx.manifest:
        if src["role"] == role:
            return src
    return None


def sentinel_tokens(ctx: Ctx) -> set:
    """Tokens listed under sentinel_tokens in the nomenclature contract."""
    src = source_named(ctx, "contract_nomenclature")
    tokens, section = set(), None
    for raw in _split_lines(ctx.dir / src["name"]):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        text = line.strip()
        if not line.startswith(" "):
            section = text.rstrip(":")
        elif section == "sentinel_tokens" and text.startswith("- "):
            token = text[2:].strip()
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
                token = token[1:-1]
            tokens.add(token)
    return tokens


def doc_params(ctx: Ctx, role: str, reader):
    src = source_named(ctx, role)
    lines = reader(ctx.dir / src["name"])
    return prefixed_rows(lines, src["name"])


def bps_value(row) -> int:
    value = to_int(get(row, "value", "index_value", "uplift_value", "shift_value",
                       "derate_value"))
    unit = str(get(row, "unit") or "bps").strip()
    return value * 100 if unit == "pct" else value


def scaled_amount(row) -> int:
    value = to_int(get(row, "value", "amount"))
    scale = str(get(row, "scale", "unit") or "cents").strip()
    return value * 1000 if scale == "kcents" else value


IDENT_GROUPS = (("item_code", "item", "sku", "code"), ("period_code", "period"),
                ("plant_code", "plant"), ("project_id",), ("zone",))


def row_key(row, date_period) -> str:
    parts = []
    for names in IDENT_GROUPS:
        value = get(row, *names)
        if value is None and names[0] == "period_code" and "date" in row:
            value = date_period.get(str(row["date"]).strip())
        if value is not None:
            parts.append(norm_code(value))
    return ":".join(parts)


def audit_pass(ctx: Ctx, cutoff: int, item_status: dict, date_period: dict):
    # one independent sweep over every primary tabular source
    rejects = []
    out_of_scope = 0
    voided = 0
    for src in ctx.manifest:
        if src["authority"] != "primary" or src["fmt"] not in TABULAR:
            continue
        demand_like = src["role"] in ("demand", "demand_overlay")
        for row in ctx.by_src.get(src["name"], []):
            uid = str(get(row, "row_uid") or "").strip()
            key = row_key(row, date_period)
            reason = ""
            if demand_like:
                code = norm_code(get(row, "item_code", "item", "sku", "code"))
                if code not in item_status:
                    reason = "unknown_item"
                elif item_status[code] == "retired":
                    reason = "retired_item"
            if not reason:
                for name, value in row.items():
                    if name.startswith("__"):
                        continue
                    if is_sentinel(value):
                        reason = "sentinel"
                        break
            if reason:
                rejects.append((src["name"], uid, key, reason))
                continue
            seq_raw = get(row, "effective_seq")
            if seq_raw is None:
                continue
            if to_int(seq_raw) > cutoff:
                out_of_scope += 1
            elif to_int(get(row, "void") or 0) == 1 or ctx.lifecycle.get(uid):
                voided += 1
    ctx.rejects = rejects
    ctx.out_of_scope = out_of_scope
    ctx.void_rows = voided


def workbook_rows(ctx: Ctx):
    src = source_named(ctx, "capital_programme")
    sheets = read_xlsx_sheets(ctx.dir / src["name"])
    control, volumes = [], []
    for name, rows in sheets.items():
        if not rows:
            continue
        header = [h.strip() for h in rows[0]]
        for idx, cells in enumerate(rows[1:]):
            row = {}
            for i, col in enumerate(header):
                row[col] = cells[i] if i < len(cells) else ""
            row["__src"] = src["name"]
            row["__idx"] = idx
            if "parameter" in row:
                control.append(row)
            elif "project_id" in row:
                volumes.append(row)
    return control, volumes


# ---------------------------------------------------------------------------
# the full corrected build
# ---------------------------------------------------------------------------
def item_fallbacks(ctx: Ctx) -> dict:
    """Per item setup fallback under the runbook item_defaults block."""
    src = source_named(ctx, "contract_config")
    out = {}
    if src is None:
        return out
    section, item = None, None
    for raw in _split_lines(ctx.dir / src["name"]):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if depth == 0:
            section, item = text.rstrip(":"), None
        elif section == "item_defaults" and depth == 2 and text.endswith(":"):
            item = norm_code(text[:-1])
        elif section == "item_defaults" and item and text.startswith("setup_fallback_cents:"):
            out[item] = int(text.split(":", 1)[1].strip())
    return out


def win_map(buckets, valuefn):
    out = {}
    for key, bucket in buckets.items():
        win = winner(bucket)
        if win:
            out[key] = valuefn(win)
    return out


def bucket_win(buckets, key):
    bucket = buckets.get(key)
    return winner(bucket) if bucket else None


def live_int(buckets, key):
    win = bucket_win(buckets, key)
    return to_int(win[4]) if win else 0


def win_int(win):
    return to_int(win[4])


def win_text(win):
    return str(win[4]).strip()


def win_bps(win):
    return bps_value(win[3])


def field(*names):
    return lambda r: get(r, *names)


def code_of(*names):
    return lambda r: norm_code(get(r, *names))


def pair_of(first, second):
    return lambda r: (norm_code(get(r, first)), norm_code(get(r, second)))


def adj_id(row):
    return str(get(row, "adj_id")).strip()


def amend_id(row):
    return str(get(row, "amend_id")).strip()


def amend_sign(row):
    return -1 if str(get(row, "sign")).strip() == "credit" else 1


def pick(st, role, keyfn, valuefn):
    ctx = st["ctx"]
    return classify(ctx, ctx.by_role.get(role, []), keyfn, valuefn, st["cutoff"])


def read_settings(data_dir):
    ctx = load(Path(data_dir))
    cfg = config(ctx)
    fallback = item_fallbacks(ctx)
    cutoff = int(cfg["plan_sequence_cutoff"])
    st = {"ctx": ctx, "cutoff": cutoff, "fallback": fallback,
          "grid": int(cfg["capex_grid_cents"]),
          "default_setup": int(cfg["default_setup_cents"]),
          "min_handling": int(cfg["minimum_handling_cents"])}
    ctx.cutoff = cutoff
    ctx.lifecycle = lifecycle_state(ctx, cutoff)
    return st


def read_horizon(st):
    ordinals = win_map(pick(st, "period_order", code_of("period_code", "period"),
                            field("fiscal_ordinal")), win_int)
    st["ordinals"] = ordinals
    st["horizon"] = sorted(ordinals, key=lambda p: (ordinals[p], p))
    st["date_period"] = {str(get(row, "date")).strip(): norm_code(get(row, "period_code"))
                         for row in st["ctx"].by_role.get("calendar", [])}


def read_registries(st):
    item_status = win_map(pick(st, "item_status", code_of("code", "item"),
                               field("status")), win_text)
    st["item_status"] = item_status
    st["items"] = sorted(k for k, v in item_status.items() if v != "retired")
    st["families"] = win_map(pick(st, "item_family", code_of("item", "code"),
                                  field("family")), win_text)
    plant_status = win_map(pick(st, "plant_status", pair_of("plant", "period"),
                                field("status")), win_text)
    st["plant_status"] = plant_status
    st["plants"] = sorted({p for (p, _t) in plant_status})
    st["plant_zone"] = win_map(pick(st, "plant_zone", code_of("plant"), field("zone")),
                               win_text)
    st["zone_uplift"] = win_map(pick(st, "zone_tariff", lambda r: str(get(r, "zone")).strip(),
                                     field("uplift_value")), win_bps)
    st["shift"] = win_map(pick(st, "shift_pattern", code_of("plant"), field("shift_value")),
                          win_bps)
    st["derate"] = win_map(pick(st, "holiday_derate", code_of("period"),
                                field("derate_value")), win_bps)
    fx_b = pick(st, "fx_rate", lambda r: "FX", field("usd_per_eur_micros"))
    st["fx_micros"] = to_int(winner(fx_b["FX"])[4])


def read_documents(st):
    ctx, cutoff = st["ctx"], st["cutoff"]
    sched = doc_params(ctx, "penalty_schedule", read_pdf_lines)
    memo = doc_params(ctx, "energy_memo", read_docx_paragraphs)
    sched_b = classify(ctx, sched, lambda r: r["name"], lambda r: r["value"], cutoff)
    memo_b = classify(ctx, memo, lambda r: r["name"], lambda r: r["value"], cutoff)
    st["shortfall_rate"] = to_int(winner(sched_b["shortfall_penalty_per_unit"])[4])
    st["holding_bps"] = bps_value(winner(sched_b["holding_rate"])[3])
    st["energy_surcharge"] = bps_value(winner(memo_b["energy_surcharge"])[3])
    control_rows, volume_rows = workbook_rows(ctx)
    ctrl_b = classify(ctx, control_rows, lambda r: str(r.get("parameter", "")).strip(),
                      lambda r: r.get("value"), cutoff)
    budget_win = winner(ctrl_b["capital_budget"])
    st["budget"] = scaled_amount({"value": budget_win[4], "unit": budget_win[3].get("unit")})
    vol_b = classify(ctx, volume_rows, lambda r: norm_code(r.get("project_id")),
                     lambda r: r.get("committed_volume_units"), cutoff)
    st["volumes"] = win_map(vol_b, win_int)


def demand_period(st, row):
    period = get(row, "period_code", "period")
    if period is None:
        return st["date_period"].get(str(get(row, "date")).strip())
    return norm_code(period)


def demand_buckets(st):
    ctx, item_status = st["ctx"], st["item_status"]
    rows = ctx.by_role.get("demand", []) + ctx.by_role.get("demand_overlay", [])
    buckets = {}
    for row in rows:
        code = norm_code(get(row, "item_code", "item", "sku", "code"))
        period = demand_period(st, row)
        raw = get(row, "units", "qty", "planned_units", "units_dz")
        uid_text = str(get(row, "row_uid")).strip()
        if item_status.get(code, "retired") == "retired" or is_sentinel(raw):
            continue
        seq = to_int(get(row, "effective_seq"))
        bucket = buckets.setdefault((code, period), Bucket())
        if seq > st["cutoff"]:
            bucket.cut = True
        elif to_int(get(row, "void") or 0) == 1 or ctx.lifecycle.get(uid_text):
            bucket.voided = True
        else:
            units = to_int(raw) * (12 if "units_dz" in row else 1)
            bucket.live.append((to_int(get(row, "rev") or 1), seq, row["__idx"], row, units))
    return buckets


def read_demand(st):
    buckets = demand_buckets(st)
    demand = {}
    for it in st["items"]:
        for t in st["horizon"]:
            win = bucket_win(buckets, (it, t))
            demand[(it, t)] = win[4] if win else 0
    st["demand"] = demand
    audit_pass(st["ctx"], st["cutoff"], st["item_status"], st["date_period"])


def read_cost_tables(st):
    ctx = st["ctx"]
    item_period = pair_of("item", "period")
    tab = {"base": pick(st, "unit_cost", item_period, field("amount")),
           "over": pick(st, "cost_override", item_period, field("amount"))}
    tab["amend_totals"], tab["amend_marks"] = accumulate(
        ctx, ctx.by_role.get("cost_amendment", []), item_period, field("amount"),
        st["cutoff"], idfn=amend_id, signfn=amend_sign)
    tab["energy"] = win_map(pick(st, "energy_index", code_of("period"),
                                 field("index_value")), win_bps)
    tab["setup"] = pick(st, "setup_cost", item_period, field("amount"))
    return tab


def bucket_marks(bucket):
    marks = set()
    if bucket and bucket.cut:
        marks.add("CUT")
    if bucket and bucket.voided:
        marks.add("VOI")
    return marks


def base_amount(st, win, mark):
    if not win:
        return 0
    row = win[3]
    ccy = str(get(row, "ccy") or "USD").strip()
    scale = str(get(row, "scale") or "cents").strip()
    amount = to_int(win[4])
    if scale == "kcents":
        amount *= 1000
        mark.add("KC")
    if ccy == "EUR":
        amount = rhu(amount * st["fx_micros"], 1000000)
        mark.add("FX")
    return amount


def item_period_cost(st, tab, key):
    mark = set()
    bucket = tab["base"].get(key)
    value = base_amount(st, winner(bucket) if bucket else None, mark)
    mark |= bucket_marks(bucket)
    value += tab["amend_totals"].get(key, 0)
    mark |= tab["amend_marks"].get(key, set())
    over = tab["over"].get(key)
    owin = winner(over) if over else None
    if owin:
        value = to_int(owin[4])
        mark.add("OVR")
    mark |= bucket_marks(over)
    bps = tab["energy"].get(key[1], 0) + st["energy_surcharge"]
    uplift = rhu(value * bps, 10000)
    if uplift:
        mark.add("ENR")
    return value + uplift, bps, "+".join(sorted(mark))


def price_items(st):
    tab = read_cost_tables(st)
    for name in ("unit_cost", "setup_cost", "holding_cost", "flags", "energy_applied"):
        st[name] = {}
    for it in st["items"]:
        for t in st["horizon"]:
            key = (it, t)
            value, bps, flag = item_period_cost(st, tab, key)
            st["unit_cost"][key] = value
            st["energy_applied"][key] = bps
            st["flags"][key] = flag
            swin = bucket_win(tab["setup"], key)
            st["setup_cost"][key] = (scaled_amount(swin[3]) if swin
                                     else st["fallback"].get(it, st["default_setup"]))
            st["holding_cost"][key] = rhu(value * st["holding_bps"], 10000)


def read_plant_tables(st):
    ctx = st["ctx"]
    plant_period = pair_of("plant", "period")
    tab = {"capbase": pick(st, "capacity_base", plant_period, field("base_capacity_units"))}
    tab["cap_adj"], _ = accumulate(
        ctx, ctx.by_role.get("capacity_adjustment", []), plant_period,
        field("delta_units"), st["cutoff"], idfn=adj_id)
    tab["handbase"] = pick(st, "handling_base", plant_period,
                           field("handling_cents_per_unit"))
    tab["hand_adj"], _ = accumulate(
        ctx, ctx.by_role.get("handling_adjustment", []), plant_period,
        field("delta_cents"), st["cutoff"], idfn=adj_id)
    return tab


def rate_plants(st):
    tab = read_plant_tables(st)
    st["capacity"], st["handling_pre"] = {}, {}
    for j in st["plants"]:
        for t in st["horizon"]:
            key = (j, t)
            total = live_int(tab["capbase"], key) + tab["cap_adj"].get(key, 0)
            value = rhu(rhu(total * st["shift"].get(j, 10000), 10000)
                        * st["derate"].get(t, 10000), 10000)
            if st["plant_status"].get(key) == "mothballed":
                value = 0
            st["capacity"][key] = max(0, value)
            htotal = live_int(tab["handbase"], key) + tab["hand_adj"].get(key, 0)
            uplift = st["zone_uplift"].get(st["plant_zone"].get(j, ""), 0)
            st["handling_pre"][key] = rhu(htotal * (10000 + uplift), 10000)


def retrofit_candidates(st):
    proj_b = pick(st, "retrofit_project", code_of("project_id"), field("status"))
    projects = sorted(k for k, b in proj_b.items() if winner(b))
    project_plant = {key: norm_code(get(winner(proj_b[key])[3], "plant")) for key in projects}
    elig_b = pick(st, "retrofit_eligibility", code_of("project_id"), field("eligible"))
    capex_b = pick(st, "retrofit_capex", code_of("project_id"), field("amount"))
    save_b = pick(st, "retrofit_savings", code_of("project_id"), field("savings_value"))
    candidates = []
    for pid in projects:
        ewin = bucket_win(elig_b, pid)
        cwin = bucket_win(capex_b, pid)
        swin = bucket_win(save_b, pid)
        if not ewin or str(ewin[4]).strip() != "yes" or not cwin or not swin:
            continue
        saving = to_int(swin[4])
        if str(get(swin[3], "ccy") or "USD").strip() == "EUR":
            saving = rhu(saving * st["fx_micros"], 1000000)
        volume = st["volumes"].get(pid, 0)
        candidates.append({"id": pid, "plant": project_plant[pid],
                           "capex": scaled_amount(cwin[3]), "saving": saving,
                           "volume": volume, "value": saving * volume})
    candidates.sort(key=lambda c: c["id"])
    return candidates


def knapsack(candidates, grid, budget_cents):
    cap_units = budget_cents // grid
    best = [(0, 0, 0)] * (cap_units + 1)
    for bit, cand in enumerate(candidates):
        need = cand["capex"] // grid
        if need > cap_units:
            continue
        for c in range(cap_units, need - 1, -1):
            pv, pc, pm = best[c - need]
            nv = pv + cand["value"]
            nc = pc + cand["capex"]
            nm = pm | (1 << bit)
            cv, cc, cm = best[c]
            if (nv, -nc, -nm) > (cv, -cc, -cm):
                best[c] = (nv, nc, nm)
    return best[cap_units]


def select_retrofits(st):
    candidates = retrofit_candidates(st)
    grid = st["grid"]
    sel_value, sel_capex, sel_mask = knapsack(candidates, grid, st["budget"])
    selected = [candidates[b]["id"] for b in range(len(candidates)) if sel_mask >> b & 1]
    plant_saving = {}
    for cand in candidates:
        if cand["id"] in selected:
            plant_saving[cand["plant"]] = plant_saving.get(cand["plant"], 0) + cand["saving"]
    handling = {}
    for key, rate in st["handling_pre"].items():
        handling[key] = max(st["min_handling"], rate - plant_saving.get(key[0], 0))
    st.update(candidates=candidates, selected=selected, sel_value=sel_value,
              sel_capex=sel_capex, handling=handling,
              knapsack=lambda budget_cents: knapsack(candidates, grid, budget_cents))


def lot_block(series, a, b):
    d, c, k, h = series
    total = sum(d[a:b])
    if total == 0:
        return 0, 0
    cost = k[a] + c[a] * total
    carry = 0
    for u in range(a, b):
        carry += d[u] * sum(h[a:u])
    return cost + carry, total


def lot_cuts(series, span):
    best = [0] + [None] * span
    arg = [0] * (span + 1)
    for b in range(1, span + 1):
        for a in range(0, b):
            if best[a] is None:
                continue
            cost, _q = lot_block(series, a, b)
            cand = best[a] + cost
            if best[b] is None or cand < best[b]:
                best[b] = cand
                arg[b] = a
    cuts = []
    pos = span
    while pos > 0:
        cuts.append((arg[pos], pos))
        pos = arg[pos]
    cuts.reverse()
    return cuts, best[span]


def size_lots(st):
    horizon = st["horizon"]
    span = len(horizon)
    produced, inventory, opens, item_cost = {}, {}, {}, {}
    for it in st["items"]:
        series = tuple([st[name][(it, t)] for t in horizon]
                       for name in ("demand", "unit_cost", "setup_cost", "holding_cost"))
        d = series[0]
        cuts, item_cost[it] = lot_cuts(series, span)
        qty = [0] * span
        for a, b in cuts:
            _cost, total = lot_block(series, a, b)
            qty[a] = total
            if total:
                opens[(it, horizon[a])] = [horizon[x] for x in range(a, b) if d[x] > 0]
        inv = 0
        for idx in range(span):
            produced[(it, horizon[idx])] = qty[idx]
            inv = inv + qty[idx] - d[idx]
            inventory[(it, horizon[idx])] = inv
    st.update(produced=produced, inventory=inventory, opens=opens, item_cost=item_cost)


def source_period(st, t):
    produced, handling = st["produced"], st["handling"]
    queue = [(it, produced[(it, t)]) for it in st["items"] if produced[(it, t)] > 0]
    need = sum(q for _i, q in queue)
    pos = 0
    for j in sorted(st["plants"], key=lambda p: (handling[(p, t)], p)):
        take = min(need, st["capacity"][(j, t)])
        st["assigned"][(j, t)] = take
        need -= take
        left = take
        while left > 0 and pos < len(queue):
            it, avail = queue[pos]
            use = min(left, avail)
            st["alloc_rows"].append((t, j, it, use, handling[(j, t)]))
            left -= use
            if use == avail:
                pos += 1
            else:
                queue[pos] = (it, avail - use)
    return need


def source_lots(st):
    st["alloc_rows"], st["assigned"], st["shortfall"] = [], {}, {}
    for t in st["horizon"]:
        st["shortfall"][t] = source_period(st, t)


def total_costs(st):
    items, horizon = st["items"], st["horizon"]
    produced, inventory = st["produced"], st["inventory"]
    st["production_total"] = sum(st["unit_cost"][(i, t)] * produced[(i, t)]
                                 for i in items for t in horizon)
    st["setup_total"] = sum(st["setup_cost"][(i, t)] for (i, t) in st["opens"])
    st["holding_total"] = sum(st["holding_cost"][(i, t)] * inventory[(i, t)]
                              for i in items for t in horizon if inventory[(i, t)] > 0)
    st["handling_total"] = sum(units * rate for (_t, _j, _i, units, rate) in st["alloc_rows"])
    st["shortfall_cost"] = sum(st["shortfall"][t] * st["shortfall_rate"] for t in horizon)
    st["total_objective"] = (st["production_total"] + st["setup_total"] + st["holding_total"]
                             + st["handling_total"] + st["shortfall_cost"] + st["sel_capex"])


BUILD_STAGES = (read_horizon, read_registries, read_documents, read_demand, price_items,
                rate_plants, select_retrofits, size_lots, source_lots, total_costs)


def build(data_dir):
    st = read_settings(data_dir)
    for stage in BUILD_STAGES:
        stage(st)
    return st


# ---------------------------------------------------------------------------
# artifact rendering
# ---------------------------------------------------------------------------
def jdump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def jlines(objs) -> str:
    return "".join(json.dumps(o, sort_keys=True, separators=(",", ":")) + "\n" for o in objs)


def csv_text(header, rows) -> str:
    out = [",".join(header)]
    for row in rows:
        out.append(",".join(str(c) for c in row))
    return "\n".join(out) + "\n"


def ratio_better(a, b) -> bool:
    # a is better than b when value/capex is larger, ties on lower id
    left = a["value"] * b["capex"]
    right = b["value"] * a["capex"]
    if left != right:
        return left > right
    return a["id"] < b["id"]


def render_coefficients(S):
    rows = []
    for it in S["items"]:
        for t in S["horizon"]:
            rows.append({
                "demand_units": S["demand"][(it, t)],
                "energy_bps_applied": S["energy_applied"][(it, t)],
                "fiscal_ordinal": S["ordinal_of"][t],
                "flags": S["flags"][(it, t)],
                "holding_cost_cents": S["holding_cost"][(it, t)],
                "item": it,
                "period": t,
                "setup_cost_cents": S["setup_cost"][(it, t)],
                "unit_cost_cents": S["unit_cost"][(it, t)],
            })
    return {"corrected_coefficients.jsonl": jlines(rows)}


def render_objective(S):
    return {"objective.json": jdump({
        "capex_cents": S["sel_capex"],
        "handling_cost_cents": S["handling_total"],
        "holding_cost_cents": S["holding_total"],
        "items_in_scope": len(S["items"]),
        "periods_in_horizon": len(S["horizon"]),
        "plants_in_scope": len(S["plants"]),
        "production_cost_cents": S["production_total"],
        "setup_cost_cents": S["setup_total"],
        "shortfall_penalty_cents": S["shortfall_cost"],
        "total_demand_units": sum(S["demand"].values()),
        "total_objective_cents": S["total_objective"],
        "total_produced_units": sum(S["produced"].values()),
        "total_shortfall_units": sum(S["shortfall"].values()),
    })}


def render_plan(S):
    rows = []
    for it in S["items"]:
        for t in S["horizon"]:
            if (it, t) in S["opens"]:
                rows.append({
                    "covers_periods": S["opens"][(it, t)],
                    "fiscal_ordinal": S["ordinal_of"][t],
                    "item": it,
                    "period": t,
                    "produced_units": S["produced"][(it, t)],
                    "production_cost_cents": S["unit_cost"][(it, t)] * S["produced"][(it, t)],
                    "setup_cost_cents": S["setup_cost"][(it, t)],
                })
    return {"optimal_plan.jsonl": jlines(rows)}


def render_schedules(S):
    sched_rows, hold_rows = [], []
    for it in S["items"]:
        cumulative = 0
        for t in S["horizon"]:
            inv = S["inventory"][(it, t)]
            charge = S["holding_cost"][(it, t)] * inv if inv > 0 else 0
            cumulative += charge
            sched_rows.append([it, t, S["ordinal_of"][t], S["demand"][(it, t)],
                               S["produced"][(it, t)], inv])
            hold_rows.append([it, t, S["ordinal_of"][t], inv, S["holding_cost"][(it, t)],
                              charge, cumulative])
    return {
        "production_schedule.csv": csv_text(
            ["item", "period", "fiscal_ordinal", "demand_units", "produced_units",
             "ending_inventory_units"], sched_rows),
        "holding_profile.csv": csv_text(
            ["item", "period", "fiscal_ordinal", "ending_inventory_units", "holding_rate_cents",
             "period_holding_cents", "cumulative_holding_cents"], hold_rows),
    }


def render_sourcing(S):
    ordinal_of = S["ordinal_of"]
    alloc = [[t, ordinal_of[t], j, it, units, rate, units * rate]
             for (t, j, it, units, rate) in S["alloc_rows"]]
    util_rows = []
    for j in S["plants"]:
        for t in S["horizon"]:
            cap = S["capacity"][(j, t)]
            got = S["assigned"].get((j, t), 0)
            bps = rhu(got * 10000, cap) if cap else 0
            util_rows.append([j, t, ordinal_of[t], cap, got, cap - got, bps])
    short_rows = []
    for t in S["horizon"]:
        required = sum(S["produced"][(it, t)] for it in S["items"])
        cap = sum(S["capacity"][(j, t)] for j in S["plants"])
        short = S["shortfall"][t]
        short_rows.append([t, ordinal_of[t], required, cap, short, S["shortfall_rate"],
                           short * S["shortfall_rate"]])
    return {
        "sourcing_allocation.csv": csv_text(
            ["period", "fiscal_ordinal", "plant", "item", "units", "handling_rate_cents",
             "handling_cost_cents"], alloc),
        "plant_utilization.csv": csv_text(
            ["plant", "period", "fiscal_ordinal", "capacity_units", "assigned_units",
             "idle_units", "utilisation_bps"], util_rows),
        "shortfall_ledger.csv": csv_text(
            ["period", "fiscal_ordinal", "required_units", "capacity_units", "shortfall_units",
             "penalty_rate_cents", "penalty_cents"], short_rows),
    }


def render_capital(S):
    candidates, selected, slack = S["candidates"], S["selected"], S["slack"]
    return {
        "retrofit_selection.json": jdump({
            "budget_cents": S["budget"],
            "candidate_project_ids": [c["id"] for c in candidates],
            "capex_grid_cents": S["grid"],
            "eligible_project_count": len(candidates),
            "rejected_project_ids": [c["id"] for c in candidates if c["id"] not in selected],
            "selected_capex_cents": S["sel_capex"],
            "selected_project_ids": selected,
            "selected_value_cents": S["sel_value"],
        }),
        "budget_utilization.json": jdump({
            "budget_binding": S["marginal"] > 0,
            "budget_cents": S["budget"],
            "capex_cents": S["sel_capex"],
            "slack_cents": slack,
            "slack_grid_units": slack // S["grid"],
            "utilisation_bps": rhu(S["sel_capex"] * 10000, S["budget"]) if S["budget"] else 0,
        }),
    }


def cost_parts(S, it, periods):
    prod = sum(S["unit_cost"][(it, t)] * S["produced"][(it, t)] for t in periods)
    setup = sum(S["setup_cost"][(it, t)] for t in periods if (it, t) in S["opens"])
    hold = sum(S["holding_cost"][(it, t)] * S["inventory"][(it, t)]
               for t in periods if S["inventory"][(it, t)] > 0)
    return prod, setup, hold


def render_period_costs(S):
    period_costs = {}
    for t in S["horizon"]:
        parts = [cost_parts(S, it, (t,)) for it in S["items"]]
        prod = sum(p[0] for p in parts)
        setup = sum(p[1] for p in parts)
        hold = sum(p[2] for p in parts)
        handle = sum(units * rate for (tt, _j, _i, units, rate) in S["alloc_rows"] if tt == t)
        short = S["shortfall"][t] * S["shortfall_rate"]
        period_costs[t] = {
            "handling_cost_cents": handle,
            "holding_cost_cents": hold,
            "production_cost_cents": prod,
            "setup_cost_cents": setup,
            "shortfall_penalty_cents": short,
            "total_cents": prod + setup + hold + handle + short,
        }
    return {"period_costs.json": jdump(period_costs)}


def render_item_summary(S):
    horizon = S["horizon"]
    item_summary = {}
    for it in S["items"]:
        prod, setup, hold = cost_parts(S, it, horizon)
        item_summary[it] = {
            "demand_units": sum(S["demand"][(it, t)] for t in horizon),
            "family": S["families"].get(it, ""),
            "holding_cost_cents": hold,
            "produced_units": sum(S["produced"][(it, t)] for t in horizon),
            "production_cost_cents": prod,
            "setup_cost_cents": setup,
            "setup_count": sum(1 for t in horizon if (it, t) in S["opens"]),
            "total_cents": prod + setup + hold,
        }
    return {"item_summary.json": jdump(item_summary)}


def render_bindings(S):
    full_cap, zero_cap = [], []
    for j in S["plants"]:
        for t in S["horizon"]:
            cap = S["capacity"][(j, t)]
            if cap == 0:
                zero_cap.append([j, t])
            elif S["assigned"].get((j, t), 0) == cap:
                full_cap.append([j, t])
    short_periods = [t for t in S["horizon"] if S["shortfall"][t] > 0]
    return {"binding_constraints.json": jdump({
        "binding_count": len(full_cap) + len(short_periods) + (1 if S["marginal"] > 0 else 0),
        "budget_binding": S["marginal"] > 0,
        "full_capacity_plant_periods": full_cap,
        "shortfall_periods": short_periods,
        "zero_capacity_plant_periods": zero_cap,
    })}


def idle_rates(S, t):
    return [S["handling"][(j, t)] for j in S["plants"]
            if S["capacity"][(j, t)] - S["assigned"].get((j, t), 0) > 0]


def zero_inventory_entry(S, it):
    entering = 0
    for t in S["horizon"]:
        if S["produced"][(it, t)] > 0 and entering != 0:
            return False
        entering = S["inventory"][(it, t)]
    return True


def no_cheaper_idle(S, t):
    used = [S["handling"][(j, t)] for j in S["plants"] if S["assigned"].get((j, t), 0) > 0]
    idle = idle_rates(S, t)
    return not (used and idle and min(idle) < max(used))


def render_certificate(S):
    selected = S["selected"]
    fits = not any(c["id"] not in selected and c["value"] > 0 and c["capex"] <= S["slack"]
                   for c in S["candidates"])
    recon = all(sum(cost_parts(S, it, S["horizon"])) == S["item_cost"][it] for it in S["items"])
    produced = sum(S["produced"].values())
    covered = (produced == sum(S["demand"].values())
               and sum(S["assigned"].values()) + sum(S["shortfall"].values()) == produced)
    return {"optimality_certificate.json": jdump({
        "all_demand_covered_or_charged": covered,
        "capital_no_unfunded_candidate_fits": fits,
        "lot_sizing_reconstructed_cost_matches": recon,
        "lot_sizing_zero_inventory_property": all(zero_inventory_entry(S, it)
                                                  for it in S["items"]),
        "sourcing_no_cheaper_idle_capacity": all(no_cheaper_idle(S, t) for t in S["horizon"]),
        "total_objective_cents": S["total_objective"],
    })}


def render_sensitivity(S):
    top = None
    for cand in S["candidates"]:
        if cand["id"] in S["selected"] or cand["capex"] <= 0:
            continue
        if top is None or ratio_better(cand, top):
            top = cand
    next_unit = {}
    for t in S["horizon"]:
        idle = idle_rates(S, t)
        next_unit[t] = min(idle) if idle else S["shortfall_rate"]
    return {"sensitivity_report.json": jdump({
        "budget_binding": S["marginal"] > 0,
        "budget_grid_unit_cents": S["grid"],
        "marginal_value_of_one_grid_unit_cents": S["marginal"],
        "next_unit_cost_by_period": next_unit,
        "top_unfunded_capex_cents": top["capex"] if top else 0,
        "top_unfunded_project_id": top["id"] if top else "",
    })}


def incumbent_report(S):
    ctx = S["ctx"]
    rep_src = source_named(ctx, "incumbent_report")
    report = json.loads((ctx.dir / rep_src["name"]).read_text(encoding="utf-8"))
    inc_projects = sorted(str(p) for p in report["selected_projects"])
    return report, int(report["published_total_objective_cents"]), inc_projects


def render_incumbent(S):
    report, inc_total, inc_projects = incumbent_report(S)
    stage = report["stage_totals_cents"]
    selected = S["selected"]
    components = {
        "capex_cents": S["sel_capex"],
        "handling_cost_cents": S["handling_total"],
        "holding_cost_cents": S["holding_total"],
        "production_cost_cents": S["production_total"],
        "setup_cost_cents": S["setup_total"],
        "shortfall_penalty_cents": S["shortfall_cost"],
    }
    return {"incumbent_delta.json": jdump({
        "component_deltas": {k: v - int(stage.get(k, 0)) for k, v in components.items()},
        "corrected_selected_project_ids": selected,
        "corrected_total_objective_cents": S["total_objective"],
        "delta_cents": S["total_objective"] - inc_total,
        "incumbent_selected_project_ids": inc_projects,
        "incumbent_total_objective_cents": inc_total,
        "projects_added": [p for p in selected if p not in inc_projects],
        "projects_dropped": [p for p in inc_projects if p not in selected],
    })}


def render_corrections(S):
    ctx = S["ctx"]
    dump_src = source_named(ctx, "incumbent_plan")
    inc_cost = {}
    for row in read_ndjson(ctx.dir / dump_src["name"]):
        inc_cost[(norm_code(row["item"]), norm_code(row["period"]))] = int(row["unit_cost_cents"])
    rows = []
    for it in S["items"]:
        for t in S["horizon"]:
            old = inc_cost.get((it, t))
            new = S["unit_cost"][(it, t)]
            if old is not None and old != new:
                rows.append([it, t, old, new, new - old, S["flags"][(it, t)]])
    return {"coefficient_corrections.csv": csv_text(
        ["item", "period", "incumbent_unit_cost_cents", "corrected_unit_cost_cents",
         "delta_cents", "flags"], rows)}


def sorted_rejects(ctx):
    return sorted(set(ctx.rejects), key=lambda r: (r[0], r[1]))


def render_accounting(S):
    ctx = S["ctx"]
    sources, mismatches = [], []
    for src in ctx.manifest:
        seen = physical_rows(ctx.dir / src["name"], src["fmt"])
        sources.append({"authority": src["authority"], "fmt": src["fmt"], "name": src["name"],
                        "record_count_declared": src["record_count"], "role": src["role"],
                        "rows_seen": seen})
        if seen != src["record_count"]:
            mismatches.append(src["name"])
    rejects = sorted_rejects(ctx)
    return {
        "data_quality.json": jdump({
            "count_mismatches": sorted(mismatches),
            "sources": sources,
            "totals": {
                "out_of_scope_rows": ctx.out_of_scope,
                "rejected_rows": len(rejects),
                "sources_seen": len(sources),
                "void_rows": ctx.void_rows,
            },
        }),
        "rejected_records.csv": csv_text(
            ["source", "row_uid", "key", "reason"], [list(r) for r in rejects]),
    }


def render_summary(S):
    _report, inc_total, _projects = incumbent_report(S)
    figures = [
        ("corrected_total_objective_cents", S["total_objective"]),
        ("incumbent_total_objective_cents", inc_total),
        ("delta_cents", S["total_objective"] - inc_total),
        ("selected_capex_cents", S["sel_capex"]),
        ("budget_cents", S["budget"]),
        ("total_shortfall_units", sum(S["shortfall"].values())),
        ("shortfall_penalty_cents", S["shortfall_cost"]),
        ("items_in_scope", len(S["items"])),
        ("rejected_rows", len(sorted_rejects(S["ctx"]))),
    ]
    lines = ["# Replan Audit Summary", ""]
    lines.extend("- %s: %d" % (k, v) for k, v in figures)
    lines.append("")
    lines.append("Selected projects: " + ", ".join(S["selected"]))
    return {
        "reconciliation.txt": "".join("%s=%d\n" % (k, v) for k, v in figures),
        "audit_summary.md": "\n".join(lines) + "\n",
    }


RENDERERS = (render_coefficients, render_objective, render_plan, render_schedules,
             render_sourcing, render_capital, render_period_costs, render_item_summary,
             render_bindings, render_certificate, render_sensitivity, render_incumbent,
             render_corrections, render_accounting, render_summary)


def compute(data_dir):
    S = build(data_dir)
    S["ordinal_of"] = {t: idx + 1 for idx, t in enumerate(S["horizon"])}
    S["slack"] = S["budget"] - S["sel_capex"]
    S["marginal"] = S["knapsack"](S["budget"] + S["grid"])[0] - S["sel_value"]
    out = {}
    for render in RENDERERS:
        out.update(render(S))
    return out


def write_outputs(data_dir, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in compute(data_dir).items():
        (out_dir / name).write_text(text, encoding="utf-8")


def _main():
    import os
    import sys
    argv = sys.argv[1:]
    input_dir = Path(argv[0]) if argv else Path(os.environ.get("INPUT_DIR", "/app/data"))
    output_dir = Path(argv[1]) if len(argv) > 1 else Path(os.environ.get("OUTPUT_DIR", "/app/out"))
    write_outputs(input_dir, output_dir)


if __name__ == "__main__":
    _main()
