"""Seeded, stdlib-only generator for environment/ci and environment/repo of
schema-migration-plan-repair.

    python3 datagen.py <bundle>/environment

Writes the 12 contract and CI files into ci/ and copies the shipped repository
into repo/. Every rule the task grades is written into
repository_contract.md, migration_semantics.md, or the comment headers of
null_semantics.ini, correction_log.txt, partner_aliases.xml and
report_taxonomy.json. No file holds an expected output.
"""

from __future__ import annotations

import csv
import io
import json
import random
import sys
from pathlib import Path

SEED = 590237
TIME_LIMIT_SEC = 10
WORK = Path(__file__).resolve().parent
SHIPPED_REPO = WORK / "repo_shipped"

NOUNS = [
    "orders", "invoices", "shipments", "returns", "payouts", "refunds", "quotes", "tickets",
    "accounts", "contacts", "leases", "claims", "policies", "meters", "readings", "routes",
    "stops", "parcels", "pallets", "batches", "lots", "assets", "permits", "visits", "tariffs",
]
QUALIFIERS = ["core", "edge", "retail", "trade"]
FIELD_POOL = [
    "amount", "currency", "region", "status", "channel", "owner", "tier", "unit", "weight", "note",
    "ref", "code", "label", "origin", "dest", "qty", "price", "vat", "score", "zone", "batch_ref",
    "carrier", "due", "issued", "rate", "grade", "site", "lane", "slot", "kind",
]


# --------------------------------------------------------------------------- specs

