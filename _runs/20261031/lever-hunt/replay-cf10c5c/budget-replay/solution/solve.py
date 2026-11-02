#!/usr/bin/env python3
"""Reference transform for the 43986de8-bb38-5141-98f3-f9f31ce56581.

Usage: python3 transform.py DATA_DIR OUT_DIR
Reads the extract, closes the ledger, runs the month-end sweep for every household and writes every report.
Everything is settled in memory before any report is written.
"""
import configparser
import csv
import hashlib
import json
import sqlite3
import sys
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

DISTRICTS = ("central", "east", "north", "south", "west")
SEGMENTS = ("consumer", "corporate", "enterprise", "smb")
REGISTER = ("env_a.csv", "env_b.tsv", "env_c.jsonl")
EXPORTS = ("tx_a.csv", "tx_b.tsv", "tx_c.bin")
RATE_LOW, RATE_HIGH = 12, 50
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class ExtractError(Exception):
    """An input breaks a rule the documents state."""


def read_register(data):
    """Envelope register of record: three shards read through the column crosswalk, joined to districts."""
    xw = json.loads((data / "xw_columns.json").read_text(encoding="utf-8"))
    rows = []
    for name in REGISTER:
        if name.endswith(".jsonl"):
            text = (data / name).read_text(encoding="utf-8")
            recs = [json.loads(ln) for ln in text.split("\n") if ln != ""]
        else:
            table = table_rows(data / name)
            recs = [dict(zip(table[0], rec)) for rec in table[1:]]
        rows += [{xw[name][k]: v for k, v in rec.items()} for rec in recs]
    con = sqlite3.connect(f"file:{data / 'hh_core.sqlite'}?mode=ro", uri=True)
    try:
        homes = {r[0]: (r[1].lower(), r[2]) for r in con.execute(
            "SELECT h.hh_code, d.district_name, h.family_name FROM household h JOIN district d ON d.district_id = h.district_id")}
        files = dict(con.execute("SELECT file_no, hh_code FROM file"))
        plans = dict(con.execute("SELECT env_code, plan FROM keep_plan"))
        alias = {}
        for name, code, since in con.execute("SELECT alias, env_code, since FROM env_alias"):
            alias.setdefault(name, []).append((since, code))
    finally:
        con.close()
    funds, cats = read_pdf_codes(data), read_docx_codes(data)
    envs = [{"code": r["env_code"], "hh": files[r["file_no"]], "label": r["label"], "category": cats[r["category_code"]],
             "segment": funds[r["funding_code"]], "fund": r["funding_code"], "cat": r["category_code"], "plan": plans[r["env_code"]],
             "need": int(r["need_dollars"]), "opening": int(r["opening_cents"])}
            for r in rows]
    return homes, envs, alias


def table_rows(path):
    """Rows of a delimited file: RFC 4180 for .csv (quoted fields allowed), plain tab-separated for .tsv."""
    text = path.read_text(encoding="utf-8")
    if path.name.endswith(".csv"):
        return [rec for rec in csv.reader(io.StringIO(text, newline="")) if rec]
    return [ln.split("\t") for ln in text.split("\n") if ln != ""]


def pdf_ref(text, key):
    """Object number after the dictionary key (None when the key is absent)."""
    m = re.search(("/" + key + r"\s+(\d+)").encode("ascii"), text)
    return int(m.group(1)) if m else None


