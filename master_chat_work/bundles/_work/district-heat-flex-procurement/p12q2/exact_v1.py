    def exact(cands: list[dict[str, Any]], goals, caps, floors_here, cw: int, vw: int, width: int):
        """Exact optimum by a layered table of partial portfolios, sites in ascending id order.

        After each site every reachable state (relief and recovery ticks per interval, segment relief capped
        at its floor) keeps only its cheapest (cost, count), the number of portfolios reaching it and the
        greatest sorted id tuple among them. A state is dropped once no completion can beat a known portfolio:
        its key with shortfall and floor deficit taken against every remaining offer at once is above the key
        of the best portfolio met so far, which starts from a single-site-swap local optimum."""
        nseg = len(segment_names)
        segix = {g: i for i, g in enumerate(segment_names)}
        floor_ticks = [floors_here[g][0] for g in segment_names]
        floor_pen = [floors_here[g][1] for g in segment_names]
        per_site: dict[str, list] = {}
        for o in cands:
            per_site.setdefault(o["site"]["sid"], []).append(
                (o["id"], cw * o["cost"], tuple(tk(x) for x in o["r"]), tuple(tk(x) for x in o["v"]),
                 segix[o["site"]["segment"]]))
        order = sorted(per_site)
        n = len(order)
        # what all later sites could still add, each interval and each segment on its own
        more = [[0] * width for _ in range(n + 1)]
        more_seg = [[0] * nseg for _ in range(n + 1)]
        for k in range(n - 1, -1, -1):
            opts = per_site[order[k]]
            more[k] = [more[k + 1][t] + max(r[t] for _, _, r, _, _ in opts) for t in range(width)]
            more_seg[k] = list(more_seg[k + 1])
            more_seg[k][opts[0][4]] += max(sum(r) for _, _, r, _, _ in opts)

        def key_of(rel, rec, segs, spent, used, k):
            gap = sum(goals[t][1] * max(0, goals[t][0] - rel[t] - more[k][t]) for t in range(width))
            deficit = sum(floor_pen[j] * max(0, floor_ticks[j] - segs[j] - more_seg[k][j]) for j in range(nseg))
            parts = [gap, deficit, spent + vw * sum(rec), sum(max(0, rel[t] - goals[t][0]) for t in range(width)),
                     used]
            return tuple(parts)

        def fits(rel, rec):
            return all(rel[t] <= caps[t][0] and rec[t] <= caps[t][1] for t in range(width))

        def total(pick):
            rel = [0] * width
            rec = [0] * width
            segs = [0] * nseg
            spent = used = 0
            for choice in pick:
                if choice is None:
                    continue
                _, cost, r, v, j = choice
                for t in range(width):
                    rel[t] += r[t]
                    rec[t] += v[t]
                segs[j] += sum(r)
                spent += cost
                used += 1
            return (key_of(rel, rec, segs, spent, used, n) if fits(rel, rec) else None)

        # incumbent: start empty, take the best single-site change until none improves
        pick: list = [None] * n
        best = total(pick)
        moved = True
        while moved:
            moved = False
            for k in range(n):
                for choice in [None] + per_site[order[k]]:
                    if choice is pick[k]:
                        continue
                    trial = pick[:k] + [choice] + pick[k + 1:]
                    got = total(trial)
                    if got is not None and got < best:
                        best, pick, moved = got, trial, True
        zero = (0,) * width
        table = {(zero, zero, (0,) * nseg): (0, 0, 1, ())}
        for k, sid in enumerate(order):
            nxt: dict = {}

            def put(state, item):
                old = nxt.get(state)
                if old is None or item[:2] < old[:2]:
                    nxt[state] = item
                elif item[:2] == old[:2]:
                    nxt[state] = (old[0], old[1], old[2] + item[2], max(old[3], item[3]))

            for (rel, rec, segs), (spent, used, ways, ids) in table.items():
                put((rel, rec, segs), (spent, used, ways, ids))
                for oid, cost, r, v, j in per_site[sid]:
                    nrel = tuple(rel[t] + r[t] for t in range(width))
                    nrec = tuple(rec[t] + v[t] for t in range(width))
                    if not fits(nrel, nrec):
                        continue
                    nseg_ = list(segs)
                    nseg_[j] = min(floor_ticks[j], nseg_[j] + sum(r))
                    put((nrel, nrec, tuple(nseg_)), (spent + cost, used + 1, ways, tuple(sorted(ids + (oid,)))))
            table = {}
            for (rel, rec, segs), item in nxt.items():
                done = key_of(rel, rec, segs, item[0], item[1], n)
                if done < best:
                    best = done
                if key_of(rel, rec, segs, item[0], item[1], k + 1) <= best:
                    table[(rel, rec, segs)] = item
            table = {s: it for s, it in table.items() if key_of(*s, it[0], it[1], k + 1) <= best}
        ways = 0
        ids: tuple = ()
        for (rel, rec, segs), (spent, used, w, got) in table.items():
            if key_of(rel, rec, segs, spent, used, n) == best:
                ways += w
                ids = max(ids, got)
        return ids, ways