def contract_md() -> str:
    return f"""# migrakit repository contract

This file and `migration_semantics.md` state how the repaired `migrakit`
repository must behave. More rules live in the comment headers of
`null_semantics.ini` (N rules), `correction_log.txt` (C rules),
`partner_aliases.xml` (P rules) and the `rules` list of `report_taxonomy.json`
(T rules). Rules are numbered K1 to K19 here. Every rule applies whether or not
the shipped code already follows it.

## Package and public API

K1. The repository at `/app/repo` holds `pyproject.toml`, `README.md`,
`src/migrakit/` and `tests/test_visible.py`; the delivered archive holds the
same layout at its root. The package imports as `migrakit`
from `src/`, uses only the Python 3.12 standard library, and every name below is
importable from the top-level `migrakit` package.

K2. `load_contracts(path)` reads these seven files from one contract folder and
returns a registry object that the other functions take as their first
argument: `schema_versions.json`, `migration_edges.csv`, `field_policy.tsv`,
`null_semantics.ini`, `partner_aliases.xml`, `report_taxonomy.json`,
`partner_order.tsv`. Other files in the folder are ignored. `/app/ci` is such a
folder.

K3. `resolve_partner(registry, value)` returns the canonical partner id for a
partner id or alias string (P rules).

K4. `record_fingerprint(schema_id, payload)` returns the 64-character lowercase
hex sha256 of the UTF-8 bytes of
`json.dumps({{"payload": payload, "schema": schema_id}}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.

K5. `state_signature(registry, schema_id, payload)` returns a dict (M10).

K6. `plan_migration(registry, schema_id, payload)` returns the plan as a list of
edge id strings (M6 to M9). It plans on the payload exactly as given.

K7. `execute_plan(registry, schema_id, payload, plan, corrections)` runs a plan on
one record (M11, M12 and the C rules) and returns a dict. `plan` is a list of
edge ids forming a path from `schema_id`. `corrections` is a list, in log order,
of the corrections that belong to this record, each a dict
`{{"id": str, "op": "SET" | "UNSET" | "NULL", "schema": str, "field": str, "value": any}}`
(`value` is used by SET only). None of `state_signature`, `plan_migration` and
`execute_plan` changes its arguments.

K8. `build_summary(registry, records, invalid_corrections)` returns the run
summary (K18) for a list of record dicts (K17) and a list of invalid correction
ids.

K9. `run_pipeline(contracts, feed, corrections, manifest)` takes four paths (the
contract folder, the feed, the correction log, the replay manifest) and returns
the tuple `(records, summary)`: the record dicts in feed line order and the
summary built from them.

K10. `python -m migrakit run --contracts DIR --feed FILE --corrections FILE
--manifest FILE --out DIR` runs `run_pipeline`, creates the output folder if
needed, and writes `records.jsonl` (one record per line, feed line order) and
`run_summary.json`. Relative paths are taken from the caller's working
directory. `python -m migrakit --help` exits with status 0.

K11. A rejection raises `migrakit.MigrationError`; its `code` attribute is one
of the K12 codes. `plan_migration` raises it for E_UNKNOWN_SCHEMA and
E_UNREACHABLE, `resolve_partner` for E_UNKNOWN_PARTNER and E_ALIAS_CYCLE,
`state_signature` for E_UNKNOWN_SCHEMA.

K12. Error catalogue (exact strings): `E_PARSE` (bad feed line, K15),
`E_UNKNOWN_PARTNER` (P1), `E_ALIAS_CYCLE` (P3), `E_UNKNOWN_SCHEMA` (schema id
not in schema_versions.json), `E_UNREACHABLE` (no plan exists, M7),
`E_PREREQ_FAILED` (a prerequisite fails during execution, M11),
`E_REPLAY_CONFLICT` (K16), `E_INVALID_CORRECTION` (C8; listed in the summary,
never a record code).

## Pipeline

K13. Stage order for each feed line: parse (K15); canonical partner (P rules);
fingerprint and replay identity (K16); null tokens (N6 to N8); plan (M rules);
execute with corrections (C rules, M11); classify (status and code from the
execution result) and summarise (K18, T rules). Lines are processed in
`received_seq` order of their batch in `replay_manifest.csv` (columns
`batch_id,received_seq,lines,fp_xor`), then by feed line number. The last two
columns are the batch receipt, which confirms that the lines of a batch arrived
as sent: `lines` is the number of records whose `batch` is that batch, and
`fp_xor` is the bitwise XOR of the first eight hex digits of
`record_fingerprint(schema, payload)` over those records' lines as received,
written as eight lowercase hex digits (`00000000` when no record has that
batch). The run lists in `receipt_mismatches` the sorted ids of the batches
whose count or XOR differs from their receipt.

K14. Limits. A contract folder holds at most 1,200 schemas and 6,000 edges; the
edges of one domain name at most 8 prerequisite fields and at most 10 fields in
total; a plan has at most 80 edges. Inside these limits every
`plan_migration` call must return within {TIME_LIMIT_SEC} seconds on a machine
with 2 CPUs, including graphs whose number of distinct paths is far too large
to list.

K15. A feed line is rejected with E_PARSE when it is not JSON, is not an object,
lacks a non-empty string `batch`, `partner`, `key` or `schema`, has a `payload`
that is not an object, or names a batch missing from the manifest. Such a record
has `batch`, `partner`, `key` and `schema` null. The run continues with the next
line.

K16. Replay identity. The identity of a record is (canonical partner id, key).
Its fingerprint is `record_fingerprint(schema, payload)` taken on the line as
received, before null tokens are replaced and before migration. In processing
order, the first record of an identity that passes the partner stage is its
holder. A later record with the same identity and the same fingerprint is
`replayed`. A later record with a different fingerprint is rejected with
E_REPLAY_CONFLICT, unless a REISSUE correction (C7) for that identity names a
prefix of its fingerprint: then the holder becomes `superseded` (code null,
payload null; its other keys stay) and the new record becomes the holder and is
migrated.

## Records, summary and reports

K17. Record keys (records.jsonl and `run_pipeline`): `line` (1-based feed line),
`batch`, `partner` (canonical id or null), `key`, `status` (`migrated`, `failed`,
`replayed`, `superseded`, `rejected`), `code` (a K12 code or null), `schema`
(canonical schema when migrated, the schema where execution stopped when failed,
else the schema as received), `plan` (edge ids or null), `completed_steps` (0
when execution never started), `failed_edge`, `payload` (the migrated payload when migrated, else null),
`attempted` (true when execution started), `fingerprint` (null before the
partner stage passes).

K18. Summary keys (`run_summary.json`, `build_summary`): `records` (count),
`attempted` (records with `attempted` true), `by_status` and `by_code` (counts
of the values present), `by_category` (T1, T2), `invalid_corrections` (sorted
ids, C8), `partners` (T3: list of `{{"partner", "records", "migrated",
"failed"}}`). The summary returned by `run_pipeline` and written to
`run_summary.json` also has `receipt_mismatches` (K13).

K19. Deliverables under `/app/out`:
- `patched-repo.zip`: the repaired repository with the K1 layout at the archive
  root, no directory entries, no absolute or `..` member names.
- `summary.json`: the run summary the repaired package produces for the shipped
  inputs (contracts `/app/ci`, feed `partner_batches.jsonl`, corrections
  `correction_log.txt`, manifest `replay_manifest.csv`).
- `module_core.json`, `module_parser.json`, `module_report.json`: each
  `{{"module": "core" | "parser" | "report", "changed_functions": [...],
  "notes": [...]}}`. `changed_functions` is the sorted, non-empty list of dotted
  names relative to `migrakit` (for example `core.records.FieldView.state`) of
  every function or method you changed or added in that area. Areas: core is
  `core/` and `pipeline.py`; parser is `parser/` and `cli.py`; report is
  `report/`. A function counts as changed when its syntax tree differs from the
  shipped version after omitting its leading docstring; comments and layout do
  not alter that tree.
  A nested function is named by the module-level function or class method that
  contains it. `notes` is a list of strings.
- `test_fixes.json`: `{{"visible_tests": [{{"name", "before", "after"}}, ...]}}`,
  one entry per test method of `tests/test_visible.py` sorted by name, `before`
  and `after` being `pass` or `fail` (an error counts as `fail`) for the shipped
  and the repaired repository.
- `repair-report.json`: `{{"package": "migrakit", "fixes": [non-empty strings],
  "checks": [{{"name": str, "passed": bool}}, ...]}}` with at least one passed
  check.
"""


