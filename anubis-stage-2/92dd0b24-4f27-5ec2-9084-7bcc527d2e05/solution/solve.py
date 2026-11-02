"""Adjudicate the open slate, drive the arbiter, and publish the slate files."""
import csv
import datetime as dt
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/app"
DATA = ROOT + "/data"
SERVICE = ROOT + "/service"
OUT = ROOT + "/out"

STAGES = ["S1", "S2", "S3", "S4", "S5", "S6"]
FORMATS = ["classic", "singleton", "relic"]
VERDICTS = ["seated", "amended", "flagged", "barred", "unresolved"]
REASONS = ["card_barred", "chain_cycle", "charge_cycle", "copy_breach",
           "no_prior_list", "points_over", "tier_bar", "unknown_printing"]
SOURCES = ["addendum", "base", "global", "rider"]
TIERS = ["barred", "caution", "clear", "probation"]
OP_FOR = {"seated": "seat", "amended": "amend", "flagged": "flag",
          "barred": "bar", "unresolved": "defer"}


def P(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def PL(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


def U(x):
    return x.strftime("%Y-%m-%dT%H:%M:%SZ")


def D(s):
    return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)


def hu(num, den):
    return (num * 2 + den) // (den * 2)


def rows(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        grid = list(csv.reader(fh))
    grid = [g for g in grid if g]
    return grid[0], grid[1:]


def trows(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")
    head = lines[0].split("\t")
    out = []
    for ln in lines[1:]:
        if not ln:
            continue
        out.append(ln.split("\t"))
    return head, out


def jrows(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def ini(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    sec = {}
    cur = None
    for ln in text.split("\n"):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            sec[cur] = {}
        elif "=" in s and cur is not None:
            k, v = s.split("=", 1)
            sec[cur][k.strip()] = v.strip()
    return sec


def norm_set(raw):
    s = raw.strip().upper()
    if s.endswith("*"):
        s = s[:-1]
    m = re.search(r"([0-9]+)$", s)
    if m:
        head = s[:m.start()]
        s = head + str(int(m.group(1)))
    return s


class Ctx(object):
    pass


def load(root):
    c = Ctx()
    c.root = root
    c.win = ini(os.path.join(root, "slate_window.ini"))
    c.rules_ini = ini(os.path.join(root, "format_rules.ini"))
    c.clocks = ini(os.path.join(root, "venue_clocks.ini"))
    c.chan = ini(os.path.join(root, "channel_policy.ini"))
    c.sreg = ini(os.path.join(root, "source_registry.ini"))
    c.scen = ini(os.path.join(root, "scenario_brief.ini"))
    with open(os.path.join(root, "registry_seed.json"), encoding="utf-8") as fh:
        c.seed = json.load(fh)
    with open(os.path.join(root, "service_token.json"), encoding="utf-8") as fh:
        c.token = json.load(fh)

    c.slate_id = c.win["slate"]["slate_id"]
    c.season = c.win["slate"]["season"]
    c.base_cutoff = P(c.win["slate"]["legality_cutoff"])
    c.cutover = P(c.win["slate"]["precedence_cutover"])
    c.carry_cap = int(c.win["slate"]["carry_cap"])
    c.relief = int(c.win["slate"]["carry_relief"])
    c.open_stage = c.win["slate"]["open_stage"]
    c.closes = {k: P(v) for k, v in c.win["stage_closes"].items()}
    c.bands = {}
    for name, spec in c.win["tier_bands"].items():
        for part in spec.split(","):
            c.bands[int(part.strip())] = name
    c.weights = {k: int(v) for k, v in c.win["penalty_weights"].items()}

    c.base_off = {}
    c.host_of = {}
    for sec, kv in c.clocks.items():
        c.base_off[sec] = int(kv["base_offset_minutes"])
        c.host_of[sec] = kv["intake_host"]

    c.shifts = {}
    head, rr = rows(os.path.join(root, "venue_offset_shifts.csv"))
    for r in rr:
        c.shifts.setdefault(r[0], []).append((P(r[1]), int(r[2]), int(r[3])))
    for v in c.shifts:
        c.shifts[v].sort()

    c.join = {}
    c.home = {}
    head, rr = rows(os.path.join(root, "player_registry.csv"))
    for r in rr:
        c.join[r[0]] = D(r[2])
        c.home[r[0]] = r[3]

    c.handles = {}
    head, rr = rows(os.path.join(root, "handle_changes.csv"))
    for r in rr:
        c.handles.setdefault(r[0], []).append((P(r[2]), r[1], P(r[3])))
    for h in c.handles:
        c.handles[h].sort()

    c.ident = []
    head, rr = rows(os.path.join(root, "identity_events.csv"))
    for r in rr:
        c.ident.append({"id": r[0], "kind": r[1], "a": r[2], "b": r[3],
                        "eff": P(r[4]), "rec": P(r[5])})

    c.region_rows = {}
    head, rr = rows(os.path.join(root, "venue_roster.csv"))
    for r in rr:
        c.region_rows.setdefault(r[0], []).append((P(r[2]), r[1], P(r[3])))
    for v in c.region_rows:
        c.region_rows[v].sort()

    c.pr_key = {}
    c.pr_set = {}
    c.pr_name = {}
    c.pr_rel = {}
    c.key_prints = {}
    head, rr = rows(os.path.join(root, "printing_registry.csv"))
    for r in rr:
        c.pr_key[r[0]] = r[1]
        c.pr_set[r[0]] = r[2]
        c.pr_name[r[0]] = r[3]
        c.pr_rel[r[0]] = D(r[4])
        c.key_prints.setdefault(r[1], []).append(r[0])
    c.key_first = {}
    c.key_name = {}
    for k, ps in c.key_prints.items():
        ps.sort(key=lambda x: (c.pr_rel[x], x))
        c.key_first[k] = ps[0]
        c.key_name[k] = c.pr_name[ps[0]]

    c.renames = {}
    head, rr = rows(os.path.join(root, "card_renames.csv"))
    for r in rr:
        c.renames.setdefault(r[0], []).append((P(r[2]), r[1], P(r[3])))
    for k in c.renames:
        c.renames[k].sort()

    c.links = {}
    head, rr = trows(os.path.join(root, "reprint_links.tsv"))
    for r in rr:
        c.links.setdefault(r[1], []).append(
            {"id": r[0], "a": r[2], "b": r[3], "eff": P(r[4]), "rec": r[5]})
    for f in c.links:
        c.links[f].sort(key=lambda x: (x["eff"], x["id"]))

    c.exempt = {}
    head, rr = rows(os.path.join(root, "format_exemptions.csv"))
    for r in rr:
        c.exempt.setdefault((r[0], r[1], r[2]), []).append((r[3], P(r[4])))

    c.cal = {}
    head, rr = rows(os.path.join(root, "stage_calendar.csv"))
    for r in rr:
        c.cal.setdefault((r[0], r[1]), []).append(
            {"ws": P(r[2]), "we": P(r[3]), "rev": r[4], "pub": P(r[5])})

    c.hoff = {}
    head, rr = rows(os.path.join(root, "host_clock_offsets.csv"))
    for r in rr:
        c.hoff[(r[0], r[1])] = int(r[2])

    c.board = {}
    with open(os.path.join(root, "printing_release_board.txt"), encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if not ln:
                continue
            c.board[ln[0:8].strip()] = int(ln[32:38])

    c.gl = {}
    for i in range(1, 5):
        for rec in jrows(os.path.join(root, "global_restrictions_%02d.jsonl" % i)):
            c.gl.setdefault((rec["format"], rec["canonical_key"]), []).append(rec)

    c.add = {}
    for reg in ("north", "south", "east"):
        head, rr = rows(os.path.join(root, "addendum_%s.csv" % reg))
        for r in rr:
            c.add.setdefault((reg, r[0], r[1]), []).append(
                {"ac": r[2], "pc": r[3], "eff": P(r[4]), "rec": P(r[5])})
    for k in c.add:
        c.add[k].sort(key=lambda x: (x["eff"], x["rec"]))

    c.rider = {}
    head, rr = trows(os.path.join(root, "event_rider.tsv"))
    for r in rr:
        c.rider.setdefault((r[0], r[1]), []).append(
            {"ac": r[2], "pc": r[3], "auth": r[4], "eff": P(r[5]), "rec": P(r[6])})
    for k in c.rider:
        c.rider[k].sort(key=lambda x: (x["eff"], x["rec"]))

    c.rank = {}
    head, rr = rows(os.path.join(root, "authority_roster.csv"))
    for r in rr:
        c.rank.setdefault(r[0], []).append((P(r[2]), int(r[1]), P(r[3])))
    for j in c.rank:
        c.rank[j].sort()

    c.headers = []
    for i in range(1, 5):
        head, rr = rows(os.path.join(root, "entry_header_%02d.csv" % i))
        for r in rr:
            c.headers.append({"sid": r[0], "handle": r[1], "fmt": r[2],
                              "venue": r[3], "local": r[4], "record_venue": r[5],
                              "tag": r[6]})

    c.legacy = []
    head, rr = trows(os.path.join(root, "legacy_entries.tsv"))
    for r in rr:
        c.legacy.append({"season": r[0], "sid": r[1], "handle": r[2],
                         "fmt": r[3], "venue": r[4], "local": r[5],
                         "rec": r[6], "note": r[7]})

    c.deck = {}
    for i in range(1, 7):
        head, rr = rows(os.path.join(root, "deck_lines_%02d.csv" % i))
        for r in rr:
            c.deck.setdefault(r[0], []).append(
                {"no": int(r[1]), "name": r[2], "set": r[3], "copies": r[4]})
    for s in c.deck:
        c.deck[s].sort(key=lambda x: x["no"])

    c.amend = {}
    for i in (1, 2):
        for rec in jrows(os.path.join(root, "amendments_%02d.jsonl" % i)):
            c.amend.setdefault(rec["submission_id"], []).append(rec)

    c.events = []
    for i in (1, 2):
        c.events.extend(jrows(os.path.join(root, "entry_events_%02d.jsonl" % i)))

    c.standing = []
    head, rr = rows(os.path.join(root, "standing_entries.csv"))
    for r in rr:
        c.standing.append({"id": r[0], "handle": r[1], "fmt": r[2], "venue": r[3],
                           "wd": r[4], "local": r[5], "start": D(r[6]),
                           "until": D(r[7]), "rec": P(r[8])})

    c.exc = []
    head, rr = rows(os.path.join(root, "entry_exceptions.csv"))
    for r in rr:
        c.exc.append({"id": r[0], "kind": r[1], "sid": r[2], "venue": r[3],
                      "on": r[4], "rec": P(r[5])})

    c.grants = []
    head, rr = rows(os.path.join(root, "reinstatement_grants.csv"))
    for r in rr:
        c.grants.append({"id": r[0], "player": r[1], "eff": P(r[2]),
                         "rec": P(r[3]), "auth": r[4]})

    c.contested = []
    head, rr = rows(os.path.join(root, "contested_entries.csv"))
    for r in rr:
        c.contested.append(r[0])

    c.receipts = {}
    for name in ("intake_journal.log.1", "intake_journal.log"):
        cur = None
        with open(os.path.join(root, name), encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.rstrip("\n")
                if not ln:
                    continue
                if ln.startswith("    "):
                    body = ln.strip()
                    if body.startswith("recorded_override=") and cur is not None:
                        cur["override"] = P(body.split("=", 1)[1])
                    continue
                parts = ln.split(" ")
                fields = {}
                for p in parts[1:]:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        fields[k] = v
                cur = {"raw": PL(parts[0]), "host": fields.get("host", ""),
                       "rc": fields.get("receipt", ""), "override": None}
                c.receipts.setdefault(fields.get("submission", ""), []).append(cur)
    return c


def offset_at(c, v, inst):
    off = c.base_off[v]
    for at, before, after in c.shifts.get(v, []):
        if inst >= at:
            off = after
    return off


def utc_from_local(c, v, local):
    cands = set([c.base_off[v]])
    for at, before, after in c.shifts.get(v, []):
        cands.add(before)
        cands.add(after)
    good = []
    for o in sorted(cands):
        inst = (local - dt.timedelta(minutes=o)).replace(
            tzinfo=dt.timezone.utc)
        if offset_at(c, v, inst) == o:
            good.append(inst)
    if good:
        return min(good)
    best = None
    for at, before, after in c.shifts.get(v, []):
        naive = at.replace(tzinfo=None)
        lo = naive + dt.timedelta(minutes=before)
        hi = naive + dt.timedelta(minutes=after)
        a, b = min(lo, hi), max(lo, hi)
        if a <= local.replace(tzinfo=None) < b:
            best = at
    if best is None:
        return (local - dt.timedelta(minutes=c.base_off[v])).replace(
            tzinfo=dt.timezone.utc)
    return best


def comp_day(c, v, inst):
    loc = inst + dt.timedelta(minutes=offset_at(c, v, inst))
    if loc.hour * 60 + loc.minute < 240:
        loc = loc - dt.timedelta(days=1)
    return loc.strftime("%Y-%m-%d")


def region_at(c, v, inst, cutoff):
    best = None
    for eff, reg, rec in c.region_rows.get(v, []):
        if eff <= inst and rec <= cutoff:
            if best is None or eff >= best[0]:
                best = (eff, reg)
    return None if best is None else best[1]


def rank_at(c, j, inst, cutoff):
    best = None
    for eff, rk, rec in c.rank.get(j, []):
        if eff <= inst and rec <= cutoff:
            if best is None or eff >= best[0]:
                best = (eff, rk)
    return 0 if best is None else best[1]


def window_of(c, stage, venue, cutoff):
    best = None
    for r in c.cal.get((stage, venue), []):
        if r["pub"] <= cutoff:
            if best is None or r["pub"] > best["pub"]:
                best = r
    if best is None:
        return None
    return (best["ws"], best["we"])


def stage_of(c, venue, inst, cutoff):
    found = None
    for s in STAGES:
        wnd = window_of(c, s, venue, cutoff)
        if wnd and wnd[0] <= inst < wnd[1]:
            found = s
    return found


def handle_player(c, handle, inst, cutoff):
    best = None
    for eff, pid, rec in c.handles.get(handle, []):
        if eff <= inst and rec <= cutoff:
            if best is None or eff >= best[0]:
                best = (eff, pid)
    return None if best is None else best[1]


def rules_for(c, fmt, stage):
    want = ["default_copies", "copies_cap", "points_budget_cpt", "charge_ceiling_cpt"]
    start = "format.%s.%s" % (fmt, stage)
    if start not in c.rules_ini:
        start = "format.%s" % fmt
    out = {}
    seen = set()
    cur = start
    while cur is not None and cur in c.rules_ini and cur not in seen:
        seen.add(cur)
        kv = c.rules_ini[cur]
        for k in want:
            if k in kv and k not in out:
                out[k] = int(kv[k])
        cur = kv.get("inherits")
    return out


def name_index(c, cutoff):
    idx = {}
    for pr, nm in c.pr_name.items():
        idx.setdefault((norm_set(c.pr_set[pr]), nm), []).append(pr)
    for v in idx.values():
        v.sort()
    return idx


def rename_at(c, key, inst, cutoff):
    best = None
    for eff, nm, rec in c.renames.get(key, []):
        if eff <= inst and rec <= cutoff:
            if best is None or eff >= best[0]:
                best = (eff, nm)
    return None if best is None else best[1]


def link_sets(c, fmt, inst, cutoff, cache):
    adm = []
    for ln in c.links.get(fmt, []):
        if ln["eff"] > inst:
            continue
        rec = ln["rec"]
        if rec == "\\N":
            continue
        if rec == "":
            pass
        else:
            if P(rec) > cutoff:
                continue
        adm.append(ln)
    key = (fmt, len(adm))
    if key in cache:
        return cache[key]
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ln in adm:
        ra, rb = find(ln["a"]), find(ln["b"])
        if ra != rb:
            parent[rb] = ra
    groups = {}
    for x in list(parent):
        groups.setdefault(find(x), []).append(x)
    surv = {}
    for root_key, members in groups.items():
        best = None
        for m in members:
            first = c.key_first.get(m)
            rel = c.pr_rel.get(first, D("2099-01-01")) if first else D("2099-01-01")
            if best is None or (rel, m) < best[0]:
                best = ((rel, m), m)
        for m in members:
            surv[m] = best[1]
    cache[key] = surv
    return surv


def parse_milli(text, mark):
    t = text.strip()
    if mark == "comma":
        t = t.replace(",", ".")
    if "." in t:
        whole, frac = t.split(".", 1)
    else:
        whole, frac = t, ""
    frac = (frac + "000")[:3]
    sign = -1 if whole.startswith("-") else 1
    whole = whole.lstrip("+-") or "0"
    return sign * (int(whole) * 1000 + int(frac))


def global_pick(c, fmt, key, inst, cutoff):
    adm = []
    cyc = False
    for rec in c.gl.get((fmt, key), []):
        if P(rec["effective_at"]) > inst:
            continue
        if P(rec["recorded_at"]) > cutoff:
            continue
        if rec.get("retracted"):
            continue
        adm.append(rec)
    if not adm:
        return None, False
    ids = set(r["revision_id"] for r in adm)
    covered = set()
    for r in adm:
        sup = r.get("supersedes")
        if sup in ids:
            covered.add(sup)
    heads = [r for r in adm if r["revision_id"] not in covered]
    if not heads:
        return None, True
    heads.sort(key=lambda r: (P(r["effective_at"]), P(r["recorded_at"]),
                              r["revision_id"]))
    return heads[-1], cyc


def resolve_restriction(c, fmt, key, inst, region, cutoff, stage, drop, memo, seen):
    mk = (fmt, key, region, inst, stage)
    if mk in memo:
        return memo[mk]
    if mk in seen:
        return {"cycle": "charge_cycle", "copies": None, "charge": None,
                "source": "base"}
    seen.add(mk)
    chain = False
    g, gcyc = global_pick(c, fmt, key, inst, cutoff)
    if gcyc:
        chain = True
    gac = None if g is None else g.get("allowed_copies")
    gpc = None if g is None else g.get("point_charge")

    aac = apc = None
    rowsa = c.add.get((region, fmt, key), []) if region else []
    pick = None
    for r in rowsa:
        if r["eff"] <= inst and r["rec"] <= cutoff:
            pick = r
    if pick is not None:
        aac = int(pick["ac"]) if pick["ac"] != "" else None
        apc = pick["pc"] if pick["pc"] != "" else None

    rac = rpc = None
    if drop != "rider":
        pick = None
        for r in c.rider.get((fmt, key), []):
            if r["eff"] <= inst and r["rec"] <= cutoff:
                if rank_at(c, r["auth"], r["rec"], cutoff) >= 3:
                    pick = r
        if pick is not None:
            rac = int(pick["ac"]) if pick["ac"] != "" else None
            rpc = pick["pc"] if pick["pc"] != "" else None

    if inst >= c.cutover:
        copy_order = [("rider", rac), ("global", gac), ("addendum", aac)]
        charge_order = [("rider", rpc), ("global", gpc), ("addendum", apc)]
    else:
        copy_order = [("rider", rac), ("addendum", aac), ("global", gac)]
        # Order settled from the observations by derive_conventions.
        given = {"rider": rpc, "global": gpc, "addendum": apc}
        charge_order = [(name, given[name]) for name in c.pre_charge]

    copies = None
    for name, val in copy_order:
        if val is not None:
            copies = int(val)
            break
    charge = None
    csource = "base"
    for name, val in charge_order:
        if val is None:
            continue
        csource = name
        if name == "rider":
            charge = int(val)
        elif name == "addendum":
            charge = hu(parse_milli(str(val), "comma"), 10)
        else:
            sval = str(val)
            if sval.startswith("mirror:"):
                tgt = sval.split(":", 1)[1]
                sub = resolve_restriction(c, fmt, tgt, inst, region, cutoff,
                                          stage, drop, memo, seen)
                if sub["cycle"] == "charge_cycle" or sub["charge"] is None:
                    charge = None
                    csource = name
                    seen.discard(mk)
                    out = {"cycle": "charge_cycle", "copies": copies,
                           "charge": None, "source": name}
                    memo[mk] = out
                    return out
                charge = sub["charge"]
            else:
                charge = hu(parse_milli(sval, "dot"), 10)
        break
    if charge is None:
        first = c.key_first.get(key)
        if first is not None and first in c.board:
            charge = hu(c.board[first], 10)
            csource = "base"
        else:
            charge = 0
            csource = "base"
    out = {"cycle": "chain_cycle" if chain else "", "copies": copies,
           "charge": charge, "source": csource}
    seen.discard(mk)
    memo[mk] = out
    return out


def evaluate(c, fmt, venue, inst, stage, lines, cutoff, drop, as_fmt, memo,
             lcache):
    efmt = as_fmt if as_fmt else fmt
    rl = rules_for(c, efmt, stage)
    region = region_at(c, venue, inst, cutoff)
    surv = link_sets(c, efmt, inst, cutoff, lcache)
    idx = c.nidx
    unknown = False
    counted = {}
    for ln in lines:
        ns = norm_set(ln["set"])
        nm = ln["name"]
        cands = list(idx.get((ns, nm), []))
        if not cands:
            hit = []
            for pr in c.by_set.get(ns, []):
                if rename_at(c, c.pr_key[pr], inst, cutoff) == nm:
                    hit.append(pr)
            cands = sorted(hit)
        if not cands:
            unknown = True
            continue
        pr = cands[0]
        key = c.pr_key[pr]
        key = surv.get(key, key)
        cs = str(ln["copies"]).strip()
        n = 1 if cs == "" else int(cs)
        counted[key] = counted.get(key, 0) + n
    chain = False
    cycle = False
    total = 0
    breach = 0
    zero = False
    best = None
    for key in sorted(counted):
        n = counted[key]
        res = resolve_restriction(c, efmt, key, inst, region, cutoff, stage,
                                  drop, memo, set())
        if res["cycle"] == "charge_cycle":
            cycle = True
            continue
        if res["cycle"] == "chain_cycle":
            chain = True
            continue
        allow = res["copies"] if res["copies"] is not None else rl["default_copies"]
        kinds = [k for k, rec in c.exempt.get((efmt, stage, key), []) if rec <= cutoff]
        if "singleton_copies" not in kinds:
            allow = min(allow, rl["copies_cap"])
        per = res["charge"]
        # Ceiling stage ("copy" or "contribution") settled by derive_conventions.
        ceiling = None if "charge_ceiling" in kinds else rl["charge_ceiling_cpt"]
        if ceiling is not None and c.ceiling_at == "copy":
            per = min(per, ceiling)
        if allow == 0:
            zero = True
        if n > allow:
            breach += 1
        contrib = per * n
        if ceiling is not None and c.ceiling_at == "contribution":
            contrib = min(contrib, ceiling)
        total += contrib
        if best is None or (-contrib, key) < (-best[0], best[1]):
            best = (contrib, key, res["source"])
    gsrc = "base" if best is None else best[2]
    return {"unknown": unknown, "chain": chain, "cycle": cycle,
            "points": total, "breach": breach, "zero": zero,
            "source": gsrc, "budget": rl["points_budget_cpt"],
            "keys": sorted(counted)}


def prepare(c):
    c.nidx = name_index(c, c.base_cutoff)
    c.by_set = {}
    for pr in sorted(c.pr_set):
        c.by_set.setdefault(norm_set(c.pr_set[pr]), []).append(pr)
    c.lcache = {}


def tier_of(c, carry):
    return c.bands.get(carry, "barred")


def receipt_instant(c, sid, cutoff):
    best = None
    for rec in c.receipts.get(sid, []):
        if rec["override"] is not None:
            at = rec["override"]
        else:
            off = c.hoff.get((rec["host"], day_key(rec["raw"])), 0)
            at = rec["raw"] - dt.timedelta(seconds=off)
        if at > cutoff:
            continue
        if best is None or at < best:
            best = at
    return best


def day_key(inst):
    return inst.strftime("%Y-%m-%d")


def live_links(c, inst, cutoff):
    out = {}
    for fmt in ("classic", "singleton", "relic"):
        out[fmt] = link_sets(c, fmt, inst, cutoff, c.lcache)
    return out


def event_state(c, cutoff):
    seen = {}
    rejected = 0
    rejects = set()
    order = []
    for rec in c.events:
        eid = rec["event_id"]
        body = (rec["kind"], rec["submission_id"], rec.get("successor"),
                rec["effective_at"], rec["recorded_at"])
        if eid in seen:
            if seen[eid][0] == body:
                continue
            rejected += 2 if eid not in rejects else 1
            rejects.add(eid)
            continue
        seen[eid] = (body, rec)
        order.append(eid)
    withdrawn = {}
    restored = {}
    superseded = {}
    for eid in order:
        if eid in rejects:
            continue
        rec = seen[eid][1]
        if P(rec["recorded_at"]) > cutoff:
            continue
        sid = rec["submission_id"]
        at = P(rec["effective_at"])
        if rec["kind"] == "withdraw":
            if sid not in withdrawn or at > withdrawn[sid]:
                withdrawn[sid] = at
        elif rec["kind"] == "restore":
            if sid not in restored or at > restored[sid]:
                restored[sid] = at
        elif rec["kind"] == "supersede":
            superseded[sid] = rec.get("successor")
    dropped = set()
    for sid, at in withdrawn.items():
        if sid in restored and restored[sid] > at:
            continue
        dropped.add(sid)
    for sid in superseded:
        dropped.add(sid)
    return dropped, rejected, superseded


def amendment_pick(c, sid, cutoff):
    best = None
    for rec in c.amend.get(sid, []):
        if rec.get("status") != "accepted":
            continue
        if P(rec["recorded_at"]) > cutoff:
            continue
        v = int(rec["version"])
        if best is None or v > int(best["version"]):
            best = rec
    return best


def identity_plan(c, cutoff):
    merges = []
    splits = []
    for rec in c.ident:
        if rec["kind"] == "status":
            continue
        if rec["rec"] > cutoff:
            continue
        a, b = rec["a"], rec["b"]
        if rec["kind"] == "merge":
            ja = c.join.get(a, D("2099-01-01"))
            jb = c.join.get(b, D("2099-01-01"))
            if (ja, a) <= (jb, b):
                keep, gone = a, b
            else:
                keep, gone = b, a
            merges.append({"at": rec["eff"], "keep": keep,
                           "gone": gone, "id": rec["id"]})
        else:
            splits.append({"at": rec["eff"], "src": a,
                           "new": b, "id": rec["id"]})
    merges.sort(key=lambda r: (r["at"], r["id"]))
    splits.sort(key=lambda r: (r["at"], r["id"]))
    return merges, splits


def route_player(player, inst, merges, splits):
    cur = player
    changed = True
    while changed:
        changed = False
        for m in merges:
            if m["at"] <= inst and m["gone"] == cur:
                cur = m["keep"]
                changed = True
        for s in splits:
            if s["at"] <= inst and s["src"] == cur:
                cur = s["new"]
                changed = True
    return cur


def assemble(c, cutoff):
    merges, splits = identity_plan(c, cutoff)
    dropped, rejected, superseded = event_state(c, cutoff)
    subs = []
    pool = []
    for h in c.headers:
        pool.append((h["sid"], h["handle"], h["fmt"], h["venue"],
                     h["local"], None))
    seen_sids = set(x[0] for x in pool)
    for lg in c.legacy:
        if lg["season"] != c.season:
            continue
        if lg["sid"] in seen_sids:
            continue
        pool.append((lg["sid"], lg["handle"], lg["fmt"], lg["venue"],
                     lg["local"], P(lg["rec"])))
    for sid, handle, fmt, venue, localtext, given in pool:
        if venue not in c.base_off:
            continue
        eff = utc_from_local(c, venue, PL(localtext))
        rec = given if given is not None else receipt_instant(c, sid, cutoff)
        if rec is None or rec > cutoff:
            continue
        stage = stage_of(c, venue, eff, cutoff)
        if stage is None:
            continue
        who = handle_player(c, handle, eff, cutoff)
        if who is None:
            continue
        who = route_player(who, eff, merges, splits)
        lines = list(c.deck.get(sid, []))
        amended = False
        am = amendment_pick(c, sid, cutoff)
        if am is not None:
            if "lines" in am and am["lines"] is not None:
                lines = [{"no": i + 1, "name": x["printed_name"],
                          "set": x["set_code"],
                          "copies": str(x.get("copies", ""))}
                         for i, x in enumerate(am["lines"])]
                amended = True
            else:
                amended = True
        subs.append({"sid": sid, "player": who, "fmt": fmt, "venue": venue,
                     "eff": eff, "rec": rec, "stage": stage, "lines": lines,
                     "amended": amended, "standing": False,
                     "live": sid not in dropped})
    subs = [s for s in subs if s["live"]]
    subs.sort(key=lambda s: (s["eff"], s["rec"], s["sid"]))
    return subs, merges, splits, rejected


def materialize(c, subs, cutoff):
    open_stage = c.open_stage
    taken = set()
    for s in subs:
        if s["stage"] == open_stage:
            taken.add((s["player"], s["venue"], s["fmt"],
                       comp_day(c, s["venue"], s["eff"])))
    skips = {}
    closures = {}
    for e in c.exc:
        if e["rec"] > cutoff:
            continue
        if e["kind"] == "skip":
            skips.setdefault(e["sid"], set()).add(e["on"])
        else:
            closures.setdefault(e["venue"], set()).add(e["on"])
    made = []
    for st in c.standing:
        if st["rec"] > cutoff:
            continue
        if st["venue"] not in c.base_off:
            continue
        win = window_of(c, open_stage, st["venue"], cutoff)
        if win is None:
            continue
        ws, we = win
        cur = st["start"]
        last = st["until"]
        while cur <= last:
            if cur.strftime("%a").lower()[:3] != st["wd"][:3].lower():
                cur = cur + dt.timedelta(days=1)
                continue
            dkey = cur.strftime("%Y-%m-%d")
            local = dt.datetime.strptime(dkey + " " + st["local"],
                                         "%Y-%m-%d %H:%M:%S")
            inst = utc_from_local(c, st["venue"], local)
            cday = comp_day(c, st["venue"], inst)
            if ws <= inst < we:
                if dkey not in skips.get(st["id"], set()) \
                        and cday not in closures.get(st["venue"], set()):
                    who = handle_player(c, st["handle"], inst, cutoff)
                    if who is not None:
                        if (who, st["venue"], st["fmt"], cday) not in taken:
                            made.append({"sid": "STD-" + who + "-"
                                         + cday.replace("-", ""),
                                         "player": who, "fmt": st["fmt"],
                                         "venue": st["venue"], "eff": inst,
                                         "rec": st["rec"],
                                         "stage": open_stage, "lines": None,
                                         "amended": False, "standing": True,
                                         "live": True})
                            taken.add((who, st["venue"], st["fmt"], cday))
            cur = cur + dt.timedelta(days=7)
    return made


def timeline(c, subs, merges, cutoff, drop=None, as_fmt=None):
    carry = {}
    stage_weight = {}
    stage_members = {}
    memo = {}
    events = []
    for s in subs:
        events.append((s["eff"], 2, s["rec"], s["sid"], s))
    for m in merges:
        events.append((m["at"], 1, m["at"], m["id"], m))
    for st in ("S1", "S2", "S3", "S4", "S5", "S6"):
        events.append((c.closes[st], 0, c.closes[st], st, st))
    events.sort(key=lambda e: (e[0], e[1], e[2], e[3]))
    out = []
    prior = {}
    for at, kind, _t, _k, payload in events:
        if kind == 0:
            st = payload
            for who in sorted(stage_members.get(st, ())):
                if stage_weight.get((st, who), 0) == 0:
                    carry[who] = max(carry.get(who, 0) - c.relief, 0)
            continue
        if kind == 1:
            keep, gone = payload["keep"], payload["gone"]
            carry[keep] = min(carry.get(keep, 0) + carry.get(gone, 0),
                              c.carry_cap)
            carry[gone] = 0
            continue
        s = payload
        who = s["player"]
        before = carry.get(who, 0)
        af = as_fmt if (as_fmt and s["stage"] == c.open_stage) else None
        efmt = af if af else s["fmt"]
        if s["standing"]:
            src = prior.get(who)
            if src is None:
                verdict, reason = "unresolved", "no_prior_list"
                ev = {"points": 0, "breach": 0, "source": "base", "keys": []}
            else:
                lines = src
                ev = evaluate(c, s["fmt"], s["venue"], s["eff"], s["stage"],
                              lines, cutoff, drop, af, memo, c.lcache)
                verdict, reason = verdict_of(c, ev, before, False)
        else:
            ev = evaluate(c, s["fmt"], s["venue"], s["eff"], s["stage"],
                          s["lines"], cutoff, drop, af, memo, c.lcache)
            verdict, reason = verdict_of(c, ev, before, s["amended"])
        w = c.weights[verdict]
        after = min(before + w, c.carry_cap)
        carry[who] = after
        stage_members.setdefault(s["stage"], set()).add(who)
        key = (s["stage"], who)
        stage_weight[key] = stage_weight.get(key, 0) + w
        if verdict in ("seated", "amended") and not s["standing"]:
            prior[who] = s["lines"]
        out.append({"sid": s["sid"], "player": who, "fmt": s["fmt"],
                    "venue": s["venue"], "eff": s["eff"], "rec": s["rec"],
                    "stage": s["stage"], "verdict": verdict,
                    "reason": reason, "points": ev["points"],
                    "breach": ev["breach"], "before": before,
                    "after": after, "tier": tier_of(c, after),
                    "source": ev["source"], "standing": s["standing"],
                    "keys": ev["keys"]})
    return out, carry


def verdict_of(c, ev, before, amended):
    if ev["cycle"]:
        return "unresolved", "charge_cycle"
    if ev["chain"]:
        return "unresolved", "chain_cycle"
    if ev["unknown"]:
        return "unresolved", "unknown_printing"
    if tier_of(c, before) == "barred":
        return "barred", "tier_bar"
    if ev["zero"]:
        return "barred", "card_barred"
    if ev["breach"] > 0:
        return "flagged", "copy_breach"
    if ev["points"] > ev["budget"]:
        return "flagged", "points_over"
    if amended:
        return "amended", None
    return "seated", None


OP_FOR = {"seated": "seat", "amended": "amend", "flagged": "flag",
          "barred": "bar", "unresolved": "defer"}
CONSOLE_ONLY = ("bar", "reinstate")
NEXT = {"register": "intake", "seat": "seated", "amend": "amended",
        "flag": "flagged", "bar": "barred", "defer": "deferred",
        "reinstate": "deferred"}


def admitted_grants(c, cutoff):
    out = set()
    for g in c.grants:
        if g["rec"] > cutoff:
            continue
        if rank_at(c, g["auth"], g["rec"], cutoff) < 4:
            continue
        out.add(g["player"])
    return out


def run_all(c, cutoff, drop=None, as_fmt=None):
    subs, merges, splits, rejected = assemble(c, cutoff)
    made = materialize(c, subs, cutoff)
    allsubs = sorted(subs + made, key=lambda s: (s["eff"], s["rec"], s["sid"]))
    rowsall, carry = timeline(c, allsubs, merges, cutoff, drop, as_fmt)
    rows = [r for r in rowsall if r["stage"] == c.open_stage]
    rows.sort(key=lambda r: (r["eff"], r["rec"], r["sid"]))
    redirected = 0
    hmap = {}
    for h in c.headers:
        hmap[h["sid"]] = h["handle"]
    for lg in c.legacy:
        hmap[lg["sid"]] = lg["handle"]
    for r in rows:
        hd = hmap.get(r["sid"])
        if hd is None:
            continue
        base = handle_player(c, hd, r["eff"], cutoff)
        if base is not None and base != r["player"]:
            redirected += 1
    return {"rows": rows, "all": rowsall, "rejected": rejected,
            "merges": merges, "splits": splits, "made": made,
            "redirected": redirected, "carry": carry}


def plan_ops(c, rows, cutoff):
    pre = list(c.seed["preseeded_entries"])
    preset = set(pre)
    contested = set(c.contested)
    granted = admitted_grants(c, cutoff)
    state = {}
    for sid in pre:
        state[sid] = {"state": c.seed.get("initial_state", "intake"),
                      "scope": "none", "channel": "none", "last_seq": 0}
    seq = 0
    digest = hashlib.sha256(c.slate_id.encode("utf-8")).hexdigest()
    refusals = {}
    conflicts = []
    console = 0
    api = 0
    deferred = 0
    journal = []
    for r in rows:
        ops = []
        if r["sid"] not in preset:
            ops.append("register")
        ops.append(OP_FOR[r["verdict"]])
        if r["verdict"] == "barred" and r["reason"] == "tier_bar" \
                and r["player"] in granted:
            ops.append("reinstate")
        first_cond = True
        for op in ops:
            ch = "console" if op in CONSOLE_ONLY else "api"
            if op != "register" and first_cond:
                first_cond = False
                if r["sid"] in contested:
                    refusals["stale_etag"] = refusals.get("stale_etag", 0) + 1
                    conflicts.append(r["sid"])
            if op != "register" and r["fmt"] == "relic":
                deferred += 1
            if ch == "console":
                console += 1
            else:
                api += 1
            seq += 1
            scope = r["source"]
            line = "%d:%s:%s:%s:%s" % (seq, op, r["sid"], scope, ch)
            digest = hashlib.sha256((digest + "|" + line)
                                    .encode("utf-8")).hexdigest()
            journal.append({"seq": seq, "op": op, "entry": r["sid"],
                            "scope": scope, "channel": ch})
            state[r["sid"]] = {"state": NEXT[op], "scope": scope,
                               "channel": ch, "last_seq": seq}
    npages = (len(pre) + c.seed["page_size"] - 1) // c.seed["page_size"]
    empties = npages // c.seed["empty_page_after_pages"]
    if npages % c.seed["empty_page_after_pages"] == 0 and npages > 0:
        empties = npages // c.seed["empty_page_after_pages"] - 1
    insl = set(r["sid"] for r in rows)
    return {"journal": journal, "digest": digest, "seq": seq,
            "state": state, "refusals": refusals,
            "conflicts": sorted(set(conflicts)), "console": console,
            "api": api, "deferred": deferred,
            "pages": npages + empties, "empties": empties,
            "preseeded": len([s for s in pre if s in insl])}


def report_of(c, res, plan, cutoff):
    ents = []
    for r in res["rows"]:
        ch = "console" if OP_FOR[r["verdict"]] in CONSOLE_ONLY else "api"
        ents.append({"submission_id": r["sid"], "player_id": r["player"],
                     "format": r["fmt"], "venue": r["venue"],
                     "effective_at": U(r["eff"]), "recorded_at": U(r["rec"]),
                     "verdict": r["verdict"], "reason_code": r["reason"],
                     "points_total": r["points"],
                     "copy_breach_count": r["breach"],
                     "carry_before": r["before"], "carry_after": r["after"],
                     "tier": r["tier"], "governing_source": r["source"],
                     "channel": ch})
    return {"slate_id": c.slate_id, "cutoff": U(cutoff),
            "entry_count": len(ents), "entries": ents}


def summary_of(c, res):
    rows = res["rows"]
    vc = dict((v, 0) for v in VERDICTS)
    rc = dict((x, 0) for x in REASONS)
    rc["none"] = 0
    sc = dict((x, 0) for x in SOURCES)
    tc = dict((x, 0) for x in TIERS)
    keys = set()
    for r in rows:
        vc[r["verdict"]] += 1
        rc[r["reason"] if r["reason"] else "none"] += 1
        sc[r["source"]] += 1
        tc[r["tier"]] += 1
        for k in r["keys"]:
            keys.add(k)
    return {"slate_id": c.slate_id, "entry_count": len(rows),
            "verdict_counts": vc, "reason_counts": rc,
            "source_counts": sc, "tier_counts": tc,
            "points_total_sum": sum(r["points"] for r in rows),
            "copy_breach_total": sum(r["breach"] for r in rows),
            "carry_cap_hits": len([r for r in rows
                                   if r["after"] == c.carry_cap]),
            "redirected_entries": res["redirected"],
            "materialized_entry_count": len([r for r in rows
                                             if r["standing"]]),
            "distinct_canonical_cards": len(keys),
            "rejected_events": res["rejected"]}


def transcript_of(c, plan):
    return {"slate_id": c.slate_id, "pages_walked": plan["pages"],
            "empty_pages": plan["empties"],
            "preseeded_entries": plan["preseeded"],
            "deferred_operations": plan["deferred"],
            "conflicts_met": len(plan["conflicts"]),
            "conflict_entries": plan["conflicts"],
            "console_operations": plan["console"],
            "api_operations": plan["api"],
            "refusals": plan["refusals"], "journal_seq": plan["seq"],
            "digest": plan["digest"]}


def scenario_of(c, base_rows, res, basis):
    rows = res["rows"]
    vc = dict((v, 0) for v in VERDICTS)
    tc = dict((x, 0) for x in TIERS)
    for r in rows:
        vc[r["verdict"]] += 1
        tc[r["tier"]] += 1
    bmap = dict((r["sid"], r["verdict"]) for r in base_rows)
    smap = dict((r["sid"], r["verdict"]) for r in rows)
    changed = []
    for sid in sorted(set(bmap) | set(smap)):
        if bmap.get(sid, "absent") != smap.get(sid, "absent"):
            changed.append(sid)
    return {"basis": basis, "entry_count": len(rows), "verdict_counts": vc,
            "tier_counts": tc,
            "points_total_sum": sum(r["points"] for r in rows),
            "changed": changed, "changed_count": len(changed)}


def solve(root):
    c = load(root)
    prepare(c)
    c.derived = derive_conventions(c)
    res = run_all(c, c.base_cutoff)
    plan = plan_ops(c, res["rows"], c.base_cutoff)
    out = {"report": report_of(c, res, plan, c.base_cutoff),
           "summary": summary_of(c, res),
           "transcript": transcript_of(c, plan), "plan": plan, "res": res}
    sc = {}
    for name in ("alpha", "beta", "mode"):
        sec = c.scen[name]
        basis = sec["basis"]
        if basis == "cutoff":
            cut = P(sec["legality_cutoff"])
            c.lcache = {}
            r2 = run_all(c, cut)
        elif basis == "source":
            c.lcache = {}
            r2 = run_all(c, c.base_cutoff, drop=sec["withdraw_source"])
        else:
            c.lcache = {}
            r2 = run_all(c, c.base_cutoff, as_fmt=sec["evaluate_as"])
        sc[name] = scenario_of(c, res["rows"], r2, basis)
        sc[name + "_res"] = r2
    out["scen"] = sc
    out["ctx"] = c
    return out


HOST = "127.0.0.1"
PORT = 8814
BASE = "http://%s:%d" % (HOST, PORT)


def _call(method, path, body=None, key=None, match=None):
    url = BASE + path
    data = None
    head = {"X-Arbiter-Channel": "api"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        head["Content-Type"] = "application/json"
    if key:
        head["X-Arbiter-Key"] = key
    if match:
        head["If-Match"] = match
    req = urllib.request.Request(url, data=data, headers=head, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8")
        try:
            return err.code, json.loads(raw)
        except ValueError:
            return err.code, {}


def api(method, path, body=None, key=None, match=None):
    code, payload = _call(method, path, body, key, match)
    if code == 401 and payload.get("refusal"):
        _call("POST", "/renew")
        code, payload = _call(method, path, body, key, match)
    return code, payload


def console(op, entry, fmt, scope, key, match):
    cmd = [sys.executable, SERVICE + "/arbiterctl.py", op,
           "--entry", entry, "--format", fmt, "--scope", scope,
           "--key", key, "--host", HOST, "--port", str(PORT)]
    if match:
        cmd += ["--match", match]
    done = subprocess.run(cmd, capture_output=True, text=True)
    try:
        payload = json.loads(done.stdout.strip() or "{}")
    except ValueError:
        payload = {}
    if payload.get("refusal") == "token_expired":
        _call("POST", "/renew")
        done = subprocess.run(cmd, capture_output=True, text=True)
        try:
            payload = json.loads(done.stdout.strip() or "{}")
        except ValueError:
            payload = {}
    return payload


def start():
    busy = False
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=2) as resp:
            busy = resp.status == 200
    except Exception:
        busy = False
    if busy:
        raise RuntimeError(
            "an arbiter already answers on %s:%d, so this run would record "
            "into a state it did not seed" % (HOST, PORT))
    proc = subprocess.Popen(
        [sys.executable, SERVICE + "/arbiter.py",
         "--seed", DATA + "/registry_seed.json",
         "--host", HOST, "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(400):
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=5) as resp:
                if resp.status == 200:
                    return proc
        except Exception:
            time.sleep(0.05)
    return proc


def walk():
    seen = []
    pages = 0
    empty = 0
    cursor = "p0"
    while cursor:
        code, payload = api("GET", "/entries?cursor=" + cursor)
        if code != 200:
            break
        rows = payload.get("entries", [])
        pages += 1
        if not rows:
            empty += 1
        for row in rows:
            seen.append(row["entry"] if isinstance(row, dict) else row)
        cursor = payload.get("next_cursor")
    return seen, pages, empty


def etag_of(entry):
    code, payload = api("GET", "/entry?id=" + entry)
    if code != 200:
        return None
    return payload.get("etag")


def settle(payload, entry):
    token = payload.get("operation_id")
    if not token:
        return payload, False
    code, done = api("GET", "/operation?id=" + token)
    return done, True


def drive(ctx, rows, plan):
    listed, pages, empty = walk()
    pre = set(ctx.seed["preseeded_entries"])
    grants = admitted_grants(ctx, ctx.base_cutoff)
    tally = {"console": 0, "api": 0, "deferred": 0, "conflicts": []}
    counter = 0
    for row in rows:
        sid = row["sid"]
        fmt = row["fmt"]
        scope = row["source"]
        ops = []
        if sid not in pre:
            ops.append("register")
        ops.append(OP_FOR[row["verdict"]])
        if row["verdict"] == "barred" and row["reason"] == "tier_bar" \
                and row["player"] in grants:
            ops.append("reinstate")
        for op in ops:
            counter += 1
            key = "IK%07d" % counter
            body = {"operation": op, "entry": sid, "format": fmt,
                    "scope": scope}
            if op == "register":
                code, payload = api("POST", "/act", body, key)
                tally["api"] += 1
                continue
            match = etag_of(sid)
            if op in CONSOLE_ONLY:
                payload = console(op, sid, fmt, scope, key, match)
                tally["console"] += 1
            else:
                code, payload = api("POST", "/act", body, key, match)
                tally["api"] += 1
            if payload.get("refusal"):
                if sid not in tally["conflicts"]:
                    tally["conflicts"].append(sid)
                match = etag_of(sid)
                if op in CONSOLE_ONLY:
                    payload = console(op, sid, fmt, scope, key, match)
                else:
                    code, payload = api("POST", "/act", body, key, match)
            payload, parked = settle(payload, sid)
            if parked:
                tally["deferred"] += 1
    tally["pages"] = pages
    tally["empty"] = empty
    tally["listed"] = listed
    return tally


def shape_report(book):
    return book["report"]


def write_out(book, tally, state):
    os.makedirs(OUT, exist_ok=True)
    ids = set(r["submission_id"] for r in book["report"]["entries"])
    transcript = {
        "slate_id": book["report"]["slate_id"],
        "pages_walked": tally["pages"],
        "empty_pages": tally["empty"],
        "preseeded_entries": len([e for e in tally["listed"] if e in ids]),
        "deferred_operations": tally["deferred"],
        "conflicts_met": len(tally["conflicts"]),
        "conflict_entries": sorted(tally["conflicts"]),
        "console_operations": tally["console"],
        "api_operations": tally["api"],
        "refusals": state["refusals"],
        "journal_seq": state["journal_seq"],
        "digest": state["digest"],
    }
    files = [
        ("report.json", book["report"]),
        ("summary.json", book["summary"]),
        ("transcript_summary.json", transcript),
        ("final_state.json", state),
        ("scenario_alpha.json", book["scen"]["alpha"]),
        ("scenario_beta.json", book["scen"]["beta"]),
        ("scenario_mode.json", book["scen"]["mode"]),
    ]
    for name, payload in files:
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")


def observations(c):
    """Adjudications already settled for the closed stages, lane lines dropped."""
    seen = {}
    for name in ("judge_log_a.log", "judge_log_b.log"):
        with open(os.path.join(c.root, name), encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln or "lane=" in ln:
                    continue
                bits = ln.split()
                kv = {}
                for bit in bits[1:]:
                    if "=" in bit:
                        k, v = bit.split("=", 1)
                        kv[k] = v
                sid = kv.get("submission")
                if sid is None:
                    continue
                seen.setdefault(sid, []).append(
                    (kv.get("governed_by"), kv.get("points_cpt"),
                     kv.get("verdict"), kv.get("carry_after")))
    return seen


def settled_observations(c):
    """One adjudication per observed submission: the judge of higher rank at the
    observation's timestamp governs, and equal ranks go to the later timestamp."""
    best = {}
    for name in ("judge_log_a.log", "judge_log_b.log"):
        with open(os.path.join(c.root, name), encoding="utf-8") as fh:
            for ln in fh:
                bits = ln.split()
                if not bits or "lane=" in ln:
                    continue
                kv = dict(bit.split("=", 1) for bit in bits[1:] if "=" in bit)
                sid = kv.get("submission")
                if sid is None:
                    continue
                stamp = P(bits[0])
                rank = rank_at(c, kv.get("judge"), stamp, c.base_cutoff)
                mark = (kv.get("governed_by"), int(kv.get("points_cpt")),
                        kv.get("verdict"), int(kv.get("carry_after")))
                held = best.get(sid)
                if held is None or (rank, stamp) > held[0]:
                    best[sid] = ((rank, stamp), mark)
    return {sid: held[1] for sid, held in best.items()}


def contradicted(c, marks):
    rows = {r["sid"]: r for r in run_all(c, c.base_cutoff)["all"]}
    bad = 0
    for sid, mark in marks.items():
        r = rows.get(sid)
        if r is None or (r["source"], r["points"], r["verdict"], r["after"]) != mark:
            bad += 1
    return bad


def derive_conventions(c):
    """Settle the pre cutover charge order and the ceiling stage by replaying the
    closed stages under every candidate and keeping the one no settled
    adjudication contradicts."""
    marks = settled_observations(c)
    tally = {}
    for order in itertools.permutations(("addendum", "global", "rider")):
        for stage in ("copy", "contribution"):
            c.pre_charge, c.ceiling_at = order, stage
            tally[(order, stage)] = contradicted(c, marks)
    clean = [combo for combo, bad in tally.items() if bad == 0]
    if len(clean) != 1:
        raise RuntimeError("the observations do not single out one convention pair:"
                           " %d candidates contradict none" % len(clean))
    c.pre_charge, c.ceiling_at = clean[0]
    others = [bad for (order, stage), bad in tally.items()
              if stage == c.ceiling_at and order != c.pre_charge]
    other_stage = "contribution" if c.ceiling_at == "copy" else "copy"
    return {"marks": len(marks), "order": c.pre_charge, "ceiling": c.ceiling_at,
            "order_low": min(others), "order_high": max(others),
            "ceiling_other": tally[(c.pre_charge, other_stage)],
            "combos": len(tally)}


def closing_counts(c):
    """The season wide figures the closing message states."""
    cutoff = c.base_cutoff
    merges, splits = identity_plan(c, cutoff)
    pool = [(h["sid"], h["handle"], h["venue"], h["local"], None) for h in c.headers]
    filed_once = set(x[0] for x in pool)
    pool += [(l["sid"], l["handle"], l["venue"], l["local"], P(l["rec"]))
             for l in c.legacy
             if l["season"] == c.season and l["sid"] not in filed_once]
    gap = 0
    moved = 0
    stageless = 0
    for sid, handle, venue, local, given in pool:
        filed = given if given is not None else receipt_instant(c, sid, cutoff)
        if filed is None:
            gap += 1
            continue
        if venue not in c.base_off:
            continue
        inst = utc_from_local(c, venue, PL(local))
        if filed > cutoff:
            continue
        stage = stage_of(c, venue, inst, cutoff)
        if stage is None:
            stageless += 1
            continue
        base = handle_player(c, handle, inst, cutoff)
        if base is None:
            continue
        if route_player(base, inst, merges, splits) != base:
            moved += 1

    subs = assemble(c, cutoff)[0]
    unmatched = 0
    for row in subs:
        for ln in row["lines"]:
            ns = norm_set(ln["set"])
            nm = ln["name"]
            if c.nidx.get((ns, nm)):
                continue
            if any(rename_at(c, c.pr_key[pr], row["eff"], cutoff) == nm
                   for pr in c.by_set.get(ns, [])):
                continue
            unmatched += 1

    close = c.closes[c.open_stage]
    absorbed = 0
    for fmt in FORMATS:
        surv = link_sets(c, fmt, close, cutoff, {})
        absorbed += len([k for k, v in surv.items() if v != k])
    withdrawn = len([r for f in c.links for r in c.links[f] if r["rec"] == "\\N"])

    retracted = 0
    for lst in c.gl.values():
        for rev in lst:
            if not rev.get("retracted"):
                continue
            if P(rev["effective_at"]) <= cutoff and P(rev["recorded_at"]) <= cutoff:
                retracted += 1

    rider_rows = 0
    rider_out = 0
    for lst in c.rider.values():
        for row in lst:
            rider_rows += 1
            if row["eff"] > cutoff or row["rec"] > cutoff:
                continue
            if rank_at(c, row["auth"], row["rec"], cutoff) < 3:
                rider_out += 1

    marks = observations(c)
    clash = len([sid for sid, lst in marks.items() if len(set(lst)) > 1])

    skips = {}
    closures = {}
    for e in c.exc:
        if e["rec"] > cutoff:
            continue
        if e["kind"] == "skip":
            skips.setdefault(e["sid"], set()).add(e["on"])
        else:
            closures.setdefault(e["venue"], set()).add(e["on"])
    admitted = 0
    hushed = 0
    for st in c.standing:
        if st["rec"] > cutoff or st["venue"] not in c.base_off:
            continue
        win = window_of(c, c.open_stage, st["venue"], cutoff)
        if win is None:
            continue
        ws, we = win
        day = st["start"]
        while day <= st["until"]:
            if day.strftime("%a").lower()[:3] != st["wd"][:3].lower():
                day = day + dt.timedelta(days=1)
                continue
            dkey = day.strftime("%Y-%m-%d")
            local = dt.datetime.strptime(dkey + " " + st["local"],
                                         "%Y-%m-%d %H:%M:%S")
            inst = utc_from_local(c, st["venue"], local)
            if ws <= inst < we:
                admitted += 1
                cday = comp_day(c, st["venue"], inst)
                if dkey in skips.get(st["id"], set()) \
                        or cday in closures.get(st["venue"], set()):
                    hushed += 1
            day = day + dt.timedelta(days=7)

    outranked = 0
    for lst in c.amend.values():
        ok = [a for a in lst if a.get("status") == "accepted"
              and P(a["recorded_at"]) <= cutoff and P(a["effective_at"]) <= cutoff]
        if not ok:
            continue
        top = max(int(a["version"]) for a in ok)
        outranked += len([a for a in ok if int(a["version"]) < top])

    return {"gap": gap, "moved": moved, "unmatched": unmatched,
            "absorbed": absorbed, "withdrawn": withdrawn, "retracted": retracted,
            "rider_out": rider_out, "rider_rows": rider_rows, "clash": clash,
            "observed": len(marks), "admitted": admitted, "hushed": hushed,
            "outranked": outranked, "stageless": stageless}


FEED_NAME = {"addendum": "the addendum", "global": "the global feed",
             "rider": "the rider"}


def closing_message(n, derived):
    print("submissions carrying no admitted intake receipt: %d"
          " (intake_journal.log with intake_journal.log.1, read against the"
          " published legality cutoff)" % n["gap"])
    print("submissions held by an entrant other than the handle assignment alone"
          " would name: %d (handle_changes.csv with identity_events.csv)" % n["moved"])
    print("deck lines naming a printing no admitted registry row matches: %d"
          " (deck_lines_01..06.csv and amendments_01..02.jsonl against"
          " printing_registry.csv with card_renames.csv)" % n["unmatched"])
    print("canonical keys losing their identity to an admitted reprint link at the"
          " published close of the open stage: %d (reprint_links.tsv with"
          " printing_registry.csv)" % n["absorbed"])
    print("reprint links withdrawn by the token in place of a recorded instant: %d"
          " (reprint_links.tsv)" % n["withdrawn"])
    print("restriction revisions retracted among those otherwise admitted: %d"
          " (global_restrictions_01..04.jsonl)" % n["retracted"])
    print("rider rows turned away for an authorising judge of too low a rank:"
          " %d of %d (event_rider.tsv against authority_roster.csv)"
          % (n["rider_out"], n["rider_rows"]))
    print("submissions carrying observations that disagree with each other:"
          " %d of %d (judge_log_a.log with judge_log_b.log)"
          % (n["clash"], n["observed"]))
    print("standing occurrences the open stage window admits: %d, of which an"
          " exception suppresses %d (standing_entries.csv with"
          " entry_exceptions.csv and stage_calendar.csv)"
          % (n["admitted"], n["hushed"]))
    print("accepted amendments outranked by a higher accepted version: %d"
          " (amendments_01..02.jsonl)" % n["outranked"])
    print("submissions falling in no governing stage window: %d"
          " (stage_calendar.csv with venue_clocks.ini)" % n["stageless"])
    first, second, third = (FEED_NAME[x] for x in derived["order"])
    print("convention one, the pre cutover point charge order: %s, then %s, then"
          " %s. The observations settle it: the closed stages were replayed under"
          " all six orders, and against the %d adjudications the judge logs settle"
          " (where two observations of a submission disagree, the judge of higher"
          " rank at the observation's timestamp in authority_roster.csv governs,"
          " and equal ranks go to the later timestamp) this order is the only one"
          " that contradicts none; the other five contradict between %d and %d."
          % (first, second, third, derived["marks"], derived["order_low"],
             derived["order_high"]))
    if derived["ceiling"] == "copy":
        chosen = "on a single copy, before the counted copies multiply it"
        other = "clamping the whole card contribution instead"
    else:
        chosen = "on the whole card contribution, after the counted copies multiply it"
        other = "clamping a single copy instead"
    print("convention two, where the charge ceiling binds: %s. The observations"
          " settle it: under the same replay %s contradicts %d of those"
          " adjudications, while this reading contradicts none."
          % (chosen, other, derived["ceiling_other"]))


def main():
    book = solve(DATA)
    proc = start()
    try:
        tally = drive(book["ctx"], book["res"]["rows"], book["plan"])
        code, state = api("GET", "/state")
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    write_out(book, tally, state)
    closing_message(closing_counts(book["ctx"]), book["ctx"].derived)


if __name__ == "__main__":
    main()
