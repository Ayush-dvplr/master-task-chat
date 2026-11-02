"""Verifier checks for the settled pledge docket."""

import base64
import json
import os
import zlib

from rewardkit import criteria, criterion

_EXPECT_BLOB = "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"

_CACHE = {}

ARTIFACTS = (
    "report.json",
    "final_state.json",
    "transcript_summary.json",
    "scenario_alpha.json",
    "scenario_beta.json",
    "scenario_mode.json",
    "summary.json",
)


def _expect():
    if "data" not in _CACHE:
        raw = zlib.decompress(base64.b64decode(_EXPECT_BLOB))
        _CACHE["data"] = json.loads(raw.decode("utf-8"))
    return _CACHE["data"]


def _load(workspace, name):
    path = os.path.join(workspace, "out", name)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _same(got, want):
    if isinstance(want, bool):
        return isinstance(got, bool) and got == want
    if isinstance(want, int):
        return isinstance(got, int) and not isinstance(got, bool) and got == want
    if isinstance(want, float):
        return isinstance(got, float) and got == want
    if isinstance(want, str):
        return isinstance(got, str) and got == want
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return False
        return all(_same(a, b) for a, b in zip(got, want))
    if isinstance(want, dict):
        if not isinstance(got, dict) or set(got) != set(want):
            return False
        return all(_same(got[k], want[k]) for k in want)
    return got is want


def _holds(probe, workspace):
    try:
        return bool(probe(workspace))
    except Exception:
        return False


def _rows(workspace):
    return {row["pledge_id"]: row for row in _load(workspace, "report.json")["pledges"]}


def _want_rows():
    return {row["pledge_id"]: row for row in _expect()["report"]["pledges"]}


def _field_matches(workspace, field):
    got = _rows(workspace)
    want = _want_rows()
    if set(got) != set(want):
        return False
    return all(_same(got[pid].get(field), want[pid][field]) for pid in want)


def _subset(got, want, keys):
    return all(_same(got.get(key), want[key]) for key in keys)


def _check_docket_membership(workspace):
    report = _load(workspace, "report.json")
    got = [row["pledge_id"] for row in report["pledges"]]
    want = [row["pledge_id"] for row in _expect()["report"]["pledges"]]
    return got == want


def _check_due_instants(workspace):
    return _field_matches(workspace, "governing_due_instant")


def _check_final_states(workspace):
    return _field_matches(workspace, "final_state")


def _check_lateness(workspace):
    return _field_matches(workspace, "lateness_minutes")


def _check_granted(workspace):
    return _field_matches(workspace, "granted_minutes")


def _check_reason_codes(workspace):
    return _field_matches(workspace, "reason_codes")


def _check_rate_block(workspace):
    got = _load(workspace, "summary.json")
    want = _expect()["summary"]
    return _subset(
        got,
        want,
        (
            "audit_total",
            "breach_rate_denominator",
            "breached_in_rate",
            "breach_rate_per_mille",
        ),
    )


def _check_fingerprint(workspace):
    want = _expect()["summary"]["settlement_fingerprint"]
    first = _load(workspace, "summary.json").get("settlement_fingerprint")
    second = _load(workspace, "final_state.json").get("settlement_fingerprint")
    return first == want and second == want


def _check_due_authority(workspace):
    return _field_matches(workspace, "due_authority") and _field_matches(
        workspace, "due_record_key"
    )


def _check_effective_instants(workspace):
    return _field_matches(workspace, "effective_discharge_instant")


def _check_residual(workspace):
    return _field_matches(workspace, "residual_minutes")


def _check_holders_and_classes(workspace):
    return _field_matches(workspace, "counterparty_key") and _field_matches(
        workspace, "pledge_class"
    )


def _check_report_counts(workspace):
    return _load(workspace, "report.json")["counts"] == _expect()["report"]["counts"]


def _check_alpha(workspace):
    got = _load(workspace, "scenario_alpha.json")
    want = _expect()["scenario_alpha"]
    return got == want


def _check_beta(workspace):
    got = _load(workspace, "scenario_beta.json")
    want = _expect()["scenario_beta"]
    return got == want


def _check_mode(workspace):
    got = _load(workspace, "scenario_mode.json")
    want = _expect()["scenario_mode"]
    return got == want


def _check_transcript_counts(workspace):
    got = _load(workspace, "transcript_summary.json")
    want = _expect()["transcript_summary"]
    return _subset(
        got,
        want,
        (
            "total_calls",
            "accepted_calls",
            "rejected_calls",
            "first_sequence",
            "last_sequence",
            "seal_sequence",
        ),
    )


def _check_transcript_channels(workspace):
    got = _load(workspace, "transcript_summary.json")
    want = _expect()["transcript_summary"]
    return _subset(got, want, ("calls_by_channel", "rejections_by_reason"))


