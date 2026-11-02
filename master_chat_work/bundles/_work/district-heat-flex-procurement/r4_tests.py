"""Redesign r4: rewrite the extract writer, hidden generator and criteria of WORK/test_output.src.py in place.

Run once on the source whose reference() already carries the r4 rules. usage: python3 -B r4_tests.py
"""
from __future__ import annotations

from pathlib import Path

WORK = Path(__file__).resolve().parent
SRC = WORK / "test_output.src.py"
DATA = WORK.parent.parent / "district-heat-flex-procurement" / "environment" / "data"
s = SRC.read_text(encoding="utf-8")


def rep(old: str, new: str) -> None:
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)


# ---- docstring
start = s.index('"""Verifier for district-heat-flex-procurement.')
end = s.index('"""', start + 3) + 3
s = s[:start] + '''"""Verifier for district-heat-flex-procurement.

Every value check reruns the submitted derive_report.py, as an unprivileged user, on an
extract and compares the rows it owns with an independent reference implementation of
schema.md. Each family of rows is checked twice: once on the shipped extract and once,
as a `_hard` check, on a seeded season extract built here. Three mutation checks run the
program on two extracts that differ in one governed input. Four format checks read the
reports the agent wrote into /app/out; they never compare values.

Negative checks return True when the cheat is present; their negative weight does the
punishing, so an honest submission leaves them False.
"""''' + s[end:]

# ---- reference trace hook (used only by the generator to plant grant pools)
rep('''            total_w = sum(heft.values())
            grant_rows: list[dict[str, Any]] = []''', '''            total_w = sum(heft.values())
            if trace is not None:
                trace.append((eid, region, brought, credit, {b: w for b, w in heft.items() if w}))
            grant_rows: list[dict[str, Any]] = []''')
rep('''def reference(root: Path, lazy: frozenset = frozenset()) -> dict[str, Any]:''',
    '''def reference(root: Path, lazy: frozenset = frozenset(), trace: list | None = None) -> dict[str, Any]:''')

# ---- writer: [grants] and draws_from
rep('''    ini += "\\n[export]\\nwaiver_signed = Y\\n"''', '''    claim, minimum = spec.get("grants", (40, 25))
    ini += f"\\n[grants]\\nclaim_cents_per_weight = {claim}\\nminimum_grant_cents = {minimum}\\n"
    ini += "\\n[export]\\n# Defaults the legacy export tool applies to fields it did not record.\\nwaiver_signed = Y\\n"''')
rep('''    (folder / "site_allowances.tsv").write_text(_ALLOWANCE_COMMENT + "site_id\\tallowance_ticks\\n" + "".join(
        f"{sid}\\t{allowances.get(sid, 10 ** 9)}\\n" for sid in owned), encoding="utf-8")''',
    '''    draws = spec.get("draws", {})
    (folder / "site_allowances.tsv").write_text(_ALLOWANCE_COMMENT + "site_id\\tallowance_ticks\\tdraws_from\\n" + "".join(
        f"{sid}\\t{allowances.get(sid, 10 ** 9)}\\t{draws.get(sid, '')}\\n" for sid in owned), encoding="utf-8")''')

# ---- comments identical to the shipped files
card = (DATA / "rate_cards.xml").read_text(encoding="utf-8")
card_comment = card[card.index("<!--"):card.index("-->") + 3] + "\n"
allow = "".join(x + "\n" for x in (DATA / "site_allowances.tsv").read_text(encoding="utf-8").splitlines()
                if x.startswith("#"))
i = s.index("_CARD_COMMENT = (")
j = s.index("\n\n\n", i)
s = s[:i] + "_CARD_COMMENT = " + repr(card_comment) + s[j:]
i = s.index("_ALLOWANCE_COMMENT = (")
j = s.index("\n\n\n", i)
s = s[:i] + "_ALLOWANCE_COMMENT = " + repr(allow) + s[j:]

