"""Idempotent data generator for sentinel-policy-recompute harden P9 r1.

Reads SOURCE environment/data (read-only) and writes the edited files into
BUNDLE environment/data. Run with the spr_venv python (pyarrow 18.1.0).
"""
import json
import re
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path("/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/sentinel-policy-recompute/environment/data")
DST = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute/environment/data")

PRINCIPAL_TENANT = {"K042": "t-atlas", "K118": "t-atlas", "K077": "t-borealis", "K201": "t-cinder"}

CONVENTIONS = [
    "Each row is one override for the principal named by param_key, which belongs to the tenant named by tenant.",
    "Rows are stored in ascending seq, and seq values are unique.",
    "rev is 1 or 2.",
    "timeout_ms_delta is a delta in milliseconds; a rev 1 row stores it in whole seconds.",
    "Value ranges: max_records_delta -60 to 60, retry_limit_delta 0 to 3, risk_delta 0 to 20, timeout_ms_delta -5 to 5 on rev 1 rows and -900 to 900 on rev 2 rows.",
    "A row passes selection when it meets every condition in override_precedence.conf.",
    "Each tenant has an override allowance in quota_limits.cfg. The rows that pass selection use that allowance one unit each, in ascending seq order across all rows of the tenant whichever principal they name, and a row that passes selection after its tenant's allowance is used up is not applied.",
    "Every applied row adds its deltas to the base parameters of its principal.",
    "controls gives, per tenant, the number of stored rows and the sums of max_records_delta and of timeout_ms_delta in milliseconds over every stored row of that tenant, whatever its status, window, version or allowance; it is a parse and count control for this file only.",
]

ALLOWANCE = {"t-atlas": 5, "t-borealis": 3, "t-cinder": 4}
for i in range(10):
    ALLOWANCE["t-f%03d" % i] = 2 + (i % 5)


def tenant_of(param_key):
    if param_key in PRINCIPAL_TENANT:
        return PRINCIPAL_TENANT[param_key]
    return "t-f%03d" % (int(param_key[1:]) % 10)


def timeout_ms(row):
    return row["timeout_ms_delta"] * (1000 if row["rev"] == 1 else 1)


def controls_for(rows):
    out = {}
    for row in rows:
        c = out.setdefault(row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0})
        c["rows"] += 1
        c["max_records_delta_sum"] += row["max_records_delta"]
        c["timeout_ms_delta_sum_ms"] += timeout_ms(row)
    return {k: out[k] for k in sorted(out)}


def build_ledger():
    src = json.loads((SRC / "override_deltas.json").read_text())["overrides"]
    by_id = {r["override_id"]: dict(r) for r in src}
    head_ids = ["OV-K042-decoy", "OV-K118-x", "OV-K042-prev", "OV-K042-v099", "OV-K042-auth", "OV-K042-old"]
    head = [by_id[i] for i in head_ids]
    rest = [dict(r) for r in src if r["override_id"] not in head_ids]
    special = {
        "OV-K042-decoy": (2, 800),
        "OV-K118-x": (2, 100),
        "OV-K042-prev": (1, 3),
        "OV-K042-v099": (2, 300),
        "OV-K042-auth": (2, 250),
        "OV-K042-old": (1, -2),
    }
    rows = []
    for r in head:
        rev, td = special[r["override_id"]]
        r["rev"], r["timeout_ms_delta"] = rev, td
        if r["override_id"] == "OV-K042-decoy":
            r["override_id"] = "OV-K042-pre"
            r["window_id"] = "WIN-PRE"
        if r["override_id"] == "OV-K042-auth":
            r["risk_delta"] = 2
        rows.append(r)
    for idx, r in enumerate(rest):
        v = r["timeout_ms_delta"]
        assert 0 <= v <= 60, r
        if idx % 4 == 0:
            r["rev"] = 2
            r["timeout_ms_delta"] = (100 + v * 10) * (-1 if idx % 8 == 0 else 1)
        else:
            r["rev"] = 1
            r["timeout_ms_delta"] = v // 10 - 1
        rows.append(r)
    for seq, r in enumerate(rows, start=1):
        r["seq"] = seq
        r["tenant"] = tenant_of(r["param_key"])
    for r in rows:
        assert -60 <= r["max_records_delta"] <= 60
        assert 0 <= r["retry_limit_delta"] <= 3
        assert 0 <= r["risk_delta"] <= 20
        if r["rev"] == 1:
            assert -5 <= r["timeout_ms_delta"] <= 5
        else:
            assert -900 <= r["timeout_ms_delta"] <= 900 and abs(r["timeout_ms_delta"]) >= 100
    rows = [{k: r[k] for k in sorted(r)} for r in rows]
    return {"conventions": CONVENTIONS, "overrides": rows, "controls": controls_for(rows)}


def write(name, text):
    (DST / name).write_text(text, encoding="utf-8")


