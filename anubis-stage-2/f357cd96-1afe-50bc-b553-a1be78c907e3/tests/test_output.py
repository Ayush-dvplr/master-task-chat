"""Verifier for the HTTP/3 fleet migration scheduling task.

Runs the agent-delivered scheduler against independently reviewed golden
results for the shipped corpus, discriminating fixtures, four hidden seeded
scenarios, and five sealed cases. It also verifies output hygiene, integrity
chaining, and concrete hardcoding, filename, float, scratch-file,
nondeterminism, and hollow-program failures.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from rewardkit import criteria, criterion

_EMBEDDED_DATA_B64 = (
    "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"
    "/h9jfBZRAPAAAA=="
)

def _provision_embedded_data() -> Path:
    """Decode the embedded tar.gz once per process to a stable /tmp path."""
    import base64
    import io
    import tarfile

    target = Path("/tmp/h3_verifier_data")
    marker = target / ".provisioned"
    if not marker.exists():
        target.mkdir(parents=True, exist_ok=True)
        raw = base64.b64decode(_EMBEDDED_DATA_B64)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            tar.extractall(target)
        marker.write_text("ok\n", encoding="utf-8")
    return target

def _resolve_data_dir() -> Path:
    provisioned = _provision_embedded_data()
    if (provisioned / "fleet_nodes.csv").exists():
        return provisioned
    if (Path("/app/data") / "fleet_nodes.csv").exists():
        return Path("/app/data")
    return provisioned


_DATA_DIR: Path | None = None


def _data_dir() -> Path:
    """Resolve and, when needed, provision verifier data only when a test runs."""
    global _DATA_DIR
    if _DATA_DIR is None:
        _DATA_DIR = _resolve_data_dir()
    return _DATA_DIR


OUT_DIR = Path("/app/out")
SCHEDULER = Path("/app/out/reusable_scheduler.py")

CANONICAL_ARTIFACT_ORDER = (
    "schedule_matrix.json",
    "fleet_utilization.json",
    "tenant_fairness_report.json",
    "migration_ledger.json",
    "preemption_events.json",
    "sla_violation_report.json",
    "objective_breakdown.json",
    "fixed_point_trace.json",
)
ALL_ARTIFACTS = CANONICAL_ARTIFACT_ORDER + ("integrity_manifest.json", "final_state.json")

LARGEST_REMAINDER_TIE = "by_tenant_id_asc"
FLOOR_APPLICATION_ORDER = "floors_before_cap"
SLO_COMPARISON = "strict_lt"
BUCKET_REFILL_ROUNDING = "floor"


def _canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _round_frac(num: int, den: int, mode: str) -> int:
    if mode == "floor":
        return num // den
    if mode == "ceil":
        return -(-num // den)
    if mode == "banker":
        q, r = divmod(num, den)
        two_r = 2 * r
        if two_r < den:
            return q
        if two_r > den:
            return q + 1
        return q if q % 2 == 0 else q + 1
    raise ValueError(mode)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_case(case_path: Path, out_dir: Path) -> Path:
    case = _read_json(case_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, body in case["files"].items():
        (out_dir / name).write_text(body, encoding="utf-8")
    return out_dir


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


_UNPRIVILEGED_UID = 65534
_UNPRIVILEGED_GID = 65534


def _privilege_drop_prefix() -> list:
    """Command prefix that runs agent-produced code as an unprivileged user.

    Agent artifacts are executed during grading; dropping to nobody (paired with
    a root-owned locked log directory and go-rwx /tests) stops that code from
    reading the answer key or overwriting grader outputs. Returns an empty
    prefix off Linux or when the grader is not root, leaving behaviour unchanged.
    """
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return []
    if shutil.which("setpriv") is None:
        return []
    return [
        "setpriv",
        f"--reuid={_UNPRIVILEGED_UID}",
        f"--regid={_UNPRIVILEGED_GID}",
        "--clear-groups",
    ]


def _grant_access(path: Path, writable: bool) -> None:
    dir_mode = 0o777 if writable else 0o755
    file_mode = 0o666 if writable else 0o644
    try:
        os.chmod(path, dir_mode)
        for root, dirs, files in os.walk(path):
            for name in dirs:
                try:
                    os.chmod(Path(root) / name, dir_mode)
                except OSError:
                    pass
            for name in files:
                try:
                    os.chmod(Path(root) / name, file_mode)
                except OSError:
                    pass
    except OSError:
        pass


def _grant_traversal(path: Path) -> None:
    """Add world-execute to every ancestor of `path` so the dropped-privilege
    scheduler can traverse into it. tempfile.TemporaryDirectory() creates its
    root at mode 0700 owned by root, which otherwise blocks the unprivileged
    user from reaching the fixture data and output directories nested under it.
    Execute-only is safe: it grants directory traversal, never read or write."""
    try:
        tmp_root = Path(tempfile.gettempdir()).resolve()
    except OSError:
        tmp_root = None
    current = path.resolve()
    while True:
        parent = current.parent
        if parent == current:
            break
        try:
            os.chmod(parent, os.stat(parent).st_mode | 0o111)
        except OSError:
            pass
        if tmp_root is not None and parent == tmp_root:
            break
        current = parent


def _run_agent(data_dir: Path, out_dir: Path, scheduler: Path = SCHEDULER) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = _privilege_drop_prefix()
    if prefix:
        _grant_access(data_dir, writable=False)
        _grant_access(out_dir, writable=True)
        _grant_traversal(data_dir)
        _grant_traversal(out_dir)
        try:
            os.chmod(scheduler, 0o644)
        except OSError:
            pass
    proc = subprocess.Popen(
        prefix + [sys.executable, str(scheduler), str(data_dir), str(out_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        _, stderr = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        proc.communicate()
        raise AssertionError(f"agent scheduler timed out on {data_dir}")
    finally:
        _kill_process_group(proc.pid)
    if proc.returncode != 0:
        raise AssertionError(
            f"agent scheduler failed on {data_dir}: rc={proc.returncode} stderr={stderr[-800:]}"
        )


INPUT_FILES = (
    "fleet_nodes.csv", "stream_manifest.csv", "tenants.csv", "qos_classes.json",
    "token_buckets.csv", "mtu_matrix.csv", "migration_penalty_table.json",
    "latency_matrix.csv", "preemption_ladder.json", "epoch_windows.csv",
    "fixed_point_constants.json", "packet_rate_profiles.csv",
)

# Reviewed expected results for the finite shipped, sealed, seeded, and fresh
# corpora. This compressed JSON is inert test data, not executable code. Keeping
# it independent from the implementation lets the verifier catch shared bugs.
_GOLDEN_RESULTS_B64 = (
    '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'
)


def _data_fingerprint(data_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in INPUT_FILES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update((data_dir / name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _golden_results() -> dict:
    import base64
    import zlib

    packed = zlib.decompress(base64.b64decode(_GOLDEN_RESULTS_B64))
    return json.loads(packed.decode("utf-8"))


_GOLDEN_RESULTS = _golden_results()


def _reference_solve(data_dir: Path) -> dict:
    fingerprint = _data_fingerprint(data_dir)
    try:
        return copy.deepcopy(_GOLDEN_RESULTS[fingerprint])
    except KeyError as exc:
        raise AssertionError(
            f"fixture has no independently reviewed golden result: {fingerprint}"
        ) from exc


def _load_agent_out(out_dir: Path = OUT_DIR) -> dict:
    return {name: _read_json(out_dir / name) for name in ALL_ARTIFACTS if (out_dir / name).exists()}


def _run_and_load(data_dir: Path):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_out = Path(tmp) / "out"
        _run_agent(data_dir, tmp_out)
        agent = {name: _read_json(tmp_out / name) for name in CANONICAL_ARTIFACT_ORDER}
        agent["integrity_manifest.json"] = _read_json(tmp_out / "integrity_manifest.json")
        agent["final_state.json"] = _read_json(tmp_out / "final_state.json")
    return agent


def _run_on_case(case_name: str) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "in"
        out_dir = Path(tmp) / "out"
        _extract_case(_data_dir() / f"case-{case_name}.json", in_dir)
        _run_agent(in_dir, out_dir)
        agent = {name: _read_json(out_dir / name) for name in CANONICAL_ARTIFACT_ORDER}
        ref = _reference_solve(in_dir)
    return agent, ref


# ============================================================
# BUCKET A -- Hygiene (4 tests)
# ============================================================

def test_artifacts_exist_and_parse():
    for name in ALL_ARTIFACTS:
        path = OUT_DIR / name
        assert path.exists() and path.stat().st_size > 0, f"missing {name}"
    for name in CANONICAL_ARTIFACT_ORDER + ("integrity_manifest.json", "final_state.json"):
        _read_json(OUT_DIR / name)
    scheduler = OUT_DIR / "reusable_scheduler.py"
    assert scheduler.exists() and scheduler.stat().st_size > 0, "missing reusable_scheduler.py"


def test_schedule_matrix_schema_is_exact():
    sched = _read_json(OUT_DIR / "schedule_matrix.json")
    assert set(sched.keys()) == {"epochs"}
    for entry in sched["epochs"]:
        assert set(entry.keys()) == {"epoch", "assignments", "preempted"}
        assert isinstance(entry["epoch"], int)
        assert isinstance(entry["assignments"], dict)
        assert entry["preempted"] == sorted(entry["preempted"])


def test_canonical_serialization_is_sorted_and_newline_terminated():
    for name in ALL_ARTIFACTS:
        raw = (OUT_DIR / name).read_bytes()
        assert raw.endswith(b"\n"), f"{name} missing trailing newline"
        payload = json.loads(raw)
        expected = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        assert raw == expected, f"{name} not canonical"


def test_reusable_scheduler_runs_on_alternate_data_directory():
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,2,small,re,2\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS101,T01,K02,0,0,3,P02\nS102,T01,K02,0,0,3,P02\n",
    })
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "alternate-data"
        out_dir = Path(tmp) / "output"
        _write_files(files, data_dir)
        _run_agent(data_dir, out_dir)
        schedule = _read_json(out_dir / "schedule_matrix.json")
        final = _read_json(out_dir / "final_state.json")
    assert schedule["epochs"][0]["assignments"] == {"S101": "N01", "S102": "N01"}
    assert final["stream_count"] == 2


# ============================================================
# BUCKET C -- Discriminating fresh fixtures (12 tests)
# ============================================================

def _fixture_files(overrides: dict, base: dict | None = None) -> dict:
    base_files = {
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,2,small,re,2\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K02,0,0,3,P02\n",
        "tenants.csv": "tenant_id,floor,ceiling,migration_mult,tenant_region\nT01,0,5,2,re\n",
        "qos_classes.json": '{"classes":[{"class_id":"K01","priority_rank":3,"slo_max_hops":2},{"class_id":"K02","priority_rank":2,"slo_max_hops":3},{"class_id":"K03","priority_rank":1,"slo_max_hops":4}]}\n',
        "token_buckets.csv": "node_id,bucket_capacity,refill_num,refill_den,refill_offset\nN01,5,1,1,0\n",
        "mtu_matrix.csv": "mtu_class,class_id,units\nsmall,K01,1\nsmall,K02,1\nsmall,K03,1\n",
        "migration_penalty_table.json": '{"base":[{"tenant":"T01","epoch":0,"base":3}]}\n',
        "latency_matrix.csv": "node_id,tenant_region,hops\nN01,re,1\n",
        "preemption_ladder.json": '{"ladder":[]}\n',
        "epoch_windows.csv": "epoch,duration_num,duration_den,warm_start\n0,1,1,\n",
        "fixed_point_constants.json": '{"alpha":5,"beta":3,"gamma":2,"damping_num":3,"damping_den":3,"tolerance":0,"max_iterations":4}\n',
        "packet_rate_profiles.csv": "profile_id,base_rate,class_hint\nP02,3,K02\n",
    }
    if base:
        base_files.update(base)
    base_files.update(overrides)
    return base_files


def _write_files(files: dict, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (dst / name).write_text(body, encoding="utf-8")


def _run_fixture(files: dict) -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "in"
        out_dir = Path(tmp) / "out"
        _write_files(files, in_dir)
        _run_agent(in_dir, out_dir)
        agent = {name: _read_json(out_dir / name) for name in CANONICAL_ARTIFACT_ORDER}
        ref = _reference_solve(in_dir)
    return agent, ref


def test_fresh_slo_boundary_is_strictly_excluded():
    # POSITIVE: A K02 stream (SLO=3 hops) must NOT be placed on a node whose latency equals 3.
    # Wrong reading `non_strict_leq` would place the stream on that node.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,1,small,rn,1\n",
        "latency_matrix.csv": "node_id,tenant_region,hops\nN01,re,3\n",
    })
    agent, ref = _run_fixture(files)
    assert ref["preemption_events.json"]["total_count"] == 1, f"reference must preempt boundary case: {ref}"
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]
    assert agent["preemption_events.json"] == ref["preemption_events.json"]


def test_fresh_largest_remainder_tie_uses_tenant_id_asc():
    # POSITIVE: Three tenants all tied on remainder for two available slots; T01 and T02 win under by_tenant_id_asc.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,1,small,re,1\nN02,1,small,re,1\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS005,T02,K02,0,0,3,P02\nS008,T03,K02,0,0,3,P02\nS010,T01,K02,0,0,3,P02\n",
        "tenants.csv": "tenant_id,floor,ceiling,migration_mult,tenant_region\nT01,0,5,2,re\nT02,0,5,2,re\nT03,0,5,2,re\n",
        "token_buckets.csv": "node_id,bucket_capacity,refill_num,refill_den,refill_offset\nN01,5,1,1,0\nN02,5,1,1,0\n",
        "latency_matrix.csv": "node_id,tenant_region,hops\nN01,re,1\nN02,re,1\n",
        "migration_penalty_table.json": '{"base":[{"tenant":"T01","epoch":0,"base":3},{"tenant":"T02","epoch":0,"base":3},{"tenant":"T03","epoch":0,"base":3}]}\n',
    })
    agent, ref = _run_fixture(files)
    admitted = set(ref["schedule_matrix.json"]["epochs"][0]["assignments"].keys())
    assert admitted == {"S005", "S010"}, f"reference under true tie rule should admit S005+S010, got {admitted}"
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]


def test_fresh_floor_applied_before_hard_cap():
    # POSITIVE: T01 floor=2 ceiling=3, T02 floor=1 ceiling=1, cap=2. floors_before_cap prunes T01 to 1 via largest-remainder; T02 keeps 1.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,2,small,re,2\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K02,0,0,3,P02\nS002,T01,K02,0,0,3,P02\nS003,T01,K02,0,0,3,P02\nS004,T02,K02,0,0,3,P02\n",
        "tenants.csv": "tenant_id,floor,ceiling,migration_mult,tenant_region\nT01,2,3,2,re\nT02,1,1,2,re\n",
        "migration_penalty_table.json": '{"base":[{"tenant":"T01","epoch":0,"base":3},{"tenant":"T02","epoch":0,"base":3}]}\n',
    })
    agent, ref = _run_fixture(files)
    admitted = set(ref["schedule_matrix.json"]["epochs"][0]["assignments"].keys())
    assert "S004" in admitted, "reference must admit T02's only stream under floors_before_cap"
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]


def test_fresh_bucket_refill_uses_floor_rounding():
    # POSITIVE: Bucket refill computes floor(2*1 / (3*1)) = 0 per epoch, so epoch 1 admits nobody.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,3,small,re,3\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K02,0,0,3,P02\nS002,T01,K02,0,0,3,P02\nS003,T01,K02,0,0,3,P02\nS004,T01,K02,1,1,3,P02\nS005,T01,K02,1,1,3,P02\n",
        "token_buckets.csv": "node_id,bucket_capacity,refill_num,refill_den,refill_offset\nN01,3,2,3,0\n",
        "migration_penalty_table.json": '{"base":[{"tenant":"T01","epoch":0,"base":3},{"tenant":"T01","epoch":1,"base":3}]}\n',
        "epoch_windows.csv": "epoch,duration_num,duration_den,warm_start\n0,1,1,\n1,1,1,\n",
    })
    agent, ref = _run_fixture(files)
    ep1_assignments = ref["schedule_matrix.json"]["epochs"][1]["assignments"]
    assert ep1_assignments == {}, f"reference under floor rounding admits nothing in epoch 1, got {ep1_assignments}"
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]


def test_fresh_migration_cost_uses_previous_epoch_assignment():
    # POSITIVE: Warm-start places S001 on N02, but N02 fails K01's SLO (latency 3 > slo cap 2), so the scheduler must move S001 to N01 and record a migration event with cost = base * mult = 3 * 2 = 6.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,1,small,re,1\nN02,1,small,rn,1\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K01,0,0,4,P01\n",
        "token_buckets.csv": "node_id,bucket_capacity,refill_num,refill_den,refill_offset\nN01,5,1,1,0\nN02,5,1,1,0\n",
        "latency_matrix.csv": "node_id,tenant_region,hops\nN01,re,1\nN02,re,3\n",
        "epoch_windows.csv": "epoch,duration_num,duration_den,warm_start\n0,1,1,S001=N02\n",
        "packet_rate_profiles.csv": "profile_id,base_rate,class_hint\nP01,4,K01\n",
    })
    agent, ref = _run_fixture(files)
    ref_events = ref["migration_ledger.json"]["events"]
    assert len(ref_events) == 1, f"expected 1 migration event, got {ref_events}"
    assert ref_events[0]["from"] == "N02" and ref_events[0]["to"] == "N01"
    assert agent["migration_ledger.json"] == ref["migration_ledger.json"]


def test_fresh_preemption_cascade_terminates_after_one_hop():
    # POSITIVE: Equal numeric ranks make tenant order place K03, K02, K02, then K01.
    # The node scan must skip N01, whose K03 is not a K01 victim, and use N02. Its
    # two equal-cost K02 victims exercise the stream-ID tie-break. A forbidden
    # recursive retry would then let the evicted K02 displace K03 on N01.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,2,small,re,1\nN02,2,small,re,2\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K03,0,0,2,P03\nS002,T02,K02,0,0,3,P02\nS004,T03,K02,0,0,3,P02\nS003,T04,K01,0,0,4,P01\n",
        "tenants.csv": "tenant_id,floor,ceiling,migration_mult,tenant_region\nT01,0,5,2,re\nT02,0,5,2,re\nT03,0,5,2,re\nT04,0,5,2,re\n",
        "qos_classes.json": '{"classes":[{"class_id":"K01","priority_rank":3,"slo_max_hops":4},{"class_id":"K02","priority_rank":3,"slo_max_hops":4},{"class_id":"K03","priority_rank":3,"slo_max_hops":4}]}\n',
        "token_buckets.csv": "node_id,bucket_capacity,refill_num,refill_den,refill_offset\nN01,10,1,1,0\nN02,10,1,1,0\n",
        "latency_matrix.csv": "node_id,tenant_region,hops\nN01,re,1\nN02,re,1\n",
        "preemption_ladder.json": '{"ladder":[{"preemptor":"K01","victim":"K02"},{"preemptor":"K02","victim":"K03"}]}\n',
        "packet_rate_profiles.csv": "profile_id,base_rate,class_hint\nP01,4,K01\nP02,3,K02\nP03,2,K03\n",
    })
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        out_dir = Path(tmp) / "out"
        _write_files(files, data_dir)
        _run_agent(data_dir, out_dir)
        schedule = _read_json(out_dir / "schedule_matrix.json")
        events = _read_json(out_dir / "preemption_events.json")
    assert schedule["epochs"][0]["assignments"] == {"S001": "N01", "S003": "N02", "S004": "N02"}
    assert schedule["epochs"][0]["preempted"] == ["S002"]
    assert events == {
        "events": [{"beneficiary": "S003", "class": "K02", "epoch": 0,
                    "reason": "cascade_evicted", "victim": "S002"}],
        "total_count": 1,
    }


def test_shipped_fixed_point_trace_converges_within_tolerance():
    # POSITIVE: the flat, global trace matches the reviewed result and ends converged.
    ref = _reference_solve(_data_dir())
    trace = ref["fixed_point_trace.json"]
    assert trace["converged"] is True
    assert len(trace["iterations"]) >= 1
    agent_trace = _read_json(OUT_DIR / "fixed_point_trace.json")
    assert agent_trace["converged"] is True
    assert agent_trace == trace


def test_shipped_tenant_report_has_every_epoch():
    # POSITIVE: A tenant with zero active streams in a given epoch must produce an epoch entry with admitted=0, target=0, deviation=0 (no missing key).
    ref = _reference_solve(_data_dir())
    agent = _read_json(OUT_DIR / "tenant_fairness_report.json")
    tenants = ref["tenant_fairness_report.json"]["tenants"]
    epoch_count = ref["_epoch_count"]
    for entry in tenants:
        assert len(entry["epochs"]) == epoch_count
    assert agent == ref["tenant_fairness_report.json"]


def test_fresh_priority_lane_hardcap_binds_midloop():
    # POSITIVE: N01 has capacity=3 but priority_lanes=1; two K02 streams cannot both fit despite raw capacity.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,3,small,re,1\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K02,0,0,3,P02\nS002,T01,K02,0,0,3,P02\n",
    })
    agent, ref = _run_fixture(files)
    assert ref["preemption_events.json"]["total_count"] == 1
    assert agent["preemption_events.json"] == ref["preemption_events.json"]


def test_shipped_integrity_manifest_matches_artifact_bytes():
    # POSITIVE: SHA-256 of each on-disk canonical artifact matches the entry in integrity_manifest.json.
    manifest = _read_json(OUT_DIR / "integrity_manifest.json")
    for name in CANONICAL_ARTIFACT_ORDER:
        want = hashlib.sha256((OUT_DIR / name).read_bytes()).hexdigest()
        assert manifest["artifact_sha256"][name] == want, f"{name} sha mismatch"
    assert manifest["artifact_names"] == sorted(CANONICAL_ARTIFACT_ORDER)


def test_shipped_final_state_folds_manifest_digest():
    # POSITIVE: final_state.folded_digest_sha256 == sha256(json.dumps(artifact_sha256, sort_keys=True)).
    manifest = _read_json(OUT_DIR / "integrity_manifest.json")
    final = _read_json(OUT_DIR / "final_state.json")
    want = hashlib.sha256(json.dumps(manifest["artifact_sha256"], sort_keys=True).encode("utf-8")).hexdigest()
    assert final["folded_digest_sha256"] == want


def test_fresh_tenant_priority_precedes_stream_id():
    # POSITIVE: quota=1, but the low-ID K03 loses to the high-ID K01.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,1,small,re,1\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K03,0,0,2,P03\nS900,T01,K01,0,0,4,P01\n",
        "packet_rate_profiles.csv": "profile_id,base_rate,class_hint\nP01,4,K01\nP03,2,K03\n",
    })
    agent, ref = _run_fixture(files)
    assert ref["schedule_matrix.json"]["epochs"][0]["assignments"] == {"S900": "N01"}
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]


# ============================================================
# BUCKET D -- Hidden seeded scenarios and shipped reviewed-result checks (7 tests)
# ============================================================

def _seeded_scenario(regime: str) -> dict:
    base = {
        name: (_data_dir() / name).read_text()
        for name in INPUT_FILES
    }
    if regime == "oversubscribed":
        base["fleet_nodes.csv"] = "node_id,capacity,mtu_class,region,priority_lanes\nN01,2,small,re,2\nN02,2,small,re,2\nN03,2,medium,rw,1\nN04,1,medium,rw,1\nN05,1,medium,rn,1\nN06,1,jumbo,rn,1\n"
    elif regime == "tight_slo":
        base["qos_classes.json"] = '{"classes":[{"class_id":"K01","priority_rank":3,"slo_max_hops":1},{"class_id":"K02","priority_rank":2,"slo_max_hops":2},{"class_id":"K03","priority_rank":1,"slo_max_hops":3}]}\n'
    elif regime == "burst_arrival":
        rows = base["stream_manifest.csv"].splitlines()
        header = rows[0]
        body = [r for r in rows[1:] if r]
        rebuilt = [header]
        for r in body:
            cols = r.split(",")
            if cols[0] in ("S001", "S005", "S009", "S013"):
                cols[3] = "0"
            rebuilt.append(",".join(cols))
        base["stream_manifest.csv"] = "\n".join(rebuilt) + "\n"
    elif regime == "migration_dominant":
        base["tenants.csv"] = "tenant_id,floor,ceiling,migration_mult,tenant_region\nT01,1,6,5,re\nT02,1,6,5,re\nT03,1,5,5,rw\nT04,1,5,5,rw\nT05,0,4,5,rn\nT06,1,4,5,rn\n"
    return base


def test_fresh_utilization_end_is_pre_refill_balance():
    # POSITIVE: epoch 0 starts above capacity because of the one-time offset.
    # One assigned stream leaves the reported pre-refill balance at 6. Phase 8
    # then clamps and refills the carry to 5 for epoch 1. Reporting that carry
    # as epoch 0's bucket_tokens_end incorrectly produces 5 instead of 6.
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,2,small,re,2\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS001,T01,K02,0,1,3,P02\n",
        "token_buckets.csv": "node_id,bucket_capacity,refill_num,refill_den,refill_offset\nN01,5,3,1,2\n",
        "migration_penalty_table.json": '{"base":[{"tenant":"T01","epoch":0,"base":3},{"tenant":"T01","epoch":1,"base":3}]}\n',
        "epoch_windows.csv": "epoch,duration_num,duration_den,warm_start\n0,1,1,\n1,1,1,\n",
    })
    with tempfile.TemporaryDirectory() as tmp:
        in_dir = Path(tmp) / "in"
        out_dir = Path(tmp) / "out"
        _write_files(files, in_dir)
        _run_agent(in_dir, out_dir)
        rows = _read_json(out_dir / "fleet_utilization.json")["nodes"][0]["utilization_by_epoch"]
    assert rows[0]["bucket_tokens_start"] == 7
    assert rows[1]["bucket_tokens_start"] == 5
    got = rows[0]
    assert got["bucket_tokens_end"] == 6


def test_hidden_tight_slo_fairness_matches_reference():
    agent, ref = _run_fixture(_seeded_scenario("tight_slo"))
    got = agent["tenant_fairness_report.json"]["tenants"][0]["epochs"][0]["deviation"]
    want = ref["tenant_fairness_report.json"]["tenants"][0]["epochs"][0]["deviation"]
    assert got == want


def test_hidden_burst_arrival_fixed_point_matches_reference():
    agent, ref = _run_fixture(_seeded_scenario("burst_arrival"))
    got = agent["fixed_point_trace.json"]["iterations"][4]["admitted_total"]
    want = ref["fixed_point_trace.json"]["iterations"][4]["admitted_total"]
    assert got == want


def test_hidden_migration_dominant_objective_matches_reference():
    agent, ref = _run_fixture(_seeded_scenario("migration_dominant"))
    assert agent["objective_breakdown.json"]["total_cost"] == ref["objective_breakdown.json"]["total_cost"]


def test_hidden_oversubscribed_objective_matches_reference():
    agent, ref = _run_fixture(_seeded_scenario("oversubscribed"))
    got = agent["objective_breakdown.json"]["fairness_deviation"]
    want = ref["objective_breakdown.json"]["fairness_deviation"]
    assert got == want


def test_shipped_final_state_matches_reviewed_result():
    ref = _reference_solve(_data_dir())
    final = _read_json(OUT_DIR / "final_state.json")
    assert final["stream_count"] == ref["_stream_count"]
    assert final["epoch_count"] == ref["_epoch_count"]
    assert final["total_cost"] == ref["_total_cost"]


def test_shipped_sla_report_matches_reference():
    ref = _reference_solve(_data_dir())
    agent_sla = _read_json(OUT_DIR / "sla_violation_report.json")
    assert agent_sla == ref["sla_violation_report.json"], "sla_violation_report content must match the reference"


# ============================================================
# BUCKET E -- Sealed case tests (5 tests)
# ============================================================

def test_sealed_argosy_witness_matches_agent_output():
    agent, ref = _run_on_case("argosy")
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]
    assert agent["preemption_events.json"] == ref["preemption_events.json"]


def test_sealed_caravel_witness_matches_agent_output():
    agent, ref = _run_on_case("caravel")
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]
    assert agent["tenant_fairness_report.json"] == ref["tenant_fairness_report.json"]


def test_sealed_dhow_witness_matches_agent_output():
    agent, ref = _run_on_case("dhow")
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]
    assert agent["fleet_utilization.json"] == ref["fleet_utilization.json"]


def test_sealed_esquif_witness_matches_agent_output():
    agent, ref = _run_on_case("esquif")
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]
    assert agent["objective_breakdown.json"] == ref["objective_breakdown.json"]


def test_sealed_frigate_witness_matches_agent_output():
    agent, ref = _run_on_case("frigate")
    assert agent["schedule_matrix.json"] == ref["schedule_matrix.json"]
    assert agent["migration_ledger.json"] == ref["migration_ledger.json"]
    assert agent["preemption_events.json"] == ref["preemption_events.json"]


# ============================================================
# BUCKET G -- Independent SLA validity
# ============================================================
def test_sla_violation_report_total_breaches_is_zero_independent_of_reference():
    # POSITIVE: sla_violation_report.total_breaches MUST be zero for a valid schedule per instruction.md and schema Phase 6. This is graded independently of the reference so a broken reference cannot mask a broken agent.
    report = _read_json(OUT_DIR / "sla_violation_report.json")
    assert report["total_breaches"] == 0, f"sla_violation_report.total_breaches must be 0, got {report['total_breaches']}"
    expected_classes = sorted(row["class_id"] for row in _read_json(_data_dir() / "qos_classes.json")["classes"])
    actual_classes = [entry["class"] for entry in report["by_class"]]
    assert actual_classes == expected_classes, f"wrong SLA class rows: {actual_classes}"
    for entry in report["by_class"]:
        assert entry["breaches"] == 0, f"class {entry['class']} has breaches={entry['breaches']}"


# ============================================================
# BUCKET F -- Negative anti-cheat and output-defect detectors (6 tests)
# ============================================================

def _scheduler_runnable() -> bool:
    return SCHEDULER.exists() and SCHEDULER.stat().st_size > 0


def test_negative_weight_hardcoded_sample_answers():
    # NEGATIVE: detect a scheduler that produces literally-identical output on a structurally different input.
    # Pass silently (no penalty) when no scheduler is present or when comparison inputs are missing.
    if not _scheduler_runnable():
        return
    if not (OUT_DIR / "schedule_matrix.json").exists():
        return
    files = _fixture_files({
        "fleet_nodes.csv": "node_id,capacity,mtu_class,region,priority_lanes\nN01,1,small,re,1\n",
        "stream_manifest.csv": "stream_id,tenant_id,class_id,arrival_epoch,deadline_epoch,rate_units,rate_profile\nS999,T01,K02,0,0,3,P02\n",
    })
    try:
        with tempfile.TemporaryDirectory() as tmp:
            in_dir = Path(tmp) / "in"
            out_dir = Path(tmp) / "out"
            _write_files(files, in_dir)
            _run_agent(in_dir, out_dir)
            fresh_schedule = _read_json(out_dir / "schedule_matrix.json")
    except Exception:
        return
    shipped_schedule = _read_json(OUT_DIR / "schedule_matrix.json")
    if fresh_schedule == shipped_schedule:
        raise AssertionError("scheduler emits identical output on a different corpus (hardcoded)")


def test_negative_weight_filename_dependent_behaviour():
    # NEGATIVE: detect a scheduler that changes behaviour when the data directory is renamed.
    # Pass silently (no penalty) when no scheduler is present or when it cannot run.
    if not _scheduler_runnable():
        return
    files = _fixture_files({})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            a_dir = Path(tmp) / "AAA_prefix_data"
            b_dir = Path(tmp) / "zzz_other_data"
            _write_files(files, a_dir)
            _write_files(files, b_dir)
            a_out = Path(tmp) / "outA"
            b_out = Path(tmp) / "outB"
            _run_agent(a_dir, a_out)
            _run_agent(b_dir, b_out)
            a = _read_json(a_out / "schedule_matrix.json")
            b = _read_json(b_out / "schedule_matrix.json")
    except Exception:
        return
    if a != b:
        raise AssertionError("scheduler output depends on directory name (filename-dependent)")


def test_negative_weight_nondeterministic_output():
    # NEGATIVE: detect a scheduler whose two consecutive runs differ.
    # Pass silently (no penalty) when no scheduler is present or when it cannot run.
    if not _scheduler_runnable():
        return
    try:
        with tempfile.TemporaryDirectory() as tmp:
            out1 = Path(tmp) / "out1"
            out2 = Path(tmp) / "out2"
            _run_agent(_data_dir(), out1)
            _run_agent(_data_dir(), out2)
            diffs = []
            for name in CANONICAL_ARTIFACT_ORDER:
                a = (out1 / name).read_bytes()
                b = (out2 / name).read_bytes()
                if a != b:
                    diffs.append(name)
    except Exception:
        return
    if diffs:
        raise AssertionError(f"{diffs[0]} differs across two runs (nondeterministic)")


def test_negative_weight_float_leak_in_artifacts():
    # NEGATIVE: fire only when a present, parseable artifact contains a JSON float.
    def contains_float(value) -> bool:
        if isinstance(value, float):
            return True
        if isinstance(value, dict):
            return any(contains_float(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_float(item) for item in value)
        return False

    for name in ALL_ARTIFACTS:
        path = OUT_DIR / name
        if not path.exists():
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        if contains_float(payload):
            raise AssertionError(f"float value present in {name}")


def test_negative_weight_scratch_files_left_in_output():
    # NEGATIVE: fire on any regular file outside the eleven declared deliverables.
    if not OUT_DIR.exists():
        return
    expected = set(ALL_ARTIFACTS) | {"reusable_scheduler.py"}
    extras = sorted(path.name for path in OUT_DIR.iterdir() if path.is_file() and path.name not in expected)
    if extras:
        raise AssertionError(f"unexpected files in /app/out: {extras}")


def test_negative_weight_hollow_declared_program():
    # NEGATIVE: once any JSON deliverable exists, the declared reusable program must be nonempty.
    any_json = any((OUT_DIR / name).exists() for name in ALL_ARTIFACTS)
    if any_json and not _scheduler_runnable():
        raise AssertionError("JSON artifacts exist but reusable_scheduler.py is absent or empty")


# Rewardkit wrappers. Original test_* bodies are unchanged.
@criterion(description='the ten JSON artifacts parse and the reusable program is nonempty')
def artifacts_exist_and_parse(workspace: Path) -> bool:
    try:
        test_artifacts_exist_and_parse()
        return True
    except Exception:
        return False

@criterion(description='schedule_matrix.json uses the exact declared schema')
def schedule_matrix_schema_is_exact(workspace: Path) -> bool:
    try:
        test_schedule_matrix_schema_is_exact()
        return True
    except Exception:
        return False

@criterion(description='JSON artifacts are canonically sorted and newline terminated')
def canonical_serialization_is_sorted_and_newline_terminated(workspace: Path) -> bool:
    try:
        test_canonical_serialization_is_sorted_and_newline_terminated()
        return True
    except Exception:
        return False

@criterion(description='reusable_scheduler.py reproduces output on an alternate data directory')
def reusable_scheduler_runs_on_alternate_data_directory(workspace: Path) -> bool:
    try:
        test_reusable_scheduler_runs_on_alternate_data_directory()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture SLO boundary uses strict less-than')
def fresh_slo_boundary_is_strictly_excluded(workspace: Path) -> bool:
    try:
        test_fresh_slo_boundary_is_strictly_excluded()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture largest-remainder tie uses tenant_id ascending')
def fresh_largest_remainder_tie_uses_tenant_id_asc(workspace: Path) -> bool:
    try:
        test_fresh_largest_remainder_tie_uses_tenant_id_asc()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture applies tenant floors before the hard cap')
def fresh_floor_applied_before_hard_cap(workspace: Path) -> bool:
    try:
        test_fresh_floor_applied_before_hard_cap()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture bucket refill uses floor rounding')
def fresh_bucket_refill_uses_floor_rounding(workspace: Path) -> bool:
    try:
        test_fresh_bucket_refill_uses_floor_rounding()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture migration cost uses the previous epoch assignment')
def fresh_migration_cost_uses_previous_epoch_assignment(workspace: Path) -> bool:
    try:
        test_fresh_migration_cost_uses_previous_epoch_assignment()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture preemption cascade terminates after one hop')
def fresh_preemption_cascade_terminates_after_one_hop(workspace: Path) -> bool:
    try:
        test_fresh_preemption_cascade_terminates_after_one_hop()
        return True
    except Exception:
        return False

@criterion(description='shipped fixed-point trace converges within tolerance')
def shipped_fixed_point_trace_converges_within_tolerance(workspace: Path) -> bool:
    try:
        test_shipped_fixed_point_trace_converges_within_tolerance()
        return True
    except Exception:
        return False

@criterion(description='shipped tenant report contains every epoch including zero rows')
def shipped_tenant_report_has_every_epoch(workspace: Path) -> bool:
    try:
        test_shipped_tenant_report_has_every_epoch()
        return True
    except Exception:
        return False

@criterion(description='fresh fixture priority-lane hard cap binds mid-loop')
def fresh_priority_lane_hardcap_binds_midloop(workspace: Path) -> bool:
    try:
        test_fresh_priority_lane_hardcap_binds_midloop()
        return True
    except Exception:
        return False

@criterion(description='shipped integrity manifest matches on-disk artifact bytes')
def shipped_integrity_manifest_matches_artifact_bytes(workspace: Path) -> bool:
    try:
        test_shipped_integrity_manifest_matches_artifact_bytes()
        return True
    except Exception:
        return False

@criterion(description='shipped final_state folds the manifest digest')
def shipped_final_state_folds_manifest_digest(workspace: Path) -> bool:
    try:
        test_shipped_final_state_folds_manifest_digest()
        return True
    except Exception:
        return False

@criterion(description='fresh tenant stream selection prioritizes class before stream id')
def fresh_tenant_priority_precedes_stream_id(workspace: Path) -> bool:
    try:
        test_fresh_tenant_priority_precedes_stream_id()
        return True
    except Exception:
        return False

@criterion(description='fresh utilization row reports the post-consumption balance before clamp and refill')
def fresh_utilization_end_is_pre_refill_balance(workspace: Path) -> bool:
    try:
        test_fresh_utilization_end_is_pre_refill_balance()
        return True
    except Exception:
        return False

@criterion(description='hidden tight-SLO first-tenant epoch-zero deviation matches the independent reference')
def hidden_tight_slo_fairness_matches_reference(workspace: Path) -> bool:
    try:
        test_hidden_tight_slo_fairness_matches_reference()
        return True
    except Exception:
        return False

@criterion(description='hidden burst-arrival iteration-four admission total matches the independent reference')
def hidden_burst_arrival_fixed_point_matches_reference(workspace: Path) -> bool:
    try:
        test_hidden_burst_arrival_fixed_point_matches_reference()
        return True
    except Exception:
        return False

@criterion(description='hidden migration-dominant total cost matches the independent reference')
def hidden_migration_dominant_objective_matches_reference(workspace: Path) -> bool:
    try:
        test_hidden_migration_dominant_objective_matches_reference()
        return True
    except Exception:
        return False

@criterion(description='hidden oversubscribed fairness deviation matches the independent reference')
def hidden_oversubscribed_objective_matches_reference(workspace: Path) -> bool:
    try:
        test_hidden_oversubscribed_objective_matches_reference()
        return True
    except Exception:
        return False

@criterion(description='shipped final_state matches the reviewed result')
def shipped_final_state_matches_reviewed_result(workspace: Path) -> bool:
    try:
        test_shipped_final_state_matches_reviewed_result()
        return True
    except Exception:
        return False

@criterion(description='shipped SLA report matches the reviewed result')
def shipped_sla_report_matches_reference(workspace: Path) -> bool:
    try:
        test_shipped_sla_report_matches_reference()
        return True
    except Exception:
        return False

@criterion(description='sealed argosy witness matches agent output')
def sealed_argosy_witness_matches_agent_output(workspace: Path) -> bool:
    try:
        test_sealed_argosy_witness_matches_agent_output()
        return True
    except Exception:
        return False

@criterion(description='sealed caravel witness matches agent output')
def sealed_caravel_witness_matches_agent_output(workspace: Path) -> bool:
    try:
        test_sealed_caravel_witness_matches_agent_output()
        return True
    except Exception:
        return False

@criterion(description='sealed dhow witness matches agent output')
def sealed_dhow_witness_matches_agent_output(workspace: Path) -> bool:
    try:
        test_sealed_dhow_witness_matches_agent_output()
        return True
    except Exception:
        return False

@criterion(description='sealed esquif witness matches agent output')
def sealed_esquif_witness_matches_agent_output(workspace: Path) -> bool:
    try:
        test_sealed_esquif_witness_matches_agent_output()
        return True
    except Exception:
        return False

@criterion(description='sealed frigate witness matches agent output')
def sealed_frigate_witness_matches_agent_output(workspace: Path) -> bool:
    try:
        test_sealed_frigate_witness_matches_agent_output()
        return True
    except Exception:
        return False

@criterion(description='sla_violation_report total_breaches is zero independent of the reference')
def sla_violation_report_total_breaches_is_zero_independent_of_reference(workspace: Path) -> bool:
    try:
        test_sla_violation_report_total_breaches_is_zero_independent_of_reference()
        return True
    except Exception:
        return False

@criterion(description='the scheduler emits identical output on a structurally different corpus')
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    try:
        test_negative_weight_hardcoded_sample_answers()
        return False
    except Exception:
        return True

@criterion(description='the scheduler changes behaviour when the data directory is renamed')
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    try:
        test_negative_weight_filename_dependent_behaviour()
        return False
    except Exception:
        return True

@criterion(description='two consecutive scheduler runs on the same input differ')
def negative_nondeterministic_output(workspace: Path) -> bool:
    try:
        test_negative_weight_nondeterministic_output()
        return False
    except Exception:
        return True

@criterion(description='a delivered JSON artifact contains a float value')
def negative_float_leak_in_artifacts(workspace: Path) -> bool:
    try:
        test_negative_weight_float_leak_in_artifacts()
        return False
    except Exception:
        return True

@criterion(description='a scratch or undeclared regular file remains under the output directory')
def negative_scratch_files_left_in_output(workspace: Path) -> bool:
    try:
        test_negative_weight_scratch_files_left_in_output()
        return False
    except Exception:
        return True

@criterion(description='JSON deliverables exist while the declared reusable program is absent or empty')
def negative_hollow_declared_program(workspace: Path) -> bool:
    try:
        test_negative_weight_hollow_declared_program()
        return False
    except Exception:
        return True


criteria.artifacts_exist_and_parse(weight=1)
criteria.schedule_matrix_schema_is_exact(weight=1)
criteria.canonical_serialization_is_sorted_and_newline_terminated(weight=1)
criteria.reusable_scheduler_runs_on_alternate_data_directory(weight=1)
criteria.fresh_slo_boundary_is_strictly_excluded(weight=5)
criteria.fresh_largest_remainder_tie_uses_tenant_id_asc(weight=5)
criteria.fresh_floor_applied_before_hard_cap(weight=5)
criteria.fresh_bucket_refill_uses_floor_rounding(weight=5)
criteria.fresh_migration_cost_uses_previous_epoch_assignment(weight=5)
criteria.fresh_preemption_cascade_terminates_after_one_hop(weight=3)
criteria.shipped_fixed_point_trace_converges_within_tolerance(weight=3)
criteria.shipped_tenant_report_has_every_epoch(weight=3)
criteria.fresh_priority_lane_hardcap_binds_midloop(weight=3)
criteria.shipped_integrity_manifest_matches_artifact_bytes(weight=3)
criteria.shipped_final_state_folds_manifest_digest(weight=3)
criteria.fresh_tenant_priority_precedes_stream_id(weight=3)
criteria.fresh_utilization_end_is_pre_refill_balance(weight=5)
criteria.hidden_tight_slo_fairness_matches_reference(weight=5)
criteria.hidden_burst_arrival_fixed_point_matches_reference(weight=5)
criteria.hidden_migration_dominant_objective_matches_reference(weight=5)
criteria.hidden_oversubscribed_objective_matches_reference(weight=5)
criteria.shipped_final_state_matches_reviewed_result(weight=3)
criteria.shipped_sla_report_matches_reference(weight=3)
criteria.sealed_argosy_witness_matches_agent_output(weight=3)
criteria.sealed_caravel_witness_matches_agent_output(weight=3)
criteria.sealed_dhow_witness_matches_agent_output(weight=3)
criteria.sealed_esquif_witness_matches_agent_output(weight=3)
criteria.sealed_frigate_witness_matches_agent_output(weight=3)
criteria.sla_violation_report_total_breaches_is_zero_independent_of_reference(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-5)
criteria.negative_float_leak_in_artifacts(weight=-3)
criteria.negative_scratch_files_left_in_output(weight=-3)
criteria.negative_hollow_declared_program(weight=-5)
