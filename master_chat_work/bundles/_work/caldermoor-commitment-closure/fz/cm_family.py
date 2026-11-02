

# ------------------------------------- family: survivor redistribution (840adf9)
# commitment-protocol.md section 9: after the floor drops a share, "the whole of
# the distributable minutes is distributed again by the same rule across only
# the commitments that held fifteen or more". No generated extract has a month
# whose survivors' summed effort is at or below the distributable minutes, so
# this fixture overrides envelopes to make some.

SURVIVOR_SEED = 4100149
SURVIVOR_MAX_GROUPS = 8


def _csv_rows(text):
    lines = [ln for ln in text.split("\n") if ln]
    head = lines[0].split(",")
    return [dict(zip(head, ln.split(","))) for ln in lines[1:]]


def _add_survivor_envelopes(files):
    """Override envelopes so that the floor's survivors fit the distributable minutes."""
    tmp = tempfile.mkdtemp(prefix="cmsurv")
    data = os.path.join(tmp, "data")
    os.makedirs(data)
    for name, text in files.items():
        with open(os.path.join(data, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    out = os.path.join(tmp, "out")
    os.makedirs(out)
    write_all(compute(data), out)
    with open(os.path.join(out, "attention_allocation.csv"), encoding="utf-8") as fh:
        alloc = _csv_rows(fh.read())
    with open(os.path.join(out, "month_load_index.csv"), encoding="utf-8") as fh:
        load = {(r["year_month"], r["obligor_actor"]): r for r in _csv_rows(fh.read())}
    shutil.rmtree(tmp, ignore_errors=True)
    groups = {}
    for r in alloc:
        if int(r["demand_minutes"]) > 0:
            groups.setdefault((r["year_month"], r["obligor_actor"]), {})[r["commitment_key"]] = int(r["demand_minutes"])
    chosen = {}
    for pair in sorted(groups):
        weights = groups[pair]
        if len(weights) < 2:
            continue
        for usable in range(ALLOC_FLOOR, sum(weights.values())):
            share = largest_remainder(weights, usable)
            keep = {k: weights[k] for k, v in share.items() if v >= ALLOC_FLOOR}
            if keep and len(keep) < len(weights) and sum(keep.values()) < usable:
                chosen[pair] = int(load[pair]["reserve_minutes"]) + usable
                break
        if len(chosen) >= SURVIVOR_MAX_GROUPS:
            break
    if not chosen:
        raise AssertionError("no month can separate survivor redistribution")
    head, *rest = [ln for ln in files["budget_overrides.psv"].split("\n") if ln]
    kept = [ln for ln in rest if (ln.split("|")[1], ln.split("|")[0]) not in chosen]
    kept += [f"{a}|{m}|{v}" for (m, a), v in sorted(chosen.items())]
    files["budget_overrides.psv"] = "\n".join([head] + kept) + "\n"
    return chosen


_SURVIVOR_CACHE = {}


def _survivor_run(seed):
    """Reference and delivered outputs for one extract carrying the fixture."""
    if seed in _SURVIVOR_CACHE:
        return _SURVIVOR_CACHE[seed]
    files, _w = build_all(seed)
    _add_survivor_envelopes(files)
    tmp = tempfile.mkdtemp(prefix="cmsurvrun")
    data = os.path.join(tmp, "data")
    os.makedirs(data)
    for name, text in sorted(files.items()):
        with open(os.path.join(data, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    ref = os.path.join(tmp, "ref")
    os.makedirs(ref)
    write_all(compute(data), ref)
    got = _run_program(data, os.path.join(tmp, "out"))
    _SURVIVOR_CACHE[seed] = (ref, got)
    return ref, got


def _survivor_same(seed, names):
    ref, got = _survivor_run(seed)
    for name in names:
        with open(os.path.join(ref, name), "rb") as fh:
            want = fh.read()
        path = os.path.join(got, name)
        if not os.path.isfile(path):
            raise AssertionError(f"survivor extract {seed}: no {name} was written")
        with open(path, "rb") as fh:
            if fh.read() != want:
                raise AssertionError(f"survivor extract {seed}: {name} differs")


SURVIVOR_NAMES = ("attention_allocation.csv", "month_load_index.csv")


def test_allocation_survivor_redistribution_exact():
    """POSITIVE: the floor's survivors share the whole of the distributable minutes."""
    _survivor_same(SURVIVOR_SEED, SURVIVOR_NAMES)


def test_allocation_survivor_redistribution_hard():
    """POSITIVE: survivor redistribution holds on an unseen extract."""
    _survivor_same(EVAL_SEEDS[2], SURVIVOR_NAMES_HARD)


@criterion(description="the floor's survivors share the whole distributable minutes.")
def allocation_survivor_redistribution_exact(workspace: Path) -> bool:
    return _passes(test_allocation_survivor_redistribution_exact)


@criterion(description="survivor redistribution holds on an unseen extract.")
def allocation_survivor_redistribution_hard(workspace: Path) -> bool:
    return _passes(test_allocation_survivor_redistribution_hard)


criteria.allocation_survivor_redistribution_exact(weight=3)
criteria.allocation_survivor_redistribution_hard(weight=5)