def semantics_md() -> str:
    return """# Migration semantics

Rules M1 to M12. Field states, presence and the fill rule are in the header of
`null_semantics.ini`; corrections are in the header of `correction_log.txt`.

M1. A schema id is `<domain>.v<n>`; `schema_versions.json` lists every schema
with its `domain` and a `canonical` flag. Each domain has one canonical schema,
the target of every record of that domain.

M2. `migration_edges.csv` columns: `edge_id`, `source`, `target` (schemas of one
domain), `requires`, `operations`, `cost` (positive integer).

M3. `requires` is empty or a `;`-separated list of `has:<field>` and
`lacks:<field>`. `has:f` holds when f counts as present (N2); `lacks:f` holds
when it does not.

M4. `operations` is empty or a `;`-separated list applied left to right:
`rename:a>b` moves field a, in whatever state it is (an explicit null stays an
explicit null), to b, replacing b; nothing happens when a is absent.
`drop:a` removes a. `add:a` applies the fill rule (N4). `cast:a:int`,
`cast:a:float`, `cast:a:str` convert a value (M5); null and absent are left
alone.

M5. Casts. int: an int stays; a float with no fractional part becomes that int;
a string that is an optional sign and digits (surrounding spaces ignored)
becomes that int. float: an int or float becomes a float; a decimal string
(optional sign, digits with an optional point, surrounding spaces ignored)
becomes a float. str: an int or a float becomes Python `str()` of it. Anything
else, booleans included, is left unchanged.

M6. An edge applies to a record when every prerequisite holds on the record as
it is at that point of the plan: after the operations of every earlier edge of
the plan (and, during execution, after the corrections applied so far).

M7. A plan is a list of edges, each leaving the schema the previous one reached,
that starts at the record's schema, ends at the canonical schema, and where every
edge applies (M6). A plan may pass through a schema more than once. A record
already at its canonical schema has the empty plan. When no plan exists the
record is rejected with E_UNREACHABLE.

M8. Among all plans the planner returns the one with the smallest total cost;
among plans of equal total cost, the one whose list of edge ids is smallest when
the lists are compared element by element as strings, first edge first (the way
Python compares two lists of strings).

M9. Planning sees the payload after null-token replacement and never sees
corrections. Two records with the same source schema can therefore need
different plans.

M10. `state_signature` returns, for each field named in a `requires` entry of
any edge whose source schema belongs to the record's domain, the field's state
(`absent`, `null` or `value`, N1), keyed by field name in sorted order.

M11. Execution follows the plan edge by edge. Corrections are applied as the C
rules say. Before each edge its prerequisites are checked on the record as it is
at that moment. When one fails, execution stops: status `failed`, code
E_PREREQ_FAILED, `failed_edge` that edge, `completed_steps` the number of edges
already applied, `schema` the schema reached, `payload` null.

M12. `execute_plan` returns `{"status", "code", "schema", "payload",
"completed_steps", "failed_edge", "corrections_applied"}`; on success status is
`migrated`, code and failed_edge are null, schema is the canonical schema,
payload the migrated record, and `corrections_applied` lists the ids of the
corrections applied, in the order they were applied.
"""


INI_HEADER = """; null_semantics.ini: field states, presence, fill and null tokens.
;
; N1. A payload field is in one of three states: absent (the key is missing),
;     explicit null (the key is present with JSON null) or a value. Every stage
;     (state signature, planning, operations and execution checks) keeps
;     explicit null distinct from absent.
; N2. For a prerequisite, a value counts as present and an absent field does
;     not. An explicit null counts as present or absent according to the
;     null_counts_as column of field_policy.tsv for that domain and field when
;     it is not empty, otherwise according to [presence] explicit_null below.
; N3. field_policy.tsv is tab separated with no quoting. Columns: domain,
;     field, default (JSON text; empty means the field has no default), fill
;     (absent_only, absent_or_null or empty), null_counts_as (present, absent
;     or empty). An empty column falls back to this file.
; N4. add:f sets f to its default when f is absent. When f is an explicit null
;     it sets the default only if the fill mode is absent_or_null (the fill
;     column when not empty, otherwise [fill] mode). A value is left alone, and
;     a field with no default is left alone.
; N5. A rename moves an explicit null like any value (M4).
; N6. Before planning, every top-level payload value that is a string exactly
;     equal to one of the partner's null tokens becomes an explicit null.
; N7. A partner whose canonical id has its own line in [tokens] uses exactly
;     that line's tokens; the default line applies to every other partner.
; N8. Tokens are separated by | and surrounding spaces are trimmed. Token
;     replacement happens after the replay fingerprint is taken (K16).
"""


CORRECTION_HEADER = """# correction_log.txt: corrections to partner records.
#
# C1. Each line is one of
#       <id> SET <partner> <key> AT <schema> <field> <json value>
#       <id> UNSET <partner> <key> AT <schema> <field>
#       <id> NULL <partner> <key> AT <schema> <field>
#       <id> REISSUE <partner> <key> <first 12 hex digits of a fingerprint>
#     fields separated by spaces; the SET value is the rest of the line.
#     Lines starting with # and blank lines are ignored.
# C2. <partner> is a partner id or alias, resolved as partner_aliases.xml
#     says (P rules); <key> is matched exactly.
# C3. A SET, UNSET or NULL correction belongs to every executed record with the
#     same canonical partner and key, and is pinned to <schema>.
# C4. It is applied when the execution first arrives at the pinned schema; the
#     record's source schema counts as an arrival before the first edge. It is
#     applied before the next edge's prerequisites are checked. A later arrival
#     at the same schema applies nothing. Corrections pinned to one schema are
#     applied in log order. SET sets the field to the value, UNSET removes it,
#     NULL makes it an explicit null.
# C5. The planner never sees corrections (M9), so a correction can make a later
#     prerequisite fail during execution (M11).
# C6. A line that does not match C1 is malformed.
# C7. REISSUE declares that the record of that partner and key whose
#     fingerprint starts with the given 12 hex digits is a legitimate new
#     version (K16).
# C8. A correction is invalid when it is malformed, when its partner cannot be
#     resolved, when a SET, UNSET or NULL correction is applied in no execution,
#     or when a REISSUE prefix matches no fingerprint of a record with that
#     partner and key. Invalid ids are listed in the summary's
#     invalid_corrections (E_INVALID_CORRECTION).
"""

