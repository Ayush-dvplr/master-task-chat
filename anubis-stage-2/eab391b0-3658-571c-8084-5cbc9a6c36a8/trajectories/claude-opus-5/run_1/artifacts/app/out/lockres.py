#!/usr/bin/env python3
"""Workspace dependency lock resolver.

Usage: python3 lockres.py IN_DIR OUT_DIR

Reads index.jsonl, workspace.json, pins.csv, lock.prev.json and manifest.json
from IN_DIR and writes lock.json, issues.jsonl and summary.json into OUT_DIR.
The mode word in manifest.json selects the rule variants used for the run.
"""

import csv
import hashlib
import json
import os
import re
import sys
from collections import deque

PKG_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
NUM_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
VER_RE = re.compile(r"^([^.]+)\.([^.]+)\.([^.-]+)(?:-rc\.([^.]+))?$")

# Mode word: bit 1 is reserved and always clear; the seven bits below each
# switch one step of screening, pinning, queueing or picking away from the
# mode-zero rule. The step bit 128 governs could not be recovered from the
# worked examples, so a run with it set behaves as if it were clear.
BIT_REPUBLISH = 2
BIT_RC = 4
BIT_YANK = 8
BIT_STICKY = 16
BIT_QUEUE_ORDER = 32
BIT_PIN_DUP = 64
BIT_UNDETERMINED = 128
MODE_BITS = (
    BIT_REPUBLISH
    | BIT_RC
    | BIT_YANK
    | BIT_STICKY
    | BIT_QUEUE_ORDER
    | BIT_PIN_DUP
    | BIT_UNDETERMINED
)


def mode_config(mode):
    """Turn a mode word into the rule choices one run is settled under."""
    if not isinstance(mode, int) or isinstance(mode, bool) or mode < 0:
        raise ValueError("mode must be a non-negative integer")
    if mode & ~MODE_BITS:
        raise ValueError("mode word uses an undefined bit")
    return {
        "keep": "last" if mode & BIT_REPUBLISH else "minseq",
        "rc": "any" if mode & BIT_RC else "group",
        "yank": "always" if mode & BIT_YANK else "seqgt",
        "sticky": "candidate" if mode & BIT_STICKY else "shamatch",
        "queue_order": "file" if mode & BIT_QUEUE_ORDER else "descending",
        "pin_dup": "last" if mode & BIT_PIN_DUP else "first",
    }


# ---------------------------------------------------------------- versions


def parse_version(text):
    """Return a sort key for a version string, or None when it is invalid."""
    if not isinstance(text, str):
        return None
    matched = VER_RE.match(text)
    if not matched:
        return None
    major, minor, patch, rc = matched.groups()
    for part in (major, minor, patch):
        if not NUM_RE.match(part):
            return None
    if rc is None:
        return (int(major), int(minor), int(patch), 1, 0)
    if not NUM_RE.match(rc):
        return None
    return (int(major), int(minor), int(patch), 0, int(rc))


def is_rc(key):
    return key[3] == 0


def release_key(major, minor, patch):
    return (major, minor, patch, 1, 0)


# ------------------------------------------------------------------ ranges


def parse_clause(text):
    """Return (operator, bound) for one clause, or None when it is invalid."""
    text = text.strip()
    if text == "*":
        return ("*", None)
    for op in (">=", "<", "^", "~", "="):
        if text.startswith(op):
            bound = parse_version(text[len(op):].strip())
            if bound is None:
                return None
            return (op, bound)
    return None


def parse_range(text):
    """Return a list of groups of clauses, or None when the range is invalid."""
    if not isinstance(text, str):
        return None
    groups = []
    for raw_group in text.split("|"):
        clauses = []
        for raw_clause in raw_group.split(","):
            clause = parse_clause(raw_clause)
            if clause is None:
                return None
            clauses.append(clause)
        groups.append(clauses)
    return groups


def caret_upper(bound):
    major, minor, patch = bound[0], bound[1], bound[2]
    if major > 0:
        return release_key(major + 1, 0, 0)
    if minor > 0:
        return release_key(0, minor + 1, 0)
    return release_key(0, 0, patch + 1)


def clause_matches(clause, key):
    op, bound = clause
    if op == "*":
        return True
    if op == "=":
        return key == bound
    if op == ">=":
        return key >= bound
    if op == "<":
        return key < bound
    if op == "^":
        return bound <= key < caret_upper(bound)
    if op == "~":
        return bound <= key < release_key(bound[0], bound[1] + 1, 0)
    raise ValueError("unknown clause operator: %r" % (op,))


def group_matches(clauses, key, cfg):
    if is_rc(key) and cfg["rc"] == "group":
        if not any(bound is not None and is_rc(bound) for _, bound in clauses):
            return False
    return all(clause_matches(clause, key) for clause in clauses)


def range_matches(groups, key, cfg):
    return any(group_matches(clauses, key, cfg) for clauses in groups)


# -------------------------------------------------------------- screening


