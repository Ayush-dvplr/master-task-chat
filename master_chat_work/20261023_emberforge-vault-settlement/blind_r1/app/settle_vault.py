#!/usr/bin/env python3
"""Settle an Emberforge crafting season (stdlib only)."""
import csv
import itertools
import json
import os
import re
import sys

INF = float("inf")

REDUCTIONS = ["floor", "ceil", "half-up", "half-down", "half-even"]
ORDERS = ["FGS", "FSG", "GFS", "GSF", "SFG", "SGF"]
REFERENCES = ["opening", "opening-plus-acquired", "consumed", "acquired"]
DEFAULT_SCHEDULES = [
    ("RS-A", {1: 40, 2: 50, 3: 60}), ("RS-B", {1: 45, 2: 55, 3: 65}),
    ("RS-C", {1: 50, 2: 60, 3: 70}), ("RS-D", {1: 35, 2: 50, 3: 65}),
    ("RS-E", {1: 55, 2: 55, 3: 55}), ("RS-F", {1: 30, 2: 45, 3: 60}),
    ("RS-G", {1: 60, 2: 50, 3: 40}),
]


def reduce_frac(num, den, conv):
    if den < 0:
        num, den = -num, -den
    q, r = divmod(num, den)
    if conv == "floor":
        return q
    if conv == "ceil":
        return q + (1 if r else 0)
    twice = 2 * r
    if twice < den:
        return q
    if twice > den:
        return q + 1
    if conv == "half-up":
        return q + 1
    if conv == "half-down":
        return q
    return q if q % 2 == 0 else q + 1


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return [{k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                for row in csv.DictReader(fh)]


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def to_int(v, default=None):
    if v is None:
        return default
    s = str(v).strip()
    if s == "":
        return default
    try:
        return int(s)
    except ValueError:
        return int(float(s))


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "t")


def parse_schedules(path):
    if not os.path.exists(path):
        return DEFAULT_SCHEDULES
    out = []
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            header = None if not line else header
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0].lower() == "schedule":
            header = []
            for c in cells[1:]:
                m = re.search(r"(\d+)", c)
                header.append(int(m.group(1)) if m else None)
            continue
        if header is None or all(set(c) <= set("-: ") for c in cells):
            continue
        try:
            rates = {t: int(cells[i + 1]) for i, t in enumerate(header) if t is not None}
        except (ValueError, IndexError):
            continue
        out.append((cells[0], rates))
    return out or DEFAULT_SCHEDULES


def apply_ops(base, pcts, order, conv):
    x = base
    for op in order:
        x = reduce_frac(x * pcts[op], 100, conv)
    return x


def determine_draw(rulings, schedules):
    charge_r = rulings.get("charge_rulings", []) or []
    return_r = rulings.get("return_rulings", []) or []
    scar_r = rulings.get("scarcity_rulings", []) or []
    for conv in REDUCTIONS:
        orders_ok = [o for o in ORDERS if all(
            apply_ops(int(r["base_value"]), {"F": int(r["family_percent"]), "G": int(r["grade_percent"]),
                                             "S": int(r["scarcity_percent"])}, o, conv) == int(r["charge_ember"])
            for r in charge_r)]
        if not orders_ok:
            continue
        sched_ok = [s for s in schedules if all(
            int(r["tier"]) in s[1] and reduce_frac(int(r["committed_units"]) * s[1][int(r["tier"])], 100, conv)
            == int(r["returned_units"]) for r in return_r)]
        if not sched_ok:
            continue
        refs_ok = []
        for ref in REFERENCES:
            good = True
            for r in scar_r:
                ref_val = {"opening": int(r["opening_units"]),
                           "opening-plus-acquired": int(r["opening_units"]) + int(r["acquired_units"]),
                           "consumed": int(r["called_for_units"]),
                           "acquired": int(r["acquired_units"])}[ref]
                if ref_val == 0:
                    idx = 0
                else:
                    idx = min(int(r["scarcity_ceiling"]),
                              reduce_frac(int(r["consumed_units"]) * 100, ref_val, conv))
                if idx != int(r["scarcity_index"]):
                    good = False
                    break
            if good:
                refs_ok.append(ref)
        if not refs_ok:
            continue
        return {"reduction": conv, "order": orders_ok[0], "schedule": sched_ok[0][1],
                "schedule_id": sched_ok[0][0], "reference": refs_ok[0]}
    return {"reduction": "floor", "order": "FGS", "schedule": schedules[0][1],
            "schedule_id": schedules[0][0], "reference": "opening"}


