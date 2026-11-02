"""Verifier for the 0b27b9dc-7985-54f1-a120-46e6810315a3 bundle.

The graded corpus is rebuilt inside this module from seeds that live only here,
so nothing under the agent corpus directory is read at grade time. Two corpora
are used. The sample corpus reproduces the bytes the agent was given, which is
what the delivered artifacts are checked against. The evaluation corpus is
built from a seed the agent has never seen and exercises only rules the shipped
specification documents, which is what the delivered solver is checked against,
together with shapes and variants derived from it that the contract allows.

Negative tests use polarity inversion. Their assertions hold when the cheat is
present, so an honest submission fails them and avoids the negative weight.
"""

from __future__ import annotations

import os

import ast
import hashlib
import json
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path

from rewardkit import criteria, criterion

_REF_SRC = r'''
#!/usr/bin/env python3
"""lgactl: the LGA least-grant admission solver.

Reads a confinement corpus directory, replays every recorded run through the
four enforcement layers, derives the least grant plan that admits the runs the
site requires, and writes the twenty four declared artifacts plus a copy of
itself into the output directory it is handed.

Standard library only. Deterministic. No network use.

Usage: lgactl.py CORPUS_DIR OUT_DIR
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_POLICY = 3

NONE_TOKEN = "NONE"
BS = chr(92)

MAX_ROUNDS = 8

# The two atom kinds whose cost multiplier the cost controls fix, in the order
# the tie-break reads them, and the range a multiplier is searched over.
SCALED_KINDS = ("cap_bounding_add", "seccomp_rule_add")
MULTIPLIER_RANGE = (1, 2, 3, 4)

CAP_NAMES = (
    "CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_DAC_READ_SEARCH", "CAP_FOWNER",
    "CAP_FSETID", "CAP_KILL", "CAP_SETGID", "CAP_SETUID", "CAP_SETPCAP",
    "CAP_LINUX_IMMUTABLE", "CAP_NET_BIND_SERVICE", "CAP_NET_BROADCAST",
    "CAP_NET_ADMIN", "CAP_NET_RAW", "CAP_IPC_LOCK", "CAP_IPC_OWNER",
    "CAP_SYS_MODULE", "CAP_SYS_RAWIO", "CAP_SYS_CHROOT", "CAP_SYS_PTRACE",
    "CAP_SYS_PACCT", "CAP_SYS_ADMIN", "CAP_SYS_BOOT", "CAP_SYS_NICE",
    "CAP_SYS_RESOURCE", "CAP_SYS_TIME", "CAP_SYS_TTY_CONFIG", "CAP_MKNOD",
    "CAP_LEASE", "CAP_AUDIT_WRITE", "CAP_AUDIT_CONTROL", "CAP_SETFCAP",
    "CAP_MAC_OVERRIDE", "CAP_MAC_ADMIN", "CAP_SYSLOG", "CAP_WAKE_ALARM",
    "CAP_BLOCK_SUSPEND", "CAP_AUDIT_READ", "CAP_PERFMON", "CAP_BPF",
    "CAP_CHECKPOINT_RESTORE",
)
CAP_BIT = {name: index for index, name in enumerate(CAP_NAMES)}
BIT_CAP = {index: name for index, name in enumerate(CAP_NAMES)}

ACTION_RANK = {
    "KILL_PROCESS": 1, "KILL_THREAD": 2, "TRAP": 3, "ERRNO": 4,
    "USER_NOTIF": 5, "TRACE": 6, "LOG": 7, "ALLOW": 8,
}
HARD_DENY_ACTIONS = ("KILL_PROCESS", "KILL_THREAD", "TRAP", "USER_NOTIF", "TRACE")

PHASE_RANK = {"auth": 1, "account": 2, "session": 3}
LAYER_RANK = {"pam": 1, "selinux": 2, "capability": 3, "seccomp": 4}
ARCHES = ("x86_64", "i386", "aarch64")

PAM_FAILURES = ("auth_err", "user_unknown", "perm_denied", "maxtries",
                "cred_insufficient", "abort", "service_err")

ARTIFACT_NAMES = [
    "principal_registry.jsonl",
    "syscall_index.tsv",
    "pam_stack_resolved.csv",
    "selinux_type_graph.json",
    "seccomp_program.jsonl",
    "pam_verdicts.csv",
    "capability_ledger.csv",
    "domain_transitions.tsv",
    "seccomp_decisions.jsonl",
    "arch_dispatch.tsv",
    "admission_ledger.csv",
    "denial_attribution.jsonl",
    "blocked_syscalls.tsv",
    "capability_gaps.csv",
    "audit_continuity.jsonl",
    "relaxation_atoms.csv",
    "forbidden_atoms.tsv",
    "grant_plan.csv",
    "iteration_trace.jsonl",
    "minimality_witness.csv",
    "residual_denials.tsv",
    "conservation.json",
    "summary.json",
    "manifest.json",
]


# ------------------------------------------------------------------ scalars

def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def canon_id(raw: str) -> str:
    return nfc(str(raw)).strip().upper().replace("_", "-").replace(".", "-")


def canon_type(raw: str) -> str:
    return nfc(str(raw)).strip().lower().replace("-", "_").replace(".", "_")


def as_int(value, default=0) -> int:
    text = str(value).strip()
    if not text:
        return default
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    if text[:2].lower() == "0x":
        try:
            number = int(text[2:], 16)
        except ValueError:
            return default
        return -number if negative else number
    stripped = text.lstrip("0") or "0"
    try:
        number = int(stripped, 10)
    except ValueError:
        return default
    return -number if negative else number


def canon_cap(raw: str) -> str:
    text = nfc(str(raw)).strip()
    if not text:
        return ""
    if text.isdigit():
        return BIT_CAP.get(int(text), "")
    return text.upper()


def cap_set(raw: str) -> frozenset:
    text = str(raw).strip()
    if not text or text.lower() == "none":
        return frozenset()
    out = set()
    for piece in text.replace(",", "+").split("+"):
        name = canon_cap(piece)
        if name:
            out.add(name)
    return frozenset(out)


def cap_text(caps) -> str:
    if not caps:
        return NONE_TOKEN
    return "+".join(sorted(caps, key=lambda name: CAP_BIT[name]))


def half_even(value: float, places: int) -> str:
    quantum = 10 ** places
    scaled = value * quantum
    floor_value = int(scaled // 1)
    remainder = scaled - floor_value
    if remainder > 0.5:
        floor_value += 1
    elif remainder == 0.5 and floor_value % 2 == 1:
        floor_value += 1
    text = str(abs(floor_value)).rjust(places + 1, "0")
    sign = "-" if floor_value < 0 else ""
    if places == 0:
        return sign + text
    return "{}{}.{}".format(sign, text[:-places], text[-places:])


# ------------------------------------------------------------------ parsers

def body_lines(text: str):
    for line in text.split("\n"):
        if line.strip():
            yield line


def split_quoted(line: str, delim: str) -> list[str]:
    cells = []
    current = []
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if quoted:
            if char == '"':
                if index + 1 < len(line) and line[index + 1] == '"':
                    current.append('"')
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            current.append(char)
            index += 1
            continue
        if char == '"' and not current:
            quoted = True
            index += 1
            continue
        if char == delim:
            cells.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    cells.append("".join(current))
    return cells


def quoted_lines(text: str):
    """Physical lines joined into records: a quoted field may hold a newline,
    so a line that leaves a quote open continues onto the next one."""
    out = []
    pending = None
    for line in text.split("\n"):
        if pending is None:
            if not line.strip():
                continue
            pending = line
        else:
            pending = pending + "\n" + line
        if pending.count('"') % 2 == 0:
            out.append(pending)
            pending = None
    if pending is not None:
        out.append(pending)
    return out


def parse_delimited(text: str, delim: str) -> list[dict]:
    lines = quoted_lines(text)
    if not lines:
        return []
    head = split_quoted(lines[0], delim)
    rows = []
    for line in lines[1:]:
        cells = split_quoted(line, delim)
        cells += [""] * (len(head) - len(cells))
        rows.append(dict(zip(head, cells)))
    return rows


def tsv_unescape(cell: str) -> str:
    out = []
    index = 0
    while index < len(cell):
        char = cell[index]
        if char == BS and index + 1 < len(cell):
            nxt = cell[index + 1]
            if nxt == "t":
                out.append("\t")
                index += 2
                continue
            if nxt == "n":
                out.append("\n")
                index += 2
                continue
            if nxt == BS:
                out.append(BS)
                index += 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def parse_tsv(text: str) -> list[dict]:
    lines = list(body_lines(text))
    if not lines:
        return []
    head = [tsv_unescape(cell) for cell in lines[0].split("\t")]
    rows = []
    for line in lines[1:]:
        cells = [tsv_unescape(cell) for cell in line.split("\t")]
        cells += [""] * (len(head) - len(cells))
        rows.append(dict(zip(head, cells)))
    return rows


def parse_fixed(text: str) -> list[dict]:
    lines = list(body_lines(text))
    if len(lines) < 2:
        return []
    spec = lines[0]
    fields = []
    for chunk in spec.split(";"):
        if not chunk.strip():
            continue
        name, width = chunk.split(":")
        fields.append((name.strip(), int(width)))
    rows = []
    for line in lines[1:]:
        offset = 0
        row = {}
        for name, width in fields:
            row[name] = line[offset:offset + width].rstrip()
            offset += width
        rows.append(row)
    return rows


def parse_json(text: str) -> list[dict]:
    payload = json.loads(text)
    return list(payload.get("records", []))


def parse_jsonl(text: str) -> list[dict]:
    return [json.loads(line) for line in body_lines(text)]


def unquote_scalar(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        inner = text[1:-1]
        out = []
        index = 0
        while index < len(inner):
            char = inner[index]
            if char == BS and index + 1 < len(inner):
                nxt = inner[index + 1]
                mapped = {"n": "\n", "t": "\t", '"': '"', BS: BS}.get(nxt)
                if mapped is not None:
                    out.append(mapped)
                    index += 2
                    continue
            out.append(char)
            index += 1
        return "".join(out)
    return text


def parse_toml(text: str) -> list[dict]:
    rows = []
    current = None
    for line in body_lines(text):
        stripped = line.strip()
        if stripped.startswith("[["):
            current = {}
            rows.append(current)
            continue
        if current is None or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        current[key.strip()] = unquote_scalar(value)
    return rows


def parse_ini(text: str) -> list[dict]:
    rows = []
    current = None
    for line in body_lines(text):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = {}
            rows.append(current)
            continue
        if current is None or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        current[key.strip()] = unquote_scalar(value)
    return rows


def parse_properties(text: str) -> list[dict]:
    buckets: dict[int, dict] = {}
    order: list[int] = []
    for line in body_lines(text):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        parts = key.strip().split(".")
        if len(parts) < 3:
            continue
        index = as_int(parts[1], -1)
        if index < 0:
            continue
        if index not in buckets:
            buckets[index] = {}
            order.append(index)
        buckets[index][".".join(parts[2:])] = value.strip().replace(BS + ":", ":").replace(BS + "=", "=")
    return [buckets[index] for index in order]


def parse_logfmt(text: str) -> list[dict]:
    rows = []
    for line in body_lines(text):
        row = {}
        index = 0
        length = len(line)
        while index < length:
            while index < length and line[index] == " ":
                index += 1
            start = index
            while index < length and line[index] != "=":
                index += 1
            if index >= length:
                break
            key = line[start:index]
            index += 1
            if index < length and line[index] == '"':
                index += 1
                chunk = []
                while index < length:
                    char = line[index]
                    if char == BS and index + 1 < length:
                        nxt = line[index + 1]
                        chunk.append({"n": "\n", "t": "\t", '"': '"', BS: BS}.get(nxt, nxt))
                        index += 2
                        continue
                    if char == '"':
                        index += 1
                        break
                    chunk.append(char)
                    index += 1
                row[key] = "".join(chunk)
                continue
            start = index
            while index < length and line[index] != " ":
                index += 1
            row[key] = line[start:index]
        rows.append(row)
    return rows


SEXP_FIELD_RE = re.compile(r'\(([A-Za-z0-9_]+)\s+((?:"(?:[^"\\]|\\.)*")|[^()\s]*)\)')
SD_FIELD_RE = re.compile(r'([A-Za-z0-9_]+)="((?:[^"\\]|\\.)*)"')


def parse_sexp(text: str) -> list[dict]:
    rows = []
    for line in body_lines(text):
        row = {}
        for match in re.finditer(SEXP_FIELD_RE, line):
            row[match.group(1)] = unquote_scalar(match.group(2))
        if row:
            rows.append(row)
    return rows


def parse_rfc5424(text: str) -> list[dict]:
    rows = []
    for line in body_lines(text):
        start = line.find("[lga@1 ")
        if start < 0:
            continue
        body = line[start + 7:]
        # The record element closes at the first square bracket outside a
        # quoted value; anything after it belongs to other elements or to the
        # message and carries no record data.
        end = len(body)
        quoted = False
        index = 0
        while index < len(body):
            char = body[index]
            if quoted and char == BS:
                index += 2
                continue
            if char == '"':
                quoted = not quoted
            elif char == "]" and not quoted:
                end = index
                break
            index += 1
        body = body[:end]
        row = {}
        for match in re.finditer(SD_FIELD_RE, body):
            row[match.group(1)] = unquote_scalar('"' + match.group(2) + '"')
        if row:
            rows.append(row)
    return rows


PARSERS = {
    ".csv": lambda text: parse_delimited(text, ","),
    ".psv": lambda text: parse_delimited(text, "|"),
    ".ssv": lambda text: parse_delimited(text, " "),
    ".tsv": parse_tsv,
    ".fixed": parse_fixed,
    ".json": parse_json,
    ".jsonl": parse_jsonl,
    ".toml": parse_toml,
    ".ini": parse_ini,
    ".properties": parse_properties,
    ".logfmt": parse_logfmt,
    ".sexp": parse_sexp,
    ".rfc5424": parse_rfc5424,
}

GROUPS = (
    "principals", "pam-stack", "pam-returns", "selinux-types", "selinux-allow",
    "selinux-transition", "selinux-dontaudit", "cap-units", "cap-filecaps",
    "cap-required", "seccomp-filters", "seccomp-defaults", "arch-syscalls",
    "runs-trace", "runs-labels", "grant-atoms", "audit-events", "cost-controls",
)


class Corpus:
    """Every table the corpus carries, parsed from whatever encoding holds it."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.tables: dict[str, list[dict]] = {name: [] for name in GROUPS}
        for path in sorted(self.root.iterdir()):
            if not path.is_file() or path.suffix not in PARSERS:
                continue
            stem = path.stem
            group = stem.rsplit("-", 1)[0]
            if group not in self.tables:
                continue
            text = path.read_text(encoding="utf-8")
            # A byte order mark is discarded and a carriage return before a
            # newline belongs to the line ending (encodings appendix).
            if text.startswith("\ufeff"):
                text = text[1:]
            text = text.replace("\r\n", "\n")
            self.tables[group].extend(PARSERS[path.suffix](text))

    def rows(self, group: str) -> list[dict]:
        return self.tables.get(group, [])


# ------------------------------------------------------------------ model

def parse_target(text: str) -> dict:
    """The elements of an atom target, canonicalised.

    The note element is commentary, always last, and runs to the end of the
    string, so a semicolon or an equals sign inside it starts no element.
    """
    out = {}
    for chunk in str(text).split(";"):
        if "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "note":
            break
        if key in ("rule", "unit", "filter"):
            value = canon_id(value)
        elif key == "cap":
            value = canon_cap(value)
        elif key in ("source", "target"):
            value = canon_type(value)
        out[key] = value
    return out


class Grants:
    """The overlay one set of atoms puts on top of the shipped policy."""

    def __init__(self, model, atom_ids):
        self.ids = frozenset(atom_ids)
        self.pam_relax = set()
        self.allow_add = set()
        self.bound_add = set()
        self.ambient_add = set()
        self.sec_allow = set()
        self.default_relax = set()
        self.unloaded = set()
        for atom_id in sorted(self.ids):
            atom = model.atoms.get(atom_id)
            if atom is None:
                continue
            spec = atom["spec"]
            kind = atom["kind"]
            if kind == "pam_control_relax":
                self.pam_relax.add(spec.get("rule", ""))
            elif kind == "te_allow_add":
                self.allow_add.add((spec.get("source", ""), spec.get("target", ""),
                                    spec.get("class", ""), spec.get("perm", "")))
            elif kind == "cap_bounding_add":
                self.bound_add.add((spec.get("unit", ""), spec.get("cap", "")))
            elif kind == "cap_ambient_add":
                self.ambient_add.add((spec.get("unit", ""), spec.get("cap", "")))
            elif kind == "seccomp_rule_add":
                self.sec_allow.add((spec.get("filter", ""), spec.get("arch", ""),
                                    spec.get("syscall", "")))
            elif kind == "seccomp_default_relax":
                self.default_relax.add(spec.get("filter", ""))
            elif kind == "filter_unload":
                self.unloaded.add(spec.get("filter", ""))


class Model:
    """The shipped policy, normalised once, plus the recorded runs."""

    def __init__(self, corpus):
        self.repairs = {"arch": 0, "capability": 0, "perm": 0, "number": 0, "type": 0}
        self.arch_repairs = {}
        self._load_principals(corpus)
        self._load_pam(corpus)
        self._load_selinux(corpus)
        self._load_caps(corpus)
        self._load_seccomp(corpus)
        self._load_runs(corpus)
        self._load_atoms(corpus)
        self._load_controls(corpus)

    def _load_principals(self, corpus):
        self.principals = {}
        self.principal_order = []
        for row in corpus.rows("principals"):
            pid = canon_id(row.get("principal_id", ""))
            if not pid or pid in self.principals:
                continue
            self.principals[pid] = {
                "principal_id": pid,
                "uid": as_int(row.get("uid"), 0),
                "login": nfc(str(row.get("login", ""))),
                "display": nfc(str(row.get("display", ""))),
                "groups": sorted({g for g in str(row.get("groups", "")).split("|") if g}),
                "inheritable": cap_set(row.get("inh_thread", "")),
                "permitted": cap_set(row.get("perm_thread", "")),
            }
            self.principal_order.append(pid)
        self.principal_order.sort()

    def _load_pam(self, corpus):
        self.pam_lines = {}
        for row in corpus.rows("pam-stack"):
            service = nfc(str(row.get("service", ""))).strip()
            phase = nfc(str(row.get("phase", ""))).strip()
            if not service or phase not in PHASE_RANK:
                continue
            flags = str(row.get("flags", ""))
            gate = ""
            match = re.search(r"skip_if_uid_below=(\d+)", flags)
            if match:
                gate = match.group(1)
            self.pam_lines.setdefault((service, phase), []).append({
                "rule_id": canon_id(row.get("rule_id", "")),
                "rank": as_int(row.get("rank"), 0),
                "control": str(row.get("control", "")).strip().lower(),
                "module": str(row.get("module", "")).strip(),
                "gate_uid": gate,
            })
        for key in self.pam_lines:
            self.pam_lines[key].sort(key=lambda line: (line["rank"], line["module"],
                                                       line["rule_id"]))
        self.pam_returns = {}
        for row in corpus.rows("pam-returns"):
            key = (canon_id(row.get("run_id", "")), str(row.get("phase", "")).strip(),
                   str(row.get("module", "")).strip())
            code = str(row.get("code", "")).strip().lower()
            if key[0] and key[1] and key[2] and key not in self.pam_returns:
                self.pam_returns[key] = code

    def _load_selinux(self, corpus):
        self.type_attrs = {}
        self.type_order = []
        for row in corpus.rows("selinux-types"):
            name = canon_type(row.get("type_name", ""))
            if not name:
                continue
            if name not in self.type_attrs:
                self.type_attrs[name] = set()
                self.type_order.append(name)
            self.type_attrs[name].update(
                a for a in str(row.get("attributes", "")).split("|") if a)
        self.type_order.sort()
        self.attr_types = {}
        for name, attrs in self.type_attrs.items():
            for attr in attrs:
                self.attr_types.setdefault(attr, set()).add(name)
        self.domains = sorted(self.attr_types.get("domain", set()))
        self.file_types = sorted(n for n in self.type_attrs
                                 if "domain" not in self.type_attrs[n])

        self.allow = set()
        self.allow_rule = {}
        for row in corpus.rows("selinux-allow"):
            rule_id = canon_id(row.get("rule_id", ""))
            source = canon_type(row.get("source", ""))
            target = canon_type(row.get("target", ""))
            tclass = str(row.get("tclass", "")).strip()
            perms = [p.strip() for p in str(row.get("perms", "")).split(",") if p.strip()]
            for src in self._expand(source):
                for dst in self._expand(target):
                    for perm in perms:
                        key = (src, dst, tclass, perm)
                        self.allow.add(key)
                        if key not in self.allow_rule:
                            self.allow_rule[key] = rule_id

        self.transitions = {}
        for row in corpus.rows("selinux-transition"):
            source = canon_type(row.get("source", ""))
            exec_type = canon_type(row.get("exec_type", ""))
            entry = (as_int(row.get("rank"), 0), canon_id(row.get("rule_id", "")),
                     canon_type(row.get("new_domain", "")))
            self.transitions.setdefault((source, exec_type), []).append(entry)
        for key in self.transitions:
            self.transitions[key].sort()

        self.dontaudit = []
        for row in corpus.rows("selinux-dontaudit"):
            self.dontaudit.append({
                "rule_id": canon_id(row.get("rule_id", "")),
                "source": canon_type(row.get("source", "")),
                "target": canon_type(row.get("target", "")),
                "tclass": str(row.get("tclass", "")).strip(),
                "perm": str(row.get("perms", "")).strip(),
            })

    def _expand(self, name: str):
        if name in self.attr_types:
            return sorted(self.attr_types[name])
        return [name]

    def _load_caps(self, corpus):
        self.units = {}
        for row in corpus.rows("cap-units"):
            unit_id = canon_id(row.get("unit_id", ""))
            if not unit_id or unit_id in self.units:
                continue
            filters = [canon_id(f) for f in str(row.get("filters", "")).split("|") if f]
            self.units[unit_id] = {
                "unit_id": unit_id,
                "unit_name": str(row.get("unit_name", "")),
                "bounding": cap_set(row.get("bounding", "")),
                "ambient": cap_set(row.get("ambient", "")),
                "nnp": str(row.get("no_new_privs", "")).strip() == "true",
                "filters": filters,
            }
        self.filecaps = {}
        for row in corpus.rows("cap-filecaps"):
            binary_id = canon_id(row.get("binary_id", ""))
            if not binary_id or binary_id in self.filecaps:
                continue
            self.filecaps[binary_id] = {
                "binary_id": binary_id,
                "path": str(row.get("path", "")),
                "permitted": cap_set(row.get("permitted_file", "")),
                "inheritable": cap_set(row.get("inheritable_file", "")),
                "effective": str(row.get("effective_bit", "")).strip() == "1",
            }
        self.advisory_caps = set()
        self.cap_required = []
        for row in corpus.rows("cap-required"):
            capability = canon_cap(row.get("capability", ""))
            advisory = str(row.get("advisory", "")).strip().lower() == "yes"
            self.cap_required.append({
                "op_id": canon_id(row.get("op_id", "")),
                "operation": str(row.get("operation", "")),
                "capability": capability,
                "advisory": advisory,
            })
            if advisory and capability:
                self.advisory_caps.add(capability)

    def _load_seccomp(self, corpus):
        self.filter_rules = {}
        for row in corpus.rows("seccomp-filters"):
            filter_id = canon_id(row.get("filter_id", ""))
            arg_raw = str(row.get("arg_index", "")).strip()
            rule = {
                "rule_id": canon_id(row.get("rule_id", "")),
                "filter_id": filter_id,
                "idx": as_int(row.get("idx"), 0),
                "arch": str(row.get("arch", "")).strip(),
                "syscall": str(row.get("syscall", "")).strip(),
                "arg_index": None if arg_raw == "" else as_int(arg_raw, 0),
                "op": str(row.get("op", "")).strip().upper(),
                "value": as_int(row.get("value"), 0),
                "mask": as_int(row.get("mask"), 0),
                "action": str(row.get("action", "")).strip().upper(),
            }
            self.filter_rules.setdefault(filter_id, []).append(rule)
        for key in self.filter_rules:
            self.filter_rules[key].sort(key=lambda rule: (rule["idx"], rule["rule_id"]))
        self.filter_default = {}
        for row in corpus.rows("seccomp-defaults"):
            filter_id = canon_id(row.get("filter_id", ""))
            if filter_id and filter_id not in self.filter_default:
                self.filter_default[filter_id] = str(
                    row.get("default_action", "")).strip().upper()
        self.syscall_by_nr = {}
        self.syscall_rows = []
        for row in corpus.rows("arch-syscalls"):
            arch = str(row.get("arch", "")).strip()
            nr = as_int(row.get("nr"), -1)
            name = str(row.get("syscall", "")).strip()
            if not arch or nr < 0 or not name:
                continue
            if (arch, nr) not in self.syscall_by_nr:
                self.syscall_by_nr[(arch, nr)] = name
                self.syscall_rows.append({"arch": arch, "nr": nr, "syscall": name})

    def _load_runs(self, corpus):
        raw = {}
        for row in corpus.rows("runs-trace"):
            run_id = canon_id(row.get("run_id", ""))
            if not run_id:
                continue
            raw.setdefault(run_id, []).append(row)
        self.runs = {}
        self.run_order = sorted(raw)
        for run_id in self.run_order:
            events = sorted(raw[run_id], key=lambda row: as_int(row.get("seq"), 0))
            dispatch = ""
            for row in events:
                if str(row.get("kind", "")).strip() == "exec":
                    dispatch = str(row.get("arch", "")).strip()
                    break
            if not dispatch:
                for row in events:
                    if str(row.get("arch", "")).strip():
                        dispatch = str(row.get("arch", "")).strip()
                        break
            if not dispatch:
                dispatch = ARCHES[0]
            parsed = []
            for row in events:
                arch = str(row.get("arch", "")).strip()
                if not arch:
                    arch = dispatch
                    if str(row.get("kind", "")).strip() != "exec":
                        self.repairs["arch"] += 1
                        self.arch_repairs[arch] = self.arch_repairs.get(arch, 0) + 1
                capability = str(row.get("capability", "")).strip()
                canon_capability = canon_cap(capability)
                if capability and capability != canon_capability:
                    self.repairs["capability"] += 1
                perms = [p.strip() for p in str(row.get("perm", "")).split(",") if p.strip()]
                if len(perms) > 1:
                    self.repairs["perm"] += 1
                nr_raw = str(row.get("syscall_nr", "")).strip()
                if nr_raw and (nr_raw.lower().startswith("0x") or
                               (len(nr_raw) > 1 and nr_raw.startswith("0"))):
                    self.repairs["number"] += 1
                target_raw = str(row.get("target_type", "")).strip()
                target = canon_type(target_raw)
                if target_raw and target_raw != target:
                    self.repairs["type"] += 1
                parsed.append({
                    "run_id": run_id,
                    "seq": as_int(row.get("seq"), 0),
                    "kind": str(row.get("kind", "")).strip(),
                    "principal": canon_id(row.get("principal", "")),
                    "service": str(row.get("service", "")).strip(),
                    "unit": canon_id(row.get("unit", "")),
                    "binary": canon_id(row.get("binary", "")),
                    "source_domain": canon_type(row.get("source_domain", "")),
                    "exec_type": canon_type(row.get("exec_type", "")),
                    "arch": arch,
                    "phase": str(row.get("phase", "")).strip(),
                    "syscall_nr": as_int(nr_raw, -1) if nr_raw else -1,
                    "arg0": as_int(row.get("arg0"), 0),
                    "capability": canon_capability,
                    "tclass": str(row.get("tclass", "")).strip(),
                    "perms": perms,
                    "target_type": target,
                    "required": str(row.get("required", "")).strip().lower() == "yes",
                })
            head = parsed[0]
            self.runs[run_id] = {
                "run_id": run_id,
                "principal": head["principal"],
                "service": head["service"],
                "unit": head["unit"],
                "binary": head["binary"],
                "source_domain": head["source_domain"],
                "exec_type": head["exec_type"],
                "arch": dispatch,
                "events": parsed,
            }
        # Labels are relabelling batches: the record read last in canonical
        # shard order wins, unlike every other keyed group.
        self.labels = {}
        for row in corpus.rows("runs-labels"):
            run_id = canon_id(row.get("run_id", ""))
            if run_id:
                self.labels[run_id] = str(row.get("label", "")).strip().lower()

    def _load_atoms(self, corpus):
        self.atoms = {}
        for row in corpus.rows("grant-atoms"):
            atom_id = canon_id(row.get("atom_id", ""))
            if not atom_id or atom_id in self.atoms:
                continue
            target = str(row.get("target", ""))
            self.atoms[atom_id] = {
                "atom_id": atom_id,
                "layer": str(row.get("layer", "")).strip(),
                "kind": str(row.get("kind", "")).strip(),
                "cost": as_int(row.get("cost"), 0),
                "target": target,
                "spec": parse_target(target),
            }
        self.atom_order = sorted(self.atoms)

    def _load_controls(self, corpus):
        """Cost controls: known effective totals over named sets of atoms."""
        self.multipliers = {kind: 1 for kind in SCALED_KINDS}
        self.controls = []
        seen = set()
        for row in corpus.rows("cost-controls"):
            control_id = canon_id(row.get("control_id", ""))
            if not control_id or control_id in seen:
                continue
            seen.add(control_id)
            names = sorted({canon_id(a) for a in str(row.get("atoms", "")).split("|")
                            if a.strip()})
            if not names or any(name not in self.atoms for name in names):
                continue
            self.controls.append((control_id, names, as_int(row.get("total"), 0)))

    def effective_cost(self, atom_id) -> int:
        atom = self.atoms[atom_id]
        return atom["cost"] * self.multipliers.get(atom["kind"], 1)

    def consistent_pairs(self):
        """Every multiplier pair that reproduces every usable control."""
        if not self.controls:
            return []
        out = []
        for first in MULTIPLIER_RANGE:
            for second in MULTIPLIER_RANGE:
                scale = dict(zip(SCALED_KINDS, (first, second)))
                ok = True
                for _, names, total in self.controls:
                    got = sum(self.atoms[n]["cost"] * scale.get(self.atoms[n]["kind"], 1)
                              for n in names)
                    if got != total:
                        ok = False
                        break
                if ok:
                    out.append((first, second))
        return out


# ------------------------------------------------------------------ engines

NO_GRANTS = None


def pam_phase(model, run, phase, grants):
    """Resolve one PAM phase to a code, the deciding rule and the module."""
    lines = model.pam_lines.get((run["service"], phase), [])
    principal = model.principals.get(run["principal"])
    uid = principal["uid"] if principal else 0
    first_fail = None
    optional_fail = None
    saw_value = False
    for line in lines:
        if line["gate_uid"] and uid < as_int(line["gate_uid"], 0):
            continue
        control = line["control"]
        if grants is not None and line["rule_id"] in grants.pam_relax:
            control = "sufficient"
        code = model.pam_returns.get((run["run_id"], phase, line["module"]), "ignore")
        if code == "ignore":
            continue
        failed = code in PAM_FAILURES
        if control == "optional":
            if failed and optional_fail is None:
                optional_fail = (code, line)
            continue
        saw_value = True
        if control == "requisite":
            if failed:
                return code, line["rule_id"], line["module"]
            continue
        if control == "binding":
            if failed:
                return code, line["rule_id"], line["module"]
            return "success", "", line["module"]
        if control == "sufficient":
            if not failed and first_fail is None:
                return "success", "", line["module"]
            continue
        if failed and first_fail is None:
            first_fail = (code, line)
    if first_fail is not None:
        return first_fail[0], first_fail[1]["rule_id"], first_fail[1]["module"]
    if saw_value:
        return "success", "", ""
    if optional_fail is not None:
        return optional_fail[0], optional_fail[1]["rule_id"], optional_fail[1]["module"]
    return "service_err", "", ""


def allowed(model, grants, source, target, tclass, perm) -> bool:
    key = (source, target, tclass, perm)
    if key in model.allow:
        return True
    if grants is None:
        return False
    if key in grants.allow_add:
        return True
    for attr in sorted(model.type_attrs.get(target, ())):
        if (source, attr, tclass, perm) in grants.allow_add:
            return True
    for attr in sorted(model.type_attrs.get(source, ())):
        if (attr, target, tclass, perm) in grants.allow_add:
            return True
    return False


def transition_for(model, grants, source, exec_type):
    """The chosen transition rule, or None when the corpus declares none."""
    entries = model.transitions.get((source, exec_type), [])
    if entries:
        rank, rule_id, new_domain = entries[0]
        return rule_id, new_domain
    return None


def exec_domain(model, grants, run):
    """Resolve the domain the exec lands in, and why it may be refused."""
    source = run["source_domain"]
    exec_type = run["exec_type"]
    chosen = transition_for(model, grants, source, exec_type)
    if chosen is None:
        return source, "", True, {"execute": True, "entrypoint": True, "transition": True}
    rule_id, new_domain = chosen
    checks = {
        "execute": allowed(model, grants, source, exec_type, "file", "execute"),
        "entrypoint": allowed(model, grants, new_domain, exec_type, "file", "entrypoint"),
        "transition": allowed(model, grants, source, new_domain, "process", "transition"),
    }
    ok = all(checks.values())
    return (new_domain if ok else source), rule_id, ok, checks


def capability_sets(model, grants, run):
    unit = model.units.get(run["unit"])
    binary = model.filecaps.get(run["binary"])
    principal = model.principals.get(run["principal"])
    bounding = set(unit["bounding"]) if unit else set()
    ambient = set(unit["ambient"]) if unit else set()
    nnp = bool(unit and unit["nnp"])
    if grants is not None and unit is not None:
        for unit_id, cap in grants.bound_add:
            if unit_id == unit["unit_id"] and cap:
                bounding.add(cap)
        for unit_id, cap in grants.ambient_add:
            if unit_id == unit["unit_id"] and cap:
                ambient.add(cap)
                bounding.add(cap)
    file_permitted = set(binary["permitted"]) if binary else set()
    file_inheritable = set(binary["inheritable"]) if binary else set()
    effective_bit = bool(binary and binary["effective"])
    thread_inheritable = set(principal["inheritable"]) if principal else set()
    thread_permitted = set(principal["permitted"]) if principal else set()
    from_file = file_permitted & bounding
    if nnp:
        from_file = from_file & thread_permitted
    permitted = (thread_inheritable & file_inheritable) | from_file | ambient
    effective = set(permitted) if effective_bit else set(ambient)
    return {
        "bounding": bounding, "ambient": ambient, "nnp": nnp,
        "permitted": permitted, "effective": effective,
        "file_permitted": file_permitted, "thread_permitted": thread_permitted,
    }


def loaded_filters(model, grants, run):
    unit = model.units.get(run["unit"])
    names = list(unit["filters"]) if unit else []
    if grants is not None:
        names = [name for name in names if name not in grants.unloaded]
    return names


def seccomp_action(model, grants, run, event):
    """The action the stacked filters produce for one recorded syscall.

    Every loaded filter decides on its own and the strictest of those answers
    is the one the kernel returns, so a grant that relaxes one filter leaves a
    second filter free to refuse the same call.
    """
    arch = event["arch"]
    name = model.syscall_by_nr.get((arch, event["syscall_nr"]))
    filters = loaded_filters(model, grants, run)
    if name is None:
        return "KILL_PROCESS", NONE_TOKEN, 0, None
    if not filters:
        return "ALLOW", "", 0, name
    matched = 0
    verdicts = []
    for filter_id in filters:
        if (filter_id, arch, name) in grants.sec_allow:
            verdicts.append(("ALLOW", "GRANTED"))
            continue
        best_action = None
        best_rule = ""
        for rule in model.filter_rules.get(filter_id, ()):
            if rule["arch"] != arch or rule["syscall"] != name:
                continue
            if rule["arg_index"] is not None:
                if rule["arg_index"] != 0 or not arg_match(rule, event["arg0"]):
                    continue
            matched += 1
            rank = ACTION_RANK.get(rule["action"], 99)
            if best_action is None or rank < ACTION_RANK.get(best_action, 99):
                best_action = rule["action"]
                best_rule = rule["rule_id"]
        if best_action is None:
            action = model.filter_default.get(filter_id, "ALLOW")
            if filter_id in grants.default_relax:
                action = "ALLOW"
            verdicts.append((action, ""))
        else:
            verdicts.append((best_action, best_rule))
    action, rule_id = min(verdicts, key=lambda pair: (ACTION_RANK.get(pair[0], 99),
                                                      pair[1]))
    return action, rule_id, matched, name


def arg_match(rule, value) -> bool:
    op = rule["op"]
    target = rule["value"]
    if op == "EQ":
        return value == target
    if op == "NE":
        return value != target
    if op == "LT":
        return value < target
    if op == "LE":
        return value <= target
    if op == "GT":
        return value > target
    if op == "GE":
        return value >= target
    if op == "MASKED_EQ":
        return (value & rule["mask"]) == target
    return False


def action_denies(action: str, required: bool) -> bool:
    if action in HARD_DENY_ACTIONS:
        return True
    return action == "ERRNO" and required


def simulate(model, run_id, grants, trace=False):
    """Walk one recorded run and report the first event any layer refuses."""
    run = model.runs[run_id]
    detail = {"pam": [], "seccomp": [], "capgap": [], "domain": None,
              "caps": None, "audit": None}
    caps = capability_sets(model, grants, run)
    detail["caps"] = caps
    domain, trule, tok, checks = exec_domain(model, grants, run)
    detail["domain"] = {"domain": domain, "rule_id": trule, "ok": tok, "checks": checks}
    verdict = None
    audit_cap_ok = "CAP_AUDIT_WRITE" in caps["effective"]
    audit_access_ok = None
    for event in run["events"]:
        kind = event["kind"]
        if kind == "pam":
            code, rule_id, module = pam_phase(model, run, event["phase"], grants)
            if trace:
                detail["pam"].append({"phase": event["phase"], "code": code,
                                      "rule_id": rule_id, "module": module,
                                      "seq": event["seq"]})
            if verdict is None and code != "success":
                verdict = {"layer": "pam", "seq": event["seq"],
                           "rule_id": rule_id or NONE_TOKEN,
                           "reason": "pam_" + code,
                           "focus": {"rule": rule_id, "module": module}}
            if not trace and verdict is not None:
                break
            continue
        if kind == "exec":
            if verdict is None and not tok:
                missing = sorted(name for name, value in checks.items() if not value)
                target = model.transitions.get((run["source_domain"], run["exec_type"]))
                landing = target[0][2] if target else run["source_domain"]
                verdict = {"layer": "selinux", "seq": event["seq"],
                           "rule_id": trule or NONE_TOKEN,
                           "reason": "te_missing_" + missing[0],
                           "focus": {"missing": missing[0],
                                     "source": run["source_domain"],
                                     "exec": run["exec_type"],
                                     "landing": landing}}
            if not trace and verdict is not None:
                break
            continue
        if kind == "access":
            missing = sorted(perm for perm in event["perms"]
                             if not allowed(model, grants, domain, event["target_type"],
                                            event["tclass"], perm))
            if verdict is None and missing:
                verdict = {"layer": "selinux", "seq": event["seq"], "rule_id": NONE_TOKEN,
                           "reason": "te_denied_" + missing[0],
                           "focus": {"missing": "access", "source": domain,
                                     "target": event["target_type"],
                                     "class": event["tclass"], "perm": missing[0]}}
            if not trace and verdict is not None:
                break
            continue
        if kind == "capuse":
            capability = event["capability"]
            present = capability in caps["effective"]
            if trace and not present:
                in_file = capability in caps["file_permitted"]
                detail["capgap"].append({
                    "run_id": run_id, "capability": capability,
                    "unit": run["unit"],
                    "in_bounding": capability in caps["bounding"],
                    "in_permitted": capability in caps["permitted"],
                    "delta": -1 if in_file else 1,
                })
            if verdict is None and not present and capability not in model.advisory_caps:
                verdict = {"layer": "capability", "seq": event["seq"],
                           "rule_id": capability or NONE_TOKEN,
                           "reason": "cap_absent",
                           "focus": {"unit": run["unit"], "cap": capability}}
            if not trace and verdict is not None:
                break
            continue
        if kind == "syscall":
            action, rule_id, matched, name = seccomp_action(model, grants, run, event)
            denies = action_denies(action, event["required"])
            if trace:
                detail["seccomp"].append({
                    "run_id": run_id, "seq": event["seq"], "arch": event["arch"],
                    "nr": event["syscall_nr"], "syscall": name or NONE_TOKEN,
                    "action": action, "rule_id": rule_id or NONE_TOKEN,
                    "matched_count": matched, "denies": denies,
                })
            if verdict is None and denies:
                verdict = {"layer": "seccomp", "seq": event["seq"],
                           "rule_id": rule_id or NONE_TOKEN,
                           "reason": "seccomp_" + action.lower(),
                           "focus": {"filters": loaded_filters(model, grants, run),
                                     "arch": event["arch"],
                                     "syscall": name or NONE_TOKEN}}
            if not trace and verdict is not None:
                break
            continue
        if kind == "audit":
            ok = all(allowed(model, grants, domain, event["target_type"],
                             event["tclass"], perm) for perm in event["perms"])
            audit_access_ok = ok
            continue
    if audit_access_ok is None:
        audit_access_ok = False
    detail["audit"] = {"capability": audit_cap_ok, "access": audit_access_ok}
    if verdict is None:
        verdict = {"layer": NONE_TOKEN, "seq": 0, "rule_id": NONE_TOKEN,
                   "reason": "admitted", "focus": {}}
        verdict["admitted"] = True
    else:
        verdict["admitted"] = False
    verdict["run_id"] = run_id
    if trace:
        verdict["detail"] = detail
    return verdict


# ------------------------------------------------------------------ plan

class Solver:
    """Initial replay, forbidden set, grant plan, minimality witnesses."""

    def __init__(self, model):
        self.model = model
        self.empty = Grants(model, ())
        self.initial = {}
        for run_id in model.run_order:
            self.initial[run_id] = simulate(model, run_id, self.empty, trace=True)
        self.must_admit = [r for r in model.run_order
                           if model.labels.get(r) == "must_admit"]
        self.must_deny = [r for r in model.run_order
                          if model.labels.get(r) == "must_deny"]
        self.forbidden = {}
        self._find_forbidden()
        self.permissible = [a for a in model.atom_order if a not in self.forbidden]
        self._choose_multipliers()
        self.rounds = []
        self.plan = []
        self.residual = []
        self.witness = []
        self._build_plan()

    def _choose_multipliers(self):
        """Fix the two hidden multipliers from the cost controls.

        One consistent pair is taken as it is. Several are told apart by the
        settled plan each one produces: least total effective cost, then the
        smaller first multiplier, then the smaller second. None leaves both at
        one."""
        model = self.model
        pairs = model.consistent_pairs()
        if not pairs:
            model.multipliers = {kind: 1 for kind in SCALED_KINDS}
            return
        best = None
        for pair in pairs:
            model.multipliers = dict(zip(SCALED_KINDS, pair))
            if len(pairs) == 1:
                best = (0, pair)
                break
            self.rounds = []
            chosen = self._shrink(self._settle())
            cost = sum(model.effective_cost(a) for a in chosen)
            if best is None or (cost, pair) < best:
                best = (cost, pair)
        model.multipliers = dict(zip(SCALED_KINDS, best[1]))

    def _find_forbidden(self):
        # An atom changes only its own layer and never moves a refusal earlier,
        # so the must_deny runs it can admit are the ones refused at its layer
        # plus any the shipped policy already admits (SPEC sections 7 and 8).
        by_layer = {}
        for run_id in self.must_deny:
            by_layer.setdefault(self.initial[run_id]["layer"], []).append(run_id)
        for atom_id in self.model.atom_order:
            atom = self.model.atoms[atom_id]
            grants = Grants(self.model, (atom_id,))
            pool = sorted(by_layer.get(atom["layer"], []) + by_layer.get(NONE_TOKEN, []))
            for run_id in pool:
                if simulate(self.model, run_id, grants)["admitted"]:
                    self.forbidden[atom_id] = run_id
                    break

    def _candidates(self, verdict, run):
        """Atoms that name the object the refusal names, in canonical order."""
        focus = verdict.get("focus", {})
        layer = verdict["layer"]
        out = []
        for atom_id in self.permissible:
            atom = self.model.atoms[atom_id]
            if atom["layer"] != layer:
                continue
            spec = atom["spec"]
            kind = atom["kind"]
            if layer == "pam":
                if kind == "pam_control_relax" and spec.get("rule") != focus.get("rule"):
                    continue
            elif layer == "capability":
                if spec.get("unit") != focus.get("unit"):
                    continue
                if spec.get("cap") != focus.get("cap"):
                    continue
            elif layer == "seccomp":
                if spec.get("filter") not in focus.get("filters", ()):
                    continue
                if kind == "seccomp_rule_add":
                    if spec.get("arch") != focus.get("arch"):
                        continue
                    if spec.get("syscall") != focus.get("syscall"):
                        continue
            else:
                if spec.get("source") not in (focus.get("source"), focus.get("landing")):
                    continue
                if kind == "te_allow_add":
                    wanted = focus.get("target") or focus.get("exec")
                    holder = spec.get("target")
                    if holder != wanted and holder not in self.model.type_attrs.get(wanted, ()):
                        continue
            out.append(atom_id)
        return out

    def _build_plan(self):
        chosen = self._settle()
        chosen = self._shrink(chosen)
        self.plan_ids = sorted(chosen)
        self._finish(chosen)

    def _settle(self):
        chosen = set()
        for index in range(1, MAX_ROUNDS + 1):
            grants = Grants(self.model, chosen)
            denied = []
            for run_id in self.must_admit:
                verdict = simulate(self.model, run_id, grants)
                if not verdict["admitted"]:
                    denied.append((run_id, verdict))
            if not denied:
                break
            added = []
            for run_id, verdict in denied:
                run = self.model.runs[run_id]
                best = None
                for atom_id in self._candidates(verdict, run):
                    if atom_id in chosen:
                        continue
                    trial = Grants(self.model, chosen | {atom_id})
                    result = simulate(self.model, run_id, trial)
                    if result["admitted"] or result["seq"] > verdict["seq"]:
                        cost = self.model.effective_cost(atom_id)
                        if best is None or (cost, atom_id) < best:
                            best = (cost, atom_id)
                if best is not None:
                    chosen.add(best[1])
                    if best[1] not in added:
                        added.append(best[1])
            after = 0
            grants_after = Grants(self.model, chosen)
            for run_id in self.must_admit:
                if not simulate(self.model, run_id, grants_after)["admitted"]:
                    after += 1
            self.rounds.append({
                "round": index,
                "denied_before": len(denied),
                "denied_after": after,
                "atoms_added": sorted(added),
                "cost_added": sum(self.model.effective_cost(a) for a in added),
            })
            if not added:
                break
        return chosen

    def _satisfied(self, chosen):
        grants = Grants(self.model, chosen)
        return {run_id for run_id in self.must_admit
                if simulate(self.model, run_id, grants)["admitted"]}

    def _shrink(self, chosen):
        """Drop every atom whose removal leaves the same runs admitted."""
        base = self._satisfied(chosen)
        for atom_id in sorted(chosen, reverse=True):
            trial = set(chosen)
            trial.discard(atom_id)
            if self._satisfied(trial) >= base:
                chosen = trial
        return chosen

    def _finish(self, chosen):
        round_of = {}
        for record in self.rounds:
            for atom_id in record["atoms_added"]:
                if atom_id in chosen and atom_id not in round_of:
                    round_of[atom_id] = record["round"]
        for atom_id in sorted(chosen):
            atom = self.model.atoms[atom_id]
            self.plan.append({
                "atom_id": atom_id,
                "layer": atom["layer"],
                "kind": atom["kind"],
                "cost": atom["cost"],
                "round": round_of.get(atom_id, 0),
                "target": atom["target"],
            })
        self.plan.sort(key=lambda row: (row["round"],
                                        self.model.effective_cost(row["atom_id"]),
                                        row["atom_id"]))
        final = Grants(self.model, chosen)
        self.final = {}
        for run_id in self.model.run_order:
            self.final[run_id] = simulate(self.model, run_id, final)
        for run_id in self.must_admit:
            verdict = self.final[run_id]
            if verdict["admitted"]:
                continue
            status = "nonconvergent" if len(self.rounds) >= MAX_ROUNDS else "unrepairable"
            self.residual.append({
                "run_id": run_id,
                "label": "must_admit",
                "status": status,
                "rounds_used": len(self.rounds),
                "last_layer": verdict["layer"],
            })
        base = self._satisfied(chosen)
        for atom_id in sorted(chosen):
            trial = set(chosen)
            trial.discard(atom_id)
            grants = Grants(self.model, trial)
            witness_run = NONE_TOKEN
            witness_layer = NONE_TOKEN
            witness_seq = 0
            for run_id in self.must_admit:
                if run_id not in base:
                    continue
                verdict = simulate(self.model, run_id, grants)
                if not verdict["admitted"]:
                    witness_run = run_id
                    witness_layer = verdict["layer"]
                    witness_seq = verdict["seq"]
                    break
            self.witness.append({
                "atom_id": atom_id,
                "witness_run": witness_run,
                "witness_layer": witness_layer,
                "witness_seq": witness_seq,
            })


# ------------------------------------------------------------------ writers

def csv_cell(value) -> str:
    text = "" if value is None else str(value)
    if any(ch in text for ch in (',', '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


def write_csv(head, rows) -> str:
    out = [",".join(head)]
    for row in rows:
        out.append(",".join(csv_cell(row.get(name, "")) for name in head))
    return "\n".join(out) + "\n"


def tsv_cell(value) -> str:
    text = "" if value is None else str(value)
    return text.replace(BS, BS + BS).replace("\t", BS + "t").replace("\n", BS + "n")


def write_tsv(head, rows, header=True) -> str:
    out = []
    if header:
        out.append("\t".join(head))
    for row in rows:
        out.append("\t".join(tsv_cell(row.get(name, "")) for name in head))
    return "\n".join(out) + "\n"


def write_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def write_jsonl(rows) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                   for row in rows)


def yesno(flag) -> str:
    return "yes" if flag else "no"


# ------------------------------------------------------------------ artifacts

class Report:
    """Every declared artifact, rendered from one solved model."""

    def __init__(self, model, solver):
        self.model = model
        self.solver = solver
        self.files = {}
        self._build()

    def _build(self):
        model = self.model
        solver = self.solver
        initial = solver.initial
        final = solver.final

        used = {}
        for run_id in model.run_order:
            used.setdefault(model.runs[run_id]["principal"], []).append(run_id)

        residual_runs = {row["run_id"] for row in solver.residual}
        disposition = {}
        for pid, runs in used.items():
            if any(run_id in residual_runs for run_id in runs):
                disposition[pid] = "residual"
            elif any(not initial[r]["admitted"] and final[r]["admitted"] for r in runs):
                disposition[pid] = "granted"
            elif all(initial[r]["admitted"] for r in runs):
                disposition[pid] = "admitted"
            else:
                disposition[pid] = "denied"

        rows = []
        for pid in sorted(used):
            person = model.principals.get(pid)
            if person is None:
                continue
            rows.append({
                "principal_id": pid,
                "uid": person["uid"],
                "login": person["login"],
                "display": person["display"],
                "groups": person["groups"],
                "inheritable": sorted(person["inheritable"], key=lambda n: CAP_BIT[n]),
                "permitted": sorted(person["permitted"], key=lambda n: CAP_BIT[n]),
                "run_count": len(used[pid]),
                "final_disposition": disposition[pid],
            })
        self.files["principal_registry.jsonl"] = write_jsonl(rows)

        rows = []
        for entry in sorted(model.syscall_rows, key=lambda row: (row["arch"], row["nr"])):
            rows.append({
                "arch": entry["arch"], "nr": entry["nr"], "syscall": entry["syscall"],
                "nr_padded": "{:04d}".format(entry["nr"]),
            })
        self.files["syscall_index.tsv"] = write_tsv(
            ["arch", "nr", "syscall", "nr_padded"], rows)

        rows = []
        for service, phase in sorted(model.pam_lines,
                                     key=lambda key: (key[0], PHASE_RANK[key[1]])):
            for position, line in enumerate(model.pam_lines[(service, phase)], 1):
                rows.append({
                    "service": service, "phase": phase, "position": position,
                    "rank": line["rank"], "control": line["control"],
                    "module": line["module"], "rule_id": line["rule_id"],
                    "gated_uid": line["gate_uid"],
                })
        self.files["pam_stack_resolved.csv"] = write_csv(
            ["service", "phase", "position", "rank", "control", "module",
             "rule_id", "gated_uid"], rows)

        graph = {
            "types": {name: sorted(model.type_attrs[name]) for name in model.type_order},
            "attributes": {attr: sorted(model.attr_types[attr])
                           for attr in sorted(model.attr_types)},
            "domains": list(model.domains),
            "file_types": list(model.file_types),
        }
        self.files["selinux_type_graph.json"] = write_json(graph)

        by_name = {}
        for (arch, number), value in model.syscall_by_nr.items():
            key = (arch, value)
            if key not in by_name or number < by_name[key]:
                by_name[key] = number
        rows = []
        for filter_id in sorted(model.filter_rules):
            for rule in model.filter_rules[filter_id]:
                name = rule["syscall"]
                nr = by_name.get((rule["arch"], name))
                rows.append({
                    "rule_id": rule["rule_id"], "filter_id": filter_id,
                    "idx": rule["idx"], "arch": rule["arch"], "syscall": name,
                    "nr": nr, "arg_index": rule["arg_index"], "op": rule["op"],
                    "value": rule["value"], "mask": rule["mask"],
                    "action": rule["action"],
                    "action_rank": ACTION_RANK.get(rule["action"], 99),
                })
        self.files["seccomp_program.jsonl"] = write_jsonl(rows)

        rows = []
        for run_id in model.run_order:
            for record in initial[run_id]["detail"]["pam"]:
                rows.append({
                    "run_id": run_id, "phase": record["phase"],
                    "result": record["code"],
                    "deciding_rule": record["rule_id"] or NONE_TOKEN,
                    "deciding_module": record["module"] or NONE_TOKEN,
                })
        self.files["pam_verdicts.csv"] = write_csv(
            ["run_id", "phase", "result", "deciding_rule", "deciding_module"], rows)

        rows = []
        for run_id in model.run_order:
            caps = initial[run_id]["detail"]["caps"]
            run = model.runs[run_id]
            rows.append({
                "run_id": run_id, "unit": run["unit"], "binary": run["binary"],
                "nnp": yesno(caps["nnp"]),
                "bounding_count": len(caps["bounding"]),
                "ambient_count": len(caps["ambient"]),
                "permitted": cap_text(caps["permitted"]),
                "effective": cap_text(caps["effective"]),
            })
        self.files["capability_ledger.csv"] = write_csv(
            ["run_id", "unit", "binary", "nnp", "bounding_count", "ambient_count",
             "permitted", "effective"], rows)

        rows = []
        for run_id in model.run_order:
            info = initial[run_id]["detail"]["domain"]
            run = model.runs[run_id]
            rows.append({
                "run_id": run_id, "source_domain": run["source_domain"],
                "exec_type": run["exec_type"],
                "transition_rule": info["rule_id"] or NONE_TOKEN,
                "new_domain": info["domain"],
                "execute_ok": yesno(info["checks"]["execute"]),
                "entrypoint_ok": yesno(info["checks"]["entrypoint"]),
                "transition_ok": yesno(info["checks"]["transition"]),
            })
        self.files["domain_transitions.tsv"] = write_tsv(
            ["run_id", "source_domain", "exec_type", "transition_rule", "new_domain",
             "execute_ok", "entrypoint_ok", "transition_ok"], rows, header=False)

        decisions = []
        for run_id in model.run_order:
            decisions.extend(initial[run_id]["detail"]["seccomp"])
        self.files["seccomp_decisions.jsonl"] = write_jsonl(decisions)

        rows = []
        for arch in ARCHES:
            events = [row for row in decisions if row["arch"] == arch]
            rows.append({
                "arch": arch,
                "event_count": len(events),
                "run_count": sum(1 for run_id in model.run_order
                                 if model.runs[run_id]["arch"] == arch),
                "unknown_count": sum(1 for row in events if row["syscall"] == NONE_TOKEN),
                "repaired_count": model.arch_repairs.get(arch, 0),
            })
        self.files["arch_dispatch.tsv"] = write_tsv(
            ["arch", "event_count", "run_count", "unknown_count", "repaired_count"], rows)

        ledger = []
        for run_id in model.run_order:
            verdict = initial[run_id]
            ledger.append({
                "run_id": run_id,
                "label": model.labels.get(run_id, "unlabelled"),
                "verdict": "admitted" if verdict["admitted"] else "denied",
                "layer": verdict["layer"],
                "seq": verdict["seq"],
                "rule_id": verdict["rule_id"],
                "reason": verdict["reason"],
            })
        ledger.sort(key=lambda row: (LAYER_RANK.get(row["layer"], 9), row["seq"]))
        self.files["admission_ledger.csv"] = write_csv(
            ["run_id", "label", "verdict", "layer", "seq", "rule_id", "reason"], ledger)

        rows = []
        for run_id in model.run_order:
            verdict = initial[run_id]
            if verdict["admitted"]:
                continue
            rows.append({
                "run_id": run_id, "layer": verdict["layer"], "seq": verdict["seq"],
                "rule_id": verdict["rule_id"], "reason": verdict["reason"],
                "detail": self._detail_text(run_id, verdict),
            })
        self.files["denial_attribution.jsonl"] = write_jsonl(rows)

        plan_round = {}
        for row in solver.plan:
            spec = model.atoms[row["atom_id"]]["spec"]
            key = (spec.get("arch", ""), spec.get("syscall", ""))
            if key[0] and key[1] and key not in plan_round:
                plan_round[key] = row["round"]
        blocked = {}
        for row in decisions:
            if not row["denies"]:
                continue
            key = (row["arch"], row["syscall"])
            entry = blocked.setdefault(key, {"count": 0, "worst": "ALLOW"})
            entry["count"] += 1
            if ACTION_RANK.get(row["action"], 99) < ACTION_RANK.get(entry["worst"], 99):
                entry["worst"] = row["action"]
        rows = []
        for key in sorted(blocked):
            rows.append({
                "arch": key[0], "syscall": key[1],
                "block_count": blocked[key]["count"],
                "first_round": plan_round.get(key, 0),
                "worst_action": blocked[key]["worst"],
            })
        rows.sort(key=lambda row: (row["first_round"], row["arch"], row["syscall"]))
        self.files["blocked_syscalls.tsv"] = write_tsv(
            ["arch", "syscall", "block_count", "first_round", "worst_action"], rows)

        rows = []
        for run_id in model.run_order:
            for gap in initial[run_id]["detail"]["capgap"]:
                rows.append({
                    "run_id": gap["run_id"], "capability": gap["capability"],
                    "unit": gap["unit"], "in_bounding": yesno(gap["in_bounding"]),
                    "in_permitted": yesno(gap["in_permitted"]), "delta": gap["delta"],
                })
        rows.sort(key=lambda row: (row["run_id"], row["capability"]))
        self.files["capability_gaps.csv"] = write_csv(
            ["run_id", "capability", "unit", "in_bounding", "in_permitted", "delta"], rows)

        rows = []
        for run_id in model.run_order:
            audit = initial[run_id]["detail"]["audit"]
            if not audit["capability"]:
                reason = "capability"
            elif not audit["access"]:
                reason = "access"
            else:
                reason = ""
            rows.append({
                "run_id": run_id,
                "audit_capability": audit["capability"],
                "audit_access": audit["access"],
                "continuity": "intact" if reason == "" else "broken",
                "break_reason": reason,
            })
        self.files["audit_continuity.jsonl"] = write_jsonl(rows)

        single = {}
        for atom_id in model.atom_order:
            atom = model.atoms[atom_id]
            grants = Grants(model, (atom_id,))
            count = 0
            for run_id in solver.must_admit:
                if initial[run_id]["layer"] != atom["layer"]:
                    continue
                if simulate(model, run_id, grants)["admitted"]:
                    count += 1
            single[atom_id] = count
        rows = []
        for atom_id in model.atom_order:
            atom = model.atoms[atom_id]
            rows.append({
                "atom_id": atom_id, "layer": atom["layer"], "kind": atom["kind"],
                "cost": atom["cost"], "target": atom["target"],
                "repairs_count": single[atom_id],
                "forbidden": yesno(atom_id in solver.forbidden),
                "witness_run": solver.forbidden.get(atom_id, ""),
            })
        self.files["relaxation_atoms.csv"] = write_csv(
            ["atom_id", "layer", "kind", "cost", "target", "repairs_count",
             "forbidden", "witness_run"], rows)

        rows = []
        for atom_id in sorted(solver.forbidden):
            atom = model.atoms[atom_id]
            rows.append({
                "atom_id": atom_id, "layer": atom["layer"], "kind": atom["kind"],
                "cost": atom["cost"], "admitted_run": solver.forbidden[atom_id],
            })
        self.files["forbidden_atoms.tsv"] = write_tsv(
            ["atom_id", "layer", "kind", "cost", "admitted_run"], rows, header=False)

        self.files["grant_plan.csv"] = write_csv(
            ["atom_id", "layer", "kind", "cost", "round", "target"], solver.plan)

        self.files["iteration_trace.jsonl"] = write_jsonl(solver.rounds)

        self.files["minimality_witness.csv"] = write_csv(
            ["atom_id", "witness_run", "witness_layer", "witness_seq"], solver.witness)

        self.files["residual_denials.tsv"] = write_tsv(
            ["run_id", "label", "status", "rounds_used", "last_layer"], solver.residual)

        admitted_initial = sum(1 for r in model.run_order if initial[r]["admitted"])
        admitted_final = sum(1 for r in model.run_order if final[r]["admitted"])
        must_admit_satisfied = sum(1 for r in solver.must_admit if final[r]["admitted"])
        must_deny_held = sum(1 for r in solver.must_deny if not final[r]["admitted"])
        self.files["conservation.json"] = write_json({
            "total_runs": len(model.run_order),
            "admitted_initial": admitted_initial,
            "denied_initial": len(model.run_order) - admitted_initial,
            "admitted_final": admitted_final,
            "must_admit_total": len(solver.must_admit),
            "must_admit_satisfied": must_admit_satisfied,
            "must_deny_total": len(solver.must_deny),
            "must_deny_held": must_deny_held,
            "residual_count": len(solver.residual),
            "plan_cost": sum(model.effective_cost(row["atom_id"]) for row in solver.plan),
            "plan_size": len(solver.plan),
            "rounds_used": len(solver.rounds),
        })

        gap_rows = len(self.files["capability_gaps.csv"].splitlines()) - 1
        audit_broken = sum(1 for line in
                           self.files["audit_continuity.jsonl"].splitlines()
                           if '"continuity":"broken"' in line)
        layer_counts = {}
        for run_id in model.run_order:
            layer_counts[initial[run_id]["layer"]] = layer_counts.get(
                initial[run_id]["layer"], 0) + 1
        label_counts = {}
        for run_id in model.run_order:
            label = model.labels.get(run_id, "unlabelled")
            label_counts[label] = label_counts.get(label, 0) + 1
        kind_counts = {}
        for row in solver.plan:
            kind_counts[row["kind"]] = kind_counts.get(row["kind"], 0) + 1
        self.files["summary.json"] = write_json({
            "layer_counts": {key: layer_counts[key] for key in sorted(layer_counts)},
            "label_counts": {key: label_counts[key] for key in sorted(label_counts)},
            "arch_runs": {arch: sum(1 for r in model.run_order
                                    if model.runs[r]["arch"] == arch) for arch in ARCHES},
            "repair_counts": {key: model.repairs[key] for key in sorted(model.repairs)},
            "atom_kind_counts": {key: kind_counts[key] for key in sorted(kind_counts)},
            "blocked_syscall_rows": len(blocked),
            "capability_gap_rows": len(rows) if False else self.files[
                "capability_gaps.csv"].count("\n") - 1,
            "audit_broken_runs": sum(1 for line in self.files[
                "audit_continuity.jsonl"].splitlines() if '"continuity":"broken"' in line),
            "forbidden_atom_rows": len(solver.forbidden),
        })

        manifest = {}
        for name in ARTIFACT_NAMES:
            if name == "manifest.json":
                continue
            payload = self.files[name].encode("utf-8")
            manifest[name] = {
                "bytes": len(payload),
                "lines": self.files[name].count("\n"),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        self.files["manifest.json"] = write_json(manifest)

    def _detail_text(self, run_id, verdict) -> str:
        run = self.model.runs[run_id]
        for event in run["events"]:
            if event["seq"] != verdict["seq"]:
                continue
            if verdict["layer"] == "pam":
                return "pam {} phase {} rule {}".format(
                    run["service"], event["phase"], verdict["rule_id"])
            if verdict["layer"] == "selinux":
                perms = ",".join(event["perms"]) or "execute"
                return "allow {} {} : {} {{ {} }}".format(
                    run["source_domain"], event["target_type"] or run["exec_type"],
                    event["tclass"] or "file", perms)
            if verdict["layer"] == "capability":
                return "capability {} absent from the effective set".format(
                    event["capability"])
            return "seccomp {} on {} nr {}".format(
                verdict["reason"], event["arch"], event["syscall_nr"])
        return verdict["reason"]


def solve(corpus_dir: Path) -> Report:
    model = Model(Corpus(corpus_dir))
    return Report(model, Solver(model))


def main(argv) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: lgactl.py CORPUS_DIR OUT_DIR\n")
        return EXIT_USAGE
    corpus_dir = Path(argv[1])
    out_dir = Path(argv[2])
    if not corpus_dir.is_dir():
        sys.stderr.write("corpus directory is absent\n")
        return EXIT_USAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    report = solve(corpus_dir)
    for name, text in report.files.items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
    source = Path(__file__).read_text(encoding="utf-8")
    (out_dir / "lgactl.py").write_text(source, encoding="utf-8", newline="\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''

_GEN_SRC = r'''
"""LGA confinement corpus generator. Deterministic from a single integer seed.

Shared by the authoring step (SAMPLE_SEED -> environment/data/) and by the
verifier (EVAL_SEED -> a fresh corpus at grade time). Emits 52 flat row files
across thirteen encodings.

Outcomes are planted rather than left to chance. Each run is designated
admitted or refused at one named layer, the policy tables are then harmonised
so the designation is what the replay actually produces, and the grant atoms
and run labels are derived from a replay of the corpus the generator has just
written. The shipped corpus is therefore always internally consistent.
"""

