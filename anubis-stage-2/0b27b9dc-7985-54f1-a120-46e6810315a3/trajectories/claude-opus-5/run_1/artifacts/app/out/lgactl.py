#!/usr/bin/env python3
"""LGA least-grant admission control solver.

Usage: lgactl.py CORPUS_DIR OUT_DIR

Reads the flat record corpus of an LGA estate, replays the recorded run
population against the shipped policy of the four enforcement layers, settles
the least set of permissible grant atoms that admits every `must_admit` run,
and writes the twenty four data artifacts of SPEC-LGA.md section 13.
"""

import csv
import hashlib
import io
import json
import os
import sys
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN

# --------------------------------------------------------------------------
# constants
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
CAP_INDEX = {name: i for i, name in enumerate(CAP_TABLE)}

ACTIONS = ["KILL_PROCESS", "KILL_THREAD", "TRAP", "ERRNO", "USER_NOTIF",
           "TRACE", "LOG", "ALLOW"]
ACTION_RANK = {a: i + 1 for i, a in enumerate(ACTIONS)}
RANK_ACTION = {i + 1: a for i, a in enumerate(ACTIONS)}
ALLOW_RANK = ACTION_RANK["ALLOW"]
REFUSING_RANKS = {1, 2, 3, 5, 6}

PHASES = ["auth", "account", "session"]
PHASE_ORDER = {p: i for i, p in enumerate(PHASES)}
ARCHS = ["x86_64", "i386", "aarch64"]
LAYER_RANK = {"pam": 1, "selinux": 2, "capability": 3, "seccomp": 4, "NONE": 9}
ROUND_CAP = 8
ADVISORY_DEFAULT = ()

ARTIFACTS = [
    "principal_registry.jsonl", "syscall_index.tsv", "pam_stack_resolved.csv",
    "selinux_type_graph.json", "seccomp_program.jsonl", "pam_verdicts.csv",
    "capability_ledger.csv", "domain_transitions.tsv",
    "seccomp_decisions.jsonl", "arch_dispatch.tsv", "admission_ledger.csv",
    "denial_attribution.jsonl", "blocked_syscalls.tsv", "capability_gaps.csv",
    "audit_continuity.jsonl", "relaxation_atoms.csv", "forbidden_atoms.tsv",
    "grant_plan.csv", "iteration_trace.jsonl", "minimality_witness.csv",
    "residual_denials.tsv", "conservation.json", "summary.json",
]

NEEDED_GROUPS = ["runs-trace", "selinux-allow", "cap-units", "grant-atoms"]

# --------------------------------------------------------------------------
# canonical forms
# --------------------------------------------------------------------------


def nfc(s):
    return unicodedata.normalize("NFC", s)


def cid(s):
    """Canonical identifier form."""
    return nfc(s).strip().upper().replace("_", "-").replace(".", "-")


def ctype(s):
    """Canonical SELinux type (or attribute) name."""
    return nfc(s).strip().lower().replace("-", "_").replace(".", "_")


def ccap(s):
    """Canonical capability name."""
    t = nfc(s).strip()
    if t.isdigit():
        return CAP_TABLE[int(t)]
    return t.upper().replace("-", "_").replace(".", "_")


def cap_bit(s):
    t = nfc(s).strip()
    if t.isdigit():
        return int(t)
    return CAP_INDEX[t.upper().replace("-", "_").replace(".", "_")]


def parse_capset(field):
    """Read a capability set field into a frozenset of bit indices."""
    t = nfc(field or "").strip()
    if t == "" or t.lower() == "none":
        return frozenset()
    out = set()
    for part in t.replace(",", "+").split("+"):
        p = part.strip()
        if p == "" or p.lower() == "none":
            continue
        out.add(cap_bit(p))
    return frozenset(out)


def capset_names(bits):
    return [CAP_TABLE[b] for b in sorted(bits)]


def capset_text(bits):
    return "+".join(capset_names(bits)) if bits else "NONE"


def parse_int(field, default=0):
    t = (field or "").strip()
    if t == "":
        return default
    neg = t.startswith("-")
    if neg:
        t = t[1:]
    if t[:2].lower() == "0x":
        v = int(t, 16)
    else:
        v = int(t, 10)
    return -v if neg else v


# --------------------------------------------------------------------------
# corpus readers
# --------------------------------------------------------------------------


def _lines(text):
    out = []
    for ln in text.split("\n"):
        if ln.endswith("\r"):
            ln = ln[:-1]
        out.append(ln)
    if out and out[-1] == "":
        out.pop()
    return out


def _blank(s):
    return s.strip() == ""


def read_sep(text, delim):
    rows = list(csv.reader(io.StringIO(text.replace("\r\n", "\n")),
                           delimiter=delim, quotechar='"'))
    rows = [r for r in rows
            if r and not (len(r) == 1 and r[0].strip() == "")]
    if not rows:
        return []
    hdr = rows[0]
    recs = []
    for r in rows[1:]:
        recs.append({name: (r[i] if i < len(r) else "")
                     for i, name in enumerate(hdr)})
    return recs


