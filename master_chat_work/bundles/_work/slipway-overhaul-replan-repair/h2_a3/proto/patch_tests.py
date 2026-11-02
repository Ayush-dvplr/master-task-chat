"""Held-out crosswalk rounds: seeds, helpers, six checks, criteria and the
weights. Old checks keep their bodies; only their weights move.

usage: python3 -B patch_tests.py <test_output.py> <group_seed> <rule_seed>
       <amendment_seed> <every_seed>
"""
import sys
from pathlib import Path

path = Path(sys.argv[1])
seeds = [int(s) for s in sys.argv[2:6]]
text = path.read_text()
count = 0


def sub(old, new):
    global text, count
    n = text.count(old)
    if n != 1:
        raise SystemExit("anchor matched %d times: %r" % (n, old[:80]))
    text = text.replace(old, new)
    count += 1


sub('''MINTED_SEEDS = (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED)
''', '''MINTED_SEEDS = (EVAL_SEED, CHALLENGE_SEED, PROBE_SEED)

# held-out rounds whose papers name jobs by the legacy identifiers the active
# crosswalk rows carry, each paired with the places it writes them in
HELD_GROUPS = (%d, ("groups",))
HELD_RULES = (%d, ("rules",))
HELD_AMENDMENTS = (%d, ("amendments",))
HELD_EVERY = (%d, ("groups", "rules", "amendments"))
''' % tuple(seeds))

sub('''def _compare(family, got, expected, label):
''', '''def _held_corpus(seed, legacy):
    key = ("held-corpus", seed, legacy)
    with _BUILD_LOCK:
        if key not in _CACHE:
            root = write_corpus(_scratch("held"), seed, legacy)
            for path in [root] + list(root.rglob("*")):
                os.chmod(path, 0o777 if path.is_dir() else 0o666)
            _CACHE[key] = root
        return _CACHE[key]


def _held_reference(seed, legacy):
    key = ("held-reference", seed, legacy)
    with _BUILD_LOCK:
        if key not in _CACHE:
            out = _scratch("held-reference")
            ref_publish(_held_corpus(seed, legacy), out, ())
            _CACHE[key] = {p.name: p.read_bytes() for p in sorted(out.iterdir())}
        return _CACHE[key]


def _held(round_, family):
    seed, legacy = round_
    key = ("held-case", seed, legacy)
    if key not in _CACHE:
        _CACHE[key] = _drive(_held_corpus(seed, legacy), "held")
    got = _CACHE[key]
    extra = sorted(set(got) - set(ARTIFACT_NAMES))
    if extra:
        raise AssertionError("the held-out round " + str(seed)
                             + " carries documents the contract does not"
                             + " name: " + ", ".join(extra))
    _compare(family, got, _held_reference(seed, legacy),
             "the held-out round " + str(seed))


def _compare(family, got, expected, label):
''')

sub('''# --------------------------------------------------------------------------
# negative detectors
''', '''def test_package_crosswalk_groups_state_exact():
    """POSITIVE: on a held-out round whose slot group memberships name some
    jobs by their legacy identifiers, the derived state and the accepted sets
    come out exactly."""
    _held(HELD_GROUPS, STATE_FAMILY)


def test_package_crosswalk_rules_state_exact():
    """POSITIVE: on a held-out round whose charge rules name some jobs by
    their legacy identifiers, the derived state and the accepted sets come
    out exactly."""
    _held(HELD_RULES, STATE_FAMILY)


def test_package_crosswalk_amendments_cascade_exact():
    """POSITIVE: on a held-out round whose amendment payloads name some jobs
    by their legacy identifiers, and which lodges one edge whose two ends are
    one job and reverses a lodgement, the classification, invalidation sets,
    work ledger, store summary and amendment optima come out exactly."""
    _held(HELD_AMENDMENTS, CASCADE_FAMILY)


def test_package_crosswalk_amendments_state_exact():
    """POSITIVE: on that round the derived state, the final accepted sets and
    the rejection register come out exactly."""
    _held(HELD_AMENDMENTS, STATE_FAMILY)


def test_package_crosswalk_every_state_exact():
    """POSITIVE: on a held-out round that names jobs by legacy identifiers in
    group memberships, charge rules and amendment payloads at once, the
    derived state and the accepted sets come out exactly."""
    _held(HELD_EVERY, STATE_FAMILY + CASCADE_FAMILY)


def test_package_crosswalk_every_publication_exact():
    """POSITIVE: on that round the graph documents, defect register,
    verification notes, manifest and summary come out exactly."""
    _held(HELD_EVERY, PUBLICATION_FAMILY)


# --------------------------------------------------------------------------
# negative detectors
''')

