#!/usr/bin/env python3
"""Release train planner for release R-NEXT.

Usage: python3 relplan.py DATA_DIR OUT_DIR

Derives the whole release package from one corpus directory, exactly as the
release engineering handbook and its two addenda describe. Standard library
only, integer arithmetic only, no network access and no dependency on any
particular corpus.
"""

from __future__ import annotations

import configparser
import csv
import hashlib
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# ----------------------------------------------------------------- helpers

ID_RE = re.compile(r"^[A-Z]+-[A-Z0-9]+$")
EXCEPTIONS: list[dict] = []


def record(code: str, subject: str, detail: str) -> None:
    EXCEPTIONS.append({"code": code, "subject": subject, "detail": detail})


def ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def norm_id(raw: object) -> str | None:
    """Strip padding; reject a form that is not canonical upper case."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not ID_RE.match(text):
        return None
    return text


def as_int(raw: object) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if raw is None:
        return None
    text = str(raw).strip().replace("_", "")
    if not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def as_bool(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() == "true"


def active(row: dict) -> bool:
    """A row counts only when every status field it carries reads active."""
    for field in ("status", "state"):
        if field in row and str(row[field]).strip().lower() != "active":
            return False
    return True


def latest(rows: list[dict], key) -> dict[object, dict]:
    """Keep the active row with the highest revision_seq, then row_id."""
    best: dict[object, dict] = {}
    for row in rows:
        if not active(row):
            continue
        k = key(row)
        if k is None:
            continue
        seq = as_int(row.get("revision_seq", 1)) or 0
        rid = str(row.get("row_id", ""))
        prev = best.get(k)
        if prev is None:
            best[k] = row
            continue
        pseq = as_int(prev.get("revision_seq", 1)) or 0
        prid = str(prev.get("row_id", ""))
        if (seq, rid) > (pseq, prid):
            best[k] = row
    return best


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    ns_main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ns_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    sheets: dict[str, list[list[str]]] = {}
    with zipfile.ZipFile(path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {}
        for rel in rels:
            target[rel.get("Id")] = rel.get("Target")
        for sheet in wb.find(f"{ns_main}sheets"):
            name = sheet.get("name")
            rid = sheet.get(f"{ns_rel}id")
            part = "xl/" + str(target[rid]).lstrip("/")
            data = ET.fromstring(zf.read(part))
            rows: list[list[str]] = []
            sheet_data = data.find(f"{ns_main}sheetData")
            if sheet_data is None:
                sheets[name] = []
                continue
            for row in sheet_data:
                cells: list[str] = []
                for cell in row:
                    inline = cell.find(f"{ns_main}is/{ns_main}t")
                    value = cell.find(f"{ns_main}v")
                    if inline is not None:
                        cells.append(inline.text or "")
                    elif value is not None:
                        cells.append(value.text or "")
                    else:
                        cells.append("")
                rows.append(cells)
            sheets[name] = rows
    return sheets


def sheet_dicts(rows: list[list[str]]) -> list[dict]:
    if not rows:
        return []
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:]]


def read_pdf_lines(path: Path) -> list[str]:
    raw = path.read_bytes().decode("latin-1")
    out = []
    for match in re.finditer(r"\((.*?)\)\s*Tj", raw, re.S):
        text = match.group(1)
        text = text.replace(r"\(", "(").replace(r"\)", ")").replace("\\\\", "\\")
        out.append(text)
    return out


def read_docx_tables(path: Path) -> list[list[list[str]]]:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    tables = []
    for tbl in doc.iter(f"{ns}tbl"):
        rows = []
        for tr in tbl.iter(f"{ns}tr"):
            cells = []
            for tc in tr.iter(f"{ns}tc"):
                cells.append("".join(t.text or "" for t in tc.iter(f"{ns}t")))
            rows.append(cells)
        tables.append(rows)
    return tables


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
                   for r in rows)
    path.write_text(text, encoding="utf-8")


def dump_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


# ------------------------------------------------------------------- stages

def plan(data: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)

    # ---- stage 1: normalized inventory -------------------------------
    comp_rows = read_csv(data / "component_register.csv")
    comps: dict[str, dict] = {}
    for row in comp_rows:
        if not active(row):
            continue
        cid_raw = str(row.get("component_id", ""))
        cid = norm_id(cid_raw)
        if cid is None:
            record("E_ID_FORM", cid_raw.strip(), "component register row ignored")
            continue
        base = as_int(row.get("base_cost_ticks"))
        if base is None:
            record("E_NON_INTEGER", cid, "base_cost_ticks is not an integer")
            continue
        prio = as_int(row.get("priority_class")) or 0
        seq = as_int(row.get("revision_seq", 1)) or 0
        rid = str(row.get("row_id", ""))
        prev = comps.get(cid)
        cand = {"component_id": cid, "kind": str(row.get("kind", "")).strip(),
                "pool_id": str(row.get("pool_id", "")).strip(),
                "priority_class_declared": prio, "base_cost_ticks": base,
                "mandatory": as_bool(row.get("mandatory")),
                "owner_team": str(row.get("owner_team", "")).strip(),
                "channel": str(row.get("channel", "")).strip(),
                "_seq": seq, "_rid": rid}
        if prev is None or (seq, rid) > (prev["_seq"], prev["_rid"]):
            comps[cid] = cand
    for comp in comps.values():
        comp.pop("_seq")
        comp.pop("_rid")

    registry = read_json(data / "target_register.json")
    release_id = str(registry.get("release_id", "R-NEXT"))
    previous_release_id = str(registry.get("previous_release_id", "R-PREV"))
    targets = {str(t["target_id"]): t for t in registry.get("targets", [])
               if as_bool(t.get("enabled", True))}
    elig = latest([e for e in registry.get("eligibility", [])],
                  lambda r: (str(r.get("target_id")), str(r.get("kind")),
                             str(r.get("channel"))))
    eligible = {k: as_bool(v.get("eligible")) for k, v in elig.items()}

    matrix = latest(read_csv(data / "target_matrix.csv"),
                    lambda r: (norm_id(r.get("component_id")),
                               norm_id(r.get("target_id"))))
    units: dict[str, dict] = {}
    for (cid, tid), row in matrix.items():
        if cid is None or tid is None:
            continue
        if not as_bool(row.get("enabled")):
            continue
        comp = comps.get(cid)
        if comp is None:
            record("E_UNKNOWN_UNIT", cid, "component absent from register")
            continue
        if tid not in targets:
            record("E_UNKNOWN_UNIT", tid, "target absent from register")
            continue
        if not eligible.get((tid, comp["kind"], comp["channel"]), False):
            record("E_NOT_ELIGIBLE", f"{cid}:{tid}",
                   "target does not accept this kind on this channel")
            continue
        unit_id = f"{cid}:{tid}"
        units[unit_id] = {"unit_id": unit_id, "component_id": cid, "target_id": tid,
                          "kind": comp["kind"], "channel": comp["channel"],
                          "pool_id": comp["pool_id"],
                          "scope_tag": str(row.get("scope_tag", "")).strip(),
                          "base_cost_ticks": comp["base_cost_ticks"],
                          "mandatory": comp["mandatory"]}

    # ---- stage 2: revisions, toolchains, contracts --------------------
    src_rows = latest(read_jsonl(data / "source_revisions.jsonl"),
                      lambda r: norm_id(r.get("component_id")))
    source_rev = {cid: str(row["source_revision"]) for cid, row in src_rows.items()}

    chains_doc = read_json(data / "toolchains.json")
    chains = {str(c["toolchain_id"]): c for c in chains_doc.get("chains", [])
              if active(c)}
    kind_default: dict[str, str] = {}
    for row in latest(chains_doc.get("kind_defaults", []),
                      lambda r: (str(r.get("toolchain_id")), str(r.get("kind")))).values():
        if not as_bool(row.get("is_default")):
            continue
        kind = str(row["kind"])
        chain_id = str(row["toolchain_id"])
        if chain_id not in chains:
            continue
        if chain_id > kind_default.get(kind, ""):
            kind_default[kind] = chain_id

    profiles = latest(read_json(data / "compiler_profiles.json").get("profiles", []),
                      lambda r: (str(r.get("target_id")), str(r.get("kind")),
                                 str(r.get("channel"))))
    overrides = latest(read_jsonl(data / "target_overrides.jsonl"),
                       lambda r: (str(r.get("target_id")), str(r.get("applies_to")),
                                  str(r.get("channel"))))
    history = latest([r for r in read_csv(data / "toolchain_history.csv")
                      if str(r.get("release_id")) == previous_release_id],
                     lambda r: (str(r.get("target_id")), str(r.get("kind")),
                                str(r.get("channel"))))

    cur_contracts = {str(r["interface_id"]): str(r["contract_revision"])
                     for r in latest(read_jsonl(data / "current_contracts.jsonl"),
                                     lambda r: str(r.get("interface_id"))).values()}
    prev_contracts = {str(r["interface_id"]): str(r["contract_revision"])
                      for r in latest(read_jsonl(data / "previous_contracts.jsonl"),
                                      lambda r: str(r.get("interface_id"))).values()}

    consumers = latest(read_csv(data / "interface_consumers.csv"),
                       lambda r: (str(r.get("interface_id")).strip(),
                                  norm_id(r.get("consumer_component"))))
    required_ifaces: dict[str, list[str]] = {}
    optional_ifaces: dict[str, list[str]] = {}
    for (iface, cid), row in consumers.items():
        if cid not in comps:
            continue
        bucket = (required_ifaces if str(row.get("requirement")).strip() == "required"
                  else optional_ifaces)
        bucket.setdefault(cid, []).append(iface)

    def contract_digest(cid: str, table: dict[str, str]) -> str:
        parts = [f"{iface}:{table.get(iface, '')}"
                 for iface in sorted(required_ifaces.get(cid, []))]
        return hashlib.sha256(";".join(parts).encode("utf-8")).hexdigest()[:12]

    toolchain_rows = []
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        key = (unit["target_id"], unit["kind"], unit["channel"])
        ovr = overrides.get(key)
        chain_id = str(ovr["toolchain_id"]) if ovr else kind_default.get(unit["kind"], "")
        chain = chains.get(chain_id)
        chain_rev = str(chain["revision"]) if chain else ""
        prof = profiles.get(key)
        prof_id = str(prof["profile_id"]) if prof else ""
        prof_rev = str(prof["revision"]) if prof else ""
        resolved = f"{chain_id}@{chain_rev}+{prof_id}@{prof_rev}"
        hist = history.get(key)
        previous = (f"{hist['toolchain_id']}@{hist['toolchain_revision']}"
                    f"+{hist['profile_id']}@{hist['profile_revision']}") if hist else ""
        unit["toolchain_revision"] = resolved
        unit["previous_toolchain_revision"] = previous
        unit["toolchain_id"] = chain_id
        unit["profile_id"] = prof_id
        toolchain_rows.append({"unit_id": unit["unit_id"], "toolchain_id": chain_id,
                               "profile_id": prof_id,
                               "toolchain_revision": resolved,
                               "previous_toolchain_revision": previous,
                               "override_applied": bool(ovr)})

    ledger_prev = latest(read_jsonl(data / "previous_release_ledger.jsonl"),
                         lambda r: str(r.get("unit_id")).strip())
    index_rows = latest(read_jsonl(data / "published_artifact_index.jsonl"),
                        lambda r: str(r.get("artifact_digest")).strip())
    retained = {digest for digest, row in index_rows.items()
                if as_bool(row.get("retained"))}

    revision_delta = []
    contract_delta = []
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        cid = unit["component_id"]
        cur = contract_digest(cid, cur_contracts)
        prev = contract_digest(cid, prev_contracts)
        unit["contract_revision"] = cur
        unit["previous_contract_revision"] = prev
        unit["source_revision"] = source_rev.get(cid, "")
        prev_row = ledger_prev.get(unit["unit_id"])
        unit["previous_source_revision"] = (str(prev_row["source_revision"])
                                            if prev_row else "")
        unit["previous_artifact_digest"] = (str(prev_row["artifact_digest"])
                                            if prev_row else "")
        unit["in_previous_release"] = prev_row is not None
        revision_delta.append({
            "unit_id": unit["unit_id"], "component_id": cid,
            "target_id": unit["target_id"],
            "source_revision": unit["source_revision"],
            "previous_source_revision": unit["previous_source_revision"],
            "source_changed": unit["source_revision"] != unit["previous_source_revision"]
            and unit["in_previous_release"],
            "in_previous_release": unit["in_previous_release"]})
        contract_delta.append({
            "unit_id": unit["unit_id"], "contract_revision": cur,
            "previous_contract_revision": prev, "contract_changed": cur != prev,
            "required_interfaces": sorted(required_ifaces.get(cid, [])),
            "optional_interfaces": sorted(optional_ifaces.get(cid, []))})

    # ---- stage 3 and 4: invalidation closure --------------------------
    edges = latest(read_csv(data / "build_edges.csv"),
                   lambda r: str(r.get("edge_id")).strip())
    opt_act = latest(read_jsonl(data / "optional_dependencies.jsonl"),
                     lambda r: (norm_id(r.get("dependent")),
                                norm_id(r.get("dependency")),
                                norm_id(r.get("target_id"))))
    activation: dict[tuple[str, str], set[str]] = {}
    for (dependent, dependency, tid), row in opt_act.items():
        if as_bool(row.get("activated")):
            activation.setdefault((dependent, dependency), set()).add(tid)

    dep_edges: list[dict] = []
    for edge in sorted(edges.values(), key=lambda e: str(e["edge_id"])):
        dependent = norm_id(edge.get("dependent"))
        dependency = norm_id(edge.get("dependency"))
        if dependent is None or dependency is None:
            continue
        if dependent not in comps or dependency not in comps:
            for missing in (dependent, dependency):
                if missing not in comps:
                    record("E_UNKNOWN_UNIT", missing,
                           "build edge names a component outside the register")
            continue
        dep_edges.append({"edge_id": str(edge["edge_id"]), "dependent": dependent,
                          "dependency": dependency,
                          "requirement": str(edge.get("requirement")).strip()})

    iface_edges = latest(read_csv(data / "interface_edges.csv"),
                         lambda r: (str(r.get("interface_id")).strip(),
                                    norm_id(r.get("consumer"))))
    generated = latest(read_jsonl(data / "generated_outputs.jsonl"),
                       lambda r: (str(r.get("interface_id")).strip(),
                                  str(r.get("artifact_kind")).strip()))

    def required_unit_deps(unit: dict) -> list[str]:
        """Required build prerequisites of one unit, same target, unit level."""
        deps = []
        for edge in dep_edges:
            if edge["dependent"] != unit["component_id"]:
                continue
            if edge["requirement"] == "optional":
                key = (edge["dependent"], edge["dependency"])
                if unit["target_id"] not in activation.get(key, set()):
                    continue
            dep_unit = f"{edge['dependency']}:{unit['target_id']}"
            if dep_unit in units:
                deps.append(dep_unit)
        return sorted(set(deps))

    for unit in units.values():
        unit["required_dependencies"] = required_unit_deps(unit)

    sdk_producer: dict[str, str] = {}
    for (iface, _kind), row in generated.items():
        if as_bool(row.get("regenerate_on_contract_change")):
            producer = norm_id(row.get("generated_sdk_component"))
            if producer:
                sdk_producer[iface] = producer

    reasons: dict[str, set[str]] = {}
    for unit in units.values():
        found: set[str] = set()
        if not unit["in_previous_release"]:
            found.add("absent_from_previous_release")
        else:
            if unit["source_revision"] != unit["previous_source_revision"]:
                found.add("source_changed")
            if unit["toolchain_revision"] != unit["previous_toolchain_revision"]:
                found.add("toolchain_changed")
            if unit["contract_revision"] != unit["previous_contract_revision"]:
                found.add("contract_changed")
            if unit["previous_artifact_digest"] not in retained:
                found.add("published_artifact_missing")
                record("E_ARTIFACT_MISSING", unit["unit_id"],
                       "previous artifact is absent or not retained")
        reasons[unit["unit_id"]] = found

    # generated interface propagation plus dependency propagation, to fixpoint
    consumer_ifaces: dict[str, list[str]] = {}
    for (iface, cid), row in iface_edges.items():
        if cid in comps:
            consumer_ifaces.setdefault(cid, []).append(iface)

    changed = True
    while changed:
        changed = False
        for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
            uid = unit["unit_id"]
            before = set(reasons[uid])
            for dep in unit["required_dependencies"]:
                if reasons.get(dep):
                    reasons[uid].add("dependency_rebuilt")
                    break
            for iface in consumer_ifaces.get(unit["component_id"], []):
                producer = sdk_producer.get(iface)
                if producer is None:
                    continue
                producer_unit = f"{producer}:{unit['target_id']}"
                if producer_unit == uid or producer_unit not in units:
                    continue
                if cur_contracts.get(iface) != prev_contracts.get(iface):
                    reasons[uid].add("generated_interface_rebuilt")
            if reasons[uid] != before:
                changed = True

    invalidation_reasons = []
    invalidation_closure = []
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        rs = sorted(reasons[unit["unit_id"]])
        unit["reasons"] = rs
        unit["dirty"] = bool(rs)
        invalidation_reasons.append({"unit_id": unit["unit_id"], "reasons": rs,
                                     "reason_count": len(rs),
                                     "dirty": unit["dirty"]})
        if unit["dirty"]:
            invalidation_closure.append({
                "unit_id": unit["unit_id"], "component_id": unit["component_id"],
                "target_id": unit["target_id"], "kind": unit["kind"],
                "direct": bool({"absent_from_previous_release", "source_changed",
                                "toolchain_changed", "contract_changed",
                                "published_artifact_missing"} & set(rs)),
                "reasons": rs})

    generated_output_plan = []
    support = latest(read_csv(data / "sdk_support_matrix.csv"),
                     lambda r: (str(r.get("interface_id")).strip(),
                                norm_id(r.get("target_id"))))
    for (iface, kind), row in sorted(generated.items()):
        producer = norm_id(row.get("generated_sdk_component"))
        if producer is None or producer not in comps:
            continue
        iface_changed = cur_contracts.get(iface) != prev_contracts.get(iface)
        for tid in sorted(targets):
            unit_id = f"{producer}:{tid}"
            if unit_id not in units:
                continue
            sup = support.get((iface, tid))
            supported = sup is not None and str(sup.get("support_state")) == "supported"
            regenerate = bool(as_bool(row.get("regenerate_on_contract_change"))
                              and iface_changed)
            if regenerate and not supported:
                record("E_SDK_UNSUPPORTED", f"{iface}@{unit_id}",
                       "generated output is unsupported for the target")
            generated_output_plan.append({
                "interface_id": iface, "artifact_kind": kind,
                "producer_unit": unit_id, "target_id": tid,
                "contract_revision": cur_contracts.get(iface, ""),
                "previous_contract_revision": prev_contracts.get(iface, ""),
                "regenerate": regenerate and supported,
                "supported": supported})

    # ---- stage 5: build unit ledger -----------------------------------
    build_unit_ledger = []
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        build_unit_ledger.append({
            "unit_id": unit["unit_id"], "component_id": unit["component_id"],
            "target_id": unit["target_id"], "kind": unit["kind"],
            "pool_id": unit["pool_id"], "channel": unit["channel"],
            "source_revision": unit["source_revision"],
            "toolchain_revision": unit["toolchain_revision"],
            "contract_revision": unit["contract_revision"],
            "state": "dirty" if unit["dirty"] else "reusable",
            "reasons": unit["reasons"],
            "required_dependencies": unit["required_dependencies"]})

    # ---- stage 6: exact integer cost ----------------------------------
    book = read_xlsx(data / "capacity_workbook.xlsx")
    scaling = latest(sheet_dicts(book["platform_scaling"]),
                     lambda r: (str(r.get("target_id")), str(r.get("kind")),
                                str(r.get("channel"))))
    rules = latest(sheet_dicts(book["cost_rules"]), lambda r: str(r.get("rule_name")))
    regen = rules.get("regeneration_surcharge", {})
    cold = rules.get("cold_cache_multiplier", {})
    regen_num = as_int(regen.get("numerator")) or 1
    regen_den = as_int(regen.get("denominator")) or 1
    cold_num = as_int(cold.get("numerator")) or 1
    cold_den = as_int(cold.get("denominator")) or 1

    kind_profiles = latest(read_json(data / "kind_cost_profiles.json").get("profiles", []),
                           lambda r: (str(r.get("kind")), str(r.get("channel")),
                                      str(r.get("target_id"))))
    minimums = latest(read_jsonl(data / "build_cost_rules.jsonl"),
                      lambda r: (str(r.get("kind")), str(r.get("channel")),
                                 str(r.get("target_id"))))

    cost_breakdown = []
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        if not unit["dirty"]:
            continue
        key = (unit["target_id"], unit["kind"], unit["channel"])
        row = scaling.get(key)
        num = as_int(row.get("multiplier_numerator")) if row else None
        den = as_int(row.get("multiplier_denominator")) if row else None
        if not num or not den:
            record("E_NON_INTEGER", unit["unit_id"], "platform scaling row unusable")
            num, den = 1, 1
        c0 = unit["base_cost_ticks"]
        c1 = ceil_div(c0 * num, den)
        profile = kind_profiles.get((unit["kind"], unit["channel"], unit["target_id"]), {})
        regen_applies = (as_bool(profile.get("regeneration_surcharge_applies"))
                         and bool({"contract_changed", "generated_interface_rebuilt"}
                                  & set(unit["reasons"])))
        c2 = ceil_div(c1 * regen_num, regen_den) if regen_applies else c1
        cold_applies = (as_bool(profile.get("cold_cache_multiplier_applies"))
                        and "absent_from_previous_release" in unit["reasons"])
        c3 = ceil_div(c2 * cold_num, cold_den) if cold_applies else c2
        floor_row = minimums.get((unit["kind"], unit["channel"], unit["target_id"]), {})
        floor_value = as_int(floor_row.get("minimum_cost_ticks")) or 0
        c4 = c3 if c0 == 0 else max(c3, floor_value)
        unit["cost_ticks"] = c4
        cost_breakdown.append({
            "unit_id": unit["unit_id"], "base_cost_ticks": c0,
            "platform_numerator": num, "platform_denominator": den,
            "after_platform": c1, "regeneration_applied": regen_applies,
            "after_regeneration": c2, "cold_cache_applied": cold_applies,
            "after_cold_cache": c3, "minimum_cost_ticks": floor_value,
            "cost_ticks": c4})
    for unit in units.values():
        unit.setdefault("cost_ticks", 0)

    # ---- stage 7: capacity --------------------------------------------
    budgets = latest(sheet_dicts(book["pool_budgets"]), lambda r: str(r.get("pool_id")))
    pool_doc = read_json(data / "pool_register.json")
    known_pools = {str(p["pool_id"]) for p in pool_doc.get("pools", [])}
    lanes = {}
    for row in read_csv(data / "worker_pool_notes.csv"):
        if active(row) and str(row.get("lane_state")) == "operational":
            lanes[str(row["pool_id"])] = lanes.get(str(row["pool_id"]), 0) + 1

    gross: dict[str, int] = {}
    for pool_id, row in budgets.items():
        if pool_id not in known_pools:
            record("E_UNKNOWN_POOL", pool_id, "budget row names an unknown pool")
            continue
        value = as_int(row.get("budget_value"))
        if value is None:
            record("E_NON_INTEGER", pool_id, "budget value is not an integer")
            continue
        if str(row.get("scale_unit")) == "milli_tick":
            value = ceil_div(value, 1000)
        gross[pool_id] = value

    reserved: dict[str, int] = {pool: 0 for pool in known_pools}
    for row in read_jsonl(data / "maintenance_windows.jsonl"):
        if not active(row):
            continue
        pool_id = str(row.get("pool_id"))
        if pool_id not in known_pools:
            record("E_UNKNOWN_POOL", pool_id,
                   "maintenance window names an unknown pool")
            continue
        if "reserved_millis" in row:
            amount = ceil_div(as_int(row["reserved_millis"]) or 0, 1000)
        else:
            amount = as_int(row.get("reserved_ticks")) or 0
        reserved[pool_id] = reserved.get(pool_id, 0) + amount
    net = {pool: max(0, gross.get(pool, 0) - reserved.get(pool, 0))
           for pool in known_pools}

    # priority overrides live only in the addendum
    overrides_pdf: dict[str, dict] = {}
    for line in read_pdf_lines(data / "rounding_precedence_addendum.pdf"):
        match = re.match(r"^\s*(\S+)\s+(\d+)\s+(\w+)\s+(\d+)\s*$", line)
        if not match:
            continue
        raw, prio, state, seq = match.groups()
        if state != "active":
            continue
        cid = norm_id(raw)
        if cid is None:
            record("E_ID_FORM", raw.strip(), "priority override row ignored")
            continue
        if cid not in comps:
            record("E_UNKNOWN_UNIT", cid, "priority override names an unknown component")
            continue
        prev = overrides_pdf.get(cid)
        if prev is None or int(seq) > prev["revision_seq"]:
            overrides_pdf[cid] = {"priority_class": int(prio),
                                  "revision_seq": int(seq)}
    for unit in units.values():
        comp = comps[unit["component_id"]]
        ovr = overrides_pdf.get(unit["component_id"])
        unit["priority_class"] = (ovr["priority_class"] if ovr
                                  else comp["priority_class_declared"])
        unit["priority_overridden"] = bool(ovr)

    policy = read_json(data / "publication_policy.json")
    prohibited: dict[str, str] = {}
    for row in policy.get("prohibitions", []):
        if not active(row):
            continue
        cid = norm_id(row.get("component_id"))
        tid = norm_id(row.get("target_id"))
        if cid and tid:
            prohibited[f"{cid}:{tid}"] = "E_PROHIBITED"
    for row in latest(policy.get("reviews", []),
                      lambda r: norm_id(r.get("component_id"))).values():
        if str(row.get("publication_review")) == "held":
            cid = norm_id(row.get("component_id"))
            for unit in units.values():
                if unit["component_id"] == cid:
                    prohibited.setdefault(unit["unit_id"], "E_REVIEW_HELD")

    channels_doc = tomllib.loads((data / "release_channels.toml").read_text(encoding="utf-8"))
    frozen = {name for name, body in channels_doc.get("channel", {}).items()
              if as_bool(body.get("frozen"))}
    for unit in units.values():
        if unit["channel"] in frozen:
            prohibited.setdefault(unit["unit_id"], "E_CHANNEL_FROZEN")
    for unit_id, code in sorted(prohibited.items()):
        if unit_id in units:
            record(code, unit_id, "publication of the unit is prohibited")

    def closure_of(unit_id: str) -> list[str]:
        """The candidate plus every dirty prerequisite of the same target.

        A prerequisite is a required build dependency or, for an interface the
        component consumes, the unit that regenerates that interface.
        """
        seen = {unit_id}
        stack = [unit_id]
        while stack:
            cur = units[stack.pop()]
            prereqs = list(cur["required_dependencies"])
            for iface in consumer_ifaces.get(cur["component_id"], []):
                producer = sdk_producer.get(iface)
                if producer is None:
                    continue
                if cur_contracts.get(iface) == prev_contracts.get(iface):
                    continue
                producer_unit = f"{producer}:{cur['target_id']}"
                if producer_unit in units:
                    prereqs.append(producer_unit)
            for dep in prereqs:
                dep_unit = units.get(dep)
                if dep_unit is None or dep in seen or not dep_unit["dirty"]:
                    continue
                seen.add(dep)
                stack.append(dep)
        return sorted(seen)

    candidates = [u for u in units.values()
                  if u["dirty"] and u["unit_id"] not in prohibited]
    selected: set[str] = set()
    deferred: dict[str, str] = {}
    spent: dict[str, int] = {pool: 0 for pool in known_pools}
    allocation: list[dict] = []
    closures = {u["unit_id"]: closure_of(u["unit_id"]) for u in candidates}

    def closure_cost(unit_id: str) -> int:
        """Addendum A4: count only closure members not already selected."""
        return sum(units[m]["cost_ticks"] for m in closures[unit_id]
                   if m not in selected)

    for pool in sorted(known_pools):
        order = sorted((u["priority_class"], closure_cost(u["unit_id"]),
                        u["unit_id"])
                       for u in candidates if u["pool_id"] == pool)
        for _prio, _cost, unit_id in order:
            if unit_id in selected:
                continue
            members = closures[unit_id]
            draw: dict[str, int] = {}
            for m in members:
                if m in selected:
                    continue
                draw[units[m]["pool_id"]] = (draw.get(units[m]["pool_id"], 0)
                                             + units[m]["cost_ticks"])
            if any(spent.get(p, 0) + amount > net.get(p, 0)
                   for p, amount in draw.items()):
                deferred.setdefault(unit_id, "E_CAPACITY")
                continue
            for p, amount in draw.items():
                spent[p] = spent.get(p, 0) + amount
            for m in members:
                if m in selected:
                    continue
                selected.add(m)
                deferred.pop(m, None)
                allocation.append({
                    "unit_id": m, "pool_id": units[m]["pool_id"],
                    "cost_ticks": units[m]["cost_ticks"],
                    "priority_class": units[m]["priority_class"],
                    "admitted_with": unit_id})

    for unit_id, code in sorted(deferred.items()):
        if unit_id not in selected:
            record(code, unit_id, "unit deferred under the capacity policy")

    # ---- stage 9: cycles ----------------------------------------------
    cycle_doc = read_json(data / "cycle_groups.json")
    groups = [g for g in cycle_doc.get("groups", []) if active(g)]
    scope = latest(cycle_doc.get("applicability", []),
                   lambda r: (str(r.get("group_id")), str(r.get("target_id"))))

    graph: dict[str, set[str]] = {uid: set() for uid in selected}
    edge_owner: dict[tuple[str, str], str] = {}
    for unit_id in sorted(selected):
        for dep in units[unit_id]["required_dependencies"]:
            if dep in selected:
                graph[dep].add(unit_id)
                edge_owner[(dep, unit_id)] = "build_edge"

    def find_cycle(g: dict[str, set[str]]) -> list[str] | None:
        colour: dict[str, int] = {}
        stack: list[str] = []

        def walk(node: str) -> list[str] | None:
            colour[node] = 1
            stack.append(node)
            for nxt in sorted(g.get(node, ())):
                if colour.get(nxt, 0) == 0:
                    found = walk(nxt)
                    if found:
                        return found
                elif colour.get(nxt) == 1:
                    return stack[stack.index(nxt):] + [nxt]
            colour[node] = 2
            stack.pop()
            return None

        for node in sorted(g):
            if colour.get(node, 0) == 0:
                found = walk(node)
                if found:
                    return found
        return None

    sys.setrecursionlimit(10000)
    cycle_records: list[dict] = []
    blocked_units: dict[str, str] = {}
    blocked_targets: set[str] = set()
    guard = 0
    while guard < 400:
        guard += 1
        cycle = find_cycle(graph)
        if cycle is None:
            break
        members = sorted({node.split(":")[0] for node in cycle})
        target = cycle[0].split(":")[1]
        group = next((g for g in groups
                      if sorted(set(g["members"])) == members
                      and as_bool(scope.get((str(g["group_id"]), target), {})
                                  .get("in_scope", False))), None)
        if group is None or str(group.get("policy")) != "breakable":
            blocked_targets.add(target)
            group_id = str(group["group_id"]) if group else ""
            for node in sorted(set(cycle)):
                blocked_units[node] = "E_CYCLE_BLOCKING"
            cycle_records.append({"group_id": group_id, "target_id": target,
                                  "policy": "blocking",
                                  "members": members, "edge_removed": "",
                                  "break_cost": 0,
                                  "units_blocked": sorted(set(cycle))})
            for node in sorted(set(cycle)):
                graph.pop(node, None)
            for node in graph:
                graph[node] -= set(cycle)
            continue
        costs = group.get("break_costs", {})
        options = []
        for idx in range(len(cycle) - 1):
            src_unit, dst_unit = cycle[idx], cycle[idx + 1]
            src, dst = src_unit.split(":")[0], dst_unit.split(":")[0]
            cost = costs.get(f"{src}->{dst}")
            if cost is None:
                continue
            options.append((int(cost), src, dst, src_unit, dst_unit))
        if not options:
            blocked_targets.add(target)
            for node in sorted(set(cycle)):
                blocked_units[node] = "E_CYCLE_BLOCKING"
            cycle_records.append({"group_id": str(group["group_id"]),
                                  "target_id": target, "policy": "blocking",
                                  "members": members, "edge_removed": "",
                                  "break_cost": 0,
                                  "units_blocked": sorted(set(cycle))})
            for node in sorted(set(cycle)):
                graph.pop(node, None)
            for node in graph:
                graph[node] -= set(cycle)
            continue
        options.sort()
        cost, src, dst, src_unit, dst_unit = options[0]
        graph[src_unit].discard(dst_unit)
        cycle_records.append({"group_id": str(group["group_id"]),
                              "target_id": target, "policy": "breakable",
                              "members": members,
                              "edge_removed": f"{src}->{dst}",
                              "break_cost": cost, "units_blocked": []})

    for unit_id in blocked_units:
        selected.discard(unit_id)
        record("E_CYCLE_BLOCKING", unit_id, "unit blocked by a cycle group policy")

    while True:
        demote = []
        for unit_id in sorted(selected):
            members = closures.get(unit_id, [unit_id])
            if any(m != unit_id and m not in selected for m in members):
                demote.append(unit_id)
        if not demote:
            break
        for unit_id in demote:
            selected.discard(unit_id)
            deferred[unit_id] = "E_PREREQ_DEFERRED"
            record("E_PREREQ_DEFERRED", unit_id,
                   "a prerequisite left the release after cycle resolution")
    allocation = [row for row in allocation if row["unit_id"] in selected]

    # ---- stage 8 and 10: schedule -------------------------------------
    order_rows = latest(read_jsonl(data / "ordering_overrides.jsonl"),
                        lambda r: str(r.get("row_id")))
    deploy_constraints = latest(read_jsonl(data / "deployment_constraints.jsonl"),
                                lambda r: (norm_id(r.get("migration_component")),
                                           norm_id(r.get("blocks_component")),
                                           norm_id(r.get("target_id"))))
    constraints = {uid: set() for uid in selected}
    for src, dsts in graph.items():
        if src in constraints:
            constraints[src] = {d for d in dsts if d in selected}
    ignored_orders = []
    for (mig, svc, tid), row in sorted(deploy_constraints.items()):
        if str(row.get("constraint")) != "migration_first":
            continue
        before, after = f"{mig}:{tid}", f"{svc}:{tid}"
        if before not in selected or after not in selected or before == after:
            continue
        if before in _reachable(constraints, after):
            ignored_orders.append({"before_unit": before, "after_unit": after})
            record("E_ORDER_IGNORED", f"{before}->{after}",
                   "deployment constraint would close a cycle")
            continue
        constraints[before].add(after)
    for row in sorted(order_rows.values(), key=lambda r: str(r.get("row_id"))):
        before = str(row.get("before_unit")).strip()
        after = str(row.get("after_unit")).strip()
        if before not in selected or after not in selected or before == after:
            continue
        if after in constraints and before in _reachable(constraints, after):
            ignored_orders.append({"before_unit": before, "after_unit": after})
            record("E_ORDER_IGNORED", f"{before}->{after}",
                   "ordering override would close a cycle")
            continue
        constraints[before].add(after)

    indegree = {uid: 0 for uid in selected}
    for src, dsts in constraints.items():
        for dst in dsts:
            indegree[dst] += 1
    ready = sorted((units[u]["priority_class"], u) for u in selected
                   if indegree[u] == 0)
    schedule = []
    seq = 0
    while ready:
        ready.sort()
        _prio, unit_id = ready.pop(0)
        seq += 1
        schedule.append({"sequence": seq, "unit_id": unit_id,
                         "pool_id": units[unit_id]["pool_id"],
                         "priority_class": units[unit_id]["priority_class"],
                         "cost_ticks": units[unit_id]["cost_ticks"],
                         "dependencies": sorted(
                             d for d in units[unit_id]["required_dependencies"]
                             if d in selected and unit_id in graph.get(d, ()))})
        for dst in sorted(constraints.get(unit_id, ())):
            indegree[dst] -= 1
            if indegree[dst] == 0:
                ready.append((units[dst]["priority_class"], dst))

    # ---- stage 11 and 12: compatibility and version selection ---------
    windows: dict[tuple[str, str], dict] = {}
    for table in read_docx_tables(data / "compatibility_window_notes.docx"):
        if not table or table[0][0] != "component_id":
            continue
        for row in table[1:]:
            cid = norm_id(row[0])
            if cid is None:
                record("E_ID_FORM", row[0].strip(), "window row ignored")
                continue
            if str(row[3]).strip() != "active":
                continue
            if cid not in comps:
                record("E_UNKNOWN_UNIT", cid,
                       "window row names a component outside the register")
                continue
            seq_value = as_int(row[4]) or 0
            key = (cid, str(row[1]).strip())
            prev = windows.get(key)
            if prev is None or seq_value > prev["revision_seq"]:
                windows[key] = {"window_state": str(row[2]).strip(),
                                "revision_seq": seq_value}

    version_rows = latest(read_jsonl(data / "component_versions.jsonl"),
                          lambda r: (norm_id(r.get("component_id")),
                                     str(r.get("version")).strip()))
    candidates_by_comp: dict[str, list[dict]] = {}
    for (cid, version), row in sorted(version_rows.items()):
        if cid not in comps:
            continue
        state = windows.get((cid, version), {}).get("window_state", "supported")
        if state != "supported":
            continue
        candidates_by_comp.setdefault(cid, []).append({
            "version": version,
            "local_preference": as_int(row.get("local_preference")) or 0,
            "api_revision": str(row.get("api_revision"))})
    for versions in candidates_by_comp.values():
        versions.sort(key=lambda v: v["version"])

    compat = latest(read_jsonl(data / "api_compatibility.jsonl"),
                    lambda r: (str(r.get("cluster_id")),
                               norm_id(r.get("left_component")),
                               str(r.get("left_version")),
                               norm_id(r.get("right_component")),
                               str(r.get("right_version"))))
    compat_map = {k: as_bool(v.get("compatible")) for k, v in compat.items()}

    released_components = sorted({units[u]["component_id"] for u in selected})
    clusters = read_json(data / "version_precedence.json").get("clusters", [])
    version_selection: list[dict] = []
    rejected: list[dict] = []
    compatibility_matrix: list[dict] = []
    unresolved: list[str] = []
    chosen_versions: dict[str, str] = {}

    for cluster in clusters:
        cluster_id = str(cluster["cluster_id"])
        members = sorted(set(cluster.get("members", [])))
        members = [m for m in members if m in released_components]
        if not members:
            continue
        options = [candidates_by_comp.get(m, []) for m in members]
        if any(not opt for opt in options):
            for m, opt in zip(members, options):
                if not opt:
                    record("E_WITHDRAWN_VERSION", m,
                           "every candidate version is withdrawn")
            unresolved.append(cluster_id)
            continue

        def combos(idx: int, acc: list[dict]):
            if idx == len(members):
                yield list(acc)
                return
            for cand in options[idx]:
                acc.append(cand)
                yield from combos(idx + 1, acc)
                acc.pop()

        scored = []
        for combo in combos(0, []):
            total = sum(c["local_preference"] for c in combo)
            key = tuple(c["version"] for c in combo)
            ok = True
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    pair_key = (cluster_id, members[a], combo[a]["version"],
                                members[b], combo[b]["version"])
                    if not compat_map.get(pair_key, False):
                        ok = False
            scored.append((total, key, ok, combo))
        scored.sort(key=lambda row: (row[0], row[1]))
        winner = next((row for row in scored if row[2]), None)
        if winner is None:
            unresolved.append(cluster_id)
            record("E_CLUSTER_UNRESOLVED", cluster_id,
                   "no compatible version combination exists")
            for total, key, ok, _combo in scored:
                rejected.append({"cluster_id": cluster_id, "members": members,
                                 "versions": list(key), "preference_sum": total,
                                 "reason": "incompatible"})
            continue
        for total, key, ok, _combo in scored:
            if total < winner[0] and not ok:
                rejected.append({"cluster_id": cluster_id, "members": members,
                                 "versions": list(key), "preference_sum": total,
                                 "reason": "incompatible"})
        for member, cand in zip(members, winner[3]):
            chosen_versions[member] = cand["version"]
            version_selection.append({
                "cluster_id": cluster_id, "component_id": member,
                "version": cand["version"],
                "local_preference": cand["local_preference"],
                "api_revision": cand["api_revision"],
                "preference_sum": winner[0]})
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                compatibility_matrix.append({
                    "cluster_id": cluster_id, "left_component": members[a],
                    "left_version": winner[3][a]["version"],
                    "right_component": members[b],
                    "right_version": winner[3][b]["version"],
                    "compatible": True})

    # ---- stage 13: manifests and provenance ---------------------------
    release_membership = []
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        uid = unit["unit_id"]
        if uid in blocked_units:
            state = "blocked"
        elif uid in selected and uid in prohibited:
            state = "built_not_published"
        elif uid in selected:
            state = "included"
        elif not unit["dirty"]:
            state = "reused"
        elif uid in prohibited:
            state = "excluded"
        else:
            state = "deferred"
        unit["membership"] = state
        release_membership.append({
            "unit_id": uid, "state": state,
            "pool_id": unit["pool_id"], "target_id": unit["target_id"],
            "reason_code": (blocked_units.get(uid) or prohibited.get(uid)
                            or deferred.get(uid, ""))})

    deferred_units = [{"unit_id": uid, "reason_code": code,
                       "pool_id": units[uid]["pool_id"],
                       "cost_ticks": units[uid]["cost_ticks"],
                       "priority_class": units[uid]["priority_class"]}
                      for uid, code in sorted(deferred.items())
                      if uid not in selected and uid not in blocked_units]

    cache_reuse = [{"unit_id": unit["unit_id"],
                    "artifact_digest": unit["previous_artifact_digest"],
                    "reusable": not unit["dirty"],
                    "justification": ("unchanged source, toolchain and contract"
                                      if not unit["dirty"] else "invalidated")}
                   for unit in sorted(units.values(), key=lambda u: u["unit_id"])
                   if not unit["dirty"]]

    deployment_members = []
    for uid in sorted(selected):
        if uid in prohibited:
            continue
        unit = units[uid]
        deployment_members.append({
            "unit_id": uid, "component_id": unit["component_id"],
            "target_id": unit["target_id"], "kind": unit["kind"],
            "version": chosen_versions.get(unit["component_id"], ""),
            "contract_revision": unit["contract_revision"]})
    for unit in sorted(units.values(), key=lambda u: u["unit_id"]):
        if unit["membership"] == "reused":
            deployment_members.append({
                "unit_id": unit["unit_id"], "component_id": unit["component_id"],
                "target_id": unit["target_id"], "kind": unit["kind"],
                "version": chosen_versions.get(unit["component_id"], ""),
                "contract_revision": unit["contract_revision"]})
    deployment_members.sort(key=lambda m: m["unit_id"])

    sdk_manifest = []
    for row in generated_output_plan:
        if not row["regenerate"]:
            continue
        producer = row["producer_unit"].split(":")[0]
        if row["producer_unit"] not in selected:
            continue
        sdk_manifest.append({
            "interface_id": row["interface_id"],
            "artifact_kind": row["artifact_kind"],
            "producer_unit": row["producer_unit"],
            "contract_revision": row["contract_revision"],
            "producer_version": chosen_versions.get(producer, "")})

    sequence_of = {row["unit_id"]: row["sequence"] for row in schedule}
    migration_order = []
    for (mig, svc, tid), row in sorted(deploy_constraints.items()):
        if str(row.get("constraint")) != "migration_first":
            continue
        mig_unit, svc_unit = f"{mig}:{tid}", f"{svc}:{tid}"
        if mig_unit not in selected or svc_unit not in selected:
            continue
        migration_order.append({
            "migration_unit": mig_unit, "blocks_unit": svc_unit,
            "target_id": tid,
            "migration_sequence": sequence_of.get(mig_unit, 0),
            "blocked_sequence": sequence_of.get(svc_unit, 0),
            "ordered": sequence_of.get(mig_unit, 0) < sequence_of.get(svc_unit, 0)})
    migration_order.sort(key=lambda r: (r["migration_unit"], r["blocks_unit"]))

    provenance = []
    for uid in sorted(selected):
        unit = units[uid]
        provenance.append({
            "unit_id": uid,
            "source_revision": unit["source_revision"],
            "toolchain_revision": unit["toolchain_revision"],
            "contract_revision": unit["contract_revision"],
            "reasons": unit["reasons"],
            "schedule_sequence": sequence_of.get(uid, 0),
            "pool_id": unit["pool_id"],
            "cost_ticks": unit["cost_ticks"]})

    pool_summary = {}
    for pool in sorted(known_pools):
        pool_summary[pool] = {
            "gross_budget_ticks": gross.get(pool, 0),
            "reserved_ticks": reserved.get(pool, 0),
            "net_budget_ticks": net.get(pool, 0),
            "consumed_ticks": sum(units[u]["cost_ticks"] for u in selected
                                  if units[u]["pool_id"] == pool),
            "remaining_ticks": net.get(pool, 0) - sum(
                units[u]["cost_ticks"] for u in selected
                if units[u]["pool_id"] == pool),
            "selected_units": sum(1 for u in selected
                                  if units[u]["pool_id"] == pool),
            "deferred_units": sum(1 for u, _c in deferred.items()
                                  if u not in selected and units[u]["pool_id"] == pool),
            "operational_lanes": lanes.get(pool, 0)}

    prev_manifest = read_json(data / "previous_release_manifest.json")
    prev_members = {str(m["unit_id"]) for m in prev_manifest.get("members", [])}
    current_members = {m["unit_id"] for m in deployment_members}
    release_delta = {
        "release_id": release_id,
        "previous_release_id": previous_release_id,
        "added_units": sorted(current_members - prev_members),
        "removed_units": sorted(prev_members - current_members),
        "retained_units": sorted(current_members & prev_members),
        "added_count": len(current_members - prev_members),
        "removed_count": len(prev_members - current_members),
        "retained_count": len(current_members & prev_members)}

    mandatory_missing = sorted(
        unit["unit_id"] for unit in units.values()
        if unit["mandatory"] and unit["membership"] in ("deferred", "blocked",
                                                        "excluded"))
    if blocked_targets or unresolved:
        decision = "blocked"
    elif mandatory_missing:
        decision = "deferred"
    else:
        decision = "publishable"

    release_decision = {
        "release_id": release_id,
        "decision": decision,
        "blocked_targets": sorted(blocked_targets),
        "unresolved_clusters": sorted(set(unresolved)),
        "mandatory_units_withheld": mandatory_missing,
        "units_total": len(units),
        "units_included": sum(1 for u in units.values()
                              if u["membership"] == "included"),
        "units_built_not_published": sum(1 for u in units.values()
                                         if u["membership"] == "built_not_published"),
        "units_reused": sum(1 for u in units.values() if u["membership"] == "reused"),
        "units_deferred": len(deferred_units),
        "units_blocked": len(blocked_units),
        "units_excluded": sum(1 for u in units.values()
                              if u["membership"] == "excluded"),
        "scheduled_units": len(schedule),
        "total_cost_ticks": sum(units[u]["cost_ticks"] for u in selected),
        "exception_count": len(EXCEPTIONS)}

    # ---- stage 15: amortize generated output cost ---------------------
    required_consumers: dict[str, list[str]] = {}
    for (iface, cid), row in consumers.items():
        if cid in comps and str(row.get("requirement")).strip() == "required":
            required_consumers.setdefault(iface, []).append(cid)

    amortization = []
    producing: dict[str, str] = {}
    for (iface, _kind), row in sorted(generated.items()):
        producer = norm_id(row.get("generated_sdk_component"))
        if producer is not None and producer in comps:
            producing[iface] = producer
    for iface, producer in sorted(producing.items()):
        for tid in sorted(targets):
            producer_unit = f"{producer}:{tid}"
            if producer_unit not in selected:
                continue
            takers = sorted({c for c in required_consumers.get(iface, [])
                              if f"{c}:{tid}" in selected})
            if not takers:
                continue
            cost = units[producer_unit]["cost_ticks"]
            base, rem = divmod(cost, len(takers))
            for rank, consumer in enumerate(takers, start=1):
                amortization.append({
                    "producer_unit": producer_unit, "interface_id": iface,
                    "consumer_component": consumer, "target_id": tid,
                    "share_ticks": base + (1 if rank <= rem else 0),
                    "remainder_rank": rank})
    amortization.sort(key=lambda r: (r["producer_unit"], r["interface_id"],
                                     r["consumer_component"]))

    # ---- stage 14: write ----------------------------------------------
    normalized_inventory = [{
        "unit_id": u["unit_id"], "component_id": u["component_id"],
        "target_id": u["target_id"], "kind": u["kind"], "channel": u["channel"],
        "pool_id": u["pool_id"], "base_cost_ticks": u["base_cost_ticks"],
        "priority_class": u["priority_class"],
        "priority_overridden": u["priority_overridden"],
        "mandatory": u["mandatory"], "scope_tag": u["scope_tag"]}
        for u in sorted(units.values(), key=lambda u: u["unit_id"])]

    dump_jsonl(out / "normalized_inventory.jsonl", normalized_inventory)
    dump_jsonl(out / "revision_delta.jsonl", revision_delta)
    dump_jsonl(out / "toolchain_resolution.jsonl", toolchain_rows)
    dump_jsonl(out / "contract_delta.jsonl", contract_delta)
    dump_jsonl(out / "invalidation_reasons.jsonl", invalidation_reasons)
    dump_jsonl(out / "invalidation_closure.jsonl", invalidation_closure)
    dump_jsonl(out / "generated_output_plan.jsonl", generated_output_plan)
    dump_jsonl(out / "build_unit_ledger.jsonl", build_unit_ledger)
    dump_jsonl(out / "build_cost_breakdown.jsonl", cost_breakdown)
    dump_jsonl(out / "capacity_allocation.jsonl",
               sorted(allocation, key=lambda r: r["unit_id"]))
    dump_jsonl(out / "deferred_units.jsonl", deferred_units)
    dump_jsonl(out / "dependency_schedule.jsonl", schedule)
    dump_jsonl(out / "cycle_resolution.jsonl",
               sorted(cycle_records, key=lambda r: (r["target_id"], r["group_id"],
                                                    r["edge_removed"])))
    dump_json(out / "worker_pool_summary.json",
              {"release_id": release_id, "pools": pool_summary})
    dump_jsonl(out / "compatibility_matrix.jsonl",
               sorted(compatibility_matrix,
                      key=lambda r: (r["cluster_id"], r["left_component"],
                                     r["right_component"])))
    dump_jsonl(out / "rejected_combinations.jsonl",
               sorted(rejected, key=lambda r: (r["cluster_id"], r["preference_sum"],
                                               r["versions"])))
    dump_jsonl(out / "version_selection.jsonl",
               sorted(version_selection, key=lambda r: (r["component_id"],
                                                        r["cluster_id"])))
    dump_jsonl(out / "release_membership.jsonl", release_membership)
    dump_json(out / "deployment_manifest.json",
              {"release_id": release_id, "decision": decision,
               "members": deployment_members,
               "member_count": len(deployment_members)})
    dump_jsonl(out / "generated_sdk_manifest.jsonl",
               sorted(sdk_manifest, key=lambda r: (r["producer_unit"],
                                                   r["interface_id"],
                                                   r["artifact_kind"])))
    dump_jsonl(out / "migration_order.jsonl", migration_order)
    dump_jsonl(out / "artifact_provenance.jsonl", provenance)
    dump_jsonl(out / "cache_reuse_manifest.jsonl", cache_reuse)
    dump_json(out / "release_delta.json", release_delta)
    dump_jsonl(out / "audit_exceptions.jsonl",
               sorted(EXCEPTIONS, key=lambda r: (r["code"], r["subject"],
                                                 r["detail"])))
    dump_jsonl(out / "cost_amortization.jsonl", amortization)
    dump_json(out / "release_decision.json", release_decision)

    summary_rows = [["metric", "value"]]
    for metric in ("units_total", "units_included", "units_built_not_published",
                   "units_reused", "units_deferred", "units_blocked",
                   "units_excluded",
                   "scheduled_units", "total_cost_ticks", "exception_count"):
        summary_rows.append([metric, release_decision[metric]])
    summary_rows.append(["decision", decision])
    text = "".join(",".join(str(c) for c in row) + "\n" for row in summary_rows)
    (out / "conformance_summary.csv").write_text(text, encoding="utf-8")

    return release_decision


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    seen = {start}
    stack = [start]
    while stack:
        for nxt in graph.get(stack.pop(), ()):  # type: ignore[arg-type]
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    EXCEPTIONS.clear()
    plan(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