def _unescape(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nx = s[i + 1]
            if nx == "n":
                out.append("\n")
                i += 2
                continue
            if nx == "t":
                out.append("\t")
                i += 2
                continue
            if nx == '"':
                out.append('"')
                i += 2
                continue
            if nx == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(c)
        i += 1
    return "".join(out)


def read_tsv(text):
    lines = [l for l in _lines(text) if not _blank(l)]
    if not lines:
        return []
    hdr = lines[0].split("\t")
    recs = []
    for ln in lines[1:]:
        vals = [_unescape(v) for v in ln.split("\t")]
        recs.append({name: (vals[i] if i < len(vals) else "")
                     for i, name in enumerate(hdr)})
    return recs


def read_fixed(text):
    lines = [l for l in _lines(text) if not _blank(l)]
    if not lines:
        return []
    fields = []
    for el in lines[0].split(";"):
        name, width = el.rsplit(":", 1)
        fields.append((name.strip(), int(width)))
    recs = []
    for ln in lines[1:]:
        d = {}
        pos = 0
        for name, width in fields:
            d[name] = ln[pos:pos + width].rstrip(" ")
            pos += width
        recs.append(d)
    return recs


def read_json(text):
    return json.loads(text)["records"]


def read_jsonl(text):
    return [json.loads(l) for l in _lines(text) if not _blank(l)]


def read_toml(text):
    recs = []
    cur = None
    for ln in _lines(text):
        s = ln.strip()
        if s == "[[record]]":
            cur = {}
            recs.append(cur)
            continue
        if _blank(s) or cur is None or "=" not in s:
            continue
        name, val = s.split("=", 1)
        val = val.strip()
        if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        out = []
        i = 0
        while i < len(val):
            if val[i] == "\\" and i + 1 < len(val) and val[i + 1] in '"\\':
                out.append(val[i + 1])
                i += 2
                continue
            out.append(val[i])
            i += 1
        cur[name.strip()] = "".join(out)
    return recs


def read_ini(text):
    recs = []
    cur = None
    for ln in _lines(text):
        s = ln.strip()
        if _blank(s):
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = {}
            recs.append(cur)
            continue
        if cur is None or "=" not in s:
            continue
        name, val = s.split("=", 1)
        cur[name.strip()] = val.strip()
    return recs


def read_properties(text):
    order = []
    byn = {}
    for ln in _lines(text):
        if _blank(ln):
            continue
        i = 0
        idx = -1
        n = len(ln)
        while i < n:
            if ln[i] == "\\":
                i += 2
                continue
            if ln[i] == "=":
                idx = i
                break
            i += 1
        if idx < 0:
            continue
        key = ln[:idx].strip()
        val = ln[idx + 1:].strip().replace("\\:", ":").replace("\\=", "=")
        parts = key.split(".")
        if len(parts) < 3:
            continue
        num = parts[1]
        name = ".".join(parts[2:])
        if num not in byn:
            byn[num] = {}
            order.append(num)
        byn[num][name] = val
    return [byn[n] for n in sorted(order, key=int)]


def read_logfmt(text):
    recs = []
    for ln in _lines(text):
        if _blank(ln):
            continue
        d = {}
        i = 0
        n = len(ln)
        while i < n:
            if ln[i] == " ":
                i += 1
                continue
            j = ln.find("=", i)
            if j < 0:
                break
            name = ln[i:j]
            i = j + 1
            if i < n and ln[i] == '"':
                i += 1
                buf = []
                while i < n:
                    if ln[i] == "\\" and i + 1 < n:
                        buf.append(ln[i])
                        buf.append(ln[i + 1])
                        i += 2
                        continue
                    if ln[i] == '"':
                        i += 1
                        break
                    buf.append(ln[i])
                    i += 1
                d[name] = _unescape("".join(buf))
            else:
                k = ln.find(" ", i)
                if k < 0:
                    k = n
                d[name] = ln[i:k]
                i = k
        if d:
            recs.append(d)
    return recs


def read_sexp(text):
    recs = []
    for ln in _lines(text):
        if _blank(ln):
            continue
        start = ln.find("(record")
        if start < 0:
            continue
        i = start + len("(record")
        n = len(ln)
        d = {}
        while i < n:
            if ln[i] != "(":
                i += 1
                continue
            j = ln.find('"', i)
            if j < 0:
                break
            name = ln[i + 1:j].strip()
            i = j + 1
            buf = []
            while i < n:
                if ln[i] == "\\" and i + 1 < n:
                    buf.append(ln[i])
                    buf.append(ln[i + 1])
                    i += 2
                    continue
                if ln[i] == '"':
                    i += 1
                    break
                buf.append(ln[i])
                i += 1
            d[name] = _unescape("".join(buf))
            while i < n and ln[i] != ")":
                i += 1
            i += 1
        if d:
            recs.append(d)
    return recs


def read_rfc5424(text):
    recs = []
    marker = "[lga@1 "
    for ln in _lines(text):
        if _blank(ln):
            continue
        start = ln.find(marker)
        if start < 0:
            continue
        i = start + len(marker)
        n = len(ln)
        d = {}
        while i < n:
            if ln[i] == " ":
                i += 1
                continue
            if ln[i] == "]":
                break
            j = ln.find('="', i)
            if j < 0:
                break
            name = ln[i:j]
            i = j + 2
            buf = []
            while i < n:
                if ln[i] == "\\" and i + 1 < n:
                    buf.append(ln[i])
                    buf.append(ln[i + 1])
                    i += 2
                    continue
                if ln[i] == '"':
                    i += 1
                    break
                buf.append(ln[i])
                i += 1
            d[name] = _unescape("".join(buf))
        if d:
            recs.append(d)
    return recs


READERS = {
    ".csv": lambda t: read_sep(t, ","),
    ".psv": lambda t: read_sep(t, "|"),
    ".ssv": lambda t: read_sep(t, " "),
    ".tsv": read_tsv,
    ".fixed": read_fixed,
    ".json": read_json,
    ".jsonl": read_jsonl,
    ".toml": read_toml,
    ".ini": read_ini,
    ".properties": read_properties,
    ".logfmt": read_logfmt,
    ".sexp": read_sexp,
    ".rfc5424": read_rfc5424,
}


def load_corpus(corpus_dir):
    groups = {}
    for fn in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, fn)
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(fn)
        if ext not in READERS or "-" not in stem:
            continue
        group = stem[:stem.rfind("-")]
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8-sig")
        groups.setdefault(group, []).extend(READERS[ext](text))
    return groups


def dedup(records, keyfn, last_wins=False):
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
    return [out[k] for k in order], out


# --------------------------------------------------------------------------
# atom targets
# --------------------------------------------------------------------------


def parse_target(target):
    """Split an atom target into its elements; `note` swallows the remainder."""
    elems = {}
    parts = target.split(";")
    for i, part in enumerate(parts):
        if part.startswith("note="):
            elems["note"] = ";".join(parts[i:])[len("note="):]
            break
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        elems[k.strip()] = v.strip()
    return elems


ELEM_CANON = {
    "rule": cid, "unit": cid, "filter": cid, "cap": ccap,
    "source": ctype, "target": ctype, "class": ctype,
    "perm": ctype, "arch": lambda s: nfc(s).strip().lower(),
    "syscall": lambda s: nfc(s).strip().lower(),
}


class Atom(object):
    __slots__ = ("aid", "layer", "kind", "cost", "target", "el", "eff_cost")

    def __init__(self, rec):
        self.aid = cid(rec["atom_id"])
        self.layer = nfc(rec.get("layer", "")).strip()
        self.kind = nfc(rec.get("kind", "")).strip()
        self.cost = parse_int(rec.get("cost", "0"))
        self.target = rec.get("target", "")
        raw = parse_target(self.target)
        el = {}
        for k, v in raw.items():
            if k == "note":
                continue
            fn = ELEM_CANON.get(k)
            el[k] = fn(v) if fn else nfc(v).strip()
        self.el = el
        self.eff_cost = self.cost


# --------------------------------------------------------------------------
# policy overlay
# --------------------------------------------------------------------------

EMPTY = frozenset()


class Policy(object):
    """The shipped policy plus a set of applied atoms."""

    __slots__ = ("atoms", "pam_relax", "allow_add", "bound_add", "amb_add",
                 "sec_allow", "sec_default", "sec_unload", "key")

    def __init__(self, atoms=()):
        self.atoms = frozenset(a.aid for a in atoms)
        pam_relax = set()
        allow_add = set()
        bound_add = {}
        amb_add = {}
        sec_allow = set()
        sec_default = set()
        sec_unload = set()
        for a in atoms:
            k = a.kind
            el = a.el
            if k == "pam_control_relax":
                pam_relax.add(el["rule"])
            elif k == "te_allow_add":
                allow_add.add((el["source"], el["target"], el["class"],
                               el["perm"]))
            elif k == "cap_bounding_add":
                bound_add.setdefault(el["unit"], set()).add(cap_bit(el["cap"]))
            elif k == "cap_ambient_add":
                bit = cap_bit(el["cap"])
                amb_add.setdefault(el["unit"], set()).add(bit)
                bound_add.setdefault(el["unit"], set()).add(bit)
            elif k == "seccomp_rule_add":
                sec_allow.add((el["filter"], el["arch"], el["syscall"]))
            elif k == "seccomp_default_relax":
                sec_default.add(el["filter"])
            elif k == "filter_unload":
                sec_unload.add(el["filter"])
        self.pam_relax = frozenset(pam_relax)
        self.allow_add = frozenset(allow_add)
        self.bound_add = {u: frozenset(v) for u, v in bound_add.items()}
        self.amb_add = {u: frozenset(v) for u, v in amb_add.items()}
        self.sec_allow = frozenset(sec_allow)
        self.sec_default = frozenset(sec_default)
        self.sec_unload = frozenset(sec_unload)


SHIPPED = Policy()


# --------------------------------------------------------------------------
# estate
# --------------------------------------------------------------------------


class Event(object):
    __slots__ = ("seq", "kind", "arch", "arch_repaired", "syscall_nr",
                 "arg0", "capability", "tclass", "perms", "target_type",
                 "required", "phase", "sc_name", "sc_filters")

    def __init__(self):
        self.sc_name = None
        self.sc_filters = None


class Run(object):
    __slots__ = ("rid", "events", "principal", "service", "unit", "binary",
                 "source_domain", "exec_type", "arch", "label", "pam_codes",
                 "filters", "audit_event", "exec_event")


class Estate(object):
    pass


