"""Kill-test program: proto reference engine + one convention strategy (strategy.json)."""
import argparse, importlib.util, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("t", HERE / "ref.py")
t = importlib.util.module_from_spec(spec)
sys.modules["t"] = t
spec.loader.exec_module(t)
STRAT = json.loads((HERE / "strategy.json").read_text())
DAY = 86400


def cand_space(D):
    s = STRAT
    if s["kind"] == "fixed":
        return [dict(s["conv"])]
    hs = []
    for h in s["hr"]:
        hs += ["zone:" + z for z in sorted(D["tz"])] if h == "zones" else [h]
    return [dict(hr=h, start=x, window=w) for h in hs for x in s["start"] for w in s["window"]]


def infer(D, root):
    cands = cand_space(D)
    if len(cands) == 1:
        return cands[0], {"worlds": 0}
    rows = []
    for _, row in D["att"]:
        try:
            at = t.stamp(row["reviewed_at"])
        except Exception:
            continue
        if row.get("observed_state") in ("in_effect", "not_in_effect"):
            rows.append((at, row))
    cfg, _, _ = t.settle_config(D)
    if STRAT.get("mode") == "percand":
        return percand(D, cfg, cands, rows)
    if STRAT.get("mode") == "rr":
        return roundrobin(D, cfg, cands, rows)
    W0 = t.World(D, cfg, None)
    hr_days = {}
    for eid, (pid, kind, dd) in W0.hr_ev.items():
        hr_days.setdefault(pid, []).append(t._epoch(*dd))
    for pid, (a, b, sp, tz) in W0.ctr.items():
        hr_days.setdefault(pid, []).extend([t._epoch(*a), t._epoch(*t.shift_day(b, 1))])
    ends = {}
    for x in ("requested", "decided", "recorded"):
        Wx = t.World(D, cfg, dict(start=x))
        for rid, tk in Wx.tk.items():
            if "end" in tk and tk.get("ben"):
                ends.setdefault(tk["ben"], []).extend([tk["begin"], tk["end"]])

    def score(at, row):
        pid = W0.who(row["subject"])
        if pid is None:
            return 9 * DAY
        near = [abs(at - d) for d in hr_days.get(pid, [])] + [abs(at - d) for d in ends.get(pid, [])]
        return min(near) if near else 9 * DAY
    by_at = {}
    for at, row in rows:
        by_at.setdefault(at, []).append(row)
    pri = sorted(by_at, key=lambda a: (min(score(a, r) for r in by_at[a]), a))
    surv, agree, memo, worlds = list(cands), [0] * len(cands), {}, 0
    for at in pri:
        if len(surv) <= 1:
            break
        nxt = []
        for c in surv:
            st = t.gateway_states(D, by_at[at], c, memo)
            worlds += 1
            ok = sum(s == r["observed_state"] for s, r in zip(st, by_at[at]))
            agree[cands.index(c)] += ok
            if ok == len(st):
                nxt.append(c)
        surv = nxt
    if surv:
        return surv[0], {"worlds": worlds, "survivors": len(surv)}
    best = max(range(len(cands)), key=lambda i: agree[i])
    return cands[best], {"worlds": worlds, "survivors": 0}


def percand(D, cfg, cands, rows, cap=12):
    by_at = {}
    for at, row in rows:
        by_at.setdefault(at, []).append(row)
    marks = {}
    for c in cands:
        Wc = t.World(D, cfg, c)
        m = {}
        for pid, life in Wc.life.items():
            m.setdefault(pid, []).extend(at for at, _, _ in life)
        for pid, (a, b, sp, tz) in Wc.ctr.items():
            m.setdefault(pid, []).extend([Wc.hr_wall(tz, a), Wc.hr_wall(tz, t.shift_day(b, 1))])
        for tk in Wc.tk.values():
            if "end" in tk and tk.get("ben"):
                m.setdefault(tk["ben"], []).extend([tk["begin"], tk["end"]])
        marks[repr(c)] = (Wc, m)
    worlds, memo, surv = len(cands), {}, []
    for c in cands:
        Wc, m = marks[repr(c)]
        rival = {}
        for o in cands:
            if o is c:
                continue
            for pid, xs in marks[repr(o)][1].items():
                rival.setdefault(pid, set()).update(xs)
        def score(at):
            best = 9 * DAY
            for r in by_at[at]:
                pid = Wc.who(r["subject"])
                xs = set(m.get(pid, ())) ^ rival.get(pid, set()) if pid else ()
                for x in xs:
                    best = min(best, abs(at - x))
            return best
        order = sorted(by_at, key=lambda a: (score(a), a))[:cap]
        alive = True
        for at in order:
            st = t.gateway_states(D, by_at[at], c, memo)
            worlds += 1
            if any(s != r["observed_state"] for s, r in zip(st, by_at[at])):
                alive = False
                break
        if alive:
            surv.append(c)
    return (surv[0] if surv else cands[0]), {"worlds": worlds, "survivors": len(surv)}