def valid_deps(deps, pkg):
    if not isinstance(deps, dict):
        return False
    for name, rng in deps.items():
        if not isinstance(name, str) or not PKG_RE.match(name) or name == pkg:
            return False
        if parse_range(rng) is None:
            return False
    return True


def valid_seq(seq):
    return isinstance(seq, int) and not isinstance(seq, bool) and seq >= 1


def valid_head(obj):
    if not valid_seq(obj["seq"]):
        return False
    if not isinstance(obj["pkg"], str) or not PKG_RE.match(obj["pkg"]):
        return False
    return parse_version(obj["ver"]) is not None


def classify(obj):
    """Return 'publish', 'yank' or None for one decoded index object."""
    if not isinstance(obj, dict):
        return None
    keys = set(obj)
    if keys == {"seq", "pkg", "ver", "deps", "sha"}:
        if not valid_head(obj):
            return None
        if not isinstance(obj["sha"], str) or not SHA_RE.match(obj["sha"]):
            return None
        if not valid_deps(obj["deps"], obj["pkg"]):
            return None
        return "publish"
    if keys == {"seq", "pkg", "ver", "yank"}:
        if obj["yank"] is not True:
            return None
        if not valid_head(obj):
            return None
        return "yank"
    return None


def read_index(path, cfg):
    """Screen the feed into kept publishes, accepted yanks and counts."""
    counts = {"malformed": 0, "retransmitted": 0, "republished": 0}
    accepted = set()
    publishes = []
    yanks = []
    with open(path, "rb") as handle:
        data = handle.read()
    for raw in data.split(b"\n"):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            counts["malformed"] += 1
            continue
        kind = classify(obj)
        if kind is None:
            counts["malformed"] += 1
            continue
        canon = json.dumps(obj, sort_keys=True, separators=(",", ":"))
        if canon in accepted:
            counts["retransmitted"] += 1
            continue
        accepted.add(canon)
        if kind == "publish":
            publishes.append(obj)
        else:
            yanks.append(obj)

    copies = {}
    for obj in publishes:
        copies.setdefault((obj["pkg"], obj["ver"]), []).append(obj)
    kept = {}
    for (pkg, ver), group in copies.items():
        counts["republished"] += len(group) - 1
        if cfg["keep"] == "last":
            choice = group[-1]
        else:
            choice = min(group, key=lambda obj: obj["seq"])
        kept.setdefault(pkg, {})[ver] = {
            "sha": choice["sha"],
            "deps": choice["deps"],
            "seq": choice["seq"],
            "key": parse_version(ver),
        }
    return kept, yanks, counts


def apply_yanks(kept, yanks, cfg):
    """Mark yanked versions and count each accepted yank line's outcome."""
    yanked = set()
    applied = 0
    ignored = 0
    for obj in yanks:
        pkg, ver = obj["pkg"], obj["ver"]
        entry = kept.get(pkg, {}).get(ver)
        if entry is None:
            ignored += 1
            continue
        if cfg["yank"] == "always" or obj["seq"] > entry["seq"]:
            yanked.add((pkg, ver))
            applied += 1
        else:
            ignored += 1
    return yanked, applied, ignored


# ------------------------------------------------------------------- pins


def read_pins(path, cfg):
    """Return the pins in force as package name to parsed range."""
    pins = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            pkg = row.get("pkg")
            if not isinstance(pkg, str) or not PKG_RE.match(pkg):
                continue
            parsed = parse_range(row.get("range"))
            if parsed is None:
                continue
            if pkg in pins and cfg["pin_dup"] == "first":
                continue
            pins[pkg] = parsed
    return pins


# ------------------------------------------------------------- resolution


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def requirement_items(deps, cfg):
    """One requester's requirements in the order they join the queue."""
    items = list(deps.items())
    if cfg["queue_order"] == "descending":
        items.sort(key=lambda item: item[0], reverse=True)
    return items


def candidates_for(pkg, groups, kept, yanked, pins, cfg):
    """Kept, not yanked versions meeting the range and any pin, ascending."""
    out = []
    pin = pins.get(pkg)
    for ver, entry in kept.get(pkg, {}).items():
        if (pkg, ver) in yanked:
            continue
        if not range_matches(groups, entry["key"], cfg):
            continue
        if pin is not None and not range_matches(pin, entry["key"], cfg):
            continue
        out.append((entry["key"], ver, entry))
    out.sort(key=lambda item: item[0])
    return out


def honour_previous(candidates, prev_entry, cfg):
    """Return the candidate the previous lock holds, when it may be honoured."""
    if prev_entry is None:
        return None
    version = prev_entry.get("version")
    for candidate in candidates:
        if candidate[1] != version:
            continue
        if cfg["sticky"] == "shamatch" and candidate[2]["sha"] != prev_entry.get("sha"):
            return None
        return candidate
    return None