def read_pdf_codes(data):
    """ISO 32000-1: objects located through the newest cross-reference section first, earlier ones via /Prev."""
    blob = (data / "fund_codes.pdf").read_bytes()
    where = {}
    start = int(blob[blob.rindex(b"startxref") + 9:].split()[0])
    while start is not None:
        tail = blob[start:]
        head, _sep, rest = tail.partition(b"trailer")
        nums = head.split()[1:]
        k = 0
        while k + 1 < len(nums) and nums[k] != b"trailer":
            first, count = int(nums[k]), int(nums[k + 1])
            for j in range(count):
                off, _gen, kind = nums[k + 2 + 3 * j:k + 5 + 3 * j]
                if kind == b"n":
                    where.setdefault(first + j, int(off))
            k += 2 + 3 * count
        start = pdf_ref(rest[:rest.index(b">>")], "Prev")
    def body(num):
        return blob[where[num]:blob.index(b"endobj", where[num])]
    root = pdf_ref(blob[blob.rindex(b"trailer"):], "Root")
    pages = pdf_ref(body(root), "Pages")
    page = pdf_ref(body(pages).replace(b"[", b" "), "Kids")
    content = body(pdf_ref(body(page), "Contents"))
    start = content.index(b"stream\n") + 7
    text = zlib.decompress(content[start:content.rindex(b"\nendstream")]).decode("latin-1")
    out = {}
    for m in re.finditer(r"\(((?:[^()\\]|\\.)*)\) Tj", text):
        line = re.sub(r"\\(.)", r"\1", m.group(1))
        code, eq, seg = line.partition(" = ")
        if eq:
            out[code] = seg
    return out


def read_docx_codes(data):
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(data / "cat_codes.docx") as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    rows = [[current_text(tc, w) for tc in tr.iter(w + "tc")] for tr in doc.iter(w + "tr")]
    return {r[0]: r[1] for r in rows[1:]}


def current_text(node, w):
    """Text of the current document (ECMA-376): moved-away runs (w:moveFrom) are not current, and of a markup-compatibility
    choice block (Part 3) a consumer that does not understand the required namespace takes the fallback."""
    mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
    if node.tag in (w + "move" + "From", w + "del", mc + "Choice"):
        return ""
    if node.tag == w + "t":
        return node.text or ""
    return "".join(current_text(child, w) for child in node)


def sheet_cells(node):
    """Cells of a row in document order; of a markup-compatibility block (ECMA-376 Part 3) a consumer that understands
    none of the required namespaces takes the fallback."""
    mc = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
    for child in node:
        if child.tag == NS + "c":
            yield child
        elif child.tag == mc + "AlternateContent":
            for alt in child:
                if alt.tag == mc + "Fallback":
                    yield from sheet_cells(alt)


def read_params(data, sheet_name):
    with zipfile.ZipFile(data / "sweep_tab.xlsx") as zf:
        book = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        rid = next(s.get(RNS + "id") for s in book.iter(NS + "sheet") if s.get("name") == sheet_name)
        sheet = ET.fromstring(zf.read("xl/" + targets[rid]))
    rows = []
    for row in sheet.iter(NS + "row"):
        cells = []
        for c in sheet_cells(row):
            if c.get("t") == "inlineStr":
                cells.append("".join(t.text or "" for t in c.iter(NS + "t")))
            else:
                cells.append(int(c.find(NS + "v").text))
        rows.append(cells)
    out = {}
    for r in rows[1:]:
        rec = dict(zip(rows[0], r))
        out[str(rec["district"]).lower()] = (rec["damping_percent"], rec["patience"], rec["round_budget"])
    return out


def parse_row(name, rec):
    """Return (id, day, envelope key, signed cents or None when malformed)."""
    if name == "tx_a.csv":
        txn, day, env, cents, way = rec
        ok = cents.isdigit() and way in ("in", "out")
        return txn, day, env, (int(cents) if way == "in" else -int(cents)) if ok else None
    if name == "tx_b.tsv":
        txn, day, al, amount, kind = rec
        whole, dot, frac = amount.partition(".")
        ok = whole.isdigit() and dot == "." and len(frac) == 2 and frac.isdigit() and kind in ("D", "S")
        val = int(whole) * 100 + int(frac) if ok else 0
        return txn, day, al, (val if kind == "D" else -val) if ok else None
    return rec


def read_exports(data):
    rows = []
    for name in EXPORTS:
        if name == "tx_c.bin":
            recs = read_txc(data / name)
        else:
            recs = table_rows(data / name)[1:]
        for rec in recs:
            rows.append((name,) + parse_row(name, rec))
    return rows


