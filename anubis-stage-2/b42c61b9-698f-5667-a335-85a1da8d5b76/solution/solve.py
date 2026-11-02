#!/usr/bin/env python3
"""Reference readout program: python3 run_readout.py DATA_DIR OUT_DIR.

Recomputes the WAVE-26Q3 experiment portfolio readout from the shipped corpus, following
readout_analysis_handbook.md, the statistics governance memo (pdf) and the experiment
workbook (xlsx). Standard library only.
"""

from __future__ import annotations

import bisect
import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist

UTC = timezone.utc
DAY = timedelta(days=1)
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
MICRO = 10 ** 6
OUTPUTS = ["readout.csv", "arm_metrics.tsv", "winsor_caps.psv", "cuped.json", "srm_report.csv", "bh_family.csv",
           "guardrails.csv", "decisions.json", "unit_assignments.csv", "excluded_units.jsonl", "identity_resolution.csv",
           "dedup_report.json", "source_lineage.json", "refund_outcomes.jsonl", "order_valuation.psv",
           "metric_config_used.json", "experiment_windows.xml", "portfolio_summary.json", "variance_vs_published.csv",
           "reconciliation.md"]


# ----------------------------------------------------------------------------- small helpers
def unq(v: str) -> str:
    v = str(v).strip()
    while len(v) > 1 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1].strip()
    return v


def nid(v) -> str:
    return unq(v).upper()


def tzone(spec: str) -> timezone:
    spec = unq(spec)
    sign = -1 if spec.startswith("-") else 1
    hh, mm = spec.lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def half_even(fr: Fraction) -> int:
    q, r = divmod(fr.numerator, fr.denominator)
    if 2 * r > fr.denominator or (2 * r == fr.denominator and q % 2 == 1):
        q += 1
    return q


def f6(x) -> str:
    if isinstance(x, Fraction):
        v = half_even(x * MICRO)
        sign = "-" if v < 0 else ""
        v = abs(v)
        return f"{sign}{v // MICRO}.{v % MICRO:06d}"
    s = format(float(x), ".6f")
    return "0.000000" if s == "-0.000000" else s


def e6(x: float) -> str:
    return format(float(x), ".6e")


def truthy(v: str) -> bool:
    return unq(v).upper() in ("Y", "YES", "TRUE", "1")


def mini_yaml(text: str) -> tuple[dict[str, str], dict[str, list[dict[str, str]]]]:
    scalars: dict[str, str] = {}
    lists: dict[str, list[dict[str, str]]] = {}
    section = ""
    cur: dict[str, str] | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] not in " -":
            key, _, val = raw.partition(":")
            if val.strip():
                scalars[key.strip()] = unq(val)
            else:
                section = key.strip()
                lists.setdefault(section, [])
            cur = None
            continue
        body = raw.strip()
        if body.startswith("- "):
            key, _, val = body[2:].partition(":")
            cur = {key.strip(): unq(val)}
            lists.setdefault(section, []).append(cur)
        elif cur is not None and ":" in body:
            key, _, val = body.partition(":")
            cur[key.strip()] = unq(val)
    return scalars, lists


def delimited(text: str, sep: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=sep))


# ----------------------------------------------------------------------------- xlsx and pdf
def xlsx_sheets(path: Path) -> tuple[dict[str, list[list[str]]], date]:
    out: dict[str, list[list[str]]] = {}
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        pr = wb.find(NS + "workbookPr")
        epoch = date(1904, 1, 1) if pr is not None and pr.get("date1904") in ("1", "true") else date(1899, 12, 30)
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        for sh in wb.iter(NS + "sheet"):
            target = rels[sh.attrib[RID]]
            part = target.lstrip("/") if target.startswith("/") else "xl/" + target
            ws = ET.fromstring(z.read(part))
            grid = []
            for row in ws.iter(NS + "row"):
                cells: dict[int, str] = {}
                for c in row.iter(NS + "c"):
                    letters = re.match(r"[A-Z]+", c.attrib["r"]).group(0)
                    col = 0
                    for ch in letters:
                        col = col * 26 + ord(ch) - 64
                    kind = c.attrib.get("t")
                    if kind == "inlineStr":
                        cells[col - 1] = "".join(t.text or "" for t in c.iter(NS + "t"))
                    else:
                        v = c.find(NS + "v")
                        if v is not None and v.text is not None:
                            cells[col - 1] = shared[int(v.text)] if kind == "s" else v.text
                width = max(cells) + 1 if cells else 0
                grid.append([cells.get(i, "") for i in range(width)])
            out[sh.attrib["name"]] = grid
    return out, epoch


def cell_datetime(raw: str, epoch: date) -> datetime:
    """A workbook date cell: ISO text or a serial day count in the workbook's date system."""
    v = raw.strip()
    if re.fullmatch(r"\d+(\.\d+)?", v):
        days = Fraction(Decimal(v))
        whole = days.numerator // days.denominator
        secs = (days - whole) * 86400
        return datetime(epoch.year, epoch.month, epoch.day) + timedelta(days=whole, seconds=int(secs))
    return datetime.fromisoformat(v)


PDF_TOKEN = re.compile(r"\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|[-+]?\d*\.?\d+|[A-Za-z*'\"]+|/[^\s/\[\]()<>]+")


def pdf_string(tok: str) -> str:
    if tok.startswith("("):
        body = tok[1:-1]
        out, i = [], 0
        while i < len(body):
            if body[i] == "\\" and i + 1 < len(body):
                i += 1
            out.append(body[i])
            i += 1
        return "".join(out)
    return bytes.fromhex(re.sub(r"\s", "", tok[1:-1])).decode("latin-1")