XML_HEADER = """<!--
partner_aliases.xml: partner identity.
P1. A partner value equal to a partner id names that partner; otherwise a value
    equal to an alias text names the alias's partner; otherwise the record is
    rejected with E_UNKNOWN_PARTNER. Matching is exact and case sensitive.
P2. From that partner, every merge link (from, into) is followed until a partner
    that is merged into no other partner. That partner id is the canonical id.
P3. When following merge links returns to a partner already visited, the value
    is rejected with E_ALIAS_CYCLE.
P4. The canonical id is the one used for replay identity, null tokens,
    corrections, records and the summary.
-->
"""

TAXONOMY = {
    "rules": [
        "T1. A record's category is the first category in this list whose members contain the record's code; a record whose code is null takes the first category whose members contain its status.",
        "T2. by_category in the summary holds every category of this list with its record count, zero included.",
        "T3. The summary's partners list holds each canonical partner with at least one record, ordered by rank in partner_order.tsv (ascending); partners missing from that file follow, sorted by id.",
    ],
    "categories": [
        {"name": "complete", "members": ["migrated"]},
        {"name": "duplicate", "members": ["replayed", "superseded"]},
        {"name": "execution_failure", "members": ["E_PREREQ_FAILED"]},
        {"name": "conflict", "members": ["E_REPLAY_CONFLICT"]},
        {"name": "input_error", "members": ["E_PARSE", "E_UNKNOWN_PARTNER", "E_ALIAS_CYCLE"]},
        {"name": "planning_error", "members": ["E_UNKNOWN_SCHEMA", "E_UNREACHABLE"]},
        {"name": "other", "members": ["failed", "rejected"]},
    ],
}


# --------------------------------------------------------------------------- data
#
# Round 1 visible data. Every shipped defect except the null presence default
# reads the same as the contract on these inputs; the rare boundary where the
# shipped default and the contract part ways is a handful of records with an
# explicit null on a prerequisite field whose null_counts_as column is empty.

import hashlib
import heapq
import shutil
from collections import defaultdict

SYLLABLES = ["nor", "sud", "ost", "west", "lin", "mar", "kel", "bra", "tor",
             "vik", "ama", "zen", "pol", "dur"]
WORDS = ["alpha", "beta", "gamma", "delta", "north", "south", "x-one"]
DEFAULT_TOKENS = ("NULL", "N/A")
TOKEN_CHOICES = ["~", "none", "-", "nil", "?", "void", "NULL", "N/A"]
VERSIONS = 10
FEED_LINES = 8000
BOUNDARY_EACH = 8


def build_domains(rng: random.Random) -> list[dict]:
    names = [f"{noun}_{qual}" for noun in NOUNS for qual in QUALIFIERS]
    rng.shuffle(names)
    domains = []
    for name in names[:100]:
        fields = rng.sample(FIELD_POOL, 9)
        domains.append({
            "name": name,
            "prereq": fields[:4],
            "ops": fields[4:7],
            "plain": fields[7:9],
            "canonical": rng.randint(6, VERSIONS),
        })
    return domains


def _requires(rng: random.Random, domain: dict) -> list[str]:
    picked = rng.sample(domain["prereq"], rng.randint(1, 2))
    return [f"{rng.choice(['has', 'lacks'])}:{name}" for name in picked]


def _operations(rng: random.Random, domain: dict) -> list[str]:
    found = []
    for _ in range(rng.randint(0, 3)):
        kind = rng.choice(["rename", "drop", "add", "add", "cast"])
        if kind == "rename":
            a, b = rng.sample(domain["ops"], 2)
            found.append(f"rename:{a}>{b}")
        elif kind == "cast":
            found.append(f"cast:{rng.choice(domain['ops'])}:"
                         f"{rng.choice(['int', 'float', 'str'])}")
        else:
            found.append(f"{kind}:{rng.choice(domain['ops'])}")
    return found


def _presence_vectors(domain: dict) -> list[frozenset]:
    names = domain["prereq"]
    return [frozenset(n for i, n in enumerate(names) if mask >> i & 1)
            for mask in range(1 << len(names))]


def _allowed(edge: dict, present: frozenset) -> bool:
    for item in edge["requires"]:
        kind, _, name = item.partition(":")
        if (name in present) != (kind == "has"):
            return False
    return True


def _unique_plans(domain: dict, edges: list[dict], present: frozenset):
    """Cheapest plan per source under constant prerequisite states, or None on a tie."""
    target = domain["canonical"]
    incoming = defaultdict(list)
    for edge in edges:
        if _allowed(edge, present):
            incoming[edge["target"]].append(edge)
    dist = {target: 0}
    count = {target: 1}
    nxt: dict[int, dict | None] = {target: None}
    done = set()
    heap = [(0, target)]
    while heap:
        d, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        for edge in incoming[node]:
            source = edge["source"]
            if source in done:
                continue
            nd = d + edge["cost"]
            if source not in dist or nd < dist[source]:
                dist[source], count[source], nxt[source] = nd, count[node], edge
                heapq.heappush(heap, (nd, source))
            elif nd == dist[source]:
                count[source] += count[node]
    if any(count[node] > 1 for node in dist):
        return None
    plans = {}
    for version in range(1, VERSIONS + 1):
        if version not in dist:
            plans[version] = None
            continue
        path, node = [], version
        while nxt[node] is not None:
            path.append(nxt[node])
            node = nxt[node]["target"]
        plans[version] = path
    return plans


