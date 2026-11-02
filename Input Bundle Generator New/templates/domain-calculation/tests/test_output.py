"""Verifier for the {{FORMAT_TAG}} domain-calculation task.

Expected artifacts are independently derived from the shipped flat CSV/JSON input
contract. Additional seeded cases exercise the reusable program without storing
expected answers in the bundle.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. Honest agent -> assertion fails -> negative weight not added.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import ast
import base64
import csv
import shutil
import zlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

SAMPLE_SEED = {{SAMPLE_SEED}}
CHALLENGE_SEED = {{CHALLENGE_SEED}}
EVAL_SEED = {{EVAL_SEED}}

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
ARTIFACT_NAMES = ["summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json", "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json"]
REGION_NAMES = ("North", "South", "West", "East")
SEGMENT_NAMES = ("commercial", "public")
_UNTRUSTED_UID = 65532
_UNTRUSTED_GID = 65532
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

_SHIPPED_DATA: dict[str, str] = {{SHIPPED_DATA}}
_VISIBLE_INPUTS: Path | None = None
_DERIVED: dict[str, dict[str, Any]] = {}


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFFFFFFFFFF or 0xA0761D6478BD642F

    def _next(self) -> int:
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq: list[str]) -> str:
        return seq[self._next() % len(seq)]


def _half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _money_to_usd(amount: int, currency: str, fx: dict[str, int]) -> int:
    return _half_up(Decimal(amount) * Decimal(fx[currency]) / Decimal(10000))


def _add(target: dict[str, int], key: str, value: int) -> None:
    target[key] = target.get(key, 0) + value


def _bucket(name: str) -> dict[str, Any]:
    return {"name": name, "transaction_count": 0, "gross_cents": 0, "tax_cents": 0, "adjusted_net_cents": 0, "department_totals": {}, "category_units": {}, "customers": [], "alerts": []}


def _final(bucket: dict[str, Any], threshold: int) -> dict[str, Any]:
    delta = bucket["adjusted_net_cents"] - bucket["gross_cents"]
    if abs(delta) >= threshold:
        bucket["alerts"] = [{"name": bucket["name"], "delta_cents": delta}]
    bucket["department_totals"] = dict(sorted(bucket["department_totals"].items()))
    bucket["category_units"] = dict(sorted(bucket["category_units"].items()))
    bucket["customers"] = sorted(bucket["customers"])
    return bucket


def derive(data_dir: Path) -> dict[str, Any]:
    key = str(data_dir.resolve())
    if key not in _DERIVED:
        _DERIVED[key] = _derive(data_dir)
    return _DERIVED[key]


def _derive(data_dir: Path) -> dict[str, Any]:
    policy = json.loads((data_dir / "policy.json").read_text(encoding="utf-8"))
    thresholds = json.loads((data_dir / "thresholds.json").read_text(encoding="utf-8"))
    tax_rules = json.loads((data_dir / "tax_rules.json").read_text(encoding="utf-8"))
    discounts = {k: int(v) for k, v in json.loads((data_dir / "discount_rules.json").read_text(encoding="utf-8")).items()}
    transactions = _read_csv(data_dir / "transactions.csv")
    customers = {r["customer_id"]: r for r in _read_csv(data_dir / "customers.csv")}
    rate_rows = _read_csv(data_dir / "rate_table.csv")
    rates = {(r["department"], r["category"]): Decimal(r["base_multiplier"]) for r in rate_rows}
    fx = {(r["date"], r["currency"]): int(r["rate_to_usd_basis_points"]) for r in _read_csv(data_dir / "fx_rates.csv")}
    regions = {r["site"]: r for r in _read_csv(data_dir / "regions.csv")}
    calendar = {r["date"]: r for r in _read_csv(data_dir / "calendar.csv")}
    site_tax = tax_rules["site_overrides_basis_points"]
    region_tax = tax_rules["region_overrides_basis_points"]
    region_buckets = {name: _bucket(name) for name in thresholds["required_regions"]}
    segment_buckets = {name: _bucket(name) for name in thresholds["required_segments"]}
    dept: dict[str, int] = {}; site: dict[str, int] = {}; site_gross: dict[str, int] = {}; units: dict[str, int] = {}; periods: dict[str, int] = {}
    gross = tax_total = adjusted_total = 0
    lags: list[int] = []
    largest: tuple[int, str] | None = None
    issues: list[str] = []
    for row in transactions:
        customer = customers[row["customer_id"]]
        region = regions[row["site"]]
        region_name = region["region_name"]
        segment = customer["segment"]
        bps = fx[(row["posted_date"], row["currency"])]
        amount = _half_up(Decimal(int(row["amount_cents"])) * Decimal(bps) / Decimal(10000))
        basis = _half_up(Decimal(int(row["tax_basis_cents"])) * Decimal(bps) / Decimal(10000))
        tax_bps = int(site_tax.get(row["site"], region_tax.get(region_name, tax_rules["default_tax_rate_basis_points"])))
        discount_bps = discounts[customer["discount_code"]]
        tax = _half_up(Decimal(basis) * Decimal(tax_bps) / Decimal(10000))
        discounted = _half_up(Decimal(amount + tax) * (Decimal(10000 + discount_bps) / Decimal(10000)))
        multiplied = _half_up(Decimal(discounted) * rates[(row["department"], row["category"])])
        adjusted = max(int(thresholds["minimum_net_cents"]), multiplied + int(region["site_adjustment_cents"]))
        lag = (date.fromisoformat(row["posted_date"]) - date.fromisoformat(row["service_date"])).days
        if lag > int(thresholds["quality_max_posting_lag_days"]):
            issues.append(f"{row['txn_id']}: posting lag {lag} days")
        if row["posted_date"] not in calendar:
            issues.append(f"{row['txn_id']}: posted date missing from calendar")
        period = calendar.get(row["posted_date"], {"period": "unknown"})["period"]
        gross += amount; tax_total += tax; adjusted_total += adjusted; lags.append(lag)
        _add(dept, row["department"], adjusted); _add(site, row["site"], adjusted); _add(site_gross, row["site"], amount)
        _add(units, row["category"], int(row["units"])); _add(periods, period, adjusted)
        if largest is None or amount > largest[0] or (amount == largest[0] and row["txn_id"] < largest[1]):
            largest = (amount, row["txn_id"])
        for bucket in (region_buckets.get(region_name), segment_buckets.get(segment)):
            if bucket is None:
                continue
            bucket["transaction_count"] += 1; bucket["gross_cents"] += amount; bucket["tax_cents"] += tax; bucket["adjusted_net_cents"] += adjusted
            _add(bucket["department_totals"], row["department"], adjusted); _add(bucket["category_units"], row["category"], int(row["units"]))
            bucket.setdefault("_customers", set()).add(customer["customer_id"])
    threshold = int(thresholds["variance_alert_cents"])
    alerts = [{"site": key, "delta_cents": site[key] - site_gross[key]} for key in sorted(site) if abs(site[key] - site_gross[key]) >= threshold]
    multipliers: dict[str, dict[str, str]] = {}
    for r in rate_rows:
        multipliers.setdefault(r["department"], {})[r["category"]] = r["base_multiplier"]
    out = {
        "summary.json": {"report_id": policy["report_id"], "transaction_count": len(transactions), "gross_cents": gross, "tax_cents": tax_total, "adjusted_net_cents": adjusted_total, "department_totals": dict(sorted(dept.items())), "site_totals": dict(sorted(site.items())), "category_units": dict(sorted(units.items())), "period_totals": dict(sorted(periods.items())), "largest_transaction": {"txn_id": largest[1] if largest else None, "amount_cents": largest[0] if largest else 0}, "posting_lag_days": {"max": max(lags) if lags else 0, "average": round(sum(lags) / len(lags), 2) if lags else 0.0}, "alerts": alerts},
        "policy_audit.json": {"report_id": policy["report_id"], "default_tax_basis_points": int(tax_rules["default_tax_rate_basis_points"]), "tax_regions": dict(sorted(region_tax.items())), "tax_sites": dict(sorted(site_tax.items())), "discount_codes": dict(sorted(discounts.items())), "department_multipliers": {d: dict(sorted(c.items())) for d, c in sorted(multipliers.items())}, "minimum_net_cents": int(thresholds["minimum_net_cents"]), "variance_alert_cents": threshold},
        "data_quality.json": {"input_file_count": len([p for p in data_dir.iterdir() if p.is_file()]), "transaction_count": len(transactions), "customer_count": len(customers), "region_count": len(regions), "quality_issue_count": len(issues), "quality_issues": sorted(issues)},
    }
    for buckets in (region_buckets, segment_buckets):
        for bucket in buckets.values():
            bucket["customers"] = sorted(bucket.pop("_customers", set()))
    for name in REGION_NAMES:
        out[f"region_{name}.json"] = _final(region_buckets[name], threshold)
    for name in SEGMENT_NAMES:
        out[f"segment_{name}.json"] = _final(segment_buckets[name], threshold)
    return out


def _shipped_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="domain-shipped-"))
    for rel, blob in _SHIPPED_DATA.items():
        (root / rel).write_bytes(zlib.decompress(base64.b64decode(blob)))
    return root


def _seal(root: Path) -> None:
    for path in root.iterdir():
        path.chmod(0o644)
    root.chmod(0o755)


def visible_inputs() -> Path:
    global _VISIBLE_INPUTS
    if _VISIBLE_INPUTS is None:
        _VISIBLE_INPUTS = _shipped_root()
        _seal(_VISIBLE_INPUTS)
    return _VISIBLE_INPUTS


def _copy_inputs(root: Path) -> Path:
    shutil.copytree(visible_inputs(), root)
    return root


def _write_transactions(root: Path, rows: list[list[object]]) -> None:
    header = "txn_id,customer_id,site,department,category,currency,amount_cents,tax_basis_cents,units,service_date,posted_date"
    (root / "transactions.csv").write_text(header + "\n" + "".join(",".join(map(str, r)) + "\n" for r in rows), encoding="utf-8")


def write_case(root: Path, seed: int, n: int = 70) -> Path:
    rng = Rng(seed)
    _copy_inputs(root)
    customers = [r["customer_id"] for r in _read_csv(root / "customers.csv")]
    sites = [r["site"] for r in _read_csv(root / "regions.csv")]
    pairs = [(r["department"], r["category"]) for r in _read_csv(root / "rate_table.csv")]
    rates = [(r["date"], r["currency"]) for r in _read_csv(root / "fx_rates.csv")]
    rows: list[list[object]] = []
    for i in range(1, n + 1):
        department, category = pairs[rng.rand_int(0, len(pairs) - 1)]
        posted, currency = rates[rng.rand_int(0, len(rates) - 1)]
        credit = rng.rand_int(0, 9) == 0
        amount = -rng.rand_int(100, 2500) if credit else rng.rand_int(400, 25000)
        service = date.fromisoformat(posted) - timedelta(days=rng.rand_int(0, 7))
        rows.append([f"x{i:04d}", rng.choice(customers), rng.choice(sites), department, category, currency, amount,
                     0 if credit else max(0, amount - rng.rand_int(0, 300)), rng.rand_int(1, 8), service.isoformat(), posted])
    _write_transactions(root, rows)
    thresholds = json.loads((root / "thresholds.json").read_text(encoding="utf-8"))
    thresholds["variance_alert_cents"] = rng.rand_int(300, 1800)
    (root / "thresholds.json").write_text(json.dumps(thresholds, sort_keys=True), encoding="utf-8")
    (root / "policy.json").write_text(json.dumps({"report_id": "case-" + str(seed)}), encoding="utf-8")
    _seal(root)
    return root


def actual(name: str) -> Any:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


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


def _source_text() -> str:
    chunks = [p.read_text(encoding="utf-8", errors="replace") for p in OUT.glob("*.py")]
    chunks.extend((OUT / name).read_text(encoding="utf-8", errors="replace") for name in ARTIFACT_NAMES if (OUT / name).exists())
    return "\n".join(chunks)


def _py_source_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in OUT.glob("*.py"))


def _check_artifact_set_exists_and_parses():
    """POSITIVE: all ten declared artifacts exist, including the reusable program, and JSON outputs parse."""
    assert SCRIPT.is_file(), "missing /app/out/derive_report.py"
    for name in ARTIFACT_NAMES:
        assert (OUT / name).is_file(), f"missing /app/out/{name}"
        assert isinstance(actual(name), dict)


def _check_summary_schema_is_exact():
    """POSITIVE: summary has the exact required top-level schema."""
    assert set(actual("summary.json")) == {"report_id", "transaction_count", "gross_cents", "tax_cents", "adjusted_net_cents", "department_totals", "site_totals", "category_units", "period_totals", "largest_transaction", "posting_lag_days", "alerts"}


def _check_visible_summary_matches_reference():
    """POSITIVE: visible summary matches independently derived expected output."""
    assert actual("summary.json") == derive(visible_inputs())["summary.json"]


def _check_policy_audit_matches_reference():
    """POSITIVE: policy audit artifact matches independently derived policy and rule data."""
    assert actual("policy_audit.json") == derive(visible_inputs())["policy_audit.json"]


def _check_data_quality_matches_reference():
    """POSITIVE: data quality artifact matches independently derived input checks."""
    assert actual("data_quality.json") == derive(visible_inputs())["data_quality.json"]


def _check_region_north_artifact_matches_reference():
    """POSITIVE: North region artifact is exactly derived from transaction-level rules."""
    assert actual("region_North.json") == derive(visible_inputs())["region_North.json"]


def _check_region_south_artifact_matches_reference():
    """POSITIVE: South region artifact is exactly derived from transaction-level rules."""
    assert actual("region_South.json") == derive(visible_inputs())["region_South.json"]


def _check_region_west_artifact_matches_reference():
    """POSITIVE: West region artifact is exactly derived from transaction-level rules."""
    assert actual("region_West.json") == derive(visible_inputs())["region_West.json"]


def _check_region_east_artifact_matches_reference():
    """POSITIVE: East region artifact is exactly derived from transaction-level rules."""
    assert actual("region_East.json") == derive(visible_inputs())["region_East.json"]


def _check_segment_commercial_artifact_matches_reference():
    """POSITIVE: commercial segment artifact is exactly derived from customer joins."""
    assert actual("segment_commercial.json") == derive(visible_inputs())["segment_commercial.json"]


def _check_segment_public_artifact_matches_reference():
    """POSITIVE: public segment artifact is exactly derived from customer joins."""
    assert actual("segment_public.json") == derive(visible_inputs())["segment_public.json"]


def _check_hidden_seeded_outputs_match_reference():
    """POSITIVE: reusable program handles a fresh seeded flat corpus and emits all JSON outputs."""
    with tempfile.TemporaryDirectory() as td:
        root = write_case(Path(td) / "data", EVAL_SEED, 90)
        out = Path(td) / "out"
        Path(td).chmod(0o777)
        subprocess.run(_untrusted_command([sys.executable, str(SCRIPT), str(root), str(out)]), check=True, timeout=120)
        expected = derive(root)
        for name in ARTIFACT_NAMES:
            assert json.loads((out / name).read_text(encoding="utf-8")) == expected[name]


def _check_rounding_credits_fx_discounts_and_clamp():
    """POSITIVE: half-up rounding, dated currency conversion, discounts, credits, and clamps are correct."""
    with tempfile.TemporaryDirectory() as td:
        root = _copy_inputs(Path(td) / "data")
        discounts = json.loads((root / "discount_rules.json").read_text(encoding="utf-8"))
        customer = next(r["customer_id"] for r in _read_csv(root / "customers.csv") if discounts[r["discount_code"]] < 0)
        adjusted_site = next(r["site"] for r in _read_csv(root / "regions.csv") if int(r["site_adjustment_cents"]) < 0)
        posted, currency = next((r["date"], r["currency"]) for r in _read_csv(root / "fx_rates.csv") if r["currency"] != "USD")
        department, category = next((r["department"], r["category"]) for r in _read_csv(root / "rate_table.csv") if r["base_multiplier"] not in {"1", "1.0"})
        _write_transactions(root, [["e0001", customer, adjusted_site, department, category, currency, -100, 1, 1, posted, posted],
                                   ["e0002", customer, adjusted_site, department, category, currency, 333, 333, 2, posted, posted]])
        thresholds = json.loads((root / "thresholds.json").read_text(encoding="utf-8"))
        thresholds["minimum_net_cents"] = 40
        thresholds["variance_alert_cents"] = 1
        (root / "thresholds.json").write_text(json.dumps(thresholds), encoding="utf-8")
        _seal(root)
        out = Path(td) / "out"
        Path(td).chmod(0o777)
        subprocess.run(_untrusted_command([sys.executable, str(SCRIPT), str(root), str(out)]), check=True, timeout=120)
        assert json.loads((out / "summary.json").read_text()) == derive(root)["summary.json"]


def _check_canonical_serialization_and_sorted_keys():
    """POSITIVE: JSON artifacts are deterministic newline-terminated sorted-key serializations."""
    for name in ARTIFACT_NAMES:
        text = (OUT / name).read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert json.loads(text) == json.loads(json.dumps(actual(name), sort_keys=True))


def _check_no_network_dependencies_or_verifier_reads():
    """POSITIVE: source avoids network, dependency, and verifier access patterns."""
    for path in OUT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
                assert not ({"requests", "urllib", "http", "socket", "pandas", "numpy"} & set(names))
    lowered = _source_text().lower()
    assert "/tests" not in lowered and "reward" not in lowered


def _check_reusable_script_writable_by_unprivileged_submission_style():
    """POSITIVE: reusable script can produce the complete artifact set as an unprivileged user."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out"
        Path(td).chmod(0o777)
        subprocess.run(_untrusted_command([sys.executable, str(SCRIPT), str(visible_inputs()), str(out)]), check=True, timeout=120)
        assert sorted(p.name for p in out.iterdir()) == sorted(ARTIFACT_NAMES)


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: catches reports/source hardcoding visible sample identifiers."""
    source = _py_source_text()
    expected = derive(visible_inputs())["summary.json"]
    txn_ids = [r["txn_id"] for r in _read_csv(visible_inputs() / "transactions.csv")]
    tokens = [txn_ids[0], txn_ids[-1], expected["largest_transaction"]["txn_id"], str(expected["adjusted_net_cents"]), str(expected["gross_cents"])]
    hits = sum(token in source for token in tokens)
    assert hits >= 3, "no hardcoded visible sample pattern detected"


def _check_negative_weight_missing_substantive_sections():
    """NEGATIVE: catches totals-only reports that omit substantive sections."""
    data = actual("summary.json") if (OUT / "summary.json").exists() else {}
    assert not all(key in data for key in ["department_totals", "site_totals", "category_units", "alerts"]), "substantive sections are present"


def _check_negative_weight_reads_tests_or_reward_files():
    """NEGATIVE: catches verifier/reward file access."""
    lowered = _source_text().lower()
    assert any(token in lowered for token in ["/tests", "test_output", "judge.toml", "rewardkit"]), "no verifier read detected"


def _check_negative_weight_external_dependency_or_network():
    """NEGATIVE: catches external dependency or network usage."""
    lowered = _source_text().lower()
    assert any(token in lowered for token in ["requests", "pandas", "numpy", "socket", "urllib"]), "no external dependency/network marker detected"


def _write_corpus(root: Path) -> None:
    write_case(root / "data", SAMPLE_SEED, 12)



if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="All ten declared artifacts exist, including the reusable program, and JSON outputs parse.")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    return _holds(_check_artifact_set_exists_and_parses)


@criterion(description="Summary has the exact required top-level schema.")
def summary_schema_is_exact(workspace: Path) -> bool:
    return _holds(_check_summary_schema_is_exact)


@criterion(description="Visible summary matches independently derived expected output.")
def visible_summary_matches_reference(workspace: Path) -> bool:
    return _holds(_check_visible_summary_matches_reference)


@criterion(description="Policy audit artifact matches independently derived policy and rule data.")
def policy_audit_matches_reference(workspace: Path) -> bool:
    return _holds(_check_policy_audit_matches_reference)


@criterion(description="Data quality artifact matches independently derived input checks.")
def data_quality_matches_reference(workspace: Path) -> bool:
    return _holds(_check_data_quality_matches_reference)


@criterion(description="North region artifact is exactly derived from transaction-level rules.")
def region_north_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_region_north_artifact_matches_reference)


@criterion(description="South region artifact is exactly derived from transaction-level rules.")
def region_south_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_region_south_artifact_matches_reference)


@criterion(description="West region artifact is exactly derived from transaction-level rules.")
def region_west_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_region_west_artifact_matches_reference)


@criterion(description="East region artifact is exactly derived from transaction-level rules.")
def region_east_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_region_east_artifact_matches_reference)


@criterion(description="Commercial segment artifact is exactly derived from customer joins.")
def segment_commercial_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_segment_commercial_artifact_matches_reference)


@criterion(description="Public segment artifact is exactly derived from customer joins.")
def segment_public_artifact_matches_reference(workspace: Path) -> bool:
    return _holds(_check_segment_public_artifact_matches_reference)


@criterion(description="Reusable program handles a fresh seeded flat corpus and emits all JSON outputs.")
def hidden_seeded_outputs_match_reference(workspace: Path) -> bool:
    return _holds(_check_hidden_seeded_outputs_match_reference)


@criterion(description="Half-up rounding, currency conversion, discounts, credits, and clamps are correct.")
def rounding_credits_fx_discounts_and_clamp(workspace: Path) -> bool:
    return _holds(_check_rounding_credits_fx_discounts_and_clamp)


@criterion(description="JSON artifacts are deterministic newline-terminated sorted-key serializations.")
def canonical_serialization_and_sorted_keys(workspace: Path) -> bool:
    return _holds(_check_canonical_serialization_and_sorted_keys)


@criterion(description="Source avoids network, dependency, and verifier access patterns.")
def no_network_dependencies_or_verifier_reads(workspace: Path) -> bool:
    return _holds(_check_no_network_dependencies_or_verifier_reads)


@criterion(description="Reusable script can produce the complete artifact set as an unprivileged user.")
def reusable_script_writable_by_unprivileged_submission_style(workspace: Path) -> bool:
    return _holds(_check_reusable_script_writable_by_unprivileged_submission_style)


@criterion(description="Catches reports/source hardcoding visible sample identifiers.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Catches totals-only reports that omit substantive sections.")
def negative_missing_substantive_sections(workspace: Path) -> bool:
    return _holds(_check_negative_weight_missing_substantive_sections)


@criterion(description="Catches verifier/reward file access.")
def negative_reads_tests_or_reward_files(workspace: Path) -> bool:
    return _holds(_check_negative_weight_reads_tests_or_reward_files)


@criterion(description="Catches external dependency or network usage.")
def negative_external_dependency_or_network(workspace: Path) -> bool:
    return _holds(_check_negative_weight_external_dependency_or_network)


criteria.artifact_set_exists_and_parses(weight=1)
criteria.summary_schema_is_exact(weight=3)
criteria.visible_summary_matches_reference(weight=5)
criteria.policy_audit_matches_reference(weight=3)
criteria.data_quality_matches_reference(weight=3)
criteria.region_north_artifact_matches_reference(weight=3)
criteria.region_south_artifact_matches_reference(weight=3)
criteria.region_west_artifact_matches_reference(weight=3)
criteria.region_east_artifact_matches_reference(weight=3)
criteria.segment_commercial_artifact_matches_reference(weight=3)
criteria.segment_public_artifact_matches_reference(weight=3)
criteria.hidden_seeded_outputs_match_reference(weight=5)
criteria.rounding_credits_fx_discounts_and_clamp(weight=5)
criteria.canonical_serialization_and_sorted_keys(weight=3)
criteria.no_network_dependencies_or_verifier_reads(weight=3)
criteria.reusable_script_writable_by_unprivileged_submission_style(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_missing_substantive_sections(weight=-3)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-3)
