#!/usr/bin/env python3
"""Month-end ledger close and envelope sweep for the household budgeting office."""

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import date, timedelta

DISTRICTS = ("central", "east", "north", "south", "west")
RATE_MIN = 12
RATE_MAX = 50
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOCREL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class InputRuleError(Exception):
    """An extract that breaks a rule of the inputs."""


def round_half_zero(num, den):
    """num/den to the nearest integer, a half going to the value nearer zero."""
    if den < 0:
        num, den = -num, -den
    neg = num < 0
    mag = -num if neg else num
    whole, rest = divmod(mag, den)
    if 2 * rest > den:
        whole += 1
    return -whole if neg else whole


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def read_delimited(path, delimiter):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def load_ini(path):
    section = None
    conf = {}
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            conf[section] = {}
        else:
            key, _, value = line.partition("=")
            conf[section][key.strip()] = value.strip()
    return conf


def load_db(path):
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        tables = {}
        names = [row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for name in names:
            cur = con.execute("SELECT * FROM %s" % name)
            cols = [d[0] for d in cur.description]
            tables[name] = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()
    return tables


def load_fund_codes(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    segments = {}
    for match in re.finditer(rb"<<([^<>]*)>>\s*stream\r?\n", raw):
        if b"FlateDecode" not in match.group(1):
            continue
        start = match.end()
        body = raw[start:raw.index(b"endstream", start)]
        text = zlib.decompress(body.rstrip(b"\r\n")).decode("latin-1")
        for line in re.findall(r"\((.*?)\)\s*Tj", text):
            bits = line.split(" = ")
            if len(bits) == 2:
                segments[bits[0].strip()] = bits[1].strip()
    return segments


def load_cat_codes(path):
    with zipfile.ZipFile(path) as book:
        root = ET.fromstring(book.read("word/document.xml"))
    table = root.find(".//%stbl" % WORD)
    categories = {}
    for row in table.findall("%str" % WORD):
        cells = ["".join(node.text or "" for node in cell.iter("%st" % WORD))
                 for cell in row.findall("%stc" % WORD)]
        if len(cells) == 2 and cells[0] != "code":
            categories[cells[0]] = cells[1]
    return categories


def sheet_rows(book, part):
    root = ET.fromstring(book.read(part))
    rows = []
    for row in root.iter("%srow" % MAIN):
        cells = {}
        for cell in row.findall("%sc" % MAIN):
            letters = re.match(r"[A-Z]+", cell.get("r")).group(0)
            inline = cell.find("%sis/%st" % (MAIN, MAIN))
            value = cell.find("%sv" % MAIN)
            if inline is not None:
                cells[letters] = inline.text or ""
            elif value is not None:
                cells[letters] = value.text or ""
        rows.append(cells)
    return rows


def load_parameters(path, sheet_name, overrides):
    with zipfile.ZipFile(path) as book:
        wb = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target")
                   for rel in rels.findall("%sRelationship" % PKGREL)}
        part = None
        for sheet in wb.iter("%ssheet" % MAIN):
            if sheet.get("name") == sheet_name:
                part = "xl/" + targets[sheet.get("%sid" % DOCREL)]
        if part is None:
            raise InputRuleError("parameter sheet %s not found" % sheet_name)
        rows = sheet_rows(book, part)
    header = {name: letters for letters, name in rows[0].items()}
    params = {}
    for row in rows[1:]:
        district = row[header["district"]].strip().lower()
        params[district] = {
            name: int(row[header[name]])
            for name in ("damping_percent", "patience", "round_budget")}
    for (district, name), value in overrides.items():
        if name == "round_budget" and district in params:
            params[district][name] = value
    return params


def read_overrides(conf):
    out = {}
    for key, value in conf.get("overrides", {}).items():
        district, _, name = key.strip().lower().partition("_")
        out[(district, name)] = int(value)
    return out


def load_envelopes(data_dir, crosswalk, tables):
    files = {"env_a.csv": lambda p: read_delimited(p, ","),
             "env_b.tsv": lambda p: read_delimited(p, "\t"),
             "env_c.jsonl": lambda p: [json.loads(line) for line
                                       in read_text(p).splitlines() if line.strip()]}
    envelopes = {}
    for name in sorted(files):
        for raw in files[name](os.path.join(data_dir, name)):
            row = {crosswalk[name][key]: value for key, value in raw.items()}
            envelopes[row["env_code"]] = {
                "code": row["env_code"],
                "file_no": row["file_no"],
                "label": row["label"],
                "category_code": row["category_code"],
                "funding_code": row["funding_code"],
                "need": int(str(row["need_dollars"])),
                "opening": int(str(row["opening_cents"]))}
    file_hh = {r["file_no"]: r["hh_code"] for r in tables["file"]}
    households = {r["hh_code"]: r for r in tables["household"]}
    district_name = {r["district_id"]: r["district_name"].strip().lower()
                     for r in tables["district"]}
    plans = {r["env_code"]: r["plan"] for r in tables["keep_plan"]}
    for env in envelopes.values():
        hh = households[file_hh[env["file_no"]]]
        env["hh_code"] = hh["hh_code"]
        env["family_name"] = hh["family_name"]
        env["district"] = district_name[hh["district_id"]]
        env["plan"] = plans[env["code"]]
    return envelopes


def name_codes(envelopes, fund_codes, categories):
    for env in envelopes.values():
        env["segment"] = fund_codes[env["funding_code"]]
        env["category"] = categories[env["category_code"]]


def make_row(txn, day, code, cents, source, malformed, code_map, period):
    key = code.upper()
    if key not in code_map:
        raise InputRuleError("row %s names unknown envelope %s" % (txn, code))
    in_period = period[0] <= day <= period[1]
    return {"txn": txn, "date": day, "env": code_map[key], "cents": cents,
            "source": source, "malformed": malformed,
            "in_period": in_period, "voided": False}


def load_tx_a(path, code_map, period):
    rows = []
    for raw in read_delimited(path, ","):
        cents, direction = raw["cents"], raw["dir"]
        bad = not re.fullmatch(r"[0-9]+", cents or "") or direction not in ("in", "out")
        signed = None if bad else int(cents) * (1 if direction == "in" else -1)
        rows.append(make_row(raw["txn"], date.fromisoformat(raw["day"]), raw["env"],
                             signed, "tx_a.csv", bad, code_map, period))
    return rows


def resolve_alias(aliases, alias, day, txn):
    best = None
    for since, code in aliases.get(alias, ()):
        if since <= day and (best is None or since > best[0]):
            best = (since, code)
    if best is None:
        raise InputRuleError("row %s names unresolvable alias %s" % (txn, alias))
    return best[1]


def load_tx_b(path, code_map, period, aliases):
    rows = []
    for raw in read_delimited(path, "\t"):
        amount, kind = raw["amount"], raw["kind"]
        bad = (not re.fullmatch(r"[0-9]+\.[0-9]{2}", amount or "")
               or kind not in ("D", "S"))
        day = date.fromisoformat(raw["posted"])
        signed = None
        if not bad:
            whole, _, frac = amount.partition(".")
            signed = (int(whole) * 100 + int(frac)) * (1 if kind == "D" else -1)
        code = resolve_alias(aliases, raw["alias"], day, raw["id"])
        rows.append(make_row(raw["id"], day, code, signed, "tx_b.tsv", bad,
                             code_map, period))
    return rows


def read_varint(buf, pos):
    shift = 0
    value = 0
    while True:
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7


def read_svarint(buf, pos):
    value, pos = read_varint(buf, pos)
    if value % 2:
        return -(value + 1) // 2, pos
    return value // 2, pos


def txc_epoch(path):
    match = re.search(r"counts days after (\d{4}-\d{2}-\d{2})", read_text(path))
    if match is None:
        raise InputRuleError("tx_c.bin day epoch not documented")
    return date.fromisoformat(match.group(1))


def load_tx_c(path, code_map, period, epoch):
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw[:4] != b"TXC1":
        raise InputRuleError("tx_c.bin lacks its magic bytes")
    if zlib.crc32(raw[:-4]) != int.from_bytes(raw[-4:], "big"):
        raise InputRuleError("tx_c.bin checksum does not match")
    count = int.from_bytes(raw[5:7], "big")
    pos = 7
    rows = []
    dictionary = []
    prev_day = None
    prev_code = None
    for _ in range(count):
        selector = raw[pos]
        pos += 1
        mode, bad = selector & 3, bool(selector & 4)
        if mode == 3 or selector & 0xF8:
            raise InputRuleError("tx_c.bin holds an unknown selector")
        number, pos = read_varint(raw, pos)
        if mode == 0:
            size = raw[pos]
            pos += 1
            code = raw[pos:pos + size].decode("ascii")
            pos += size
            day, pos = read_svarint(raw, pos)
            if not any(entry.upper() == code.upper() for entry in dictionary):
                dictionary.insert(0, code)
        elif mode == 1:
            delta, pos = read_svarint(raw, pos)
            day, code = prev_day + delta, prev_code
        else:
            index = raw[pos]
            pos += 1
            day, pos = read_svarint(raw, pos)
            code = dictionary[index]
        signed = None
        if not bad:
            signed, pos = read_svarint(raw, pos)
        prev_day, prev_code = day, code
        rows.append(make_row("T%05d" % number, epoch + timedelta(days=day), code,
                             signed, "tx_c.bin", bad, code_map, period))
    if pos != len(raw) - 4:
        raise InputRuleError("tx_c.bin record count does not fill the file")
    return rows


def load_corrections(path):
    rows = []
    for raw in read_delimited(path, "|"):
        rows.append({"seq": int(raw["seq"]), "txn": raw["txn"],
                     "action": raw["action"], "value": raw["value"]})
    return rows


def apply_corrections(rows, corrections, cutoff):
    by_txn = {}
    for row in rows:
        if row["txn"] in by_txn:
            raise InputRuleError("transaction id %s appears twice" % row["txn"])
        by_txn[row["txn"]] = row
    applied = [c for c in corrections if c["seq"] <= cutoff]
    for corr in applied:
        if corr["txn"] not in by_txn:
            raise InputRuleError("correction %d names unknown transaction %s"
                                 % (corr["seq"], corr["txn"]))
    for corr in sorted(applied, key=lambda c: c["seq"]):
        row = by_txn[corr["txn"]]
        if row["malformed"] or not row["in_period"] or row["voided"]:
            continue
        if corr["action"] == "void":
            row["voided"] = True
        elif corr["action"] == "amend":
            sign = -1 if row["cents"] < 0 else 1
            row["cents"] = sign * int(corr["value"])
        else:
            raise InputRuleError("correction %d has unknown action" % corr["seq"])
    return len(applied), len(corrections) - len(applied)


def fee_groups(fees, envelopes):
    groups = []
    hh_codes = {env["hh_code"] for env in envelopes.values()}
    funds = {env["funding_code"] for env in envelopes.values()}
    cats = {env["category_code"] for env in envelopes.values()}
    for row in fees:
        ref = row["client_ref"]
        if ref in hh_codes:
            members = [e for e in envelopes.values() if e["hh_code"] == ref]
        elif ref in funds:
            members = [e for e in envelopes.values() if e["funding_code"] == ref]
        elif ref in cats:
            members = [e for e in envelopes.values() if e["category_code"] == ref]
        else:
            raise InputRuleError("fee row %s names nothing of the register" % ref)
        groups.append((int(row["charge_cents"]), members))
    return groups


def group_tables(groups):
    """Per fee row: its charge and, per keeping plan, each rate's contribution."""
    tables = []
    for charge, members in groups:
        per_plan = {}
        for env in members:
            per_plan.setdefault(env["plan"], []).append(env["opening"])
        shaped = {}
        for plan, openings in per_plan.items():
            shaped[plan] = [sum(round_half_zero(o * rate, 10000) for o in openings)
                            for rate in range(RATE_MIN, RATE_MAX + 1)]
        tables.append({"charge": charge, "plans": shaped})
    return tables


def plan_order(tables, plans):
    order = []
    for table in sorted(tables, key=lambda t: len(t["plans"])):
        for plan in sorted(table["plans"]):
            if plan not in order:
                order.append(plan)
    for plan in sorted(plans):
        if plan not in order:
            order.append(plan)
    return order


def rates_possible(tables, assign):
    for table in tables:
        total = 0
        low = 0
        high = 0
        for plan, column in table["plans"].items():
            if plan in assign:
                total += column[assign[plan] - RATE_MIN]
            else:
                low += min(column)
                high += max(column)
        if not total + low <= table["charge"] <= total + high:
            return False
    return True


def search_rates(tables, order, assign, depth, found):
    if depth == len(order):
        found.append(dict(assign))
        return
    plan = order[depth]
    for rate in range(RATE_MIN, RATE_MAX + 1):
        assign[plan] = rate
        if rates_possible(tables, assign):
            search_rates(tables, order, assign, depth + 1, found)
            if len(found) > 1:
                break
    del assign[plan]


def solve_rates(fees, envelopes):
    plans = sorted({env["plan"] for env in envelopes.values()})
    tables = group_tables(fee_groups(fees, envelopes))
    found = []
    search_rates(tables, plan_order(tables, plans), {}, 0, found)
    if not found:
        raise InputRuleError("no keeping rate assignment meets stmt_fees.csv")
    if len(found) > 1:
        raise InputRuleError("more than one keeping rate assignment meets"
                             " stmt_fees.csv")
    return found[0]


def close_ledger(envelopes, rows, fees, rates):
    statement_day = date.fromisoformat(fees[0]["through"])
    for env in envelopes.values():
        env["applied_cents"] = 0
        env["statement_cents"] = env["opening"]
    for row in rows:
        if row["malformed"] or not row["in_period"] or row["voided"]:
            continue
        env = envelopes[row["env"]]
        env["applied_cents"] += row["cents"]
        if row["date"] <= statement_day:
            env["statement_cents"] += row["cents"]
    for env in envelopes.values():
        rate = rates[env["plan"]]
        env["charge"] = round_half_zero(env["statement_cents"] * rate, 1000000)
        env["closing_cents"] = env["opening"] + env["applied_cents"]
        env["presweep"] = env["closing_cents"] // 100 - env["charge"]


def sweep_round(balances, needs, pool):
    claims = [need + max(0, need - bal) for need, bal in zip(needs, balances)]
    total = sum(claims)
    targets = [round_half_zero(pool * claim, total) for claim in claims]
    gaps = [target - bal for target, bal in zip(targets, balances)]
    return gaps, sum(abs(gap) for gap in gaps)


def adjustment_index(gaps, labels):
    best = None
    for index, gap in enumerate(gaps):
        if best is None or abs(gap) > abs(gaps[best]) or (
                abs(gap) == abs(gaps[best]) and labels[index] < labels[best]):
            best = index
    return best


def sweep_household(envelopes, params):
    """Run the sweep of one household; envelopes come in envelope code order."""
    needs = [env["need"] for env in envelopes]
    labels = [env["label"] for env in envelopes]
    balances = [env["presweep"] for env in envelopes]
    pool = sum(balances)
    damping = params["damping_percent"]
    states = [tuple(balances)]
    rounds = []
    strikes = 0
    previous = None
    while True:
        gaps, spread = sweep_round(balances, needs, pool)
        if spread == 0:
            return {"exit": "settled", "damping": damping, "final": balances,
                    "round_rows": rounds, "pool": pool}
        if previous is not None and spread >= previous:
            strikes += 1
            if strikes >= params["patience"]:
                damping //= 2
                strikes = 0
        drafts = [round_half_zero(gap * damping, 100) for gap in gaps]
        if not any(drafts):
            rounds.append((spread, damping, strikes, 0))
            return {"exit": "stalled", "damping": damping, "final": balances,
                    "round_rows": rounds, "pool": pool}
        posted = list(drafts)
        excess = sum(drafts)
        if excess:
            posted[adjustment_index(gaps, labels)] -= excess
        balances = [bal + post for bal, post in zip(balances, posted)]
        rounds.append((spread, damping, strikes,
                       sum(post for post in posted if post > 0)))
        state = tuple(balances)
        if state in states:
            record = states[states.index(state):]
            return {"exit": "cycling", "damping": damping,
                    "final": list(min(record)), "round_rows": rounds, "pool": pool}
        states.append(state)
        if len(rounds) == params["round_budget"]:
            return {"exit": "budget", "damping": damping, "final": balances,
                    "round_rows": rounds, "pool": pool}
        previous = spread


def run_sweeps(envelopes, params):
    results = {}
    for district in DISTRICTS:
        members = sorted((env for env in envelopes.values()
                          if env["district"] == district), key=lambda e: e["code"])
        result = sweep_household(members, params[district])
        for env, final in zip(members, result["final"]):
            env["final"] = final
        result["rounds"] = len(result["round_rows"])
        result["envelopes"] = members
        result["moved"] = sum(max(0, env["final"] - env["presweep"])
                              for env in members)
        result["hh_code"] = members[0]["hh_code"]
        result["family_name"] = members[0]["family_name"]
        results[district] = result
    return results


def dump_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def report_normalized(rows, envelopes):
    lines = []
    applied = [row for row in rows
               if not row["malformed"] and row["in_period"] and not row["voided"]]
    for row in sorted(applied, key=lambda r: r["txn"]):
        obj = {"cents": row["cents"], "date": row["date"].isoformat(),
               "district": envelopes[row["env"]]["district"],
               "envelope": row["env"], "source": row["source"], "txn": row["txn"]}
        lines.append(json.dumps(obj, sort_keys=True, separators=(",", ":")))
    return "".join(line + "\n" for line in lines), len(applied)


def report_data_quality(rows, corrections_applied, past_cutoff):
    exports = {}
    for name in ("tx_a.csv", "tx_b.tsv", "tx_c.bin"):
        subset = [row for row in rows if row["source"] == name]
        good = [row for row in subset if not row["malformed"] and row["in_period"]]
        exports[name] = {
            "rows": len(subset),
            "malformed": sum(1 for row in subset if row["malformed"]),
            "out_of_period": sum(1 for row in subset
                                 if not row["malformed"] and not row["in_period"]),
            "applied": sum(1 for row in good if not row["voided"]),
            "voided": sum(1 for row in good if row["voided"])}
    return dump_json({"exports": exports,
                      "corrections": {"applied": corrections_applied,
                                      "past_cutoff": past_cutoff}})


def report_summary(conf, results, applied_count):
    exits = {name: 0 for name in ("budget", "cycling", "settled", "stalled")}
    for result in results.values():
        exits[result["exit"]] += 1
    return dump_json({
        "first_day": conf["period"]["first_day"],
        "last_day": conf["period"]["last_day"],
        "households": len(results),
        "exits": exits,
        "moved_dollars": sum(r["moved"] for r in results.values()),
        "transactions_applied": applied_count})


def report_product_summary(envelopes):
    groups = {}
    for env in envelopes.values():
        groups.setdefault(env["category"], []).append(env)
    categories = []
    for name in sorted(groups):
        members = groups[name]
        categories.append({
            "category": name,
            "envelopes": len(members),
            "presweep_dollars": sum(e["presweep"] for e in members),
            "final_dollars": sum(e["final"] for e in members),
            "moved_in_dollars": sum(max(0, e["final"] - e["presweep"])
                                    for e in members),
            "moved_out_dollars": sum(max(0, e["presweep"] - e["final"])
                                     for e in members)})
    return dump_json({"categories": categories})


def report_region(district, result):
    return dump_json({
        "district": district,
        "household": result["hh_code"],
        "family_name": result["family_name"],
        "exit": result["exit"],
        "rounds": result["rounds"],
        "damping_percent": result["damping"],
        "pool_dollars": result["pool"],
        "moved_dollars": result["moved"],
        "envelopes": [{"code": env["code"], "label": env["label"],
                       "category": env["category"], "segment": env["segment"],
                       "need_dollars": env["need"],
                       "presweep_dollars": env["presweep"],
                       "final_dollars": env["final"]}
                      for env in result["envelopes"]]})


def report_hold(district, result):
    short = [env for env in result["envelopes"] if env["final"] < env["need"]]
    return dump_json({
        "district": district,
        "household": result["hh_code"],
        "rounds": result["rounds"],
        "envelopes": [{"code": env["code"], "category": env["category"],
                       "segment": env["segment"],
                       "short_dollars": env["need"] - env["final"]}
                      for env in short],
        "short_dollars": sum(env["need"] - env["final"] for env in short)})


def report_segment(segment, ordered):
    members = [env for env in ordered if env["segment"] == segment]
    return dump_json({
        "segment": segment,
        "envelopes": len(members),
        "presweep_dollars": sum(env["presweep"] for env in members),
        "final_dollars": sum(env["final"] for env in members),
        "members": [{"district": env["district"], "code": env["code"],
                     "final_dollars": env["final"]} for env in members]})


def report_sweep_rounds(results):
    lines = ["district,round,spread,damping_percent,strikes,posted_dollars"]
    for district in DISTRICTS:
        for index, row in enumerate(results[district]["round_rows"], start=1):
            lines.append("%s,%d,%d,%d,%d,%d" % (district, index, row[0], row[1],
                                                row[2], row[3]))
    return "".join(line + "\n" for line in lines)


def report_envelope_final(ordered):
    lines = ["\t".join(("district", "code", "label", "category", "segment",
                        "final_dollars"))]
    for env in ordered:
        lines.append("\t".join((env["district"], env["code"], env["label"],
                                env["category"], env["segment"],
                                str(env["final"]))))
    return "".join(line + "\n" for line in lines)


def report_moves(ordered):
    lines = ["district,code,label,presweep_dollars,final_dollars,moved_dollars"]
    for env in ordered:
        if env["final"] != env["presweep"]:
            lines.append("%s,%s,%s,%d,%d,%d" % (
                env["district"], env["code"], env["label"], env["presweep"],
                env["final"], env["final"] - env["presweep"]))
    return "".join(line + "\n" for line in lines)


def xml_attr(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def report_exits(results):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<sweep>"]
    for district in DISTRICTS:
        result = results[district]
        lines.append(
            '  <household district="%s" exit="%s" rounds="%s" damping_percent="%s"'
            ' family_name="%s"/>' % (
                xml_attr(district), xml_attr(result["exit"]),
                xml_attr(result["rounds"]), xml_attr(result["damping"]),
                xml_attr(result["family_name"])))
    lines.append("</sweep>")
    return "".join(line + "\n" for line in lines)


def report_prior_delta(results, prior):
    lines = []
    for district in DISTRICTS:
        prior_moved = prior["households"][district]["moved_dollars"]
        lines.append("%s: %d" % (district, results[district]["moved"] - prior_moved))
    return "".join(line + "\n" for line in lines)


def report_reconciliation(results):
    lines = []
    for district in DISTRICTS:
        result = results[district]
        lines.append("%s pool=%d final=%d moved=%d" % (
            district, result["pool"],
            sum(env["final"] for env in result["envelopes"]), result["moved"]))
    return "".join(line + "\n" for line in lines)


def report_ledger_totals(ordered):
    lines = ["district|code|applied_cents|presweep_dollars"]
    for env in ordered:
        lines.append("%s|%s|%d|%d" % (env["district"], env["code"],
                                      env["applied_cents"], env["presweep"]))
    return "".join(line + "\n" for line in lines)


def table_blocks(results, ordered):
    final = [(env["district"], env["code"], env["final"]) for env in ordered]
    exits = [(district, results[district]["exit"], results[district]["rounds"],
              results[district]["damping"]) for district in DISTRICTS]
    sqlite_blocks = [
        ("envelope_final", ["district", "code", "final_dollars"], final),
        ("household_exit", ["district", "exit", "rounds", "damping_percent"], exits)]
    book_blocks = [
        ("exits", ["district", "exit", "rounds", "damping_percent"], exits),
        ("final", ["district", "code", "final_dollars"], final)]
    return sqlite_blocks, book_blocks


def table_text(blocks):
    out = []
    for name, header, rows in blocks:
        out.append("table %s: %s\n" % (name, "|".join(header)))
        for row in rows:
            out.append("|".join(str(value) for value in row) + "\n")
    return "".join(out)


def write_sqlite(path, exits, final):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE envelope_final (district TEXT, code TEXT,"
                    " final_dollars INTEGER)")
        con.execute("CREATE TABLE household_exit (district TEXT, exit TEXT,"
                    " rounds INTEGER, damping_percent INTEGER)")
        con.executemany("INSERT INTO envelope_final VALUES (?,?,?)", final)
        con.executemany("INSERT INTO household_exit VALUES (?,?,?,?)", exits)
        con.commit()
    finally:
        con.close()


def sheet_xml(header, rows):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
           '2006/main"><sheetData>']
    letters = "ABCDEFGHIJKLMNOP"
    for index, row in enumerate([list(header)] + [list(r) for r in rows], start=1):
        out.append('<row r="%d">' % index)
        for column, value in enumerate(row):
            ref = "%s%d" % (letters[column], index)
            if isinstance(value, int):
                out.append('<c r="%s"><v>%d</v></c>' % (ref, value))
            else:
                out.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>'
                           % (ref, xml_attr(value)))
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def workbook_parts(blocks):
    return {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="rels" ContentType="application/'
            'vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml"'
            ' ContentType="application/xml"/><Override PartName="/xl/workbook.xml"'
            ' ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/'
            'sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/'
            'sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
            ' Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
            'main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships"><sheets><sheet name="%s" sheetId="1" r:id="rId1"/>'
            '<sheet name="%s" sheetId="2" r:id="rId2"/></sheets></workbook>'
            % (blocks[0][0], blocks[1][0]),
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.'
            'openxmlformats.org/officeDocument/2006/relationships/worksheet"'
            ' Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://'
            'schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
            ' Target="worksheets/sheet2.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet_xml(blocks[0][1], blocks[0][2]),
        "xl/worksheets/sheet2.xml": sheet_xml(blocks[1][1], blocks[1][2])}


