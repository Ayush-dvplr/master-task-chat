"""Apply the P12 edits to tests/test_output.py (blob and extracts are sealed separately).

usage: python3 -B patch_tests.py <test_output.py in> <test_output.py out>
"""
import sys

src = open(sys.argv[1]).read()


def sub(old, new, count=1):
    global src
    n = src.count(old)
    if n != count:
        raise SystemExit("expected %d hit(s), found %d for: %r" % (count, n, old[:80]))
    src = src.replace(old, new)


# G03-6: name the real source of the sealed fixtures.
sub("# _EXPECTED_BLOB and _EXTRACTS are populated by solution/rebuild_fixtures.py.\n"
    "# Each is a zlib+base64 blob. Do NOT hand-edit.\n",
    "# _EXPECTED_BLOB holds the values solution/solve.py writes over environment/data and\n"
    "# over the two extracts in _EXTRACTS; both are zlib+base64 and are sealed together.\n")

# G03-1: the agent module runs as the unused solver uid from a staged, root-owned copy.
sub('_CACHE = {}\n',
    '_CACHE = {}\n'
    '_SOLVER_UID = 1002\n'
    '_DQ_KEYS = ["late_recorded", "duplicate_identical", "duplicate_conflicting",\n'
    '            "cross_source_collapsed", "fold_disambiguated", "gap_shifted",\n'
    '            "log_continuations", "unknown_reinsurer_rows", "out_of_horizon_rows",\n'
    '            "block_unit_rows", "paren_negatives", "restatement_gaps"]\n'
    '_AUDIT_SECTIONS = ["settlement", "attachment", "endorsements", "reserve_state",\n'
    '                   "chain_ladder", "allocation"]\n')

STAGE = '''def _stage(module: Path, room: str, data: Path, out: Path) -> Path:
    copy = Path(room) / "reserving.py"
    shutil.copyfile(module, copy)
    os.chmod(copy, 0o644)
    os.chmod(room, 0o755)
    for path in [data, out, *data.rglob("*")]:
        os.chown(path, _SOLVER_UID, _SOLVER_UID)
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    return copy


def _kill_solver_processes() -> None:
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("Uid:") and str(_SOLVER_UID) in line.split()[1:2]:
                try:
                    os.kill(int(entry.name), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                break


def _launch(copy: Path, room: str, data: Path, out: Path) -> int:
    command = ["setpriv", "--reuid=%d" % _SOLVER_UID, "--regid=%d" % _SOLVER_UID,
               "--clear-groups", sys.executable, "-I", str(copy),
               "--data", str(data), "--out", str(out)]
    process = None
    code = -1
    try:
        process = subprocess.Popen(command, cwd=room, env=dict(_ENV),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            process.communicate(timeout=500)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.communicate()
        code = process.returncode
    except (OSError, subprocess.SubprocessError):
        code = -1
    finally:
        if process is not None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        _kill_solver_processes()
    return code


def _run(workspace: Path, tag: str):
'''
sub('def _run(workspace: Path, tag: str):\n', STAGE)

sub('''    copy = Path(room) / "reserving.py"
    shutil.copy2(module, copy)
    os.chmod(copy, 0o755)
    for path in sorted(data.iterdir()):
        if path.is_file():
            result["before"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    command = [sys.executable, "-I", str(copy), "--data", str(data), "--out", str(out)]
    process = None
    try:
        process = subprocess.Popen(command, cwd=room, env=dict(_ENV),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            process.communicate(timeout=500)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.communicate()
        result["code"] = process.returncode
    except Exception:
        result["code"] = -1
    finally:
        if process is not None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
''', '''    copy = _stage(module, room, data, out)
    for path in sorted(data.iterdir()):
        if path.is_file():
            result["before"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    result["code"] = _launch(copy, room, data, out)
''')

sub('''    copy = Path(room) / "reserving.py"
    shutil.copy2(_module(workspace), copy)
    os.chmod(copy, 0o755)
    command = [sys.executable, "-I", str(copy), "--data", str(data), "--out", str(out)]
    process = None
    try:
        process = subprocess.Popen(command, cwd=room, env=dict(_ENV),
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            process.communicate(timeout=500)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.communicate()
    except Exception:
        pass
    finally:
        if process is not None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
''', '''    copy = _stage(_module(workspace), room, data, out)
    _launch(copy, room, data, out)
''')

