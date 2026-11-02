"""Behavioral verifier for the spectrum license clearinghouse."""
# pyright: reportMissingImports=false
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import zlib
from pathlib import Path
from typing import Any, Callable

from rewardkit import criteria, criterion

SAMPLE_SEED = 8301742261
CHALLENGE_SEED = 530918447
EVAL_SEED = 774120663
OUT = Path("/app/out")
SCRIPT = OUT / "clear_spectrum.py"
REPORTS = (
    "manifest.json", "data_quality.json", "grant_ledger.json",
    "spectrum_slice_ledger.json", "preemption_ledger.json",
    "party_settlements.json", "auction_adjustments.json",
    "exception_register.json", "audit_trace.json",
)
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

_PACKED = {
    "activation_events.jsonl": "eNqd0MEKgkAQBuB7jzHnhNnV3WJvapego6ciRHTJJVHIpSDp3RuMsmztEMzp/4fhYzrIcmvOmTVNnZoCFIRx4jGYQ2VyXbf6EW7WsRdSmOuqakHtIGawp53mkh7LKyhfCF8gzqE0h/IVyT5qbXaydIMjlx4ymoQtFSLNlk7qungveYL+s7zNOiePu3jRB4+PeDLAMU8u0MkjgfzBG+xTvChc/fE/8QUUAU78rwe4gVSyAXgHa/OA9Q==",
    "auction_results.jsonl": "eNrN0T0LwjAQBuDdn5HZQHLVDt1aJ8FJdHEJoTloQVtJ0g4W/7un7WCxagUF4ab7eOHhGmYxLa1RuWERi9dcxmzKdJX6vCy65pbHkpoW69xRl0Vy2l2hUdrTCgiYcwkcxEaI6FY7unBe+8rRXFNcjdTZ5ykWDtvg1XLB43bNdikhF5Kql4KFuR9Cb2i1R0WZ3qkjWnXITiorK8simAlxnjQPvOQ9D57ywr/hBWKQB4Pfg5Hfg6/w4BUvGMkLB3nBEC+Rv+IlH39vJA/klXcBMhH+xw==",
    "corrections.jsonl": "eNqrVkrOLypKTS7JzM+Lz0xRslJy9g/SNVTSUcrJTE7NK06FCPp4Ous6AgUTc/NL80rigTIlxUpW5gaGtVzVWE0wIs4EXUMDY1xGGGMzwgnTCFOQEQA72T9Y",
    "exclusions.jsonl": "eNqN0E0LgkAQBuB7P2OOoTCuuKW3/DgEHjp4iCIkdMkl0UijD+m/tyqU5hbCnN5hXh6mAnaL0kvB8yzkMVjgrVUNFEh5xLKCtZm/dNSFCE/7c3lvo5Xqen5QhxFL0wKsLTgEduIwv4bH5AGWbhgzRFQg4YfkHZlNVJSiSbQQJFRFTUygEQtRzEZUsizuLkln+ZxUEjGRie2+eNqz6l9WOh9Ya73MSoLGIrfqnaXcai/cEdox/6XGwEzpL7OGf/6L5sf8AoCmkAw=",
    "grant_revisions.jsonl": "eNrd1l9rwjAQAPD3fYw8W0guTe36ZqvIQGEMnzZGydpgw6SVtHM42XdfqjJt0zpRpmPQpzvzx1/vjq6QElGm4lDGyEPDB4v0UAdNFU+LbcgiOqDEQuYyS5FHOtsVIg55oX8AGJhFwAI8wdhbP496RV7w4i3XeR4VciF0ZCYjkeZis+3oLrDKk+ZcFctN6N7qD0aTMhiJ2UwvfUJBeXYA6Fmvzt7D1+QDeZQxzDDuoEROk++Quw7pQ9X2To6FiX4qdxJpvJ+ECYFdcq5kpmSxRB6UOyVcifBlrq/h6K0/b1YGlH8YClqh4GJQBBtQt/jSUGBUFBxZUeRsqGFvPK5D1YzANOq2GjkHjPaTOyNWIXJxIxE1iOhvEfk/11L5egJac3LMpnNuT2g6WknunEi1lrrNULYBZR8JRc+GMmvJMDJryXHbamm/pY7st7pRc7/Z/mGj9sFkNxtFPC3/s4j/FRMzSolVmGgrEzt7LPkDo+VqU4maU8lpJoJTus2tDu7mZmP+9YTMKvqTRH6vXzfahK71wWTXlGxsKuETlEjb2IYKE4G10xddTuQj",
    "guard_bands.jsonl": "eNqrVkovTSxKic9MUbJScnfSdVTSUcrJTE7NK06FiPl4OoMFIcqyM6qUrIxMDWq5qtE0OmHT6ISq0dQAqBEA3Hwiew==",
    "licenses.jsonl": "eNqrVsrJTE7NK06Nz0xRslLy8XTWdVTSUcovz0stii9ILCqphEgE6Dr6BHiApJJTc3KKlayilZwNgTxnI6VYHaWc/PL47IwqJStjU1MDINBRyshMz4AJmUGEikuAxgGNMjIwMtM1MASiEAMDKzCKApqUmpeCLGmMJFnLVY3pTCfsznRyDUF1pRHIlcZorjTDdKU5bVzp6ILdnS6uPmgOtURzowXxbjTC50ZDFDcCAJQChdY=",
    "parties.json": "eNqL5lJQqFYqSCwqqYzPTFGyUgrQdfQJ8HBU0lHKS8xNBQo45hRkJCqEZxal5qQWFyvV6mDqcHINQdLglFqSqBBUWpSYg1Wxu6OvL5Jq98Tc3ESFgNKknMxkheDEtNSSSqzaXFx9kC1xSc0B2uKZH6JUyxXLBQAiuztK",
    "policy.json": "eNpNjEEKwkAMRfdzimHWVlJBELdu3fUAYdBoA51MSaeVKt7dVKG4+ov3/ns57wPJnYVwIh04Szj60JybU1VvIWwW3iunqDPaZuUym1HVAPCF16wpSsH8ENJ/ZTVSLKQcO7yQlMHIbg/rm25x7AqqOT+OvWVS+8Q2j7pkDgDu7T5Y2zTh",
    "schema.md": "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",
}