def workbook_bytes(blocks):
    parts = workbook_parts(blocks)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as book:
        for name in ["[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                     "xl/_rels/workbook.xml.rels", "xl/worksheets/sheet1.xml",
                     "xl/worksheets/sheet2.xml"]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            book.writestr(info, parts[name])
    return buffer.getvalue()


def build_reports(conf, envelopes, rows, results, counts, prior):
    ordered = []
    for district in DISTRICTS:
        ordered.extend(results[district]["envelopes"])
    normalized, applied_count = report_normalized(rows, envelopes)
    texts = {
        "normalized.jsonl": normalized,
        "data_quality.json": report_data_quality(rows, counts[0], counts[1]),
        "summary.json": report_summary(conf, results, applied_count),
        "product_summary.json": report_product_summary(envelopes),
        "sweep_rounds.csv": report_sweep_rounds(results),
        "envelope_final.tsv": report_envelope_final(ordered),
        "moves.csv": report_moves(ordered),
        "exits.xml": report_exits(results),
        "prior_delta.yaml": report_prior_delta(results, prior),
        "reconciliation.txt": report_reconciliation(results),
        "ledger_totals.psv": report_ledger_totals(ordered)}
    for district in DISTRICTS:
        texts["region_%s.json" % district] = report_region(district,
                                                           results[district])
        if results[district]["exit"] == "stalled":
            name = "hold_%s.json" % results[district]["hh_code"].lower()
            texts[name] = report_hold(district, results[district])
    for segment in ("consumer", "corporate", "enterprise", "smb"):
        texts["segment_%s.json" % segment] = report_segment(segment, ordered)
    return texts, table_blocks(results, ordered)


