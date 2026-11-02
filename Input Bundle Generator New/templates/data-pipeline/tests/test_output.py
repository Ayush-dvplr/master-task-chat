from __future__ import annotations

import csv
import hashlib
import base64
import json
import os
import random
import subprocess
import sys
import tempfile
import zlib
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = int("{{SAMPLE_SEED}}")
CHALLENGE_SEED = int("{{CHALLENGE_SEED}}")
EVAL_SEED = int("{{EVAL_SEED}}")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
REGIONS = ["central", "east", "north", "south", "west"]
SEGMENTS = ["consumer", "corporate", "enterprise", "smb"]
ARTIFACTS = [
    "transform.py",
    "normalized.jsonl",
    "summary.json",
    "data_quality.json",
    "product_summary.json",
    "region_central.json",
    "region_east.json",
    "region_north.json",
    "region_south.json",
    "region_west.json",
    "segment_consumer.json",
    "segment_corporate.json",
    "segment_enterprise.json",
    "segment_smb.json",
]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


_SHIPPED_DATA: dict[str, str] = {{SHIPPED_DATA}}
_DATA_CACHE: list[Path] = []


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


def _clean(value: object) -> str:
    return str(value or "").strip().lower()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


SOURCES = ["sales.csv", "refunds.csv", "adjustments.jsonl", "legacy.txt"]


