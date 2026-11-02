from typing import Any

def _portfolio(info: dict[str, dict[str, Any]], joined: dict[frozenset[str], set[str]]) -> list[str]:
    """Best conflict-free set; ties go to the lexicographically smaller sorted id list.

    Scores are pairs (benefit, priority) compared in order, where priority holds one bit
    per chosen proposal and the smallest id owns the highest bit, so among equal benefits
    the larger priority is the smaller sorted id list.
    """
    names = sorted(info)
    n = len(names)
    near = [0] * n
    index = {p: i for i, p in enumerate(names)}
    for pair in joined:
        a, b = (index[p] for p in pair)
        near[a] |= 1 << b
        near[b] |= 1 << a
    graph = list(near)
    alive = (1 << n) - 1
    order = []
    while alive:
        pick, score = -1, None
        rest = alive
        while rest:
            v = (rest & -rest).bit_length() - 1
            rest &= rest - 1
            around = graph[v] & alive
            missing = 0
            others = around
            while others:
                u = (others & -others).bit_length() - 1
                others &= others - 1
                missing += bin(around & ~graph[u] & ~(1 << u)).count("1")
            key = (missing, bin(around).count("1"), v)
            if score is None or key < score:
                pick, score = v, key
        around = graph[pick] & alive
        others = around
        while others:
            u = (others & -others).bit_length() - 1
            others &= others - 1
            graph[u] |= around & ~(1 << u)
        alive &= ~(1 << pick)
        order.append((pick, around))
    place = {v: k for k, (v, _) in enumerate(order)}
    inbox: list[list[tuple[int, dict[int, tuple[int, int, int]]]]] = [[] for _ in range(n)]
    roots = []
    for v, scope in order:
        members = []
        rest = scope
        while rest:
            u = (rest & -rest).bit_length() - 1
            rest &= rest - 1
            members.append(u)
        subsets = [0]
        for u in members:
            subsets += [s | (1 << u) for s in subsets if not s & near[u]]
        own = (info[names[v]]["benefit"], 1 << (n - 1 - v), 1 << v)
        table = {}
        for s in subsets:
            out_score = [0, 0, 0]
            for mask, msg in inbox[v]:
                got = msg[s & mask]
                out_score = [out_score[0] + got[0], out_score[1] + got[1], out_score[2] | got[2]]
            best = tuple(out_score)
            if not s & near[v]:
                with_v = list(own)
                for mask, msg in inbox[v]:
                    got = msg[(s | (1 << v)) & mask]
                    with_v = [with_v[0] + got[0], with_v[1] + got[1], with_v[2] | got[2]]
                if (with_v[0], with_v[1]) > (best[0], best[1]):
                    best = tuple(with_v)
            table[s] = best
        if members:
            inbox[min(members, key=lambda u: place[u])].append((scope, table))
        else:
            roots.append(table[0])
    picked = 0
    for r in roots:
        picked |= r[2]
    return [names[i] for i in range(n) if picked >> i & 1]

