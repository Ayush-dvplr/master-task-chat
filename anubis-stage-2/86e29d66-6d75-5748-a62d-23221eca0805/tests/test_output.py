"""Deterministic checks for the chainfold run ledger repair task.

The grading container holds only this directory, so every workload used here is
either an expectation frozen from the shipped archive or a run plan built in
memory and written to a temporary directory before the delivered program is
pointed at it.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import signal
import shutil
import subprocess
import sys
import tempfile

from rewardkit import criteria, criterion

OUT = pathlib.Path("/app/out")
PROGRAM = OUT / "optimize.py"
LANES = ("visible", "peak", "steady", "burst", "latency")
REASONS = (
    "duplicate_sequence",
    "unknown_field",
    "unknown_shard",
    "retired_shard",
    "empty_shard",
    "unknown_owner",
    "owner_excluded",
    "owner_mismatch",
    "examples_out_of_range",
    "bad_loss_scale",
)
MICRO_FIELDS = frozenset(
    ("record", "sequence", "owner", "shard", "pass_index", "examples", "loss_scale", "overflow")
)
REPORTS = (
    "scenario_visible.json",
    "scenario_peak.json",
    "scenario_steady.json",
    "scenario_burst.json",
    "scenario_latency.json",
    "perf_report.json",
    "bottleneck_analysis.json",
    "recommendations.json",
    "data_quality.json",
)
SEAL = {
    "scenario_visible.json": "d0c895c6797fbdca",
    "scenario_peak.json": "30326cf0c46aa184",
    "scenario_steady.json": "31edb33e2396d179",
    "scenario_burst.json": "e16a2b767f75b2d7",
    "scenario_latency.json": "062c8f4f6d4deb4e",
    "perf_report.json": "62017eeab89e4c61",
    "bottleneck_analysis.json": "d555c072620f4a90",
    "recommendations.json": "2116111b45fb0f46",
    "data_quality.json": "11e0095462d75520",
}
LEDGER = {
    "visible": {
        "accepted_examples": 5894,
        "accepted_records": 124,
        "optimizer_steps": 30,
        "rolled_back_records": 1,
        "rolled_back_examples": 48,
        "discarded_partial_records": 0,
        "discarded_partial_examples": 0,
        "trailing_partial_records": 2,
        "trailing_partial_examples": 90,
        "total_records": 127,
        "overflow_skipped": 2,
        "rejected_records": 0,
        "cursor_drift": 0,
    },
    "peak": {
        "accepted_examples": 5894,
        "accepted_records": 124,
        "optimizer_steps": 20,
        "rolled_back_records": 1,
        "rolled_back_examples": 48,
        "discarded_partial_records": 2,
        "discarded_partial_examples": 96,
        "trailing_partial_records": 2,
        "trailing_partial_examples": 90,
        "total_records": 127,
        "overflow_skipped": 2,
        "rejected_records": 0,
        "cursor_drift": 0,
    },
    "steady": {
        "accepted_examples": 5894,
        "accepted_records": 124,
        "optimizer_steps": 30,
        "rolled_back_records": 1,
        "rolled_back_examples": 48,
        "discarded_partial_records": 0,
        "discarded_partial_examples": 0,
        "trailing_partial_records": 2,
        "trailing_partial_examples": 90,
        "total_records": 127,
        "overflow_skipped": 2,
        "rejected_records": 0,
        "cursor_drift": 0,
    },
    "burst": {
        "accepted_examples": 5894,
        "accepted_records": 124,
        "optimizer_steps": 41,
        "rolled_back_records": 1,
        "rolled_back_examples": 48,
        "discarded_partial_records": 0,
        "discarded_partial_examples": 0,
        "trailing_partial_records": 1,
        "trailing_partial_examples": 42,
        "total_records": 127,
        "overflow_skipped": 2,
        "rejected_records": 0,
        "cursor_drift": 0,
    },
    "latency": {
        "accepted_examples": 4660,
        "accepted_records": 98,
        "optimizer_steps": 23,
        "rolled_back_records": 1,
        "rolled_back_examples": 48,
        "discarded_partial_records": 3,
        "discarded_partial_examples": 144,
        "trailing_partial_records": 3,
        "trailing_partial_examples": 132,
        "total_records": 127,
        "overflow_skipped": 2,
        "rejected_records": 26,
        "cursor_drift": 6,
    },
}
CURVE = {
    "visible": {
        "rate_first": 533,
        "rate_last": 1620,
        "rate_min": 533,
        "rate_max": 3200,
        "rate_sum": 59420,
        "rate_digest": "66e7f2ceca7b2a8b",
        "logged_steps": 6,
    },
    "peak": {
        "rate_first": 533,
        "rate_last": 920,
        "rate_min": 533,
        "rate_max": 3200,
        "rate_sum": 37905,
        "rate_digest": "22e17ab8c24575bb",
        "logged_steps": 4,
    },
    "steady": {
        "rate_first": 480,
        "rate_last": 1742,
        "rate_min": 480,
        "rate_max": 2880,
        "rate_sum": 58915,
        "rate_digest": "315c99229154f091",
        "logged_steps": 6,
    },
    "burst": {
        "rate_first": 533,
        "rate_last": 2180,
        "rate_min": 533,
        "rate_max": 3200,
        "rate_sum": 80034,
        "rate_digest": "f5a437c906cdfe19",
        "logged_steps": 8,
    },
    "latency": {
        "rate_first": 533,
        "rate_last": 2600,
        "rate_min": 533,
        "rate_max": 3200,
        "rate_sum": 44731,
        "rate_digest": "c740d95337b4cbf1",
        "logged_steps": 4,
    },
}
PROBE = {
    "visible": (6, 1, 4, "ck-02", 28, 47800),
    "peak": (5, 0, 5, "ck-02", 20, 48200),
    "steady": (6, 1, 4, "ck-02", 28, 47800),
    "burst": (9, 1, 1, "ck-02", 36, 48000),
    "latency": (2, 0, 8, "ck-04", 16, 48500),
}
DELTAS = {
    "peak": (0, -10),
    "steady": (0, 0),
    "burst": (0, 11),
    "latency": (-1234, -7),
}
TOTALS = {
    "accepted_examples": 28236,
    "accepted_records": 594,
    "optimizer_steps": 144,
    "rejected_records": 26,
    "rolled_back_records": 5,
    "skipped_records": 10,
}
STAGE_ORDER = {
    "visible": ("trailing", "rollback", "ownership", "partial_discard", "validation"),
    "peak": ("partial_discard", "trailing", "rollback", "ownership", "validation"),
    "steady": ("trailing", "rollback", "ownership", "partial_discard", "validation"),
    "burst": ("rollback", "trailing", "ownership", "partial_discard", "validation"),
    "latency": ("ownership", "partial_discard", "trailing", "rollback", "validation"),
}
QUIET_CODES = [
    "shorten-checkpoint-interval",
    "restore-probe-cadence",
    "retire-stray-probes",
    "pad-final-window",
    "reconcile-shard-plan",
]
SPLIT_CODES = [
    "align-restart-to-window",
    "shorten-checkpoint-interval",
    "retire-stray-probes",
    "pad-final-window",
    "reconcile-shard-plan",
]
MERGED_CODES = [
    "align-restart-to-window",
    "shorten-checkpoint-interval",
    "restore-probe-cadence",
    "retire-stray-probes",
    "pad-final-window",
    "reconcile-shard-plan",
]
DROP_GUARD = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


def _flat(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(obj: object) -> str:
    return hashlib.sha256(_flat(obj).encode("utf-8")).hexdigest()[:16]


def _load(name: str) -> dict:
    raw = (OUT / name).read_text(encoding="utf-8")
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("report body is not an object")
    return body


def _sealed(body: dict) -> bool:
    copy = dict(body)
    stamp = copy.pop("body_fingerprint", None)
    return isinstance(stamp, str) and stamp == _digest(copy)


def _no_floats(node: object) -> bool:
    if isinstance(node, bool):
        return True
    if isinstance(node, float):
        return False
    if isinstance(node, dict):
        return all(_no_floats(item) for item in node.values())
    if isinstance(node, list):
        return all(_no_floats(item) for item in node)
    return True


def _grant_read(argument: str) -> None:
    if not argument.startswith("/app"):
        return
    path = pathlib.Path(argument)
    try:
        if not path.exists():
            return
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(parts: list) -> list:
    for item in parts:
        _grant_read(str(item))
    if os.name == "posix" and os.geteuid() == 0:
        return list(DROP_GUARD) + list(parts)
    return list(parts)


def _invoke(source: pathlib.Path, target: pathlib.Path) -> bool:
    target.mkdir(parents=True, exist_ok=True)
    for item in (source, target):
        item.chmod(0o777)
    command = _untrusted_command(
        [sys.executable, "-I", "-S", str(PROGRAM), "--data", str(source), "--out", str(target)]
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONHASHSEED": "0",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        },
    )
    try:
        process.communicate(timeout=240)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    return process.returncode == 0


def _gather(folder: pathlib.Path, name: str) -> dict:
    return json.loads((folder / name).read_text(encoding="utf-8"))


def _lanes(entries: list) -> list:
    shaped = []
    for name, width, scale, span, carry, barred, pace in entries:
        shaped.append(
            {
                "name": name,
                "width_override": width,
                "rate_scale_percent": scale,
                "decay_span_steps": span,
                "carry_partial": carry,
                "excluded_owners": list(barred),
                "eval_cadence_scale": pace,
            }
        )
    return shaped


PLANS = {
    "alpha": {
        "base": {
            "peak_rate_milli": 4200,
            "floor_rate_milli": 600,
            "warmup_steps": 5,
            "decay_span_steps": 12,
            "restart_period_steps": 9,
        },
        "policy": {
            "default_width": 4,
            "minimum_width": 2,
            "maximum_width": 7,
            "partial_window_rule": "discard",
        },
        "phases": [
            {"phase": "q1", "accumulation_width": 4, "rate_scale_percent": 100},
            {"phase": "q2", "accumulation_width": 5, "rate_scale_percent": 90},
            {"phase": "q3", "accumulation_width": 6, "rate_scale_percent": 85},
        ],
        "markers": [(1, "q1"), (30, "q2"), (62, "q3")],
        "exceptions": [
            {
                "restart_id": "rx-1",
                "accumulation_width": None,
                "rate_scale_percent": 100,
                "carry_partial": None,
            },
            {
                "restart_id": "rx-2",
                "accumulation_width": 3,
                "rate_scale_percent": 75,
                "carry_partial": True,
            },
        ],
        "restarts": [
            {"restart_id": "rx-1", "at_sequence": 20, "resume_checkpoint": "ca-1"},
            {"restart_id": "rx-2", "at_sequence": 48, "resume_checkpoint": "ca-2"},
        ],
        "checkpoints": [
            ("ca-1", 9, "ca-2", 11),
            ("ca-2", 21, "", 39),
            ("ca-3", 30, "ca-4", 55),
            ("ca-4", 40, "", 70),
            ("ca-5", 55, "", 88),
            ("ca-6", 0, "ca-7", 95),
            ("ca-7", 0, "ca-6", 96),
        ],
        "cadence": {
            "log_every_steps": 4,
            "eval_every_steps": 3,
            "patience_probes": 2,
            "average_window": 2,
        },
        "probes": [
            ("pa-01", 3, 61000, "ca-1"),
            ("pa-02", 5, 60000, "ca-2"),
            ("pa-03", 6, 59000, "ca-3"),
            ("pa-04", 9, 59000, "ca-4"),
            ("pa-05", 12, 58000, "ca-6"),
            ("pa-06", 15, 60200, "ca-5"),
        ],
        "shards": [
            ("sa-1", "w21", 900, (1, 2), 5, "active"),
            ("sa-2", "w22", 760, (1,), 10, "active"),
            ("sa-3", "w23", 180, (1,), 15, "retired"),
            ("sa-4", "w21", 120, (1,), 20, "active"),
            ("sa-5", "w24", 1200, (1,), 25, "active"),
        ],
        "holdouts": [("sa-1", 10), ("sa-2", 6), ("sa-4", 70)],
        "dropped": [("sa-1", 6), ("sa-4", 50), ("sa-5", 8)],
        "moves": [
            ("sa-5", "w24", "w22", 30),
            ("sa-5", "w24", "w23", 30),
            ("sa-1", "w21", "w23", 500),
        ],
        "roster": [("w21", "trainer", 8), ("w22", "trainer", 8), ("w23", "trainer", 4), ("w24", "trainer", 4)],
        "chunk": 50,
        "overflow_at": (7, 23),
        "conflict": False,
        "twin_markers": False,
        "style": 0,
        "precedence_probes": True,
    },
}
PLANS["beta"] = {
    "base": {
        "peak_rate_milli": 2000,
        "floor_rate_milli": 500,
        "warmup_steps": 0,
        "decay_span_steps": 0,
        "restart_period_steps": 0,
    },
    "policy": {
        "default_width": 3,
        "minimum_width": 2,
        "maximum_width": 5,
        "partial_window_rule": "carry",
    },
    "phases": [
        {"phase": "b1", "accumulation_width": None, "rate_scale_percent": 100},
        {"phase": "b2", "accumulation_width": 5, "rate_scale_percent": 110},
    ],
    "markers": [(1, "b1"), (33, "b2")],
    "exceptions": [
        {
            "restart_id": "rb-1",
            "accumulation_width": 2,
            "rate_scale_percent": 50,
            "carry_partial": False,
        }
    ],
    "restarts": [{"restart_id": "rb-1", "at_sequence": 32, "resume_checkpoint": "cb-1"}],
    "checkpoints": [("cb-1", 5, "", 20), ("cb-2", 14, "", 26), ("cb-3", 28, "cb-2", 34)],
    "cadence": {
        "log_every_steps": 0,
        "eval_every_steps": 2,
        "patience_probes": 3,
        "average_window": 4,
    },
    "probes": [
        ("pb-01", 2, 44000, "cb-1"),
        ("pb-02", 4, 43000, "cb-3"),
        ("pb-03", 6, 43500, "cb-2"),
        ("pb-04", 8, 43600, "cb-1"),
        ("pb-05", 10, 43700, "cb-2"),
    ],
    "shards": [
        ("sb-1", "w31", 400, (1, 2), 3, "active"),
        ("sb-2", "w32", 300, (1,), 6, "active"),
        ("sb-3", "w33", 90, (1,), 9, "active"),
    ],
    "holdouts": [("sb-1", 4)],
    "dropped": [("sb-2", 10)],
    "moves": [("sb-2", "w32", "w33", 18)],
    "roster": [("w31", "trainer", 6), ("w32", "trainer", 6), ("w33", "trainer", 2)],
    "chunk": 40,
    "overflow_at": (5,),
    "conflict": False,
    "twin_markers": False,
    "style": 1,
}

PLANS["gamma"] = {
    "base": {
        "peak_rate_milli": 1000,
        "floor_rate_milli": 1000,
        "warmup_steps": 3,
        "decay_span_steps": 5,
        "restart_period_steps": 0,
    },
    "policy": {
        "default_width": 8,
        "minimum_width": 8,
        "maximum_width": 8,
        "partial_window_rule": "discard",
    },
    "phases": [{"phase": "g1", "accumulation_width": 2, "rate_scale_percent": 100}],
    "markers": [(1, "g1")],
    "exceptions": [],
    "restarts": [],
    "checkpoints": [("cg-1", 2, "", 5)],
    "cadence": {
        "log_every_steps": 2,
        "eval_every_steps": 5,
        "patience_probes": 1,
        "average_window": 0,
    },
    "probes": [],
    "shards": [("sg-1", "w41", 100, (1,), 1, "active")],
    "holdouts": [],
    "dropped": [],
    "moves": [],
    "roster": [("w41", "trainer", 2)],
    "chunk": 30,
    "overflow_at": (),
    "conflict": False,
    "twin_markers": False,
    "style": 0,
}
PLANS["delta"] = {
    "base": {
        "peak_rate_milli": 3000,
        "floor_rate_milli": 300,
        "warmup_steps": 4,
        "decay_span_steps": 10,
        "restart_period_steps": 6,
    },
    "policy": {
        "default_width": 5,
        "minimum_width": 3,
        "maximum_width": 6,
        "partial_window_rule": "discard",
    },
    "phases": [
        {"phase": "d1", "accumulation_width": 3, "rate_scale_percent": 100},
        {"phase": "d2", "accumulation_width": None, "rate_scale_percent": 95},
        {"phase": "d3", "accumulation_width": 5, "rate_scale_percent": 80},
        {"phase": "d9", "accumulation_width": 6, "rate_scale_percent": 70},
    ],
    "markers": [(1, "d1"), (18, "d2"), (44, "d3")],
    "exceptions": [
        {
            "restart_id": "rd-1",
            "accumulation_width": None,
            "rate_scale_percent": 120,
            "carry_partial": None,
        }
    ],
    "restarts": [{"restart_id": "rd-1", "at_sequence": 26, "resume_checkpoint": "cd-2"}],
    "checkpoints": [
        ("cd-1", 3, "cd-2", 8),
        ("cd-2", 10, "", 14),
        ("cd-3", 20, "", 30),
        ("cd-4", 26, "cd-3", 38),
    ],
    "cadence": {
        "log_every_steps": 3,
        "eval_every_steps": 4,
        "patience_probes": 2,
        "average_window": 3,
    },
    "probes": [
        ("pd-01", 4, 52000, "cd-1"),
        ("pd-02", 7, 51000, "cd-2"),
        ("pd-03", 8, 51000, "cd-3"),
        ("pd-04", 12, 51500, "cd-4"),
        ("pd-05", 16, 50500, "cd-2"),
    ],
    "shards": [
        ("sd-1", "w51", 600, (1,), 2, "active"),
        ("sd-2", "w52", 450, (1, 2), 4, "active"),
        ("sd-3", "w53", 240, (1,), 8, "active"),
    ],
    "holdouts": [("sd-2", 5)],
    "dropped": [("sd-1", 12)],
    "moves": [("sd-3", "w53", "w51", 22)],
    "roster": [("w51", "trainer", 5), ("w52", "trainer", 5), ("w53", "trainer", 3)],
    "chunk": 45,
    "overflow_at": (11,),
    "conflict": True,
    "twin_markers": True,
    "style": 1,
}

LANESETS = {
    "alpha": _lanes(
        [
            ("visible", None, 100, None, None, (), 1),
            ("peak", 6, 100, None, None, (), 1),
            ("steady", None, 80, 18, None, (), 1),
            ("burst", 2, 100, None, True, (), 1),
            ("latency", None, 100, None, None, ("w22",), 2),
        ]
    ),
    "beta": _lanes(
        [
            ("visible", None, 100, None, None, (), 1),
            ("peak", 5, 100, None, None, (), 1),
            ("steady", None, 95, 6, None, (), 1),
            ("burst", 2, 100, None, True, (), 1),
            ("latency", None, 100, None, None, ("w33",), 3),
        ]
    ),
    "gamma": _lanes(
        [
            ("visible", None, 100, None, None, (), 1),
            ("peak", 8, 100, None, None, (), 1),
            ("steady", None, 50, 3, None, (), 1),
            ("burst", 2, 100, None, True, (), 1),
            ("latency", None, 100, None, None, ("w41",), 2),
        ]
    ),
    "delta": _lanes(
        [
            ("visible", None, 100, None, None, (), 1),
            ("peak", 6, 100, None, None, (), 2),
            ("steady", None, 90, 20, None, (), 1),
            ("burst", 3, 100, None, True, (), 1),
            ("latency", None, 100, None, None, ("w52",), 1),
        ]
    ),
}


def _owner_now(moves: list, shard: str, seat: str, sequence: int) -> str:
    best = None
    for row in moves:
        if row[0] != shard or row[3] > sequence:
            continue
        mark = (row[3], row[2])
        if best is None or mark > best:
            best = mark
    return seat if best is None else best[1]


def _compose(tag: str) -> dict:
    spec = PLANS[tag]
    chunk = spec["chunk"]
    held = dict(spec["holdouts"])
    cut = dict(spec["dropped"])
    size = {}
    manifest = []
    blocks = []
    for shard, seat, count, passes, order, status in spec["shards"]:
        size[shard] = count - held.get(shard, 0) - cut.get(shard, 0)
        for pas in passes:
            manifest.append(
                {
                    "shard_id": shard,
                    "owner": seat,
                    "example_count": str(count),
                    "pass_index": str(pas),
                    "order_key": str(order),
                    "status": status,
                }
            )
            amount = size[shard] if size[shard] > 0 else count
            pieces = []
            left = amount
            while left > chunk:
                pieces.append(chunk)
                left -= chunk
            if left > 0:
                pieces.append(left)
            blocks.append([shard, seat, pas, pieces])
    if spec["conflict"]:
        head = spec["shards"][0]
        manifest.append(
            {
                "shard_id": head[0],
                "owner": "w88",
                "example_count": str(head[2] + 40),
                "pass_index": str(head[3][0]),
                "order_key": str(head[4] + 90),
                "status": "active",
            }
        )
    reserved = {seat for seat, _ in spec["markers"]}
    records = []
    cursor = 2
    scales = (512, 1024, 2048)
    pointer = 0
    while any(item[3] for item in blocks):
        for item in blocks:
            if not item[3]:
                continue
            while cursor in reserved:
                cursor += 1
            shard, seat, pas, pieces = item
            amount = pieces.pop(0)
            records.append(
                {
                    "record": "micro",
                    "sequence": cursor,
                    "owner": _owner_now(spec["moves"], shard, seat, cursor),
                    "shard": shard,
                    "pass_index": pas,
                    "examples": amount,
                    "loss_scale": scales[pointer % 3],
                    "overflow": 1 if pointer in spec["overflow_at"] else 0,
                }
            )
            cursor += 1
            pointer += 1
    for seat, phase in spec["markers"]:
        records.append({"record": "marker", "sequence": seat, "kind": "phase_open", "phase": phase})
    if spec["twin_markers"]:
        twin = spec["markers"][1]
        records.append({"record": "marker", "sequence": twin[0], "kind": "phase_open", "phase": "d9"})
    return {
        "spec": spec,
        "size": size,
        "manifest": manifest,
        "blocks": blocks,
        "records": records,
        "cursor": cursor,
        "held": held,
        "cut": cut,
    }


def _rough(bundle: dict) -> None:
    spec = bundle["spec"]
    if not spec["moves"]:
        return
    cursor = bundle["cursor"]
    head = spec["shards"][0]
    moved = spec["moves"][0]
    plain = {"record": "micro", "loss_scale": 1024, "overflow": 0, "pass_index": head[3][0]}
    rows = bundle["records"]
    rows.append(dict(plain, sequence=cursor, owner="w99", shard=head[0], examples=12))
    rows.append(dict(plain, sequence=cursor + 1, owner=moved[1], shard=moved[0], examples=12))
    rows.append(
        dict(plain, sequence=cursor + 2, owner=head[1], shard=head[0], examples=12, loss_scale=1000)
    )
    stray = dict(plain, sequence=cursor + 3, owner=head[1], shard=head[0], examples=12)
    stray["note"] = "late"
    rows.append(stray)
    rows.append(dict(plain, sequence=cursor + 4, owner=head[1], shard=head[0], examples=99999))
    rows.append(dict(plain, sequence=cursor + 5, owner=head[1], shard="zz-9", examples=12))
    rows.append(dict(plain, sequence=cursor + 1, owner="w98", shard=moved[0], examples=12))
    bundle["cursor"] = cursor + 6
    if spec.get("precedence_probes"):
        retired = spec["shards"][2]
        rows.append(dict(plain, sequence=cursor + 6, owner="w97", shard=retired[0], examples=12))
        rows.append(dict(plain, sequence=cursor + 7, owner=head[1], shard=head[0], examples=12,
                         loss_scale=1000, overflow=1))
        bundle["cursor"] = cursor + 8


def _archive(tag: str) -> dict:
    bundle = _compose(tag)
    _rough(bundle)
    spec = bundle["spec"]
    docs = {
        "schedule_base": dict(spec["base"], document="schedule_base"),
        "schedule_phases": {"document": "schedule_phases", "phases": spec["phases"]},
        "restart_exceptions": {"document": "restart_exceptions", "exceptions": spec["exceptions"]},
        "accumulation_policy": dict(spec["policy"], document="accumulation_policy"),
        "profiles": {"document": "profiles", "profiles": LANESETS[tag]},
        "cadence": dict(spec["cadence"], document="cadence"),
        "eval_probes": {
            "document": "eval_probes",
            "probes": [
                {"probe": name, "step": step, "metric_milli": value, "checkpoint": mark}
                for name, step, value, mark in spec["probes"]
            ],
        },
        "restarts": {"document": "restarts", "restarts": spec["restarts"]},
    }
    holdouts = []
    for shard, count in spec["holdouts"]:
        for index in range(count):
            holdouts.append(
                {
                    "example_id": shard + "-h" + str(index + 1),
                    "shard_id": shard,
                    "reason": "eval_split",
                }
            )
    duplicates = []
    for shard, count in spec["dropped"]:
        for index in range(count):
            duplicates.append(
                {
                    "group_id": shard + "-g" + str(index + 1),
                    "shard_id": shard,
                    "example_id": shard + "-d" + str(index + 1),
                    "keep": "0",
                }
            )
        duplicates.append(
            {
                "group_id": shard + "-g0",
                "shard_id": shard,
                "example_id": shard + "-d0",
                "keep": "1",
            }
        )
    tables = {
        "manifest": bundle["manifest"],
        "moves": [
            {
                "shard_id": row[0],
                "from_owner": row[1],
                "to_owner": row[2],
                "effective_sequence": str(row[3]),
            }
            for row in spec["moves"]
        ],
        "roster": [
            {"owner": row[0], "role": row[1], "slots": str(row[2])} for row in spec["roster"]
        ],
        "checkpoints": [
            {
                "checkpoint": row[0],
                "micro_cursor": str(row[1]),
                "superseded_by": row[2],
                "written_at_sequence": str(row[3]),
            }
            for row in spec["checkpoints"]
        ],
        "holdouts": holdouts,
        "duplicates": duplicates,
    }
    return {"docs": docs, "tables": tables, "records": bundle["records"], "lanes": LANESETS[tag]}


def _put(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o644)


def _sheet(rows: list, columns: list) -> str:
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(str(row[name]) for name in columns))
    return "\n".join(lines) + "\n"


COLUMNS = {
    "manifest": ["shard_id", "owner", "example_count", "pass_index", "order_key", "status"],
    "moves": ["shard_id", "from_owner", "to_owner", "effective_sequence"],
    "roster": ["owner", "role", "slots"],
    "checkpoints": ["checkpoint", "micro_cursor", "superseded_by", "written_at_sequence"],
    "holdouts": ["example_id", "shard_id", "reason"],
    "duplicates": ["group_id", "shard_id", "example_id", "keep"],
}


def _stage(tag: str, root: pathlib.Path) -> dict:
    archive = _archive(tag)
    style = PLANS[tag]["style"]
    doc_tag = "cfg_" if style == 0 else "zdoc_"
    tab_tag = "tab_" if style == 0 else "ytab_"
    log_tag = "blk_" if style == 0 else "xblk_"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o755)
    for index, key in enumerate(sorted(archive["docs"])):
        _put(root / (doc_tag + str(index + 11) + ".json"), _flat(archive["docs"][key]) + "\n")
    slot = 20
    for role in sorted(archive["tables"]):
        rows = archive["tables"][role]
        columns = COLUMNS[role]
        if role == "manifest":
            buckets = [[], [], []]
            for position, row in enumerate(rows):
                buckets[position % 3].append(row)
            for piece in buckets:
                _put(root / (tab_tag + str(slot) + ".csv"), _sheet(piece, columns))
                slot += 1
        else:
            _put(root / (tab_tag + str(slot) + ".csv"), _sheet(rows, columns))
            slot += 1
    spread = [[] for _ in range(9)]
    for position, row in enumerate(archive["records"]):
        spread[(position * 7) % 9].append(_flat(row))
    for index, lines in enumerate(spread):
        body = "\n".join(reversed(lines))
        _put(root / (log_tag + str(index + 40) + ".jsonl"), body + "\n" if body else "")
    return archive


def _rounded(num: int, den: int, box: list) -> int:
    if den == 0:
        box[0] += 1
        return 0
    whole, rest = divmod(num, den)
    doubled = rest * 2
    if doubled > den:
        return whole + 1
    if doubled < den:
        return whole
    return whole if whole % 2 == 0 else whole + 1


def _pct(value: int, share: int, box: list) -> int:
    return _rounded(value * share, 100, box)


def _seatmap(moves: list, shard: str, seat: str, when: int) -> str:
    picked = None
    for row in moves:
        if row["shard_id"] != shard:
            continue
        mark = int(row["effective_sequence"])
        if mark <= when and (picked is None or (mark, row["to_owner"]) > picked):
            picked = (mark, row["to_owner"])
    return seat if picked is None else picked[1]


def _phase_at(line: list, when: int) -> str:
    found = ""
    for mark, label in line:
        if mark <= when:
            found = label
    return found


def _exception_at(line: list, plan: list, when: int) -> dict:
    kept = None
    for entry in sorted(plan, key=lambda item: int(item["at_sequence"])):
        start = int(entry["at_sequence"])
        if start > when:
            continue
        if not any(start < mark <= when for mark, _ in line):
            kept = entry
    return kept


def _powered(value: int) -> bool:
    return value >= 64 and value <= 65536 and value & (value - 1) == 0


def _width_for(lane: dict, phase: dict, waiver: dict, policy: dict) -> int:
    choice = None
    if lane.get("width_override") is not None:
        choice = lane["width_override"]
    elif waiver is not None and waiver.get("accumulation_width") is not None:
        choice = waiver["accumulation_width"]
    elif phase is not None and phase.get("accumulation_width") is not None:
        choice = phase["accumulation_width"]
    else:
        choice = policy["default_width"]
    choice = max(policy["minimum_width"], int(choice))
    return min(policy["maximum_width"], choice)


def _carry_for(lane: dict, waiver: dict, policy: dict) -> bool:
    if lane.get("carry_partial") is not None:
        return bool(lane["carry_partial"])
    if waiver is not None and waiver.get("carry_partial") is not None:
        return bool(waiver["carry_partial"])
    return policy["partial_window_rule"] == "carry"


def _pace(index: int, phase: dict, waiver: dict, base: dict, lane: dict, box: list) -> int:
    top = base["peak_rate_milli"]
    bottom = base["floor_rate_milli"]
    ramp = base["warmup_steps"]
    reach = lane["decay_span_steps"] if lane.get("decay_span_steps") is not None else base["decay_span_steps"]
    cycle = base["restart_period_steps"]
    if index <= ramp:
        value = _rounded(top * index, ramp, box)
    else:
        gone = index - ramp
        if cycle > 0:
            gone = ((gone - 1) % cycle) + 1
        value = top - _rounded((top - bottom) * min(gone, reach), reach, box)
    if phase is not None:
        value = _pct(value, phase["rate_scale_percent"], box)
    value = _pct(value, lane["rate_scale_percent"], box)
    if waiver is not None:
        value = _pct(value, waiver["rate_scale_percent"], box)
    return value


def _mirror(archive: dict, lane: dict) -> dict:
    docs = archive["docs"]
    tables = archive["tables"]
    base = docs["schedule_base"]
    policy = docs["accumulation_policy"]
    phases = {item["phase"]: item for item in docs["schedule_phases"]["phases"]}
    waivers = {item["restart_id"]: item for item in docs["restart_exceptions"]["exceptions"]}
    beat = docs["cadence"]
    probes = docs["eval_probes"]["probes"]
    restarts = docs["restarts"]["restarts"]
    box = [0]

    pool = {}
    twins = []
    for row in sorted(archive["records"], key=_flat):
        key = int(row["sequence"])
        if key in pool:
            twins.append(row)
        else:
            pool[key] = row
    chain = [pool[key] for key in sorted(pool)]
    micro = [row for row in chain if row.get("record") == "micro"]
    line = sorted(
        (int(row["sequence"]), row["phase"])
        for row in chain
        if row.get("record") == "marker" and row.get("kind") == "phase_open"
    )
    doubles = [row for row in twins if row.get("record") == "micro"]

    seats, bulk, state, blocks, clash = {}, {}, {}, set(), 0
    for row in sorted(tables["manifest"], key=lambda item: int(item["order_key"])):
        shard = row["shard_id"]
        blocks.add((shard, int(row["pass_index"])))
        trio = (row["owner"], int(row["example_count"]), row["status"])
        if shard not in seats:
            seats[shard], bulk[shard], state[shard] = trio
        elif (seats[shard], bulk[shard], state[shard]) != trio:
            clash += 1
    held, cut = {}, {}
    for row in tables["holdouts"]:
        held[row["shard_id"]] = held.get(row["shard_id"], 0) + 1
    for row in tables["duplicates"]:
        if int(row["keep"]) == 0:
            cut[row["shard_id"]] = cut.get(row["shard_id"], 0) + 1
    span = {
        shard: bulk[shard] - held.get(shard, 0) - cut.get(shard, 0) for shard in bulk
    }
    planned = sum(max(span.get(shard, 0), 0) for shard, _ in blocks)
    crew = {row["owner"] for row in tables["roster"]}
    marks = {row["checkpoint"]: row for row in tables["checkpoints"]}

    tally = {name: 0 for name in REASONS}
    volume = {name: 0 for name in REASONS}
    tally["duplicate_sequence"] = len(doubles)
    volume["duplicate_sequence"] = sum(int(row["examples"]) for row in doubles)
    taken, skipped, skipped_examples = [], 0, 0
    for row in micro:
        shard = row.get("shard", "")
        when = int(row["sequence"])
        reason = ""
        if set(row) != MICRO_FIELDS:
            reason = "unknown_field"
        elif (shard, int(row["pass_index"])) not in blocks:
            reason = "unknown_shard"
        elif state.get(shard) == "retired":
            reason = "retired_shard"
        elif span.get(shard, 0) <= 0:
            reason = "empty_shard"
        elif row["owner"] not in crew:
            reason = "unknown_owner"
        elif row["owner"] in lane["excluded_owners"]:
            reason = "owner_excluded"
        elif row["owner"] != _seatmap(tables["moves"], shard, seats[shard], when):
            reason = "owner_mismatch"
        elif int(row["examples"]) <= 0 or int(row["examples"]) > span.get(shard, 0):
            reason = "examples_out_of_range"
        elif not _powered(int(row["loss_scale"])):
            reason = "bad_loss_scale"
        if reason:
            tally[reason] += 1
            volume[reason] += int(row.get("examples", 0))
        elif int(row["overflow"]) == 1:
            skipped += 1
            skipped_examples += int(row["examples"])
        else:
            taken.append(row)
    return _ledger(
        archive, lane, base, policy, phases, waivers, beat, probes, restarts, marks,
        taken, micro, doubles, tally, volume, skipped, skipped_examples, planned, clash, box, line,
    )


def _ledger(
    archive, lane, base, policy, phases, waivers, beat, probes, restarts, marks,
    taken, micro, doubles, tally, volume, skipped, skipped_examples, planned, clash, box, line,
):
    schedule = sorted(restarts, key=lambda item: int(item["at_sequence"]))
    pulled = []
    for entry in schedule:
        anchor = marks.get(entry["resume_checkpoint"])
        if anchor is None:
            continue
        low = int(anchor["written_at_sequence"])
        high = int(entry["at_sequence"])
        pulled += [row for row in taken if low < int(row["sequence"]) < high]
        taken = [row for row in taken if not low < int(row["sequence"]) < high]
    drift = 0
    for name in sorted(marks):
        edge = int(marks[name]["written_at_sequence"])
        rebuilt = len([row for row in taken if int(row["sequence"]) <= edge])
        if rebuilt != int(marks[name]["micro_cursor"]):
            drift += 1

    waiting, carried, steps = 0, 0, []
    lost, lost_examples, fired = 0, 0, set()
    for row in taken:
        when = int(row["sequence"])
        for entry in schedule:
            tagged = entry["restart_id"]
            if tagged in fired or int(entry["at_sequence"]) > when:
                continue
            fired.add(tagged)
            if not _carry_for(lane, waivers.get(tagged), policy) and waiting > 0:
                lost += waiting
                lost_examples += carried
                waiting, carried = 0, 0
        label = _phase_at(line, when)
        active = _exception_at(line, restarts, when)
        waiver = waivers.get(active["restart_id"]) if active else None
        width = _width_for(lane, phases.get(label), waiver, policy)
        waiting += 1
        carried += int(row["examples"])
        if waiting >= width:
            steps.append(
                {
                    "index": len(steps) + 1,
                    "phase": label,
                    "exception": active["restart_id"] if active else "",
                    "examples": carried,
                }
            )
            waiting, carried = 0, 0

    curve = [
        [item["index"], _pace(item["index"], phases.get(item["phase"]), waivers.get(item["exception"]), base, lane, box)]
        for item in steps
    ]
    last = steps[-1]["index"] if steps else 0
    beats = beat["log_every_steps"]
    if beats <= 0:
        box[0] += 1
        logged = 0
    else:
        logged = last // beats
    stride = beat["eval_every_steps"] * lane["eval_cadence_scale"]
    if stride <= 0:
        box[0] += 1
        wanted = set()
    else:
        wanted = set(range(stride, last + 1, stride))
    hits, stray = [], 0
    for probe in sorted(probes, key=lambda item: (int(item["step"]), item["probe"])):
        if int(probe["step"]) in wanted:
            hits.append(probe)
        else:
            stray += 1
    absent = len(wanted) - len({int(probe["step"]) for probe in hits})

    loops = [0]
    def _settle(name: str) -> str:
        walked = [name]
        here = name
        while True:
            row = marks.get(here)
            if row is None:
                break
            nxt = row["superseded_by"].strip()
            if not nxt:
                break
            if nxt in walked:
                loops[0] += 1
                break
            walked.append(nxt)
            here = nxt
        return here

    pick = ""
    if hits:
        ranked = sorted(hits, key=lambda item: (int(item["metric_milli"]), int(item["step"]), item["probe"]))
        pick = _settle(ranked[0]["checkpoint"])
    strikes, standing, halt = 0, None, 0
    for probe in hits:
        value = int(probe["metric_milli"])
        if standing is None or value < standing:
            standing, strikes = value, 0
        else:
            strikes += 1
        halt = int(probe["step"])
        if strikes >= beat["patience_probes"]:
            break
    bag = [
        int(probe["metric_milli"])
        for probe in hits
        if int(probe["step"]) <= halt and not marks.get(probe["checkpoint"], {}).get("superseded_by", "").strip()
    ]
    window = beat["average_window"]
    chosen = bag[-window:] if window > 0 and bag else []
    blended = _rounded(sum(chosen), len(chosen), box) if chosen else _rounded(0, 0, box)

    accepted_examples = sum(int(row["examples"]) for row in taken)
    return {
        "accepted_examples": accepted_examples,
        "accepted_records": len(taken),
        "averaged_metric_milli": blended,
        "best_checkpoint": pick,
        "coverage_gap": planned - accepted_examples,
        "cursor_drift": drift,
        "discarded_partial_examples": lost_examples,
        "discarded_partial_records": lost,
        "logged_steps": logged,
        "manifest_conflict": clash,
        "matched_probes": len(hits),
        "missing_probe": absent,
        "optimizer_steps": len(steps),
        "orphan_probe": stray,
        "overflow_skipped": skipped,
        "planned_examples": planned,
        "profile": lane["name"],
        "rate_digest": _digest(curve),
        "rate_first": curve[0][1] if curve else 0,
        "rate_last": curve[-1][1] if curve else 0,
        "rate_max": max((item[1] for item in curve), default=0),
        "rate_min": min((item[1] for item in curve), default=0),
        "rate_sum": sum(item[1] for item in curve),
        "reject_counts": tally,
        "reject_examples": volume,
        "rejected_records": sum(tally.values()),
        "rolled_back_examples": sum(int(row["examples"]) for row in pulled),
        "rolled_back_records": len(pulled),
        "skipped_examples": skipped_examples,
        "stop_step": halt,
        "supersession_cycle": loops[0],
        "total_records": len(micro) + len(doubles),
        "trailing_partial_examples": carried,
        "trailing_partial_records": waiting,
        "zero_denominator": box[0],
    }


GROUPS = {
    "ownership": ("unknown_owner", "owner_excluded", "owner_mismatch"),
    "validation": (
        "duplicate_sequence",
        "unknown_field",
        "unknown_shard",
        "retired_shard",
        "empty_shard",
        "examples_out_of_range",
        "bad_loss_scale",
    ),
}


def _stages(found: dict) -> list:
    rows = []
    for stage in sorted(GROUPS):
        rows.append(
            {
                "stage": stage,
                "records_removed": sum(found["reject_counts"][name] for name in GROUPS[stage]),
                "examples_removed": sum(found["reject_examples"][name] for name in GROUPS[stage]),
            }
        )
    rows.append(
        {
            "stage": "rollback",
            "records_removed": found["rolled_back_records"],
            "examples_removed": found["rolled_back_examples"],
        }
    )
    rows.append(
        {
            "stage": "partial_discard",
            "records_removed": found["discarded_partial_records"],
            "examples_removed": found["discarded_partial_examples"],
        }
    )
    rows.append(
        {
            "stage": "trailing",
            "records_removed": found["trailing_partial_records"],
            "examples_removed": found["trailing_partial_examples"],
        }
    )
    rows.sort(key=lambda item: (-item["records_removed"], item["stage"]))
    return rows


def _worst(found: dict) -> str:
    counts = found["reject_counts"]
    if not any(counts.values()):
        return "none"
    return sorted(counts, key=lambda name: (-counts[name], name))[0]


RULE_ORDER = (
    "align-restart-to-window",
    "shorten-checkpoint-interval",
    "freeze-shard-moves",
    "restore-probe-cadence",
    "retire-stray-probes",
    "lower-loss-scale",
    "pad-final-window",
    "repair-schedule-spans",
    "reconcile-shard-plan",
)


def _codes(found: dict) -> list:
    picked = []
    if found["discarded_partial_records"] > 0:
        picked.append("align-restart-to-window")
    if found["rolled_back_records"] > 0:
        picked.append("shorten-checkpoint-interval")
    if found["reject_counts"]["owner_mismatch"] > 0:
        picked.append("freeze-shard-moves")
    if found["missing_probe"] > 0:
        picked.append("restore-probe-cadence")
    if found["orphan_probe"] > 0:
        picked.append("retire-stray-probes")
    if found["overflow_skipped"] * 100 > found["accepted_records"] * 5:
        picked.append("lower-loss-scale")
    if found["trailing_partial_records"] > 0:
        picked.append("pad-final-window")
    if found["zero_denominator"] > 0:
        picked.append("repair-schedule-spans")
    if found["coverage_gap"] != 0:
        picked.append("reconcile-shard-plan")
    return picked if picked else ["hold-current-plan"]


def _expected(tag: str, root: pathlib.Path) -> dict:
    archive = _stage(tag, root)
    return {lane["name"]: _mirror(archive, lane) for lane in archive["lanes"]}


def _scored(tag: str, place: pathlib.Path) -> tuple:
    source = place / ("src_" + tag)
    target = place / ("dst_" + tag)
    wanted = _expected(tag, source)
    ok = _invoke(source, target)
    return wanted, target, ok


_VAULT: dict = {}


def _bundle(tag: str) -> tuple:
    if tag not in _VAULT:
        place = pathlib.Path(tempfile.mkdtemp(prefix="cf" + tag))
        place.chmod(0o755)
        _VAULT[tag] = _scored(tag, place)
    return _VAULT[tag]


def _agrees(found: dict, body: dict, names: tuple) -> bool:
    return all(body.get(name) == found[name] for name in names)


def _lane_bodies(folder: pathlib.Path) -> dict:
    return {name: _gather(folder, "scenario_" + name + ".json") for name in LANES}


@criterion(description="All ten deliverables exist under the output directory and carry content")
def e_artifacts_present(workspace) -> bool:
    try:
        if not PROGRAM.is_file() or PROGRAM.stat().st_size == 0:
            return False
        return all((OUT / name).is_file() and (OUT / name).stat().st_size > 0 for name in REPORTS)
    except OSError:
        return False


@criterion(description="Every report parses as a JSON object that names its own document kind")
def e_reports_parse(workspace) -> bool:
    try:
        for name in REPORTS:
            body = _load(name)
            if not isinstance(body.get("document"), str) or not body["document"]:
                return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="No report holds a floating point value anywhere in its structure")
def e_integers_only(workspace) -> bool:
    try:
        return all(_no_floats(_load(name)) for name in REPORTS)
    except (OSError, ValueError):
        return False


@criterion(description="Every report file holds the canonical serialization of its body plus one newline")
def e_canonical_bytes(workspace) -> bool:
    try:
        for name in REPORTS:
            raw = (OUT / name).read_text(encoding="utf-8")
            if raw != _flat(json.loads(raw)) + "\n":
                return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="The delivered program runs on a fresh run archive and emits the nine reports")
def e_program_runs(workspace) -> bool:
    try:
        _, folder, ok = _bundle("gamma")
        if not ok:
            return False
        return all((folder / name).is_file() for name in REPORTS)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


@criterion(description="Each lane report states the settled record ledger of the shipped archive")
def h_visible_ledger(workspace) -> bool:
    try:
        for name in LANES:
            body = _load("scenario_" + name + ".json")
            for field, value in LEDGER[name].items():
                if body.get(field) != value:
                    return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="Each lane report states the schedule curve summary of the shipped archive")
def h_visible_rates(workspace) -> bool:
    try:
        for name in LANES:
            body = _load("scenario_" + name + ".json")
            for field, value in CURVE[name].items():
                if body.get(field) != value:
                    return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="Each lane report states the probe cadence outcome and the selection result")
def h_visible_probes(workspace) -> bool:
    try:
        for name in LANES:
            body = _load("scenario_" + name + ".json")
            seen = (
                body.get("matched_probes"),
                body.get("missing_probe"),
                body.get("orphan_probe"),
                body.get("best_checkpoint"),
                body.get("stop_step"),
                body.get("averaged_metric_milli"),
            )
            if seen != PROBE[name]:
                return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="The wide window lane attributes its loss to the discarded partial window stage")
def h_peak_split(workspace) -> bool:
    # Stage ordering for every lane is graded once, by h_bottleneck_rank.
    try:
        body = _load("bottleneck_analysis.json")
        lane = body["profiles"]["peak"]
        if lane.get("dominant_stage") != "partial_discard":
            return False
        head = lane["stages"][0]
        return head["records_removed"] == 2 and head["examples_removed"] == 96
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False


@criterion(description="The lane that bars one worker reports the reduced ledger and the cursor drift")
def h_latency_exclusion(workspace) -> bool:
    try:
        body = _load("scenario_latency.json")
        audit = _load("data_quality.json")["profiles"]["latency"]
        if body.get("reject_counts", {}).get("owner_excluded") != 26:
            return False
        if (body.get("accepted_records"), body.get("accepted_examples")) != (98, 4660):
            return False
        if body.get("cursor_drift") != 6:
            return False
        cover = audit["coverage"]
        return cover == {
            "accepted_examples": 4660,
            "coverage_gap": 1378,
            "planned_examples": 6038,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return False


@criterion(description="Every report carries the self describing fingerprint of its finished body")
def h_visible_fingerprints(workspace) -> bool:
    try:
        for name in REPORTS:
            body = _load(name)
            if not _sealed(body) or body.get("body_fingerprint") != SEAL[name]:
                return False
        return True
    except (OSError, ValueError):
        return False


@criterion(description="The cross lane report states the signed deltas and the run wide totals")
def h_perf_deltas(workspace) -> bool:
    try:
        body = _load("perf_report.json")
        for name, pair in DELTAS.items():
            entry = body["deltas_vs_visible"][name]
            if (entry["accepted_examples_delta"], entry["optimizer_steps_delta"]) != pair:
                return False
        if body["totals"] != TOTALS:
            return False
        return body["identity_checks"] == {
            "coverage_gap_total": 1954,
            "partition_holds": 1,
            "profiles_checked": 5,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return False


@criterion(description="The stage attribution ranks every lane by removed records with the named order")
def h_bottleneck_rank(workspace) -> bool:
    try:
        body = _load("bottleneck_analysis.json")["profiles"]
        for name in LANES:
            if tuple(item["stage"] for item in body[name]["stages"]) != STAGE_ORDER[name]:
                return False
        if body["visible"]["dominant_reason"] != "none":
            return False
        return body["latency"]["dominant_reason"] == "owner_excluded"
    except (OSError, ValueError, KeyError, TypeError):
        return False


@criterion(description="The recommendation codes follow the documented rule order for every lane")
def h_recommend_codes(workspace) -> bool:
    try:
        body = _load("recommendations.json")
        shape = {
            "visible": QUIET_CODES,
            "steady": QUIET_CODES,
            "burst": QUIET_CODES,
            "peak": SPLIT_CODES,
            "latency": SPLIT_CODES,
        }
        for name, codes in shape.items():
            if body["per_profile"][name] != codes:
                return False
        return body["codes"] == MERGED_CODES
    except (OSError, ValueError, KeyError, TypeError):
        return False


@criterion(description="The quality account balances the record partition and the example coverage")
def h_quality_identities(workspace) -> bool:
    try:
        body = _load("data_quality.json")["profiles"]
        for name in LANES:
            lane = body[name]
            if set(lane["reject_counts"]) != set(REASONS):
                return False
            part = lane["partition"]
            total = (
                part["accepted_records"]
                + part["rejected_records"]
                + part["rolled_back_records"]
                + part["skipped_records"]
            )
            if total != part["total_records"] or part["holds"] != 1:
                return False
            if part["total_records"] != 127:
                return False
        quiet = body["visible"]
        return quiet["partition"]["accepted_records"] == 124 and quiet["coverage"][
            "planned_examples"
        ] == 6038
    except (OSError, ValueError, KeyError, TypeError):
        return False


CORE_FIELDS = (
    "accepted_records",
    "accepted_examples",
    "optimizer_steps",
    "total_records",
    "rolled_back_records",
    "rolled_back_examples",
    "discarded_partial_records",
    "discarded_partial_examples",
    "trailing_partial_records",
    "trailing_partial_examples",
)
CURVE_FIELDS = (
    "rate_first",
    "rate_last",
    "rate_min",
    "rate_max",
    "rate_sum",
    "rate_digest",
    "logged_steps",
    "zero_denominator",
)
PICK_FIELDS = (
    "matched_probes",
    "missing_probe",
    "orphan_probe",
    "best_checkpoint",
    "stop_step",
    "averaged_metric_milli",
    "supersession_cycle",
)


def _compare(tag: str, fields: tuple) -> bool:
    wanted, folder, ok = _bundle(tag)
    if not ok:
        return False
    bodies = _lane_bodies(folder)
    return all(_agrees(wanted[name], bodies[name], fields) for name in LANES)


ALL_FIELDS = CORE_FIELDS + CURVE_FIELDS + PICK_FIELDS
TAGS = ("alpha", "beta", "gamma", "delta")


@criterion(description="An unseen run archive yields the settled ledger for every lane")
def h_hidden_alpha_core(workspace) -> bool:
    try:
        return _compare("alpha", CORE_FIELDS)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="An unseen run archive yields the refusal account and the balanced partition")
def h_hidden_alpha_faults(workspace) -> bool:
    try:
        wanted, folder, ok = _bundle("alpha")
        if not ok:
            return False
        audit = _gather(folder, "data_quality.json")["profiles"]
        bodies = _lane_bodies(folder)
        for name in LANES:
            mark = wanted[name]
            if bodies[name].get("reject_counts") != mark["reject_counts"]:
                return False
            lane = audit[name]
            if lane.get("manifest_conflict") != mark["manifest_conflict"]:
                return False
            if lane.get("overflow_skipped") != mark["overflow_skipped"]:
                return False
            part = lane["partition"]
            if part["accepted_records"] != mark["accepted_records"]:
                return False
            if part["rejected_records"] != mark["rejected_records"]:
                return False
            if part["rolled_back_records"] != mark["rolled_back_records"]:
                return False
            if part["total_records"] != mark["total_records"]:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="An unseen run archive yields the schedule curve for every lane")
def h_hidden_alpha_schedule(workspace) -> bool:
    try:
        return _compare("alpha", CURVE_FIELDS)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="An unseen run archive yields the probe match and the checkpoint selection")
def h_hidden_alpha_selection(workspace) -> bool:
    try:
        return _compare("alpha", PICK_FIELDS)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="A run archive with vanishing schedule spans yields the stated fallback values")
def h_hidden_beta_degenerate(workspace) -> bool:
    try:
        return _compare("beta", ALL_FIELDS)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="A run archive too short to close a window yields an empty step ledger")
def h_hidden_gamma_empty(workspace) -> bool:
    try:
        return _compare("gamma", ALL_FIELDS)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="A run archive with scattered sequences and a clashing plan row yields the stated ledger")
def h_hidden_delta_order(workspace) -> bool:
    try:
        return _compare("delta", ALL_FIELDS)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="Reports for unseen archives stay canonical and carry a matching fingerprint")
def h_hidden_seals(workspace) -> bool:
    try:
        for tag in TAGS:
            _, folder, ok = _bundle(tag)
            if not ok:
                return False
            for name in REPORTS:
                raw = (folder / name).read_text(encoding="utf-8")
                body = json.loads(raw)
                if raw != _flat(body) + "\n" or not _sealed(body):
                    return False
                if not _no_floats(body):
                    return False
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


@criterion(description="Roll up reports for unseen archives agree with the lane reports they summarise")
def h_hidden_rollups(workspace) -> bool:
    try:
        for tag in TAGS:
            wanted, folder, ok = _bundle(tag)
            if not ok:
                return False
            summary = _gather(folder, "perf_report.json")
            stages = _gather(folder, "bottleneck_analysis.json")["profiles"]
            advice = _gather(folder, "recommendations.json")
            audit = _gather(folder, "data_quality.json")["profiles"]
            union = set()
            for name in LANES:
                mark = wanted[name]
                if summary["profiles"][name]["optimizer_steps"] != mark["optimizer_steps"]:
                    return False
                if summary["profiles"][name]["best_checkpoint"] != mark["best_checkpoint"]:
                    return False
                if name != "visible":
                    gap = summary["deltas_vs_visible"][name]
                    base = wanted["visible"]
                    if gap["optimizer_steps_delta"] != mark["optimizer_steps"] - base["optimizer_steps"]:
                        return False
                if stages[name]["stages"] != _stages(mark):
                    return False
                if stages[name]["dominant_reason"] != _worst(mark):
                    return False
                codes = _codes(mark)
                if advice["per_profile"][name] != codes:
                    return False
                union |= {code for code in codes if code in RULE_ORDER}
                if audit[name]["coverage"]["coverage_gap"] != mark["coverage_gap"]:
                    return False
            merged = [code for code in RULE_ORDER if code in union]
            if advice["codes"] != (merged if merged else ["hold-current-plan"]):
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


@criterion(description="Each unseen archive run leaves exactly the nine named reports in the output directory")
def h_hidden_output_set(workspace) -> bool:
    try:
        for tag in TAGS:
            _, folder, ok = _bundle(tag)
            if not ok:
                return False
            if sorted(item.name for item in folder.iterdir()) != sorted(REPORTS):
                return False
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


@criterion(description="The delivered program reproduces the shipped archive figures on an unrelated archive")
def negative_hardcoded_sample_answers(workspace) -> bool:
    # Inverted polarity: return True only when this prohibited behavior is detected.
    try:
        for tag in TAGS:
            _, folder, ok = _bundle(tag)
            if not ok:
                continue
            body = _gather(folder, "scenario_visible.json")
            if body.get("total_records") == 127 and body.get("optimizer_steps") == 30:
                return True
            if body.get("body_fingerprint") == SEAL["scenario_visible.json"]:
                return True
        return False
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


@criterion(description="The delivered program changes its answer when the same archive is renamed")
def negative_filename_dependent_behaviour(workspace) -> bool:
    # Inverted polarity: return True only when this prohibited behavior is detected.
    try:
        _, first, ok = _bundle("alpha")
        if not ok:
            return False
        place = pathlib.Path(tempfile.mkdtemp(prefix="cfrename"))
        place.chmod(0o755)
        source = place / "src"
        target = place / "dst"
        source.mkdir()
        source.chmod(0o755)
        origin = pathlib.Path(str(first).replace("dst_alpha", "src_alpha"))
        groups: dict = {}
        for item in sorted(origin.iterdir()):
            groups.setdefault(item.suffix, []).append(item)
        for suffix, items in groups.items():
            names = [item.name for item in items]
            for position, item in enumerate(items):
                _put(source / names[(position + 1) % len(names)], item.read_text(encoding="utf-8"))
        if not _invoke(source, target):
            return False
        for name in REPORTS:
            if (target / name).read_bytes() != (first / name).read_bytes():
                return True
        return False
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


@criterion(description="The delivered program emits different bytes on two runs over one archive")
def negative_nondeterministic_output(workspace) -> bool:
    # Inverted polarity: return True only when this prohibited behavior is detected.
    try:
        _, first, ok = _bundle("beta")
        if not ok:
            return False
        origin = pathlib.Path(str(first).replace("dst_beta", "src_beta"))
        second = pathlib.Path(tempfile.mkdtemp(prefix="cfrepeat")) / "dst"
        second.parent.chmod(0o755)
        if not _invoke(origin, second):
            return False
        for name in REPORTS:
            if (second / name).read_bytes() != (first / name).read_bytes():
                return True
        return False
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


@criterion(description="The output directory holds an import hook that rebinds the checking dependencies")
def negative_rebinds_verifier_dependencies(workspace) -> bool:
    # Inverted polarity: return True only when this prohibited behavior is detected.
    try:
        planted = ("sitecustomize.py", "usercustomize.py", "conftest.py", "rewardkit")
        for folder in (OUT, OUT.parent):
            if not folder.is_dir():
                continue
            for item in folder.iterdir():
                if item.name in planted:
                    return True
        return False
    except OSError:
        return False


criteria.e_artifacts_present(weight=1)
criteria.e_reports_parse(weight=1)
criteria.e_integers_only(weight=1)
criteria.e_canonical_bytes(weight=1)
criteria.e_program_runs(weight=3)
criteria.h_visible_ledger(weight=3)
criteria.h_visible_rates(weight=3)
criteria.h_visible_probes(weight=3)
criteria.h_peak_split(weight=3)
criteria.h_latency_exclusion(weight=3)
criteria.h_visible_fingerprints(weight=5)
criteria.h_perf_deltas(weight=3)
criteria.h_bottleneck_rank(weight=3)
criteria.h_recommend_codes(weight=3)
criteria.h_quality_identities(weight=3)
criteria.h_hidden_alpha_core(weight=5)
criteria.h_hidden_alpha_faults(weight=5)
criteria.h_hidden_alpha_schedule(weight=5)
criteria.h_hidden_alpha_selection(weight=5)
criteria.h_hidden_beta_degenerate(weight=5)
criteria.h_hidden_gamma_empty(weight=5)
criteria.h_hidden_delta_order(weight=5)
criteria.h_hidden_seals(weight=5)
criteria.h_hidden_rollups(weight=5)
criteria.h_hidden_output_set(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-1)