def main():
    for p in SRC.iterdir():
        if p.is_file() and p.name != "tool.zip":
            shutil.copy2(p, DST / p.name)

    ledger = build_ledger()
    write("override_deltas.json", json.dumps(ledger, indent=2) + "\n")

    lines = ["[quota]", "per_tenant = 1000", "burst = 200", "window_seconds = 60", "",
             "# each override_allowance value is a whole number from 1 to 6", "[override_allowance]"]
    lines += ["%s = %d" % (k, ALLOWANCE[k]) for k in sorted(ALLOWANCE)]
    write("quota_limits.cfg", "\n".join(lines) + "\n")

    write("risk_weight_rounding.txt", "\n".join([
        "# risk weight contribution",
        "terms = risk_weight_base of the principal and the risk_delta of every applied override",
        "contribution = sum of round_half_up(term * mult_bps / 1000) over the terms",
    ]) + "\n")

    write("clamp_rules.txt", "\n".join([
        "# max_records clamp order",
        "after_delta = max_records_base + the max_records_delta of every applied override",
        "scaled = round_half_up(after_delta * mult_bps / 1000)",
        "max_records = min(cap, scaled)",
    ]) + "\n")

    write("reconciliation_rules.conf", "[reconcile]\ntimeout_unit_factor = 1000\niteration_divisor = 10\n")

    write("override_precedence.conf", "\n".join([
        "[precedence]",
        "select = active status only",
        "match = half-open window containing effective_instant",
        "match_version = the override row and the window containing effective_instant both carry the effective version from policy_version_map",
        "apply_to = base_parameters",
    ]) + "\n")

    vmap = json.loads((SRC / "policy_version_map.json").read_text())
    vmap["selection"] = "the effective version is the version with the greatest effective_from that is not after effective_instant in boot_manifest.toml"
    write("policy_version_map.json", json.dumps(vmap, indent=2, sort_keys=True) + "\n")

    t = (SRC / "bundle_ledger.jsonc").read_text()
    t = t.replace("  // B7 is the active operator bundle; B9 is the retired legacy bundle.\n", "")
    t = t.replace(', "status": "superseded"}, // decoy latest\n', ', "status": "superseded"},\n')
    assert "//" not in t
    write("bundle_ledger.jsonc", t)

    t = (SRC / "boot_manifest.toml").read_text()
    t = t.replace('operator_legacy = "retired bundle, do not compile"', 'operator_legacy = "legacy operator bundle"')
    assert "do not compile" not in t
    write("boot_manifest.toml", t)

    t = (SRC / "numeric_constants.env").read_text()
    t = t.replace("# numeric constants (some decoy)", "# numeric constants").replace("DECOY_MAX_RECORDS", "LEGACY_MAX_RECORDS")
    write("numeric_constants.env", t)

    t = (SRC / "legacy_override_table.ini").read_text()
    t = t.replace("; retired legacy bundle B9 overrides -- superseded, do not compile", "; legacy bundle B9 overrides")
    assert "do not compile" not in t
    write("legacy_override_table.ini", t)

    t = (SRC / "effective_windows.xml").read_text()
    assert t.count('id="WIN-DECOY"') == 1
    write("effective_windows.xml", t.replace('id="WIN-DECOY"', 'id="WIN-PRE"'))

    t = (SRC / "output_field_spec.txt").read_text()
    old15 = ("dependency_trace = object with active_bundle, effective_version, param_key, tenant, client_version_ignored "
             "(true when the client-claimed version was not used), resolution_order (files consumed in order), rejected_branches "
             "(list of entries; each entry names an id or filename and the reason it was rejected; the entries together must name "
             "the superseded bundle id, the decoy override table file, and the decoy windows file)")
    assert old15 in t
    new15 = ("dependency_trace = object with active_bundle, effective_version, param_key, tenant, client_version_ignored "
             "(true when the client-claimed version was not used), applied_overrides (list of the override_id of every override "
             "applied to the resolved principal, in ascending seq), ledger_controls (object keyed by every tenant in the controls "
             "block of override_deltas.json; the value is \"ok\" when that tenant's stored control equals the one recomputed from "
             "the stored rows and \"mismatch\" otherwise), resolution_order (files consumed in order), rejected_branches (list of "
             "entries; each entry names an id or filename and the reason it was rejected; the entries together must name the "
             "superseded bundle id, the legacy override table file, and the superseded windows file)")
    head = "# these list the exact keys each artifact must carry. every value is computed by you.\n"
    assert head in t
    t = t.replace(head, head + "# the tool's resolve subcommand writes policy_resolved.json, threshold_curve.json and dependency_trace.json "
                  "with the fields of the policy_resolved, threshold_curve and dependency_trace entries below.\n")
    write("output_field_spec.txt", t.replace(old15, new15))

    t = (SRC / "convergence_spec.txt").read_text()
    assert t.endswith("seed_value = base_threshold\n")
    t += "base_threshold = base_threshold of the threshold_tier_curve.parquet row whose tier equals the role_level of the resolved principal\n"
    write("convergence_spec.txt", t)

    table = pq.read_table(SRC / "threshold_tier_curve.parquet")
    table = table.replace_schema_metadata({"tier": "the role_level of the resolved principal in principal_role_index.yaml"})
    pq.write_table(table, DST / "threshold_tier_curve.parquet", compression="snappy")

    # P12 v3 r3 (QC P2): the source alias table ships under a neutral name.
    shutil.copyfile(SRC / "decoy_alias_table.jsonc", DST / "principal_alias_table.jsonc")
    (DST / "decoy_alias_table.jsonc").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
