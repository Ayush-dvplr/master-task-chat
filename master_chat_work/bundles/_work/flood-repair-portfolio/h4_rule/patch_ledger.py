import sys
p = sys.argv[1]
s = open(p).read()
def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
rep("import io\nimport json\n", "import io\nimport itertools\nimport json\n")
rep("        chosen = _portfolio(info, joined)\n", "        chosen = _capped(info, joined, self.mode)\n")
rep('''    return [names[i] for i in range(n) if picked >> i & 1]


def expected(''', '''    return [names[i] for i in range(n) if picked >> i & 1]


def _capped(info: dict[str, dict[str, Any]], joined: dict[frozenset[str], set[str]],
            mode: dict[str, str]) -> list[str]:
    crews: dict[str, list[str]] = {}
    for p, d in info.items():
        if mode[d["crew"]] == "shared":
            crews.setdefault(d["crew"], []).append(p)
    over = [sorted(ps) for ps in crews.values() if len(ps) > CAP]
    if not over:
        return _portfolio(info, joined)
    best = None
    for keep in itertools.product(*(itertools.combinations(ps, CAP) for ps in over)):
        out = {p for ps in over for p in ps} - {p for ks in keep for p in ks}
        part = {p: d for p, d in info.items() if p not in out}
        pick = _portfolio(part, {k: v for k, v in joined.items() if not k & out})
        key = (-sum(info[p]["benefit"] for p in pick), sorted(pick))
        if best is None or key < best:
            best = key
    return best[1]


def expected(''')
rep('''    """Every planned round's reported portfolio is conflict-free, maximal and totals its benefits."""''',
    '''    """Every planned round's reported portfolio is conflict-free, within the shared-crew limit, maximal and totals its benefits."""''')
rep('''        taken = set(picks)
        for p in x["info"]:
            if p not in taken:
                assert any''', '''        taken = set(picks)
        held: dict[str, int] = {}
        for p in picks:
            c = x["info"][p]["crew"]
            if led.mode[c] == "shared":
                held[c] = held.get(c, 0) + 1
        assert all(v <= CAP for v in held.values()), \\
            "round %s gives a shared crew more than four proposals" % entry["round"]
        for p in x["info"]:
            if p not in taken and held.get(x["info"][p]["crew"], 0) < CAP:
                assert any''')
open(p, "w").write(s)
print("ok")
