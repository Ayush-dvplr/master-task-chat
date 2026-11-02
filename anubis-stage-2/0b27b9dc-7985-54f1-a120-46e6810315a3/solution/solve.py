#!/usr/bin/env python3
"""lgactl: the LGA least grant admission control solver (reference solution).

Usage: lgactl.py CORPUS_DIR OUT_DIR

Reads the flat LGA corpus, replays the recorded run population against the
shipped policy under the four enforcement layers, settles the least set of
permissible grant atoms that admits every ``must_admit`` run while holding
every ``must_deny`` run refused, and writes the twenty four delivered
artifacts plus a byte copy of itself.  Standard library only; no network
access.
"""

import hashlib
import json
import os
import sys
import unicodedata

# --------------------------------------------------------------------------
# constants fixed by the contract
# --------------------------------------------------------------------------

CAP_TABLE = [
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
]
CAP_BIT = {name: i for i, name in enumerate(CAP_TABLE)}

ACTION_ORDER = ["KILL_PROCESS", "KILL_THREAD", "TRAP", "ERRNO",
                "USER_NOTIF", "TRACE", "LOG", "ALLOW"]
ACTION_RANK = {a: i + 1 for i, a in enumerate(ACTION_ORDER)}
REFUSING_ACTIONS = {"KILL_PROCESS", "KILL_THREAD", "TRAP", "USER_NOTIF", "TRACE"}

LAYER_RANK = {"pam": 1, "selinux": 2, "capability": 3, "seccomp": 4, "NONE": 9}
PHASES = ["auth", "account", "session"]
ARCHES = ["x86_64", "i386", "aarch64"]

PAM_FAIL_CODES = {"auth_err", "user_unknown", "perm_denied", "maxtries",
                  "cred_insufficient", "abort", "service_err"}

ROUND_CAP = 8

GROUP_FIELDS = {
    "principals": ["principal_id", "uid", "login", "display", "groups",
                   "inh_thread", "perm_thread"],
    "pam-stack": ["rule_id", "service", "phase", "rank", "control", "module", "flags"],
    "pam-returns": ["run_id", "phase", "module", "code"],
    "selinux-types": ["type_name", "attributes", "is_domain", "note"],
    "selinux-allow": ["rule_id", "source", "target", "tclass", "perms"],
    "selinux-transition": ["rule_id", "source", "exec_type", "new_domain", "rank"],
    "selinux-dontaudit": ["rule_id", "source", "target", "tclass", "perms", "note"],
    "cap-units": ["unit_id", "unit_name", "bounding", "ambient", "no_new_privs", "filters"],
    "cap-filecaps": ["binary_id", "path", "permitted_file", "inheritable_file", "effective_bit"],
    "cap-required": ["op_id", "operation", "capability", "advisory", "note"],
    "seccomp-filters": ["rule_id", "filter_id", "idx", "arch", "syscall", "arg_index",
                        "op", "value", "mask", "action"],
    "seccomp-defaults": ["filter_id", "default_action", "priority"],
    "arch-syscalls": ["arch", "nr", "syscall", "note"],
    "runs-trace": ["run_id", "seq", "kind", "principal", "service", "unit", "binary",
                   "source_domain", "exec_type", "arch", "phase", "syscall_nr", "arg0",
                   "capability", "tclass", "perm", "target_type", "required"],
    "runs-labels": ["run_id", "label", "note"],
    "grant-atoms": ["atom_id", "layer", "kind", "cost", "target"],
    "audit-events": ["event_id", "run_id", "ts", "action", "principal"],
    "cost-controls": ["control_id", "atoms", "total", "note"],
}

# SPEC section 14: the groups the work cannot proceed without.
REQUIRED_GROUPS = ["runs-trace", "selinux-allow", "cap-units", "grant-atoms"]

ARTIFACTS = [
    "principal_registry.jsonl", "syscall_index.tsv", "pam_stack_resolved.csv",
    "selinux_type_graph.json", "seccomp_program.jsonl", "pam_verdicts.csv",
    "capability_ledger.csv", "domain_transitions.tsv", "seccomp_decisions.jsonl",
    "arch_dispatch.tsv", "admission_ledger.csv", "denial_attribution.jsonl",
    "blocked_syscalls.tsv", "capability_gaps.csv", "audit_continuity.jsonl",
    "relaxation_atoms.csv", "forbidden_atoms.tsv", "grant_plan.csv",
    "iteration_trace.jsonl", "minimality_witness.csv", "residual_denials.tsv",
    "conservation.json", "summary.json",
]


# --------------------------------------------------------------------------
# canonical forms
# --------------------------------------------------------------------------

def nfc(s):
    return unicodedata.normalize("NFC", s)


def cid(s):
    """Canonical identifier form."""
    return s.upper().replace("_", "-").replace(".", "-")


def ctype(s):
    """Canonical SELinux type name form."""
    return s.lower().replace("-", "_").replace(".", "_")


def ccap(s):
    """Canonical capability name."""
    s = s.strip()
    if not s:
        return ""
    if s.isdigit():
        i = int(s)
        if 0 <= i < len(CAP_TABLE):
            return CAP_TABLE[i]
        return s
    return s.upper()


def capset(field):
    """Read a capability set field into a frozenset of canonical names."""
    f = field.strip()
    if not f or f.lower() == "none":
        return frozenset()
    out = set()
    for part in f.replace(",", "+").split("+"):
        part = part.strip()
        if not part:
            continue
        if part.lower() == "none":
            continue
        out.add(ccap(part))
    return frozenset(out)


def capsort(caps):
    return sorted(caps, key=lambda c: (CAP_BIT.get(c, len(CAP_TABLE)), c))


def capjoin(caps):
    s = capsort(caps)
    return "+".join(s) if s else "NONE"


def to_int(s, default=0):
    s = s.strip()
    if not s:
        return default
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if s[:2].lower() == "0x":
        try:
            v = int(s, 16)
        except ValueError:
            return default
        return -v if neg else v
    try:
        v = int(s, 10)
    except ValueError:
        return default
    return -v if neg else v


# --------------------------------------------------------------------------
# encodings
# --------------------------------------------------------------------------

def _physical_lines(data):
    if data.startswith("\ufeff"):
        data = data[1:]
    out = []
    for ln in data.split("\n"):
        if ln.endswith("\r"):
            ln = ln[:-1]
        out.append(ln)
    if out and out[-1] == "":
        out.pop()
    return out


def _split_sep(line, sep):
    fields = []
    cur = []
    i = 0
    n = len(line)
    inq = False
    while i < n:
        c = line[i]
        if inq:
            if c == '"':
                if i + 1 < n and line[i + 1] == '"':
                    cur.append('"')
                    i += 2
                    continue
                inq = False
                i += 1
                continue
            cur.append(c)
            i += 1
            continue
        if c == '"' and not cur:
            inq = True
            i += 1
            continue
        if c == sep:
            fields.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    fields.append("".join(cur))
    return fields, inq


def _read_sep(data, sep):
    logical = []
    pending = None
    for ln in _physical_lines(data):
        if pending is not None:
            pending = pending + "\n" + ln
            if not _split_sep(pending, sep)[1]:
                logical.append(pending)
                pending = None
            continue
        if not ln.strip():
            continue
        if _split_sep(ln, sep)[1]:
            pending = ln
        else:
            logical.append(ln)
    if pending is not None:
        logical.append(pending)
    if not logical:
        return []
    header = _split_sep(logical[0], sep)[0]
    recs = []
    for ln in logical[1:]:
        vals = _split_sep(ln, sep)[0]
        recs.append({name: (vals[i] if i < len(vals) else "")
                     for i, name in enumerate(header)})
    return recs


def _unescape(v, table):
    out = []
    i = 0
    n = len(v)
    while i < n:
        if v[i] == "\\" and i + 1 < n and v[i + 1] in table:
            out.append(table[v[i + 1]])
            i += 2
            continue
        out.append(v[i])
        i += 1
    return "".join(out)


_TSV_ESC = {"t": "\t", "n": "\n", "\\": "\\"}
_TOML_ESC = {'"': '"', "\\": "\\"}
_PROP_ESC = {":": ":", "=": "="}
_LOGFMT_ESC = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}
_RFC_ESC = {'"': '"', "\\": "\\"}


def _read_tsv(data):
    lines = [l for l in _physical_lines(data) if l.strip()]
    if not lines:
        return []
    header = [_unescape(x, _TSV_ESC) for x in lines[0].split("\t")]
    recs = []
    for ln in lines[1:]:
        vals = ln.split("\t")
        recs.append({name: (_unescape(vals[i], _TSV_ESC) if i < len(vals) else "")
                     for i, name in enumerate(header)})
    return recs