def roundrobin(D, cfg, cands, rows):
    by_at = {}
    for at, row in rows:
        by_at.setdefault(at, []).append(row)
    marks = {}
    for c in cands:
        Wc = t.World(D, cfg, c)
        m = {}
        for pid, life in Wc.life.items():
            m.setdefault(pid, set()).update(at for at, _, _ in life)
        for pid, (a, b, sp, tz) in Wc.ctr.items():
            m.setdefault(pid, set()).update([Wc.hr_wall(tz, a), Wc.hr_wall(tz, t.shift_day(b, 1))])
        for tk in Wc.tk.values():
            if "end" in tk and tk.get("ben"):
                m.setdefault(tk["ben"], set()).update([tk["begin"], tk["end"]])
        marks[repr(c)] = (Wc, m)
    queues = {}
    for c in cands:
        Wc, m = marks[repr(c)]
        rival = {}
        for o in cands:
            if o is not c:
                for pid, xs in marks[repr(o)][1].items():
                    rival.setdefault(pid, set()).update(xs)

        def score(at):
            best = 9 * DAY
            for r in by_at[at]:
                pid = Wc.who(r["subject"])
                if pid:
                    for x in m.get(pid, set()) ^ rival.get(pid, set()):
                        best = min(best, abs(at - x))
            return best
        queues[repr(c)] = sorted(by_at, key=lambda a: (score(a), a))
    alive, done, memo, worlds, rounds = list(cands), set(), {}, len(cands), 0
    pos = {repr(c): 0 for c in cands}
    while len(alive) > 1:
        rounds += 1
        picked = []
        for c in alive:
            q, k = queues[repr(c)], pos[repr(c)]
            while k < len(q) and q[k] in done:
                k += 1
            pos[repr(c)] = k
            if k < len(q):
                picked.append(q[k])
                done.add(q[k])
        if not picked:
            break
        for at in picked:
            nxt = []
            for c in alive:
                st = t.gateway_states(D, by_at[at], c, memo)
                worlds += 1
                if all(s == r["observed_state"] for s, r in zip(st, by_at[at])):
                    nxt.append(c)
            alive = nxt
            if len(alive) <= 1:
                break
    return (alive[0] if alive else cands[0]), {"worlds": worlds, "survivors": len(alive), "rounds": rounds}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--data", required=True)
    ap.add_argument("--config")
    ap.add_argument("--profile")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = Path(a.data)
    D = t.load(root)
    if a.cmd == "resolve-config":
        cfg, _, _ = t.settle_config(D)
        Path(a.out).write_text(json.dumps(cfg, sort_keys=True, indent=2))
        return
    t0 = time.time()
    conv, info = infer(D, root)
    sys.stderr.write(f"conv {conv} {info} {time.time() - t0:.1f}s\n")
    cfg, prof, audit, summ, _ = t.everything(root, conv)
    names = sorted(p.name for p in root.iterdir() if p.is_file())
    doc = {"compile": lambda: prof[a.profile], "audit": lambda: audit,
           "summarize": lambda: dict(summ, inputs=names, input_count=len(names))}[a.cmd]()
    Path(a.out).write_text(json.dumps(doc, sort_keys=True, indent=2))
    (Path(a.out).parent / "conv.log").open("a").write(f"{a.cmd} {conv} {info} {time.time() - t0:.1f}s\n")


if __name__ == "__main__":
    main()
