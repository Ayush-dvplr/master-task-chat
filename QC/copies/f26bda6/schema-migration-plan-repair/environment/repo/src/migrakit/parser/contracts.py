"""Read the contract folder into one in-memory registry."""

from __future__ import annotations

import configparser
import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import MigrationError

CONTRACT_FILES = (
    "schema_versions.json",
    "migration_edges.csv",
    "field_policy.tsv",
    "null_semantics.ini",
    "partner_aliases.xml",
    "report_taxonomy.json",
    "partner_order.tsv",
)


@dataclass(frozen=True)
class Edge:
    edge_id: str
    source: str
    target: str
    requires: tuple[tuple[str, str], ...]
    operations: tuple[tuple[str, ...], ...]
    cost: int


@dataclass(frozen=True)
class FieldPolicy:
    has_default: bool
    default: object
    fill: str
    null_counts_as: str


@dataclass
class Registry:
    schemas: dict[str, str]
    canonical: dict[str, str]
    edges: dict[str, Edge]
    edges_from: dict[str, list[Edge]]
    policies: dict[tuple[str, str], FieldPolicy]
    presence_default: str
    fill_default: str
    default_tokens: tuple[str, ...]
    partner_tokens: dict[str, tuple[str, ...]]
    partners: frozenset[str]
    aliases: dict[str, str]
    merges: dict[str, str]
    taxonomy: list[tuple[str, tuple[str, ...]]]
    partner_rank: dict[str, int]
    _prerequisite_fields: dict[str, list[str]] = field(default_factory=dict)
    _named_fields: dict[str, list[str]] = field(default_factory=dict)

    def domain_of(self, schema_id: str) -> str:
        try:
            return self.schemas[schema_id]
        except (KeyError, TypeError):
            raise MigrationError("E_UNKNOWN_SCHEMA", str(schema_id)) from None

    def prerequisite_fields(self, domain: str) -> list[str]:
        """Fields named in a prerequisite of any edge leaving a schema of ``domain``."""
        if domain not in self._prerequisite_fields:
            names = {
                name
                for edge in self.edges.values()
                if self.schemas.get(edge.source) == domain
                for _, name in edge.requires
            }
            self._prerequisite_fields[domain] = sorted(names)
        return self._prerequisite_fields[domain]

    def named_fields(self, domain: str) -> list[str]:
        """Every field a prerequisite or an operation of the domain's edges names."""
        if domain not in self._named_fields:
            names = set(self.prerequisite_fields(domain))
            for edge in self.edges.values():
                if self.schemas.get(edge.source) != domain:
                    continue
                for operation in edge.operations:
                    names.update(_operation_fields(operation))
            self._named_fields[domain] = sorted(names)
        return self._named_fields[domain]

    def tokens_for(self, partner_id: str) -> tuple[str, ...]:
        return self.partner_tokens.get(partner_id) or self.default_tokens


def _operation_fields(operation: tuple[str, ...]) -> list[str]:
    if operation[0] == "rename":
        return [operation[1], operation[2]]
    return [operation[1]]


def parse_requires(text: str) -> tuple[tuple[str, str], ...]:
    found = []
    for part in filter(None, (piece.strip() for piece in text.split(";"))):
        kind, _, name = part.partition(":")
        if kind not in ("has", "lacks") or not name:
            raise ValueError(f"bad prerequisite {part!r}")
        found.append((kind, name))
    return tuple(found)


def parse_operations(text: str) -> tuple[tuple[str, ...], ...]:
    found: list[tuple[str, ...]] = []
    for part in filter(None, (piece.strip() for piece in text.split(";"))):
        kind, _, rest = part.partition(":")
        if kind == "rename":
            source, sep, target = rest.partition(">")
            if not (source and sep and target):
                raise ValueError(f"bad rename {part!r}")
            found.append(("rename", source, target))
        elif kind in ("drop", "add") and rest:
            found.append((kind, rest))
        elif kind == "cast":
            name, _, target_type = rest.partition(":")
            if not name or target_type not in ("int", "float", "str"):
                raise ValueError(f"bad cast {part!r}")
            found.append(("cast", name, target_type))
        else:
            raise ValueError(f"bad operation {part!r}")
    return tuple(found)