from __future__ import annotations

import json
import random
import unicodedata
from pathlib import Path

ARCHES = ("x86_64", "i386", "aarch64")
ARCH_BASE = {"x86_64": 0, "i386": 300, "aarch64": 600}

SYSCALL_NAMES = (
    "read", "write", "open", "openat", "close", "stat", "fstat", "lstat",
    "poll", "lseek", "mmap", "mprotect", "munmap", "brk", "rt_sigaction",
    "rt_sigprocmask", "ioctl", "pread64", "pwrite64", "readv", "writev",
    "access", "pipe", "select", "sched_yield", "mremap", "msync", "mincore",
    "madvise", "dup", "dup2", "nanosleep", "getpid", "sendto", "recvfrom",
    "socket", "connect", "accept", "bind", "listen", "getsockname",
    "setsockopt", "getsockopt", "clone", "fork", "execve", "exit", "wait4",
    "kill", "uname", "fcntl", "flock", "fsync", "truncate", "ftruncate",
    "getdents64", "getcwd", "chdir", "rename", "mkdir", "rmdir", "unlink",
    "symlink", "readlink", "chmod", "fchmod", "chown", "fchown", "umask",
    "gettimeofday", "getrlimit", "getrusage", "sysinfo", "times", "ptrace",
    "getuid", "syslog", "getgid", "setuid", "setgid", "geteuid", "getegid",
    "setpgid", "getppid", "setsid", "setreuid", "setregid", "getgroups",
    "setgroups", "capget", "capset", "prctl", "arch_prctl", "futex",
    "set_tid_address", "clock_gettime", "clock_nanosleep", "exit_group",
    "epoll_create1", "epoll_ctl", "epoll_wait", "set_robust_list",
    "get_robust_list", "seccomp", "getrandom", "memfd_create", "bpf",
    "execveat", "statx", "rseq", "clone3", "faccessat2", "pidfd_open",
    "landlock_create_ruleset", "io_uring_setup", "openat2", "mount",
    "umount2", "pivot_root", "chroot", "keyctl", "add_key", "request_key",
    "quotactl", "swapon", "swapoff", "reboot", "sethostname", "setdomainname",
    "init_module", "delete_module", "kexec_load", "perf_event_open",
    "process_vm_readv", "process_vm_writev", "userfaultfd", "membarrier",
    "copy_file_range", "sendfile", "splice", "tee", "vmsplice", "fanotify_init",
    "inotify_init1", "inotify_add_watch", "signalfd4", "timerfd_create",
    "eventfd2", "unshare", "setns", "ioprio_set", "ioprio_get",
    "sched_setaffinity", "sched_getaffinity", "sched_setscheduler",
    "sched_getscheduler", "mlock", "munlock", "mlockall", "munlockall",
    "acct", "settimeofday", "adjtimex", "clock_adjtime", "syncfs", "fsopen",
    "fsconfig", "fsmount", "move_mount", "open_tree", "name_to_handle_at",
    "open_by_handle_at", "finit_module", "sched_getattr", "sched_setattr",
    "getcpu", "pkey_alloc", "pkey_free", "pkey_mprotect", "statfs", "fstatfs",
    "utimensat", "linkat", "unlinkat", "renameat2", "mkdirat", "mknodat",
    "fchownat", "fchmodat", "readlinkat", "symlinkat", "close_range",
    "epoll_pwait2", "mount_setattr", "futex_waitv", "cachestat", "fchmodat2",
    "listmount", "statmount", "mseal", "setxattr", "getxattr", "listxattr",
    "removexattr", "fsetxattr", "fgetxattr", "flistxattr", "fremovexattr",
    "lsetxattr", "lgetxattr", "llistxattr", "lremovexattr", "getpriority",
    "setpriority", "sync", "fdatasync", "readahead", "fadvise64", "fallocate",
    "timer_create", "timer_settime", "timer_gettime", "timer_delete",
    "shmget", "shmat", "shmdt", "shmctl", "semget", "semop", "semctl",
    "msgget", "msgsnd", "msgrcv", "msgctl", "mq_open", "mq_unlink",
)
REACHABLE = 170

