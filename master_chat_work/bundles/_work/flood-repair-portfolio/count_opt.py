"""Number of maximum-benefit conflict-free portfolios (raw benefits, no tie-break) per planned round."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import solve_draft as S


def count_best(rnd):
    ids = sorted(rnd.ids)
    adj = {p: set() for p in ids}
    for a, b in rnd.pairs:
        adj[a].add(b); adj[b].add(a)
    total_v, total_c, seen = 0, 1, set()
    for pid in ids:
        if pid in seen:
            continue
        piece, stack = [], [pid]; seen.add(pid)
        while stack:
            v = stack.pop(); piece.append(v)
            for u in adj[v] - seen:
                seen.add(u); stack.append(u)
        order = S.sweep_order(piece, adj)
        pos = {v: i for i, v in enumerate(order)}
        last = {v: max([pos[u] for u in adj[v]] + [pos[v]]) for v in order}
        bit = {v: 1 << i for i, v in enumerate(order)}
        states = {0: (0, 1)}
        for i, v in enumerate(order):
            earlier = sum(bit[u] for u in adj[v] if pos[u] < i)
            keep = sum(bit[u] for u in order[:i + 1] if last[u] > i)
            nxt = {}
            for key, (sc, c) in states.items():
                for take in (0, 1):
                    if take and key & earlier:
                        continue
                    k2 = ((key | bit[v]) if take else key) & keep
                    s2 = sc + (rnd.detail[v]["benefit"] if take else 0)
                    o = nxt.get(k2)
                    if o is None or s2 > o[0]:
                        nxt[k2] = (s2, c)
                    elif s2 == o[0]:
                        nxt[k2] = (s2, o[1] + c)
            states = nxt
        best = max(s for s, _ in states.values())
        total_v += best
        total_c *= sum(c for s, c in states.values() if s == best)
    return total_v, total_c


if __name__ == "__main__":
    book = S.load(sys.argv[1])
    for r in S.build(book):
        if r.fault is None:
            v, c = count_best(r)
            if c != 1 or len(r.ids) > 40:
                print(r.rid, len(r.ids), v, c)
