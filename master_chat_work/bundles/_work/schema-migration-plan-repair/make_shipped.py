"""Build repo_shipped/ (the broken repository) from repo_fixed/ with asserted patches.

Each patch is one planned divergence (F1..F15 in DESIGN.md). Run from anywhere:
    python3 make_shipped.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

WORK = Path(__file__).resolve().parent
FIXED = WORK / "repo_fixed"
SHIPPED = WORK / "repo_shipped"

PLANNER_SHIPPED = '''def _better(best: tuple[int, list[str]] | None, candidate: tuple[int, list[str]]) -> tuple[int, list[str]]:
    """Prefer the cheaper plan, then the shorter one; keep the first plan found otherwise."""
    if best is None:
        return candidate
    if (candidate[0], len(candidate[1])) < (best[0], len(best[1])):
        return candidate
    return best


def _enumerate_paths(
    registry: Registry,
    domain: str,
    origin: FieldView,
    node: str,
    target: str,
    names: list[str],
    state: tuple[str, ...],
    path: list[str],
    visited: set[str],
    cost: int,
    best: list,
) -> None:
    if node == target:
        best[0] = _better(best[0], (cost, list(path)))
        return
    for edge in registry.edges_from.get(node, ()):
        if edge.target in visited:
            continue
        if not edge_allowed(registry, domain, origin, edge):
            continue
        visited.add(edge.target)
        path.append(edge.edge_id)
        following = _advance(registry, domain, names, state, edge)
        _enumerate_paths(registry, domain, origin, edge.target, target, names, following, path, visited, cost + edge.cost, best)
        path.pop()
        visited.discard(edge.target)


def plan_migration(registry: Registry, schema_id: str, payload: dict) -> list[str]:
    """Cheapest plan to the canonical schema."""
    domain = registry.domain_of(schema_id)
    target = registry.canonical.get(domain)
    if target is None:
        raise MigrationError("E_UNREACHABLE", f"domain {domain} has no canonical schema")
    if schema_id == target:
        return []
    names = registry.named_fields(domain)
    origin = FieldView.from_payload(payload)
    best: list = [None]
    _enumerate_paths(registry, domain, origin, schema_id, target, names, origin.states(names), [], {schema_id}, 0, best)
    if best[0] is None:
        raise MigrationError("E_UNREACHABLE", f"no feasible plan from {schema_id} to {target}")
    return best[0][1]
'''

EXECUTOR_SHIPPED = '''def execute_plan(
    registry: Registry, schema_id: str, payload: dict, plan: list[str], corrections: list[dict]
) -> dict:
    """Execute ``plan`` from ``schema_id`` after applying the record's corrections."""
    domain = registry.domain_of(schema_id)
    record = copy.deepcopy(payload)
    applied: list[str] = []
    for correction in corrections:
        _apply_correction(record, correction)
        applied.append(correction["id"])
    current = schema_id
    for step, edge_id in enumerate(plan):
        edge = registry.edges.get(edge_id)
        if edge is None or edge.source != current:
            raise ValueError(f"plan step {step} ({edge_id}) does not leave {current}")
        record = apply_operations(registry, domain, record, edge.operations)
        current = edge.target
    return {
        "status": "migrated",
        "code": None,
        "schema": current,
        "payload": record,
        "completed_steps": len(plan),
        "failed_edge": None,
        "corrections_applied": applied,
    }
'''

ADMIT_SHIPPED = '''    def _admit(self, item: FeedLine) -> dict:
        document = item.record
        record = _blank_record(item.line, document)
        try:
            partner_id = resolve_partner(self.registry, document["partner"])
        except MigrationError as exc:
            record["code"] = exc.code
            return record
        record["partner"] = partner_id
        fingerprint = record_fingerprint(document["schema"], document["payload"])
        record["fingerprint"] = fingerprint
        identity = (document["partner"], document["key"])
        self.fingerprints.setdefault((partner_id, document["key"]), set()).add(fingerprint)
        holder = self.holders.get(identity)
        if holder is not None:
            if holder["fingerprint"] == fingerprint:
                record["status"] = "replayed"
                return record
            if not any(fingerprint.startswith(r.fingerprint_prefix) for r in self.reissues.get((partner_id, document["key"]), ())):
                record["code"] = "E_REPLAY_CONFLICT"
                return record
            holder.update(status="superseded", code=None, payload=None)
        self._migrate(record, document, (partner_id, document["key"]))
        if record["attempted"]:
            self.holders[identity] = record
        return record
