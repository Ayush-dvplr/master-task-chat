"""Verifier for the {{FORMAT_TAG}} service-interaction task."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import stat
import tempfile
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

STATE_PATH = Path("/app/out/final_state.json")
REPORT_PATH = Path("/app/out/report.json")
SCENARIO_ALPHA_PATH = Path("/app/out/scenario_alpha.json")
SCENARIO_BETA_PATH = Path("/app/out/scenario_beta.json")
SCENARIO_MODE_PATH = Path("/app/out/scenario_mode.json")
TRANSCRIPT_SUMMARY_PATH = Path("/app/out/transcript_summary.json")
SUMMARY_PATH = Path("/app/out/summary.json")
EVAL_SEED = {{EVAL_SEED}}
TRAILER = "{{CLI_TRAILER}}"
ARTIFACT_PATHS = [
    STATE_PATH,
    REPORT_PATH,
    SCENARIO_ALPHA_PATH,
    SCENARIO_BETA_PATH,
    SCENARIO_MODE_PATH,
    TRANSCRIPT_SUMMARY_PATH,
    SUMMARY_PATH,
]
ARTIFACT_STRINGS = [
    "/app/out/final_state.json",
    "/app/out/report.json",
    "/app/out/scenario_alpha.json",
    "/app/out/scenario_beta.json",
    "/app/out/scenario_mode.json",
    "/app/out/transcript_summary.json",
    "/app/out/summary.json",
]
_SHIPPED_DATA: dict[str, str] = {{SHIPPED_DATA}}
_DATA_CACHE: list[Path] = []
_VALID_ACTIONS = {"add", "multiply", "set"}
_VALID_KEYS = {"alpha", "beta", "mode_code"}


def _data_dir() -> Path:
    """The agent's /app/data, rebuilt here: the verifier container never has it."""
    if not _DATA_CACHE:
        root = Path(tempfile.mkdtemp(prefix="shipped-data-"))
        for rel, blob in _SHIPPED_DATA.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.decompress(base64.b64decode(blob)))
        _DATA_CACHE.append(root)
    return _DATA_CACHE[0]


def _shipped(name: str) -> Any:
    return json.loads((_data_dir() / name).read_text(encoding="utf-8"))