def build_estate(groups):
    est = Estate()

    # ---- principals
    prec, _ = dedup(groups.get("principals", []),
                    lambda r: cid(r["principal_id"]))
    est.principals = {}
    for r in prec:
        pid = cid(r["principal_id"])
        est.principals[pid] = {
            "principal_id": pid,
            "uid": parse_int(r.get("uid", "0")),
            "login": nfc(r.get("login", "")),
            "display": nfc(r.get("display", "")),
            "groups": sorted(nfc(g).strip() for g in
                             (r.get("groups", "") or "").split("|")
                             if g.strip()),
            "ti": parse_capset(r.get("inh_thread", "")),
            "tp": parse_capset(r.get("perm_thread", "")),
        }

    # ---- pam stack
    est.pam_lines = {}
    est.pam_by_rule = {}
    for r in groups.get("pam-stack", []):
        rule = cid(r["rule_id"])
        service = nfc(r.get("service", "")).strip()
        phase = nfc(r.get("phase", "")).strip()
        flags = nfc(r.get("flags", "")) or ""
        gate = None
        for word in flags.replace(",", " ").split():
            if word.startswith("skip_if_uid_below="):
                gate = parse_int(word.split("=", 1)[1])
        line = {
            "rule_id": rule,
            "service": service,
            "phase": phase,
            "rank": parse_int(r.get("rank", "0")),
            "control": nfc(r.get("control", "")).strip(),
            "module": nfc(r.get("module", "")).strip(),
            "gate": gate,
        }
        est.pam_lines.setdefault((service, phase), []).append(line)
        est.pam_by_rule[rule] = line
    est.pam_rule_sets = {}
    for key, lines in est.pam_lines.items():
        lines.sort(key=lambda l: (l["rank"], l["module"], l["rule_id"]))
        est.pam_rule_sets[key] = frozenset(l["rule_id"] for l in lines)

    # ---- pam returns
    est.pam_returns = {}
    for r in groups.get("pam-returns", []):
        key = (cid(r["run_id"]), nfc(r.get("phase", "")).strip(),
               nfc(r.get("module", "")).strip())
        if key in est.pam_returns:
            continue
        est.pam_returns[key] = nfc(r.get("code", "")).strip()

    # ---- selinux types
    est.type_attrs = {}
    for r in groups.get("selinux-types", []):
        tname = ctype(r["type_name"])
        attrs = sorted({ctype(a) for a in
                        (r.get("attributes", "") or "").split("|")
                        if a.strip()})
        if tname not in est.type_attrs:
            est.type_attrs[tname] = attrs
    est.attr_types = {}
    for tname in sorted(est.type_attrs):
        for a in est.type_attrs[tname]:
            est.attr_types.setdefault(a, []).append(tname)
    est.attr_names = frozenset(est.attr_types)

    # ---- selinux allow
    base = {}
    for r in groups.get("selinux-allow", []):
        src = ctype(r.get("source", ""))
        tgt = ctype(r.get("target", ""))
        cls = ctype(r.get("tclass", ""))
        perms = {ctype(p) for p in (r.get("perms", "") or "").split(",")
                 if p.strip()}
        if not perms:
            continue
        key = (src, tgt, cls)
        cur = base.get(key)
        if cur is None:
            base[key] = perms
        else:
            cur.update(perms)
    est.allow_base = {k: frozenset(v) for k, v in base.items()}

    # ---- selinux transitions
    trans = {}
    for r in groups.get("selinux-transition", []):
        src = ctype(r.get("source", ""))
        ex = ctype(r.get("exec_type", ""))
        trans.setdefault((src, ex), []).append({
            "rule_id": cid(r["rule_id"]),
            "new_domain": ctype(r.get("new_domain", "")),
            "rank": parse_int(r.get("rank", "0")),
        })
    for key in trans:
        trans[key].sort(key=lambda t: (t["rank"], t["rule_id"]))
    est.transitions = {k: v[0] for k, v in trans.items()}

    # ---- units
    urec, _ = dedup(groups.get("cap-units", []), lambda r: cid(r["unit_id"]))
    est.units = {}
    for r in urec:
        uid = cid(r["unit_id"])
        est.units[uid] = {
            "unit_id": uid,
            "unit_name": nfc(r.get("unit_name", "")),
            "bounding": parse_capset(r.get("bounding", "")),
            "ambient": parse_capset(r.get("ambient", "")),
            "nnp": nfc(r.get("no_new_privs", "")).strip() == "true",
            "filters": [cid(f) for f in
                        (r.get("filters", "") or "").split("|") if f.strip()],
        }

    # ---- binaries
    brec, _ = dedup(groups.get("cap-filecaps", []),
                    lambda r: cid(r["binary_id"]))
    est.binaries = {}
    for r in brec:
        bid = cid(r["binary_id"])
        est.binaries[bid] = {
            "binary_id": bid,
            "path": nfc(r.get("path", "")),
            "fp": parse_capset(r.get("permitted_file", "")),
            "fi": parse_capset(r.get("inheritable_file", "")),
            "ebit": nfc(r.get("effective_bit", "")).strip() == "1",
        }

    # ---- advisory capabilities
    advisory = set()
    for r in groups.get("cap-required", []):
        if nfc(r.get("advisory", "")).strip().lower() == "yes":
            advisory.add(cap_bit(r["capability"]))
    est.advisory = frozenset(advisory)

    # ---- syscall table
    srec, _ = dedup(groups.get("arch-syscalls", []),
                    lambda r: (nfc(r["arch"]).strip(),
                               parse_int(r["nr"])))
    est.syscall_rows = []
    est.nr_name = {}
    name_nr = {}
    for r in srec:
        arch = nfc(r["arch"]).strip()
        nr = parse_int(r["nr"])
        name = nfc(r.get("syscall", "")).strip()
        est.syscall_rows.append((arch, nr, name))
        est.nr_name[(arch, nr)] = name
        key = (arch, name)
        if key not in name_nr or nr < name_nr[key]:
            name_nr[key] = nr
    est.name_nr = name_nr

    # ---- seccomp defaults
    drec, _ = dedup(groups.get("seccomp-defaults", []),
                    lambda r: cid(r["filter_id"]))
    est.filter_default = {}
    for r in drec:
        est.filter_default[cid(r["filter_id"])] = \
            nfc(r.get("default_action", "")).strip()

    # ---- seccomp filters
    est.sec_rules = []
    est.rules_by_key = {}
    for r in groups.get("seccomp-filters", []):
        rule = {
            "rule_id": cid(r["rule_id"]),
            "filter_id": cid(r["filter_id"]),
            "idx": parse_int(r.get("idx", "0")),
            "arch": nfc(r.get("arch", "")).strip().lower(),
            "syscall": nfc(r.get("syscall", "")).strip(),
            "arg_index": (None if (r.get("arg_index", "") or "").strip() == ""
                          else parse_int(r["arg_index"])),
            "op": nfc(r.get("op", "")).strip(),
            "value": parse_int(r.get("value", "")),
            "mask": parse_int(r.get("mask", "")),
            "action": nfc(r.get("action", "")).strip(),
        }
        rule["rank"] = ACTION_RANK[rule["action"]]
        est.sec_rules.append(rule)
        est.rules_by_key.setdefault(
            (rule["filter_id"], rule["arch"], rule["syscall"]), []).append(rule)
    for key in est.rules_by_key:
        est.rules_by_key[key].sort(key=lambda x: (x["idx"], x["rule_id"]))

    # ---- labels
    _, lmap = dedup(groups.get("runs-labels", []),
                    lambda r: cid(r["run_id"]), last_wins=True)
    est.labels = {k: nfc(v.get("label", "")).strip() for k, v in lmap.items()}

    # ---- atoms
    arec, _ = dedup(groups.get("grant-atoms", []), lambda r: cid(r["atom_id"]))
    est.atoms = {}
    for r in arec:
        a = Atom(r)
        est.atoms[a.aid] = a
    est.atom_ids = sorted(est.atoms)

    # ---- cost controls
    crec, _ = dedup(groups.get("cost-controls", []),
                    lambda r: cid(r["control_id"]))
    est.controls = []
    for r in crec:
        ids = [cid(x) for x in (r.get("atoms", "") or "").split("|")
               if x.strip()]
        est.controls.append((cid(r["control_id"]), ids,
                             parse_int(r.get("total", "0"))))

    # ---- audit events (advisory; recorded, never acted on)
    est.audit_events = groups.get("audit-events", [])
    est.dontaudit = groups.get("selinux-dontaudit", [])

    return est


def filter_default_rank(est, fid):
    action = est.filter_default.get(fid)
    if action is None:
        return ALLOW_RANK
    return ACTION_RANK[action]


# --------------------------------------------------------------------------
# run construction and repairs
# --------------------------------------------------------------------------


