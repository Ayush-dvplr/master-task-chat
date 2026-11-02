"""python3 -B newbooks.py TEST_OUTPUT [--write]: regenerate _BOOKS sha256 with capped counts using the
generator embedded in TEST_OUTPUT; compare with the prototype meta; optionally rewrite the literal."""
import ast, hashlib, json, os, pprint, sys
p = sys.argv[1]
text = open(p, encoding="utf-8").read()
head = "_BOOKS: dict[str, dict[str, Any]] = "
start = text.index(head) + len(head)
end = text.index("\n\n", start)
lit = text[start:end]
table = ast.literal_eval(lit)
orig = {k: dict(v) for k, v in table.items()}
g0 = text.index("# Seeded book generator")
gsrc = text[:text.index("from rewardkit")] + text[g0:text.index(head)]
ns = {"__name__": "gen"}
exec(compile(gsrc, "gen", "exec"), ns)
want = {"H1": 3, "H2": 3, "H3": 3, "M": 2}
here = os.path.dirname(os.path.abspath(__file__))
for name, e in table.items():
    spec = dict(e["spec"])
    if name in want:
        spec["capped"] = want[name]
    files, meta = ns["make_book"](e["seed"], spec)
    d = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    proto = None
    mp = os.path.join(here, "proto", name + "c.meta.json")
    if name in want and os.path.exists(mp):
        proto = json.load(open(mp))
        assert proto["sha256"] == d, (name, "differs from prototype")
        assert proto["capped"] == json.loads(json.dumps(meta["capped"])), name
    if name not in want:
        assert d == e["sha256"], (name, "unchanged book moved")
    print(name, e["seed"], e["sha256"][:12], "->", d[:12], "proto_match" if proto else "", sorted(meta["capped"]))
    e["spec"] = spec
    e["sha256"] = d
if "--write" in sys.argv:
    new = lit
    for name in want:
        e = table[name]
        a = "'%s': {'seed': %d," % (name, e["seed"])
        assert new.count(a) == 1, name
        i0 = new.index(a)
        j = new.index("'crews':", i0)
        ind = new.rindex("\n", 0, j) + 1
        pad = new[ind:j]
        seg = new[i0:j].replace(orig[name]["sha256"], e["sha256"])
        new = new[:i0] + seg + "'capped': %d,\n" % want[name] + pad + new[j:]
    assert ast.literal_eval(new) == table
    open(p, "w", encoding="utf-8").write(text[:start] + new + text[end:])
    print("written")
print("ALL_DONE")
