"""Build lazy-reading variants of the oracle by exact string patches (each patch must apply once)."""
from pathlib import Path

HERE = Path(__file__).parent
SOLVE = (HERE.parent.parent.parent / "district-heat-flex-procurement" / "solution" / "solve.py").read_text()

PATCHES = {
    "H1": [("""    if site.pending and waiver_valid:
        return "CONTINUITY_WAIVED"
""", "")],
    "H2": [("    pick = max(best)\n", "    pick = min(best)\n")],
    "H3": [("    rate = min(offer.site.base + uplift, offer.site.cap)\n",
            "    rate = min(offer.site.base, offer.site.cap) + uplift\n")],
    "H4": [("    order = sorted(shares, key=lambda b: (rest[b], b), reverse=True)\n",
            "    order = sorted(shares, key=lambda b: (-rest[b], b))\n")],
    "H5": [
        ('            offer.relief[t] = ticks(r["relief_wh"])\n            offer.recovery[t] = ticks(r["recovery_wh"])\n',
         '            offer.relief[t] = int(r["relief_wh"])\n            offer.recovery[t] = int(r["recovery_wh"])\n'),
        ("        relief = [sum(o.relief[t] for o in chosen) for t in range(n)]\n        recovery = [sum(o.recovery[t] for o in chosen) for t in range(n)]\n",
         "        relief = [half_up(sum(o.relief[t] for o in chosen), ex.wh_per_tick) for t in range(n)]\n        recovery = [half_up(sum(o.recovery[t] for o in chosen), ex.wh_per_tick) for t in range(n)]\n"),
        ("            got = sum(sum(o.relief) for o in chosen if o.site.segment == seg)\n",
         "            got = half_up(sum(sum(o.relief) for o in chosen if o.site.segment == seg), ex.wh_per_tick)\n"),
        ("    energy_wh = sum(offer.relief) * ex.wh_per_tick\n    return half_up(energy_wh * rate, 1000 * ex.millicents_per_cent)\n",
         "    return sum(offer.relief) * rate\n"),
        ("                rel = sum(o.relief[t] for o in chosen)\n",
         "                rel = half_up(sum(o.relief[t] for o in chosen), ex.wh_per_tick)\n"),
        ('                                  "recovery_ticks": sum(o.recovery[t] for o in chosen),\n',
         '                                  "recovery_ticks": half_up(sum(o.recovery[t] for o in chosen), ex.wh_per_tick),\n'),
        ('                "credit_cents": sum(credit.values()), "grant_pool_cents": pool,\n',
         '                "credit_cents": half_up(sum(credit.values()), 1000 * ex.millicents_per_cent), "grant_pool_cents": pool,\n'),
        ("                relief = sum(sum(o.relief) for o in mine)\n",
         "                relief = half_up(sum(sum(o.relief) for o in mine), ex.wh_per_tick)\n"),
        ('                    "relief_ticks": relief, "recovery_ticks": sum(sum(o.recovery) for o in mine),\n',
         '                    "relief_ticks": relief, "recovery_ticks": half_up(sum(sum(o.recovery) for o in mine), ex.wh_per_tick),\n'),
        ('"credit_cents": sum(credit[o.offer_id] for o in mine),\n',
         '"credit_cents": half_up(sum(credit[o.offer_id] for o in mine), 1000 * ex.millicents_per_cent),\n'),
    ],
    "GREEDY": [("def choose_portfolio(", "def exact_portfolio("),
               ("def credit_cents(", '''def choose_portfolio(ex, event, region, candidates):
    """First-fit greedy: walk sites in id order, keep the first mode that fits and cuts shortfall."""
    eid = event["event_id"]
    n = int(event["interval_count"])
    target = [ex.targets.get((eid, region, t + 1), (0, 0))[0] for t in range(n)]
    limit = [ex.ceilings.get((eid, region, t + 1), (0, 0)) for t in range(n)]
    relief, recovery, chosen = [0] * n, [0] * n, []
    by_site = {}
    for offer in candidates:
        by_site.setdefault(offer.site.site_id, []).append(offer)
    for sid in sorted(by_site):
        for o in sorted(by_site[sid], key=lambda x: x.offer_id):
            r2 = [relief[t] + o.relief[t] for t in range(n)]
            v2 = [recovery[t] + o.recovery[t] for t in range(n)]
            fits = all(r2[t] <= limit[t][0] and v2[t] <= limit[t][1] for t in range(n))
            helps = sum(max(0, target[t] - r2[t]) for t in range(n)) < sum(max(0, target[t] - relief[t]) for t in range(n))
            if fits and helps:
                relief, recovery = r2, v2
                chosen.append(o)
                break
    return chosen, 1


def credit_cents(''')],
}

VARIANTS = {
    "only_H1": ["H1"], "only_H2": ["H2"], "only_H3": ["H3"], "only_H4": ["H4"], "only_H5": ["H5"],
    "three_H2_H3_H5": ["H2", "H3", "H5"], "four_all_but_H1": ["H2", "H3", "H4", "H5"],
    "all_lazy": ["H1", "H2", "H3", "H4", "H5"], "greedy_four_lazy": ["H1", "H2", "H3", "H4", "GREEDY"],
}
for name, keys in VARIANTS.items():
    text = SOLVE
    for key in keys:
        for old, new in PATCHES[key]:
            assert text.count(old) == 1, (name, key, old[:60])
            text = text.replace(old, new)
    (HERE / f"{name}.py").write_text(text)
print("wrote", len(VARIANTS))