def _check_sealed_state(workspace):
    got = _load(workspace, "final_state.json")
    want = _expect()["final_state"]
    return _subset(
        got,
        want,
        (
            "sealed",
            "window_id",
            "registered",
            "accepted_transitions",
            "rejected_calls",
            "state_counts",
            "grace_granted_total",
            "total_lateness_minutes",
        ),
    )


def _check_summary_tail(workspace):
    got = _load(workspace, "summary.json")
    want = _expect()["summary"]
    return _subset(
        got,
        want,
        (
            "window_id",
            "governing_mode",
            "granted_minutes_total",
            "unresolved_pledges",
            "counterparty_count",
            "top_breach_counterparty",
        ),
    )


def _check_call_identity(workspace):
    transcript = _load(workspace, "transcript_summary.json")
    state = _load(workspace, "final_state.json")
    return (
        transcript["accepted_calls"]
        == state["accepted_transitions"] + state["registered"] + 2
        and transcript["last_sequence"] == transcript["total_calls"]
        and transcript["seal_sequence"] == transcript["total_calls"] - 1
    )


def _check_grace_identity(workspace):
    report = _load(workspace, "report.json")
    summary = _load(workspace, "summary.json")
    state = _load(workspace, "final_state.json")
    mode = _load(workspace, "scenario_mode.json")
    total = sum(row["granted_minutes"] for row in report["pledges"])
    return (
        total == summary["granted_minutes_total"] == state["grace_granted_total"]
        and mode["grace_unused_minutes"] == mode["grace_pool_minutes"] - total
    )


def _check_artifacts_parse(workspace):
    loaded = [_load(workspace, name) for name in ARTIFACTS]
    return all(isinstance(item, dict) and len(item) > 0 for item in loaded)


def _check_key_sets(workspace):
    data = _expect()
    for name in ARTIFACTS:
        stem = name[:-5]
        if sorted(_load(workspace, name)) != sorted(data[stem]):
            return False
    return True


def _check_no_zero_grace(workspace):
    report = _load(workspace, "report.json")
    return any(row["granted_minutes"] > 0 for row in report["pledges"])


def _check_counts_recomputed(workspace):
    report = _load(workspace, "report.json")
    counts = report["counts"]
    for state in (
        "cleared",
        "tempered_clear",
        "breached",
        "waived",
        "blocked",
        "held",
        "lapsed",
    ):
        tally = sum(1 for row in report["pledges"] if row["final_state"] == state)
        if counts.get(state) != tally:
            return False
    return counts.get("audit_total") == len(report["pledges"])


def _check_state_counts_agree(workspace):
    report = _load(workspace, "report.json")
    state = _load(workspace, "final_state.json")["state_counts"]
    for name, value in state.items():
        if sum(1 for row in report["pledges"] if row["final_state"] == name) != value:
            return False
    return True


def _check_alpha_revert_identity(workspace):
    report = _load(workspace, "report.json")
    alpha = _load(workspace, "scenario_alpha.json")
    gap = alpha["breached"] - report["counts"]["breached"]
    return gap == len(alpha["reverted_pledges"]) and gap > 0


def _check_mode_tallies_differ(workspace):
    tallies = _load(workspace, "scenario_mode.json")["tallies"]
    return tallies["strict"] != tallies["tempered"]


def _check_beta_differs(workspace):
    report = _load(workspace, "report.json")
    beta = _load(workspace, "scenario_beta.json")
    return (
        beta["docket_size"] != report["counts"]["audit_total"]
        or len(beta["membership_changes"]) > 0
    )


def _check_cli_channel_used(workspace):
    transcript = _load(workspace, "transcript_summary.json")
    report = _load(workspace, "report.json")
    return (
        transcript["calls_by_channel"].get("cli", 0) == report["counts"]["waived"]
        and report["counts"]["waived"] > 0
    )


def _check_boundary_rejections(workspace):
    reasons = _load(workspace, "transcript_summary.json")["rejections_by_reason"]
    return reasons.get("out_of_window", 0) > 0 and reasons.get("already_sealed", 0) == 1


def _check_sealed_true(workspace):
    return _load(workspace, "final_state.json").get("sealed") is True


def _check_provenance_and_holders(workspace):
    return _check_due_authority(workspace) and _check_holders_and_classes(workspace)


def _check_row_tail_fields(workspace):
    return _check_effective_instants(workspace) and _check_residual(workspace)


def _check_transcript_block(workspace):
    return _check_transcript_counts(workspace) and _check_transcript_channels(workspace)


def _check_cross_identities(workspace):
    return _check_call_identity(workspace) and _check_grace_identity(workspace)


