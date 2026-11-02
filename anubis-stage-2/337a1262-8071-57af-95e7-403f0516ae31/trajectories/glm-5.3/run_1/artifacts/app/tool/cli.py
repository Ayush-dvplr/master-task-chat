from __future__ import annotations

import argparse
import configparser
import json
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

# sentinel-ctl: policy bundle compiler.
# The compiled numbers are reconstructed from the reference material by walking
# the dependency chain each reference file points to, applying the rules that
# live in the file holding the data they govern.

JSON_INDENT = 2


def dump_json(data):
    return json.dumps(data, sort_keys=True, indent=JSON_INDENT) + "\n"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(dump_json(data), encoding="utf-8")


def coerce(value):
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if value in ("true", "false"):
        return value == "true"
    return value


def assert_flat(data):
    bad = [key for key, value in data.items() if isinstance(value, (dict, list))]
    if bad:
        raise SystemExit("configuration must be flat: " + ",".join(sorted(bad)))


def round_half_up(num, den):
    # glossary.txt: half_up = round .5 upward (ties go up)
    if den < 0:
        num, den = -num, -den
    return (2 * num + den) // (2 * den)


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def read_toml(path):
    import tomllib

    return tomllib.loads(read_text(path))


def read_jsonc(path):
    text = read_text(path)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", "", text)
    return json.loads(text)


def read_yaml_flat(path):
    out = {}
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ": " not in stripped and not stripped.endswith(":"):
            continue
        key, _, value = stripped.partition(":")
        out[key.strip()] = value.strip().strip('"')
    return out


def read_kv_text(path):
    # rule files: "key = value" or "key: value" lines, comments with # or ;
    out = {}
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        match = re.match(r"^([A-Za-z0-9_.\- ]+?)\s*=\s*(.*)$", stripped)
        if match:
            out[match.group(1).strip()] = match.group(2).strip()
            continue
        match = re.match(r"^([A-Za-z0-9_.\- ]+?):\s*(.*)$", stripped)
        if match:
            out[match.group(1).strip()] = match.group(2).strip()
    return out


def read_conf_sections(path):
    parser = configparser.ConfigParser(interpolation=None)
    with Path(path).open(encoding="utf-8") as handle:
        parser.read_file(handle)
    sections = {}
    for section in parser.sections():
        sections[section] = {key: value for key, value in parser.items(section)}
    return sections


def read_conf(path):
    flat = {}
    for section in read_conf_sections(path).values():
        flat.update(section)
    return flat


def conf_value(sections, key, default=None):
    for section in sections.values():
        if key in section:
            return section[key]
    return default


def read_pdf_text(path):
    raw = Path(path).read_bytes()
    chunks = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        chunk = match.group(1)
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            pass
        for token in re.findall(rb"\((?:[^()\\]|\\.)*\)", chunk):
            chunks.append(token[1:-1].decode("latin-1"))
    return "\n".join(chunks)


def read_xml_records(path, tag):
    root = ET.parse(path).getroot()
    return [dict(node.attrib) for node in root.iter(tag)]


def _col_to_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    idx = 0
    for char in letters:
        idx = idx * 26 + (ord(char) - ord("A") + 1)
    return idx - 1


def read_xlsx_rows(path):
    ns = "{" + "http" + "://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        sroot = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sroot.iter(ns + "row"):
            cells = {}
            for cell in row.iter(ns + "c"):
                ref = cell.get("r", "A1")
                col = _col_to_idx(ref)
                vnode = cell.find(ns + "v")
                if cell.get("t") == "inlineStr":
                    tnode = cell.find(ns + "is/" + ns + "t")
                    cells[col] = tnode.text if tnode is not None else ""
                else:
                    cells[col] = vnode.text if vnode is not None else ""
            rows.append(cells)
    header = [rows[0][i] for i in sorted(rows[0])]
    records = []
    for cells in rows[1:]:
        records.append({name: cells.get(i, "") for i, name in enumerate(header)})
    return records


def read_parquet_rows(path):
    import pyarrow.parquet as pq

    return pq.read_table(path).to_pylist()


