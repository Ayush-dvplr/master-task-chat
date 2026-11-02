"""One-shot rewrite of the criteria tail of tests/test_output.py (harden lp1 r1)."""
import sys
from pathlib import Path

path = Path(sys.argv[1]) / "tests" / "test_output.py"
text = path.read_text(encoding="utf-8")


def cut(src, start, end):
    a = src.index(start)
    b = src.index(end, a)
    return src[:a], src[a:b], src[b:]


# 1. _season keeps the reason a run failed; _agrees removed in favour of _check.
old_season = '''        try:
            _run_delivered(data, out)
            got = _read_dir(out)
        except (AssertionError, OSError, ValueError):
            got = None
        _CACHE[key] = (want, got)
    return _CACHE[key]


def _agrees(name: str, observe) -> bool:
    want, got = _season(name)
    if got is None:
        return False
    try:
        return _same(observe(got), observe(want))
    except (KeyError, TypeError, IndexError, AttributeError):
        return False
'''
new_season = '''        try:
            _run_delivered(data, out)
            got = _read_dir(out)
        except (AssertionError, OSError, ValueError) as error:
            got = None
            _CACHE["fault:" + name] = "%s: %s" % (type(error).__name__, error)
        _CACHE[key] = (want, got)
    return _CACHE[key]


def _note(fault: str) -> None:
    """Record why a check lost credit, so the verifier log tells a crash from a wrong value."""
    print("check note: %s" % fault, file=sys.stderr)


def _settled_nothing(name: str) -> str:
    return "%s: the program settled nothing (%s)" % (name, _CACHE.get("fault:" + name, "no records"))


def _check(name: str, observe, what: str) -> None:
    """The read `observe` of the delivered records equals the settled season's."""
    want, got = _season(name)
    assert got is not None, _settled_nothing(name)
    try:
        mine = observe(got)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise AssertionError("%s: %s is missing from the records (%s: %s)" % (name, what, type(error).__name__, error))
    assert _same(mine, observe(want)), "%s: %s differs from the settled season" % (name, what)
'''
assert old_season in text
text = text.replace(old_season, new_season)

# 2. Structure: drop the reseeded findings-form check (the data_quality document
# is graded whole on fresh seasons instead).
head, _old, rest = cut(text, "def test_structure_findings_canonical_form():", "# ------------------------------------------------------------- negative ---")
text = head + rest

# 3. Negatives: drop the two that grade conduct rather than cheating.
for start, end in (
    ("def test_negative_weight_nondeterministic_output():", "def test_negative_weight_reads_training_corpus_at_runtime():"),
    ("def test_negative_weight_imports_outside_standard_library():", "# rewardkit checks."),
):
    head, _old, rest = cut(text, start, end)
    text = head + rest

# 4. New graded checks and registration.
head, _old, rest = cut(text, "# rewardkit checks.", "def main() -> None:")
DOC_FILES = {
    "summary": "summary.json",
    "vault_audit": "vault_audit.json",
    "reconciliation": "reconciliation.json",
    "data_quality": "data_quality.json",
    "allocation": "allocation.json",
    "workshop_reports": "every workshop report",
    "guild_reports": "every guild report",
}
DOC_WORDS = {
    "summary": "summary.json",
    "vault_audit": "vault_audit.json",
    "reconciliation": "reconciliation.json",
    "data_quality": "data_quality.json, findings and counts,",
    "allocation": "allocation.json",
    "workshop_reports": "each workshop report",
    "guild_reports": "each guild report",
}
tail = '''# ------------------------------------------------- whole documents ---
#
# One check per downstream document. Each runs the delivered program on four
# reseeded seasons the agent never sees and asserts only its own document;
# credit is the share of seasons on which that document matches whole.


def _whole_share(document: str) -> float:
    observe = DOCUMENTS[document]
    hits = 0
    for name in WHOLE_SEASONS:
        want, got = _season(name)
        if got is None:
            _note(_settled_nothing(name))
            continue
        try:
            mine = observe(got)
        except (KeyError, TypeError, IndexError, AttributeError) as error:
            _note("%s: %s is missing from the records (%s: %s)" % (name, document, type(error).__name__, error))
            continue
        if _same(mine, observe(want)):
            hits += 1
        else:
            _note("%s: %s differs from the settled season" % (name, document))
    return hits / len(WHOLE_SEASONS)


'''
for doc in DOC_FILES:
    tail += "def test_whole_%s() -> float:\n    return _whole_share(%r)\n\n\n" % (doc, doc)
