"""Seating reducer for the Hollowbrand package relay.

The reducer owns the only writable copy of channel seating. It boots from the
evidence directory and then accepts batches of operations. It never reads the
clock and never writes to disk, so the same boot plus the same batches always
produce the same state.
"""
from __future__ import annotations

import copy

import csv
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

LADDER = ("edge", "canary", "staging", "stable")
API_VERSION = "3"
PROMOTE = "promote"
SEAL = "seal"


def revision_tuple(text: str) -> Tuple[int, int, int, int, int]:
    epoch, rest = text.split(":", 1)
    core, build = rest.rsplit("-", 1)
    major, minor, patch = core.split(".")
    return (int(epoch), int(major), int(minor), int(patch), int(build))


def label_to_unit(label: str, suffixes: Iterable[str]) -> Optional[str]:
    body = label
    for suffix in suffixes:
        if body.endswith(suffix):
            body = body[: -len(suffix)]
            break
    parts = body.split("_")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return "%s/%s" % (parts[0].lower(), parts[1].lower())


def _read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_tsv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _snapshot_membership(data_dir: str) -> Dict[str, Dict[str, str]]:
    rows = _read_csv(os.path.join(data_dir, "channel_membership_snapshot.csv"))
    if not rows:
        return dict((channel, {}) for channel in LADDER)
    current = max(int(row["snapshot_seq"]) for row in rows)
    seating: Dict[str, Dict[str, str]] = dict((channel, {}) for channel in LADDER)
    for row in rows:
        if int(row["snapshot_seq"]) != current:
            continue
        if row["state"] != "promoted":
            continue
        if row["channel"] in seating:
            seating[row["channel"]][row["unit_key"]] = row["revision"]
    return seating


def _mirror_revisions(data_dir: str, cut: str) -> Dict[str, Dict[str, str]]:
    with open(os.path.join(data_dir, "platform_suffixes.json"), "r", encoding="utf-8") as handle:
        suffixes = json.load(handle)["suffixes"]
    published: Dict[str, Dict[str, str]] = {}
    for channel in LADDER:
        best: Dict[str, str] = {}
        for row in _read_tsv(os.path.join(data_dir, "mirror_index_%s.tsv" % channel)):
            if row["state"] != "published" or row["published_at"] > cut:
                continue
            unit = label_to_unit(row["label"], suffixes)
            if unit is None:
                continue
            held = best.get(unit)
            if held is None or revision_tuple(row["revision"]) > revision_tuple(held):
                best[unit] = row["revision"]
        published[channel] = best
    return published


def boot(data_dir: str, cut: str) -> Dict[str, Any]:
    seating = _snapshot_membership(data_dir)
    published = _mirror_revisions(data_dir, cut)
    channels: Dict[str, Dict[str, Any]] = {}
    for channel in LADDER:
        held: Dict[str, Any] = {}
        for unit, snapshot_revision in sorted(seating[channel].items()):
            revision = published[channel].get(unit, snapshot_revision)
            held[unit] = {"revision": revision, "state": "promoted", "seq": 0}
        channels[channel] = held
    return {"api_version": API_VERSION, "op_seq": 0, "sealed": [], "channels": channels}


def head_index(state: Dict[str, Any], unit: str) -> int:
    head = -1
    for index, channel in enumerate(LADDER):
        if unit in state["channels"][channel]:
            head = index
    return head


def _requirements_met(state: Dict[str, Any], channel: str,
                      requires: Iterable[Iterable[str]]) -> Optional[str]:
    held = state["channels"][channel]
    for pair in requires or []:
        unit, minimum = pair[0], pair[1]
        seated = held.get(unit)
        if seated is None:
            return unit
        if revision_tuple(seated["revision"]) < revision_tuple(minimum):
            return unit
    return None


