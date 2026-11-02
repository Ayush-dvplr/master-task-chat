"""Phase 1 prototype, candidate B (monthly tier positions): how often does the probe-2 reading
(account position over the whole period; the current oracle, which the agent matches on 306/306
fuzz corpora) differ from a month-restart reading on the CURRENT corpora, shipped data and
regression cases. Read-only on BUNDLE/WORK; imports WORK/test_output.src.py as a module."""
import importlib.util
import json
import sys
from datetime import date
from fractions import Fraction
from pathlib import Path

WORK = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair")
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
sys.path.insert(0, str(WORK / "rewardkit_stub"))
spec = importlib.util.spec_from_file_location("T", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


class Monthly(T._Ledger):
    """Account position counted afresh in each calendar month; a meter's units in a tier are the
    sum over the months."""

    def document(self):
        self.monthly = {}
        taken = set()
        for read in self.reads:
            account, meter = read["account"].strip(), read["meter"].strip()
            day = date.fromisoformat(read["day"].strip())
            if self._reason(account, meter, day, read["quantity"], taken) is None:
                taken.add((account, meter, day))
                key = (account, meter, (day.year, day.month))
                self.monthly[key] = self.monthly.get(key, 0) + read["quantity"]
        return super().document()

    def _invoice(self, account, usage):
        base = super()._invoice(account, usage)
        plan = self.plans[base["plan"]]
        meters = sorted(m for (a, m) in self.windows if a == account)
        months = sorted({k[2] for k in self.monthly if k[0] == account})
        units = {}
        for month in months:
            position = 0
            for meter in meters:
                quantity, floor = self.monthly.get((account, meter, month), 0), 0
                for number, tier in enumerate(plan["tiers"], 1):
                    cap = tier["up_to"]
                    low = max(position, floor)
                    high = position + quantity if cap is None else min(position + quantity, cap)
                    if high > low:
                        units[(meter, number)] = units.get((meter, number), 0) + high - low
                    if cap is None:
                        break
                    floor = cap
                position += quantity
        old = {(l["meter"], l["tier"]): l["units"] for l in base["lines"] if l["kind"] == "energy"}
        return {"same": old == units}


def compare(texts):
    a = Monthly(texts).document()["invoices"]
    return sum(1 for inv in a if not inv["same"]), len(a)


out = {}
for corpus in ("fresh", "rescaled", "relocated", "rotated", "api"):
    out[corpus] = compare(T._corpus_texts(corpus))
ci = BUNDLE / "environment" / "ci"
shipped = {n: (ci / n).read_text(encoding="utf-8") for n in T.INPUT_FILES}
out["shipped"] = compare(shipped)
card = (ci / "rate_card.json").read_text(encoding="utf-8")
diff = 0
cases = [json.loads(x) for x in (ci / "regression_cases.jsonl").read_text().splitlines()]
for case in cases:
    diff += compare(T._case_texts(case, card))[0]
out["regression"] = (diff, len(cases))
print(json.dumps(out), flush=True)

# fuzz incidence: same job list as fuzz_r2.py (seed 0x0DD7A8C, 80 per family) plus N2+N3
import random
rng = random.Random(0x0DD7A8C)
FAM = {"none": frozenset(), "N1": frozenset({"N1"}), "N2": frozenset({"N2"}), "N3": frozenset({"N3"})}
jobs = [(f, rng.randrange(1, 10**9), rng.choice([12, 24, 30, 45])) for f in FAM for _ in range(80)]
jobs += [("N2+N3", rng.randrange(1, 10**9), rng.choice([12, 24, 30, 45])) for _ in range(80)]
FAM["N2+N3"] = frozenset({"N2", "N3"})
tally = {}
for fam, seed, size in jobs:
    try:
        texts, _ = T._corpus(seed, size, (), FAM[fam])
    except Exception:
        continue
    d, n = compare(texts)
    t = tally.setdefault(fam, [0, 0, 0, 0])
    t[0] += d > 0; t[1] += 1; t[2] += d; t[3] += n
print(json.dumps({"fuzz_corpora_differ/valid/accounts_differ/accounts": tally}))
