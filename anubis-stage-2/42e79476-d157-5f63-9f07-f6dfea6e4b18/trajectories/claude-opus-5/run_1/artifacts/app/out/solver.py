#!/usr/bin/env python3
"""Network replan optimizer.

Rebuilds every cost coefficient from the shipped registers, re-solves the three
stage plan the operating handbook defines (capital selection, lot sizing,
sourcing) and writes the full artifact set.

Usage:  python3 solver.py <DATA_DIR> <OUT_DIR>
"""

import json
import os
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from collections import defaultdict

# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------

DELIM = {"csv": ",", "tsv": "\t", "psv": "|"}
SWEEP_FMTS = {"csv", "tsv", "psv", "jsonl", "ndjson", "json", "xml", "txt"}

_NUM_TAIL = re.compile(r"^(.*?)(\d+)$")


def rhu(num, den):
    """round_half_up(num / den), away from zero.  den > 0."""
    if num < 0:
        return -((-2 * num + den) // (2 * den))
    return (2 * num + den) // (2 * den)


def norm_code(value, pad=2):
    if value is None:
        return ""
    s = str(value).strip().upper().replace("-", "").replace("_", "")
    s = "".join(s.split())
    m = _NUM_TAIL.match(s)
    if m:
        head, tail = m.group(1), m.group(2)
        s = head + tail.zfill(pad)
    return s


def as_text(value):
    return "" if value is None else str(value).strip()


def to_int(value):
    return int(str(value).strip())


# --------------------------------------------------------------------------
# raw readers, one per physical format
# --------------------------------------------------------------------------


def read_delimited(path, sep):
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    header = lines[0].split(sep)
    rows = []
    for line in lines[1:]:
        if line.strip() == "":
            continue
        rows.append(dict(zip(header, line.split(sep))))
    return rows


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_json_records(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)["records"]


def read_xml(path):
    return [dict(child.attrib) for child in ET.parse(path).getroot()]


def read_text_pipe(path):
    """Plain text register: a header comment names the fixed column order."""
    header = None
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                if header is None and "column order" in line:
                    header = line.split(":", 1)[1].strip().split("|")
                continue
            rows.append(dict(zip(header, line.split("|"))))
    return rows


def read_text_lines(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            body = line.strip()
            if body and not body.startswith("#"):
                out.append(line.rstrip("\n"))
    return out


def read_pdf_records(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", blob, re.S):
        try:
            text = zlib.decompress(m.group(1)).decode("latin-1")
        except zlib.error:
            continue
        for line in text.split("\n"):
            line = line.strip()
            mm = re.match(r"\((.*)\)\s*Tj", line)
            if mm and mm.group(1).startswith("R|"):
                out.append(mm.group(1))
    return out


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx_records(path):
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for para in root.iter(_W + "p"):
        text = "".join(t.text or "" for t in para.iter(_W + "t"))
        if text.startswith("R|"):
            out.append(text)
    return out


_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def read_xlsx(path):
    zf = zipfile.ZipFile(path)
    book = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels}
    sheets_meta = [(s.get("name"), target[s.get(_R + "id")])
                   for s in book.iter(_X + "sheet")]
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        ss = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in ss.iter(_X + "si"):
            shared.append("".join(t.text or "" for t in si.iter(_X + "t")))
    sheets = {}
    for name, rel in sheets_meta:
        member = rel if rel.startswith("xl/") else "xl/" + rel.lstrip("/")
        root = ET.fromstring(zf.read(member))
        grid = []
        for row in root.iter(_X + "row"):
            vals = []
            for cell in row.iter(_X + "c"):
                kind = cell.get("t")
                inline = cell.find(_X + "is")
                node = cell.find(_X + "v")
                if kind == "inlineStr" and inline is not None:
                    vals.append("".join(t.text or "" for t in inline.iter(_X + "t")))
                elif kind == "s" and node is not None:
                    vals.append(shared[int(node.text)])
                else:
                    vals.append(node.text if node is not None else "")
            grid.append(vals)
        sheets[name] = grid
    return sheets


def read_sqlite_tables(path):
    con = sqlite3.connect(path)
    tables = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' "
        "and name not like 'sqlite_%'")]
    out = {}
    for name in tables:
        cur = con.execute('select * from "%s"' % name)
        cols = [d[0] for d in cur.description]
        out[name] = [dict(zip(cols, r)) for r in cur]
    con.close()
    return out


# --------------------------------------------------------------------------
# the export set
# --------------------------------------------------------------------------


class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.manifest = []          # list of dicts from the sources table
        self.by_role = defaultdict(list)
        self.rows = {}              # source name -> list of row dicts
        self.counts = {}            # source name -> physical row count
        self._discover()

    def path(self, name):
        return os.path.join(self.dir, name)

    def _discover(self):
        manifest_name = None
        for name in sorted(os.listdir(self.dir)):
            if not name.lower().endswith((".db", ".sqlite")):
                continue
            tables = read_sqlite_tables(self.path(name))
            if "sources" in tables:
                manifest_name = name
                self.manifest = tables["sources"]
                self.manifest_tables = tables
                break
        if manifest_name is None:
            raise SystemExit("no source manifest found")
        self.manifest_name = manifest_name
        self.manifest.sort(key=lambda r: r["name"])
        for entry in self.manifest:
            self.by_role[entry["role"]].append(entry)

    def sources(self, role):
        """Primary/contract sources of a role, in canonical (name) order."""
        return [e for e in self.by_role.get(role, [])
                if e["authority"] in ("primary", "contract")]

    def load(self, name, fmt):
        if name in self.rows:
            return self.rows[name]
        p = self.path(name)
        if fmt in DELIM:
            rows = read_delimited(p, DELIM[fmt])
        elif fmt in ("jsonl", "ndjson"):
            rows = read_jsonl(p)
        elif fmt == "json":
            rows = read_json_records(p)
        elif fmt == "xml":
            rows = read_xml(p)
        elif fmt == "txt":
            rows = read_text_pipe(p) if self._is_pipe_register(p) else []
        else:
            rows = []
        self.rows[name] = rows
        return rows

    @staticmethod
    def _is_pipe_register(path):
        with open(path, "r", encoding="utf-8") as fh:
            head = fh.readline()
        return "column order" in head

    def physical_count(self, name, fmt):
        if name in self.counts:
            return self.counts[name]
        p = self.path(name)
        if fmt in DELIM or fmt in ("jsonl", "ndjson", "json", "xml"):
            n = len(self.load(name, fmt))
        elif fmt in ("txt", "md", "yaml", "yml"):
            n = len(read_text_lines(p))
        elif fmt in ("db", "sqlite"):
            n = sum(len(v) for v in read_sqlite_tables(p).values())
        elif fmt == "xlsx":
            n = sum(max(0, len(g) - 1) for g in read_xlsx(p).values())
        elif fmt == "pdf":
            n = len(read_pdf_records(p))
        elif fmt == "docx":
            n = len(read_docx_records(p))
        else:
            n = 0
        self.counts[name] = n
        return n