class _Reference:
    def __init__(self, data_dir: Path) -> None:
        self.customers = {r["customer_id"].strip(): r for r in _read_csv(data_dir / "customers.csv")}
        self.regions = {r["postal_prefix"].strip(): r for r in _read_csv(data_dir / "regions.csv")}
        self.products = {r["sku"].strip(): _clean(r["category"]) for r in _read_csv(data_dir / "product_catalog.csv")}
        self.terminals = {r["terminal"].strip(): _clean(r["channel_group"]) for r in _read_csv(data_dir / "channels.csv")}
        self.calendar = {r["date"].strip(): r["fiscal_week"].strip() for r in _read_csv(data_dir / "calendar.csv")}
        self.fx = {(r["date"].strip(), r["currency"].strip().upper()): Decimal(r["usd_rate"].strip()) for r in _read_csv(data_dir / "fx_rates.csv")}
        self.warehouses: dict[str, str] = {}
        self.stock: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in _read_csv(data_dir / "inventory.csv"):
            self.warehouses[r["warehouse"].strip()] = r["postal_code"].strip()
            self.stock[r["sku"].strip()][0] += int(r["on_hand"])
            self.stock[r["sku"].strip()][1] += int(r["reorder_point"])

    def region_of(self, postal_code: str) -> dict[str, str]:
        return self.regions[postal_code.split("-")[0].strip()]

    def record(self, raw: dict, source: str) -> dict:
        customer_id = str(raw["customer_id"]).strip()
        sku = str(raw["sku"]).strip()
        customer = self.customers[customer_id]
        category = self.products[sku]
        if source == "adjustments.jsonl":
            region_row = self.region_of(customer["postal_code"])
            warehouse = None
            channel_group = "adjustment"
        else:
            warehouse = str(raw["warehouse"]).strip()
            region_row = self.region_of(self.warehouses[warehouse])
            channel_group = self.terminals[str(raw["terminal"]).strip()]
        currency = str(raw.get("currency") or "").strip().upper() or region_row["default_currency"].strip().upper()
        day = str(raw["date"]).strip()
        rate = self.fx[(day, currency)]
        cents = int((raw["amount"] * rate * Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        return {
            "event_id": str(raw["event_id"]).strip(),
            "date": day,
            "fiscal_week": self.calendar.get(day, "unknown"),
            "customer_id": customer_id,
            "segment": _clean(customer["segment"]),
            "region": _clean(region_row["region"]),
            "sku": sku,
            "category": category,
            "kind": raw["kind"],
            "quantity": raw["quantity"],
            "amount_usd_cents": cents,
            "currency": currency,
            "source": source,
            "channel_group": channel_group,
            "warehouse": warehouse,
        }


def _strict_int(text: object) -> int:
    value = str(text).strip()
    if not value.lstrip("-").isdigit():
        raise ValueError(value)
    return int(value)


def _raw_rows(data_dir: Path, source: str):
    path = data_dir / source
    if source == "sales.csv":
        for row in _read_csv(path):
            def build_sale(row=row):
                qty = _strict_int(row["quantity"])
                return {**row, "kind": "sale", "quantity": qty, "amount": Decimal(row["unit_price"].strip()) * qty}
            yield build_sale
    elif source == "refunds.csv":
        for row in _read_csv(path):
            def build_refund(row=row):
                qty = _strict_int(row["quantity"])
                return {**row, "kind": "refund", "quantity": qty, "amount": -abs(Decimal(row["refund_amount"].strip()))}
            yield build_refund
    elif source == "adjustments.jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            def build_adjustment(line=line):
                row = json.loads(line)
                cents = row["amount_cents"]
                if isinstance(cents, bool) or not isinstance(cents, int):
                    raise ValueError(cents)
                return {**row, "kind": _clean(row["kind"]), "quantity": 0, "amount": Decimal(cents) / Decimal(100)}
            yield build_adjustment
    else:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            def build_legacy(line=line):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) != 11:
                    raise ValueError(line)
                event_id, day, customer_id, sku, warehouse, kind, quantity, amount, currency, terminal, _note = parts
                kind = _clean(kind)
                magnitude = abs(Decimal(amount))
                signed = {"sale": magnitude, "fee": magnitude, "refund": -magnitude, "credit": -magnitude}[kind]
                return {"event_id": event_id, "date": day, "customer_id": customer_id, "sku": sku, "warehouse": warehouse,
                        "kind": kind, "quantity": _strict_int(quantity), "amount": signed, "currency": currency, "terminal": terminal}
            yield build_legacy


def _units(rec: dict) -> int:
    return rec["quantity"] if rec["kind"] == "sale" else -rec["quantity"] if rec["kind"] == "refund" else 0


def _group_payload(name: str, records: list[dict], key: str) -> dict:
    selected = [r for r in records if r[key] == name]
    by_kind: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    for rec in selected:
        by_kind[rec["kind"]] += rec["amount_usd_cents"]
        by_category[rec["category"]] += rec["amount_usd_cents"]
    return {key: name, "record_count": len(selected), "total_usd_cents": sum(r["amount_usd_cents"] for r in selected), "net_units": sum(_units(r) for r in selected), "customers": sorted({r["customer_id"] for r in selected}), "by_kind": dict(sorted(by_kind.items())), "by_category": dict(sorted(by_category.items()))}


_EXPECTED_CACHE: dict[tuple[str, float], dict[str, object]] = {}


def _expected(data_dir: Path) -> dict[str, object]:
    key = (str(data_dir.resolve()), max(p.stat().st_mtime for p in data_dir.iterdir()))
    if key not in _EXPECTED_CACHE:
        _EXPECTED_CACHE[key] = _compute_expected(data_dir)
    return _EXPECTED_CACHE[key]


def _compute_expected(data_dir: Path) -> dict[str, object]:
    ref = _Reference(data_dir)
    records = []
    accepted: dict[str, int] = defaultdict(int)
    skipped: dict[str, int] = {}
    for source in SOURCES:
        if not (data_dir / source).is_file():
            continue
        skipped[source] = 0
        for build in _raw_rows(data_dir, source):
            try:
                rec = ref.record(build(), source)
            except (KeyError, ValueError, ArithmeticError, TypeError):
                skipped[source] += 1
                continue
            records.append(rec)
            accepted[source] += 1
    records.sort(key=lambda r: r["event_id"])
    skipped_total = sum(skipped.values())
    summary: dict[str, object] = {"record_count": len(records), "skipped_count": skipped_total, "total_usd_cents": sum(r["amount_usd_cents"] for r in records)}
    for field in ["region", "segment", "kind", "category", "channel_group"]:
        bucket: dict[str, int] = defaultdict(int)
        for rec in records:
            bucket[rec[field]] += rec["amount_usd_cents"]
        summary[f"by_{field}"] = dict(sorted(bucket.items()))
    per_sku: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        per_sku[rec["sku"]].append(rec)
    product_rows = []
    for sku in sorted(ref.products):
        selected = per_sku.get(sku, [])
        on_hand, reorder = ref.stock.get(sku, [0, 0])
        product_rows.append({"sku": sku, "category": ref.products[sku], "record_count": len(selected), "total_usd_cents": sum(r["amount_usd_cents"] for r in selected), "net_units": sum(_units(r) for r in selected), "on_hand": on_hand, "reorder_point": reorder})
    payloads: dict[str, object] = {
        "normalized.jsonl": records,
        "summary.json": summary,
        "data_quality.json": {"input_files": sorted(p.name for p in data_dir.iterdir() if p.is_file()), "records_by_source": dict(sorted(accepted.items())), "skipped_by_source": dict(sorted(skipped.items())), "skipped_count": skipped_total},
        "product_summary.json": {"products": product_rows},
    }
    for region in REGIONS:
        payloads[f"region_{region}.json"] = _group_payload(region, records, "region")
    for segment in SEGMENTS:
        payloads[f"segment_{segment}.json"] = _group_payload(segment, records, "segment")
    return payloads


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _run_transform(input_dir: Path, output_dir: Path) -> dict[str, object]:
    script = OUT_DIR / "transform.py"
    assert script.is_file(), "transform.py missing"
    before = {p.resolve() for p in output_dir.parent.rglob("*")} if output_dir.parent.exists() else set()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_dir.parent.chmod(0o777)
    except PermissionError:
        pass
    for path in [input_dir, *input_dir.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    if output_dir.is_dir():
        output_dir.chmod(0o777)
    proc = subprocess.run(_untrusted_command([sys.executable, str(script), str(input_dir), str(output_dir)]), text=True, capture_output=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-500:]
    after = {p.resolve() for p in output_dir.parent.rglob("*")}
    outside = [p for p in after - before if output_dir.resolve() not in [p, *p.parents]]
    assert not outside, f"wrote outside output dir: {outside}"
    return {name: (_read_jsonl(output_dir / name) if name.endswith(".jsonl") else _read_json(output_dir / name)) for name in ARTIFACTS if name != "transform.py"}


def _copy_visible_data(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for path in _data_dir().iterdir():
        if path.is_file():
            (target / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def _check_artifacts_exist():
    """POSITIVE: all fourteen requested output artifacts exist."""
    for name in ARTIFACTS:
        assert (OUT_DIR / name).is_file(), name


def _check_transform_script_is_executable_python():
    """POSITIVE: transform.py is a reusable executable Python entry point."""
    script = OUT_DIR / "transform.py"
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env python3")
    assert "sys.argv" in text and "INPUT_DIR" in text and "OUTPUT_DIR" in text
    assert os.access(script, os.X_OK)


def _check_visible_normalized_jsonl_exact():
    """POSITIVE: visible normalized.jsonl is exactly canonical."""
    assert _read_jsonl(OUT_DIR / "normalized.jsonl") == _expected(_data_dir())["normalized.jsonl"]


def _check_visible_summary_exact():
    """POSITIVE: visible summary.json contains exact global aggregates."""
    assert _read_json(OUT_DIR / "summary.json") == _expected(_data_dir())["summary.json"]


def _check_data_quality_exact():
    """POSITIVE: data quality output lists inputs, sources, and skipped rows."""
    assert _read_json(OUT_DIR / "data_quality.json") == _expected(_data_dir())["data_quality.json"]


def _check_product_summary_exact():
    """POSITIVE: product summary joins transaction and inventory data."""
    assert _read_json(OUT_DIR / "product_summary.json") == _expected(_data_dir())["product_summary.json"]


def _check_region_outputs_exact():
    """POSITIVE: every fixed region artifact is present and exact."""
    expected = _expected(_data_dir())
    for region in REGIONS:
        assert _read_json(OUT_DIR / f"region_{region}.json") == expected[f"region_{region}.json"]


def _check_segment_outputs_exact():
    """POSITIVE: every fixed segment artifact is present and exact."""
    expected = _expected(_data_dir())
    for segment in SEGMENTS:
        assert _read_json(OUT_DIR / f"segment_{segment}.json") == expected[f"segment_{segment}.json"]


def _check_output_format_is_canonical_and_deterministic():
    """POSITIVE: JSONL is sorted compact JSON and JSON files use stable formatting."""
    records = _expected(_data_dir())["normalized.jsonl"]
    assert isinstance(records, list)
    assert (OUT_DIR / "normalized.jsonl").read_text(encoding="utf-8").splitlines() == [json.dumps(r, sort_keys=True, separators=(",", ":")) for r in records]
    for name in ARTIFACTS:
        if name.endswith(".json"):
            assert (OUT_DIR / name).read_text(encoding="utf-8").endswith("\n")


def _check_reusable_transform_regenerates_visible_outputs_elsewhere():
    """POSITIVE: transform.py accepts explicit input and output directories."""
    root = Path(tempfile.mkdtemp(prefix="pipeline-visible-copy-"))
    out = Path(tempfile.mkdtemp(prefix="pipeline-visible-out-")) / "nested"
    _copy_visible_data(root)
    assert _run_transform(root, out) == _expected(root)


def _check_hidden_row_order_and_currency_transform_correctly():
    """POSITIVE: reusable script handles reordered rows and changed exchange rates."""
    root = Path(tempfile.mkdtemp(prefix="pipeline-hidden-in-"))
    _copy_visible_data(root)
    rng = random.Random(EVAL_SEED)
    for name in ["sales.csv", "fx_rates.csv"]:
        rows = _read_csv(root / name)
        if name == "fx_rates.csv":
            bumped = rng.choice(sorted({r["currency"] for r in rows} - {"USD"}))
            for row in rows:
                if row["currency"] == bumped:
                    row["usd_rate"] = str((Decimal(row["usd_rate"]) * Decimal("1.0375")).quantize(Decimal("0.000001")))
        rng.shuffle(rows)
        with (root / name).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    out = Path(tempfile.mkdtemp(prefix="pipeline-hidden-out-")) / "out"
    assert _run_transform(root, out) == _expected(root)


def _check_transform_avoids_network_dependencies_and_shelling_out():
    """POSITIVE: transform source remains stdlib-local and does not shell out."""
    text = (OUT_DIR / "transform.py").read_text(encoding="utf-8")
    banned = ["requests", "urllib", "socket", "subprocess", "os.system", "pandas", "numpy"]
    assert not any(token in text for token in banned)


def _check_transform_does_not_write_outside_output_dir():
    """POSITIVE: hidden execution creates only files under the requested output directory."""
    root = Path(tempfile.mkdtemp(prefix="pipeline-safe-in-"))
    _copy_visible_data(root)
    parent = Path(tempfile.mkdtemp(prefix="pipeline-safe-parent-"))
    assert _run_transform(root, parent / "out") == _expected(root)


def _check_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: detects visible-output hashes or hidden seed constants in transform source."""
    text = (OUT_DIR / "transform.py").read_text(encoding="utf-8")
    digest = hashlib.sha256(json.dumps(_expected(_data_dir())["summary.json"], sort_keys=True).encode()).hexdigest()
    assert digest in text or str(EVAL_SEED) in text or str(CHALLENGE_SEED) in text


def _check_negative_weight_embedded_visible_records():
    """NEGATIVE: detects embedding the visible customers/SKUs instead of reading inputs."""
    text = (OUT_DIR / "transform.py").read_text(encoding="utf-8")
    ids = [r["customer_id"].strip() for r in _read_csv(_data_dir() / "customers.csv")]
    ids += [r["sku"].strip() for r in _read_csv(_data_dir() / "product_catalog.csv")]
    assert sum(token in text for token in ids) >= 10


def _check_negative_weight_network_dependency_or_shell_cheat():
    """NEGATIVE: detects network, dependency, or shell execution cheat paths."""
    text = (OUT_DIR / "transform.py").read_text(encoding="utf-8")
    assert any(token in text for token in ["requests", "urllib", "socket", "subprocess", "os.system", "pandas", "numpy"])


def _check_negative_weight_nondeterministic_output():
    """NEGATIVE: detects nondeterminism sources in the transform implementation."""
    text = (OUT_DIR / "transform.py").read_text(encoding="utf-8")
    assert any(token in text for token in ["random", "time.time", "datetime.now", "uuid4"])


if __name__ == "__main__":
    print(json.dumps({"tests": len([n for n in globals() if n.startswith("test_")])}, sort_keys=True))


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="All fourteen requested output artifacts exist.")
def artifacts_exist(workspace: Path) -> bool:
    return _holds(_check_artifacts_exist)


@criterion(description="Transform.py is a reusable executable Python entry point.")
def transform_script_is_executable_python(workspace: Path) -> bool:
    return _holds(_check_transform_script_is_executable_python)


@criterion(description="Visible normalized.jsonl is exactly canonical.")
def visible_normalized_jsonl_exact(workspace: Path) -> bool:
    return _holds(_check_visible_normalized_jsonl_exact)


@criterion(description="Visible summary.json contains exact global aggregates.")
def visible_summary_exact(workspace: Path) -> bool:
    return _holds(_check_visible_summary_exact)


@criterion(description="Data quality output lists inputs, sources, and skipped rows.")
def data_quality_exact(workspace: Path) -> bool:
    return _holds(_check_data_quality_exact)


@criterion(description="Product summary joins transaction and inventory data.")
def product_summary_exact(workspace: Path) -> bool:
    return _holds(_check_product_summary_exact)


@criterion(description="Every fixed region artifact is present and exact.")
def region_outputs_exact(workspace: Path) -> bool:
    return _holds(_check_region_outputs_exact)


@criterion(description="Every fixed segment artifact is present and exact.")
def segment_outputs_exact(workspace: Path) -> bool:
    return _holds(_check_segment_outputs_exact)


@criterion(description="JSONL is sorted compact JSON and JSON files use stable formatting.")
def output_format_is_canonical_and_deterministic(workspace: Path) -> bool:
    return _holds(_check_output_format_is_canonical_and_deterministic)


@criterion(description="Transform.py accepts explicit input and output directories.")
def reusable_transform_regenerates_visible_outputs_elsewhere(workspace: Path) -> bool:
    return _holds(_check_reusable_transform_regenerates_visible_outputs_elsewhere)


@criterion(description="Reusable script handles reordered rows and changed exchange rates.")
def hidden_row_order_and_currency_transform_correctly(workspace: Path) -> bool:
    return _holds(_check_hidden_row_order_and_currency_transform_correctly)


@criterion(description="Transform source remains stdlib-local and does not shell out.")
def transform_avoids_network_dependencies_and_shelling_out(workspace: Path) -> bool:
    return _holds(_check_transform_avoids_network_dependencies_and_shelling_out)


@criterion(description="Hidden execution creates only files under the requested output directory.")
def transform_does_not_write_outside_output_dir(workspace: Path) -> bool:
    return _holds(_check_transform_does_not_write_outside_output_dir)


@criterion(description="Detects visible-output hashes or hidden seed constants in transform source.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_weight_hardcoded_sample_answers)


@criterion(description="Detects embedding the visible customers/SKUs instead of reading inputs.")
def negative_embedded_visible_records(workspace: Path) -> bool:
    return _holds(_check_negative_weight_embedded_visible_records)


@criterion(description="Detects network, dependency, or shell execution cheat paths.")
def negative_network_dependency_or_shell_cheat(workspace: Path) -> bool:
    return _holds(_check_negative_weight_network_dependency_or_shell_cheat)


@criterion(description="Detects nondeterminism sources in the transform implementation.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_check_negative_weight_nondeterministic_output)


criteria.artifacts_exist(weight=3)
criteria.transform_script_is_executable_python(weight=3)
criteria.visible_normalized_jsonl_exact(weight=5)
criteria.visible_summary_exact(weight=5)
criteria.data_quality_exact(weight=3)
criteria.product_summary_exact(weight=3)
criteria.region_outputs_exact(weight=5)
criteria.segment_outputs_exact(weight=5)
criteria.output_format_is_canonical_and_deterministic(weight=3)
criteria.reusable_transform_regenerates_visible_outputs_elsewhere(weight=5)
criteria.hidden_row_order_and_currency_transform_correctly(weight=5)
criteria.transform_avoids_network_dependencies_and_shelling_out(weight=3)
criteria.transform_does_not_write_outside_output_dir(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_embedded_visible_records(weight=-5)
criteria.negative_network_dependency_or_shell_cheat(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
