

# ===================================================================== gateway observations
GATE_ENVS = ("dev", "prod")


def gateway_cfg(D, at, memo=None):
    if memo is not None and at in memo:
        return memo[at]
    D2 = dict(D)
    D2["site"] = {k: dict(v) for k, v in D["site"].items()}
    D2["site"]["anchor"]["as_of"] = D2["site"]["anchor"]["recorded_cutoff"] = utc(at)
    c, _, _ = settle_config(D2)
    c = dict(c)
    for e in GATE_ENVS:
        c[e + ".attestation_required"] = False
        c[e + ".sod_enforced"] = False
    if memo is not None:
        memo[at] = c
    return c


def gateway_states(D, rows, conv, memo=None):
    """observed_state the gateway shows for each row under conventions conv."""
    by_at = defaultdict(list)
    for i, row in enumerate(rows):
        by_at[stamp(row["reviewed_at"])].append(i)
    out = [None] * len(rows)
    for at in sorted(by_at):
        W = World(D, gateway_cfg(D, at, memo), conv)
        keys = {}
        for i in by_at[at]:
            row = rows[i]
            env = row["env"]
            if env not in keys:
                keys[env] = W.profile(env)["keys"]
            pid = W.who(row["subject"])
            out[i] = "in_effect" if pid is not None and pid + "|" + row["permission"] in keys[env] else "not_in_effect"
    return out


def observe(root: Path, g, seed: int, conv=None) -> None:
    conv = dict(SHIPPED_CONV, **(conv or {}))
    r = random.Random(seed * 13 + 7)
    path = root / "access_attestations.csv"
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    fields = list(rows[0])
    D = load(root)
    cfg, _, _ = settle_config(D)
    cfg = dict(cfg)
    for e in GATE_ENVS:
        cfg[e + ".attestation_required"] = False
        cfg[e + ".sod_enforced"] = False
    W0 = World(D, cfg, conv)
    E, R = W0.E, W0.R
    live = sorted(p for p, s in W0.profile("prod")["status"].items() if s == "eligible" and p.startswith("emp:"))
    hand = {p: sorted(h) for p, h in W0.mine.items()}
    seq = max(int(x["attestation_id"].split("-")[1]) for x in rows)
    new = []
    memo = {}

    def add(pid, perm, env, at):
        nonlocal seq
        rev = r.choice([p for p in live if p != pid and hand.get(p)])
        seq += 1
        new.append({"attestation_id": f"AT-{seq:06d}", "reviewer": r.choice(hand[rev]), "subject": r.choice(hand[pid]),
                    "permission": perm, "env": env, "reviewed_at": iso_off(at, r.choice(g.offsets)), "decision": "keep",
                    "observed_state": "", "recorded_at": iso_z(min(at + 600, R - 1))})

    def held(at, pid):
        c = gateway_cfg(D, at, memo)
        W = World(D, c, conv)
        return sorted((e, k.split("|")[1]) for e in GATE_ENVS for k in W.profile(e)["keys"] if k.startswith(pid + "|"))

    lo_lim, hi_lim = E - 300 * DAY, min(E, R) - 2 * HOUR
    zones = sorted(D["tz"])
    alts = [("hr", h) for h in ["site", "utc"] + ["zone:" + z for z in zones] if h != conv["hr"]]
    alts += [("start", v) for v in ("requested", "decided", "recorded", "latest") if v != conv["start"]]
    alts += [("window", v) for v in ("half", "closed") if v != conv["window"]]
    kills = {a: 0 for a in alts}

    def row(pid, perm, env, at):
        return {"subject": hand[pid][0], "permission": perm, "env": env, "reviewed_at": iso_z(at)}, (pid, perm, env, at)

    def group(specs):
        rs = [row(*x) for x in specs]
        return [x[0] for x in rs], [x[1] for x in rs]

    def try_specs(dim, specs):
        rs, sp = group(specs)
        open_ = [a for a in alts if a[0] == dim and kills[a] < 2]
        if not open_ or not rs:
            return
        base = gateway_states(D, rs, conv, memo)
        keep = set()
        for a in open_:
            st = gateway_states(D, rs, dict(conv, **{a[0]: a[1]}), memo)
            hit = [i for i in range(len(rs)) if st[i] != base[i]]
            if hit:
                kills[a] += 1
                keep.update(hit)
        for i in sorted(keep):
            add(*sp[i])

    # HR clock evidence: instants between the candidate readings of an event's date
    evs = sorted((eid, pid, kind, dd) for eid, (pid, kind, dd) in W0.hr_ev.items())
    r.shuffle(evs)
    probes = 0
    for eid, pid, kind, dd in evs:
        if probes >= 40 or all(kills[a] >= 2 for a in alts if a[0] == "hr"):
            break
        if not hand.get(pid) or kind not in ("terminate", "hire", "rehire", "leave_start", "leave_end"):
            continue
        tz = W0.emp_tz[pid]
        bs = sorted({W0.clock.wall(tz, dd), _epoch(*dd)} | {W0.clock.wall(z, dd) for z in zones})
        lo_i, hi_i = bs[0] - 3 * HOUR, bs[-1] + 3 * HOUR
        if not (lo_lim < lo_i and hi_i < hi_lim):
            continue
        probes += 1
        on = held(lo_i if kind in ("terminate", "leave_start") else hi_i, pid)
        if not on:
            continue
        env, perm = r.choice(on)
        ats = [lo_i] + [(a + b) // 2 for a, b in zip(bs, bs[1:]) if b - a >= 120] + [hi_i]
        try_specs("hr", [(pid, perm, env, at) for at in ats])
    # grant start and window evidence: instants between candidate grant ends, and the planted end itself
    Ws = {s: World(D, cfg, dict(conv, start=s)) for s in ("requested", "decided", "recorded", "latest")}
    cands = []
    for rid in sorted(W0.tk):
        ts_ = [Ws[s].tk[rid] for s in Ws]
        if any(t.get("state") != "approved" for t in ts_) or W0.tk[rid]["ben"] not in hand:
            continue
        ends = sorted({t["end"] for t in ts_})
        if ends[0] - 2 * HOUR < lo_lim or ends[-1] + 2 * HOUR > hi_lim:
            continue
        cands.append(rid)
    r.shuffle(cands)
    cands.sort(key=lambda rid: -len({Ws[s].tk[rid]["end"] for s in Ws}))
    for rid in cands[:60]:
        if all(kills[a] >= 2 for a in alts if a[0] in ("start", "window")):
            break
        t = W0.tk[rid]
        ends = sorted({Ws[s].tk[rid]["end"] for s in Ws})
        perm = sorted(t["perms"])[0]
        ats = sorted({ends[0] - 1800, t["end"], t["end"] - 1, ends[-1] + 1800} | {(a + b) // 2 for a, b in zip(ends, ends[1:])})
        specs = [(t["ben"], perm, t["env"], at) for at in ats]
        if len(ends) > 1:
            try_specs("start", specs)
        try_specs("window", specs)
    observe.kills = dict(kills)
    rows += new
    states = gateway_states(D, rows, conv, memo)
    for row, st in zip(rows, states):
        row["observed_state"] = st
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow(row)
    path.write_text(buf.getvalue(), encoding="utf-8")