class Season:
    def __init__(self, data_dir):
        d = data_dir
        self.patches = sorted(read_csv(os.path.join(d, "patch_calendar.csv")),
                              key=lambda p: to_int(p["ordinal"]))
        for p in self.patches:
            p["ordinal"] = to_int(p["ordinal"])
            p["opens_day"] = to_int(p["opens_day"])
            p["closes_day"] = to_int(p["closes_day"])
        self.patch_by_id = {p["patch_id"]: p for p in self.patches}
        self.first_day = min(p["opens_day"] for p in self.patches)
        self.last_day = max(p["closes_day"] for p in self.patches)

        self.reagents = {}
        for r in read_csv(os.path.join(d, "reagent_registry.csv")):
            rp = r.get("retired_patch", "") or ""
            self.reagents[r["reagent_id"]] = {
                "grade": to_int(r["grade"], 0), "scarce": truthy(r.get("scarce", "0")),
                "retired_patch": rp}
        self.reagent_ids = sorted(self.reagents)
        self.scarce_ids = [r for r in self.reagent_ids if self.reagents[r]["scarce"]]
        self.retired_from = {}
        for rid, r in self.reagents.items():
            if r["retired_patch"] and r["retired_patch"] in self.patch_by_id:
                self.retired_from[rid] = self.patch_by_id[r["retired_patch"]]["opens_day"]

        self.artifacts = {}
        for a in read_csv(os.path.join(d, "artifact_catalogue.csv")):
            self.artifacts[a["artifact_id"]] = {"family": a["family"], "tier": to_int(a["tier"]),
                                                "base": to_int(a["base_charge"])}

        eds = {}
        for row in read_csv(os.path.join(d, "recipe_editions.csv")):
            if truthy(row.get("recalled", "")):
                continue
            fp = self.patch_by_id.get(row["from_patch"])
            if fp is None:
                continue
            key = (row["artifact_id"], row["edition"])
            e = eds.setdefault(key, {"artifact": row["artifact_id"], "edition": row["edition"],
                                     "from_ord": fp["ordinal"], "lines": {}})
            e["from_ord"] = min(e["from_ord"], fp["ordinal"])
            rid = row["reagent_id"]
            e["lines"][rid] = e["lines"].get(rid, 0) + to_int(row["units_per_craft"], 0)
        self.editions_by_art = {}
        for e in eds.values():
            self.editions_by_art.setdefault(e["artifact"], []).append(e)
        for lst in self.editions_by_art.values():
            lst.sort(key=lambda e: (e["from_ord"], to_int(e["edition"], 0)))

        self.workshops = {}
        for w in read_csv(os.path.join(d, "workshop_registry.csv")):
            self.workshops[w["workshop_id"]] = {
                "charter_id": w["charter_id"], "guild_id": w["guild_id"],
                "opened": to_int(w["opened_day"]), "closed": to_int(w.get("closed_day", "")),
                "tier": to_int(w["charter_tier"]), "provisional": truthy(w.get("provisional", "")
                                                                          or w.get("provisional_charter", ""))}

        self.events = read_csv(os.path.join(d, "smith_identity_events.csv"))
        for e in self.events:
            e["day"] = to_int(e["day"])
            e["kind"] = e["kind"].strip().lower()
        self.events.sort(key=lambda e: (e["day"], e["event_id"]))

        self.ledger = read_csv(os.path.join(d, "crafting_ledger.csv"))
        for e in self.ledger:
            e["day"] = to_int(e["day"])
            e["units"] = to_int(e["units"], 0)
            e["op"] = e["op"].strip().lower()
        self.entry_by_id = {e["entry_id"]: e for e in self.ledger}

        self.acqs = read_csv(os.path.join(d, "reagent_acquisitions.csv"))
        for a in self.acqs:
            a["day"] = to_int(a["day"])
            a["units"] = to_int(a["units"], 0)
        self.opening = {r: 0 for r in self.reagent_ids}
        for row in read_csv(os.path.join(d, "vault_opening.csv")):
            self.opening[row["reagent_id"]] = to_int(row["opening_units"], 0)
            if row["reagent_id"] not in self.reagents:
                self.reagents[row["reagent_id"]] = {"grade": 0, "scarce": False, "retired_patch": ""}
        self.reagent_ids = sorted(self.reagents)

        self.requisitions = read_json(os.path.join(d, "requisitions.json")).get("requisitions", [])
        self.charter = read_json(os.path.join(d, "season_charter.json"))
        self.rulings = read_json(os.path.join(d, "council_rulings.json"))
        self.draw = determine_draw(self.rulings, parse_schedules(os.path.join(d, "convention_register.md")))

        ch = self.charter
        self.in_scope = sorted(w for w, r in self.workshops.items()
                               if r["opened"] is not None and r["opened"] <= self.first_day
                               and (r["closed"] is None or r["closed"] >= self.last_day)
                               and r["tier"] is not None and r["tier"] >= 2)
        self.in_scope_set = set(self.in_scope)
        self.guilds = sorted({self.workshops[w]["guild_id"] for w in self.in_scope})
        tcc = ch.get("tier_charge_cap", {})
        ext_patch = ch.get("extension_patch")
        ext_allow = ch.get("extension_allowance") or ch.get("tier_extension_allowance") or {}
        self.cap = {}
        for w in self.workshops:
            t = self.workshops[w]["tier"]
            c = to_int(tcc.get(str(t), 0), 0)
            if ext_patch:
                c += to_int(ext_allow.get(str(t), 0), 0) if isinstance(ext_allow, dict) else 0
            if self.workshops[w]["provisional"]:
                c = c // 2
            self.cap[w] = c

        self.order = sorted(self.ledger, key=lambda e: (e["day"], e["entry_id"]))
        self._canon_cache = {}

    def patch_of(self, day):
        if day is None:
            return None
        for p in self.patches:
            if p["opens_day"] <= day <= p["closes_day"]:
                return p
        return None

    def canon(self, handle, day):
        key = (handle, day)
        if key in self._canon_cache:
            return self._canon_cache[key]
        moves = {}
        for e in self.events:
            if e["day"] > day:
                break
            if e["kind"] in ("rename", "merge") and e["from_ref"] and e["to_ref"]:
                moves.setdefault(e["from_ref"], e["to_ref"])
        cur = handle
        seen = {cur}
        while cur in moves and moves[cur] not in seen:
            cur = moves[cur]
            seen.add(cur)
        self._canon_cache[key] = cur
        return cur

    def retired(self, canon_id, day):
        for e in self.events:
            if e["day"] > day:
                break
            if e["kind"] != "retire":
                continue
            if self.canon(e["from_ref"], day) != canon_id:
                continue
            reinstated = any(r["kind"] == "register" and e["day"] < r["day"] <= day
                             and self.canon(r["from_ref"] or r["to_ref"], day) == canon_id
                             for r in self.events)
            if not reinstated:
                return True
        return False

    def apprentice(self, canon_id, day):
        p = self.patch_of(day)
        for r in self.events:
            if r["kind"] != "register" or r["day"] > day:
                continue
            h = r["from_ref"] or r["to_ref"]
            if self.canon(h, day) == canon_id and self.patch_of(r["day"]) is p and p is not None:
                return True
        return False

    def edition_for(self, artifact, day):
        if artifact not in self.artifacts:
            return None
        p = self.patch_of(day)
        if p is None:
            return None
        best = None
        for e in self.editions_by_art.get(artifact, []):
            if e["from_ord"] <= p["ordinal"]:
                best = e
        return best

    def forge_charge(self, entry, edition, indices):
        conv = self.draw["reduction"]
        art = self.artifacts[entry["artifact_id"]]
        fam = to_int(self.charter.get("family_multiplier", {}).get(art["family"], 100), 100)
        step = to_int(self.charter.get("grade_step", 0), 0)
        maxg = max([self.reagents.get(r, {"grade": 0})["grade"] for r in edition["lines"]] or [0])
        sidx = sum(indices.get(r, 0) for r in edition["lines"] if self.reagents.get(r, {}).get("scarce"))
        pcts = {"F": fam, "G": 100 + step * maxg, "S": 100 + sidx}
        per = apply_ops(art["base"], pcts, self.draw["order"], conv)
        charge = per * entry["units"]
        return charge

    def settle(self, indices):
        conv = self.draw["reduction"]
        sched = self.draw["schedule"]
        bal = dict(self.opening)
        pidx = {p["patch_id"]: i for i, p in enumerate(self.patches)}
        n = len(self.patches)
        acq_p = {r: [0] * n for r in self.reagent_ids}
        ret_p = {r: [0] * n for r in self.reagent_ids}
        con_p = {r: [0] * n for r in self.reagent_ids}
        acq_by_day = {}
        for a in self.acqs:
            p = self.patch_of(a["day"])
            if p is None or a["reagent_id"] not in bal:
                continue
            acq_by_day.setdefault(a["day"], []).append(a)
        acq_days = sorted(acq_by_day)
        ai = 0
        findings = []
        settled = {}
        accrued = {w: 0 for w in self.workshops}
        closed = set()
        settled_forges = []
        live = {}
        credited_forge = set()
        called_for = {r: 0 for r in self.reagent_ids}
        acquired_total = {r: 0 for r in self.reagent_ids}
        charges = {}
        returns = {}
        draws = {}
        entry_canon = {}
        credited_salvages = []

        def apply_acq_upto(day):
            nonlocal ai
            while ai < len(acq_days) and acq_days[ai] <= day:
                for a in acq_by_day[acq_days[ai]]:
                    p = self.patch_of(a["day"])
                    bal[a["reagent_id"]] += a["units"]
                    acq_p[a["reagent_id"]][pidx[p["patch_id"]]] += a["units"]
                    acquired_total[a["reagent_id"]] += a["units"]
                ai += 1

        for e in self.order:
            apply_acq_upto(e["day"])
            eid = e["entry_id"]
            day = e["day"]
            ws = e["workshop_id"]
            cn = self.canon(e["smith_ref"], day)
            entry_canon[eid] = cn
            refusal = []
            if ws not in self.in_scope_set:
                refusal.append(("OUT_OF_SCOPE_WORKSHOP", ws))
            if self.retired(cn, day):
                refusal.append(("RETIRED_SMITH", cn))
            src = None
            if e["op"] == "salvage":
                ref = e.get("forge_ref", "") or ""
                src = self.entry_by_id.get(ref)
                if src is None:
                    refusal.append(("MISSING_FORGE_REF", ref))
                    edition = None
                    if e["artifact_id"] not in self.artifacts:
                        refusal.append(("UNRESOLVED_EDITION", e["artifact_id"]))
                else:
                    edition = self.edition_for(e["artifact_id"], src["day"])
                    if edition is None or self.patch_of(day) is None:
                        refusal.append(("UNRESOLVED_EDITION", e["artifact_id"]))
            else:
                edition = self.edition_for(e["artifact_id"], day)
                if edition is None:
                    refusal.append(("UNRESOLVED_EDITION", e["artifact_id"]))
            if refusal:
                for c, dtl in refusal:
                    findings.append((eid, c, dtl))
                continue
            p = self.patch_of(day)
            pi = pidx[p["patch_id"]]
            if e["op"] == "forge":
                fnd = []
                charge = self.forge_charge(e, edition, indices)
                if self.apprentice(cn, day):
                    charge = reduce_frac(charge * 80, 100, conv)
                if ws in closed:
                    fnd.append(("CAP_REACHED", ws))
                elif accrued[ws] + charge > self.cap[ws]:
                    fnd.append(("CAP_REACHED", ws))
                    closed.add(ws)
                draw = {r: u * e["units"] for r, u in edition["lines"].items()}
                for r in sorted(draw):
                    called_for[r] = called_for.get(r, 0) + draw[r]
                short = [r for r in sorted(draw) if bal.get(r, 0) - draw[r] < 0]
                if short:
                    fnd.append(("STOCK_FLOOR", short[0]))
                ret = [r for r in sorted(draw) if r in self.retired_from and day >= self.retired_from[r]]
                if ret:
                    fnd.append(("RETIRED_REAGENT", ret[0]))
                if fnd:
                    for c, dtl in fnd:
                        findings.append((eid, c, dtl))
                    continue
                for r, u in draw.items():
                    bal[r] -= u
                    con_p[r][pi] += u
                accrued[ws] += charge
                settled[eid] = True
                charges[eid] = charge
                draws[eid] = draw
                fam = self.artifacts[e["artifact_id"]]["family"]
                settled_forges.append((eid, fam, day, e["smith_ref"]))
                live[eid] = True
            else:
                ref = src["entry_id"]
                if ref in credited_forge:
                    findings.append((eid, "SALVAGE_ALREADY_CREDITED", ref))
                    continue
                fam = self.artifacts[e["artifact_id"]]["family"]
                cands = [f for f in settled_forges
                         if live.get(f[0]) and f[1] == fam and f[2] < day and self.canon(f[3], day) == cn]
                window = [f[0] for f in cands[-3:]]
                if ref not in window:
                    findings.append((eid, "UNCREDITED_SALVAGE", ref))
                    continue
                tier = self.artifacts[e["artifact_id"]]["tier"]
                rate = sched.get(tier, 0)
                rmap = {}
                for r, u in edition["lines"].items():
                    q = reduce_frac(u * src["units"] * rate, 100, conv)
                    rmap[r] = q
                    bal[r] = bal.get(r, 0) + q
                    ret_p[r][pi] += q
                returns[eid] = rmap
                credited_forge.add(ref)
                live[ref] = False
                fw = src["workshop_id"]
                accrued[fw] -= charges.get(ref, 0)
                settled[eid] = True
                credited_salvages.append(eid)

        consumed_total = {r: sum(con_p[r]) for r in self.reagent_ids}
        ceiling = to_int(self.charter.get("scarcity_ceiling", 0), 0)
        new_idx = {}
        for r in self.scarce_ids:
            ref = self.draw["reference"]
            if ref == "opening":
                rv = self.opening.get(r, 0)
            elif ref == "opening-plus-acquired":
                rv = self.opening.get(r, 0) + acquired_total[r]
            elif ref == "consumed":
                rv = called_for[r]
            else:
                rv = acquired_total[r]
            if rv == 0:
                new_idx[r] = 0
            else:
                new_idx[r] = min(ceiling, reduce_frac(consumed_total[r] * 100, rv, conv))
        return {"findings": findings, "settled": settled, "closed": closed, "charges": charges,
                "returns": returns, "draws": draws, "entry_canon": entry_canon, "balance": bal,
                "acq_p": acq_p, "ret_p": ret_p, "con_p": con_p, "indices": new_idx,
                "credited_salvages": credited_salvages}

    def fixed_point(self):
        idx = {r: 0 for r in self.scarce_ids}
        seen = []
        for _ in range(200):
            res = self.settle(idx)
            if res["indices"] == idx:
                return idx, res
            seen.append(dict(idx))
            if res["indices"] in seen:
                break
            idx = res["indices"]
        seen.append(dict(idx))
        ceiling = to_int(self.charter.get("scarcity_ceiling", 0), 0)
        ranges = []
        for r in self.scarce_ids:
            vals = [s[r] for s in seen]
            ranges.append(range(min(vals), max(vals) + 1))
        for combo in itertools.product(*ranges):
            cand = dict(zip(self.scarce_ids, combo))
            res = self.settle(cand)
            if res["indices"] == cand:
                return cand, res
        for combo in itertools.product(*[range(0, ceiling + 1)] * len(self.scarce_ids)):
            cand = dict(zip(self.scarce_ids, combo))
            res = self.settle(cand)
            if res["indices"] == cand:
                return cand, res
        res = self.settle(idx)
        return idx, res


