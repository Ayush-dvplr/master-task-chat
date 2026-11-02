#!/usr/bin/env python3
"""Release train planner for release R-NEXT.

    python3 relplan.py DATA_DIR OUT_DIR

Rebuilds the release package into OUT_DIR from the corpus in DATA_DIR under the
rules of release_engineering_handbook.md, rounding_precedence_addendum.pdf
(addendum A) and compatibility_window_notes.docx (addendum B).  Every figure is
derived from the corpus, all arithmetic is integer arithmetic and the output is
byte for byte reproducible.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zlib
import zipfile
import xml.etree.ElementTree as ET
from itertools import product as iproduct
from pathlib import Path

NS_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_XR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

CID_RE = re.compile(r"C-\d{4}\Z")
TID_RE = re.compile(r"T-\d{2}\Z")
IFID_RE = re.compile(r"IF-\d{3}\Z")
INT_RE = re.compile(r"[+-]?\d+\Z")
A8_ROW_RE = re.compile(r"\A\S+\s+\d+\s+\S+\s+\d+\Z")

DIRECT_REASONS = (
    "absent_from_previous_release",
    "source_changed",
    "toolchain_changed",
    "contract_changed",
    "published_artifact_missing",
)
PROPAGATED_REASONS = ("dependency_rebuilt", "generated_interface_rebuilt")
PROHIBITION_ORDER = ("E_PROHIBITED", "E_REVIEW_HELD", "E_CHANNEL_FROZEN")


def ceildiv(a: int, b: int) -> int:
    """Ceiling division for a >= 0 and b > 0 (addendum A section A2)."""
    return -(-a // b)


# ---------------------------------------------------------------- low level IO


def read_jsonl(path: Path) -> list:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_int(raw) -> tuple[bool, int | None]:
    """Integer with underscore digit grouping; a decimal point is not one."""
    if isinstance(raw, bool):
        return False, None
    if isinstance(raw, int):
        return True, raw
    text = str(raw).strip().replace("_", "")
    if not text or "." in text or not INT_RE.match(text):
        return False, None
    return True, int(text)


def row_seq(row: dict) -> int:
    ok, value = parse_int(row.get("revision_seq"))
    return value if ok else 0


def row_key(row: dict) -> str:
    return str(row.get("row_id") or "").strip()


def pick(rows: list[dict]) -> dict:
    """Handbook section 2 rule 6: greatest revision_seq, then bytewise row_id."""
    best = None
    for row in rows:
        key = (row_seq(row), row_key(row))
        if best is None or key > best[0]:
            best = (key, row)
    return best[1]


def group_winners(rows: list[dict], keyfn) -> dict:
    """Active rows only; the winner of each key group survives."""
    groups: dict = {}
    for row in rows:
        if str(row.get("status") or "").strip() != "active":
            continue
        key = keyfn(row)
        groups.setdefault(key, []).append(row)
    return {key: pick(group) for key, group in groups.items()}


def workbook_sheets(path: Path) -> dict[str, list[dict]]:
    sheets: dict[str, list[dict]] = {}
    with zipfile.ZipFile(path) as zf:
        book = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = {
            rel.get("Id"): rel.get("Target")
            for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        }
        for sheet in book.find(NS_X + "sheets"):
            part = "xl/" + str(rels[sheet.get(NS_XR + "id")]).lstrip("/")
            data = ET.fromstring(zf.read(part))
            grid = []
            sheet_data = data.find(NS_X + "sheetData")
            for row in (sheet_data if sheet_data is not None else []):
                cells = []
                for cell in row:
                    inline = cell.find(NS_X + "is/" + NS_X + "t")
                    value = cell.find(NS_X + "v")
                    if inline is not None:
                        cells.append(inline.text or "")
                    else:
                        cells.append(value.text if value is not None and value.text else "")
                grid.append(cells)
            header = grid[0] if grid else []
            sheets[sheet.get("name")] = [dict(zip(header, line)) for line in grid[1:]]
    return sheets


def pdf_lines(path: Path) -> list[str]:
    """Text lines of the addendum PDF, in document order."""
    data = path.read_bytes()
    lines: list[str] = []
    for m in re.finditer(rb"\d+\s+0\s+obj\s*(<<[^>]*>>)\s*stream\r?\n", data):
        length = re.search(rb"/Length\s+(\d+)", m.group(1))
        start = m.end()
        if length:
            raw = data[start : start + int(length.group(1))]
        else:
            raw = data[start : data.find(b"endstream", start)]
        try:
            raw = zlib.decompress(raw)
        except Exception:
            pass
        text = raw.decode("latin-1")
        for tm in re.finditer(r"\((.*?)\)\s*Tj", text, re.S):
            piece = tm.group(1)
            piece = piece.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
            lines.append(piece)
    return lines


def docx_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    rows = []
    for tr in doc.iter(NS_W + "tr"):
        cells = [
            "".join(t.text or "" for t in tc.iter(NS_W + "t"))
            for tc in tr.iter(NS_W + "tc")
        ]
        if cells:
            rows.append(cells)
    return rows


def toml_channels(path: Path) -> dict[str, bool]:
    """Channel freeze flags out of release_channels.toml (addendum B)."""
    frozen: dict[str, bool] = {}
    channel = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        if text.startswith("[["):
            channel = ""
            continue
        if text.startswith("[") and text.endswith("]"):
            name = text[1:-1].strip()
            channel = name[len("channel.") :].strip() if name.startswith("channel.") else ""
            continue
        if channel and "=" in text:
            key, _, value = text.partition("=")
            if key.strip() == "frozen":
                frozen[channel] = value.strip().lower() == "true"
    return frozen


# ------------------------------------------------------------------- planner


class Planner:
    def __init__(self, data_dir: Path):
        self.d = data_dir
        self.exceptions: list[dict] = []
        self.units: dict[str, dict] = {}
        self.components: dict[str, dict] = {}
        self.targets: dict[str, dict] = {}
        self.pools: dict[str, dict] = {}
        self.release_id = ""
        self.previous_release_id = ""

    # ------------------------------------------------------------- exceptions

    def exc(self, code: str, subject: str, detail: str) -> None:
        self.exceptions.append({"code": code, "detail": detail, "subject": subject})

    def identifier(self, raw, regex, where: str, field: str) -> str | None:
        """Section 2 rules 1 and 2: strip padding, reject non canonical form."""
        text = str(raw or "").strip()
        if regex.match(text):
            return text
        if text:
            self.exc(
                "E_ID_FORM",
                text,
                "%s: %s %r is not in canonical form" % (where, field, text),
            )
        return None

    def integer(self, raw, where: str, field: str, subject: str) -> int | None:
        """Section 2 rule 4 and addendum A section A2."""
        ok, value = parse_int(raw)
        if ok:
            return value
        self.exc(
            "E_NON_INTEGER",
            subject,
            "%s: %s is not a whole tick count" % (where, field),
        )
        return None

    def known_component(self, cid: str | None, where: str, field: str) -> str | None:
        if cid is None:
            return None
        if cid not in self.components:
            self.exc(
                "E_UNKNOWN_UNIT",
                cid,
                "%s: %s %s names no component of the register" % (where, field, cid),
            )
            return None
        return cid

    def known_target(self, tid: str | None, where: str, field: str) -> str | None:
        if tid is None:
            return None
        if tid not in self.targets:
            self.exc(
                "E_UNKNOWN_UNIT",
                tid,
                "%s: %s %s names no target of the register" % (where, field, tid),
            )
            return None
        return tid

    # ------------------------------------------------------------ stage 1, ids

    def load_registers(self) -> None:
        register = read_json(self.d / "target_register.json")
        self.release_id = str(register.get("release_id") or "")
        self.previous_release_id = str(register.get("previous_release_id") or "")
        self.targets = {
            str(t.get("target_id") or "").strip(): t
            for t in register.get("targets", [])
            if t.get("enabled") is True
            and TID_RE.match(str(t.get("target_id") or "").strip())
        }
        self.pools = {
            str(p.get("pool_id") or "").strip(): p
            for p in read_json(self.d / "pool_register.json").get("pools", [])
        }

    def load_priority_overrides(self) -> dict[str, int]:
        """Addendum A section A8 table out of the addendum PDF."""
        overrides: dict[str, int] = {}
        rows = []
        for line in pdf_lines(self.d / "rounding_precedence_addendum.pdf"):
            text = line.strip()
            if not A8_ROW_RE.match(text):
                continue
            parts = text.split()
            if parts[0] == "component_id":
                continue
            rows.append(
                {
                    "component_id": parts[0],
                    "priority_class": parts[1],
                    "status": parts[2],
                    "revision_seq": parts[3],
                    "row_id": "line-%d" % len(rows),
                }
            )
        for idx, row in enumerate(rows):
            cid = row["component_id"]
            if not CID_RE.match(cid):
                self.exc(
                    "E_ID_FORM",
                    cid,
                    "addendum A section A8 row %d names a component that is not in "
                    "canonical upper case form" % (idx + 1),
                )
                continue
            if str(row.get("status") or "").strip() != "active":
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "addendum A section A8 row %d names a component absent from the "
                    "register" % (idx + 1),
                )
                continue
            ok, value = parse_int(row.get("priority_class"))
            if not ok:
                self.exc(
                    "E_NON_INTEGER",
                    cid,
                    "addendum A section A8 row %d priority_class is not an integer"
                    % (idx + 1),
                )
                continue
            previous = overrides.get(cid)
            if previous is None or (row_seq(row), row_key(row)) > previous[0]:
                overrides[cid] = ((row_seq(row), row_key(row)), value)
        return {cid: value for cid, (key, value) in overrides.items()}

    def load_inventory(self) -> None:
        # component register
        rows = []
        for row in read_csv(self.d / "component_register.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            cid = self.identifier(row.get("component_id"), CID_RE,
                                  "component register", "component_id")
            if cid is None:
                continue
            base = self.integer(row.get("base_cost_ticks"), "component register",
                                "base_cost_ticks", cid)
            if base is None:
                continue
            prio = self.integer(row.get("priority_class"), "component register",
                                "priority_class", cid)
            if prio is None:
                continue
            pool_id = str(row.get("pool_id") or "").strip()
            if pool_id and pool_id not in self.pools:
                self.exc(
                    "E_UNKNOWN_POOL",
                    pool_id,
                    "component register row %s names a pool absent from the pool "
                    "register" % (row.get("row_id") or ""),
                )
            row["component_id"] = cid
            row["_base_cost_ticks"] = base
            row["_priority_class"] = prio
            row["_mandatory"] = str(row.get("mandatory") or "").strip() == "true"
            rows.append(row)
        for cid, row in group_winners(rows, lambda r: r["component_id"]).items():
            self.components[cid] = row

        overrides = self.load_priority_overrides()

        # eligibility table
        eligibility = {}
        elig_rows = [
            row
            for row in read_json(self.d / "target_register.json").get("eligibility", [])
            if str(row.get("status") or "").strip() == "active"
        ]
        for key, row in group_winners(
            elig_rows,
            lambda r: (
                str(r.get("target_id") or "").strip(),
                str(r.get("kind") or "").strip(),
                str(r.get("channel") or "").strip(),
            ),
        ).items():
            eligibility[key] = row.get("eligible") is True

        # target matrix
        matrix = {}
        mrows = []
        for row in read_csv(self.d / "target_matrix.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            cid = self.identifier(row.get("component_id"), CID_RE,
                                   "target matrix", "component_id")
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "target matrix", "target_id")
            if cid is None or tid is None:
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "target matrix row %s names a component absent from the register"
                    % (row.get("row_id") or ""),
                )
                continue
            if tid not in self.targets:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    tid,
                    "target matrix row %s names a target absent from the register"
                    % (row.get("row_id") or ""),
                )
                continue
            row["_component_id"] = cid
            row["_target_id"] = tid
            mrows.append(row)
        for key, row in group_winners(
            mrows, lambda r: (r["_component_id"], r["_target_id"])
        ).items():
            matrix[key] = row

        for (cid, tid), row in sorted(matrix.items()):
            if str(row.get("enabled") or "").strip() != "true":
                continue
            comp = self.components[cid]
            unit_id = cid + ":" + tid
            if not eligibility.get((tid, comp["kind"], comp["channel"]), False):
                self.exc(
                    "E_NOT_ELIGIBLE",
                    unit_id,
                    "the eligibility table refuses %s for kind %s on channel %s"
                    % (tid, comp["kind"], comp["channel"]),
                )
                continue
            overridden = cid in overrides
            self.units[unit_id] = {
                "unit_id": unit_id,
                "component_id": cid,
                "target_id": tid,
                "kind": comp["kind"],
                "channel": comp["channel"],
                "pool_id": comp["pool_id"],
                "base_cost_ticks": comp["_base_cost_ticks"],
                "mandatory": comp["_mandatory"],
                "priority_class": overrides[cid] if overridden else comp["_priority_class"],
                "priority_overridden": overridden,
                "scope_tag": str(row.get("scope_tag") or ""),
            }

    # ------------------------------------------------- stage 2, source revisions

    def load_source_revisions(self) -> dict[str, str]:
        rows = []
        for row in read_jsonl(self.d / "source_revisions.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            cid = self.identifier(row.get("component_id"), CID_RE,
                                   "source revisions", "component_id")
            if cid is None:
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "source revision row %s names a component absent from the register"
                    % (row.get("row_id") or ""),
                )
                continue
            rows.append(row)
        return {
            cid: str(row.get("source_revision") or "")
            for cid, row in group_winners(rows, lambda r: str(r["component_id"]).strip()).items()
        }

    def load_ledger(self) -> dict[str, dict]:
        rows = []
        for row in read_jsonl(self.d / "previous_release_ledger.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            unit_id = str(row.get("unit_id") or "").strip()
            parts = unit_id.split(":")
            cid = parts[0] if parts else ""
            tid = parts[1] if len(parts) > 1 else ""
            if not CID_RE.match(cid) or not TID_RE.match(tid):
                self.exc(
                    "E_ID_FORM",
                    unit_id,
                    "previous release ledger row %s carries a unit id that is not in "
                    "canonical form" % (row.get("row_id") or ""),
                )
                continue
            unknown = None
            if cid not in self.components:
                unknown = cid
            elif tid not in self.targets:
                unknown = tid
            if unknown is not None:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    unknown,
                    "previous release ledger row %s names %s, which is absent from "
                    "its register" % (row.get("row_id") or "", unknown),
                )
                continue
            rows.append(row)
        return group_winners(rows, lambda r: str(r.get("unit_id") or "").strip())

    # --------------------------------------------- stage 2, toolchain resolution

    def load_toolchains(self) -> None:
        spec = read_json(self.d / "toolchains.json")
        self.chains = {
            str(c.get("toolchain_id") or "").strip(): c
            for c in spec.get("chains", [])
            if str(c.get("status") or "").strip() == "active"
        }
        defaults: dict[str, list[dict]] = {}
        for row in spec.get("kind_defaults", []):
            if str(row.get("status") or "").strip() != "active":
                continue
            if row.get("is_default") is not True:
                continue
            kind = str(row.get("kind") or "").strip()
            chain = str(row.get("toolchain_id") or "").strip()
            if chain not in self.chains:
                continue
            defaults.setdefault(kind, []).append(row)
        self.kind_default = {kind: max(rows, key=lambda r: str(r["toolchain_id"]))
                             for kind, rows in defaults.items()}
        self.profiles = group_winners(
            read_json(self.d / "compiler_profiles.json").get("profiles", []),
            lambda r: (str(r.get("target_id") or "").strip(),
                       str(r.get("kind") or "").strip(),
                       str(r.get("channel") or "").strip()),
        )
        overrides = {}
        for row in read_jsonl(self.d / "target_overrides.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            tid = self.identifier(row.get("target_id"), TID_RE,
                                   "target overrides", "target_id")
            if tid is None:
                continue
            if tid not in self.targets:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    tid,
                    "target override row %s names a target absent from the register"
                    % (row.get("row_id") or ""),
                )
                continue
            chain = str(row.get("toolchain_id") or "").strip()
            if chain and chain not in self.chains:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    chain,
                    "target override row %s names a toolchain absent from the chain "
                    "register" % (row.get("row_id") or ""),
                )
                continue
            row["_target_id"] = tid
            overrides.setdefault(
                (tid, str(row.get("applies_to") or "").strip(),
                 str(row.get("channel") or "").strip()), []
            ).append(row)
        self.chain_overrides = {
            key: pick(rows) for key, rows in overrides.items()
        }
        history = []
        for row in read_csv(self.d / "toolchain_history.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            if str(row.get("release_id") or "").strip() != self.previous_release_id:
                continue
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "toolchain history", "target_id")
            if tid is None:
                continue
            row["_target_id"] = tid
            history.append(row)
        self.toolchain_history = group_winners(
            history,
            lambda r: (r["_target_id"], str(r.get("kind") or "").strip(),
                       str(r.get("channel") or "").strip()),
        )

    def resolve_toolchain(self, unit: dict) -> tuple[str, str, str, str, bool]:
        key = (unit["target_id"], unit["kind"], unit["channel"])
        override = self.chain_overrides.get(key)
        override_applied = override is not None
        if override is not None:
            chain_id = str(override.get("toolchain_id") or "")
        else:
            default = self.kind_default.get(unit["kind"])
            chain_id = str(default.get("toolchain_id") or "") if default else ""
        chain = self.chains.get(chain_id, {})
        chain_revision = str(chain.get("revision") or "")
        profile = self.profiles.get(key, {})
        profile_id = str(profile.get("profile_id") or "")
        profile_revision = str(profile.get("revision") or "")
        revision = "%s@%s+%s@%s" % (chain_id, chain_revision, profile_id, profile_revision)
        old = self.toolchain_history.get(key)
        if old is not None:
            previous = "%s@%s+%s@%s" % (
                str(old.get("toolchain_id") or ""),
                str(old.get("toolchain_revision") or ""),
                str(old.get("profile_id") or ""),
                str(old.get("profile_revision") or ""),
            )
        else:
            previous = ""
        return revision, previous, chain_id, profile_id, override_applied

    # ---------------------------------------------- stage 2, contract revisions

    def load_contracts(self) -> None:
        def by_interface(name: str) -> dict[str, str]:
            rows = []
            for row in read_jsonl(self.d / name):
                if str(row.get("status") or "").strip() != "active":
                    continue
                ifid = self.identifier(row.get("interface_id"), IFID_RE, name,
                                       "interface_id")
                if ifid is None:
                    continue
                rows.append(row)
            return {
                ifid: str(row.get("contract_revision") or "")
                for ifid, row in group_winners(
                    rows, lambda r: str(r.get("interface_id") or "").strip()
                ).items()
            }

        self.current_contracts = by_interface("current_contracts.jsonl")
        self.previous_contracts = by_interface("previous_contracts.jsonl")

        consumers: dict[str, list[dict]] = {}
        for row in read_csv(self.d / "interface_consumers.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            ifid = self.identifier(row.get("interface_id"), IFID_RE,
                                   "interface consumers", "interface_id")
            cid = self.identifier(row.get("consumer_component"), CID_RE,
                                   "interface consumers", "consumer_component")
            if ifid is None or cid is None:
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "interface consumer row %s names a component absent from the "
                    "register" % (row.get("row_id") or ""),
                )
                continue
            row["_interface_id"] = ifid
            row["_consumer_component"] = cid
            consumers.setdefault(ifid, []).append(row)
        self.consumers_by_interface = {
            ifid: group_winners(rows, lambda r: r["_consumer_component"])
            for ifid, rows in consumers.items()
        }
        required: dict[str, set[str]] = {}
        optional: dict[str, set[str]] = {}
        for ifid, rows in self.consumers_by_interface.items():
            for cid, row in rows.items():
                target = required if str(row.get("requirement") or "").strip() == "required" else optional
                target.setdefault(cid, set()).add(ifid)
        self.required_interfaces = required
        self.optional_interfaces = optional

        owners = []
        for row in read_csv(self.d / "interface_owners.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            ifid = self.identifier(row.get("interface_id"), IFID_RE,
                                   "interface owners", "interface_id")
            if ifid is None:
                continue
            bad = None
            for field in ("owner_component", "generated_sdk_component"):
                cid = self.identifier(row.get(field), CID_RE, "interface owners", field)
                if cid is None:
                    bad = "form"
                    break
                if cid not in self.components:
                    self.exc(
                        "E_UNKNOWN_UNIT",
                        cid,
                        "interface owner row %s names a component absent from the "
                        "register" % (row.get("row_id") or ""),
                    )
                    bad = "unknown"
                    break
            if bad is not None:
                continue
            row["_interface_id"] = ifid
            owners.append(row)
        self.owners = group_winners(owners, lambda r: r["_interface_id"])

    def load_generated_outputs(self) -> None:
        rows = []
        for row in read_jsonl(self.d / "generated_outputs.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            ifid = self.identifier(row.get("interface_id"), IFID_RE,
                                   "generated outputs", "interface_id")
            cid = self.identifier(row.get("generated_sdk_component"), CID_RE,
                                  "generated outputs", "generated_sdk_component")
            if ifid is None or cid is None:
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "generated output row %s names a component absent from the "
                    "register" % (row.get("row_id") or ""),
                )
                continue
            row["_interface_id"] = ifid
            row["_generated_sdk_component"] = cid
            rows.append(row)
        self.generated_outputs = group_winners(
            rows, lambda r: (r["_interface_id"], str(r.get("artifact_kind") or "").strip())
        )
        self.producer_of: dict[str, str] = {}
        for (ifid, _kind), row in self.generated_outputs.items():
            self.producer_of[ifid] = row["_generated_sdk_component"]
        for ifid, row in self.owners.items():
            self.producer_of.setdefault(ifid, str(row.get("generated_sdk_component") or ""))

    def load_support_matrix(self) -> None:
        rows = []
        for row in read_csv(self.d / "sdk_support_matrix.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            ifid = self.identifier(row.get("interface_id"), IFID_RE,
                                   "sdk support matrix", "interface_id")
            cid = self.identifier(row.get("sdk_component"), CID_RE,
                                  "sdk support matrix", "sdk_component")
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "sdk support matrix", "target_id")
            if ifid is None or cid is None or tid is None:
                continue
            unknown = None
            if cid not in self.components:
                unknown = cid
            elif tid not in self.targets:
                unknown = tid
            if unknown is not None:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    unknown,
                    "sdk support row %s names %s, which is absent from its register"
                    % (row.get("row_id") or "", unknown),
                )
                continue
            row["_interface_id"] = ifid
            row["_sdk_component"] = cid
            row["_target_id"] = tid
            rows.append(row)
        self.support = {
            key: str(row.get("support_state") or "").strip() == "supported"
            for key, row in group_winners(
                rows,
                lambda r: (r["_interface_id"], r["_sdk_component"], r["_target_id"]),
            ).items()
        }

    def contract_digest(self, cid: str, table: dict[str, str]) -> str:
        interfaces = sorted(self.required_interfaces.get(cid, ()))
        parts = ["%s:%s" % (ifid, table.get(ifid, "")) for ifid in interfaces]
        joined = ";".join(parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]

    # ---------------------------------------------------- stage 3, build edges

    def load_edges(self) -> None:
        required: dict[str, set[str]] = {}
        optional: dict[str, set[str]] = {}
        for row in read_csv(self.d / "build_edges.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            dependent = self.identifier(row.get("dependent"), CID_RE,
                                       "build edges", "dependent")
            dependency = self.identifier(row.get("dependency"), CID_RE,
                                         "build edges", "dependency")
            if dependent is None or dependency is None:
                continue
            bad = False
            for cid in (dependent, dependency):
                if cid not in self.components:
                    self.exc(
                        "E_UNKNOWN_UNIT",
                        cid,
                        "build edge row %s names a component absent from the register"
                        % (row.get("row_id") or ""),
                    )
                    bad = True
            if bad:
                continue
            if str(row.get("requirement") or "").strip() == "required":
                required.setdefault(dependent, set()).add(dependency)
            else:
                optional.setdefault(dependent, set()).add(dependency)
        self.required_deps = required
        self.optional_deps = optional

        activation = set()
        for row in read_jsonl(self.d / "optional_dependencies.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            if row.get("activated") is not True:
                continue
            dependent = self.identifier(row.get("dependent"), CID_RE,
                                       "optional dependencies", "dependent")
            dependency = self.identifier(row.get("dependency"), CID_RE,
                                         "optional dependencies", "dependency")
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "optional dependencies", "target_id")
            if dependent is None or dependency is None or tid is None:
                continue
            bad = None
            if dependent not in self.components:
                bad = dependent
            elif dependency not in self.components:
                bad = dependency
            elif tid not in self.targets:
                bad = tid
            if bad is not None:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    bad,
                    "optional dependency row %s names %s, which is absent from its "
                    "register" % (row.get("row_id") or "", bad),
                )
                continue
            activation.add((dependent, dependency, tid))
        self.optional_active = activation

    # --------------------------------------------------------- stage 6, costs

    def load_costs(self) -> None:
        book = workbook_sheets(self.d / "capacity_workbook.xlsx")

        scaling = {}
        for row in book.get("platform_scaling", []):
            if str(row.get("status") or "").strip() != "active":
                continue
            key = (str(row.get("target_id") or "").strip(),
                   str(row.get("kind") or "").strip(),
                   str(row.get("channel") or "").strip())
            num = self.integer(row.get("multiplier_numerator"),
                               "capacity workbook platform_scaling",
                               "multiplier_numerator", "%s:%s:%s" % key)
            den = self.integer(row.get("multiplier_denominator"),
                               "capacity workbook platform_scaling",
                               "multiplier_denominator", "%s:%s:%s" % key)
            if num is None or den is None:
                continue
            if den == 0:
                self.exc(
                    "E_NON_INTEGER",
                    "%s:%s:%s" % key,
                    "capacity workbook platform_scaling row carries a zero "
                    "multiplier_denominator",
                )
                continue
            scaling.setdefault(key, []).append((num, den, row_seq(row), row_key(row)))
        self.platform = {}
        for key, rows in scaling.items():
            best = max(rows, key=lambda r: (r[2], r[3]))
            self.platform[key] = (best[0], best[1])

        rules = {}
        for row in book.get("cost_rules", []):
            if str(row.get("status") or "").strip() != "active":
                continue
            name = str(row.get("rule_name") or "").strip()
            num = self.integer(row.get("numerator"), "capacity workbook cost_rules",
                               "numerator", name)
            den = self.integer(row.get("denominator"), "capacity workbook cost_rules",
                               "denominator", name)
            if num is None or den is None:
                continue
            if den == 0:
                self.exc(
                    "E_NON_INTEGER",
                    name,
                    "capacity workbook cost_rules row %s carries a zero denominator"
                    % name,
                )
                continue
            rules.setdefault(name, []).append((num, den, row_seq(row), row_key(row)))
        self.cost_rules = {
            name: max(rows, key=lambda r: (r[2], r[3]))[:2] for name, rows in rules.items()
        }

        kinds = group_winners(
            read_json(self.d / "kind_cost_profiles.json").get("profiles", []),
            lambda r: (str(r.get("kind") or "").strip(),
                       str(r.get("channel") or "").strip(),
                       str(r.get("target_id") or "").strip()),
        )
        self.kind_profiles = {
            key: (row.get("regeneration_surcharge_applies") is True,
                  row.get("cold_cache_multiplier_applies") is True)
            for key, row in kinds.items()
        }

        minimums = []
        for row in read_jsonl(self.d / "build_cost_rules.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "build cost rules", "target_id")
            if tid is None:
                continue
            minimum = self.integer(row.get("minimum_cost_ticks"), "build cost rules",
                                   "minimum_cost_ticks", str(row.get("kind") or ""))
            if minimum is None:
                continue
            row["_target_id"] = tid
            minimums.append(row)
        self.minimum_cost = {
            key: value
            for key, row in group_winners(
                minimums,
                lambda r: (str(r.get("kind") or "").strip(),
                           str(r.get("channel") or "").strip(),
                           r["_target_id"]),
            ).items()
            for value in [row.get("minimum_cost_ticks")]
        }

    def unit_cost(self, unit: dict, reasons: set[str]) -> dict | None:
        key = (unit["target_id"], unit["kind"], unit["channel"])
        num, den = self.platform.get(key, (1, 1))
        base = unit["base_cost_ticks"]
        after_platform = ceildiv(base * num, den)
        profile = self.kind_profiles.get(key, (False, False))
        regeneration = profile[0] and ("contract_changed" in reasons
                                      or "generated_interface_rebuilt" in reasons)
        after_regeneration = after_platform
        if regeneration:
            rnum, rden = self.cost_rules.get("regeneration_surcharge", (1, 1))
            after_regeneration = ceildiv(after_platform * rnum, rden)
        cold = profile[1] and "absent_from_previous_release" in reasons
        after_cold = after_regeneration
        if cold:
            knum, kden = self.cost_rules.get("cold_cache_multiplier", (1, 1))
            after_cold = ceildiv(after_regeneration * knum, kden)
        minimum = self.minimum_cost.get((unit["kind"], unit["channel"], unit["target_id"]), 0)
        cost = after_cold if base == 0 else max(after_cold, minimum)
        return {
            "base_cost_ticks": base,
            "after_platform": after_platform,
            "after_regeneration": after_regeneration,
            "after_cold_cache": after_cold,
            "cost_ticks": cost,
            "minimum_cost_ticks": minimum,
            "platform_numerator": num,
            "platform_denominator": den,
            "regeneration_applied": regeneration,
            "cold_cache_applied": cold,
        }

    # -------------------------------------------------------- stage 7, capacity

    def load_pools(self) -> None:
        book = workbook_sheets(self.d / "capacity_workbook.xlsx")
        budgets: dict[str, list] = {}
        for index, row in enumerate(book.get("pool_budgets", []), start=1):
            if str(row.get("status") or "").strip() != "active":
                continue
            pool_id = str(row.get("pool_id") or "").strip()
            value = self.integer(row.get("budget_value"),
                                 "capacity workbook pool_budgets",
                                 "budget_value", pool_id)
            if value is None:
                continue
            if pool_id not in self.pools:
                self.exc(
                    "E_UNKNOWN_POOL",
                    pool_id,
                    "capacity workbook pool_budgets row %d names a pool absent "
                    "from the pool register" % index,
                )
                continue
            scale = str(row.get("scale_unit") or "").strip()
            ticks = ceildiv(value, 1000) if scale == "milli_tick" else value
            budgets.setdefault(pool_id, []).append((ticks, row_seq(row), row_key(row)))
        self.gross_budget = {
            pool: max(rows, key=lambda r: (r[1], r[2]))[0]
            for pool, rows in budgets.items()
        }

        reservations: dict[str, int] = {}
        for row in read_jsonl(self.d / "maintenance_windows.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            pool_id = str(row.get("pool_id") or "").strip()
            if pool_id not in self.pools:
                self.exc(
                    "E_UNKNOWN_POOL",
                    pool_id,
                    "maintenance window %s names a pool absent from the pool register"
                    % (row.get("window_id") or ""),
                )
                continue
            amount = 0
            for field in ("reserved_ticks", "reserved_millis"):
                if field in row and row[field] is not None:
                    value = self.integer(row[field], "maintenance windows", field, pool_id)
                    if value is None:
                        amount = None
                        break
                    amount = ceildiv(value, 1000) if field.endswith("_millis") else value
                    break
            if amount is None:
                continue
            reservations[pool_id] = reservations.get(pool_id, 0) + amount
        self.reserved_ticks = reservations

        lanes: dict[str, int] = {}
        for row in read_csv(self.d / "worker_pool_notes.csv"):
            if str(row.get("status") or "").strip() != "active":
                continue
            pool_id = str(row.get("pool_id") or "").strip()
            if pool_id not in self.pools:
                self.exc(
                    "E_UNKNOWN_POOL",
                    pool_id,
                    "worker pool lane %s names a pool absent from the pool register"
                    % (row.get("lane_id") or ""),
                )
                continue
            if str(row.get("lane_state") or "").strip() == "operational":
                lanes[pool_id] = lanes.get(pool_id, 0) + 1
        self.operational_lanes = lanes

    def load_publication_policy(self) -> None:
        policy = read_json(self.d / "publication_policy.json")
        prohibited: dict[str, str] = {}
        for row in policy.get("prohibitions", []):
            if str(row.get("status") or "").strip() != "active":
                continue
            cid = self.identifier(row.get("component_id"), CID_RE,
                                  "publication policy", "component_id")
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "publication policy", "target_id")
            if cid is None or tid is None:
                continue
            unit_id = cid + ":" + tid
            if unit_id in self.units:
                prohibited.setdefault(unit_id, "E_PROHIBITED")
        held = set()
        for row in policy.get("reviews", []):
            if str(row.get("status") or "").strip() != "active":
                continue
            cid = self.identifier(row.get("component_id"), CID_RE,
                                  "publication policy", "component_id")
            if cid is None:
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "publication review row names a component absent from the register",
                )
                continue
            if str(row.get("publication_review") or "").strip() == "held":
                held.add(cid)
        frozen = toml_channels(self.d / "release_channels.toml")
        self.frozen_channels = {name for name, flag in frozen.items() if flag}
        self.prohibited = prohibited
        self.held_components = held

    def prohibition_codes(self, unit: dict) -> list[str]:
        codes = []
        unit_id = unit["unit_id"]
        if unit_id in self.prohibited:
            codes.append("E_PROHIBITED")
        if unit["component_id"] in self.held_components:
            codes.append("E_REVIEW_HELD")
        if unit["channel"] in self.frozen_channels:
            codes.append("E_CHANNEL_FROZEN")
        return codes

    # ------------------------------------------------------------ stage 8/9/14

    def load_cycles(self) -> None:
        spec = read_json(self.d / "cycle_groups.json")
        groups = []
        for row in spec.get("groups", []):
            if str(row.get("status") or "").strip() != "active":
                continue
            members = []
            for cid in sorted(str(m) for m in row.get("members", [])):
                if not CID_RE.match(cid):
                    self.exc(
                        "E_ID_FORM",
                        cid,
                        "cycle group %s names a component that is not in canonical form"
                        % (row.get("group_id") or ""),
                    )
                    continue
                if cid not in self.components:
                    self.exc(
                        "E_UNKNOWN_UNIT",
                        cid,
                        "cycle group %s names a component absent from the register"
                        % (row.get("group_id") or ""),
                    )
                    continue
                members.append(cid)
            if not members:
                continue
            row["_members"] = members
            groups.append(row)
        applicability = group_winners(
            spec.get("applicability", []),
            lambda r: (str(r.get("group_id") or "").strip(),
                       str(r.get("target_id") or "").strip()),
        )
        self.cycle_groups = groups
        self.cycle_scope = {
            key: row.get("in_scope") is True for key, row in applicability.items()
        }

    def load_ordering(self) -> None:
        migrations = []
        for row in read_jsonl(self.d / "deployment_constraints.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            if str(row.get("constraint") or "").strip() != "migration_first":
                continue
            migration = self.identifier(row.get("migration_component"), CID_RE,
                                        "deployment constraints", "migration_component")
            blocked = self.identifier(row.get("blocks_component"), CID_RE,
                                      "deployment constraints", "blocks_component")
            tid = self.identifier(row.get("target_id"), TID_RE,
                                  "deployment constraints", "target_id")
            if migration is None or blocked is None or tid is None:
                continue
            bad = None
            if migration not in self.components:
                bad = migration
            elif blocked not in self.components:
                bad = blocked
            elif tid not in self.targets:
                bad = tid
            if bad is not None:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    bad,
                    "deployment constraint row %s names %s, which is absent from its "
                    "register" % (row.get("row_id") or "", bad),
                )
                continue
            migrations.append((migration, blocked, tid))
        self.migrations = migrations

        ordering = []
        for row in read_jsonl(self.d / "ordering_overrides.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            ordering.append((row_key(row),
                             str(row.get("before_unit") or ""),
                             str(row.get("after_unit") or "")))
        self.ordering_overrides = sorted(ordering)

    # ------------------------------------------------- stage 10, version choice

    def load_versions(self) -> None:
        precedence = read_json(self.d / "version_precedence.json")
        clusters = []
        for row in precedence.get("clusters", []):
            members = []
            for cid in sorted(str(m) for m in row.get("members", [])):
                if not CID_RE.match(cid):
                    self.exc(
                        "E_ID_FORM",
                        cid,
                        "version precedence cluster %s names a component that is not "
                        "in canonical form" % (row.get("cluster_id") or ""),
                    )
                    continue
                if cid not in self.components:
                    self.exc(
                        "E_UNKNOWN_UNIT",
                        cid,
                        "version precedence cluster %s names a component absent from "
                        "the register" % (row.get("cluster_id") or ""),
                    )
                    continue
                members.append(cid)
            if not members:
                continue
            clusters.append({"cluster_id": str(row.get("cluster_id") or ""),
                             "members": members})
        self.clusters = clusters

        # addendum B window table
        windows: dict[str, dict] = {}
        rows = []
        for cells in docx_rows(self.d / "compatibility_window_notes.docx"):
            if len(cells) != 5:
                continue
            if cells[0].strip() == "component_id":
                continue
            cid = self.identifier(cells[0], CID_RE, "addendum B window table",
                                   "component_id")
            if cid is None:
                continue
            rows.append({
                "component_id": cid,
                "version": cells[1].strip(),
                "window_state": cells[2].strip(),
                "status": cells[3].strip(),
                "revision_seq": cells[4].strip(),
                "row_id": "line-%d" % len(rows),
            })
        for idx, row in enumerate(rows):
            if row["status"] != "active":
                continue
            cid = row["component_id"]
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "addendum B window row %d names a component absent from the "
                    "register" % (idx + 1),
                )
                continue
            key = (cid, row["version"])
            previous = windows.get(key)
            if previous is None or (row_seq(row), row_key(row)) > previous[0]:
                windows[key] = ((row_seq(row), row_key(row)), row["window_state"])
        self.windows = {key: value for key, (seq, value) in windows.items()}

        versions: dict[str, dict[str, dict]] = {}
        vrows = []
        for row in read_jsonl(self.d / "component_versions.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            cid = self.identifier(row.get("component_id"), CID_RE,
                                  "component versions", "component_id")
            if cid is None:
                continue
            if cid not in self.components:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    cid,
                    "component version row %s names a component absent from the "
                    "register" % (row.get("row_id") or ""),
                )
                continue
            preference = self.integer(row.get("local_preference"), "component versions",
                                       "local_preference", cid)
            if preference is None:
                continue
            row["_component_id"] = cid
            vrows.append(row)
        for (cid, version), row in group_winners(
            vrows, lambda r: (r["_component_id"], str(r.get("version") or "").strip())
        ).items():
            if self.windows.get((cid, version)) == "supported":
                versions.setdefault(cid, {})[version] = {
                    "version": version,
                    "local_preference": row["local_preference"],
                    "api_revision": str(row.get("api_revision") or ""),
                }
        self.versions = versions

        compatibility: dict[tuple, dict[tuple, list]] = {}
        for row in read_jsonl(self.d / "api_compatibility.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            left = self.identifier(row.get("left_component"), CID_RE,
                                    "api compatibility", "left_component")
            right = self.identifier(row.get("right_component"), CID_RE,
                                    "api compatibility", "right_component")
            if left is None or right is None:
                continue
            bad = None
            if left not in self.components:
                bad = left
            elif right not in self.components:
                bad = right
            if bad is not None:
                self.exc(
                    "E_UNKNOWN_UNIT",
                    bad,
                    "api compatibility row %s names a component absent from the "
                    "register" % (row.get("row_id") or ""),
                )
                continue
            cluster = str(row.get("cluster_id") or "").strip()
            left_version = str(row.get("left_version") or "").strip()
            right_version = str(row.get("right_version") or "").strip()
            # both orientations are indexed, so a pair is found whatever order
            # the row names its components in.
            for key, versions in (
                ((cluster, left, right), (left_version, right_version)),
                ((cluster, right, left), (right_version, left_version)),
            ):
                group = compatibility.setdefault(key, {}).setdefault(versions, [])
                group.append((row_seq(row), row_key(row), row.get("compatible") is True))
        self.compatibility: dict[tuple, dict[tuple, bool]] = {}
        for key, table in compatibility.items():
            self.compatibility[key] = {
                versions: max(rows, key=lambda r: (r[0], r[1]))[2]
                for versions, rows in table.items()
            }

    def pair_compatible(self, cluster: str, left: str, left_version: str,
                        right: str, right_version: str) -> tuple[bool, str]:
        """Addendum B: a pair with no active compatible row is incompatible."""
        if left > right:
            left, right = right, left
            left_version, right_version = right_version, left_version
        table = self.compatibility.get((cluster, left, right))
        if not table or (left_version, right_version) not in table:
            return False, "no_active_compatibility_row"
        if table[(left_version, right_version)] is True:
            return True, ""
        return False, "compatibility_row_false"

    # ================================================================ pipeline

    def run(self, out_dir: Path) -> None:
        self.load_registers()
        self.load_inventory()
        source = self.load_source_revisions()
        ledger = self.load_ledger()
        self.load_toolchains()
        self.load_contracts()
        self.load_generated_outputs()
        self.load_support_matrix()
        self.load_edges()
        self.load_costs()
        self.load_pools()
        self.load_publication_policy()
        self.load_cycles()
        self.load_ordering()
        self.load_versions()

        # ---- stage 2 and 3, revisions and direct invalidation
        previous_units = set(ledger)
        artifact_index: dict[str, list[dict]] = {}
        index_rows = []
        for row in read_jsonl(self.d / "published_artifact_index.jsonl"):
            if str(row.get("status") or "").strip() != "active":
                continue
            digest = str(row.get("artifact_digest") or "").strip()
            if not digest:
                continue
            index_rows.append(row)
        for row in index_rows:
            artifact_index.setdefault(str(row.get("artifact_digest") or ""), []).append(row)
        retained = {}
        for digest, rows in artifact_index.items():
            best = pick(rows)
            retained[digest] = best.get("retained") is True

        contract_of = {}
        previous_contract_of = {}
        for unit_id, unit in self.units.items():
            cid = unit["component_id"]
            if cid not in contract_of:
                contract_of[cid] = self.contract_digest(cid, self.current_contracts)
                previous_contract_of[cid] = self.contract_digest(
                    cid, self.previous_contracts)
            unit["contract_revision"] = contract_of[cid]
            unit["previous_contract_revision"] = previous_contract_of[cid]
            revision, previous, chain_id, profile_id, override_applied = (
                self.resolve_toolchain(unit))
            unit["toolchain_revision"] = revision
            unit["previous_toolchain_revision"] = previous
            unit["toolchain_id"] = chain_id
            unit["profile_id"] = profile_id
            unit["override_applied"] = override_applied
            unit["source_revision"] = source.get(cid, "")
            row = ledger.get(unit_id)
            unit["in_previous_release"] = row is not None
            unit["ledger"] = row
            unit["previous_source_revision"] = (
                str(row.get("source_revision") or "") if row else "")
            if row is not None:
                unit["artifact_digest"] = str(row.get("artifact_digest") or "")

        direct: dict[str, set[str]] = {}
        for unit_id, unit in sorted(self.units.items()):
            reasons: set[str] = set()
            row = unit.get("ledger")
            if row is None:
                reasons.add("absent_from_previous_release")
            else:
                if unit["source_revision"] != unit["previous_source_revision"]:
                    reasons.add("source_changed")
                if unit["toolchain_revision"] != unit["previous_toolchain_revision"]:
                    reasons.add("toolchain_changed")
                if unit["contract_revision"] != unit["previous_contract_revision"]:
                    reasons.add("contract_changed")
                digest = str(row.get("artifact_digest") or "")
                if not retained.get(digest, False):
                    reasons.add("published_artifact_missing")
                    self.exc(
                        "E_ARTIFACT_MISSING",
                        unit_id,
                        "the previous artifact %s of this unit is absent from the "
                        "published artifact index or is not retained" % digest,
                    )
            direct[unit_id] = reasons

        # ---- stage 3 and 4, propagation to a fixed point
        changed_interfaces = {
            ifid for ifid, revision in self.current_contracts.items()
            if self.previous_contracts.get(ifid) != revision
        }
        reasons = {unit_id: set(value) for unit_id, value in direct.items()}
        unit_at: dict[tuple[str, str], str] = {
            (unit["component_id"], unit["target_id"]): unit_id
            for unit_id, unit in self.units.items()
        }

        def producers_of(cid: str) -> list[str]:
            out = []
            for table in (self.required_interfaces, self.optional_interfaces):
                for ifid in table.get(cid, ()):  # noqa: B023
                    if ifid in changed_interfaces:
                        out.append(ifid)
            return sorted(set(out))

        while True:
            grew = False
            for unit_id in sorted(self.units):
                unit = self.units[unit_id]
                cid = unit["component_id"]
                tid = unit["target_id"]
                before = len(reasons[unit_id])
                for dependency in self.required_deps.get(cid, ()):
                    other = unit_at.get((dependency, tid))
                    if other is not None and reasons[other]:
                        reasons[unit_id].add("dependency_rebuilt")
                for dependency in self.optional_deps.get(cid, ()):
                    if (cid, dependency, tid) not in self.optional_active:
                        continue
                    other = unit_at.get((dependency, tid))
                    if other is not None and reasons[other]:
                        reasons[unit_id].add("dependency_rebuilt")
                for ifid in producers_of(cid):
                    producer = self.producer_of.get(ifid)
                    if producer is None:
                        continue
                    other = unit_at.get((producer, tid))
                    if other is not None:
                        reasons[unit_id].add("generated_interface_rebuilt")
                if len(reasons[unit_id]) > before:
                    grew = True
            if not grew:
                break

        for unit_id, unit in self.units.items():
            unit["reasons"] = reasons[unit_id]
            unit["direct_reasons"] = set(direct[unit_id])
            unit["dirty"] = bool(reasons[unit_id])

        # ---- stage 5, generated outputs
        plan = []
        for (ifid, kind), row in sorted(self.generated_outputs.items()):
            producer_component = row["_generated_sdk_component"]
            regenerate_on_change = row.get("regenerate_on_contract_change") is True
            contract = self.current_contracts.get(ifid, "")
            previous_contract = self.previous_contracts.get(ifid, "")
            changed = ifid in changed_interfaces
            for tid in sorted(self.targets):
                producer_unit = unit_at.get((producer_component, tid))
                if producer_unit is None:
                    continue
                supported = self.support.get((ifid, producer_component, tid), False)
                regenerate = bool(regenerate_on_change and changed and supported)
                if regenerate_on_change and changed and not supported:
                    self.exc(
                        "E_SDK_UNSUPPORTED",
                        "%s@%s" % (ifid, producer_unit),
                        "the support matrix refuses the regeneration of the %s "
                        "output of %s on %s" % (kind, ifid, tid),
                    )
                plan.append({
                    "interface_id": ifid,
                    "artifact_kind": kind,
                    "target_id": tid,
                    "producer_unit": producer_unit,
                    "contract_revision": contract,
                    "previous_contract_revision": previous_contract,
                    "regenerate": regenerate,
                    "supported": supported,
                })
        self.generated_plan = plan

        # ---- stage 6, cost of every dirty unit
        costs: dict[str, dict] = {}
        for unit_id, unit in sorted(self.units.items()):
            if not unit["dirty"]:
                continue
            costs[unit_id] = self.unit_cost(unit, unit["reasons"])
        self.costs = costs

        # ---- stage 7, closures, budgets and admission
        closure_edges: dict[str, set[str]] = {}
        for unit_id, unit in self.units.items():
            if not unit["dirty"]:
                continue
            cid = unit["component_id"]
            tid = unit["target_id"]
            edges: set[str] = set()
            for dependency in self.required_deps.get(cid, ()):
                other = unit_at.get((dependency, tid))
                if other is not None and self.units[other]["dirty"]:
                    edges.add(other)
            for ifid in producers_of(cid):
                producer = self.producer_of.get(ifid)
                if producer is None:
                    continue
                other = unit_at.get((producer, tid))
                if other is not None and self.units[other]["dirty"]:
                    edges.add(other)
            closure_edges[unit_id] = edges

        def closure(unit_id: str) -> set[str]:
            """Every dirty unit reachable from the candidate on its own target."""
            seen = {unit_id}
            stack = [unit_id]
            while stack:
                node = stack.pop()
                for other in sorted(closure_edges.get(node, ())):
                    if other not in seen:
                        seen.add(other)
                        stack.append(other)
            return seen

        self.closure = closure

        prohibited_units = {
            unit_id for unit_id, unit in self.units.items() if self.prohibition_codes(unit)
        }
        for unit_id in sorted(prohibited_units):
            for code in self.prohibition_codes(self.units[unit_id]):
                self.exc(
                    code,
                    unit_id,
                    "publication of this unit is prohibited by %s" % code,
                )

        net_budget: dict[str, int] = {}
        for pool in sorted(self.pools):
            gross = self.gross_budget.get(pool, 0)
            reserved = self.reserved_ticks.get(pool, 0)
            net_budget[pool] = max(0, gross - reserved)
        remaining = dict(net_budget)

        selected: dict[str, str] = {}
        deferred: dict[str, str] = {}
        admitted_with: dict[str, list[str]] = {}
        capacity_deferred: dict[str, str] = {}

        candidates = {
            unit_id for unit_id in sorted(self.units)
            if self.units[unit_id]["dirty"] and unit_id not in prohibited_units
        }
        for pool in sorted(self.pools):
            pending = {
                unit_id for unit_id in candidates
                if self.units[unit_id]["pool_id"] == pool
                and unit_id not in selected
            }
            while pending:
                best = None
                for unit_id in sorted(pending):
                    group = closure(unit_id)
                    price = sum(
                        costs[member]["cost_ticks"]
                        for member in group
                        if member not in selected
                    )
                    key = (self.units[unit_id]["priority_class"], price, unit_id)
                    if best is None or key < best[0]:
                        best = (key, unit_id, group, price)
                assert best is not None
                _, unit_id, group, _price = best
                pending.discard(unit_id)
                if unit_id in selected:
                    continue
                draws: dict[str, int] = {}
                for member in group:
                    if member in selected:
                        continue
                    member_pool = self.units[member]["pool_id"]
                    draws[member_pool] = (
                        draws.get(member_pool, 0)
                        + costs[member]["cost_ticks"]
                    )
                fits = all(
                    amount <= remaining.get(pool_id, 0) for pool_id, amount in draws.items()
                )
                if not fits:
                    deferred[unit_id] = "E_CAPACITY"
                    capacity_deferred[unit_id] = (
                        "the prerequisite closure of this unit does not fit the "
                        "remaining net budget of its pool")
                    continue
                admitted = sorted(
                    member for member in group if member not in selected
                )
                for member in admitted:
                    selected[member] = "admitted"
                    deferred.pop(member, None)
                    capacity_deferred.pop(member, None)
                    remaining[self.units[member]["pool_id"]] = (
                        remaining.get(self.units[member]["pool_id"], 0)
                        - costs[member]["cost_ticks"]
                    )
                for member in admitted:
                    admitted_with[member] = sorted(
                        other for other in admitted if other != member
                    )

        # ---- stage 8, cycles
        removed_edges: set[tuple[str, str]] = set()
        blocked: dict[str, str] = {}
        blocked_targets: set[str] = set()
        cycle_records = []
        for tid in sorted(self.targets):
            graph: dict[str, set[str]] = {}
            for unit_id in selected:
                if self.units[unit_id]["target_id"] != tid:
                    continue
                graph.setdefault(unit_id, set())
            for unit_id in graph:
                cid = self.units[unit_id]["component_id"]
                for dependency in self.required_deps.get(cid, ()):
                    other = unit_at.get((dependency, tid))
                    if other in graph and other != unit_id:
                        graph[unit_id].add(other)
                        graph.setdefault(other, set())
            for cycle in elementary_cycles(graph):
                member_set = {self.units[u]["component_id"] for u in cycle}
                group = None
                for candidate in self.cycle_groups:
                    if candidate["_members"] == sorted(member_set):
                        if self.cycle_scope.get(
                            (candidate.get("group_id"), tid), False
                        ):
                            group = candidate
                            break
                edges = []
                for index in range(len(cycle)):
                    dependent = cycle[index]
                    dependency = cycle[(index + 1) % len(cycle)]
                    # the cycle path runs along prerequisite links, so the edge of
                    # the schedule runs from the dependency to the dependent.
                    edges.append((dependency, dependent))
                units_blocked = []
                policy = ""
                group_id = ""
                break_cost = 0
                edge_removed = ""
                removable = []
                if group is not None:
                    group_id = str(group.get("group_id") or "")
                    policy = str(group.get("policy") or "")
                    costs_table = group.get("break_costs", {}) or {}
                    for dependency, dependent in edges:
                        key = "%s->%s" % (self.units[dependency]["component_id"],
                                          self.units[dependent]["component_id"])
                        value = costs_table.get(key)
                        if value is None:
                            continue
                        ok, amount = parse_int(value)
                        if not ok:
                            continue
                        removable.append((amount, dependency, dependent))
                if group is not None and policy == "breakable" and removable:
                    amount, dependency, dependent = min(removable)
                    break_cost = amount
                    edge_removed = "%s->%s" % (
                        self.units[dependency]["component_id"],
                        self.units[dependent]["component_id"])
                    removed_edges.add((dependency, dependent))
                else:
                    for unit_id in sorted(cycle):
                        if unit_id not in blocked:
                            blocked[unit_id] = "E_CYCLE_BLOCKING"
                            self.exc(
                                "E_CYCLE_BLOCKING",
                                unit_id,
                                "cycle policy blocks this unit on target %s" % tid,
                            )
                        units_blocked.append(unit_id)
                    blocked_targets.add(tid)
                    policy = policy or "blocking"
                cycle_records.append({
                    "target_id": tid,
                    "group_id": group_id,
                    "policy": policy,
                    "members": sorted(member_set),
                    "edge_removed": edge_removed,
                    "break_cost": break_cost,
                    "units_blocked": units_blocked,
                })

        # ---- stage 8 and addendum A section A5, demotion to a fixed point
        for unit_id in blocked:
            selected.pop(unit_id, None)
        while True:
            victims = []
            for unit_id in sorted(selected):
                for member in closure(unit_id):
                    if member not in selected:
                        victims.append(unit_id)
                        break
            for unit_id in victims:
                selected.pop(unit_id, None)
                deferred[unit_id] = "E_PREREQ_DEFERRED"
                capacity_deferred.pop(unit_id, None)
                self.exc(
                    "E_PREREQ_DEFERRED",
                    unit_id,
                    "a prerequisite of this unit was not selected, so the unit is "
                    "demoted to deferred",
                )
            if not victims:
                break
        for unit_id in sorted(capacity_deferred):
            self.exc("E_CAPACITY", unit_id, capacity_deferred[unit_id])

        # ---- membership states
        states: dict[str, str] = {}
        reason_codes: dict[str, str] = {}
        for unit_id, unit in sorted(self.units.items()):
            if unit_id in blocked:
                state = "blocked"
                code = "E_CYCLE_BLOCKING"
            elif unit_id in deferred:
                state = "deferred"
                code = deferred[unit_id]
            elif unit_id in selected:
                codes = self.prohibition_codes(unit)
                state = "built_not_published" if codes else "included"
                code = codes[0] if codes else ""
            elif unit["dirty"]:
                state = "excluded"
                code = (self.prohibition_codes(unit) or [""])[0]
            else:
                state = "reused"
                code = ""
            states[unit_id] = state
            reason_codes[unit_id] = code

        # ---- stage 9, the schedule
        schedule_edges: dict[str, set[str]] = {unit_id: set() for unit_id in selected}
        reverse_edges: dict[str, set[str]] = {unit_id: set() for unit_id in selected}
        for unit_id in selected:
            tid = self.units[unit_id]["target_id"]
            cid = self.units[unit_id]["component_id"]
            for dependency in self.required_deps.get(cid, ()):
                other = unit_at.get((dependency, tid))
                if other in selected and other != unit_id:
                    if (other, unit_id) in removed_edges:
                        continue
                    schedule_edges[unit_id].add(other)
                    reverse_edges[other].add(unit_id)

        def reachable(start: str) -> set[str]:
            seen = {start}
            stack = [start]
            while stack:
                node = stack.pop()
                for nxt in reverse_edges.get(node, ()):  # successors
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            return seen

        # reverse_edges maps a unit to its dependents, which is the forward
        # direction of the schedule, so reachability along it closes a cycle.
        migration_records = []
        for migration, blocked_component, tid in sorted(self.migrations):
            migration_unit = unit_at.get((migration, tid))
            blocked_unit = unit_at.get((blocked_component, tid))
            if migration_unit not in selected or blocked_unit not in selected:
                continue
            if blocked_unit in reachable(migration_unit):
                self.exc(
                    "E_ORDER_IGNORED",
                    "%s->%s" % (migration_unit, blocked_unit),
                    "the migration_first edge from %s to %s would close a cycle and "
                    "was dropped" % (migration_unit, blocked_unit),
                )
            else:
                schedule_edges[blocked_unit].add(migration_unit)
                reverse_edges[migration_unit].add(blocked_unit)
            migration_records.append((migration_unit, blocked_unit, tid))

        for _row_id, before, after in self.ordering_overrides:
            if before not in selected or after not in selected:
                continue
            if after in reachable(before):
                self.exc(
                    "E_ORDER_IGNORED",
                    "%s->%s" % (before, after),
                    "the ordering override edge from %s to %s would close a cycle and "
                    "was dropped" % (before, after),
                )
            else:
                schedule_edges[after].add(before)
                reverse_edges[before].add(after)

        indegree = {unit_id: len(schedule_edges[unit_id]) for unit_id in selected}
        ready = sorted(
            (unit_id for unit_id in selected if indegree[unit_id] == 0),
            key=lambda u: (self.units[u]["priority_class"], u),
        )
        sequence: dict[str, int] = {}
        order = []
        while ready:
            ready.sort(key=lambda u: (self.units[u]["priority_class"], u))
            unit_id = ready.pop(0)
            sequence[unit_id] = len(order) + 1
            order.append(unit_id)
            for dependent in sorted(reverse_edges.get(unit_id, ())):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)

        # ---- stage 10 and 11, versions
        selected_components = sorted({
            self.units[unit_id]["component_id"] for unit_id in selected
        })
        selected_versions: dict[str, dict] = {}
        matrix_records = []
        rejected_records = []
        version_records = []
        unresolved = []
        withdrawn = sorted(
            cid for cid in selected_components if not self.versions.get(cid)
        )
        for cid in withdrawn:
            self.exc(
                "E_WITHDRAWN_VERSION",
                cid,
                "no supported version of this component is a candidate for release "
                "selection",
            )
        for cluster in self.clusters:
            members = [cid for cid in cluster["members"] if cid in selected_components]
            if not members:
                continue
            candidates = []
            for cid in members:
                versions = sorted(self.versions.get(cid, {}))
                candidates.append(versions if versions else [""])
            best = None
            combos = []
            for combo in iproduct(*candidates):
                total = 0
                valid = True
                for cid, version in zip(members, combo):
                    if not version:
                        valid = False
                        continue
                    total += self.versions[cid][version]["local_preference"]
                if not valid:
                    continue
                compatible = True
                reasons_text = []
                for i in range(len(members)):
                    for j in range(i + 1, len(members)):
                        ok_pair, why = self.pair_compatible(
                            cluster["cluster_id"], members[i], combo[i],
                            members[j], combo[j])
                        if not ok_pair:
                            compatible = False
                            reasons_text.append(why)
                combos.append((tuple(combo), total, compatible, reasons_text))
            for combo, total, compatible, reasons_text in combos:
                if not compatible:
                    continue
                key = (total, combo)
                if best is None or key < best[0]:
                    best = (key, combo, total)
            if best is None:
                unresolved.append(cluster["cluster_id"])
                self.exc(
                    "E_CLUSTER_UNRESOLVED",
                    cluster["cluster_id"],
                    "no compatible combination of supported versions exists for this "
                    "cluster",
                )
                for combo, total, compatible, reasons_text in combos:
                    rejected_records.append({
                        "cluster_id": cluster["cluster_id"],
                        "members": list(members),
                        "versions": list(combo),
                        "preference_sum": total,
                        "reason": reasons_text[0] if reasons_text else "incompatible",
                    })
                continue
            chosen, total = best[1], best[2]
            for cid, version in zip(members, chosen):
                record = {
                    "cluster_id": cluster["cluster_id"],
                    "version": version,
                    "local_preference": self.versions[cid][version]["local_preference"],
                    "api_revision": self.versions[cid][version]["api_revision"],
                    "preference_sum": total,
                }
                version_records.append(dict(record, component_id=cid))
                previous = selected_versions.get(cid)
                if previous is None or record["cluster_id"] < previous["cluster_id"]:
                    selected_versions[cid] = record
            for combo, sum_total, compatible, reasons_text in combos:
                if not compatible and sum_total < total:
                    rejected_records.append({
                        "cluster_id": cluster["cluster_id"],
                        "members": list(members),
                        "versions": list(combo),
                        "preference_sum": sum_total,
                        "reason": reasons_text[0] if reasons_text else "incompatible",
                    })
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    matrix_records.append({
                        "cluster_id": cluster["cluster_id"],
                        "left_component": members[i],
                        "left_version": chosen[i],
                        "right_component": members[j],
                        "right_version": chosen[j],
                        "compatible": True,
                    })

        # ---- outputs
        out = out_dir
        out.mkdir(parents=True, exist_ok=True)

        def dump_jsonl(name: str, records: list[dict]) -> None:
            with (out / name).open("w", encoding="utf-8", newline="\n") as fh:
                for record in records:
                    fh.write(json.dumps(record, sort_keys=True,
                                        separators=(",", ":")) + "\n")

        def dump_json(name: str, obj) -> None:
            with (out / name).open("w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")

        # normalized inventory
        dump_jsonl("normalized_inventory.jsonl", [
            {
                "base_cost_ticks": unit["base_cost_ticks"],
                "channel": unit["channel"],
                "component_id": unit["component_id"],
                "kind": unit["kind"],
                "mandatory": unit["mandatory"],
                "pool_id": unit["pool_id"],
                "priority_class": unit["priority_class"],
                "priority_overridden": unit["priority_overridden"],
                "scope_tag": unit["scope_tag"],
                "target_id": unit["target_id"],
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items())
        ])

        # revision delta
        dump_jsonl("revision_delta.jsonl", [
            {
                "component_id": unit["component_id"],
                "in_previous_release": unit["in_previous_release"],
                "previous_source_revision": unit["previous_source_revision"],
                "source_changed": "source_changed" in unit["direct_reasons"],
                "source_revision": unit["source_revision"],
                "target_id": unit["target_id"],
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items())
        ])

        # toolchain resolution
        dump_jsonl("toolchain_resolution.jsonl", [
            {
                "override_applied": unit["override_applied"],
                "previous_toolchain_revision": unit["previous_toolchain_revision"],
                "profile_id": unit["profile_id"],
                "toolchain_id": unit["toolchain_id"],
                "toolchain_revision": unit["toolchain_revision"],
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items())
        ])

        # contract delta
        dump_jsonl("contract_delta.jsonl", [
            {
                "contract_changed": unit["contract_revision"]
                != unit["previous_contract_revision"],
                "contract_revision": unit["contract_revision"],
                "optional_interfaces": sorted(self.optional_interfaces.get(
                    unit["component_id"], ())),
                "previous_contract_revision": unit["previous_contract_revision"],
                "required_interfaces": sorted(self.required_interfaces.get(
                    unit["component_id"], ())),
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items())
        ])

        # invalidation reasons
        dump_jsonl("invalidation_reasons.jsonl", [
            {
                "dirty": unit["dirty"],
                "reason_count": len(unit["reasons"]),
                "reasons": sorted(unit["reasons"]),
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items())
        ])

        # invalidation closure
        dump_jsonl("invalidation_closure.jsonl", [
            {
                "component_id": unit["component_id"],
                "direct": sorted(unit["direct_reasons"]),
                "kind": unit["kind"],
                "reasons": sorted(unit["reasons"]),
                "target_id": unit["target_id"],
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items()) if unit["dirty"]
        ])

        # generated output plan
        dump_jsonl("generated_output_plan.jsonl", sorted(
            plan,
            key=lambda r: (r["interface_id"], r["artifact_kind"], r["target_id"]),
        ))

        # build unit ledger
        dump_jsonl("build_unit_ledger.jsonl", [
            {
                "channel": unit["channel"],
                "component_id": unit["component_id"],
                "contract_revision": unit["contract_revision"],
                "kind": unit["kind"],
                "pool_id": unit["pool_id"],
                "reasons": sorted(unit["reasons"]),
                "required_dependencies": sorted(
                    unit_at.get((dependency, unit["target_id"]))
                    for dependency in self.required_deps.get(unit["component_id"], ())
                    if unit_at.get((dependency, unit["target_id"])) is not None
                ),
                "source_revision": unit["source_revision"],
                "state": states[unit_id],
                "target_id": unit["target_id"],
                "toolchain_revision": unit["toolchain_revision"],
                "unit_id": unit_id,
            }
            for unit_id, unit in sorted(self.units.items())
        ])

        # cost breakdown
        dump_jsonl("build_cost_breakdown.jsonl", [
            dict(record, unit_id=unit_id) for unit_id, record in sorted(costs.items())
        ])

        # capacity allocation
        dump_jsonl("capacity_allocation.jsonl", [
            {
                "admitted_with": admitted_with.get(unit_id, []),
                "cost_ticks": costs[unit_id]["cost_ticks"],
                "pool_id": self.units[unit_id]["pool_id"],
                "priority_class": self.units[unit_id]["priority_class"],
                "unit_id": unit_id,
            }
            for unit_id in sorted(selected)
        ])

        # deferred units
        dump_jsonl("deferred_units.jsonl", [
            {
                "cost_ticks": costs[unit_id]["cost_ticks"] if unit_id in costs else 0,
                "pool_id": self.units[unit_id]["pool_id"],
                "priority_class": self.units[unit_id]["priority_class"],
                "reason_code": reason_codes[unit_id],
                "unit_id": unit_id,
            }
            for unit_id in sorted(deferred)
        ])

        # dependency schedule
        dump_jsonl("dependency_schedule.jsonl", [
            {
                "cost_ticks": costs[unit_id]["cost_ticks"],
                "dependencies": sorted(schedule_edges[unit_id]),
                "pool_id": self.units[unit_id]["pool_id"],
                "priority_class": self.units[unit_id]["priority_class"],
                "sequence": sequence[unit_id],
                "unit_id": unit_id,
            }
            for unit_id in order
        ])

        # cycle resolution
        dump_jsonl("cycle_resolution.jsonl", sorted(
            cycle_records,
            key=lambda r: (r["target_id"], r["group_id"], r["edge_removed"]),
        ))

        # worker pool summary
        pool_summary = {}
        for pool in sorted(self.pools):
            members = [u for u in sorted(self.units) if self.units[u]["pool_id"] == pool]
            consumed = sum(
                costs[u]["cost_ticks"] for u in members if u in selected
            )
            pool_summary[pool] = {
                "consumed_ticks": consumed,
                "deferred_units": sum(1 for u in members if states[u] == "deferred"),
                "gross_budget_ticks": self.gross_budget.get(pool, 0),
                "net_budget_ticks": net_budget[pool],
                "operational_lanes": self.operational_lanes.get(pool, 0),
                "remaining_ticks": net_budget[pool] - consumed,
                "reserved_ticks": self.reserved_ticks.get(pool, 0),
                "selected_units": sum(1 for u in members if u in selected),
            }
        dump_json("worker_pool_summary.json", {
            "pools": pool_summary,
            "release_id": self.release_id,
        })

        # compatibility matrix, rejected combinations, version selection
        dump_jsonl("compatibility_matrix.jsonl", sorted(
            matrix_records,
            key=lambda r: (r["cluster_id"], r["left_component"], r["right_component"]),
        ))
        dump_jsonl("rejected_combinations.jsonl", sorted(
            rejected_records,
            key=lambda r: (r["cluster_id"], r["preference_sum"], r["versions"]),
        ))
        dump_jsonl("version_selection.jsonl", sorted(
            version_records,
            key=lambda r: (r["component_id"], r["cluster_id"]),
        ))

        # release membership
        dump_jsonl("release_membership.jsonl", [
            {
                "pool_id": self.units[unit_id]["pool_id"],
                "reason_code": reason_codes[unit_id],
                "state": states[unit_id],
                "target_id": self.units[unit_id]["target_id"],
                "unit_id": unit_id,
            }
            for unit_id in sorted(self.units)
        ])

        # deployment manifest
        manifest_members = []
        for unit_id in sorted(self.units):
            if states[unit_id] not in ("included", "reused"):
                continue
            unit = self.units[unit_id]
            version = selected_versions.get(unit["component_id"])
            manifest_members.append({
                "component_id": unit["component_id"],
                "contract_revision": unit["contract_revision"],
                "kind": unit["kind"],
                "target_id": unit["target_id"],
                "unit_id": unit_id,
                "version": version["version"] if version else "",
            })

        # generated sdk manifest
        sdk_records = []
        for record in self.generated_plan:
            if not record["regenerate"]:
                continue
            producer = record["producer_unit"]
            if producer not in selected:
                continue
            version = selected_versions.get(
                self.units[producer]["component_id"])
            sdk_records.append({
                "artifact_kind": record["artifact_kind"],
                "contract_revision": record["contract_revision"],
                "interface_id": record["interface_id"],
                "producer_unit": producer,
                "producer_version": version["version"] if version else "",
            })
        dump_jsonl("generated_sdk_manifest.jsonl", sorted(
            sdk_records,
            key=lambda r: (r["producer_unit"], r["interface_id"], r["artifact_kind"]),
        ))

        # migration order
        migration_rows = []
        for migration_unit, blocked_unit, tid in sorted(migration_records):
            migration_rows.append({
                "blocked_sequence": sequence.get(blocked_unit, 0),
                "blocks_unit": blocked_unit,
                "migration_sequence": sequence.get(migration_unit, 0),
                "migration_unit": migration_unit,
                "ordered": sequence.get(migration_unit, 0)
                < sequence.get(blocked_unit, 0),
                "target_id": tid,
            })
        dump_jsonl("migration_order.jsonl", sorted(
            migration_rows,
            key=lambda r: (r["migration_unit"], r["blocks_unit"]),
        ))

        # artifact provenance
        dump_jsonl("artifact_provenance.jsonl", [
            {
                "contract_revision": self.units[unit_id]["contract_revision"],
                "cost_ticks": costs[unit_id]["cost_ticks"],
                "pool_id": self.units[unit_id]["pool_id"],
                "reasons": sorted(self.units[unit_id]["reasons"]),
                "schedule_sequence": sequence.get(unit_id, 0),
                "source_revision": self.units[unit_id]["source_revision"],
                "toolchain_revision": self.units[unit_id]["toolchain_revision"],
                "unit_id": unit_id,
            }
            for unit_id in sorted(selected)
        ])

        # cache reuse manifest
        dump_jsonl("cache_reuse_manifest.jsonl", [
            {
                "artifact_digest": self.units[unit_id].get("artifact_digest", ""),
                "justification": "no invalidation reason; the previous artifact is "
                "retained by the published artifact index",
                "reusable": True,
                "unit_id": unit_id,
            }
            for unit_id in sorted(self.units)
            if states[unit_id] == "reused"
        ])

        # release delta
        previous_members = set(ledger)
        current_members = {row["unit_id"] for row in manifest_members}
        dump_json("release_delta.json", {
            "added_count": len(current_members - previous_members),
            "added_units": sorted(current_members - previous_members),
            "previous_release_id": self.previous_release_id,
            "release_id": self.release_id,
            "removed_count": len(previous_members - current_members),
            "removed_units": sorted(previous_members - current_members),
            "retained_count": len(previous_members & current_members),
            "retained_units": sorted(previous_members & current_members),
        })

        # audit exceptions
        dump_jsonl("audit_exceptions.jsonl", sorted(
            self.exceptions,
            key=lambda r: (r["code"], r["subject"], r["detail"]),
        ))

        # cost amortization
        amortization = []
        for unit_id in sorted(selected):
            producer_component = self.units[unit_id]["component_id"]
            interfaces = sorted({
                ifid for (ifid, _kind) in self.generated_outputs
                if self.generated_outputs[(ifid, _kind)]["_generated_sdk_component"]
                == producer_component
            })
            cost = costs[unit_id]["cost_ticks"]
            for ifid in interfaces:
                shares = []
                for cid in sorted(self.consumers_by_interface.get(ifid, ())):
                    row = self.consumers_by_interface[ifid][cid]
                    if str(row.get("requirement") or "").strip() != "required":
                        continue
                    other = unit_at.get((cid, self.units[unit_id]["target_id"]))
                    if other is None or other not in selected:
                        continue
                    shares.append((cid, other))
                if not shares:
                    continue
                base = cost // len(shares)
                remainder = cost - len(shares) * base
                for rank, (cid, _other) in enumerate(shares, start=1):
                    amortization.append({
                        "consumer_component": cid,
                        "interface_id": ifid,
                        "producer_unit": unit_id,
                        "remainder_rank": rank,
                        "share_ticks": base + (1 if rank <= remainder else 0),
                        "target_id": self.units[unit_id]["target_id"],
                    })
        dump_jsonl("cost_amortization.jsonl", sorted(
            amortization,
            key=lambda r: (r["producer_unit"], r["interface_id"],
                          r["consumer_component"]),
        ))

        # release decision
        mandatory_withheld = sorted(
            unit_id for unit_id, unit in self.units.items()
            if unit["mandatory"]
            and states[unit_id] in ("deferred", "blocked", "excluded")
        )
        total_cost = sum(costs[u]["cost_ticks"] for u in selected)
        if blocked_targets or unresolved:
            decision = "blocked"
        elif mandatory_withheld:
            decision = "deferred"
        else:
            decision = "publishable"
        dump_json("deployment_manifest.json", {
            "decision": decision,
            "member_count": len(manifest_members),
            "members": manifest_members,
            "release_id": self.release_id,
        })
        decision_obj = {
            "blocked_targets": sorted(blocked_targets),
            "decision": decision,
            "exception_count": len(self.exceptions),
            "mandatory_units_withheld": mandatory_withheld,
            "release_id": self.release_id,
            "scheduled_units": sorted(selected),
            "total_cost_ticks": total_cost,
            "units_blocked": sorted(u for u in sorted(self.units)
                                    if states[u] == "blocked"),
            "units_built_not_published": sorted(u for u in sorted(self.units)
                                                if states[u] == "built_not_published"),
            "units_deferred": sorted(u for u in sorted(self.units)
                                     if states[u] == "deferred"),
            "units_excluded": sorted(u for u in sorted(self.units)
                                     if states[u] == "excluded"),
            "units_included": sorted(u for u in sorted(self.units)
                                     if states[u] == "included"),
            "units_reused": sorted(u for u in sorted(self.units)
                                   if states[u] == "reused"),
            "units_total": len(self.units),
            "unresolved_clusters": sorted(unresolved),
        }
        dump_json("release_decision.json", decision_obj)

        # conformance summary
        lines = ["metric,value"]
        for metric in ("units_total", "units_included", "units_built_not_published",
                       "units_reused", "units_deferred", "units_blocked",
                       "units_excluded", "scheduled_units", "total_cost_ticks",
                       "exception_count"):
            if metric == "total_cost_ticks":
                value = total_cost
            elif metric == "exception_count":
                value = len(self.exceptions)
            elif metric == "units_total":
                value = len(self.units)
            else:
                value = len(decision_obj[metric])
            lines.append("%s,%d" % (metric, value))
        lines.append("decision,%s" % decision)
        with (out / "conformance_summary.csv").open(
                "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")


def elementary_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """All elementary directed cycles of a sparse graph, each in canonical form."""
    cycles: list[tuple[str, ...]] = {}
    for start in sorted(graph):
        stack = [(start, (start,))]
        while stack:
            node, path = stack.pop()
            for nxt in sorted(graph.get(node, ())):
                if nxt == start:
                    rotated = canonical(path)
                    cycles[rotated] = True
                elif nxt not in path:
                    stack.append((nxt, path + (nxt,)))
    return [list(c) for c in sorted(cycles)]


def canonical(path: tuple[str, ...]) -> tuple[str, ...]:
    lowest = min(range(len(path)), key=lambda i: path[i])
    return path[lowest:] + path[:lowest]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    planner = Planner(Path(argv[1]))
    planner.run(Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
