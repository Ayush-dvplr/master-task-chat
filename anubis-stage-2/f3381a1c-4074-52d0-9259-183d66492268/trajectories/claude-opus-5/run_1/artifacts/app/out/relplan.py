#!/usr/bin/env python3
"""Release train planner.

    python3 relplan.py DATA_DIR OUT_DIR

Rebuilds the whole release package from the corpus in DATA_DIR into OUT_DIR
under the release engineering handbook, addendum A (rounding, precedence and
admission) and addendum B (compatibility windows).  Every figure is derived
from the corpus, all arithmetic is integer arithmetic and the standard library
is the only dependency.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import tomllib
import zipfile
import zlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

COMPONENT_RE = re.compile(r"\AC-[0-9]{4}\Z")
TARGET_RE = re.compile(r"\AT-[0-9]{2}\Z")
POOL_RE = re.compile(r"\AP-.+\Z")

SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


# --------------------------------------------------------------------------
# reading rules of handbook section 2
# --------------------------------------------------------------------------

def text(value) -> str:
    """Stripped text of a field; a missing field reads as the empty string."""
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value).strip()


def integer(value):
    """Integer of a field, or None when the field is not an integer.

    Underscore digit grouping is ordinary; a decimal point is not an integer.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return None
    raw = str(value).strip().replace("_", "")
    if re.fullmatch(r"[+-]?[0-9]+", raw):
        return int(raw)
    return None


def flag(value) -> bool:
    return text(value).lower() == "true"


def ceil_div(num: int, den: int) -> int:
    """ceil(num / den) for num >= 0 and den > 0, in integer arithmetic."""
    return (num + den - 1) // den


def is_active(row: dict) -> bool:
    for key in ("status", "state"):
        if key in row:
            return text(row[key]) == "active"
    return True


def revision_seq(row: dict) -> int:
    value = integer(row.get("revision_seq"))
    return value if value is not None else 0


def row_rank(row: dict):
    """Precedence of two active rows carrying the same key (rule 6)."""
    return (revision_seq(row), text(row.get("row_id")),
            json.dumps(row, sort_keys=True, default=str))


def winner(rows):
    return max(rows, key=row_rank)


# --------------------------------------------------------------------------
# corpus readers
# --------------------------------------------------------------------------

def rows_of_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{k: ("" if v is None else v) for k, v in row.items() if k is not None}
                for row in csv.DictReader(handle)]


def rows_of_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def object_of_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - 64)
    return index - 1


