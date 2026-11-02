"""Assemble BUNDLE/tests/test_output.py from tests_src parts, the engine and the shipped data.

usage: python3 -B build_tests.py <bundle dir>
"""
import base64
import sys
import zlib
from pathlib import Path

WORK = Path(__file__).resolve().parent
SRC = WORK / "tests_src"
TAGS = {"core": "module_core.json", "metrics": "module_metrics.json",
        "deps": "dependency_resolution.json", "summary": "summary.json"}

CHECKS = []  # (name, weight, description, body or None)
for k in range(1, 5):
    for tag, doc in TAGS.items():
        CHECKS.append(("hidden_book_%d_%s" % (k, tag), 5,
                       "Fresh book %d: %s from the archived package equals the replay exactly" % (k, doc),
                       '_hidden_document(%d, "%s")' % (k, doc)))
CHECKS += [
    ("rows_reshuffled", 5, "Book 2 with other row order, blank event lines and a stray file: module_core.json exact", None),
    ("policy_changed", 5, "Forty shipped sets under another lease length and retry delay: summary.json exact", None),
    ("run_twice", 3, "A relocated copy of book 3 under another hash seed yields the same four documents", None),
]
for tag, doc in TAGS.items():
    CHECKS.append(("shipped_%s" % tag, 3, "The delivered /app/out/%s equals the replay of the shipped book" % doc,
                   '_shipped_document("%s")' % doc))
CHECKS += [
    ("worker_capacity", 3, "Every checkpoint pairs up workers and running jobs one to one inside their pool", None),
    ("state_invariants", 3, "Attempts, remaining work, terminal states and run counts stay consistent", None),
    ("refuse_missing_input", 3, "Absent input files: exit 2, one ERROR MISSING_INPUT line naming the first, no documents", None),
    ("refuse_invalid_policy", 3, "Out-of-bound retry delay: exit 2, one ERROR INVALID_POLICY line, no documents", None),
    ("refuse_unknown_entity", 3, "Event naming an undefined worker: exit 2, one ERROR UNKNOWN_ENTITY line, no documents", None),
    ("refuse_event_conflict", 3, "One event id with two contents: exit 2, one ERROR EVENT_ID_CONFLICT line, no documents", None),
    ("refuse_cycle", 3, "Dependency cycle: exit 2, one ERROR DEPENDENCY_CYCLE line, no documents", None),
    ("artifacts_present", 1, "The seven deliverables exist under /app/out and the JSON ones parse", None),
    ("call_and_module_agree", 3, "leasebook.main and python -m leasebook write the same documents", None),
    ("selftest_matches_rerun", 3, "selftest.json equals a fresh unittest run of the archived tests", None),
    ("build_report", 3, "build_report.json lists the members and hash of package.zip and the versions agree", None),
    ("shipped_tests_kept", 3, "Every shipped test file is inside package.zip unchanged", None),
    ("negative_package_reads_grader_paths", -5, "Package source names the verifier test or log directories", None),
    ("negative_hardcoded_sample_answers", -3, "The archive carries a finished document or a shipped dispatch hash", None),
]


def engine_text() -> str:
    refsim = (WORK / "engine" / "refsim.py").read_text().splitlines()
    gen = (WORK / "engine" / "gen.py").read_text().splitlines()
    start_r = next(i for i, line in enumerate(refsim) if line.startswith("TERMINAL ="))
    start_g = next(i for i, line in enumerate(gen) if line.startswith("POOL_NAMES"))
    banner = "\n\n# " + "-" * 75 + "\n# %s\n# " + "-" * 75 + "\n\n"
    return (banner % "Unit-step reference replay (integer clock, no heap)." + "\n".join(refsim[start_r:]) + "\n"
            + banner % "Seeded book generator; plants coincident instants against a live replay."
            + "\n".join(gen[start_g:]) + "\n")


def checks_text() -> str:
    out = ["\n\n# " + "-" * 75 + "\n# Per-document checks on fresh books.\n# " + "-" * 75 + "\n"]
    for name, _, desc, body in CHECKS:
        if body:
            out.append('\ndef _check_%s() -> None:\n    """POSITIVE: %s."""\n    %s\n' % (name, desc, body))
    out.append('''

def _holds(check) -> bool:
    try:
        check()
    except Exception as error:  # a failed assertion or a crash both mean the property does not hold
        print("%s: %s" % (check.__name__, error), file=sys.stderr)
        return False
    return True

''')
    for name, _, desc, _ in CHECKS:
        assert "{" not in desc and "}" not in desc
        out.append('\n@criterion(description="%s")\ndef %s(workspace: Path) -> bool:\n    return _holds(_check_%s)\n\n'
                   % (desc, name, name))
    out.append("\n")
    for name, weight, _, _ in CHECKS:
        out.append("criteria.%s(weight=%d)\n" % (name, weight))
    return "".join(out)


MAIN_BLOCK = '''

if __name__ == "__main__":
    for _name, _value in list(globals().items()):
        if _name.startswith("_check_") and callable(_value):
            print("PASS" if _holds(_value) else "FAIL", _name[len("_check_"):])
'''


def data_text(bundle: Path) -> str:
    folder = bundle / "environment" / "data"
    lines = ["\n\n_SHIPPED_DATA: dict[str, str] = {\n"]
    for path in sorted(folder.iterdir()):
        blob = base64.b64encode(zlib.compress(path.read_bytes(), 9)).decode()
        lines.append('    "%s": (\n' % path.name)
        for i in range(0, len(blob), 96):
            lines.append('        "%s"\n' % blob[i:i + 96])
        lines.append("    ),\n")
    lines.append("}\n")
    return "".join(lines)


def main() -> None:
    bundle = Path(sys.argv[1])
    text = ((SRC / "head.py").read_text() + engine_text() + (SRC / "books.py").read_text()
            + (SRC / "checks.py").read_text() + checks_text() + data_text(bundle) + MAIN_BLOCK)
    target = bundle / "tests" / "test_output.py"
    target.write_text(text)
    positive = sum(w for _, w, _, _ in CHECKS if w > 0)
    print("wrote", target, "checks", len(CHECKS), "positive", positive, "lines", text.count("\n"))


if __name__ == "__main__":
    main()