class Resolver:
    """Walks the reference material in the order each file points to the next."""

    def __init__(self, data_dir):
        self.data = Path(data_dir)
        self.order = []
        self.rejects = {}

    def consume(self, name):
        if name not in self.order:
            self.order.append(name)
        return self.data / name

    def reject(self, entry_id, reason):
        reasons = self.rejects.setdefault(str(entry_id), [])
        if reason not in reasons:
            reasons.append(reason)

    def rejected_branches(self):
        return [
            {"id": entry_id, "reason": "; ".join(reasons)}
            for entry_id, reasons in sorted(self.rejects.items())
        ]

    def exists(self, name):
        return (self.data / name).is_file()

    def optional(self, reader, name):
        # reference files that only some corpora carry
        if not self.exists(name):
            return {}
        return reader(self.consume(name))

    def yaml_flat(self, name):
        return read_yaml_flat(self.consume(name))

    def kv(self, name):
        return read_kv_text(self.consume(name))

    def conf(self, name):
        return read_conf_sections(self.consume(name))

    def json_file(self, name):
        return load_json(self.consume(name))

    def jsonc(self, name):
        return read_jsonc(self.consume(name))

    def toml(self, name):
        return read_toml(self.consume(name))

    def xml(self, name, tag):
        return read_xml_records(self.consume(name), tag)

    def xlsx(self, name):
        return read_xlsx_rows(self.consume(name))

    def parquet(self, name):
        return read_parquet_rows(self.consume(name))


