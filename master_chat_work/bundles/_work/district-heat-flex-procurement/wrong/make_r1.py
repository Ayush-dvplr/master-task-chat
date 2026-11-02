"""Round-1 wrong solvers: exact string patches of solution/solve.py (each patch must apply once).

Usage: python3 make_r1.py   (writes wrong/r1_<variant>.py and prints the list)

Lever readings (the reflex reading of each rule):
  H1   a pending certificate is always CERTIFICATE_PENDING (no CONTINUITY_WAIVED label)
  H2   equal portfolios resolve to the smallest sorted id tuple
  H3   rate = min(base, cap) + uplift
  H4   equal remainders are served in ascending beneficiary id
  H5   reported energy sums raw Wh and converts once; credits use raw Wh and round once per group
  DH1  plain enumeration of every portfolio (itertools.product), exact but exponential
  DH2  the portfolio search adds raw Wh and converts the sum to ticks
  DH3  grants share the raw pools.txt pool
  DH4  profile rows written straight into the interval slot (last row wins, interval 0 wraps,
       interval above the count crashes); an unknown region code crashes
  DH5  doubled grant weight decided from the raw waiver fields, ignoring hold and cooldown
"""
from pathlib import Path

HERE = Path(__file__).parent
SOLVE = (HERE.parent.parent.parent / "district-heat-flex-procurement" / "solution" / "solve.py").read_text()

ENUMERATION = '''def choose_portfolio(ex: Extract, event: dict, region: str, candidates: list[Offer]) -> tuple[list[Offer], int]:
    """Plain enumeration of every portfolio."""
    import itertools
    eid = event["event_id"]
    n = int(event["interval_count"])
    scale = search_scale(ex)
    target = [ex.targets.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    limit = [ex.ceilings.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    cost_w = int(event["objective"]["cost_weight"])
    rec_w = int(event["objective"]["recovery_weight"])
    seg_floor = {s: ex.floors.get((eid, region, s), (0, 0)) for s in ex.segments}
    by_site: dict[str, list[Offer]] = {}
    for offer in candidates:
        by_site.setdefault(offer.site.site_id, []).append(offer)
    options = [[None, *by_site[k]] for k in sorted(by_site)]
    best_key, best, winners = None, [], {}
    for combo in itertools.product(*options):
        chosen = [o for o in combo if o is not None]
        units = [search_units(o, scale) for o in chosen]
        relief = [half_up(sum(u[0][t] for u in units), scale) for t in range(n)]
        recovery = [half_up(sum(u[1][t] for u in units), scale) for t in range(n)]
        if any(relief[t] > limit[t][0] or recovery[t] > limit[t][1] for t in range(n)):
            continue
        shortfall = sum(target[t][1] * max(0, target[t][0] - relief[t]) for t in range(n))
        deficit = 0
        for seg, (floor, weight) in seg_floor.items():
            got = half_up(sum(sum(u[0]) for o, u in zip(chosen, units) if o.site.segment == seg), scale)
            deficit += weight * max(0, floor - got)
        blended = cost_w * sum(o.cost for o in chosen) + rec_w * sum(recovery)
        over = sum(max(0, relief[t] - target[t][0]) for t in range(n))
        key = (shortfall, deficit, blended, over, len(chosen))
        ids = tuple(sorted(o.offer_id for o in chosen))
        if best_key is None or key < best_key:
            best_key, best, winners = key, [ids], {ids: chosen}
        elif key == best_key:
            best.append(ids)
            winners[ids] = chosen
    pick = best[0]
    for ids in best[1:]:
        pick = prefer(pick, ids)
    return winners[pick], len(best)


def exact_portfolio('''

NAIVE_PROFILES = '''def read_profiles(folder: Path, offer_rows: list[dict[str, str]], offers: dict[str, Offer],
                  interval_count: dict[str, int], rows: dict[str, int]) -> dict[str, int]:
    """Profile rows written straight into their interval slot."""
    known = {r["offer_id"] for r in offer_rows}
    profile_rows = table(folder / "profiles.tsv", "\\t")
    rows["profiles.tsv"] = len(profile_rows)
    rejected = {"orphan_profile_rows": 0, "out_of_range_profile_rows": 0, "duplicate_profile_rows": 0}
    for r in profile_rows:
        if r["offer_id"] not in known:
            rejected["orphan_profile_rows"] += 1
            continue
        offer = offers.get(r["offer_id"])
        if offer is not None:
            offer.relief_wh[int(r["interval"]) - 1] = int(r["relief_wh"])
            offer.recovery_wh[int(r["interval"]) - 1] = int(r["recovery_wh"])
    return rejected


def checked_profiles('''

