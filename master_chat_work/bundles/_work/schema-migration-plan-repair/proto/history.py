"""Scratch: long hidden replay corpora (P-2 prototype) built from the tests' world family.

    python3 -B history.py OUTDIR [n_corpora] [idents] [versions]

Writes OUTDIR/<name>/ job folders (contracts, feed, corrections, manifest) plus
OUTDIR/<name>/expected.json from the tests' reference pipeline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORK / "rewardkit_stub"))
_spec = importlib.util.spec_from_file_location("tests_src", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

FIELD_OPS = ["rename:{a}>{b}", "rename:{b}>{a}", "rename:{c}>{a}", "drop:{a}", "drop:{b}", "add:{a}", "add:{b}",
             "cast:{a}:int", "cast:{b}:float", "cast:{a}:str", "drop:{c}", "add:{c}"]


def history(w, idents: int, versions: int) -> None:
    """One domain whose edges chain rename/drop/add/cast on shared names; many identities, long version runs."""
    n = 7
    dom, s = w.domain(n)
    a, b, c, p = (w.fresh(x, 4) for x in "abcp")
    names = {"a": a, "b": b, "c": c}
    w.policy += [(dom, a, '"da"', "", ""), (dom, b, "0", "absent_or_null", "present"), (dom, c, '"dc"', "", "absent"),
                 (dom, p, "", "", "present")]
    pairs = [(i, i + 1) for i in range(n - 1)] + [(i, i + 2) for i in range(n - 2)] + [(2, 1), (4, 2), (5, 3)]
    for i, j in pairs:
        for _ in range(w.rng.randint(1, 2)):
            req = ";".join(f"{w.rng.choice(['has', 'lacks'])}:{w.rng.choice([a, b, c, p])}"
                           for _ in range(w.rng.choice([0, 0, 1, 1, 2])))
            ops = ";".join(w.rng.choice(FIELD_OPS).format(**names) for _ in range(w.rng.choice([0, 1, 1, 2, 3])))
            w.edge(s[i], s[j], req, ops, w.rng.randint(1, 9))

    def payload() -> dict:
        out: dict = {}
        for f in (a, b, c, p, "memo"):
            roll = w.rng.random()
            if roll < 0.25:
                continue
            out[f] = None if roll < 0.4 else ("NULL" if roll < 0.5 else T._val(w.rng))
        return out

    for _ in range(idents):
        partner, pid = w.who()
        forms = [pid, w.partners[pid][0]] + [r for r, t in w.relays if t == pid]
        key = w.fresh("k", 6)
        src = w.rng.choice(s[:-1])
        seen: list[tuple[str, dict]] = []
        for _ in range(versions):
            roll = w.rng.random()
            if seen and roll < 0.3:
                sch, pay = w.rng.choice(seen)
            else:
                sch, pay = (src if w.rng.random() < 0.7 else w.rng.choice(s[:-1])), payload()
                seen.append((sch, pay))
                if w.rng.random() < 0.5:
                    w.fix(f"REISSUE {w.rng.choice(forms)} {key} {T._fp(sch, pay)[:12]}")
            seq = w.rng.randint(1, 50000) if w.rng.random() < 0.5 else None
            w.line(w.rng.choice(forms), sch, json.loads(json.dumps(pay)), key, w.batch(seq=seq))
        for _ in range(w.rng.randint(0, 3)):
            f = w.rng.choice([a, b, c, p])
            at = w.rng.choice(s)
            kind = w.rng.choice(["SET", "UNSET", "NULL"])
            text = f"{kind} {w.rng.choice(forms)} {key} AT {at} {f}" + (f" {json.dumps(T._val(w.rng))}" if kind == "SET" else "")
            w.fix(text)


def corpus(salt: int, idents: int, versions: int):
    w = T._World(salt, ("FEED",))
    for _ in range(3):
        history(w, idents, versions)
    T._filler(w, 16)
    return w.finish()


def main() -> None:
    out = Path(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    idents = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    versions = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    out.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        name = f"hist_{index:02d}"
        world = corpus(910000 + index, idents, versions)
        spec, lines, seqs, corrections, receipts = world
        start = time.time()
        expected = T._ref_pipeline(spec, T._feed_text(lines), seqs, T._corrections_text(corrections), receipts)
        took = time.time() - start
        job = T._feed_job(spec, lines, seqs, corrections, receipts)
        folder = out / name
        folder.mkdir(exist_ok=True)
        (folder / "job.json").write_text(json.dumps(job), encoding="utf-8")
        (folder / "expected.json").write_text(json.dumps(expected, sort_keys=True), encoding="utf-8")
        st = expected["summary"]["by_status"]
        print(name, len(lines), "lines", len(corrections), "corr", f"ref {took:.2f}s", json.dumps(st, sort_keys=True),
              "invalid", len(expected["summary"]["invalid_corrections"]))


if __name__ == "__main__":
    main()