CAP_NAMES = (
    "CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_DAC_READ_SEARCH", "CAP_FOWNER",
    "CAP_FSETID", "CAP_KILL", "CAP_SETGID", "CAP_SETUID", "CAP_SETPCAP",
    "CAP_LINUX_IMMUTABLE", "CAP_NET_BIND_SERVICE", "CAP_NET_BROADCAST",
    "CAP_NET_ADMIN", "CAP_NET_RAW", "CAP_IPC_LOCK", "CAP_IPC_OWNER",
    "CAP_SYS_MODULE", "CAP_SYS_RAWIO", "CAP_SYS_CHROOT", "CAP_SYS_PTRACE",
    "CAP_SYS_PACCT", "CAP_SYS_ADMIN", "CAP_SYS_BOOT", "CAP_SYS_NICE",
    "CAP_SYS_RESOURCE", "CAP_SYS_TIME", "CAP_SYS_TTY_CONFIG", "CAP_MKNOD",
    "CAP_LEASE", "CAP_AUDIT_WRITE", "CAP_AUDIT_CONTROL", "CAP_SETFCAP",
    "CAP_MAC_OVERRIDE", "CAP_MAC_ADMIN", "CAP_SYSLOG", "CAP_WAKE_ALARM",
    "CAP_BLOCK_SUSPEND", "CAP_AUDIT_READ", "CAP_PERFMON", "CAP_BPF",
    "CAP_CHECKPOINT_RESTORE",
)
CAP_BIT = {name: index for index, name in enumerate(CAP_NAMES)}

