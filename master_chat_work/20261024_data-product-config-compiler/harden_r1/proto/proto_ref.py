"""Scratch prototype of the round-1 replacement levers (not shipped).

ref_compute_p(files, assign=, budget=, cap=) is ref_core.ref_compute with three new rules:
  NL-1 assignment on D: the owner's row with the latest active_from on or before D; the owner
       is assigned on D when that row's active_to is empty or on/after D.
       reflexes: any_first (first covering row, file order), any_last (last covering row).
  NL-2 change budget: manifest change_budget N; product overrides that pass the earlier checks are
       accepted in ascending seq while the product's team has budget left, else reason budget.
       A product with no team (orphaned) draws on no budget.
       reflexes: off, nullgroup (orphans share one budget), consume (rejected records consume).
  NL-3 quota cap: optional setting quota_cap; first pass weight share; a product above its cap gets its
       cap, every product keeps what it holds, and the units above the caps are shared again by the same
       rule among the products still below their cap (repeat).  When every product left has a cap and
       their remaining room fits within the units, each fills its room and the rest stays unassigned.
       reflexes: restart (water-filling from the whole quota each round), single (one re-share, no
       re-check), off.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys

sys.path.insert(0, "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/data-product-config-compiler")
from ref_core import REF_INPUTS, RefError, _ref_judge, _ref_lines, _ref_shares, _ref_text, ref_canon  # noqa: E402


def capped_shares(quota, weights, caps, mode):
    if mode == "off" or not weights:
        return _ref_shares(quota, weights) if weights else {}
    if mode == "restart":
        fixed = {}
        while True:
            rest = {p: w for p, w in weights.items() if p not in fixed}
            pool = quota - sum(fixed.values())
            if rest and all(p in caps for p in rest) and sum(caps[p] for p in rest) <= pool:
                return {**fixed, **{p: caps[p] for p in rest}}
            sh = _ref_shares(pool, rest) if rest else {}
            over = [p for p in rest if p in caps and sh[p] > caps[p]]
            if not over:
                return {**fixed, **sh}
            for p in over:
                fixed[p] = caps[p]
    held = {p: 0 for p in weights}
    pool, elig, rounds = quota, dict(weights), 0
    while pool > 0 and elig:
        room = {p: caps[p] - held[p] for p in elig if p in caps}
        if len(room) == len(elig) and sum(room.values()) <= pool:
            for p in elig:
                held[p] += room[p]
            return held
        sh = _ref_shares(pool, elig)
        for p in elig:
            held[p] += sh[p]
        rounds += 1
        over = [p for p in elig if p in caps and held[p] > caps[p]]
        if not over:
            return held
        pool = sum(held[p] - caps[p] for p in over)
        for p in over:
            held[p] = caps[p]
        elig = {p: w for p, w in elig.items() if not (p in caps and held[p] >= caps[p])}
        if mode == "single" and rounds == 1:
            sh = _ref_shares(pool, elig) if elig else {}
            for p in elig:
                held[p] += sh[p]
            return held
    return held


SKIP = object()


def _txt(spec, raw, mode):
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        s = s[1:-1]
    if mode == "isdigit" and spec and spec["type"] == "integer":
        return int(s) if s.isdigit() else SKIP
    if mode == "sign" and spec and spec["type"] == "integer":
        return int(s) if re.fullmatch(r"[+-]?[0-9]+", s) else SKIP
    if mode in ("isdigit", "sign"):
        mode = "strict"
    if mode == "lenient":
        try:
            return _ref_text(spec, raw)
        except ValueError:
            return SKIP
    if spec and spec["type"] == "integer" and not re.fullmatch(r"[0-9]+", s):
        return SKIP
    if spec and spec["type"] == "boolean" and s.lower() not in ("true", "false"):
        return SKIP
    return _ref_text(spec, raw)


def ref_compute_p(files, date=None, quota_override=None, assign="latest", budget="oracle", cap="oracle", textmode="strict"):
    for name in REF_INPUTS:
        if name not in files:
            raise RefError(2, f"error: missing input {name}")
    manifest = json.loads(files["release_manifest.json"])
    day = manifest["compile_date"] if date is None else date
    schema = json.loads(files["schema_registry.json"])["keys"]
    base = {}
    for text in _ref_lines(files["base_layer.yaml"]):
        key, _, raw = text.partition(":")
        v = _txt(schema[key.strip()], raw, textmode)
        if v is not SKIP:
            base[key.strip()] = v
    products, current = {}, None
    for text in _ref_lines(files["products.ini"]):
        if text.startswith("[product ") and text.endswith("]"):
            current = {"id": ref_canon(text[9:-1].strip()), "lines": []}
            products[current["id"]] = current
            continue
        key, _, raw = text.partition("=")
        key, raw = key.strip(), raw.strip()
        if key == "owner":
            current["owner"] = raw
        elif key == "tier":
            current["tier"] = raw
        elif key == "labels":
            current["labels"] = [x.strip() for x in raw.split(",")] if raw else []
        else:
            v = _txt(schema[key], raw, textmode)
            if v is not SKIP:
                current["lines"].append((key, v))
    rows = list(csv.DictReader(io.StringIO(files["owners.csv"].decode("utf-8"))))
    gone_products, gone_owners = set(), set()
    for text in _ref_lines(files["deprecation.log"]):
        parts = text.split()
        if len(parts) < 3 or parts[1] != "RETIRE" or parts[0][:10] > day:
            continue
        field, _, value = parts[2].partition("=")
        if field == "product":
            gone_products.add(ref_canon(value))
        elif field == "owner":
            gone_owners.add(value)
    team_on_day = {}
    if assign == "latest":
        latest = {}
        for row in rows:
            if row["active_from"] <= day:
                if row["owner"] not in latest or row["active_from"] > latest[row["owner"]]["active_from"]:
                    latest[row["owner"]] = row
        for owner, row in latest.items():
            if (row["active_to"] == "" or row["active_to"] >= day) and owner not in gone_owners:
                team_on_day[owner] = row["team"]
    elif assign == "latest_covering":
        latest = {}
        for row in rows:
            if row["active_from"] <= day and (row["active_to"] == "" or row["active_to"] >= day) and row["owner"] not in gone_owners:
                if row["owner"] not in latest or row["active_from"] > latest[row["owner"]]["active_from"]:
                    latest[row["owner"]] = row
        team_on_day = {o: r["team"] for o, r in latest.items()}
    else:
        for row in rows:
            if row["active_from"] <= day and (row["active_to"] == "" or row["active_to"] >= day):
                if row["owner"] not in gone_owners:
                    if assign == "any_last" or row["owner"] not in team_on_day:
                        team_on_day[row["owner"]] = row["team"]
    status, team = {}, {}
    for pid, prod in products.items():
        if pid in gone_products:
            status[pid], team[pid] = "retired", None
        elif prod["owner"] in team_on_day:
            status[pid], team[pid] = "active", team_on_day[prod["owner"]]
        else:
            status[pid], team[pid] = "orphaned", None
    compiled = [pid for pid in sorted(products) if status[pid] != "retired"]
    active = [pid for pid in compiled if status[pid] == "active"]
    rejected_team, team_layer = [], {}
    tdoc = json.loads(files["team_overrides.json"])
    for tname in sorted(tdoc):
        for key in sorted(tdoc[tname]):
            reason = _ref_judge(schema.get(key), tdoc[tname][key])
            if reason:
                rejected_team.append({"source": "team_overrides", "team": tname, "key": key, "reason": reason})
            else:
                team_layer.setdefault(tname, []).append((key, tdoc[tname][key]))
    compiled_set = set(compiled)
    over = [json.loads(x) for x in files["product_overrides.jsonl"].decode("utf-8").splitlines() if x.strip()]
    over.sort(key=lambda o: o["seq"])
    limit = manifest.get("change_budget")
    used = {}
    rejected_prod, prod_layer = [], {}
    for o in over:
        pid = ref_canon(o["product"])
        reason = "unknown_product" if pid not in compiled_set else _ref_judge(schema.get(o["key"]), o["value"])
        if limit is not None and budget != "off":
            group = team[pid] if pid in compiled_set else None
            counted = group is not None or budget == "nullgroup"
            if counted and (reason is None or (budget == "consume" and pid in compiled_set)):
                if reason is None and used.get(group, 0) >= limit:
                    reason = "budget"
                used[group] = used.get(group, 0) + 1
        if reason:
            rejected_prod.append({"source": "product_overrides", "seq": o["seq"], "product": pid,
                                  "key": o["key"], "reason": reason})
        else:
            prod_layer.setdefault(pid, []).append((o["key"], o["value"]))
    rules = []
    for text in _ref_lines(files["selectors.rules"]):
        m = re.match(r"match (team|tier|label):(\S+) set (\S+) ?(.*)$", text)
        v = _txt(schema[m.group(3)], m.group(4), textmode)
        if v is not SKIP:
            rules.append((m.group(1), m.group(2), m.group(3), v))

    def env_layers(blob):
        sections, name = {}, None
        for text in _ref_lines(blob):
            if text.startswith("["):
                name = text[1:-1].strip()
                sections[name] = []
                continue
            key, _, raw = text.partition("=")
            v = _txt(schema[key.strip()], raw, textmode)
            if v is not SKIP:
                sections[name].append((key.strip(), v))
        return sections

    def resolve(pid, env):
        prod = products[pid]
        s, chain = dict(base), []
        if env is not None:
            chain += env.get("defaults", []) + env.get("tier." + prod["tier"], [])
        for field, name, key, value in rules:
            if (field == "team" and team[pid] == name) or (field == "tier" and prod["tier"] == name) or \
                    (field == "label" and name in prod["labels"]):
                chain.append((key, value))
        if team[pid] is not None:
            chain += team_layer.get(team[pid], [])
        chain += prod["lines"] + prod_layer.get(pid, [])
        for key, value in chain:
            if value is None:
                s.pop(key, None)
            else:
                s[key] = value
        return s

    quotas = json.loads(files["cluster_quota.json"])
    if quota_override:
        quotas = dict(quotas, **quota_override)

    def shares(q, st):
        caps = {p: st[p]["quota_cap"] for p in active if "quota_cap" in st[p]}
        return capped_shares(q, {p: st[p]["weight"] for p in active}, caps, cap)

    out = {}
    settings = {pid: resolve(pid, None) for pid in compiled}
    sh = shares(quotas["shared"], settings)
    out["config.json"] = {
        "release": manifest["release"], "compile_date": day, "cluster_quota": quotas["shared"],
        "products": {pid: {"status": status[pid], "owner": products[pid]["owner"], "tier": products[pid]["tier"],
                           "team": team[pid], "settings": settings.get(pid), "quota": sh.get(pid, 0)}
                     for pid in sorted(products)},
    }
    totals = {"config": sum(sh.values())}
    for env_name in ("dev", "prod"):
        layers = env_layers(files[f"env_{env_name}.toml"])
        es = {pid: resolve(pid, layers) for pid in active}
        eq = shares(quotas[env_name], es)
        totals[env_name] = sum(eq.values())
        out[f"profile_{env_name}.json"] = {
            "env": env_name, "release": manifest["release"], "compile_date": day, "cluster_quota": quotas[env_name],
            "products": {pid: {"alerts_enabled": es[pid]["alerts_enabled"], "pii_scan": es[pid]["pii_scan"],
                               "replicas": es[pid]["replicas"], "quota": eq[pid]} for pid in active},
        }
    out["validation_report.json"] = {"release": manifest["release"], "rejected_overrides": rejected_team + rejected_prod}
    by_team = {}
    for pid in active:
        by_team[team[pid]] = by_team.get(team[pid], 0) + 1
    counts = {"active": 0, "orphaned": 0, "retired": 0}
    for pid in products:
        counts[status[pid]] += 1
    out["summary.json"] = {
        "release": manifest["release"], "compile_date": day, "status_counts": counts, "active_by_team": by_team,
        "rejected_overrides": {"team_overrides": len(rejected_team), "product_overrides": len(rejected_prod)},
        "quota_total": totals,
    }
    return out
