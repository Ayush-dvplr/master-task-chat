"""Per book and per baseline: which whole documents differ from the reference, and on how many images."""
import sys
import bookgen as bg
import variants as V

ABBR = {"module_core.json": "c", "module_metrics.json": "m", "dependency_resolution.json": "d", "summary.json": "s"}


def books(seed):
    return {
        "S": bg.build_book(seed, "light", 24, light=True),
        "H1": bg.build_book(seed + 1, "dense", 12, dense=True, min_restarts=2),
        "H2": bg.build_book(seed + 2, "restart", 12, dense=True, min_restarts=2),
        "H3": bg.build_book(seed + 3, "max", 12, dense=True, min_restarts=2),
    }


def main(seed):
    bk = books(seed)
    ref = {k: bg.documents(b) for k, b in bk.items()}
    same = {k: V.documents(b, set()) == ref[k] for k, b in bk.items()}
    print("flags-off equals reference:", same)
    for name, flags in V.VARS.items():
        row = []
        for k, b in bk.items():
            got = V.documents(b, flags)
            docs = "".join(ABBR[d] for d in ABBR if got[d] != ref[k][d])
            ncore = sum(1 for i in ref[k]["module_core.json"]["images"]
                        if got["module_core.json"]["images"][i] != ref[k]["module_core.json"]["images"][i])
            row.append("%s:%s/%d" % (k, docs or "-", ncore))
        print("%-24s %s" % (name, "  ".join(row)))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