def _check_no_sample_refs(workspace):
    return all(
        len(pid) != 8 or pid[:4] not in ("PL-4", "PL-5")
        for pid in _rows(workspace)
    )

def _check_row_key_sets(workspace):
    report = _load(workspace, "report.json")
    want = set(_expect()["report"]["pledges"][0])
    rows = report["pledges"]
    return len(rows) > 0 and all(set(row) == want for row in rows)


def _check_byte_form(workspace):
    for name in ARTIFACTS:
        with open(os.path.join(workspace, "out", name), "rb") as handle:
            raw = handle.read()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or len(payload) == 0:
            return False
        shaped = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if raw != shaped.encode("utf-8"):
            return False
    return True


def _missing(workspace):
    for name in ARTIFACTS:
        try:
            got = _load(workspace, name)
        except Exception:
            return True
        if not isinstance(got, dict):
            return True
        if set(got) != set(_expect()[name[:-5]]):
            return True
    return False


@criterion(description="The docket holds exactly the pledges whose governing due instant falls inside the settlement window, in canonical order")
def report_docket_membership(workspace):
    return _holds(_check_docket_membership, workspace)


@criterion(description="Every governing due instant in the filed report matches the instant the corpus rules produce")
def report_due_instants(workspace):
    return _holds(_check_due_instants, workspace)


@criterion(description="Every final state in the filed report matches the settled state for that pledge")
def report_final_states(workspace):
    return _holds(_check_final_states, workspace)


@criterion(description="Every lateness figure in the filed report matches the whole minute count the rules produce")
def report_lateness_minutes(workspace):
    return _holds(_check_lateness, workspace)


@criterion(description="Every granted minute figure in the filed report matches the grace round outcome")
def report_granted_minutes(workspace):
    return _holds(_check_granted, workspace)


@criterion(description="Every reason code list in the filed report matches the closed vocabulary outcome for that pledge")
def report_reason_codes(workspace):
    return _holds(_check_reason_codes, workspace)


@criterion(description="The summary carries the audit total, the breach rate denominator, the breached in rate count and the rate in parts per thousand")
def summary_rate_block(workspace):
    return _holds(_check_rate_block, workspace)


@criterion(description="The settlement fingerprint the interface returned appears in both the sealed state and the summary")
def settlement_fingerprint_agrees(workspace):
    return _holds(_check_fingerprint, workspace)


@criterion(description="Every due authority, governing record key, holder key and class in the filed report matches the governing record and the resolved holder")
def report_provenance_and_holders(workspace):
    return _holds(_check_provenance_and_holders, workspace)


@criterion(description="Every effective discharge instant and residual minute figure in the filed report matches the propagated outcome")
def report_row_tail_fields(workspace):
    return _holds(_check_row_tail_fields, workspace)


@criterion(description="The report state tally carries the audit total, the breach rate denominator and each of the seven state counts")
def report_counts_block(workspace):
    return _holds(_check_report_counts, workspace)


@criterion(description="The grace withdrawn scenario matches on its breached tally, its tempered clear tally, its reverted pledge list and its residual total")
def scenario_alpha_block(workspace):
    return _holds(_check_alpha, workspace)


@criterion(description="The presence zone scenario matches on its docket size, its breached tally, its membership changes and its lateness delta")
def scenario_beta_block(workspace):
    return _holds(_check_beta, workspace)


@criterion(description="The mode scenario matches on the governing mode, the countersignature authority, both tallies, the pool and the unused minutes")
def scenario_mode_block(workspace):
    return _holds(_check_mode, workspace)


@criterion(description="The transcript summary matches on call totals, the three sequence numbers, the per channel tally and the refusal reason tally")
def transcript_summary_block(workspace):
    return _holds(_check_transcript_block, workspace)


@criterion(description="The sealed state read back from the interface matches on registration count, accepted transitions, refused calls, state counts, granted total and lateness total")
def sealed_state_block(workspace):
    return _holds(_check_sealed_state, workspace)


@criterion(description="The summary matches on window identifier, governing mode, granted total, unresolved pledge list, holder count and leading breached holder")
def summary_tail_block(workspace):
    return _holds(_check_summary_tail, workspace)


@criterion(description="The accepted call count, the seal sequence and the granted minutes agree across the report, the summary, the sealed state and the transcript")
def cross_artifact_identities(workspace):
    return _holds(_check_cross_identities, workspace)


@criterion(description="All seven artifacts parse as JSON objects")
def artifacts_parse(workspace):
    return _holds(_check_artifacts_parse, workspace)


@criterion(description="Each artifact carries exactly the key set the output contract fixes")
def artifact_key_sets(workspace):
    return _holds(_check_key_sets, workspace)


