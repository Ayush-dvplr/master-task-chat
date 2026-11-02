import random, sys, time, resource
from pathlib import Path
sys.path.insert(0, "/w")
from book_digests import load
tt = load(sys.argv[1])
ns = dict(vars(tt))
exec(compile(Path(sys.argv[2]).read_text(), sys.argv[2], "exec"), ns)
for k in ("_link_by_link", "_one_queue"):
    f = ns[k]
    def wrap(root, sites, elist, need, wt, f=f, k=k):
        t = time.time()
        r = f(root, sites, elist, need, wt)
        dt = time.time() - t
        if dt > 0.2:
            print("  slow", k, "sites", len(sites), "links", len(elist), "need", len(need), round(dt, 2),
                  "rss MB", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024, flush=True)
        return r
    ns[k] = wrap
rng = random.Random(int(sys.argv[3]))
for i in range(int(sys.argv[4])):
    P = tt._wide_project(rng)
    proj = tt._as_project(P)
    t = time.time(); old = tt._optimum(proj); to = time.time() - t
    t = time.time(); new = ns["_optimum"](proj); tn = time.time() - t
    print(i, "n", proj["n"], "old", round(to, 2), "new", round(tn, 2), "same", old == new, flush=True)