def max_flow(groups, guild_cap, reagent_cap, pool):
    """groups: dict (guild, reagent) -> capacity. Returns max total flow."""
    if pool <= 0 or not groups:
        return 0
    guilds = sorted({g for g, _ in groups})
    reagents = sorted({r for _, r in groups})
    nodes = ["S", "P"] + ["g:" + g for g in guilds] + ["r:" + r for r in reagents] + ["T"]
    ix = {v: i for i, v in enumerate(nodes)}
    N = len(nodes)
    cap = [[0] * N for _ in range(N)]
    big = 10 ** 9
    cap[ix["S"]][ix["P"]] = pool
    for g in guilds:
        c = guild_cap.get(g, big)
        cap[ix["P"]][ix["g:" + g]] = max(0, min(c, big))
    for r in reagents:
        c = reagent_cap.get(r, big)
        cap[ix["r:" + r]][ix["T"]] = max(0, min(c, big))
    for (g, r), c in groups.items():
        cap[ix["g:" + g]][ix["r:" + r]] += c
    s, t = ix["S"], ix["T"]
    flow = 0
    while True:
        parent = [-1] * N
        parent[s] = s
        q = [s]
        qi = 0
        while qi < len(q) and parent[t] == -1:
            u = q[qi]
            qi += 1
            for v in range(N):
                if parent[v] == -1 and cap[u][v] > 0:
                    parent[v] = u
                    q.append(v)
        if parent[t] == -1:
            break
        f = big
        v = t
        while v != s:
            u = parent[v]
            f = min(f, cap[u][v])
            v = u
        v = t
        while v != s:
            u = parent[v]
            cap[u][v] -= f
            cap[v][u] += f
            v = u
        flow += f
    return flow