# --------------------------------------------------------------------------
# register machinery: sentinels, lifecycle, supersession
# --------------------------------------------------------------------------


class Registers(object):
    def __init__(self, corpus, sentinels, cutoff):
        self.c = corpus
        self.sentinels = sentinels
        self.cutoff = cutoff
        self.lifecycle = {}

    # -- loading -----------------------------------------------------------
    def role_rows(self, role):
        """All rows of a role, tagged with their canonical order."""
        out = []
        order = 0
        for entry in self.c.sources(role):
            rows = self.c.load(entry["name"], entry["fmt"])
            for idx, row in enumerate(rows):
                out.append(Row(entry["name"], idx, order, row))
                order += 1
        return out

    def is_sentinel(self, value):
        return as_text(value) in self.sentinels

    def build_lifecycle(self):
        entries = defaultdict(list)
        for row in self.role_rows("row_lifecycle"):
            seq = to_int(row.get("seq"))
            if seq > self.cutoff:
                continue
            entries[as_text(row.get("row_uid"))].append(
                (seq, row.order, as_text(row.get("action"))))
        state = {}
        marked = set()
        for uid, items in entries.items():
            items.sort()
            decision = None
            for _, _, action in items:
                if action == "void":
                    marked.add(uid)
                if action in ("void", "restore"):
                    decision = action
            if decision == "void":
                state[uid] = False
            elif decision == "restore":
                state[uid] = True
        self.lifecycle = state
        self.lifecycle_marked = marked

    def lifecycle_voided(self, uid):
        return self.lifecycle.get(uid, True) is False

    def void_marked(self, row):
        """Row carries a void marker, even if a later restore revived it."""
        v = row.get("void")
        if v is not None and as_text(v) not in ("", "0"):
            return True
        return as_text(row.get("row_uid")) in self.lifecycle_marked

    # -- classification ----------------------------------------------------
    def classify(self, row, value_fields):
        """sentinel / cut / void / live, in that precedence."""
        for field in value_fields:
            if self.is_sentinel(row.get(field)):
                return "sentinel"
        seq = row.get("effective_seq")
        if seq is not None and as_text(seq) != "":
            if to_int(seq) > self.cutoff:
                return "cut"
        voided = False
        v = row.get("void")
        if v is not None and as_text(v) not in ("", "0"):
            voided = True
        if self.lifecycle_voided(as_text(row.get("row_uid"))):
            voided = True
        return "void" if voided else "live"


class Row(object):
    __slots__ = ("source", "index", "order", "data")

    def __init__(self, source, index, order, data):
        self.source = source
        self.index = index
        self.order = order
        self.data = data

    def get(self, *names):
        for name in names:
            if name in self.data:
                return self.data[name]
        return None

    def has(self, *names):
        return any(name in self.data for name in names)

    def rev(self):
        v = self.get("rev")
        return to_int(v) if v is not None and as_text(v) != "" else 0

    def seq(self):
        v = self.get("effective_seq")
        return to_int(v) if v is not None and as_text(v) != "" else 0

    def rank(self):
        return (self.rev(), self.seq(), self.order)


def pick_winner(rows):
    best = None
    for row in rows:
        if best is None or row.rank() > best.rank():
            best = row
    return best


# --------------------------------------------------------------------------
# document registers (pdf / docx / xlsx control parameters)
# --------------------------------------------------------------------------


def param_winner(records, name, cutoff, sentinels, lifecycle_voided):
    """R|PARAM|<name>|<value>|<unit>|rev|seq|void|uid records."""
    best = None
    for order, rec in enumerate(records):
        f = rec.split("|")
        if len(f) < 9 or f[1] != "PARAM" or f[2] != name:
            continue
        value, unit, rev, seq, void, uid = f[3], f[4], f[5], f[6], f[7], f[8]
        if value.strip() in sentinels:
            continue
        if int(seq) > cutoff:
            continue
        if void.strip() not in ("", "0"):
            continue
        if lifecycle_voided(uid):
            continue
        key = (int(rev), int(seq), order)
        if best is None or key > best[0]:
            best = (key, value, unit)
    return None if best is None else (best[1], best[2])


def sheet_rows(grid):
    if not grid:
        return []
    header = grid[0]
    return [dict(zip(header, r)) for r in grid[1:]]


# --------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, sort_keys=True, indent=1)
        fh.write("\n")


def write_jsonl(path, objs):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for obj in objs:
            fh.write(json.dumps(obj, sort_keys=True, separators=(",", ":")))
            fh.write("\n")


def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(",".join(header) + "\n")
        for row in rows:
            fh.write(",".join("" if v is None else str(v) for v in row) + "\n")


