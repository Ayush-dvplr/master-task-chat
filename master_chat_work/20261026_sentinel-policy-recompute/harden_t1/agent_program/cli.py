from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# sentinel-ctl: policy bundle compiler.

BPS_DENOMINATOR = 1000
MIN_POOL_SHARE_MS = 100
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
ZIP_MODE = 0o644


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, sort_keys=True, indent=2) + "\n"
    Path(path).write_text(text, encoding="utf-8")


def read_commands(value):
    """Accept a command transcript either inline or as a path to a JSON file."""
    if Path(value).is_file():
        return load_json(value)
    return json.loads(value)


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


def is_scalar_flat(data):
    return all(isinstance(value, (str, int, float, bool)) or value is None for value in data.values())


def read_toml(path):
    import tomllib

    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonc(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", "", text)
    return json.loads(text)


def read_yaml_flat(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        out[key.strip()] = value.strip().strip('"')
    return out


def read_rules(path):
    """Parse a rule sheet of `key = value` / `key: value` lines.

    Rule prose carries both delimiters, so the one appearing first wins.
    """
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        positions = [stripped.index(d) for d in ("=", ":") if d in stripped]
        if not positions:
            continue
        cut = min(positions)
        out[stripped[:cut].strip()] = stripped[cut + 1 :].strip()
    return out


def _parser():
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    return parser


def read_conf_sections(path):
    parser = _parser()
    parser.read(path, encoding="utf-8")
    return {section: dict(parser.items(section)) for section in parser.sections()}


def read_conf(path):
    flat = {}
    for values in read_conf_sections(path).values():
        flat.update(values)
    return flat


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


def scale_half_up(value, mult_bps):
    """round_half_up(value * mult_bps / BPS_DENOMINATOR) in exact integers."""
    return (2 * value * mult_bps + BPS_DENOMINATOR) // (2 * BPS_DENOMINATOR)


def resolve_policy(data_dir):
    data = Path(data_dir)
    order = []

    def consume(name):
        if name not in order:
            order.append(name)
        return data / name

    rejected = []

    manifest = read_toml(consume("boot_manifest.toml"))["manifest"]
    instant = int(manifest["effective_instant"])

    stale = read_rules(consume("stale_version_rules.txt"))
    preferred_field = stale["prefer"]
    ignored_field = stale["ignore"]
    superseded_status = stale["superseded_marker"].split(":")[-1]

    ledger = read_jsonc(consume("bundle_ledger.jsonc"))
    active_bundle = str(manifest[preferred_field])
    ignored_bundle = str(manifest[ignored_field])
    migration = read_yaml_flat(consume("migration_notice.yml"))
    rejected.append(
        {
            "id": ignored_bundle,
            "reason": (
                "bundle {} is the {} and is {} in bundle_ledger.jsonc; stale_version_rules.txt "
                "prefers {}={} and migration_notice.yml records it as superseded by {}".format(
                    ignored_bundle,
                    ignored_field,
                    ledger[ignored_bundle]["status"],
                    preferred_field,
                    active_bundle,
                    migration.get("active_bundle", active_bundle),
                )
            ),
        }
    )
    rejected.append(
        {
            "id": ledger[ignored_bundle]["role_key"],
            "reason": "role_key of the {} bundle {}; not reachable from {}={}".format(
                ledger[ignored_bundle]["status"], ignored_bundle, preferred_field, active_bundle
            ),
        }
    )

    bundle = ledger[active_bundle]
    role_key = bundle["role_key"]
    index = read_yaml_flat(consume(bundle["index_file"]))
    param_key = index[role_key + ".param_key"]
    tenant = index[role_key + ".tenant"]
    role_level = int(index[role_key + ".role_level"])
    legacy_param_key = index[ledger[ignored_bundle]["role_key"] + ".param_key"]
    rejected.append(
        {
            "id": legacy_param_key,
            "reason": "param_key of the {} bundle {}; the resolved principal is {}".format(
                ledger[ignored_bundle]["status"], ignored_bundle, param_key
            ),
        }
    )
    rejected.append(
        {
            "id": "legacy_override_table.ini",
            "reason": (
                "legacy override table of bundle {}, marked status {}; applied overrides are read "
                "from override_deltas.json".format(ignored_bundle, ledger[ignored_bundle]["status"])
            ),
        }
    )
    rejected.append(
        {
            "id": "principal_alias_table.jsonc",
            "reason": "retired-bundle aliases that remap the resolved tenant and param_key; the file states they must not be used",
        }
    )
    rejected.append(
        {
            "id": "legacy_policy_memo.pdf",
            "reason": "audit-only memo for the {} bundle {}; it states its numbers must not be compiled".format(
                ledger[ignored_bundle]["status"], ignored_bundle
            ),
        }
    )

    base_rows = {row["param_key"]: row for row in read_parquet_rows(consume("base_parameters.parquet"))}
    base = base_rows[param_key]

    version_map = load_json(consume("policy_version_map.json"))
    effective_from = {row["version"]: int(row["effective_from"]) for row in version_map["versions"]}
    version = max(
        (row for row in version_map["versions"] if int(row["effective_from"]) <= instant),
        key=lambda row: int(row["effective_from"]),
    )["version"]

    units = read_rules(consume("units_reference.txt"))
    cutover = int(units["timeout_ms_delta cutover"])
    reconcile = read_conf(consume("reconciliation_rules.conf"))
    unit_factor = int(reconcile["timeout_unit_factor"])
    divisor = int(reconcile["iteration_divisor"])

    def timeout_delta_ms(row):
        stored = int(row["timeout_ms_delta"])
        if effective_from[row["version"]] < cutover:
            return stored * unit_factor
        return stored

    windows = {w["id"]: w for w in read_xml_records(consume("effective_windows.xml"), "window")}
    rejected.append(
        {
            "id": "superseded_windows.xml",
            "reason": "every window there carries status {}; effective-time windows are read from effective_windows.xml".format(
                superseded_status
            ),
        }
    )

    precedence = read_conf(consume("override_precedence.conf"))
    if precedence["select"] != "active status only":
        raise SystemExit("unexpected override selection rule: " + precedence["select"])

    ledger_doc = load_json(consume("override_deltas.json"))
    rows = sorted(ledger_doc["overrides"], key=lambda row: int(row["seq"]))

    sums = {}
    for row in rows:
        entry = sums.setdefault(
            row["tenant"], {"max_records_delta_sum": 0, "rows": 0, "timeout_ms_delta_sum_ms": 0}
        )
        entry["rows"] += 1
        entry["max_records_delta_sum"] += int(row["max_records_delta"])
        entry["timeout_ms_delta_sum_ms"] += timeout_delta_ms(row)
    ledger_controls = {
        name: ("ok" if sums.get(name) == control else "mismatch")
        for name, control in ledger_doc["controls"].items()
    }

    def selection_failure(row):
        if row["status"] != "active":
            return "override status is {}".format(row["status"])
        window = windows.get(row["window_id"])
        if window is None:
            return "window {} is absent from effective_windows.xml".format(row["window_id"])
        if not int(window["start"]) <= instant < int(window["end"]):
            return (
                "window {} is the half-open interval [{}, {}) and does not contain "
                "effective_instant {}".format(row["window_id"], window["start"], window["end"], instant)
            )
        if row["version"] != version:
            return "override version {} is not the effective version {}".format(row["version"], version)
        if window["version"] != version:
            return "window {} carries version {}, not the effective version {}".format(
                row["window_id"], window["version"], version
            )
        return None

    passed = [row for row in rows if selection_failure(row) is None]

    tenants = {t["id"]: t for t in read_xml_records(consume("tenant_catalog.xml"), "tenant")}
    allowance = {
        region: int(count)
        for region, count in read_conf_sections(consume("quota_limits.cfg"))["override_allowance"].items()
    }

    admit_left = {wid: int(window["admit"]) for wid, window in windows.items()}
    allowance_left = dict(allowance)
    applied = []
    refused = {}
    for row in passed:
        region = tenants[row["tenant"]]["region"]
        if allowance_left[region] > 0 and admit_left[row["window_id"]] > 0:
            allowance_left[region] -= 1
            admit_left[row["window_id"]] -= 1
            applied.append(row)
        else:
            refused[row["override_id"]] = (
                "refused by draw_order: region {} allowance or window {} admit count was exhausted at seq {}".format(
                    region, row["window_id"], row["seq"]
                )
            )

    added_ms = {}
    for wid in sorted({row["window_id"] for row in applied}):
        pool = int(windows[wid]["timeout_pool"])
        members = [row for row in applied if row["window_id"] == wid]
        positive = [row for row in members if timeout_delta_ms(row) > 0]
        for row in members:
            if timeout_delta_ms(row) <= 0:
                added_ms[row["override_id"]] = timeout_delta_ms(row)
        total = sum(timeout_delta_ms(row) for row in positive)
        if total == 0:
            continue
        if total <= pool:
            for row in positive:
                added_ms[row["override_id"]] = timeout_delta_ms(row)
            continue
        share = {row["override_id"]: (pool * timeout_delta_ms(row)) // total for row in positive}
        kept = [row for row in positive if share[row["override_id"]] >= MIN_POOL_SHARE_MS]
        if len(kept) == len(positive):
            added_ms.update(share)
            continue
        kept_total = sum(timeout_delta_ms(row) for row in kept)
        for row in positive:
            if row in kept:
                added_ms[row["override_id"]] = (pool * timeout_delta_ms(row)) // kept_total
            else:
                added_ms[row["override_id"]] = 0

    mine = [row for row in applied if row["param_key"] == param_key]
    applied_overrides = [row["override_id"] for row in mine]
    for row in rows:
        if row["param_key"] != param_key:
            continue
        reason = selection_failure(row) or refused.get(row["override_id"])
        if reason is not None:
            rejected.append({"id": row["override_id"], "reason": reason})

    multipliers = {row["tenant"]: row for row in read_xlsx_rows(consume("tenant_multiplier_table.xlsx"))}
    multiplier = multipliers[tenant]
    mult_bps = int(multiplier["mult_bps"])
    cap = int(multiplier["max_records_cap"])
    rejected.append(
        {
            "id": "tenant_region_multipliers.xlsx",
            "reason": (
                "region_bps sheet carrying no row for the resolved tenant {}; the tenant multiplier "
                "and cap come from tenant_multiplier_table.xlsx".format(tenant)
            ),
        }
    )

    clamp = read_rules(consume("clamp_rules.txt"))
    if "round_half_up" not in clamp["scaled"]:
        raise SystemExit("unexpected max_records clamp rule: " + clamp["scaled"])
    after_delta = int(base["max_records_base"]) + sum(int(row["max_records_delta"]) for row in mine)
    max_records = min(cap, scale_half_up(after_delta, mult_bps))

    retry_limit = int(base["retry_limit_base"]) + sum(int(row["retry_limit_delta"]) for row in mine)
    timeout_ms = int(base["timeout_seconds_base"]) * unit_factor + sum(
        added_ms[row["override_id"]] for row in mine
    )

    weights = read_rules(consume("risk_weight_rounding.txt"))
    if "round_half_up" not in weights["contribution"]:
        raise SystemExit("unexpected risk weight rule: " + weights["contribution"])
    terms = [int(base["risk_weight_base"])] + [int(row["risk_delta"]) for row in mine]
    contribution = sum(scale_half_up(term, mult_bps) for term in terms)

    tier_rows = read_parquet_rows(consume("threshold_tier_curve.parquet"))
    tiers = {int(row["tier"]): int(row["base_threshold"]) for row in tier_rows}
    base_threshold = tiers[role_level]

    convergence = read_rules(consume("convergence_spec.txt"))
    epsilon = int(convergence["convergence_epsilon"])
    max_iterations = int(convergence["max_iterations"])
    threshold = base_threshold
    iterations = [threshold]
    converged = False
    for _ in range(max_iterations):
        nxt = base_threshold + (contribution + threshold) // divisor
        iterations.append(nxt)
        step = abs(nxt - threshold)
        threshold = nxt
        if step <= epsilon:
            converged = True
            break
    if not converged:
        raise SystemExit("threshold reconciliation did not converge")

    corpus = load_json(consume("request_corpus.json"))
    claims = sorted(
        {
            entry["claimed_version"]
            for entry in corpus["entries"]
            if entry.get("principal") == role_key and entry.get("tenant") == tenant
        }
    )
    for claim in claims:
        rejected.append(
            {
                "id": claim,
                "reason": (
                    "client-claimed version in request_corpus.json; the effective version {} is "
                    "selected from policy_version_map.json at effective_instant {}".format(version, instant)
                ),
            }
        )

    schema = load_json(consume(manifest["schema_ref"]))
    defaults = load_json(consume(manifest["trailer_ref"]))

    resolved = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": defaults["checksum"],
        "mode": defaults["mode"],
        "max_records": max_records,
        "retry_limit": retry_limit,
        "timeout_ms": timeout_ms,
        "trailer": str(defaults["base_config"]["trailer"]),
        "param_key": param_key,
        "tenant": tenant,
        "effective_version": version,
        "risk_threshold": threshold,
    }
    trace = {
        "active_bundle": active_bundle,
        "effective_version": version,
        "param_key": param_key,
        "tenant": tenant,
        "client_version_ignored": True,
        "applied_overrides": applied_overrides,
        "ledger_controls": ledger_controls,
        "resolution_order": order,
        "rejected_branches": rejected,
    }
    curve = {
        "tier": role_level,
        "base_threshold": base_threshold,
        "contribution": contribution,
        "iterations": iterations,
        "converged": threshold,
    }
    return resolved, trace, curve


def config_keys(schema):
    required = schema["required_keys"]
    if isinstance(required, str):
        required = [key.strip() for key in required.split(",") if key.strip()]
    return list(required)


def cmd_init(args):
    schema = load_json(args.schema)
    data = {
        "profile": schema["profile"],
        "producer": schema["producer"],
        "container": schema["container"],
        "checksum": schema["checksum"],
        "mode": schema.get("mode", "strict-local"),
    }
    write_json(args.out, data)
    print("initialized")


def cmd_resolve(args):
    resolved, trace, curve = resolve_policy(args.data_dir)
    out = Path(args.out)
    write_json(out / "policy_resolved.json", resolved)
    write_json(out / "dependency_trace.json", trace)
    write_json(out / "threshold_curve.json", curve)
    print(json.dumps(resolved, sort_keys=True))


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
    missing = [key for key in config_keys(schema) if key not in data]
    if missing:
        raise SystemExit("missing: " + ",".join(missing))
    if schema.get("scalar_only") and not is_scalar_flat(data):
        raise SystemExit("configuration must be scalar")
    print("ok")


def cmd_profile(args):
    data = Path(args.data_dir)
    policy = load_json(args.policy)
    schema = load_json(data / "config_schema.json")
    env = load_json(data / "env_overrides.json")[args.name]
    sidecar = load_json(data / ("sample_config_" + args.name + ".json"))
    profile = {
        "checksum": policy["checksum"],
        "container": policy["container"],
        "producer": policy["producer"],
        "mode": env["mode"],
        "profile": schema["profile"] + "-" + args.name,
        "max_records": policy["max_records"] + int(sidecar["max_records_delta"]),
        "retry_limit": policy["retry_limit"] + int(env["retry_limit_delta"]),
        "timeout_ms": policy["timeout_ms"] + int(env["timeout_ms_delta"]),
        "trailer": policy["trailer"] + ":" + args.name,
    }
    assert_flat(profile)
    write_json(args.out, profile)
    print("profile " + args.name)


def cmd_summarize(args):
    data = Path(args.data_dir)
    rules = load_json(data / "validation_rules.json")
    schema = load_json(data / "config_schema.json")
    defaults = load_json(data / "defaults.json")
    inputs = sorted(path.name for path in data.iterdir() if path.is_file())
    artifacts = list(rules["required_artifacts"])
    summary = {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "profiles": list(rules["profiles"]),
        "format_tag": schema["profile"],
        "trailer": str(defaults["base_config"]["trailer"]),
        "input_count": len(inputs),
        "inputs": inputs,
    }
    write_json(args.out, summary)
    print("summarized")


def cmd_verify(args):
    data = Path(args.data_dir)
    rules = load_json(data / "validation_rules.json")
    schema = load_json(data / "config_schema.json")
    policy = load_json(args.policy)
    trace = load_json(args.trace)
    curve = load_json(args.curve)
    config = load_json(args.config)
    commands = read_commands(args.commands)
    out_dir = Path(args.out_dir)

    artifacts = list(rules["required_artifacts"])
    expected = {key: policy[key] for key in config_keys(schema)}
    profiles = {}
    for name in rules["profiles"]:
        path = out_dir / ("profile_" + name + ".json")
        profiles[name] = {"trailer": load_json(path)["trailer"] if path.exists() else None}

    checks = {
        "all_artifacts_present": all((out_dir / name).exists() for name in artifacts),
        "config_matches_policy": config == expected,
        "config_scalar_flat": is_scalar_flat(config),
        "command_failures": [entry["argv"] for entry in commands if int(entry["returncode"]) != 0],
        "required_artifacts": artifacts,
        "profiles": profiles,
    }
    report = {
        "ok": bool(
            checks["all_artifacts_present"]
            and checks["config_matches_policy"]
            and checks["config_scalar_flat"]
            and not checks["command_failures"]
        ),
        "checks": checks,
        "policy_resolved": policy,
        "threshold_curve": curve,
        "dependency_trace": trace,
    }
    write_json(args.out, report)
    print("verified")


def cmd_package(args):
    source = Path(args.tool_dir)
    members = sorted(path.name for path in source.iterdir() if path.is_file())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for name in members:
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.external_attr = (0o100000 | ZIP_MODE) << 16
            info.create_system = 3
            zf.writestr(info, (source / name).read_bytes())
    print("packaged " + ",".join(members))


def cmd_report(args):
    data = load_json(args.config)
    commands = read_commands(args.commands)
    report = {
        "ok": all(int(entry["returncode"]) == 0 for entry in commands),
        "tool": "sentinel-ctl",
        "commands": commands,
        "config_sha256": args.digest,
        "trailer": data.get("trailer"),
    }
    write_json(args.out, report)
    print("reported")


def cmd_digest(args):
    print(hashlib.sha256(Path(args.path).read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(prog="sentinel-ctl")
    sub = parser.add_subparsers(dest="command", required=True)

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

    p = sub.add_parser("profile")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("summarize")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_summarize)

    p = sub.add_parser("verify")
    p.add_argument("--data-dir", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--trace", required=True)
    p.add_argument("--curve", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--commands", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("package")
    p.add_argument("--tool-dir", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("export-report")
    p.add_argument("--config", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--commands", required=True)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("digest")
    p.add_argument("--path", required=True)
    p.set_defaults(func=cmd_digest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
