"""Build the R7 post-training preference corpus release from an export directory.

Usage: python3 build.py <DATA_DIR> <OUT_DIR>
"""
from __future__ import annotations

import argparse
import calendar
import csv
import io
import json
import re
import sqlite3
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path

RECORD_FIELDS = {"rid": "rid", "rec": "rid", "par": "par", "pnt": "par", "val": "val",
                 "val_x1000": "val", "at": "at", "ts": "at", "fa": "fa", "a": "fa",
                 "fb": "fb", "b": "fb"}
LOOKALIKE = {"\u0410": "A", "\u0412": "B", "\u0421": "C", "\u0415": "E", "\u041d": "H",
             "\u0408": "J", "\u041a": "K", "\u041c": "M", "\u041e": "O", "\u0420": "P",
             "\u0422": "T", "\u0425": "X", "\u0430": "a", "\u0441": "c", "\u0435": "e",
             "\u043e": "o", "\u0440": "p", "\u0445": "x"}
CHOICES = ("both_bad", "left", "right", "tie")
VERDICT_PARTITION_BY_VENDOR = {
    "calder": "verdicts_vendor_a.jsonl",
    "northwind": "verdicts_vendor_b.jsonl",
    "orbit": "verdicts_shard1.parquet",
    "tessel": "verdicts_shard2.parquet",
}
OUTPUTS = ("annotator_standing.json", "verdict_admissibility.jsonl",
           "comparison_resolution.jsonl", "agreement.json", "prompt_eligibility.jsonl",
           "dedup_clusters.json", "preference_pairs.jsonl", "split_assignment.json",
           "mixture_plan.json", "packing_plan.json", "training_schedule.json",
           "slice_coverage.json", "source_audit.json", "control_reconciliation.json",
           "release_gates.json")


