#!/usr/bin/env python3
"""Reference program: recompute the QA26-Q4 result-cache node plan.

Usage: python3 plan_cache.py DATA_DIR OUT_DIR
Standard library only.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from pathlib import Path

UTC = timezone.utc
HOUR = timedelta(hours=1)
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
ZERO = Decimal(0)
OUTPUTS = ["cache_plan.csv", "pool_curves.psv", "pool_hourly.tsv", "hourly_rollup.tsv", "rates_used.csv",
           "ruleset_used.json", "dedup_report.json", "source_lineage.json", "applied_adjustments.jsonl",
           "project_resolution.csv", "scope_projects.csv", "excluded_queries.jsonl", "reservation_dispositions.csv",
           "excluded_pools.jsonl", "cluster_commitments.jsonl", "family_rollup.json", "cluster_rollup.xml", "chargeback.csv", "team_rollup.json",
           "plan_summary.json", "variance_vs_published.csv", "reconciliation.md"]
Q3 = Decimal("0.001")
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")
UNIT_DIV = {"gib": Decimal(1), "mib": Decimal(1024), "kib": Decimal(1048576), "cgib": Decimal(100)}


# ----------------------------------------------------------------------------- basics
def norm(v) -> str:
    s = str(v).strip()
    while len(s) > 1 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1].strip()
    return s.upper()


def unq(v: str) -> str:
    v = v.strip()
    if len(v) > 1 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def tzof(text: str) -> timezone:
    t = text.strip()
    sign = -1 if t.startswith("-") else 1
    hh, mm = t.lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(text: str) -> datetime:
    return datetime.fromisoformat(unq(text).replace("Z", "+00:00")).astimezone(UTC)


def plain(d: Decimal) -> str:
    if d == 0:
        return "0"
    s = format(d.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def cents(d: Decimal) -> int:
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def pct(num: Decimal, den: Decimal) -> str:
    return str((num * 100 / den).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def dict_rows(text: str, sep: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=sep))


def yaml_sections(text: str) -> tuple[dict, dict]:
    """Tiny reader for the flat YAML shapes used in the corpus."""
    top: dict[str, str] = {}
    lists: dict[str, list[dict]] = {}
    current = None
    item = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0] not in " -":
            key, _, val = line.partition(":")
            key = key.strip()
            if val.strip():
                top[key] = unq(val)
                current = None
            else:
                current = key
                lists[current] = []
            item = None
            continue
        if current is None:
            current = ""
            lists.setdefault("", [])
        if stripped.startswith("- "):
            key, _, val = stripped[2:].partition(":")
            item = {key.strip(): unq(val)}
            lists[current].append(item)
        elif item is not None:
            key, _, val = stripped.partition(":")
            item[key.strip()] = unq(val)
    return top, lists


def sheet(path: Path, name: str) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        target = None
        for s in wb.iter(NS + "sheet"):
            if s.get("name") == name:
                target = rels[s.get(RID)]
        if target is None:
            raise SystemExit(f"sheet {name} not found in {path.name}")
        part = target.lstrip("/")
        if not part.startswith("xl/"):
            part = "xl/" + part
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        ws = ET.fromstring(z.read(part))
    out = []
    for row in ws.iter(NS + "row"):
        cells = {}
        for c in row.iter(NS + "c"):
            col = "".join(ch for ch in c.get("r") if ch.isalpha())
            kind = c.get("t")
            if kind == "inlineStr":
                cells[col] = "".join(t.text or "" for t in c.iter(NS + "t"))
            else:
                v = c.find(NS + "v")
                if v is None:
                    continue
                cells[col] = shared[int(v.text)] if kind == "s" else v.text
        out.append(cells)
    return out


def pdf_tokens(text: str):
    """Yield ("op", name) and ("val", value) tokens of a page content stream."""
    i, n = 0, len(text)
    stack: list[list] = []
    out: list = []

    def emit(v) -> None:
        (stack[-1] if stack else out).append(v)

    while i < n:
        ch = text[i]
        if ch in " \t\r\n\f":
            i += 1
        elif ch == "(":
            depth, buf, i = 1, [], i + 1
            while True:
                ch = text[i]
                if ch == "\\":
                    nxt = text[i + 1]
                    if nxt in "01234567":
                        j = i + 1
                        while j < i + 4 and text[j] in "01234567":
                            j += 1
                        buf.append(chr(int(text[i + 1:j], 8)))
                        i = j
                        continue
                    buf.append({"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f"}.get(nxt, nxt))
                    i += 2
                    continue
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                buf.append(ch)
                i += 1
            emit(("val", "".join(buf)))
        elif ch == "<":
            j = text.index(">", i)
            hx = "".join(text[i + 1:j].split())
            if len(hx) % 2:
                hx += "0"
            emit(("val", bytes.fromhex(hx).decode("latin-1")))
            i = j + 1
        elif ch == "[":
            stack.append([])
            i += 1
        elif ch == "]":
            arr = stack.pop()
            emit(("val", [v for _, v in arr]))
            i += 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n\f()<>[]":
                j += 1
            word = text[i:j]
            i = j
            if re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)", word):
                emit(("val", float(word)))
            elif word.startswith("/"):
                emit(("val", word))
            else:
                emit(("op", word))
    return out


def pdf_rows(path: Path) -> list[list[str]]:
    """Rows of text cells of every page, pages in page-tree order, rows top down, cells left to right."""
    data = path.read_bytes()
    objects: dict[int, bytes] = {}
    for m in re.finditer(rb"(\d+) 0 obj\n(.*?)\nendobj", data, re.S):
        objects[int(m.group(1))] = m.group(2)
    pages_obj = next(b for b in objects.values() if re.search(rb"/Type /Pages\b", b))
    kids = [int(x) for x in re.findall(rb"(\d+) 0 R", re.search(rb"/Kids \[(.*?)\]", pages_obj, re.S).group(1))]
    rows: list[list[str]] = []
    for kid in kids:
        cont = int(re.search(rb"/Contents (\d+) 0 R", objects[kid]).group(1))
        body = objects[cont]
        length = int(re.search(rb"/Length (\d+)", body).group(1))
        s = body.index(b"stream\n") + len(b"stream\n")
        text = zlib.decompress(body[s:s + length]).decode("latin-1")
        cells: list[tuple[float, float, str]] = []
        ops: list = []
        x = y = 0.0
        for kind, v in pdf_tokens(text):
            if kind == "val":
                ops.append(v)
                continue
            if v == "Tm":
                x, y = ops[-2], ops[-1]
            elif v == "Tj":
                cells.append((y, x, ops[-1]))
            elif v == "TJ":
                cells.append((y, x, "".join(p for p in ops[-1] if isinstance(p, str))))
            ops = []
        by_y: dict[float, list[tuple[float, str]]] = {}
        for cy, cx, s_ in cells:
            by_y.setdefault(cy, []).append((cx, s_))
        for cy in sorted(by_y, reverse=True):
            rows.append([s_ for _, s_ in sorted(by_y[cy])])
    return rows


# ----------------------------------------------------------------------------- feeds
def read_feed(path: Path, layout: str) -> list[tuple]:
    """Return rows as (qid, ts, project, cluster, template, size, volume, option, status, rev)."""
    if layout in ("sqlite_rows", "db_rows"):
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        if layout == "sqlite_rows":
            q = ("SELECT query_id, started_utc, project_id, cluster, template_id, wh_size, scanned_gib, cache_option, "
                 "query_status, revision FROM query_log")
        else:
            q = "SELECT qid, ep, prj, clu, tpl, wh, cg, oc, sc, rv FROM ql"
        rows = [tuple(str(x) for x in r) for r in con.execute(q)]
        con.close()
        return rows
    text = path.read_text(encoding="utf-8")
    rows: list[tuple] = []
    if layout == "jsonl_flat":
        for line in text.splitlines():
            if line.strip():
                o = json.loads(line)
                rows.append((o["qid"], o["start"], o["proj"], o["clu"], o["tpl"], o["wh"], o["gib"], o["opt"], o["st"], o["rev"]))
    elif layout == "ndjson_nested":
        for line in text.splitlines():
            if line.strip():
                o = json.loads(line, parse_float=str, parse_int=str)
                c = o["ctx"]
                rows.append((o["query"]["id"], o["scan"]["start"], c["project"], c["cluster"], c["template"], c["size"],
                             o["scan"]["mib"], o["bill"]["option"], o["bill"]["status"], o["query"]["rev"]))
    elif layout == "csv_a":
        for r in dict_rows(text, ","):
            rows.append((r["query_id"], r["started_utc"], r["project_id"], r["cluster"], r["template_id"], r["wh_size"],
                         r["scanned_gib"], r["cache_option"], r["query_status"], r["revision"]))
    elif layout == "tsv_epoch":
        for r in dict_rows(text, "\t"):
            rows.append((r["id"], r["epoch_s"], r["proj"], r["clu"], r["tpl"], r["wh"], r["scan_kib"], r["opt"], r["st"], r["rev"]))
    elif layout == "psv_local":
        for r in dict_rows(text, "|"):
            rows.append((r["id"], r["local_start"], r["proj"], r["clu"], r["tpl"], r["wh"], r["gib"], r["opt"], r["st"], r["rev"]))
    elif layout == "txt_fixed":
        for line in text.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            rows.append((line[0:12], line[12:26], line[26:38], line[38:63], line[63:73], line[73:77], line[77:89],
                         line[89:91], line[91:92], line[92:95]))
    elif layout == "xml_attr":
        for e in ET.fromstring(text).iter("q"):
            a = e.attrib
            rows.append((a["id"], a["t"], a["p"], a["c"], a["tp"], a["w"], a["g"], a["o"], a["s"], a["v"]))
    elif layout == "yaml_list":
        for i in yaml_sections(text)[1].get("records", []):
            rows.append((i["id"], i["start"], i["project"], i["cluster"], i["template"], i["size"], i["gib"], i["option"], i["status"], i["rev"]))
    elif layout == "json_array":
        for o in json.loads(text, parse_float=str, parse_int=str)["export"]["rows"]:
            rows.append((o["queryId"], o["epochMillis"], o["projectId"], o["clusterCode"], o["templateId"], o["whSize"],
                         o["scannedMib"], o["option"], o["status"], o["revision"]))
    elif layout == "csv_offset":
        for r in dict_rows(text, ","):
            rows.append((r["query"], r["ts_offset"], r["project"], r["cluster"], r["template"], r["size"], r["kib"], r["opt"], r["code"], r["rev"]))
    elif layout == "xml_elem":
        for e in ET.fromstring(text).iter("query"):
            g = {c.tag: c.text or "" for c in e}
            rows.append((g["id"], g["epoch"], g["project"], g["cluster"], g["template"], g["size"], g["gib"], g["option"], g["status"], g["rev"]))
    elif layout == "yml_list":
        for i in yaml_sections(text)[1].get("", []):
            size, _, tpl = i["shape"].partition("@")
            rows.append((i["qid"], i["local"], i["prj"], i["clu"], tpl, size, i["gib"], i["o"], i["s"], i["rev"]))
    elif layout == "json_keyed":
        for key, o in json.loads(text, parse_float=str, parse_int=str).items():
            rows.append((key, o["ms"], o["p"], o["c"], o["t"], o["w"], o["mib"], o["o"], o["s"], o["v"]))
    elif layout == "txt_kv":
        pat = re.compile(r'(\w+)=("[^"]*"|\S+)')
        for line in text.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            kv = {k: unq(v) for k, v in pat.findall(line)}
            rows.append((kv["query"], kv["at"], kv["project"], kv["cluster"], kv["template"], kv["size"], kv["gib"], kv["option"], kv["state"], kv["rev"]))
    else:
        raise SystemExit(f"unknown layout {layout}")
    return [tuple(str(x) for x in r) for r in rows]


# ----------------------------------------------------------------------------- plan
class Plan:
    def __init__(self, data: Path) -> None:
        self.data = data
        top, lists = yaml_sections((data / "plan_profile_qa4.yml").read_text(encoding="utf-8"))
        self.top = top
        self.bill = tzof(top["billing_offset"])
        self.w0_local = datetime.fromisoformat(top["lookback_start_local"])
        self.w0 = self.w0_local.replace(tzinfo=self.bill).astimezone(UTC)
        self.w1 = datetime.fromisoformat(top["lookback_end_local"]).replace(tzinfo=self.bill).astimezone(UTC)
        self.hours = int((self.w1 - self.w0) / HOUR)
        self.horizon = parse_utc(top["horizon_end_utc"])
        self.org = norm(top["org_id"])

        _, cl = yaml_sections((data / "cluster_aliases.yaml").read_text(encoding="utf-8"))
        self.alias = {norm(i["alias"]): norm(i["canonical"]) for i in cl["clusters"]}
        self.merge: dict[str, tuple[str, datetime]] = {}
        for r in dict_rows((data / "project_merges.psv").read_text(encoding="utf-8"), "|"):
            eff = datetime.fromisoformat(r["merged_on"].strip()).replace(tzinfo=self.bill).astimezone(UTC)
            self.merge[norm(r["from_project"])] = (norm(r["merged_into"]), eff)

        self.scope_clusters = {self.cluster(i["cluster"]) for i in lists.get("clusters_in_scope", [])}
        self.dev = {self.project(i["project"], self.w1)[0] for i in lists.get("dev_projects", [])}
        self.outage: dict[str, list[tuple[datetime, datetime]]] = {}
        for i in lists.get("outage_windows", []):
            a = datetime.fromisoformat(i["from_local"]).replace(tzinfo=self.bill).astimezone(UTC)
            b = datetime.fromisoformat(i["to_local"]).replace(tzinfo=self.bill).astimezone(UTC)
            self.outage.setdefault(self.cluster(i["cluster"]), []).append((a, b))

        self.templates = {}
        section = None
        for line in (data / "feed_layouts.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            if section and section.startswith("Appendix T") and line.lstrip().startswith("|"):
                parts = [p.strip() for p in line.strip().strip("|").split("|")]
                if len(parts) < 2 or parts[0] == "template_id" or not parts[0].strip("-"):
                    continue
                self.templates[norm(parts[0])] = parts[1].lower()

        book = data / "capacity_workbook_fy26.xlsx"
        with zipfile.ZipFile(book) as z:
            pr = ET.fromstring(z.read("xl/workbook.xml")).find(NS + "workbookPr")
        flag = (pr.get("date1904") if pr is not None else None) or "0"
        epoch = date(1904, 1, 1) if flag.strip().lower() in ("1", "true") else date(1899, 12, 30)
        track = norm(top["ruleset_track"])
        best = None
        for c in sheet(book, "Adoptions"):
            if (c.get("A") or "").strip() in ("", "adoption_id"):
                continue
            if norm(c.get("B", "")) != track or c.get("E", "").strip().upper() != "ADOPTED":
                continue
            eff = epoch + timedelta(days=int(Decimal(c["D"].strip())))
            if eff <= self.w0_local.date() and (best is None or eff > best[0]):
                best = (eff, c["C"].strip(), norm(c["A"]))
        self.effective_date, self.sheet_name, self.adoption_id = best
        self.plan_kv = {}
        self.fams = {}
        for c in sheet(book, self.sheet_name):
            tag = (c.get("A") or "").strip()
            if tag == "PLAN":
                self.plan_kv[c["B"].strip()] = c["C"].strip()
            elif tag == "FAM":
                def num(col: str) -> int:
                    return int(Decimal(c[col].strip()))
                self.fams[c["B"].strip().lower()] = {
                    "eligible": c["C"].strip().lower() in ("y", "yes", "true", "1"),
                    "node_units": num("D"), "min_nodes": num("E"), "family_cap": num("F"), "growth_pct": num("G"),
                    "tier_units": num("H"), "tier_discount_pct": num("I"), "mem_units_per_node": num("J")}
        self.cap = int(Decimal(self.plan_kv["node_cap_total"]))
        self.mem_budget = int(Decimal(self.plan_kv["mem_budget_units"]))
        self.factor = {}
        for c in sheet(book, "ScanFactors"):
            eng = (c.get("A") or "").strip().lower()
            if eng and eng != "engine":
                self.factor[eng] = Decimal(c["B"].strip())
        self.offset = {}
        for c in sheet(book, "Clusters"):
            cc = (c.get("A") or "").strip()
            if cc and cc != "cluster":
                self.offset[norm(cc)] = tzof(c["B"])

        self.rates: dict[tuple[str, str], list[str]] = {}
        self.rulings = {}
        self.errata = []
        self.commit: dict[str, int] = {}
        table = None
        for cells in pdf_rows(data / "pricing_bulletin_q4.pdf"):
            if len(cells) == 1:
                m = re.match(r"Table ([A-Z]-\d)", cells[0])
                if m:
                    table = m.group(1)
                continue
            if cells[0] in ("family", "erratum_id", "reservation_id", "cluster"):
                continue
            if table == "R-2":
                self.rates[(cells[0].lower(), self.cluster(cells[1]))] = [cells[2], cells[3]]
            elif table == "E-1":
                self.errata.append((cells[0].strip(), cells[1].strip().lower(), self.cluster(cells[2]), cells[3].strip(), cells[4].strip(), cells[5].strip().upper()))
            elif table == "C-1":
                self.rulings[norm(cells[0])] = (cells[1].strip().upper(), cells[2].strip())
            elif table == "M-1":
                self.commit[self.cluster(cells[0])] = int(cells[1].strip())
        for _eid, fam, clu, field, value, status in sorted(self.errata):
            if status == "IN FORCE":
                self.rates[(fam, clu)][0 if field == "scan_rate_cents" else 1] = value

        self.registry = {}
        for r in dict_rows((data / "proj_registry_archive.tsv").read_text(encoding="utf-8"), "\t"):
            closed = r["Closed"].strip()
            self.registry[norm(r["PROJ"])] = {"org": norm(r["Org"]), "team": norm(r["Team"]), "status": r["Status"].strip().upper(),
                                              "closed": datetime.strptime(closed, "%d/%m/%Y").date() if closed else None}
        for r in dict_rows((data / "proj_registry_main.csv").read_text(encoding="utf-8"), ","):
            closed = r["closed_on"].strip()
            self.registry[norm(r["project_id"])] = {"org": norm(r["org_id"]), "team": norm(r["team"]),
                                                    "status": r["project_status"].strip().upper(),
                                                    "closed": date.fromisoformat(closed) if closed else None}

    # ------------------------------------------------------------------ lookups
    def cluster(self, tok: str) -> str:
        t = norm(tok)
        return self.alias.get(t, t)

    def project(self, tok: str, at: datetime) -> tuple[str, int]:
        cur = norm(tok)
        walk = [cur]
        while cur in self.merge and self.merge[cur][1] <= at:
            cur = self.merge[cur][0]
            if cur in walk:
                return min(walk[walk.index(cur):]), len(walk)
            walk.append(cur)
        return cur, len(walk) - 1

    def scope_state(self, proj: str) -> str:
        r = self.registry.get(proj)
        if r is None:
            return "UNKNOWN_PROJECT"
        if r["org"] != self.org:
            return "OTHER_ORG"
        if r["status"] == "CLOSED" and r["closed"] is not None and r["closed"] < self.w0_local.date():
            return "CLOSED_PROJECT"
        if proj in self.dev:
            return "DEV_PROJECT"
        return ""

    def is_outage(self, clu: str, h: int) -> bool:
        start = self.w0 + HOUR * h
        return any(a <= start < b for a, b in self.outage.get(clu, ()))

    def when(self, raw: str, conv: str, ctok: str) -> datetime:
        v = unq(raw)
        if conv in ("iso_z", "iso_offset"):
            return parse_utc(v)
        if conv == "epoch_s":
            return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=int(v))
        if conv == "epoch_ms":
            return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=int(v))
        if conv == "compact_utc":
            return datetime.strptime(v, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        wall = datetime.strptime(v.replace("T", " "), "%Y-%m-%d %H:%M:%S")
        tz = self.bill if conv == "local_billing" else self.offset[self.cluster(ctok)]
        return wall.replace(tzinfo=tz).astimezone(UTC)

    def eligible(self, fam: str) -> bool:
        return fam in self.fams and self.fams[fam]["eligible"]

    # ------------------------------------------------------------------ stages
    def ingest(self) -> None:
        manifest = json.loads((self.data / "ingest_manifest_r7.json").read_text(encoding="utf-8"))
        best: dict[str, tuple[int, str, dict]] = {}
        self.lineage = {}
        rows_read = dups = 0
        for shard in manifest["shards"]:
            fn = shard["file"]
            omap = {k.strip(): v for k, v in shard["option_codes"].items()}
            smap = {k.strip(): v for k, v in shard["status_codes"].items()}
            div = UNIT_DIV[shard["qty_unit"]]
            rows = read_feed(self.data / fn, shard["layout"])
            self.lineage[fn] = {"rows": len(rows), "kept": 0}
            for qid, ts, pj, clu, tpl, size, vol, opt, stat, rev in rows:
                rows_read += 1
                key = norm(qid)
                r = int(rev)
                if key in best:
                    dups += 1
                    if best[key][0] >= r:
                        continue
                best[key] = (r, fn, {"t": self.when(ts, shard["ts_convention"], clu), "proj": pj, "cl": clu, "tpl": norm(tpl),
                                     "size": size.strip().lower(), "gib": Decimal(vol.strip()) / div,
                                     "opt": omap[opt.strip()], "st": smap[stat.strip()]})
        self.live = {}
        voided = 0
        for key, (_, fn, rec) in best.items():
            if rec["st"] == "V":
                voided += 1
                continue
            self.live[key] = rec
            self.lineage[fn]["kept"] += 1
        self.dedup = {"rows_read": rows_read, "duplicate_rows_dropped": dups, "voided_rows": voided, "live_queries": len(self.live)}

    def adjustments(self) -> None:
        entries = []
        for line in (self.data / "scan_adjustments.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                e["journal"] = "jsonl"
                entries.append(e)
        for el in ET.fromstring((self.data / "scan_adjustments_late.xml").read_text(encoding="utf-8")).iter("entry"):
            e = {c.tag: (c.text or "").strip() for c in el}
            e["query_id"] = e.pop("query")
            e["seq"] = el.get("seq")
            e["status"] = el.get("status")
            e["journal"] = "xml"
            entries.append(e)
        entries.sort(key=lambda e: int(e["seq"]))
        self.applied = []
        for e in entries:
            if str(e["status"]).strip().lower() != "posted":
                continue
            op = e["op"].strip().upper()
            key = norm(e["query_id"])
            if op == "ADD":
                if key in self.live:
                    outcome = "skipped_duplicate"
                else:
                    outcome = "applied"
                    self.live[key] = {"t": parse_utc(e["usage_start_utc"]), "proj": e["project"], "cl": e["cluster"],
                                      "tpl": norm(e["template"]), "size": e["size"].strip().lower(),
                                      "gib": Decimal(str(e["quantity_gib"]).strip()), "opt": e["option"].strip().upper(), "st": "F"}
            elif key not in self.live:
                outcome = "skipped_missing"
            else:
                outcome = "applied"
                if op == "VOID":
                    del self.live[key]
                elif op == "SETQTY":
                    self.live[key]["gib"] = Decimal(str(e["quantity_gib"]).strip())
                elif op == "MOVE":
                    self.live[key]["proj"] = e["project"]
                elif op == "RETAG":
                    self.live[key]["tpl"] = norm(e["template"])
            self.applied.append({"seq": int(e["seq"]), "journal": e["journal"], "query_id": key, "op": op, "outcome": outcome})

    def classify(self) -> None:
        self.excluded = []
        self.out_of_window = 0
        self.usage: dict[str, dict[int, Decimal]] = {}
        self.proj_usage: dict[str, dict[str, Decimal]] = {}
        self.pool_key: dict[str, tuple[str, str]] = {}
        for key in sorted(self.live):
            q = self.live[key]
            if q["t"] < self.w0 or q["t"] >= self.w1:
                self.out_of_window += 1
                continue
            proj = self.project(q["proj"], q["t"])[0]
            clu = self.cluster(q["cl"])
            fam = self.templates[q["tpl"]]
            h = int((q["t"] - self.w0) / HOUR)
            reason = self.scope_state(proj)
            if not reason and clu not in self.scope_clusters:
                reason = "CLUSTER_OUT_OF_SCOPE"
            if not reason and not self.eligible(fam):
                reason = "INELIGIBLE_FAMILY"
            if not reason and q["opt"] == "B":
                reason = "BATCH_QUERY"
            if not reason and self.is_outage(clu, h):
                reason = "OUTAGE_HOUR"
            if reason:
                self.excluded.append({"query_id": key, "reason": reason})
                continue
            pid = f"{fam.upper()}@{clu}"
            self.pool_key[pid] = (fam, clu)
            units = (q["gib"] * self.factor[f"{fam}.{q['size']}"]).quantize(Q3, rounding=ROUND_HALF_EVEN)
            hu = self.usage.setdefault(pid, {})
            hu[h] = hu.get(h, ZERO) + units
            pu = self.proj_usage.setdefault(pid, {})
            pu[proj] = pu.get(proj, ZERO) + units

    def reservations(self) -> None:
        self.netted = {}
        self.dispositions = []
        for el in ET.fromstring((self.data / "cache_reservations.xml").read_text(encoding="utf-8")).iter("reservation"):
            rid = norm(el.get("id"))
            fam = el.get("family").strip().lower()
            clu = self.cluster(el.get("cluster"))
            owner = self.project(el.get("owner"), self.w1)[0]
            units = Decimal(el.get("units").strip())
            ruling, revised = self.rulings.get(rid, ("", ""))
            end = parse_utc(revised) if ruling == "EXTENDED" else parse_utc(el.get("end_utc"))
            pid = f"{fam.upper()}@{clu}"
            if ruling == "CANCELLED":
                status = "CANCELLED"
            elif el.get("state").strip().upper() != "ACTIVE":
                status = "NOT_ACTIVE"
            elif self.scope_state(owner):
                status = "OWNER_OUT_OF_SCOPE"
            elif clu not in self.scope_clusters or not self.eligible(fam):
                status = "NO_POOL"
            elif end < self.horizon:
                status = "LAPSES"
            else:
                status = "NETTED"
                self.netted[pid] = self.netted.get(pid, ZERO) + units
            self.dispositions.append([rid, pid, owner, plain(units), iso(end), status])
        self.dispositions.sort()

    @staticmethod
    def rate_at(info: dict, c: Decimal) -> Decimal:
        if c >= info["tier"]:
            return (info["nd"] * (100 - info["tp"]) / 100).quantize(Q4, rounding=ROUND_HALF_EVEN)
        return info["nd"]

    def curves(self) -> None:
        self.pools = {}
        self.excluded_pools = []
        for pid in sorted(self.usage):
            fam, clu = self.pool_key[pid]
            cfg = self.fams[fam]
            valid = [h for h in range(self.hours) if not self.is_outage(clu, h)]
            net = self.netted.get(pid, ZERO)
            grow = Decimal(100 + cfg["growth_pct"]) / 100
            load = {}
            for h in valid:
                v = (self.usage[pid].get(h, ZERO) * grow).quantize(Q2, rounding=ROUND_HALF_EVEN) - net
                load[h] = v if v > 0 else ZERO
            sc, nd = (Decimal(x) for x in self.rates[(fam, clu)])
            info = {"fam": fam, "cl": clu, "valid": valid, "load": load, "sc": sc, "nd": nd, "unit": cfg["node_units"],
                    "min": cfg["min_nodes"], "net": net, "growth": cfg["growth_pct"], "rates": self.rates[(fam, clu)],
                    "tier": cfg["tier_units"], "tp": cfg["tier_discount_pct"], "mu": cfg["mem_units_per_node"]}
            self.pools[pid] = info
            peak = max(load.values()) if load else ZERO
            kmax = int((peak / info["unit"]).to_integral_value(rounding=ROUND_FLOOR))
            if peak == 0:
                self.excluded_pools.append({"pool_id": pid, "reason": "NO_RESIDUAL"})
                continue
            if kmax < info["min"]:
                self.excluded_pools.append({"pool_id": pid, "reason": "BELOW_MIN_NODES"})
                continue
            levels = [0] + list(range(info["min"], kmax + 1))
            curve = {}
            nv = len(valid)
            for k in levels:
                c = Decimal(k * info["unit"])
                served = sum((x if x < c else c) for x in load.values())
                curve[k] = (served, sc * served - self.rate_at(info, c) * nv * c)
            info["curve"] = curve
        self.cands = [p for p in sorted(self.pools) if "curve" in self.pools[p]]

    def optimise(self) -> None:
        closed: set[str] = set()
        self.rounds = []
        while True:
            self.solve(closed)
            nodes: dict[str, int] = {}
            saving: dict[str, Decimal] = {}
            for p in self.cands:
                clu = self.pools[p]["cl"]
                nodes[clu] = nodes.get(clu, 0) + self.k[p]
                saving[clu] = saving.get(clu, ZERO) + self.pools[p]["curve"][self.k[p]][1]
            short = [c for c in sorted(nodes) if 0 < nodes[c] < self.commit.get(c, 0)]
            if not short:
                return
            worst = min(short, key=lambda c: (saving[c], c))
            self.rounds.append({"round": len(self.rounds) + 1, "cluster": worst, "planned_nodes": nodes[worst],
                                "min_nodes": self.commit[worst], "saving_exact_cents": plain(saving[worst]),
                                "short_clusters": len(short)})
            closed.add(worst)

    def solve(self, closed: set) -> None:
        fams = sorted({self.pools[p]["fam"] for p in self.cands}, key=str.upper)
        per_family = {}
        for fam in fams:
            cap = self.fams[fam]["family_cap"]
            members = [p for p in self.cands if self.pools[p]["fam"] == fam]
            # dp[t] = (saving, pool vector) for exactly t nodes in the family
            dp: dict[int, tuple[Decimal, tuple]] = {0: (ZERO, ())}
            for p in members:
                new: dict[int, tuple[Decimal, tuple]] = {}
                for t, (val, vec) in dp.items():
                    for k, (_, s) in self.pools[p]["curve"].items():
                        if t + k > cap or (k and self.pools[p]["cl"] in closed):
                            continue
                        cand = (val + s, vec + (k,))
                        old = new.get(t + k)
                        if old is None or cand[0] > old[0] or (cand[0] == old[0] and cand[1] < old[1]):
                            new[t + k] = cand
                dp = new
            per_family[fam] = (members, dp)
        # states keyed by (nodes, memory) over families in order
        states: dict[tuple[int, int], tuple[Decimal, tuple]] = {(0, 0): (ZERO, ())}
        for fam in fams:
            mu = self.fams[fam]["mem_units_per_node"]
            dp = per_family[fam][1]
            new: dict[tuple[int, int], tuple[Decimal, tuple]] = {}
            for (n, m), (val, tots) in states.items():
                for t in sorted(dp):
                    if n + t > self.cap or m + t * mu > self.mem_budget:
                        continue
                    cand = (val + dp[t][0], tots + (t,))
                    key = (n + t, m + t * mu)
                    old = new.get(key)
                    if old is None or cand[0] > old[0] or (cand[0] == old[0] and cand[1] < old[1]):
                        new[key] = cand
            states = new
        best_key = None
        for key, (val, _) in states.items():
            if best_key is None:
                best_key = key
                continue
            bv = states[best_key][0]
            if val > bv or (val == bv and key < best_key):
                best_key = key
        self.total_exact, tots = states[best_key]
        self.k = {}
        for fam, t in zip(fams, tots):
            members, dp = per_family[fam]
            for p, k in zip(members, dp[t][1]):
                self.k[p] = k

    def chargeback(self) -> None:
        self.charge = []
        for p in self.cands:
            k = self.k[p]
            if k == 0:
                continue
            saving = cents(self.pools[p]["curve"][k][1])
            usage = self.proj_usage[p]
            total = sum(usage.values(), ZERO)
            exact = {a: Decimal(saving) * u / total for a, u in usage.items()}
            floor = {a: int(v.to_integral_value(rounding=ROUND_FLOOR)) for a, v in exact.items()}
            left = saving - sum(floor.values())
            order = sorted(usage, key=lambda a: (-(exact[a] - floor[a]), a))
            for a in order[:left]:
                floor[a] += 1
            for a in sorted(usage):
                self.charge.append([p, a, self.registry[a]["team"], plain(usage[a]), str(floor[a])])

    # ------------------------------------------------------------------ output
    def render(self) -> dict[str, str]:
        f: dict[str, str] = {}

        def lines(rows, sep):
            return "".join(sep.join(str(c) for c in r) + "\n" for r in rows)

        def j(o):
            return json.dumps(o, sort_keys=True) + "\n"

        P = self.pools
        units = {p: Decimal(self.k[p] * P[p]["unit"]) for p in self.cands}
        mem = {p: self.k[p] * P[p]["mu"] for p in self.cands}
        sav = {p: cents(P[p]["curve"][self.k[p]][1]) for p in self.cands}

        rows = [["pool_id", "family", "cluster", "nodes", "cache_units", "mem_units", "hourly_node_cents", "saving_cents", "served_pct", "utilization_pct"]]
        for p in self.cands:
            info, k, c = P[p], self.k[p], units[p]
            served = info["curve"][k][0]
            util = pct(served, c * len(info["valid"])) if k else ""
            rows.append([p, info["fam"], info["cl"], k, plain(c), mem[p], plain(c * self.rate_at(info, c)), sav[p],
                         pct(served, sum(info["load"].values(), ZERO)), util])
        f["cache_plan.csv"] = lines(rows, ",")

        rows = [["pool_id", "nodes", "cache_units", "served_unit_hours", "saving_exact_cents"]]
        for p in self.cands:
            for k in sorted(P[p]["curve"]):
                served, s = P[p]["curve"][k]
                rows.append([p, k, plain(Decimal(k * P[p]["unit"])), plain(served), plain(s)])
        f["pool_curves.psv"] = lines(rows, "|")

        rows = [["pool_id", "hour_index", "hour_start_utc", "usage_units", "load_units"]]
        for p in sorted(P):
            for h in P[p]["valid"]:
                rows.append([p, h, iso(self.w0 + HOUR * h), plain(self.usage[p].get(h, ZERO)), plain(P[p]["load"][h])])
        f["pool_hourly.tsv"] = lines(rows, "\t")

        rows = [["hour_index", "hour_start_utc", "pools_valid", "load_units", "cache_units", "served_units", "overflow_units"]]
        for h in range(self.hours):
            n = 0
            tl = tc = ts = to = ZERO
            for p in self.cands:
                if h not in P[p]["load"]:
                    continue
                n += 1
                ld, c = P[p]["load"][h], units[p]
                tl += ld
                tc += c
                ts += min(ld, c)
                to += max(ZERO, ld - c)
            rows.append([h, iso(self.w0 + HOUR * h), n, plain(tl), plain(tc), plain(ts), plain(to)])
        f["hourly_rollup.tsv"] = lines(rows, "\t")

        rows = [["pool_id", "family", "cluster", "scan_rate_cents", "node_rate_cents", "node_units", "min_nodes", "growth_pct",
                 "tier_units", "tier_discount_pct", "mem_units_per_node", "netted_units", "valid_hours"]]
        for p in sorted(P):
            i = P[p]
            rows.append([p, i["fam"], i["cl"], i["rates"][0], i["rates"][1], i["unit"], i["min"], i["growth"], i["tier"], i["tp"], i["mu"],
                         plain(i["net"]), len(i["valid"])])
        f["rates_used.csv"] = lines(rows, ",")

        fam_list = []
        for fam in sorted(self.fams, key=str.upper):
            d = dict(self.fams[fam])
            d["family"] = fam
            fam_list.append(d)
        f["ruleset_used.json"] = j({"sheet": self.sheet_name, "adoption_id": self.adoption_id,
                                    "effective_date": self.effective_date.isoformat(), "node_cap_total": self.cap, "mem_budget_units": self.mem_budget,
                                    "saving_rounding": self.plan_kv["saving_rounding"], "families": fam_list})
        f["dedup_report.json"] = j(self.dedup)
        f["source_lineage.json"] = j(self.lineage)
        f["applied_adjustments.jsonl"] = "".join(j(a) for a in self.applied)

        rows = [["alias", "canonical", "hops"]]
        for a in sorted(self.merge):
            c, n = self.project(a, self.w1)
            rows.append([a, c, n])
        f["project_resolution.csv"] = lines(rows, ",")

        rows = [["project_id", "team", "project_status", "scope"]]
        label = {"": "IN_SCOPE", "CLOSED_PROJECT": "CLOSED", "DEV_PROJECT": "DEV"}
        for a in sorted(self.registry):
            r = self.registry[a]
            if r["org"] == self.org:
                rows.append([a, r["team"], r["status"], label[self.scope_state(a)]])
        f["scope_projects.csv"] = lines(rows, ",")
        f["excluded_queries.jsonl"] = "".join(j(e) for e in self.excluded)
        f["reservation_dispositions.csv"] = lines([["reservation_id", "pool_id", "owner_project", "units", "effective_end_utc", "status"]]
                                                  + self.dispositions, ",")
        f["excluded_pools.jsonl"] = "".join(j(e) for e in self.excluded_pools)
        f["cluster_commitments.jsonl"] = "".join(j(e) for e in self.rounds)

        fr: dict[str, dict] = {}
        for p in self.cands:
            fam = P[p]["fam"]
            d = fr.setdefault(fam.upper(), {"pools": 0, "nodes": 0, "family_cap": self.fams[fam]["family_cap"], "mem_units": 0, "saving_cents": 0})
            d["pools"] += 1
            d["nodes"] += self.k[p]
            d["mem_units"] += mem[p]
            d["saving_cents"] += sav[p]
        f["family_rollup.json"] = j(fr)

        xml = [f'<clusters plan="{self.top["plan_id"]}">']
        for clu in sorted({P[p]["cl"] for p in self.cands}):
            ps = [p for p in self.cands if P[p]["cl"] == clu]
            xml.append(f'<cluster code="{clu}" pools="{len(ps)}" nodes="{sum(self.k[p] for p in ps)}" '
                       f'cache_units="{plain(sum((units[p] for p in ps), ZERO))}" mem_units="{sum(mem[p] for p in ps)}" '
                       f'saving_cents="{sum(sav[p] for p in ps)}"/>')
        xml.append("</clusters>")
        f["cluster_rollup.xml"] = "\n".join(xml) + "\n"

        f["chargeback.csv"] = lines([["pool_id", "project_id", "team", "usage_units", "allocated_cents"]] + self.charge, ",")
        teams: dict[str, dict] = {}
        seen: dict[str, set] = {}
        for p, a, t, _, c in self.charge:
            seen.setdefault(t, set()).add(a)
            d = teams.setdefault(t, {"projects": 0, "allocated_cents": 0})
            d["allocated_cents"] += int(c)
            d["projects"] = len(seen[t])
        f["team_rollup.json"] = j(teams)

        f["plan_summary.json"] = j({
            "plan_id": self.top["plan_id"], "ruleset_version": self.sheet_name, "lookback_hours": self.hours,
            "out_of_window_queries": self.out_of_window, "excluded_queries": len(self.excluded),
            "candidate_pools": len(self.cands), "selected_pools": sum(1 for p in self.cands if self.k[p]),
            "nodes_total": sum(self.k.values()), "node_cap_total": self.cap, "mem_units_total": sum(mem.values()),
            "mem_budget_units": self.mem_budget, "total_saving_cents": cents(self.total_exact),
            "chargeback_total_cents": sum(int(r[4]) for r in self.charge),
            "netted_units_total": plain(sum(self.netted.values(), ZERO)), "closure_rounds": len(self.rounds)})

        pub: dict[str, list[int]] = {}
        for r in dict_rows((self.data / self.top["published_plan"]).read_text(encoding="utf-8"), ","):
            e = pub.setdefault(norm(r["pool_id"]), [int(r["nodes"]), 0])
            e[1] += int(r["saving_cents"])
        rows = [["pool_id", "published_nodes", "corrected_nodes", "node_delta", "published_saving_cents", "corrected_saving_cents", "status"]]
        for p in sorted(set(pub) | set(self.cands)):
            pb, ps = pub[p] if p in pub else (None, None)
            cb = self.k.get(p)
            cs = sav.get(p)
            if pb is None:
                status = "NEW"
            elif cb is None:
                status = "DROPPED"
            else:
                status = "MATCH" if cb == pb else "CHANGED"
            rows.append([p, "" if pb is None else pb, "" if cb is None else cb, (cb or 0) - (pb or 0),
                         "" if ps is None else ps, "" if cs is None else cs, status])
        f["variance_vs_published.csv"] = lines(rows, ",")

        pf: dict[str, int] = {}
        for p, (b, _) in pub.items():
            fam = p.split("@")[0]
            pf[fam] = pf.get(fam, 0) + b
        cf: dict[str, int] = {}
        for p in self.cands:
            fam = P[p]["fam"].upper()
            cf[fam] = cf.get(fam, 0) + self.k[p]
        md = [f"# Plan {self.top['plan_id']} cache reconciliation", "",
              "| family | published_nodes | corrected_nodes | delta_nodes |", "|---|---|---|---|"]
        for fam in sorted(set(pf) | set(cf)):
            md.append(f"| {fam} | {pf.get(fam, 0)} | {cf.get(fam, 0)} | {cf.get(fam, 0) - pf.get(fam, 0)} |")
        tp, tc = sum(pf.values()), sum(cf.values())
        md.append(f"| ALL | {tp} | {tc} | {tc - tp} |")
        f["reconciliation.md"] = "\n".join(md) + "\n"
        return f


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: plan_cache.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, out = Path(argv[1]), Path(argv[2])
    plan = Plan(data)
    plan.ingest()
    plan.adjustments()
    plan.classify()
    plan.reservations()
    plan.curves()
    plan.optimise()
    plan.chargeback()
    files = plan.render()
    out.mkdir(parents=True, exist_ok=True)
    man = []
    for name in OUTPUTS:
        blob = files[name].encode("utf-8")
        (out / name).write_bytes(blob)
        man.append({"name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    (out / "manifest.json").write_text(json.dumps({"files": man}, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