def resolve(workspace, kept, yanked, pins, prev, cfg):
    """Walk the requirement queue; return picks, issues and the sticky count."""
    queue = deque()
    for member in workspace.get("members", []):
        by = "member:" + member["name"]
        for pkg, rng in requirement_items(member.get("deps", {}), cfg):
            queue.append((pkg, rng, by))

    prev_packages = prev.get("packages", {}) if isinstance(prev, dict) else {}
    picks = {}
    issues = []
    sticky = 0

    while queue:
        pkg, rng, by = queue.popleft()
        groups = parse_range(rng)
        if pkg in picks:
            if groups is None or not range_matches(groups, picks[pkg]["key"], cfg):
                issues.append(
                    {
                        "kind": "conflict",
                        "pkg": pkg,
                        "range": rng,
                        "by": by,
                        "picked": picks[pkg]["version"],
                    }
                )
            continue
        candidates = []
        if groups is not None:
            candidates = candidates_for(pkg, groups, kept, yanked, pins, cfg)
        if not candidates:
            issues.append({"kind": "unresolved", "pkg": pkg, "range": rng, "by": by})
            continue
        chosen = honour_previous(candidates, prev_packages.get(pkg), cfg)
        if chosen is None:
            chosen = candidates[-1]
        else:
            sticky += 1
        key, ver, entry = chosen
        picks[pkg] = {"sha": entry["sha"], "version": ver, "via": by, "key": key}
        requester = "%s@%s" % (pkg, ver)
        for dep, dep_range in requirement_items(entry["deps"], cfg):
            queue.append((dep, dep_range, requester))
    return picks, issues, sticky


# ---------------------------------------------------------------- reports


def lock_bytes(picks):
    packages = {
        pkg: {"sha": info["sha"], "version": info["version"], "via": info["via"]}
        for pkg, info in picks.items()
    }
    text = json.dumps({"packages": packages}, sort_keys=True, indent=2) + "\n"
    return text.encode("utf-8")


def issues_bytes(issues):
    parts = []
    for record in issues:
        parts.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    return "".join(parts).encode("utf-8")


def lock_lines(picks, names):
    return "".join(
        "%s@%s:%s\n" % (pkg, picks[pkg]["version"], picks[pkg]["sha"])
        for pkg in sorted(names)
    )


def lock_digest(picks):
    return hashlib.sha256(lock_lines(picks, picks.keys()).encode("utf-8")).hexdigest()


def summary_bytes(picks, issues, sticky, counts, yank_counts, pins):
    conflicts = sum(1 for record in issues if record["kind"] == "conflict")
    summary = {
        "malformed": counts["malformed"],
        "retransmitted": counts["retransmitted"],
        "republished": counts["republished"],
        "yanks_applied": yank_counts[0],
        "yanks_ignored": yank_counts[1],
        "picked": len(picks),
        "sticky": sticky,
        "conflicts": conflicts,
        "unresolved": len(issues) - conflicts,
        "pins": len(pins),
        "lock_digest": lock_digest(picks),
    }
    return (json.dumps(summary, sort_keys=True, indent=2) + "\n").encode("utf-8")


def member_roots(picks, workspace):
    """Map each member name to the picks whose via chain ends at that member."""
    roots = {}
    for member in workspace.get("members", []):
        roots[member["name"]] = set()
    for pkg in picks:
        seen = set()
        current = pkg
        while current not in seen:
            seen.add(current)
            via = picks[current]["via"]
            if via.startswith("member:"):
                name = via[len("member:"):]
                if name in roots:
                    roots[name].add(pkg)
                break
            parent = via.rsplit("@", 1)[0]
            if parent not in picks:
                break
            current = parent
    return roots


def member_digests(picks, workspace):
    """Lowercase hex SHA-256 of each member's share of the lock."""
    return {
        name: hashlib.sha256(lock_lines(picks, names).encode("utf-8")).hexdigest()
        for name, names in member_roots(picks, workspace).items()
    }


def write_bytes(path, payload):
    with open(path, "wb") as handle:
        handle.write(payload)


def run(in_dir, out_dir):
    """Resolve one intake folder and write its three reports into out_dir."""
    manifest = read_json(os.path.join(in_dir, "manifest.json"))
    cfg = mode_config(manifest.get("mode", 0))
    workspace = read_json(os.path.join(in_dir, "workspace.json"))
    prev = read_json(os.path.join(in_dir, "lock.prev.json"))
    pins = read_pins(os.path.join(in_dir, "pins.csv"), cfg)
    kept, yanks, counts = read_index(os.path.join(in_dir, "index.jsonl"), cfg)
    yanked, applied, ignored = apply_yanks(kept, yanks, cfg)
    picks, issues, sticky = resolve(workspace, kept, yanked, pins, prev, cfg)

    os.makedirs(out_dir, exist_ok=True)
    write_bytes(os.path.join(out_dir, "lock.json"), lock_bytes(picks))
    write_bytes(os.path.join(out_dir, "issues.jsonl"), issues_bytes(issues))
    write_bytes(
        os.path.join(out_dir, "summary.json"),
        summary_bytes(picks, issues, sticky, counts, (applied, ignored), pins),
    )
    return picks, issues, workspace


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: lockres.py IN_DIR OUT_DIR\n")
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