# ---- mutation cases for the grant minimum
rep('''    raise KeyError(name)
''', '''    if name in ("mut_grant", "mut_grant_moved"):
        # One region over three events in season order; the *_moved twin changes minimum_grant_cents only.
        rng = Rng(31)
        spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "pools": {},
                "grants": (30, 26 if name == "mut_grant_moved" else 20)}
        for k, eid in enumerate(("T8-0101", "T8-0102", "T8-0103")):
            spec["events"].append(_event(eid, 2, start=f"2026-12-05T{10 + k:02d}:00:00+00:00"))
            for i, w in enumerate((1, 3, 2)):
                sid = f"G{k}{i}"
                spec["sites"].append(_site(eid, sid, ben=f"BEN-G{i}", weight=w))
                spec["offers"].append(_offer(eid, sid, "A", rng.between(100, 900), [rng.between(1, 30) * 10] * 2))
            spec["targets"][(eid, "North")] = [(200, 1)] * 2
            spec["limits"][(eid, "North")] = _wide(2)
            spec["pools"][(eid, "North")] = (100, 150, 120)[k]
        return spec
    raise KeyError(name)
''')

# ---- hidden season extracts
i = s.index("# Per composed extract: the wrong readings")
j = s.index("def _region_docs(")
hidden = '''# Hidden season extracts. H1 plants draws_from chains (two to five sites long) whose holder allowances bind;
# H2 has no draws_from rows, so its money rows depend on settlement and grants only. Both plant, in every region,
# one funded pool whose first largest-remainder share leaves some beneficiaries under minimum_grant_cents.
SHAPES = ((1, 1), (1, 2), (2, 3), (1, 3), (2, 5), (1, 4))
HIDDEN_GUARDS: dict[str, tuple[tuple[str, str], ...]] = {
    "H1": (("CHAIN1", "selection"), ("CHAIN0", "selection"), ("LEDid", "selection"), ("REENTRY", "grants"),
           ("RELIEF", "credit_rows")),
    "H2": (("REENTRY", "grants"), ("DROPLEFT", "grants"), ("NODROP", "grants"), ("RELIEF", "credit_rows"),
           ("NOCARRY", "funded_pool"), ("DH3", "funded_pool"), ("H4", "grants")),
}


def _region_of_code(code: str) -> str | None:
    return next((r for r, codes in REGION_CODES.items() if code in codes), None)


def _hidden_spec(kind: str, seed: int) -> dict[str, Any]:
    spec = _composed_spec("ABCD"[seed % 4], seed)
    rng = Rng(seed * 104729 + (11 if kind == "H1" else 23))
    claim = rng.between(30, 80)
    spec["grants"] = (claim, claim * rng.between(80, 125) // 100)
    spec["draws"] = {}
    if kind == "H1":
        by_region: dict[str, list[str]] = {}
        for x in spec["sites"]:
            region = _region_of_code(x["code"])
            if region is not None and x["sid"] in spec["allowances"]:
                by_region.setdefault(region, [])
                if x["sid"] not in by_region[region]:
                    by_region[region].append(x["sid"])
        demand = dict(spec["allowances"])
        for region in sorted(by_region):
            free = sorted(by_region[region])
            rng.shuffle(free)
            for _ in range(rng.between(1, 2)):
                length = rng.between(2, 5)
                if len(free) < length:
                    break
                chain = [free.pop() for _ in range(length)]
                for parent, child in zip(chain, chain[1:]):
                    spec["draws"][child] = parent
                spec["allowances"][chain[0]] = sum(demand[x] for x in chain) * rng.pick([35, 50, 65, 80, 100]) // 100
                for x in chain[1:]:
                    spec["allowances"][x] = 0
    return spec


def _separating_pools(weights: dict[str, int], claim: int, minimum: int) -> list[int]:
    """Funded pools whose first share leaves some, not all, beneficiaries under the minimum while the claims
    of the others add up to the pool or less."""
    out = []
    for funded in range(1, sum(weights.values()) * claim):
        cut, _, _ = _apportion(funded, weights, False)
        kept = [b for b in weights if cut[b] >= minimum]
        if 0 < len(kept) < len(weights) and sum(weights[b] for b in kept) * claim <= funded:
            out.append(funded)
    return out


def _probe(spec: dict[str, Any], tag: str) -> list:
    folder = _scratch() / f"probe-{tag}"
    if folder.exists():
        shutil.rmtree(folder)
    write_extract(folder, spec)
    trace: list = []
    reference(folder, frozenset(), trace)
    shutil.rmtree(folder)
    return trace


def _plant_grants(spec: dict[str, Any], seed: int, tag: str) -> int:
    """Per region, the first event-region in season order that admits a separating funded pool gets one, and the
    region's earlier pools are set to 0 so nothing is carried into it. Returns the number of regions planted."""
    claim, minimum = spec["grants"]
    rng = Rng(seed * 7919 + 5)
    planted = 0
    for region in REGION_CODES:
        for attempt in range(len(SHAPES) + 1):
            rows = [t for t in _probe(spec, tag) if t[1] == region]
            hit = None
            for k, (eid, _, _, credit, weights) in enumerate(rows):
                if len(weights) >= 2:
                    options = _separating_pools(weights, claim, minimum)
                    if options:
                        hit = (k, eid, credit, rng.pick(options))
                        break
            if hit:
                k, eid, credit, funded = hit
                for prior in rows[:k]:
                    if (prior[0], region) in spec["pools"]:
                        spec["pools"][(prior[0], region)] = 0
                spec["pools"][(eid, region)] = funded + credit
                planted += 1
                break
            target = next((t for t in rows if len(t[4]) >= 2), None)
            if attempt == len(SHAPES) or target is None:
                break
            a, b = SHAPES[attempt]
            hosts = [x for x in spec["sites"] if x["event_id"] == target[0] and _region_of_code(x["code"]) == region
                     and x["weight"] is not None]
            pair = sorted({x["ben"] for x in hosts})[:2]
            given: set[str] = set()
            for x in hosts:
                if x["ben"] in pair and x["ben"] not in given:
                    x["weight"] = a if x["ben"] == pair[0] else b
                    given.add(x["ben"])
                else:
                    x["weight"] = 0
    return planted


def _assert_bounds(spec: dict[str, Any]) -> None:
    """Every drawn value stays inside what schema.md states (G12)."""
    claim, minimum = spec["grants"]
    assert claim > 0 and minimum > 0
    assert all(v >= 0 for v in spec["allowances"].values())
    assert all(v >= 0 for v in spec["pools"].values())
    for start in spec["draws"]:
        seen = {start}
        node = start
        while node in spec["draws"]:
            node = spec["draws"][node]
            assert node not in seen, "draws_from chain returns to a site"
            seen.add(node)
        assert spec["draws"].get(node) is None
    for o in spec["offers"]:
        assert all(r >= 0 for r in o["r"]) and all(v >= 0 for v in o["v"])


def hidden_root(kind: str) -> Path | None:
    """First seed from EVAL_SEED whose season extract plants a grant pool in every region and separates every
    reading in HIDDEN_GUARDS on the family it is graded on."""
    with _LOCK:
        if ("hidden", kind) not in _CACHE:
            found = None
            for step in range(40):
                seed = EVAL_SEED % 100000 + 7 * step + (0 if kind == "H1" else 3)
                spec = _hidden_spec(kind, seed)
                if not within_contract(spec):
                    continue
                if _plant_grants(spec, seed, kind) < len(REGION_CODES):
                    continue
                _assert_bounds(spec)
                folder = write_extract(_scratch() / f"hidden-{kind}-{step}", spec)
                right = expected(folder)
                if all(FAMILIES[family](expected(folder, frozenset({flag}))) != FAMILIES[family](right)
                       for flag, family in HIDDEN_GUARDS[kind]):
                    found = folder
                    break
            _CACHE[("hidden", kind)] = found
        return _CACHE[("hidden", kind)]


'''
s = s[:i] + hidden + s[j:]

