#!/usr/bin/env python3
"""Derive the winter demand-response reports from one season extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Every rule, unit and output field follows the data contract in schema.md.
All reported figures are exact integers: energy in ticks, money in cents,
ratios in basis points.  Binary floating point is never used.
"""

import configparser
import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from operator import add

LABELS = ("SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR")


def rhu(num, den):
    """num/den for non-negative integers, rounded half up."""
    return (2 * num + den) // (2 * den)


# --------------------------------------------------------------------------- #
# input
# --------------------------------------------------------------------------- #

def read_extract(data_dir):
    ex = {"rows": {}, "dq": defaultdict(int)}

    def path(name):
        return os.path.join(data_dir, name)

    cfg = configparser.ConfigParser()
    with open(path("program.ini"), encoding="utf-8") as fh:
        cfg.read_file(fh)
    wh = int(cfg["units"]["wh_per_tick"])
    ex["wh_per_tick"] = wh
    ex["mcc"] = int(cfg["units"]["millicents_per_cent"])
    # configparser lower-cases option names; codes in the other files are upper case.
    region_of = {code.upper(): name for code, name in cfg["region_codes"].items()}
    segment_of = {code.upper(): name for code, name in cfg["segment_codes"].items()}
    ex["regions"] = sorted(set(region_of.values()))
    ex["segments"] = sorted(set(segment_of.values()))
    ex["seg_index"] = {name: i for i, name in enumerate(ex["segments"])}

    with open(path("events.json"), encoding="utf-8") as fh:
        events = json.load(fh)
    ex["rows"]["events.json"] = len(events)
    ex["events"] = {e["event_id"]: e for e in events}
    ex["event_ids"] = sorted(ex["events"])

    sites = {}
    count = 0
    with open(path("sites.csv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            count += 1
            region = region_of.get(row["region_code"].upper())
            if region is None:
                ex["dq"]["unknown_region_site_rows"] += 1
                continue
            sites[(row["event_id"], row["site_id"])] = {
                "region": region,
                "segment": segment_of[row["segment_code"].upper()],
                "beneficiary_id": row["beneficiary_id"],
                "critical": row["critical"] == "Y",
            }
    ex["rows"]["sites.csv"] = count
    ex["sites"] = sites

    state = {}
    count = 0
    with open(path("site_state.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            count += 1
            obj = json.loads(line)
            key = (obj["event_id"], obj["site_id"])
            if key in sites:  # lines of unknown-region site rows are skipped
                state[key] = obj
    ex["rows"]["site_state.jsonl"] = count
    ex["state"] = state

    waivers = {}
    count = 0
    with open(path("continuity_waivers.csv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            count += 1
            key = (row["event_id"], row["site_id"])
            if key not in sites:
                continue
            signed = (row["waiver_signed"] or "").strip()
            if signed == "":
                ex["dq"]["waiver_signed_missing"] += 1
            waivers[key] = {
                "pending": row["routine_certificate_pending"] == "Y",
                "status": row["waiver_status"],
                "signed": signed == "Y",
            }
    ex["rows"]["continuity_waivers.csv"] = count
    ex["waivers"] = waivers

    cards = {}
    count = 0
    for card in ET.parse(path("rate_cards.xml")).getroot().findall("card"):
        count += 1
        key = (card.get("event"), card.get("site"))
        if key not in sites:
            continue
        cards[key] = (int(card.findtext("base")), int(card.findtext("cap")))
    ex["rows"]["rate_cards.xml"] = count
    ex["cards"] = cards

    weights = {}
    count = 0
    with open(path("recipient_weights.tsv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            count += 1
            key = (row["event_id"], row["site_id"])
            if key in sites:
                weights[key] = int(row["grant_weight"])
    ex["rows"]["recipient_weights.tsv"] = count
    ex["weights"] = weights

    offers = {}
    count = 0
    with open(path("offers.csv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            count += 1
            key = (row["event_id"], row["site_id"])
            orphan = key not in sites
            offers[row["offer_id"]] = {
                "event_id": row["event_id"],
                "site_id": row["site_id"],
                "bid": int(row["bid_cost_cents"]),
                "orphan": orphan,
            }
            if orphan:
                ex["dq"]["orphan_offer_rows"] += 1
            elif not state[key]["dispatch_authorized"]:
                ex["dq"]["ineligible_offer_count"] += 1
    ex["rows"]["offers.csv"] = count
    ex["offers"] = offers

    profiles = defaultdict(dict)
    count = 0
    with open(path("profiles.tsv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            count += 1
            offer = offers.get(row["offer_id"])
            if offer is None:
                ex["dq"]["orphan_profile_rows"] += 1
                continue
            interval = int(row["interval"])
            if not 1 <= interval <= ex["events"][offer["event_id"]]["interval_count"]:
                ex["dq"]["out_of_range_profile_rows"] += 1
                continue
            kept = profiles[row["offer_id"]]
            if interval in kept:
                ex["dq"]["duplicate_profile_rows"] += 1
                continue
            # Wh becomes ticks the moment it is read, before any summation.
            kept[interval] = (rhu(int(row["relief_wh"]), wh), rhu(int(row["recovery_wh"]), wh))
    ex["rows"]["profiles.tsv"] = count
    ex["profiles"] = profiles

    targets = {}
    count = 0
    with open(path("targets.tsv"), newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            count += 1
            key = (row["event_id"], region_of[row["region_code"].upper()], int(row["interval"]))
            targets[key] = (rhu(int(row["target_wh"]), wh), int(row["shortfall_weight"]))
    ex["rows"]["targets.tsv"] = count
    ex["targets"] = targets

    limits = {}
    count = 0
    with open(path("feeder_limits.txt"), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            count += 1
            key = (line[0:10].strip(), region_of[line[10:14].strip().upper()], int(line[14:17]))
            limits[key] = (rhu(int(line[17:27]), wh), rhu(int(line[27:37]), wh))
    ex["rows"]["feeder_limits.txt"] = count
    ex["limits"] = limits

    floors = {}
    with open(path("segment_floors.json"), encoding="utf-8") as fh:
        entries = json.load(fh)["floors"]
    ex["rows"]["segment_floors.json"] = len(entries)
    for entry in entries:
        key = (
            entry["event_id"],
            region_of[entry["region_code"].upper()],
            segment_of[entry["segment_code"].upper()],
        )
        floors[key] = (rhu(int(entry["floor_wh"]), wh), int(entry["priority_weight"]))
    ex["floors"] = floors

    pools = {}
    count = 0
    with open(path("pools.txt"), encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            count += 1
            pools[(line[0:10].strip(), region_of[line[10:14].strip().upper()])] = int(line[14:26])
    ex["rows"]["pools.txt"] = count
    ex["pools"] = pools

    return ex


# --------------------------------------------------------------------------- #
# optimisation (section 5)
# --------------------------------------------------------------------------- #

# An option is (offer_id, relief ticks per interval, recovery ticks per interval,
# bid cents, segment index, total relief ticks).  A folded option carries a
# seventh field: how many offers of its site it stands for.


def fold(group):
    """Fold one site's options into classes the objective cannot tell apart.

    Two offers of a site agreeing on relief, recovery, bid and segment
    contribute identically to feasibility and to all five components, so only
    how many of them there are matters.  Of two otherwise equal portfolios the
    greater offer id wins, and replacing one member of a set by a greater one
    always raises its sorted tuple, so the class keeps its greatest id as the
    representative.  Folding keeps the tie count exact while never enumerating
    interchangeable portfolios separately.
    """
    classes = {}
    for oid, rel, rec, bid, seg, total in group:
        key = (rel, rec, bid, seg)
        entry = classes.get(key)
        if entry is None:
            classes[key] = [oid, rel, rec, bid, seg, total, 1]
            continue
        entry[6] += 1
        if oid > entry[0]:
            entry[0] = oid
    return sorted(tuple(entry) for entry in classes.values())


def _suffix_maxima(groups, ic, nseg):
    """The most relief, per interval and per segment, that later sites can add."""
    n = len(groups)
    suf_rel = [[0] * ic for _ in range(n + 1)]
    suf_seg = [[0] * nseg for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        group = groups[i]
        later = suf_rel[i + 1]
        row = suf_rel[i]
        for t in range(ic):
            row[t] = later[t] + max(opt[1][t] for opt in group)
        suf_seg[i] = list(suf_seg[i + 1])
        # Every option of a site carries that site's segment.
        suf_seg[i][group[0][4]] += max(opt[5] for opt in group)
    return suf_rel, suf_seg


def _multipliers(groups, ctx):
    """Weights folding the five components into one integer objective.

    Each weight exceeds every total the components below it can reach together,
    so comparing the single integer is exactly the lexicographic comparison of
    section 5.  One integer is what lets a bound weigh relief against what
    buying that relief costs; comparing the components one at a time cannot.
    """
    ic = ctx["ic"]
    target = ctx["target"]
    relceil = ctx["relceil"]
    recceil = ctx["recceil"]
    peak_rel = [0] * ic
    peak_rec = [0] * ic
    max_bid = 0
    for group in groups:
        for t in range(ic):
            peak_rel[t] += max(opt[1][t] for opt in group)
            peak_rec[t] += max(opt[2][t] for opt in group)
        max_bid += max(opt[3] for opt in group)
    # Upper bounds on components 5, 4, 3 and 2: one offer per site at most, and
    # no interval can exceed its ceiling.
    ub5 = len(groups)
    ub4 = sum(max(0, min(relceil[t], peak_rel[t]) - target[t]) for t in range(ic))
    ub3 = ctx["cost_weight"] * max_bid + ctx["recovery_weight"] * sum(
        min(recceil[t], peak_rec[t]) for t in range(ic)
    )
    ub2 = sum(priority * floor_ticks for floor_ticks, priority in ctx["floors"])
    m4 = ub5 + 1
    m3 = m4 * (ub4 + 1)
    m2 = m3 * (ub3 + 1)
    m1 = m2 * (ub2 + 1)
    return m1, m2, m3, m4


def _patterns(groups, ctx, mult):
    """Corner multipliers that put a price on relief for the search.

    An interval's shortfall, max(0, target - relief), is the greater of two
    linear functions of the relief, and a segment's floor deficit behaves the
    same way.  Fixing one of the two slopes for every interval and every
    segment therefore leaves a surrogate that is linear in the relief and never
    exceeds the objective.  Being linear it is separable, so its least value
    over all portfolios is found one site at a time, and that value bounds the
    optimum from below.  The search uses the greatest of those bounds, which is
    the Lagrangian dual taken over the corners of the multipliers.

    This is what the two bounds above cannot do.  Both hand out the relief of
    the undecided sites as if it were free, which says almost nothing when what
    relief is worth buying is the whole question.  Here relief carries its
    price, and while no ceiling binds the bound is sharp enough to confirm the
    optimum outright.

    Returns (constants, option weights, suffix minima), one entry per slope
    choice, or None when there are more choices than they can pay for.
    """
    ic = ctx["ic"]
    nseg = ctx["nseg"]
    target = ctx["target"]
    sw = ctx["sw"]
    floors = ctx["floors"]
    m1, m2, m3, m4 = mult

    # A set bit prices that interval as reaching its target, or that segment as
    # reaching its floor, so the component is charged from above instead.
    if (1 << ic) * (1 << nseg) <= 512:
        choices = [(p, q) for p in range(1 << ic) for q in range(1 << nseg)]
    else:
        # Too many corners to price them all.  The all-clear corner is kept
        # because it is the objective itself while no interval passes its
        # target, and with it the all-set corner and every single-bit one.
        choices = [(0, 0), ((1 << ic) - 1, (1 << nseg) - 1)]
        choices += [(1 << t, 0) for t in range(ic)]
        choices += [(0, 1 << s) for s in range(nseg)]
    count = len(choices)
    consts = []
    for p, q in choices:
        const = 0
        for t in range(ic):
            if p >> t & 1:
                const -= m4 * target[t]
            else:
                const += m1 * sw[t] * target[t]
        for s in range(nseg):
            if not (q >> s & 1):
                const += m2 * floors[s][1] * floors[s][0]
        consts.append(const)

    weights = []
    for group in groups:
        rows = []
        for opt in group:
            rel = opt[1]
            seg = opt[4]
            priority = floors[seg][1]
            row = []
            for p, q in choices:
                value = opt[7]
                for t in range(ic):
                    if p >> t & 1:
                        value += m4 * rel[t]
                    else:
                        value -= m1 * sw[t] * rel[t]
                if not (q >> seg & 1):
                    value -= m2 * priority * opt[5]
                row.append(value)
            rows.append(row)
        weights.append(rows)

    n = len(groups)
    suffix = [[0] * count for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        later = suffix[i + 1]
        row = suffix[i]
        rows = weights[i]
        for k in range(count):
            least = 0  # leaving the site out costs nothing and earns nothing
            for option in rows:
                if option[k] < least:
                    least = option[k]
            row[k] = later[k] + least
    # The bound is one addition per corner, so fold the constants in now.
    combined = [[consts[k] + row[k] for k in range(count)] for row in suffix]
    return weights, combined


def _bounds(ctx, mult):
    """Return (exact, optimistic) scalarised value functions.

    `exact` scores a whole portfolio.  `optimistic` scores a prefix with a
    lower bound over every completion of it, so a prefix scoring worse than an
    achievable value can reach neither the optimum nor a portfolio tied with
    it.  It is the greater of two lower bounds, which is itself one.

    The first bound takes the components independently: relief only grows (so
    overdelivery and the offer count only grow), bids and recovery are
    non-negative (so the blended cost only grows), and the shortfall and floor
    deficit are computed as if every undecided site added its greatest relief,
    capped by the ceiling.  It is the one that bites when the ceilings are
    tight, since it is the only one that knows them.

    The second couples relief with its price.  Relief beyond the remaining
    deficit closes no shortfall, so an undecided site is credited only
    min(deficit, relief) per interval while being charged its whole bid and
    recovery.  Once the deficit is closed no site can earn a credit, the cost
    alone decides, and the search stops descending instead of enumerating the
    portfolios that merely overdeliver.

    `_patterns` supplies the third and strongest bound directly to the search.
    """
    ic = ctx["ic"]
    nseg = ctx["nseg"]
    target = ctx["target"]
    sw = ctx["sw"]
    relceil = ctx["relceil"]
    recceil = ctx["recceil"]
    floors = ctx["floors"]
    rw = ctx["recovery_weight"]
    m1, m2, m3, m4 = mult
    irange = range(ic)
    srange = range(nseg)

    def exact(rel, rec, seg, cost, cnt):
        short = 0
        over = 0
        for t in irange:
            got = rel[t]
            tgt = target[t]
            if tgt > got:
                short += sw[t] * (tgt - got)
            elif got > tgt:
                over += got - tgt
        deficit = 0
        for s in srange:
            floor_ticks, priority = floors[s]
            if floor_ticks > seg[s]:
                deficit += priority * (floor_ticks - seg[s])
        return m1 * short + m2 * deficit + m3 * (cost + rw * sum(rec)) + m4 * over + cnt

    def optimistic(rel, rec, seg, cost, cnt, groups, i, sr, ss, limit):
        short = 0
        over = 0
        reach_short = 0
        for t in irange:
            got = rel[t]
            tgt = target[t]
            if tgt > got:
                short += sw[t] * (tgt - got)
            elif got > tgt:
                over += got - tgt
            reach = got + sr[t]
            if reach > relceil[t]:
                reach = relceil[t]
            if tgt > reach:
                reach_short += sw[t] * (tgt - reach)
        deficit = 0
        reach_deficit = 0
        for s in srange:
            floor_ticks, priority = floors[s]
            if floor_ticks > seg[s]:
                deficit += priority * (floor_ticks - seg[s])
            room = seg[s] + ss[s]
            if floor_ticks > room:
                reach_deficit += priority * (floor_ticks - room)
        base = m3 * (cost + rw * sum(rec)) + m4 * over + cnt
        best = m1 * reach_short + m2 * reach_deficit + base
        if limit is not None and best > limit:
            return best
        if not short and not deficit:
            return best
        second = m1 * short + m2 * deficit + base
        for j in range(i, len(groups)):
            gain = 0  # leaving the site out earns nothing and costs nothing
            for opt in groups[j]:
                orel = opt[1]
                orec = opt[2]
                blocked = False
                credit = 0
                for t in irange:
                    if rel[t] + orel[t] > relceil[t] or rec[t] + orec[t] > recceil[t]:
                        blocked = True
                        break
                    tgt = target[t]
                    got = rel[t]
                    if tgt > got:
                        room = tgt - got
                        r = orel[t]
                        credit += sw[t] * (r if r < room else room)
                if blocked:
                    continue
                value = opt[7] - m1 * credit
                floor_ticks, priority = floors[opt[4]]
                if priority and floor_ticks > seg[opt[4]]:
                    room = floor_ticks - seg[opt[4]]
                    total = opt[5]
                    value -= m2 * priority * (total if total < room else room)
                if value < gain:
                    gain = value
            second += gain
        return second if second > best else best

    return exact, optimistic


def _beam(groups, ctx, mult, width):
    """Value of the best portfolio a width-limited layered sweep finds.

    Every surviving state is a real portfolio, so the value returned is always
    achievable and therefore a sound incumbent for the exact search.  Keeping
    the width finite bounds the memory, which a full layered sweep cannot do.
    """
    ic = ctx["ic"]
    nseg = ctx["nseg"]
    relceil = ctx["relceil"]
    recceil = ctx["recceil"]
    cost_weight = ctx["cost_weight"]
    exact, _ = _bounds(ctx, mult)

    states = {((0,) * ic, (0,) * ic, (0,) * nseg): (0, 0)}
    for group in groups:
        new = {}
        for key, pair in states.items():
            rel, rec, seg = key
            cost, cnt = pair
            old = new.get(key)  # skipping this site keeps the state as it is
            if old is None or pair < old:
                new[key] = pair
            for opt in group:
                orel = opt[1]
                orec = opt[2]
                n_rel = tuple(rel[t] + orel[t] for t in range(ic))
                if any(n_rel[t] > relceil[t] for t in range(ic)):
                    continue
                n_rec = tuple(rec[t] + orec[t] for t in range(ic))
                if any(n_rec[t] > recceil[t] for t in range(ic)):
                    continue
                s = opt[4]
                n_seg = tuple(seg[k] + (opt[5] if k == s else 0) for k in range(nseg))
                n_key = (n_rel, n_rec, n_seg)
                n_pair = (cost + cost_weight * opt[3], cnt + 1)
                old = new.get(n_key)
                if old is None or n_pair < old:
                    new[n_key] = n_pair
        if len(new) > width:
            ranked = sorted(
                new.items(),
                key=lambda kv: exact(kv[0][0], kv[0][1], kv[0][2], kv[1][0], kv[1][1]),
            )
            new = dict(ranked[:width])
        states = new

    best = None
    for (rel, rec, seg), (cost, cnt) in states.items():
        current = exact(rel, rec, seg, cost, cnt)
        if best is None or current < best:
            best = current
    return best


def _greedy(groups, ctx, mult):
    """Value of the portfolio that decides every site on its own.

    Each site takes the option that pulls the linear surrogate down most,
    ignoring the others, and options are then dropped until the feeder ceilings
    hold.  The result is a real portfolio, so its value is a sound incumbent,
    and in the regime where the surrogate is the objective it is already the
    optimum, which is what lets the third bound close the search at once.
    """
    ic = ctx["ic"]
    nseg = ctx["nseg"]
    sw = ctx["sw"]
    floors = ctx["floors"]
    relceil = ctx["relceil"]
    recceil = ctx["recceil"]
    cost_weight = ctx["cost_weight"]
    m1, m2 = mult[0], mult[1]
    exact, _ = _bounds(ctx, mult)
    irange = range(ic)

    picks = []
    for group in groups:
        gain = 0
        choice = None
        for opt in group:
            orel = opt[1]
            credit = 0
            for t in irange:
                credit += sw[t] * orel[t]
            value = opt[7] - m1 * credit
            priority = floors[opt[4]][1]
            if priority:
                value -= m2 * priority * opt[5]
            if value < gain:
                gain = value
                choice = opt
        picks.append(choice)

    while True:
        rel = [0] * ic
        rec = [0] * ic
        for opt in picks:
            if opt is None:
                continue
            for t in irange:
                rel[t] += opt[1][t]
                rec[t] += opt[2][t]
        hot = None
        for t in irange:
            if rel[t] > relceil[t] or rec[t] > recceil[t]:
                hot = t
                break
        if hot is None:
            break
        drop = None
        for k, opt in enumerate(picks):
            if opt is None:
                continue
            load = opt[1][hot] + opt[2][hot]
            if drop is None or load > drop[0]:
                drop = (load, k)
        if drop is None:
            break  # nothing left to drop: the empty portfolio is always feasible
        picks[drop[1]] = None

    rel = [0] * ic
    rec = [0] * ic
    seg = [0] * nseg
    cost = 0
    cnt = 0
    for opt in picks:
        if opt is None:
            continue
        for t in irange:
            rel[t] += opt[1][t]
            rec[t] += opt[2][t]
        seg[opt[4]] += opt[5]
        cost += cost_weight * opt[3]
        cnt += 1
    return exact(rel, rec, seg, cost, cnt)


def _solve(groups, ctx, mult, patterns, incumbent):
    """Exact depth-first branch and bound over portfolios.

    Returns (best value, how many portfolios reach it, the greatest offer-id set
    among them).  Only the current path is held, so the memory is proportional
    to the number of sites however many portfolios there are.  Pruning is
    strict, so every portfolio tied at the best value is still visited and both
    the tie count and the greatest-identifier choice stay exact.
    """
    ic = ctx["ic"]
    nseg = ctx["nseg"]
    relceil = ctx["relceil"]
    recceil = ctx["recceil"]
    cost_weight = ctx["cost_weight"]
    exact, optimistic = _bounds(ctx, mult)
    suf_rel, suf_seg = _suffix_maxima(groups, ic, nseg)
    corner = patterns[1] if patterns is not None else None
    n = len(groups)
    irange = range(ic)

    rel = [0] * ic
    rec = [0] * ic
    seg = [0] * nseg
    chosen = []
    # One running total per corner, pushed and popped with the path.
    priced = None if corner is None else [[0] * len(corner[0])]
    state = {"best": incumbent, "count": 0, "ids": ()}

    def visit(i, cost, cnt, folds):
        if i == n:
            value = exact(rel, rec, seg, cost, cnt)
            best = state["best"]
            ids = tuple(sorted(chosen))
            if best is None or value < best:
                state["best"] = value
                state["count"] = folds
                state["ids"] = ids
            elif value == best:
                state["count"] += folds
                if ids > state["ids"]:
                    state["ids"] = ids
            return
        best = state["best"]
        if best is not None:
            if corner is not None and max(map(add, priced[-1], corner[i])) > best:
                return
            bound = optimistic(
                rel, rec, seg, cost, cnt, groups, i, suf_rel[i], suf_seg[i], best
            )
            if bound > best:
                return
        for opt in groups[i]:
            orel = opt[1]
            orec = opt[2]
            feasible = True
            for t in irange:
                if rel[t] + orel[t] > relceil[t] or rec[t] + orec[t] > recceil[t]:
                    feasible = False
                    break
            if not feasible:
                continue
            for t in irange:
                rel[t] += orel[t]
                rec[t] += orec[t]
            seg[opt[4]] += opt[5]
            chosen.append(opt[0])
            if corner is not None:
                priced.append(list(map(add, priced[-1], opt[8])))
            visit(i + 1, cost + cost_weight * opt[3], cnt + 1, folds * opt[6])
            if corner is not None:
                priced.pop()
            chosen.pop()
            seg[opt[4]] -= opt[5]
            for t in irange:
                rel[t] -= orel[t]
                rec[t] -= orec[t]
        visit(i + 1, cost, cnt, folds)  # choosing no offer at this site

    visit(0, 0, 0, 1)
    return state["best"], state["count"], state["ids"]


def optimise(groups, ctx):
    """Return (selected offer ids ascending, portfolios tied at the best value)."""
    folded = [fold(group) for group in groups]
    mult = _multipliers(folded, ctx)
    m3 = mult[2]
    cost_weight = ctx["cost_weight"]
    recovery_weight = ctx["recovery_weight"]
    # Field 7: what choosing this option adds to components 3 and 5.
    folded = [
        tuple(
            opt + (m3 * (cost_weight * opt[3] + recovery_weight * sum(opt[2])) + 1,)
            for opt in group
        )
        for group in folded
    ]
    # Sites offering the most relief go first: they prune the most.  Inside a
    # site the largest offer comes first, which meets good portfolios early.
    folded.sort(key=lambda g: (-max(opt[5] for opt in g), g))
    folded = [tuple(sorted(group, key=lambda opt: (-opt[5], opt[0]))) for group in folded]
    patterns = _patterns(folded, ctx, mult)
    # Field 8: the option's weight under every corner of the price bound.
    weights = patterns[0]
    folded = [
        tuple(opt + (weights[i][j],) for j, opt in enumerate(group))
        for i, group in enumerate(folded)
    ]
    space = 1
    for group in folded:
        space *= len(group) + 1
    incumbent = _greedy(folded, ctx, mult)
    if space > 5000:
        for width in (1, 32, 512):
            found = _beam(folded, ctx, mult, width)
            if incumbent is None or found < incumbent:
                incumbent = found
    _, count, ids = _solve(folded, ctx, mult, patterns, incumbent)
    return ids, count


# --------------------------------------------------------------------------- #
# grants (section 7)
# --------------------------------------------------------------------------- #

def apportion(funded, weights):
    """Largest-remainder share-out of `funded` cents over {beneficiary: weight}.

    Returns (grants, allocated, unallocated, residual, residual_tie, unallocated_pool).
    """
    total = sum(weights.values())
    if total == 0:
        return {}, 0, funded, 0, False, True
    positive = [ben for ben, w in weights.items() if w > 0]
    grants = {}
    remainders = {}
    allocated = 0
    for ben in positive:
        share = funded * weights[ben]
        grants[ben] = share // total
        remainders[ben] = share % total
        allocated += grants[ben]
    residual = funded - allocated
    # Decreasing remainder; equal remainders are served greatest identifier first.
    order = sorted(positive, reverse=True)
    order.sort(key=lambda ben: remainders[ben], reverse=True)
    for ben in order[:residual]:
        grants[ben] += 1
    seen = set()
    tie = False
    for ben in positive:
        rem = remainders[ben]
        if rem == 0:
            continue
        if rem in seen:
            tie = True
            break
        seen.add(rem)
    return grants, funded, 0, residual, tie, False


# --------------------------------------------------------------------------- #
# derivation
# --------------------------------------------------------------------------- #

def build(ex):
    wh = ex["wh_per_tick"]
    mcc = ex["mcc"]
    seg_index = ex["seg_index"]
    segments = ex["segments"]
    nseg = len(segments)

    labels = {}
    for key, info in ex["sites"].items():
        st = ex["state"][key]
        wv = ex["waivers"].get(key, {"pending": False, "status": "NONE", "signed": False})
        valid_waiver = (
            wv["status"] == "VALID"
            and wv["signed"]
            and info["critical"]
            and info["segment"] == "public"
        )
        if st["safety_hold"]:
            label = "SAFETY_HOLD"
        elif st["cooldown"]:
            label = "COOLDOWN"
        elif wv["pending"] and valid_waiver:
            label = "CONTINUITY_WAIVED"
        elif wv["pending"]:
            label = "CERTIFICATE_PENDING"
        else:
            label = "CLEAR"
        labels[key] = label

    rows_by_er = defaultdict(list)
    for key, info in ex["sites"].items():
        rows_by_er[(key[0], info["region"])].append(key)

    candidates = defaultdict(lambda: defaultdict(list))
    for oid, offer in ex["offers"].items():
        if offer["orphan"]:
            continue
        key = (offer["event_id"], offer["site_id"])
        if not ex["state"][key]["dispatch_authorized"]:
            continue
        info = ex["sites"][key]
        ic = ex["events"][offer["event_id"]]["interval_count"]
        prof = ex["profiles"].get(oid, {})
        rel = tuple(prof.get(t, (0, 0))[0] for t in range(1, ic + 1))
        rec = tuple(prof.get(t, (0, 0))[1] for t in range(1, ic + 1))
        candidates[(offer["event_id"], info["region"])][key].append(
            (oid, rel, rec, offer["bid"], seg_index[info["segment"]], sum(rel))
        )

    results = {}
    audit = {
        "cap_binding_count": 0,
        "residual_cents": 0,
        "residual_tie_pool_count": 0,
        "tie_decisions": [],
    }
    dq = ex["dq"]

    for eid in ex["event_ids"]:
        event = ex["events"][eid]
        ic = event["interval_count"]
        uplift = event["uplift_millicents_per_kwh"]
        for region in ex["regions"]:
            er = (eid, region)
            target = []
            sw = []
            relceil = []
            recceil = []
            for t in range(1, ic + 1):
                tt, weight = ex["targets"][(eid, region, t)]
                target.append(tt)
                sw.append(weight)
                rc, vc = ex["limits"][(eid, region, t)]
                relceil.append(rc)
                recceil.append(vc)

            floors = []
            for name in segments:
                floor_ticks, priority = ex["floors"].get((eid, region, name), (0, 0))
                floors.append((floor_ticks, priority))
                if floor_ticks == 0:
                    dq["zero_floor_count"] += 1

            by_site = candidates.get(er, {})
            groups = [tuple(sorted(opts)) for opts in by_site.values()]
            candidate_count = sum(len(g) for g in groups)
            if candidate_count == 0:
                dq["empty_candidate_groups"] += 1

            selected, tied = optimise(
                groups,
                {
                    "ic": ic,
                    "nseg": nseg,
                    "target": target,
                    "sw": sw,
                    "relceil": relceil,
                    "recceil": recceil,
                    "floors": floors,
                    "cost_weight": event["objective"]["cost_weight"],
                    "recovery_weight": event["objective"]["recovery_weight"],
                },
            )
            if tied >= 2:
                audit["tie_decisions"].append(
                    {
                        "event_id": eid,
                        "region": region,
                        "selected_offer_ids": list(selected),
                        "tied_portfolio_count": tied,
                    }
                )

            option_of = {opt[0]: opt for group in groups for opt in group}
            relief = [0] * ic
            recovery = [0] * ic
            bid_cents = 0
            credit_cents = 0
            seg_stats = {
                name: {"offers": [], "relief": 0, "recovery": 0, "bid": 0, "credit": 0}
                for name in segments
            }
            for oid in selected:
                opt = option_of[oid]
                offer = ex["offers"][oid]
                key = (offer["event_id"], offer["site_id"])
                for t in range(ic):
                    relief[t] += opt[1][t]
                    recovery[t] += opt[2][t]
                bid_cents += opt[3]
                base, cap = ex["cards"][key]
                rate = base + uplift
                if rate > cap:
                    audit["cap_binding_count"] += 1
                    rate = cap
                credit = rhu(opt[5] * wh * rate, 1000 * mcc)
                credit_cents += credit
                stats = seg_stats[ex["sites"][key]["segment"]]
                stats["offers"].append(oid)
                stats["relief"] += opt[5]
                stats["recovery"] += sum(opt[2])
                stats["bid"] += opt[3]
                stats["credit"] += credit

            pool = ex["pools"].get(er, 0)
            funded = max(0, pool - credit_cents)
            weights = defaultdict(int)
            for key in rows_by_er.get(er, ()):
                if key not in ex["weights"]:
                    continue
                weight = ex["weights"][key]
                if labels[key] == "CONTINUITY_WAIVED":
                    weight *= 2
                weights[ex["sites"][key]["beneficiary_id"]] += weight
            grants, allocated, unallocated, residual, tie, unalloc = apportion(funded, weights)
            audit["residual_cents"] += residual
            if tie:
                audit["residual_tie_pool_count"] += 1
            if unalloc:
                dq["unallocated_pool_count"] += 1

            counts = dict.fromkeys(LABELS, 0)
            for key in rows_by_er.get(er, ()):
                counts[labels[key]] += 1

            results[er] = {
                "candidate_offer_count": candidate_count,
                "selected": selected,
                "relief": relief,
                "recovery": recovery,
                "target": target,
                "bid_cents": bid_cents,
                "credit_cents": credit_cents,
                "pool": pool,
                "funded": funded,
                "allocated": allocated,
                "unallocated": unallocated,
                "grants": grants,
                "counts": counts,
                "segments": seg_stats,
                "floors": {name: floors[seg_index[name]][0] for name in segments},
            }

    return results, audit, labels


# --------------------------------------------------------------------------- #
# reporting (section 8)
# --------------------------------------------------------------------------- #

REGION_TOTAL_KEYS = (
    "event_count",
    "candidate_offer_count",
    "selected_offer_count",
    "relief_ticks",
    "recovery_ticks",
    "shortfall_ticks",
    "overdelivery_ticks",
    "bid_cost_cents",
    "credit_cents",
    "grant_pool_cents",
    "grant_funded_cents",
    "grant_allocated_cents",
    "grant_unallocated_cents",
)

SEGMENT_TOTAL_KEYS = (
    "selected_offer_count",
    "relief_ticks",
    "recovery_ticks",
    "bid_cost_cents",
    "credit_cents",
    "floor_ticks",
)


def write_json(out_dir, name, obj):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, indent=1)
        fh.write("\n")


def emit(ex, results, audit, labels, out_dir):
    grand = defaultdict(int)
    summary_regions = {}
    summary_segments = {}

    for region in ex["regions"]:
        events_out = []
        totals = defaultdict(int)
        for eid in ex["event_ids"]:
            res = results[(eid, region)]
            intervals = []
            for t in range(len(res["relief"])):
                relief = res["relief"][t]
                target = res["target"][t]
                intervals.append(
                    {
                        "interval": t + 1,
                        "overdelivery_ticks": max(0, relief - target),
                        "recovery_ticks": res["recovery"][t],
                        "relief_ticks": relief,
                        "shortfall_ticks": max(0, target - relief),
                        "target_ticks": target,
                    }
                )
            events_out.append(
                {
                    "bid_cost_cents": res["bid_cents"],
                    "candidate_offer_count": res["candidate_offer_count"],
                    "compliance_counts": res["counts"],
                    "credit_cents": res["credit_cents"],
                    "event_id": eid,
                    "grant_allocated_cents": res["allocated"],
                    "grant_funded_cents": res["funded"],
                    "grant_pool_cents": res["pool"],
                    "grant_unallocated_cents": res["unallocated"],
                    "grants": [
                        {"beneficiary_id": ben, "cents": cents}
                        for ben, cents in sorted(res["grants"].items())
                    ],
                    "intervals": intervals,
                    "selected_offer_ids": list(res["selected"]),
                }
            )
            totals["event_count"] += 1
            totals["candidate_offer_count"] += res["candidate_offer_count"]
            totals["selected_offer_count"] += len(res["selected"])
            totals["relief_ticks"] += sum(res["relief"])
            totals["recovery_ticks"] += sum(res["recovery"])
            totals["shortfall_ticks"] += sum(iv["shortfall_ticks"] for iv in intervals)
            totals["overdelivery_ticks"] += sum(iv["overdelivery_ticks"] for iv in intervals)
            totals["bid_cost_cents"] += res["bid_cents"]
            totals["credit_cents"] += res["credit_cents"]
            totals["grant_pool_cents"] += res["pool"]
            totals["grant_funded_cents"] += res["funded"]
            totals["grant_allocated_cents"] += res["allocated"]
            totals["grant_unallocated_cents"] += res["unallocated"]

        region_totals = {k: totals[k] for k in REGION_TOTAL_KEYS}
        write_json(
            out_dir,
            "region_%s.json" % region,
            {"events": events_out, "region": region, "totals": region_totals},
        )
        for k in REGION_TOTAL_KEYS:
            if k != "event_count":
                grand[k] += totals[k]
        summary_regions[region] = {
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
            "grant_allocated_cents": totals["grant_allocated_cents"],
            "relief_ticks": totals["relief_ticks"],
            "selected_offer_count": totals["selected_offer_count"],
        }

    for name in ex["segments"]:
        entries = []
        totals = defaultdict(int)
        for eid in ex["event_ids"]:
            for region in ex["regions"]:
                res = results[(eid, region)]
                stats = res["segments"][name]
                floor_ticks = res["floors"][name]
                relief = stats["relief"]
                if floor_ticks == 0:
                    attainment = 10000
                else:
                    attainment = min(10000, rhu(10000 * relief, floor_ticks))
                entries.append(
                    {
                        "bid_cost_cents": stats["bid"],
                        "credit_cents": stats["credit"],
                        "event_id": eid,
                        "floor_attainment_bp": attainment,
                        "floor_ticks": floor_ticks,
                        "recovery_ticks": stats["recovery"],
                        "region": region,
                        "relief_ticks": relief,
                        "selected_offer_ids": sorted(stats["offers"]),
                    }
                )
                totals["selected_offer_count"] += len(stats["offers"])
                totals["relief_ticks"] += relief
                totals["recovery_ticks"] += stats["recovery"]
                totals["bid_cost_cents"] += stats["bid"]
                totals["credit_cents"] += stats["credit"]
                totals["floor_ticks"] += floor_ticks
        write_json(
            out_dir,
            "segment_%s.json" % name,
            {
                "event_regions": entries,
                "segment": name,
                "totals": {k: totals[k] for k in SEGMENT_TOTAL_KEYS},
            },
        )
        summary_segments[name] = {
            "bid_cost_cents": totals["bid_cost_cents"],
            "credit_cents": totals["credit_cents"],
            "relief_ticks": totals["relief_ticks"],
            "selected_offer_count": totals["selected_offer_count"],
        }

    write_json(
        out_dir,
        "summary.json",
        {
            "bid_cost_cents": grand["bid_cost_cents"],
            "candidate_offer_count": grand["candidate_offer_count"],
            "credit_cents": grand["credit_cents"],
            "event_count": len(ex["event_ids"]),
            "event_region_count": len(ex["event_ids"]) * len(ex["regions"]),
            "grant_allocated_cents": grand["grant_allocated_cents"],
            "grant_funded_cents": grand["grant_funded_cents"],
            "grant_pool_cents": grand["grant_pool_cents"],
            "grant_unallocated_cents": grand["grant_unallocated_cents"],
            "overdelivery_ticks": grand["overdelivery_ticks"],
            "recovery_ticks": grand["recovery_ticks"],
            "regions": summary_regions,
            "relief_ticks": grand["relief_ticks"],
            "segments": summary_segments,
            "selected_offer_count": grand["selected_offer_count"],
            "shortfall_ticks": grand["shortfall_ticks"],
            "site_count": len(ex["sites"]),
        },
    )

    counts = dict.fromkeys(LABELS, 0)
    for label in labels.values():
        counts[label] += 1
    write_json(
        out_dir,
        "policy_audit.json",
        {
            "cap_binding_count": audit["cap_binding_count"],
            "compliance_counts": counts,
            "residual_cents": audit["residual_cents"],
            "residual_tie_pool_count": audit["residual_tie_pool_count"],
            "site_labels": [
                {"event_id": eid, "label": labels[(eid, sid)], "site_id": sid}
                for eid, sid in sorted(labels)
            ],
            "tie_decisions": sorted(
                audit["tie_decisions"], key=lambda d: (d["event_id"], d["region"])
            ),
        },
    )

    dq = ex["dq"]
    write_json(
        out_dir,
        "data_quality.json",
        {
            "duplicate_profile_rows": dq["duplicate_profile_rows"],
            "empty_candidate_groups": dq["empty_candidate_groups"],
            "ineligible_offer_count": dq["ineligible_offer_count"],
            "orphan_offer_rows": dq["orphan_offer_rows"],
            "orphan_profile_rows": dq["orphan_profile_rows"],
            "out_of_range_profile_rows": dq["out_of_range_profile_rows"],
            "rows": ex["rows"],
            "unallocated_pool_count": dq["unallocated_pool_count"],
            "unknown_region_site_rows": dq["unknown_region_site_rows"],
            "waiver_signed_missing": dq["waiver_signed_missing"],
            "zero_floor_count": dq["zero_floor_count"],
        },
    )


def main(argv):
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    ex = read_extract(data_dir)
    results, audit, labels = build(ex)
    emit(ex, results, audit, labels, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