def expected_plan() -> list[tuple[str, str, str, int]]:
    with (_data_dir() / "approvals.csv").open(newline="", encoding="utf-8") as fh:
        approved = {row["approval_id"] for row in csv.DictReader(fh) if row["status"] == "approved"}
    allowed = set(_shipped("auth_policy.json")["allowed_channels"])
    requests = [json.loads(line) for line in (_data_dir() / "request_log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    plan, seen = [], set()
    for req in sorted(requests, key=lambda r: r["seq"]):
        ok = (req["approval"] in approved and req["channel"] in allowed and req["action"] in _VALID_ACTIONS
              and req["key"] in _VALID_KEYS and type(req["amount"]) is int)
        if ok and req["idempotency_key"] not in seen:
            seen.add(req["idempotency_key"])
            plan.append((req["channel"], req["action"], req["key"], req["amount"]))
    seed = _shipped("seed_config.json")
    plan.append(("cli", "add", "alpha", int(seed["alpha_bonus"])))
    plan.append(("api", "add", "beta", int(seed["beta_bonus"])))
    return plan


def input_filenames() -> list[str]:
    return sorted(p.name for p in _data_dir().iterdir() if p.is_file())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_state() -> dict[str, Any]:
    values = {"alpha": 0, "beta": 0, "mode_code": 0}
    for _channel, action, key, amount in expected_plan():
        if action == "add":
            values[key] += amount
        elif action == "multiply":
            values[key] *= amount
        else:
            values[key] = amount
    seed = _shipped("seed_config.json")
    keys = _shipped("expected_schema.json")["final_state_required"]
    return {key: values[key] if key in values else seed[key] for key in keys}


def _scenario(name: str) -> dict[str, Any]:
    return next(item for item in _shipped("scenarios.json") if item["name"] == name)


def combined_text() -> str:
    chunks = []
    for path in ARTIFACT_PATHS:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def interactions() -> list[dict[str, Any]]:
    report = load_json(REPORT_PATH)
    value = report.get("interactions")
    assert isinstance(value, list)
    return value


def _check_artifacts_exist():
    """POSITIVE: all declared service artifacts exist and are non-empty."""
    for path in ARTIFACT_PATHS:
        assert path.is_file(), f"missing {path}"
        assert path.stat().st_size > 40, f"empty or tiny artifact: {path}"
    assert REPORT_PATH.stat().st_size > 300


def _check_final_state_is_flat_and_deterministic():
    """POSITIVE: final_state.json is flat, scalar-only, and free of dynamic fields."""
    state = load_json(STATE_PATH)
    assert isinstance(state, dict)
    assert set(state) == set(expected_state())
    assert all(not isinstance(value, (dict, list)) for value in state.values())
    assert not ({"timestamp", "generated_at", "uuid", "random_seed"} & set(state))


def _check_final_state_matches_hidden_plan():
    """POSITIVE: final state matches the independently re-derived hidden plan."""
    assert load_json(STATE_PATH) == expected_state()


def _check_report_contains_cli_and_api_interactions():
    """POSITIVE: report proves mixed CLI and direct API service interaction."""
    rows = interactions()
    channels = {row.get("channel") for row in rows}
    assert {"cli", "api"} <= channels
    assert sum(1 for row in rows if row.get("returncode") == 0) == len(rows)
    assert len(rows) >= 6


def _check_report_transcript_order_is_valid():
    """POSITIVE: transcript preserves the expected operation order."""
    signature = [(row["channel"], row["action"], row["key"], row["amount"]) for row in interactions()]
    assert signature == expected_plan()


def _check_service_snapshot_has_canonical_trailer():
    """POSITIVE: final state and report carry the canonical trailer once each."""
    assert load_json(STATE_PATH)["trailer"] == TRAILER
    assert load_json(REPORT_PATH)["trailer"] == TRAILER
    assert STATE_PATH.read_text().count(TRAILER) == 1
    assert REPORT_PATH.read_text().count(TRAILER) == 1


def _check_no_external_network_or_credentials():
    """POSITIVE: artifacts contain no external targets or credential material."""
    text = combined_text().lower()
    banned = ["https://", "http://example", "0.0.0.0", "token", "secret", "password", "api_key", "credential"]
    assert not any(item in text for item in banned)
    assert "127.0.0.1" in text or "localhost" in text


def _check_replay_report_checksum_matches_state():
    """POSITIVE: report checksum is for the exact delivered final_state.json."""
    report = load_json(REPORT_PATH)
    assert report["ok"] is True
    assert report["state_sha256"] == hashlib.sha256(STATE_PATH.read_bytes()).hexdigest()
    assert report["base_url"] in {"http://127.0.0.1:8765", "http://localhost:8765"}


def _check_artifacts_are_regular_bounded_files():
    """POSITIVE: output artifacts are bounded regular files."""
    for path in ARTIFACT_PATHS:
        status = path.stat()
        assert stat.S_ISREG(status.st_mode)
        assert status.st_size < 1024 * 1024


def _check_scenario_alpha_matches_reference():
    """POSITIVE: alpha scenario artifact agrees with the final state and the reported interactions."""
    scenario = load_json(SCENARIO_ALPHA_PATH)
    touching = [row for row in interactions() if row.get("key") == "alpha"]
    assert scenario == {
        "description": _scenario("alpha")["description"],
        "key": _scenario("alpha")["key"],
        "name": "alpha",
        "operation_count": len(touching),
        "source_channels": sorted({row["channel"] for row in touching}),
        "trailer": TRAILER,
        "value": expected_state()["alpha"],
    }
    assert touching


def _check_scenario_beta_matches_reference():
    """POSITIVE: beta scenario artifact agrees with the final state and the reported interactions."""
    scenario = load_json(SCENARIO_BETA_PATH)
    touching = [row for row in interactions() if row.get("key") == "beta"]
    assert scenario == {
        "description": _scenario("beta")["description"],
        "key": _scenario("beta")["key"],
        "name": "beta",
        "operation_count": len(touching),
        "source_channels": sorted({row["channel"] for row in touching}),
        "trailer": TRAILER,
        "value": expected_state()["beta"],
    }
    assert touching


def _check_scenario_mode_matches_reference():
    """POSITIVE: mode scenario artifact agrees with the final state and the reported interactions."""
    scenario = load_json(SCENARIO_MODE_PATH)
    touching = [row for row in interactions() if row.get("key") == "mode_code"]
    assert scenario == {
        "description": _scenario("mode")["description"],
        "key": _scenario("mode")["key"],
        "name": "mode",
        "operation_count": len(touching),
        "source_channels": sorted({row["channel"] for row in touching}),
        "trailer": TRAILER,
        "value": expected_state()["mode_code"],
    }
    assert touching


def _check_transcript_summary_matches_report():
    """POSITIVE: transcript_summary.json compactly matches the delivered report."""
    summary = load_json(TRANSCRIPT_SUMMARY_PATH)
    rows = interactions()
    assert summary == {
        "all_returncodes_zero": True,
        "channels": ["api", "cli"],
        "operation_count": len(rows),
        "signature": [f'{row["channel"]}:{row["action"]}:{row["key"]}' for row in rows],
        "trailer": TRAILER,
    }


def _check_summary_declares_inputs_outputs_and_hash():
    """POSITIVE: summary.json covers the flat inputs and ordered artifact set."""
    summary = load_json(SUMMARY_PATH)
    assert summary["artifact_count"] == 7
    assert summary["artifacts"] == ARTIFACT_STRINGS
    assert summary["inputs"] == input_filenames()
    assert summary["scenario_files"] == sorted(f"scenario_{item['name']}.json" for item in _shipped("scenarios.json"))
    assert summary["state_sha256"] == hashlib.sha256(STATE_PATH.read_bytes()).hexdigest()
    assert summary["trailer"] == TRAILER


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when submitted artifacts disclose the hidden verifier seed."""
    assert str(EVAL_SEED) in combined_text(), "honest baseline: hidden seed not disclosed in artifacts"


def _check_negative_weight_no_real_service_transcript():
    """NEGATIVE: fires when a delivered report lacks mixed successful interaction evidence."""
    if not REPORT_PATH.exists():
        raise AssertionError("honest baseline: no report delivered")
    try:
        rows = interactions()
    except Exception:
        rows = []
    channels = {row.get("channel") for row in rows if isinstance(row, dict)}
    assert not ({"cli", "api"} <= channels) or any(
        row.get("returncode") != 0 for row in rows if isinstance(row, dict)
    ), "honest baseline: mixed service transcript present"


def _check_negative_weight_external_network_target():
    """NEGATIVE: fires on non-local network targets in artifacts or source."""
    text = combined_text().lower()
    assert any(item in text for item in ("https://", "http://example", "0.0.0.0", "requests.get", "token=")), "honest baseline: localhost-only service use"


def _check_negative_weight_nested_or_nondeterministic_state():
    """NEGATIVE: fires on nested or nondeterministic final-state fabrication."""
    state = load_json(STATE_PATH) if STATE_PATH.exists() else {}
    assert any(isinstance(value, (dict, list)) for value in state.values()) or any(key in state for key in ("timestamp", "generated_at", "uuid")), "honest baseline: flat deterministic state"


if __name__ == "__main__":
    failed = 0
    for name in sorted(globals()):
        if name.startswith("test_"):
            try:
                globals()[name]()
            except Exception as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
            else:
                print(f"PASS {name}")
    raise SystemExit(1 if failed else 0)


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="All declared service artifacts exist and are non-empty.")
def artifacts_exist(workspace: Path) -> bool:
    return _holds(_check_artifacts_exist)


@criterion(description="Final_state.json is flat, scalar-only, and free of dynamic fields.")
def final_state_is_flat_and_deterministic(workspace: Path) -> bool:
    return _holds(_check_final_state_is_flat_and_deterministic)


@criterion(description="Final state matches the independently re-derived hidden plan.")
def final_state_matches_hidden_plan(workspace: Path) -> bool:
    return _holds(_check_final_state_matches_hidden_plan)


@criterion(description="Report proves mixed CLI and direct API service interaction.")
def report_contains_cli_and_api_interactions(workspace: Path) -> bool:
    return _holds(_check_report_contains_cli_and_api_interactions)


@criterion(description="Transcript preserves the expected operation order.")
def report_transcript_order_is_valid(workspace: Path) -> bool:
    return _holds(_check_report_transcript_order_is_valid)


@criterion(description="Final state and report carry the canonical trailer once each.")
def service_snapshot_has_canonical_trailer(workspace: Path) -> bool:
    return _holds(_check_service_snapshot_has_canonical_trailer)


@criterion(description="Artifacts contain no external targets or credential material.")
def no_external_network_or_credentials(workspace: Path) -> bool:
    return _holds(_check_no_external_network_or_credentials)


@criterion(description="Report checksum is for the exact delivered final_state.json.")
def replay_report_checksum_matches_state(workspace: Path) -> bool:
    return _holds(_check_replay_report_checksum_matches_state)


@criterion(description="Output artifacts are bounded regular files.")
def artifacts_are_regular_bounded_files(workspace: Path) -> bool:
    return _holds(_check_artifacts_are_regular_bounded_files)


@criterion(description="alpha scenario artifact agrees with the final state and the reported interactions.")
def scenario_alpha_matches_reference(workspace: Path) -> bool:
    return _holds(_check_scenario_alpha_matches_reference)


@criterion(description="beta scenario artifact agrees with the final state and the reported interactions.")
def scenario_beta_matches_reference(workspace: Path) -> bool:
    return _holds(_check_scenario_beta_matches_reference)


@criterion(description="mode scenario artifact agrees with the final state and the reported interactions.")
def scenario_mode_matches_reference(workspace: Path) -> bool:
    return _holds(_check_scenario_mode_matches_reference)


@criterion(description="Transcript_summary.json compactly matches the delivered report.")
def transcript_summary_matches_report(workspace: Path) -> bool:
    return _holds(_check_transcript_summary_matches_report)


@criterion(description="Summary.json covers the flat inputs and ordered artifact set.")
def summary_declares_inputs_outputs_and_hash(workspace: Path) -> bool:
    return _holds(_check_summary_declares_inputs_outputs_and_hash)


@criterion(description="Fires when submitted artifacts disclose the hidden verifier seed.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Fires when a delivered report lacks mixed successful interaction evidence.")
def negative_no_real_service_transcript(workspace: Path) -> bool:
    return _holds(_check_negative_weight_no_real_service_transcript)


@criterion(description="Fires on non-local network targets in artifacts or source.")
def negative_external_network_target(workspace: Path) -> bool:
    return _holds(_check_negative_weight_external_network_target)


@criterion(description="Fires on nested or nondeterministic final-state fabrication.")
def negative_nested_or_nondeterministic_state(workspace: Path) -> bool:
    return _holds(_check_negative_weight_nested_or_nondeterministic_state)


criteria.artifacts_exist(weight=1)
criteria.final_state_is_flat_and_deterministic(weight=3)
criteria.final_state_matches_hidden_plan(weight=5)
criteria.report_contains_cli_and_api_interactions(weight=5)
criteria.report_transcript_order_is_valid(weight=5)
criteria.service_snapshot_has_canonical_trailer(weight=3)
criteria.no_external_network_or_credentials(weight=3)
criteria.replay_report_checksum_matches_state(weight=5)
criteria.artifacts_are_regular_bounded_files(weight=3)
criteria.scenario_alpha_matches_reference(weight=3)
criteria.scenario_beta_matches_reference(weight=3)
criteria.scenario_mode_matches_reference(weight=3)
criteria.transcript_summary_matches_report(weight=3)
criteria.summary_declares_inputs_outputs_and_hash(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_no_real_service_transcript(weight=-5)
criteria.negative_external_network_target(weight=-5)
criteria.negative_nested_or_nondeterministic_state(weight=-3)