SCENARIOS = (
    "revision_cells", "revision_scalar", "activation_identifier",
    "half_open_boundary", "guard_abutment", "correction_tie",
    "half_up_midpoint", "exclusion_span",
)
_EXPECTED_BUNDLES = {
    "revision_cells": "d9653e55907d47c3b4beb3579309652f8bc24911ca071f6577a1d96864da2cfe",
    "revision_scalar": "812c244de9c1e17ddb72a88414cd5eddbeda2a9d0d51e4d8c1d9daef04fbeb04",
    "activation_identifier": "38c32565e48a114a1994e58b1e70c50bc662c203c2e20478e05a334e7a2b7980",
    "half_open_boundary": "ba500a2fe24a8688ccbacd8c3cb28557917c1bb5433cc66445c4b4817ca99c00",
    "guard_abutment": "d6ab61f3a07f9875b6d48323f0d464bd9ec3469f6ccaeb87734d5fd3c9a1830f",
    "correction_tie": "06800255a1cbbd4f019bf5dc1ddff4d0f5a7b871a364de27ceb7ca491c6d6f53",
    "half_up_midpoint": "91e76adc7b6c46108938d13b7b314556b24ecc8b8147b3a0d2cca36113bd0fc6",
    "exclusion_span": "d35c949ff320ed0bae85c2a91d7219e1f42100caab98d0b273fd16a8dbebc942",
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _apply_scenario(data: Path, scenario: str) -> None:
    grants_path = data / "grant_revisions.jsonl"
    grants = _read_rows(grants_path)
    if scenario == "revision_cells":
        peer = dict(next(row for row in grants if row["record_id"] == "GR-1B"))
        peer["record_id"] = "GR-1Z"
        peer["cells"] = list(reversed(peer["cells"]))
        grants.append(peer)
        _write_rows(grants_path, grants)
    elif scenario == "revision_scalar":
        peer = dict(next(row for row in grants if row["record_id"] == "GR-2A"))
        peer["record_id"] = "GR-2Z"
        peer["priority"] = 4
        grants.append(peer)
        _write_rows(grants_path, grants)
    elif scenario == "activation_identifier":
        template = dict(next(row for row in grants if row["record_id"] == "GR-1B"))
        for record_id, grant_id in (("GR-ACT-1", "G-ACT-1"), ("GR-ACT-2", "G-ACT-2")):
            row = dict(template)
            row.update(record_id=record_id, grant_id=grant_id, revision=1,
                       recorded_at="2025-12-27T00:00:00Z", party_id="P-BETA",
                       cells=["C1"], low_khz=3550000, high_khz=3552000,
                       start="2026-01-02T18:00:00Z", end="2026-01-02T19:00:00Z",
                       priority=10, share_bps=5000)
            grants.append(row)
        _write_rows(grants_path, grants)
        activations_path = data / "activation_events.jsonl"
        activations = _read_rows(activations_path)
        activations.append({
            "activation_id": "PRIMARY-Z", "license_id": "LIC-A", "cells": ["C1"],
            "low_khz": 3550000, "high_khz": 3552000,
            "start": "2026-01-02T18:00:00Z", "end": "2026-01-02T19:00:00Z",
        })
        _write_rows(activations_path, activations)
    elif scenario == "half_open_boundary":
        guards_path = data / "guard_bands.jsonl"
        guards = _read_rows(guards_path)
        next(row for row in guards if row["license_id"] == "LIC-B")["guard_khz"] = 0
        _write_rows(guards_path, guards)
        template = dict(next(row for row in grants if row["record_id"] == "GR-3A"))
        for record_id, grant_id, party, low, high in (
            ("GR-HL", "G-HL", "P-GAMMA", 3561000, 3563000),
            ("GR-HR", "G-HR", "P-DELTA", 3563000, 3565000),
        ):
            row = dict(template)
            row.update(record_id=record_id, grant_id=grant_id, party_id=party,
                       cells=["C3"], low_khz=low, high_khz=high,
                       start="2026-01-02T18:00:00Z", end="2026-01-03T00:00:00Z",
                       priority=1, share_bps=5000)
            grants.append(row)
        _write_rows(grants_path, grants)
    elif scenario == "guard_abutment":
        template = dict(next(row for row in grants if row["record_id"] == "GR-1B"))
        for record_id, grant_id, party, low, high in (
            ("GR-GL", "G-GL", "P-BETA", 3550000, 3555500),
            ("GR-GR", "G-GR", "P-DELTA", 3555000, 3560000),
        ):
            row = dict(template)
            row.update(record_id=record_id, grant_id=grant_id, revision=1,
                       recorded_at="2025-12-27T00:00:00Z", party_id=party,
                       cells=["C2"], low_khz=low, high_khz=high,
                       start="2026-01-02T13:00:00Z", end="2026-01-02T17:00:00Z",
                       priority=-10, share_bps=5000)
            grants.append(row)
        _write_rows(grants_path, grants)
    elif scenario == "correction_tie":
        licenses_path = data / "licenses.jsonl"
        licenses = _read_rows(licenses_path)
        licenses.append({"license_id": "LIC-C", "owner_party_id": "P-ALPHA",
                          "cells": ["C4"], "low_khz": 3600000, "high_khz": 3601000,
                          "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z"})
        _write_rows(licenses_path, licenses)
        grants.append({"record_id": "GR-C", "grant_id": "G-C", "revision": 1,
                       "recorded_at": "2025-12-27T00:00:00Z", "status": "active",
                       "license_id": "LIC-C", "party_id": "P-BETA", "cells": ["C4"],
                       "low_khz": 3600000, "high_khz": 3601000,
                       "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T01:00:00Z",
                       "priority": 1, "share_bps": 5000})
        _write_rows(grants_path, grants)
        corrections_path = data / "corrections.jsonl"
        corrections = _read_rows(corrections_path)
        corrections.append({"correction_id": "COR-C", "license_id": "LIC-C", "amount_cents": 1})
        _write_rows(corrections_path, corrections)
    elif scenario == "half_up_midpoint":
        licenses_path = data / "licenses.jsonl"
        licenses = _read_rows(licenses_path)
        licenses.append({"license_id": "LIC-D", "owner_party_id": "P-ALPHA",
                          "cells": ["C5"], "low_khz": 3610000, "high_khz": 3611000,
                          "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T00:30:00Z"})
        _write_rows(licenses_path, licenses)
        auctions_path = data / "auction_results.jsonl"
        auctions = _read_rows(auctions_path)
        auctions.append({"record_id": "AR-D", "auction_id": "AU-D", "revision": 1,
                         "recorded_at": "2025-12-27T00:00:00Z", "status": "active",
                         "license_id": "LIC-D", "start": "2026-01-01T00:00:00Z",
                         "end": "2026-01-01T00:30:00Z", "rate_cents_per_mhz_hour": 1})
        _write_rows(auctions_path, auctions)
    elif scenario == "exclusion_span":
        exclusions_path = data / "exclusions.jsonl"
        exclusions = _read_rows(exclusions_path)
        exclusions.append({"exclusion_id": "EX-SPAN", "license_id": "LIC-A",
                           "party_id": "*", "cells": ["C1"],
                           "low_khz": 3551500, "high_khz": 3557500,
                           "start": "2026-01-01T05:00:00Z", "end": "2026-01-02T07:00:00Z"})
        _write_rows(exclusions_path, exclusions)
    else:
        raise ValueError(f"unknown scenario: {scenario}")


def _write_variant(root: Path, scenario: str) -> Path:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    for name, blob in _PACKED.items():
        (data / name).write_bytes(zlib.decompress(base64.b64decode(blob)))
    _apply_scenario(data, scenario)
    for path in data.iterdir():
        path.chmod(0o644)
    data.chmod(0o755)
    return data


def _write_corpus(root: Path, fresh: bool = True) -> Path:
    return _write_variant(root, "revision_cells" if fresh else "revision_scalar")


def _root_only_tests() -> bool:
    try:
        stat = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return stat.st_uid == 0 and stat.st_mode & 0o077 == 0


def _grant(path_text: str) -> None:
    path = Path(path_text)
    if not path_text.startswith("/app") or not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if parent == Path("/app"):
                break
    except OSError:
        pass


def _command(args: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests():
        raise RuntimeError("POSIX isolation required")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests():
        raise RuntimeError("root required for isolation")
    if os.name == "posix" and os.geteuid() == 0:
        for arg in args:
            _grant(arg)
        return [*_SETPRIV, *args]
    return args


def _run(data: Path, out: Path) -> None:
    out.parent.chmod(0o777)
    out.mkdir(mode=0o777)
    for name in REPORTS:
        (out / name).write_text('{"stale":true}\n')
        (out / name).chmod(0o666)
    process = subprocess.Popen(
        _command([sys.executable, "-I", "-S", str(SCRIPT), str(data), str(out)]),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"},
    )
    try:
        stdout, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise AssertionError("submission timed out")
    assert process.returncode == 0, f"submission exited {process.returncode}: {stdout[-400:]} {stderr[-400:]}"


_SCENARIO_ACTUAL: dict[str, Path] = {}
_SCENARIO_TEMPS: dict[str, tempfile.TemporaryDirectory[str]] = {}
_SCENARIO_LOCK = threading.Lock()


def _scenario_out(scenario: str) -> Path:
    with _SCENARIO_LOCK:
        if scenario not in _SCENARIO_ACTUAL:
            temp = tempfile.TemporaryDirectory()
            _SCENARIO_TEMPS[scenario] = temp
            parent = Path(temp.name)
            parent.chmod(0o777)
            data = _write_variant(parent, scenario)
            scenario_out = parent / "out"
            _run(data, scenario_out)
            _SCENARIO_ACTUAL[scenario] = scenario_out
        return _SCENARIO_ACTUAL[scenario]


def _holds(check: Callable[[], Any]) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


def _bundle_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for name in REPORTS:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((path / name).read_bytes())
    return digest.hexdigest()


def _artifacts() -> None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size > 0
    for name in REPORTS:
        assert isinstance(json.loads((OUT / name).read_text()), dict)


def _exact_scenario(scenario: str) -> None:
    assert _bundle_hash(_scenario_out(scenario)) == _EXPECTED_BUNDLES[scenario]


def _serialization() -> None:
    for name in REPORTS:
        text = (OUT / name).read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def _safe_source() -> None:
    assert SCRIPT.is_file() and SCRIPT.stat().st_size > 0
    text = SCRIPT.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    assert "/tests" not in lowered and "rewardkit" not in lowered and "judge.toml" not in lowered
    forbidden = {"requests", "urllib", "socket", "pandas", "numpy"}
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            assert not ({name.name.split(".")[0] for name in node.names} & forbidden)
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden


def _determinism() -> None:
    with tempfile.TemporaryDirectory() as td:
        parent = Path(td); parent.chmod(0o777)
        data = _write_variant(parent, "revision_cells")
        before = {path.name: _hash(path) for path in data.iterdir()}
        first, second = parent / "first", parent / "second"
        _run(data, first); _run(data, second)
        assert before == {path.name: _hash(path) for path in data.iterdir()}
        assert {name: (first / name).read_bytes() for name in REPORTS} == {name: (second / name).read_bytes() for name in REPORTS}


def _source_contains(markers: tuple[str, ...], count: int = 1) -> None:
    text = SCRIPT.read_text(encoding="utf-8", errors="replace")
    assert sum(marker in text for marker in markers) >= count


@criterion(description="The reusable program and all nine JSON reports exist and parse.")
def artifact_set(workspace: Path) -> bool: return _holds(_artifacts)

@criterion(description="A fresh equal-rank cells-order revision scenario produces all nine exact reports.")
def scenario_revision_cells(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("revision_cells"))

@criterion(description="A fresh equal-rank scalar-conflict revision scenario produces all nine exact reports.")
def scenario_revision_scalar(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("revision_scalar"))

@criterion(description="A fresh prefix-independent primary activation scenario produces all nine exact reports.")
def scenario_activation_identifier(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("activation_identifier"))

@criterion(description="A fresh half-open adjacent-grant boundary scenario produces all nine exact reports.")
def scenario_half_open_boundary(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("half_open_boundary"))

@criterion(description="A fresh guard-adjusted abutting-band scenario produces all nine exact reports.")
def scenario_guard_abutment(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("guard_abutment"))

@criterion(description="A fresh signed largest-remainder tie scenario produces all nine exact reports.")
def scenario_correction_tie(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("correction_tie"))

@criterion(description="A fresh exact-half monetary rounding scenario produces all nine exact reports.")
def scenario_half_up_midpoint(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("half_up_midpoint"))

@criterion(description="A fresh multi-atom exclusion-span scenario produces all nine exact reports.")
def scenario_exclusion_span(workspace: Path) -> bool: return _holds(lambda: _exact_scenario("exclusion_span"))

@criterion(description="All JSON uses sorted-key two-space serialization with trailing newlines.")
def canonical_serialization(workspace: Path) -> bool: return _holds(_serialization)

@criterion(description="The submission is nonempty, local, standard-library code that does not inspect graders.")
def local_safe_source(workspace: Path) -> bool: return _holds(_safe_source)

@criterion(description="Fresh runs are deterministic and do not mutate inputs.")
def deterministic_no_mutation(workspace: Path) -> bool: return _holds(_determinism)

@criterion(description="Detects hardcoded visible identifiers, values, or report digests.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool: return _holds(lambda: _source_contains(("LIC-A", "P-ALPHA", "d3f52a656b", "3550500", "8301742261"), 3))

@criterion(description="Detects attempts to inspect verifier or reward files.")
def negative_reads_verifier(workspace: Path) -> bool: return _holds(lambda: _source_contains(("/tests", "rewardkit", "judge.toml", "test_output")))

@criterion(description="Detects external dependencies, network access, or subprocess delegation.")
def negative_external_or_subprocess(workspace: Path) -> bool: return _holds(lambda: _source_contains(("requests", "urllib", "socket", "pandas", "numpy", "subprocess")))

criteria.artifact_set(weight=1)
criteria.scenario_revision_cells(weight=5)
criteria.scenario_revision_scalar(weight=5)
criteria.scenario_activation_identifier(weight=5)
criteria.scenario_half_open_boundary(weight=5)
criteria.scenario_guard_abutment(weight=5)
criteria.scenario_correction_tie(weight=5)
criteria.scenario_half_up_midpoint(weight=5)
criteria.scenario_exclusion_span(weight=5)
criteria.canonical_serialization(weight=3)
criteria.local_safe_source(weight=3)
criteria.deterministic_no_mutation(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_verifier(weight=-5)
criteria.negative_external_or_subprocess(weight=-3)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/spectrum-corpus")
    _write_corpus(target, True)
    print(target / "data")