def resolve_policy(data_dir):
    rs = Resolver(data_dir)

    # 1. boot manifest: the entry point of the chain.
    manifest = rs.toml("boot_manifest.toml")["manifest"]
    instant = int(manifest["effective_instant"])
    schema_ref = str(manifest.get("schema_ref", "config_schema.json"))
    trailer_ref = str(manifest.get("trailer_ref", "defaults.json"))
    ledger_ref = str(manifest.get("ledger_ref", "bundle_ledger.jsonc"))

    # 2. stale version rules: which manifest key names the bundle in force.
    stale = rs.optional(read_kv_text, "stale_version_rules.txt")
    prefer_key = str(stale.get("prefer", "active_bundle_id"))
    ignore_key = str(stale.get("ignore", "latest_bundle_id"))
    active_bundle = str(manifest[prefer_key])
    ignored_bundle = str(manifest[ignore_key]) if ignore_key in manifest else None
    if ignored_bundle and ignored_bundle != active_bundle:
        rs.reject(
            ignored_bundle,
            "%s in boot_manifest.toml ignored; stale_version_rules.txt prefers %s"
            % (ignore_key, prefer_key),
        )
    retired_bundle = stale.get("retired_bundle")
    if retired_bundle and str(retired_bundle) != active_bundle:
        rs.reject(str(retired_bundle), "retired bundle named by stale_version_rules.txt")

    # 3. supersession record.
    migration = rs.optional(read_yaml_flat, "migration_notice.yml")
    if migration.get("active_bundle") and str(migration["active_bundle"]) != active_bundle:
        rs.reject(
            str(migration["active_bundle"]),
            "active_bundle in migration_notice.yml disagrees with the boot manifest",
        )
    superseded_bundle = migration.get("superseded_bundle")
    if superseded_bundle and str(superseded_bundle) != active_bundle:
        rs.reject(
            str(superseded_bundle),
            "superseded by bundle %s in migration_notice.yml (effective_from %s)"
            % (active_bundle, migration.get("effective_from")),
        )

    # 4. bundle ledger, reached through the manifest's ledger_ref.
    ledger = rs.jsonc(ledger_ref)
    if active_bundle not in ledger:
        raise SystemExit("bundle not in ledger: " + active_bundle)
    bundle_entry = ledger[active_bundle]
    role_key = str(bundle_entry["role_key"])
    index_file = str(bundle_entry["index_file"])
    for bundle_id in sorted(ledger):
        if bundle_id == active_bundle:
            continue
        status = str(ledger[bundle_id].get("status", ""))
        if status in ("superseded", "retired", "withdrawn"):
            rs.reject(
                bundle_id,
                "status %s in %s; %s is the bundle in force"
                % (status, ledger_ref, active_bundle),
            )

    # 5. principal role index, reached through the ledger's index_file.
    index = rs.yaml_flat(index_file)
    param_key = str(index[role_key + ".param_key"])
    tenant = str(index[role_key + ".tenant"])
    role_level = int(index[role_key + ".role_level"])
    overrides_ref = str(index.get("overrides_ref", "override_deltas.json"))

    # 6. numeric base table.
    base_rows = {str(row["param_key"]): row for row in rs.parquet("base_parameters.parquet")}
    if param_key not in base_rows:
        raise SystemExit("param_key not in base parameters: " + param_key)
    base = base_rows[param_key]

    # 7. version map: the greatest effective_from not after the instant.
    version_doc = rs.json_file("policy_version_map.json")
    effective_from = {}
    effective_version = None
    best_from = None
    for entry in version_doc["versions"]:
        version = str(entry["version"])
        started = int(entry["effective_from"])
        effective_from[version] = started
        if started <= instant and (best_from is None or started > best_from):
            best_from = started
            effective_version = version

    # 8. effective windows (half-open spans).
    windows = {}
    for window in rs.xml("effective_windows.xml", "window"):
        windows[str(window["id"])] = {
            "id": str(window["id"]),
            "start": int(window["start"]),
            "end": int(window["end"]),
            "version": str(window.get("version", "")),
            "admit": int(window.get("admit", 0)),
            "timeout_pool": int(window.get("timeout_pool", 0)),
        }

    # 9. superseded window set: rejected in full.
    if rs.exists("superseded_windows.xml"):
        superseded_windows = rs.xml("superseded_windows.xml", "window")
        statuses = sorted({str(w.get("status", "superseded")) for w in superseded_windows})
        rs.reject(
            "superseded_windows.xml",
            "superseded window set (%d windows, status %s) rejected; only effective_windows.xml admits rows"
            % (len(superseded_windows), "/".join(statuses)),
        )

    # 10. override deltas, reached through the role index's overrides_ref.
    ledger_doc = rs.json_file(overrides_ref)
    overrides = list(ledger_doc["overrides"])
    controls = ledger_doc.get("controls", {})
    aliases = ledger_doc.get("param_key_aliases") or []
    reports = [r for r in (ledger_doc.get("reports") or []) if r.get("kind") == "curve"]
    resets = [r for r in (ledger_doc.get("resets") or []) if r.get("kind") == "reset"]

    # 11. override precedence rules.
    precedence = rs.conf("override_precedence.conf")
    pool_rule = str(conf_value(precedence, "timeout_pool", ""))
    pool_min_match = re.search(r"below (\d+) adds none", pool_rule)
    pool_min = int(pool_min_match.group(1)) if pool_min_match else 100

    # 12. tenant multipliers.
    multipliers = {str(row["tenant"]): row for row in rs.xlsx("tenant_multiplier_table.xlsx")}
    if tenant not in multipliers:
        raise SystemExit("tenant not in multiplier table: " + tenant)
    mult_bps = int(multipliers[tenant]["mult_bps"])
    cap = int(multipliers[tenant]["max_records_cap"])

    # 13. tenant regions and the override allowance keyed by them.
    regions = {
        str(row["id"]): str(row["region"])
        for row in rs.xml("tenant_catalog.xml", "tenant")
    }
    quota = rs.conf("quota_limits.cfg")
    allowance = {}
    for section in quota.values():
        allowance.update(section)

    # 14. threshold tier curve.
    tiers = {int(row["tier"]): row for row in rs.parquet("threshold_tier_curve.parquet")}

    # 15. convergence spec and reconciliation rules.
    convergence = rs.kv("convergence_spec.txt")
    epsilon = int(convergence.get("convergence_epsilon", 0))
    max_iterations = int(convergence.get("max_iterations", 64))
    reconcile = rs.conf("reconciliation_rules.conf")
    conf_divisor = int(conf_value(reconcile, "iteration_divisor", 10))
    unit_factor = int(conf_value(reconcile, "timeout_unit_factor", 1000))
    divisor_lo, divisor_hi = 6, 14
    span = re.search(r"whole number from (\d+) to (\d+)", read_text(rs.data / "reconciliation_rules.conf"))
    if span:
        divisor_lo, divisor_hi = int(span.group(1)), int(span.group(2))

    # 16. clamp, rounding and unit conventions.
    rs.kv("clamp_rules.txt")
    rs.kv("risk_weight_rounding.txt")
    units = rs.kv("units_reference.txt")
    factor = unit_factor
    conversion = next((v for k, v in units.items() if k.startswith("conversion")), "")
    conv_match = re.search(r"\*\s*(\d+)\s*$", conversion)
    if conv_match:
        factor = int(conv_match.group(1))
    cutover_key = next((k for k in units if "cutover" in k), None)
    cutover = int(units[cutover_key]) if cutover_key else 0
    floor_match = re.search(r"falls below (\d+)", read_text(rs.data / "units_reference.txt"))
    timeout_floor = int(floor_match.group(1)) if floor_match else 1000

    # 17. legacy material, consumed only to be rejected.
    if rs.exists("legacy_override_table.ini"):
        legacy = read_conf_sections(rs.consume("legacy_override_table.ini"))
        legacy_ids = sorted(legacy)
        legacy_rows = sorted({key for section in legacy.values() for key in section})
        rs.reject(
            "legacy_override_table.ini",
            "legacy override table (sections %s, keys %s) of a retired bundle; %s is the authoritative override source"
            % (",".join(legacy_ids), ",".join(legacy_rows), overrides_ref),
        )
    if rs.exists("principal_alias_table.jsonc"):
        alias_doc = read_jsonc(rs.consume("principal_alias_table.jsonc"))
        rs.reject(
            "principal_alias_table.jsonc",
            "conflicting aliases from a retired bundle (%s); the resolved principal keeps %s and %s"
            % (",".join(sorted(alias_doc)), param_key, tenant),
        )
    if rs.exists("legacy_policy_memo.pdf"):
        read_pdf_text(rs.consume("legacy_policy_memo.pdf"))
        rs.reject(
            "legacy_policy_memo.pdf",
            "legacy memo retained for audit only; its numbers are never compiled",
        )

    # 18. request corpus: the client claim is never the effective version.
    claimed_version = None
    if rs.exists("request_corpus.json"):
        entries = rs.json_file("request_corpus.json").get("entries") or []
        if entries:
            claimed_version = str(entries[0].get("claimed_version"))

    # 19. identity fields, reached through the manifest's refs.
    defaults = rs.json_file(trailer_ref)
    schema = rs.json_file(schema_ref)
    trailer = str(defaults["base_config"]["trailer"])
    checksum = str(defaults.get("checksum", schema.get("checksum", "crc32")))
    mode = str(defaults.get("mode", "strict-local"))
    profile = str(schema["profile"])
    producer = str(schema["producer"])
    container = str(schema["container"])

    # ---- override draw ----------------------------------------------
    alias_map = {
        str(entry["alias"]): (str(entry["principal"]), int(entry["start"]), int(entry["end"]))
        for entry in aliases
    }

    def row_principal(row):
        # param_key_aliases: a row keyed by the alias is an override of the
        # aliased principal only inside the half-open alias span.
        target = alias_map.get(str(row["param_key"]))
        if target is None:
            return str(row["param_key"])
        if target[1] <= instant < target[2]:
            return target[0]
        return None

    def delta_ms(row):
        # units_reference.txt: whole seconds before the cutover, ms afterwards
        started = effective_from.get(str(row["version"]))
        value = int(row["timeout_ms_delta"])
        if started is not None and started < cutover:
            return value * factor
        return value

    highest = {}
    by_override_id = {}
    for row in overrides:
        override_id = str(row["override_id"])
        seq = int(row["seq"])
        if override_id not in highest or seq > highest[override_id]:
            highest[override_id] = seq
        by_override_id.setdefault(override_id, []).append(row)
    for rows in by_override_id.values():
        rows.sort(key=lambda r: int(r["seq"]))

    def last_active_before(seq, override_id):
        best = None
        for row in by_override_id.get(override_id, ()):
            if str(row["status"]) != "active" or int(row["seq"]) >= seq:
                continue
            if best is None or int(row["seq"]) > int(best["seq"]):
                best = row
        return best

    candidates = []
    carry_rows = []
    for row in sorted(overrides, key=lambda r: int(r["seq"])):
        override_id = str(row["override_id"])
        seq = int(row["seq"])
        status = str(row["status"])
        # a reissued override is only the row stored at its highest seq
        if seq != highest[override_id]:
            continue
        if status == "withdrawn":
            continue
        window = windows.get(str(row["window_id"]))
        in_window = bool(window) and window["start"] <= instant < window["end"]
        version_ok = bool(window) and str(row["version"]) == effective_version and window["version"] == effective_version
        if status == "superseded":
            if "carry" in row and in_window and version_ok:
                carry_rows.append(row)
            continue
        if status not in ("active", "reinstated"):
            continue
        if not in_window or not version_ok:
            continue
        if status == "reinstated":
            source = last_active_before(seq, override_id)
            if source is None:
                continue
            row = dict(row)
            row["_source"] = source
        candidates.append(row)

    applied = []
    applied_ids = set()
    allowance_left = {}
    admit_left = {}
    for row in candidates:
        window_id = str(row["window_id"])
        override_id = str(row["override_id"])
        region = regions.get(str(row["tenant"]))
        if region is None:
            continue
        if region not in allowance_left:
            try:
                allowance_left[region] = int(allowance[region])
            except (KeyError, ValueError):
                allowance_left[region] = 0
        if window_id not in admit_left:
            admit_left[window_id] = windows[window_id]["admit"]
        requires = row.get("requires")
        if requires is not None and str(requires) not in applied_ids:
            continue
        if allowance_left[region] <= 0 or admit_left[window_id] <= 0:
            continue
        allowance_left[region] -= 1
        admit_left[window_id] -= 1
        applied.append(row)
        applied_ids.add(override_id)

    def row_source(row):
        # a reinstated row adds the deltas of the active row it restates
        return row.get("_source", row)

    # timeout_pool: the positive deltas of one window share that window's pool
    amounts = {}
    by_window = {}
    for row in applied:
        by_window.setdefault(str(row["window_id"]), []).append(row)
    for window_id, rows in by_window.items():
        pool = windows[window_id]["timeout_pool"]
        positive = []
        for row in rows:
            value = delta_ms(row_source(row))
            if value > 0:
                positive.append((row, value))
            else:
                amounts[int(row["seq"])] = value
        if not positive:
            continue
        summed = sum(value for _, value in positive)
        if summed <= pool:
            for row, value in positive:
                amounts[int(row["seq"])] = value
            continue
        shared = {int(row["seq"]): (pool * value) // summed for row, value in positive}
        keep = [(row, value) for row, value in positive if shared[int(row["seq"])] >= pool_min]
        for row, value in positive:
            if shared[int(row["seq"])] < pool_min:
                amounts[int(row["seq"])] = 0
        if keep:
            resummed = sum(value for _, value in keep)
            for row, value in keep:
                amounts[int(row["seq"])] = (pool * value) // resummed

    def applied_for(principal):
        return [row for row in applied if row_principal(row) == principal]

    def carry_for(principal):
        return [row for row in carry_rows if row_principal(row) == principal]

    def contribution_for(principal, tenant_name):
        # risk_weight_rounding.txt: every term is scaled and rounded on its own
        if principal not in base_rows or tenant_name not in multipliers:
            return None
        terms = [int(base_rows[principal]["risk_weight_base"])]
        for row in applied_for(principal):
            terms.append(int(row_source(row)["risk_delta"]))
        for row in carry_for(principal):
            if str(row.get("carry")) == "risk_delta":
                terms.append(int(row["risk_delta"]))
        bps = int(multipliers[tenant_name]["mult_bps"])
        return sum(round_half_up(term * bps, 1000) for term in terms)

    def curve_for(principal, tenant_name, level, divisor):
        # convergence_spec.txt: seed at the tier base, step until within epsilon
        if int(level) not in tiers:
            return None, None
        base_threshold = int(tiers[int(level)]["base_threshold"])
        contribution = contribution_for(principal, tenant_name)
        if contribution is None:
            # the role the report names has no curve of its own, so the report
            # cannot be satisfied by any divisor
            return None, None
        value = base_threshold
        iterations = [value]
        converged = None
        for _ in range(max(0, max_iterations)):
            nxt = base_threshold + (contribution + value) // divisor
            iterations.append(nxt)
            if abs(nxt - value) <= epsilon:
                converged = nxt
                break
            value = nxt
        return iterations, converged

    standing = [
        report
        for report in reports
        if not any(int(reset["seq"]) > int(report["seq"]) for reset in resets)
    ]
    divisor = None
    if not standing:
        divisor = conf_divisor
    else:
        fixed = []
        for candidate in range(divisor_lo, divisor_hi + 1):
            ok = True
            for report in standing:
                role = str(report["role"])
                if role + ".param_key" not in index:
                    ok = False
                    break
                principal = str(index[role + ".param_key"])
                tenant_name = str(index[role + ".tenant"])
                level = int(index[role + ".role_level"])
                _, converged = curve_for(principal, tenant_name, level, candidate)
                if converged is None or converged != int(report["converged"]):
                    ok = False
                    break
            if ok:
                fixed.append(candidate)
        if len(fixed) == 1:
            divisor = fixed[0]

    base_threshold = int(tiers[role_level]["base_threshold"]) if role_level in tiers else None
    iterations = None
    converged = None
    if divisor is not None and base_threshold is not None:
        iterations, converged = curve_for(param_key, tenant, role_level, divisor)
    if converged is None:
        # threshold unresolved: iterations holds only the seed value
        iterations = [base_threshold] if base_threshold is not None else []
    risk_threshold = converged

    # ---- compiled scalars -------------------------------------------
    after_delta = int(base["max_records_base"])
    for row in applied_for(param_key):
        after_delta += int(row_source(row)["max_records_delta"])
    for row in carry_for(param_key):
        if str(row.get("carry")) == "max_records_delta":
            after_delta += int(row["max_records_delta"])
    # clamp_rules.txt: scale after the deltas, then clamp to the cap
    scaled = round_half_up(after_delta * mult_bps, 1000)
    max_records = min(cap, scaled)

    retry_limit = int(base["retry_limit_base"])
    for row in applied_for(param_key):
        retry_limit += int(row_source(row)["retry_limit_delta"])

    timeout_ms = int(base["timeout_seconds_base"]) * factor
    for row in sorted(applied_for(param_key), key=lambda r: int(r["seq"])):
        timeout_ms += amounts[int(row["seq"])]
        if timeout_ms < timeout_floor:
            timeout_ms = timeout_floor

    contribution = contribution_for(param_key, tenant)

    resolved = {
        "profile": profile,
        "producer": producer,
        "container": container,
        "checksum": checksum,
        "mode": mode,
        "trailer": trailer,
        "max_records": max_records,
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "risk_threshold": risk_threshold,
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": effective_version,
    }

    # ---- ledger controls and repairs --------------------------------
    sums = {}
    for row in overrides:
        entry = sums.setdefault(
            str(row["tenant"]),
            {"rows": 0, "max_records_delta_sum": 0, "timeout_ms_delta_sum_ms": 0},
        )
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += delta_ms(row)

    ledger_controls = {}
    for name in controls:
        control = controls[name]
        computed = sums.get(
            name,
            {"rows": 0, "max_records_delta_sum": 0, "timeout_ms_delta_sum_ms": 0},
        )
        ledger_controls[name] = (
            "ok"
            if computed["rows"] == int(control["rows"])
            and computed["max_records_delta_sum"] == int(control["max_records_delta_sum"])
            and computed["timeout_ms_delta_sum_ms"] == int(control["timeout_ms_delta_sum_ms"])
            else "mismatch"
        )

    spare = []
    for row in overrides:
        override_id = str(row["override_id"])
        seq = int(row["seq"])
        status = str(row["status"])
        is_spare = (
            status == "withdrawn"
            or (status == "superseded" and "carry" not in row)
            or seq != highest[override_id]
        )
        if not is_spare:
            continue
        if status == "active" and seq != highest[override_id]:
            rows_of_id = by_override_id[override_id]
            top_status = str(rows_of_id[-1]["status"])
            if top_status == "reinstated":
                # the restated active row is never spare
                earlier = [
                    row2
                    for row2 in rows_of_id
                    if str(row2["status"]) == "active" and int(row2["seq"]) < highest[override_id]
                ]
                if earlier and int(earlier[-1]["seq"]) == seq:
                    continue
        spare.append(row)

    def best_repair(name):
        # A repair is a set of the tenant's spare rows whose removal leaves the
        # stored row count and both sums equal to the control entry; of all
        # repairs the tenant takes the one with the smallest total of absolute
        # timeout deltas, ties going to the first ascending seq list.
        control = controls[name]
        tenant_rows = [row for row in overrides if str(row["tenant"]) == name]
        spare_rows = sorted(
            [row for row in spare if str(row["tenant"]) == name],
            key=lambda r: int(r["seq"]),
        )
        need_rows = len(tenant_rows) - int(control["rows"])
        need_mr = sum(int(row["max_records_delta"]) for row in tenant_rows) - int(control["max_records_delta_sum"])
        need_ms = sum(delta_ms(row) for row in tenant_rows) - int(control["timeout_ms_delta_sum_ms"])
        if need_rows < 0 or need_rows > len(spare_rows):
            return None
        order = [
            (int(row["seq"]), int(row["max_records_delta"]), delta_ms(row))
            for row in spare_rows
        ]
        size = len(order)
        suffix_count = [0] * (size + 1)
        suffix_low = [(0, 0)] * (size + 1)
        suffix_high = [(0, 0)] * (size + 1)
        for idx in range(size - 1, -1, -1):
            seq, mr, row_ms = order[idx]
            suffix_count[idx] = suffix_count[idx + 1] + 1
            low_mr, low_ms = suffix_low[idx + 1]
            high_mr, high_ms = suffix_high[idx + 1]
            suffix_low[idx] = (low_mr + min(mr, 0), low_ms + min(row_ms, 0))
            suffix_high[idx] = (high_mr + max(mr, 0), high_ms + max(row_ms, 0))
        cheapest = sorted(abs(item[2]) for item in order)
        cheapest_sum = [0] * (len(cheapest) + 1)
        for idx, value in enumerate(cheapest):
            cheapest_sum[idx + 1] = cheapest_sum[idx] + value
        # the extremes a given number of further rows can add: taking k rows
        # cannot fall below the k smallest of their values nor above the k largest
        mr_values = sorted(item[1] for item in order)
        ms_values = sorted(item[2] for item in order)
        low_mr = [0] * (size + 1)
        high_mr = [0] * (size + 1)
        low_ms = [0] * (size + 1)
        high_ms = [0] * (size + 1)
        for idx in range(size):
            low_mr[idx + 1] = low_mr[idx] + mr_values[idx]
            low_ms[idx + 1] = low_ms[idx] + ms_values[idx]
            high_mr[idx + 1] = high_mr[idx] + mr_values[size - 1 - idx]
            high_ms[idx + 1] = high_ms[idx] + ms_values[size - 1 - idx]

        def can_reach(idx, count, mr_sum, ms_sum):
            more = need_rows - count
            if more < 0 or suffix_count[idx] < more:
                return False
            if not low_mr[more] <= need_mr - mr_sum <= high_mr[more]:
                return False
            if not low_ms[more] <= need_ms - ms_sum <= high_ms[more]:
                return False
            floor_mr, floor_ms = suffix_low[idx]
            top_mr, top_ms = suffix_high[idx]
            if not floor_mr <= need_mr - mr_sum <= top_mr:
                return False
            return floor_ms <= need_ms - ms_sum <= top_ms

        # pass one: the cheapest repair, as a subset-sum over the three targets
        states = {(0, 0, 0): 0}
        for idx, (seq, mr, row_ms) in enumerate(order):
            following = idx + 1
            step = []
            for key in sorted(states):
                if key[0] > need_rows:
                    continue
                step.append((key, states[key]))
                cost = states[key]
                count, mr_sum, ms_sum = key
                if count + 1 > need_rows:
                    continue
                if not can_reach(following, count + 1, mr_sum + mr, ms_sum + row_ms):
                    continue
                candidate = (count + 1, mr_sum + mr, ms_sum + row_ms)
                total = cost + abs(row_ms)
                if states.get(candidate, total + 1) > total:
                    states[candidate] = total
            for key, cost in step:
                count, mr_sum, ms_sum = key
                if not can_reach(following, count, mr_sum, ms_sum):
                    del states[key]
            if len(states) > 400_000:
                states = None
                break
        target_cost = None
        if states is not None:
            target_cost = states.get((need_rows, need_mr, need_ms))
            if target_cost is None:
                return None

        # pass two: walk the rows in ascending seq taking before skipping, so the
        # first repair of the cheapest cost is the one with the first seq list
        best = {"chosen": None}
        budget = [2_000_000]

        def walk(idx, count, mr_sum, ms_sum, cost, chosen):
            if best["chosen"] is not None:
                return
            if count == need_rows and mr_sum == need_mr and ms_sum == need_ms:
                if target_cost is None or cost == target_cost:
                    best["chosen"] = chosen
                return
            if idx >= size or count > need_rows:
                return
            if not can_reach(idx, count, mr_sum, ms_sum):
                return
            if target_cost is not None:
                if cost + cheapest_sum[need_rows - count] > target_cost:
                    return
            budget[0] -= 1
            if budget[0] < 0:
                return
            seq, mr, row_ms = order[idx]
            walk(idx + 1, count + 1, mr_sum + mr, ms_sum + row_ms, cost + abs(row_ms), chosen + [seq])
            walk(idx + 1, count, mr_sum, ms_sum, cost, chosen)

        walk(0, 0, 0, 0, 0, [])
        return best["chosen"]

    ledger_repair = {}
    for name in sorted(ledger_controls):
        if ledger_controls[name] == "mismatch":
            ledger_repair[name] = best_repair(name)

    trace = {
        "active_bundle": active_bundle,
        "effective_version": effective_version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": claimed_version is None or claimed_version != effective_version,
        "applied_overrides": [
            str(row["override_id"])
            for row in sorted(applied_for(param_key), key=lambda r: int(r["seq"]))
        ],
        "ledger_controls": ledger_controls,
        "resolution_order": list(rs.order),
        "rejected_branches": rs.rejected_branches(),
    }

    curve = {
        "tier": role_level,
        "base_threshold": base_threshold,
        "contribution": contribution,
        "iterations": iterations,
        "converged": converged,
    }

    return resolved, trace, curve, ledger_repair


def cmd_init(args):
    schema = load_json(args.schema)
    data = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema["checksum"],
        "mode": str(schema.get("mode", "strict-local")),
    }
    write_json(args.out, data)
    print("initialized")


