"""Idempotent data generator for sentinel-policy-recompute (harden P9 r1, harden round 2, test-hardening t1 and t2).

Reads SOURCE environment/data (read-only) and writes the edited files into
BUNDLE environment/data. Run with the spr_venv python (pyarrow 18.1.0).
"""
import json
import re
import shutil
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

SRC = Path("/Users/mac/Desktop/Terminal Bench/QC assigned/converted tasks/sentinel-policy-recompute/environment/data")
DST = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute/environment/data")

PRINCIPAL_TENANT = {"K042": "t-atlas", "K118": "t-atlas", "K077": "t-borealis", "K201": "t-cinder", "K301": "t-aurora"}
EXTRA_TENANTS = [("t-borealis", "r-east"), ("t-cinder", "r-west"), ("t-aurora", "r-north")]
CUTOVER = 1650000000

CONVENTIONS = [
    "Each row is one override for the principal named by param_key, which belongs to the tenant named by tenant.",
    "param_key_aliases, when present at the top level, lists entries with alias, principal, start and end; while effective_instant lies in the half-open span from start to end, a row whose param_key is the alias is an override of that principal, and at any other instant it is an override of no principal; either way the row draws like any other row. For example, with alias K900, principal K905, start 100 and end 200, such a row belongs to K905 at instants 100 and 150 and to no principal at 200.",
    "Rows are stored in ascending seq, and seq values are unique across the rows and the reports.",
    "An override_id is stored on more than one row when the override was reissued; only the row with the highest seq is that override, and its earlier rows pass no selection and draw no unit. For example, OV-Q7 stored at seq 40 as active and at seq 52 as superseded is neither applied nor drawn.",
    "rev: the revision of the override row record, 1 or 2.",
    "timeout_ms_delta is a timeout delta; its stored unit is given in units_reference.txt.",
    "Value ranges: max_records_delta -60 to 60, retry_limit_delta 0 to 3, risk_delta 0 to 20, timeout_ms_delta -900 to 900.",
    "A row passes selection when it meets every condition in override_precedence.conf.",
    "A row that passes selection is applied or refused as set by admit, draw_order and requires in override_precedence.conf; requires is an optional row field naming an override_id.",
    "Every applied row adds its deltas to the base parameters of its principal; the timeout delta it adds is the amount set by timeout_pool in override_precedence.conf.",
    "A superseded row may have a carry field naming max_records_delta or risk_delta. When the window of such a row contains effective_instant and the row and the window both carry the effective version, that one delta is added for the row's principal in clamp_rules.txt or risk_weight_rounding.txt the way the delta of an applied override is added, while the row itself is not applied, draws no unit and is not listed among the applied overrides. For example, a superseded row with carry risk_delta, risk_delta 7 and max_records_delta 30 in such a window adds the term 7 to its principal's risk terms and nothing to max_records.",
    "status is active, superseded, withdrawn or reinstated. A withdrawn row passes no selection. A reinstated row passes selection the way an active row does, but adds, in place of its own deltas, the deltas of the last active row of its override_id at a lower seq; when there is no such row it passes no selection. For example, OV-Z1 stored at seq 3 as active with max_records_delta 7, at seq 5 as active with max_records_delta 9, at seq 8 as withdrawn and at seq 12 as reinstated with max_records_delta 2 adds 9.",
    "reports, when present at the top level, lists curve reports, each with kind curve, seq, role (a role key of principal_role_index.yaml) and converged (a whole number), and resets, each with kind reset and seq. A reset withdraws every curve report at a lower seq; a curve report that no reset withdraws stands. For example, with curve reports at seq 4 and 9 and a reset at seq 6, only the curve report at seq 9 stands.",
    "controls gives, per tenant, the number of stored rows and the sums of max_records_delta and of timeout_ms_delta in milliseconds over every stored row of that tenant, whatever its status, window, version or allowance; it is a parse and count control for this file only.",
]

ALLOWANCE = {"r-north": 5, "r-east": 3, "r-west": 4}
for i in range(12):
    ALLOWANCE["r-%02d" % i] = 2 + (i % 5)
VERSION_FROM = {"v%03d" % i: 1600000000 + 1000000 * i for i in range(240)}


def tenant_of(param_key):
    if param_key in PRINCIPAL_TENANT:
        return PRINCIPAL_TENANT[param_key]
    return "t-f%03d" % (int(param_key[1:]) % 10)


def in_seconds(row):
    return VERSION_FROM[row["version"]] < CUTOVER