# G03-4 (TS-16): a banned literal counts only where it is compared or assigned.
sub('''    return numbers, strings


@criterion''', '''    return numbers, strings


def _compared_or_assigned_strings(workspace: Path):
    tree = ast.parse(_source(workspace))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            targets = [node]
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            targets = [node.value]
        else:
            continue
        for target in targets:
            for sub_node in ast.walk(target):
                if isinstance(sub_node, ast.Constant) and isinstance(sub_node.value, str):
                    found.append(sub_node.value)
    return found


def _hardcodes_sample_answers(workspace: Path) -> bool:
    if not _module(workspace).is_file():
        return False
    numbers, strings = _literals(workspace)
    shipped = _expected()["shipped"]
    marks = {shipped["scalars"].get(k) for k in
             ("total_ceded", "total_ultimate", "total_paid_to_date",
              "treaty_ceded_total", "treaty_retention",
              "treaty_working_excess", "treaty_cat_excess")}
    marks = {m for m in marks if isinstance(m, int) and m > 1000}
    if marks & numbers:
        return True
    hexes = set(shipped.get("digests", {}).values())
    if any(v in hexes for v in strings):
        return True
    banned_literal_strings = {"2032-07-01T00:00:00Z"}
    return any(v in banned_literal_strings for v in _compared_or_assigned_strings(workspace))


@criterion''')

sub('''    def body():
        if not _module(workspace).is_file():
            return False
        numbers, strings = _literals(workspace)
        shipped = _expected()["shipped"]
        marks = {shipped["scalars"].get(k) for k in
                 ("total_ceded", "total_ultimate", "total_paid_to_date",
                  "treaty_ceded_total", "treaty_retention",
                  "treaty_working_excess", "treaty_cat_excess")}
        marks = {m for m in marks if isinstance(m, int) and m > 1000}
        if marks & numbers:
            return True
        hexes = set(shipped.get("digests", {}).values())
        if any(v in hexes for v in strings):
            return True
        banned_literal_strings = {"2032-07-01T00:00:00Z"}
        if any(v in banned_literal_strings for v in strings):
            return True
        return False
    return _safe(body)
''', '''    return _safe(lambda: _hardcodes_sample_answers(workspace))
''')

sub('''# Excludes scalars that are small integers reused by the task's own
# vocabulary (such as 0, 1, 2, 3, 26) to avoid false positives.
''', '''# Excludes scalars that are small integers reused by the task's own
# vocabulary (such as 0, 1, 2, 3, 26) to avoid false positives. The epoch
# boundary instant counts only where it is compared or assigned.
''')

# G05-6 (AL-28): one penalty per act.
sub('''# which proves the output is independent of the input. Pairs with
# program_reproduces_unseen_extract_beta on the positive side.
''', '''# which proves the output is independent of the input. Stays silent when
# negative_hardcoded_sample_answers already fires on the same module.
''')
sub('''    def body():
        first = _run(workspace, "A")
        second = _run(workspace, "B")
''', '''    def body():
        if _safe(lambda: _hardcodes_sample_answers(workspace)):
            return False
        first = _run(workspace, "A")
        second = _run(workspace, "B")
''')

# G03-5 renames.
sub('''@criterion(description="LOB ledger backbone (per-claim lob|cycle|claim|reinsurer|layer|ultimate|paid) digests exactly, keyed only on fields the contract declares.")
def development_spine_exact(''', '''@criterion(description="On the shipped corpus every LOB ledger row's lob, cycle, claim_ref, reinsurer_canonical, layer, ultimate and paid_to_date match the reference exactly.")
def ledger_backbone_exact(''')
sub('''@criterion(description="Ledger spine (ceded_hours, alae, ibnr-as-ultimate-minus-paid) digests exactly for the running-totals-never-heal invariant.")
def ibnr_carryforward_exact(''', '''@criterion(description="On the shipped corpus every LOB ledger row's ceded_hours, alae and ultimate minus paid_to_date match the reference exactly.")
def ledger_spine_exact(''')

