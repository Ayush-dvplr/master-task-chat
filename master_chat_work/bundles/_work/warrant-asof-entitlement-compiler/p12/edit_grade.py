"""P12 grading edits (F4 TS-17, F8 AL-2, F9 TS-13/20, F10 TS-24, F11 TS-27, F12 AL-17).

usage: python3 -B edit_grade.py <test_output.py> [per_call_seconds]
Each legacy text must occur exactly once.
"""
import sys
from pathlib import Path

path = Path(sys.argv[1])
PER_CALL = int(sys.argv[2]) if len(sys.argv) > 2 else 450
src = path.read_text(encoding="utf-8")

EDITS = []


def edit(old, new):
    EDITS.append((old, new))


edit("import shutil\nimport stat\nimport subprocess\n", "import shutil\nimport signal\nimport stat\nimport subprocess\n")
edit("import tempfile\nimport threading\nimport tomllib\n", "import tempfile\nimport threading\nimport time\nimport tomllib\n")

# F12 AL-17: per-call cap and one global deadline that leaves time to write the reward.
edit('_MAX_JSON = 64 * 1024 * 1024\n',
     '_MAX_JSON = 64 * 1024 * 1024\n'
     f'_CALL_SECONDS = {PER_CALL}\n'
     '_BUDGET_SECONDS = 2400\n'
     '_T0 = time.monotonic()\n')

# F4 TS-17: strict JSON equality (no True == 1).
edit('def _rows(items):\n',
     'def _same(a, b) -> bool:\n'
     '    return a is not None and b is not None and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)\n'
     '\n\n'
     'def _rows(items):\n')

# F10 TS-24: own session, kill the whole group on timeout and after return.
edit('''    try:
        proc = subprocess.run(argv, cwd=work, env=env, capture_output=True, timeout=900, check=False)
    except Exception:
        return None
    return proc.returncode
''', '''    left = _BUDGET_SECONDS - (time.monotonic() - _T0)
    if left <= 1:
        return None
    try:
        proc = subprocess.Popen(argv, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
    except Exception:
        return None
    try:
        proc.communicate(timeout=min(_CALL_SECONDS, left))
        rc = proc.returncode
    except Exception:
        rc = None
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if rc is None:
        try:
            proc.communicate(timeout=10)
        except Exception:
            pass
    return rc
''')

# F4: strict compares.
edit('            if any(_rows(got[k]) != _rows(exp[k]) for k in exp if k != "self_check") or got["self_check"] != exp["self_check"]:\n',
     '            if any(_rows(got[k]) != _rows(exp[k]) for k in exp if k != "self_check") or not _same(got["self_check"], exp["self_check"]):\n')
edit('        summ, exp = _artifact("summary.json"), _expected_shipped()[3]\n        if summ != exp:\n',
     '        summ, exp = _artifact("summary.json"), _expected_shipped()[3]\n        if not _same(summ, exp):\n')
edit('        return _run_all(_tier("tier_a"), "tier_a")["summary"] == _expected_tier("tier_a")[3]\n',
     '        return _same(_run_all(_tier("tier_a"), "tier_a")["summary"], _expected_tier("tier_a")[3])\n')
edit('        return isinstance(got, dict) and got.get("self_check") == _expected_shipped()[2]["self_check"]\n',
     '        return isinstance(got, dict) and _same(got.get("self_check"), _expected_shipped()[2]["self_check"])\n')
edit('        return all(value is not None and value == _artifact(name) for value, name in pairs)\n',
     '        return all(_same(value, _artifact(name)) for value, name in pairs)\n')