def allocate(season, balance):
    ch = season.charter
    pool = to_int(ch.get("season_pool_units", 0), 0)
    gcap = {g: to_int(v, 0) for g, v in (ch.get("guild_cap_units", {}) or {}).items()}
    tuc = ch.get("tier_unit_cap", {}) or {}
    reqs = []
    for r in season.requisitions:
        reqs.append({"req_id": r["req_id"], "workshop_id": r["workshop_id"], "reagent_id": r["reagent_id"],
                     "priority": to_int(r.get("priority", 0), 0), "min": to_int(r.get("min_units", 0), 0),
                     "req": to_int(r.get("units_requested", 0), 0)})
    grants = {r["req_id"]: 0 for r in reqs}
    elig = []
    for r in reqs:
        w = r["workshop_id"]
        if w not in season.in_scope_set:
            continue
        wr = season.workshops[w]
        hi = min(r["req"], to_int(tuc.get(str(wr["tier"]), 0), 0))
        lo = max(r["min"], 0)
        if lo == 0:
            lo = 1
        if hi < lo:
            continue
        elig.append(dict(r, lo=lo, hi=hi, guild=wr["guild_id"], charter=wr["charter_id"],
                         scarce=season.reagents.get(r["reagent_id"], {}).get("scarce", False)))
    elig.sort(key=lambda r: (r["priority"], r["req_id"]))
    n = len(elig)
    rcap = {rid: balance.get(rid, 0) for rid in season.scarce_ids}
    big = 10 ** 9
    best = {"total": -1, "vals": None}
    vals = [0] * n

    def bound(i, pool_left, g_left, r_left, funded):
        groups = {}
        charter_max = {}
        for j in range(i, n):
            r = elig[j]
            if r["charter"] in funded:
                continue
            c = min(r["hi"], pool_left, g_left.get(r["guild"], big))
            if r["scarce"]:
                c = min(c, r_left.get(r["reagent_id"], 0))
            if c < r["lo"]:
                continue
            key = (r["guild"], r["reagent_id"] if r["scarce"] else "~free")
            groups[key] = groups.get(key, 0) + c
            charter_max[r["charter"]] = max(charter_max.get(r["charter"], 0), c)
        fl = max_flow(groups, g_left, {k: v for k, v in r_left.items()}, pool_left)
        return min(fl, sum(charter_max.values()), pool_left)

    def dfs(i, total, pool_left, g_left, r_left, funded):
        if i == n:
            if total > best["total"]:
                best["total"] = total
                best["vals"] = list(vals)
            return
        ub = total + bound(i, pool_left, g_left, r_left, funded)
        if best["vals"] is not None and ub <= best["total"]:
            return
        r = elig[i]
        options = []
        if r["charter"] not in funded:
            c = min(r["hi"], pool_left, g_left.get(r["guild"], big))
            if r["scarce"]:
                c = min(c, r_left.get(r["reagent_id"], 0))
            options = list(range(c, r["lo"] - 1, -1))
        for v in options:
            vals[i] = v
            g_left2 = dict(g_left)
            if r["guild"] in g_left2:
                g_left2[r["guild"]] -= v
            r_left2 = r_left
            if r["scarce"]:
                r_left2 = dict(r_left)
                r_left2[r["reagent_id"]] -= v
            dfs(i + 1, total + v, pool_left - v, g_left2, r_left2, funded | {r["charter"]})
            if best["vals"] is not None and total + bound(i, pool_left, g_left, r_left, funded) <= best["total"]:
                vals[i] = 0
                return
        vals[i] = 0
        dfs(i + 1, total, pool_left, g_left, r_left, funded)

    sys.setrecursionlimit(10000)
    dfs(0, 0, pool, dict(gcap), dict(rcap), frozenset())
    if best["vals"] is not None:
        for r, v in zip(elig, best["vals"]):
            grants[r["req_id"]] = v
    return pool, reqs, grants