# --------------------------------------------------------------------------
# main solve
# --------------------------------------------------------------------------


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: solver.py <DATA_DIR> <OUT_DIR>")
    data_dir, out_dir = argv[1], argv[2]
    corpus = Corpus(data_dir)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    # ---- contract parameters -------------------------------------------
    auth = {}
    for entry in corpus.by_role.get("authority_control", []):
        auth = read_sqlite_tables(corpus.path(entry["name"]))
        break
    control = {r["parameter"]: r["value"] for r in auth.get("cutoff_control", [])}
    sentinels = set()
    for r in auth.get("sentinel_authority", []):
        tok = r["token"]
        sentinels.add("" if tok == "<empty>" else tok)
    sentinels.add("")

    runbook = {}
    for entry in corpus.by_role.get("contract_config", []):
        runbook = parse_runbook(corpus.path(entry["name"]))
        break

    cutoff = int(runbook["control"]["plan_sequence_cutoff"])
    assert cutoff == int(control["plan_sequence_cutoff"])

    reg = Registers(corpus, sentinels, cutoff)
    reg.build_lifecycle()

    memo_records = []
    for entry in corpus.sources("energy_memo"):
        memo_records = read_docx_records(corpus.path(entry["name"]))
    got = param_winner(memo_records, "plan_sequence_cutoff", cutoff,
                       sentinels, reg.lifecycle_voided)
    if got is not None:
        assert int(got[0]) == cutoff, "memo cutoff disagrees"

    rc = runbook["control"]
    capex_grid = int(rc["capex_grid_cents"])
    default_setup = int(rc["default_setup_cents"])
    min_handling = int(rc["minimum_handling_cents"])
    item_defaults = runbook.get("item_defaults", {})
    for name, value in (("capex_grid_cents", capex_grid),
                        ("default_setup_cents", default_setup),
                        ("minimum_handling_cents", min_handling)):
        assert int(control[name]) == value, "%s disagrees" % name

    # energy surcharge, memorandum only
    surcharge_bps = int(param_winner(memo_records, "energy_surcharge", cutoff,
                                     sentinels, reg.lifecycle_voided)[0])

    # holding rate and shortfall penalty, schedule document only
    sched_records = []
    for entry in corpus.sources("penalty_schedule"):
        sched_records = read_pdf_records(corpus.path(entry["name"]))
    holding_rate_bps = int(param_winner(sched_records, "holding_rate", cutoff,
                                        sentinels, reg.lifecycle_voided)[0])
    shortfall_penalty = int(param_winner(
        sched_records, "shortfall_penalty_per_unit", cutoff, sentinels,
        reg.lifecycle_voided)[0])

    # capital programme workbook: funded envelope and committed volumes
    envelope = None
    committed_rows = []
    for entry in corpus.sources("capital_programme"):
        order = 0
        ctl = []
        for grid in read_xlsx(corpus.path(entry["name"])).values():
            for row in sheet_rows(grid):
                if "parameter" in row:
                    ctl.append(Row(entry["name"], order, order, row))
                elif "committed_volume_units" in row:
                    committed_rows.append(Row(entry["name"], order, order, row))
                order += 1
        envelope = scalar_amount(reg, ctl, "capital_budget", "value", "unit",
                                 auth)

    # ---- horizon --------------------------------------------------------
    groups = defaultdict(list)
    for row in reg.role_rows("period_order"):
        if reg.classify(row, ("fiscal_ordinal",)) != "live":
            continue
        groups[norm_code(row.get("period_code", "period"))].append(row)
    horizon = []
    for code, rows in groups.items():
        win = pick_winner(rows)
        horizon.append((to_int(win.get("fiscal_ordinal")), code,
                        as_text(win.get("fy_start"))))
    horizon.sort()
    periods = [code for _, code, _ in horizon]
    start = [c for _, c, f in horizon if f not in ("", "0")]
    if start:
        assert periods[0] == start[0], "fy_start is not ordinal one"

    # ---- item scope -----------------------------------------------------
    item_status = {}
    groups = defaultdict(list)
    for row in reg.role_rows("item_status"):
        if reg.classify(row, ("status",)) != "live":
            continue
        groups[norm_code(row.get("code", "item", "item_code"))].append(row)
    for code, rows in groups.items():
        item_status[code] = as_text(pick_winner(rows).get("status"))
    items = sorted(c for c, s in item_status.items() if s != "retired")

    families = {}
    groups = defaultdict(list)
    for row in reg.role_rows("item_family"):
        if reg.classify(row, ("family",)) != "live":
            continue
        groups[norm_code(row.get("item", "item_code", "code"))].append(row)
    for code, rows in groups.items():
        families[code] = as_text(pick_winner(rows).get("family"))

    # ---- plant scope ----------------------------------------------------
    plant_state = {}
    groups = defaultdict(list)
    for row in reg.role_rows("plant_status"):
        if reg.classify(row, ("status",)) != "live":
            continue
        key = (norm_code(row.get("plant", "plant_code")),
               norm_code(row.get("period", "period_code")))
        groups[key].append(row)
    for key, rows in groups.items():
        plant_state[key] = as_text(pick_winner(rows).get("status"))
    plants = sorted({p for p, _ in plant_state})

    # ---- calendar -------------------------------------------------------
    calendar = {}
    for row in reg.role_rows("calendar"):
        calendar[as_text(row.get("date"))] = norm_code(
            row.get("period_code", "period"))

    # ---- demand ---------------------------------------------------------
    demand = build_demand(reg, calendar, item_status, periods)

    # ---- unit cost coefficients -----------------------------------------
    fx_micros = pick_fx(reg)
    coef = build_coefficients(reg, items, periods, fx_micros, surcharge_bps,
                              holding_rate_bps, item_defaults, default_setup,
                              demand)

    # ---- capacity and handling ------------------------------------------
    capacity = build_capacity(reg, plants, periods, plant_state)
    handling_base = build_handling(reg, plants, periods)

    # ---- stage one: capital selection -----------------------------------
    cap = capital_stage(reg, committed_rows, fx_micros, envelope, capex_grid)

    savings_by_plant = defaultdict(int)
    for pid in cap["selected"]:
        plant = cap["plant"].get(pid)
        if plant:
            savings_by_plant[plant] += cap["saving"][pid]
    handling = {}
    for key, rate in handling_base.items():
        handling[key] = max(min_handling, rate - savings_by_plant.get(key[0], 0))

    # ---- stage two: lot sizing ------------------------------------------
    plan = {}
    for item in items:
        dem = [demand.get((item, p), 0) for p in periods]
        uc = [coef[(item, p)]["unit_cost_cents"] for p in periods]
        su = [coef[(item, p)]["setup_cost_cents"] for p in periods]
        ho = [coef[(item, p)]["holding_cost_cents"] for p in periods]
        plan[item] = lot_size(dem, uc, su, ho)

    # ---- stage three: sourcing ------------------------------------------
    sourcing = source_stage(items, periods, plan, capacity, handling, plants)

    # ---- assemble and write ---------------------------------------------
    emit(out_dir, corpus, reg, cutoff, items, periods, plants, coef,
         capacity, handling, plan, sourcing, cap, envelope, capex_grid,
         shortfall_penalty, families, item_status, calendar)


# --------------------------------------------------------------------------
# runbook parser (indentation based, no external yaml)
# --------------------------------------------------------------------------


def parse_runbook(path):
    root = {}
    stack = [(-1, root)]
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            body = line.strip()
            if ":" not in body:
                continue
            key, _, value = body.partition(":")
            key, value = key.strip(), value.strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            if value == "":
                node = {}
                parent[key] = node
                stack.append((indent, node))
            else:
                parent[key] = value
    return root


# --------------------------------------------------------------------------
# scalar document parameters
# --------------------------------------------------------------------------


def scalar_amount(reg, rows, name, value_field, unit_field, auth):
    factors = {r["token"]: r["factor"] for r in auth.get("scale_authority", [])}
    cands = []
    for row in rows:
        if as_text(row.get("parameter")) != name:
            continue
        if reg.classify(row, (value_field,)) != "live":
            continue
        cands.append(row)
    win = pick_winner(cands)
    unit = as_text(win.get(unit_field))
    return to_int(win.get(value_field)) * factors.get(unit, 1)


# --------------------------------------------------------------------------
# demand rebuild
# --------------------------------------------------------------------------

UNIT_COLS = ("units", "qty", "planned_units")
DOZEN_COLS = ("units_dz",)