def varint(blob, pos, signed):
    value = shift = 0
    while True:
        byte = blob[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            break
    if signed:
        value = (value >> 1) ^ -(value & 1)
    return value, pos


def day_text(n):
    if n <= 0:
        return "2026-08-%02d" % (n + 31)
    return "2026-10-%02d" % (n - 30) if n > 30 else "2026-09-%02d" % n


def read_txc(path):
    """Decode tx_c.bin into (id, day, envelope code, signed cents or None) rows."""
    blob = path.read_bytes()
    if blob[:4] != b"TXC1" or zlib.crc32(blob[:-4]) != int.from_bytes(blob[-4:], "big"):
        raise ExtractError("tx_c.bin: header or checksum does not match")
    pos, rows, words = 7, [], []
    day = 0
    code = ""
    for _ in range(int.from_bytes(blob[5:7], "big")):
        sel = blob[pos]
        number, pos = varint(blob, pos + 1, False)
        if sel & 3 == 0:
            size = blob[pos]
            code = blob[pos + 1:pos + 1 + size].decode("ascii")
            day, pos = varint(blob, pos + 1 + size, True)
            if code.upper() not in (w.upper() for w in words):
                words.append(code)
        elif sel & 3 == 1:
            step, pos = varint(blob, pos, True)
            day += step
        else:
            code = words[len(words) - 1 - blob[pos]]
            day, pos = varint(blob, pos + 1, True)
        cents = None
        if not sel & 4:
            cents, pos = varint(blob, pos, True)
        rows.append(("T%05d" % number, day_text(day), code, cents))
    return rows


def resolve(name, key, alias, codes, day):
    if name == "tx_b.tsv":
        held = sorted(r for r in alias.get(key, []) if r[0] <= day)
        key = held[-1][1] if held else ""
    up = key.upper()
    if up not in codes:
        raise ExtractError(f"{name}: transaction names unknown envelope {key!r}")
    return up


def close_ledger(data, cfg, envs, alias):
    first, last = cfg["period"]["first_day"], cfg["period"]["last_day"]
    cutoff = int(cfg["corrections"]["cutoff_seq"])
    codes = {e["code"] for e in envs}
    rows = read_exports(data)
    seen = set()
    quality = {n: {"rows": 0, "malformed": 0, "out_of_period": 0, "applied": 0, "voided": 0} for n in EXPORTS}
    live = {}
    for name, txn, day, key, cents in rows:
        if txn in seen:
            raise ExtractError(f"transaction id {txn} appears twice")
        seen.add(txn)
        quality[name]["rows"] += 1
        code = resolve(name, key, alias, codes, day)
        if cents is None:
            quality[name]["malformed"] += 1
        elif not first <= day <= last:
            quality[name]["out_of_period"] += 1
        else:
            live[txn] = {"txn": txn, "date": day, "envelope": code, "cents": cents,
                         "source": name}
    applied, past = apply_corrections(data, cutoff, live, seen)
    for t in live.values():
        quality[t["source"]]["voided" if t.get("void") else "applied"] += 1
    ledger = sorted((t for t in live.values() if not t.get("void")), key=lambda t: t["txn"])
    return ledger, {"exports": quality, "corrections": {"applied": applied, "past_cutoff": past}}


def apply_corrections(data, cutoff, live, seen):
    lines = [ln for ln in (data / "adj_log.psv").read_text(encoding="utf-8").split("\n") if ln != ""]
    entries = []
    for ln in lines[1:]:
        seq, txn, action, value = ln.split("|")
        entries.append((int(seq), txn, action, value))
    entries.sort()
    applied = past = 0
    for seq, txn, action, value in entries:
        if seq > cutoff:
            past += 1
            continue
        applied += 1
        if txn not in seen:
            raise ExtractError(f"correction {seq} names unknown transaction {txn}")
        t = live.get(txn)
        if t is None or t.get("void"):
            continue
        if action == "void":
            t["void"] = True
        else:
            t["cents"] = int(value) if t["cents"] > 0 else -int(value)
    return applied, past


def keeping_charges(data, envs, ledger):
    """Settle every keeping plan's rate from the fee statement and return each envelope's keeping charge in dollars."""
    table = table_rows(data / "stmt_fees.csv")
    rows = [dict(zip(table[0], rec)) for rec in table[1:]]
    through = rows[0]["through"]
    base = {e["code"]: e["opening"] for e in envs}
    for t in ledger:
        if t["date"] <= through:
            base[t["envelope"]] += t["cents"]
    evidence = [(int(r["charge_cents"]), [(e["plan"], e["opening"]) for e in envs if r["client_ref"] in (e["hh"], e["fund"], e["cat"])])
                for r in rows]
    fits = plan_rates(evidence, 2)
    if len(fits) != 1:
        raise ExtractError(f"{len(fits)} sets of plan rates meet the fee statement")
    return {e["code"]: rounded(fits[0][e["plan"]] * base[e["code"]], 1000000) for e in envs}


def plan_rates(evidence, limit):
    """Assignments of whole-basis-point rates to plans that meet every statement row, at most `limit` of them."""
    width = RATE_HIGH - RATE_LOW + 1
    tables = []
    for want, members in evidence:
        cols = {}
        for plan, cents in members:
            col = cols.setdefault(plan, [0] * width)
            for i in range(width):
                col[i] += rounded((RATE_LOW + i) * cents, 10000)
        tables.append((want, cols))
    plans = sorted({p for _want, cols in tables for p in cols})
    found = []
    search(tables, {p: list(range(width)) for p in plans}, found, limit)
    return [{p: RATE_LOW + dom[p][0] for p in dom} for dom in found]


def search(tables, dom, found, limit):
    """Branch on the plan with the fewest remaining rates after narrowing every row."""
    if len(found) >= limit or not narrow(tables, dom):
        return
    open_plans = [p for p in dom if len(dom[p]) > 1]
    if not open_plans:
        found.append(dom)
        return
    pick = min(open_plans, key=lambda p: (len(dom[p]), p))
    for i in dom[pick]:
        sub = {p: list(v) for p, v in dom.items()}
        sub[pick] = [i]
        search(tables, sub, found, limit)


def narrow(tables, dom):
    """Drop every rate that no choice of the other plans' remaining rates can complete; False when a row fails."""
    changed = True
    while changed:
        changed = False
        for want, cols in tables:
            low = {p: min(cols[p][i] for i in dom[p]) for p in cols}
            high = {p: max(cols[p][i] for i in dom[p]) for p in cols}
            total_low, total_high = sum(low.values()), sum(high.values())
            if not total_low <= want <= total_high:
                return False
            for p in cols:
                keep = [i for i in dom[p] if total_low - low[p] + cols[p][i] <= want <= total_high - high[p] + cols[p][i]]
                if len(keep) < len(dom[p]):
                    if not keep:
                        return False
                    dom[p] = keep
                    changed = True
                    new_low, new_high = min(cols[p][i] for i in keep), max(cols[p][i] for i in keep)
                    total_low, total_high = total_low - low[p] + new_low, total_high - high[p] + new_high
                    low[p], high[p] = new_low, new_high
    return True


def rounded(num, den):
    """num/den to the nearest whole number, exact halves toward zero."""
    sign = -1 if (num < 0) != (den < 0) else 1
    q, rem = divmod(abs(num), abs(den))
    if 2 * rem > abs(den):
        q += 1
    return sign * q


def targets(bal, need, pool):
    claim = {c: need[c] + max(need[c] - bal[c], 0) for c in bal}
    total = sum(claim.values())
    return {c: rounded(pool * claim[c], total) for c in bal}


def balance(gap, rate, tie_order):
    sweep = {c: rounded(gap[c] * rate, 100) for c in gap}
    posted = dict(sweep)
    excess = sum(sweep.values())
    if excess:
        far = max(abs(v) for v in gap.values())
        pick = next(c for c in tie_order if abs(gap[c]) == far)
        posted[pick] -= excess
    return sweep, posted


def sweep_household(envs, rate, patience, budget):
    """envs in register order. Returns exit, rounds, rate, final balances and the round log."""
    order = sorted(e["code"] for e in envs)
    tie_order = sorted(order, key=lambda c: ([ord(ch) for ch in labels_of(envs)[c]], c))
    need = {e["code"]: e["need"] for e in envs}
    bal = {e["code"]: e["bal"] for e in envs}
    pool = sum(bal.values())
    held = [tuple(bal[c] for c in order)]
    strikes, last_spread, log = 0, None, []
    for rnd in range(budget):
        gap = {c: t - bal[c] for c, t in targets(bal, need, pool).items()}
        spread = sum(abs(v) for v in gap.values())
        if spread == 0:
            return "settled", rnd, rate, bal, log
        if last_spread is not None and spread >= last_spread:
            strikes += 1
            if strikes == patience:
                rate, strikes = rate // 2, 0
        sweep, posted = balance(gap, rate, tie_order)
        log.append((rnd + 1, spread, rate, strikes, sum(v for v in posted.values() if v > 0)))
        if all(v == 0 for v in sweep.values()):
            return "stalled", rnd + 1, rate, bal, log
        bal = {c: bal[c] + posted[c] for c in bal}
        state = tuple(bal[c] for c in order)
        if state in held:
            low = min(held[held.index(state):])
            return "cycling", rnd + 1, rate, dict(zip(order, low)), log
        held.append(state)
        last_spread = spread
    return "budget", budget, rate, bal, log


def labels_of(envs):
    return {e["code"]: e["label"] for e in envs}


def settle(data):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read_string((data / "office.ini").read_text(encoding="utf-8"))
    homes, envs, alias = read_register(data)
    params = read_params(data, cfg["sweep"]["parameter_sheet"])
    ledger, quality = close_ledger(data, cfg, envs, alias)
    cents = {e["code"]: e["opening"] for e in envs}
    for t in ledger:
        cents[t["envelope"]] += t["cents"]
    charge = keeping_charges(data, envs, ledger)
    results = {}
    for hh, (district, family) in homes.items():
        mine = [dict(e, bal=cents[e["code"]] // 100 - charge[e["code"]]) for e in envs if e["hh"] == hh]
        rate, patience, budget = params[district]
        budget = int(cfg.get("overrides", f"{district}_round_budget", fallback=budget))
        exit_, rounds, rate, final, log = sweep_household(mine, rate, patience, budget)
        results[district] = {"hh": hh, "family": family, "envs": mine, "exit": exit_, "rounds": rounds, "rate": rate,
                             "final": final, "log": log}
    where = {e["code"]: homes[e["hh"]][0] for e in envs}
    for t in ledger:
        t["district"] = where[t["envelope"]]
    prior = json.loads((data / "prior_sweep.json").read_text(encoding="utf-8"))
    return cfg, results, ledger, quality, prior


def dump(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def text(lines):
    return ("\n".join(lines) + "\n").encode("ascii")


def region_report(district, r):
    rows = []
    for e in sorted(r["envs"], key=lambda e: e["code"]):
        rows.append({"code": e["code"], "label": e["label"], "category": e["category"], "segment": e["segment"],
                     "need_dollars": e["need"], "presweep_dollars": e["bal"], "final_dollars": r["final"][e["code"]]})
    moved = sum(max(x["final_dollars"] - x["presweep_dollars"], 0) for x in rows)
    return {"district": district, "household": r["hh"], "family_name": r["family"], "exit": r["exit"],
            "rounds": r["rounds"], "damping_percent": r["rate"], "pool_dollars": sum(x["presweep_dollars"] for x in rows),
            "moved_dollars": moved, "envelopes": rows}


def build_reports(cfg, results, ledger, quality, prior):
    """Return (text reports by name, table reports by name); table reports are lists of (name, header, rows)."""
    out = {}
    regions = {d: region_report(d, results[d]) for d in DISTRICTS}
    for d in DISTRICTS:
        out[f"region_{d}.json"] = dump(regions[d])
    flat = [(d, x) for d in DISTRICTS for x in regions[d]["envelopes"]]
    for seg in SEGMENTS:
        mem = [(d, x) for d, x in flat if x["segment"] == seg]
        out[f"segment_{seg}.json"] = dump({"segment": seg, "envelopes": len(mem),
                                           "presweep_dollars": sum(x["presweep_dollars"] for _d, x in mem),
                                           "final_dollars": sum(x["final_dollars"] for _d, x in mem),
                                           "members": [{"district": d, "code": x["code"], "final_dollars": x["final_dollars"]}
                                                       for d, x in mem]})
    out["product_summary.json"] = dump({"categories": categories(flat)})
    out["data_quality.json"] = dump(quality)
    out["normalized.jsonl"] = "".join(json.dumps({k: t[k] for k in ("cents", "date", "district", "envelope", "source", "txn")},
                                                 sort_keys=True, separators=(",", ":")) + "\n" for t in ledger).encode("ascii")
    out["summary.json"] = dump(summary(cfg, regions, ledger, prior))
    out["sweep_rounds.csv"] = rounds_csv(results)
    out.update(flat_reports(regions, flat, ledger, prior))
    out.update(hold_reports(regions))
    tables = table_reports(regions, flat)
    digests = {n: hashlib.sha256(b).hexdigest() for n, b in out.items()}
    digests.update({n: hashlib.sha256(table_dump(t)).hexdigest() for n, t in tables.items()})
    out["manifest.json"] = dump({"reports": [{"name": n, "sha256": digests[n]} for n in sorted(digests)]})
    return out, tables


def hold_reports(regions):
    """One hold report per household whose sweep ends stalled, named by its household code in lower case."""
    out = {}
    for d in DISTRICTS:
        r = regions[d]
        if r["exit"] != "stalled":
            continue
        short = [x for x in r["envelopes"] if x["final_dollars"] < x["need_dollars"]]
        out[f"hold_{r['household'].lower()}.json"] = dump({
            "district": d, "household": r["household"], "rounds": r["rounds"],
            "short_dollars": sum(x["need_dollars"] - x["final_dollars"] for x in short),
            "envelopes": [{"code": x["code"], "category": x["category"], "segment": x["segment"],
                           "short_dollars": x["need_dollars"] - x["final_dollars"]} for x in short]})
    return out


def categories(flat):
    cats = []
    for cat in sorted({x["category"] for _d, x in flat}):
        xs = [x for _d, x in flat if x["category"] == cat]
        cats.append({"category": cat, "envelopes": len(xs), "presweep_dollars": sum(x["presweep_dollars"] for x in xs),
                     "final_dollars": sum(x["final_dollars"] for x in xs),
                     "moved_in_dollars": sum(max(x["final_dollars"] - x["presweep_dollars"], 0) for x in xs),
                     "moved_out_dollars": sum(max(x["presweep_dollars"] - x["final_dollars"], 0) for x in xs)})
    return cats


def flat_reports(regions, flat, ledger, prior):
    out = {}
    out["envelope_final.tsv"] = text(["district\tcode\tlabel\tcategory\tsegment\tfinal_dollars"] + [
        "\t".join([d, x["code"], x["label"], x["category"], x["segment"], str(x["final_dollars"])]) for d, x in flat])
    out["moves.csv"] = text(["district,code,label,presweep_dollars,final_dollars,moved_dollars"] + [
        ",".join([d, x["code"], x["label"], str(x["presweep_dollars"]), str(x["final_dollars"]),
                  str(x["final_dollars"] - x["presweep_dollars"])]) for d, x in flat if x["final_dollars"] != x["presweep_dollars"]])
    out["exits.xml"] = text(['<?xml version="1.0" encoding="UTF-8"?>', "<sweep>"] + [
        f'  <household district="{d}" exit="{r["exit"]}" rounds="{r["rounds"]}" damping_percent="{r["damping_percent"]}" '
        f'family_name="{xml_escape(r["family_name"])}"/>' for d, r in regions.items()] + ["</sweep>"])
    out["prior_delta.yaml"] = text([f"{d}: {regions[d]['moved_dollars'] - prior['households'][d]['moved_dollars']}"
                                    for d in DISTRICTS])
    out["reconciliation.txt"] = text([f"{d} pool={r['pool_dollars']} final={sum(x['final_dollars'] for x in r['envelopes'])} "
                                      f"moved={r['moved_dollars']}" for d, r in regions.items()])
    per = {}
    for t in ledger:
        per[t["envelope"]] = per.get(t["envelope"], 0) + t["cents"]
    out["ledger_totals.psv"] = text(["district|code|applied_cents|presweep_dollars"] + [
        f"{d}|{x['code']}|{per.get(x['code'], 0)}|{x['presweep_dollars']}" for d, x in flat])
    return out


def xml_escape(v):
    return v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def table_reports(regions, flat):
    exits = [[d, r["exit"], r["rounds"], r["damping_percent"]] for d, r in regions.items()]
    final = [[d, x["code"], x["final_dollars"]] for d, x in flat]
    return {"sweep.sqlite": [("envelope_final", ["district", "code", "final_dollars"], final),
                             ("household_exit", ["district", "exit", "rounds", "damping_percent"], exits)],
            "sweep_book.xlsx": [("exits", ["district", "exit", "rounds", "damping_percent"], exits),
                                ("final", ["district", "code", "final_dollars"], final)]}


def table_dump(tables):
    lines = []
    for name, head, rows in tables:
        lines.append(f"table {name}: " + "|".join(head))
        lines += ["|".join(str(v) for v in row) for row in rows]
    return text(lines)


def summary(cfg, regions, ledger, prior):
    exits = {k: 0 for k in ("budget", "cycling", "settled", "stalled")}
    for r in regions.values():
        exits[r["exit"]] += 1
    return {"first_day": cfg["period"]["first_day"], "last_day": cfg["period"]["last_day"], "households": len(regions),
            "exits": exits, "moved_dollars": sum(r["moved_dollars"] for r in regions.values()),
            "transactions_applied": len(ledger)}


def rounds_csv(results):
    lines = ["district,round,spread,damping_percent,strikes,posted_dollars"]
    for d in DISTRICTS:
        lines += [",".join(str(v) for v in (d,) + row) for row in results[d]["log"]]
    return text(lines)


def write_sqlite(path, tables):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    try:
        for name, head, rows in tables:
            kinds = ["INTEGER" if isinstance(v, int) else "TEXT" for v in rows[0]]
            con.execute(f"CREATE TABLE {name} (" + ", ".join(f"{h} {k}" for h, k in zip(head, kinds)) + ")")
            con.executemany(f"INSERT INTO {name} VALUES (" + ", ".join("?" * len(head)) + ")", rows)
        con.commit()
    finally:
        con.close()


def write_xlsx(path, tables):
    sheets = [(name, [head] + rows) for name, head, rows in tables]
    path.write_bytes(xlsx_bytes(sheets))


def xlsx_bytes(sheets):
    ns = "http://schemas.openxmlformats.org"
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml"
    parts = {
        "[Content_Types].xml": f'<Types xmlns="{ns}/package/2006/content-types"><Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" '
        f'ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="{ctype}.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{ctype}.worksheet+xml"/>'
                  for i in range(1, len(sheets) + 1)) + "</Types>",
        "_rels/.rels": f'<Relationships xmlns="{ns}/package/2006/relationships"><Relationship Id="rId1" '
        f'Type="{ns}/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{ns}/spreadsheetml/2006/main" xmlns:r="{ns}/officeDocument/2006/relationships">'
        "<sheets>" + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _r) in enumerate(sheets, 1))
        + "</sheets></workbook>",
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{ns}/package/2006/relationships">' + "".join(
            f'<Relationship Id="rId{i}" Type="{ns}/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)) + "</Relationships>",
    }
    for i, (_n, rows) in enumerate(sheets, 1):
        parts[f"xl/worksheets/sheet{i}.xml"] = f'<worksheet xmlns="{ns}/spreadsheetml/2006/main"><sheetData>' + "".join(
            f'<row r="{r}">' + "".join(xlsx_cell(f"{chr(65 + j)}{r}", v) for j, v in enumerate(row)) + "</row>"
            for r, row in enumerate(rows, 1)) + "</sheetData></worksheet>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 30, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (head + body).encode("utf-8"))
    return buf.getvalue()


def xlsx_cell(ref, v):
    if isinstance(v, int):
        return f'<c r="{ref}"><v>{v}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(v)}</t></is></c>'


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: transform.py DATA_DIR OUT_DIR")
    data, out_dir = Path(argv[1]), Path(argv[2])
    try:
        reports, tables = build_reports(*settle(data))
    except ExtractError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(reports):
        (out_dir / name).write_bytes(reports[name])
    write_sqlite(out_dir / "sweep.sqlite", tables["sweep.sqlite"])
    write_xlsx(out_dir / "sweep_book.xlsx", tables["sweep_book.xlsx"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