def timeout_ms(row):
    return row["timeout_ms_delta"] * (1000 if in_seconds(row) else 1)


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
        "OV-K042-prev": (2, 300),
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
    rows.append({"max_records_delta": 5, "override_id": "OV-K301-a", "param_key": "K301", "retry_limit_delta": 0,
                 "risk_delta": 0, "status": "active", "timeout_ms_delta": 2, "version": "v040", "window_id": "WIN-OLD", "rev": 1})
    rows.append({"max_records_delta": -5, "override_id": "OV-K301-b", "param_key": "K301", "retry_limit_delta": 1,
                 "risk_delta": 1, "status": "superseded", "timeout_ms_delta": 150, "version": "v100", "window_id": "WIN-AUTH", "rev": 2})
    for idx, r in enumerate(rest):
        v = r["timeout_ms_delta"]
        assert 0 <= v <= 60, r
        if not in_seconds(r):
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
        assert r["rev"] == (1 if in_seconds(r) else 2), r
        if in_seconds(r):
            assert -5 <= r["timeout_ms_delta"] <= 5
        else:
            assert -900 <= r["timeout_ms_delta"] <= 900 and abs(r["timeout_ms_delta"]) >= 100
    rows = [{k: r[k] for k in sorted(r)} for r in rows]
    return {"conventions": CONVENTIONS, "overrides": rows, "controls": controls_for(rows)}


def add_xlsx_row(src, dst, values):
    with zipfile.ZipFile(src) as zin:
        infos = zin.infolist()
        blobs = {i.filename: zin.read(i.filename) for i in infos}
    sheet = blobs["xl/worksheets/sheet1.xml"].decode("utf-8")
    last = max(int(n) for n in re.findall(r'<row r="(\d+)"', sheet))
    r = last + 1
    cells = "".join('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>' % ("ABCD"[i], r, v) for i, v in enumerate(values))
    assert sheet.endswith("</sheetData></worksheet>")
    sheet = sheet[:-len("</sheetData></worksheet>")] + '<row r="%d">%s</row></sheetData></worksheet>' % (r, cells)
    blobs["xl/worksheets/sheet1.xml"] = sheet.encode("utf-8")
    with zipfile.ZipFile(dst, "w") as zout:
        for i in infos:
            zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
            zi.compress_type = i.compress_type
            zi.external_attr = i.external_attr
            zout.writestr(zi, blobs[i.filename])


def write(name, text):
    (DST / name).write_text(text, encoding="utf-8")