def build_runs(est, trace):
    buckets = {}
    for r in trace:
        buckets.setdefault(cid(r["run_id"]), []).append(r)

    repairs = {"arch": 0, "capability": 0, "number": 0, "perm": 0, "type": 0}
    arch_repaired = {a: 0 for a in ARCHS}
    runs = {}
    for rid in sorted(buckets):
        recs = sorted(buckets[rid], key=lambda r: parse_int(r["seq"]))
        first = recs[0]
        run = Run()
        run.rid = rid
        run.principal = cid(first["principal"])
        run.service = nfc(first.get("service", "")).strip()
        run.unit = cid(first["unit"])
        run.binary = cid(first["binary"])
        run.source_domain = ctype(first.get("source_domain", ""))
        run.exec_type = ctype(first.get("exec_type", ""))

        # dispatch architecture
        disp = ""
        for r in recs:
            if r["kind"] == "exec":
                disp = nfc(r.get("arch", "")).strip()
                break
        if disp == "":
            for r in recs:
                a = nfc(r.get("arch", "")).strip()
                if a:
                    disp = a
                    break
        if disp == "":
            disp = "x86_64"
        run.arch = disp

        events = []
        for r in recs:
            ev = Event()
            ev.seq = parse_int(r["seq"])
            ev.kind = nfc(r.get("kind", "")).strip()
            raw_arch = nfc(r.get("arch", "")).strip()
            if raw_arch == "" and ev.kind != "exec":
                ev.arch = disp
                ev.arch_repaired = True
                repairs["arch"] += 1
                if disp in arch_repaired:
                    arch_repaired[disp] += 1
            else:
                ev.arch = raw_arch if raw_arch else disp
                ev.arch_repaired = False

            raw_nr = nfc(r.get("syscall_nr", "")).strip()
            if raw_nr == "":
                ev.syscall_nr = None
            else:
                ev.syscall_nr = parse_int(raw_nr)
                if raw_nr[:2].lower() == "0x" or (len(raw_nr) > 1
                                                  and raw_nr[0] == "0"):
                    repairs["number"] += 1

            ev.arg0 = parse_int(r.get("arg0", ""))

            raw_cap = nfc(r.get("capability", "")).strip()
            if raw_cap == "":
                ev.capability = None
            else:
                ev.capability = cap_bit(raw_cap)
                if raw_cap != CAP_TABLE[ev.capability]:
                    repairs["capability"] += 1

            ev.tclass = ctype(r.get("tclass", "")) if r.get("tclass") else ""
            raw_perm = nfc(r.get("perm", "")).strip()
            if raw_perm == "":
                ev.perms = []
            else:
                ev.perms = [ctype(p) for p in raw_perm.split(",") if p.strip()]
                if "," in raw_perm:
                    repairs["perm"] += 1

            raw_tt = nfc(r.get("target_type", "")).strip()
            if raw_tt == "":
                ev.target_type = ""
            else:
                ev.target_type = ctype(raw_tt)
                if raw_tt != ev.target_type:
                    repairs["type"] += 1

            ev.required = nfc(r.get("required", "")).strip()
            ev.phase = nfc(r.get("phase", "")).strip()
            events.append(ev)

        run.events = events
        run.exec_event = next(e for e in events if e.kind == "exec")
        run.audit_event = next((e for e in events if e.kind == "audit"), None)
        run.label = est.labels.get(rid, "unlabelled")
        run.filters = est.units[run.unit]["filters"]

        run.pam_codes = {ph: {} for ph in PHASES}
        runs[rid] = run

    # pam return codes per run and phase
    for (r_id, ph, mod), code in est.pam_returns.items():
        run = runs.get(r_id)
        if run is None or ph not in run.pam_codes:
            continue
        run.pam_codes[ph][mod] = code

    # resolve syscall events against the architecture table
    for rid in sorted(runs):
        run = runs[rid]
        for ev in run.events:
            if ev.kind != "syscall":
                continue
            name = est.nr_name.get((ev.arch, ev.syscall_nr))
            ev.sc_name = name
            info = []
            if name is not None:
                for fid in run.filters:
                    matched = 0
                    best_rank = None
                    best_rule = None
                    for rule in est.rules_by_key.get((fid, ev.arch, name), ()):
                        if not rule_matches(rule, ev.arg0):
                            continue
                        matched += 1
                        if best_rank is None or rule["rank"] < best_rank:
                            best_rank = rule["rank"]
                            best_rule = rule["rule_id"]
                    info.append((fid, matched, best_rank, best_rule,
                                 filter_default_rank(est, fid)))
            ev.sc_filters = info

    return runs, repairs, arch_repaired


def rule_matches(rule, arg0):
    ai = rule["arg_index"]
    if ai is None:
        return True
    if ai != 0:
        return False
    op = rule["op"]
    val = rule["value"]
    if op == "EQ":
        return arg0 == val
    if op == "NE":
        return arg0 != val
    if op == "LT":
        return arg0 < val
    if op == "LE":
        return arg0 <= val
    if op == "GT":
        return arg0 > val
    if op == "GE":
        return arg0 >= val
    if op == "MASKED_EQ":
        return (arg0 & rule["mask"]) == val
    return False


# --------------------------------------------------------------------------
# layer engines
# --------------------------------------------------------------------------


class Engine(object):
    def __init__(self, est):
        self.est = est
        self._allow_memo = {}
        self._keys_memo = {}
        self._eff_memo = {}
        self._pam_memo = {}

    # -- SELinux ----------------------------------------------------------
    def keys_for(self, tname):
        k = self._keys_memo.get(tname)
        if k is None:
            k = [tname] + list(self.est.type_attrs.get(tname, ()))
            self._keys_memo[tname] = k
        return k

    def allowed(self, src, tgt, cls, perm, pol):
        memo = self._allow_memo
        mk = (src, tgt, cls, perm)
        base = memo.get(mk)
        if base is None:
            base = False
            ab = self.est.allow_base
            for s in self.keys_for(src):
                for t in self.keys_for(tgt):
                    ps = ab.get((s, t, cls))
                    if ps is not None and perm in ps:
                        base = True
                        break
                if base:
                    break
            memo[mk] = base
        if base:
            return True
        add = pol.allow_add
        if not add:
            return False
        for s in self.keys_for(src):
            for t in self.keys_for(tgt):
                if (s, t, cls, perm) in add:
                    return True
        return False

    def transition(self, run, pol):
        """Return (rule_id|None, landing|None, exec_ok, entry_ok, trans_ok)."""
        rec = self.est.transitions.get((run.source_domain, run.exec_type))
        if rec is None:
            return None, None, True, True, True
        landing = rec["new_domain"]
        ok_x = self.allowed(run.source_domain, run.exec_type, "file",
                            "execute", pol)
        ok_e = self.allowed(landing, run.exec_type, "file", "entrypoint", pol)
        ok_t = self.allowed(run.source_domain, landing, "process",
                            "transition", pol)
        return rec["rule_id"], landing, ok_x, ok_e, ok_t

    # -- capabilities -----------------------------------------------------
    def cap_sets(self, run, pol):
        unit = self.est.units[run.unit]
        badd = pol.bound_add.get(run.unit, EMPTY)
        aadd = pol.amb_add.get(run.unit, EMPTY)
        key = (run.unit, run.binary, run.principal, badd, aadd)
        got = self._eff_memo.get(key)
        if got is not None:
            return got
        binary = self.est.binaries[run.binary]
        prn = self.est.principals[run.principal]
        bounding = unit["bounding"] | badd
        ambient = unit["ambient"] | aadd
        if unit["nnp"]:
            from_file = binary["fp"] & bounding & prn["tp"]
        else:
            from_file = binary["fp"] & bounding
        permitted = (prn["ti"] & binary["fi"]) | from_file | ambient
        effective = permitted if binary["ebit"] else ambient
        got = (bounding, ambient, frozenset(permitted), frozenset(effective))
        self._eff_memo[key] = got
        return got

    # -- PAM --------------------------------------------------------------
    def pam_phase(self, run, phase, pol):
        key = (run.service, phase)
        lines = self.est.pam_lines.get(key, ())
        relevant = EMPTY
        if pol.pam_relax:
            rs = self.est.pam_rule_sets.get(key, EMPTY)
            relevant = frozenset(r for r in pol.pam_relax if r in rs)
        mk = (run.rid, phase, relevant)
        got = self._pam_memo.get(mk)
        if got is not None:
            return got
        uid = self.est.principals[run.principal]["uid"]
        codes = run.pam_codes.get(phase, {})
        first_fail = None
        first_fail_line = None
        first_opt = None
        first_opt_line = None
        flag = False
        result = None
        for line in lines:
            gate = line["gate"]
            if gate is not None and uid < gate:
                continue
            code = codes.get(line["module"], "ignore")
            if code == "ignore":
                continue
            ctrl = ("sufficient" if line["rule_id"] in relevant
                    else line["control"])
            if ctrl == "optional":
                if code != "success" and first_opt is None:
                    first_opt = code
                    first_opt_line = line
                continue
            flag = True
            if ctrl == "requisite":
                if code != "success":
                    result = (code, line, line)
                    break
            elif ctrl == "binding":
                if code != "success":
                    result = (code, line, line)
                else:
                    result = ("success", None, line)
                break
            elif ctrl == "sufficient":
                if code == "success" and first_fail is None:
                    result = ("success", None, line)
                    break
            elif ctrl == "required":
                if code != "success" and first_fail is None:
                    first_fail = code
                    first_fail_line = line
        if result is None:
            if first_fail is not None:
                result = (first_fail, first_fail_line, first_fail_line)
            elif flag:
                result = ("success", None, None)
            elif first_opt is not None:
                result = (first_opt, first_opt_line, first_opt_line)
            else:
                result = ("service_err", None, None)
        self._pam_memo[mk] = result
        return result

    # -- seccomp ----------------------------------------------------------
    def seccomp(self, ev, pol):
        """Return (rank, rule_id_text, matched_count)."""
        if ev.sc_name is None:
            return 1, "", 0
        name = ev.sc_name
        arch = ev.arch
        best_rank = None
        best_rule = ""
        matched = 0
        unload = pol.sec_unload
        sallow = pol.sec_allow
        sdef = pol.sec_default
        for fid, mcount, rrank, rrule, drank in ev.sc_filters:
            if fid in unload:
                continue
            matched += mcount
            if sallow and (fid, arch, name) in sallow:
                rank = ALLOW_RANK
                rid = ""
            elif rrank is not None:
                rank = rrank
                rid = rrule
            else:
                rank = ALLOW_RANK if fid in sdef else drank
                rid = ""
            if best_rank is None or rank < best_rank or \
                    (rank == best_rank and rid < best_rule):
                best_rank = rank
                best_rule = rid
        if best_rank is None:
            return ALLOW_RANK, "", 0
        return best_rank, best_rule, matched


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------