def pdf_lines(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    lines: list[list[str]] = []
    for m in re.finditer(rb"<<([^<>]*?)>>\s*stream\r?\n", raw):
        head = m.group(1).decode("latin-1")
        n = re.search(r"/Length (\d+)", head)
        if not n:
            continue
        data = raw[m.end():m.end() + int(n.group(1))]
        if "FlateDecode" in head:
            data = zlib.decompress(data)
        runs: list[tuple[float, float, str]] = []
        stack: list = []
        x = y = 0.0
        arr: list | None = None
        for tok in PDF_TOKEN.findall(data.decode("latin-1")):
            if tok == "[":
                arr = []
            elif tok == "]":
                stack.append(arr or [])
                arr = None
            elif arr is not None:
                if tok[0] in "(<":
                    arr.append(pdf_string(tok))
            elif tok == "Tm":
                x, y = float(stack[-2]), float(stack[-1])
                stack = []
            elif tok == "Tj":
                runs.append((y, x, pdf_string(stack[-1])))
                stack = []
            elif tok == "TJ":
                runs.append((y, x, "".join(stack[-1])))
                stack = []
            elif tok in ("BT", "ET", "Tf"):
                stack = []
            else:
                stack.append(tok)
        by_y: dict[float, list[tuple[float, str]]] = {}
        for yy, xx, txt in runs:
            by_y.setdefault(yy, []).append((xx, txt))
        for yy in sorted(by_y, reverse=True):
            lines.append([t for _, t in sorted(by_y[yy])])
    return lines


def pdf_tables(path: Path) -> dict[str, list[list[str]]]:
    tables: dict[str, list[list[str]]] = {}
    current = None
    headers: dict[str, list[str]] = {}
    for cells in pdf_lines(path):
        if len(cells) == 1:
            m = re.match(r"Table ([A-Z]-\d+)\b", cells[0].strip())
            if m:
                current = m.group(1)
                tables.setdefault(current, [])
            continue
        if current is None or len(cells) < 3:
            continue
        if current not in headers:
            headers[current] = cells
            continue
        if cells == headers[current]:
            continue
        tables[current].append([c.strip() for c in cells])
    return {k: [dict(zip(headers[k], r)) for r in v] for k, v in tables.items() if k in headers}


# ----------------------------------------------------------------------------- feeds
def parse_time(raw, conv: str, exp_tz: timezone | None, rep_tz: timezone) -> datetime:
    s = unq(str(raw))
    if conv == "iso_z":
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if conv == "iso_offset":
        return datetime.fromisoformat(s).astimezone(UTC)
    if conv == "epoch_s":
        return datetime.fromtimestamp(int(s), UTC)
    if conv == "epoch_ms":
        return datetime.fromtimestamp(int(s) // 1000, UTC)
    if conv == "compact_utc":
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    if conv in ("local_experiment", "local_reporting"):
        tz = exp_tz if conv == "local_experiment" else rep_tz
        return datetime.fromisoformat(s.replace("T", " ")).replace(tzinfo=tz).astimezone(UTC)
    raise ValueError(conv)


def read_exposures(path: Path, layout: str) -> list[tuple]:
    """Return (id, time, unit, experiment, variant, status, revision) tuples."""
    if layout == "x_sqlite":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = con.execute("SELECT exposure_id, epoch_s, unit_token, experiment, variant, status, revision FROM exposure").fetchall()
        con.close()
        return rows
    text = path.read_text(encoding="utf-8")
    if layout == "x_jsonl":
        return [(o["eid"], o["ts"], o["unit"], o["exp"], o["arm"], o["st"], o["rev"]) for o in map(json.loads, filter(str.strip, text.splitlines()))]
    if layout == "x_ndjson":
        out = []
        for o in map(json.loads, filter(str.strip, text.splitlines())):
            out.append((o["event"]["id"], o["at"]["epoch"], o["subject"]["unit"], o["assign"]["experiment"], o["assign"]["variant"],
                        o["state"], o["event"]["rev"]))
        return out
    if layout == "x_csv":
        return [(r["exposure_id"], r["logged_at"], r["unit_token"], r["experiment"], r["variant"], r["status"], r["revision"]) for r in delimited(text, ",")]
    if layout == "x_tsv":
        return [(r["exposure"], r["ms"], r["unit"], r["exp"], r["variant"], r["state"], r["rev"]) for r in delimited(text, "\t")]
    if layout == "x_psv":
        return [(r["exposure"], r["local_time"], r["unit"], r["experiment"], r["variant"], r["status"], r["rev"]) for r in delimited(text, "|")]
    if layout == "x_txt":
        out = []
        for ln in text.splitlines():
            if not ln.strip() or ln.startswith("#"):
                continue
            out.append((ln[0:12], ln[12:26], ln[26:37], ln[37:53], ln[53:77], ln[77:78], ln[78:81]))
        return out
    if layout == "x_xml":
        return [(e.get("id"), e.get("t"), e.get("u"), e.get("e"), e.get("v"), e.get("s"), e.get("r")) for e in ET.fromstring(text).iter("x")]
    if layout == "x_yaml":
        return [(i["id"], i["ts"], i["unit"], i["experiment"], i["variant"], i["status"], i["rev"]) for i in mini_yaml(text)[1].get("records", [])]
    if layout == "x_json":
        return [(o["exposureId"], o["epochMillis"], o["unitToken"], o["experimentKey"], o["variantKey"], o["state"], o["revision"])
                for o in json.loads(text)["export"]["rows"]]
    raise ValueError(layout)


def read_orders(path: Path, layout: str) -> list[tuple]:
    """Return (id, time, unit, currency, amount, status, revision) tuples."""
    if layout == "o_db":
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = con.execute("SELECT oid, ep, uid, ccy, amt, st, rv FROM ord").fetchall()
        con.close()
        return rows
    text = path.read_text(encoding="utf-8")
    if layout == "o_csv":
        return [(r["order_id"], r["placed_at"], r["customer"], r["currency"], r["amount"], r["order_status"], r["revision"]) for r in delimited(text, ",")]
    if layout == "o_xml":
        out = []
        for e in ET.fromstring(text).iter("order"):
            g = {c.tag: (c.text or "") for c in e}
            out.append((g["id"], g["at"], g["customer"], g["ccy"], g["minor"], g["st"], g["rev"]))
        return out
    if layout == "o_yml":
        out = []
        for i in mini_yaml(text)[1].get("", []):
            amt, ccy = unq(i["money"]).split(" ")
            out.append((i["order"], i["local"], i["cust"], ccy, amt, i["s"], i["rev"]))
        return out
    if layout == "o_json":
        return [(k, o["ms"], o["u"], o["c"], o["a"], o["s"], o["v"]) for k, o in json.loads(text).items()]
    raise ValueError(layout)


# ----------------------------------------------------------------------------- main computation
class Readout:
    def __init__(self, data: Path):
        self.data = data
        self.load_reference()
        self.load_feeds()
        self.build_units()
        self.build_participants()
        self.build_orders()
        self.build_metrics()
        self.build_tests()

    # ------------------------------------------------------------------ reference
    def load_reference(self) -> None:
        d = self.data
        self.prof, plists = mini_yaml((d / "analysis_profile_w26.yml").read_text(encoding="utf-8"))
        self.cutoff = datetime.strptime(unq(self.prof["data_cutoff_utc"]), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        self.pre_days = int(self.prof["pre_period_days"])
        self.rep_tz = tzone(self.prof["reporting_offset"])
        _, alists = mini_yaml((d / "experiment_aliases.yaml").read_text(encoding="utf-8"))
        self.exp_alias = {nid(i["alias"]): nid(i["canonical"]) for i in alists.get("experiments", [])}
        self.var_alias: dict[tuple[str, str], str] = {}
        for i in alists.get("variants", []):
            self.var_alias[(self.canon_exp(i["experiment"]), unq(i["variant"]).lower())] = nid(i["arm"])
        self.scope = sorted({self.canon_exp(i["experiment"]) for i in plists.get("experiments_in_scope", [])})
        links = delimited((d / "identity_links.psv").read_text(encoding="utf-8"), "|")
        self.links = {nid(r["from_id"]): (nid(r["linked_to"]), datetime.fromisoformat(r["linked_on"].strip()).replace(tzinfo=UTC))
                      for r in links}
        self.internal = {self.resolve(i["unit"], self.cutoff)[0] for i in plists.get("internal_units", [])}

        sheets, epoch = xlsx_sheets(d / "experiment_workbook_w26.xlsx")
        self.fx_sheet = unq(self.prof["fx_sheet"])
        self.registry_version = unq(self.prof["registry_version"])
        self.registry = self.read_registry(sheets[self.registry_version])
        self.experiments: dict[str, dict] = {}
        rows = sheets["Experiments"]
        head = [c.strip() for c in rows[0]]
        for r in rows[1:]:
            rec = dict(zip(head, [c.strip() for c in r]))
            if not rec.get("experiment"):
                continue
            code = nid(rec["experiment"])
            tz = tzone(rec["tz_offset"])
            self.experiments[code] = {"tz_text": unq(rec["tz_offset"]), "tz": tz,
                                      "start_local": cell_datetime(rec["start_local"], epoch),
                                      "end_local": cell_datetime(rec["end_local"], epoch),
                                      "primary": rec["primary_metric"].strip().lower(), "team": rec["owner_team"].strip().lower(), "arms": {}}
        rows = sheets["Allocation"]
        head = [c.strip() for c in rows[0]]
        for r in rows[1:]:
            rec = dict(zip(head, [c.strip() for c in r]))
            if not rec.get("arm"):
                continue
            self.experiments[nid(rec["experiment"])]["arms"][nid(rec["arm"])] = (rec["role"].strip().lower(), unq(rec["weight_pct"]))
        self.minor_units = {}
        rows = sheets["Currencies"]
        for r in rows[1:]:
            if r and r[0].strip():
                self.minor_units[r[0].strip().upper()] = int(Decimal(r[1].strip()))
        self.fx: dict[str, list[tuple[date, str, Fraction]]] = {}
        for r in sheets[self.fx_sheet]:
            if len(r) < 4 or r[0].strip().lower() == "date" or not re.match(r"\d", r[0].strip()):
                continue
            ccy = r[1].strip().upper()
            self.fx.setdefault(ccy, []).append((cell_datetime(r[0], epoch).date(), r[2].strip().upper(), Fraction(Decimal(r[3].strip()))))
        for v in self.fx.values():
            v.sort()
        self.fx_days = {c: [x[0] for x in v] for c, v in self.fx.items()}

        tables = pdf_tables(d / "stats_governance_memo_w26.pdf")
        self.params = {r["parameter"]: r["value"] for r in tables["P-1"]}
        self.alpha = float(self.params["alpha_two_sided"])
        self.bh_q = float(self.params["bh_q"])
        self.srm_alpha = float(self.params["srm_alpha"])
        self.amendments = [r for r in tables["A-1"] if r["status"].upper() == "IN FORCE"]
        self.rulings: dict[str, tuple[str, str]] = {}
        for r in tables["X-1"]:
            if r["status"].upper() == "IN FORCE":
                self.rulings[self.canon_exp(r["experiment"])] = (r["ruling"].upper(), r["revised_end_local"])
        self.unit_rulings: dict[str, str] = {}
        for r in tables["U-1"]:
            if r["status"].upper() == "IN FORCE":
                self.unit_rulings[self.resolve(r["unit_token"], self.cutoff)[0]] = r["ruling"].upper()
        self.capacity = {r["owner_team"].strip().lower(): int(r["max_ship"]) for r in tables.get("C-1", [])}

        main = delimited((d / "unit_registry_main.csv").read_text(encoding="utf-8"), ",")
        legacy = delimited((d / "unit_registry_legacy.tsv").read_text(encoding="utf-8"), "\t")
        self.acct: dict[str, str] = {}
        for r in legacy:
            uid = nid(r["UNIT"])
            if not self.retired(uid):
                self.acct[uid] = r["AccountType"].strip().lower()
        for r in main:
            uid = nid(r["unit_id"])
            if not self.retired(uid):
                self.acct[uid] = r["account_type"].strip().lower()

        # windows
        for code, ex in self.experiments.items():
            ruling = self.rulings.get(code, ("NONE", "-"))
            end_local = datetime.fromisoformat(ruling[1]) if ruling[0] in ("EXTENDED", "SHORTENED") else ex["end_local"]
            ex["ruling"] = ruling[0]
            ex["start"] = ex["start_local"].replace(tzinfo=ex["tz"]).astimezone(UTC)
            ex["end"] = end_local.replace(tzinfo=ex["tz"]).astimezone(UTC)
        self.analysed = [c for c in self.scope if self.experiments[c]["ruling"] != "ABORTED"]

        # metric configuration per experiment after amendments
        def amend_key(r: dict) -> tuple[int, str]:
            return (0 if nid(r["experiment"]) == "ALL" else 1, r["amendment_id"])

        ordered = sorted(self.amendments, key=amend_key)
        self.config: dict[str, dict[str, dict]] = {}
        for code in self.analysed:
            cfg = {m: dict(v, amendments=[]) for m, v in self.registry.items()}
            for r in ordered:
                target = nid(r["experiment"])
                if target != "ALL" and self.canon_exp(target) != code:
                    continue
                m = r["metric"].strip().lower()
                if m not in cfg:
                    continue
                fld = r["field"].strip()
                val = r["new_value"].strip()
                if fld == "winsor_pct":
                    cfg[m]["winsor_pct"] = val
                elif fld == "attribution_days":
                    cfg[m]["attribution_days"] = int(val)
                elif fld == "cuped":
                    cfg[m]["cuped"] = truthy(val)
                cfg[m]["amendments"].append(r["amendment_id"])
            for v in cfg.values():
                v["cuped"] = bool(v["cuped"] and v["covariate"])
            self.config[code] = cfg

    def read_registry(self, grid: list[list[str]]) -> dict[str, dict]:
        head = None
        reg = {}
        for r in grid:
            cells = [c.strip() for c in r]
            if cells and cells[0] == "section":
                head = cells
                continue
            if head and cells and cells[0] == "METRIC":
                rec = dict(zip(head, cells))
                dash = lambda v: None if v in ("", "-") else v  # noqa: E731
                reg[rec["metric"].lower()] = {
                    "kind": rec["kind"].lower(), "attribution_days": int(Decimal(rec["attribution_days"])),
                    "winsor_pct": dash(rec["winsor_pct"]), "cuped": truthy(rec["cuped"]), "covariate": dash(rec["covariate"]),
                    "role": rec["role"].lower(), "higher_is_better": truthy(rec["higher_is_better"]),
                    "numerator": dash(rec["numerator"]), "denominator": dash(rec["denominator"])}
        return reg

    def canon_exp(self, tok: str) -> str:
        k = nid(tok)
        return self.exp_alias.get(k, k)

    def retired(self, uid: str) -> bool:
        link = self.links.get(uid)
        return link is not None and link[1] <= self.cutoff

    def resolve(self, tok: str, at: datetime) -> tuple[str, int]:
        cur = nid(tok)
        path = [cur]
        seen = {cur: 0}
        while True:
            link = self.links.get(cur)
            if link is None or link[1] > at:
                return cur, len(path) - 1
            nxt = link[0]
            if nxt in seen:
                return min(path[seen[nxt]:]), len(path) - 1
            seen[nxt] = len(path)
            path.append(nxt)
            cur = nxt

    # ------------------------------------------------------------------ feeds
    def load_feeds(self) -> None:
        catalog = json.loads((self.data / "ingest_catalog_w26.json").read_text(encoding="utf-8"))
        self.lineage: dict[str, dict] = {}
        xv: dict[str, list] = {}
        ov: dict[str, list] = {}
        for sh in catalog["shards"]:
            fn, lay, conv = sh["file"], sh["layout"], sh["ts_convention"]
            codes = {k.strip(): v for k, v in sh["status_codes"].items()}
            path = self.data / fn
            if sh["stream"] == "exposure":
                rows = read_exposures(path, lay)
                for i, (xid, t, unit, exp, var, st, rev) in enumerate(rows):
                    code = self.canon_exp(exp)
                    tz = self.experiments[code]["tz"] if code in self.experiments else None
                    rec = {"id": nid(xid), "t": parse_time(t, conv, tz, self.rep_tz), "unit": unit, "exp": code, "var": unq(var).lower(),
                           "live": codes[str(st).strip()] == "LIVE", "rev": int(str(rev).strip()), "src": (fn, i)}
                    xv.setdefault(rec["id"], []).append(rec)
            else:
                rows = read_orders(path, lay)
                for i, (oid, t, unit, ccy, amt, st, rev) in enumerate(rows):
                    ccy = str(ccy).strip().upper()
                    if sh["amount_unit"] == "minor":
                        minor = int(str(amt).strip())
                    else:
                        val = Decimal(str(amt).strip()) * (10 ** self.minor_units[ccy])
                        minor = int(val)
                        if val != minor:
                            raise ValueError(f"non-integral minor amount {amt} {ccy}")
                    rec = {"id": nid(oid), "t": parse_time(t, conv, None, self.rep_tz), "unit": unit, "ccy": ccy, "minor": minor,
                           "live": codes[str(st).strip()] == "PLACED", "rev": int(str(rev).strip()), "src": (fn, i)}
                    ov.setdefault(rec["id"], []).append(rec)
            self.lineage[fn] = {"stream": sh["stream"], "rows": len(rows), "kept": 0}

        def winners(versions: dict[str, list]) -> tuple[dict[str, dict], int, int]:
            win, dups, dead = {}, 0, 0
            for k, vs in versions.items():
                best = max(vs, key=lambda r: r["rev"])
                dups += len(vs) - 1
                if best["live"]:
                    win[k] = best
                    self.lineage[best["src"][0]]["kept"] += 1
                else:
                    dead += 1
            return win, dups, dead

        xw, xd, xdead = winners(xv)
        ow, od, odead = winners(ov)
        out_scope = unmapped = 0
        self.exposures = []
        for r in xw.values():
            if r["exp"] not in self.scope:
                out_scope += 1
                continue
            arm = self.var_alias.get((r["exp"], r["var"]))
            if arm is None:
                unmapped += 1
                continue
            r["arm"] = arm
            self.exposures.append(r)
        self.orders_all = ow
        self.order_ids_any = set(ov)
        self.dedup = {"exposure": {"rows_read": sum(len(v) for v in xv.values()), "duplicate_rows_dropped": xd, "voided": xdead,
                                   "live": len(xw), "out_of_scope": out_scope, "unmapped_variant": unmapped},
                      "order": {"rows_read": sum(len(v) for v in ov.values()), "duplicate_rows_dropped": od, "cancelled": odead, "live": len(ow)}}

    # ------------------------------------------------------------------ units
    def eligibility(self, unit: str) -> str | None:
        acct = self.acct.get(unit)
        if acct is None:
            return "UNREGISTERED"
        ruling = self.unit_rulings.get(unit)
        if ruling == "EXCLUDE":
            return "RULING_EXCLUDED"
        if unit in self.internal:
            return "INTERNAL_LIST"
        if ruling == "REINSTATE":
            acct = "human"
        if acct != "human":
            return acct.upper()
        return None

    def build_units(self) -> None:
        self.resolution = [(k, *self.resolve(k, self.cutoff)) for k in sorted(self.links)]

    def build_participants(self) -> None:
        by: dict[tuple[str, str], list[dict]] = {}
        for r in self.exposures:
            if r["exp"] not in self.analysed:
                continue
            ex = self.experiments[r["exp"]]
            if r["t"] >= ex["end"]:
                continue
            unit = self.resolve(r["unit"], r["t"])[0]
            by.setdefault((r["exp"], unit), []).append(r)
        self.participants: dict[str, dict[str, dict]] = {c: {} for c in self.analysed}
        self.excluded = []
        for (code, unit), rs in sorted(by.items()):
            ex = self.experiments[code]
            reason = self.eligibility(unit)
            arms = {r["arm"] for r in rs}
            fe = min(r["t"] for r in rs)
            if reason is None and len(arms) > 1:
                reason = "CROSSOVER"
            if reason is None and fe < ex["start"]:
                reason = "PRE_START"
            if reason:
                self.excluded.append({"experiment": code, "unit_id": unit, "reason": reason})
            else:
                self.participants[code][unit] = {"arm": arms.pop(), "fe": fe, "n": len(rs)}

    # ------------------------------------------------------------------ orders
    def usd_micro(self, minor: int, ccy: str, day: date) -> tuple[int, str]:
        amount = Fraction(minor, 10 ** self.minor_units[ccy])
        if ccy == "USD":
            return half_even(amount * MICRO), ""
        d, quote, rate = self.fixing(ccy, day)
        if quote == "USD_PER_UNIT":
            usd = amount * rate
        elif quote == "UNIT_PER_USD":
            usd = amount / rate
        else:
            _, eq, erate = self.fixing("EUR", day)
            eur = amount / rate
            usd = eur * erate if eq == "USD_PER_UNIT" else eur / erate
        return half_even(usd * MICRO), d.isoformat()

    def fixing(self, ccy: str, day: date) -> tuple[date, str, Fraction]:
        i = bisect.bisect_right(self.fx_days[ccy], day) - 1
        return self.fx[ccy][i]

    def build_orders(self) -> None:
        entries = []
        for o in map(json.loads, filter(str.strip, (self.data / "refund_journal.jsonl").read_text(encoding="utf-8").splitlines())):
            entries.append(("jsonl", int(o["seq"]), o["status"], nid(o["refund_id"]), nid(o["order_id"]), int(o["amount_minor"]),
                            datetime.strptime(o["posted_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC),
                            unq(o.get("kind") or "refund").lower()))
        for e in ET.fromstring((self.data / "refund_journal_late.xml").read_text(encoding="utf-8")).iter("refund"):
            g = {c.tag: (c.text or "") for c in e}
            entries.append(("xml", int(e.get("seq")), e.get("status"), nid(g["id"]), nid(g["order"]), int(g["minor"].strip()),
                            datetime.strptime(g["posted"].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC),
                            unq(e.get("kind") or "refund").lower()))
        entries.sort(key=lambda x: x[1])
        live = {k: o for k, o in self.orders_all.items() if o["t"] < self.cutoff}
        refund_by_id: dict[str, tuple[str, int]] = {}
        self.refund_log = []
        for journal, seq, status, rid, oid, amt, posted, kind in entries:
            if status.strip().upper() != "POSTED":
                continue
            if posted >= self.cutoff:
                outcome = "AFTER_CUTOFF"
            elif oid not in self.order_ids_any:
                outcome = "NO_ORDER"
            elif oid not in self.orders_all:
                outcome = "ORDER_CANCELLED"
            elif kind == "reversal":
                if rid in refund_by_id:
                    outcome = "REVERSED"
                    del refund_by_id[rid]
                else:
                    outcome = "NOTHING_TO_REVERSE"
            elif rid in refund_by_id:
                outcome = "REPLACED"
                refund_by_id[rid] = (oid, amt)
            else:
                outcome = "APPLIED"
                refund_by_id[rid] = (oid, amt)
            self.refund_log.append({"journal": journal, "seq": seq, "kind": kind, "refund_id": rid, "order_id": oid, "outcome": outcome})
        refunds: dict[str, int] = {}
        for oid, amt in refund_by_id.values():
            refunds[oid] = refunds.get(oid, 0) + amt
        self.valuation = []
        self.unit_orders: dict[str, list[tuple]] = {}
        for oid in sorted(live):
            o = live[oid]
            unit = self.resolve(o["unit"], o["t"])[0]
            ref = refunds.get(oid, 0)
            net = max(0, o["minor"] - ref)
            refunded = o["minor"] - net
            day = o["t"].astimezone(UTC).date()
            net_usd, fxd = self.usd_micro(net, o["ccy"], day)
            ref_usd, _ = self.usd_micro(refunded, o["ccy"], day)
            self.valuation.append([oid, unit, o["ccy"], o["minor"], ref, net, fxd, f6(Fraction(net_usd, MICRO)), f6(Fraction(ref_usd, MICRO))])
            self.unit_orders.setdefault(unit, []).append((o["t"], net_usd, ref_usd, net > 0))
        self.usd_total = sum(Fraction(int(r[7].replace(".", "")), MICRO) for r in self.valuation)
        for v in self.unit_orders.values():
            v.sort()

    # ------------------------------------------------------------------ metric values
    def window_value(self, unit: str, a: datetime, b: datetime, base: str) -> int:
        tot = 0
        for t, net, ref, pos in self.unit_orders.get(unit, []):
            if a <= t < b:
                if base in ("conv7", "pre_conv"):
                    if pos:
                        return 1
                elif base in ("rev14", "pre_rev"):
                    tot += net
                elif base in ("ord14", "pre_ord"):
                    tot += 1 if pos else 0
                elif base == "rfd14":
                    tot += ref
        return tot

    def build_metrics(self) -> None:
        self.unit_values: dict[str, dict[str, dict[str, dict]]] = {}
        self.caps: list[list] = []
        self.cuped: dict[str, dict[str, dict]] = {}
        self.arm_stats: dict[tuple[str, str, str], dict] = {}
        for code in self.analysed:
            ex = self.experiments[code]
            arms_an = sorted(a for a, (role, _) in ex["arms"].items() if role in ("control", "treatment"))
            for m, cfg in sorted(self.config[code].items()):
                horizon = timedelta(days=cfg["attribution_days"])
                pre = timedelta(days=self.pre_days)
                units = sorted(u for u, p in self.participants[code].items()
                               if p["arm"] in arms_an and p["fe"] + horizon <= self.cutoff)
                vals = {}
                for u in units:
                    p = self.participants[code][u]
                    fe = p["fe"]
                    if cfg["kind"] == "ratio":
                        y = self.window_value(u, fe, fe + horizon, cfg["numerator"])
                        x = self.window_value(u, fe, fe + horizon, cfg["denominator"])
                    else:
                        y = self.window_value(u, fe, fe + horizon, m)
                        x = self.window_value(u, fe - pre, fe, cfg["covariate"]) if cfg["cuped"] else 0
                    vals[u] = [y, x]
                scale = MICRO if (m in ("rev14", "rfd14") or cfg["kind"] == "ratio") else 1
                if cfg["kind"] == "mean" and cfg["winsor_pct"] is not None and units:
                    pct = Fraction(Decimal(cfg["winsor_pct"]))

                    def cap_of(idx: int) -> int:
                        arr = sorted(v[idx] for v in vals.values())
                        k = math.ceil(pct * len(arr) / 100)
                        return arr[max(1, k) - 1]

                    cy = cap_of(0)
                    capped = sum(1 for v in vals.values() if v[0] > cy)
                    cx = cap_of(1) if cfg["cuped"] else None
                    for v in vals.values():
                        v[0] = min(v[0], cy)
                        if cx is not None:
                            v[1] = min(v[1], cx)
                    self.caps.append([code, m, cfg["winsor_pct"], len(units), f6(Fraction(cy, scale)),
                                      f6(Fraction(cx, scale)) if cx is not None else "", capped])
                pooled = self.sums(list(vals.values()))
                theta = Fraction(0)
                if cfg["cuped"] and cfg["kind"] != "ratio":
                    n, sy, sx, syy, sxx, sxy = pooled
                    vx = Fraction(n * sxx - sx * sx)
                    theta = Fraction(n * sxy - sx * sy) / vx if vx else Fraction(0)
                    theta = Fraction(half_even(theta * MICRO), MICRO)
                    mean_x = Fraction(sx, n)
                    vy = Fraction(n * syy - sy * sy)
                    vadj = vy - 2 * theta * (n * sxy - sx * sy) + theta * theta * vx
                    self.cuped.setdefault(code, {})[m] = {"theta": f6(theta), "mean_x": f6(mean_x / scale),
                                                          "variance_reduction_pct": f6(100 * (1 - vadj / vy)) if vy else None}
                else:
                    mean_x = Fraction(0)
                for arm in arms_an:
                    rows = [vals[u] for u in units if self.participants[code][u]["arm"] == arm]
                    n, sy, sx, syy, sxx, sxy = self.sums(rows)
                    st = {"n": n}
                    if cfg["kind"] == "ratio":
                        my, mx = Fraction(sy, n), Fraction(sx, n)
                        s_yy = Fraction(n * syy - sy * sy, n * (n - 1))
                        s_xx = Fraction(n * sxx - sx * sx, n * (n - 1))
                        s_xy = Fraction(n * sxy - sx * sy, n * (n - 1))
                        R = my / mx
                        V = (s_yy / mx ** 2 - 2 * my * s_xy / mx ** 3 + my ** 2 * s_xx / mx ** 4) / n
                        st.update(raw=R / scale, adj=R / scale, var=V / scale ** 2)
                    else:
                        raw = Fraction(sy, n)
                        adj = raw - theta * (Fraction(sx, n) - mean_x)
                        s_yy = Fraction(n * syy - sy * sy, n * (n - 1))
                        s_xx = Fraction(n * sxx - sx * sx, n * (n - 1))
                        s_xy = Fraction(n * sxy - sx * sy, n * (n - 1))
                        var = s_yy - 2 * theta * s_xy + theta * theta * s_xx
                        st.update(raw=raw / scale, adj=adj / scale, var=var / scale ** 2)
                    self.arm_stats[(code, arm, m)] = st

    @staticmethod
    def sums(rows: list[list[int]]) -> tuple[int, int, int, int, int, int]:
        n = len(rows)
        sy = sum(r[0] for r in rows)
        sx = sum(r[1] for r in rows)
        syy = sum(r[0] * r[0] for r in rows)
        sxx = sum(r[1] * r[1] for r in rows)
        sxy = sum(r[0] * r[1] for r in rows)
        return n, sy, sx, syy, sxx, sxy

    # ------------------------------------------------------------------ tests and decisions
    def build_tests(self) -> None:
        zc = NormalDist().inv_cdf(1 - self.alpha / 2)
        self.srm: dict[str, dict] = {}
        for code in self.analysed:
            ex = self.experiments[code]
            counts = {a: 0 for a in ex["arms"]}
            for p in self.participants[code].values():
                counts[p["arm"]] += 1
            N = sum(counts.values())
            chi2 = Fraction(0)
            exp_counts = {}
            for a, (role, w) in ex["arms"].items():
                e = Fraction(N) * Fraction(Decimal(w)) / 100
                exp_counts[a] = e
                chi2 += (counts[a] - e) ** 2 / e
            dof = len(ex["arms"]) - 1
            c2 = float(chi2)
            if dof == 1:
                p = math.erfc(math.sqrt(c2 / 2))
            elif dof == 2:
                p = math.exp(-c2 / 2)
            else:
                p = math.erfc(math.sqrt(c2 / 2)) + math.sqrt(2 * c2 / math.pi) * math.exp(-c2 / 2)
            self.srm[code] = {"counts": counts, "expected": exp_counts, "chi2": chi2, "dof": dof, "p": p, "fail": p < self.srm_alpha}
        self.tests: list[dict] = []
        for code in self.analysed:
            ex = self.experiments[code]
            control = next(a for a, (role, _) in ex["arms"].items() if role == "control")
            treats = sorted(a for a, (role, _) in ex["arms"].items() if role == "treatment")
            for arm in treats:
                for m in sorted(self.config[code]):
                    cfg = self.config[code][m]
                    c, t = self.arm_stats[(code, control, m)], self.arm_stats[(code, arm, m)]
                    diff = t["adj"] - c["adj"]
                    if cfg["kind"] == "ratio":
                        var = t["var"] + c["var"]
                    else:
                        var = t["var"] / t["n"] + c["var"] / c["n"]
                    se = math.sqrt(float(var))
                    z = float(diff) / se
                    p = math.erfc(abs(z) / math.sqrt(2))
                    lo, hi = float(diff) - zc * se, float(diff) + zc * se
                    base = c["raw"]
                    role = "primary" if m == ex["primary"] else cfg["role"]
                    self.tests.append({"exp": code, "arm": arm, "metric": m, "role": role, "c": c, "t": t, "diff": diff, "se": se, "z": z,
                                       "p": p, "lo": lo, "hi": hi, "base": base, "cfg": cfg, "q": None, "sig": None})
        fam = [x for x in self.tests if x["role"] == "primary" and not self.srm[x["exp"]]["fail"]]
        fam.sort(key=lambda x: (x["p"], x["exp"], x["arm"]))
        m = len(fam)
        q = 1.0
        for i in range(m - 1, -1, -1):
            q = min(q, min(1.0, m * fam[i]["p"] / (i + 1)))
            fam[i]["q"] = q
        self.family = fam
        for x in self.tests:
            if x["role"] == "primary":
                if self.srm[x["exp"]]["fail"]:
                    x["sig"] = ""
                else:
                    x["sig"] = "Y" if x["q"] <= self.bh_q else "N"
            else:
                x["sig"] = "Y" if x["p"] < self.alpha else "N"
        self.guard: list[dict] = []
        for x in self.tests:
            if x["cfg"]["role"] != "guardrail":
                continue
            M = float(self.params[f"guardrail_margin_pct.{x['metric']}"])
            llo, lhi = 100 * x["lo"] / float(x["base"]), 100 * x["hi"] / float(x["base"])
            lift = 100 * x["diff"] / x["base"]
            worse = x["diff"] < 0 if x["cfg"]["higher_is_better"] else x["diff"] > 0
            Mx = Fraction(Decimal(self.params[f"guardrail_margin_pct.{x['metric']}"]))
            beyond = lift < -Mx if x["cfg"]["higher_is_better"] else lift > Mx
            breach = x["p"] < self.alpha and worse and beyond
            self.guard.append({"x": x, "lift": lift, "lo": llo, "hi": lhi,
                               "margin": self.params[f"guardrail_margin_pct.{x['metric']}"], "breach": breach})
        self.decisions: dict[str, dict[str, dict]] = {}
        for code in self.scope:
            ex = self.experiments[code]
            treats = sorted(a for a, (role, _) in ex["arms"].items() if role == "treatment")
            self.decisions[code] = {}
            for arm in treats:
                if ex["ruling"] == "ABORTED":
                    self.decisions[code][arm] = {"decision": "ABORTED", "primary_metric": ex["primary"], "q_value": None, "guardrail_breaches": []}
                    continue
                prim = next(x for x in self.tests if x["exp"] == code and x["arm"] == arm and x["role"] == "primary")
                br = sorted(g["x"]["metric"] for g in self.guard if g["x"]["exp"] == code and g["x"]["arm"] == arm and g["breach"])
                hib = prim["cfg"]["higher_is_better"]
                good = prim["diff"] > 0 if hib else prim["diff"] < 0
                if self.srm[code]["fail"]:
                    dec = "INVALID_SRM"
                elif br:
                    dec = "NO_SHIP_GUARDRAIL"
                elif prim["sig"] == "Y":
                    dec = "SHIP" if good else "NO_SHIP"
                else:
                    dec = "INCONCLUSIVE"
                self.decisions[code][arm] = {"decision": dec, "primary_metric": ex["primary"],
                                             "q_value": e6(prim["q"]) if prim["q"] is not None else None, "guardrail_breaches": br}

        # ship capacity pass (H13.5)
        by_team: dict[str, list[tuple]] = {}
        for code in self.scope:
            for arm, d in self.decisions[code].items():
                if d["decision"] == "SHIP":
                    q = next(x["q"] for x in self.tests if x["exp"] == code and x["arm"] == arm and x["role"] == "primary")
                    by_team.setdefault(self.experiments[code]["team"], []).append((q, code, arm))
        self.deferred = []
        for team, arms in by_team.items():
            if team not in self.capacity:
                continue
            arms.sort()
            for q, code, arm in arms[self.capacity[team]:]:
                self.decisions[code][arm]["decision"] = "SHIP_DEFERRED"
                self.deferred.append(f"{code}/{arm}")
        self.deferred.sort()

    # ------------------------------------------------------------------ rendering
    def render(self) -> dict[str, str]:
        out: dict[str, str] = {}

        def table(rows: list[list], sep: str) -> str:
            return "".join(sep.join(str(c) for c in r) + "\n" for r in rows)

        def js(o) -> str:
            return json.dumps(o, sort_keys=True) + "\n"

        rows = [["experiment", "arm", "metric", "role", "n_control", "n_treatment", "mean_control", "mean_treatment", "diff", "lift_pct",
                 "se", "z", "p_value", "ci_low", "ci_high", "q_value", "significant"]]
        for x in self.tests:
            rows.append([x["exp"], x["arm"], x["metric"], x["role"], x["c"]["n"], x["t"]["n"], f6(x["c"]["adj"]), f6(x["t"]["adj"]), f6(x["diff"]),
                         f6(100 * x["diff"] / x["base"]) if x["base"] else "", f6(x["se"]), f6(x["z"]), e6(x["p"]), f6(x["lo"]), f6(x["hi"]),
                         e6(x["q"]) if x["q"] is not None else "", x["sig"]])
        out["readout.csv"] = table(rows, ",")
        rows = [["experiment", "arm", "metric", "n", "raw_mean", "adj_mean", "variance"]]
        for (code, arm, m), st in sorted(self.arm_stats.items()):
            rows.append([code, arm, m, st["n"], f6(st["raw"]), f6(st["adj"]), f6(st["var"])])
        out["arm_metrics.tsv"] = table(rows, "\t")
        out["winsor_caps.psv"] = table([["experiment", "metric", "winsor_pct", "n_pooled", "cap", "covariate_cap", "capped_units"]] + sorted(self.caps), "|")
        out["cuped.json"] = js(self.cuped)
        rows = [["experiment", "arm", "role", "weight_pct", "observed", "expected", "chi2", "dof", "p_value", "status"]]
        for code in self.analysed:
            s = self.srm[code]
            for a in sorted(self.experiments[code]["arms"]):
                role, w = self.experiments[code]["arms"][a]
                rows.append([code, a, role, w, s["counts"][a], f6(s["expected"][a]), f6(s["chi2"]), s["dof"], e6(s["p"]), "FAIL" if s["fail"] else "PASS"])
        out["srm_report.csv"] = table(rows, ",")
        rows = [["rank", "experiment", "arm", "metric", "p_value", "q_value", "significant"]]
        for i, x in enumerate(self.family, 1):
            rows.append([i, x["exp"], x["arm"], x["metric"], e6(x["p"]), e6(x["q"]), x["sig"]])
        out["bh_family.csv"] = table(rows, ",")
        rows = [["experiment", "arm", "metric", "lift_pct", "lift_ci_low", "lift_ci_high", "margin_pct", "breach"]]
        for g in self.guard:
            rows.append([g["x"]["exp"], g["x"]["arm"], g["x"]["metric"], f6(g["lift"]), f6(g["lo"]), f6(g["hi"]), g["margin"], "Y" if g["breach"] else "N"])
        out["guardrails.csv"] = table(rows, ",")
        out["decisions.json"] = js(self.decisions)
        rows = [["experiment", "unit_id", "arm", "first_exposure_utc", "exposures"]]
        for code in self.analysed:
            for u in sorted(self.participants[code]):
                p = self.participants[code][u]
                rows.append([code, u, p["arm"], iso(p["fe"]), p["n"]])
        out["unit_assignments.csv"] = table(rows, ",")
        out["excluded_units.jsonl"] = "".join(js(x) for x in self.excluded)
        out["identity_resolution.csv"] = table([["from_id", "unit_id", "hops"]] + [list(r) for r in self.resolution], ",")
        out["dedup_report.json"] = js(self.dedup)
        out["source_lineage.json"] = js(self.lineage)
        out["refund_outcomes.jsonl"] = "".join(js(x) for x in self.refund_log)
        out["order_valuation.psv"] = table([["order_id", "unit_id", "currency", "amount_minor", "refund_minor", "net_minor", "fx_date", "usd_net",
                                             "usd_refunded"]] + self.valuation, "|")
        cfg_out: dict = {"registry_version": self.registry_version, "fx_sheet": self.fx_sheet}
        for code in self.analysed:
            cfg_out[code] = {m: {k: v for k, v in c.items()} for m, c in self.config[code].items()}
        out["metric_config_used.json"] = js(cfg_out)
        xml = [f'<portfolio id="{self.prof["portfolio_id"]}">']
        for code in self.scope:
            ex = self.experiments[code]
            xml.append(f'  <experiment code="{code}" tz_offset="{ex["tz_text"]}" owner_team="{ex["team"]}" start_utc="{iso(ex["start"])}" end_utc="{iso(ex["end"])}" '
                       f'ruling="{ex["ruling"]}" status="{"ABORTED" if ex["ruling"] == "ABORTED" else "ANALYSED"}"/>')
        xml.append("</portfolio>")
        out["experiment_windows.xml"] = "\n".join(xml) + "\n"
        counts: dict[str, int] = {}
        for code in self.decisions:
            for d in self.decisions[code].values():
                counts[d["decision"]] = counts.get(d["decision"], 0) + 1
        out["portfolio_summary.json"] = js({
            "portfolio_id": self.prof["portfolio_id"], "registry_version": self.registry_version,
            "experiments_analysed": len(self.analysed), "experiments_aborted": len(self.scope) - len(self.analysed),
            "srm_failures": sum(1 for c in self.analysed if self.srm[c]["fail"]), "family_size": len(self.family), "decisions": counts,
            "deferred_arms": self.deferred,
            "participants": sum(len(v) for v in self.participants.values()), "excluded_candidates": len(self.excluded),
            "live_orders": len(self.valuation), "usd_net_total": f6(self.usd_total)})
        pub = {}
        for r in delimited((self.data / unq(self.prof["published_readout"])).read_text(encoding="utf-8"), ","):
            if r["cut"].strip().upper() == "ALL":
                pub[(nid(r["experiment"]), nid(r["arm"]), r["metric"].strip().lower())] = (r["diff"].strip(), r["significant"].strip().upper())
        cor = {(x["exp"], x["arm"], x["metric"]): (f6(x["diff"]), x["sig"] or "N") for x in self.tests}
        rows = [["experiment", "arm", "metric", "published_diff", "corrected_diff", "published_significant", "corrected_significant", "status"]]
        for k in sorted(set(pub) | set(cor)):
            p, c = pub.get(k), cor.get(k)
            status = "NEW" if p is None else "DROPPED" if c is None else "FLIPPED" if p[1] != c[1] else "SAME"
            rows.append([*k, p[0] if p else "", c[0] if c else "", p[1] if p else "", c[1] if c else "", status])
        out["variance_vs_published.csv"] = table(rows, ",")
        md = [f"# Portfolio {self.prof['portfolio_id']} readout reconciliation", "",
              "| experiment | arm | published_decision | corrected_decision |", "|---|---|---|---|"]
        for code in self.scope:
            prim = self.experiments[code]["primary"]
            for arm, d in sorted(self.decisions[code].items()):
                p = pub.get((code, arm, prim))
                if p is None:
                    pd = "MISSING"
                elif p[1] == "Y":
                    pd = "SHIP" if Decimal(p[0]) > 0 else "NO_SHIP"
                else:
                    pd = "INCONCLUSIVE"
                md.append(f"| {code} | {arm} | {pd} | {d['decision']} |")
        out["reconciliation.md"] = "\n".join(md) + "\n"
        return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: run_readout.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, outdir = Path(argv[1]), Path(argv[2])
    files = Readout(data).render()
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name in OUTPUTS:
        blob = files[name].encode("utf-8")
        (outdir / name).write_bytes(blob)
        manifest.append({"name": name, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()})
    (outdir / "manifest.json").write_text(json.dumps({"files": manifest}, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