def manifest_json(texts, sqlite_blocks, book_blocks):
    entries = []
    for name in texts:
        digest = hashlib.sha256(texts[name].encode("ascii")).hexdigest()
        entries.append({"name": name, "sha256": digest})
    for name, blocks in (("sweep.sqlite", sqlite_blocks),
                         ("sweep_book.xlsx", book_blocks)):
        digest = hashlib.sha256(table_text(blocks).encode("ascii")).hexdigest()
        entries.append({"name": name, "sha256": digest})
    entries.sort(key=lambda entry: entry["name"])
    return dump_json({"reports": entries})


def write_reports(out_dir, texts, sqlite_blocks, book_blocks):
    os.makedirs(out_dir, exist_ok=True)
    texts = dict(texts)
    texts["manifest.json"] = manifest_json(texts, sqlite_blocks, book_blocks)
    for name in sorted(texts):
        with open(os.path.join(out_dir, name), "w", encoding="ascii",
                  newline="") as handle:
            handle.write(texts[name])
    write_sqlite(os.path.join(out_dir, "sweep.sqlite"), sqlite_blocks[1][2],
                 sqlite_blocks[0][2])
    with open(os.path.join(out_dir, "sweep_book.xlsx"), "wb") as handle:
        handle.write(workbook_bytes(book_blocks))