def main():
    for p in SRC.iterdir():
        if p.is_file() and p.name != "tool.zip":
            shutil.copy2(p, DST / p.name)

    ledger = build_ledger()
    write("override_deltas.json", json.dumps(ledger, indent=2) + "\n")

    lines = ["[quota]", "per_tenant = 1000", "burst = 200", "window_seconds = 60", "",
             "# each override_allowance value is a whole number from 1 to 6",
             "# override_allowance is keyed by region; the region of a tenant is its region in tenant_catalog.xml",
             "[override_allowance]"]
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

    write("reconciliation_rules.conf", "[reconcile]\ntimeout_unit_factor = 1000\n"
          "# the divisor of iteration_rule in convergence_spec.txt is a whole number from 6 to 14\n"
          "iteration_divisor = 10\n")

    write("override_precedence.conf", "\n".join([
        "[precedence]",
        "select = active or reinstated status only",
        "match = half-open window containing effective_instant",
        "match_version = the override row and the window containing effective_instant both carry the effective version from policy_version_map",
        "admit = each window in effective_windows.xml admits at most its admit count of applied rows",
        "draw_order = the rows that pass selection draw in ascending seq across all rows of override_deltas.json; a row is applied only when the override_allowance of its tenant's region and the admit count of its window both have a unit left, and an applied row uses one unit of each; a row refused by either draws neither",
        "requires = a row with a requires field is applied only when the override it names was applied earlier in the same draw, at a lower seq; otherwise the row is refused and draws neither unit; for example, with R1 at seq 10 requiring R2, R2 at seq 12 and R3 at seq 14 requiring R2, R2 and R3 are applied and R1 is refused",
        "timeout_pool = the applied rows of one window whose timeout delta in milliseconds is above zero share the timeout_pool of that window in effective_windows.xml, a whole number of milliseconds from 600 to 1500: when their summed delta is at or below the pool, each adds its own delta; otherwise each adds floor(pool * its delta / summed delta). A row whose added delta is then below 100 adds none, and every millisecond of the pool is shared again, floor(pool * its delta / summed delta of the rows whose added delta was 100 or more), across only those rows. An applied row whose delta is zero or below adds its own delta",
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
    t = t.replace('id="WIN-DECOY"', 'id="WIN-PRE"')
    admits = {"WIN-PRE": 2, "WIN-AUTH": 3, "WIN-AUTH-V099": 2, "WIN-OLD": 4}

    pools = {"WIN-PRE": 900, "WIN-AUTH": 1200, "WIN-AUTH-V099": 1000, "WIN-OLD": 800}

    def add_admit(m):
        wid = m.group(1)
        n = admits[wid] if wid in admits else 1 + int(wid[5:]) % 4
        pool = pools[wid] if wid in pools else 600 + 100 * (int(wid[5:]) % 10)
        return m.group(0)[:-3] + ' admit="%d" timeout_pool="%d" />' % (n, pool)
    t, count = re.subn(r'<window id="([A-Z0-9-]+)" [^>]*? />', add_admit, t)
    assert count == 204 and t.count("admit=") == 204 and t.count("timeout_pool=") == 204, count
    write("effective_windows.xml", t)

    t = (SRC / "units_reference.txt").read_text()
    assert t.endswith("then apply timeout_ms_delta\n")
    t += ("timeout_ms_delta cutover: %d\n" % CUTOVER
          + "timeout_ms_delta stored: whole seconds on an override row whose version has an effective_from in "
          "policy_version_map.json before the cutover, milliseconds on every other override row\n"
          + "timeout floor: the timeout starts at the base in milliseconds and takes the amount each applied override adds, one at a time in ascending seq; whenever the running value falls below 1000 it is raised to 1000 before the next amount\n"
          + "timeout floor example: a base of 3000 with added amounts -900, -900, -800 and +500 runs 2100, 1200, 1000, 1500\n")
    write("units_reference.txt", t)

    t = (SRC / "tenant_catalog.xml").read_text()
    tail = "</tenants>"
    assert t.endswith(tail) and 't-aurora' not in t
    t = t[:-len(tail)] + "".join('<tenant id="%s" region="%s" status="active" />' % x for x in EXTRA_TENANTS) + tail
    write("tenant_catalog.xml", t)

    t = (SRC / "principal_role_index.yaml").read_text()
    assert t.endswith("guardian.role_level: 5\n")
    write("principal_role_index.yaml", t + "steward.param_key: K301\nsteward.tenant: t-aurora\nsteward.role_level: 3\n")

    add_xlsx_row(SRC / "tenant_multiplier_table.xlsx", DST / "tenant_multiplier_table.xlsx",
                 ["t-aurora", "1050", "320", "r-north"])

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
    t = t.replace(old15, new15)
    # test-hardening t2: null forms of an unresolved threshold.
    old14 = "policy_resolved = the resolved authoritative policy: exactly the flat config keys plus param_key, tenant, effective_version, risk_threshold, and no other keys"
    assert old14 in t
    t = t.replace(old14, old14 + "; risk_threshold is null when the threshold is unresolved")
    old_conv = "ending with the first value whose step change is within convergence_epsilon), converged"
    assert old_conv in t
    t = t.replace(old_conv, old_conv + " (null when the threshold is unresolved)")
    write("output_field_spec.txt", t)

    t = (SRC / "convergence_spec.txt").read_text()
    assert t.endswith("seed_value = base_threshold\n")
    t += "base_threshold = base_threshold of the threshold_tier_curve.parquet row whose tier equals the role_level of the resolved principal\n"
    # test-hardening t2: the divisor is fixed by the standing curve reports.
    t += ("iteration_divisor = fixed by the curve reports in override_deltas.json: it is the divisor under which every standing curve report, "
          "its curve computed for the role it names (that role's param_key, tenant and role_level in principal_role_index.yaml) by the rules "
          "that give the resolved principal its curve, converges to its reported converged value; with no standing curve report it is "
          "iteration_divisor in reconciliation_rules.conf. When the reports fix no single divisor, the threshold is unresolved: iterations "
          "holds only the seed value, and converged and risk_threshold are null\n")
    write("convergence_spec.txt", t)

    table = pq.read_table(SRC / "threshold_tier_curve.parquet")
    table = table.replace_schema_metadata({"tier": "the role_level of the resolved principal in principal_role_index.yaml"})
    pq.write_table(table, DST / "threshold_tier_curve.parquet", compression="snappy")

    # P12 v3 r3 (QC P2): the source alias table ships under a neutral name.
    shutil.copyfile(SRC / "decoy_alias_table.jsonc", DST / "principal_alias_table.jsonc")
    (DST / "decoy_alias_table.jsonc").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