def _read_fixed(data):
    lines = [l for l in _physical_lines(data) if l.strip()]
    if not lines:
        return []
    spec = []
    for el in lines[0].split(";"):
        el = el.strip()
        if not el:
            continue
        name, width = el.rsplit(":", 1)
        spec.append((name, int(width)))
    recs = []
    for ln in lines[1:]:
        rec = {}
        pos = 0
        for name, w in spec:
            rec[name] = ln[pos:pos + w].rstrip(" ")
            pos += w
        recs.append(rec)
    return recs


def _read_json(data):
    if data.startswith("\ufeff"):
        data = data[1:]
    obj = json.loads(data)
    return [dict(r) for r in obj.get("records", [])]


def _read_jsonl(data):
    return [dict(json.loads(ln)) for ln in _physical_lines(data) if ln.strip()]


def _read_toml(data):
    recs = []
    cur = None
    for ln in _physical_lines(data):
        s = ln.strip()
        if not s:
            continue
        if s == "[[record]]":
            cur = {}
            recs.append(cur)
            continue
        if cur is None or "=" not in s:
            continue
        name, val = s.split("=", 1)
        val = val.strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        cur[name.strip()] = _unescape(val, _TOML_ESC)
    return recs


def _read_ini(data):
    recs = []
    cur = None
    for ln in _physical_lines(data):
        s = ln.strip()
        if not s:
            continue
        if s.startswith("[record_") and s.endswith("]"):
            cur = {}
            recs.append(cur)
            continue
        if cur is None or "=" not in s:
            continue
        name, val = s.split("=", 1)
        cur[name.strip()] = val.strip()
    return recs


def _read_properties(data):
    order = []
    recs = {}
    for ln in _physical_lines(data):
        if not ln.strip():
            continue
        i = 0
        pos = -1
        while i < len(ln):
            if ln[i] == "\\":
                i += 2
                continue
            if ln[i] == "=":
                pos = i
                break
            i += 1
        if pos < 0:
            continue
        key = ln[:pos].strip()
        val = _unescape(ln[pos + 1:].strip(), _PROP_ESC)
        parts = key.split(".")
        if len(parts) < 3 or parts[0] != "record":
            continue
        idx = parts[1]
        if idx not in recs:
            recs[idx] = {}
            order.append(idx)
        recs[idx][".".join(parts[2:])] = val
    return [recs[i] for i in sorted(order, key=int)]


def _parse_kv(s, esc):
    rec = {}
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i] == " ":
            i += 1
        if i >= n:
            break
        j = s.find("=", i)
        if j < 0:
            break
        name = s[i:j]
        i = j + 1
        if i < n and s[i] == '"':
            i += 1
            buf = []
            while i < n:
                if s[i] == "\\" and i + 1 < n:
                    buf.append(s[i])
                    buf.append(s[i + 1])
                    i += 2
                    continue
                if s[i] == '"':
                    i += 1
                    break
                buf.append(s[i])
                i += 1
            rec[name] = _unescape("".join(buf), esc)
        else:
            k = s.find(" ", i)
            if k < 0:
                k = n
            rec[name] = s[i:k]
            i = k
    return rec


def _read_logfmt(data):
    return [_parse_kv(ln, _LOGFMT_ESC) for ln in _physical_lines(data) if ln.strip()]


def _read_sexp(data):
    recs = []
    for ln in _physical_lines(data):
        if not ln.strip():
            continue
        rec = {}
        i = 0
        n = len(ln)
        while True:
            o = ln.find("(", i)
            if o < 0:
                break
            k = o + 1
            while k < n and (ln[k].isalnum() or ln[k] == "_"):
                k += 1
            name = ln[o + 1:k]
            m = k
            while m < n and ln[m] in " \t":
                m += 1
            if not name or m >= n or ln[m] != '"':
                i = o + 1
                continue
            j = m + 1
            buf = []
            while j < n:
                if ln[j] == "\\" and j + 1 < n:
                    buf.append(ln[j])
                    buf.append(ln[j + 1])
                    j += 2
                    continue
                if ln[j] == '"':
                    break
                buf.append(ln[j])
                j += 1
            rec[name] = _unescape("".join(buf), {'"': '"', "\\": "\\"})
            i = j + 1
        if rec:
            recs.append(rec)
    return recs


def _read_rfc5424(data):
    recs = []
    marker = "[lga@1 "
    for ln in _physical_lines(data):
        if not ln.strip():
            continue
        start = ln.find(marker)
        if start < 0:
            continue
        i = start + len(marker)
        n = len(ln)
        j = i
        inq = False
        while j < n:
            c = ln[j]
            if inq:
                if c == "\\":
                    j += 2
                    continue
                if c == '"':
                    inq = False
                j += 1
                continue
            if c == '"':
                inq = True
                j += 1
                continue
            if c == "]":
                break
            j += 1
        rec = _parse_kv(ln[i:j], _RFC_ESC)
        if rec:
            recs.append(rec)
    return recs


READERS = {
    ".csv": lambda d: _read_sep(d, ","),
    ".psv": lambda d: _read_sep(d, "|"),
    ".ssv": lambda d: _read_sep(d, " "),
    ".tsv": _read_tsv,
    ".fixed": _read_fixed,
    ".json": _read_json,
    ".jsonl": _read_jsonl,
    ".toml": _read_toml,
    ".ini": _read_ini,
    ".properties": _read_properties,
    ".logfmt": _read_logfmt,
    ".sexp": _read_sexp,
    ".rfc5424": _read_rfc5424,
}


def load_groups(corpus_dir):
    groups = {g: [] for g in GROUP_FIELDS}
    for name in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, name)
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(name)
        if ext not in READERS or "-" not in stem:
            continue
        group = stem[:stem.rfind("-")]
        if group not in GROUP_FIELDS:
            continue
        with open(path, "r", encoding="utf-8") as fh:
            data = fh.read()
        fields = GROUP_FIELDS[group]
        for rec in READERS[ext](data):
            groups[group].append(
                {f: nfc("" if rec.get(f) is None else str(rec[f])) for f in fields})
    return groups


def dedupe(records, keyfn, last_wins=False):
    out = {}
    order = []
    for rec in records:
        k = keyfn(rec)
        if k in out:
            if last_wins:
                out[k] = rec
            continue
        out[k] = rec
        order.append(k)
    return out, order


# --------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------

def csv_field(v):
    s = str(v)
    if any(c in s for c in (",", '"', "\n", "\r")):
        return '"' + s.replace('"', '""') + '"'
    return s


def csv_line(vals):
    return ",".join(csv_field(v) for v in vals)