# ---- families replace VIEWS; composed_root stays for nothing -> remove views and composed_root
i = s.index("def _region_docs(")
j = s.index("MAX_SITES, MAX_OFFERS")
families = '''REGIONS = tuple(REGION_CODES)
SEGMENTS = tuple(SEGMENT_CODES.values())
QUALITY_LEDGER = ("allowance_blocked_offer_count", "empty_candidate_groups")


def _rows(files: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return {r: [{k: e[k] for k in keys} for e in files[f"region_{r}.json"]["events"]] for r in REGIONS}


def _seg_rows(files: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return {g: [{k: e[k] for k in keys} for e in files[f"segment_{g}.json"]["event_regions"]] for g in SEGMENTS}


FAMILIES: dict[str, Any] = {
    "selection": lambda f: _rows(f, ("event_id", "candidate_offer_count", "selected_offer_ids")),
    "intervals": lambda f: _rows(f, ("event_id", "intervals")),
    "tie_decisions": lambda f: f["policy_audit.json"]["tie_decisions"],
    "segment_rows": lambda f: _seg_rows(f, ("event_id", "region", "selected_offer_ids", "relief_ticks",
                                            "recovery_ticks", "floor_ticks", "floor_attainment_bp")),
    "ledger_quality": lambda f: {k: f["data_quality.json"][k] for k in QUALITY_LEDGER},
    **{f"region_totals_{r}": (lambda f, r=r: f[f"region_{r}.json"]["totals"]) for r in REGIONS},
    "segment_totals": lambda f: {g: f[f"segment_{g}.json"]["totals"] for g in SEGMENTS},
    "summary": lambda f: f["summary.json"],
    "labels": lambda f: {k: f["policy_audit.json"][k] for k in ("compliance_counts", "site_labels")},
    "quality_counts": lambda f: {k: v for k, v in f["data_quality.json"].items() if k not in QUALITY_LEDGER},
    "credit_rows": lambda f: _rows(f, ("event_id", "credit_cents")),
    "segment_credit_rows": lambda f: _seg_rows(f, ("event_id", "region", "bid_cost_cents", "credit_cents")),
    "funded_pool": lambda f: _rows(f, ("event_id", "grant_pool_cents", "grant_funded_cents")),
    "grants": lambda f: _rows(f, ("event_id", "grants")),
    "grant_allocation": lambda f: _rows(f, ("event_id", "grant_allocated_cents", "grant_unallocated_cents")),
    "residual": lambda f: {"residual_cents": f["policy_audit.json"]["residual_cents"],
                           "residual_tie_pool_count": f["policy_audit.json"]["residual_tie_pool_count"],
                           "unallocated_pool_count": f["data_quality.json"]["unallocated_pool_count"]},
    "cap_binding": lambda f: f["policy_audit.json"]["cap_binding_count"],
}
HIDDEN_OF = {name: ("H2" if name in ("credit_rows", "segment_credit_rows", "funded_pool", "grants",
                                     "grant_allocation", "residual", "cap_binding") else "H1") for name in FAMILIES}


def _project(family: str, files: dict[str, Any]) -> Any:
    try:
        return FAMILIES[family](files)
    except (KeyError, TypeError, AttributeError):
        return None


'''
s = s[:i] + families + s[j:]
i = s.index("def composed_root(")
j = s.index("def case_root(")
s = s[:i] + s[j:]
rep('''                if all(FAMILIES[family](expected(folder, frozenset({flag}))) != FAMILIES[family](right)''',
    '''                if all(_project(family, expected(folder, frozenset({flag}))) != _project(family, right)''')

