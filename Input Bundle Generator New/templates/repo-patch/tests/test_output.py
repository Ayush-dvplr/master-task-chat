from __future__ import annotations

import csv
import hashlib
import io
import base64
import zlib
import json
import os
import random
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

SAMPLE_SEED = int("{{SAMPLE_SEED}}")
CHALLENGE_SEED = int("{{CHALLENGE_SEED}}")
EVAL_SEED = int("{{EVAL_SEED}}")
PACKAGE = "{{PACKAGE_NAME}}"
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
ARTIFACTS = [
    "/app/out/patched-repo.zip",
    "/app/out/repair-report.json",
    "/app/out/module_core.json",
    "/app/out/module_parser.json",
    "/app/out/module_report.json",
    "/app/out/test_fixes.json",
    "/app/out/summary.json",
]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


_SHIPPED_DATA: dict[str, str] = {{SHIPPED_DATA}}
_DATA_CACHE: list[Path] = []


def _data_dir() -> Path:
    """The agent's /app/ci, rebuilt here: the verifier container never has it."""
    if not _DATA_CACHE:
        root = Path(tempfile.mkdtemp(prefix="shipped-data-"))
        for rel, blob in _SHIPPED_DATA.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.decompress(base64.b64decode(blob)))
        _DATA_CACHE.append(root)
    return _DATA_CACHE[0]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _write_corpus(root: str | Path) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "sample_ledger.json").write_text(json.dumps({"rows": _hidden_rows(SAMPLE_SEED, 3)}), encoding="utf-8")
    with (root / "field_ledger.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["account", "delta", "note"])
        writer.writeheader()
        writer.writerows(_hidden_rows(CHALLENGE_SEED, 4))


def _hidden_rows(seed: int, n: int = 8) -> list[dict[str, object]]:
    rng = random.Random(seed)
    accounts = ["alpha", "beta", "gamma", "delta"]
    rows = []
    for i in range(n):
        rows.append({"account": rng.choice(accounts), "delta": rng.randint(-7, 9), "note": f"n{i}"})
    rows.extend([{"account": "alpha", "delta": -3}, {"account": "beta", "delta": 0}])
    return rows


def _expected(rows: list[dict[str, object]]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        account = str(row["account"])
        totals[account] = totals.get(account, 0) + int(str(row["delta"]))
    return {k: totals[k] for k in sorted(totals)}


def _artifact(name: str) -> Path:
    return OUT_DIR / name


def _extract_archive() -> Path:
    archive = _artifact("patched-repo.zip")
    assert archive.is_file(), "patched-repo.zip missing"
    dest = Path(tempfile.mkdtemp(prefix="repo-patch-check-"))
    dest.chmod(0o755)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            rel = Path(info.filename)
            assert not rel.is_absolute() and ".." not in rel.parts, "unsafe archive member"
            assert not info.filename.endswith("/"), "directory entries are not needed"
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            target.chmod(0o644)
    for directory in [dest, *(p for p in dest.rglob("*") if p.is_dir())]:
        directory.chmod(0o755)
    return dest


def _run_package(repo: Path, code: str) -> Any:
    root = Path(tempfile.mkdtemp(prefix="repo-patch-run-"))
    root.chmod(0o755)
    script = root / "run.py"
    script.write_text(code, encoding="utf-8")
    script.chmod(0o644)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo / "src")
    proc = subprocess.run(_untrusted_command([sys.executable, str(script)]), text=True, capture_output=True, env=env, timeout=10)
    assert proc.returncode == 0, proc.stderr[-500:]
    return json.loads(proc.stdout)


def _read_report() -> dict:
    return json.loads(_artifact("repair-report.json").read_text(encoding="utf-8"))


def _read_json_artifact(name: str) -> dict:
    return json.loads(_artifact(name).read_text(encoding="utf-8"))


def _regression_cases() -> list[dict[str, Any]]:
    cases = []
    for line in (_data_dir() / "regression_cases.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def _manifest() -> dict[str, Any]:
    return json.loads((_data_dir() / "package_manifest.json").read_text(encoding="utf-8"))


def _archive_config() -> dict[str, Any]:
    return json.loads((_data_dir() / "build_config.json").read_text(encoding="utf-8"))["archive"]


def _lint_errors(module: str) -> int:
    issues = json.loads((_data_dir() / "lint_report.json").read_text(encoding="utf-8"))["issues"]
    return sum(1 for issue in issues if issue["module"] == module and issue["severity"] == "error")


def _previously_failing() -> list[str]:
    names = set()
    for line in (_data_dir() / "failing_tests.log").read_text(encoding="utf-8").splitlines():
        if line.startswith("test_") and (line.endswith(" ... FAIL") or line.endswith(" ... ERROR")):
            names.add(line.split(" ", 1)[0].removeprefix("test_"))
    return sorted(names)


def _module_note(name: str, extra: str) -> dict[str, Any]:
    note = _read_json_artifact(f"module_{name}.json")
    assert set(note) == {"module", "status", "fixes", "lint_errors", extra}, sorted(note)
    assert note["lint_errors"] == _lint_errors(name)
    assert note["module"] == name and note["status"] in ("fixed", "unchanged")
    assert isinstance(note["fixes"], list) and all(isinstance(f, str) and f.strip() for f in note["fixes"])
    assert note["status"] == "unchanged" or note["fixes"]
    return note


def _expected_summary() -> dict[str, Any]:
    return {
        "package": PACKAGE,
        "status": "complete",
        "inputs_used": sorted(p.name for p in _data_dir().iterdir() if p.is_file()),
        "artifacts": ARTIFACTS,
        "artifact_count": len(ARTIFACTS),
        "stdlib_only": True,
    }


def _check_artifacts_exist():
    """POSITIVE: requested output files exist at the exact artifact paths."""
    for artifact in ARTIFACTS:
        assert _artifact(Path(artifact).name).is_file()


def _check_archive_is_safe_and_deterministic():
    """POSITIVE: archive members are safe and have deterministic metadata."""
    config = _archive_config()
    method = {"stored": zipfile.ZIP_STORED, "deflated": zipfile.ZIP_DEFLATED}[config["compression"]]
    with zipfile.ZipFile(_artifact("patched-repo.zip")) as zf:
        names = zf.namelist()
        assert names == sorted(names)
        assert len(names) >= 6
        for info in zf.infolist():
            assert info.date_time == tuple(config["timestamp"])
            assert info.compress_type == method
            assert (info.external_attr >> 16) & 0o777 == int(config["mode"], 8)
            assert ".." not in Path(info.filename).parts


def _check_archive_has_expected_source_layout():
    """POSITIVE: repaired repository uses a conventional src package layout."""
    repo = _extract_archive()
    assert (repo / "src" / PACKAGE / "__init__.py").is_file()
    assert (repo / "src" / PACKAGE / "core.py").is_file()
    assert (repo / "tests" / "test_visible.py").is_file()


def _check_metadata_is_python312_and_stdlib_only():
    """POSITIVE: pyproject metadata is Python 3.12 compatible and dependency-free."""
    repo = _extract_archive()
    data = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == PACKAGE
    assert project["version"] == _manifest()["version"]
    assert "3.13" not in project.get("requires-python", "")
    assert project.get("dependencies", []) == []


def _check_package_imports_offline_as_unprivileged_user():
    """POSITIVE: submitted source imports in a child process without verifier privileges."""
    repo = _extract_archive()
    result = _run_package(repo, f"import json, {PACKAGE}; print(json.dumps({{'version': {PACKAGE}.VERSION, 'report': {PACKAGE}.build_report('[]')['version'], 'api': hasattr({PACKAGE}, 'build_report')}}))")
    version = _manifest()["version"]
    assert result == {"version": version, "report": version, "api": True}


def _check_hidden_json_ledgers_are_accumulated_correctly():
    """POSITIVE: hidden JSON ledgers accumulate signed deltas per account."""
    repo = _extract_archive()
    rows = _hidden_rows(EVAL_SEED, 10)
    payload = json.dumps({"rows": rows})
    code = f"import json, {PACKAGE}; print(json.dumps({PACKAGE}.build_report({payload!r}), sort_keys=True))"
    result = _run_package(repo, code)
    assert result["accounts"] == _expected(rows)
    assert result["grand_total"] == sum(_expected(rows).values())


def _check_hidden_csv_ledgers_are_supported():
    """POSITIVE: hidden CSV ledgers use the same semantics as JSON rows."""
    repo = _extract_archive()
    rows = _hidden_rows(EVAL_SEED ^ CHALLENGE_SEED, 9)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["account", "delta", "note"])
    writer.writeheader()
    writer.writerows(rows)
    code = f"import json, {PACKAGE}; print(json.dumps({PACKAGE}.build_report({buf.getvalue()!r}), sort_keys=True))"
    result = _run_package(repo, code)
    assert result["accounts"] == _expected(rows)


def _check_report_output_is_sorted_and_deterministic():
    """POSITIVE: package reports sort account keys and repeat byte-identically."""
    repo = _extract_archive()
    rows = [{"account": "zeta", "delta": 1}, {"account": "alpha", "delta": 2}]
    payload = json.dumps({"rows": rows})
    code = f"import json, {PACKAGE}; a={PACKAGE}.build_report({payload!r}); b={PACKAGE}.build_report({payload!r}); print(json.dumps([a,b], sort_keys=True))"
    result = _run_package(repo, code)
    assert result[0] == result[1]
    assert list(result[0]["accounts"]) == ["alpha", "zeta"]


def _check_visible_tests_are_preserved():
    """POSITIVE: meaningful visible tests remain in the repaired archive."""
    repo = _extract_archive()
    text = (repo / "tests" / "test_visible.py").read_text(encoding="utf-8")
    assert "test_tally_accumulates_rows" in text
    assert "build_report" in text
    assert "pass" not in text.lower()


def _check_repair_report_is_truthful():
    """POSITIVE: repair report names its fixes and at least one passing check."""
    report = _read_report()
    assert report.get("package") == PACKAGE
    assert isinstance(report.get("fixes"), list) and any(isinstance(f, str) and f.strip() for f in report["fixes"])
    checks = report.get("checks", [])
    assert all(isinstance(c, dict) and isinstance(c.get("name"), str) and isinstance(c.get("passed"), bool) for c in checks)
    assert any(c["passed"] for c in checks)


def _check_core_module_artifact_matches_reference():
    """POSITIVE: core note is well formed, marks the repair, and lists tally validations."""
    note = _module_note("core", "validations")
    assert note["status"] == "fixed"
    assert isinstance(note["validations"], list) and note["validations"]


def _check_parser_module_artifact_matches_reference():
    """POSITIVE: parser note is well formed and names the contract entry points."""
    note = _module_note("parser", "contract_terms")
    assert note["status"] == "fixed"
    assert note["contract_terms"] == ["build_report", "load_events", "tally_events"]


def _check_report_module_artifact_matches_reference():
    """POSITIVE: report note is well formed and its determinism claim holds."""
    note = _module_note("report", "deterministic")
    repo = _extract_archive()
    probe = "import json; from " + PACKAGE + " import build_report; t = json.dumps([{'account': 'b', 'delta': 2}, {'account': 'a', 'delta': 1}]); print(json.dumps(build_report(t) == build_report(t)))"
    assert note["deterministic"] is (_run_package(repo, probe) is True)


def _check_test_fixes_artifact_covers_sidecar_regressions():
    """POSITIVE: regression evidence covers every sidecar case without fake passes."""
    payload = _read_json_artifact("test_fixes.json")
    case_names = [case["name"] for case in _regression_cases()]
    result_names = [case["name"] for case in payload.get("regression_cases", [])]
    assert payload["visible_tests_preserved"] is True
    assert payload["previously_failing"] == _previously_failing()
    assert payload["all_regressions_passed"] is True
    assert result_names == case_names
    for result, case in zip(payload["regression_cases"], _regression_cases(), strict=True):
        assert result["expected"] == case["expected"]
        assert result["actual"] == case["expected"]
        assert result["passed"] is True


def _check_summary_artifact_matches_manifest():
    """POSITIVE: summary reports the complete ordered artifact and input manifest."""
    assert _read_json_artifact("summary.json") == _expected_summary()


def _check_source_avoids_network_and_runtime_patch_imports():
    """POSITIVE: repaired source contains no network clients or monkeypatch hooks."""
    repo = _extract_archive()
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in (repo / "src").rglob("*.py"))
    banned = ["requests", "urllib", "socket", "subprocess", "importlib", "sitecustomize", "sys.meta_path"]
    assert not any(token in text for token in banned)


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: detects submissions containing hashes or constants for hidden sample answers."""
    repo = _extract_archive()
    hidden_digest = hashlib.sha256(json.dumps(_expected(_hidden_rows(EVAL_SEED, 10)), sort_keys=True).encode()).hexdigest()
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in repo.rglob("*.py"))
    assert hidden_digest in text or str(EVAL_SEED) in text


def _check_negative_weight_fake_report_without_real_patch():
    """NEGATIVE: detects a report claiming success while the package source is absent."""
    repo = _extract_archive()
    report = _read_report()
    assert report.get("checks") and not (repo / "src" / PACKAGE / "core.py").is_file()


def _check_negative_weight_deleted_visible_tests():
    """NEGATIVE: detects removal or neutering of the shipped visible tests."""
    repo = _extract_archive()
    text = (repo / "tests" / "test_visible.py").read_text(encoding="utf-8") if (repo / "tests" / "test_visible.py").exists() else ""
    assert "test_tally_accumulates_rows" not in text or "assert" not in text


def _check_negative_weight_network_or_monkeypatch_cheat():
    """NEGATIVE: detects network access or import monkeypatch cheat hooks in source."""
    repo = _extract_archive()
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in repo.rglob("*.py"))
    assert any(token in text for token in ["requests", "urllib", "socket", "sys.meta_path", "sitecustomize"])


if __name__ == "__main__":
    import sys as _sys
    _write_corpus(_sys.argv[1] if len(_sys.argv) > 1 else "environment/data")


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="Requested output files exist at the exact artifact paths.")
def artifacts_exist(workspace: Path) -> bool:
    return _holds(_check_artifacts_exist)


@criterion(description="Archive members are safe and have deterministic metadata.")
def archive_is_safe_and_deterministic(workspace: Path) -> bool:
    return _holds(_check_archive_is_safe_and_deterministic)


@criterion(description="Repaired repository uses a conventional src package layout.")
def archive_has_expected_source_layout(workspace: Path) -> bool:
    return _holds(_check_archive_has_expected_source_layout)


@criterion(description="Pyproject metadata is Python 3.12 compatible and dependency-free.")
def metadata_is_python312_and_stdlib_only(workspace: Path) -> bool:
    return _holds(_check_metadata_is_python312_and_stdlib_only)


@criterion(description="Submitted source imports in a child process without verifier privileges.")
def package_imports_offline_as_unprivileged_user(workspace: Path) -> bool:
    return _holds(_check_package_imports_offline_as_unprivileged_user)


@criterion(description="Hidden JSON ledgers accumulate signed deltas per account.")
def hidden_json_ledgers_are_accumulated_correctly(workspace: Path) -> bool:
    return _holds(_check_hidden_json_ledgers_are_accumulated_correctly)


@criterion(description="Hidden CSV ledgers use the same semantics as JSON rows.")
def hidden_csv_ledgers_are_supported(workspace: Path) -> bool:
    return _holds(_check_hidden_csv_ledgers_are_supported)


@criterion(description="Package reports sort account keys and repeat byte-identically.")
def report_output_is_sorted_and_deterministic(workspace: Path) -> bool:
    return _holds(_check_report_output_is_sorted_and_deterministic)


@criterion(description="Meaningful visible tests remain in the repaired archive.")
def visible_tests_are_preserved(workspace: Path) -> bool:
    return _holds(_check_visible_tests_are_preserved)


@criterion(description="repair-report.json names its fixes and at least one passing check.")
def repair_report_is_truthful(workspace: Path) -> bool:
    return _holds(_check_repair_report_is_truthful)


@criterion(description="module_core.json is well formed, marks the repair and lists tally validations.")
def core_module_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_core_module_artifact_matches_reference)


@criterion(description="module_parser.json is well formed and names the contract entry points.")
def parser_module_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_parser_module_artifact_matches_reference)


@criterion(description="module_report.json is well formed and its determinism claim holds.")
def report_module_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_report_module_artifact_matches_reference)


@criterion(description="Regression evidence covers every sidecar case without fake passes.")
def test_fixes_artifact_covers_sidecar_regressions(workspace: Path) -> bool:
    return _holds(_check_test_fixes_artifact_covers_sidecar_regressions)


@criterion(description="summary.json lists the shipped inputs and the ordered deliverables.")
def summary_artifact_matches_manifest(workspace: Path) -> bool:
    return _holds(_check_summary_artifact_matches_manifest)


@criterion(description="Repaired source contains no network clients or monkeypatch hooks.")
def source_avoids_network_and_runtime_patch_imports(workspace: Path) -> bool:
    return _holds(_check_source_avoids_network_and_runtime_patch_imports)


@criterion(description="Detects submissions containing hashes or constants for hidden sample answers.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Detects a report claiming success while the package source is absent.")
def negative_fake_report_without_real_patch(workspace: Path) -> bool:
    return _holds(_check_negative_weight_fake_report_without_real_patch)


@criterion(description="Detects removal or neutering of the shipped visible tests.")
def negative_deleted_visible_tests(workspace: Path) -> bool:
    return _holds(_check_negative_weight_deleted_visible_tests)


@criterion(description="Detects network access or import monkeypatch cheat hooks in source.")
def negative_network_or_monkeypatch_cheat(workspace: Path) -> bool:
    return _holds(_check_negative_weight_network_or_monkeypatch_cheat)


criteria.artifacts_exist(weight=1)
criteria.archive_is_safe_and_deterministic(weight=3)
criteria.archive_has_expected_source_layout(weight=3)
criteria.metadata_is_python312_and_stdlib_only(weight=5)
criteria.package_imports_offline_as_unprivileged_user(weight=5)
criteria.hidden_json_ledgers_are_accumulated_correctly(weight=5)
criteria.hidden_csv_ledgers_are_supported(weight=5)
criteria.report_output_is_sorted_and_deterministic(weight=3)
criteria.visible_tests_are_preserved(weight=3)
criteria.repair_report_is_truthful(weight=3)
criteria.core_module_artifact_matches_reference(weight=3)
criteria.parser_module_artifact_matches_reference(weight=3)
criteria.report_module_artifact_matches_reference(weight=3)
criteria.test_fixes_artifact_covers_sidecar_regressions(weight=3)
criteria.summary_artifact_matches_manifest(weight=3)
criteria.source_avoids_network_and_runtime_patch_imports(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_fake_report_without_real_patch(weight=-5)
criteria.negative_deleted_visible_tests(weight=-3)
criteria.negative_network_or_monkeypatch_cheat(weight=-3)