sub('''@criterion(description="the crew quantities were converted at one flat''',
    '''@criterion(description="on a held-out round whose slot group memberships name jobs by legacy identifiers the derived state and accepted sets come out exactly")
def package_crosswalk_groups_state_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_crosswalk_groups_state_exact)


@criterion(description="on a held-out round whose charge rules name jobs by legacy identifiers the derived state and accepted sets come out exactly")
def package_crosswalk_rules_state_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_crosswalk_rules_state_exact)


@criterion(description="on a held-out round whose amendment payloads name jobs by legacy identifiers the classification, invalidation sets, ledger, store and optima come out exactly")
def package_crosswalk_amendments_cascade_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_crosswalk_amendments_cascade_exact)


@criterion(description="on that round the derived state, final accepted sets and rejection register come out exactly")
def package_crosswalk_amendments_state_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_crosswalk_amendments_state_exact)


@criterion(description="on a held-out round naming jobs by legacy identifiers in groups, rules and amendments at once the state and cascade documents come out exactly")
def package_crosswalk_every_state_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_crosswalk_every_state_exact)


@criterion(description="on that round the graph documents, defect register, verification notes, manifest and summary come out exactly")
def package_crosswalk_every_publication_exact(workspace: Path) -> bool:
    return _graded(workspace, test_package_crosswalk_every_publication_exact)


@criterion(description="the crew quantities were converted at one flat''')

OLD = '''criteria.shipped_identifier_layer_exact(weight=3)
criteria.shipped_graph_layer_exact(weight=3)
criteria.shipped_closure_and_demand_exact(weight=5)
criteria.shipped_rule_and_charge_exact(weight=5)
criteria.shipped_baseline_optimum_exact(weight=5)
criteria.shipped_amendment_classification_exact(weight=3)
criteria.shipped_invalidation_sets_exact(weight=5)
criteria.shipped_work_ledger_exact(weight=5)
criteria.shipped_store_summary_exact(weight=3)
criteria.shipped_final_optimum_exact(weight=5)
criteria.shipped_audit_documents_exact(weight=3)
criteria.package_eval_state_exact(weight=5)
criteria.package_eval_cascade_exact(weight=5)
criteria.package_challenge_state_exact(weight=5)
criteria.package_challenge_cascade_exact(weight=3)
criteria.package_probe_publication_exact(weight=3)
'''
NEW = '''criteria.shipped_identifier_layer_exact(weight=2)
criteria.shipped_graph_layer_exact(weight=2)
criteria.shipped_closure_and_demand_exact(weight=3)
criteria.shipped_rule_and_charge_exact(weight=3)
criteria.shipped_baseline_optimum_exact(weight=3)
criteria.shipped_amendment_classification_exact(weight=2)
criteria.shipped_invalidation_sets_exact(weight=3)
criteria.shipped_work_ledger_exact(weight=3)
criteria.shipped_store_summary_exact(weight=2)
criteria.shipped_final_optimum_exact(weight=3)
criteria.shipped_audit_documents_exact(weight=2)
criteria.package_eval_state_exact(weight=3)
criteria.package_eval_cascade_exact(weight=3)
criteria.package_challenge_state_exact(weight=3)
criteria.package_challenge_cascade_exact(weight=2)
criteria.package_probe_publication_exact(weight=2)
criteria.package_crosswalk_groups_state_exact(weight=9)
criteria.package_crosswalk_rules_state_exact(weight=9)
criteria.package_crosswalk_amendments_cascade_exact(weight=8)
criteria.package_crosswalk_amendments_state_exact(weight=8)
criteria.package_crosswalk_every_state_exact(weight=8)
criteria.package_crosswalk_every_publication_exact(weight=8)
'''
sub(OLD, NEW)

path.write_text(text)
print("patched", count)