def demand_value(row):
    for col in DOZEN_COLS:
        if col in row.data:
            return to_int(row.data[col]) * 12, col
    for col in UNIT_COLS:
        if col in row.data:
            return to_int(row.data[col]), col
    raise KeyError("no demand column")


def demand_field(row):
    for col in DOZEN_COLS + UNIT_COLS:
        if col in row.data:
            return col
    raise KeyError("no demand column")


def build_demand(reg, calendar, item_status, periods):
    rows = reg.role_rows("demand") + reg.role_rows("demand_overlay")
    rows.sort(key=lambda r: (r.source, r.index))
    for order, row in enumerate(rows):
        row.order = order
    valid = set(periods)
    groups = defaultdict(list)
    for row in rows:
        item = norm_code(row.get("item_code", "item", "sku", "code"))
        if "date" in row.data:
            period = calendar.get(as_text(row.data["date"]), "")
        else:
            period = norm_code(row.get("period_code", "period"))
        status = item_status.get(item)
        if status is None or status == "retired":
            continue
        if reg.classify(row, (demand_field(row),)) != "live":
            continue
        if period not in valid:
            continue
        groups[(item, period)].append(row)
    demand = {}
    for key, cands in groups.items():
        win = pick_winner(cands)
        demand[key] = demand_value(win)[0]
    return demand


# --------------------------------------------------------------------------
# treasury rate
# --------------------------------------------------------------------------


def pick_fx(reg):
    best = None
    for row in reg.role_rows("fx_rate"):
        if reg.classify(row, ("usd_per_eur_micros",)) != "live":
            continue
        key = (row.seq(), row.order)
        if best is None or key > best[0]:
            best = (key, to_int(row.get("usd_per_eur_micros")))
    return best[1]


def convert_money(amount, ccy, scale, fx_micros):
    factor = 1000 if scale == "kcents" else 1
    value = amount * factor
    if ccy == "EUR":
        value = rhu(value * fx_micros, 1000000)
    return value


# --------------------------------------------------------------------------
# coefficient rebuild
# --------------------------------------------------------------------------


def build_coefficients(reg, items, periods, fx_micros, surcharge_bps,
                       holding_rate_bps, item_defaults, default_setup,
                       demand):
    keyset = {(i, p) for i in items for p in periods}
    key_flags = defaultdict(set)

    def cost_rows(role):
        """Live rows per key, recording the CUT and VOI letters on the way."""
        live = defaultdict(list)
        for row in reg.role_rows(role):
            key = (norm_code(row.get("item", "item_code", "sku", "code")),
                   norm_code(row.get("period", "period_code")))
            if reg.is_sentinel(row.get("amount")):
                continue
            if row.seq() > reg.cutoff:
                key_flags[key].add("CUT")
            if reg.void_marked(row):
                key_flags[key].add("VOI")
            if reg.classify(row, ("amount",)) == "live":
                live[key].append(row)
        return live

    base_live = cost_rows("unit_cost")
    amend_live = cost_rows("cost_amendment")
    over_live = cost_rows("cost_override")

    amend = defaultdict(dict)
    for key, rows in amend_live.items():
        for row in rows:
            aid = as_text(row.get("amend_id"))
            if aid not in amend[key]:
                amend[key][aid] = row

    setup_live = defaultdict(list)
    for row in reg.role_rows("setup_cost"):
        key = (norm_code(row.get("item", "item_code", "sku", "code")),
               norm_code(row.get("period", "period_code")))
        if reg.classify(row, ("amount",)) != "live":
            continue
        setup_live[key].append(row)

    index_bps = {}
    groups = defaultdict(list)
    for row in reg.role_rows("energy_index"):
        if reg.classify(row, ("index_value",)) != "live":
            continue
        groups[norm_code(row.get("period", "period_code"))].append(row)
    for code, rows in groups.items():
        win = pick_winner(rows)
        value = to_int(win.get("index_value"))
        if as_text(win.get("unit")) == "pct":
            value *= 100
        index_bps[code] = value

    coef = {}
    for key in keyset:
        item, period = key
        flags = set(key_flags.get(key, ()))
        win = pick_winner(base_live.get(key, []))
        if win is None:
            value = 0
        else:
            ccy = as_text(win.get("ccy")) or "USD"
            scale = as_text(win.get("scale")) or "cents"
            if ccy == "EUR":
                flags.add("FX")
            if scale == "kcents":
                flags.add("KC")
            value = convert_money(to_int(win.get("amount")), ccy, scale,
                                  fx_micros)
        rows = amend.get(key)
        if rows:
            flags.add("AMD")
            for row in rows.values():
                amt = to_int(row.get("amount"))
                if as_text(row.get("sign")) == "credit":
                    amt = -amt
                value += amt
        ow = pick_winner(over_live.get(key, []))
        if ow is not None:
            flags.add("OVR")
            value = to_int(ow.get("amount"))
        energy = index_bps.get(period, 0) + surcharge_bps
        uplift = rhu(value * energy, 10000)
        if uplift != 0:
            flags.add("ENR")
        value += uplift

        sw = pick_winner(setup_live.get(key, []))
        if sw is not None:
            setup = to_int(sw.get("amount")) * (
                1000 if as_text(sw.get("scale")) == "kcents" else 1)
        else:
            d = item_defaults.get(item)
            setup = int(d["setup_fallback_cents"]) if d else default_setup

        coef[key] = {
            "demand_units": demand.get(key, 0),
            "energy_bps_applied": energy,
            "flags": "+".join(sorted(flags)),
            "holding_cost_cents": rhu(value * holding_rate_bps, 10000),
            "item": item,
            "period": period,
            "setup_cost_cents": setup,
            "unit_cost_cents": value,
        }
    return coef


# --------------------------------------------------------------------------
# capacity and handling
# --------------------------------------------------------------------------


def _winner_map(reg, role, key_fn, value_fields):
    groups = defaultdict(list)
    for row in reg.role_rows(role):
        if reg.classify(row, value_fields) != "live":
            continue
        groups[key_fn(row)].append(row)
    return {k: pick_winner(v) for k, v in groups.items()}


def _accumulate(reg, role, key_fn, id_field, value_field):
    seen = defaultdict(dict)
    for row in reg.role_rows(role):
        if reg.classify(row, (value_field,)) != "live":
            continue
        key = key_fn(row)
        aid = as_text(row.get(id_field))
        if aid not in seen[key]:
            seen[key][aid] = to_int(row.get(value_field))
    return {k: sum(v.values()) for k, v in seen.items()}


def _pp(row):
    return (norm_code(row.get("plant", "plant_code")),
            norm_code(row.get("period", "period_code")))