def tsv_field(v):
    return (str(v).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n"))


def tsv_line(vals):
    return "\t".join(tsv_field(v) for v in vals)


def jdump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


class Writer(object):
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.written = {}

    def write(self, name, lines):
        text = "".join(l + "\n" for l in lines)
        if not text and name.endswith((".csv", ".tsv")):
            # SPEC 13: every delimited artifact ends with a newline, even a
            # headerless one with no rows.
            text = "\n"
        blob = text.encode("utf-8")
        with open(os.path.join(self.out_dir, name), "wb") as fh:
            fh.write(blob)
        self.written[name] = blob


# --------------------------------------------------------------------------
# target strings
# --------------------------------------------------------------------------

def parse_target(raw):
    """Parse a semicolon separated key=value target.  ``note`` runs to the end."""
    out = {}
    rest = raw
    while rest:
        if rest.startswith("note="):
            out["note"] = rest[5:]
            break
        j = rest.find(";")
        if j < 0:
            el, rest = rest, ""
        else:
            el, rest = rest[:j], rest[j + 1:]
        if "=" in el:
            k, v = el.split("=", 1)
            k = k.strip()
            if k and k not in out:
                out[k] = v
    return out


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------

class Policy(object):
    """The shipped policy, read from the corpus."""

    def __init__(self, groups):
        self.groups = groups
        self._build_types()
        self._build_allow()
        self._build_transitions()
        self._build_pam()
        self._build_caps()
        self._build_seccomp()
        self._build_atoms()

    # -- SELinux types ----------------------------------------------------
    def _build_types(self):
        self.type_attrs = {}
        self.type_order = []
        for rec in self.groups["selinux-types"]:
            t = ctype(rec["type_name"])
            if not t or t in self.type_attrs:
                continue
            attrs = [a.strip() for a in rec["attributes"].split("|") if a.strip()]
            self.type_attrs[t] = sorted(set(attrs))
            self.type_order.append(t)
        self.attributes = {}
        for t in sorted(self.type_attrs):
            for a in self.type_attrs[t]:
                self.attributes.setdefault(a, []).append(t)
        self.attr_names = set(self.attributes)
        self._keys_cache = {}

    def keys_of(self, name):
        """The record-source/target names that expand onto this type."""
        k = self._keys_cache.get(name)
        if k is None:
            k = (name,) + tuple(self.type_attrs.get(name, ()))
            self._keys_cache[name] = k
        return k

    def expand_attr(self, name):
        """Types a source/target element covers."""
        if name in self.attributes:
            return self.attributes[name]
        return [name]

    # -- SELinux allow ----------------------------------------------------
    def _build_allow(self):
        tbl = {}
        for rec in self.groups["selinux-allow"]:
            src = ctype(rec["source"])
            tgt = ctype(rec["target"])
            cls = rec["tclass"].strip()
            perms = [p.strip() for p in rec["perms"].split(",") if p.strip()]
            if not perms:
                continue
            key = (src, tgt, cls)
            s = tbl.get(key)
            if s is None:
                s = set()
                tbl[key] = s
            s.update(perms)
        self.allow_tbl = tbl
        self._allow_cache = {}

    def base_perms(self, src, tgt, cls):
        key = (src, tgt, cls)
        got = self._allow_cache.get(key)
        if got is None:
            acc = set()
            tbl = self.allow_tbl
            for s in self.keys_of(src):
                for t in self.keys_of(tgt):
                    v = tbl.get((s, t, cls))
                    if v:
                        acc |= v
            got = frozenset(acc)
            self._allow_cache[key] = got
        return got

    # -- SELinux transitions ---------------------------------------------
    def _build_transitions(self):
        tr = {}
        for rec in self.groups["selinux-transition"]:
            src = ctype(rec["source"])
            ex = ctype(rec["exec_type"])
            tr.setdefault((src, ex), []).append(
                (to_int(rec["rank"]), cid(rec["rule_id"]), ctype(rec["new_domain"])))
        self.transitions = {}
        for k, v in tr.items():
            v.sort(key=lambda x: (x[0], x[1]))
            self.transitions[k] = v[0]

    # -- PAM --------------------------------------------------------------
    def _build_pam(self):
        self.pam_lines = []
        self.pam_by_sp = {}
        self.pam_by_rule = {}
        for rec in self.groups["pam-stack"]:
            flags = rec["flags"]
            gate = None
            for word in flags.replace(",", " ").split():
                if word.startswith("skip_if_uid_below="):
                    gate = to_int(word.split("=", 1)[1])
            line = {
                "rule_id": cid(rec["rule_id"]),
                "service": rec["service"].strip(),
                "phase": rec["phase"].strip(),
                "rank": to_int(rec["rank"]),
                "control": rec["control"].strip(),
                "module": rec["module"].strip(),
                "gate": gate,
            }
            self.pam_lines.append(line)
            self.pam_by_sp.setdefault((line["service"], line["phase"]), []).append(line)
            self.pam_by_rule[line["rule_id"]] = line
        for v in self.pam_by_sp.values():
            v.sort(key=lambda l: (l["rank"], l["module"], l["rule_id"]))
        self.pam_rules_by_sp = {k: frozenset(l["rule_id"] for l in v)
                                for k, v in self.pam_by_sp.items()}
        ret, _ = dedupe(self.groups["pam-returns"],
                        lambda r: (cid(r["run_id"]), r["phase"].strip(), r["module"].strip()))
        self.pam_returns = {k: v["code"].strip() for k, v in ret.items()}

    # -- capabilities -----------------------------------------------------
    def _build_caps(self):
        units, _ = dedupe(self.groups["cap-units"], lambda r: cid(r["unit_id"]))
        self.units = {}
        for k, r in units.items():
            self.units[k] = {
                "unit_id": k,
                "name": r["unit_name"],
                "bounding": capset(r["bounding"]),
                "ambient": capset(r["ambient"]),
                "nnp": r["no_new_privs"] == "true",
                "filters": tuple(cid(f.strip()) for f in r["filters"].split("|") if f.strip()),
            }
        bins, _ = dedupe(self.groups["cap-filecaps"], lambda r: cid(r["binary_id"]))
        self.binaries = {}
        for k, r in bins.items():
            self.binaries[k] = {
                "binary_id": k,
                "path": r["path"],
                "fp": capset(r["permitted_file"]),
                "fi": capset(r["inheritable_file"]),
                "ebit": r["effective_bit"].strip() == "1",
            }
        prs, _ = dedupe(self.groups["principals"], lambda r: cid(r["principal_id"]))
        self.principals = {}
        for k, r in prs.items():
            self.principals[k] = {
                "principal_id": k,
                "uid": to_int(r["uid"]),
                "login": r["login"],
                "display": r["display"],
                "groups": sorted({x.strip() for x in r["groups"].split("|") if x.strip()}),
                "ti": capset(r["inh_thread"]),
                "tp": capset(r["perm_thread"]),
            }
        self.advisory_caps = set()
        for r in self.groups["cap-required"]:
            if r["advisory"].strip().lower() == "yes":
                c = ccap(r["capability"])
                if c:
                    self.advisory_caps.add(c)

    # -- seccomp ----------------------------------------------------------
    def _build_seccomp(self):
        self.syscall_tbl = {}
        self.syscall_rows = []
        seen = set()
        for r in self.groups["arch-syscalls"]:
            arch = r["arch"].strip()
            nr = to_int(r["nr"])
            key = (arch, nr)
            if key in seen:
                continue
            seen.add(key)
            name = r["syscall"].strip()
            self.syscall_tbl[key] = name
            self.syscall_rows.append((arch, nr, name))
        self.syscall_rows.sort(key=lambda x: (x[0], x[1]))
        self.name_to_nr = {}
        for arch, nr, name in self.syscall_rows:
            k = (arch, name)
            if k not in self.name_to_nr or nr < self.name_to_nr[k]:
                self.name_to_nr[k] = nr

        defaults, _ = dedupe(self.groups["seccomp-defaults"], lambda r: cid(r["filter_id"]))
        self.filter_default = {k: r["default_action"].strip() for k, r in defaults.items()}

        self.filter_rules = {}
        self.filter_index = {}
        self.seccomp_rules = []
        for r in self.groups["seccomp-filters"]:
            arg_raw = r["arg_index"].strip()
            rule = {
                "rule_id": cid(r["rule_id"]),
                "filter_id": cid(r["filter_id"]),
                "idx": to_int(r["idx"]),
                "arch": r["arch"].strip(),
                "syscall": r["syscall"].strip(),
                "arg_index": (to_int(arg_raw) if arg_raw != "" else None),
                "op": r["op"].strip(),
                "value": to_int(r["value"]),
                "mask": to_int(r["mask"]),
                "action": r["action"].strip(),
            }
            self.seccomp_rules.append(rule)
            self.filter_rules.setdefault(rule["filter_id"], []).append(rule)
            self.filter_index.setdefault(rule["filter_id"], {}).setdefault(
                (rule["arch"], rule["syscall"]), []).append(rule)
        self.seccomp_rules.sort(key=lambda r: (r["filter_id"], r["idx"], r["rule_id"]))

    def default_of(self, fid):
        return self.filter_default.get(fid, "ALLOW")

    # -- atoms ------------------------------------------------------------
    def _build_atoms(self):
        recs, order = dedupe(self.groups["grant-atoms"], lambda r: cid(r["atom_id"]))
        self.atoms = {}
        for k in order:
            r = recs[k]
            el = parse_target(r["target"])
            kind = r["kind"].strip()
            atom = {
                "atom_id": k,
                "layer": r["layer"].strip(),
                "kind": kind,
                "cost": to_int(r["cost"]),
                "target": r["target"],
            }
            if kind == "pam_control_relax":
                atom["rule"] = cid(el.get("rule", ""))
            elif kind == "te_allow_add":
                atom["source"] = ctype(el.get("source", ""))
                atom["tgt"] = ctype(el.get("target", ""))
                atom["class"] = el.get("class", "").strip()
                atom["perm"] = el.get("perm", "").strip()
            elif kind in ("cap_bounding_add", "cap_ambient_add"):
                atom["unit"] = cid(el.get("unit", ""))
                atom["cap"] = ccap(el.get("cap", ""))
            elif kind == "seccomp_rule_add":
                atom["filter"] = cid(el.get("filter", ""))
                atom["arch"] = el.get("arch", "").strip()
                atom["syscall"] = el.get("syscall", "").strip()
            elif kind in ("seccomp_default_relax", "filter_unload"):
                atom["filter"] = cid(el.get("filter", ""))
            self.atoms[k] = atom
        self.atom_order = order

        ctl, _ = dedupe(self.groups["cost-controls"], lambda r: cid(r["control_id"]))
        self.controls = []
        for k in sorted(ctl):
            r = ctl[k]
            names = sorted({cid(a.strip()) for a in r["atoms"].split("|") if a.strip()})
            self.controls.append({"control_id": k, "atoms": names,
                                  "total": to_int(r["total"])})


# --------------------------------------------------------------------------
# policy state (shipped policy plus a set of atoms)
# --------------------------------------------------------------------------

class State(object):
    __slots__ = ("pol", "atom_ids", "pam_relax", "te_adds", "bound_add", "amb_add",
                 "sec_allow", "sec_default", "unloaded", "_eff_cache", "_pam_cache",
                 "_loaded_cache")

    def __init__(self, pol, atom_ids=()):
        self.pol = pol
        self.atom_ids = frozenset(atom_ids)
        self.pam_relax = set()
        self.te_adds = {}
        self.bound_add = {}
        self.amb_add = {}
        self.sec_allow = {}
        self.sec_default = set()
        self.unloaded = set()
        self._eff_cache = {}
        self._pam_cache = {}
        self._loaded_cache = {}
        for aid in sorted(self.atom_ids):
            a = pol.atoms[aid]
            k = a["kind"]
            if k == "pam_control_relax":
                self.pam_relax.add(a["rule"])
            elif k == "te_allow_add":
                self.te_adds.setdefault((a["source"], a["tgt"], a["class"]), set()).add(a["perm"])
            elif k == "cap_bounding_add":
                self.bound_add.setdefault(a["unit"], set()).add(a["cap"])
            elif k == "cap_ambient_add":
                self.amb_add.setdefault(a["unit"], set()).add(a["cap"])
                self.bound_add.setdefault(a["unit"], set()).add(a["cap"])
            elif k == "seccomp_rule_add":
                self.sec_allow.setdefault(a["filter"], set()).add((a["arch"], a["syscall"]))
            elif k == "seccomp_default_relax":
                self.sec_default.add(a["filter"])
            elif k == "filter_unload":
                self.unloaded.add(a["filter"])

    # -- SELinux ----------------------------------------------------------
    def te_allowed(self, src, tgt, cls, perm):
        if perm in self.pol.base_perms(src, tgt, cls):
            return True
        if not self.te_adds:
            return False
        ks = self.pol.keys_of(src)
        kt = self.pol.keys_of(tgt)
        for s in ks:
            for t in kt:
                v = self.te_adds.get((s, t, cls))
                if v and perm in v:
                    return True
        return False

    # -- capabilities -----------------------------------------------------
    def effective(self, unit_id, binary_id, principal_id):
        key = (unit_id, binary_id, principal_id)
        got = self._eff_cache.get(key)
        if got is not None:
            return got
        pol = self.pol
        u = pol.units.get(unit_id)
        b = pol.binaries.get(binary_id)
        p = pol.principals.get(principal_id)
        B = (u["bounding"] if u else frozenset())
        A = (u["ambient"] if u else frozenset())
        nnp = bool(u and u["nnp"])
        extra_b = self.bound_add.get(unit_id)
        if extra_b:
            B = B | extra_b
        extra_a = self.amb_add.get(unit_id)
        if extra_a:
            A = A | extra_a
        Fp = (b["fp"] if b else frozenset())
        Fi = (b["fi"] if b else frozenset())
        ebit = bool(b and b["ebit"])
        Ti = (p["ti"] if p else frozenset())
        Tp = (p["tp"] if p else frozenset())
        from_file = (Fp & B & Tp) if nnp else (Fp & B)
        permitted = (Ti & Fi) | from_file | A
        eff = permitted if ebit else A
        got = (frozenset(permitted), frozenset(eff), frozenset(B), frozenset(A), nnp)
        self._eff_cache[key] = got
        return got

    # -- seccomp ----------------------------------------------------------
    def loaded(self, unit_id):
        got = self._loaded_cache.get(unit_id)
        if got is None:
            u = self.pol.units.get(unit_id)
            fl = u["filters"] if u else ()
            got = tuple(f for f in fl if f not in self.unloaded)
            self._loaded_cache[unit_id] = got
        return got

    def seccomp_decide(self, unit_id, arch, name, arg0):
        """Return (action, rule_name, matched_count)."""
        pol = self.pol
        best = None  # (rank, sortkey, rule_name)
        matched = 0
        for fid in self.loaded(unit_id):
            ov = self.sec_allow.get(fid)
            if ov and (arch, name) in ov:
                ans = (ACTION_RANK["ALLOW"], (0, ""), "NONE")
                if best is None or ans[:2] < best[:2]:
                    best = ans
                continue
            cand = pol.filter_index.get(fid, {}).get((arch, name))
            frank = None
            fkey = None
            fname = None
            if cand:
                for rule in cand:
                    if not _arg_match(rule, arg0):
                        continue
                    matched += 1
                    r = ACTION_RANK.get(rule["action"], len(ACTION_ORDER) + 1)
                    key = (rule["idx"], rule["rule_id"])
                    if frank is None or r < frank or (r == frank and key < fkey):
                        frank, fkey, fname = r, key, rule["rule_id"]
            if frank is None:
                act = "ALLOW" if fid in self.sec_default else pol.default_of(fid)
                ans = (ACTION_RANK.get(act, len(ACTION_ORDER) + 1), (0, ""), "NONE")
            else:
                ans = (frank, (1, fname), fname)
            if best is None or ans[:2] < best[:2]:
                best = ans
        if best is None:
            return "ALLOW", "NONE", matched
        return ACTION_ORDER[best[0] - 1], best[2], matched

    # -- PAM --------------------------------------------------------------
    def pam_phase(self, run, phase):
        pol = self.pol
        service = run["service"]
        sp = (service, phase)
        relevant = frozenset()
        if self.pam_relax:
            rules = pol.pam_rules_by_sp.get(sp)
            if rules:
                inter = self.pam_relax & rules
                if inter:
                    relevant = frozenset(inter)
        key = (run["run_id"], phase, relevant)
        got = self._pam_cache.get(key)
        if got is not None:
            return got
        got = _pam_walk(pol, run, phase, relevant)
        self._pam_cache[key] = got
        return got


def _arg_match(rule, arg0):
    ai = rule["arg_index"]
    if ai is None:
        return True
    if ai != 0:
        return False
    op = rule["op"]
    v = rule["value"]
    if op == "EQ":
        return arg0 == v
    if op == "NE":
        return arg0 != v
    if op == "LT":
        return arg0 < v
    if op == "LE":
        return arg0 <= v
    if op == "GT":
        return arg0 > v
    if op == "GE":
        return arg0 >= v
    if op == "MASKED_EQ":
        return (arg0 & rule["mask"]) == v
    return False


def _pam_walk(pol, run, phase, relax):
    """Return (result, deciding_rule, deciding_module)."""
    lines = pol.pam_by_sp.get((run["service"], phase))
    if not lines:
        return ("service_err", "NONE", "NONE")
    uid = run["uid"]
    rec_fail = None
    opt_fail = None
    flag = False
    returns = pol.pam_returns
    rid = run["run_id"]
    for line in lines:
        gate = line["gate"]
        if gate is not None and uid < gate:
            continue
        code = returns.get((rid, phase, line["module"]), "ignore")
        if code == "ignore":
            continue
        control = "sufficient" if line["rule_id"] in relax else line["control"]
        if control == "optional":
            if code in PAM_FAIL_CODES and opt_fail is None:
                opt_fail = (code, line)
            continue
        flag = True
        if control == "requisite":
            if code in PAM_FAIL_CODES:
                return (code, line["rule_id"], line["module"])
            continue
        if control == "binding":
            if code in PAM_FAIL_CODES:
                return (code, line["rule_id"], line["module"])
            if code == "success":
                return ("success", "NONE", line["module"])
            continue
        if control == "sufficient":
            if code == "success" and rec_fail is None:
                return ("success", "NONE", line["module"])
            continue
        if control == "required":
            if code in PAM_FAIL_CODES and rec_fail is None:
                rec_fail = (code, line)
            continue
    if rec_fail is not None:
        return (rec_fail[0], rec_fail[1]["rule_id"], rec_fail[1]["module"])
    if flag:
        return ("success", "NONE", "NONE")
    if opt_fail is not None:
        return (opt_fail[0], opt_fail[1]["rule_id"], opt_fail[1]["module"])
    return ("service_err", "NONE", "NONE")


# --------------------------------------------------------------------------
# runs
# --------------------------------------------------------------------------

def build_runs(pol, groups):
    by_run = {}
    for rec in groups["runs-trace"]:
        by_run.setdefault(cid(rec["run_id"]), []).append(rec)
    repair = {"arch": 0, "capability": 0, "number": 0, "perm": 0, "type": 0}
    arch_repaired = {a: 0 for a in ARCHES}
    runs = {}
    for rid in sorted(by_run):
        recs = sorted(by_run[rid], key=lambda r: to_int(r["seq"]))
        events = []
        for rec in recs:
            raw_nr = rec["syscall_nr"].strip()
            nr = None
            if raw_nr:
                nr = to_int(raw_nr)
                low = raw_nr.lower()
                if low.startswith("0x") or (len(raw_nr) > 1 and raw_nr[0] == "0"):
                    repair["number"] += 1
            raw_cap = rec["capability"].strip()
            cap = ccap(raw_cap)
            if raw_cap and raw_cap != cap:
                repair["capability"] += 1
            raw_perm = rec["perm"].strip()
            perms = [p.strip() for p in raw_perm.split(",") if p.strip()]
            if len(perms) > 1:
                repair["perm"] += 1
            raw_tt = rec["target_type"].strip()
            tt = ctype(raw_tt)
            if raw_tt and raw_tt != tt:
                repair["type"] += 1
            events.append({
                "seq": to_int(rec["seq"]),
                "kind": rec["kind"].strip(),
                "arch": rec["arch"].strip(),
                "phase": rec["phase"].strip(),
                "nr": nr,
                "arg0": to_int(rec["arg0"]),
                "capability": cap,
                "tclass": rec["tclass"].strip(),
                "perms": perms,
                "target_type": tt,
                "required": rec["required"].strip(),
            })
        first = recs[0]
        execs = [e for e in events if e["kind"] == "exec"]
        disp = ""
        if execs and execs[0]["arch"]:
            disp = execs[0]["arch"]
        if not disp:
            for e in events:
                if e["arch"]:
                    disp = e["arch"]
                    break
        if not disp:
            disp = "x86_64"
        for e in events:
            if e["kind"] != "exec" and not e["arch"]:
                e["arch"] = disp
                repair["arch"] += 1
                if disp in arch_repaired:
                    arch_repaired[disp] += 1
        pid = cid(first["principal"])
        prn = pol.principals.get(pid)
        runs[rid] = {
            "run_id": rid,
            "principal": pid,
            "uid": prn["uid"] if prn else 0,
            "service": first["service"].strip(),
            "unit": cid(first["unit"]),
            "binary": cid(first["binary"]),
            "source_domain": ctype(first["source_domain"]),
            "exec_type": ctype(first["exec_type"]),
            "dispatch": disp,
            "events": events,
        }
    return runs, repair, arch_repaired


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------

def replay(run, st, collect=False):
    """Walk a run.  Returns a result dict; stops at the first refusal unless
    ``collect`` asks for the full reporting walk."""
    pol = st.pol
    unit = run["unit"]
    first = None
    res = {}
    if collect:
        res["pam"] = {}
        res["syscalls"] = []
        res["gaps"] = []
        res["blocks"] = []
    permitted, eff, B, A, nnp = st.effective(unit, run["binary"], run["principal"])
    domain = run["source_domain"]
    # The domain in force is the domain the exec event leaves the process in,
    # wherever an event sits in the run (selinux appendix, glossary).
    in_force = run["source_domain"]
    hop = pol.transitions.get((run["source_domain"], run["exec_type"]))
    if hop is not None and all((
            st.te_allowed(run["source_domain"], run["exec_type"], "file", "execute"),
            st.te_allowed(hop[2], run["exec_type"], "file", "entrypoint"),
            st.te_allowed(run["source_domain"], hop[2], "process", "transition"))):
        in_force = hop[2]
    tr_info = None
    audit_access = None
    for ev in run["events"]:
        kind = ev["kind"]
        if kind == "pam":
            result, rule, module = st.pam_phase(run, ev["phase"])
            if collect:
                res["pam"][ev["phase"]] = (result, rule, module)
            if result != "success" and first is None:
                first = ("pam", ev["seq"], rule, "pam_" + result, ev)
                if not collect:
                    break
        elif kind == "exec":
            tr = pol.transitions.get((run["source_domain"], run["exec_type"]))
            if tr is None:
                tr_info = ("NONE", run["source_domain"], True, True, True)
                domain = run["source_domain"]
            else:
                land = tr[2]
                e_ok = st.te_allowed(run["source_domain"], run["exec_type"], "file", "execute")
                n_ok = st.te_allowed(land, run["exec_type"], "file", "entrypoint")
                t_ok = st.te_allowed(run["source_domain"], land, "process", "transition")
                missing = []
                if not e_ok:
                    missing.append("execute")
                if not n_ok:
                    missing.append("entrypoint")
                if not t_ok:
                    missing.append("transition")
                if missing:
                    domain = run["source_domain"]
                    tr_info = (tr[1], domain, e_ok, n_ok, t_ok)
                    if first is None:
                        first = ("selinux", ev["seq"], tr[1],
                                 "te_missing_" + sorted(missing)[0], ev)
                        if not collect:
                            break
                else:
                    domain = land
                    tr_info = (tr[1], land, True, True, True)
        elif kind == "access":
            missing = [p for p in ev["perms"]
                       if not st.te_allowed(domain, ev["target_type"], ev["tclass"], p)]
            if missing and first is None:
                first = ("selinux", ev["seq"], "NONE",
                         "te_denied_" + sorted(missing)[0], ev)
                if not collect:
                    break
        elif kind == "capuse":
            cap = ev["capability"]
            if cap not in eff:
                if collect:
                    res["gaps"].append((cap, cap in B, cap in permitted))
                if cap not in pol.advisory_caps and first is None:
                    first = ("capability", ev["seq"], cap, "cap_absent", ev)
                    if not collect:
                        break
        elif kind == "syscall":
            arch = ev["arch"]
            nr = ev["nr"] if ev["nr"] is not None else 0
            name = pol.syscall_tbl.get((arch, nr))
            if name is None:
                action, rule, matched = "KILL_PROCESS", "NONE", 0
                denies = True
            else:
                action, rule, matched = st.seccomp_decide(unit, arch, name, ev["arg0"])
                if action in REFUSING_ACTIONS:
                    denies = True
                elif action == "ERRNO":
                    denies = ev["required"] == "yes"
                else:
                    denies = False
            if collect:
                res["syscalls"].append((ev["seq"], arch, nr, name, action, rule,
                                        matched, denies))
                if denies:
                    res["blocks"].append((arch, name if name else "NONE", action))
            if denies and first is None:
                first = ("seccomp", ev["seq"], rule, "seccomp_" + action.lower(), ev)
                if not collect:
                    break
        elif kind == "audit":
            audit_access = all(
                st.te_allowed(in_force, ev["target_type"], ev["tclass"], p)
                for p in ev["perms"])
    if first is None:
        res["verdict"] = "admitted"
        res["layer"] = "NONE"
        res["seq"] = 0
        res["rule"] = "NONE"
        res["reason"] = "admitted"
        res["event"] = None
    else:
        res["verdict"] = "denied"
        res["layer"] = first[0]
        res["seq"] = first[1]
        res["rule"] = first[2]
        res["reason"] = first[3]
        res["event"] = first[4]
    if collect:
        res["transition"] = tr_info
        res["domain"] = domain
        res["permitted"] = permitted
        res["effective"] = eff
        res["bounding"] = B
        res["ambient"] = A
        res["nnp"] = nnp
        res["audit_access"] = audit_access
        res["audit_cap"] = ("CAP_AUDIT_WRITE" in eff)
    return res


# --------------------------------------------------------------------------
# atom scoping
# --------------------------------------------------------------------------

def build_scopes(pol, runs):
    """For each atom, the run ids it could possibly change."""
    runs_by_unit = {}
    runs_by_service = {}
    runs_by_filter = {}
    runs_by_srckey = {}
    landing = {}
    for rid, run in runs.items():
        runs_by_unit.setdefault(run["unit"], []).append(rid)
        runs_by_service.setdefault(run["service"], []).append(rid)
        for f in (pol.units.get(run["unit"], {}).get("filters", ())):
            runs_by_filter.setdefault(f, []).append(rid)
        tr = pol.transitions.get((run["source_domain"], run["exec_type"]))
        land = tr[2] if tr else run["source_domain"]
        landing[rid] = land
        keys = set(pol.keys_of(run["source_domain"])) | set(pol.keys_of(land))
        for k in keys:
            runs_by_srckey.setdefault(k, []).append(rid)
    scopes = {}
    for aid, a in pol.atoms.items():
        k = a["kind"]
        if k == "pam_control_relax":
            line = pol.pam_by_rule.get(a["rule"])
            ids = runs_by_service.get(line["service"], []) if line else []
        elif k in ("cap_bounding_add", "cap_ambient_add"):
            ids = runs_by_unit.get(a["unit"], [])
        elif k in ("seccomp_rule_add", "seccomp_default_relax", "filter_unload"):
            ids = runs_by_filter.get(a["filter"], [])
        elif k == "te_allow_add":
            ids = runs_by_srckey.get(a["source"], [])
        else:
            ids = list(runs)
        scopes[aid] = frozenset(ids)
    return scopes, landing


# --------------------------------------------------------------------------
# cost controls
# --------------------------------------------------------------------------

def multiplier_pairs(pol):
    usable = [c for c in pol.controls if all(a in pol.atoms for a in c["atoms"])]
    if not usable:
        return [(1, 1)]
    good = []
    for m1 in range(1, 5):
        for m2 in range(1, 5):
            ok = True
            for c in usable:
                tot = 0
                for aid in c["atoms"]:
                    a = pol.atoms[aid]
                    mult = m1 if a["kind"] == "cap_bounding_add" else (
                        m2 if a["kind"] == "seccomp_rule_add" else 1)
                    tot += a["cost"] * mult
                if tot != c["total"]:
                    ok = False
                    break
            if ok:
                good.append((m1, m2))
    return good if good else [(1, 1)]


def eff_cost(pol, aid, mults):
    a = pol.atoms[aid]
    if a["kind"] == "cap_bounding_add":
        return a["cost"] * mults[0]
    if a["kind"] == "seccomp_rule_add":
        return a["cost"] * mults[1]
    return a["cost"]


# --------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------

def candidate_atoms(pol, run, result, landing, atoms_by_layer):
    """Permissible atoms naming the object the refusal named."""
    layer = result["layer"]
    out = []
    if layer == "pam":
        rule = result["rule"]
        for aid in atoms_by_layer["pam"]:
            if pol.atoms[aid].get("rule") == rule:
                out.append(aid)
    elif layer == "capability":
        cap = result["rule"]
        unit = run["unit"]
        for aid in atoms_by_layer["capability"]:
            a = pol.atoms[aid]
            if a.get("unit") == unit and a.get("cap") == cap:
                out.append(aid)
    elif layer == "seccomp":
        ev = result["event"]
        arch = ev["arch"]
        nr = ev["nr"] if ev["nr"] is not None else 0
        name = pol.syscall_tbl.get((arch, nr))
        loaded = set(pol.units.get(run["unit"], {}).get("filters", ()))
        for aid in atoms_by_layer["seccomp"]:
            a = pol.atoms[aid]
            if a.get("filter") not in loaded:
                continue
            if a["kind"] == "seccomp_rule_add":
                if a.get("arch") != arch or name is None or a.get("syscall") != name:
                    continue
            out.append(aid)
    elif layer == "selinux":
        ev = result["event"]
        src = run["source_domain"]
        land = landing[run["run_id"]]
        if ev["kind"] == "exec":
            refused_target = run["exec_type"]
        else:
            refused_target = ev["target_type"]
        tkeys = set(pol.keys_of(refused_target))
        for aid in atoms_by_layer["selinux"]:
            a = pol.atoms[aid]
            if a.get("source") not in (src, land):
                continue
            if a["kind"] == "te_allow_add" and a.get("tgt") not in tkeys:
                continue
            out.append(aid)
    return out


def settle(pol, runs, must_admit, permissible, scopes, landing, mults):
    atoms_by_layer = {}
    for aid in permissible:
        atoms_by_layer.setdefault(pol.atoms[aid]["layer"], []).append(aid)
    for v in atoms_by_layer.values():
        v.sort()
    for layer in ("pam", "selinux", "capability", "seccomp"):
        atoms_by_layer.setdefault(layer, [])

    chosen = {}
    trace = []
    rnd = 0
    while rnd < ROUND_CAP:
        st = State(pol, chosen)
        denied = []
        baseline = {}
        for rid in must_admit:
            r = replay(runs[rid], st)
            if r["verdict"] == "denied":
                denied.append(rid)
                baseline[rid] = r
        if not denied:
            break
        rnd += 1
        added = []
        cost_added = 0
        for rid in denied:
            run = runs[rid]
            base = baseline[rid]
            cands = candidate_atoms(pol, run, base, landing, atoms_by_layer)
            best = None
            for aid in cands:
                if aid in chosen:
                    continue
                trial = State(pol, set(chosen) | {aid})
                r = replay(run, trial)
                if r["verdict"] == "admitted" or r["seq"] > base["seq"]:
                    c = eff_cost(pol, aid, mults)
                    if best is None or (c, aid) < best:
                        best = (c, aid)
            if best is not None:
                chosen[best[1]] = rnd
                added.append(best[1])
                cost_added += best[0]
        st2 = State(pol, chosen)
        after = 0
        for rid in must_admit:
            if replay(runs[rid], st2)["verdict"] == "denied":
                after += 1
        trace.append({"round": rnd, "denied_before": len(denied), "denied_after": after,
                      "atoms_added": sorted(added), "cost_added": cost_added})
        if not added:
            break
    return chosen, trace, rnd


def shrink(pol, runs, must_admit, chosen):
    full = State(pol, chosen)
    target = [rid for rid in must_admit
              if replay(runs[rid], full)["verdict"] == "admitted"]
    cur = set(chosen)
    for aid in sorted(chosen, reverse=True):
        trial = cur - {aid}
        st = State(pol, trial)
        ok = True
        for rid in target:
            if replay(runs[rid], st)["verdict"] == "denied":
                ok = False
                break
        if ok:
            cur = trial
    return cur


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        return 2
    corpus_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(corpus_dir):
        return 2
    groups = load_groups(corpus_dir)
    for g in REQUIRED_GROUPS:
        if not groups.get(g):
            return 3
    os.makedirs(out_dir, exist_ok=True)

    pol = Policy(groups)
    runs, repair_counts, arch_repaired = build_runs(pol, groups)
    if not runs:
        return 3

    labels_recs = groups["runs-labels"]
    label_map = {}
    for rec in labels_recs:
        label_map[cid(rec["run_id"])] = rec["label"].strip()
    run_ids = sorted(runs)
    labels = {rid: label_map.get(rid, "unlabelled") or "unlabelled" for rid in run_ids}
    for rid in run_ids:
        if labels[rid] not in ("must_admit", "must_deny", "unlabelled"):
            labels[rid] = "unlabelled"

    must_admit = [r for r in run_ids if labels[r] == "must_admit"]
    must_deny = [r for r in run_ids if labels[r] == "must_deny"]

    shipped = State(pol)
    full = {rid: replay(runs[rid], shipped, collect=True) for rid in run_ids}

    scopes, landing = build_scopes(pol, runs)

    # ---- forbidden atoms ------------------------------------------------
    forbidden = {}
    for aid in pol.atom_order:
        # A must_deny run the shipped policy already admits is admitted by any
        # atom alone; any other must_deny run only by an atom whose scope
        # reaches it. The witness is the canonically first of all of them.
        wit = None
        scope = scopes[aid]
        st = State(pol, (aid,))
        for rid in must_deny:
            if full[rid]["verdict"] == "admitted":
                wit = rid
                break
            if rid in scope and replay(runs[rid], st)["verdict"] == "admitted":
                wit = rid
                break
        if wit is not None:
            forbidden[aid] = wit
    permissible = [aid for aid in pol.atom_order if aid not in forbidden]

    # ---- repairs_count per atom -----------------------------------------
    ma_denied = [rid for rid in must_admit if full[rid]["verdict"] == "denied"]
    repairs_count = {}
    for aid in pol.atom_order:
        layer = pol.atoms[aid]["layer"]
        scope = scopes[aid]
        cands = [rid for rid in ma_denied
                 if full[rid]["layer"] == layer and rid in scope]
        n = 0
        if cands:
            st = State(pol, (aid,))
            for rid in cands:
                if replay(runs[rid], st)["verdict"] == "admitted":
                    n += 1
        repairs_count[aid] = n

    # ---- the plan -------------------------------------------------------
    pairs = multiplier_pairs(pol)
    best = None
    for mults in pairs:
        chosen, trace, rounds_used = settle(pol, runs, must_admit, permissible,
                                            scopes, landing, mults)
        plan = shrink(pol, runs, must_admit, chosen)
        total = sum(eff_cost(pol, a, mults) for a in plan)
        key = (total, mults[0], mults[1])
        if best is None or key < best[0]:
            best = (key, mults, chosen, trace, rounds_used, plan)
    mults = best[1]
    chosen = best[2]
    trace = best[3]
    rounds_used = best[4]
    plan = best[5]

    plan_state = State(pol, plan)
    final = {rid: replay(runs[rid], plan_state) for rid in run_ids}

    residuals = [rid for rid in must_admit if final[rid]["verdict"] == "denied"]
    residual_status = "nonconvergent" if rounds_used >= ROUND_CAP else "unrepairable"

    # ---- minimality witnesses ------------------------------------------
    plan_admitted = [rid for rid in must_admit if final[rid]["verdict"] == "admitted"]
    witnesses = {}
    for aid in sorted(plan):
        st = State(pol, set(plan) - {aid})
        found = None
        for rid in plan_admitted:
            r = replay(runs[rid], st)
            if r["verdict"] == "denied":
                found = (rid, r["layer"], r["seq"])
                break
        witnesses[aid] = found if found else ("NONE", "NONE", 0)

    # ---- artifacts ------------------------------------------------------
    w = Writer(out_dir)

    # principal registry
    prn_runs = {}
    for rid in run_ids:
        prn_runs.setdefault(runs[rid]["principal"], []).append(rid)
    lines = []
    for pid in sorted(prn_runs):
        p = pol.principals.get(pid)
        rl = prn_runs[pid]
        if any(r in residuals for r in rl):
            disp = "residual"
        elif any(full[r]["verdict"] == "denied" and final[r]["verdict"] == "admitted"
                 for r in rl):
            disp = "granted"
        elif all(full[r]["verdict"] == "admitted" for r in rl):
            disp = "admitted"
        else:
            disp = "denied"
        lines.append(jdump({
            "principal_id": pid,
            "uid": p["uid"] if p else 0,
            "login": p["login"] if p else "",
            "display": p["display"] if p else "",
            "groups": p["groups"] if p else [],
            "inheritable": capsort(p["ti"]) if p else [],
            "permitted": capsort(p["tp"]) if p else [],
            "run_count": len(rl),
            "final_disposition": disp,
        }))
    w.write("principal_registry.jsonl", lines)

    # syscall index
    lines = [tsv_line(["arch", "nr", "syscall", "nr_padded"])]
    for arch, nr, name in pol.syscall_rows:
        lines.append(tsv_line([arch, nr, name, str(nr).zfill(4)]))
    w.write("syscall_index.tsv", lines)

    # pam stack resolved
    lines = [csv_line(["service", "phase", "position", "rank", "control", "module",
                       "rule_id", "gated_uid"])]
    for service in sorted({l["service"] for l in pol.pam_lines}):
        for phase in PHASES:
            group = pol.pam_by_sp.get((service, phase), [])
            for i, l in enumerate(group, 1):
                lines.append(csv_line([service, phase, i, l["rank"], l["control"],
                                       l["module"], l["rule_id"],
                                       "" if l["gate"] is None else l["gate"]]))
    w.write("pam_stack_resolved.csv", lines)

    # selinux type graph
    graph = {
        "types": {t: pol.type_attrs[t] for t in sorted(pol.type_attrs)},
        "attributes": {a: sorted(pol.attributes[a]) for a in sorted(pol.attributes)},
        "domains": sorted(t for t in pol.type_attrs if "domain" in pol.type_attrs[t]),
        "file_types": sorted(t for t in pol.type_attrs if "domain" not in pol.type_attrs[t]),
    }
    w.write("selinux_type_graph.json", [jdump(graph)])

    # seccomp program
    lines = []
    for r in pol.seccomp_rules:
        lines.append(jdump({
            "rule_id": r["rule_id"],
            "filter_id": r["filter_id"],
            "idx": r["idx"],
            "arch": r["arch"],
            "syscall": r["syscall"],
            "nr": pol.name_to_nr.get((r["arch"], r["syscall"])),
            "arg_index": r["arg_index"],
            "op": r["op"],
            "value": r["value"],
            "mask": r["mask"],
            "action": r["action"],
            "action_rank": ACTION_RANK.get(r["action"], len(ACTION_ORDER) + 1),
        }))
    w.write("seccomp_program.jsonl", lines)

    # pam verdicts
    lines = [csv_line(["run_id", "phase", "result", "deciding_rule", "deciding_module"])]
    for rid in run_ids:
        pv = full[rid]["pam"]
        for phase in PHASES:
            got = pv.get(phase)
            if got is None:
                got = shipped.pam_phase(runs[rid], phase)
            result, rule, module = got
            lines.append(csv_line([rid, phase, result, rule, module]))
    w.write("pam_verdicts.csv", lines)

    # capability ledger
    lines = [csv_line(["run_id", "unit", "binary", "nnp", "bounding_count",
                       "ambient_count", "permitted", "effective"])]
    for rid in run_ids:
        f = full[rid]
        lines.append(csv_line([rid, runs[rid]["unit"], runs[rid]["binary"],
                               "yes" if f["nnp"] else "no",
                               len(f["bounding"]), len(f["ambient"]),
                               capjoin(f["permitted"]), capjoin(f["effective"])]))
    w.write("capability_ledger.csv", lines)

    # domain transitions
    lines = []
    for rid in run_ids:
        f = full[rid]
        tr = f["transition"]
        if tr is None:
            tr = ("NONE", runs[rid]["source_domain"], True, True, True)
        lines.append(tsv_line([rid, runs[rid]["source_domain"], runs[rid]["exec_type"],
                               tr[0], tr[1],
                               "yes" if tr[2] else "no",
                               "yes" if tr[3] else "no",
                               "yes" if tr[4] else "no"]))
    w.write("domain_transitions.tsv", lines)

    # seccomp decisions
    lines = []
    for rid in run_ids:
        for seq, arch, nr, name, action, rule, matched, denies in full[rid]["syscalls"]:
            lines.append(jdump({
                "run_id": rid, "seq": seq, "arch": arch, "nr": nr,
                "syscall": name if name else "NONE",
                "action": action, "rule_id": rule,
                "matched_count": matched, "denies": bool(denies),
            }))
    w.write("seccomp_decisions.jsonl", lines)

    # arch dispatch
    ev_count = {a: 0 for a in ARCHES}
    unk_count = {a: 0 for a in ARCHES}
    run_count = {a: 0 for a in ARCHES}
    for rid in run_ids:
        d = runs[rid]["dispatch"]
        if d in run_count:
            run_count[d] += 1
        for seq, arch, nr, name, action, rule, matched, denies in full[rid]["syscalls"]:
            if arch in ev_count:
                ev_count[arch] += 1
                if name is None:
                    unk_count[arch] += 1
    lines = [tsv_line(["arch", "event_count", "run_count", "unknown_count",
                       "repaired_count"])]
    for a in ARCHES:
        lines.append(tsv_line([a, ev_count[a], run_count[a], unk_count[a],
                               arch_repaired[a]]))
    w.write("arch_dispatch.tsv", lines)

    # admission ledger
    rows = []
    for rid in run_ids:
        f = full[rid]
        rows.append((LAYER_RANK.get(f["layer"], 9), f["seq"],
                     [rid, labels[rid], f["verdict"], f["layer"], f["seq"],
                      f["rule"], f["reason"]]))
    rows.sort(key=lambda x: (x[0], x[1]))
    lines = [csv_line(["run_id", "label", "verdict", "layer", "seq", "rule_id", "reason"])]
    for _, _, vals in rows:
        lines.append(csv_line(vals))
    w.write("admission_ledger.csv", lines)

    # denial attribution
    lines = []
    distinct_rules = set()
    for rid in run_ids:
        f = full[rid]
        if f["verdict"] != "denied":
            continue
        ev = f["event"]
        layer = f["layer"]
        if layer == "pam":
            detail = "pam %s phase %s rule %s" % (runs[rid]["service"], ev["phase"],
                                                  f["rule"])
        elif layer == "selinux":
            detail = "allow %s %s : %s { %s }" % (
                runs[rid]["source_domain"], ev["target_type"], ev["tclass"],
                ",".join(ev["perms"]))
        elif layer == "capability":
            detail = "capability %s absent from the effective set" % f["rule"]
        else:
            nr = ev["nr"] if ev["nr"] is not None else 0
            detail = "seccomp %s on %s nr %d" % (f["reason"], ev["arch"], nr)
        if f["rule"] != "NONE":
            distinct_rules.add(f["rule"])
        lines.append(jdump({"run_id": rid, "layer": layer, "seq": f["seq"],
                            "rule_id": f["rule"], "reason": f["reason"],
                            "detail": detail}))
    w.write("denial_attribution.jsonl", lines)

    # blocked syscalls
    blocks = {}
    for rid in run_ids:
        for arch, name, action in full[rid]["blocks"]:
            key = (arch, name)
            e = blocks.get(key)
            if e is None:
                blocks[key] = [1, action]
            else:
                e[0] += 1
                if ACTION_RANK.get(action, 99) < ACTION_RANK.get(e[1], 99):
                    e[1] = action
    first_round = {}
    for aid in plan:
        a = pol.atoms[aid]
        if a["kind"] != "seccomp_rule_add":
            continue
        key = (a.get("arch", ""), a.get("syscall", ""))
        r = chosen[aid]
        if key not in first_round or r < first_round[key]:
            first_round[key] = r
    rows = []
    for (arch, name), (count, worst) in blocks.items():
        rows.append((first_round.get((arch, name), 0), arch, name, count, worst))
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    lines = [tsv_line(["arch", "syscall", "block_count", "first_round", "worst_action"])]
    for fr, arch, name, count, worst in rows:
        lines.append(tsv_line([arch, name, count, fr, worst]))
    w.write("blocked_syscalls.tsv", lines)

    # capability gaps
    gap_rows = []
    for rid in run_ids:
        f = full[rid]
        fp = pol.binaries.get(runs[rid]["binary"], {}).get("fp", frozenset())
        for cap, in_b, in_p in f["gaps"]:
            gap_rows.append((rid, cap, runs[rid]["unit"],
                             "yes" if in_b else "no", "yes" if in_p else "no",
                             -1 if cap in fp else 1))
    gap_rows.sort(key=lambda r: (r[0], r[1]))
    lines = [csv_line(["run_id", "capability", "unit", "in_bounding", "in_permitted",
                       "delta"])]
    for r in gap_rows:
        lines.append(csv_line(list(r)))
    w.write("capability_gaps.csv", lines)

    # audit continuity
    lines = []
    audit_broken = 0
    audit_broken_cap = 0
    for rid in run_ids:
        f = full[rid]
        cap_ok = bool(f["audit_cap"])
        acc = f["audit_access"]
        acc_ok = True if acc is None else bool(acc)
        if cap_ok and acc_ok:
            cont, reason = "intact", ""
        elif not cap_ok:
            cont, reason = "broken", "capability"
            audit_broken_cap += 1
        else:
            cont, reason = "broken", "access"
        if cont == "broken":
            audit_broken += 1
        lines.append(jdump({"run_id": rid, "audit_capability": cap_ok,
                            "audit_access": acc_ok, "continuity": cont,
                            "break_reason": reason}))
    w.write("audit_continuity.jsonl", lines)

    # relaxation atoms
    lines = [csv_line(["atom_id", "layer", "kind", "cost", "target", "repairs_count",
                       "forbidden", "witness_run"])]
    for aid in sorted(pol.atoms):
        a = pol.atoms[aid]
        lines.append(csv_line([aid, a["layer"], a["kind"], a["cost"], a["target"],
                               repairs_count[aid],
                               "yes" if aid in forbidden else "no",
                               forbidden.get(aid, "")]))
    w.write("relaxation_atoms.csv", lines)

    # forbidden atoms
    lines = []
    for aid in sorted(forbidden):
        a = pol.atoms[aid]
        lines.append(tsv_line([aid, a["layer"], a["kind"], a["cost"], forbidden[aid]]))
    w.write("forbidden_atoms.tsv", lines)

    # grant plan
    plan_rows = sorted(plan, key=lambda aid: (chosen[aid], eff_cost(pol, aid, mults), aid))
    lines = [csv_line(["atom_id", "layer", "kind", "cost", "round", "target"])]
    for aid in plan_rows:
        a = pol.atoms[aid]
        lines.append(csv_line([aid, a["layer"], a["kind"], a["cost"], chosen[aid],
                               a["target"]]))
    w.write("grant_plan.csv", lines)

    # iteration trace
    lines = [jdump({"round": t["round"], "denied_before": t["denied_before"],
                    "denied_after": t["denied_after"], "atoms_added": t["atoms_added"],
                    "cost_added": t["cost_added"]}) for t in trace]
    w.write("iteration_trace.jsonl", lines)

    # minimality witness
    lines = [csv_line(["atom_id", "witness_run", "witness_layer", "witness_seq"])]
    for aid in sorted(plan):
        wr, wl, ws = witnesses[aid]
        lines.append(csv_line([aid, wr, wl, ws]))
    w.write("minimality_witness.csv", lines)

    # residual denials
    lines = [tsv_line(["run_id", "label", "status", "rounds_used", "last_layer"])]
    for rid in residuals:
        lines.append(tsv_line([rid, labels[rid], residual_status, rounds_used,
                               final[rid]["layer"]]))
    w.write("residual_denials.tsv", lines)

    # conservation
    admitted_initial = sum(1 for r in run_ids if full[r]["verdict"] == "admitted")
    admitted_final = sum(1 for r in run_ids if final[r]["verdict"] == "admitted")
    must_admit_satisfied = sum(1 for r in must_admit if final[r]["verdict"] == "admitted")
    must_deny_held = sum(1 for r in must_deny if final[r]["verdict"] == "denied")
    plan_cost = sum(eff_cost(pol, a, mults) for a in plan)
    cons = {
        "total_runs": len(run_ids),
        "admitted_initial": admitted_initial,
        "denied_initial": len(run_ids) - admitted_initial,
        "admitted_final": admitted_final,
        "must_admit_total": len(must_admit),
        "must_admit_satisfied": must_admit_satisfied,
        "must_deny_total": len(must_deny),
        "must_deny_held": must_deny_held,
        "residual_count": len(residuals),
        "plan_cost": plan_cost,
        "plan_size": len(plan),
        "rounds_used": rounds_used,
    }
    w.write("conservation.json", [jdump(cons)])

    # summary
    layer_counts = {}
    for rid in run_ids:
        layer_counts[full[rid]["layer"]] = layer_counts.get(full[rid]["layer"], 0) + 1
    label_counts = {}
    for rid in run_ids:
        label_counts[labels[rid]] = label_counts.get(labels[rid], 0) + 1
    kind_counts = {}
    for aid in plan:
        k = pol.atoms[aid]["kind"]
        kind_counts[k] = kind_counts.get(k, 0) + 1
    summary = {
        "layer_counts": {k: layer_counts[k] for k in sorted(layer_counts)},
        "label_counts": {k: label_counts[k] for k in sorted(label_counts)},
        "arch_runs": {a: run_count[a] for a in ARCHES},
        "repair_counts": {k: repair_counts[k] for k in sorted(repair_counts)},
        "atom_kind_counts": {k: kind_counts[k] for k in sorted(kind_counts)},
        "blocked_syscall_rows": len(blocks),
        "capability_gap_rows": len(gap_rows),
        "audit_broken_runs": audit_broken,
        "forbidden_atom_rows": len(forbidden),
    }
    w.write("summary.json", [jdump(summary)])

    # manifest
    man = {}
    for name in ARTIFACTS:
        blob = w.written[name]
        man[name] = {"bytes": len(blob), "lines": blob.count(b"\n"),
                     "sha256": hashlib.sha256(blob).hexdigest()}
    w.write("manifest.json", [jdump(man)])

    # The program delivers itself beside the plan it wrote.
    with open(os.path.abspath(__file__), "rb") as fh:
        source = fh.read()
    with open(os.path.join(out_dir, "lgactl.py"), "wb") as fh:
        fh.write(source)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