def _apply_promote(state: Dict[str, Any], op: Dict[str, Any]) -> Dict[str, Any]:
    unit = op["unit_key"]
    revision = op["revision"]
    channel = op["target_channel"]
    if channel not in LADDER:
        return {"accepted": False, "reason": "unknown_channel"}
    if channel in state["sealed"]:
        return {"accepted": False, "reason": "channel_sealed"}
    index = LADDER.index(channel)
    head = head_index(state, unit)
    if head < 0:
        if index != 0:
            return {"accepted": False, "reason": "channel_not_adjacent"}
    elif index not in (head, head + 1):
        return {"accepted": False, "reason": "channel_not_adjacent"}
    seated = state["channels"][channel].get(unit)
    if seated is not None and revision_tuple(seated["revision"]) >= revision_tuple(revision):
        return {"accepted": False, "reason": "revision_regression"}
    short = _requirements_met(state, channel, op.get("requires") or [])
    if short is not None:
        return {"accepted": False, "reason": "missing_dependency", "detail": short}
    state["op_seq"] += 1
    state["channels"][channel][unit] = {
        "revision": revision, "state": "promoted", "seq": state["op_seq"],
    }
    return {"accepted": True, "reason": "ok", "op_seq": state["op_seq"]}


def _apply_seal(state: Dict[str, Any], op: Dict[str, Any]) -> Dict[str, Any]:
    channel = op["channel"]
    if channel not in LADDER:
        return {"accepted": False, "reason": "unknown_channel"}
    if channel in state["sealed"]:
        return {"accepted": False, "reason": "channel_already_sealed"}
    state["op_seq"] += 1
    state["sealed"].append(channel)
    return {"accepted": True, "reason": "ok", "op_seq": state["op_seq"]}


def apply_batch(state: Dict[str, Any], transcript: List[Dict[str, Any]],
                seen: Dict[str, Dict[str, Any]], body: Dict[str, Any],
                batch_limit: int, actor: str) -> Dict[str, Any]:
    key = body.get("idempotency_key")
    if key in seen:
        replay = dict(seen[key])
        replay["replay"] = True
        transcript.append({"idempotency_key": key, "replay": True,
                           "ops": len(body.get("ops") or []),
                           "accepted": replay.get("accepted", 0),
                           "rejected": replay.get("rejected", 0)})
        return replay
    ops = body.get("ops") or []
    if body.get("actor") != actor:
        return {"ok": False, "reason": "unknown_actor", "accepted": 0,
                "rejected": 0, "results": []}
    if len(ops) > batch_limit:
        return {"ok": False, "reason": "batch_too_large", "accepted": 0,
                "rejected": 0, "results": []}
    # One refused op aborts the whole call, so the ops are read against a scratch
    # copy and the committed state only moves when every op was accepted.
    scratch = copy.deepcopy(state)
    results: List[Dict[str, Any]] = []
    accepted = 0
    refused = -1
    for index, op in enumerate(ops):
        kind = op.get("op")
        if kind == PROMOTE:
            outcome = _apply_promote(scratch, op)
        elif kind == SEAL:
            outcome = _apply_seal(scratch, op)
        else:
            outcome = {"accepted": False, "reason": "unknown_op"}
        results.append(outcome)
        if outcome["accepted"]:
            accepted += 1
        else:
            refused = index
            break
    if refused >= 0:
        answer = {"ok": False, "reason": "adjudication_error",
                  "refused_op_index": refused, "accepted": 0,
                  "rejected": len(ops), "results": results,
                  "op_seq": state["op_seq"]}
        if key is not None:
            seen[key] = answer
        transcript.append({"idempotency_key": key, "replay": False, "ops": len(ops),
                           "accepted": 0, "rejected": len(ops), "aborted": True})
        return answer
    state.clear()
    state.update(scratch)
    answer = {"ok": True, "reason": "applied", "accepted": accepted,
              "rejected": 0, "results": results,
              "op_seq": state["op_seq"]}
    if key is not None:
        seen[key] = answer
    transcript.append({"idempotency_key": key, "replay": False, "ops": len(ops),
                       "accepted": accepted, "rejected": 0, "aborted": False})
    return answer