# F9 TS-13: split config_resolution_exact; F8 AL-2: altered --config and byte format checks.
edit('''@criterion(description="config.json and the delivered tool's resolution of three unseen corpora equal the recomputed configurations")
def config_resolution_exact(workspace: Path) -> bool:
    try:
        if _artifact("config.json") != _expected_shipped()[0]:
            return False
        return all(_run_all(_tier(t), t)["config"] == _expected_tier(t)[0] for t in ("tier_a", "tier_b", "tier_c"))
    except Exception:
        return False
''', '''@criterion(description="config.json equals the recomputed configuration of the shipped corpus")
def config_shipped_exact(workspace: Path) -> bool:
    try:
        return _same(_artifact("config.json"), _expected_shipped()[0])
    except Exception:
        return False


@criterion(description="the delivered tool resolves three unseen corpora into the recomputed configurations")
def config_heldout_resolution_exact(workspace: Path) -> bool:
    try:
        return all(_same(_run_all(_tier(t), t)["config"], _expected_tier(t)[0]) for t in ("tier_a", "tier_b", "tier_c"))
    except Exception:
        return False


def _altered():
    """tier_b with a hand-edited --config: anchors two days earlier and a different prod approvals_required."""
    def build_one():
        root = _tier("tier_b")
        cfg = dict(_expected_tier("tier_b")[0])
        for key in ("as_of", "recorded_cutoff"):
            cfg[key] = iso_z(stamp(cfg[key]) - 2 * DAY)
        cfg["prod.approvals_required"] = 1 if cfg["prod.approvals_required"] != 1 else 2
        W = World(load(root), cfg)
        exp = {env: {k: utc(v) for k, (v, _) in sorted(W.profile(env)["keys"].items())} for env in ("dev", "prod")}
        out = _scratch("warrant-altered-")
        out.chmod(0o777)
        path = out / "config.json"
        path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
        path.chmod(0o644)
        got = {}
        for env in ("dev", "prod"):
            target = out / f"profile_{env}.json"
            rc = _invoke(["compile", "--data", str(root), "--config", str(path), "--profile", env, "--out", str(target)])
            got[env] = _read_json(target) if rc == 0 else None
        return got, exp
    return _cached("altered", build_one)


@criterion(description="the delivered tool compiles unseen corpus tier_b under a --config with earlier anchors and another prod approvals_required, as recomputed")
def altered_config_profiles_exact(workspace: Path) -> bool:
    try:
        got, exp = _altered()
        return all(_same(got[env], exp[env]) for env in ("dev", "prod"))
    except Exception:
        return False


_LIST_ORDER = {"rejects": ("source", "record", "reason"), "unresolved": ("source", "record", "reason"),
               "held_grants": ("profile", "ticket"), "unattested": ("profile", "principal", "permission"),
               "sod": ("profile", "principal", "rule")}


@criterion(description="every delivered JSON artifact is written in the contract layout and its report lists follow the contract order")
def artifacts_contract_layout(workspace: Path) -> bool:
    try:
        for name in ARTIFACT_NAMES:
            if not name.endswith(".json"):
                continue
            raw = (OUT / name).read_bytes()
            doc = _artifact(name)
            if doc is None or raw not in {(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=a) + "\\n").encode("utf-8")
                                          for a in (False, True)}:
                return False
        report = _artifact("validation_report.json")
        for part, fields in _LIST_ORDER.items():
            rows = report[part]
            keys = [tuple(str(r[f]) for f in fields) for r in rows]
            if any(a > b for a, b in zip(keys, keys[1:])):
                return False
            if part in ("rejects", "unresolved") and len({json.dumps(r, sort_keys=True) for r in rows}) != len(rows):
                return False
        inputs = _artifact("summary.json")["inputs"]
        return inputs == sorted(inputs)
    except Exception:
        return False
''')

# F11 TS-27: transcript cross-checked against the verifier's own run.
edit('''        tool = _tool_dir()
        repairs = report.get("repairs")
''', '''        own = _run_all(_shipped_dir(), "shipped")["rc"]
        if any(own.get(k) != 0 for k in ("resolve-config", "dev", "prod", "audit", "summarize")):
            return False
        tool = _tool_dir()
        repairs = report.get("repairs")
''')

# Registrations.
edit('criteria.summary_identity_triangle(weight=5)\n', 'criteria.summary_identity_triangle(weight=3)\n')
edit('criteria.profile_dev_values_exact(weight=3)\ncriteria.config_resolution_exact(weight=3)\n',
     'criteria.profile_dev_values_exact(weight=5)\ncriteria.config_shipped_exact(weight=2)\n'
     'criteria.config_heldout_resolution_exact(weight=2)\ncriteria.altered_config_profiles_exact(weight=2)\n')
edit('criteria.report_transcript_complete(weight=3)\n', 'criteria.report_transcript_complete(weight=1)\n')
edit('criteria.artifacts_reproduce_from_tool(weight=1)\n',
     'criteria.artifacts_reproduce_from_tool(weight=1)\ncriteria.artifacts_contract_layout(weight=1)\n')

for old, new in EDITS:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"edit target found {n} times: {old[:80]!r}")
    src = src.replace(old, new)
path.write_text(src, encoding="utf-8")
print(f"applied {len(EDITS)} edits, per call {PER_CALL}s")