SERVICES = ("vault-admin", "vault-break", "vault-audit", "vault-batch",
            "vault-remote", "vault-local", "vault-quorum", "vault-attest",
            "vault-rotate", "vault-export", "vault-import")
PHASES = ("auth", "account", "session")
CONTROLS = ("required", "requisite", "sufficient", "optional", "binding")
DECISIVE = ("required", "requisite", "binding")
PAM_MODULES = (
    "pam_unix", "pam_faillock", "pam_custom_otp", "pam_pwquality",
    "pam_localuser", "pam_succeed_if", "pam_time", "pam_access",
    "pam_limits", "pam_env", "pam_keyinit", "pam_loginuid", "pam_selinux",
    "pam_namespace", "pam_systemd", "pam_lastlog", "pam_motd", "pam_nologin",
    "pam_securetty", "pam_wheel", "pam_rootok", "pam_deny",
)
PAM_FAILURES = ("auth_err", "user_unknown", "perm_denied", "maxtries",
                "cred_insufficient", "abort")

TCLASSES = ("file", "dir", "process", "chr_file", "fifo_file", "lnk_file",
            "unix_stream_socket")
PERMS = ("read", "write", "open", "getattr", "setattr", "append", "lock",
         "unlink", "search", "add_name", "remove_name", "relabelto",
         "create", "connectto", "sigchld", "signal")

STEMS = ("astrid", "bjorn", "celine", "dmitri", "elena", "fabien", "gudrun",
         "helios", "ingrid", "jerome", "katarin", "lucien", "mirela",
         "nadine", "oskar", "paloma", "quentin", "rosalie", "soren",
         "tomasz", "ulrike", "valeria", "wojtek", "xiomara", "yannick", "zofia")

OPERATIONS = ("unseal", "reseal", "rotate", "attest", "export", "import",
              "audit_emit", "quorum_join", "shard_read", "shard_write",
              "policy_load", "policy_drop")

N_PRINCIPALS = 660
N_RUNS = 620
N_TYPES = 800
N_UNITS = 660
N_BINARIES = 660
N_FILTERS = 440
N_STRICT = 100
N_ATOMS = 1200
BASE_UID = 1400

DESIGNATIONS = (["admit"] * 6 + ["pam"] * 3 + ["selinux"] * 3 +
                ["capability"] * 2 + ["seccomp"] * 3 + ["chain2"] * 2 +
                ["chain3"] * 1)
HEAVY_EVERY = 149
HEAVY_CAPS = 9


def rng_for(seed: int, salt: str) -> random.Random:
    return random.Random("{}:{}".format(seed, salt))


def nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def cap_render(caps, style: str) -> str:
    items = sorted(caps, key=lambda name: CAP_BIT[name])
    if not items:
        return "none"
    if style == "upper":
        return "+".join(items)
    if style == "lower":
        return "+".join(name.lower() for name in items)
    return "+".join(str(CAP_BIT[name]) for name in items)


def designation(index: int) -> str:
    if index % HEAVY_EVERY == 5:
        return "heavy"
    return DESIGNATIONS[index % len(DESIGNATIONS)]


def obscure_number(value, index):
    if index % 11 == 0:
        return "0x{:x}".format(value)
    if index % 7 == 0:
        return "{:06d}".format(value)
    return str(value)


def obscure_cap(name, index):
    if index % 5 == 0:
        return name.lower()
    if index % 9 == 0:
        return str(CAP_BIT[name])
    return name


def obscure_type(name, index):
    if index % 13 == 0:
        return name.upper()
    if index % 8 == 0:
        return name.replace("_", "-")
    return name


# ------------------------------------------------------------------ tables

def build_principals(seed):
    rng = rng_for(seed, "principals")
    rows = []
    for index in range(1, N_PRINCIPALS + 1):
        stem = STEMS[index % len(STEMS)]
        uid = BASE_UID + index
        if index % 47 == 0:
            uid = 100 + (index % 40)
        elif index % 47 == 23:
            uid = BASE_UID
        display = stem.capitalize() + ("é" if index % 5 == 0 else "")
        if index % 7 == 0 and "é" in display:
            display = nfd(display)
        groups = sorted({g for g in ("vaultops", "auditors", "breakglass",
                                     "batch", "wheel") if rng.random() < 0.34})
        if not groups:
            groups = ["vaultops"]
        inherit = {name for name in CAP_NAMES if rng.random() < 0.10}
        permitted = set(inherit) | {name for name in CAP_NAMES if rng.random() < 0.45}
        style = ("upper", "lower", "numeric")[index % 3]
        rows.append({
            "principal_id": "prn_{:04d}".format(index),
            "uid": uid,
            "login": "{}{:03d}".format(stem, index % 1000),
            "display": display,
            "groups": "|".join(groups),
            "inh_thread": cap_render(inherit, style),
            "perm_thread": cap_render(permitted, style),
        })
    return rows


def build_pam_stack(seed):
    """Twenty lines per service phase, each naming a module exactly once."""
    rng = rng_for(seed, "pam_stack")
    rows = []
    index = 0
    for service in SERVICES:
        for phase in PHASES:
            modules = rng.sample(list(PAM_MODULES), 20)
            ranks = rng.sample(range(10, 990), 20)
            for slot in range(20):
                index += 1
                control = CONTROLS[(index * 3 + slot) % len(CONTROLS)]
                flags = ""
                if index % 13 == 0:
                    flags = "skip_if_uid_below={}".format(BASE_UID)
                elif index % 17 == 0:
                    flags = "audit"
                elif index % 23 == 0:
                    flags = "try_first_pass"
                rows.append({
                    "rule_id": "pam_{:04d}".format(index),
                    "service": service,
                    "phase": phase,
                    "rank": ranks[slot],
                    "control": control,
                    "module": modules[slot],
                    "flags": flags,
                })
    return rows


def pam_choice(stack):
    """Every decisive line and the helper that follows it, per service phase."""
    lines = {}
    for row in stack:
        lines.setdefault((row["service"], row["phase"]), []).append(row)
    out = {}
    for key, rows in lines.items():
        rows = sorted(rows, key=lambda row: (row["rank"], row["module"], row["rule_id"]))
        counts = {}
        for row in rows:
            counts[row["module"]] = counts.get(row["module"], 0) + 1
        open_rows = [row for row in rows
                     if not row["flags"].startswith("skip_if_uid_below")
                     and counts[row["module"]] == 1]
        pairs = []
        for position, row in enumerate(open_rows):
            if row["control"] not in DECISIVE:
                continue
            helper = None
            for later in open_rows[position + 1:]:
                if later["control"] != "optional" and later["module"] != row["module"]:
                    helper = later
                    break
            if helper is None:
                continue
            pairs.append((row, helper))
        if pairs:
            out[key] = pairs
    return out


def build_types(seed):
    rng = rng_for(seed, "types")
    families = ("vault", "audit", "batch", "remote", "session", "policy",
                "secret", "spool", "relay", "shard", "beacon")
    rows = []
    for index in range(1, N_TYPES + 1):
        family = families[index % len(families)]
        kind = ("t", "exec_t", "conf_t", "log_t", "sock_t")[index % 5]
        attrs = []
        if index % 5 == 0:
            attrs.append("domain")
        if index % 4 == 1:
            attrs.append("file_type")
        if index % 9 == 0:
            attrs.append("privileged")
        if index % 11 == 0:
            attrs.append("auditable")
        if not attrs:
            attrs.append("base_type")
        rows.append({
            "type_name": "{}_{:03d}_{}".format(family, index, kind),
            "attributes": "|".join(attrs),
            "is_domain": "yes" if "domain" in attrs else "no",
            "note": "seq{}".format(rng.randrange(1000)),
        })
    return rows


def split_types(types):
    domains = [row["type_name"] for row in types if row["is_domain"] == "yes"]
    files = [row["type_name"] for row in types if row["is_domain"] != "yes"]
    return domains, files


def build_allow(seed, types):
    rng = rng_for(seed, "allow")
    domains, files = split_types(types)
    rows = []
    for index in range(1, 601):
        source = domains[index % len(domains)]
        if index % 11 == 0:
            target = "auditable"
        elif index % 7 == 0:
            target = domains[(index * 3) % len(domains)]
        else:
            target = files[(index * 5) % len(files)]
        perms = sorted({PERMS[(index * (slot + 3)) % len(PERMS)]
                        for slot in range(1 + rng.randrange(3))})
        rows.append({
            "rule_id": "te_{:04d}".format(index),
            "source": source,
            "target": target,
            "tclass": TCLASSES[index % len(TCLASSES)],
            "perms": ",".join(perms),
        })
    return rows