# --------------------------------------------------------------------------
# value readers
# --------------------------------------------------------------------------
def utc(y, mo, d, h=0, mi=0, s=0):
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def six(value):
    if value is None:
        return None
    d = Decimal(value.numerator) / Decimal(value.denominator)
    return float(d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def clean_text(s):
    return str(s if s is not None else "").replace("\u00a0", " ").strip()


def low(s):
    return clean_text(s).lower()


_GROUPED = re.compile(r"\d{1,3}(?:[.,\s]\d{3})+")


def read_int(s, scaled=False):
    s = clean_text(s)
    if s in ("", "-1", "N/A", "n/a"):
        return None
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    if _GROUPED.fullmatch(s):
        s = re.sub(r"[.,\s]", "", s)
    value = int(Decimal(s).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    if negative:
        value = -value
    return value // 1000 if scaled else value


_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z")
_ICS = re.compile(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z")
_LOCAL = re.compile(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.(\d{3}))?")
EXCEL_EPOCH = utc(1899, 12, 30)


def read_instant(s, local_shift=None):
    s = clean_text(s)
    m = _ISO.fullmatch(s) or _ICS.fullmatch(s)
    if m:
        return utc(*map(int, m.groups()))
    m = _LOCAL.fullmatch(s)
    if m:
        if local_shift is None:
            raise ValueError(f"local instant with no workstation: {s!r}")
        return utc(*map(int, m.groups()[:6])) - local_shift
    if re.fullmatch(r"\d{12,}", s):
        return int(s) // 1000
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return EXCEL_EPOCH + int(round(float(s) * 86400))
    raise ValueError(f"unreadable instant: {s!r}")


class Ids:
    def __init__(self, forms):
        self.forms = forms

    @staticmethod
    def key(s):
        s = unicodedata.normalize("NFKC", "".join(LOOKALIKE.get(c, c) for c in clean_text(s)))
        m = re.fullmatch(r"([A-Za-z]+)-?0*(\d+)", s.replace(" ", ""))
        if not m:
            return None
        return m.group(1).lower(), int(m.group(2))

    def canonical(self, s):
        k = self.key(s)
        if k is None or k[0] not in self.forms:
            return None
        prefix, width = self.forms[k[0]]
        return f"{prefix}-{k[1]:0{width}d}"


# --------------------------------------------------------------------------
# format readers: every reader yields the export's record rows
# --------------------------------------------------------------------------
def _record(raw):
    rec, scaled = {}, False
    for k, v in raw.items():
        field = RECORD_FIELDS.get(str(k).strip())
        if field:
            rec[field] = v
            scaled = scaled or str(k).strip() == "val_x1000"
    rec["scaled"] = scaled
    return rec


def _is_header(cells):
    return bool(cells) and clean_text(cells[0]) in ("rid", "rec")


def read_delimited(data, delim):
    rows, header = [], None
    for cells in csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=delim):
        if _is_header(cells):
            header = cells
        elif header and cells:
            rows.append(_record(dict(zip(header, cells))))
    return rows


def read_jsonl(data):
    return [_record(json.loads(x)) for x in data.decode("utf-8").splitlines() if x.strip()]


def read_json(data):
    return [_record(x) for x in json.loads(data.decode("utf-8"))["entries"]]


def read_xml(data):
    return [_record(el.attrib) for el in ET.fromstring(data).iter("record")]


def read_log(data):
    rows = []
    for line in data.decode("utf-8").splitlines():
        parts = line.split(" ")
        if len(parts) > 2:
            rows.append(_record(dict(p.split("=", 1) for p in parts[2:] if "=" in p)))
    return rows


def read_yaml(data):
    rows, cur = [], None
    for line in data.decode("utf-8").splitlines():
        if line.startswith("  - "):
            cur = {}
            rows.append(cur)
            line = line[4:]
        elif not line.startswith("    ") or cur is None:
            continue
        k, _, v = line.strip().partition(": ")
        cur[k] = json.loads(v)
    return [_record(r) for r in rows]


def read_toml(data):
    rows, cur = [], None
    for line in data.decode("utf-8").splitlines():
        if line.startswith("[["):
            cur = {}
            rows.append(cur)
        elif " = " in line and cur is not None:
            k, _, v = line.partition(" = ")
            cur[k.strip()] = json.loads(v)
    return [_record(r) for r in rows]


def read_ini(data):
    rows = []
    for line in data.decode("utf-8").splitlines():
        if not line or line.startswith("["):
            continue
        left, _, right = line.partition(" = ")
        rid, _, at = left.partition("@")
        raw = {"rid": rid, "at": at}
        raw.update(p.split("=", 1) for p in right.split("; ") if "=" in p)
        rows.append(_record(raw))
    return rows


def read_fixed(data):
    lines = data.decode("utf-8").splitlines()
    return [{"line": ln} for ln in lines if ln.strip() and not ln.startswith("#COLUMNS")]


def read_mbox(data):
    return [{"line": ln} for ln in data.decode("utf-8").splitlines() if ln.startswith("From ")]


def read_ics(data):
    rows, cur = [], None
    for line in data.decode("utf-8").splitlines():
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            rows.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            k, _, v = line.partition(":")
            cur[k] = v
    return rows


_CELL = re.compile(r'<c r="[A-Z]+\d+"(?: t="inlineStr")?>(?:<is><t[^>]*>(.*?)</t></is>|<v>(.*?)</v>)</c>', re.S)


def _xml_text(s):
    return s.replace("&#13;", "\r").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def read_xlsx(data):
    rows = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/")):
            header = None
            for row in re.findall(r"<row[^>]*>(.*?)</row>", zf.read(name).decode("utf-8"), re.S):
                cells = [_xml_text(a or b) for a, b in _CELL.findall(row)]
                if _is_header(cells):
                    header = cells
                elif header and cells:
                    rows.append(_record(dict(zip(header, cells))))
    return rows


def read_sqlite(data):
    con = sqlite3.connect(":memory:")
    con.deserialize(data)
    cur = con.execute("SELECT * FROM records")
    cols = [d[0] for d in cur.description]
    rows = [_record(dict(zip(cols, r))) for r in cur.fetchall()]
    con.close()
    return rows


def read_parquet(data):
    import pyarrow as pa
    import pyarrow.parquet as pq
    return [_record(r) for r in pq.read_table(pa.BufferReader(data)).to_pylist()]


def _docx_tables(data):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    for tbl in re.findall(r"<w:tbl>(.*?)</w:tbl>", xml, re.S):
        yield [[_xml_text(re.sub(r"<[^>]+>", "", c)) for c in re.findall(r"<w:tc>(.*?)</w:tc>", tr, re.S)]
               for tr in re.findall(r"<w:tr>(.*?)</w:tr>", tbl, re.S)]


def read_docx(data):
    rows = []
    for table in _docx_tables(data):
        if table and _is_header(table[0]):
            rows += [_record(dict(zip(table[0], r))) for r in table[1:] if not _is_header(r)]
    return rows


def _md_tables(text):
    tables, cur = [], []
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip().replace("\\|", "|") for c in line.strip().strip("|").split(" | ")]
            if not set("".join(cells)) <= set("-:| "):
                cur.append(cells)
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def read_md(data):
    rows = []
    for table in _md_tables(data.decode("utf-8")):
        if _is_header(table[0]):
            rows += [_record(dict(zip(table[0], r))) for r in table[1:] if not _is_header(r)]
    return rows


def read_html(data):
    rows = []
    for table in re.findall(r'<table class="data">(.*?)</table>', data.decode("utf-8"), re.S):
        trs = re.findall(r"<tr>(.*?)</tr>", table, re.S)
        header = re.findall(r"<th>(.*?)</th>", trs[0]) if trs else []
        rows += [_record(dict(zip(header, re.findall(r"<td>(.*?)</td>", tr)))) for tr in trs[1:]]
    return rows


def pdf_lines(data):
    raw = data.decode("latin-1")
    out = []
    for m in re.finditer(r"stream\n(.*?)\nendstream", raw, re.S):
        try:
            text = zlib.decompress(m.group(1).encode("latin-1")).decode("latin-1")
        except zlib.error:
            continue
        for s in re.findall(r"\((.*?)\)\s*Tj", text):
            out.append(s.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\"))
    return out


def read_pdf(data):
    rows, in_table, pending = [], False, False
    for line in pdf_lines(data):
        if line.startswith("TABLE "):
            in_table = True
        elif line.startswith("== "):
            in_table = False
        elif in_table and not pending:
            rows.append({"line": line})
            pending = line.endswith(" \\")
        else:
            pending = False
    return rows


READERS = {".csv": lambda d: read_delimited(d, ","), ".tsv": lambda d: read_delimited(d, "\t"),
           ".jsonl": read_jsonl, ".json": read_json, ".xml": read_xml, ".log": read_log,
           ".yaml": read_yaml, ".toml": read_toml, ".ini": read_ini, ".txt": read_fixed,
           ".mbox": read_mbox, ".ics": read_ics, ".xlsx": read_xlsx, ".db": read_sqlite,
           ".parquet": read_parquet, ".docx": read_docx, ".md": read_md, ".html": read_html,
           ".pdf": read_pdf}


class Corpus:
    def __init__(self, data_dir):
        self.raw = {p.name: p.read_bytes() for p in sorted(Path(data_dir).iterdir()) if p.is_file()}
        self._rows = {}

    def rows(self, name):
        if name not in self._rows:
            self._rows[name] = READERS[Path(name).suffix](self.raw[name])
        return self._rows[name]

    def text(self, name):
        return self.raw[name].decode("utf-8")


# --------------------------------------------------------------------------
# the standing documents
# --------------------------------------------------------------------------
def _dec(s):
    return Fraction(clean_text(s))


def read_policy(corpus):
    values = {}
    for table in _md_tables(corpus.text("corpus_policy.md")):
        if table[0][:2] == ["parameter", "value"]:
            values.update({r[0]: r[1] for r in table[1:] if len(r) >= 2})
    p = {name: int(values[name]) for name in (
        "gold_min_items", "min_votes", "max_prompt_tokens", "max_pair_tokens",
        "contamination_hard", "contamination_soft", "epoch_cap", "sequence_length",
        "global_batch", "micro_batch", "shard_sequences", "min_slice_pairs")}
    for name in ("bias_limit", "validation_fraction", "warmup_fraction",
                 "max_train_contamination_rate", "min_kappa"):
        p[name] = _dec(values[name])
    p["floors"] = {k.split(".", 1)[1]: _dec(v) for k, v in values.items() if k.startswith("gold_floor.")}
    for name in ("collection_window_start", "collection_window_end", "adjudication_cutoff"):
        p[name] = read_instant(values[name])
    return p


def read_conventions(corpus):
    forms, zones = {}, {}
    for table in _md_tables(corpus.text("source_conventions.md")):
        head = table[0]
        if head[:3] == ["entity", "registry", "registered form"]:
            for r in table[1:]:
                prefix, _, digits = r[2].partition("-")
                forms[prefix.lower()] = (prefix, len(digits))
        elif head[:2] == ["zone", "offset"]:
            for r in table[1:]:
                m = re.fullmatch(r"([+-])(\d{2}):(\d{2})", r[1])
                sign = -1 if m.group(1) == "-" else 1
                zones[r[0].lower()] = sign * (int(m.group(2)) * 3600 + int(m.group(3)) * 60)
    return Ids(forms), zones


# --------------------------------------------------------------------------
# reconstruction
# --------------------------------------------------------------------------
class Release:
    def __init__(self, data_dir):
        self.c = Corpus(data_dir)
        self.p = read_policy(self.c)
        self.ids, self.zones = read_conventions(self.c)
        self._workstations()
        self._prompts()
        self._completions()
        self._comparisons()
        self._annotators()
        self._verdicts()
        self._errata()
        self._gold()
        self._adjudications()
        self._freezes()
        self._contamination()
        self._clusters()
        self.targets = {low(r["fa"]): Fraction(read_int(r["fb"]), 100)
                        for r in self.c.rows("mixture_targets.xlsx")}

    def _id(self, value):
        return self.ids.canonical(value)

    def _first(self, name, use=lambda r: True):
        out = {}
        for r in self.c.rows(name):
            k = self._id(r.get("rid"))
            if k and k not in out and use(r):
                out[k] = r
        return out

    def _workstations(self):
        self.shift = {}
        for r in self.c.rows("workstation_inventory.ini"):
            ws = self._id(r.get("rid"))
            if ws and ws not in self.shift:
                self.shift[ws] = self.zones[low(r["fa"])] + int(clean_text(r["fb"]))

    def _prompts(self):
        self.prompts = {}
        for pid, r in self._first("prompt_registry.csv").items():
            self.prompts[pid] = {"family": self._id(r["par"]), "tokens": read_int(r["val"], r["scaled"]),
                                 "domain": low(r["fa"]), "source": low(r["fb"]),
                                 "retired": False, "opted_out": False}
        locales = {x.lower(): x for x in ("de_DE", "en_IN", "en_US", "es_ES", "fr_FR", "ja_JP")}
        for pid, r in self._first("slice_attributes.csv").items():
            if pid in self.prompts:
                self.prompts[pid]["locale"] = locales[low(r["fa"])]
                self.prompts[pid]["difficulty"] = low(r["fb"])
        for pid, r in self._first("prompt_locales.tsv").items():
            if pid in self.prompts:
                self.prompts[pid]["risk"] = low(r["fa"])

    def _completions(self):
        self.completions = {}
        for cid, r in self._first("completion_index.csv").items():
            self.completions[cid] = {"prompt": self._id(r["par"]), "tokens": read_int(r["val"], r["scaled"])}
        self.amended = {}
        for r in self.c.rows("completion_amendments.xml"):
            cid = self._id(r.get("rid"))
            if cid:
                self.amended[cid] = max(self.amended.get(cid, 0), read_instant(r["at"]))

    def _comparisons(self):
        self.comparisons = {}
        for mid, r in self._first("batch_registry.xml").items():
            self.comparisons[mid] = {"prompt": self._id(r["par"]), "left": self._id(r["fa"]),
                                     "right": self._id(r["fb"])}
        self.balanced = set()
        for r in self.c.rows("harness_events.log"):
            mid = self._id(r.get("rid"))
            if mid in self.comparisons and low(r.get("fb")) == "balanced":
                self.balanced.add(mid)

    def _annotators(self):
        self.annotators = {a: {"vendor": low(r["par"])} for a, r in self._first("annotator_roster.csv").items()}

    def _verdicts(self):
        self.verdicts = {}
        for vid, r in self._first("annotation_store.db", lambda r: read_int(r["val"], r["scaled"]) is not None).items():
            ws = self._id(r["fb"])
            self.verdicts[vid] = {"comparison": self._id(r["par"]), "annotator": self._id(r["fa"]),
                                  "workstation": ws, "confidence": read_int(r["val"], r["scaled"]),
                                  "at": read_instant(r["at"], self.shift.get(ws))}
        choices = {vendor: self._first(name)
                   for vendor, name in VERDICT_PARTITION_BY_VENDOR.items()}
        for vid, verdict in self.verdicts.items():
            vendor = self.annotators[verdict["annotator"]]["vendor"]
            verdict["choice"] = low(choices[vendor][vid]["fb"])

    def _errata(self):
        voided, restored = set(), set()
        for r in self.c.rows("errata_register.docx"):
            key, action = self._id(r.get("rid")), low(r.get("fa"))
            if key in self.prompts and action == "retire":
                self.prompts[key]["retired"] = True
            elif key in self.prompts and action == "optout":
                self.prompts[key]["opted_out"] = True
            elif action == "void":
                voided.add(key)
            elif action == "restore":
                restored.add(key)
        self.voided = voided - restored

    def _gold(self):
        self.gold = {m: self._id(r["fb"]) for m, r in self._first("gold_set.tsv").items()}
        self.gold_retired = {}
        for r in self.c.rows("gold_answers_revised.csv"):
            m = self._id(r.get("rid"))
            if m in self.gold and low(r.get("fa")) == "retired" and m not in self.gold_retired:
                self.gold_retired[m] = read_instant(r["at"])

    def _adjudications(self):
        self.adjudications = {m: {"at": read_instant(r["at"]), "choice": low(r["fa"])}
                              for m, r in self._first("adjudications.jsonl").items()}
        self.approved = {self._id(r.get("rid")) for r in self.c.rows("review_minutes.docx")
                         if low(r.get("fa")) == "approved"}

    def _freezes(self):
        self.freezes = {}
        for ev in self.c.rows("freeze_windows.ics"):
            ws = self._id(ev.get("X-WORKSTATION"))
            start = read_instant(ev["DTSTART"])
            self.freezes.setdefault(ws, []).append((start, start + int(ev["X-HOURS"]) * 3600))

    def _contamination(self):
        best = {}
        for r in self.c.rows("contamination_hits.jsonl"):
            pid, sim = self._id(r.get("rid")), read_int(r["val"], r["scaled"])
            if pid and sim is not None:
                best[pid] = max(best.get(pid, sim), sim)
        self.hard = {p for p, s in best.items() if s >= self.p["contamination_hard"]}
        self.soft = {p for p, s in best.items() if self.p["contamination_soft"] <= s < self.p["contamination_hard"]}

    def _clusters(self):
        members, effective = {}, {}
        for r in self.c.rows("dedup_clusters.tsv"):
            cluster, member = self._id(r.get("rid")), self._id(r.get("par"))
            if cluster and member:
                members.setdefault(cluster, set()).add(member)
                t = read_instant(r["at"])
                effective[member] = min(effective.get(member, t), t)
        self.clusters = {k: sorted(v) for k, v in sorted(members.items())}
        self.cluster_of = {m: k for k, ms in self.clusters.items() for m in ms}
        self.effective = effective
        self.canonical = {k: min(ms, key=lambda m: (effective[m], m)) for k, ms in self.clusters.items()}

    # ---------------------------------------------------------------- stages
    def standing(self):
        by_annotator = {}
        for vid in sorted(self.verdicts):
            by_annotator.setdefault(self.verdicts[vid]["annotator"], []).append(self.verdicts[vid])
        out = {}
        for a in sorted(self.annotators):
            mine = by_annotator.get(a, [])
            scored = [v for v in mine if v["comparison"] in self.gold
                      and not (v["comparison"] in self.gold_retired and v["at"] >= self.gold_retired[v["comparison"]])]
            hits = sum(1 for v in scored
                       if v["choice"] in ("left", "right")
                       and self.comparisons[v["comparison"]][v["choice"]] == self.gold[v["comparison"]])
            sided = [v for v in mine if v["comparison"] in self.balanced and v["choice"] in ("left", "right")]
            agreement = Fraction(hits, len(scored)) if scored else None
            bias = Fraction(sum(v["choice"] == "left" for v in sided), len(sided)) - Fraction(1, 2) if sided else None
            vendor = self.annotators[a]["vendor"]
            admitted = (len(scored) >= self.p["gold_min_items"] and agreement is not None
                        and agreement >= self.p["floors"][vendor])
            out[a] = {"vendor": vendor, "gold_items": len(scored), "gold_hits": hits,
                      "gold_agreement": six(agreement), "balanced_verdicts": len(sided),
                      "a_side_bias": six(bias), "biased": bias is not None and abs(bias) > self.p["bias_limit"],
                      "standing": "admitted" if admitted else "gated"}
        return out

    def _latest_amendment(self, mid):
        cm = self.comparisons[mid]
        return max(self.amended.get(cm["left"], 0), self.amended.get(cm["right"], 0))

    def _frozen(self, ws, t):
        return any(start <= t < end for start, end in self.freezes.get(ws, ()))

    def admissibility(self, standing):
        tests = (
            ("annotator_gated", lambda v: standing[v["annotator"]]["standing"] == "gated"),
            ("outside_window", lambda v: not self.p["collection_window_start"] <= v["at"] < self.p["collection_window_end"]),
            ("freeze_window", lambda v: self._frozen(v["workstation"], v["at"])),
            ("stale_amendment", lambda v: v["at"] <= self._latest_amendment(v["comparison"])),
            ("unbalanced_biased", lambda v: standing[v["annotator"]]["biased"] and v["comparison"] not in self.balanced),
            ("voided", lambda v: v["id"] in self.voided),
        )
        out = {}
        for vid in sorted(self.verdicts):
            v = dict(self.verdicts[vid], id=vid)
            reason = next((name for name, applies in tests if applies(v)), None)
            out[vid] = {"verdict_id": vid, "comparison": v["comparison"], "annotator": v["annotator"],
                        "admissible": reason is None, "reason": reason}
        return out

    def _live(self, admissibility):
        live = {}
        for vid, row in admissibility.items():
            if row["admissible"]:
                live.setdefault(row["comparison"], []).append(self.verdicts[vid])
        return live

    def resolution(self, admissibility):
        live = self._live(admissibility)
        out = {}
        for mid in sorted(self.comparisons):
            votes = live.get(mid, [])
            adj = self.adjudications.get(mid)
            row = {"comparison_id": mid, "votes": len(votes)}
            if (adj and self._latest_amendment(mid) < adj["at"] < self.p["adjudication_cutoff"]
                    and mid in self.approved):
                row.update(resolved=adj["choice"], route="adjudicated", margin=1.0)
            elif len(votes) < self.p["min_votes"]:
                row.update(resolved=None, route="insufficient", margin=None)
            else:
                count = {c: 0 for c in CHOICES}
                weight = {c: 0 for c in CHOICES}
                for v in votes:
                    count[v["choice"]] += 1
                    weight[v["choice"]] += v["confidence"]
                winner = min(CHOICES, key=lambda c: (-count[c], -weight[c], c))
                runner_up = max(count[c] for c in CHOICES if c != winner)
                row.update(resolved=winner, route="majority",
                           margin=six(Fraction(count[winner] - runner_up, len(votes))))
            out[mid] = row
        return out

    def eligibility(self, resolution):
        with_pair = {self.comparisons[m]["prompt"] for m, r in resolution.items() if r["resolved"] in ("left", "right")}
        out = {}
        for pid in sorted(self.prompts):
            pr = self.prompts[pid]
            cluster = self.cluster_of.get(pid)
            checks = (("retired", pr["retired"]), ("opted_out", pr["opted_out"]),
                      ("contaminated", pid in self.hard),
                      ("duplicate", cluster is not None and self.canonical[cluster] != pid),
                      ("over_length", pr["tokens"] > self.p["max_prompt_tokens"]),
                      ("no_resolved_pair", pid not in with_pair))
            reason = next((name for name, hit in checks if hit), None)
            out[pid] = {"prompt_id": pid, "eligible": reason is None, "reason": reason, "cluster": cluster,
                        "family": pr["family"], "source": pr["source"]}
        return out

    def pairs(self, resolution, eligibility):
        out = []
        for mid, r in sorted(resolution.items()):
            cm = self.comparisons[mid]
            if r["resolved"] not in ("left", "right") or not eligibility[cm["prompt"]]["eligible"]:
                continue
            chosen = cm[r["resolved"]]
            rejected = cm["right" if r["resolved"] == "left" else "left"]
            pr = self.prompts[cm["prompt"]]
            tokens = pr["tokens"] + self.completions[chosen]["tokens"] + self.completions[rejected]["tokens"]
            if tokens <= self.p["max_pair_tokens"]:
                out.append({"pair_id": "PP-" + mid.split("-")[1], "comparison": mid, "prompt": cm["prompt"],
                            "family": pr["family"], "source": pr["source"], "chosen": chosen,
                            "rejected": rejected, "margin": r["margin"], "route": r["route"], "tokens": tokens})
        return out

    def agreement(self, admissibility):
        live = self._live(admissibility)
        fold = lambda c: "tie" if c == "both_bad" else c
        overall, by_vendor, by_domain = [], {}, {}
        for mid in sorted(live):
            votes = live[mid]
            if len(votes) < 2:
                continue
            overall.append([fold(v["choice"]) for v in votes])
            domain = self.prompts[self.comparisons[mid]["prompt"]]["domain"]
            by_domain.setdefault(domain, []).append(overall[-1])
            groups = {}
            for v in votes:
                groups.setdefault(self.annotators[v["annotator"]]["vendor"], []).append(fold(v["choice"]))
            for vendor, cats in groups.items():
                if len(cats) >= 2:
                    by_vendor.setdefault(vendor, []).append(cats)

        def block(units):
            agree = pairs = 0
            totals = {}
            for cats in units:
                counts = {}
                for c in cats:
                    counts[c] = counts.get(c, 0) + 1
                    totals[c] = totals.get(c, 0) + 1
                agree += sum(n * (n - 1) for n in counts.values())
                pairs += len(cats) * (len(cats) - 1)
            ratings = sum(totals.values())
            if not pairs:
                return {"observed_agreement": None, "kappa": None, "rated_units": len(units), "rater_pairs": 0}
            observed = Fraction(agree, pairs)
            expected = sum(Fraction(n, ratings) ** 2 for n in totals.values())
            kappa = Fraction(0) if expected == 1 else (observed - expected) / (1 - expected)
            return {"observed_agreement": six(observed), "kappa": six(kappa),
                    "rated_units": len(units), "rater_pairs": pairs // 2}

        vendors = sorted({a["vendor"] for a in self.annotators.values()})
        domains = sorted({p["domain"] for p in self.prompts.values()})
        return {"overall": block(overall),
                "by_vendor": {v: block(by_vendor.get(v, [])) for v in vendors},
                "by_domain": {d: block(by_domain.get(d, [])) for d in domains}}

    def dedup(self):
        return {k: {"canonical": self.canonical[k], "members": ms,
                    "dropped": [m for m in ms if m != self.canonical[k]],
                    "canonical_effective_at": iso(self.effective[self.canonical[k]])}
                for k, ms in self.clusters.items()}

    def split(self, pairs):
        per_family = {}
        for x in pairs:
            per_family[x["family"]] = per_family.get(x["family"], 0) + 1
        soft_families = {self.prompts[p]["family"] for p in self.soft if p in self.prompts}
        quota = self.p["validation_fraction"] * len(pairs)
        families = {f: "validation" for f in per_family if f in soft_families}
        held = sum(per_family[f] for f in families)
        for fam in sorted(per_family):
            if fam not in families:
                families[fam] = "validation" if held < quota else "train"
                held += per_family[fam] if families[fam] == "validation" else 0
        pair_counts = {s: sum(n for f, n in per_family.items() if families[f] == s) for s in ("train", "validation")}
        return {"families": dict(sorted(families.items())),
                "family_counts": {s: sum(1 for v in families.values() if v == s) for s in ("train", "validation")},
                "pair_counts": pair_counts,
                "validation_share": six(Fraction(pair_counts["validation"], len(pairs))) if pairs else None}

    def mixture(self, pairs, split):
        sources = sorted(self.targets)
        available = {s: 0 for s in sources}
        for x in pairs:
            if split["families"][x["family"]] == "train":
                available[x["source"]] += 1
        budget = sum(available.values())
        cap = {s: self.p["epoch_cap"] * available[s] for s in sources}
        alloc = {s: Fraction(0) for s in sources}
        fixed = set()
        free = [s for s in sources if available[s]]
        left = Fraction(budget)
        while free:
            total_target = sum(self.targets[s] for s in free)
            if not total_target:
                break
            offer = {s: left * self.targets[s] / total_target for s in free}
            over = [s for s in free if offer[s] > cap[s]]
            if not over:
                alloc.update(offer)
                break
            for s in over:
                alloc[s] = Fraction(cap[s])
                left -= cap[s]
                fixed.add(s)
            free = [s for s in free if s not in fixed]
        plan = {s: {"available_pairs": available[s], "target_weight": six(self.targets[s]),
                    "allocated_pairs": int(alloc[s]),
                    "effective_weight": six(alloc[s] / budget) if budget else None,
                    "epochs": six(alloc[s] / available[s]) if available[s] else None,
                    "capped": s in fixed}
                for s in sources}
        plan["_total"] = {"budget_pairs": budget,
                          "allocated_pairs": sum(plan[s]["allocated_pairs"] for s in sources)}
        return plan

    def packing(self, pairs, split):
        width = self.p["sequence_length"]
        lengths, current, dropped = [], None, 0
        for x in sorted(pairs, key=lambda x: x["pair_id"]):
            if split["families"][x["family"]] != "train":
                continue
            if x["tokens"] > width:
                dropped += 1
                continue
            if current is None or current + x["tokens"] > width:
                if current is not None:
                    lengths.append(current)
                current = 0
            current += x["tokens"]
        if current:
            lengths.append(current)
        packed = sum(1 for x in pairs if split["families"][x["family"]] == "train") - dropped
        capacity = len(lengths) * width
        used = sum(lengths)
        return {"sequence_length": width, "packed_pairs": packed, "dropped_pairs": dropped,
                "sequences": len(lengths), "token_capacity": capacity, "tokens_used": used,
                "padding_tokens": capacity - used,
                "packing_efficiency": six(Fraction(used, capacity)) if capacity else None}

    def schedule(self, packing):
        seqs, batch = packing["sequences"], self.p["global_batch"]
        steps = seqs // batch
        return {"sequences": seqs, "global_batch": batch, "micro_batch": self.p["micro_batch"],
                "gradient_accumulation": batch // self.p["micro_batch"], "optimizer_steps": steps,
                "warmup_steps": round(self.p["warmup_fraction"] * steps),
                "shards": -(-seqs // self.p["shard_sequences"]), "shard_sequences": self.p["shard_sequences"],
                "dropped_tail_sequences": seqs - steps * batch}

    def slices(self, pairs, split):
        out = {}
        for x in pairs:
            pr = self.prompts[x["prompt"]]
            keys = ("domain-" + pr["domain"], "difficulty-" + pr["difficulty"], "risk-" + pr["risk"],
                    "locale-" + pr["locale"], "source-" + x["source"])
            for key in keys:
                cell = out.setdefault(key, {"pairs": 0, "train": 0, "validation": 0, "tokens": 0})
                cell["pairs"] += 1
                cell[split["families"][x["family"]]] += 1
                cell["tokens"] += x["tokens"]
        return dict(sorted(out.items()))

    def gates(self, pairs, split, agreement, packing, slices):
        small = sorted(k for k, v in slices.items() if v["pairs"] < self.p["min_slice_pairs"])
        sides = {}
        for x in pairs:
            sides.setdefault(x["family"], set()).add(split["families"][x["family"]])
        leaked = sum(1 for x in pairs if split["families"][x["family"]] == "train"
                     and (x["prompt"] in self.soft or x["prompt"] in self.hard))
        rate = Fraction(leaked, len(pairs)) if pairs else None
        kappa = agreement["overall"]["kappa"]
        gates = {"min_slice_pairs_met": not small,
                 "no_family_straddles_split": all(len(s) == 1 for s in sides.values()),
                 "train_contamination_within_limit": rate is not None and rate <= self.p["max_train_contamination_rate"],
                 "kappa_above_floor": kappa is not None and Fraction(str(kappa)) >= self.p["min_kappa"],
                 "packing_efficiency_reported": packing["sequences"] > 0}
        gates["release_approved"] = all(gates.values())
        return {"gates": gates, "undersized_slices": small, "train_contamination_rate": six(rate),
                "total_pairs": len(pairs)}

    def build(self):
        standing = self.standing()
        adm = self.admissibility(standing)
        res = self.resolution(adm)
        elig = self.eligibility(res)
        pairs = self.pairs(res, elig)
        agreement = self.agreement(adm)
        split = self.split(pairs)
        packing = self.packing(pairs, split)
        slices = self.slices(pairs, split)
        return {
            "annotator_standing.json": standing,
            "verdict_admissibility.jsonl": list(adm.values()),
            "comparison_resolution.jsonl": list(res.values()),
            "agreement.json": agreement,
            "prompt_eligibility.jsonl": list(elig.values()),
            "dedup_clusters.json": self.dedup(),
            "preference_pairs.jsonl": pairs,
            "split_assignment.json": split,
            "mixture_plan.json": self.mixture(pairs, split),
            "packing_plan.json": packing,
            "training_schedule.json": self.schedule(packing),
            "slice_coverage.json": slices,
            "source_audit.json": {n: {"rows": len(self.c.rows(n))} for n in sorted(self.c.raw)},
            "control_reconciliation.json": {
                "prompts": len(self.prompts), "completions": len(self.completions),
                "comparisons": len(self.comparisons), "verdicts": len(self.verdicts),
                "admissible": sum(1 for r in adm.values() if r["admissible"]),
                "resolved": sum(1 for r in res.values() if r["resolved"] is not None),
                "eligible": sum(1 for r in elig.values() if r["eligible"]),
                "pairs": len(pairs)},
            "release_gates.json": self.gates(pairs, split, agreement, packing, slices),
        }


def write(out_dir, result):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:
        value = result[name]
        if name.endswith(".jsonl"):
            body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in value)
        else:
            body = json.dumps(value, sort_keys=True, indent=1) + "\n"
        (out / name).write_text(body, encoding="utf-8", newline="\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="build the R7 preference corpus release")
    ap.add_argument("data_dir")
    ap.add_argument("out_dir")
    ns = ap.parse_args(argv)
    write(ns.out_dir, Release(ns.data_dir).build())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