def build_capacity(reg, plants, periods, plant_state):
    base = _winner_map(reg, "capacity_base", _pp, ("base_capacity_units",))
    adj = _accumulate(reg, "capacity_adjustment", _pp, "adj_id", "delta_units")
    shift = _winner_map(reg, "shift_pattern",
                        lambda r: norm_code(r.get("plant", "plant_code")),
                        ("shift_value",))
    derate = _winner_map(reg, "holiday_derate",
                         lambda r: norm_code(r.get("period", "period_code")),
                         ("derate_value",))

    def bps(win, field):
        if win is None:
            return 10000
        value = to_int(win.get(field))
        if as_text(win.get("unit")) == "pct":
            value *= 100
        return value

    out = {}
    for plant in plants:
        sb = bps(shift.get(plant), "shift_value")
        for period in periods:
            key = (plant, period)
            if plant_state.get(key) == "mothballed":
                out[key] = 0
                continue
            bw = base.get(key)
            value = to_int(bw.get("base_capacity_units")) if bw else 0
            value += adj.get(key, 0)
            db = bps(derate.get(period), "derate_value")
            value = rhu(rhu(value * sb, 10000) * db, 10000)
            out[key] = max(0, value)
    return out


def build_handling(reg, plants, periods):
    base = _winner_map(reg, "handling_base", _pp, ("handling_cents_per_unit",))
    adj = _accumulate(reg, "handling_adjustment", _pp, "adj_id", "delta_cents")
    zone = _winner_map(reg, "plant_zone",
                       lambda r: norm_code(r.get("plant", "plant_code")),
                       ("zone",))
    uplift = _winner_map(reg, "zone_tariff",
                         lambda r: norm_code(r.get("zone",)),
                         ("uplift_value",))
    out = {}
    for plant in plants:
        zw = zone.get(plant)
        zcode = norm_code(zw.get("zone")) if zw else ""
        uw = uplift.get(zcode)
        if uw is None:
            up = 0
        else:
            up = to_int(uw.get("uplift_value"))
            if as_text(uw.get("unit")) == "pct":
                up *= 100
        for period in periods:
            key = (plant, period)
            bw = base.get(key)
            value = to_int(bw.get("handling_cents_per_unit")) if bw else 0
            value += adj.get(key, 0)
            out[key] = rhu(value * (10000 + up), 10000)
    return out


# --------------------------------------------------------------------------
# stage one: capital selection
# --------------------------------------------------------------------------


def capital_stage(reg, committed_rows, fx_micros, envelope, grid):
    projects = _winner_map(reg, "retrofit_project",
                           lambda r: norm_code(r.get("project_id")),
                           ("status",))
    capex = _winner_map(reg, "retrofit_capex",
                        lambda r: norm_code(r.get("project_id")),
                        ("amount",))
    savings = _winner_map(reg, "retrofit_savings",
                          lambda r: norm_code(r.get("project_id")),
                          ("savings_value",))
    elig = _winner_map(reg, "retrofit_eligibility",
                       lambda r: norm_code(r.get("project_id")),
                       ("eligible",))
    groups = defaultdict(list)
    for row in committed_rows:
        if reg.classify(row, ("committed_volume_units",)) != "live":
            continue
        groups[norm_code(row.get("project_id"))].append(row)
    volume = {k: pick_winner(v) for k, v in groups.items()}

    candidates = []
    plant = {}
    saving_cents = {}
    capex_cents = {}
    value_cents = {}
    for pid, win in elig.items():
        if as_text(win.get("eligible")) != "yes":
            continue
        cw, sw, vw = capex.get(pid), savings.get(pid), volume.get(pid)
        if cw is None or sw is None or vw is None:
            continue
        capex_cents[pid] = to_int(cw.get("amount")) * (
            1000 if as_text(cw.get("scale")) == "kcents" else 1)
        saving_cents[pid] = convert_money(
            to_int(sw.get("savings_value")), as_text(sw.get("ccy")), "cents",
            fx_micros)
        vol = to_int(vw.get("committed_volume_units"))
        value_cents[pid] = saving_cents[pid] * vol
        pw = projects.get(pid)
        plant[pid] = norm_code(pw.get("plant", "plant_code")) if pw else ""
        candidates.append(pid)
    candidates.sort()

    selected, value, cost = knapsack(candidates, capex_cents, value_cents,
                                     envelope, grid)
    _, plus_value, _ = knapsack(candidates, capex_cents, value_cents,
                                envelope + grid, grid)
    return {
        "candidates": candidates,
        "selected": selected,
        "value": value,
        "capex": cost,
        "capex_cents": capex_cents,
        "value_cents": value_cents,
        "saving": saving_cents,
        "plant": plant,
        "marginal": plus_value - value,
    }