def load_transactions(data_dir, tables, code_map, period):
    aliases = {}
    for row in tables["env_alias"]:
        aliases.setdefault(row["alias"], []).append(
            (date.fromisoformat(row["since"]), row["env_code"]))
    rows = load_tx_a(os.path.join(data_dir, "tx_a.csv"), code_map, period)
    rows += load_tx_b(os.path.join(data_dir, "tx_b.tsv"), code_map, period, aliases)
    rows += load_tx_c(os.path.join(data_dir, "tx_c.bin"), code_map, period,
                      txc_epoch(os.path.join(data_dir, "fmt_txc.md")))
    return rows


def process(data_dir, out_dir):
    conf = load_ini(os.path.join(data_dir, "office.ini"))
    crosswalk = json.loads(read_text(os.path.join(data_dir, "xw_columns.json")))
    tables = load_db(os.path.join(data_dir, "hh_core.sqlite"))
    envelopes = load_envelopes(data_dir, crosswalk, tables)
    name_codes(envelopes,
               load_fund_codes(os.path.join(data_dir, "fund_codes.pdf")),
               load_cat_codes(os.path.join(data_dir, "cat_codes.docx")))
    params = load_parameters(os.path.join(data_dir, "sweep_tab.xlsx"),
                             conf["sweep"]["parameter_sheet"],
                             read_overrides(conf))
    period = (date.fromisoformat(conf["period"]["first_day"]),
              date.fromisoformat(conf["period"]["last_day"]))
    code_map = {code.upper(): code for code in envelopes}
    rows = load_transactions(data_dir, tables, code_map, period)
    corrections = load_corrections(os.path.join(data_dir, "adj_log.psv"))
    counts = apply_corrections(rows, corrections,
                               int(conf["corrections"]["cutoff_seq"]))
    fees = read_delimited(os.path.join(data_dir, "stmt_fees.csv"), ",")
    close_ledger(envelopes, rows, fees, solve_rates(fees, envelopes))
    results = run_sweeps(envelopes, params)
    prior = json.loads(read_text(os.path.join(data_dir, "prior_sweep.json")))
    texts, (sqlite_blocks, book_blocks) = build_reports(
        conf, envelopes, rows, results, counts, prior)
    write_reports(out_dir, texts, sqlite_blocks, book_blocks)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: transform.py DATA_DIR OUT_DIR\n")
        return 2
    try:
        process(argv[1], argv[2])
    except InputRuleError as err:
        sys.stderr.write("extract not processed: %s\n" % err)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