class Verdict(object):
    __slots__ = ("admitted", "layer", "seq", "rule", "reason", "event",
                 "cap_bit", "target", "perms", "tclass", "sc_rank")

    def __init__(self):
        self.admitted = True
        self.layer = "NONE"
        self.seq = 0
        self.rule = "NONE"
        self.reason = "admitted"
        self.event = None
        self.cap_bit = None
        self.target = ""
        self.perms = ()
        self.tclass = ""
        self.sc_rank = None


def replay(engine, run, pol, collect=False):
    """Walk a run's events. Returns (Verdict, detail) where detail is a dict
    of per-event reporting data when collect is true."""
    est = engine.est
    v = Verdict()
    detail = None
    if collect:
        detail = {"pam": [], "capuse": [], "syscall": []}

    tr_rule, landing, ok_x, ok_e, ok_t = engine.transition(run, pol)
    dom = landing if (tr_rule is not None and ok_x and ok_e and ok_t) \
        else run.source_domain
    if collect:
        detail["transition"] = (tr_rule, landing, ok_x, ok_e, ok_t, dom)
    detail_landing = landing

    bounding = ambient = permitted = effective = None

    for ev in run.events:
        kind = ev.kind
        ref = None
        if kind == "pam":
            code, rule_line, mod_line = engine.pam_phase(run, ev.phase, pol)
            if collect:
                detail["pam"].append((ev.phase, code, rule_line, mod_line))
            if code != "success":
                ref = ("pam", rule_line["rule_id"] if rule_line else "NONE",
                       "pam_" + code, None, "", (), "", None)
        elif kind == "exec":
            if tr_rule is not None and not (ok_x and ok_e and ok_t):
                missing = []
                if not ok_e:
                    missing.append("entrypoint")
                if not ok_x:
                    missing.append("execute")
                if not ok_t:
                    missing.append("transition")
                ref = ("selinux", tr_rule, "te_missing_" + sorted(missing)[0],
                       None, run.exec_type, tuple(ev.perms), ev.tclass, None)
        elif kind == "access":
            missing = [p for p in ev.perms
                       if not engine.allowed(dom, ev.target_type, ev.tclass,
                                             p, pol)]
            if missing:
                ref = ("selinux", "NONE", "te_denied_" + sorted(missing)[0],
                       None, ev.target_type, tuple(ev.perms), ev.tclass, None)
        elif kind == "capuse":
            if effective is None:
                bounding, ambient, permitted, effective = \
                    engine.cap_sets(run, pol)
            inside = ev.capability in effective
            if collect:
                detail["capuse"].append((ev, inside))
            if not inside and ev.capability not in est.advisory:
                ref = ("capability", CAP_TABLE[ev.capability], "cap_absent",
                       ev.capability, "", (), "", None)
        elif kind == "syscall":
            rank, rid, mcount = engine.seccomp(ev, pol)
            denies = rank in REFUSING_RANKS or \
                (rank == 4 and ev.required == "yes")
            if collect:
                detail["syscall"].append((ev, rank, rid, mcount, denies))
            if denies:
                ref = ("seccomp", rid if rid else "NONE",
                       "seccomp_" + RANK_ACTION[rank].lower(), None, "", (),
                       "", rank)
        if ref is not None and v.admitted:
            v.admitted = False
            v.seq = ev.seq
            v.event = ev
            (v.layer, v.rule, v.reason, v.cap_bit, v.target, v.perms,
             v.tclass, v.sc_rank) = ref
            if not collect:
                return v, None

    if v.admitted:
        v.layer = "NONE"
        v.seq = 0
        v.rule = "NONE"
        v.reason = "admitted"
    if collect:
        if effective is None:
            bounding, ambient, permitted, effective = engine.cap_sets(run, pol)
        detail["caps"] = (bounding, ambient, permitted, effective)
        detail["landing"] = detail_landing
        detail["dom"] = dom
    return v, detail


def first_refusal(engine, run, pol):
    v, _ = replay(engine, run, pol, collect=False)
    return v


# --------------------------------------------------------------------------
# plan construction
# --------------------------------------------------------------------------


def candidate_atoms(est, run, v, chosen, permissible_by_layer, landing):
    layer = v.layer
    out = []
    for a in permissible_by_layer.get(layer, ()):
        if a.aid in chosen:
            continue
        el = a.el
        if layer == "capability":
            if el.get("unit") != run.unit:
                continue
            if cap_bit(el.get("cap", "CAP_CHOWN")) != v.cap_bit:
                continue
        elif layer == "seccomp":
            if el.get("filter") not in run.filters:
                continue
            if a.kind == "seccomp_rule_add":
                ev = v.event
                if el.get("arch") != ev.arch or el.get("syscall") != ev.sc_name:
                    continue
        elif layer == "pam":
            if el.get("rule") != v.rule:
                continue
        elif layer == "selinux":
            src = el.get("source")
            if src != run.source_domain and src != landing:
                continue
            if a.kind == "te_allow_add":
                tgt = el.get("target")
                if tgt != v.target:
                    if not (tgt in est.attr_names and
                            tgt in est.type_attrs.get(v.target, ())):
                        continue
        else:
            continue
        out.append(a)
    return out