def knapsack(candidates, capex_cents, value_cents, envelope, grid):
    """Exact 0/1 knapsack on the capital grid.

    Maximises (total value, -total capex, -indicator) lexicographically, where
    the indicator has the first candidate in ascending code order as its least
    significant bit.
    """
    budget = envelope // grid
    weights = [capex_cents[p] // grid for p in candidates]
    best = [(0, 0, 0)] * (budget + 1)      # (value, -capex, -indicator)
    for idx, pid in enumerate(candidates):
        w = weights[idx]
        v = value_cents[pid]
        if w > budget:
            continue
        bit = 1 << idx
        cost = capex_cents[pid]
        nxt = list(best)
        for c in range(budget, w - 1, -1):
            pv, pc, pi = best[c - w]
            cand = (pv + v, pc - cost, pi - bit)
            if cand > nxt[c]:
                nxt[c] = cand
        best = nxt
    value, negcost, negind = best[budget]
    mask = -negind
    selected = [candidates[i] for i in range(len(candidates))
                if mask >> i & 1]
    return selected, value, -negcost


# --------------------------------------------------------------------------
# stage two: lot sizing (Wagner-Whitin, exact)
# --------------------------------------------------------------------------


def lot_size(dem, unit, setup, hold):
    T = len(dem)
    # prefix sums for demand and holding
    cum_h = [0] * (T + 1)
    for t in range(T):
        cum_h[t + 1] = cum_h[t] + hold[t]
    best = [None] * (T + 1)
    best[0] = (0, (), ())            # cost, reversed production tuple, choices
    for b in range(1, T + 1):
        for a in range(b):
            prev = best[a]
            if prev is None:
                continue
            block = 0
            carry = 0
            for t in range(a, b):
                block += dem[t]
                if t > a:
                    carry += dem[t] * (cum_h[t] - cum_h[a])
            if block == 0:
                cost = 0
                prod = prev[1]
            else:
                cost = setup[a] + unit[a] * block + carry
                prod = (a,) + prev[1]
            cand = (prev[0] + cost, prod, prev[2] + ((a, b, block),))
            if best[b] is None or cand[:2] < best[b][:2]:
                best[b] = cand
    total, _, blocks = best[T]
    produced = [0] * T
    opened = []
    for a, b, block in blocks:
        if block > 0:
            produced[a] += block
            opened.append((a, b))
    inv = [0] * T
    carry = 0
    for t in range(T):
        carry += produced[t] - dem[t]
        inv[t] = carry
    return {"produced": produced, "inventory": inv, "blocks": opened,
            "cost": total}


# --------------------------------------------------------------------------
# stage three: sourcing
# --------------------------------------------------------------------------


def source_stage(items, periods, plan, capacity, handling, plants):
    out = {}
    for pi, period in enumerate(periods):
        queue = [(item, plan[item]["produced"][pi]) for item in items
                 if plan[item]["produced"][pi] > 0]
        required = sum(q for _, q in queue)
        order = sorted(plants, key=lambda p: (handling[(p, period)], p))
        assigns = []
        assigned = defaultdict(int)
        qi = 0
        remaining = queue[qi][1] if queue else 0
        for plant in order:
            free = capacity[(plant, period)]
            while free > 0 and qi < len(queue):
                take = min(free, remaining)
                if take > 0:
                    assigns.append((plant, queue[qi][0], take))
                    assigned[plant] += take
                    free -= take
                    remaining -= take
                if remaining == 0:
                    qi += 1
                    remaining = queue[qi][1] if qi < len(queue) else 0
        short = 0
        if qi < len(queue):
            short = remaining + sum(q for _, q in queue[qi + 1:])
        out[period] = {
            "required": required,
            "order": order,
            "assigns": assigns,
            "assigned": dict(assigned),
            "shortfall": short,
            "capacity": sum(capacity[(p, period)] for p in plants),
        }
    return out


# --------------------------------------------------------------------------
# rejection and accounting sweep
# --------------------------------------------------------------------------


def sweep(corpus, reg, cutoff, calendar, item_status, demand_roles):
    rejected = []
    out_of_scope = 0
    void_rows = 0
    entries = [e for e in corpus.manifest
               if e["authority"] == "primary" and e["fmt"] in SWEEP_FMTS]
    for entry in entries:
        role = entry["role"]
        rows = corpus.load(entry["name"], entry["fmt"])
        for raw in rows:
            row = Row(entry["name"], 0, 0, raw)
            uid = as_text(row.get("row_uid"))
            reason = None
            if role in demand_roles:
                item = norm_code(row.get("item_code", "item", "sku", "code"))
                status = item_status.get(item)
                if status is None:
                    reason = "unknown_item"
                elif status == "retired":
                    reason = "retired_item"
            if reason is None:
                for value in raw.values():
                    if reg.is_sentinel(value):
                        reason = "sentinel"
                        break
            if reason is not None:
                rejected.append((entry["name"], uid,
                                 sweep_key(row, calendar), reason))
                continue
            seq = row.get("effective_seq")
            if seq is None or as_text(seq) == "":
                continue
            if to_int(seq) > cutoff:
                out_of_scope += 1
                continue
            blocked = False
            v = row.get("void")
            if v is not None and as_text(v) not in ("", "0"):
                blocked = True
            if reg.lifecycle_voided(uid):
                blocked = True
            if blocked:
                void_rows += 1
    rejected.sort(key=lambda r: (r[0], r[1]))
    return rejected, out_of_scope, void_rows, len(corpus.manifest)


def sweep_key(row, calendar):
    parts = []
    if row.has("item", "item_code", "sku", "code"):
        parts.append(norm_code(row.get("item", "item_code", "sku", "code")))
    if row.has("period", "period_code"):
        parts.append(norm_code(row.get("period", "period_code")))
    elif "date" in row.data:
        parts.append(calendar.get(as_text(row.data["date"]), ""))
    if row.has("plant", "plant_code"):
        parts.append(norm_code(row.get("plant", "plant_code")))
    if row.has("project_id"):
        parts.append(norm_code(row.get("project_id")))
    if row.has("zone"):
        parts.append(norm_code(row.get("zone")))
    return ":".join(parts)


# --------------------------------------------------------------------------
# artifact emission
# --------------------------------------------------------------------------


def emit(out_dir, corpus, reg, cutoff, items, periods, plants, coef,
         capacity, handling, plan, sourcing, cap, envelope, grid,
         shortfall_penalty, families, item_status, calendar):
    J = lambda n: os.path.join(out_dir, n)
    T = len(periods)

    # ---- coefficients ---------------------------------------------------
    rows = []
    for item in items:
        for pi, period in enumerate(periods):
            c = coef[(item, period)]
            rows.append({
                "demand_units": c["demand_units"],
                "energy_bps_applied": c["energy_bps_applied"],
                "fiscal_ordinal": pi + 1,
                "flags": c["flags"],
                "holding_cost_cents": c["holding_cost_cents"],
                "item": item,
                "period": period,
                "setup_cost_cents": c["setup_cost_cents"],
                "unit_cost_cents": c["unit_cost_cents"],
            })
    write_jsonl(J("corrected_coefficients.jsonl"), rows)

    # ---- plan aggregates -------------------------------------------------
    production_cost = 0
    setup_cost = 0
    holding_cost = 0
    total_demand = 0
    total_produced = 0
    per_period = {p: {"handling_cost_cents": 0, "holding_cost_cents": 0,
                      "production_cost_cents": 0, "setup_cost_cents": 0,
                      "shortfall_penalty_cents": 0} for p in periods}
    plan_rows = []
    sched_rows = []
    hold_rows = []
    item_sum = {}
    for item in items:
        st = plan[item]
        i_prod_cost = 0
        i_setup_cost = 0
        i_hold_cost = 0
        i_demand = 0
        i_produced = 0
        i_setups = 0
        cum = 0
        starts = {a: b for a, b in st["blocks"]}
        for pi, period in enumerate(periods):
            c = coef[(item, period)]
            dem = c["demand_units"]
            prod = st["produced"][pi]
            inv = st["inventory"][pi]
            i_demand += dem
            i_produced += prod
            pcost = c["unit_cost_cents"] * prod
            i_prod_cost += pcost
            per_period[period]["production_cost_cents"] += pcost
            scost = 0
            if pi in starts:
                scost = c["setup_cost_cents"]
                i_setups += 1
                i_setup_cost += scost
                per_period[period]["setup_cost_cents"] += scost
                covers = [periods[t] for t in range(pi, starts[pi])
                          if coef[(item, periods[t])]["demand_units"] > 0]
                plan_rows.append({
                    "covers_periods": covers,
                    "fiscal_ordinal": pi + 1,
                    "item": item,
                    "period": period,
                    "production_cost_cents": pcost,
                    "produced_units": prod,
                    "setup_cost_cents": scost,
                })
            hcost = inv * c["holding_cost_cents"]
            i_hold_cost += hcost
            cum += hcost
            per_period[period]["holding_cost_cents"] += hcost
            sched_rows.append((item, period, pi + 1, dem, prod, inv))
            hold_rows.append((item, period, pi + 1, inv,
                              c["holding_cost_cents"], hcost, cum))
        production_cost += i_prod_cost
        setup_cost += i_setup_cost
        holding_cost += i_hold_cost
        total_demand += i_demand
        total_produced += i_produced
        item_sum[item] = {
            "demand_units": i_demand,
            "family": families.get(item, ""),
            "holding_cost_cents": i_hold_cost,
            "produced_units": i_produced,
            "production_cost_cents": i_prod_cost,
            "setup_count": i_setups,
            "setup_cost_cents": i_setup_cost,
            "total_cents": i_prod_cost + i_setup_cost + i_hold_cost,
        }
    plan_rows.sort(key=lambda r: (r["item"], r["fiscal_ordinal"]))
    write_jsonl(J("optimal_plan.jsonl"), plan_rows)
    write_csv(J("production_schedule.csv"),
              ["item", "period", "fiscal_ordinal", "demand_units",
               "produced_units", "ending_inventory_units"], sched_rows)
    write_csv(J("holding_profile.csv"),
              ["item", "period", "fiscal_ordinal", "ending_inventory_units",
               "holding_rate_cents", "period_holding_cents",
               "cumulative_holding_cents"], hold_rows)

    # ---- sourcing --------------------------------------------------------
    handling_cost = 0
    shortfall_units = 0
    shortfall_cents = 0
    alloc_rows = []
    short_rows = []
    for pi, period in enumerate(periods):
        s = sourcing[period]
        rank = {p: i for i, p in enumerate(s["order"])}
        grouped = defaultdict(int)
        for plant, item, units in s["assigns"]:
            grouped[(plant, item)] += units
        for (plant, item), units in sorted(
                grouped.items(), key=lambda kv: (rank[kv[0][0]], kv[0][1])):
            rate = handling[(plant, period)]
            cost = rate * units
            handling_cost += cost
            per_period[period]["handling_cost_cents"] += cost
            alloc_rows.append((period, pi + 1, plant, item, units, rate, cost))
        pen = s["shortfall"] * shortfall_penalty
        shortfall_units += s["shortfall"]
        shortfall_cents += pen
        per_period[period]["shortfall_penalty_cents"] += pen
        short_rows.append((period, pi + 1, s["required"], s["capacity"],
                           s["shortfall"], shortfall_penalty, pen))
    write_csv(J("sourcing_allocation.csv"),
              ["period", "fiscal_ordinal", "plant", "item", "units",
               "handling_rate_cents", "handling_cost_cents"], alloc_rows)
    write_csv(J("shortfall_ledger.csv"),
              ["period", "fiscal_ordinal", "required_units", "capacity_units",
               "shortfall_units", "penalty_rate_cents", "penalty_cents"],
              short_rows)

    util_rows = []
    full_cap = []
    zero_cap = []
    for plant in plants:
        for pi, period in enumerate(periods):
            capy = capacity[(plant, period)]
            assigned = sourcing[period]["assigned"].get(plant, 0)
            idle = capy - assigned
            util = rhu(assigned * 10000, capy) if capy else 0
            util_rows.append((plant, period, pi + 1, capy, assigned, idle,
                              util))
            if capy == 0:
                zero_cap.append([plant, period])
            elif assigned == capy:
                full_cap.append([plant, period])
    write_csv(J("plant_utilization.csv"),
              ["plant", "period", "fiscal_ordinal", "capacity_units",
               "assigned_units", "idle_units", "utilisation_bps"], util_rows)

    capex_cents = cap["capex"]
    total_objective = (production_cost + setup_cost + holding_cost +
                       handling_cost + shortfall_cents + capex_cents)

    write_json(J("objective.json"), {
        "capex_cents": capex_cents,
        "handling_cost_cents": handling_cost,
        "holding_cost_cents": holding_cost,
        "items_in_scope": len(items),
        "periods_in_horizon": T,
        "plants_in_scope": len(plants),
        "production_cost_cents": production_cost,
        "setup_cost_cents": setup_cost,
        "shortfall_penalty_cents": shortfall_cents,
        "total_demand_units": total_demand,
        "total_objective_cents": total_objective,
        "total_produced_units": total_produced,
        "total_shortfall_units": shortfall_units,
    })

    # ---- capital artifacts ----------------------------------------------
    selected = sorted(cap["selected"])
    unfunded = sorted(set(cap["candidates"]) - set(selected))
    marginal = cap["marginal"]
    budget_binding = marginal > 0
    write_json(J("retrofit_selection.json"), {
        "budget_cents": envelope,
        "candidate_project_ids": sorted(cap["candidates"]),
        "capex_grid_cents": grid,
        "eligible_project_count": len(cap["candidates"]),
        "rejected_project_ids": unfunded,
        "selected_capex_cents": capex_cents,
        "selected_project_ids": selected,
        "selected_value_cents": cap["value"],
    })
    slack = envelope - capex_cents
    write_json(J("budget_utilization.json"), {
        "budget_binding": budget_binding,
        "budget_cents": envelope,
        "capex_cents": capex_cents,
        "slack_cents": slack,
        "slack_grid_units": slack // grid,
        "utilisation_bps": rhu(capex_cents * 10000, envelope) if envelope else 0,
    })

    write_json(J("period_costs.json"), {
        p: dict(v, total_cents=sum(v.values())) for p, v in per_period.items()})
    write_json(J("item_summary.json"), item_sum)

    shortfall_periods = [p for p in periods if sourcing[p]["shortfall"] > 0]
    write_json(J("binding_constraints.json"), {
        "binding_count": len(full_cap) + len(shortfall_periods) +
                         (1 if budget_binding else 0),
        "budget_binding": budget_binding,
        "full_capacity_plant_periods": full_cap,
        "shortfall_periods": shortfall_periods,
        "zero_capacity_plant_periods": zero_cap,
    })

    # ---- certificate -----------------------------------------------------
    remaining = envelope - capex_cents
    no_fit = True
    for pid in unfunded:
        if cap["value_cents"][pid] > 0 and cap["capex_cents"][pid] <= remaining:
            no_fit = False
            break
    zero_inv = True
    recon_ok = True
    for item in items:
        st = plan[item]
        entering = 0
        recon = 0
        for pi, period in enumerate(periods):
            c = coef[(item, period)]
            if st["produced"][pi] > 0:
                if entering != 0:
                    zero_inv = False
                recon += c["setup_cost_cents"]
            recon += c["unit_cost_cents"] * st["produced"][pi]
            recon += st["inventory"][pi] * c["holding_cost_cents"]
            entering = st["inventory"][pi]
        if recon != st["cost"]:
            recon_ok = False
    sourcing_ok = True
    for period in periods:
        s = sourcing[period]
        used = {p for p in plants if s["assigned"].get(p, 0) > 0}
        idle = [p for p in plants
                if capacity[(p, period)] - s["assigned"].get(p, 0) > 0]
        if used and idle:
            cheapest_idle = min(handling[(p, period)] for p in idle)
            dearest_used = max(handling[(p, period)] for p in used)
            if cheapest_idle < dearest_used:
                sourcing_ok = False
    total_assigned = sum(u for _, _, _, _, u, _, _ in alloc_rows)
    coverage_ok = (total_produced == total_demand and
                   total_assigned + shortfall_units == total_produced and
                   all(plan[i]["inventory"][T - 1] == 0 for i in items))
    write_json(J("optimality_certificate.json"), {
        "all_demand_covered_or_charged": bool(coverage_ok),
        "capital_no_unfunded_candidate_fits": bool(no_fit),
        "lot_sizing_reconstructed_cost_matches": bool(recon_ok),
        "lot_sizing_zero_inventory_property": bool(zero_inv),
        "sourcing_no_cheaper_idle_capacity": bool(sourcing_ok),
        "total_objective_cents": total_objective,
    })

    # ---- sensitivity -----------------------------------------------------
    next_unit = {}
    for period in periods:
        s = sourcing[period]
        idle = [p for p in plants
                if capacity[(p, period)] - s["assigned"].get(p, 0) > 0]
        if idle:
            next_unit[period] = min(handling[(p, period)] for p in idle)
        else:
            next_unit[period] = shortfall_penalty
    top_id, top_capex = "", 0
    best = None
    for pid in unfunded:
        c = cap["capex_cents"][pid]
        v = cap["value_cents"][pid]
        if c <= 0:
            continue
        if best is None or v * best[1] > best[0] * c:
            best = (v, c)
            top_id, top_capex = pid, c
    write_json(J("sensitivity_report.json"), {
        "budget_binding": budget_binding,
        "budget_grid_unit_cents": grid,
        "marginal_value_of_one_grid_unit_cents": marginal,
        "next_unit_cost_by_period": next_unit,
        "top_unfunded_capex_cents": top_capex,
        "top_unfunded_project_id": top_id,
    })

    inc_total = write_incumbent_artifacts(
        J, corpus, items, periods, coef, selected, total_objective, {
            "capex_cents": capex_cents,
            "handling_cost_cents": handling_cost,
            "holding_cost_cents": holding_cost,
            "production_cost_cents": production_cost,
            "setup_cost_cents": setup_cost,
            "shortfall_penalty_cents": shortfall_cents,
        })

    rejected_rows = write_quality_artifacts(J, corpus, reg, cutoff, calendar,
                                            item_status)

    # ---- reconciliation --------------------------------------------------
    figures = [
        ("corrected_total_objective_cents", total_objective),
        ("incumbent_total_objective_cents", inc_total),
        ("delta_cents", total_objective - inc_total),
        ("selected_capex_cents", capex_cents),
        ("budget_cents", envelope),
        ("total_shortfall_units", shortfall_units),
        ("shortfall_penalty_cents", shortfall_cents),
        ("items_in_scope", len(items)),
        ("rejected_rows", rejected_rows),
    ]
    with open(J("reconciliation.txt"), "w", encoding="utf-8",
              newline="\n") as fh:
        for k, v in figures:
            fh.write("%s=%s\n" % (k, v))
    with open(J("audit_summary.md"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write("# Replan Audit Summary\n\n")
        for k, v in figures:
            fh.write("- %s: %s\n" % (k, v))
        fh.write("\nSelected projects: %s\n" % ", ".join(selected))


def write_incumbent_artifacts(J, corpus, items, periods, coef, selected,
                              total_objective, components):
    """incumbent_delta.json and coefficient_corrections.csv."""
    report = {}
    for entry in corpus.by_role.get("incumbent_report", []):
        with open(corpus.path(entry["name"]), "r", encoding="utf-8") as fh:
            report = json.load(fh)
        break
    totals = report.get("stage_totals_cents", {})
    published = report.get("published_total_objective_cents", 0)
    projects = sorted(norm_code(p)
                      for p in report.get("selected_projects", []))
    write_json(J("incumbent_delta.json"), {
        "component_deltas": {k: components[k] - totals[k]
                             for k in totals if k in components},
        "corrected_selected_project_ids": selected,
        "corrected_total_objective_cents": total_objective,
        "delta_cents": total_objective - published,
        "incumbent_selected_project_ids": projects,
        "incumbent_total_objective_cents": published,
        "projects_added": sorted(set(selected) - set(projects)),
        "projects_dropped": sorted(set(projects) - set(selected)),
    })

    previous = {}
    for entry in corpus.by_role.get("incumbent_plan", []):
        for row in read_jsonl(corpus.path(entry["name"])):
            previous[(norm_code(row["item"]), norm_code(row["period"]))] = \
                int(row["unit_cost_cents"])
        break
    rows = []
    for item in items:
        for period in periods:
            new = coef[(item, period)]
            old = previous.get((item, period), 0)
            if old != new["unit_cost_cents"]:
                rows.append((item, period, old, new["unit_cost_cents"],
                             new["unit_cost_cents"] - old, new["flags"]))
    write_csv(J("coefficient_corrections.csv"),
              ["item", "period", "incumbent_unit_cost_cents",
               "corrected_unit_cost_cents", "delta_cents", "flags"], rows)
    return published


def write_quality_artifacts(J, corpus, reg, cutoff, calendar, item_status):
    """rejected_records.csv and data_quality.json."""
    rejected, oos, voids, seen = sweep(
        corpus, reg, cutoff, calendar, item_status,
        {"demand", "demand_overlay"})
    write_csv(J("rejected_records.csv"), ["source", "row_uid", "key", "reason"],
              rejected)
    sources = []
    mismatches = []
    for entry in corpus.manifest:
        declared = int(entry["record_count"])
        physical = corpus.physical_count(entry["name"], entry["fmt"])
        sources.append({
            "authority": entry["authority"],
            "fmt": entry["fmt"],
            "name": entry["name"],
            "record_count_declared": declared,
            "role": entry["role"],
            "rows_seen": physical,
        })
        if physical != declared:
            mismatches.append(entry["name"])
    write_json(J("data_quality.json"), {
        "count_mismatches": sorted(mismatches),
        "sources": sources,
        "totals": {
            "out_of_scope_rows": oos,
            "rejected_rows": len(rejected),
            "sources_seen": seen,
            "void_rows": voids,
        },
    })
    return len(rejected)


if __name__ == "__main__":
    main(sys.argv)