# ---- family pass function replaces composed_passes
i = s.index("def composed_passes(")
j = s.index("# ---------------------------------------------------------------- format checks")
s = s[:i] + '''def family_passes(workspace: Path, family: str, hard: bool) -> tuple[bool, str]:
    """The rows one family owns, on the shipped extract or (hard) on its seeded season extract."""
    root = hidden_root(HIDDEN_OF[family]) if hard else visible_root()
    if root is None:
        return False, f"grader fault: no planted seed for extract {HIDDEN_OF[family]}"
    got = run_agent(workspace, root)
    if got is None:
        return False, _run_failed(root)
    want = _project(family, expected(root))
    mine_ = _project(family, got)
    if mine_ is not None and canon(mine_) == canon(want):
        return True, ""
    if mine_ is None:
        return False, f"missing value: a report or key this family owns is absent ({family})"
    return False, "wrong value: " + _first_difference(mine_, want)


''' + s[j:]

# ---- criteria: replace composed + isolated cases with families; keep format, mutations, negatives
i = s.index("def _composed(workspace: Path, tag: str, view: str, name: str) -> bool:")
j = s.index("def _credit_family(")
desc = {
    "selection": "the candidate_offer_count and selected_offer_ids of every event entry in the four region files",
    "intervals": "the intervals array of every event entry in the four region files",
    "tie_decisions": "the tie_decisions entries of policy_audit.json",
    "segment_rows": "the selection, energy and floor fields of every event_regions entry in both segment files",
    "ledger_quality": "allowance_blocked_offer_count and empty_candidate_groups in data_quality.json",
    "region_totals_North": "the totals object of region_North.json",
    "region_totals_South": "the totals object of region_South.json",
    "region_totals_West": "the totals object of region_West.json",
    "region_totals_East": "the totals object of region_East.json",
    "segment_totals": "the totals objects of both segment files",
    "summary": "every value of summary.json",
    "labels": "compliance_counts and site_labels of policy_audit.json",
    "quality_counts": "the row counts and data-quality counters of data_quality.json other than the allowance ledger counters",
    "credit_rows": "the credit_cents of every event entry in the four region files",
    "segment_credit_rows": "the bid_cost_cents and credit_cents of every event_regions entry in both segment files",
    "funded_pool": "grant_pool_cents and grant_funded_cents of every event entry in the four region files",
    "grants": "the grants array of every event entry in the four region files",
    "grant_allocation": "grant_allocated_cents and grant_unallocated_cents of every event entry in the four region files",
    "residual": "residual_cents and residual_tie_pool_count of policy_audit.json and unallocated_pool_count of data_quality.json",
    "cap_binding": "cap_binding_count of policy_audit.json",
}
block = []
for fam, text in desc.items():
    where_hard = ("a seeded season extract with draws_from chains and planted grant pools"
                  if fam not in ("credit_rows", "segment_credit_rows", "funded_pool", "grants", "grant_allocation",
                                 "residual", "cap_binding")
                  else "a seeded season extract with planted grant pools and no draws_from rows")
    block.append(f'''@criterion(description="Run on the shipped extract, the program reports {text} exactly as the contract defines them.")
def {fam}_match(workspace: Path) -> bool:
    return _graded("{fam}_match", lambda: family_passes(workspace, "{fam}", False))


@criterion(description="Run on {where_hard}, the program reports {text} exactly as the contract defines them.")
def {fam}_match_hard(workspace: Path) -> bool:
    return _graded("{fam}_match_hard", lambda: family_passes(workspace, "{fam}", True))


''')
s = s[:i] + "".join(block) + '''def _ledger_view(files: dict[str, Any]) -> Any:
    return (per_event(files, "candidate_offer_count"), per_event(files, "selected_offer_ids"),
            field_of(files, "data_quality.json", "allowance_blocked_offer_count", "empty_candidate_groups"))


''' + s[j:]