def build_edges(rng: random.Random, domain: dict) -> tuple[list[dict], dict]:
    canonical = domain["canonical"]
    pairs = [(v, v + 1 if v < canonical else v - 1)
             for v in range(1, VERSIONS + 1) if v != canonical]
    while len(pairs) < VERSIONS - 1 + 5:
        a, b = rng.randint(1, VERSIONS), rng.randint(1, VERSIONS)
        if a != b and a != canonical and (a, b) not in pairs:
            pairs.append((a, b))
    edges = []
    for index, (a, b) in enumerate(pairs):
        chance = 0.25 if index < VERSIONS - 1 else 0.4
        edges.append({
            "source": a, "target": b,
            "requires": _requires(rng, domain) if rng.random() < chance else [],
            "operations": _operations(rng, domain),
            "cost": 0,
        })
    while True:
        for edge in edges:
            edge["cost"] = rng.randint(1, 9)
        table = {}
        for present in _presence_vectors(domain):
            plans = _unique_plans(domain, edges, present)
            if plans is None:
                break
            table[present] = plans
        else:
            return edges, table


def build_partners(rng: random.Random):
    ids = [f"P{n:05d}" for n in range(1, 2101)]
    aliases: dict[str, list[str]] = {}
    taken = set()
    for pid in ids:
        names = []
        for _ in range(rng.randint(1, 2)):
            while True:
                alias = (rng.choice(SYLLABLES) + rng.choice(SYLLABLES)
                         + str(rng.randint(10, 999)))
                if alias not in taken:
                    break
            taken.add(alias)
            names.append(alias)
        aliases[pid] = names
    pool = ids[:]
    rng.shuffle(pool)
    merges: list[tuple[str, str]] = []
    while len(merges) < 146:
        hops = min(rng.randint(1, 3), 146 - len(merges))
        chain = [pool.pop() for _ in range(hops + 1)]
        merges.extend(zip(chain, chain[1:]))
    loop_members = set()
    for _ in range(2):
        a, b = pool.pop(), pool.pop()
        merges.extend([(a, b), (b, a)])
        loop_members.update([a, b])
    into = dict(merges)

    def canonical(pid: str) -> str | None:
        seen = {pid}
        while pid in into:
            pid = into[pid]
            if pid in seen:
                return None
            seen.add(pid)
        return pid

    safe = {}
    for pid in ids:
        if pid in loop_members:
            continue
        hops = 0
        node = pid
        while node in into:
            node, hops = into[node], hops + 1
        if hops <= 1:
            safe[pid] = node
    terminals = [pid for pid in ids if pid not in into]
    return ids, aliases, merges, safe, terminals, canonical