def dump(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "/app/out"
    os.makedirs(out_dir, exist_ok=True)
    s = Season(data_dir)
    indices, res = s.fixed_point()
    settled = res["settled"]
    charges = res["charges"]
    findings = sorted(set(res["findings"]), key=lambda f: (f[0], f[1]))
    # dedupe on (entry, code)
    seen = set()
    fl = []
    for f in findings:
        if (f[0], f[1]) in seen:
            continue
        seen.add((f[0], f[1]))
        fl.append(f)
    counts = {}
    for f in fl:
        counts[f[1]] = counts.get(f[1], 0) + 1

    n = len(s.patches)
    recon_patches = []
    season_res = 0
    open_bal = dict(s.opening)
    for i, p in enumerate(s.patches):
        rows = []
        pres = 0
        for r in s.reagent_ids:
            o = open_bal.get(r, 0)
            a = res["acq_p"][r][i]
            rt = res["ret_p"][r][i]
            c = res["con_p"][r][i]
            cl = o + a + rt - c
            resid = abs(o + a + rt - c - cl)
            rows.append({"reagent_id": r, "opening_units": o, "acquired_units": a, "returned_units": rt,
                         "consumed_units": c, "closing_units": cl, "residual": resid})
            pres += resid
            open_bal[r] = cl
        recon_patches.append({"patch_id": p["patch_id"], "ordinal": p["ordinal"], "reagents": rows,
                              "residual": pres})
        season_res += pres

    vault_rows = []
    cons_resid = 0
    for r in s.reagent_ids:
        o = s.opening.get(r, 0)
        a = sum(res["acq_p"][r])
        rt = sum(res["ret_p"][r])
        c = sum(res["con_p"][r])
        cl = res["balance"].get(r, 0)
        cons_resid += abs(o + a + rt - c - cl)
        vault_rows.append({"reagent_id": r, "grade": s.reagents[r]["grade"], "scarce": s.reagents[r]["scarce"],
                           "opening_units": o, "acquired_units": a, "returned_units": rt, "consumed_units": c,
                           "closing_units": cl, "scarcity_index": indices.get(r, 0) if s.reagents[r]["scarce"] else 0})

    pool, reqs, grants = allocate(s, res["balance"])
    alloc_total = sum(grants.values())

    ws_reports = {}
    for w in s.in_scope:
        wr = s.workshops[w]
        ents = [e for e in s.order if e["workshop_id"] == w]
        adm = sum(1 for e in ents if settled.get(e["entry_id"]))
        smiths = {}
        flow = {}
        for e in ents:
            cn = res["entry_canon"][e["entry_id"]]
            row = smiths.setdefault(cn, {"canonical_smith": cn, "admitted_forges": 0, "credited_salvages": 0,
                                         "charge_ember": 0})
            if not settled.get(e["entry_id"]):
                continue
            if e["op"] == "forge":
                row["admitted_forges"] += 1
                row["charge_ember"] += charges[e["entry_id"]]
                for r, u in res["draws"][e["entry_id"]].items():
                    fr = flow.setdefault(r, [0, 0])
                    fr[0] += u
            else:
                row["credited_salvages"] += 1
                for r, u in res["returns"][e["entry_id"]].items():
                    fr = flow.setdefault(r, [0, 0])
                    fr[1] += u
        charge = sum(charges[e["entry_id"]] for e in ents if e["op"] == "forge" and settled.get(e["entry_id"]))
        ws_reports[w] = {
            "workshop_id": w, "guild_id": wr["guild_id"], "charter_id": wr["charter_id"],
            "charter_tier": wr["tier"], "entries_admitted": adm, "entries_rejected": len(ents) - adm,
            "charge_ember": charge, "cap_ember": s.cap[w], "cap_reached": w in res["closed"],
            "allocated_units": sum(grants[r["req_id"]] for r in reqs if r["workshop_id"] == w),
            "smiths": [smiths[k] for k in sorted(smiths)],
            "reagent_flow": [{"reagent_id": r, "consumed_units": flow[r][0], "returned_units": flow[r][1],
                              "net_units": flow[r][0] - flow[r][1]} for r in sorted(flow)],
        }
    g_reports = {}
    for g in s.guilds:
        wl = [w for w in s.in_scope if s.workshops[w]["guild_id"] == g]
        flow = {}
        for w in wl:
            for row in ws_reports[w]["reagent_flow"]:
                fr = flow.setdefault(row["reagent_id"], [0, 0])
                fr[0] += row["consumed_units"]
                fr[1] += row["returned_units"]
        g_reports[g] = {
            "guild_id": g, "workshops": wl,
            "entries_admitted": sum(ws_reports[w]["entries_admitted"] for w in wl),
            "charge_ember": sum(ws_reports[w]["charge_ember"] for w in wl),
            "allocated_units": sum(ws_reports[w]["allocated_units"] for w in wl),
            "reagent_flow": [{"reagent_id": r, "consumed_units": flow[r][0], "returned_units": flow[r][1],
                              "net_units": flow[r][0] - flow[r][1]} for r in sorted(flow)],
        }
    charge_total = sum(ws_reports[w]["charge_ember"] for w in s.in_scope)
    admitted = sum(1 for e in s.ledger if settled.get(e["entry_id"]))

    summary = {
        "season": {"first_day": s.first_day, "last_day": s.last_day, "patch_count": len(s.patches)},
        "workshops_in_scope": list(s.in_scope),
        "guilds_in_scope": list(s.guilds),
        "entries_total": len(s.ledger),
        "entries_admitted": admitted,
        "entries_rejected": len(s.ledger) - admitted,
        "credited_salvages": len(res["credited_salvages"]),
        "uncredited_salvages": counts.get("UNCREDITED_SALVAGE", 0),
        "scarcity_index": {r: indices.get(r, 0) for r in s.scarce_ids},
        "season_charge_ember": charge_total,
        "allocated_units_total": alloc_total,
        "conservation_residual": cons_resid,
    }
    dump(os.path.join(out_dir, "summary.json"), summary)
    dump(os.path.join(out_dir, "vault_audit.json"), {"reagents": vault_rows})
    dump(os.path.join(out_dir, "reconciliation.json"), {
        "patches": recon_patches, "season_residual": season_res,
        "charge_by_workshop": {w: ws_reports[w]["charge_ember"] for w in s.in_scope},
        "charge_by_guild": {g: g_reports[g]["charge_ember"] for g in s.guilds},
        "charge_total": charge_total})
    dump(os.path.join(out_dir, "data_quality.json"), {
        "findings": [{"entry_id": f[0], "code": f[1], "detail": f[2]} for f in fl],
        "counts": {k: counts[k] for k in sorted(counts)}})
    dump(os.path.join(out_dir, "allocation.json"), {
        "pool_units": pool,
        "assignments": [{"req_id": r["req_id"], "workshop_id": r["workshop_id"], "reagent_id": r["reagent_id"],
                         "allocated_units": grants[r["req_id"]], "served": grants[r["req_id"]] > 0}
                        for r in sorted(reqs, key=lambda r: r["req_id"])],
        "allocated_total": alloc_total})
    for w, rep in ws_reports.items():
        dump(os.path.join(out_dir, "workshop_" + w + ".json"), rep)
    for g, rep in g_reports.items():
        dump(os.path.join(out_dir, "guild_" + g + ".json"), rep)


if __name__ == "__main__":
    main()