'''

SUMMARY_SHIPPED = '''def build_summary(registry: Registry, records: list[dict], invalid_corrections: list[str] | tuple = ()) -> dict:
    by_status = Counter(record["status"] for record in records)
    by_code = Counter(record["code"] for record in records if record["code"] is not None)
    by_category = {name: 0 for name, _ in registry.taxonomy}
    for record in records:
        by_category[record["status"]] = by_category.get(record["status"], 0) + 1
    per_partner: dict[str, Counter] = {}
    for record in records:
        if record["partner"] is not None:
            per_partner.setdefault(record["partner"], Counter())[record["status"]] += 1
    partners = [
        {
            "partner": pid,
            "records": sum(per_partner[pid].values()),
            "migrated": per_partner[pid]["migrated"],
            "failed": per_partner[pid]["failed"],
        }
        for pid in sorted(per_partner)
    ]
'''

PATCHES: list[tuple[str, str, str]] = [
    # F1..F4 planner: exhaustive simple-path DFS, prerequisites on the received record, (cost, steps) tie.
    ("src/migrakit/core/planner.py", "PLANNER_FROM_HERE", PLANNER_SHIPPED),
    ("src/migrakit/core/planner.py", "import heapq\nfrom typing import Callable\n\nfrom ..errors import MigrationError", "from ..errors import MigrationError"),
    ("src/migrakit/core/planner.py", "from .records import ABSENT, NULL, VALUE, FieldView, counts_present, edge_allowed", "from .records import ABSENT, NULL, FieldView, edge_allowed"),
    # F5 shared FieldView drops explicit nulls.
    (
        "src/migrakit/core/records.py",
        "return cls({name: NULL if value is None else VALUE for name, value in payload.items()})",
        "return cls({name: VALUE for name, value in payload.items() if value is not None})",
    ),
    # F6 (decoy, round 1) an empty null_counts_as column is read as absent instead of the ini [presence] value.
    (
        "src/migrakit/core/records.py",
        """def null_counts_as(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.null_counts_as:
        return policy.null_counts_as
    return registry.presence_default""",
        """def null_counts_as(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.null_counts_as:
        return policy.null_counts_as
    # A field the policy leaves open is optional, so its explicit null counts as absent.
    return OPTIONAL_NULL""",
    ),
    (
        "src/migrakit/core/records.py",
        """def fill_mode(registry: Registry, domain: str, name: str) -> str:
    policy = registry.policies.get((domain, name))
    if policy is not None and policy.fill:
        return policy.fill
    return registry.fill_default""",
        """def fill_mode(registry: Registry, domain: str, name: str) -> str:
    return registry.fill_default""",
    ),
    # F7 partner token list merged with the default list.
    (
        "src/migrakit/parser/contracts.py",
        "        partner: _split_tokens(value)\n",
        "        partner: tuple(dict.fromkeys(default + _split_tokens(value)))\n",
    ),
    # F8 corrections applied up front, no prerequisite re-check.
    ("src/migrakit/core/executor.py", "EXECUTOR_FROM_HERE", EXECUTOR_SHIPPED),
    ("src/migrakit/core/executor.py", "from .operations import apply_operations\nfrom .records import FieldView, edge_allowed\n", "from .operations import apply_operations\n"),
    # F9 a planned record is reported migrated.
    (
        "src/migrakit/report/classify.py",
        '''    """Status and code of an executed record, taken from the execution result."""
    return result["status"], result["code"]''',
        '''    """Status and code of an executed record."""
    if plan is not None:
        return "migrated", None
    return result["status"], result["code"]''',
    ),
    # F10 (round 1) replay identity keyed on the raw partner value; a record holds its identity only once planning succeeded.
    ("src/migrakit/pipeline.py", "ADMIT_FROM_HERE", ADMIT_SHIPPED),
    # F11 feed file order.
    (
        "src/migrakit/pipeline.py",
        '''    """Processing order: the batch's received_seq, then the feed line number."""
    return sorted(lines, key=lambda item: (received[item.record["batch"]], item.line))''',
        '''    """Processing order of the admitted lines."""
    return list(lines)''',
    ),
    # F12 one merge hop, no loop detection.
    (
        "src/migrakit/parser/identity.py",
        """    seen = {partner_id}
    while partner_id in registry.merges:
        partner_id = registry.merges[partner_id]
        if partner_id in seen:
            raise MigrationError("E_ALIAS_CYCLE", value)
        seen.add(partner_id)
    return partner_id""",
        """    return registry.merges.get(partner_id, partner_id)""",
    ),
    (
        "src/migrakit/parser/identity.py",
        """    The id is found first (a partner id, else an alias), then every merge link
    is followed until a partner that is merged into no other partner.""",
        """    The id is found first (a partner id, else an alias), then its merge link.""",
    ),
    # F13 one bad line aborts the run.
    (
        "src/migrakit/parser/feed.py",
        """        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            found.append(FeedLine(number, None, f"not JSON: {exc.msg}"))
            continue
""",
        """        document = json.loads(raw)
""",
    ),
    # F14 category = status, partners sorted by id.
    ("src/migrakit/report/summary.py", "SUMMARY_FROM_HERE", SUMMARY_SHIPPED),
    ("src/migrakit/report/summary.py", "from ..parser.contracts import Registry\nfrom .classify import category_of\n", "from ..parser.contracts import Registry\n"),
    # F15 CLI paths resolved against the package folder.
    (
        "src/migrakit/cli.py",
        '''    """Resolve a command-line path against the caller's working directory."""
    return Path(value).expanduser().resolve()''',
        '''    """Resolve a command-line path; relative paths are taken from the package folder."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(__file__).resolve().parent / path''',
    ),
    # Round 1 additions (appended so wrong/make_wrong.py indices stay valid).
    # F6 decoy constant and the README sentence that backs it.
    (
        "src/migrakit/core/records.py",
        'VALUE = "value"\n',
        'VALUE = "value"\nOPTIONAL_NULL = ABSENT\n',
    ),
    (
        "README.md",
        "- `src/migrakit/cli.py`: `python -m migrakit run ...`.\n",
        "- `src/migrakit/cli.py`: `python -m migrakit run ...`.\n\n"
        "Field policy: a field whose `null_counts_as` column is empty in the field\n"
        "policy is optional, so an explicit null on it counts as absent\n"
        "(`OPTIONAL_NULL` in `core/records.py`).\n",
    ),
    # F7b an empty partner token line falls back to the default list.
    (
        "src/migrakit/parser/contracts.py",
        "        return self.partner_tokens.get(partner_id, self.default_tokens)\n",
        "        return self.partner_tokens.get(partner_id) or self.default_tokens\n",
    ),
    # Harden r1 additions.
    # F16 null tokens compared after trimming the payload value.
    (
        "src/migrakit/pipeline.py",
        '''    """Replace the partner's null tokens with explicit nulls."""
    return {name: (None if isinstance(value, str) and value in tokens else value) for name, value in payload.items()}''',
        '''    """Replace the partner's null tokens with explicit nulls; values are compared trimmed, as the tokens are."""
    return {name: (None if isinstance(value, str) and value.strip() in tokens else value) for name, value in payload.items()}''',
    ),
    # F17 receipt counted on the batch each line names, XOR taken from the record fingerprints.
    (
        "src/migrakit/pipeline.py",
        '''    for item in items:
        batch = records[item.line]["batch"]
        if batch is None:
            continue
        document = item.record
        counts[batch] = counts.get(batch, 0) + 1
        xors[batch] = xors.get(batch, 0) ^ int(record_fingerprint(document["schema"], document["payload"])[:8], 16)''',
        '''    for item in items:
        batch = item.batch
        if batch not in receipts:
            continue
        counts[batch] = counts.get(batch, 0) + 1
        fingerprint = records[item.line]["fingerprint"]
        if fingerprint is not None:
            xors[batch] = xors.get(batch, 0) ^ int(fingerprint[:8], 16)''',
    ),
]

PATCHES.append((
    # J4 (gate v3.6): a contract file that fails to parse surfaces the reader's bare error, not the file name.
    "src/migrakit/parser/contracts.py",
    """def _read(reader, path: Path):
    \"\"\"Run one file reader; a file that cannot be parsed raises ValueError naming that file.\"\"\"
    try:
        return reader(path)
    except (ValueError, KeyError, TypeError, AttributeError, configparser.Error, ET.ParseError) as exc:
        raise ValueError(f"{path}: cannot read contract file: {exc}") from exc


def load_contracts(""",
    "def load_contracts(",
))
for _name in ("schemas", "edges", "null_semantics", "aliases", "policies", "taxonomy", "order"):
    PATCHES.append(("src/migrakit/parser/contracts.py", f"_read(_read_{_name}, root / ", f"_read_{_name}(root / "))

SPANS = {
    "PLANNER_FROM_HERE": ("def plan_migration(", None),
    "EXECUTOR_FROM_HERE": ("def execute_plan(", None),
    "ADMIT_FROM_HERE": ("    def _admit(self, item: FeedLine) -> dict:", "    def _migrate("),
    "SUMMARY_FROM_HERE": ("def build_summary(", "    return {\n        \"records\""),
}


def _replace_span(text: str, marker: str, new: str) -> str:
    start_token, end_token = SPANS[marker]
    start = text.index(start_token)
    end = len(text) if end_token is None else text.index(end_token, start)
    if end_token is not None:
        new = new + "\n" if marker == "ADMIT_FROM_HERE" else new
    return text[:start] + new + text[end:]


def build() -> None:
    if SHIPPED.exists():
        shutil.rmtree(SHIPPED)
    shutil.copytree(FIXED, SHIPPED, ignore=shutil.ignore_patterns("__pycache__"))
    (SHIPPED / "src/migrakit/__main__.py").unlink()
    for rel, old, new in PATCHES:
        path = SHIPPED / rel
        text = path.read_text(encoding="utf-8")
        if old in SPANS:
            text = _replace_span(text, old, new)
        else:
            if text.count(old) != 1:
                raise SystemExit(f"patch target not unique in {rel}: {old[:60]!r}")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    build()
    print("built", SHIPPED)