# G05-2 / G03-5: attachment check keeps the two strings; absence moves to its own check.
sub('''        if not _str_eq(audit.get("attachment",{}).get("attachment_rule"), "clash_cover_per_event"):
            return False
        if not _int_eq(audit.get("attachment",{}).get("layer_count"), 3):
            return False
        layer_names = audit.get("attachment",{}).get("layer_names")
        if not isinstance(layer_names, list) or layer_names != _LAYERS:
            return False
        # methodology_audit.json carries no counterfactual_summary key.
        if "counterfactual_summary" in audit:
            return False
        return True
    return _safe(body)
''', '''        if not _str_eq(audit.get("attachment",{}).get("attachment_rule"), "clash_cover_per_event"):
            return False
        return True
    return _safe(body)


def _all_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _all_keys(value)


@criterion(description="methodology_audit.json holds only its six declared sections and no key at any depth names a counterfactual.")
def methodology_audit_holds_only_declared_sections(workspace: Path) -> bool:
    def body():
        audit = json.loads((_delivered(workspace) / "methodology_audit.json").read_text())
        if not isinstance(audit, dict) or sorted(audit) != sorted(_AUDIT_SECTIONS):
            return False
        return all("counterfactual" not in str(key).lower() for key in _all_keys(audit))
    return _safe(body)


@criterion(description="The endorsements, reserve_state, chain_ladder and allocation sections of methodology_audit.json match the reference on the shipped corpus and on both unseen extracts.")
def methodology_audit_remaining_sections_exact(workspace: Path) -> bool:
    def body():
        expected = _expected()
        outs = [("shipped", _delivered(workspace))]
        for corpus in ("A", "B"):
            result = _run(workspace, corpus)
            if result["code"] != 0:
                return False
            outs.append((corpus, result["out"]))
        for corpus, out in outs:
            audit = json.loads((out / "methodology_audit.json").read_text())
            for section in ("endorsements", "reserve_state", "chain_ladder", "allocation"):
                if audit.get(section) != expected[corpus]["audit"][section]:
                    return False
        return True
    return _safe(body)


@criterion(description="On both unseen extracts every data_quality tally and every ledger row's outcome and reason match the reference exactly.")
def hidden_extract_quality_tallies_and_outcomes_exact(workspace: Path) -> bool:
    def body():
        expected = _expected()
        for corpus in ("A", "B"):
            result = _run(workspace, corpus)
            if result["code"] != 0 or not _complete(result["out"]):
                return False
            dq = json.loads((result["out"] / "data_quality.json").read_text())
            for key in _DQ_KEYS:
                if not _int_eq(dq.get(key), expected[corpus]["scalars"].get(f"dq_{key}")):
                    return False
            outcome = _digest(_views(result["out"])["ledger_outcome"])
            if outcome != expected[corpus]["digests"]["ledger_outcome"]:
                return False
        return True
    return _safe(body)


@criterion(description="The output directory holds the nine report documents and reserving.py and nothing else.")
def output_directory_holds_exactly_ten_documents(workspace: Path) -> bool:
    def body():
        names = {path.name for path in _delivered(workspace).iterdir()}
        return names == set(_ARTIFACTS) | {"reserving.py"}
    return _safe(body)
''')

# Weights.
sub('''# POSITIVE WEIGHTS (sum = 67)
criteria.development_spine_exact(weight=5)
criteria.ibnr_carryforward_exact(weight=5)
''', '''# POSITIVE WEIGHTS (sum = 69)
criteria.ledger_backbone_exact(weight=5)
criteria.ledger_spine_exact(weight=5)
''')
sub('criteria.cross_artifact_identity_triangle_holds(weight=5)\n',
    'criteria.cross_artifact_identity_triangle_holds(weight=1)\n')
sub('criteria.methodology_audit_attachment_exact(weight=3)\n',
    'criteria.methodology_audit_attachment_exact(weight=3)\n')
sub('criteria.chain_ladder_development_exact(weight=3)\n',
    'criteria.chain_ladder_development_exact(weight=3)\n'
    'criteria.hidden_extract_quality_tallies_and_outcomes_exact(weight=3)\n')
sub('criteria.program_runs_and_exits_clean(weight=1)\n',
    'criteria.program_runs_and_exits_clean(weight=1)\n'
    'criteria.methodology_audit_holds_only_declared_sections(weight=1)\n'
    'criteria.methodology_audit_remaining_sections_exact(weight=1)\n'
    'criteria.output_directory_holds_exactly_ten_documents(weight=1)\n')

open(sys.argv[2], "w").write(src)
print("patched")