def _read_schemas(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    schemas: dict[str, str] = {}
    canonical: dict[str, str] = {}
    for entry in document["schemas"]:
        schemas[entry["id"]] = entry["domain"]
        if entry.get("canonical"):
            canonical[entry["domain"]] = entry["id"]
    return schemas, canonical


def _read_edges(path: Path) -> tuple[dict[str, Edge], dict[str, list[Edge]]]:
    edges: dict[str, Edge] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            edge = Edge(
                edge_id=row["edge_id"],
                source=row["source"],
                target=row["target"],
                requires=parse_requires(row["requires"]),
                operations=parse_operations(row["operations"]),
                cost=int(row["cost"]),
            )
            edges[edge.edge_id] = edge
    outgoing: dict[str, list[Edge]] = {}
    for edge_id in sorted(edges):
        outgoing.setdefault(edges[edge_id].source, []).append(edges[edge_id])
    return edges, outgoing


def _read_policies(path: Path) -> dict[tuple[str, str], FieldPolicy]:
    policies: dict[tuple[str, str], FieldPolicy] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE):
            raw_default = row["default"].strip()
            policies[(row["domain"], row["field"])] = FieldPolicy(
                has_default=bool(raw_default),
                default=json.loads(raw_default) if raw_default else None,
                fill=row["fill"].strip(),
                null_counts_as=row["null_counts_as"].strip(),
            )
    return policies


def _split_tokens(value: str) -> tuple[str, ...]:
    return tuple(token.strip() for token in value.split("|") if token.strip())


def _token_lists(parser: configparser.ConfigParser) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    section = parser["tokens"]
    default = _split_tokens(section.get("default", ""))
    by_partner = {
        partner: tuple(dict.fromkeys(default + _split_tokens(value)))
        for partner, value in section.items()
        if partner != "default"
    }
    return default, by_partner


def _read_null_semantics(path: Path):
    parser = configparser.ConfigParser(
        interpolation=None, comment_prefixes=(";",), inline_comment_prefixes=None
    )
    parser.optionxform = str  # partner ids are case sensitive
    parser.read_string(path.read_text(encoding="utf-8"))
    presence = parser.get("presence", "explicit_null", fallback="present").strip()
    fill = parser.get("fill", "mode", fallback="absent_only").strip()
    default_tokens, partner_tokens = _token_lists(parser)
    return presence, fill, default_tokens, partner_tokens


def _read_aliases(path: Path) -> tuple[frozenset[str], dict[str, str], dict[str, str]]:
    root = ET.parse(path).getroot()
    partners: set[str] = set()
    aliases: dict[str, str] = {}
    for element in root.iter("partner"):
        partner_id = element.get("id", "")
        partners.add(partner_id)
        for alias in element.iter("alias"):
            aliases[(alias.text or "").strip()] = partner_id
    merges = {element.get("from", ""): element.get("into", "") for element in root.iter("merge")}
    return frozenset(partners), aliases, merges


def _read_taxonomy(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return [(entry["name"], tuple(entry["members"])) for entry in document["categories"]]


def _read_order(path: Path) -> dict[str, int]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["partner_id"]: int(row["rank"]) for row in csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)}


def load_contracts(path: str | Path) -> Registry:
    """Load the seven contract files of one folder."""
    root = Path(path)
    schemas, canonical = _read_schemas(root / "schema_versions.json")
    edges, outgoing = _read_edges(root / "migration_edges.csv")
    presence, fill, default_tokens, partner_tokens = _read_null_semantics(root / "null_semantics.ini")
    partners, aliases, merges = _read_aliases(root / "partner_aliases.xml")
    return Registry(
        schemas=schemas,
        canonical=canonical,
        edges=edges,
        edges_from=outgoing,
        policies=_read_policies(root / "field_policy.tsv"),
        presence_default=presence,
        fill_default=fill,
        default_tokens=default_tokens,
        partner_tokens=partner_tokens,
        partners=partners,
        aliases=aliases,
        merges=merges,
        taxonomy=_read_taxonomy(root / "report_taxonomy.json"),
        partner_rank=_read_order(root / "partner_order.tsv"),
    )
