"""Write wrong programs for the cost table: WORK/mutants/<name>.py, each a copy of solve.py
with one rule changed or the optimiser replaced. Run: python3 -B mutants.py"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVE = HERE.parent.parent / "cleanroom-window-schedule" / "solution" / "solve.py"
DEST = HERE / "mutants"

HELPERS = '''

_exact_plan = best_plan


def _simulate(book, night_id, jobs, holding, plan):
    """Net of a plan under the stated rules, or None when the plan breaks one."""
    terms = {(a, b): v for (n, a, b), v in book.fees.items() if n == night_id}
    rate = {b["bay_id"]: b["minute_rate"] for b in book.bays}
    fam = dict(holding)
    free = {b: 0 for b in fam}
    windows, net = [], 0
    for j in sorted((j for j in jobs if j["job_id"] in plan), key=lambda j: (j["start"], j["job_id"])):
        bay = plan[j["job_id"]]
        if j["family"] not in book.qualified[bay] or j["start"] < free[bay]:
            return None
        net += j["value"] - rate[bay] * (j["end"] - j["start"])
        if j["family"] != fam[bay]:
            fee, minutes = terms[(fam[bay], j["family"])]
            lo = j["start"] - minutes
            if lo < max(free[bay], 0) or any(lo < e and s < j["start"] for s, e in windows):
                return None
            windows.append((lo, j["start"]))
            net -= fee
        fam[bay], free[bay] = j["family"], j["end"]
    return net


def _greedy(book, night_id, jobs, holding):
    must = set(book.mandatory.get(night_id, []))
    order = sorted(jobs, key=lambda j: (j["job_id"] not in must, -j["value"] / (j["end"] - j["start"]), j["job_id"]))
    plan, current = {}, 0
    for j in order:
        best = None
        for b in book.bays:
            trial = dict(plan)
            trial[j["job_id"]] = b["bay_id"]
            got = _simulate(book, night_id, jobs, holding, trial)
            if got is not None and (best is None or got > best[0]):
                best = (got, trial)
        if best is not None and (j["job_id"] in must or best[0] > current):
            current, plan = best
    return plan, current
'''

GREEDY = '''

def best_plan(book, night_id, jobs, holding):
    return _greedy(book, night_id, jobs, holding)[0]
'''

GREEDY_LS = '''

def best_plan(book, night_id, jobs, holding):
    must = set(book.mandatory.get(night_id, []))
    plan, current = _greedy(book, night_id, jobs, holding)
    bays = [b["bay_id"] for b in book.bays]
    ids = sorted(j["job_id"] for j in jobs)
    for _ in range(200):
        moves = []
        for jid in ids:
            if jid not in plan:
                moves += [((), ((jid, b),)) for b in bays]
            else:
                if jid not in must:
                    moves.append(((jid,), ()))
                    moves += [((jid,), ((k, b),)) for k in ids if k not in plan for b in bays]
                moves += [((jid,), ((jid, b),)) for b in bays if b != plan[jid]]
        better = None
        for drop, add in moves:
            trial = {k: v for k, v in plan.items() if k not in drop}
            trial.update(add)
            got = _simulate(book, night_id, jobs, holding, trial)
            if got is not None and got > current and must <= set(trial):
                better = (got, trial)
                break
        if better is None:
            break
        current, plan = better
    return plan
'''

LANE_BY_LANE = '''

class _OneBay:
    def __init__(self, book, bay):
        self.bays = [bay]
        self.qualified = book.qualified
        self.fees = book.fees
        self.mandatory = {}


def best_plan(book, night_id, jobs, holding):
    plan, left = {}, list(jobs)
    for bay in book.bays:
        part = _exact_plan(_OneBay(book, bay), night_id, left, {bay["bay_id"]: holding[bay["bay_id"]]})
        plan.update(part)
        left = [j for j in left if j["job_id"] not in part]
    return plan
'''

RAW_TUNED = '''

def _bound_data(book, night_id, jobs, holding, order):
    low = min(b["minute_rate"] for b in book.bays)
    gains = [max(0, j["value"] - low * (j["end"] - j["start"])) for j in order]
    suffix = [0] * (len(order) + 1)
    for i in range(len(order) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + gains[i]
    plan = _greedy(book, night_id, jobs, holding)[0]
    got = _simulate(book, night_id, jobs, holding, plan)
    if got is None or not set(book.mandatory.get(night_id, [])) <= set(plan):
        got = -10 ** 12
    return suffix, got
'''


def edit(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def insert_before_main(text, block):
    return edit(text, "\n\ndef main(", HELPERS + block + "\n\ndef main(")


def build():
    base = SOLVE.read_text(encoding="utf-8")
    # A wrong program still runs every night: a job no state can take is skipped.
    base = edit(base, "        layers.append(nxt)\n",
                "        if not nxt:\n            nxt = {k: (v, k, 0) for k, (v, _, _) in frontier.items()}\n"
                "        layers.append(nxt)\n")
    lead = "    lead = max((c for _, c in terms.values()), default=0)\n"
    out = {}
    out["greedy"] = insert_before_main(base, GREEDY)
    out["greedy_ls"] = insert_before_main(base, GREEDY_LS)
    out["lane_by_lane"] = insert_before_main(base, LANE_BY_LANE)
    t = edit(base, "                if fam not in book.qualified[bay]:\n                    continue\n", "")
    out["flow_relax"] = edit(t, "if start - minutes < max(free, crew):", "if start - minutes < free:")
    out["no_crew"] = edit(base, "if start - minutes < max(free, crew):", "if start - minutes < free:")
    out["naive_collapse"] = edit(base, lead, "    lead = 0\n")
    out["raw_exact"] = edit(base, lead, "    lead = 10 ** 9\n")
    t = edit(base, lead, "    lead = 10 ** 9\n")
    t = edit(t, "    layers = []\n", "    layers = []\n    suffix, incumbent = _bound_data(book, night_id, jobs, holding, order)\n")
    t = edit(t, "        layers.append(nxt)\n",
             "        nxt = {k: v for k, v in nxt.items() if v[0] + suffix[depth + 1] >= incumbent}\n"
             "        layers.append(nxt)\n")
    out["raw_tuned"] = insert_before_main(t, RAW_TUNED)
    out["reset_nightly"] = edit(base, "        jobs = []\n",
                                "        holding = {b[\"bay_id\"]: b[\"initial_family\"] for b in book.bays}\n        jobs = []\n")
    t = edit(base, "    holding = {b[\"bay_id\"]: b[\"initial_family\"] for b in book.bays}\n",
             "    holding = {b[\"bay_id\"]: None for b in book.bays}\n")
    t = edit(t, "                if fam != held_fam:\n", "                if held_fam is not None and fam != held_fam:\n")
    out["no_initial"] = edit(t, "            if j[\"family\"] != last_family[bay]:\n",
                             "            if last_family[bay] is not None and j[\"family\"] != last_family[bay]:\n")
    t = edit(base, "                if fam != held_fam:\n", "                if fam != held_fam and free == start:\n")
    t = edit(t, "        last_family = dict(holding)\n", "        last_family = dict(holding)\n        last_end = {}\n")
    t = edit(t, "            if j[\"family\"] != last_family[bay]:\n",
             "            if j[\"family\"] != last_family[bay] and last_end.get(bay) == j[\"start\"]:\n")
    out["touching_only"] = edit(t, "            last_family[bay] = j[\"family\"]\n",
                                "            last_family[bay] = j[\"family\"]\n            last_end[bay] = j[\"end\"]\n")
    DEST.mkdir(exist_ok=True)
    for name, text in out.items():
        (DEST / (name + ".py")).write_text(text, encoding="utf-8")
        compile(text, name, "exec")
    print("wrote", len(out), "mutants:", ", ".join(sorted(out)))


if __name__ == "__main__":
    build()
