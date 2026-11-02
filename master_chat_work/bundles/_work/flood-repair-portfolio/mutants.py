"""Write wrong programs for the cost table and rule coverage: WORK/mutants/<name>.py.

Each is solution/solve.py with one rule changed or the optimiser replaced.
python3 -B mutants.py   -> writes the files and prints name, lever
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVE = HERE.parent.parent / "flood-repair-portfolio" / "solution" / "solve.py"
DEST = HERE / "mutants"

OPT = '''

import random as _random
import time as _time

_exact_best_set = best_set
_PIECE_SECONDS = 8.0


def _bits(weights, adj, vertices):
    idx = {v: i for i, v in enumerate(vertices)}
    nb = [0] * len(vertices)
    for v in vertices:
        for u in adj[v]:
            nb[idx[v]] |= 1 << idx[u]
    return nb, [weights[v] for v in vertices]


def _greedy_mask(nb, w, key):
    order = sorted(range(len(w)), key=key)
    taken, blocked = 0, 0
    for i in order:
        if not blocked >> i & 1:
            taken |= 1 << i
            blocked |= nb[i] | (1 << i)
    return taken


def _score(w, mask):
    return sum(w[i] for i in range(len(w)) if mask >> i & 1)


def _swaps(nb, w, mask, deadline=None):
    n = len(w)
    improved = True
    while improved:
        improved = False
        for i in range(n):
            if deadline and _time.time() > deadline:
                return mask
            if mask >> i & 1:
                continue
            out = mask & nb[i]
            if _score(w, out) < w[i]:
                mask = (mask & ~out) | (1 << i)
                improved = True
        for i in range(n):
            for j in range(i + 1, n):
                if mask >> i & 1 or mask >> j & 1 or nb[i] >> j & 1:
                    continue
                out = mask & (nb[i] | nb[j])
                if _score(w, out) < w[i] + w[j]:
                    mask = (mask & ~out) | (1 << i) | (1 << j)
                    improved = True
    for i in range(n):
        if not mask & (nb[i] | (1 << i)):
            mask |= 1 << i
    return mask


def _as_list(vertices, mask):
    return [v for i, v in enumerate(vertices) if mask >> i & 1]


def _cover_bound(nb, w, mask):
    total = 0
    while mask:
        v = max((i for i in range(len(w)) if mask >> i & 1), key=lambda i: w[i])
        clique, cand = 1 << v, nb[v] & mask
        while cand:
            u = max((i for i in range(len(w)) if cand >> i & 1), key=lambda i: w[i])
            clique |= 1 << u
            cand &= nb[u]
        total += w[v]
        mask &= ~clique
    return total


class _Stop(Exception):
    pass


def _bnb(nb, w, limit):
    n = len(w)
    best = [_greedy_mask(nb, w, lambda i: -w[i])]
    best.append(_score(w, best[0]))
    deadline = _time.time() + limit

    def rec(mask, score, chosen):
        if _time.time() > deadline:
            raise _Stop
        alone = 0
        for i in range(n):
            if mask >> i & 1 and not nb[i] & mask:
                alone |= 1 << i
        if alone:
            score += _score(w, alone)
            chosen |= alone
            mask &= ~alone
        if not mask:
            if score > best[1]:
                best[0], best[1] = chosen, score
            return
        if score + _cover_bound(nb, w, mask) <= best[1]:
            return
        v = max((i for i in range(n) if mask >> i & 1), key=lambda i: bin(nb[i] & mask).count("1"))
        rec(mask & ~nb[v] & ~(1 << v), score + w[v], chosen | (1 << v))
        rec(mask & ~(1 << v), score, chosen)

    try:
        rec((1 << n) - 1, 0, 0)
    except _Stop:
        pass
    return best[0]


def _ils(nb, w, limit):
    rng = _random.Random(7)
    n = len(w)
    cur = _swaps(nb, w, _greedy_mask(nb, w, lambda i: -w[i] / (1 + bin(nb[i]).count("1"))))
    best, best_score = cur, _score(w, cur)
    deadline = _time.time() + limit
    while _time.time() < deadline:
        trial = cur
        for i in rng.sample(range(n), rng.randint(1, 3)):
            trial = (trial & ~nb[i]) | (1 << i)
        trial = _swaps(nb, w, trial, deadline)
        s = _score(w, trial)
        if s >= _score(w, cur):
            cur = trial
        if s > best_score:
            best, best_score = trial, s
    return best
'''

OPTIMISERS = {
    "greedy_benefit": "return _as_list(vertices, _greedy_mask(nb, w, lambda i: -w[i]))",
    "greedy_ratio": "return _as_list(vertices, _greedy_mask(nb, w, lambda i: -w[i] / (1 + bin(nb[i]).count('1'))))",
    "greedy_swaps": "return _as_list(vertices, _swaps(nb, w, _greedy_mask(nb, w, lambda i: -w[i])))",
    "timed_bnb": "return _as_list(vertices, _bnb(nb, w, _PIECE_SECONDS) if len(w) > 40 else _bits_exact())",
    "timed_ils": "return _as_list(vertices, _ils(nb, w, _PIECE_SECONDS) if len(w) > 40 else _bits_exact())",
}

RULES = [
    # (name, lever, old, new)
    ("no_tiebreak", "LV-FP-1",
     'weights = {pid: rnd.detail[pid]["benefit"] * (1 << n) + (1 << (n - 1 - rank[pid])) for pid in ids}',
     'weights = {pid: rnd.detail[pid]["benefit"] for pid in ids}'),
    ("tiebreak_largest", "LV-FP-1",
     '(1 << (n - 1 - rank[pid]))', '(1 << rank[pid])'),
    ("no_crew", "LV-FP-2", 'mark(members, members, "crew")', 'pass'),
    ("shared_crews_too", "LV-FP-2", 'if book["crews"][crew] == "exclusive":', 'if True:'),
    ("no_permit", "LV-FP-2", 'mark(members, members, "permit")', 'pass'),
    ("withdrawn_counts", "LV-FP-2", 'if status != "withdrawn":', 'if True:'),
    ("no_exclusion", "LV-FP-2",
     'mark(by_site.get(first, [first]) if first not in rnd.detail else [first],',
     'continue\n        mark(by_site.get(first, [first]) if first not in rnd.detail else [first],'),
    ("site_names_ignored", "LV-FP-2",
     'mark(by_site.get(first, [first]) if first not in rnd.detail else [first],\n'
     '             by_site.get(second, [second]) if second not in rnd.detail else [second], "exclusion")',
     'mark([first], [second], "exclusion")'),
    ("no_override", "LV-FP-3", 'risk = override or book["sites"][site]["risk_class"]',
     'risk = book["sites"][site]["risk_class"]'),
    ("no_premium", "LV-FP-3",
     'benefit = h * (book["segment_rate"][segment] + book["risk_uplift"][risk]) + premium',
     'benefit = h * (book["segment_rate"][segment] + book["risk_uplift"][risk])'),
    ("uplift_flat", "LV-FP-3",
     'benefit = h * (book["segment_rate"][segment] + book["risk_uplift"][risk]) + premium',
     'benefit = h * book["segment_rate"][segment] + book["risk_uplift"][risk] + premium'),
    ("no_uplift", "LV-FP-3",
     'benefit = h * (book["segment_rate"][segment] + book["risk_uplift"][risk]) + premium',
     'benefit = h * book["segment_rate"][segment] + premium'),
    ("fixed_file_order", "LV-FP-4", 'for name in book["order"]:\n            if name in ROUND_FILES:',
     'for name in ROUND_FILES:\n            if name in ROUND_FILES:'),
    ("invalid_before_duplicate", "LV-FP-4",
     '            if proposal in seen:\n                code = "DUPLICATE_PROPOSAL"\n'
     '            elif not (households.isdigit() and households.isascii() and 1 <= int(households) <= 60):\n'
     '                code = "INVALID_INPUT"',
     '            if not (households.isdigit() and households.isascii() and 1 <= int(households) <= 60):\n'
     '                code = "INVALID_INPUT"\n            elif proposal in seen:\n                code = "DUPLICATE_PROPOSAL"'),
    ("first_occurrence_duplicate", "LV-FP-4", '                code = "DUPLICATE_PROPOSAL"\n',
     '                code = "DUPLICATE_PROPOSAL"\n'
     '                number = next(k for k, f in numbered if f[0] == proposal)\n'),
    ("row_within_round", "LV-FP-4",
     'rnd.fault = {"round": rid, "code": hit[1], "file": name, "row": hit[0]}',
     'rnd.fault = {"round": rid, "code": hit[1], "file": name, "row": [k for k, _ in per_file[name].get(rid, [])].index(hit[0]) + 1}'),
    ("value_before_files", "LV-FP-4",
     '    attach(book, rounds)\n    for rnd in rounds.values():\n        if rnd.fault is None:\n            value(book, rnd)\n',
     '    attach(book, rounds)\n    for rnd in rounds.values():\n        kept, rnd.fault = rnd.fault, None\n        try:\n            value(book, rnd)\n        except (KeyError, ValueError):\n            pass\n        if rnd.fault is None:\n            rnd.fault = kept\n'),
]


def main():
    src = SOLVE.read_text()
    DEST.mkdir(exist_ok=True)
    made = []
    for name, body in OPTIMISERS.items():
        extra = OPT + '''

def best_set(weights, adj, vertices):
    nb, w = _bits(weights, adj, vertices)

    def _bits_exact():
        got = set(_exact_best_set(weights, adj, vertices))
        return sum(1 << i for i, v in enumerate(vertices) if v in got)

    %s
''' % body
        text = src.replace("\n\ndef main(argv):", extra + "\n\ndef main(argv):", 1)
        assert text != src
        (DEST / (name + ".py")).write_text(text)
        made.append((name, "LV-FP-1"))
    for name, lever, old, new in RULES:
        assert src.count(old) >= 1, name
        text = src.replace(old, new, 1)
        (DEST / (name + ".py")).write_text(text)
        made.append((name, lever))
    for name, lever in made:
        print(name, lever)


if __name__ == "__main__":
    main()
