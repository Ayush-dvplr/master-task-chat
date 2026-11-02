"""Verifier for the Hollowbrand relay promotion gate.

Ground truth is pinned in _TRUTH_BLOB. The relay reducer that shipped with the
environment is pinned in _CORE_BLOB so this container can replay operation
sequences and probe delivered seating with batches the agent never saw.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import math
import stat
import tempfile
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

OUT_DIR = Path("/app/out")
STATE_PATH = OUT_DIR / "final_state.json"
REPORT_PATH = OUT_DIR / "report.json"
SCENARIO_ALPHA_PATH = OUT_DIR / "scenario_alpha.json"
SCENARIO_BETA_PATH = OUT_DIR / "scenario_beta.json"
SCENARIO_MODE_PATH = OUT_DIR / "scenario_mode.json"
TRANSCRIPT_SUMMARY_PATH = OUT_DIR / "transcript_summary.json"
SUMMARY_PATH = OUT_DIR / "summary.json"
ARTIFACT_PATHS = [
    STATE_PATH,
    REPORT_PATH,
    SCENARIO_ALPHA_PATH,
    SCENARIO_BETA_PATH,
    SCENARIO_MODE_PATH,
    TRANSCRIPT_SUMMARY_PATH,
    SUMMARY_PATH,
]
LADDER = ("edge", "canary", "staging", "stable")
BATCH_LIMIT = 10
PROBE_REVISION = "9:9.9.9-99"
REGISTRY = (
    "ok", "alias_unresolved", "channel_not_adjacent", "revision_regression",
    "withdrawn_revision", "quarantine_floor", "embargo_active", "embargo_pending",
    "attestation_failed", "risk_tier_blocked", "channel_cooldown", "freeze_window",
    "recurring_hold", "missing_dependency", "cycle_unresolved", "budget_exhausted",
    "carry_forward_exhausted",
)
REJECTION_FAMILY = frozenset([
    "alias_unresolved", "channel_not_adjacent", "revision_regression",
    "withdrawn_revision", "attestation_failed", "risk_tier_blocked",
])
TEMPORAL_FAMILY = frozenset([
    "quarantine_floor", "embargo_active", "embargo_pending", "channel_cooldown",
    "freeze_window", "recurring_hold",
])
CAPACITY_FAMILY = frozenset([
    "missing_dependency", "cycle_unresolved", "budget_exhausted",
    "carry_forward_exhausted",
])
TOP_LEVEL_KEYS = {
    "final_state.json": frozenset(["api_version", "op_seq", "sealed", "channels"]),
    "report.json": frozenset([
        "cycle_id", "decision_instant", "audit_count", "decisions",
        "reason_code_counts", "escalations", "unresolved", "admission_order",
    ]),
    "summary.json": frozenset([
        "cycle_id", "inputs_seen", "audit_count", "admitted_total", "deferred_total",
        "rejected_total", "withdrawn_excluded", "escalated_total", "admission_rate",
        "admitted_by_channel", "coverage_share_pct", "repeat_deferral_count",
        "closure_passes", "rollback_holds", "dependency_digest",
    ]),
    "transcript_summary.json": frozenset([
        "actor", "endpoint", "batch_limit", "calls", "replayed_calls", "aborted_calls",
        "ops_submitted", "ops_accepted", "ops_rejected", "seal_ops", "final_op_seq",
        "idempotency_keys",
    ]),
    "scenario_alpha.json": frozenset([
        "scenario", "decision_instant", "audit_count", "admitted_total",
        "deferred_total", "rejected_total", "reason_code_counts", "admitted_digest",
    ]),
    "scenario_beta.json": frozenset([
        "scenario", "decision_instant", "audit_count", "admitted_total",
        "deferred_total", "rejected_total", "reason_code_counts", "admitted_digest",
    ]),
    "scenario_mode.json": frozenset(["cycle_id", "modes", "delta"]),
}
DYNAMIC_KEYS = frozenset([
    "timestamp", "generated_at", "created_at", "uuid", "hostname", "elapsed",
    "random_seed", "run_id", "wall_clock",
])
_TRUTH_BLOB = "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"
_CORE_BLOB = "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"
_TRUTH_CACHE: list[dict[str, Any]] = []
_CORE_CACHE: list[Any] = []


def _truth() -> dict[str, Any]:
    if not _TRUTH_CACHE:
        raw = zlib.decompress(base64.b64decode(_TRUTH_BLOB)).decode("utf-8")
        _TRUTH_CACHE.append(json.loads(raw))
    return _TRUTH_CACHE[0]


def _core() -> Any:
    """The shipped reducer, rebuilt here so delivered seating can be probed."""
    if not _CORE_CACHE:
        root = Path(tempfile.mkdtemp(prefix="relay-core-"))
        target = root / "relay_core.py"
        target.write_bytes(zlib.decompress(base64.b64decode(_CORE_BLOB)))
        spec = importlib.util.spec_from_file_location("pinned_relay_core", str(target))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _CORE_CACHE.append(module)
    return _CORE_CACHE[0]


def _load(path: Path) -> Any:
    try:
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _delivered_rows() -> list[dict[str, Any]]:
    report = _load(REPORT_PATH)
    if not isinstance(report, dict):
        return []
    rows = report.get("decisions")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _delivered_codes() -> dict[str, str]:
    out: dict[str, str] = {}
    for row in _delivered_rows():
        key = row.get("request_id")
        code = row.get("reason_code")
        if isinstance(key, str) and isinstance(code, str):
            out[key] = code
    return out


def _truth_codes() -> dict[str, str]:
    return dict((row[0], row[7]) for row in _truth()["decisions"])


def _family_holds(family: frozenset) -> bool:
    truth = _truth_codes()
    delivered = _delivered_codes()
    if len(delivered) != len(truth):
        return False
    for key, code in truth.items():
        if code in family and delivered.get(key) != code:
            return False
    for key, code in delivered.items():
        if code in family and truth.get(key) != code:
            return False
    return True


def _bump(revision: str) -> str:
    core, build = revision.rsplit("-", 1)
    return "%s-%d" % (core, int(build) + 1)


def _probe_passes() -> list[list[dict[str, Any]]]:
    """Operation batteries built from pinned seating, never shown to the agent."""
    channels = _truth()["state"]["channels"]
    units = sorted(set(unit for channel in LADDER for unit in channels.get(channel, {})))
    passes: list[list[dict[str, Any]]] = []
    for channel in LADDER:
        passes.append([
            {"op": "promote", "unit_key": unit, "revision": PROBE_REVISION,
             "target_channel": channel, "requires": []}
            for unit in units
        ])
    same: list[dict[str, Any]] = []
    higher: list[dict[str, Any]] = []
    for unit in units:
        head = None
        for channel in LADDER:
            if unit in channels.get(channel, {}):
                head = channel
        revision = channels[head][unit]["revision"]
        same.append({"op": "promote", "unit_key": unit, "revision": revision,
                     "target_channel": head, "requires": []})
        higher.append({"op": "promote", "unit_key": unit, "revision": _bump(revision),
                       "target_channel": head, "requires": []})
    passes.append(same)
    passes.append(higher)
    return passes


def _run_passes(state: dict[str, Any], reverse: bool) -> dict[str, str]:
    core = _core()
    verdicts: dict[str, str] = {}
    for index, ops in enumerate(_probe_passes()):
        working = copy.deepcopy(state)
        working["sealed"] = []
        seen: dict[str, Any] = {}
        transcript: list[dict[str, Any]] = []
        # One refused op aborts a whole call, so each probe travels on its own call
        # and every probe therefore comes back with a verdict of its own.
        ordered = list(reversed(ops)) if reverse else list(ops)
        for position, op in enumerate(ordered):
            body = {"ops": [op], "actor": "relay-gate",
                    "idempotency_key": "probe-%d-%d" % (index, position)}
            answer = core.apply_batch(working, transcript, seen, body, 1, "relay-gate")
            for result in answer.get("results") or []:
                label = "%d|%s" % (index, op["unit_key"])
                verdicts[label] = "%s:%s" % (result.get("accepted"), result.get("reason"))
    return verdicts


def _ops_from_order(order: list[str]) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    for item in order:
        unit, revision, channel = item.split("|")
        ops.append({"op": "promote", "unit_key": unit, "revision": revision,
                    "target_channel": channel, "requires": []})
    return ops


def _combined_text() -> str:
    chunks = []
    for path in ARTIFACT_PATHS:
        try:
            if path.is_file():
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    return "\n".join(chunks)


def _keys_anywhere(node: Any, found: set) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(str(key).lower())
            _keys_anywhere(value, found)
    elif isinstance(node, list):
        for value in node:
            _keys_anywhere(value, found)


@criterion(description="The governing request roster is complete and partitioned into the three decision classes.")
def decision_roster_is_the_governing_request_set(workspace: Path) -> bool:
    try:
        report = _load(REPORT_PATH)
        rows = _delivered_rows()
        if not isinstance(report, dict) or len(rows) != len(report.get("decisions") or []):
            return False
        truth = _truth()
        ids = [row.get("request_id") for row in rows]
        if len(set(ids)) != len(ids):
            return False
        if sorted(str(item) for item in ids) != sorted(row[0] for row in truth["decisions"]):
            return False
        if report.get("audit_count") != truth["audit_count"]:
            return False
        if report.get("cycle_id") != truth["cycle_id"]:
            return False
        if report.get("decision_instant") != truth["decision_instant"]:
            return False
        classes = {"admitted": 0, "deferred": 0, "rejected": 0}
        for row in rows:
            value = row.get("decision")
            if value not in classes:
                return False
            classes[value] += 1
        if sum(classes.values()) != truth["audit_count"]:
            return False
        expected = {"admitted": 0, "deferred": 0, "rejected": 0}
        for row in truth["decisions"]:
            expected[row[6]] += 1
        return classes == expected
    except Exception:
        return False


@criterion(description="Every reason code settled before capacity matches the adjudication.")
def pre_capacity_reason_codes_are_exact(workspace: Path) -> bool:
    try:
        return _family_holds(REJECTION_FAMILY | TEMPORAL_FAMILY)
    except Exception:
        return False


@criterion(description="Every dependency and capacity reason code matches the adjudication.")
def capacity_family_reason_codes_are_exact(workspace: Path) -> bool:
    try:
        return _family_holds(CAPACITY_FAMILY)
    except Exception:
        return False


@criterion(description="The admitted sequence matches the cycle admission order.")
def admitted_sequence_matches_the_cycle(workspace: Path) -> bool:
    try:
        report = _load(REPORT_PATH)
        truth = _truth()
        if not isinstance(report, dict):
            return False
        order = report.get("admission_order")
        if order != truth["admission_order"]:
            return False
        admitted = []
        for row in _delivered_rows():
            if row.get("decision") == "admitted":
                admitted.append("%s|%s|%s" % (row.get("unit_key"), row.get("revision"),
                                              row.get("target_channel")))
        return sorted(admitted) == sorted(truth["admission_order"])
    except Exception:
        return False


@criterion(description="Seats moved this cycle carry the right revisions in the right channels.")
def promoted_seating_matches_the_cycle(workspace: Path) -> bool:
    try:
        state = _load(STATE_PATH)
        truth = _truth()["state"]
        if not isinstance(state, dict):
            return False
        for channel in LADDER:
            held = truth["channels"].get(channel, {})
            mine = state.get("channels", {}).get(channel)
            if not isinstance(mine, dict):
                return False
            want = dict((unit, entry["revision"]) for unit, entry in held.items()
                        if entry["seq"] > 0)
            got = {}
            for unit, entry in mine.items():
                if isinstance(entry, dict) and isinstance(entry.get("seq"), int) and entry["seq"] > 0:
                    got[unit] = entry.get("revision")
            if want != got:
                return False
        return True
    except Exception:
        return False


@criterion(description="Inherited seating answers unseen probe batteries the same way the reference seating does.")
def inherited_seating_answers_unseen_probes(workspace: Path) -> bool:
    try:
        state = _load(STATE_PATH)
        if not isinstance(state, dict) or not isinstance(state.get("channels"), dict):
            return False
        reference = _run_passes(_truth()["state"], False)
        mine = _run_passes(state, False)
        permuted = _run_passes(state, True)
        return bool(reference) and mine == reference and permuted == reference
    except Exception:
        return False


@criterion(description="The strict and delegated comparison matches the cycle.")
def mode_comparison_matches_the_cycle(workspace: Path) -> bool:
    try:
        return _load(SCENARIO_MODE_PATH) == _truth()["mode"]
    except Exception:
        return False


@criterion(description="Each ladder channel refuses a fresh promote probe once the cycle is closed.")
def every_channel_refuses_a_probe_after_the_close(workspace: Path) -> bool:
    try:
        state = _load(STATE_PATH)
        if not isinstance(state, dict):
            return False
        core = _core()
        working = copy.deepcopy(state)
        seen: dict[str, Any] = {}
        transcript: list[dict[str, Any]] = []
        reasons = []
        for channel in LADDER:
            op = {"op": "promote", "unit_key": "hbprobe/shim",
                  "revision": PROBE_REVISION, "target_channel": channel,
                  "requires": []}
            answer = core.apply_batch(working, transcript, seen,
                                      {"ops": [op], "actor": "relay-gate",
                                       "idempotency_key": "seal-probe-%s" % channel},
                                      1, "relay-gate")
            results = answer.get("results") or []
            if len(results) != 1:
                return False
            reasons.append(results[0].get("reason"))
        return all(reason == "channel_sealed" for reason in reasons)
    except Exception:
        return False


@criterion(description="The cover held for rollback and the depth of the revalidation match the cycle.")
def rollback_cover_and_closure_depth_are_exact(workspace: Path) -> bool:
    try:
        summary = _load(SUMMARY_PATH)
        truth = _truth()["summary"]
        if not isinstance(summary, dict):
            return False
        for field in ("closure_passes", "rollback_holds"):
            value = summary.get(field)
            if not isinstance(value, int) or isinstance(value, bool):
                return False
            if value != truth[field]:
                return False
        return True
    except Exception:
        return False


@criterion(description="Each seat opened this cycle carries the sequence number its draw earned.")
def seat_sequence_numbers_match_the_draw(workspace: Path) -> bool:
    try:
        state = _load(STATE_PATH)
        truth = _truth()["state"]
        if not isinstance(state, dict):
            return False
        if state.get("op_seq") != truth["op_seq"]:
            return False
        for channel in LADDER:
            held = truth["channels"].get(channel, {})
            mine = state.get("channels", {}).get(channel)
            if not isinstance(mine, dict):
                return False
            want = dict((unit, entry["seq"]) for unit, entry in held.items()
                        if entry["seq"] > 0)
            got = {}
            for unit, entry in mine.items():
                if not isinstance(entry, dict):
                    return False
                seq = entry.get("seq")
                if isinstance(seq, int) and not isinstance(seq, bool) and seq > 0:
                    got[unit] = seq
            if want != got:
                return False
        return True
    except Exception:
        return False


@criterion(description="Summary totals reconcile with the decision roster.")
def summary_totals_reconcile_with_the_report(workspace: Path) -> bool:
    try:
        summary = _load(SUMMARY_PATH)
        truth = _truth()["summary"]
        rows = _delivered_rows()
        if not isinstance(summary, dict) or not rows:
            return False
        counts = {"admitted": 0, "deferred": 0, "rejected": 0}
        for row in rows:
            if row.get("decision") in counts:
                counts[row["decision"]] += 1
        fields = ("cycle_id", "inputs_seen", "audit_count", "admitted_total",
                  "deferred_total", "rejected_total", "withdrawn_excluded",
                  "escalated_total")
        for field in fields:
            if summary.get(field) != truth[field]:
                return False
        if summary.get("admitted_total") != counts["admitted"]:
            return False
        if summary.get("deferred_total") != counts["deferred"]:
            return False
        return summary.get("rejected_total") == counts["rejected"]
    except Exception:
        return False


@criterion(description="The admission rate is exact on the documented denominator.")
def admission_rate_is_exact(workspace: Path) -> bool:
    try:
        summary = _load(SUMMARY_PATH)
        truth = _truth()["summary"]
        if not isinstance(summary, dict):
            return False
        rate = summary.get("admission_rate")
        if not isinstance(rate, (int, float)) or isinstance(rate, bool):
            return False
        if int(round(float(rate) * 10000)) != int(round(truth["admission_rate"] * 10000)):
            return False
        admitted = int(summary.get("admitted_total"))
        audit = int(summary.get("audit_count"))
        withheld = int(summary.get("withdrawn_excluded"))
        denominator = audit - withheld
        if denominator <= 0:
            return False
        scaled = (admitted * 20000 + denominator) // (2 * denominator)
        return scaled == int(round(truth["admission_rate"] * 10000))
    except Exception:
        return False


@criterion(description="Coverage shares follow the largest remainder rule and agree with seating.")
def coverage_shares_follow_the_largest_remainder(workspace: Path) -> bool:
    try:
        summary = _load(SUMMARY_PATH)
        state = _load(STATE_PATH)
        truth = _truth()["summary"]
        if not isinstance(summary, dict) or not isinstance(state, dict):
            return False
        shares = summary.get("coverage_share_pct")
        if not isinstance(shares, dict) or set(shares) != set(LADDER):
            return False
        for channel in LADDER:
            value = shares[channel]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            if int(round(float(value) * 100)) != int(round(truth["coverage_share_pct"][channel] * 100)):
                return False
        if summary.get("admitted_by_channel") != truth["admitted_by_channel"]:
            return False
        total = sum(int(round(float(shares[channel]) * 100)) for channel in LADDER)
        if total not in (0, 10000):
            return False
        for channel in LADDER:
            held = state.get("channels", {}).get(channel)
            if not isinstance(held, dict):
                return False
            moved = sum(1 for entry in held.values()
                        if isinstance(entry, dict) and isinstance(entry.get("seq"), int)
                        and entry["seq"] > 0)
            if moved != summary["admitted_by_channel"].get(channel):
                return False
        return True
    except Exception:
        return False


@criterion(description="The repeat deferral count and the dependency digest are exact.")
def repeat_deferral_and_digest_are_exact(workspace: Path) -> bool:
    try:
        summary = _load(SUMMARY_PATH)
        truth = _truth()["summary"]
        if not isinstance(summary, dict):
            return False
        if summary.get("repeat_deferral_count") != truth["repeat_deferral_count"]:
            return False
        digest = summary.get("dependency_digest")
        if not isinstance(digest, str) or len(digest) != 16:
            return False
        if digest != digest.lower() or any(ch not in "0123456789abcdef" for ch in digest):
            return False
        return digest == truth["dependency_digest"]
    except Exception:
        return False


@criterion(description="The alpha overlay matches the shifted decision instant.")
def alpha_scenario_matches_the_shifted_instant(workspace: Path) -> bool:
    try:
        return _load(SCENARIO_ALPHA_PATH) == _truth()["alpha"]
    except Exception:
        return False


@criterion(description="The beta overlay matches the withdrawn authority layers.")
def beta_scenario_matches_the_withdrawn_layers(workspace: Path) -> bool:
    try:
        return _load(SCENARIO_BETA_PATH) == _truth()["beta"]
    except Exception:
        return False


@criterion(description="Unresolved entries, escalations and reason code counts are exact.")
def unresolved_and_escalations_are_exact(workspace: Path) -> bool:
    try:
        report = _load(REPORT_PATH)
        truth = _truth()
        if not isinstance(report, dict):
            return False
        if report.get("unresolved") != truth["unresolved"]:
            return False
        if report.get("escalations") != truth["escalations"]:
            return False
        return report.get("reason_code_counts") == truth["reason_code_counts"]
    except Exception:
        return False


@criterion(description="Transcript accounting reconciles with the delivered state and order.")
def transcript_accounting_reconciles_with_the_state(workspace: Path) -> bool:
    try:
        transcript = _load(TRANSCRIPT_SUMMARY_PATH)
        state = _load(STATE_PATH)
        report = _load(REPORT_PATH)
        truth = _truth()["transcript"]
        if not isinstance(transcript, dict) or not isinstance(state, dict):
            return False
        if not isinstance(report, dict):
            return False
        order = report.get("admission_order") or []
        for field in ("actor", "endpoint", "batch_limit", "calls", "replayed_calls",
                      "ops_submitted", "ops_accepted", "ops_rejected", "seal_ops",
                      "aborted_calls", "final_op_seq"):
            if transcript.get(field) != truth[field]:
                return False
        keys = transcript.get("idempotency_keys")
        if not isinstance(keys, list) or len(keys) != truth["calls"]:
            return False
        if len(set(str(item) for item in keys)) != len(keys):
            return False
        if transcript["calls"] != math.ceil(len(order) / BATCH_LIMIT) + 1:
            return False
        if transcript["ops_submitted"] != len(order) + len(LADDER):
            return False
        return state.get("op_seq") == transcript["final_op_seq"]
    except Exception:
        return False


@criterion(description="All seven artifacts parse and carry the contract key sets.")
def artifacts_carry_the_contract_keys(workspace: Path) -> bool:
    try:
        for path in ARTIFACT_PATHS:
            body = _load(path)
            if not isinstance(body, dict):
                return False
            if set(body) != set(TOP_LEVEL_KEYS[path.name]):
                return False
        return True
    except Exception:
        return False


@criterion(description="All seven artifacts are bounded regular files.")
def artifacts_are_bounded_regular_files(workspace: Path) -> bool:
    try:
        for path in ARTIFACT_PATHS:
            if path.is_symlink():
                return False
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                return False
            if info.st_size < 40 or info.st_size > 4 * 1024 * 1024:
                return False
        return True
    except Exception:
        return False


@criterion(description="Fires when requests submitted outside the horizon were adjudicated.")
def negative_requests_outside_the_horizon_were_adjudicated(workspace: Path) -> bool:
    # Fires when the roster keeps requests submitted outside the cycle horizon.
    try:
        rows = _delivered_rows()
        if not rows:
            return False
        outside = set(_truth()["out_of_horizon_ids"])
        return any(row.get("request_id") in outside for row in rows)
    except Exception:
        return False


@criterion(description="Fires when superseded duplicate submissions inflated the roster.")
def negative_duplicate_request_rows_were_counted(workspace: Path) -> bool:
    # Fires when superseded duplicate submissions inflate the roster.
    try:
        report = _load(REPORT_PATH)
        rows = _delivered_rows()
        if not isinstance(report, dict) or not rows:
            return False
        ids = [row.get("request_id") for row in rows]
        if len(set(ids)) != len(ids):
            return True
        audit = report.get("audit_count")
        return isinstance(audit, int) and audit > _truth()["audit_count"]
    except Exception:
        return False


@criterion(description="Fires when a decision carries a code outside the registry.")
def negative_reason_codes_outside_the_registry(workspace: Path) -> bool:
    # Fires when a decision carries a code that the registry does not define.
    try:
        rows = _delivered_rows()
        if not rows:
            return False
        for row in rows:
            code = row.get("reason_code")
            if not isinstance(code, str) or code not in REGISTRY:
                return True
        report = _load(REPORT_PATH)
        counts = report.get("reason_code_counts") if isinstance(report, dict) else None
        if isinstance(counts, dict):
            return any(key not in REGISTRY for key in counts)
        return False
    except Exception:
        return False


@criterion(description="Fires when the state was never moved by the relay service.")
def negative_state_was_never_moved_by_the_service(workspace: Path) -> bool:
    # Fires when the report claims admissions yet no seat carries an operation sequence.
    try:
        state = _load(STATE_PATH)
        rows = _delivered_rows()
        if not isinstance(state, dict) or not rows:
            return False
        admitted = sum(1 for row in rows if row.get("decision") == "admitted")
        if admitted == 0:
            return False
        moved = 0
        for channel in LADDER:
            held = state.get("channels", {}).get(channel)
            if isinstance(held, dict):
                moved += sum(1 for entry in held.values()
                             if isinstance(entry, dict) and isinstance(entry.get("seq"), int)
                             and entry["seq"] > 0)
        return moved == 0
    except Exception:
        return False


@criterion(description="Fires when the reported calls cannot hold the reported operations.")
def negative_batch_limit_was_ignored(workspace: Path) -> bool:
    # Fires when the reported call count cannot hold the reported operations.
    try:
        transcript = _load(TRANSCRIPT_SUMMARY_PATH)
        if not isinstance(transcript, dict):
            return False
        calls = transcript.get("calls")
        submitted = transcript.get("ops_submitted")
        limit = transcript.get("batch_limit")
        if not isinstance(calls, int) or not isinstance(submitted, int):
            return False
        if not isinstance(limit, int) or limit <= 0:
            return False
        return submitted > calls * limit
    except Exception:
        return False


@criterion(description="Fires when both overlay artifacts repeat the baseline counts.")
def negative_scenarios_repeat_the_baseline_counts(workspace: Path) -> bool:
    # Fires when both overlay artifacts carry the baseline reason code counts.
    try:
        report = _load(REPORT_PATH)
        alpha = _load(SCENARIO_ALPHA_PATH)
        beta = _load(SCENARIO_BETA_PATH)
        if not isinstance(report, dict) or not isinstance(alpha, dict):
            return False
        if not isinstance(beta, dict):
            return False
        base = report.get("reason_code_counts")
        if not isinstance(base, dict):
            return False
        return alpha.get("reason_code_counts") == base and beta.get("reason_code_counts") == base
    except Exception:
        return False


@criterion(description="Fires when the stated mode delta disagrees with the stated modes.")
def negative_mode_delta_disagrees_with_its_own_modes(workspace: Path) -> bool:
    # Fires when the stated delta is not the difference of the two stated modes.
    try:
        mode = _load(SCENARIO_MODE_PATH)
        if not isinstance(mode, dict):
            return False
        modes = mode.get("modes")
        delta = mode.get("delta")
        if not isinstance(modes, dict) or not isinstance(delta, dict):
            return False
        strict = modes.get("strict")
        delegated = modes.get("delegated")
        if not isinstance(strict, dict) or not isinstance(delegated, dict):
            return False
        for field in ("admitted_total", "deferred_total", "attestation_failed"):
            left = strict.get(field)
            right = delegated.get(field)
            stated = delta.get(field)
            if not isinstance(left, int) or not isinstance(right, int):
                return False
            if stated != left - right:
                return True
        return False
    except Exception:
        return False


@criterion(description="Fires when an artifact records a clock reading or a run identifier.")
def negative_artifacts_carry_dynamic_fields(workspace: Path) -> bool:
    # Fires when an artifact records a clock reading, a host name or a run identifier.
    try:
        found: set = set()
        for path in ARTIFACT_PATHS:
            body = _load(path)
            if body is None:
                continue
            _keys_anywhere(body, found)
        if not found:
            return False
        return bool(found & DYNAMIC_KEYS)
    except Exception:
        return False


@criterion(description="Fires when the output directory holds files beyond the seven artifacts.")
def negative_extra_files_sit_in_the_output_directory(workspace: Path) -> bool:
    # Fires when the output directory holds files beyond the seven artifacts.
    try:
        if not OUT_DIR.is_dir():
            return False
        names = set(item.name for item in OUT_DIR.iterdir())
        if not names:
            return False
        return bool(names - set(path.name for path in ARTIFACT_PATHS))
    except Exception:
        return False


@criterion(description="Fires when the delivered state seats a unit the report ruled other than admitted.")
def negative_final_state_seats_a_rejected_unit(workspace: Path) -> bool:
    # Fires when a seat the cycle created contradicts its own decision row.
    try:
        state = _load(STATE_PATH)
        report = _load(REPORT_PATH)
        if not isinstance(state, dict) or not isinstance(report, dict):
            return False
        verdict: dict[tuple[str, str], str] = {}
        rows = report.get("decisions")
        if not isinstance(rows, list):
            return False
        for row in rows:
            if isinstance(row, dict):
                key = (str(row.get("unit_key")), str(row.get("target_channel")))
                verdict[key] = str(row.get("decision"))
        channels = state.get("channels")
        if not isinstance(channels, dict):
            return False
        for channel, seats in channels.items():
            if not isinstance(seats, dict):
                continue
            for unit, seat in seats.items():
                if not isinstance(seat, dict):
                    continue
                try:
                    seq = int(seat.get("seq") or 0)
                except Exception:
                    continue
                if seq <= 0:
                    continue
                ruling = verdict.get((str(unit), str(channel)))
                if ruling is not None and ruling != "admitted":
                    return True
        return False
    except Exception:
        return False


@criterion(description="Fires when the admitted totals repeat a published capacity figure in place of the settled draw.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Fires when the per channel totals are copied from the shipped budget file.
    try:
        summary = _load(SUMMARY_PATH)
        if not isinstance(summary, dict):
            return False
        offered = summary.get("admitted_by_channel")
        if not isinstance(offered, dict):
            return False
        seen: dict[str, int] = {}
        for channel in LADDER:
            try:
                seen[channel] = int(offered.get(channel))
            except Exception:
                return False
        published = (
            {"edge": 17, "canary": 30, "staging": 20, "stable": 8},
            {"edge": 14, "canary": 20, "staging": 13, "stable": 3},
            {"edge": 3, "canary": 4, "staging": 3, "stable": 2},
        )
        return seen in published
    except Exception:
        return False



criteria.decision_roster_is_the_governing_request_set(weight=5)
criteria.capacity_family_reason_codes_are_exact(weight=5)
criteria.admitted_sequence_matches_the_cycle(weight=5)
criteria.promoted_seating_matches_the_cycle(weight=5)
criteria.seat_sequence_numbers_match_the_draw(weight=5)
criteria.inherited_seating_answers_unseen_probes(weight=5)
criteria.rollback_cover_and_closure_depth_are_exact(weight=5)
criteria.mode_comparison_matches_the_cycle(weight=5)
criteria.pre_capacity_reason_codes_are_exact(weight=3)
criteria.summary_totals_reconcile_with_the_report(weight=3)
criteria.admission_rate_is_exact(weight=3)
criteria.coverage_shares_follow_the_largest_remainder(weight=3)
criteria.repeat_deferral_and_digest_are_exact(weight=3)
criteria.alpha_scenario_matches_the_shifted_instant(weight=3)
criteria.beta_scenario_matches_the_withdrawn_layers(weight=3)
criteria.unresolved_and_escalations_are_exact(weight=3)
criteria.transcript_accounting_reconciles_with_the_state(weight=3)
criteria.artifacts_carry_the_contract_keys(weight=1)
criteria.artifacts_are_bounded_regular_files(weight=1)
criteria.every_channel_refuses_a_probe_after_the_close(weight=1)
criteria.negative_requests_outside_the_horizon_were_adjudicated(weight=-5)
criteria.negative_duplicate_request_rows_were_counted(weight=-3)
criteria.negative_reason_codes_outside_the_registry(weight=-3)
criteria.negative_state_was_never_moved_by_the_service(weight=-3)
criteria.negative_batch_limit_was_ignored(weight=-3)
criteria.negative_scenarios_repeat_the_baseline_counts(weight=-3)
criteria.negative_mode_delta_disagrees_with_its_own_modes(weight=-1)
criteria.negative_artifacts_carry_dynamic_fields(weight=-1)
criteria.negative_extra_files_sit_in_the_output_directory(weight=-1)
criteria.negative_final_state_seats_a_rejected_unit(weight=-1)
criteria.negative_hardcoded_sample_answers(weight=-1)
