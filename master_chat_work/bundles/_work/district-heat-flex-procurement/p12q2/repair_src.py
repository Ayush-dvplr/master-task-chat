"""One-shot repair of test_output.src.py after gen_wide_truth.py's regex cut src_before L143-L1137.

Rebuilds: current L1-470 (header, _apportion, _WIDE_TRUTH table) + _exact + src_before L143-L1137 with
the F2/F5/F15 edits + current L471-end. Run once: python3 -B p12q2/repair_src.py
"""
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
cur = (WORK / "test_output.src.py").read_text(encoding="utf-8").split("\n")
old = (WORK / "p12q2/src_before/test_output.src.py").read_text(encoding="utf-8").split("\n")
assert cur[469] == "}" and cur[148].startswith("_WIDE_TRUTH"), "unexpected current layout"
assert old[142].startswith("def reference(") and old[1136] == "}", "unexpected src_before layout"

EXACT = '''def _exact(cands: list[tuple], goals: list[tuple[int, int]], caps: list[tuple[int, int]],
           floors: list[tuple[int, int]], cw: int, vw: int, width: int) -> tuple[tuple[str, ...], int]:
    """Optimal portfolio of one event-region by a table over sites, independent of solve.py's branch search.

    cands holds (site_id, offer_id, cost, relief ticks, recovery ticks, segment index) per candidate offer.
    Sites are taken one at a time, those with the most relief first; the table maps what has been chosen so
    far (relief and recovery per interval, segment relief up to its floor) to the cheapest, then smallest,
    way of getting there, with the number of such ways and the greatest sorted id list among them. A state
    is dropped once even all relief of the sites still to come cannot bring its key level with the best
    whole portfolio seen. Returns the greatest sorted id list of the optimal portfolios and their number.
    """
    nseg = len(floors)
    floor_ticks = [f[0] for f in floors]
    floor_pen = [f[1] for f in floors]
    per_site: dict[str, list[tuple]] = {}
    for sid, oid, cost, r, v, seg in cands:
        per_site.setdefault(sid, []).append((oid, cw * cost, r, v, seg))
    order = sorted(per_site)
    order.sort(key=lambda s: -max(sum(o[2]) for o in per_site[s]))
    n = len(order)
    more = [[0] * width for _ in range(n + 1)]
    more_seg = [[0] * nseg for _ in range(n + 1)]
    for k in range(n - 1, -1, -1):
        opts = per_site[order[k]]
        more[k] = [more[k + 1][t] + max(o[2][t] for o in opts) for t in range(width)]
        more_seg[k] = list(more_seg[k + 1])
        more_seg[k][opts[0][4]] += max(sum(o[2]) for o in opts)

    def key_at(rel, rec, segs, spent, used, k):
        gaps = [goals[t][0] - rel[t] for t in range(width)]
        return (sum(goals[t][1] * max(0, gaps[t] - more[k][t]) for t in range(width)),
                sum(floor_pen[j] * max(0, floor_ticks[j] - segs[j] - more_seg[k][j]) for j in range(nseg)),
                spent + vw * sum(rec), sum(max(0, -g) for g in gaps), used)

    def fits(rel, rec):
        return all(rel[t] <= caps[t][0] and rec[t] <= caps[t][1] for t in range(width))

    def total(pick):
        rel, rec, segs = [0] * width, [0] * width, [0] * nseg
        spent = used = 0
        for ch in pick:
            if ch is None:
                continue
            _, cost, r, v, j = ch
            for t in range(width):
                rel[t] += r[t]
                rec[t] += v[t]
            segs[j] += sum(r)
            spent += cost
            used += 1
        return key_at(rel, rec, segs, spent, used, n) if fits(rel, rec) else None

    # A first whole portfolio to cut against: improve one site's choice at a time from the empty portfolio.
    pick: list = [None] * n
    best = total(pick)
    moved = True
    while moved:
        moved = False
        for k in range(n):
            for ch in [None] + per_site[order[k]]:
                if ch is pick[k]:
                    continue
                trial = pick[:k] + [ch] + pick[k + 1:]
                got = total(trial)
                if got is not None and got < best:
                    best, pick, moved = got, trial, True
    zero = (0,) * width
    table = {(zero, zero, (0,) * nseg): (0, 0, 1, ())}
    for k, sid in enumerate(order):
        nxt: dict = {}
        for (rel, rec, segs), item in table.items():
            spent, used, ways, ids = item
            states = [((rel, rec, segs), item)]
            for oid, cost, r, v, j in per_site[sid]:
                nrel = tuple(rel[t] + r[t] for t in range(width))
                nrec = tuple(rec[t] + v[t] for t in range(width))
                if not fits(nrel, nrec):
                    continue
                ns = list(segs)
                ns[j] = min(floor_ticks[j], ns[j] + sum(r))
                states.append(((nrel, nrec, tuple(ns)), (spent + cost, used + 1, ways, tuple(sorted(ids + (oid,))))))
            for state, it in states:
                was = nxt.get(state)
                if was is None or it[:2] < was[:2]:
                    nxt[state] = it
                elif it[:2] == was[:2]:
                    nxt[state] = (was[0], was[1], was[2] + it[2], max(was[3], it[3]))
        for (rel, rec, segs), it in nxt.items():
            done = key_at(rel, rec, segs, it[0], it[1], n)
            if done < best:
                best = done
        table = {s: it for s, it in nxt.items() if key_at(*s, it[0], it[1], k + 1) <= best}
    ways, ids = 0, ()
    for (rel, rec, segs), (spent, used, w, got) in table.items():
        if key_at(rel, rec, segs, spent, used, n) == best:
            ways += w
            ids = max(ids, got)
    return ids, ways
'''