def build_plan(est, engine, must_admit_runs, permissible, mult):
    """Run the rounds and the shrink under one multiplier pair."""
    for a in permissible:
        a.eff_cost = a.cost * mult.get(a.kind, 1)
    by_layer = {}
    for a in permissible:
        by_layer.setdefault(a.layer, []).append(a)
    for k in by_layer:
        by_layer[k].sort(key=lambda a: a.aid)

    chosen = []
    chosen_set = set()
    trace = []
    rounds_used = 0
    pol = Policy([])

    while rounds_used < ROUND_CAP:
        denied = []
        for run in must_admit_runs:
            v = first_refusal(engine, run, pol)
            if not v.admitted:
                denied.append((run, v))
        if not denied:
            break
        rounds_used += 1
        added = []
        for run, v in denied:
            tr_rule, landing, _, _, _ = engine.transition(run, pol)
            cands = candidate_atoms(est, run, v, chosen_set, by_layer, landing)
            if not cands:
                continue
            best = None
            for a in cands:
                trial = Policy([est.atoms[x] for x in chosen_set] + [a])
                tv = first_refusal(engine, run, trial)
                if tv.admitted or tv.seq > v.seq:
                    key = (a.eff_cost, a.aid)
                    if best is None or key < best[0]:
                        best = (key, a)
            if best is None:
                continue
            a = best[1]
            chosen_set.add(a.aid)
            chosen.append(a)
            added.append(a)
            pol = Policy([est.atoms[x] for x in chosen_set])
        denied_after = 0
        for run in must_admit_runs:
            if not first_refusal(engine, run, pol).admitted:
                denied_after += 1
        trace.append({
            "round": rounds_used,
            "denied_before": len(denied),
            "denied_after": denied_after,
            "atoms_added": sorted(a.aid for a in added),
            "cost_added": sum(a.eff_cost for a in added),
        })
        if not added:
            break

    round_of = {}
    for entry in trace:
        for aid in entry["atoms_added"]:
            round_of[aid] = entry["round"]

    full = Policy([est.atoms[x] for x in chosen_set])
    base_admitted = [run for run in must_admit_runs
                     if first_refusal(engine, run, full).admitted]
    current = set(chosen_set)
    for aid in sorted(current, reverse=True):
        trial_ids = current - {aid}
        trial = Policy([est.atoms[x] for x in trial_ids])
        if all(first_refusal(engine, run, trial).admitted
               for run in base_admitted):
            current = trial_ids
    plan_ids = sorted(current)
    plan_cost = sum(est.atoms[a].eff_cost for a in plan_ids)
    return {
        "plan": plan_ids,
        "round_of": round_of,
        "trace": trace,
        "rounds_used": rounds_used,
        "plan_cost": plan_cost,
        "mult": mult,
    }


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------


class Out(object):
    def __init__(self, out_dir):
        self.dir = out_dir
        self.written = {}

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        self.written[name] = data

    def write_text(self, name, text):
        self.write(name, text.encode("utf-8"))

    def write_csv(self, name, header, rows):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n", quotechar='"',
                       quoting=csv.QUOTE_MINIMAL)
        if header:
            w.writerow(header)
        for r in rows:
            w.writerow(r)
        self.write_text(name, buf.getvalue())

    def write_tsv(self, name, header, rows):
        def esc(v):
            s = str(v)
            return s.replace("\\", "\\\\").replace("\t", "\\t") \
                    .replace("\n", "\\n")
        lines = []
        if header:
            lines.append("\t".join(header))
        for r in rows:
            lines.append("\t".join(esc(c) for c in r))
        self.write_text(name, "".join(l + "\n" for l in lines))

    def write_jsonl(self, name, objs):
        parts = []
        for o in objs:
            parts.append(json.dumps(o, separators=(",", ":"),
                                    ensure_ascii=False))
            parts.append("\n")
        self.write_text(name, "".join(parts))

    def write_json(self, name, obj):
        self.write_text(name, json.dumps(obj, separators=(",", ":"),
                                         ensure_ascii=False) + "\n")