def cmd_resolve(args):
    resolved, trace, curve, ledger_repair = resolve_policy(args.data_dir)
    out = Path(args.out)
    write_json(out / "policy_resolved.json", resolved)
    write_json(out / "dependency_trace.json", trace)
    write_json(out / "threshold_curve.json", curve)
    write_json(out / "ledger_repair.json", ledger_repair)
    print(dump_json(resolved), end="")


def cmd_set(args):
    data = load_json(args.config)
    data[args.key] = coerce(args.value)
    assert_flat(data)
    write_json(args.config, data)
    print("set " + args.key)


def cmd_validate(args):
    schema = load_json(args.schema)
    data = load_json(args.config)
    assert_flat(data)
    required = schema.get("required_keys", [])
    if isinstance(required, str):
        required = [key.strip() for key in required.split(",") if key.strip()]
    missing = [key for key in required if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    print("ok")


def cmd_report(args):
    data = load_json(args.config)
    commands = json.loads(args.commands)
    report = {
        "ok": True,
        "tool": "sentinel-ctl",
        "commands": commands,
        "config_sha256": args.digest,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def main():
    parser = argparse.ArgumentParser(prog="sentinel-ctl")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init")
    p.add_argument("--schema", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("resolve")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("set")
    p.add_argument("--config", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("validate")
    p.add_argument("--schema", required=True)
    p.add_argument("--config", required=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