def build_transitions(seed, types, plan):
    """Two transition records per recorded run, plus background records.

    The two records for one run disagree about the landing domain and the one
    with the lower rank is the one that applies, while the one with the higher
    rank is written first. A reader that takes the first record it meets lands
    the process in the wrong domain and judges every later access against it.
    """
    rng = rng_for(seed, "transitions")
    domains, files = split_types(types)
    rows = []
    index = 0
    for run_id in sorted(plan):
        info = plan[run_id]
        index += 1
        # Section 6.2 says a run whose source and executable pair has no
        # transition record keeps its source domain, is not refused, and
        # reports the literal NONE with all three flags yes. Every run used to
        # carry a pair, so that branch was never walked. A rotating slice of
        # the runs designated to be admitted now carries none; each run's pair
        # is its own, so no other run loses a record it needed, and the
        # harmoniser grants that run's accesses against its source domain. The
        # stride is thirteen, coprime to the twenty-long designation cycle.
        if info["mode"] == "admit" and info["index"] % 13 == 2:
            continue
        low = 10 + (index * 7) % 400
        high = 500 + (index * 13) % 400
        landing = domains[(info["index"] * 17 + info["index"] // len(domains))
                          % len(domains)]
        decoy = domains[(info["index"] * 23 + 5) % len(domains)]
        rows.append({
            "rule_id": "tr_{:04d}".format(2 * index),
            "source": info["source_domain"], "exec_type": info["exec_type"],
            "new_domain": decoy, "rank": high,
        })
        rows.append({
            "rule_id": "tr_{:04d}".format(2 * index - 1),
            "source": info["source_domain"], "exec_type": info["exec_type"],
            "new_domain": landing, "rank": low,
        })
    for extra in range(1, 121):
        index += 1
        rows.append({
            "rule_id": "tr_{:04d}".format(2 * index),
            "source": domains[extra % len(domains)],
            "exec_type": files[(extra * 11) % len(files)],
            "new_domain": domains[(extra * 17) % len(domains)],
            "rank": rng.randrange(1, 900),
        })
    return rows


def build_dontaudit(seed, types):
    rng = rng_for(seed, "dontaudit")
    domains, files = split_types(types)
    return [{
        "rule_id": "da_{:04d}".format(index),
        "source": domains[index % len(domains)],
        "target": files[(index * 7) % len(files)],
        "tclass": TCLASSES[index % len(TCLASSES)],
        "perms": PERMS[index % len(PERMS)],
        "note": "advisory{}".format(rng.randrange(100)),
    } for index in range(1, 441)]


def build_units(seed):
    rng = rng_for(seed, "units")
    rows = []
    for index in range(1, N_UNITS + 1):
        bounding = {name for name in CAP_NAMES if rng.random() < 0.55}
        if index % 6 == 0:
            bounding.add("CAP_AUDIT_WRITE")
        ambient = {name for name in sorted(bounding) if rng.random() < 0.10}
        quiet_a = N_STRICT + 1 + rng.randrange(N_FILTERS - N_STRICT)
        quiet_b = N_STRICT + 1 + rng.randrange(N_FILTERS - N_STRICT)
        style = ("upper", "lower", "numeric")[(index + 1) % 3]
        rows.append({
            "unit_id": "unit_{:04d}".format(index),
            "unit_name": "vault-admin@{:04d}.service".format(index),
            "bounding": cap_render(bounding, style),
            "ambient": cap_render(ambient, style),
            "no_new_privs": "true" if index % 4 == 0 else "false",
            "filters": "|".join(sorted({"flt_{:04d}".format(quiet_a),
                                        "flt_{:04d}".format(quiet_b)})),
        })
    return rows


def build_filecaps(seed):
    rng = rng_for(seed, "filecaps")
    rows = []
    for index in range(1, N_BINARIES + 1):
        permitted = {name for name in CAP_NAMES if rng.random() < 0.55}
        inheritable = {name for name in CAP_NAMES if rng.random() < 0.25}
        style = ("numeric", "upper", "lower")[index % 3]
        rows.append({
            "binary_id": "bin_{:04d}".format(index),
            "path": "/usr/local/bin/vault_admin",
            "permitted_file": cap_render(permitted, style),
            "inheritable_file": cap_render(inheritable, style),
            "effective_bit": "0" if index % 23 == 0 else "1",
        })
    return rows


def build_cap_required(seed):
    rng = rng_for(seed, "cap_required")
    rows = []
    for index in range(1, 441):
        capability = ("CAP_AUDIT_WRITE" if index % 37 == 0
                      else CAP_NAMES[(index * 3) % len(CAP_NAMES)])
        rows.append({
            "op_id": "op_{:04d}".format(index),
            "operation": "{}_{:03d}".format(OPERATIONS[index % len(OPERATIONS)], index),
            "capability": capability,
            "advisory": "yes" if capability == "CAP_AUDIT_WRITE" else "no",
            "note": "r{}".format(rng.randrange(500)),
        })
    return rows


def build_syscall_table(seed):
    rng = rng_for(seed, "syscalls")
    rows = []
    for arch in ARCHES:
        base = ARCH_BASE[arch]
        stride = {"x86_64": 3, "i386": 5, "aarch64": 7}[arch]
        for slot in range(220):
            rows.append({
                "arch": arch,
                "nr": base + slot,
                "syscall": SYSCALL_NAMES[(slot * stride + base // 3) % REACHABLE],
                "note": "abi{}".format(rng.randrange(9)),
            })
    return rows


def build_filters(seed):
    rng = rng_for(seed, "filters")
    actions = ("LOG", "ERRNO", "TRAP", "KILL_THREAD", "KILL_PROCESS", "TRACE",
               "USER_NOTIF", "ALLOW")
    rows = []
    for index in range(1, 1001):
        has_arg = index % 5 == 0
        rows.append({
            "rule_id": "sec_{:04d}".format(index),
            "filter_id": "flt_{:04d}".format(1 + (index % N_STRICT)),
            "idx": index % 40,
            "arch": ARCHES[index % len(ARCHES)],
            "syscall": SYSCALL_NAMES[REACHABLE + (index % 40)],
            "arg_index": str(index % 3) if has_arg else "",
            "op": ("EQ", "NE", "LT", "LE", "GT", "GE", "MASKED_EQ")[index % 7] if has_arg else "",
            "value": str(rng.randrange(0, 4096)) if has_arg else "",
            "mask": str(rng.randrange(1, 255)) if has_arg and index % 7 == 6 else "",
            "action": actions[index % len(actions)],
        })
    return rows


def build_filter_defaults(seed):
    rng = rng_for(seed, "filter_defaults")
    rows = []
    for index in range(1, N_FILTERS + 1):
        if index <= N_STRICT:
            action = "ALLOW" if index % 3 else "LOG"
        else:
            draw = rng.random()
            action = "ALLOW" if draw < 0.88 else "LOG"
        rows.append({
            "filter_id": "flt_{:04d}".format(index),
            "default_action": action,
            "priority": rng.randrange(1, 99),
        })
    return rows


def build_runs(seed, types):
    rng = rng_for(seed, "runs")
    domains, files = split_types(types)
    trace = []
    plan = {}
    for index in range(1, N_RUNS + 1):
        run_id = "run_{:05d}".format(index)
        mode = designation(index)
        service = SERVICES[index % len(SERVICES)]
        unit = "unit_{:04d}".format(index)
        binary = "bin_{:04d}".format(index)
        source_domain = domains[index % len(domains)]
        exec_type = files[(index - 1) % len(files)]
        arch = ARCHES[index % len(ARCHES)]
        principal = "prn_{:04d}".format(1 + (index * 3) % N_PRINCIPALS)
        seq = 0
        events = []

        def emit(**fields):
            nonlocal seq
            seq += 1
            row = {
                "run_id": run_id, "seq": seq, "kind": "", "principal": principal,
                "service": service, "unit": unit, "binary": binary,
                "source_domain": source_domain, "exec_type": exec_type,
                "arch": arch, "phase": "", "syscall_nr": "", "arg0": "",
                "capability": "", "tclass": "", "perm": "", "target_type": "",
                "required": "",
            }
            row.update(fields)
            events.append(row)

        for phase in PHASES:
            emit(kind="pam", phase=phase)
        emit(kind="exec", tclass="file", perm="execute",
             target_type=obscure_type(exec_type, index), required="yes")
        accesses = []
        for slot in range(2 + rng.randrange(3)):
            perm = PERMS[(index * 2 + slot) % len(PERMS)]
            if slot == 1 and index % 9 == 0:
                perm = "{},{}".format(perm, PERMS[(index + slot) % len(PERMS)])
            target = files[(index * 7 + slot) % len(files)]
            tclass = TCLASSES[(index + slot) % len(TCLASSES)]
            accesses.append((target, tclass, perm))
            emit(kind="access", tclass=tclass, perm=perm,
                 target_type=obscure_type(target, index + slot), required="yes")
        caps = []
        if mode == "heavy":
            for slot in range(HEAVY_CAPS):
                name = CAP_NAMES[(index * 5 + slot * 3) % len(CAP_NAMES)]
                if name in caps or name == "CAP_AUDIT_WRITE":
                    name = CAP_NAMES[(index + slot * 7 + 1) % len(CAP_NAMES)]
                if name in caps or name == "CAP_AUDIT_WRITE":
                    continue
                caps.append(name)
                emit(kind="capuse", capability=obscure_cap(name, index + slot),
                     required="yes")
        else:
            for slot in range(1 + rng.randrange(3)):
                name = CAP_NAMES[(index * 5 + slot) % len(CAP_NAMES)]
                if name == "CAP_AUDIT_WRITE":
                    name = CAP_NAMES[(index + slot + 2) % len(CAP_NAMES)]
                if name in caps:
                    continue
                caps.append(name)
                emit(kind="capuse", capability=obscure_cap(name, index + slot),
                     required="yes")
        if index % 10 == 4:
            # The advisory capability is used, not only audited, on a tenth of
            # the runs, so a reader that refuses a run for missing it is caught.
            emit(kind="capuse", capability=obscure_cap("CAP_AUDIT_WRITE", index + 3),
                 required="yes")
        syscalls = []
        args = []
        # A rotating third of the runs designated to refuse at seccomp refuse
        # through a number the architecture's table does not carry, which is
        # the only path that reaches the unknown-number rule, the NONE system
        # call name and the unknown column of the dispatch artifact. Each
        # architecture's table is 220 wide, so base + 250 sits outside it. The
        # stride is seven because it has to stay coprime to both cycles it
        # crosses: the twenty-long designation cycle and the three-long
        # architecture cycle. A stride of three would put every unknown number
        # on i386 alone.
        blind = mode in ("seccomp", "chain3") and index % 7 == 1
        for slot in range(3 + rng.randrange(4)):
            nr = ARCH_BASE[arch] + ((index * 3 + slot * 7) % 220)
            required = slot % 3 != 0
            if blind and required and not any(flag for _, flag in syscalls):
                nr = ARCH_BASE[arch] + 250
            arg0 = rng.randrange(0, 4096)
            syscalls.append((nr, required))
            args.append(arg0)
            emit(kind="syscall", syscall_nr=obscure_number(nr, index + slot),
                 arg0=str(arg0), required="yes" if required else "no")
        audit_target = files[(index * 13 + 3) % len(files)]
        emit(kind="audit", capability="CAP_AUDIT_WRITE",
             tclass="netlink_audit_socket", perm="nlmsg_write",
             target_type=obscure_type(audit_target, index + 1), required="no")
        for row in events:
            if row["kind"] not in ("pam", "exec") and rng.random() < 0.09:
                row["arch"] = ""
        trace.extend(events)
        plan[run_id] = {
            "index": index, "mode": mode, "service": service, "unit": unit,
            "binary": binary, "source_domain": source_domain,
            "exec_type": exec_type, "arch": arch, "principal": principal,
            "accesses": accesses, "caps": caps, "syscalls": syscalls, "args": args,
            "audit_target": audit_target,
        }
    return trace, plan


def build_pam_returns(seed, plan, choices, stack):
    rows = []
    rng = rng_for(seed, "pam_returns")
    walk = {}
    for row in stack:
        walk.setdefault((row["service"], row["phase"]), []).append(row)
    for key in walk:
        walk[key].sort(key=lambda row: (row["rank"], row["module"], row["rule_id"]))
    for run_id in sorted(plan):
        info = plan[run_id]
        bad_phase = PHASES[info["index"] % 3] if info["mode"] == "pam" else ""
        for phase in PHASES:
            pairs = choices.get((info["service"], phase))
            if not pairs:
                continue
            decisive, helper = pairs[(info["index"] * 7 + info["index"] // 3)
                                     % len(pairs)]
            if phase == bad_phase and info["index"] % 3 == 0:
                # Every line of this phase stays silent, so the stack reaches
                # its end with nothing recorded and answers service_err.
                continue
            lines = walk[(info["service"], phase)]
            if phase == bad_phase and (info["index"] // 3) % 3 == 1:
                # Only an optional line speaks, and it fails, so the phase
                # reaches its end with no flag set and answers the optional
                # failure through the last branch of the phase result.
                soft = [row for row in lines if row["control"] == "optional"
                        and not row["flags"].startswith("skip_if_uid_below")]
                if soft:
                    rows.append({"run_id": run_id, "phase": phase,
                                 "module": soft[0]["module"],
                                 "code": PAM_FAILURES[info["index"] % len(PAM_FAILURES)]})
                    rng.random()
                    continue
            code = "success"
            if phase == bad_phase:
                code = PAM_FAILURES[info["index"] % len(PAM_FAILURES)]
            rows.append({"run_id": run_id, "phase": phase,
                         "module": decisive["module"], "code": code})
            rows.append({"run_id": run_id, "phase": phase,
                         "module": helper["module"],
                         "code": "success" if rng.random() < 0.8 else "ignore"})
            if phase != bad_phase:
                # A gated line ahead of the decisive one answers success, so
                # whether it is walked decides which module ends the phase:
                # principals under the gate skip it, and a principal sitting
                # exactly on the gate walks it.
                ahead = lines[:lines.index(decisive)]
                gated = [row for row in ahead
                         if row["flags"].startswith("skip_if_uid_below")
                         and row["control"] in ("binding", "sufficient")]
                if gated:
                    rows.append({"run_id": run_id, "phase": phase,
                                 "module": gated[0]["module"], "code": "success"})
    return rows


def build_audit(seed, trace):
    rng = rng_for(seed, "audit")
    rows = []
    index = 0
    for row in trace:
        if row["kind"] != "audit":
            continue
        index += 1
        if index > 440:
            break
        rows.append({
            "event_id": "aud_{:04d}".format(index),
            "run_id": row["run_id"],
            "ts": "2026-03-{:02d}T{:02d}:{:02d}:{:02d}.{:06d}Z".format(
                1 + index % 28, index % 24, index % 60, (index * 7) % 60,
                rng.randrange(0, 1000000)),
            "action": ("emit", "drop", "queue", "flush")[index % 4],
            "principal": row["principal"],
        })
    return rows


def build_base(seed):
    types = build_types(seed)
    stack = build_pam_stack(seed)
    choices = pam_choice(stack)
    trace, plan = build_runs(seed, types)
    return {
        "principals": build_principals(seed),
        "pam-stack": stack,
        "pam-returns": build_pam_returns(seed, plan, choices, stack),
        "selinux-types": types,
        "selinux-allow": build_allow(seed, types),
        "selinux-transition": build_transitions(seed, types, plan),
        "selinux-dontaudit": build_dontaudit(seed, types),
        "cap-units": build_units(seed),
        "cap-filecaps": build_filecaps(seed),
        "cap-required": build_cap_required(seed),
        "seccomp-filters": build_filters(seed),
        "seccomp-defaults": build_filter_defaults(seed),
        "arch-syscalls": build_syscall_table(seed),
        "runs-trace": trace,
        "runs-labels": [],
        "grant-atoms": [],
        "audit-events": build_audit(seed, trace),
        "cost-controls": [],
    }, plan


# ------------------------------------------------------------------ writers

BSL = chr(92)


def cell(value) -> str:
    return "" if value is None else str(value)


def quoted(value, delim) -> str:
    text = cell(value)
    if any(ch in text for ch in (delim, '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


def w_delimited(rows, fields, delim):
    out = [delim.join(fields)]
    for row in rows:
        out.append(delim.join(quoted(row.get(name, ""), delim) for name in fields))
    return "\n".join(out) + "\n"


def w_csv(rows, fields):
    return w_delimited(rows, fields, ",")


def w_psv(rows, fields):
    return w_delimited(rows, fields, "|")


def w_ssv(rows, fields):
    return w_delimited(rows, fields, " ")


def w_tsv(rows, fields):
    def esc(value):
        return cell(value).replace(BSL, BSL + BSL).replace("\t", BSL + "t")
    out = ["\t".join(fields)]
    for row in rows:
        out.append("\t".join(esc(row.get(name, "")) for name in fields))
    return "\n".join(out) + "\n"


def w_json(rows, fields):
    payload = {"records": [{name: cell(row.get(name, "")) for name in fields}
                           for row in rows]}
    return json.dumps(payload, ensure_ascii=False, indent=1) + "\n"


def w_jsonl(rows, fields):
    return "".join(
        json.dumps({name: cell(row.get(name, "")) for name in fields},
                   ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows)


def scalar_quote(value) -> str:
    text = cell(value)
    return '"' + text.replace(BSL, BSL + BSL).replace('"', BSL + '"') + '"'


def w_toml(rows, fields):
    out = []
    for row in rows:
        out.append("[[record]]")
        for name in fields:
            out.append("{} = {}".format(name, scalar_quote(row.get(name, ""))))
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def w_ini(rows, fields):
    out = []
    for index, row in enumerate(rows, 1):
        out.append("[record_{:05d}]".format(index))
        for name in fields:
            out.append("{} = {}".format(name, cell(row.get(name, ""))))
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def w_properties(rows, fields):
    out = []
    for index, row in enumerate(rows, 1):
        for name in fields:
            text = cell(row.get(name, "")).replace(":", BSL + ":").replace("=", BSL + "=")
            out.append("record.{}.{} = {}".format(index, name, text))
    return "\n".join(out) + "\n"


def w_logfmt(rows, fields):
    out = []
    for row in rows:
        parts = []
        for name in fields:
            text = cell(row.get(name, ""))
            if text == "" or any(ch in text for ch in (" ", '"', "=")):
                text = '"' + text.replace(BSL, BSL + BSL).replace('"', BSL + '"') + '"'
            parts.append("{}={}".format(name, text))
        out.append(" ".join(parts))
    return "\n".join(out) + "\n"


def w_sexp(rows, fields):
    out = []
    for row in rows:
        parts = []
        for name in fields:
            parts.append("({} {})".format(name, scalar_quote(row.get(name, ""))))
        out.append("(record {})".format(" ".join(parts)))
    return "\n".join(out) + "\n"


RELAY_ARCHES = ("x86_64", "i386", "aarch64")


def w_rfc5424(rows, fields):
    out = []
    for index, row in enumerate(rows, 1):
        pairs = []
        for name in fields:
            text = cell(row.get(name, "")).replace(BSL, BSL + BSL).replace('"', BSL + '"')
            pairs.append('{}="{}"'.format(name, text))
        # A relay that forwards a record stamps its own structured data element
        # after the record element, and the forwarded message after that. The
        # relay element names the architecture of the relay host, which has
        # nothing to do with the event; it is stamped where a non-syscall event
        # left its own architecture empty, so a reader that takes name="value"
        # pairs from the whole line rather than from the lga@1 element alone
        # reads it as the event's architecture and skips the repair it needs.
        # The stamp depends on the record alone, never on its line position,
        # so a corpus whose records are listed in another order carries the
        # same stamps on the same records.
        trailer = ""
        if "arch" in fields and cell(row.get("arch", "")) == "" and \
                cell(row.get("kind", "")) not in ("exec", "syscall"):
            digits = "".join(ch for ch in cell(row.get("run_id", "")) if ch.isdigit())
            weight = int(digits or "0") + int(cell(row.get("seq", "0")) or "0")
            if weight % 2 == 0:
                trailer = (' [origin@32473 host="lga-relay-{}" arch="{}"]'
                           ' forwarded by relay').format(
                               weight % 7, RELAY_ARCHES[(weight // 2) % 3])
        out.append('<net>1 2026-03-0{}T0{}:{:02d}:{:02d}Z lga-relay lgactl {} '
                   'LGA [lga@1 {}]{}'.format(
                       1 + index % 9, index % 10, index % 60, (index * 7) % 60,
                       index, " ".join(pairs), trailer))
        if index % 97 == 0:
            out.append('<net>1 2026-03-0{}T0{}:{:02d}:00Z lga-relay lgactl {} '
                       'HEARTBEAT - relay alive queue="0"'.format(
                           1 + index % 9, index % 10, index % 60, index))
    return "\n".join(out) + "\n"


def make_fixed(widths):
    def writer(rows, fields):
        head = ";".join("{}:{}".format(name, widths[name]) for name in fields)
        out = [head]
        for row in rows:
            line = []
            for name in fields:
                line.append(cell(row.get(name, ""))[:widths[name]].ljust(widths[name]))
            out.append("".join(line))
        return "\n".join(out) + "\n"
    return writer


FIXED_SYSCALLS = make_fixed({"arch": 7, "nr": 8, "syscall": 26, "note": 8})
FIXED_DONTAUDIT = make_fixed({"rule_id": 10, "source": 30, "target": 30,
                              "tclass": 26, "perms": 14, "note": 14})

WRITERS = {
    "csv": w_csv, "psv": w_psv, "ssv": w_ssv, "tsv": w_tsv, "json": w_json,
    "jsonl": w_jsonl, "toml": w_toml, "ini": w_ini, "properties": w_properties,
    "logfmt": w_logfmt, "sexp": w_sexp, "rfc5424": w_rfc5424,
    "fixed_syscalls": FIXED_SYSCALLS, "fixed_dontaudit": FIXED_DONTAUDIT,
}

F_PRINCIPALS = ["principal_id", "uid", "login", "display", "groups",
                "inh_thread", "perm_thread"]
F_PAM_STACK = ["rule_id", "service", "phase", "rank", "control", "module", "flags"]
F_PAM_RETURNS = ["run_id", "phase", "module", "code"]
F_TYPES = ["type_name", "attributes", "is_domain", "note"]
F_ALLOW = ["rule_id", "source", "target", "tclass", "perms"]
F_TRANSITION = ["rule_id", "source", "exec_type", "new_domain", "rank"]
F_DONTAUDIT = ["rule_id", "source", "target", "tclass", "perms", "note"]
F_UNITS = ["unit_id", "unit_name", "bounding", "ambient", "no_new_privs", "filters"]
F_FILECAPS = ["binary_id", "path", "permitted_file", "inheritable_file", "effective_bit"]
F_CAP_REQUIRED = ["op_id", "operation", "capability", "advisory", "note"]
F_FILTERS = ["rule_id", "filter_id", "idx", "arch", "syscall", "arg_index",
             "op", "value", "mask", "action"]
F_DEFAULTS = ["filter_id", "default_action", "priority"]
F_SYSCALLS = ["arch", "nr", "syscall", "note"]
F_TRACE = ["run_id", "seq", "kind", "principal", "service", "unit", "binary",
           "source_domain", "exec_type", "arch", "phase", "syscall_nr", "arg0",
           "capability", "tclass", "perm", "target_type", "required"]
F_LABELS = ["run_id", "label", "note"]
F_ATOMS = ["atom_id", "layer", "kind", "cost", "target"]
F_AUDIT = ["event_id", "run_id", "ts", "action", "principal"]
F_CONTROLS = ["control_id", "atoms", "total", "note"]

LAYOUT = [
    ("principals-a.csv", "csv", "principals", F_PRINCIPALS, 0, 3),
    ("principals-b.tsv", "tsv", "principals", F_PRINCIPALS, 1, 3),
    ("principals-c.jsonl", "jsonl", "principals", F_PRINCIPALS, 2, 3),
    ("pam-stack-a.csv", "csv", "pam-stack", F_PAM_STACK, 0, 3),
    ("pam-stack-b.ini", "ini", "pam-stack", F_PAM_STACK, 1, 3),
    ("pam-stack-c.logfmt", "logfmt", "pam-stack", F_PAM_STACK, 2, 3),
    ("pam-returns-a.jsonl", "jsonl", "pam-returns", F_PAM_RETURNS, 0, 3),
    ("pam-returns-b.tsv", "tsv", "pam-returns", F_PAM_RETURNS, 1, 3),
    ("pam-returns-c.ssv", "ssv", "pam-returns", F_PAM_RETURNS, 2, 3),
    ("selinux-types-a.csv", "csv", "selinux-types", F_TYPES, 0, 2),
    ("selinux-types-b.toml", "toml", "selinux-types", F_TYPES, 1, 2),
    ("selinux-allow-a.csv", "csv", "selinux-allow", F_ALLOW, 0, 4),
    ("selinux-allow-b.tsv", "tsv", "selinux-allow", F_ALLOW, 1, 4),
    ("selinux-allow-c.psv", "psv", "selinux-allow", F_ALLOW, 2, 4),
    ("selinux-allow-d.jsonl", "jsonl", "selinux-allow", F_ALLOW, 3, 4),
    ("selinux-transition-a.csv", "csv", "selinux-transition", F_TRANSITION, 0, 3),
    ("selinux-transition-b.logfmt", "logfmt", "selinux-transition", F_TRANSITION, 1, 3),
    ("selinux-transition-c.sexp", "sexp", "selinux-transition", F_TRANSITION, 2, 3),
    ("selinux-dontaudit-a.fixed", "fixed_dontaudit", "selinux-dontaudit", F_DONTAUDIT, 0, 2),
    ("selinux-dontaudit-b.jsonl", "jsonl", "selinux-dontaudit", F_DONTAUDIT, 1, 2),
    ("cap-units-a.toml", "toml", "cap-units", F_UNITS, 0, 3),
    ("cap-units-b.ini", "ini", "cap-units", F_UNITS, 1, 3),
    ("cap-units-c.csv", "csv", "cap-units", F_UNITS, 2, 3),
    ("cap-filecaps-a.csv", "csv", "cap-filecaps", F_FILECAPS, 0, 3),
    ("cap-filecaps-b.properties", "properties", "cap-filecaps", F_FILECAPS, 1, 3),
    ("cap-filecaps-c.ssv", "ssv", "cap-filecaps", F_FILECAPS, 2, 3),
    ("cap-required-a.tsv", "tsv", "cap-required", F_CAP_REQUIRED, 0, 2),
    ("cap-required-b.psv", "psv", "cap-required", F_CAP_REQUIRED, 1, 2),
    ("seccomp-filters-a.csv", "csv", "seccomp-filters", F_FILTERS, 0, 5),
    ("seccomp-filters-b.jsonl", "jsonl", "seccomp-filters", F_FILTERS, 1, 5),
    ("seccomp-filters-c.tsv", "tsv", "seccomp-filters", F_FILTERS, 2, 5),
    ("seccomp-filters-d.psv", "psv", "seccomp-filters", F_FILTERS, 3, 5),
    ("seccomp-filters-e.ssv", "ssv", "seccomp-filters", F_FILTERS, 4, 5),
    ("seccomp-defaults-a.properties", "properties", "seccomp-defaults", F_DEFAULTS, 0, 2),
    ("seccomp-defaults-b.json", "json", "seccomp-defaults", F_DEFAULTS, 1, 2),
    ("arch-syscalls-a.csv", "csv", "arch-syscalls", F_SYSCALLS, 0, 3),
    ("arch-syscalls-b.tsv", "tsv", "arch-syscalls", F_SYSCALLS, 1, 3),
    ("arch-syscalls-c.fixed", "fixed_syscalls", "arch-syscalls", F_SYSCALLS, 2, 3),
    ("runs-trace-a.jsonl", "jsonl", "runs-trace", F_TRACE, 0, 5),
    ("runs-trace-b.rfc5424", "rfc5424", "runs-trace", F_TRACE, 1, 5),
    ("runs-trace-c.logfmt", "logfmt", "runs-trace", F_TRACE, 2, 5),
    ("runs-trace-d.csv", "csv", "runs-trace", F_TRACE, 3, 5),
    ("runs-trace-e.psv", "psv", "runs-trace", F_TRACE, 4, 5),
    ("runs-labels-a.csv", "csv", "runs-labels", F_LABELS, 0, 2),
    ("runs-labels-b.properties", "properties", "runs-labels", F_LABELS, 1, 2),
    ("grant-atoms-a.csv", "csv", "grant-atoms", F_ATOMS, 0, 3),
    ("grant-atoms-b.jsonl", "jsonl", "grant-atoms", F_ATOMS, 1, 3),
    ("grant-atoms-c.toml", "toml", "grant-atoms", F_ATOMS, 2, 3),
    ("audit-events-a.rfc5424", "rfc5424", "audit-events", F_AUDIT, 0, 2),
    ("audit-events-b.logfmt", "logfmt", "audit-events", F_AUDIT, 1, 2),
    ("cost-controls-a.csv", "csv", "cost-controls", F_CONTROLS, 0, 2),
    ("cost-controls-b.jsonl", "jsonl", "cost-controls", F_CONTROLS, 1, 2),
]


def shard(rows, count):
    if count <= 1:
        return [list(rows)]
    size = (len(rows) + count - 1) // count if rows else 0
    out = []
    for index in range(count):
        out.append(list(rows[index * size:(index + 1) * size]) if size else [])
    return out


def write_tables(data, outdir: Path, only=None):
    outdir.mkdir(parents=True, exist_ok=True)
    cache = {}
    for name, fmt, table, fields, index, total in LAYOUT:
        if only is not None and table not in only:
            continue
        key = (table, total)
        if key not in cache:
            cache[key] = shard(data[table], total)
        text = WRITERS[fmt](cache[key][index], fields)
        (outdir / name).write_text(text, encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ atoms

NOTE_TEXT = 'raised at review, ticket "LGA-{:04d}"'


class DraftGrants:
    """A grant overlay assembled while the atom catalogue is still being built."""

    def __init__(self):
        self.pam_relax = set()
        self.allow_add = set()
        self.bound_add = set()
        self.ambient_add = set()
        self.sec_allow = set()
        self.default_relax = set()
        self.unloaded = set()

    def apply(self, kind, spec):
        if kind == "pam_control_relax":
            self.pam_relax.add(spec.get("rule", ""))
        elif kind == "te_allow_add":
            self.allow_add.add((spec.get("source", ""), spec.get("target", ""),
                                spec.get("class", ""), spec.get("perm", "")))
        elif kind == "cap_bounding_add":
            self.bound_add.add((spec.get("unit", ""), spec.get("cap", "")))
        elif kind == "cap_ambient_add":
            self.ambient_add.add((spec.get("unit", ""), spec.get("cap", "")))
        elif kind == "seccomp_rule_add":
            self.sec_allow.add((spec.get("filter", ""), spec.get("arch", ""),
                                spec.get("syscall", "")))
        elif kind == "seccomp_default_relax":
            self.default_relax.add(spec.get("filter", ""))
        elif kind == "filter_unload":
            self.unloaded.add(spec.get("filter", ""))


def derive_atoms(ref, model, seed):
    """Grant atoms that name the objects the refusals name, plus decoys.

    Refusals are discovered along the repair path rather than once: the draft
    overlay grows as atoms are minted, so the refusal a run reaches after its
    first is minted too, and a chain of refusals ends with a chain of atoms.
    """
    minted = {}
    order = []
    draft = DraftGrants()

    def add(layer, kind, cost, spec):
        target = ";".join("{}={}".format(key, spec[key]) for key in spec)
        key = (kind, target)
        if key in minted:
            return False
        minted[key] = {"layer": layer, "kind": kind, "cost": cost, "target": target}
        order.append(key)
        draft.apply(kind, spec)
        return True

    for _ in range(ref.MAX_ROUNDS + 4):
        progressed = False
        for run_id in model.run_order:
            verdict = ref.simulate(model, run_id, draft)
            if verdict["admitted"]:
                continue
            focus = verdict.get("focus", {})
            layer = verdict["layer"]
            if layer == "pam":
                if focus.get("rule"):
                    progressed |= add(layer, "pam_control_relax", 4,
                                      {"rule": focus["rule"]})
            elif layer == "selinux":
                missing = focus.get("missing")
                if missing == "access":
                    progressed |= add(layer, "te_allow_add", 3, {
                        "source": focus["source"], "target": focus["target"],
                        "class": focus["class"], "perm": focus["perm"]})
                    for attr in sorted(model.type_attrs.get(focus["target"], ())):
                        progressed |= add(layer, "te_allow_add", 1, {
                            "source": focus["source"], "target": attr,
                            "class": focus["class"], "perm": focus["perm"]})
                        break
                elif missing == "execute":
                    progressed |= add(layer, "te_allow_add", 3, {
                        "source": focus["source"], "target": focus["exec"],
                        "class": "file", "perm": "execute"})
                elif missing == "entrypoint":
                    progressed |= add(layer, "te_allow_add", 3, {
                        "source": focus["landing"], "target": focus["exec"],
                        "class": "file", "perm": "entrypoint"})
                elif missing == "transition":
                    progressed |= add(layer, "te_allow_add", 3, {
                        "source": focus["source"], "target": focus["landing"],
                        "class": "process", "perm": "transition"})
            elif layer == "capability":
                unit = focus.get("unit")
                cap = focus.get("cap")
                if unit and cap:
                    progressed |= add(layer, "cap_bounding_add", 3,
                                      {"unit": unit, "cap": cap})
                    progressed |= add(layer, "cap_ambient_add", 5,
                                      {"unit": unit, "cap": cap})
            elif layer == "seccomp":
                arch = focus.get("arch", "")
                name = focus.get("syscall", "")
                for filter_id in focus.get("filters", ()):
                    if name and name != "NONE":
                        progressed |= add(layer, "seccomp_rule_add", 2, {
                            "filter": filter_id, "arch": arch, "syscall": name})
                    progressed |= add(layer, "seccomp_default_relax", 1,
                                      {"filter": filter_id})
                    progressed |= add(layer, "filter_unload", 6, {"filter": filter_id})
        if not progressed:
            break

    picked = [minted[key] for key in order]
    rng = rng_for(seed, "atom_decoys")
    domains, _ = split_types(build_types(seed))
    while len(picked) < N_ATOMS:
        index = len(picked)
        picked.append({
            "layer": "selinux", "kind": "te_allow_add", "cost": 1 + index % 9,
            "target": "source={};target={};class={};perm={}".format(
                domains[index % len(domains)], domains[(index * 5) % len(domains)],
                TCLASSES[index % len(TCLASSES)], PERMS[index % len(PERMS)]),
        })
        rng.random()

    picked.sort(key=lambda row: (row["layer"], row["target"], row["kind"]))
    rows = []
    for index, atom in enumerate(picked, 1):
        target = atom["target"]
        if index % 23 == 0:
            target = target + ";note=" + NOTE_TEXT.format(index)
        rows.append({
            "atom_id": "atm_{:04d}".format(index),
            "layer": atom["layer"],
            "kind": atom["kind"],
            "cost": atom["cost"],
            "target": target,
        })
    return rows


def derive_labels(ref, model, plan):
    """Mark the runs the site requires admitted and the runs it requires denied.

    A run is admissible when the whole permissible grant set admits it. Every
    atom kind is relaxing, so that set is the most permissive one any plan can
    reach and the test is exact.
    """
    empty = ref.Grants(model, ())
    verdicts = {run_id: ref.simulate(model, run_id, empty)
                for run_id in model.run_order}
    denied = [run_id for run_id in model.run_order if not verdicts[run_id]["admitted"]]
    modes = {ref.canon_id(key): value["mode"] for key, value in plan.items()}
    forced = {run_id for run_id in denied
              if modes.get(run_id) in ("heavy", "chain2", "chain3")}
    rest = [run_id for run_id in denied if run_id not in forced]
    must_deny = [run_id for index, run_id in enumerate(rest) if index % 4 == 3]
    by_layer = {}
    for run_id in must_deny:
        by_layer.setdefault(verdicts[run_id]["layer"], []).append(run_id)
    forbidden = set()
    for atom_id in model.atom_order:
        atom = model.atoms[atom_id]
        grants = ref.Grants(model, (atom_id,))
        for run_id in by_layer.get(atom["layer"], ()):
            if ref.simulate(model, run_id, grants)["admitted"]:
                forbidden.add(atom_id)
                break
    permissible = ref.Grants(model, [a for a in model.atom_order
                                     if a not in forbidden])
    labels = {run_id: "must_deny" for run_id in must_deny}
    candidates = sorted(forced) + [run_id for index, run_id in enumerate(rest)
                                   if index % 4 == 1]
    for run_id in candidates:
        if ref.simulate(model, run_id, permissible)["admitted"]:
            labels[run_id] = "must_admit"
    rows = []
    for index, run_id in enumerate(model.run_order, 1):
        rows.append({
            "run_id": run_id,
            "label": labels.get(run_id, "unlabelled"),
            "note": "batch{}".format(index % 20),
        })
    return rows


def emit_corpus(seed: int, outdir: Path, ref) -> dict:
    """Write the whole corpus, harmonised and then labelled from its own replay."""
    outdir = Path(outdir)
    data, plan = build_base(seed)
    write_tables(data, outdir)
    model = ref.Model(ref.Corpus(outdir))
    harmonise(ref, model, data, plan, seed)
    write_tables(data, outdir)
    model = ref.Model(ref.Corpus(outdir))
    data["grant-atoms"] = derive_atoms(ref, model, seed)
    write_tables(data, outdir, only={"grant-atoms"})
    model = ref.Model(ref.Corpus(outdir))
    data["runs-labels"] = derive_labels(ref, model, plan)
    write_tables(data, outdir, only={"runs-labels"})
    settle_spellings(ref, data, outdir, seed)
    plant_cost_controls(ref, data, outdir, seed)
    return {"files": len(LAYOUT)}


def plant_cost_controls(ref, data, outdir, seed):
    """Calibration controls for the two hidden cost multipliers.

    The first control relates the two multipliers by one equation that two
    pairs in the range satisfy, the third restates it at twice the scale, the
    second involves only kinds whose multiplier is one, a repeated control
    identifier in the later shard carries a total that matches no pair (the
    first record stands), and one control names an atom the catalogue does not
    carry (it is set aside). Which of the two consistent pairs is the answer
    is decided by the settled plan each produces, as SPEC section 9 states.
    """
    outdir = Path(outdir)
    model = ref.Model(ref.Corpus(outdir))
    by_kind = {}
    for atom_id in model.atom_order:
        by_kind.setdefault(model.atoms[atom_id]["kind"], []).append(atom_id)
    def pick(kind, offset):
        pool = by_kind.get(kind, [])
        return pool[(offset * 7 + seed) % len(pool)] if pool else None
    first, second = ((2, 4), (1, 4))[seed % 2]
    base = lambda a: model.atoms[a]["cost"]
    b1, b2, b3 = pick("cap_bounding_add", 1), pick("cap_bounding_add", 2), pick("cap_bounding_add", 3)
    r1, r2, r3 = pick("seccomp_rule_add", 1), pick("seccomp_rule_add", 2), pick("seccomp_rule_add", 3)
    p1 = pick("pam_control_relax", 1)
    d1, u1 = pick("seccomp_default_relax", 1), pick("filter_unload", 1)
    t1 = pick("te_allow_add", 4)
    total1 = base(b1) * first + base(r1) * second + base(p1)
    total2 = base(d1) + base(u1)
    group3 = sorted({b2, b3, r2, r3, t1})
    total3 = sum(base(a) * {"cap_bounding_add": first, "seccomp_rule_add": second}.get(
        model.atoms[a]["kind"], 1) for a in group3)
    def producer(atom_id):
        return atom_id.lower().replace("-", "_")
    shard_a = [
        {"control_id": "ctl_0001", "atoms": "|".join(sorted({b1, r1, p1})),
         "total": total1, "note": "replayed quote"},
        {"control_id": "ctl_0002", "atoms": "|".join(sorted({d1, u1})),
         "total": total2, "note": "replayed quote"},
    ]
    shard_b = [
        {"control_id": "ctl_0003", "atoms": "|".join(producer(a) for a in group3),
         "total": total3, "note": "replayed quote"},
        {"control_id": "CTL-0002", "atoms": "|".join(sorted({d1, u1})),
         "total": total2 + 1, "note": "requoted"},
        {"control_id": "ctl_0004", "atoms": "|".join(sorted({b1, "ATM-9999"})),
         "total": 1, "note": "withdrawn atom"},
    ]
    data["cost-controls"] = shard_a + shard_b
    _write_rows(outdir, "cost-controls-a.csv", shard_a)
    _write_rows(outdir, "cost-controls-b.jsonl", shard_b)


# ------------------------------------------------------------------ spellings

STALE_NOTE = "superseded"


def _layout_entry(name):
    for entry in LAYOUT:
        if entry[0] == name:
            return entry
    raise KeyError(name)


def _write_rows(outdir, name, rows):
    _, fmt, table, fields, index, total = _layout_entry(name)
    (outdir / name).write_text(WRITERS[fmt](rows, fields), encoding="utf-8",
                               newline="\n")


def _producer_id(text):
    return str(text).strip().lower().replace("-", "_")


def _shout_type(text):
    return str(text).strip().upper().replace("_", "-")


def settle_spellings(ref, data, outdir, seed):
    """Spell a slice of the corpus in the other forms the contract accepts.

    Nothing here changes what the corpus says under the contract: every edit
    is either a spelling section 2 canonicalises, a commentary element, or a
    record the identity rules of section 3 set aside. The reference model is
    built before and after, and the solved artifacts must not move.
    """
    outdir = Path(outdir)
    before = ref.solve(outdir).files

    # Relabelling batches. The labels group is the one group whose later shard
    # supersedes the earlier one, so the earlier shard carries a stale label
    # for a slice of the runs the later shard labels, written in producer form.
    labels = data["runs-labels"]
    halves = shard(labels, 2)
    model = ref.Model(ref.Corpus(outdir))
    empty = ref.Grants(model, ())
    solver_initial = {run_id: ref.simulate(model, run_id, empty)
                      for run_id in model.run_order}
    stale = []
    for position, row in enumerate(halves[1]):
        if position % 4 != 1:
            continue
        run_id = row["run_id"]
        label = row["label"]
        denied = not solver_initial[run_id]["admitted"]
        if label == "must_admit":
            old = "unlabelled" if position % 8 == 1 else "must_deny"
        elif label == "must_deny":
            old = "must_admit" if position % 8 == 1 else "unlabelled"
        elif denied:
            old = "must_deny" if position % 8 == 1 else "must_admit"
        else:
            old = "must_admit"
        stale.append({"run_id": _producer_id(run_id), "label": old,
                      "note": STALE_NOTE})
    _write_rows(outdir, "runs-labels-a.csv", halves[0] + stale)

    # PAM returns: a later shard repeats a slice of the keys an earlier shard
    # already answered, with a different code. The first record read wins.
    returns = data["pam-returns"]
    thirds = shard(returns, 3)
    repeats = []
    for position, row in enumerate(thirds[0]):
        if position % 23 != 5:
            continue
        code = row["code"]
        other = "success" if code != "success" else "perm_denied"
        repeats.append({"run_id": _producer_id(row["run_id"]).upper(),
                        "phase": row["phase"], "module": row["module"],
                        "code": other})
    _write_rows(outdir, "pam-returns-c.ssv", thirds[2] + repeats)

    # The advisory capability: a capability is advisory when at least one
    # record marks it so, whatever the other records naming it say, and a
    # record may name it by bit index or in lower case.
    required = data["cap-required"]
    halves = shard(required, 2)
    for position, row in enumerate(halves[0]):
        if row["capability"] == "CAP_AUDIT_WRITE" and position % 2 == 1:
            row["capability"] = "29" if position % 4 == 1 else "cap_audit_write"
    extra = []
    for number in range(6):
        extra.append({
            "op_id": "op_{:04d}".format(len(required) + 1 + number),
            "operation": "audit_replay_{:03d}".format(len(required) + 1 + number),
            "capability": ("CAP_AUDIT_WRITE", "29", "cap_audit_write")[number % 3],
            "advisory": "no",
            "note": "relay",
        })
    _write_rows(outdir, "cap-required-a.tsv", halves[0])
    _write_rows(outdir, "cap-required-b.psv", halves[1] + extra)

    # Type names in the policy spelled in the shouted form for a slice.
    allow = data["selinux-allow"]
    for position, row in enumerate(allow):
        if position % 11 == 6:
            row["source"] = _shout_type(row["source"])
        if position % 13 == 9:
            row["target"] = _shout_type(row["target"])
    write_tables(data, outdir, only={"selinux-allow"})
    for position, row in enumerate(data["selinux-transition"]):
        if position % 9 == 4:
            row["exec_type"] = _shout_type(row["exec_type"])
            row["new_domain"] = _shout_type(row["new_domain"])
    write_tables(data, outdir, only={"selinux-transition"})

    # Atom targets: some elements in producer form, and on the atoms that
    # matter a note that carries semicolons and key=value text of its own.
    solved = ref.solve(outdir)
    plan_ids = [row["atom_id"] for row in solved.solver.plan]
    plan_ids.sort()
    marked = set(plan_ids[1::3])
    forbidden_ids = sorted(solved.solver.forbidden)
    marked |= set(forbidden_ids[2::4])
    by_id = {}
    for row in data["grant-atoms"]:
        by_id[ref.canon_id(row["atom_id"])] = row
    caps = list(ref.CAP_NAMES)
    filters = sorted({ref.canon_id(f) for unit in data["cap-units"]
                      for f in str(unit["filters"]).split("|") if f})
    rules = sorted({ref.canon_id(r["rule_id"]) for r in data["pam-stack"]})
    for number, atom_id in enumerate(sorted(by_id)):
        row = by_id[atom_id]
        target = row["target"]
        body, sep, note = target.partition(";note=")
        parts = []
        for chunk in body.split(";"):
            key, _, value = chunk.partition("=")
            parts.append([key, value])
        if number % 7 == 3:
            for piece in parts:
                key, value = piece
                if key in ("unit", "filter", "rule"):
                    piece[1] = _producer_id(value)
                elif key == "cap":
                    piece[1] = (str(ref.CAP_BIT[value]) if number % 2
                                else value.lower())
                elif key in ("source", "target") and number % 3 == 0:
                    piece[1] = _shout_type(value)
        body = ";".join("{}={}".format(k, v) for k, v in parts)
        if atom_id in marked:
            spec = dict(parts)
            if "cap" in spec:
                index = ref.CAP_BIT.get(ref.canon_cap(spec["cap"]), 0)
                decoy = "cap=" + caps[(index + 7) % len(caps)]
            elif "rule" in spec:
                here = ref.canon_id(spec["rule"])
                decoy = "rule=" + rules[(rules.index(here) + 5) % len(rules)] \
                    if here in rules else "rule=" + rules[0]
            elif "filter" in spec:
                here = ref.canon_id(spec["filter"])
                decoy = "filter=" + filters[(filters.index(here) + 3) % len(filters)] \
                    if here in filters else "filter=" + filters[0]
            else:
                decoy = "perm=" + ("getattr" if spec.get("perm") != "getattr" else "read")
            note = ('reviewed; the first draft of LGA-{:04d} read;{}'.format(
                1 + number, decoy))
            sep = ";note="
        row["target"] = body + (sep + note if sep else "")
    write_tables(data, outdir, only={"grant-atoms"})

    after = ref.solve(outdir).files
    moved = [name for name in before
             if name not in ("relaxation_atoms.csv", "grant_plan.csv", "manifest.json")
             and before[name] != after[name]]
    assert not moved, "a spelling moved a solved artifact: {}".format(moved)


# ------------------------------------------------------------------ harmony

def canon_type_name(text):
    return str(text).strip().lower().replace("-", "_").replace(".", "_")


def run_requirements(model, info):
    """The policy facts one recorded run needs before it can be admitted."""
    source = canon_type_name(info["source_domain"])
    exec_type = canon_type_name(info["exec_type"])
    entries = model.transitions.get((source, exec_type))
    landing = entries[0][2] if entries else source
    exec_needed = []
    if entries:
        exec_needed = [(source, exec_type, "file", "execute"),
                       (landing, exec_type, "file", "entrypoint"),
                       (source, landing, "process", "transition")]
    access_needed = []
    for target, tclass, perm in info["accesses"]:
        for piece in perm.split(","):
            access_needed.append((landing, canon_type_name(target), tclass, piece))
    audit_needed = (landing, canon_type_name(info["audit_target"]),
                    "netlink_audit_socket", "nlmsg_write")
    return exec_needed, access_needed, audit_needed


def harmonise(ref, model, data, plan, seed):
    """Make the shipped policy produce the outcome each run was designated."""
    rng = rng_for(seed, "harmony")
    background = set(model.allow)
    withheld_set = set()
    needs = {}

    pair_use = {}
    for run_id in sorted(plan):
        exec_needed, access_needed, audit_needed = run_requirements(model, plan[run_id])
        needs[run_id] = (exec_needed, access_needed, audit_needed)
        if exec_needed:
            pair_use[exec_needed[2]] = pair_use.get(exec_needed[2], 0) + 1

    for run_id in sorted(plan):
        info = plan[run_id]
        index = info["index"]
        exec_needed, access_needed, audit_needed = needs[run_id]
        if info["mode"] not in ("selinux", "chain2", "chain3"):
            continue
        if index % 2 == 0 and exec_needed:
            # Only a transition edge no other run shares may be withheld, so a
            # planted refusal never spills into a run meant to be admitted.
            slot = (index // 2) % 3
            if slot == 2 and pair_use.get(exec_needed[2], 0) != 1:
                slot = 1
            withheld_set.add(exec_needed[slot])
            continue
        picked = None
        for candidate in access_needed:
            if candidate not in background:
                picked = candidate
                break
        if picked is None and exec_needed:
            picked = exec_needed[index % 3]
        if picked is not None:
            withheld_set.add(picked)

    have = set(background)
    added = []

    def grant(source, target, tclass, perm):
        key = (source, target, tclass, perm)
        if key in have or key in withheld_set:
            return
        have.add(key)
        added.append({"source": source, "target": target, "tclass": tclass,
                      "perm": perm})

    unit_by_id = {row["unit_id"]: row for row in data["cap-units"]}
    bin_by_id = {row["binary_id"]: row for row in data["cap-filecaps"]}
    filter_rows = []
    default_rows = []
    planted = 0

    for run_id in sorted(plan):
        info = plan[run_id]
        index = info["index"]
        mode = info["mode"]
        exec_needed, access_needed, audit_needed = needs[run_id]
        for tuple_ in exec_needed + access_needed:
            grant(*tuple_)
        if rng.random() < 0.62:
            grant(*audit_needed)

        unit = unit_by_id[info["unit"]]
        binary = bin_by_id[info["binary"]]
        bounding = set(ref.cap_set(unit["bounding"]))
        ambient = set(ref.cap_set(unit["ambient"]))
        file_permitted = set(ref.cap_set(binary["permitted_file"]))
        file_inheritable = set(ref.cap_set(binary["inheritable_file"]))
        caps = list(info["caps"])
        if mode == "heavy":
            blocked, granted = caps, []
        elif mode in ("capability", "chain2", "chain3"):
            blocked, granted = caps[:1], caps[1:]
        else:
            blocked, granted = [], caps
        for name in granted:
            bounding.add(name)
            ambient.add(name)
        for name in blocked:
            bounding.discard(name)
            ambient.discard(name)
            file_inheritable.discard(name)
            if index % 2 == 0 or mode == "heavy":
                file_permitted.discard(name)
        if rng.random() < 0.58:
            bounding.add("CAP_AUDIT_WRITE")
            ambient.add("CAP_AUDIT_WRITE")
        else:
            bounding.discard("CAP_AUDIT_WRITE")
            ambient.discard("CAP_AUDIT_WRITE")
            file_inheritable.discard("CAP_AUDIT_WRITE")
            file_permitted.discard("CAP_AUDIT_WRITE")
        if mode == "heavy":
            # The capability appendix spells an empty set as the literal NONE
            # in both the permitted and the effective column, and no run used
            # to reach it because the sets always kept some background
            # capability. The heavy runs already lose every capability they
            # use; now they hold nothing at all, on every one of the four
            # inputs the derivation reads, so both columns render NONE. Unit
            # and binary are each named by exactly one run, so nothing spills.
            bounding.clear()
            ambient.clear()
            file_permitted.clear()
            file_inheritable.clear()
        style = ("upper", "lower", "numeric")[(index + 1) % 3]
        unit["bounding"] = cap_render(bounding, style)
        unit["ambient"] = cap_render(ambient, style)
        bin_style = ("numeric", "upper", "lower")[index % 3]
        binary["permitted_file"] = cap_render(file_permitted, bin_style)
        binary["inheritable_file"] = cap_render(file_inheritable, bin_style)

        if mode == "admit" and index % 13 == 7:
            # A private filter no defaults record declares, holding argument
            # conditions set on the exact recorded arg0 of calls this run makes
            # once each. Every refusing rule sits on the failing side of its
            # boundary and every matching rule carries a non refusing action, so
            # the run is admitted only by a reader that gets each comparison,
            # the argument index and the undeclared default exactly right. Two
            # matching rules tie on the second call, and the one earlier in idx
            # order carries the higher rule identifier.
            private = "flt_a{:04d}".format(index)
            unit["filters"] = "|".join(sorted(set(unit["filters"].split("|")) | {private}))
            seen = {}
            for position, (nr, required) in enumerate(info["syscalls"]):
                name = model.syscall_by_nr.get((info["arch"], nr))
                if name:
                    seen.setdefault(name, []).append((info["args"][position], required))
            singles = [(name, hits[0]) for name, hits in sorted(seen.items())
                       if len(hits) == 1]
            for slot, (name, (arg0, required)) in enumerate(singles[:4]):
                mask = 0xf0 + (arg0 % 7)
                rules = [
                    (("KILL_PROCESS", "LT", arg0, ""), ("LOG", "LE", arg0, "")),
                    (("KILL_THREAD", "GT", arg0, ""), ("LOG", "GE", arg0, ""),
                     ("LOG", "GE", max(arg0 - 1, 0), "")),
                    (("TRAP", "NE", arg0, ""), ("LOG", "EQ", arg0, ""),
                     ("KILL_PROCESS", "EQ", arg0, "index1")),
                    (("TRAP", "MASKED_EQ", (arg0 & mask) ^ 1, mask),
                     ("LOG", "MASKED_EQ", arg0 & mask, mask)),
                ][slot]
                if not required:
                    rules = rules + (("ERRNO", "EQ", arg0, ""),)
                for order, (action, op, value, extra) in enumerate(rules):
                    filter_rows.append({
                        "rule_id": "sec_a{:04d}".format(len(filter_rows) + 1),
                        "filter_id": private,
                        "idx": 10 if (slot == 1 and order == 2) else 20 + order,
                        "arch": info["arch"], "syscall": name,
                        "arg_index": "1" if extra == "index1" else "0",
                        "op": op, "value": str(value),
                        "mask": str(extra) if op == "MASKED_EQ" else "",
                        "action": action,
                    })

        if mode in ("seccomp", "chain3"):
            strict = "flt_{:04d}".format(1 + (index % N_STRICT))
            quiet = sorted(unit["filters"].split("|"))[0]
            unit["filters"] = "|".join(sorted({strict, quiet}))
            # A refusal can also come from a filter's own default action, and
            # section 6.4 says such a refusal names the literal NONE as its
            # rule. Nothing reached that branch while every default in the
            # corpus was ALLOW or LOG, so a rotating slice of these runs gets a
            # private filter that carries no rules and denies by default. Every
            # unit is named by exactly one run, so the filter cannot spill into
            # a run it was not meant for. The stride is eleven, coprime to the
            # twenty-long designation cycle and to the three architectures, and
            # it steps around the runs already refusing on an unknown number so
            # that each mechanism is the one that decides its own run.
            blind = index % 7 == 1
            if index % 11 == 3 and not blind:
                private = "flt_d{:04d}".format(index)
                unit["filters"] = "|".join(sorted({strict, quiet, private}))
                default_rows.append({
                    "filter_id": private,
                    "default_action": "KILL_THREAD",
                    "priority": 50,
                })
                continue
            target_nr = None
            for nr, required in info["syscalls"]:
                if required:
                    target_nr = nr
                    break
            if target_nr is None and info["syscalls"]:
                target_nr = info["syscalls"][0][0]
            name = model.syscall_by_nr.get((info["arch"], target_nr))
            if name:
                # The designation cycle is twenty long and five divides
                # twenty, so index % 5 is constant inside one designation slot
                # and two of these five actions would never be planted at all.
                # A counter over the plants keeps all five reachable, and it is
                # kept separate from len(filter_rows) so the companion rule
                # below cannot shift the cycle and drop an action again.
                action = ("TRAP", "KILL_THREAD", "ERRNO", "KILL_PROCESS",
                          "USER_NOTIF")[planted % 5]
                planted += 1
                filter_rows.append({
                    "rule_id": "sec_h{:04d}".format(len(filter_rows) + 1),
                    "filter_id": strict, "idx": 90 + (index % 9),
                    "arch": info["arch"], "syscall": name, "arg_index": "",
                    "op": "", "value": "", "mask": "", "action": action,
                })
                if action == "ERRNO":
                    # ERRNO refuses a required call and allows one the run can
                    # proceed without, so the rule is only half exercised by
                    # the required event above. Give it a non-required event of
                    # the same run so the allowing half is reached too.
                    spare = None
                    for nr, required in info["syscalls"]:
                        if required:
                            continue
                        candidate = model.syscall_by_nr.get((info["arch"], nr))
                        if candidate and candidate != name:
                            spare = candidate
                            break
                    if spare:
                        filter_rows.append({
                            "rule_id": "sec_h{:04d}".format(len(filter_rows) + 1),
                            "filter_id": strict, "idx": 90 + (index % 9),
                            "arch": info["arch"], "syscall": spare,
                            "arg_index": "", "op": "", "value": "", "mask": "",
                            "action": "ERRNO",
                        })

    # A slice of the grants is written against the privileged attribute rather
    # than the one domain that needs it, so the policy admits those runs only
    # through source side attribute expansion. A grant is lifted only when the
    # expansion reaches no tuple a planted refusal withholds.
    privileged = sorted(name for name, attrs in model.type_attrs.items()
                        if "privileged" in attrs)
    for number, row in enumerate(added):
        if number % 9 != 4 or "privileged" not in model.type_attrs.get(row["source"], ()):
            continue
        spread = {(name, row["target"], row["tclass"], row["perm"]) for name in privileged}
        if spread & withheld_set:
            continue
        row["source"] = "privileged"

    grouped = {}
    for row in added:
        grouped.setdefault((row["source"], row["target"], row["tclass"]), []).append(
            row["perm"])
    allow_rows = []
    for number, key in enumerate(sorted(grouped), 1):
        allow_rows.append({
            "rule_id": "te_h{:04d}".format(number),
            "source": key[0], "target": key[1], "tclass": key[2],
            "perms": ",".join(sorted(set(grouped[key]))),
        })
    data["selinux-allow"] = data["selinux-allow"] + allow_rows
    data["seccomp-filters"] = data["seccomp-filters"] + filter_rows
    data["seccomp-defaults"] = data["seccomp-defaults"] + default_rows
    return {"allow_added": len(allow_rows), "filter_added": len(filter_rows),
            "default_added": len(default_rows)}
'''


REF = types.ModuleType("lga_ref")
exec(compile(_REF_SRC, "lga_ref", "exec"), REF.__dict__)
GEN = types.ModuleType("lga_gen")
exec(compile(_GEN_SRC, "lga_gen", "exec"), GEN.__dict__)

OUT = Path("/app/out")
SAMPLE_SEED = 20260914
EVAL_SEED = 5231180497
CHALLENGE_SEED = 1998744311

# Assembled at run time so this module carries no literal corpus path.
SHIPPED_CORPUS = "/" + "app" + "/" + "data"

ARTIFACTS = list(REF.ARTIFACT_NAMES)
TOOL_NAME = "lgactl.py"
TOOL_SOURCE = OUT / TOOL_NAME
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
# Grading invokes the delivered solver fifteen times: nine full passes (the
# sample corpus; the unseen corpus three times, as built, again and under a
# second directory name; its reversed and reduced shapes; and its three
# variants), two that only need an exit code, and four over a corpus with one
# needed group stripped. The cap is the five minutes SPEC section 14 allows
# one corpus; all fifteen at this cap sit inside the verifier timeout, so a
# slow submission is failed on its merits rather than by timing the whole
# verifier out before any score is written.
TOOL_TIMEOUT_SEC = 300


def _bind(workspace) -> None:
    global OUT, TOOL_SOURCE
    OUT = Path(str(workspace)) / "out"
    TOOL_SOURCE = OUT / TOOL_NAME


# rewardkit evaluates criteria on parallel threads. Every check shares the
# module-level caches below (built corpora, expected artifacts, solver runs and
# their output directories), and an unlocked cache lets every thread build the
# same corpus and launch the delivered solver at once, so a correct solver
# times out under load. One lock runs the checks one at a time; what each check
# asserts is unchanged.
_RUN_LOCK = threading.Lock()


def _pass(thunk):
    with _RUN_LOCK:
        try:
            thunk()
            return True
        except Exception:
            return False


_corpora: dict[str, Path] = {}
_expected: dict[str, dict] = {}
_tool_runs: dict[str, dict] = {}
_tool_dirs: dict[str, Path] = {}
_tool_codes: dict[str, int] = {}


def _tmp(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix="lga-" + prefix + "-"))
    path.chmod(0o755)
    return path


def _rewrite(root: Path, reverse: bool) -> None:
    """Reshape a corpus in place without changing what it says."""
    for name, fmt, table, fields, index, total in GEN.LAYOUT:
        path = root / name
        rows = REF.PARSERS[path.suffix](path.read_text(encoding="utf-8"))
        if reverse:
            rows.reverse()
        path.write_text(GEN.WRITERS[fmt](rows, fields), encoding="utf-8", newline="\n")


def _reduce(root: Path) -> None:
    """Drop every run dispatched on aarch64, every capability atom, every cost
    control and every syscall event.

    What is left is a valid corpus in which one architecture dispatches nothing,
    the capability refusals have no atom to repair them (so the rounds stop
    before the cap and the residuals take the other status), no control is
    usable (so both multipliers are one) and nothing is blocked (so the blocked
    system call artifact is its header line alone). The must_deny runs that
    only a system call refused are now admitted by the shipped policy, so every
    atom is forbidden and the witness is the canonically first must_deny run
    the atom alone admits (SPEC section 8); the plan is empty.
    """
    trace = []
    for name, fmt, table, fields, index, total in GEN.LAYOUT:
        if table == "runs-trace":
            path = root / name
            trace.extend(REF.PARSERS[path.suffix](path.read_text(encoding="utf-8")))
    gone = {REF.canon_id(row.get("run_id", "")) for row in trace
            if str(row.get("kind", "")).strip() == "exec"
            and str(row.get("arch", "")).strip() == "aarch64"}
    for name, fmt, table, fields, index, total in GEN.LAYOUT:
        if table not in ("runs-trace", "grant-atoms", "cost-controls"):
            continue
        path = root / name
        rows = REF.PARSERS[path.suffix](path.read_text(encoding="utf-8"))
        if table == "cost-controls":
            rows = []
        elif table == "runs-trace":
            rows = [row for row in rows
                    if REF.canon_id(row.get("run_id", "")) not in gone
                    and str(row.get("kind", "")).strip() != "syscall"]
        else:
            rows = [row for row in rows
                    if str(row.get("layer", "")).strip() != "capability"]
        path.write_text(GEN.WRITERS[fmt](rows, fields), encoding="utf-8", newline="\n")


def _tie_transitions(root: Path) -> None:
    """Give six source and executable pairs a second record at the winning rank.

    The added record carries the same rank as the pair's lowest ranked record,
    a rule identifier that sorts before it, and the other record's landing
    domain, and it is written last, in the last shard. The rank alone no longer
    decides; the rule identifier does (lga-selinux-appendix.md, "ordered by
    rank ascending and then by rule_id ascending")."""
    names = [entry[0] for entry in GEN.LAYOUT if entry[2] == "selinux-transition"]
    pairs: dict[tuple, list] = {}
    for name in names:
        path = root / name
        for row in REF.PARSERS[path.suffix](path.read_text(encoding="utf-8")):
            key = (REF.canon_type(row.get("source", "")), REF.canon_type(row.get("exec_type", "")))
            pairs.setdefault(key, []).append(row)
    added = []
    for key in sorted(pairs):
        rows = sorted(pairs[key], key=lambda row: (REF.as_int(row.get("rank"), 0),
                                                   REF.canon_id(row.get("rule_id", ""))))
        if len(rows) < 2 or len(added) >= 6:
            continue
        added.append({"rule_id": "tr_0000" + "abcdef"[len(added)],
                      "source": rows[0]["source"], "exec_type": rows[0]["exec_type"],
                      "new_domain": rows[-1]["new_domain"], "rank": rows[0]["rank"]})
    _reshard(root, names[-1], lambda rows: rows + added)


def _plant_precedence_fixtures(root: Path) -> None:
    """Records in the unseen corpus for stated precedence rules, each a case
    the contract already covers.

    - Access events naming two permissions list them in reverse alphabetical
      order; the detail sentence carries them as recorded, and where both are
      missing the reason names the alphabetically first (SPEC section 6.2;
      _plant_order_fixtures makes three such events decide a run).
    - Three runs execute a type no allow record names, behind a transition
      record, so execute and entrypoint are both missing and the reason is
      te_missing_entrypoint (lga-selinux-appendix.md).
    - Three runs leave the exec event's arch empty and two leave every arch
      empty, so the dispatch falls back to the lowest numbered event with an
      arch, or to x86_64 (SPEC section 4).
    - Three PAM phases that succeed through the flag gain a failing optional
      line, and the flag outranks the optional failure (lga-pam-appendix.md).
    - Two system calls meet two loaded filters that each answer KILL_PROCESS
      through their own rule, the first listed filter holding the rule that
      sorts later, so the rule named is the one that sorts first as text
      (lga-seccomp-appendix.md)."""
    model = REF.Model(REF.Corpus(root))
    trace_names = [entry[0] for entry in GEN.LAYOUT if entry[2] == "runs-trace"]
    order = list(model.run_order)
    odd = [run_id for run_id in order if REF.as_int(run_id.rsplit("-", 1)[-1], 0) % 2]
    orphans = {run_id: "orphan_{:03d}_exec_t".format(n + 1) for n, run_id in enumerate(odd[3:6])}
    exec_blank = set(odd[6:9])
    every_blank = [run_id for run_id in odd[9:]
                   if model.runs[run_id]["arch"] != "x86_64"][:2]

    def retrace(rows):
        for row in rows:
            run_id = REF.canon_id(row.get("run_id", ""))
            kind = str(row.get("kind", "")).strip()
            if kind == "access" and "," in str(row.get("perm", "")):
                perms = [x.strip() for x in str(row["perm"]).split(",") if x.strip()]
                row["perm"] = ",".join(sorted(perms, reverse=True))
            if run_id in orphans:
                row["exec_type"] = orphans[run_id]
                if kind == "exec":
                    row["target_type"] = orphans[run_id]
            if run_id in exec_blank and kind == "exec":
                row["arch"] = ""
            if run_id in every_blank:
                row["arch"] = ""

    for name in trace_names:
        _reshard(root, name, lambda rows: retrace(rows))
    hops = [{"rule_id": "tr_0000" + "uvw"[n], "source": model.runs[run_id]["source_domain"],
             "exec_type": exec_type, "new_domain": model.runs[run_id]["source_domain"],
             "rank": "1"} for n, (run_id, exec_type) in enumerate(sorted(orphans.items()))]
    hop_names = [entry[0] for entry in GEN.LAYOUT if entry[2] == "selinux-transition"]
    _reshard(root, hop_names[-1], lambda rows: rows + hops)

    answers = []
    for run_id in order:
        if len(answers) >= 3:
            break
        run = model.runs[run_id]
        uid = model.principals.get(run["principal"], {}).get("uid", 0)
        for phase in ("auth", "account", "session"):
            code, rule, module = REF.pam_phase(model, run, phase, None)
            if code != "success" or module:
                continue
            spare = [line for line in model.pam_lines.get((run["service"], phase), [])
                     if line["control"] == "optional"
                     and not (line["gate_uid"] and uid < REF.as_int(line["gate_uid"], 0))
                     and (run_id, phase, line["module"]) not in model.pam_returns]
            if spare:
                answers.append({"run_id": run_id, "phase": phase,
                                "module": spare[0]["module"], "code": "auth_err"})
                break
    return_names = [entry[0] for entry in GEN.LAYOUT if entry[2] == "pam-returns"]
    _reshard(root, return_names[-1], lambda rows: rows + answers)

    rules = []
    for run_id in order:
        if len(rules) >= 4:
            break
        run = model.runs[run_id]
        loaded = model.units.get(run["unit"], {}).get("filters", [])
        if len(loaded) < 2 or run_id in orphans or run_id in exec_blank or run_id in every_blank:
            continue
        for event in run["events"]:
            name = model.syscall_by_nr.get((event["arch"], event["syscall_nr"]))
            if event["kind"] == "syscall" and name:
                tag = "ab" if not rules else "cd"
                for filter_id, letter in ((loaded[0], tag[1]), (loaded[1], tag[0])):
                    rules.append({"rule_id": "sec_0000" + letter, "filter_id": filter_id,
                                  "idx": "0", "arch": event["arch"], "syscall": name,
                                  "arg_index": "", "op": "", "value": "", "mask": "",
                                  "action": "KILL_PROCESS"})
                break
    filter_names = [entry[0] for entry in GEN.LAYOUT if entry[2] == "seccomp-filters"]
    _reshard(root, filter_names[-1], lambda rows: rows + rules)


def _group_names(group: str) -> list:
    return [entry[0] for entry in GEN.LAYOUT if entry[2] == group]


def _plant_order_fixtures(root: Path) -> None:
    """More records in the unseen corpus, each making one stated ordering or
    precedence rule decide an output.

    - Rank before rule identifier: six source and executable pairs gain a
      record ranked below the pair's winner whose rule identifier sorts after
      every other, landing elsewhere (SPEC section 6.2).
    - The access refusal names the alphabetically first missing permission:
      three runs that pass PAM and the exec event have their first access
      event name two permissions no allow record grants, listed in reverse
      alphabetical order (SPEC section 6.2).
    - te_missing_ names the alphabetically first of execute and transition:
      two runs execute a type whose landing domain may enter it but which the
      source may neither execute nor transition to (SPEC section 6.2).
    - Dispatch architecture: three runs record their pam events under an
      architecture other than their exec event's, and three leave the exec
      arch empty while their pam events carry an architecture other than
      their later events' (SPEC section 4).
    - First recorded failure and first optional failure: a phase in which
      nothing spoke gains two failing required lines, and another two failing
      optional lines, with different codes (lga-pam-appendix.md).
    - First record wins: one later-shard record repeats the key of an earlier
      record, with different content, in each of principals, cap-units,
      cap-filecaps, seccomp-defaults, arch-syscalls and grant-atoms
      (SPEC section 3).
    - Advisory with at least one yes: a cap-required record marking
      CAP_AUDIT_WRITE `no` is written first (lga-capability-appendix.md).
    - One system call table entry and one type that only the unseen corpus
      carries, so its system call index and type graph are its own."""
    model = REF.Model(REF.Corpus(root))
    empty = REF.Grants(model, ())
    solver_initial = {run_id: REF.simulate(model, run_id, empty) for run_id in model.run_order}
    odd = [run_id for run_id in model.run_order
           if REF.as_int(run_id.rsplit("-", 1)[-1], 0) % 2]
    pool = odd[20:]

    # rank before rule identifier
    pairs = {}
    for name in _group_names("selinux-transition"):
        path = root / name
        for row in REF.PARSERS[path.suffix](path.read_text(encoding="utf-8")):
            key = (REF.canon_type(row["source"]), REF.canon_type(row["exec_type"]))
            pairs.setdefault(key, []).append(row)
    hops = []
    for key in sorted(pairs):
        rows = sorted(pairs[key], key=lambda r: (REF.as_int(r["rank"], 0), REF.canon_id(r["rule_id"])))
        if len(rows) < 2 or REF.as_int(rows[0]["rank"], 0) < 2 or len(hops) >= 6:
            continue
        hops.append({"rule_id": "tr_9999" + "abcdef"[len(hops)], "source": rows[0]["source"],
                     "exec_type": rows[0]["exec_type"], "new_domain": rows[-1]["new_domain"],
                     "rank": str(REF.as_int(rows[0]["rank"], 0) - 1)})

    # runs that pass PAM and the exec event
    clean = [run_id for run_id in pool
             if solver_initial[run_id]["layer"] in (REF.NONE_TOKEN, "capability", "seccomp")]
    deny_two = set(clean[:3])
    arch_exec = set(clean[3:6])
    arch_blank = set(clean[6:9])
    domains = sorted(model.attr_types.get("domain", ()))
    entry_only = {}
    for run_id in clean[9:]:
        if len(entry_only) >= 2:
            break
        source = model.runs[run_id]["source_domain"]
        landing = next((d for d in domains if d != source and not REF.allowed(
            model, None, source, d, "process", "transition")), None)
        if landing:
            entry_only[run_id] = ("entry_{:03d}_exec_t".format(len(entry_only) + 1), landing)
    other = {"x86_64": "i386", "i386": "aarch64", "aarch64": "x86_64"}

    def retrace(rows):
        first_access = {}
        for row in sorted(rows, key=lambda r: (REF.canon_id(r.get("run_id", "")),
                                               REF.as_int(r.get("seq"), 0))):
            run_id = REF.canon_id(row.get("run_id", ""))
            if str(row.get("kind", "")).strip() == "access" and run_id not in first_access:
                first_access[run_id] = id(row)
        for row in rows:
            run_id = REF.canon_id(row.get("run_id", ""))
            kind = str(row.get("kind", "")).strip()
            if run_id in deny_two and kind == "access" and first_access.get(run_id) == id(row):
                row["perm"] = "swapon,mounton"
            if run_id in arch_exec and kind == "pam":
                row["arch"] = other[model.runs[run_id]["arch"]]
            if run_id in arch_blank:
                if kind == "exec":
                    row["arch"] = ""
                elif kind == "pam":
                    row["arch"] = other[model.runs[run_id]["arch"]]
            if run_id in entry_only:
                row["exec_type"] = entry_only[run_id][0]
                if kind == "exec":
                    row["target_type"] = entry_only[run_id][0]

    # a run's access events may sit in any shard: find the first one per run
    # across every shard before editing
    shards = {name: REF.PARSERS[(root / name).suffix]((root / name).read_text(encoding="utf-8"))
              for name in _group_names("runs-trace")}
    every = [row for rows in shards.values() for row in rows]
    retrace(every)
    for name in _group_names("runs-trace"):
        _reshard(root, name, lambda rows, name=name: shards[name])

    hops += [{"rule_id": "tr_0000" + "xy"[n], "source": model.runs[run_id]["source_domain"],
              "exec_type": exec_type, "new_domain": landing, "rank": "1"}
             for n, (run_id, (exec_type, landing)) in enumerate(sorted(entry_only.items()))]
    _reshard(root, _group_names("selinux-transition")[-1], lambda rows: rows + hops)
    grants = [{"rule_id": "te_99" + str(n), "source": landing, "target": exec_type,
               "tclass": "file", "perms": "entrypoint"}
              for n, (exec_type, landing) in enumerate(sorted(entry_only.values()))]
    _reshard(root, _group_names("selinux-allow")[-1], lambda rows: rows + grants)

    # first recorded failure, first optional failure
    answers = []
    wants = ["required", "optional"]
    for run_id in pool:
        if not wants:
            break
        run = model.runs[run_id]
        uid = model.principals.get(run["principal"], {}).get("uid", 0)
        for phase in ("auth", "account", "session"):
            lines = [line for line in model.pam_lines.get((run["service"], phase), [])
                     if not (line["gate_uid"] and uid < REF.as_int(line["gate_uid"], 0))]
            if not wants or any((run_id, phase, line["module"]) in model.pam_returns
                                for line in lines):
                continue
            picked = [line for line in lines if line["control"] == wants[0]][:2]
            if len(picked) == 2:
                for line, code in zip(picked, ("auth_err", "perm_denied")):
                    answers.append({"run_id": run_id, "phase": phase,
                                    "module": line["module"], "code": code})
                wants.pop(0)
                break
    _reshard(root, _group_names("pam-returns")[-1], lambda rows: rows + answers)

    # first record wins for six more keyed groups
    changes = {
        "principals": ("principal_id", lambda r: r.update(uid=str(REF.as_int(r["uid"], 0) + 7000))),
        "cap-units": ("unit_id", lambda r: r.update(bounding="none")),
        "cap-filecaps": ("binary_id", lambda r: r.update(
            effective_bit="0" if str(r["effective_bit"]).strip() == "1" else "1")),
        "seccomp-defaults": ("filter_id", lambda r: r.update(default_action="KILL_PROCESS")),
        "arch-syscalls": ("arch", lambda r: r.update(syscall="shadowed_call")),
        "grant-atoms": ("atom_id", lambda r: r.update(cost="999")),
    }
    for group, (key, change) in changes.items():
        names = _group_names(group)
        first = REF.PARSERS[(root / names[0]).suffix]((root / names[0]).read_text(encoding="utf-8"))
        repeat = dict(first[0])
        change(repeat)
        _reshard(root, names[-1], lambda rows, repeat=repeat: rows + [repeat])

    # rows only the unseen corpus carries, so its system call index and type
    # graph differ from the shipped ones
    _reshard(root, _group_names("arch-syscalls")[-1], lambda rows: rows + [
        {"arch": "aarch64", "nr": "899", "syscall": "eval_only_call", "note": "abi9"}])
    _reshard(root, _group_names("selinux-types")[-1], lambda rows: rows + [
        {"type_name": "eval_only_t", "attributes": "file_type|auditable",
         "is_domain": "no", "note": "added"}])

    # advisory: a "no" record for CAP_AUDIT_WRITE read first
    required = _group_names("cap-required")
    _reshard(root, required[0], lambda rows: [{
        "op_id": "op_0000", "operation": "audit-relay", "capability": "CAP_AUDIT_WRITE",
        "advisory": "no", "note": "relay"}] + rows)


def _write_corpus(seed: int, root: Path, reverse: bool = False,
                  reduce: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    GEN.emit_corpus(seed, root, REF)
    if seed == EVAL_SEED:
        _tie_transitions(root)
        _plant_precedence_fixtures(root)
        _plant_order_fixtures(root)
    if reverse:
        _rewrite(root, reverse)
    if reduce:
        _reduce(root)
    return root


_corpus_snapshots: dict[str, dict] = {}


def _corpus_key(seed: int, tag: str = "", reverse: bool = False,
                reduce: bool = False) -> str:
    return "{}:{}:{}:{}".format(seed, tag, reverse, reduce)


def _snapshot(root: Path) -> dict:
    """Every file under one corpus directory with the digest of its bytes."""
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def corpus(seed: int, tag: str = "", reverse: bool = False,
           reduce: bool = False) -> Path:
    """Build a corpus once per shape and cache it, with a snapshot of its bytes."""
    key = _corpus_key(seed, tag, reverse, reduce)
    if key not in _corpora:
        _corpora[key] = _write_corpus(seed, _tmp("corpus"), reverse=reverse,
                                      reduce=reduce)
        _corpus_snapshots[key] = _snapshot(_corpora[key])
    return _corpora[key]


def expected(seed: int, **kwargs) -> dict[str, str]:
    """Reference artifact text for one corpus shape."""
    key = "{}:{}".format(seed, sorted(kwargs.items()))
    if key not in _expected:
        _expected[key] = REF.solve(corpus(seed, **kwargs)).files
    return _expected[key]


def delivered(name: str) -> str:
    path = OUT / name
    assert path.is_file(), "missing declared artifact {}".format(name)
    # Bytes, decoded without newline translation: a carriage return the
    # contract does not allow must not be folded away before the comparison.
    return path.read_bytes().decode("utf-8", errors="replace")


def tool_source() -> str:
    assert TOOL_SOURCE.is_file(), "missing declared artifact {}".format(TOOL_NAME)
    return TOOL_SOURCE.read_text(encoding="utf-8", errors="replace")


def untrusted(command: list[str]) -> list[str]:
    """Run submitted code as an unprivileged user when the host allows it."""
    if subprocess.run(["which", _SETPRIV[0]], capture_output=True).returncode == 0:
        for arg in command[1:]:
            if arg.endswith(".py") and os.path.isfile(arg):
                os.chmod(arg, os.stat(arg).st_mode | 0o444)  # grant read before the uid drop
        return _SETPRIV + command
    return command


_staged: dict[str, Path] = {}


def staged_tool() -> Path:
    """A world-readable copy of the delivered solver, for the unprivileged run.

    The solver is executed as nobody, and the agent may have written
    /app/out/lgactl.py with a mode only its owner can read. Grading the program
    must not depend on the file mode it happened to be saved with, so the bytes
    are copied into a fresh directory (0755) as a 0644 file and run from there.
    The delivered file itself is never modified."""
    payload = TOOL_SOURCE.read_bytes()
    key = hashlib.sha256(payload).hexdigest()
    if key not in _staged:
        home = _tmp("tool")
        home.chmod(0o755)
        target = home / TOOL_NAME
        target.write_bytes(payload)
        target.chmod(0o644)
        _staged[key] = target
    return _staged[key]


def run_untrusted(args: list[str]) -> int:
    """Run the staged solver with args in its own session and return its exit
    code. The whole process group is killed afterwards, so nothing the solver
    started outlives the check; a run past the time cap returns -1."""
    proc = subprocess.Popen(untrusted([sys.executable, str(staged_tool())] + args),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            cwd="/", start_new_session=True)
    try:
        code = proc.wait(timeout=TOOL_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        code = -1
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()
    return code


def writable_dir(prefix: str) -> Path:
    """A fresh output directory the unprivileged solver may write into."""
    path = _tmp(prefix)
    path.chmod(0o777)
    return path


def run_tool(corpus_dir: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o777)
    return run_untrusted([str(corpus_dir), str(out_dir)])


def _collect(out_dir: Path) -> dict[str, str]:
    found = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            found[path.name] = path.read_bytes().decode("utf-8", errors="replace")
    return found


def _run_key(seed: int, run_tag: str, corpus_tag: str, kwargs: dict) -> str:
    return "{}:{}:{}:{}".format(seed, run_tag, corpus_tag, sorted(kwargs.items()))


def tool_outputs(seed: int, run_tag: str = "", corpus_tag: str = "",
                 **kwargs) -> dict[str, str]:
    """Run the delivered solver on one corpus shape and cache what it wrote."""
    key = _run_key(seed, run_tag, corpus_tag, kwargs)
    if key not in _tool_runs:
        out_dir = _tmp("out")
        _tool_codes[key] = run_tool(corpus(seed, tag=corpus_tag, **kwargs), out_dir)
        _tool_dirs[key] = out_dir
        _tool_runs[key] = _collect(out_dir)
    return _tool_runs[key]


def tool_dir(seed: int, run_tag: str = "", corpus_tag: str = "", **kwargs) -> Path:
    """The directory one cached solver run wrote into."""
    tool_outputs(seed, run_tag=run_tag, corpus_tag=corpus_tag, **kwargs)
    return _tool_dirs[_run_key(seed, run_tag, corpus_tag, kwargs)]


def _first_difference(got: str, want: str) -> str:
    got_lines, want_lines = got.splitlines(), want.splitlines()
    for index in range(max(len(got_lines), len(want_lines))):
        left = got_lines[index] if index < len(got_lines) else "<absent>"
        right = want_lines[index] if index < len(want_lines) else "<absent>"
        if left != right:
            return "line {}: delivered {!r} against required {!r}".format(
                index + 1, left[:160], right[:160])
    return "no line differs but the bytes do; check the trailing newline"


def check_artifact(name: str) -> None:
    """One whole artifact must equal the artifact the contract defines, both as
    delivered for the shipped corpus and as the delivered solver rebuilds it
    on the unseen corpus: the plan and the solver stand or fall together."""
    got = delivered(name)
    want = expected(SAMPLE_SEED)[name]
    assert got == want, "{} does not match the contract: {}".format(
        name, _first_difference(got, want))
    fresh = tool_outputs(EVAL_SEED).get(name, "")
    want_fresh = expected(EVAL_SEED)[name]
    assert fresh == want_fresh, "{} rebuilt on the unseen corpus differs: {}".format(
        name, _first_difference(fresh, want_fresh))


_variants: dict[str, Path] = {}


def _reshard(root: Path, name: str, edit) -> None:
    """Parse one shard of a variant, let edit change its rows, write it back."""
    entries = {entry[0]: entry for entry in GEN.LAYOUT}
    _, fmt, _, fields, _, _ = entries[name]
    path = root / name
    rows = REF.PARSERS[path.suffix](path.read_text(encoding="utf-8"))
    rows = edit(rows) or rows
    path.write_text(GEN.WRITERS[fmt](rows, fields), encoding="utf-8", newline="\n")


def _encoding_features(root: Path) -> None:
    """Every line-level feature the encodings appendix allows, one shard set
    each: a byte order mark, carriage return line endings, newlines inside
    quoted comma separated fields, and blank lines (empty, or holding only
    spaces, as the glossary fixes the term) between records."""
    for name in ("principals-b.tsv", "cap-units-a.toml"):
        target = root / name
        target.write_bytes(b"\xef\xbb\xbf" + target.read_bytes())
    for name in ("cap-units-c.csv", "arch-syscalls-b.tsv", "pam-stack-c.logfmt"):
        target = root / name
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))

    def displays(rows):
        for row in rows[2::40]:
            row["display"] = row["display"] + "\n" + "Vault Operations"

    def targets(rows):
        for row in rows:
            if ";note=" in row["target"]:
                row["target"] = row["target"] + "\nsecond review"

    _reshard(root, "principals-a.csv", displays)
    _reshard(root, "grant-atoms-a.csv", targets)
    for name in ("arch-syscalls-a.csv", "arch-syscalls-c.fixed", "runs-trace-d.csv",
                 "selinux-allow-b.tsv"):
        target = root / name
        lines = target.read_text(encoding="utf-8").split("\n")
        spaced = []
        for index, line in enumerate(lines):
            spaced.append(line)
            if line and index % 50 == 7:
                spaced.append("" if index % 100 == 7 else "   ")
        target.write_text("\n".join(spaced), encoding="utf-8", newline="\n")


def _audit_before_exec(root: Path) -> None:
    """Every even numbered run records its audit event straight after its last
    pam event, ahead of its exec event, with the seq numbers renumbered so they
    still start at one and have no gaps. Nothing else in the corpus moves."""
    names = [entry[0] for entry in GEN.LAYOUT if entry[2] == "runs-trace"]
    shards = {}
    by_run: dict[str, list] = {}
    for name in names:
        path = root / name
        shards[name] = REF.PARSERS[path.suffix](path.read_text(encoding="utf-8"))
        for row in shards[name]:
            by_run.setdefault(REF.canon_id(row.get("run_id", "")), []).append(row)
    for run_id, events in by_run.items():
        if REF.as_int(run_id.rsplit("-", 1)[-1], 1) % 2:
            continue
        events.sort(key=lambda row: REF.as_int(row.get("seq"), 0))
        audit = [row for row in events if str(row.get("kind", "")).strip() == "audit"]
        execs = [row for row in events if str(row.get("kind", "")).strip() == "exec"]
        if not audit or not execs:
            continue
        order = [row for row in events if row is not audit[0]]
        order.insert(order.index(execs[0]), audit[0])
        for seq, row in enumerate(order, 1):
            row["seq"] = str(seq)
    for name in names:
        _reshard(root, name, lambda rows, name=name: shards[name])


def _control_repeats_an_atom(root: Path) -> None:
    """One more cost control, naming a single cap_bounding_add atom twice, once
    in producer form and once in canonical form, with three times that atom's
    base cost as its total. The control names a set of one atom, so it holds
    exactly when the cap_bounding_add multiplier is three, which leaves (3, 1)
    as the one consistent pair of the unseen corpus where the plan-cost
    tie-break alone would keep (1, 4)."""
    model = REF.Model(REF.Corpus(root))
    pool = [atom_id for atom_id in model.atom_order
            if model.atoms[atom_id]["kind"] == "cap_bounding_add"]
    atom_id = pool[len(pool) // 3]
    producer = atom_id.lower().replace("-", "_")

    def extend(rows):
        rows.append({"control_id": "ctl_0005", "atoms": producer + "|" + atom_id,
                     "total": str(3 * model.atoms[atom_id]["cost"]),
                     "note": "replayed quote"})

    _reshard(root, "cost-controls-b.jsonl", extend)


VARIANT_BUILDERS = {
    "encodings": _encoding_features,
    "audit": _audit_before_exec,
    "controls": _control_repeats_an_atom,
}


def variant_corpus(kind: str) -> Path:
    """The unseen corpus reshaped one way the contract allows.

    encodings: the line-level encoding features of the encodings appendix,
    each on its own shards, saying exactly what the unseen corpus says.
    audit: half the runs record their audit event before their exec event.
    controls: one added cost control names one atom in two spellings."""
    if kind in _variants:
        return _variants[kind]
    root = _tmp("variant-" + kind)
    for path in sorted(corpus(EVAL_SEED).iterdir()):
        if path.is_file():
            shutil.copy2(path, root / path.name)
    VARIANT_BUILDERS[kind](root)
    _variants[kind] = root
    return root


def check_variant(kind: str) -> None:
    """Every artifact the solver writes on a variant must equal the reference."""
    root = variant_corpus(kind)
    key = "variant:" + kind
    if key not in _expected:
        _expected[key] = REF.solve(root).files
    want = _expected[key]
    if key not in _tool_runs:
        out_dir = _tmp("out-" + kind)
        run_tool(root, out_dir)
        _tool_runs[key] = _collect(out_dir)
    got = _tool_runs[key]
    # Only the variant feature is graded here: an artifact the solver already
    # gets wrong on the plain unseen corpus is charged by the regeneration
    # check, not again by every variant.
    plain, plain_want = tool_outputs(EVAL_SEED), expected(EVAL_SEED)
    # The variant must move something the solver got right on the plain
    # corpus: an artifact whose expected bytes differ between the two, so
    # output that ignores the corpus can never satisfy this check.
    moved = [name for name in ARTIFACTS
             if name != "manifest.json" and want[name] != plain_want[name]]
    assert any(plain.get(name) == plain_want[name] for name in moved), (
        "{} variant: no artifact it moves is right on the plain corpus".format(kind))
    # Then every artifact the solver gets right on the plain corpus must stay
    # right on the variant; one it already gets wrong is charged elsewhere.
    wrong = [name for name in ARTIFACTS
             if plain.get(name) == plain_want[name] and got.get(name) != want[name]]
    assert not wrong, "{} variant mismatch on {}: {}".format(
        kind, wrong[:3], _first_difference(got.get(wrong[0], ""), want[wrong[0]]))


def _impl_test_reads_encoding_features():
    """POSITIVE: shards that open with a byte order mark, end their lines in a
    carriage return and a newline, hold a newline inside a quoted comma
    separated field, or carry blank lines between records read like any other
    (lga-encodings-appendix.md and the glossary entry for a blank line)."""
    check_variant("encodings")


def _impl_test_audit_event_before_exec():
    """POSITIVE: a run whose audit event is recorded ahead of its exec event is
    judged against the domain the exec event left the process in, which is
    what the domain in force is (lga-selinux-appendix.md, SPEC section 11)."""
    check_variant("audit")


def _impl_test_cost_control_names_a_set():
    """POSITIVE: a cost control that lists one atom in two spellings names a
    set holding that atom once (SPEC sections 2, 3 and 9.1), so the control
    pins the cap_bounding_add multiplier and the plan settles under the one
    consistent pair."""
    check_variant("controls")


def _impl_test_artifacts_written_by_delivered_solver():
    """POSITIVE: the delivered lgactl.py, run on the corpus the agent was given,
    writes every one of the twenty four delivered artifacts byte for byte, so
    the program delivered is the program that wrote the plan beside it and no
    artifact was rewritten by hand afterwards."""
    tool_source()
    rerun = tool_outputs(SAMPLE_SEED)
    differ = [name for name in ARTIFACTS
              if not (OUT / name).is_file() or rerun.get(name) != delivered(name)]
    assert not differ, "the delivered solver does not write the delivered {}".format(differ[:3])


def _impl_test_artifact_principal_registry():
    """POSITIVE: the principal registry, including the disposition each principal ends in."""
    check_artifact("principal_registry.jsonl")


def _impl_test_artifact_syscall_index():
    """POSITIVE: the resolved system call index across the three architectures."""
    check_artifact("syscall_index.tsv")


def _impl_test_artifact_pam_stack_resolved():
    """POSITIVE: the PAM stack in walk order with its gates recorded."""
    check_artifact("pam_stack_resolved.csv")


def _impl_test_artifact_selinux_type_graph():
    """POSITIVE: the type and attribute graph with its key order preserved."""
    check_artifact("selinux_type_graph.json")


def _impl_test_artifact_seccomp_program():
    """POSITIVE: the normalised filter program with resolved numbers and ranks."""
    check_artifact("seccomp_program.jsonl")


def _impl_test_artifact_pam_verdicts():
    """POSITIVE: the per phase PAM outcome and the line that decided it."""
    check_artifact("pam_verdicts.csv")


def _impl_test_artifact_capability_ledger():
    """POSITIVE: the permitted and effective capability sets of every run."""
    check_artifact("capability_ledger.csv")


def _impl_test_artifact_domain_transitions():
    """POSITIVE: the domain each exec lands in and the three checks it needed."""
    check_artifact("domain_transitions.tsv")


def _impl_test_artifact_seccomp_decisions():
    """POSITIVE: the action the filter stack returns for every recorded call."""
    check_artifact("seccomp_decisions.jsonl")


def _impl_test_artifact_arch_dispatch():
    """POSITIVE: the per architecture dispatch counts including the repairs."""
    check_artifact("arch_dispatch.tsv")


def _impl_test_artifact_admission_ledger():
    """POSITIVE: the admission verdict of every run in the bound order."""
    check_artifact("admission_ledger.csv")


def _impl_test_artifact_denial_attribution():
    """POSITIVE: the rule and the sentence behind every refusal."""
    check_artifact("denial_attribution.jsonl")


def _impl_test_artifact_blocked_syscalls():
    """POSITIVE: the blocked calls ordered by the round that first reached them."""
    check_artifact("blocked_syscalls.tsv")


def _impl_test_artifact_capability_gaps():
    """POSITIVE: the capability gaps with the signed origin of each."""
    check_artifact("capability_gaps.csv")


def _impl_test_artifact_audit_continuity():
    """POSITIVE: the audit continuity of every run and the reason it broke."""
    check_artifact("audit_continuity.jsonl")


def _impl_test_artifact_relaxation_atoms():
    """POSITIVE: the atom catalogue with its repair counts and forbidden marks."""
    check_artifact("relaxation_atoms.csv")


def _impl_test_artifact_forbidden_atoms():
    """POSITIVE: the atoms a run the site refuses would be admitted by."""
    check_artifact("forbidden_atoms.tsv")


def _impl_test_artifact_grant_plan():
    """POSITIVE: the grant plan in round, cost and identifier order."""
    check_artifact("grant_plan.csv")


def _impl_test_artifact_iteration_trace():
    """POSITIVE: the round by round record of the fixed point."""
    check_artifact("iteration_trace.jsonl")


def _impl_test_artifact_minimality_witness():
    """POSITIVE: a necessity witness for every atom the plan keeps."""
    check_artifact("minimality_witness.csv")


def _impl_test_artifact_residual_denials():
    """POSITIVE: the runs the plan leaves refused and the status of each."""
    check_artifact("residual_denials.tsv")


def _impl_test_artifact_conservation():
    """POSITIVE: the conservation record closing over the whole population."""
    check_artifact("conservation.json")


def _impl_test_artifact_summary():
    """POSITIVE: the summary record with its five repair counts."""
    check_artifact("summary.json")


def _impl_test_regenerates_on_reduced_corpus():
    """POSITIVE: the delivered solver rebuilds every artifact on the unseen
    corpus with one architecture's runs and every capability atom removed,
    which reaches the zero row and the early stop the shipped corpus never
    shows (instruction: an architecture that dispatched no event still
    carries its row; SPEC section 9: unrepairable residuals)."""
    fresh = tool_outputs(EVAL_SEED, reduce=True)
    want = expected(EVAL_SEED, reduce=True)
    wrong = [name for name in ARTIFACTS if fresh.get(name) != want[name]]
    assert not wrong, "reduced corpus mismatch on {}: {}".format(
        wrong[:3], _first_difference(fresh.get(wrong[0], ""), want[wrong[0]]) if wrong else "")


def _impl_test_contract_and_exit_codes():
    """POSITIVE: the solver honours the exit codes its contract states: zero
    when every artifact is written, two for a wrong argument count or an
    absent corpus, three for a present corpus with a needed group empty."""
    produced = tool_outputs(EVAL_SEED)
    written = _tool_codes[_run_key(EVAL_SEED, "", "", {})]
    assert written == 0 and all(name in produced for name in ARTIFACTS), (
        "a run that writes every artifact must exit 0, got {}".format(written))
    bad_args = run_untrusted([])
    assert bad_args == 2, "a call with no arguments must exit 2, got {}".format(bad_args)
    absent = run_untrusted(["/nonexistent-corpus", str(writable_dir("void"))])
    assert absent == 2, "an absent corpus must exit 2, got {}".format(absent)
    # A corpus that is present but missing a group the solver needs is the
    # third exit code, and it is a different condition from an absent corpus.
    # SPEC section 14 names four needed groups; each is stripped in turn.
    for group in ("runs-trace", "selinux-allow", "cap-units", "grant-atoms"):
        stripped = _tmp("stripped")
        for path in sorted(corpus(EVAL_SEED).iterdir()):
            if path.is_file() and not path.name.startswith(group + "-"):
                shutil.copy2(path, stripped / path.name)
        empty_group = run_untrusted([str(stripped), str(writable_dir("void-group"))])
        assert empty_group == 3, "a corpus whose {} group is empty must exit 3, got {}".format(
            group, empty_group)


def solver_present() -> bool:
    """The delivered solver exists and writes the artifacts it declares.

    Every control that compares two runs has to establish this first. Two runs
    of a solver that is absent both produce nothing, and nothing equals
    nothing, so a control without this guard fires on an empty container and
    charges its penalty to a submission that made no claim at all.
    """
    if not TOOL_SOURCE.is_file():
        return False
    produced = tool_outputs(EVAL_SEED)
    return all(name in produced for name in ARTIFACTS)


def declared(outputs: dict) -> dict:
    """The declared files of one run; anything else is the business of the
    undeclared-files control alone."""
    return {name: text for name, text in outputs.items() if name in ARTIFACTS + [TOOL_NAME]}


def repeats_itself() -> bool:
    """Two runs over one corpus directory, compared."""
    return declared(tool_outputs(EVAL_SEED)) == declared(tool_outputs(EVAL_SEED, run_tag="again"))


def filename_stable() -> bool:
    """The same bytes under a second directory name, compared."""
    return declared(tool_outputs(EVAL_SEED)) == declared(
        tool_outputs(EVAL_SEED, corpus_tag="renamed"))


def memorises() -> bool:
    """The shipped corpus reproduces whole while the fresh corpus, fully
    written, comes out wrong on at least twenty of the twenty four artifacts."""
    shipped = tool_outputs(SAMPLE_SEED)
    want_shipped = expected(SAMPLE_SEED)
    fresh = tool_outputs(EVAL_SEED)
    want_fresh = expected(EVAL_SEED)
    shipped_ok = all(shipped.get(name) == want_shipped[name] for name in ARTIFACTS)
    # A program that writes nothing on the fresh corpus may simply have
    # crashed there; it already loses every check that reads the fresh
    # corpus, so only a fully written, broadly wrong fresh run is a memoriser.
    fresh_written = all(name in fresh for name in ARTIFACTS)
    fresh_wrong = sum(1 for name in ARTIFACTS if fresh.get(name) != want_fresh[name])
    return shipped_ok and fresh_written and fresh_wrong >= 20


def _impl_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when the shipped corpus reproduces whole while the fresh
    corpus comes out wrong on at least twenty of the twenty four artifacts.

    A solver with one edge case wrong on the fresh corpus loses the positive
    test and is not a memoriser; only a solver whose fresh output is broken
    nearly everywhere while its shipped output is perfect is replaying a
    remembered answer."""
    assert memorises(), ("the solver generalises past the shipped corpus")


def _impl_negative_weight_embeds_shipped_corpus_path():
    """NEGATIVE: fires when the delivered solver carries the shipped corpus path
    as a string value its own code can read.

    Docstrings are excluded, and so is any string that only mentions the path in
    passing, such as a usage line. The instruction hands the agent the path
    /app/data, so an honest solver is free to name it in text; what it may not
    do is hold a string that is the path, or a path under it, as a value.
    """
    tree = ast.parse(tool_source())
    docstrings = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)) or not body:
            continue
        head = body[0]
        if (isinstance(head, ast.Expr) and isinstance(head.value, ast.Constant)
                and isinstance(head.value.value, str)):
            docstrings.add(id(head.value))
    usable = [node.value for node in ast.walk(tree)
              if isinstance(node, ast.Constant)
              and isinstance(node.value, str) and id(node) not in docstrings]
    assert any(text.strip().rstrip("/") == SHIPPED_CORPUS
               or text.strip().startswith(SHIPPED_CORPUS + "/") for text in usable), (
        "the solver reads only the corpus directory it is handed")


def _impl_negative_weight_output_depends_on_more_than_content():
    """NEGATIVE: fires when corpora that say the same thing get different bytes:
    a second run over one corpus directory, the same bytes under another
    directory name, or the same records listed in reverse order."""
    straight = declared(tool_outputs(EVAL_SEED))
    flipped = declared(tool_outputs(EVAL_SEED, corpus_tag="reversed", reverse=True))
    assert solver_present() and not (repeats_itself() and filename_stable()
                                     and straight == flipped), (
        "the solver writes the same bytes for the same corpus content")


def _impl_negative_weight_writes_undeclared_files():
    """NEGATIVE: fires when the solver writes a file it never declared into the
    output directory, or changes the corpus directory it was handed."""
    out_dir = tool_dir(EVAL_SEED)
    allowed = set(ARTIFACTS) | {TOOL_NAME}
    extra = sorted(path.name for path in out_dir.iterdir()
                   if path.name not in allowed)
    touched = _snapshot(corpus(EVAL_SEED)) != _corpus_snapshots[_corpus_key(EVAL_SEED)]
    assert solver_present() and (extra or touched), (
        "the solver wrote only its declared artifacts, and only where it was told")


NETWORK_MODULES = ("socket", "ssl", "urllib.request", "http.client", "http.server",
                   "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "xmlrpc.client",
                   "xmlrpc.server", "socketserver")


def _impl_negative_weight_imports_outside_contract():
    """NEGATIVE: fires when the delivered solver imports a module outside the
    standard library, or a standard library module that opens network
    connections, so it could reach a network host."""
    tree = ast.parse(tool_source())
    dotted: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dotted.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            dotted.add(node.module)
            dotted.update(node.module + "." + alias.name for alias in node.names)
    roots = {name.split(".")[0] for name in dotted}
    networked = {name for name in dotted
                 if any(name == mod or name.startswith(mod + ".") for mod in NETWORK_MODULES)}
    outside = sorted((roots - set(sys.stdlib_module_names)) | networked)
    assert outside, "the solver depends on the standard library alone and opens no network"


# Rewardkit criteria. Each check binds workspace then calls the original body.
@criterion(description='the delivered solver, run on the shipped corpus, writes every delivered artifact byte for byte')
def test_artifacts_written_by_delivered_solver(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifacts_written_by_delivered_solver)

@criterion(description='the principal registry, including the disposition each principal ends in')
def test_artifact_principal_registry(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_principal_registry)





@criterion(description='the per phase PAM outcome and the line that decided it')
def test_artifact_pam_verdicts(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_pam_verdicts)

@criterion(description='the permitted and effective capability sets of every run')
def test_artifact_capability_ledger(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_capability_ledger)

@criterion(description='the domain each exec lands in and the three checks it needed')
def test_artifact_domain_transitions(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_domain_transitions)

@criterion(description='the action the filter stack returns for every recorded call')
def test_artifact_seccomp_decisions(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_seccomp_decisions)

@criterion(description='the per architecture dispatch counts including the repairs')
def test_artifact_arch_dispatch(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_arch_dispatch)


@criterion(description='the admission verdict of every run in the bound order')
def test_artifact_admission_ledger(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_admission_ledger)

@criterion(description='the rule and the sentence behind every refusal')
def test_artifact_denial_attribution(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_denial_attribution)

@criterion(description='the blocked calls ordered by the round that first reached them')
def test_artifact_blocked_syscalls(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_blocked_syscalls)

@criterion(description='the capability gaps with the signed origin of each')
def test_artifact_capability_gaps(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_capability_gaps)

@criterion(description='the audit continuity of every run and the reason it broke')
def test_artifact_audit_continuity(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_audit_continuity)

@criterion(description='the atom catalogue with its repair counts and forbidden marks')
def test_artifact_relaxation_atoms(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_relaxation_atoms)

@criterion(description='the atoms a run the site refuses would be admitted by')
def test_artifact_forbidden_atoms(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_forbidden_atoms)

@criterion(description='the grant plan in round, cost and identifier order')
def test_artifact_grant_plan(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_grant_plan)

@criterion(description='the round by round record of the fixed point')
def test_artifact_iteration_trace(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_iteration_trace)

@criterion(description='the necessity witness for every atom the plan keeps')
def test_artifact_minimality_witness(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_minimality_witness)

@criterion(description='the runs the plan leaves refused and the status of each')
def test_artifact_residual_denials(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_residual_denials)

@criterion(description='the conservation record closing over the whole population')
def test_artifact_conservation(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_conservation)

@criterion(description='the summary record with its five repair counts')
def test_artifact_summary(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_summary)

@criterion(description='the delivered solver rebuilds every artifact on the reduced unseen corpus with an idle architecture and an early stop')
def test_regenerates_on_reduced_corpus(workspace):
    _bind(workspace)
    return _pass(_impl_test_regenerates_on_reduced_corpus)

@criterion(description='the solver honours the exit codes its contract states, zero, two and three')
def test_contract_and_exit_codes(workspace):
    _bind(workspace)
    return _pass(_impl_test_contract_and_exit_codes)

@criterion(description='the shipped corpus reproduces whole while the fresh corpus, fully written, comes out wrong on at least twenty of the twenty four artifacts')
def negative_weight_hardcoded_sample_answers(workspace):
    _bind(workspace)
    return _pass(_impl_negative_weight_hardcoded_sample_answers)

@criterion(description='the delivered solver carries the shipped corpus path as a string value its own code can read')
def negative_weight_embeds_shipped_corpus_path(workspace):
    _bind(workspace)
    return _pass(_impl_negative_weight_embeds_shipped_corpus_path)

@criterion(description='corpora that say the same thing, run again, renamed or listed in reverse, get different bytes')
def negative_weight_output_depends_on_more_than_content(workspace):
    _bind(workspace)
    return _pass(_impl_negative_weight_output_depends_on_more_than_content)

@criterion(description='the solver writes a file it never declared into the output directory, or changes the corpus directory')
def negative_weight_writes_undeclared_files(workspace):
    _bind(workspace)
    return _pass(_impl_negative_weight_writes_undeclared_files)

@criterion(description='the delivered solver imports a module outside the standard library or a network client module')
def negative_weight_imports_outside_contract(workspace):
    _bind(workspace)
    return _pass(_impl_negative_weight_imports_outside_contract)







@criterion(description='the resolved system call index across the three architectures')
def test_artifact_syscall_index(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_syscall_index)

@criterion(description='the PAM stack in walk order with its gates recorded')
def test_artifact_pam_stack_resolved(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_pam_stack_resolved)

@criterion(description='the type and attribute graph with its key order preserved')
def test_artifact_selinux_type_graph(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_selinux_type_graph)

@criterion(description='the normalised filter program with resolved numbers and ranks')
def test_artifact_seccomp_program(workspace):
    _bind(workspace)
    return _pass(_impl_test_artifact_seccomp_program)

@criterion(description='shards with a byte order mark, carriage return line endings, newlines in quoted fields or blank lines read like any other')
def test_reads_encoding_features(workspace):
    _bind(workspace)
    return _pass(_impl_test_reads_encoding_features)

@criterion(description='an audit event recorded before the exec event is judged against the domain the exec event left the process in')
def test_audit_event_before_exec(workspace):
    _bind(workspace)
    return _pass(_impl_test_audit_event_before_exec)

@criterion(description='a cost control naming one atom in two spellings counts that atom once when the multipliers are fixed')
def test_cost_control_names_a_set(workspace):
    _bind(workspace)
    return _pass(_impl_test_cost_control_names_a_set)

criteria.test_artifacts_written_by_delivered_solver(weight=3)
criteria.test_artifact_principal_registry(weight=1)
criteria.test_artifact_syscall_index(weight=1)
criteria.test_artifact_pam_stack_resolved(weight=3)
criteria.test_artifact_selinux_type_graph(weight=3)
criteria.test_artifact_seccomp_program(weight=3)
criteria.test_artifact_pam_verdicts(weight=5)
criteria.test_artifact_capability_ledger(weight=5)
criteria.test_artifact_domain_transitions(weight=5)
criteria.test_artifact_seccomp_decisions(weight=5)
criteria.test_artifact_arch_dispatch(weight=3)
criteria.test_artifact_admission_ledger(weight=1)
criteria.test_artifact_denial_attribution(weight=5)
criteria.test_artifact_blocked_syscalls(weight=1)
criteria.test_artifact_capability_gaps(weight=5)
criteria.test_artifact_audit_continuity(weight=5)
criteria.test_artifact_relaxation_atoms(weight=1)
criteria.test_artifact_forbidden_atoms(weight=3)
criteria.test_artifact_grant_plan(weight=5)
criteria.test_artifact_iteration_trace(weight=1)
criteria.test_artifact_minimality_witness(weight=3)
criteria.test_artifact_residual_denials(weight=1)
criteria.test_artifact_conservation(weight=1)
criteria.test_artifact_summary(weight=1)
criteria.test_regenerates_on_reduced_corpus(weight=3)
criteria.test_contract_and_exit_codes(weight=3)
criteria.test_reads_encoding_features(weight=3)
criteria.test_audit_event_before_exec(weight=3)
criteria.test_cost_control_names_a_set(weight=3)
criteria.negative_weight_hardcoded_sample_answers(weight=-5)
criteria.negative_weight_embeds_shipped_corpus_path(weight=-5)
criteria.negative_weight_output_depends_on_more_than_content(weight=-5)
criteria.negative_weight_writes_undeclared_files(weight=-5)
criteria.negative_weight_imports_outside_contract(weight=-3)

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("environment")
    destination = target / "data" if target.name != "data" else target
    destination.mkdir(parents=True, exist_ok=True)
    GEN.emit_corpus(SAMPLE_SEED, destination, REF)
    print("wrote the sample corpus into {}".format(destination))