OPTIMUM = '''    def optimum(cands: list[dict[str, Any]], goals, caps, floors_here, cw: int, vw: int, width: int):
        """The optimum by _exact, read from _WIDE_TRUTH when the event-region is one of the wide extracts'."""
        plain = [(o["site"]["sid"], o["id"], o["cost"], tuple(tk(x) for x in o["r"]), tuple(tk(x) for x in o["v"]),
                  segment_names.index(o["site"]["segment"])) for o in cands]
        floors_list = [floors_here[g] for g in segment_names]
        digest = hashlib.sha256(repr((plain, goals, caps, floors_list, cw, vw, width)).encode()).hexdigest()[:24]
        if digest in _WIDE_TRUTH:
            ways, ids = _WIDE_TRUTH[digest]
            return tuple(ids.split()), ways
        return _exact(plain, goals, caps, floors_list, cw, vw, width)
'''

mid = old[142:1137]  # src_before L143..L1137
text = "\n".join(mid)


def swap(text: str, a: str, b: str) -> str:
    assert text.count(a) == 1, a[:80]
    return text.replace(a, b)


# (a) bounded -> optimum
i = text.index("    def bounded(")
j = text.index("    sites_of: dict[tuple[str, str], list[dict[str, Any]]] = {}")
text = text[:i] + OPTIMUM + "\n" + text[j:]
# (b) selection
text = swap(text, "solver = search if lazy & SEARCH_FLAGS else bounded", "solver = search if lazy & SEARCH_FLAGS else optimum")
# (c) receipt (F5)
text = swap(text, '"""export_manifest.tsv: record counts and written-field sums of the files just written."""',
            '"""export_manifest.tsv: one line per file just written, with written-field sums where a field is named."""')
for a, b in (
    ('lines = [("events.json", len(json.loads((folder / "events.json").read_text(encoding="utf-8"))), "", "")]',
     'lines = [("events.json", "", "")]'),
    ('lines += [(name, len(rows), f, str(sum(int(r[f]) for r in rows))) for f in fields] or [(name, len(rows), "", "")]',
     'lines += [(name, f, str(sum(int(r[f]) for r in rows))) for f in fields] or [(name, "", "")]'),
    ('lines.append(("site_allowances.tsv", len(held), "allowance_ticks",', 'lines.append(("site_allowances.tsv", "allowance_ticks",'),
    ('lines.append(("feeder_limits.txt", len(feeder), "relief_ceiling_wh",', 'lines.append(("feeder_limits.txt", "relief_ceiling_wh",'),
    ('lines.append(("pools.txt", len(pools), "pool_cents",', 'lines.append(("pools.txt", "pool_cents",'),
    ('    states = [x for x in (folder / "site_state.jsonl").read_text(encoding="utf-8").split("\\n") if x.strip()]\n'
     '    lines.append(("site_state.jsonl", len(states), "", ""))',
     '    lines.append(("site_state.jsonl", "", ""))'),
    ('lines.append(("segment_floors.json", len(floors), "floor_wh",', 'lines.append(("segment_floors.json", "floor_wh",'),
    ('lines.append(("rate_cards.xml", len(cards), "base",', 'lines.append(("rate_cards.xml", "base",'),
    ('            "# Each line names a file and gives its records, counted the way data_quality.json counts the\\n"\n'
     '            "# rows of that file. Where a field is named, field_sum is the sum of that field\'s values as they\\n"\n'
     '            "# are written in the file, over all of its records; otherwise field and field_sum are empty.\\n"\n',
     '            "# Each line names a file. Where a field is named, field_sum is the sum of that field\'s values as\\n"\n'
     '            "# they are written in the file, over all of its records; otherwise field and field_sum are empty.\\n"\n'),
    ('"file\\trecords\\tfield\\tfield_sum\\n")', '"file\\tfield\\tfield_sum\\n")'),
    ('text += "".join(f"{a}\\t{b}\\t{c}\\t{d}\\n" for a, b, c, d in lines)', 'text += "".join(f"{a}\\t{b}\\t{c}\\n" for a, b, c in lines)'),
):
    text = swap(text, a, b)
# (d) case_spec (F15)
i = text.index('    if name == "allowance_order":')
j = text.index('        spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "allowances": allowances}')
text = text[:i] + '''    if name in ("mut_allowance", "mut_allowance_moved"):
        # Sites that take part in several events: what an earlier event draws is gone for a later one. The
        # events start in an order that differs from both the id order and the order of the written strings.
        plan = tuple((eid, start, ("AL-6", "AL-7", "AL-8")) for eid, start in (
            ("T5-0201", "2026-12-03T10:00:00+00:00"), ("T5-0202", "2026-12-03T09:00:00+01:00"),
            ("T5-0203", "2026-12-03T09:00:00+00:00")))
        allowances = {"AL-6": 190 if name == "mut_allowance_moved" else 130, "AL-7": 70, "AL-8": 1000}
        relief = {"AL-6": [400, 200], "AL-7": [300, 300], "AL-8": [200, 100]}
''' + text[j:]

out = "\n".join(cur[:470]) + "\n\n\n" + EXACT + "\n\n" + text + "\n" + "\n".join(cur[470:])
(WORK / "test_output.src.py").write_text(out, encoding="utf-8")
print("written", out.count("\n") + 1, "lines")