PATCHES = {
    "H1": [('''    if site.pending and waiver_valid:
        return "CONTINUITY_WAIVED"
''', "")],
    "H2": [("    return max(first, second)\n", "    return min(first, second)\n")],
    "H3": [("    rate = min(offer.site.base + uplift, offer.site.cap)\n",
            "    rate = min(offer.site.base, offer.site.cap) + uplift\n")],
    "H4": [("    order = sorted(shares, key=lambda b: (rest[b], b), reverse=True)\n",
            "    order = sorted(shares, key=lambda b: (-rest[b], b))\n")],
    "H5": [
        ("    return sum(getattr(o, kind)[interval] for o in offers)\n",
         "    return half_up(sum(getattr(o, kind + \"_wh\")[interval] for o in offers), ex.wh_per_tick)\n"),
        ('                relief = sum(report_ticks(ex, mine, t, "relief") for t in range(n))\n',
         '                relief = half_up(sum(sum(o.relief_wh) for o in mine), ex.wh_per_tick)\n'),
        ('"recovery_ticks": sum(report_ticks(ex, mine, t, "recovery") for t in range(n)),',
         '"recovery_ticks": half_up(sum(sum(o.recovery_wh) for o in mine), ex.wh_per_tick),'),
        ("    energy_wh = sum(offer.relief) * ex.wh_per_tick\n    return half_up(energy_wh * rate, 1000 * ex.millicents_per_cent)\n",
         "    return sum(offer.relief_wh) * rate\n"),
        ("            credit_total = sum(credit.values())\n",
         "            credit_total = half_up(sum(credit.values()), 1000 * ex.millicents_per_cent)\n"),
        ('"credit_cents": sum(credit[o.offer_id] for o in mine),',
         '"credit_cents": half_up(sum(credit[o.offer_id] for o in mine), 1000 * ex.millicents_per_cent),'),
    ],
    "DH1": [("def choose_portfolio(", ENUMERATION)],
    "DH2": [('''    """Units of the search per energy tick: 1 means the search adds per-value ticks (section 2.3)."""
    return 1
''', '''    """Units of the search per energy tick: 1 means the search adds per-value ticks (section 2.3)."""
    return ex.wh_per_tick
''')],
    "DH3": [("    return max(0, pool - credit_total)\n", "    return pool\n")],
    "DH4": [("def read_profiles(", NAIVE_PROFILES),
            ('''        region = region_of.get(r["region_code"].upper())
        if region is None:
            unknown_region += 1
            continue
''', '''        region = region_of[r["region_code"].upper()]
''')],
    "DH5": [('''    return site.weight * 2 if label_for(site) == "CONTINUITY_WAIVED" else site.weight
''', '''    waiver_valid = (site.waiver_status == "VALID" and site.waiver_signed == "Y"
                    and site.critical and site.segment == "public")
    return site.weight * 2 if site.pending and waiver_valid else site.weight
''')],
}

OLD = ["H1", "H2", "H3", "H4", "H5"]
NEW = ["DH1", "DH2", "DH3", "DH4", "DH5"]
VARIANTS = {f"S3_{k}": [k] for k in OLD + NEW}
VARIANTS["S2_all_lazy"] = OLD + NEW
VARIANTS["S4_careful"] = NEW
VARIANTS["S4b_careful_dh3_right"] = ["DH1", "DH2", "DH4", "DH5"]

for name, keys in VARIANTS.items():
    text = SOLVE
    for key in keys:
        for old, new in PATCHES[key]:
            assert text.count(old) == 1, (name, key, old[:60])
            text = text.replace(old, new)
    (HERE / f"r1_{name}.py").write_text(text)
print("wrote", len(VARIANTS), sorted(VARIANTS))