# ---- third mutation
rep('''# ---------------------------------------------------------------- negative checks''', '''def _grant_rows(files: dict[str, Any]) -> Any:
    try:
        return [(e["event_id"], e["grants"], e["grant_allocated_cents"]) for e in files["region_North.json"]["events"]]
    except (KeyError, TypeError):
        return None


@criterion(description="Raising minimum_grant_cents in program.ini moves the grants of the region file as the contract says, with the same portfolios and credits.")
def minimum_grant_mutation(workspace: Path) -> bool:
    return _graded("minimum_grant_mutation", lambda: mutation_passes(workspace, "mut_grant", "mut_grant_moved", _grant_rows, _credit_family))


# ---------------------------------------------------------------- negative checks''')

# ---- weights
i = s.index("criteria.artifact_set_exists_and_parses(weight=1)")
j = s.index("\n", s.index("criteria.negative_external_dependency_or_network("))
neg = s[s.index("criteria.negative_hardcoded_sample_answers("):j]
lines = ["criteria.artifact_set_exists_and_parses(weight=1)", "criteria.canonical_serialization_and_integer_units(weight=1)",
         "criteria.report_keys_match_schema(weight=1)", "criteria.report_arrays_in_schema_order(weight=1)"]
for fam in desc:
    lines += [f"criteria.{fam}_match(weight=3)", f"criteria.{fam}_match_hard(weight=5)"]
lines += ["criteria.segment_rate_adder_mutation(weight=3)", "criteria.allowance_ticks_mutation(weight=3)",
          "criteria.minimum_grant_mutation(weight=3)"]
s = s[:i] + "\n".join(lines) + "\n" + neg + s[j:]

SRC.write_text(s, encoding="utf-8")
print("rewritten", len(s.splitlines()), "lines")