def yn(b):
    return "yes" if b else "no"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main(argv):
    if len(argv) != 3:
        return 2
    corpus_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(corpus_dir):
        return 2
    groups = load_corpus(corpus_dir)
    for g in NEEDED_GROUPS:
        if not groups.get(g):
            return 3
    os.makedirs(out_dir, exist_ok=True)

    est = build_estate(groups)
    runs, repairs, arch_repaired = build_runs(est, groups["runs-trace"])
    engine = Engine(est)
    run_ids = sorted(runs)
    run_list = [runs[r] for r in run_ids]

    # ---- shipped replay ------------------------------------------------
    shipped = {}
    details = {}
    for run in run_list:
        v, d = replay(engine, run, SHIPPED, collect=True)
        shipped[run.rid] = v
        details[run.rid] = d

    must_admit = [r for r in run_list if r.label == "must_admit"]
    must_deny = [r for r in run_list if r.label == "must_deny"]

    # ---- forbidden atoms ----------------------------------------------
    # an atom of layer L can only move a run whose first refusal is at L,
    # so only those runs (and any already admitted) can be admitted by it
    deny_by_layer = {}
    for layer in sorted(set(LAYER_RANK) | {"NONE"}):
        deny_by_layer[layer] = [run for run in must_deny
                                if shipped[run.rid].layer in (layer, "NONE")]
    admit_by_layer = {}
    for run in must_admit:
        admit_by_layer.setdefault(shipped[run.rid].layer, []).append(run)

    forbidden = {}
    repairs_count = {}
    for aid in est.atom_ids:
        a = est.atoms[aid]
        pol = Policy([a])
        witness = ""
        for run in deny_by_layer.get(a.layer, ()):
            if first_refusal(engine, run, pol).admitted:
                witness = run.rid
                break
        forbidden[aid] = witness
        n = 0
        for run in admit_by_layer.get(a.layer, ()):
            if first_refusal(engine, run, pol).admitted:
                n += 1
        repairs_count[aid] = n

    permissible = [est.atoms[a] for a in est.atom_ids if not forbidden[a]]

    # ---- cost multipliers ---------------------------------------------
    catalogue = set(est.atom_ids)
    usable = [(ids, total) for _, ids, total in est.controls
              if ids and all(i in catalogue for i in ids)]

    def eff(kind, cost, m1, m2):
        if kind == "cap_bounding_add":
            return cost * m1
        if kind == "seccomp_rule_add":
            return cost * m2
        return cost

    if not usable:
        pairs = [(1, 1)]
    else:
        pairs = []
        for m1 in range(1, 5):
            for m2 in range(1, 5):
                ok = True
                for ids, total in usable:
                    s = sum(eff(est.atoms[i].kind, est.atoms[i].cost, m1, m2)
                            for i in ids)
                    if s != total:
                        ok = False
                        break
                if ok:
                    pairs.append((m1, m2))
        if not pairs:
            pairs = [(1, 1)]

    results = []
    for m1, m2 in pairs:
        mult = {"cap_bounding_add": m1, "seccomp_rule_add": m2}
        results.append(build_plan(est, engine, must_admit, permissible, mult))
    results.sort(key=lambda r: (r["plan_cost"],
                                r["mult"]["cap_bounding_add"],
                                r["mult"]["seccomp_rule_add"]))
    chosen_result = results[0]
    m1 = chosen_result["mult"]["cap_bounding_add"]
    m2 = chosen_result["mult"]["seccomp_rule_add"]
    for a in est.atoms.values():
        a.eff_cost = eff(a.kind, a.cost, m1, m2)

    plan_ids = chosen_result["plan"]
    round_of = chosen_result["round_of"]
    trace = chosen_result["trace"]
    rounds_used = chosen_result["rounds_used"]
    plan_pol = Policy([est.atoms[a] for a in plan_ids])

    final = {}
    for run in run_list:
        final[run.rid] = first_refusal(engine, run, plan_pol)

    residuals = [run for run in must_admit if not final[run.rid].admitted]
    residual_ids = {r.rid for r in residuals}
    residual_status = ("nonconvergent" if rounds_used >= ROUND_CAP
                       else "unrepairable")

    # ---- minimality witnesses -----------------------------------------
    plan_admitted = [run for run in must_admit if final[run.rid].admitted]
    witnesses = {}
    for aid in plan_ids:
        trial = Policy([est.atoms[x] for x in plan_ids if x != aid])
        wr, wl, ws = "NONE", "NONE", 0
        for run in plan_admitted:
            v = first_refusal(engine, run, trial)
            if not v.admitted:
                wr, wl, ws = run.rid, v.layer, v.seq
                break
        witnesses[aid] = (wr, wl, ws)

    out = Out(out_dir)

    # ---- 1. principal_registry ----------------------------------------
    prn_runs = {}
    for run in run_list:
        prn_runs.setdefault(run.principal, []).append(run)
    objs = []
    granted_principals = 0
    for pid in sorted(prn_runs):
        p = est.principals[pid]
        rs = prn_runs[pid]
        if any(r.rid in residual_ids for r in rs):
            disp = "residual"
        elif any(not shipped[r.rid].admitted and final[r.rid].admitted
                 for r in rs):
            disp = "granted"
        elif all(shipped[r.rid].admitted for r in rs):
            disp = "admitted"
        else:
            disp = "denied"
        if disp == "granted":
            granted_principals += 1
        objs.append({
            "principal_id": pid,
            "uid": p["uid"],
            "login": p["login"],
            "display": p["display"],
            "groups": p["groups"],
            "inheritable": capset_names(p["ti"]),
            "permitted": capset_names(p["tp"]),
            "run_count": len(rs),
            "final_disposition": disp,
        })
    out.write_jsonl("principal_registry.jsonl", objs)

    # ---- 2. syscall_index ---------------------------------------------
    rows = []
    for arch, nr, name in sorted(est.syscall_rows, key=lambda x: (x[0], x[1])):
        rows.append([arch, str(nr), name, "%04d" % nr])
    out.write_tsv("syscall_index.tsv",
                  ["arch", "nr", "syscall", "nr_padded"], rows)

    # ---- 3. pam_stack_resolved ----------------------------------------
    rows = []
    for service in sorted({k[0] for k in est.pam_lines}):
        for phase in PHASES:
            lines = est.pam_lines.get((service, phase), ())
            for i, line in enumerate(lines):
                rows.append([service, phase, str(i + 1), str(line["rank"]),
                             line["control"], line["module"], line["rule_id"],
                             "" if line["gate"] is None else str(line["gate"])])
    out.write_csv("pam_stack_resolved.csv",
                  ["service", "phase", "position", "rank", "control",
                   "module", "rule_id", "gated_uid"], rows)

    # ---- 4. selinux_type_graph ----------------------------------------
    types_map = {t: est.type_attrs[t] for t in sorted(est.type_attrs)}
    attrs_map = {a: sorted(est.attr_types[a]) for a in sorted(est.attr_types)}
    domains = sorted(t for t in est.type_attrs
                     if "domain" in est.type_attrs[t])
    dset = set(domains)
    file_types = sorted(t for t in est.type_attrs if t not in dset)
    out.write_json("selinux_type_graph.json", {
        "types": types_map,
        "attributes": attrs_map,
        "domains": domains,
        "file_types": file_types,
    })

    # ---- 5. seccomp_program -------------------------------------------
    objs = []
    for rule in sorted(est.sec_rules,
                       key=lambda r: (r["filter_id"], r["idx"], r["rule_id"])):
        nr = est.name_nr.get((rule["arch"], rule["syscall"]))
        objs.append({
            "rule_id": rule["rule_id"],
            "filter_id": rule["filter_id"],
            "idx": rule["idx"],
            "arch": rule["arch"],
            "syscall": rule["syscall"],
            "nr": nr,
            "arg_index": rule["arg_index"],
            "op": rule["op"],
            "value": rule["value"],
            "mask": rule["mask"],
            "action": rule["action"],
            "action_rank": rule["rank"],
        })
    out.write_jsonl("seccomp_program.jsonl", objs)

    # ---- 6. pam_verdicts ----------------------------------------------
    rows = []
    for run in run_list:
        for phase, code, rule_line, mod_line in sorted(
                details[run.rid]["pam"], key=lambda p: PHASE_ORDER[p[0]]):
            rows.append([run.rid, phase, code,
                         rule_line["rule_id"] if rule_line else "NONE",
                         mod_line["module"] if mod_line else "NONE"])
    out.write_csv("pam_verdicts.csv",
                  ["run_id", "phase", "result", "deciding_rule",
                   "deciding_module"], rows)

    # ---- 7. capability_ledger -----------------------------------------
    rows = []
    for run in run_list:
        bounding, ambient, permitted, effective = details[run.rid]["caps"]
        rows.append([run.rid, run.unit, run.binary,
                     yn(est.units[run.unit]["nnp"]),
                     str(len(bounding)), str(len(ambient)),
                     capset_text(permitted), capset_text(effective)])
    out.write_csv("capability_ledger.csv",
                  ["run_id", "unit", "binary", "nnp", "bounding_count",
                   "ambient_count", "permitted", "effective"], rows)

    # ---- 8. domain_transitions ----------------------------------------
    rows = []
    for run in run_list:
        tr_rule, landing, ok_x, ok_e, ok_t, dom = \
            details[run.rid]["transition"]
        rows.append([run.rid, run.source_domain, run.exec_type,
                     tr_rule if tr_rule else "NONE", dom,
                     yn(ok_x), yn(ok_e), yn(ok_t)])
    out.write_tsv("domain_transitions.tsv", None, rows)

    # ---- 9. seccomp_decisions -----------------------------------------
    objs = []
    for run in run_list:
        for ev, rank, rid, mcount, denies in details[run.rid]["syscall"]:
            objs.append({
                "run_id": run.rid,
                "seq": ev.seq,
                "arch": ev.arch,
                "nr": ev.syscall_nr,
                "syscall": ev.sc_name if ev.sc_name is not None else "NONE",
                "action": RANK_ACTION[rank],
                "rule_id": rid if rid else "NONE",
                "matched_count": mcount,
                "denies": bool(denies),
            })
    out.write_jsonl("seccomp_decisions.jsonl", objs)

    # ---- 10. arch_dispatch --------------------------------------------
    ev_count = {a: 0 for a in ARCHS}
    run_count = {a: 0 for a in ARCHS}
    unknown = {a: 0 for a in ARCHS}
    for run in run_list:
        if run.arch in run_count:
            run_count[run.arch] += 1
        for ev in run.events:
            if ev.kind != "syscall":
                continue
            if ev.arch in ev_count:
                ev_count[ev.arch] += 1
                if ev.sc_name is None:
                    unknown[ev.arch] += 1
    rows = [[a, str(ev_count[a]), str(run_count[a]), str(unknown[a]),
             str(arch_repaired[a])] for a in ARCHS]
    out.write_tsv("arch_dispatch.tsv",
                  ["arch", "event_count", "run_count", "unknown_count",
                   "repaired_count"], rows)

    # ---- 11. admission_ledger -----------------------------------------
    ordered = sorted(run_list,
                     key=lambda r: (LAYER_RANK[shipped[r.rid].layer],
                                    shipped[r.rid].seq, r.rid))
    rows = []
    for run in ordered:
        v = shipped[run.rid]
        rows.append([run.rid, run.label,
                     "admitted" if v.admitted else "denied",
                     v.layer, str(v.seq), v.rule, v.reason])
    out.write_csv("admission_ledger.csv",
                  ["run_id", "label", "verdict", "layer", "seq", "rule_id",
                   "reason"], rows)

    # ---- 12. denial_attribution ---------------------------------------
    objs = []
    for run in run_list:
        v = shipped[run.rid]
        if v.admitted:
            continue
        if v.layer == "pam":
            det = "pam %s phase %s rule %s" % (run.service, v.event.phase,
                                               v.rule)
        elif v.layer == "selinux":
            det = "allow %s %s : %s { %s }" % (
                run.source_domain, v.target, v.tclass, ",".join(v.perms))
        elif v.layer == "capability":
            det = "capability %s absent from the effective set" % v.rule
        else:
            det = "seccomp %s on %s nr %d" % (v.reason, v.event.arch,
                                              v.event.syscall_nr)
        objs.append({
            "run_id": run.rid,
            "layer": v.layer,
            "seq": v.seq,
            "rule_id": v.rule,
            "reason": v.reason,
            "detail": det,
        })
    out.write_jsonl("denial_attribution.jsonl", objs)

    # ---- 13. blocked_syscalls -----------------------------------------
    blocked = {}
    for run in run_list:
        for ev, rank, rid, mcount, denies in details[run.rid]["syscall"]:
            if not denies:
                continue
            key = (ev.arch, ev.sc_name if ev.sc_name is not None else "NONE")
            cur = blocked.get(key)
            if cur is None:
                blocked[key] = [1, rank]
            else:
                cur[0] += 1
                if rank < cur[1]:
                    cur[1] = rank
    first_round = {}
    for aid in plan_ids:
        a = est.atoms[aid]
        if a.kind != "seccomp_rule_add":
            continue
        key = (a.el.get("arch"), a.el.get("syscall"))
        r = round_of.get(aid, 0)
        if key not in first_round or r < first_round[key]:
            first_round[key] = r
    rows = []
    for key in blocked:
        count, rank = blocked[key]
        rows.append((first_round.get(key, 0), key[0], key[1], count,
                     RANK_ACTION[rank]))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    out.write_tsv("blocked_syscalls.tsv",
                  ["arch", "syscall", "block_count", "first_round",
                   "worst_action"],
                  [[r[1], r[2], str(r[3]), str(r[0]), r[4]] for r in rows])

    # ---- 14. capability_gaps ------------------------------------------
    rows = []
    for run in run_list:
        bounding, ambient, permitted, effective = details[run.rid]["caps"]
        fp = est.binaries[run.binary]["fp"]
        gaps = []
        for ev, inside in details[run.rid]["capuse"]:
            if inside:
                continue
            cap = CAP_TABLE[ev.capability]
            gaps.append((cap, [run.rid, cap, run.unit,
                               yn(ev.capability in bounding),
                               yn(ev.capability in permitted),
                               "-1" if ev.capability in fp else "1"]))
        gaps.sort(key=lambda g: g[0])
        rows.extend(g[1] for g in gaps)
    out.write_csv("capability_gaps.csv",
                  ["run_id", "capability", "unit", "in_bounding",
                   "in_permitted", "delta"], rows)

    # ---- 15. audit_continuity -----------------------------------------
    objs = []
    audit_broken = 0
    for run in run_list:
        d = details[run.rid]
        effective = d["caps"][3]
        has_cap = CAP_INDEX["CAP_AUDIT_WRITE"] in effective
        ev = run.audit_event
        if ev is None:
            access_ok = True
        else:
            access_ok = all(engine.allowed(d["dom"], ev.target_type,
                                           ev.tclass, p, SHIPPED)
                            for p in ev.perms)
        if has_cap and access_ok:
            cont, reason = "intact", ""
        elif not has_cap:
            cont, reason = "broken", "capability"
        else:
            cont, reason = "broken", "access"
        if cont == "broken":
            audit_broken += 1
        objs.append({
            "run_id": run.rid,
            "audit_capability": bool(has_cap),
            "audit_access": bool(access_ok),
            "continuity": cont,
            "break_reason": reason,
        })
    out.write_jsonl("audit_continuity.jsonl", objs)

    # ---- 16. relaxation_atoms -----------------------------------------
    rows = []
    for aid in est.atom_ids:
        a = est.atoms[aid]
        rows.append([aid, a.layer, a.kind, str(a.cost), a.target,
                     str(repairs_count[aid]),
                     yn(bool(forbidden[aid])), forbidden[aid]])
    out.write_csv("relaxation_atoms.csv",
                  ["atom_id", "layer", "kind", "cost", "target",
                   "repairs_count", "forbidden", "witness_run"], rows)

    # ---- 17. forbidden_atoms ------------------------------------------
    rows = []
    for aid in est.atom_ids:
        if not forbidden[aid]:
            continue
        a = est.atoms[aid]
        rows.append([aid, a.layer, a.kind, str(a.cost), forbidden[aid]])
    out.write_tsv("forbidden_atoms.tsv", None, rows)
    forbidden_rows = len(rows)

    # ---- 18. grant_plan -----------------------------------------------
    plan_sorted = sorted(plan_ids,
                         key=lambda x: (round_of.get(x, 0),
                                        est.atoms[x].eff_cost, x))
    rows = []
    for aid in plan_sorted:
        a = est.atoms[aid]
        rows.append([aid, a.layer, a.kind, str(a.cost),
                     str(round_of.get(aid, 0)), a.target])
    out.write_csv("grant_plan.csv",
                  ["atom_id", "layer", "kind", "cost", "round", "target"],
                  rows)

    # ---- 19. iteration_trace ------------------------------------------
    out.write_jsonl("iteration_trace.jsonl", [
        {"round": t["round"], "denied_before": t["denied_before"],
         "denied_after": t["denied_after"], "atoms_added": t["atoms_added"],
         "cost_added": t["cost_added"]} for t in trace])

    # ---- 20. minimality_witness ---------------------------------------
    rows = []
    for aid in sorted(plan_ids):
        wr, wl, ws = witnesses[aid]
        rows.append([aid, wr, wl, str(ws)])
    out.write_csv("minimality_witness.csv",
                  ["atom_id", "witness_run", "witness_layer", "witness_seq"],
                  rows)

    # ---- 21. residual_denials -----------------------------------------
    rows = []
    for run in sorted(residuals, key=lambda r: r.rid):
        rows.append([run.rid, run.label, residual_status, str(rounds_used),
                     final[run.rid].layer])
    out.write_tsv("residual_denials.tsv",
                  ["run_id", "label", "status", "rounds_used", "last_layer"],
                  rows)

    # ---- 22. conservation ---------------------------------------------
    admitted_initial = sum(1 for r in run_list if shipped[r.rid].admitted)
    admitted_final = sum(1 for r in run_list if final[r.rid].admitted)
    must_admit_sat = sum(1 for r in must_admit if final[r.rid].admitted)
    must_deny_held = sum(1 for r in must_deny if not final[r.rid].admitted)
    plan_cost = sum(est.atoms[a].eff_cost for a in plan_ids)
    out.write_json("conservation.json", {
        "total_runs": len(run_list),
        "admitted_initial": admitted_initial,
        "denied_initial": len(run_list) - admitted_initial,
        "admitted_final": admitted_final,
        "must_admit_total": len(must_admit),
        "must_admit_satisfied": must_admit_sat,
        "must_deny_total": len(must_deny),
        "must_deny_held": must_deny_held,
        "residual_count": len(residuals),
        "plan_cost": plan_cost,
        "plan_size": len(plan_ids),
        "rounds_used": rounds_used,
    })

    # ---- 23. summary --------------------------------------------------
    layer_counts = {}
    for run in run_list:
        layer_counts[shipped[run.rid].layer] = \
            layer_counts.get(shipped[run.rid].layer, 0) + 1
    label_counts = {}
    for run in run_list:
        label_counts[run.label] = label_counts.get(run.label, 0) + 1
    kind_counts = {}
    for aid in plan_ids:
        k = est.atoms[aid].kind
        kind_counts[k] = kind_counts.get(k, 0) + 1
    out.write_json("summary.json", {
        "layer_counts": {k: layer_counts[k] for k in sorted(layer_counts)},
        "label_counts": {k: label_counts[k] for k in sorted(label_counts)},
        "arch_runs": {a: run_count[a] for a in ARCHS},
        "repair_counts": {k: repairs[k] for k in sorted(repairs)},
        "atom_kind_counts": {k: kind_counts[k] for k in sorted(kind_counts)},
        "blocked_syscall_rows": len(blocked),
        "capability_gap_rows": sum(
            1 for run in run_list
            for _ev, inside in details[run.rid]["capuse"] if not inside),
        "audit_broken_runs": audit_broken,
        "forbidden_atom_rows": forbidden_rows,
    })

    # ---- 24. manifest -------------------------------------------------
    manifest = {}
    for name in ARTIFACTS:
        data = out.written[name]
        manifest[name] = {
            "bytes": len(data),
            "lines": data.count(b"\n"),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    out.write_json("manifest.json", manifest)

    # ---- closing figures ----------------------------------------------
    total_repairs = sum(repairs.values())
    dead_atoms = sum(1 for aid in est.atom_ids
                     if not forbidden[aid] and repairs_count[aid] == 0)
    if plan_ids:
        mean = Decimal(plan_cost) / Decimal(len(plan_ids))
        mean_txt = str(mean.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
    else:
        mean_txt = "0.00"
    sys.stderr.write(
        "repairs_total=%d\npermissible_atoms_repairing_nothing=%d\n"
        "plan_mean_cost=%s\ngranted_principals=%d\n"
        "multipliers=cap_bounding_add:%d,seccomp_rule_add:%d\n"
        % (total_repairs, dead_atoms, mean_txt, granted_principals, m1, m2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