@criterion(description="Every pledge row in the report carries exactly the key set the output contract fixes")
def report_row_key_sets(workspace):
    return _holds(_check_row_key_sets, workspace)


@criterion(description="Each artifact is written with two space indentation, keys sorted as text and one closing newline")
def artifact_byte_form(workspace):
    return _holds(_check_byte_form, workspace)


@criterion(description="A filed report where no pledge carries granted minutes shows the grace round was never run")
def negative_grace_round_skipped(workspace):
    # shortcut: leaving every granted figure at zero
    if _missing(workspace):
        return False
    return not _holds(_check_no_zero_grace, workspace)


@criterion(description="A state tally that disagrees with the filed pledge rows shows the counts were asserted rather than recomputed")
def negative_counts_asserted(workspace):
    # shortcut: writing a tally that the rows do not support
    if _missing(workspace):
        return False
    return not _holds(_check_counts_recomputed, workspace)


@criterion(description="A sealed state whose state counts disagree with the filed pledge rows shows the interface was driven from different states than the report carries")
def negative_sealed_state_divergent(workspace):
    # shortcut: driving the interface from one settlement and filing another
    if _missing(workspace):
        return False
    return not _holds(_check_state_counts_agree, workspace)


@criterion(description="A grace withdrawn scenario whose breached gap misses its reverted pledge list shows the scenario was copied from the filed settlement")
def negative_alpha_copied(workspace):
    # shortcut: copying the filed tallies into the alpha scenario
    if _missing(workspace):
        return False
    return not _holds(_check_alpha_revert_identity, workspace)


@criterion(description="Identical strict and tempered tallies show the mode scenario was never settled twice")
def negative_mode_single_pass(workspace):
    # shortcut: reporting one settlement under both mode headings
    if _missing(workspace):
        return False
    return not _holds(_check_mode_tallies_differ, workspace)


@criterion(description="A presence zone scenario identical to the filed docket shows the itinerary was never applied")
def negative_beta_unresolved(workspace):
    # shortcut: reusing the filed docket for the presence zone scenario
    if _missing(workspace):
        return False
    return not _holds(_check_beta_differs, workspace)


@criterion(description="A per channel tally with no client calls shows every event travelled on one channel")
def negative_channel_rule_ignored(workspace):
    # shortcut: sending every call straight to the interface
    if _missing(workspace):
        return False
    return not _holds(_check_cli_channel_used, workspace)


@criterion(description="A refusal tally without boundary refusals and one seal confirmation shows those calls were never made")
def negative_boundary_notices_missing(workspace):
    # shortcut: skipping the boundary notices and the seal confirmation
    if _missing(workspace):
        return False
    return not _holds(_check_boundary_rejections, workspace)


@criterion(description="A sealed flag that is anything other than true shows the window was left open")
def negative_window_left_open(workspace):
    # shortcut: filing the state without sealing the window
    if _missing(workspace):
        return False
    return not _holds(_check_sealed_true, workspace)



@criterion(
    description="Report rows carry docket pledge references rather than the worked example references shipped in the closed window files"
)
def negative_hardcoded_sample_answers(workspace):
    # lifting rows straight out of the precedent files in place of settling the docket
    if _missing(workspace):
        return False
    return not _holds(_check_no_sample_refs, workspace)

criteria.report_docket_membership(weight=5)
criteria.report_due_instants(weight=5)
criteria.report_final_states(weight=5)
criteria.report_lateness_minutes(weight=5)
criteria.report_granted_minutes(weight=5)
criteria.report_reason_codes(weight=5)
criteria.summary_rate_block(weight=5)
criteria.settlement_fingerprint_agrees(weight=5)
criteria.report_provenance_and_holders(weight=3)
criteria.report_row_tail_fields(weight=3)
criteria.report_counts_block(weight=3)
criteria.scenario_alpha_block(weight=3)
criteria.scenario_beta_block(weight=3)
criteria.scenario_mode_block(weight=3)
criteria.transcript_summary_block(weight=3)
criteria.sealed_state_block(weight=3)
criteria.summary_tail_block(weight=3)
criteria.cross_artifact_identities(weight=3)
criteria.artifacts_parse(weight=1)
criteria.artifact_key_sets(weight=1)
criteria.report_row_key_sets(weight=3)
criteria.artifact_byte_form(weight=1)
criteria.negative_grace_round_skipped(weight=-5)
criteria.negative_counts_asserted(weight=-5)
criteria.negative_sealed_state_divergent(weight=-3)
criteria.negative_alpha_copied(weight=-3)
criteria.negative_mode_single_pass(weight=-3)
criteria.negative_beta_unresolved(weight=-3)
criteria.negative_channel_rule_ignored(weight=-3)
criteria.negative_boundary_notices_missing(weight=-3)
criteria.negative_window_left_open(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-3)
