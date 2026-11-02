"""Raw corpus loading. Rows are returned untyped; classification happens later."""

from __future__ import annotations

import csv
import json
import re
import tomllib
import configparser
from pathlib import Path

MANIFEST = "corpus_manifest.json"

_MFA_LINE = re.compile(r"^(.+?) (\S+) (\S+) handle=(\S+) recorded=(\S+)$")


class CorpusError(RuntimeError):
    pass


def _csv(path: Path, delimiter: str = ",") -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=delimiter))
    for row in rows:
        row["_src"] = path.name
    return rows


def _jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["_src"] = path.name
        rows.append(row)
    return rows


def _mfa_log(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        m = _MFA_LINE.match(line.strip())
        if not m:
            continue
        rows.append({"at": m.group(1), "event_id": m.group(2), "action": m.group(3),
                     "handle": m.group(4), "recorded_at": m.group(5), "_src": path.name})
    return rows


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Corpus:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        manifest = self.root / MANIFEST
        if not manifest.is_file():
            raise CorpusError(f"missing {MANIFEST}")
        listed = _json(manifest)["files"]
        missing = [name for name in listed if not (self.root / name).is_file()]
        if missing:
            raise CorpusError("missing corpus files: " + ", ".join(sorted(missing)))
        self.files = sorted(listed)
        p = self.root
        self.defaults = _json(p / "defaults.json")
        self.schema = _json(p / "config_schema.json")
        self.profiles = tomllib.loads((p / "profiles.toml").read_text(encoding="utf-8"))
        site = configparser.ConfigParser(interpolation=None)
        site.optionxform = str
        site.read_string((p / "site_policy.ini").read_text(encoding="utf-8"))
        self.site = {section: dict(site[section]) for section in site.sections()}
        self.tz_rules = _json(p / "tz_rules.json")
        self.hr_sites = _json(p / "hr_sites.json")["sites"]
        self.roles = _json(p / "role_catalog.json")["roles"]
        self.permissions = tomllib.loads((p / "permission_catalog.toml").read_text(encoding="utf-8"))["permissions"]
        self.sod = _json(p / "sod_policy.json")["pairs"]
        self.groups = {g["id"]: g for g in _json(p / "dir_groups.json")["groups"]}
        self.rotations = {r["id"]: r for r in _json(p / "oncall_rotations.json")["rotations"]}
        self.freeze = _json(p / "freeze_windows.json")["windows"]

        def shards(pattern: str) -> list[Path]:
            return sorted(p / name for name in listed if Path(name).match(pattern))

        self.journal = _jsonl(p / "policy_change_journal.jsonl")
        self.employees = _csv(p / "hr_employees.csv")
        self.hr_events = [r for f in shards("hr_events_*.csv") for r in _csv(f)]
        self.hr_corrections = _csv(p / "hr_corrections.csv")
        self.contracts = _csv(p / "contractor_contracts.csv")
        self.accounts = [r for f in shards("idp_accounts_*.jsonl") for r in _jsonl(f)]
        self.mfa = _mfa_log(p / "idp_mfa_events.log")
        self.aliases = _csv(p / "directory_aliases.tsv", delimiter="\t")
        self.members = [r for f in shards("dir_members_site_*.csv") for r in _csv(f)]
        self.removals = _csv(p / "dir_membership_removals.csv")
        self.bindings = {env: _csv(p / f"role_bindings_{env}.csv") for env in ("dev", "prod")}
        self.requests = [r for f in shards("grant_requests_*.jsonl") for r in _jsonl(f)]
        self.approvals = _csv(p / "grant_approvals.csv")
        self.corrections = _jsonl(p / "grant_corrections.jsonl")
        self.self_revocations = _csv(p / "revocations_selfservice.csv")
        self.secops = _jsonl(p / "revocations_secops.jsonl")
        self.assignments = _csv(p / "oncall_assignments.csv")
        self.swaps = _csv(p / "oncall_swaps.csv")
        self.attestations = _csv(p / "access_attestations.csv")