def _fingerprint(schema: str, payload: dict) -> str:
    text = json.dumps({"payload": payload, "schema": schema}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _value(rng: random.Random):
    roll = rng.random()
    number = rng.randint(100000, 999999)
    if roll < 0.3:
        return number
    if roll < 0.5:
        return str(number)
    if roll < 0.58:
        return f" {rng.choice(['', '-', '+'])}{number} "
    if roll < 0.66:
        return f"{number}.25"
    if roll < 0.72:
        return number + 0.5
    return rng.choice(WORDS)


def generate(env: Path) -> None:
    rng = random.Random(SEED)
    ci, repo = env / "ci", env / "repo"
    for folder in (ci, repo):
        if folder.exists():
            shutil.rmtree(folder)
    ci.mkdir(parents=True)

    domains = build_domains(rng)
    edges_by_domain, plans = {}, {}
    for domain in domains:
        edges, table = build_edges(rng, domain)
        edges_by_domain[domain["name"]] = edges
        plans[domain["name"]] = table
    every_edge = [e for d in domains for e in edges_by_domain[d["name"]]]
    numbers = list(range(1, len(every_edge) + 1))
    rng.shuffle(numbers)
    for edge, number in zip(every_edge, numbers):
        edge["id"] = f"E{number:05d}"
    for domain in domains:
        for edge in edges_by_domain[domain["name"]]:
            edge["source_id"] = f"{domain['name']}.v{edge['source']}"
            edge["target_id"] = f"{domain['name']}.v{edge['target']}"

    def schema_id(domain: dict, version: int) -> str:
        return f"{domain['name']}.v{version}"

    # schema_versions.json and migration_edges.csv
    schemas = [{"id": schema_id(d, v), "domain": d["name"],
                "canonical": v == d["canonical"]}
               for d in domains for v in range(1, VERSIONS + 1)]
    (ci / "schema_versions.json").write_text(
        json.dumps({"schemas": schemas}, indent=2) + "\n", encoding="utf-8")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["edge_id", "source", "target", "requires", "operations", "cost"])
    for edge in sorted(every_edge, key=lambda e: e["id"]):
        writer.writerow([edge["id"], edge["source_id"], edge["target_id"],
                         ";".join(edge["requires"]), ";".join(edge["operations"]),
                         edge["cost"]])
    (ci / "migration_edges.csv").write_text(buffer.getvalue(), encoding="utf-8")

    # field_policy.tsv
    policy: dict[tuple[str, str], tuple[str, str, str]] = {}
    rows = ["domain\tfield\tdefault\tfill\tnull_counts_as"]
    for domain in domains:
        for name in domain["prereq"] + domain["ops"] + domain["plain"]:
            default = (rng.choice(['"n/a"', "0", '"UNSET"', "1", '"EUR"'])
                       if rng.random() < 0.8 else "")
            fill = rng.choice(["", "", "absent_only", "absent_or_null"])
            if name in domain["prereq"]:
                nca = rng.choice(["", "absent", "present"])
            else:
                nca = rng.choice(["", "", "present", "absent"])
            policy[(domain["name"], name)] = (default, fill, nca)
            rows.append(f"{domain['name']}\t{name}\t{default}\t{fill}\t{nca}")
        used = set(domain["prereq"] + domain["ops"] + domain["plain"])
        spare = [f for f in FIELD_POOL if f not in used]
        for name in rng.sample(spare, rng.randint(1, 3)):
            filler = rng.choice(['"pending"', '"none"', '"draft"'])
            rows.append(f"{domain['name']}\t{name}\t{filler}\t\t")
    (ci / "field_policy.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    # partner_aliases.xml and null_semantics.ini
    ids, aliases, merges, safe, terminals, canonical = build_partners(rng)
    merged_away = {a for a, _ in merges}
    own: dict[str, tuple[str, ...]] = {}
    for pid in rng.sample([p for p in terminals if p not in merged_away], 60):
        own[pid] = tuple(rng.sample(TOKEN_CHOICES, rng.choice([0, 0, 1, 1, 2, 3])))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', XML_HEADER.rstrip("\n"), "<partners>"]
    for pid in ids:
        inner = "".join(f"<alias>{a}</alias>" for a in aliases[pid])
        xml.append(f'  <partner id="{pid}">{inner}</partner>')
    for a, b in merges:
        xml.append(f'  <merge from="{a}" into="{b}"/>')
    xml.append("</partners>")
    (ci / "partner_aliases.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")
    ini = [INI_HEADER.rstrip("\n"), "[presence]", "explicit_null = present", "",
           "[fill]", "mode = absent_only", "", "[tokens]",
           "default = " + " | ".join(DEFAULT_TOKENS)]
    ini += sorted(f"{p} = {' | '.join(t)}".rstrip() for p, t in own.items())
    (ci / "null_semantics.ini").write_text("\n".join(ini) + "\n", encoding="utf-8")

    def sendable(pid: str) -> tuple[str, ...]:
        return own.get(pid, DEFAULT_TOKENS)

    # report_taxonomy.json, partner_order.tsv, replay_manifest.csv
    (ci / "report_taxonomy.json").write_text(json.dumps(TAXONOMY, indent=2) + "\n",
                                             encoding="utf-8")
    ranked = rng.sample(ids, 2050)
    ranks = sorted(rng.sample(range(100000, 1000000), len(ranked)))
    order_rows = sorted(zip(ranked, ranks))
    (ci / "partner_order.tsv").write_text(
        "partner_id\trank\n" + "".join(f"{p}\t{r}\n" for p, r in order_rows),
        encoding="utf-8")
    batches = [f"B{n:05d}" for n in range(1, 2201)]
    seqs = rng.sample(range(100000, 1000000), len(batches))
    seq_of = dict(zip(batches, seqs))
    by_seq = sorted(batches, key=seq_of.get)

    # partner_batches.jsonl
    safe_ids = sorted(safe)
    used_keys: set[str] = set()

    def fresh_key() -> str:
        while True:
            key = f"K{rng.getrandbits(32):08x}"
            if key not in used_keys:
                used_keys.add(key)
                return key

    def partner_value(pid: str) -> str:
        return pid if rng.random() < 0.6 else rng.choice(aliases[pid])

    def payload_for(domain: dict, pid: str, null_field: str | None = None,
                    force: frozenset | None = None) -> tuple[dict, frozenset]:
        tokens = sendable(pid)
        payload: dict = {}
        present = set()
        for name in domain["prereq"]:
            nca = policy[(domain["name"], name)][2]
            if name == null_field:
                payload[name] = None
                continue
            wanted = (name in force) if force is not None else rng.random() >= 0.35
            if wanted:
                payload[name] = _value(rng)
                present.add(name)
            elif nca == "absent" and rng.random() < 0.3:
                payload[name] = rng.choice(tokens) if tokens and rng.random() < 0.4 else None
        for name in domain["ops"]:
            if rng.random() >= 0.25:
                payload[name] = _value(rng)
        for name in domain["plain"]:
            roll = rng.random()
            if roll < 0.2:
                continue
            if roll < 0.35:
                payload[name] = None
            elif roll < 0.45 and tokens:
                payload[name] = rng.choice(tokens)
            else:
                payload[name] = _value(rng)
        names = list(payload)
        rng.shuffle(names)
        return {n: payload[n] for n in names}, frozenset(present)

    entries: list[dict] = []        # feed documents in file order (dicts or raw text)
    executed: list[dict] = []        # identities that execute a non-empty plan
    rejected_ids: list[tuple[str, str, dict]] = []
    replay_pool: list[dict] = []
    last_seq: dict[tuple[str, str], int] = {}

    def batch_after(seq: int) -> str:
        lo = next(i for i, b in enumerate(by_seq) if seq_of[b] >= seq)
        return rng.choice(by_seq[lo:])

    def add_original() -> None:
        domain = rng.choice(domains)
        roll = rng.random()
        if roll < 0.004:
            doc_partner, pid = f"ghost{rng.randint(1000, 9999)}x", None
        else:
            pid = rng.choice(safe_ids)
            doc_partner = partner_value(pid)
        canon = safe.get(pid) if pid else None
        unknown = rng.random() < 0.01
        version = rng.randint(VERSIONS + 1, VERSIONS + 4) if unknown else rng.randint(1, VERSIONS)
        payload, present = payload_for(domain, canon or rng.choice(terminals))
        key = fresh_key()
        batch = rng.choice(batches)
        doc = {"batch": batch, "partner": doc_partner, "key": key,
               "schema": schema_id(domain, version), "payload": payload}
        entries.append(doc)
        if canon is None:
            return
        plan = None if unknown else plans[domain["name"]][present][version]
        if plan is None:
            rejected_ids.append((doc_partner, key, domain))
            return
        item = {"doc": doc, "domain": domain, "plan": plan, "canon": canon,
                "version": version, "edited": False}
        last_seq[(canon, key)] = seq_of[batch]
        replay_pool.append(item)
        if plan:
            executed.append(item)

    reissues: list[str] = []
    while len(entries) < FEED_LINES - 12 - 2 * BOUNDARY_EACH:
        roll = rng.random()
        if replay_pool and roll < 0.05:
            item = rng.choice(replay_pool)
            ident = (item["canon"], item["doc"]["key"])
            batch = batch_after(last_seq[ident])
            last_seq[ident] = seq_of[batch]
            entries.append(dict(item["doc"], batch=batch))
        elif replay_pool and roll < 0.065:
            item = rng.choice(replay_pool)
            if item["edited"] or not item["domain"]["plain"]:
                continue
            item["edited"] = True
            ident = (item["canon"], item["doc"]["key"])
            batch = batch_after(last_seq[ident])
            last_seq[ident] = seq_of[batch]
            payload = dict(item["doc"]["payload"])
            payload[rng.choice(item["domain"]["plain"])] = str(rng.randint(100000, 999999))
            doc = dict(item["doc"], batch=batch, payload=payload)
            entries.append(doc)
            if rng.random() < 0.35:
                prefix = _fingerprint(doc["schema"], payload)[:12]
                reissues.append(f"REISSUE {doc['partner']} {doc['key']} {prefix}")
        else:
            add_original()

    # Boundary records: explicit null on a prerequisite whose column is empty.
    boundary: list[dict] = []
    wanted = {"unreachable": BOUNDARY_EACH, "longer": BOUNDARY_EACH}
    attempts = 0
    while any(wanted.values()):
        attempts += 1
        if attempts > 200000:
            raise SystemExit(f"boundary search ran dry: {wanted}")
        domain = rng.choice(domains)
        open_fields = [f for f in domain["prereq"] if policy[(domain["name"], f)][2] == ""]
        if not open_fields:
            continue
        field = rng.choice(open_fields)
        version = rng.choice([v for v in range(1, VERSIONS + 1) if v != domain["canonical"]])
        others = frozenset(f for f in domain["prereq"] if f != field and rng.random() < 0.6)
        right = plans[domain["name"]][others | {field}][version]
        wrong = plans[domain["name"]][others][version]
        if right is None or not right:
            continue
        if wrong is None:
            kind = "unreachable"
        elif len(wrong) != len(right):
            kind = "longer"
        else:
            continue
        if not wanted[kind]:
            continue
        wanted[kind] -= 1
        pid = rng.choice(safe_ids)
        payload, _ = payload_for(domain, safe[pid], null_field=field, force=others)
        doc = {"batch": rng.choice(batches), "partner": partner_value(pid),
               "key": fresh_key(), "schema": schema_id(domain, version),
               "payload": payload}
        item = {"doc": doc, "domain": domain, "plan": right, "wrong": wrong,
                "kind": kind, "field": field, "canon": safe[pid]}
        boundary.append(item)
        entries.insert(rng.randint(0, len(entries)), doc)

    bad_lines = [
        '["a", "list"]',
        '{"batch": "B99902", "partner": "P00001", "key": "k", "schema": "x.v1", "payload": []}',
        '{"batch": "B99999", "partner": "P00001", "key": "k", "schema": "x.v1", "payload": {}}',
        '{"partner": "P00001", "key": "k", "schema": "x.v1", "payload": {}}',
        '{"batch": "", "partner": "P00001", "key": "k", "schema": "x.v1", "payload": {}}',
        "{}",
        "null",
        '"text"',
        "42",
        '{"batch": "B99903", "partner": "P00001", "key": "k", "schema": "", "payload": {}}',
        '{"batch": "B99904", "partner": 7, "key": "k", "schema": "x.v1", "payload": {}}',
        '{"batch": "B99905", "partner": "P00001", "key": "k", "schema": "x.v1"}',
    ]
    for text in bad_lines:
        entries.insert(rng.randint(1, len(entries)), text)
    # Padded null tokens on plain fields (N6 keeps them as strings); own generator.
    pad = random.Random(SEED + 99)
    padded = 0
    for item in pad.sample(replay_pool, len(replay_pool)):
        if padded >= 40:
            break
        tokens = sendable(item["canon"])
        payload = item["doc"]["payload"]
        hits = [n for n in item["domain"]["plain"] if payload.get(n) in tokens]
        if not hits:
            continue
        name = pad.choice(hits)
        payload[name] = pad.choice([" ", "  "]) + payload[name] if pad.random() < 0.5 else payload[name] + " "
        padded += 1
    feed = [e if isinstance(e, str) else json.dumps(e) for e in entries]
    (ci / "partner_batches.jsonl").write_text("\n".join(feed) + "\n", encoding="utf-8")
    lines_of: dict[str, int] = {}
    xor_of: dict[str, int] = {}
    for e in entries:
        if isinstance(e, dict):
            lines_of[e["batch"]] = lines_of.get(e["batch"], 0) + 1
            xor_of[e["batch"]] = xor_of.get(e["batch"], 0) ^ int(_fingerprint(e["schema"], e["payload"])[:8], 16)
    (ci / "replay_manifest.csv").write_text(
        "batch_id,received_seq,lines,fp_xor\n" + "".join(
            f"{b},{seq_of[b]},{lines_of.get(b, 0)},{xor_of.get(b, 0):08x}\n" for b in batches),
        encoding="utf-8")

    # correction_log.txt
    def step_line(item: dict, schema: str, field: str) -> str:
        op = rng.choice(["SET", "SET", "UNSET", "NULL"])
        head = f"{op} {partner_value_of(item)} {item['doc']['key']} AT {schema} {field}"
        if op != "SET":
            return head
        value = rng.choice([rng.randint(0, 99), "fixed", None, [1, 2], {"v": 1}])
        return f"{head} {json.dumps(value)}"

    def partner_value_of(item: dict) -> str:
        return item["doc"]["partner"] if rng.random() < 0.5 else partner_value(item["canon"])

    body: list[str] = []
    for item in executed:
        if rng.random() >= 0.12:
            continue
        stops = [item["doc"]["schema"]] + [e["source_id"] for e in item["plan"][1:]]
        for field in rng.sample(item["domain"]["plain"], rng.randint(1, 2)):
            body.append(step_line(item, rng.choice(stops), field))
    pinned_boundary = 0
    for item in boundary:
        if pinned_boundary >= 5:
            break
        right_stops = [item["doc"]["schema"]] + [e["source_id"] for e in item["plan"][1:]]
        wrong_stops = set()
        if item["wrong"]:
            wrong_stops = {item["doc"]["schema"]} | {e["source_id"] for e in item["wrong"][1:]}
        choices = [s for s in right_stops if s not in wrong_stops] or (
            right_stops if item["wrong"] is None else [])
        if not choices:
            continue
        body.append(step_line(item, rng.choice(choices), rng.choice(item["domain"]["plain"])))
        pinned_boundary += 1
    for _ in range(350):
        domain = rng.choice(domains)
        pid = rng.choice(safe_ids)
        fake = {"doc": {"partner": partner_value(pid), "key": fresh_key()},
                "canon": safe[pid]}
        body.append(step_line(fake, schema_id(domain, rng.randint(1, VERSIONS)),
                              rng.choice(domain["plain"])))
    for partner, key, domain in rng.sample(rejected_ids, min(40, len(rejected_ids))):
        body.append(f"UNSET {partner} {key} AT {schema_id(domain, rng.randint(1, VERSIONS))} "
                    f"{rng.choice(domain['plain'])}")
    for _ in range(5):
        domain = rng.choice(domains)
        body.append(f"NULL ghost{rng.randint(1000, 9999)}x {fresh_key()} AT "
                    f"{schema_id(domain, 1)} {domain['plain'][0]}")
    rng.shuffle(body)
    malformed = [
        "SET P00001 kx AT orders_core.v1 amount",
        "MOVE P00002 k AT orders_core.v1 amount",
        "UNSET P00003 k orders_core.v2 qty",
        "SET P00004 k AT orders_core.v1 qty {not json}",
        "REISSUE P00005 k 12345",
        "NULL P00006 k AT orders_core.v1",
        "REISSUE P00007 kq 0123456789ab",
        "UNSET P00008 k AT orders_core.v1 qty extra",
        "REISSUE P00009 k ABCDEF012345",
        "SET P00010 k AT",
    ]
    for text in malformed:
        body.insert(rng.randint(len(body) // 10, len(body)), text)
    log = [CORRECTION_HEADER.rstrip("\n")]
    number = 0
    for text in reissues + body:
        if rng.random() < 0.02:
            log.append("")
        number += 1
        log.append(f"C{number:05d} {text}")
    (ci / "correction_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")

    (ci / "repository_contract.md").write_text(contract_md(), encoding="utf-8")
    (ci / "migration_semantics.md").write_text(semantics_md(), encoding="utf-8")
    shutil.copytree(SHIPPED_REPO, repo, ignore=shutil.ignore_patterns("__pycache__"))

    design = {
        "boundary": [{"line_key": b["doc"]["key"], "kind": b["kind"], "field": b["field"],
                      "schema": b["doc"]["schema"]} for b in boundary],
        "boundary_corrections": pinned_boundary,
        "feed_lines": len(feed),
        "correction_lines": number,
        "reissues": len(reissues),
    }
    (WORK / "visible_design.json").write_text(json.dumps(design, indent=2) + "\n",
                                              encoding="utf-8")


def main() -> None:
    generate(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
