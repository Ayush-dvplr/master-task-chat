"""run_checks plus a WRONG / TIMEOUT / CRASH class for every failed positive check.

    python3 -B checks_wtc.py APP_ROOT OUT_JSON
"""
import importlib.util, json, os, sys, time
from pathlib import Path
WORK = Path(__file__).resolve().parents[1]
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
CORPORA = ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed")


def run_key(name):
    corpus = next((c for c in CORPORA if name.startswith(c + "_")), None)
    if corpus is None:
        return None
    rest = name[len(corpus) + 1:]
    for kind in ("ledger", "batch", "cycle"):
        if rest.startswith(kind + "_statement"):
            return kind, corpus
    if rest.startswith("statement"):
        return "statement", corpus
    return None


def main():
    app, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    os.environ["APP_ROOT"] = str(app)
    sys.path.insert(0, str(WORK / "rewardkit_stub"))
    spec = importlib.util.spec_from_file_location("bundle_tests", BUNDLE / "tests" / "test_output.py")
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    weights = dict(sys.modules["rewardkit"].REGISTERED)
    results, earned = {}, 0
    for name, weight in weights.items():
        started = time.time()
        value = bool(getattr(t, name)(app))
        cls = ""
        if not value and weight > 0:
            key = run_key(name)
            cls = "WRONG"
            if key:
                kind, corpus = key
                try:
                    if kind == "ledger":
                        t._ledger_run(corpus)
                    elif kind == "statement":
                        t._statement_run(corpus)
                    else:
                        t._statement_run(f"{kind}:{corpus}")
                except AssertionError as error:
                    cls = "TIMEOUT" if "no statements within" in str(error) else "CRASH"
                except Exception:
                    cls = "CRASH"
        results[name] = {"pass": value, "weight": weight, "class": cls, "sec": round(time.time() - started, 2)}
        earned += weight if value else 0
    positive = sum(w for w in weights.values() if w > 0)
    split = {c: sum(r["weight"] for r in results.values() if r["class"] == c) for c in ("WRONG", "TIMEOUT", "CRASH")}
    out.write_text(json.dumps({"score": earned / positive, "earned": earned, "positive": positive, "split": split,
                               "checks": results}, indent=1))
    print("SCORE %.4f" % (earned / positive), split)


if __name__ == "__main__":
    main()