tail += '''# ------------------------------------------------------ single rules ---
#
# Each check reads one figure family on an otherwise open season.


def test_unit_charge_season_total():
    _check("iso_unit_charge", _obs_season_charge, "the season charge in summary.json")


def test_cap_release_closures():
    _check("iso_cap_release", _coded("CAP_REACHED"), "the CAP_REACHED findings")


def test_live_window_refusals():
    _check("iso_live_window", _coded("UNCREDITED_SALVAGE"), "the UNCREDITED_SALVAGE findings")


def _moves_only_charge(name: str) -> None:
    """A changed charter constant moves the charge ledger and leaves the vault alone."""
    _check(name, _obs_charge_ledger, "the charge ledger in reconciliation.json")
    _want, base = _season("mut_base")
    _want, moved = _season(name)
    assert base is not None, _settled_nothing("mut_base")
    assert _same(moved["vault_audit.json"], base["vault_audit.json"]), (
        "%s: vault_audit.json moved when only a charge constant changed" % name
    )


def test_mutation_family_multiplier():
    _moves_only_charge("mut_family")


def test_mutation_grade_step():
    _moves_only_charge("mut_grade")


def test_priority_tie_allocation():
    _check("cl_priority", _obs_allocation, "allocation.json")


def test_merge_chain_smith_rows():
    _check("cl_identity", _obs_smith_standing, "the smith rows")


# rewardkit checks. One lock runs the checks one at a time, because rewardkit
# calls checks from parallel worker threads. A check that raises scores zero and
# leaves its message in the verifier log.
_GRADE_LOCK = threading.Lock()


def _passes(test) -> float:
    with _GRADE_LOCK:
        try:
            result = test()
        except Exception as error:
            _note("%s: %s: %s" % (test.__name__, type(error).__name__, error))
            return 0.0
        return 1.0 if result is None else float(result)


@criterion(description="a compilable settlement program sits at the declared path.")
def structure_program_delivered(workspace: Path) -> float:
    return _passes(test_structure_program_delivered)


@criterion(description="all eleven records of the shipped season are delivered under /app/out and parse as non-empty JSON.")
def structure_records_delivered(workspace: Path) -> float:
    return _passes(test_structure_records_delivered)


@criterion(description="the program writes its records into the directory it is given, and into /app/out from /app/data when given none.")
def structure_program_takes_directories(workspace: Path) -> float:
    return _passes(test_structure_program_takes_directories)


@criterion(description="every delivered record is written in the form record_shapes.md states, keys in the order it lists.")
def structure_canonical_serialisation(workspace: Path) -> float:
    return _passes(test_structure_canonical_serialisation)


'''
for doc in DOC_FILES:
    tail += (
        '@criterion(description="%s matches the settled season on each of four unseen seasons; credit is the share matched.")\n'
        "def whole_%s(workspace: Path) -> float:\n    return _passes(test_whole_%s)\n\n\n"
    ) % (DOC_WORDS[doc], doc, doc)
SINGLE = (
    ("unit_charge_season_total", "on an unseen season with no cap and no floor in reach, the season charge in summary.json matches the settled season."),
    ("cap_release_closures", "on an unseen season whose tier-3 charge cap is set tight to its workshops' charge, the CAP_REACHED findings match the settled season."),
    ("live_window_refusals", "on an unseen season with no cap and no floor in reach, the UNCREDITED_SALVAGE findings match the settled season."),
    ("mutation_family_multiplier", "changing one family multiplier in season_charter.json moves the charge ledger in reconciliation.json to the settled value and leaves vault_audit.json unchanged."),
    ("mutation_grade_step", "changing grade_step in season_charter.json moves the charge ledger in reconciliation.json to the settled value and leaves vault_audit.json unchanged."),
    ("priority_tie_allocation", "on an unseen season where a Q8 tie decides the plan, allocation.json matches the settled season."),
    ("merge_chain_smith_rows", "on an unseen season with a transitive merge chain, each workshop's smith rows match the settled season."),
)
for name, words in SINGLE:
    tail += '@criterion(description="%s")\ndef %s(workspace: Path) -> float:\n    return _passes(test_%s)\n\n\n' % (words, name, name)
NEG = (
    ("hardcoded_sample_answers", "the program replays this season's answers on a different corpus.", -3),
    ("filename_dependent_behaviour", "the program settles the same corpus differently under another name.", -1),
    ("reads_training_corpus_at_runtime", "pointed at another corpus, the program still reads the shipped season under /app/data.", -1),
    ("rebinds_verifier_dependencies", "running the program plants a module or path hook where the grader would import it.", -3),
)
for name, words, _w in NEG:
    tail += (
        '@criterion(description="%s")\ndef negative_%s(workspace: Path) -> float:\n'
        "    return _passes(test_negative_weight_%s)\n\n\n"
    ) % (words, name, name)
reg = ["criteria.structure_%s(weight=1)" % n for n in ("program_delivered", "records_delivered", "program_takes_directories", "canonical_serialisation")]
reg += ["criteria.whole_%s(weight=8)" % d for d in DOC_FILES]
reg += ["criteria.%s(weight=3)" % n for n, _w in SINGLE]
reg += ["criteria.negative_%s(weight=%d)" % (n, w) for n, _x, w in NEG]
tail += "\n".join(reg) + "\n\n\n"
text = head + tail + rest
path.write_text(text, encoding="utf-8")
print("ok", len(text))
