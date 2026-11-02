"""P12 fix v3 (2990713): test edits for G03-1, G05-2, G03-3.

Usage: python3 -B patch_tests_v3.py <test_output.py>
Each replacement must match exactly once.
"""
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()


def swap(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit("match count %d for: %s" % (count, old[:80]))
    text = text.replace(old, new)


# G03-3: run fields in their own view, attachment_authority dropped.
swap('''def _summary_values(out: Path):
    # The summary.json and treaty_working.json fields no ledger digest
    # carries: run identity, dollar totals, per-LOB figures and the two
    # ceded breakdowns.
    try:
        summary = json.loads((out / "summary.json").read_text())
        treaty = json.loads((out / "treaty_working.json").read_text())
        run = summary.get("run", {})
        totals = summary.get("totals", {})
        lobs = summary.get("lobs", {})
        lines = ["run|lobs|%s" % ",".join(str(v) for v in run.get("lobs", []))]
        for key in ("cycles_total", "admission_instant", "attachment_authority"):
            lines.append("run|%s|%s" % (key, run.get(key)))
        for key in''', '''def _summary_run(out: Path):
    # The summary.json run fields no other check carries.
    try:
        run = json.loads((out / "summary.json").read_text()).get("run", {})
        lines = ["run|lobs|%s" % ",".join(str(v) for v in run.get("lobs", []))]
        for key in ("cycles_total", "admission_instant"):
            lines.append("run|%s|%s" % (key, run.get(key)))
        return lines
    except Exception:
        return ["unreadable"]


def _summary_values(out: Path):
    # The summary.json and treaty_working.json dollar figures no ledger
    # digest carries: dollar totals, per-LOB figures and the two ceded
    # breakdowns.
    try:
        summary = json.loads((out / "summary.json").read_text())
        treaty = json.loads((out / "treaty_working.json").read_text())
        totals = summary.get("totals", {})
        lobs = summary.get("lobs", {})
        lines = []
        for key in''')

swap('''    found["summary_values"] = _digest(_summary_values(out))
''', '''    found["summary_run"] = _digest(_summary_run(out))
    found["summary_values"] = _digest(_summary_values(out))
''')

swap('''@criterion(description="On the shipped corpus and on both unseen extracts the summary.json run fields (lobs, cycles_total, admission_instant, attachment_authority), dollar totals and per-LOB figures, and the treaty_working.json ceded_by_lob and ceded_by_reinsurer_canonical values match the reference exactly.")
def summary_and_treaty_values_exact(workspace: Path) -> bool:''',
'''@criterion(description="On the shipped corpus and on both unseen extracts the summary.json run fields lobs, cycles_total and admission_instant match the reference exactly.")
def summary_run_fields_exact(workspace: Path) -> bool:
    def body():
        expected = _expected()
        if _digest(_summary_run(_delivered(workspace))) != expected["shipped"]["digests"]["summary_run"]:
            return False
        for corpus in ("A", "B"):
            result = _run(workspace, corpus)
            if result["code"] != 0 or not _complete(result["out"]):
                return False
            if _digest(_summary_run(result["out"])) != expected[corpus]["digests"]["summary_run"]:
                return False
        return True
    try:
        return bool(body())
    except Exception:
        return False


@criterion(description="On the shipped corpus and on both unseen extracts the summary.json dollar totals and per-LOB figures and the treaty_working.json ceded_by_lob and ceded_by_reinsurer_canonical values match the reference exactly.")
def summary_and_treaty_values_exact(workspace: Path) -> bool:''')

# G03-1: the absence positive goes; the negative covers any import outside the standard library.
swap('''@criterion(description="Every module the delivered reserving.py imports is part of the Python standard library.")
def module_imports_only_standard_library(workspace: Path) -> bool:
    def body():
        tree = ast.parse(_source(workspace))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    return False
                names.append(node.module or "")
        return all(name.split(".")[0] in sys.stdlib_module_names for name in names)
    try:
        return bool(body())
    except Exception:
        return False


''', '')

swap('''# Fires when the module imports a network module named in instruction.md
# (including bare `http`) or shells out to another process.
@criterion(description="The module opens the network or shells out to another process instead of deriving locally.")''',
'''# Fires when the module imports anything outside the Python standard library,
# imports a networking or terminal module named in instruction.md (including
# bare `http`), or shells out to another process.
@criterion(description="The module imports a module from outside the Python standard library or a networking or terminal module, or shells out to another process, instead of deriving locally.")''')

swap('''            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    if top in banned_imports:
                        return True
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top in banned_imports:
                    return True''', '''            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    if top in banned_imports or top not in sys.stdlib_module_names:
                        return True
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if node.level or top in banned_imports or top not in sys.stdlib_module_names:
                    return True''')

# G05-2: a negative for extra entries in the output directory.
swap('''

# POSITIVE WEIGHTS (sum = 64)''', '''

# Fires when the output directory holds any entry beyond the nine documents
# and reserving.py.
@criterion(description="The output directory holds an entry beyond the nine report documents and reserving.py.")
def negative_output_directory_holds_extra_files(workspace: Path) -> bool:
    def body():
        out = _delivered(workspace)
        if not out.is_dir():
            return False
        names = {path.name for path in out.iterdir()}
        return bool(names - (set(_ARTIFACTS) | {"reserving.py"}))
    try:
        return bool(body())
    except Exception:
        return False


# POSITIVE WEIGHTS (sum = 64)''')

swap('''criteria.summary_and_treaty_values_exact(weight=1)
criteria.module_imports_only_standard_library(weight=1)

# NEGATIVE WEIGHTS (sum of absolute values = 23)''', '''criteria.summary_run_fields_exact(weight=1)
criteria.summary_and_treaty_values_exact(weight=1)

# NEGATIVE WEIGHTS (sum of absolute values = 24)''')

swap('''criteria.negative_module_opens_network_or_shells_out(weight=-1)
''', '''criteria.negative_module_opens_network_or_shells_out(weight=-1)
criteria.negative_output_directory_holds_extra_files(weight=-1)
''')

path.write_text(text)
print("patched", path)
