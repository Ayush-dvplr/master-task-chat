#!/usr/bin/env python3
"""Assessment program for the Vellmouth Consolidated Municipal Utility Tariff Code.

Reads the provisions of tariff_code.md in the batch directory, resolves the values in
force, then computes the nine assessment statements from the registers.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

Y0, Y1, OPEN = date(2026, 1, 1), date(2026, 12, 31), date(2099, 12, 31)
MONTH_NO = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                            "September", "October", "November", "December"])}
WORD_NO = {"nil": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
           "nine": 9, "ten": 10, "twelve": 12, "fourteen": 14}
TEMPORAL = ("rate", "ww", "svc", "twv", "twl", "interest")
CAP_BASIS = {"Volumetric Charges": "volumetric", "Water Supply Charges": "water", "Service Charges": "service",
             "Supply Total": "supply", "Gross Charge": "gross"}
REGIONS = ("North", "South", "West", "East")
SIZES = (20, 25, 32, 40, 50, 80, 100, 150)


def sec_key(sec: str) -> tuple[int, int]:
    a, b = sec.split("-")
    return int(a), int(b)


def loc_key(loc: str) -> tuple[int, int, str]:
    sec, _, rest = loc.partition("(")
    a, b = sec_key(sec)
    return a, b, rest


def long_to_date(text: str) -> date:
    d, mon, y = text.split()
    return date(int(y), MONTH_NO[mon], int(d))


def typed(key: str, text: str) -> Any:
    kind = key.split(":")[0]
    if kind in ("rate", "ww", "storm", "svc", "twv", "twl"):
        whole, frac = text[1:].split(".")
        return int(whole) * 10000 + int(frac)
    if kind == "thr":
        return int(text.split()[0].replace(",", ""))
    if kind in ("sur", "dsupp", "catch", "interest"):
        whole, frac = text.split()[0].split(".")
        return int(whole) * 10000 + int((frac + "0000")[:4])
    if kind in ("discharge", "gcap", "rb_rate"):
        return int(text.split()[0])
    if kind == "min":
        whole, frac = text[1:].replace(",", "").split(".")
        return int(whole) * 100 + int(frac)
    if kind == "rb_prio":
        return int(text.split()[1])
    if kind in ("rb_carry", "grace"):
        return WORD_NO[text.split()[0]]
    if kind in ("cexempt", "drought"):
        return text == "true"
    if kind in ("band", "region"):
        return text
    if kind in ("rb_cards", "rb_excl"):
        return [x for x in text.split(",") if x]
    if kind == "rb_cap":
        if text == "none":
            return None
        if text.startswith("$"):
            whole, frac = text[1:].replace(",", "").split(".")
            return ["fixed", int(whole) * 100 + int(frac)]
        pct, _, basis = text.partition(" per cent of ")
        return [CAP_BASIS[basis], int(pct)]
    raise ValueError(key)


def resolve(prov: dict[str, Any]) -> dict[str, Any]:
    orig = [dict(o, auth=o["loc"].split("(")[0]) for o in prov["orig"]]
    amend = [dict(a, auth=a["section"]) for a in prov["amend"]]
    corr = sorted(prov["corr"], key=lambda c: loc_key(c["loc"]))
    overrides = prov["overrides"]
    created = prov["created"]

    # Division 15-2: each correction is read into the text it corrects.
    for c in corr:
        hit = False
        for o in orig:
            if o["loc"] == c["target"] and o["text"] == c["old"]:
                o["text"], o["auth"], hit = c["new"], c["section"], True
        for a in amend:
            if a["loc"] == c["target"]:
                if a["text"] == c["old"]:
                    a["text"], a["auth"], hit = c["new"], c["section"], True
                elif a.get("start") == c["old"]:
                    a["start"], hit = c["new"], True
                elif a.get("end") == c["old"]:
                    a["end"], hit = c["new"], True
            elif c["target"] == f"{a['section']}(1)" and a["made"] == c["old"]:
                a["made"], hit = c["new"], True
        if not hit:
            raise ValueError(f"correction {c['loc']} matches no text")

    scalar: dict[str, list] = {}
    series: dict[str, list[list]] = {}
    for o in orig:
        kind = o["key"].split(":")[0]
        v = typed(o["key"], o["text"])
        if kind in TEMPORAL:
            series[o["key"]] = [[Y0, OPEN if kind == "interest" else Y1, v, o["auth"]]]
        else:
            scalar[o["key"]] = [v, o["auth"]]
    for ov in overrides:
        kind = ov["key"].split(":")[0]
        v = typed(ov["key"], ov["text"])
        if kind in TEMPORAL:
            seg = series[ov["key"]]
            series[ov["key"]] = [[seg[0][0], seg[-1][1], v, ov["section"]]]
        elif ov["op"] == "add":
            scalar[ov["key"]] = [scalar[ov["key"]][0] + v, ov["section"]]
        else:
            scalar[ov["key"]] = [v, ov["section"]]

    ordered = sorted(amend, key=lambda a: (long_to_date(a["made"]), loc_key(a["loc"])))
    for a in ordered:
        kind = a["key"].split(":")[0]
        v = typed(a["key"], a["text"])
        if kind in TEMPORAL:
            lo = long_to_date(a["start"]) if a.get("start") else Y0
            segs = series[a["key"]]
            hi = long_to_date(a["end"]) if a.get("end") else segs[-1][1]
            series[a["key"]] = put(segs, max(lo, segs[0][0]), hi, v, a["auth"])
        else:
            scalar[a["key"]] = [v, a["auth"]]
    rulings = {r["kind"]: r["section"] for r in prov["rulings"]}
    return assemble(prov["struct"], created, scalar, series, rulings)


def put(segs: list[list], lo: date, hi: date, v: Any, auth: str) -> list[list]:
    out = []
    for a, b, val, au in segs:
        if b < lo or a > hi:
            out.append([a, b, val, au])
            continue
        if a < lo:
            out.append([a, lo - timedelta(days=1), val, au])
        out.append([max(a, lo), min(b, hi), v, auth])
        if b > hi:
            out.append([hi + timedelta(days=1), b, val, au])
    return out


def periods(segs: list[list], name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for a, b, v, au in segs:
        if out and out[-1][name] == v and out[-1]["authority"] == au:
            out[-1]["to"] = None if b == OPEN else b.isoformat()
        else:
            out.append({"from": a.isoformat(), "to": None if b == OPEN else b.isoformat(), name: v, "authority": au})
    return out


def due_dates(holidays: list[str]) -> dict[str, str]:
    hol = set(holidays)
    out = {}
    for q, day in (("Q1", date(2026, 5, 15)), ("Q2", date(2026, 8, 15)), ("Q3", date(2026, 11, 15)), ("Q4", date(2027, 2, 15))):
        while day.weekday() >= 5 or day.isoformat() in hol:
            day += timedelta(days=1)
        out[q] = day.isoformat()
    return out


def assemble(struct, created, scalar, series, rulings) -> dict[str, Any]:
    va = lambda pair: {"value": pair[0], "authority": pair[1]}  # noqa: E731
    strip = lambda ps: [{k: p[k] for k in p if k != "authority"} for p in ps]  # noqa: E731
    rules: dict[str, Any] = {"classes": {}, "zones": {}, "holidays": list(struct["holidays"])}
    audit: dict[str, Any] = {"tariff_classes": {}, "zones": {}}
    for code in sorted(struct["classes"]):
        rates = {f"block_{b}": periods(series[f"rate:{code}:{b}"], "rate") for b in (1, 2, 3)}
        band, dis, ex = scalar[f"band:{code}"], scalar[f"discharge:{code}"], scalar[f"cexempt:{code}"]
        rules["classes"][code] = {"sector": struct["classes"][code]["sector"], "band": band[0], "discharge_percent": dis[0],
                                  "catchment_exempt": ex[0], "rates": {k: strip(v) for k, v in rates.items()}}
        audit["tariff_classes"][code] = {"band": va(band), "discharge_factor_percent": va(dis), "catchment_exempt": va(ex),
                                         "block_rates": rates}
    for code in sorted(struct["zones"]):
        ww = periods(series[f"ww:{code}"], "rate")
        reg, dr, st = scalar[f"region:{code}"], scalar[f"drought:{code}"], scalar[f"storm:{code}"]
        rules["zones"][code] = {"region": reg[0], "drought": dr[0], "storm": st[0], "ww": strip(ww)}
        audit["zones"][code] = {"region": va(reg), "drought_zone": va(dr), "stormwater_rate": va(st), "wastewater_rate_periods": ww}
    rules["thresholds"] = {b: [scalar[f"thr:{b}:1"][0], scalar[f"thr:{b}:2"][0]] for b in "ABC"}
    audit["band_allowances_litres_per_day"] = {b: {"block_1": va(scalar[f"thr:{b}:1"]), "block_2_upper": va(scalar[f"thr:{b}:2"])} for b in "ABC"}
    svc = {str(s): periods(series[f"svc:{s}"], "rate") for s in SIZES}
    rules["service"] = {k: strip(v) for k, v in svc.items()}
    audit["daily_service_charges"] = svc
    rules["surcharge"] = {r: scalar[f"sur:{r}"][0] for r in REGIONS}
    audit["regional_surcharge_ppm"] = {r: va(scalar[f"sur:{r}"]) for r in REGIONS}
    rules["dsupp"] = scalar["dsupp"][0]
    audit["drought_supplement_ppm"] = va(scalar["dsupp"])
    rules["catch"] = scalar["catch"][0]
    audit["catchment_levy_ppm"] = va(scalar["catch"])
    tw = {"volume": periods(series["twv"], "rate"), "load": periods(series["twl"], "rate")}
    rules["trade_waste"] = {k: strip(v) for k, v in tw.items()}
    audit["trade_waste_rates"] = tw
    specs = dict(struct["rebates"])
    for c in created:
        specs[c["code"]] = {"section": c["section"], "title": c["title"], "basis": c["basis"], "elig": c["elig"]}
    rebates, arows = [], []
    for code, spec in specs.items():
        prio, rate, cap, carry = (scalar[f"rb_prio:{code}"], scalar[f"rb_rate:{code}"], scalar[f"rb_cap:{code}"], scalar[f"rb_carry:{code}"])
        cards = scalar.get(f"rb_cards:{code}")
        excl = scalar[f"rb_excl:{code}"]
        elig = dict(spec["elig"])
        if cards is not None:
            elig["cards"] = cards[0]
        if excl[0]:
            elig["excluded"] = excl[0]
        rebates.append({"code": code, "section": spec["section"], "basis": spec["basis"], "priority": prio[0], "rate_percent": rate[0],
                        "cap": cap[0], "carry_years": carry[0], "elig": elig})
        row = {"rebate_code": code, "section": spec["section"], "priority": va(prio), "rate_percent": va(rate),
               "cap": {"basis": cap[0][0] if cap[0] else None, "amount": cap[0][1] if cap[0] else None, "authority": cap[1]},
               "carry_years": va(carry), "excluded_forms": va(excl)}
        if cards is not None:
            row["concession_cards"] = va(cards)
        arows.append(row)
    key = lambda r: (r["priority"] if "code" in r else r["priority"]["value"], sec_key(r["section"]))  # noqa: E731
    rules["rebates"] = sorted(rebates, key=key)
    audit["rebates_in_application_order"] = sorted(arows, key=key)
    rules["gcap"] = scalar["gcap"][0]
    audit["global_rebate_cap_percent"] = va(scalar["gcap"])
    rules["minimum"] = {c: scalar[f"min:{c}"][0] for c in ("residential", "commercial", "public")}
    audit["minimum_charge_cents"] = {c: va(scalar[f"min:{c}"]) for c in ("residential", "commercial", "public")}
    rules["grace"] = scalar["grace"][0]
    audit["interest_grace_days"] = va(scalar["grace"])
    ip = periods(series["interest"], "rate_ppm")
    rules["interest"] = strip(ip)
    audit["interest_rate_periods"] = ip
    audit["instalment_due_dates"] = due_dates(struct["holidays"])
    rules["rulings"] = dict(rulings)
    audit["binding_rulings_applied"] = sorted(rulings.values(), key=sec_key)
    rules["audit"] = audit
    return rules


LOC = r"(\d+-\d+(?:\([0-9a-z]+\))+)"
DATE = r"(\d{1,2} [A-Z][a-z]+ \d{4})"
VAL = r"(\$[\d,]+\.\d{2,4}|\d+\.\d{4} per cent)"
CARD_ID = {"a pensioner concession card": "pensioner", "a health care card": "health", "a veteran concession card": "veteran"}
QFIRST = {"first": ("1 January 2026", "31 March 2026"), "second": ("1 April 2026", "30 June 2026"),
          "third": ("1 July 2026", "30 September 2026"), "fourth": ("1 October 2026", "31 December 2026")}
ELIG = {
    "it is a residential account or a commercial account": {"classes": ["residential", "commercial"]},
    "at least one of its properties is a drought property": {"drought_property": True},
    "it is a community organisation": {"community": True},
    "it is a residential account": {"classes": ["residential"]},
    "it is a commercial account": {"classes": ["commercial"]},
    "it has at least one Large Meter": {"large_meter": True},
    "it is an account": {},
}
BASIS = {"of the account's Service Charges": "service_pct", "of the account's Water Supply Charges": "water_pct",
         "of the expenditure claimed": "claim", "of the daily service charges of the account's Large Meters": "large_meter"}


def split_sections(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    part, div, cur = 0, "", None
    for line in text.splitlines():
        mp = re.match(r"^## Part (\d+)\. ", line)
        if mp:
            part, div, cur = int(mp.group(1)), "", None
            continue
        md = re.match(r"^#### Division ([\d-]+)\. ", line)
        if md:
            div, cur = md.group(1), None
            continue
        ms = re.match(r"^### Section (\d+-\d+)\. (.*)$", line)
        if ms:
            cur = {"num": ms.group(1), "title": ms.group(2), "part": part, "div": div, "paras": []}
            out.append(cur)
            continue
        if cur is not None and line.strip():
            cur["paras"].append(line.strip())
    return out


def label(p: str) -> str:
    m = re.match(r"^\(([0-9a-z]+)\) ", p)
    return m.group(1) if m else ""


def read_provisions(path: Path) -> dict[str, Any]:
    secs = split_sections(path.read_text(encoding="utf-8"))
    orig: list[dict[str, str]] = []
    struct: dict[str, Any] = {"classes": {}, "zones": {}, "rebates": {}, "holidays": []}
    created: list[dict[str, Any]] = []
    overrides: list[dict[str, str]] = []
    amend: list[dict[str, Any]] = []
    corr: list[dict[str, str]] = []
    rulings: list[dict[str, str]] = []

    def add(loc: str, key: str, text: str) -> None:
        orig.append({"loc": loc, "key": key, "text": text})

    for s in secs:
        num, title, part, paras = s["num"], s["title"], s["part"], [p for p in s["paras"] if not p.startswith("Note")]
        body = "\n".join(paras)
        if part == 16:
            if paras and paras[0] == "Designation: Binding Ruling.":
                ref = re.search(r"This Ruling concerns sections? ([\d-]+)", body).group(1)
                kind = {"3-002": "billing_zone", "11-010": "minimum_proration", "12-020": "payment_day", "10-003": "current_first"}[ref]
                rulings.append({"section": num, "kind": kind})
            continue
        if part == 15 and s["div"] == "15-9":
            continue
        mc = re.match(r"^Class (TC-\d+): ", title)
        if mc and part == 2:
            code = mc.group(1)
            struct["classes"][code] = {"section": num, "sector": re.search(r"The class is an? (\w+) class", body).group(1)}
            for p in paras:
                mr = re.match(r"^\((i{1,3})\) for block (\d) consumption, at (\$\d+\.\d{4}) per kilolitre", p)
                if mr:
                    add(f"{num}(d)({mr.group(1)})", f"rate:{code}:{mr.group(2)}", mr.group(3))
                elif label(p) == "e":
                    add(f"{num}(e)", f"cexempt:{code}", "false" if "are not exempt" in p else "true")
                elif label(p) == "f":
                    add(f"{num}(f)", f"band:{code}", re.search(r"Band ([ABC])", p).group(1))
                elif label(p) == "g":
                    add(f"{num}(g)", f"discharge:{code}", re.search(r"(\d+ per cent)", p).group(1))
            continue
        mz = re.match(r"^Zone (Z-\d+): ", title)
        if mz and part == 3:
            code = mz.group(1)
            struct["zones"][code] = {"section": num}
            for p in paras:
                lab = label(p)
                if lab == "b":
                    add(f"{num}(b)", f"region:{code}", re.search(r"part of the (\w+) region", p).group(1))
                elif lab == "c":
                    add(f"{num}(c)", f"drought:{code}", "false" if "is not designated" in p else "true")
                elif lab in ("d", "e"):
                    add(f"{num}({lab})", f"{'ww' if lab == 'd' else 'storm'}:{code}", re.search(r"(\$\d+\.\d{4})", p).group(1))
            continue
        if "identified by rebate code" in body:
            read_rebate(num, paras, add, struct, created, part)
            continue
        if num == "1-090":
            struct["holidays"] = [iso(x) for x in re.findall(DATE, paras[0])]
        elif num == "4-020":
            for p in paras:
                mt = re.match(r"^\(([abc])\) for Band ([ABC]), block 1 is the first ([\d,]+ litres) per day and block 2 is the consumption above that up to ([\d,]+ litres) per day", p)
                if mt:
                    add(f"4-020(2)({mt.group(1)})", f"thr:{mt.group(2)}:1", mt.group(3))
                    add(f"4-020(2)({mt.group(1)})", f"thr:{mt.group(2)}:2", mt.group(4))
        elif num == "5-210":
            add("5-210(2)", "catch", re.search(r"(\d+\.\d{4} per cent)", body).group(1))
        elif num == "5-110":
            add("5-110(2)(a)", "twv", re.search(r"volume charge of (\$\d+\.\d{4})", body).group(1))
            add("5-110(2)(b)", "twl", re.search(r"load charge of (\$\d+\.\d{4})", body).group(1))
        elif num == "6-020":
            for p in paras:
                mv = re.match(r"^\(([a-h])\) for a meter of (\d+) mm, (\$\d+\.\d{4})", p)
                if mv:
                    add(f"6-020(2)({mv.group(1)})", f"svc:{mv.group(2)}", mv.group(3))
        elif num == "7-010":
            for p in paras:
                mv = re.match(r"^\(([a-d])\) for the (\w+) region, (\d+\.\d{4} per cent)", p)
                if mv:
                    add(f"7-010(1)({mv.group(1)})", f"sur:{mv.group(2)}", mv.group(3))
        elif num == "7-020":
            add("7-020(1)", "dsupp", re.search(r"(\d+\.\d{4} per cent)", body).group(1))
        elif num == "9-002":
            add("9-002(1)", "gcap", re.search(r"(\d+ per cent)", body).group(1))
        elif num == "11-010":
            for p in paras:
                mv = re.match(r"^\(([abc])\) for an? (\w+) account, (\$[\d,]+\.\d{2})", p)
                if mv:
                    add(f"11-010(1)({mv.group(1)})", f"min:{mv.group(2)}", mv.group(3))
        elif num == "12-030":
            add("12-030(2)", "grace", re.search(r"is (\w+ days) after", body).group(1))
        elif num == "12-040":
            add("12-040(1)", "interest", re.search(r"(\d+\.\d{4} per cent) per annum", body).group(1))
        if part <= 14:
            read_overrides(num, paras, overrides)
            continue
        if part == 15 and s["div"] == "15-1":
            made = re.match(r"^\(1\) This section was made on " + DATE + r"\.$", paras[0]).group(1)
            for p in paras[1:]:
                item = read_item(p)
                if item:
                    item.update({"loc": f"{num}({label(p)})", "section": num, "made": made})
                    amend.append(item)
        elif part == 15 and s["div"] == "15-2":
            for p in paras:
                mc2 = re.match(r"^\((\d+)\) In section " + LOC + r", for '([^']+)' read '([^']+)'\.$", p)
                if mc2:
                    corr.append({"loc": f"{num}({mc2.group(1)})", "section": num, "target": mc2.group(2), "old": mc2.group(3), "new": mc2.group(4)})

    # attach keys to amendments by the location they name; drop those that name no tariff value
    by_loc: dict[str, list[dict[str, str]]] = {}
    for o in orig:
        by_loc.setdefault(o["loc"], []).append(o)
    kept = []
    for a in amend:
        hits = by_loc.get(a.pop("target"), [])
        if not hits:
            continue
        old = a.pop("old", None)
        if len(hits) > 1:
            hits = [h for h in hits if h["text"] == old]
        o = hits[0]
        kind = o["key"].split(":")[0]
        op = a.pop("op")
        if op == "value":
            text = a.pop("value")
        elif op == "quote":
            q_old, q_new = norm_quote(old), norm_quote(a.pop("value"))
            text = o["text"].replace(q_old, q_new) if q_old in o["text"] else q_new
        elif op == "repeal":
            text = {"cexempt": "false", "rb_excl": "", "rb_cap": "none"}[kind]
        elif op == "omit_not":
            text = "true"
        elif op == "insert_not":
            text = "false"
        else:  # insert a card
            text = o["text"] + "," + CARD_ID[a.pop("value")]
        a.setdefault("start", None)
        a.setdefault("end", None)
        a.update({"key": o["key"], "text": text})
        kept.append(a)
    corr = [c for c in corr if c["target"] in by_loc or c["target"].startswith("15-")]
    return {"orig": orig, "struct": struct, "created": created, "overrides": overrides, "amend": kept, "corr": corr, "rulings": rulings}


def norm_quote(q: str) -> str:
    q = q[5:] if q.startswith("Band ") else q
    return q[:-len(" tariff years")] if q.endswith(" tariff years") else q


def iso(text: str) -> str:
    d, mon, y = text.split()
    return f"{int(y):04d}-{MONTH_NO[mon]:02d}-{int(d):02d}"


def read_item(p: str) -> dict[str, Any] | None:
    body = re.sub(r"^\(\d+\) ", "", p)
    m = re.match(r"^With effect from " + DATE + r", in section " + LOC + r", for '([^']+)' substitute '([^']+)'\.$", body)
    if m:
        return {"target": m.group(2), "old": m.group(3), "op": "value", "value": m.group(4), "start": m.group(1)}
    m = re.match(r"^In section " + LOC + r", for '([^']+)' substitute '([^']+)'\.$", body)
    if m:
        return {"target": m.group(1), "old": m.group(2), "op": "quote", "value": m.group(3)}
    m = re.match(r"^.* under section " + LOC + r"(?: for a meter of \d+ mm)? is " + VAL + r"(?: per kilolitre| per kilogram| per annum)? for the period beginning on " + DATE + r"\.$", body)
    if m:
        return {"target": m.group(1), "op": "value", "value": m.group(2), "start": m.group(3)}
    m = re.match(r"^For the period from " + DATE + " to " + DATE + r", .* under section " + LOC + r"(?: for a meter of \d+ mm)? is " + VAL, body)
    if m:
        return {"target": m.group(3), "op": "value", "value": m.group(4), "start": m.group(1), "end": m.group(2)}
    m = re.match(r"^For the (\w+) and later quarters of the tariff year, .* under section " + LOC + r"(?: for a meter of \d+ mm)? is " + VAL, body)
    if m:
        return {"target": m.group(2), "op": "value", "value": m.group(3), "start": QFIRST[m.group(1)][0]}
    m = re.match(r"^For the (\w+) quarter of the tariff year only, .* under section " + LOC + r"(?: for a meter of \d+ mm)? is " + VAL, body)
    if m:
        lo, hi = QFIRST[m.group(1)]
        return {"target": m.group(2), "op": "value", "value": m.group(3), "start": lo, "end": hi}
    m = re.match(r"^(?:Paragraph|Subsection) \((\w+)\) of section (\d+-\d+) is repealed\.$", body)
    if m:
        return {"target": f"{m.group(2)}({m.group(1)})", "op": "repeal"}
    m = re.match(r"^In section " + LOC + r", omit 'not '\.$", body)
    if m:
        return {"target": m.group(1), "op": "omit_not"}
    m = re.match(r"^In section " + LOC + r", after '(?:is|are)' insert ' not'\.$", body)
    if m:
        return {"target": m.group(1), "op": "insert_not"}
    m = re.match(r"^In section " + LOC + r", after '[^']+' insert ' or (a [a-z ]+ card)'\.$", body)
    if m:
        return {"target": m.group(1), "op": "card", "value": m.group(2)}
    return None


def read_overrides(num: str, paras: list[str], out: list[dict[str, str]]) -> None:
    for p in paras:
        m = re.search(r"the percentage stated in section 5-210\(2\) is taken to be (\d+\.\d{4} per cent)", p)
        if m:
            out.append({"section": num, "key": "catch", "op": "set", "text": m.group(1)})
        m = re.search(r"Notwithstanding section 7-010, for the tariff year 2026 each regional rate stated in that section is increased by (\d+\.\d{4}) percentage points", p)
        if m:
            for r in ("North", "South", "West", "East"):
                out.append({"section": num, "key": f"sur:{r}", "op": "add", "text": f"{m.group(1)} per cent"})
        m = re.search(r"the daily service charge stated in section 6-020\(2\)\([a-h]\) for a meter of (\d+) mm has effect for the tariff year 2026 as if it were (\$\d+\.\d{4})", p)
        if m:
            out.append({"section": num, "key": f"svc:{m.group(1)}", "op": "set", "text": m.group(2)})
        m = re.search(r"Notwithstanding section 4-020, for the tariff year 2026 the block (\d) allowance for Band ([ABC]) is ([\d,]+) litres per day", p)
        if m:
            out.append({"section": num, "key": f"thr:{m.group(2)}:{m.group(1)}", "op": "set", "text": f"{m.group(3)} litres"})


def read_rebate(num: str, paras: list[str], add, struct: dict[str, Any], created: list, part: int) -> None:
    text = {label(p): p for p in paras}
    m = re.search(r"establishes the (.+), identified by rebate code (RB-\d+)", text["1"])
    title, code = m.group(1), m.group(2)
    add(f"{num}(2)", f"rb_prio:{code}", re.search(r"(priority \d+)", text["2"]).group(1))
    el = re.search(r"An account is eligible if (.*)\.$", text["3"]).group(1)
    if " whose holder holds " in el:
        head, cards = el.split(" whose holder holds ")
        elig = dict(ELIG[head])
        add(f"{num}(3)", f"rb_cards:{code}", ",".join(CARD_ID[c] for c in cards.split(" or ")))
    else:
        elig = dict(ELIG[el])
    am = re.search(r"The amount of the rebate is (\d+ per cent) (.*)\.$", text["4"])
    add(f"{num}(4)", f"rb_rate:{code}", am.group(1))
    basis = "leak" if am.group(2).startswith("of the leak value") else BASIS[am.group(2)]
    lim = re.search(r"must not exceed (.*)\.$", text["5"]).group(1)
    if lim.startswith("$"):
        cap = lim
    else:
        pct, _, what = lim.partition(" of the account's ")
        cap = f"{pct} of {what}"
    add(f"{num}(5)", f"rb_cap:{code}", cap)
    cm = re.search(r"may be carried forward for (\w+) tariff years", text["6"])
    add(f"{num}(6)", f"rb_carry:{code}", cm.group(1) if cm else "nil")
    em = re.search(r"holder form of the account is (.*)\.$", text["7"])
    add(f"{num}(7)", f"rb_excl:{code}", ",".join(em.group(1).split(" or ")) if em else "")
    spec = {"section": num, "title": title, "basis": basis, "elig": elig}
    if part == 15:
        created.append(dict(spec, code=code))
    else:
        struct["rebates"][code] = spec


QUARTERS = ("Q1", "Q2", "Q3", "Q4")
QSTART = {"Q1": date(2026, 1, 1), "Q2": date(2026, 4, 1), "Q3": date(2026, 7, 1), "Q4": date(2026, 10, 1)}
SEGMENTS = ("commercial", "public")
TOTAL_KEYS = ("water_supply_cents", "wastewater_cents", "service_charges_cents", "surcharge_cents", "catchment_levy_cents",
              "trade_waste_cents", "gross_charge_cents", "rebates_total_cents", "minimum_topup_cents", "net_charge_cents",
              "payments_cents", "interest_cents", "balance_cents")
OUTPUT_NAMES = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
                "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json")
REGISTERS = ("accounts.csv", "properties.csv", "meters.csv", "meter_reads.csv", "trade_waste.csv", "concession_claims.csv",
             "leak_claims.csv", "carryforwards.csv", "payments.csv")


def rnd(value: Fraction, mode: str) -> int:
    q = Decimal(value.numerator) / Decimal(value.denominator)
    return int(q.quantize(Decimal(1), rounding=ROUND_HALF_EVEN if mode == "even" else ROUND_HALF_UP))


def rhe(num: Any, den: int = 1) -> int:
    return rnd(Fraction(num) / den, "even")


def rhu(num: Any, den: int = 1) -> int:
    return rnd(Fraction(num) / den, "up")


def d(text: str) -> date:
    return date.fromisoformat(text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Series:
    """Prefix sums of a daily rate over the tariff year."""

    def __init__(self, periods: list[dict[str, Any]]) -> None:
        daily = []
        for i in range(365):
            day = Y0 + timedelta(days=i)
            daily.append(rate_on(periods, day))
        self.prefix = [0]
        for v in daily:
            self.prefix.append(self.prefix[-1] + v)

    def total(self, after: date, upto: date) -> int:
        """Sum of the daily rates for the days after `after` up to and including `upto`."""
        lo = max((after - Y0).days + 1, 0)
        hi = (upto - Y0).days + 1
        return self.prefix[hi] - self.prefix[lo] if hi > lo else 0


def rate_on(periods: list[dict[str, Any]], day: date) -> int:
    for p in periods:
        hi = d(p["to"]) if p["to"] else OPEN
        if d(p["from"]) <= day <= hi:
            return p.get("rate", p.get("rate_ppm"))
    raise ValueError(f"no rate in force on {day}")


def business_next(day: date, holidays: set[date]) -> date:
    while day.weekday() >= 5 or day in holidays:
        day += timedelta(days=1)
    return day


def assess(data_dir: Path, rules: dict[str, Any]) -> dict[str, Any]:
    batch = json.loads((data_dir / "batch.json").read_text(encoding="utf-8"))
    asof = d(batch["assessment_date"])
    reg = {name: read_csv(data_dir / name) for name in REGISTERS}
    classes, zones, rulings = rules["classes"], rules["zones"], rules["rulings"]
    holidays = {d(h) for h in rules["holidays"]}
    dues = {q: d(v) for q, v in rules["audit"]["instalment_due_dates"].items()}
    cache: dict[tuple, Series] = {}

    def series(key: tuple, periods: list[dict[str, Any]]) -> Series:
        if key not in cache:
            cache[key] = Series(periods)
        return cache[key]

    issues: list[str] = []
    props_of: dict[str, list] = {}
    for p in reg["properties.csv"]:
        props_of.setdefault(p["account_id"], []).append(p)
    meters_of: dict[str, list] = {}
    for mt in reg["meters.csv"]:
        meters_of.setdefault(mt["property_id"], []).append(mt)
    reads_of: dict[str, list] = {}
    for r in reg["meter_reads.csv"]:
        reads_of.setdefault(r["meter_id"], []).append(r)
    trade_of: dict[str, list] = {}
    for t in reg["trade_waste.csv"]:
        trade_of.setdefault(t["property_id"], []).append(t)
    leaks_of: dict[str, list] = {}
    for lk in reg["leak_claims.csv"]:
        leaks_of.setdefault(lk["property_id"], []).append(lk)
    by_acct: dict[str, dict[str, list]] = {a["account_id"]: {"clm": [], "cf": [], "pmt": []} for a in reg["accounts.csv"]}
    for name, k in (("concession_claims.csv", "clm"), ("carryforwards.csv", "cf"), ("payments.csv", "pmt")):
        for row in reg[name]:
            by_acct[row["account_id"]][k].append(row)
    rebates = rules["rebates"]
    rebate_by = {r["code"]: r for r in rebates}

    results = []
    for acct in sorted(reg["accounts.csv"], key=lambda a: a["account_id"]):
        aid, aclass, form, card = acct["account_id"], acct["account_class"], acct["holder_form"], acct["concession_card"]
        a0 = max(Y0, d(acct["opened_on"]))
        a1 = min(Y1, d(acct["closed_on"])) if acct["closed_on"] else Y1
        active = max(0, (a1 - a0).days + 1)
        intervals, meter_rows, prop_rows = [], [], []
        consumption: dict[str, int] = {}
        water_total = ww_total = svc_total = storm_total = trade_total = catch_base = large_svc = 0
        live_props = []
        for p in sorted(props_of.get(aid, []), key=lambda r: r["property_id"]):
            pid, zone, tcls = p["property_id"], p["zone"], p["tariff_class"]
            cl, zn = classes[tcls], zones[zone]
            p0 = max(a0, d(p["connected_on"]))
            p1 = min(a1, d(p["disconnected_on"])) if p["disconnected_on"] else a1
            pdays = max(0, (p1 - p0).days + 1)
            if pdays:
                live_props.append(p)
            t1, t2 = rules["thresholds"][cl["band"]]
            s_rates = [series(("rate", tcls, b), cl["rates"][f"block_{b}"]) for b in (1, 2, 3)]
            s_ww = series(("ww", zone), zn["ww"])
            prop_water = 0
            for mt in sorted(meters_of.get(pid, []), key=lambda r: r["meter_id"]):
                mid, size = mt["meter_id"], int(mt["size_mm"])
                m0 = max(p0, d(mt["installed_on"]))
                m1 = min(p1, d(mt["removed_on"])) if mt["removed_on"] else p1
                mdays = max(0, (m1 - m0).days + 1)
                svc = rhe(series(("svc", size), rules["service"][str(size)]).total(m0 - timedelta(days=1), m1), 100) if mdays else 0
                svc_total += svc
                if size >= 80 and mdays:
                    large_svc += svc
                meter_rows.append({"meter_id": mid, "property_id": pid, "size_mm": size, "service_days": mdays, "service_cents": svc})
                valid = []
                for r in sorted(reads_of.get(mid, []), key=lambda r: r["read_on"]):
                    day = d(r["read_on"])
                    if mdays and m0 - timedelta(days=1) <= day <= m1:
                        valid.append((day, int(r["reading_litres"])))
                    else:
                        issues.append(f"{mid}: reading of {r['read_on']} outside the meter's supply window disregarded")
                for (pd, pr), (cd, cr) in zip(valid, valid[1:]):
                    days = (cd - pd).days
                    used = cr - pr
                    if used < 0:
                        issues.append(f"{mid}: reading of {cd.isoformat()} lower than the preceding reading; consumption nil")
                        used = 0
                    q = Fraction(used, days)
                    q1 = min(q, t1)
                    q2 = min(max(q - t1, 0), t2 - t1)
                    q3 = max(q - t2, 0)
                    s1, s2, s3 = (s.total(pd, cd) for s in s_rates)
                    water = rhe(q1 * s1 + q2 * s2 + q3 * s3, 100000)
                    ww = rhu(q * cl["discharge_percent"] / 100 * s_ww.total(pd, cd), 100000)
                    intervals.append({"meter_id": mid, "property_id": pid, "from": (pd + timedelta(days=1)).isoformat(),
                                      "to": cd.isoformat(), "days": days, "litres": used, "water_cents": water, "wastewater_cents": ww})
                    prop_water += water
                    water_total += water
                    ww_total += ww
                    consumption[zone] = consumption.get(zone, 0) + used
            if not cl["catchment_exempt"]:
                catch_base += prop_water
            storm = rhu(int(p["land_area_m2"]) * zn["storm"] * pdays, 365 * 100) if pdays else 0
            storm_total += storm
            trade = 0
            for t in sorted(trade_of.get(pid, []), key=lambda r: r["return_id"]):
                if aclass != "commercial":
                    issues.append(f"{t['return_id']}: trade waste return for a property of a non-commercial account disregarded")
                    continue
                qs = QSTART[t["quarter"]]
                vol = rate_on(rules["trade_waste"]["volume"], qs)
                load = rate_on(rules["trade_waste"]["load"], qs)
                lit, mg = int(t["discharge_litres"]), int(t["bod_mg_per_l"])
                trade += rhe(Fraction(lit * vol, 100000) + Fraction(lit * mg * load, 10**6 * 100))
            trade_total += trade
            prop_rows.append({"property_id": pid, "zone": zone, "tariff_class": tcls, "supply_days": pdays,
                              "stormwater_cents": storm, "trade_waste_cents": trade})

        # billing zone (section 3-002 as applied by the Binding Ruling)
        if "billing_zone" in rulings and sum(consumption.values()) > 0:
            top = max(consumption.values())
            bzone = min(z for z, v in consumption.items() if v == top)
        else:
            pick = sorted(live_props or props_of[aid], key=lambda p: (p["connected_on"], p["property_id"]))
            bzone = pick[0]["zone"]
        region, drought = zones[bzone]["region"], zones[bzone]["drought"]

        service = svc_total + storm_total
        volumetric = water_total + ww_total
        base = volumetric + service
        surcharge = rhe(base * (rules["surcharge"][region] + (rules["dsupp"] if drought else 0)), 1_000_000)
        supply = base + surcharge
        catch = rhu(catch_base * rules["catch"], 1_000_000)
        gross = supply + catch + trade_total
        figures = {"volumetric": volumetric, "water": water_total, "service": service, "supply": supply, "gross": gross}

        facts = {"class": aclass, "form": form, "card": card,
                 "drought_property": any(zones[p["zone"]]["drought"] for p in props_of.get(aid, [])),
                 "community": aclass == "public" or form == "association", "large_meter": any(r["size_mm"] >= 80 and r["service_days"] for r in meter_rows)}
        claimed: dict[str, int] = {}
        for c in sorted(by_acct[aid]["clm"], key=lambda r: r["claim_id"]):
            code = c["rebate_code"]
            spec = rebate_by.get(code)
            if spec is None:
                issues.append(f"{aid}: claim {c['claim_id']} under {code} disregarded: no such rebate")
            elif spec["basis"] != "claim":
                issues.append(f"{aid}: claim {c['claim_id']} under {code} disregarded: rebate arises without claim")
            elif not eligible(spec, facts):
                issues.append(f"{aid}: claim {c['claim_id']} under {code} disregarded: account not eligible")
            else:
                claimed[code] = claimed.get(code, 0) + int(c["expenditure_cents"])
        leak_value = 0
        leak_spec = next((r for r in rebates if r["basis"] == "leak"), None)
        for p in sorted(props_of.get(aid, []), key=lambda r: r["property_id"]):
            for lk in sorted(leaks_of.get(p["property_id"], []), key=lambda r: r["leak_claim_id"]):
                rep = d(lk["repaired_on"])
                if not (Y0 <= rep <= Y1):
                    issues.append(f"{aid}: leak claim {lk['leak_claim_id']} disregarded: repair date outside the tariff year")
                elif leak_spec is None or not eligible(leak_spec, facts):
                    issues.append(f"{aid}: leak claim {lk['leak_claim_id']} disregarded: account not eligible")
                else:
                    r3 = rate_on(classes[p["tariff_class"]]["rates"]["block_3"], rep)
                    leak_value += rhe(int(lk["leak_litres"]) * r3 * leak_spec["rate_percent"], 100000 * 100)
        carried: dict[str, list[tuple[int, int]]] = {}
        for c in by_acct[aid]["cf"]:
            code, origin, amount = c["rebate_code"], int(c["origin_year"]), int(c["remaining_cents"])
            spec = rebate_by.get(code)
            if spec is None or spec["carry_years"] == 0:
                issues.append(f"{aid}: carryforward {code}/{origin} disregarded: not permitted")
            elif 2026 - origin > spec["carry_years"]:
                issues.append(f"{aid}: carryforward {code}/{origin} disregarded: expired")
            else:
                carried.setdefault(code, []).append((origin, amount))

        remaining = gross
        groom = rhe(gross * rules["gcap"], 100)
        applied, carry_out = [], []
        for spec in rebates:
            code, pct, basis = spec["code"], spec["rate_percent"], spec["basis"]
            current = 0
            if basis == "claim":
                current = rhe(claimed[code] * pct, 100) if code in claimed else 0
            elif basis == "leak":
                current = leak_value
            elif eligible(spec, facts):
                current = rhe({"service_pct": service, "water_pct": water_total, "large_meter": large_svc}[basis] * pct, 100)
            old = sorted(carried.get(code, []))
            now = [(2026, current)] if current > 0 else []
            sources = now + old if "current_first" in rulings else old + now
            if not sources:
                continue
            cap = spec["cap"]
            if cap is None:
                room = None
            elif cap[0] == "fixed":
                room = cap[1]
            else:
                room = rhe(figures[cap[0]] * cap[1], 100)
            for origin, amount in sources:
                take = max(0, min(amount, remaining, groom, amount if room is None else room))
                if take:
                    applied.append({"rebate_code": code, "origin_year": origin, "applied_cents": take})
                remaining -= take
                groom -= take
                if room is not None:
                    room -= take
                left = amount - take
                if left > 0 and spec["carry_years"] > 0 and 2027 - origin <= spec["carry_years"]:
                    carry_out.append({"rebate_code": code, "origin_year": origin, "remaining_cents": left})
        rebates_total = sum(r["applied_cents"] for r in applied)
        carry_out.sort(key=lambda r: (r["rebate_code"], r["origin_year"]))

        minimum = rules["minimum"][aclass]
        if "minimum_proration" in rulings:
            minimum = rhu(minimum * active, 365)
        after = gross - rebates_total
        topup = max(0, minimum - after)
        net = after + topup

        quarter = net // 4
        inst = [{"quarter": q, "due_date": dues[q], "amount_cents": quarter if q != "Q4" else net - 3 * quarter,
                 "paid_cents": 0, "interest_cents": 0} for q in QUARTERS]
        grace = timedelta(days=rules["grace"])
        pays = []
        for p in by_acct[aid]["pmt"]:
            made = d(p["paid_on"])
            if made > asof:
                issues.append(f"{aid}: payment {p['payment_id']} dated after the assessment date disregarded")
                continue
            eff = business_next(made, holidays) if "payment_day" in rulings else made
            pays.append((eff, p["payment_id"], int(p["amount_cents"])))
        counted = 0
        for eff, _pid, amount in sorted(pays):
            counted += amount
            for row in inst:
                if amount == 0:
                    break
                open_amt = row["amount_cents"] - row["paid_cents"]
                if open_amt <= 0:
                    continue
                take = min(open_amt, amount)
                row["paid_cents"] += take
                if eff > row["due_date"] + grace:
                    row["interest_cents"] += interest(rules, take, row["due_date"], eff)
                amount -= take
        for row in inst:
            unpaid = row["amount_cents"] - row["paid_cents"]
            if unpaid > 0 and asof > row["due_date"] + grace:
                row["interest_cents"] += interest(rules, unpaid, row["due_date"], asof)
            row["due_date"] = row["due_date"].isoformat()
        total_interest = sum(r["interest_cents"] for r in inst)
        results.append({
            "account_id": aid, "account_class": aclass, "holder_form": form, "concession_card": card, "active_days": active,
            "billing_zone": bzone, "region": region,
            "meter_intervals": sorted(intervals, key=lambda r: (r["meter_id"], r["to"])), "meters": meter_rows, "properties": prop_rows,
            "water_supply_cents": water_total, "wastewater_cents": ww_total, "volumetric_charges_cents": volumetric,
            "service_charges_cents": service, "base_charges_cents": base, "surcharge_cents": surcharge, "supply_total_cents": supply,
            "catchment_levy_cents": catch, "trade_waste_cents": trade_total, "gross_charge_cents": gross,
            "rebates_applied": applied, "rebates_total_cents": rebates_total, "carryforward_out": carry_out,
            "minimum_charge_cents": minimum, "minimum_topup_cents": topup, "net_charge_cents": net, "instalments": inst,
            "payments_cents": counted, "interest_cents": total_interest, "balance_cents": net + total_interest - counted,
        })

    def totals(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {k: sum(r[k] for r in rows) for k in TOTAL_KEYS}

    out: dict[str, Any] = {}
    out["summary.json"] = {
        "report_id": batch["batch_id"], "assessment_date": batch["assessment_date"], "account_count": len(results),
        "totals": totals(results), "region_totals": {r: totals([x for x in results if x["region"] == r]) for r in REGIONS},
        "class_account_counts": {c: sum(1 for x in results if x["account_class"] == c) for c in ("residential", "commercial", "public")},
        "balance_status_counts": {"credit_balance": sum(1 for x in results if x["balance_cents"] < 0),
                                  "settled": sum(1 for x in results if x["balance_cents"] == 0),
                                  "balance_due": sum(1 for x in results if x["balance_cents"] > 0)},
    }
    out["policy_audit.json"] = dict(rules["audit"], report_id=batch["batch_id"])
    out["data_quality.json"] = {
        "input_file_count": len([p for p in data_dir.iterdir() if p.is_file()]),
        "account_count": len(reg["accounts.csv"]), "property_count": len(reg["properties.csv"]), "meter_count": len(reg["meters.csv"]),
        "reading_count": len(reg["meter_reads.csv"]), "trade_waste_return_count": len(reg["trade_waste.csv"]),
        "claim_count": len(reg["concession_claims.csv"]), "leak_claim_count": len(reg["leak_claims.csv"]),
        "carryforward_count": len(reg["carryforwards.csv"]), "payment_count": len(reg["payments.csv"]),
        "quality_issue_count": len(issues), "quality_issues": sorted(issues),
    }
    for r in REGIONS:
        members = [x for x in results if x["region"] == r]
        out[f"region_{r}.json"] = {"region": r, "account_count": len(members), "totals": totals(members),
                                   "accounts": [{k: v for k, v in x.items() if k != "region"} for x in members]}
    for s in SEGMENTS:
        members = [x for x in results if x["account_class"] == s]
        rt: dict[str, int] = {}
        for x in members:
            for row in x["rebates_applied"]:
                rt[row["rebate_code"]] = rt.get(row["rebate_code"], 0) + row["applied_cents"]
        out[f"segment_{s}.json"] = {"segment": s, "account_count": len(members), "totals": totals(members),
                                    "rebate_totals": rt, "account_ids": [x["account_id"] for x in members]}
    return out


def interest(rules: dict[str, Any], amount: int, due: date, until: date) -> int:
    total = 0
    day = due + timedelta(days=1)
    while day <= until:
        total += rate_on(rules["interest"], day)
        day += timedelta(days=1)
    return rhu(amount * total, 1_000_000 * 365)


def eligible(spec: dict[str, Any], facts: dict[str, Any]) -> bool:
    e = spec["elig"]
    if "classes" in e and facts["class"] not in e["classes"]:
        return False
    if "cards" in e and facts["card"] not in e["cards"]:
        return False
    if e.get("drought_property") and not facts["drought_property"]:
        return False
    if e.get("community") and not facts["community"]:
        return False
    if e.get("large_meter") and not facts["large_meter"]:
        return False
    if facts["form"] in e.get("excluded", []):
        return False
    return True


def write_outputs(data_dir: Path, out_dir: Path, rules: dict[str, Any]) -> None:
    result = assess(data_dir, rules)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_NAMES:
        (out_dir / name).write_text(json.dumps(result[name], indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        sys.exit(2)
    batch = Path(sys.argv[1])
    write_outputs(batch, Path(sys.argv[2]), resolve(read_provisions(batch / "tariff_code.md")))