def sheets_of_xlsx(path: Path) -> dict[str, list[dict]]:
    sheets: dict[str, list[dict]] = {}
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            table = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in table:
                shared.append("".join(node.text or ""
                                      for node in item.iter(f"{SHEET_NS}t")))
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = {node.get("Id"): node.get("Target")
                for node in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        for sheet in book.find(f"{SHEET_NS}sheets"):
            part = "xl/" + str(rels[sheet.get(f"{REL_NS}id")]).lstrip("/")
            grid: list[list[str]] = []
            data = ET.fromstring(archive.read(part))
            body = data.find(f"{SHEET_NS}sheetData")
            for row in (body if body is not None else []):
                cells: list[str] = []
                for cell in row:
                    index = _column_index(cell.get("r") or "")
                    if index < 0:
                        index = len(cells)
                    while len(cells) <= index:
                        cells.append("")
                    inline = cell.find(f"{SHEET_NS}is/{SHEET_NS}t")
                    value = cell.find(f"{SHEET_NS}v")
                    if inline is not None:
                        cells[index] = inline.text or ""
                    elif value is not None and cell.get("t") == "s":
                        position = integer(value.text)
                        cells[index] = shared[position] if position is not None else ""
                    elif value is not None:
                        cells[index] = value.text or ""
                grid.append(cells)
            # the header row is the one row that carries no integer cell, so a
            # sheet whose data rows arrive in another order still reads the same
            position = 0
            for index, line in enumerate(grid):
                if line and all(integer(cell) is None for cell in line):
                    position = index
                    break
            header = grid[position] if grid else []
            rows = []
            for index, line in enumerate(grid):
                if index == position:
                    continue
                padded = list(line) + [""] * (len(header) - len(line))
                rows.append(dict(zip(header, padded)))
            sheets[sheet.get("name")] = rows
    return sheets


def table_rows_of_docx(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    rows = []
    for tr in document.iter(f"{WORD_NS}tr"):
        rows.append(["".join(node.text or "" for node in tc.iter(f"{WORD_NS}t"))
                     for tc in tr.iter(f"{WORD_NS}tc")])
    return rows


def _pdf_objects(blob: bytes) -> dict[int, bytes]:
    objects: dict[int, bytes] = {}
    for match in re.finditer(rb"(\d+)\s+0\s+obj\b(.*?)\bendobj\b", blob, re.S):
        objects[int(match.group(1))] = match.group(2)
    return objects


def _pdf_stream(body: bytes) -> bytes:
    match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", body, re.S)
    if match is None:
        return b""
    raw = match.group(1)
    if b"/FlateDecode" in body.split(b"stream", 1)[0]:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return raw
    return raw


def text_lines_of_pdf(path: Path) -> list[str]:
    blob = path.read_bytes()
    objects = _pdf_objects(blob)
    pages: list[int] = []
    for number, body in objects.items():
        if b"/Type" in body and b"/Pages" in body and b"/Kids" in body:
            kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
            if kids:
                pages = [int(n) for n in re.findall(rb"(\d+)\s+0\s+R", kids.group(1))]
                break
    if not pages:
        pages = sorted(objects)
    lines: list[str] = []
    for number in pages:
        body = objects.get(number, b"")
        contents = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        if contents is None:
            continue
        stream = _pdf_stream(objects.get(int(contents.group(1)), b""))
        page = stream.decode("latin-1")
        for match in re.finditer(r"\((?:[^()\\]|\\.)*\)\s*Tj", page):
            chunk = match.group(0)
            chunk = chunk[chunk.index("(") + 1:chunk.rindex(")")]
            chunk = (chunk.replace("\\(", "(").replace("\\)", ")")
                     .replace("\\\\", "\\"))
            lines.append(chunk)
    return lines


# --------------------------------------------------------------------------
# the planner
# --------------------------------------------------------------------------

class Planner:
    def __init__(self, data: Path):
        self.data = data
        self.exceptions: list[dict] = []
        self.components: dict[str, dict] = {}
        self.targets: dict[str, dict] = {}

    # -- exceptions ------------------------------------------------------
    def record(self, code: str, subject: str, detail: str) -> None:
        self.exceptions.append({"code": code, "subject": subject, "detail": detail})

    # -- identifier checking --------------------------------------------
    def check_row(self, row: dict, spec, origin: str):
        """Apply rules 2, 5 and 9 to one row.

        ``spec`` is a sequence of (field, kind) pairs with kind one of
        ``component``, ``target`` or ``unit``.  Returns a dict of resolved
        identifiers, or None when the row must be ignored.
        """
        resolved: dict[str, str] = {}
        malformed: list[str] = []
        pairs: list[tuple[str, str]] = []
        for field, kind in spec:
            raw = text(row.get(field))
            if kind == "unit":
                parts = raw.split(":")
                if len(parts) != 2:
                    malformed.append(raw)
                    continue
                component, target = parts[0].strip(), parts[1].strip()
                if not COMPONENT_RE.match(component):
                    malformed.append(component)
                elif not TARGET_RE.match(target):
                    malformed.append(target)
                else:
                    resolved[field] = f"{component}:{target}"
                    pairs.append((component, "component"))
                    pairs.append((target, "target"))
                continue
            pattern = COMPONENT_RE if kind == "component" else TARGET_RE
            if not pattern.match(raw):
                malformed.append(raw)
                continue
            resolved[field] = raw
            pairs.append((raw, kind))
        if malformed:
            for subject in malformed:
                self.record("E_ID_FORM", subject,
                            f"{origin} row ignored, identifier not in canonical form")
            return None
        if not is_active(row):
            return None
        missing = []
        for value, kind in pairs:
            known = self.components if kind == "component" else self.target_rows
            if value not in known:
                missing.append(value)
        if missing:
            for subject in sorted(set(missing)):
                self.record("E_UNKNOWN_UNIT", subject,
                            f"{origin} row ignored, identifier names no register row")
            return None
        return resolved

    def pool_of_row(self, row: dict, field: str, origin: str):
        pool = text(row.get(field))
        if pool not in self.pools:
            self.record("E_UNKNOWN_POOL", pool,
                        f"{origin} row ignored, pool names no pool register row")
            return None
        return pool

    # -- stage 0, the registers -----------------------------------------
    def read_registers(self) -> None:
        data = self.data
        self.target_register = object_of_json(data / "target_register.json")
        self.release_id = text(self.target_register.get("release_id"))
        self.previous_release_id = text(self.target_register.get("previous_release_id"))
        # a target that the register lists is a known identifier even when it is
        # not enabled for this release; only enabled targets carry units
        self.target_rows: dict[str, dict] = {}
        for row in self.target_register.get("targets", []):
            target = text(row.get("target_id"))
            if not TARGET_RE.match(target):
                self.record("E_ID_FORM", target,
                            "target register row ignored, identifier not in canonical form")
                continue
            if not is_active(row):
                continue
            self.target_rows[target] = row
            if flag(row.get("enabled")):
                self.targets[target] = row

        self.pool_register = object_of_json(data / "pool_register.json")
        self.pools = {}
        for row in self.pool_register.get("pools", []):
            pool = text(row.get("pool_id"))
            if POOL_RE.match(pool) and is_active(row):
                self.pools[pool] = row

        register: dict[str, list[dict]] = defaultdict(list)
        for row in rows_of_csv(data / "component_register.csv"):
            component = text(row.get("component_id"))
            if not COMPONENT_RE.match(component):
                self.record("E_ID_FORM", component,
                            "component register row ignored, identifier not in canonical form")
                continue
            if not is_active(row):
                continue
            if integer(row.get("base_cost_ticks")) is None:
                self.record("E_NON_INTEGER", component,
                            "component register row ignored, base_cost_ticks is not an integer")
                continue
            register[component].append(row)
        for component, rows in register.items():
            row = winner(rows)
            self.components[component] = {
                "component_id": component,
                "kind": text(row.get("kind")),
                "channel": text(row.get("channel")),
                "pool_id": text(row.get("pool_id")),
                "priority_class": integer(row.get("priority_class")) or 0,
                "base_cost_ticks": integer(row.get("base_cost_ticks")),
                "mandatory": flag(row.get("mandatory")),
            }
        for component in sorted(self.components):
            pool = self.components[component]["pool_id"]
            if pool not in self.pools:
                self.record("E_UNKNOWN_POOL", pool,
                            f"component register row of {component} names no pool register row")

    # -- addenda ---------------------------------------------------------
    def read_addendum_a(self) -> None:
        """Priority class overrides of addendum A section A8."""
        rows: dict[str, list[dict]] = defaultdict(list)
        for line in text_lines_of_pdf(self.data / "rounding_precedence_addendum.pdf"):
            fields = line.split()
            if len(fields) != 4:
                continue
            component, priority, state, sequence = fields
            if integer(priority) is None or integer(sequence) is None:
                continue
            if state not in ("active", "superseded"):
                continue
            row = {"component_id": component, "priority_class": integer(priority),
                   "state": state, "revision_seq": integer(sequence)}
            rows[json.dumps(row, sort_keys=True)] = row
        self.priority_overrides: dict[str, int] = {}
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows.values():
            component = text(row.get("component_id"))
            if not COMPONENT_RE.match(component):
                self.record("E_ID_FORM", component,
                            "addendum A8 row ignored, identifier not in canonical form")
                continue
            if not is_active(row):
                continue
            if component not in self.components:
                self.record("E_UNKNOWN_UNIT", component,
                            "addendum A8 row ignored, identifier names no register row")
                continue
            grouped[component].append(row)
        for component, group in grouped.items():
            self.priority_overrides[component] = winner(group)["priority_class"]

    def read_addendum_b(self) -> None:
        """Version windows of addendum B section B1."""
        rows = table_rows_of_docx(self.data / "compatibility_window_notes.docx")
        header: list[str] = []
        for cells in rows:
            if cells and text(cells[0]) == "component_id":
                header = [text(cell) for cell in cells]
                break
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        seen: set[str] = set()
        for cells in rows:
            if not cells or not header or len(cells) != len(header):
                continue
            if text(cells[0]) == "component_id":
                continue
            row = dict(zip(header, [text(cell) for cell in cells]))
            key = json.dumps(row, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            component = text(row.get("component_id"))
            if not COMPONENT_RE.match(component):
                self.record("E_ID_FORM", component,
                            "addendum B1 row ignored, identifier not in canonical form")
                continue
            if not is_active(row):
                continue
            if component not in self.components:
                self.record("E_UNKNOWN_UNIT", component,
                            "addendum B1 row ignored, identifier names no register row")
                continue
            grouped[(component, text(row.get("version")))].append(row)
        self.window_states: dict[tuple[str, str], str] = {}
        for key, group in grouped.items():
            self.window_states[key] = text(winner(group).get("window_state"))

    # -- stage 1, the normalized inventory -------------------------------
    def build_inventory(self) -> None:
        data = self.data
        eligibility: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in self.target_register.get("eligibility", []):
            resolved = self.check_row(row, [("target_id", "target")],
                                      "target register eligibility")
            if resolved is None:
                continue
            key = (resolved["target_id"], text(row.get("kind")), text(row.get("channel")))
            eligibility[key].append(row)

        matrix: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows_of_csv(data / "target_matrix.csv"):
            resolved = self.check_row(row, [("component_id", "component"),
                                            ("target_id", "target")], "target matrix")
            if resolved is None:
                continue
            matrix[(resolved["component_id"], resolved["target_id"])].append(row)

        self.units: dict[str, dict] = {}
        self.units_of_target: dict[str, set[str]] = defaultdict(set)
        self.unit_of = {}
        for key in sorted(matrix):
            component, target = key
            if target not in self.targets:
                continue
            row = winner(matrix[key])
            if not flag(row.get("enabled")):
                continue
            entry = self.components[component]
            kind, channel = entry["kind"], entry["channel"]
            rule = eligibility.get((target, kind, channel))
            unit_id = f"{component}:{target}"
            if rule is None:
                continue
            if not flag(winner(rule).get("eligible")):
                self.record("E_NOT_ELIGIBLE", unit_id,
                            "the eligibility table of the target register refuses the pair")
                continue
            priority = entry["priority_class"]
            overridden = component in self.priority_overrides
            if overridden:
                priority = self.priority_overrides[component]
            unit = {
                "unit_id": unit_id,
                "component_id": component,
                "target_id": target,
                "kind": kind,
                "channel": channel,
                "pool_id": entry["pool_id"],
                "priority_class": priority,
                "priority_overridden": overridden,
                "base_cost_ticks": entry["base_cost_ticks"],
                "mandatory": entry["mandatory"],
                "scope_tag": text(row.get("scope_tag")),
            }
            self.units[unit_id] = unit
            self.units_of_target[target].add(unit_id)
            self.unit_of[(component, target)] = unit_id

    # -- stage 2, toolchain and contract revisions -----------------------
    def resolve_revisions(self) -> None:
        data = self.data

        toolchains = object_of_json(data / "toolchains.json")
        grouped_chains: dict[str, list[dict]] = defaultdict(list)
        for row in toolchains.get("chains", []):
            if is_active(row):
                grouped_chains[text(row.get("toolchain_id"))].append(row)
        chains = {chain: winner(rows) for chain, rows in grouped_chains.items()}
        defaults: dict[str, str] = {}
        for row in toolchains.get("kind_defaults", []):
            if not is_active(row) or not flag(row.get("is_default")):
                continue
            kind = text(row.get("kind"))
            chain = text(row.get("toolchain_id"))
            if chain not in chains:
                continue
            if kind not in defaults or chain > defaults[kind]:
                defaults[kind] = chain

        overrides: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "target_overrides.jsonl"):
            resolved = self.check_row(row, [("target_id", "target")], "target override")
            if resolved is None:
                continue
            overrides[(resolved["target_id"], text(row.get("applies_to")),
                       text(row.get("channel")))].append(row)

        profiles: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in object_of_json(data / "compiler_profiles.json").get("profiles", []):
            resolved = self.check_row(row, [("target_id", "target")], "compiler profile")
            if resolved is None:
                continue
            profiles[(resolved["target_id"], text(row.get("kind")),
                      text(row.get("channel")))].append(row)

        history: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_csv(data / "toolchain_history.csv"):
            if text(row.get("release_id")) != self.previous_release_id:
                continue
            resolved = self.check_row(row, [("target_id", "target")], "toolchain history")
            if resolved is None:
                continue
            history[(resolved["target_id"], text(row.get("kind")),
                     text(row.get("channel")))].append(row)

        current = self.read_contracts(data / "current_contracts.jsonl")
        previous = self.read_contracts(data / "previous_contracts.jsonl")
        self.contract_revision_of = current
        self.previous_contract_revision_of = previous
        self.changed_interfaces = {iface for iface in set(current) | set(previous)
                                   if current.get(iface, "") != previous.get(iface, "")}

        consumers: dict[str, dict[str, str]] = defaultdict(dict)
        self.required_consumers: dict[str, list[str]] = defaultdict(list)
        self.interfaces_of: dict[str, dict[str, str]] = consumers
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows_of_csv(data / "interface_consumers.csv"):
            resolved = self.check_row(row, [("consumer_component", "component")],
                                      "interface consumer")
            if resolved is None:
                continue
            grouped[(text(row.get("interface_id")),
                     resolved["consumer_component"])].append(row)
        for (interface, component), rows in grouped.items():
            requirement = text(winner(rows).get("requirement"))
            consumers[component][interface] = requirement
            if requirement == "required":
                self.required_consumers[interface].append(component)

        for unit in self.units.values():
            kind, channel = unit["kind"], unit["channel"]
            key = (unit["target_id"], kind, channel)
            override = overrides.get(key)
            chain = text(winner(override).get("toolchain_id")) if override else \
                defaults.get(kind, "")
            unit["override_applied"] = bool(override)
            unit["toolchain_id"] = chain
            chain_revision = text(chains.get(chain, {}).get("revision"))
            profile = profiles.get(key)
            profile_row = winner(profile) if profile else {}
            unit["profile_id"] = text(profile_row.get("profile_id"))
            unit["toolchain_revision"] = (
                f"{chain}@{chain_revision}"
                f"+{unit['profile_id']}@{text(profile_row.get('revision'))}")
            old = history.get(key)
            if old:
                row = winner(old)
                unit["previous_toolchain_revision"] = (
                    f"{text(row.get('toolchain_id'))}@{text(row.get('toolchain_revision'))}"
                    f"+{text(row.get('profile_id'))}@{text(row.get('profile_revision'))}")
            else:
                unit["previous_toolchain_revision"] = ""

            consumed = consumers.get(unit["component_id"], {})
            required = sorted(iface for iface, req in consumed.items()
                              if req == "required")
            optional = sorted(iface for iface, req in consumed.items()
                              if req != "required")
            unit["required_interfaces"] = required
            unit["optional_interfaces"] = optional
            unit["contract_revision"] = self.contract_digest(required, current)
            unit["previous_contract_revision"] = self.contract_digest(required, previous)

    def read_contracts(self, path: Path) -> dict[str, str]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(path):
            if not is_active(row):
                continue
            grouped[text(row.get("interface_id"))].append(row)
        return {iface: text(winner(rows).get("contract_revision"))
                for iface, rows in grouped.items()}

    @staticmethod
    def contract_digest(interfaces, table: dict[str, str]) -> str:
        joined = ";".join(f"{iface}:{table.get(iface, '')}" for iface in interfaces)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]

    # -- stage 2b, the build graph ---------------------------------------
    def read_build_graph(self) -> None:
        data = self.data
        optional: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "optional_dependencies.jsonl"):
            resolved = self.check_row(row, [("dependent", "component"),
                                            ("dependency", "component"),
                                            ("target_id", "target")],
                                      "optional dependency")
            if resolved is None:
                continue
            optional[(resolved["dependent"], resolved["dependency"],
                      resolved["target_id"])].append(row)
        self.optional_active = {
            key for key, rows in optional.items() if flag(winner(rows).get("activated"))}

        edges: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows_of_csv(data / "build_edges.csv"):
            resolved = self.check_row(row, [("dependent", "component"),
                                            ("dependency", "component")], "build edge")
            if resolved is None:
                continue
            edges[(resolved["dependent"], resolved["dependency"])].append(row)
        self.required_edges: set[tuple[str, str]] = set()
        self.optional_edges: set[tuple[str, str]] = set()
        for key, rows in edges.items():
            if text(winner(rows).get("requirement")) == "required":
                self.required_edges.add(key)
            else:
                self.optional_edges.add(key)

        self.required_dependencies: dict[str, list[str]] = {}
        for unit_id, unit in self.units.items():
            component, target = unit["component_id"], unit["target_id"]
            deps = []
            for dependent, dependency in self.required_edges:
                if dependent != component:
                    continue
                other = self.unit_of.get((dependency, target))
                if other is not None:
                    deps.append(other)
            self.required_dependencies[unit_id] = sorted(deps)

        self.generating_unit: dict[tuple[str, str], str] = {}
        self.generator_of: dict[str, str] = {}
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "generated_outputs.jsonl"):
            resolved = self.check_row(row, [("generated_sdk_component", "component")],
                                      "generated output")
            if resolved is None:
                continue
            grouped[(text(row.get("interface_id")),
                     text(row.get("artifact_kind")))].append(row)
        self.generated_outputs: dict[tuple[str, str], dict] = {}
        for key, rows in grouped.items():
            row = winner(rows)
            self.generated_outputs[key] = row
            component = text(row.get("generated_sdk_component"))
            self.generator_of[key[0]] = component
            for target in self.targets:
                unit_id = self.unit_of.get((component, target))
                if unit_id is not None:
                    self.generating_unit[(key[0], target)] = unit_id

        support: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_csv(data / "sdk_support_matrix.csv"):
            resolved = self.check_row(row, [("sdk_component", "component"),
                                            ("target_id", "target")],
                                      "sdk support matrix")
            if resolved is None:
                continue
            support[(text(row.get("interface_id")), resolved["sdk_component"],
                     resolved["target_id"])].append(row)
        self.support_state = {
            key: text(winner(rows).get("support_state")) for key, rows in support.items()}

    # -- stage 3 and 4, invalidation -------------------------------------
    def invalidate(self) -> None:
        data = self.data
        sources: dict[str, list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "source_revisions.jsonl"):
            resolved = self.check_row(row, [("component_id", "component")],
                                      "source revision")
            if resolved is None:
                continue
            sources[resolved["component_id"]].append(row)
        self.source_revision_of = {component: text(winner(rows).get("source_revision"))
                                   for component, rows in sources.items()}

        ledger: dict[str, list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "previous_release_ledger.jsonl"):
            resolved = self.check_row(row, [("component_id", "component"),
                                            ("target_id", "target")],
                                      "previous release ledger")
            if resolved is None:
                continue
            unit_id = f"{resolved['component_id']}:{resolved['target_id']}"
            ledger[unit_id].append(row)
        self.ledger = {unit_id: winner(rows) for unit_id, rows in ledger.items()}

        index: dict[str, list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "published_artifact_index.jsonl"):
            if not is_active(row):
                continue
            index[text(row.get("artifact_digest"))].append(row)
        self.retained_digests = {digest for digest, rows in index.items()
                                 if flag(winner(rows).get("retained"))}

        direct: dict[str, set[str]] = {}
        for unit_id, unit in self.units.items():
            reasons: set[str] = set()
            row = self.ledger.get(unit_id)
            unit["in_previous_release"] = row is not None
            unit["source_revision"] = self.source_revision_of.get(
                unit["component_id"], "")
            if row is None:
                unit["previous_source_revision"] = ""
                unit["previous_artifact_digest"] = ""
                reasons.add("absent_from_previous_release")
            else:
                unit["previous_source_revision"] = text(row.get("source_revision"))
                digest = text(row.get("artifact_digest"))
                unit["previous_artifact_digest"] = digest
                if unit["source_revision"] != unit["previous_source_revision"]:
                    reasons.add("source_changed")
                if unit["toolchain_revision"] != unit["previous_toolchain_revision"]:
                    reasons.add("toolchain_changed")
                if unit["contract_revision"] != unit["previous_contract_revision"]:
                    reasons.add("contract_changed")
                if digest not in self.retained_digests:
                    reasons.add("published_artifact_missing")
                    self.record("E_ARTIFACT_MISSING", unit_id,
                                "the previous artifact digest is not retained by the "
                                "published artifact index")
            unit["source_changed"] = "source_changed" in reasons
            unit["contract_changed"] = (
                unit["contract_revision"] != unit["previous_contract_revision"])
            direct[unit_id] = reasons

        propagated: dict[str, set[str]] = {unit_id: set() for unit_id in self.units}
        for unit_id, unit in self.units.items():
            component, target = unit["component_id"], unit["target_id"]
            for interface, requirement in self.interfaces_of.get(component, {}).items():
                if interface not in self.changed_interfaces:
                    continue
                if (interface, target) in self.generating_unit:
                    propagated[unit_id].add("generated_interface_rebuilt")
                    break

        dependents: dict[str, list[str]] = defaultdict(list)
        for unit_id, unit in self.units.items():
            component, target = unit["component_id"], unit["target_id"]
            for dependent, dependency in self.required_edges:
                if dependency != component:
                    continue
                other = self.unit_of.get((dependent, target))
                if other is not None:
                    dependents[unit_id].append(other)
            for dependent, dependency in self.optional_edges:
                if dependency != component:
                    continue
                if (dependent, component, target) not in self.optional_active:
                    continue
                other = self.unit_of.get((dependent, target))
                if other is not None:
                    dependents[unit_id].append(other)

        def carries(unit_id: str) -> bool:
            return bool(direct[unit_id] or propagated[unit_id])

        pending = [unit_id for unit_id in self.units if carries(unit_id)]
        while pending:
            unit_id = pending.pop()
            for other in dependents.get(unit_id, ()):
                if "dependency_rebuilt" in propagated[other]:
                    continue
                was = carries(other)
                propagated[other].add("dependency_rebuilt")
                if not was:
                    pending.append(other)

        self.direct_reasons = {unit_id: sorted(direct[unit_id]) for unit_id in self.units}
        for unit_id, unit in self.units.items():
            reasons = sorted(direct[unit_id] | propagated[unit_id])
            unit["reasons"] = reasons
            unit["dirty"] = bool(reasons)
        self.dirty = {unit_id for unit_id, unit in self.units.items() if unit["dirty"]}

    # -- stage 5, generated outputs --------------------------------------
    def plan_generated_outputs(self) -> None:
        self.output_plan: list[dict] = []
        for (interface, kind) in sorted(self.generated_outputs):
            row = self.generated_outputs[(interface, kind)]
            component = text(row.get("generated_sdk_component"))
            for target in sorted(self.targets):
                unit_id = self.unit_of.get((component, target))
                if unit_id is None:
                    continue
                supported = self.support_state.get(
                    (interface, component, target)) == "supported"
                changed = interface in self.changed_interfaces
                wanted = flag(row.get("regenerate_on_contract_change")) and changed
                if wanted and not supported:
                    self.record("E_SDK_UNSUPPORTED", f"{interface}@{unit_id}",
                                "the sdk support matrix does not support this target")
                self.output_plan.append({
                    "artifact_kind": kind,
                    "contract_revision": self.contract_revision_of.get(interface, ""),
                    "interface_id": interface,
                    "previous_contract_revision":
                        self.previous_contract_revision_of.get(interface, ""),
                    "producer_unit": unit_id,
                    "regenerate": bool(wanted and supported),
                    "supported": supported,
                    "target_id": target,
                })
        self.output_plan.sort(key=lambda r: (r["interface_id"], r["artifact_kind"],
                                             r["target_id"]))

    # -- stage 6, cost ----------------------------------------------------
    def price(self) -> None:
        data = self.data
        book = sheets_of_xlsx(data / "capacity_workbook.xlsx")

        scaling: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in book.get("platform_scaling", []):
            resolved = self.check_row(row, [("target_id", "target")], "platform scaling")
            if resolved is None:
                continue
            scaling[(resolved["target_id"], text(row.get("kind")),
                     text(row.get("channel")))].append(row)
        self.scaling = {key: winner(rows) for key, rows in scaling.items()}

        rules: dict[str, list[dict]] = defaultdict(list)
        for row in book.get("cost_rules", []):
            if not is_active(row):
                continue
            rules[text(row.get("rule_name"))].append(row)
        self.cost_rules = {name: winner(rows) for name, rows in rules.items()}

        kinds: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in object_of_json(data / "kind_cost_profiles.json").get("profiles", []):
            resolved = self.check_row(row, [("target_id", "target")], "kind cost profile")
            if resolved is None:
                continue
            kinds[(text(row.get("kind")), text(row.get("channel")),
                   resolved["target_id"])].append(row)
        kind_profiles = {key: winner(rows) for key, rows in kinds.items()}

        floors: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "build_cost_rules.jsonl"):
            resolved = self.check_row(row, [("target_id", "target")], "build cost rule")
            if resolved is None:
                continue
            floors[(text(row.get("kind")), text(row.get("channel")),
                    resolved["target_id"])].append(row)

        self.cost_ticks: dict[str, int] = {}
        self.cost_rows: list[dict] = []
        for unit_id in sorted(self.dirty):
            unit = self.units[unit_id]
            key = (unit["target_id"], unit["kind"], unit["channel"])
            numerator, denominator = 1, 1
            row = self.scaling.get(key)
            if row is not None:
                num = integer(row.get("multiplier_numerator"))
                den = integer(row.get("multiplier_denominator"))
                if num is None or den is None or den <= 0:
                    self.record("E_NON_INTEGER", unit_id,
                                "the platform scaling row of this unit is not an "
                                "integer fraction and is ignored")
                else:
                    numerator, denominator = num, den
            profile = kind_profiles.get((unit["kind"], unit["channel"],
                                         unit["target_id"]), {})
            reasons = set(unit["reasons"])
            regeneration = bool(flag(profile.get("regeneration_surcharge_applies")) and
                                ({"contract_changed", "generated_interface_rebuilt"}
                                 & reasons))
            cold = bool(flag(profile.get("cold_cache_multiplier_applies")) and
                        "absent_from_previous_release" in reasons)
            floor_rows = floors.get((unit["kind"], unit["channel"], unit["target_id"]))
            minimum = 0
            if floor_rows:
                value = integer(winner(floor_rows).get("minimum_cost_ticks"))
                minimum = value if value is not None else 0

            base = unit["base_cost_ticks"]
            after_platform = ceil_div(base * numerator, denominator)
            after_regeneration = after_platform
            if regeneration:
                num, den = self.fraction("regeneration_surcharge")
                after_regeneration = ceil_div(after_platform * num, den)
            after_cold = after_regeneration
            if cold:
                num, den = self.fraction("cold_cache_multiplier")
                after_cold = ceil_div(after_regeneration * num, den)
            cost = after_cold if base == 0 else max(after_cold, minimum)
            self.cost_ticks[unit_id] = cost
            self.cost_rows.append({
                "after_cold_cache": after_cold,
                "after_platform": after_platform,
                "after_regeneration": after_regeneration,
                "base_cost_ticks": base,
                "cold_cache_applied": cold,
                "cost_ticks": cost,
                "minimum_cost_ticks": minimum,
                "platform_denominator": denominator,
                "platform_numerator": numerator,
                "regeneration_applied": regeneration,
                "unit_id": unit_id,
            })

    def fraction(self, name: str) -> tuple[int, int]:
        row = self.cost_rules.get(name, {})
        num = integer(row.get("numerator"))
        den = integer(row.get("denominator"))
        if num is None or den is None or den <= 0:
            return 1, 1
        return num, den

    # -- publication prohibitions ----------------------------------------
    def read_prohibitions(self) -> None:
        data = self.data
        policy = object_of_json(data / "publication_policy.json")
        self.prohibition_of: dict[str, str] = {}

        channels = tomllib.loads((data / "release_channels.toml").read_text(
            encoding="utf-8")).get("channel", {})
        frozen = {name for name, body in channels.items()
                  if isinstance(body, dict) and body.get("frozen") is True}

        held: dict[str, list[dict]] = defaultdict(list)
        for row in policy.get("reviews", []):
            resolved = self.check_row(row, [("component_id", "component")],
                                      "publication review")
            if resolved is None:
                continue
            held[resolved["component_id"]].append(row)
        review_held = {component for component, rows in held.items()
                       if text(winner(rows).get("publication_review")) == "held"}

        prohibited: set[str] = set()
        for row in policy.get("prohibitions", []):
            resolved = self.check_row(row, [("component_id", "component"),
                                            ("target_id", "target")],
                                      "publication prohibition")
            if resolved is None:
                continue
            if text(row.get("rule")) != "prohibited":
                continue
            unit_id = self.unit_of.get((resolved["component_id"],
                                        resolved["target_id"]))
            if unit_id is not None:
                prohibited.add(unit_id)

        for unit_id in sorted(self.units):
            unit = self.units[unit_id]
            codes = []
            if unit_id in prohibited:
                codes.append("E_PROHIBITED")
                self.record("E_PROHIBITED", unit_id,
                            "a prohibitions row of the publication policy names this unit")
            if unit["component_id"] in review_held:
                codes.append("E_REVIEW_HELD")
                self.record("E_REVIEW_HELD", unit_id,
                            "the publication review of the component is held")
            if unit["channel"] in frozen:
                codes.append("E_CHANNEL_FROZEN")
                self.record("E_CHANNEL_FROZEN", unit_id,
                            f"the channel {unit['channel']} is frozen")
            if codes:
                self.prohibition_of[unit_id] = codes[0]

    # -- stage 7, capacity -----------------------------------------------
    def read_budgets(self) -> None:
        data = self.data
        book = sheets_of_xlsx(data / "capacity_workbook.xlsx")
        budgets: dict[str, list[dict]] = defaultdict(list)
        for row in book.get("pool_budgets", []):
            if not is_active(row):
                continue
            pool = self.pool_of_row(row, "pool_id", "pool budget")
            if pool is None:
                continue
            if integer(row.get("budget_value")) is None:
                self.record("E_NON_INTEGER", pool,
                            "pool budget row ignored, budget_value is not an integer")
                continue
            budgets[pool].append(row)
        self.gross_budget: dict[str, int] = {pool: 0 for pool in self.pools}
        for pool, rows in budgets.items():
            row = winner(rows)
            value = integer(row.get("budget_value")) or 0
            if text(row.get("scale_unit")) == "milli_tick":
                value = ceil_div(value, 1000)
            self.gross_budget[pool] = value

        self.reserved: dict[str, int] = {pool: 0 for pool in self.pools}
        for row in rows_of_jsonl(data / "maintenance_windows.jsonl"):
            if not is_active(row):
                continue
            pool = self.pool_of_row(row, "pool_id", "maintenance window")
            if pool is None:
                continue
            amount = 0
            defective = False
            for field, value in sorted(row.items()):
                if not field.endswith(("_millis", "_ticks")):
                    continue
                number = integer(value)
                if number is None:
                    defective = True
                elif field.endswith("_millis"):
                    amount += ceil_div(number, 1000)
                else:
                    amount += number
            if defective:
                continue
            self.reserved[pool] += amount
        self.net_budget = {pool: max(0, self.gross_budget[pool] - self.reserved[pool])
                           for pool in self.pools}

        lanes: dict[str, int] = {pool: 0 for pool in self.pools}
        for row in rows_of_csv(data / "worker_pool_notes.csv"):
            if not is_active(row):
                continue
            pool = text(row.get("pool_id"))
            if pool not in self.pools:
                continue
            if text(row.get("lane_state")) == "operational":
                lanes[pool] += 1
        self.operational_lanes = lanes

    def build_closures(self) -> None:
        prerequisites: dict[str, set[str]] = {}
        for unit_id in self.dirty:
            unit = self.units[unit_id]
            target = unit["target_id"]
            found: set[str] = set()
            for other in self.required_dependencies[unit_id]:
                if other in self.dirty:
                    found.add(other)
            for interface in self.interfaces_of.get(unit["component_id"], {}):
                if interface not in self.changed_interfaces:
                    continue
                producer = self.generating_unit.get((interface, target))
                if producer is not None and producer in self.dirty \
                        and producer != unit_id:
                    found.add(producer)
            prerequisites[unit_id] = found
        self.prerequisites = prerequisites
        self.closures: dict[str, set[str]] = {}
        for unit_id in self.dirty:
            seen = {unit_id}
            stack = [unit_id]
            while stack:
                current = stack.pop()
                for other in prerequisites[current]:
                    if other not in seen:
                        seen.add(other)
                        stack.append(other)
            self.closures[unit_id] = seen

    def admit(self) -> None:
        self.selected: set[str] = set()
        self.admitted_with: dict[str, str] = {}
        self.deferral_code: dict[str, str] = {}
        consumed: dict[str, int] = {pool: 0 for pool in self.pools}
        for pool in sorted(self.pools):
            remaining = {unit_id for unit_id in self.dirty
                         if self.units[unit_id]["pool_id"] == pool
                         and unit_id not in self.prohibition_of}
            # the candidate order of this pool, closure cost counting only the
            # members no earlier pool has selected already
            order = sorted(remaining, key=lambda unit_id: (
                self.units[unit_id]["priority_class"],
                sum(self.cost_ticks[member] for member in self.closures[unit_id]
                    if member not in self.selected),
                unit_id))
            for unit_id in order:
                if unit_id in self.selected:
                    continue
                members = [member for member in sorted(self.closures[unit_id])
                           if member not in self.selected]
                draw: dict[str, int] = defaultdict(int)
                for member in members:
                    member_pool = self.units[member]["pool_id"]
                    if member_pool not in self.pools:
                        draw["__unknown__"] += self.cost_ticks[member]
                    else:
                        draw[member_pool] += self.cost_ticks[member]
                fits = all(
                    amount <= self.net_budget.get(name, 0) - consumed.get(name, 0)
                    for name, amount in draw.items())
                if fits:
                    for member in members:
                        self.selected.add(member)
                        self.admitted_with[member] = unit_id
                        member_pool = self.units[member]["pool_id"]
                        if member_pool in consumed:
                            consumed[member_pool] += self.cost_ticks[member]
                else:
                    self.deferral_code[unit_id] = "E_CAPACITY"

    # -- stage 9, cycles --------------------------------------------------
    def resolve_cycles(self) -> None:
        data = self.data
        groups = object_of_json(data / "cycle_groups.json")
        active_groups: dict[str, dict] = {}
        for row in groups.get("groups", []):
            if not is_active(row):
                continue
            active_groups[text(row.get("group_id"))] = row
        applicability: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in groups.get("applicability", []):
            resolved = self.check_row(row, [("target_id", "target")],
                                      "cycle group applicability")
            if resolved is None:
                continue
            applicability[(text(row.get("group_id")),
                           resolved["target_id"])].append(row)
        in_scope = {key for key, rows in applicability.items()
                    if flag(winner(rows).get("in_scope"))}
        by_members: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for group_id, row in active_groups.items():
            members = tuple(sorted({text(m) for m in row.get("members", [])}))
            by_members[members].append(group_id)

        # a cycle break removes the edge on the target the cycle is live on
        self.removed_edges: set[tuple[str, str, str]] = set()
        self.blocked_units: set[str] = set()
        self.blocked_targets: set[str] = set()
        self.cycle_records: list[dict] = []

        while True:
            found = None
            for target in sorted(self.targets):
                cycles = self.cycles_of_target(target)
                if cycles:
                    found = (target, cycles[0])
                    break
            if found is None:
                break
            target, cycle = found
            members = tuple(sorted({self.units[unit]["component_id"]
                                    for unit in cycle}))
            group_id = ""
            policy = "blocking"
            group = None
            for candidate in sorted(by_members.get(members, [])):
                if (candidate, target) in in_scope:
                    group_id = candidate
                    group = active_groups[candidate]
                    policy = text(group.get("policy"))
                    break
            edges = []
            for index, unit_id in enumerate(cycle):
                source = self.units[unit_id]["component_id"]
                destination = self.units[cycle[(index + 1) % len(cycle)]]["component_id"]
                edges.append((source, destination))
            break_costs = {}
            if group is not None and policy == "breakable":
                declared = group.get("break_costs") or {}
                for source, destination in edges:
                    value = integer(declared.get(f"{source}->{destination}"))
                    if value is not None:
                        break_costs[(source, destination)] = value
            if break_costs:
                cost, source, destination = min(
                    (value, edge[0], edge[1]) for edge, value in break_costs.items())
                self.removed_edges.add((target, source, destination))
                self.cycle_records.append({
                    "break_cost": cost,
                    "edge_removed": f"{source}->{destination}",
                    "group_id": group_id,
                    "members": list(members),
                    "policy": policy,
                    "target_id": target,
                    "units_blocked": [],
                })
            else:
                blocked = sorted(cycle)
                for unit_id in blocked:
                    self.blocked_units.add(unit_id)
                    self.selected.discard(unit_id)
                self.blocked_targets.add(target)
                self.cycle_records.append({
                    "break_cost": 0,
                    "edge_removed": "",
                    "group_id": group_id,
                    "members": list(members),
                    "policy": policy if group is not None else "blocking",
                    "target_id": target,
                    "units_blocked": blocked,
                })
        self.cycle_records.sort(key=lambda r: (r["target_id"], r["group_id"],
                                               r["edge_removed"]))

    def selected_graph(self, target: str) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        nodes = [unit_id for unit_id in self.units_of_target[target]
                 if unit_id in self.selected]
        node_set = set(nodes)
        for unit_id in nodes:
            edges = []
            component = self.units[unit_id]["component_id"]
            for other in self.required_dependencies[unit_id]:
                if other not in node_set:
                    continue
                source = self.units[other]["component_id"]
                if (target, source, component) in self.removed_edges:
                    continue
                edges.append(other)
            graph[unit_id] = sorted(edges)
        # edges run from a required dependency to its dependent
        forward: dict[str, list[str]] = {unit_id: [] for unit_id in nodes}
        for unit_id, sources in graph.items():
            for source in sources:
                forward[source].append(unit_id)
        return {unit_id: sorted(values) for unit_id, values in forward.items()}

    def cycles_of_target(self, target: str) -> list[list[str]]:
        graph = self.selected_graph(target)
        found: dict[tuple[str, ...], list[str]] = {}

        def visit(start: str, node: str, path: list[str], seen: set[str]) -> None:
            for other in graph.get(node, ()):
                if other == start and len(path) > 1:
                    members = tuple(sorted(path))
                    if members not in found:
                        rotation = path.index(min(path))
                        found[members] = path[rotation:] + path[:rotation]
                elif other not in seen and other > start:
                    visit(start, other, path + [other], seen | {other})

        order = sorted(graph)
        for start in order:
            visit(start, start, [start], {start})
        if not found:
            return []
        return [found[key] for key in sorted(found)]

    def demote(self) -> None:
        while True:
            lost = []
            for unit_id in sorted(self.selected):
                members = self.closures[unit_id] - {unit_id}
                if any(member not in self.selected for member in members):
                    lost.append(unit_id)
            if not lost:
                break
            for unit_id in lost:
                self.selected.discard(unit_id)
                self.deferral_code[unit_id] = "E_PREREQ_DEFERRED"

    # -- stage 8 and 10, the schedule -------------------------------------
    def schedule(self) -> None:
        data = self.data
        nodes = sorted(self.selected)
        node_set = set(nodes)
        successors: dict[str, set[str]] = {unit_id: set() for unit_id in nodes}
        dependencies: dict[str, set[str]] = {unit_id: set() for unit_id in nodes}

        def add(source: str, destination: str) -> bool:
            if source == destination:
                return False
            if destination in successors[source]:
                return True
            if self.reaches(successors, destination, source):
                return False
            successors[source].add(destination)
            return True

        for unit_id in nodes:
            component = self.units[unit_id]["component_id"]
            target = self.units[unit_id]["target_id"]
            for other in self.required_dependencies[unit_id]:
                if other not in node_set:
                    continue
                source = self.units[other]["component_id"]
                if (target, source, component) in self.removed_edges:
                    continue
                successors[other].add(unit_id)
                dependencies[unit_id].add(other)

        constraints: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "deployment_constraints.jsonl"):
            if text(row.get("constraint")) != "migration_first":
                continue
            resolved = self.check_row(row, [("migration_component", "component"),
                                            ("blocks_component", "component"),
                                            ("target_id", "target")],
                                      "deployment constraint")
            if resolved is None:
                continue
            constraints[(resolved["migration_component"],
                         resolved["blocks_component"],
                         resolved["target_id"])].append(row)
        self.migration_rows: list[dict] = []
        for key in sorted(constraints):
            migration_component, blocked_component, target = key
            migration = self.unit_of.get((migration_component, target))
            blocked = self.unit_of.get((blocked_component, target))
            if migration is None or blocked is None:
                continue
            if migration not in node_set or blocked not in node_set:
                continue
            if add(migration, blocked):
                self.migration_rows.append({"migration_unit": migration,
                                            "blocks_unit": blocked,
                                            "target_id": target})
            else:
                self.record("E_ORDER_IGNORED", f"{migration}->{blocked}",
                            "the migration_first edge would close a cycle")
                self.migration_rows.append({"migration_unit": migration,
                                            "blocks_unit": blocked,
                                            "target_id": target})

        overrides: dict[str, list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "ordering_overrides.jsonl"):
            resolved = self.check_row(row, [("before_unit", "unit"),
                                            ("after_unit", "unit")],
                                      "ordering override")
            if resolved is None:
                continue
            overrides[text(row.get("row_id"))].append(
                {**row, "before_unit": resolved["before_unit"],
                 "after_unit": resolved["after_unit"]})
        for row_id in sorted(overrides):
            row = winner(overrides[row_id])
            before, after = row["before_unit"], row["after_unit"]
            if before not in node_set or after not in node_set:
                continue
            if not add(before, after):
                self.record("E_ORDER_IGNORED", f"{before}->{after}",
                            "the ordering override would close a cycle")

        indegree = {unit_id: 0 for unit_id in nodes}
        for source, destinations in successors.items():
            for destination in destinations:
                indegree[destination] += 1
        ready = sorted((self.units[unit_id]["priority_class"], unit_id)
                       for unit_id in nodes if indegree[unit_id] == 0)
        self.sequence: dict[str, int] = {}
        step = 0
        while ready:
            _, unit_id = ready.pop(0)
            step += 1
            self.sequence[unit_id] = step
            for destination in sorted(successors[unit_id]):
                indegree[destination] -= 1
                if indegree[destination] == 0:
                    ready.append((self.units[destination]["priority_class"],
                                  destination))
            ready.sort()
        self.schedule_dependencies = {
            unit_id: sorted(dependencies[unit_id]) for unit_id in nodes}

    @staticmethod
    def reaches(successors: dict[str, set[str]], start: str, goal: str) -> bool:
        stack = [start]
        seen = {start}
        while stack:
            node = stack.pop()
            if node == goal:
                return True
            for other in successors.get(node, ()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        return False

    # -- stage 11 and 12, compatibility and version selection -------------
    def select_versions(self) -> None:
        data = self.data
        versions: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "component_versions.jsonl"):
            resolved = self.check_row(row, [("component_id", "component")],
                                      "component version")
            if resolved is None:
                continue
            versions[(resolved["component_id"], text(row.get("version")))].append(row)
        candidates: dict[str, list[dict]] = defaultdict(list)
        for key in sorted(versions):
            component, version = key
            if self.window_states.get(key, "supported") == "withdrawn":
                continue
            row = winner(versions[key])
            preference = integer(row.get("local_preference"))
            candidates[component].append({
                "version": version,
                "local_preference": preference if preference is not None else 0,
                "api_revision": text(row.get("api_revision")),
            })

        compatible: dict[tuple[str, str, str, str, str], bool] = {}
        grouped: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
        for row in rows_of_jsonl(data / "api_compatibility.jsonl"):
            resolved = self.check_row(row, [("left_component", "component"),
                                            ("right_component", "component")],
                                      "api compatibility")
            if resolved is None:
                continue
            grouped[(text(row.get("cluster_id")), resolved["left_component"],
                     text(row.get("left_version")), resolved["right_component"],
                     text(row.get("right_version")))].append(row)
        for key, rows in grouped.items():
            compatible[key] = flag(winner(rows).get("compatible"))

        selected_components = {self.units[unit_id]["component_id"]
                              for unit_id in self.selected}
        precedence = object_of_json(data / "version_precedence.json")
        clusters: dict[str, list[str]] = {}
        for row in precedence.get("clusters", []):
            if not is_active(row):
                continue
            cluster = text(row.get("cluster_id"))
            members = []
            for member in row.get("members", []):
                name = text(member)
                if not COMPONENT_RE.match(name):
                    self.record("E_ID_FORM", name,
                                "version precedence cluster member ignored, "
                                "identifier not in canonical form")
                    continue
                if name not in self.components:
                    self.record("E_UNKNOWN_UNIT", name,
                                "version precedence cluster member ignored, "
                                "identifier names no register row")
                    continue
                members.append(name)
            clusters[cluster] = sorted(set(members))

        self.version_rows: list[dict] = []
        self.matrix_rows: list[dict] = []
        self.rejected_rows: list[dict] = []
        self.unresolved_clusters: list[str] = []
        self.version_of: dict[str, str] = {}
        withdrawn_recorded: set[str] = set()

        for cluster in sorted(clusters):
            members = [member for member in clusters[cluster]
                       if member in selected_components]
            if not members:
                continue
            missing = [member for member in members if not candidates.get(member)]
            for member in missing:
                if member not in withdrawn_recorded:
                    withdrawn_recorded.add(member)
                    self.record("E_WITHDRAWN_VERSION", member,
                                "every version of the component is withdrawn")
            members = [member for member in members if candidates.get(member)]
            if not members:
                self.unresolved_clusters.append(cluster)
                self.record("E_CLUSTER_UNRESOLVED", cluster,
                            "no member of the cluster has a supported version")
                continue
            combinations = [[]]
            for member in members:
                grown = []
                for partial in combinations:
                    for candidate in sorted(candidates[member],
                                            key=lambda c: c["version"]):
                        grown.append(partial + [candidate])
                combinations = grown
            scored = []
            for combination in combinations:
                total = sum(candidate["local_preference"] for candidate in combination)
                picks = [candidate["version"] for candidate in combination]
                ok = True
                for left in range(len(members)):
                    for right in range(left + 1, len(members)):
                        key = (cluster, members[left], picks[left],
                               members[right], picks[right])
                        if not compatible.get(key, False):
                            ok = False
                            break
                    if not ok:
                        break
                scored.append((total, picks, ok, combination))
            feasible = [entry for entry in scored if entry[2]]
            if not feasible:
                self.unresolved_clusters.append(cluster)
                self.record("E_CLUSTER_UNRESOLVED", cluster,
                            "the cluster has no compatible combination")
                for total, picks, _ok, _combination in sorted(
                        scored, key=lambda e: (e[0], e[1])):
                    self.rejected_rows.append({
                        "cluster_id": cluster,
                        "members": list(members),
                        "preference_sum": total,
                        "reason": "cluster_unresolved",
                        "versions": list(picks),
                    })
                continue
            best = min(feasible, key=lambda entry: (entry[0], entry[1]))
            total, picks, _ok, combination = best
            for total_other, picks_other, ok_other, _c in sorted(
                    scored, key=lambda e: (e[0], e[1])):
                if total_other < total and not ok_other:
                    self.rejected_rows.append({
                        "cluster_id": cluster,
                        "members": list(members),
                        "preference_sum": total_other,
                        "reason": "incompatible",
                        "versions": list(picks_other),
                    })
            for member, candidate in zip(members, combination):
                self.version_rows.append({
                    "api_revision": candidate["api_revision"],
                    "cluster_id": cluster,
                    "component_id": member,
                    "local_preference": candidate["local_preference"],
                    "preference_sum": total,
                    "version": candidate["version"],
                })
                self.version_of.setdefault(member, candidate["version"])
            for left in range(len(members)):
                for right in range(left + 1, len(members)):
                    self.matrix_rows.append({
                        "cluster_id": cluster,
                        "compatible": True,
                        "left_component": members[left],
                        "left_version": picks[left],
                        "right_component": members[right],
                        "right_version": picks[right],
                    })
        self.version_rows.sort(key=lambda r: (r["component_id"], r["cluster_id"]))
        self.matrix_rows.sort(key=lambda r: (r["cluster_id"], r["left_component"],
                                             r["right_component"]))
        self.rejected_rows.sort(key=lambda r: (r["cluster_id"], r["preference_sum"],
                                               r["versions"]))

    # -- stage 13, membership ---------------------------------------------
    def membership(self) -> None:
        self.state: dict[str, str] = {}
        self.reason_code: dict[str, str] = {}
        for unit_id in sorted(self.units):
            prohibition = self.prohibition_of.get(unit_id, "")
            if unit_id in self.blocked_units:
                state, code = "blocked", "E_CYCLE_BLOCKING"
                self.record(code, unit_id,
                            "cycle policy removed the unit from the release")
            elif unit_id in self.selected:
                if prohibition:
                    state, code = "built_not_published", prohibition
                else:
                    state, code = "included", ""
            elif unit_id not in self.dirty:
                state, code = "reused", ""
            elif prohibition:
                state, code = "excluded", prohibition
            else:
                code = self.deferral_code.get(unit_id, "E_CAPACITY")
                state = "deferred"
            if state == "deferred":
                self.record(code, unit_id, "the unit leaves the release")
            self.state[unit_id] = state
            self.reason_code[unit_id] = code

    # -- stage 15, amortization -------------------------------------------
    def amortize(self) -> None:
        self.amortization_rows: list[dict] = []
        producers: dict[tuple[str, str], set[str]] = defaultdict(set)
        for (interface, _kind), row in self.generated_outputs.items():
            component = text(row.get("generated_sdk_component"))
            for target in self.targets:
                unit_id = self.unit_of.get((component, target))
                if unit_id is not None and unit_id in self.selected:
                    producers[(unit_id, interface)].add(target)
        for (unit_id, interface) in sorted(producers):
            target = self.units[unit_id]["target_id"]
            consumers = sorted({component
                                for component in self.required_consumers.get(interface, [])
                                if self.unit_of.get((component, target)) in self.selected})
            if not consumers:
                continue
            cost = self.cost_ticks.get(unit_id, 0)
            count = len(consumers)
            base = cost // count
            remainder = cost - count * base
            for index, component in enumerate(consumers):
                share = base + (1 if index < remainder else 0)
                self.amortization_rows.append({
                    "consumer_component": component,
                    "interface_id": interface,
                    "producer_unit": unit_id,
                    "remainder_rank": index + 1,
                    "share_ticks": share,
                    "target_id": target,
                })
        self.amortization_rows.sort(key=lambda r: (r["producer_unit"], r["interface_id"],
                                                   r["consumer_component"]))

    # -- the package -------------------------------------------------------
    def write(self, out: Path) -> None:
        out.mkdir(parents=True, exist_ok=True)

        def write_jsonl(name: str, records: list[dict]) -> None:
            body = "".join(json.dumps(record, sort_keys=True,
                                      separators=(",", ":")) + "\n"
                           for record in records)
            (out / name).write_text(body, encoding="utf-8")

        def write_json(name: str, obj) -> None:
            (out / name).write_text(
                json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        order = sorted(self.units)

        write_jsonl("normalized_inventory.jsonl", [{
            "base_cost_ticks": self.units[u]["base_cost_ticks"],
            "channel": self.units[u]["channel"],
            "component_id": self.units[u]["component_id"],
            "kind": self.units[u]["kind"],
            "mandatory": self.units[u]["mandatory"],
            "pool_id": self.units[u]["pool_id"],
            "priority_class": self.units[u]["priority_class"],
            "priority_overridden": self.units[u]["priority_overridden"],
            "scope_tag": self.units[u]["scope_tag"],
            "target_id": self.units[u]["target_id"],
            "unit_id": u,
        } for u in order])

        write_jsonl("revision_delta.jsonl", [{
            "component_id": self.units[u]["component_id"],
            "in_previous_release": self.units[u]["in_previous_release"],
            "previous_source_revision": self.units[u]["previous_source_revision"],
            "source_changed": self.units[u]["source_changed"],
            "source_revision": self.units[u]["source_revision"],
            "target_id": self.units[u]["target_id"],
            "unit_id": u,
        } for u in order])

        write_jsonl("toolchain_resolution.jsonl", [{
            "override_applied": self.units[u]["override_applied"],
            "previous_toolchain_revision": self.units[u]["previous_toolchain_revision"],
            "profile_id": self.units[u]["profile_id"],
            "toolchain_id": self.units[u]["toolchain_id"],
            "toolchain_revision": self.units[u]["toolchain_revision"],
            "unit_id": u,
        } for u in order])

        write_jsonl("contract_delta.jsonl", [{
            "contract_changed": self.units[u]["contract_changed"],
            "contract_revision": self.units[u]["contract_revision"],
            "optional_interfaces": self.units[u]["optional_interfaces"],
            "previous_contract_revision": self.units[u]["previous_contract_revision"],
            "required_interfaces": self.units[u]["required_interfaces"],
            "unit_id": u,
        } for u in order])

        write_jsonl("invalidation_reasons.jsonl", [{
            "dirty": self.units[u]["dirty"],
            "reason_count": len(self.units[u]["reasons"]),
            "reasons": self.units[u]["reasons"],
            "unit_id": u,
        } for u in order])

        write_jsonl("invalidation_closure.jsonl", [{
            "component_id": self.units[u]["component_id"],
            "direct": self.direct_reasons[u],
            "kind": self.units[u]["kind"],
            "reasons": self.units[u]["reasons"],
            "target_id": self.units[u]["target_id"],
            "unit_id": u,
        } for u in order if u in self.dirty])

        write_jsonl("generated_output_plan.jsonl", self.output_plan)

        write_jsonl("build_unit_ledger.jsonl", [{
            "channel": self.units[u]["channel"],
            "component_id": self.units[u]["component_id"],
            "contract_revision": self.units[u]["contract_revision"],
            "kind": self.units[u]["kind"],
            "pool_id": self.units[u]["pool_id"],
            "reasons": self.units[u]["reasons"],
            "required_dependencies": self.required_dependencies[u],
            "source_revision": self.units[u]["source_revision"],
            "state": self.state[u],
            "target_id": self.units[u]["target_id"],
            "toolchain_revision": self.units[u]["toolchain_revision"],
            "unit_id": u,
        } for u in order])

        write_jsonl("build_cost_breakdown.jsonl", self.cost_rows)

        selected = sorted(self.selected)
        write_jsonl("capacity_allocation.jsonl", [{
            "admitted_with": self.admitted_with.get(u, u),
            "cost_ticks": self.cost_ticks.get(u, 0),
            "pool_id": self.units[u]["pool_id"],
            "priority_class": self.units[u]["priority_class"],
            "unit_id": u,
        } for u in selected])

        write_jsonl("deferred_units.jsonl", [{
            "cost_ticks": self.cost_ticks.get(u, 0),
            "pool_id": self.units[u]["pool_id"],
            "priority_class": self.units[u]["priority_class"],
            "reason_code": self.reason_code[u],
            "unit_id": u,
        } for u in order if self.state[u] == "deferred"])

        write_jsonl("dependency_schedule.jsonl", [{
            "cost_ticks": self.cost_ticks.get(u, 0),
            "dependencies": self.schedule_dependencies[u],
            "pool_id": self.units[u]["pool_id"],
            "priority_class": self.units[u]["priority_class"],
            "sequence": self.sequence[u],
            "unit_id": u,
        } for u in sorted(self.sequence, key=lambda u: self.sequence[u])])

        write_jsonl("cycle_resolution.jsonl", self.cycle_records)

        consumed: dict[str, int] = {pool: 0 for pool in self.pools}
        selected_count: dict[str, int] = {pool: 0 for pool in self.pools}
        deferred_count: dict[str, int] = {pool: 0 for pool in self.pools}
        for unit_id in order:
            pool = self.units[unit_id]["pool_id"]
            if pool not in self.pools:
                continue
            if unit_id in self.selected:
                consumed[pool] += self.cost_ticks.get(unit_id, 0)
                selected_count[pool] += 1
            elif self.state[unit_id] == "deferred":
                deferred_count[pool] += 1
        write_json("worker_pool_summary.json", {
            "pools": {pool: {
                "consumed_ticks": consumed[pool],
                "deferred_units": deferred_count[pool],
                "gross_budget_ticks": self.gross_budget[pool],
                "net_budget_ticks": self.net_budget[pool],
                "operational_lanes": self.operational_lanes[pool],
                "remaining_ticks": self.net_budget[pool] - consumed[pool],
                "reserved_ticks": self.reserved[pool],
                "selected_units": selected_count[pool],
            } for pool in sorted(self.pools)},
            "release_id": self.release_id,
        })

        write_jsonl("compatibility_matrix.jsonl", self.matrix_rows)
        write_jsonl("rejected_combinations.jsonl", self.rejected_rows)
        write_jsonl("version_selection.jsonl", self.version_rows)

        write_jsonl("release_membership.jsonl", [{
            "pool_id": self.units[u]["pool_id"],
            "reason_code": self.reason_code[u],
            "state": self.state[u],
            "target_id": self.units[u]["target_id"],
            "unit_id": u,
        } for u in order])

        # a prohibited unit never enters the deployment manifest, whether it was
        # built for an admitted closure or carried over from the last release
        members = [u for u in order if self.state[u] in ("included", "reused")
                   and u not in self.prohibition_of]
        write_json("deployment_manifest.json", {
            "decision": self.decision,
            "member_count": len(members),
            "members": [{
                "component_id": self.units[u]["component_id"],
                "contract_revision": self.units[u]["contract_revision"],
                "kind": self.units[u]["kind"],
                "target_id": self.units[u]["target_id"],
                "unit_id": u,
                "version": self.version_of.get(self.units[u]["component_id"], ""),
            } for u in members],
            "release_id": self.release_id,
        })

        sdk_rows = []
        for row in self.output_plan:
            if not row["regenerate"]:
                continue
            producer = row["producer_unit"]
            if producer not in self.selected:
                continue
            sdk_rows.append({
                "artifact_kind": row["artifact_kind"],
                "contract_revision": row["contract_revision"],
                "interface_id": row["interface_id"],
                "producer_unit": producer,
                "producer_version": self.version_of.get(
                    self.units[producer]["component_id"], ""),
            })
        sdk_rows.sort(key=lambda r: (r["producer_unit"], r["interface_id"],
                                     r["artifact_kind"]))
        write_jsonl("generated_sdk_manifest.jsonl", sdk_rows)

        migration_rows = []
        for row in self.migration_rows:
            migration, blocked = row["migration_unit"], row["blocks_unit"]
            migration_rows.append({
                "blocked_sequence": self.sequence.get(blocked, 0),
                "blocks_unit": blocked,
                "migration_sequence": self.sequence.get(migration, 0),
                "migration_unit": migration,
                "ordered": self.sequence.get(migration, 0) < self.sequence.get(blocked, 0),
                "target_id": row["target_id"],
            })
        migration_rows.sort(key=lambda r: (r["migration_unit"], r["blocks_unit"]))
        write_jsonl("migration_order.jsonl", migration_rows)

        write_jsonl("artifact_provenance.jsonl", [{
            "contract_revision": self.units[u]["contract_revision"],
            "cost_ticks": self.cost_ticks.get(u, 0),
            "pool_id": self.units[u]["pool_id"],
            "reasons": self.units[u]["reasons"],
            "schedule_sequence": self.sequence.get(u, 0),
            "source_revision": self.units[u]["source_revision"],
            "toolchain_revision": self.units[u]["toolchain_revision"],
            "unit_id": u,
        } for u in selected])

        write_jsonl("cache_reuse_manifest.jsonl", [{
            "artifact_digest": self.units[u]["previous_artifact_digest"],
            "justification": "empty reason set, artifact retained by the published index",
            "reusable": True,
            "unit_id": u,
        } for u in order if self.state[u] == "reused"])

        release_units = {u for u in order
                         if self.state[u] in ("included", "built_not_published",
                                              "reused")}
        previous_units = set(self.ledger)
        added = sorted(release_units - previous_units)
        removed = sorted(previous_units - release_units)
        retained = sorted(release_units & previous_units)
        write_json("release_delta.json", {
            "added_count": len(added),
            "added_units": added,
            "previous_release_id": self.previous_release_id,
            "release_id": self.release_id,
            "removed_count": len(removed),
            "removed_units": removed,
            "retained_count": len(retained),
            "retained_units": retained,
        })

        exceptions = sorted(self.exceptions,
                            key=lambda r: (r["code"], r["subject"], r["detail"]))
        write_jsonl("audit_exceptions.jsonl", exceptions)
        write_jsonl("cost_amortization.jsonl", self.amortization_rows)

        counts = self.counts()
        write_json("release_decision.json", {
            "blocked_targets": sorted(self.blocked_targets),
            "decision": self.decision,
            "exception_count": len(exceptions),
            "mandatory_units_withheld": self.withheld,
            "release_id": self.release_id,
            "scheduled_units": len(self.sequence),
            "total_cost_ticks": self.total_cost,
            "units_blocked": counts["blocked"],
            "units_built_not_published": counts["built_not_published"],
            "units_deferred": counts["deferred"],
            "units_excluded": counts["excluded"],
            "units_included": counts["included"],
            "units_reused": counts["reused"],
            "units_total": len(self.units),
            "unresolved_clusters": sorted(self.unresolved_clusters),
        })

        rows = [("units_total", len(self.units)),
                ("units_included", counts["included"]),
                ("units_built_not_published", counts["built_not_published"]),
                ("units_reused", counts["reused"]),
                ("units_deferred", counts["deferred"]),
                ("units_blocked", counts["blocked"]),
                ("units_excluded", counts["excluded"]),
                ("scheduled_units", len(self.sequence)),
                ("total_cost_ticks", self.total_cost),
                ("exception_count", len(exceptions)),
                ("decision", self.decision)]
        body = "metric,value\n" + "".join(f"{name},{value}\n" for name, value in rows)
        (out / "conformance_summary.csv").write_text(body, encoding="utf-8")

    def counts(self) -> dict[str, int]:
        counts = {"included": 0, "built_not_published": 0, "reused": 0,
                  "deferred": 0, "blocked": 0, "excluded": 0}
        for state in self.state.values():
            counts[state] += 1
        return counts

    def decide(self) -> None:
        self.total_cost = sum(self.cost_ticks.get(unit_id, 0)
                              for unit_id in self.selected)
        withheld = [unit_id for unit_id in sorted(self.units)
                    if self.units[unit_id]["mandatory"]
                    and self.state[unit_id] in ("deferred", "blocked", "excluded")]
        self.withheld = withheld
        if self.blocked_targets or self.unresolved_clusters:
            self.decision = "blocked"
        elif withheld:
            self.decision = "deferred"
        else:
            self.decision = "publishable"

    # -- the whole run -----------------------------------------------------
    def run(self, out: Path) -> None:
        self.read_registers()
        self.read_addendum_a()
        self.read_addendum_b()
        self.build_inventory()
        self.resolve_revisions()
        self.read_build_graph()
        self.invalidate()
        self.plan_generated_outputs()
        self.price()
        self.read_prohibitions()
        self.read_budgets()
        self.build_closures()
        self.admit()
        self.resolve_cycles()
        self.demote()
        self.schedule()
        self.select_versions()
        self.membership()
        self.amortize()
        self.decide()
        self.write(out)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(__doc__ or "")
        return 2
    sys.setrecursionlimit(20000)
    Planner(Path(argv[1])).run(Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
