"""Readers for the files of a dpcc data folder.

Every reader takes the data folder and returns plain Python structures. Product
ids are put in canonical form by canon() wherever an id is read.
"""

import csv
import json
import os
import re

INPUTS = (
    "release_manifest.json",
    "schema_registry.json",
    "base_layer.yaml",
    "products.ini",
    "owners.csv",
    "deprecation.log",
    "selectors.rules",
    "team_overrides.json",
    "product_overrides.jsonl",
    "env_dev.toml",
    "env_prod.toml",
    "cluster_quota.json",
)

_DIGITS = re.compile(r"[0-9]+")


class InputError(Exception):
    """A problem with the data folder, reported on one stderr line."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def canon(pid):
    """Canonical product id: upper case, hyphens removed."""
    return str(pid).upper().replace("-", "")


def missing_inputs(data_dir):
    return [name for name in INPUTS if not os.path.isfile(os.path.join(data_dir, name))]


def _read(data_dir, name):
    with open(os.path.join(data_dir, name), encoding="utf-8") as handle:
        return handle.read()


def _content_lines(text):
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            yield line


def _unquote(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]
    return raw


def text_value(spec, raw):
    """Read one text-layer value (yaml, ini, rules, env) by its key's type.

    Raises ValueError when the text does not read as that type.
    """
    text = _unquote(raw)
    kind = spec["type"]
    if kind == "integer":
        if not _DIGITS.fullmatch(text):
            raise ValueError(raw)
        return int(text)
    if kind == "boolean":
        lowered = text.lower()
        if lowered not in ("true", "false"):
            raise ValueError(raw)
        return lowered == "true"
    if kind == "list":
        return [] if text == "" else [item.strip() for item in text.split(",")]
    if kind in ("enum", "string"):
        return text
    raise ValueError(kind)


def json_type_ok(spec, value):
    """Whether a JSON-layer value has the type the schema states for the key."""
    kind = spec["type"]
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind in ("enum", "string"):
        return isinstance(value, str)
    if kind == "list":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return False


def _text_layer_line(layer, schema, key, raw):
    """Append one text-layer entry, passing over what does not read as its type."""
    spec = schema.get(key)
    if spec is None:
        return
    try:
        layer.append((key, text_value(spec, raw)))
    except ValueError:
        pass


def load_manifest(data_dir):
    return json.loads(_read(data_dir, "release_manifest.json"))


def load_schema(data_dir):
    return json.loads(_read(data_dir, "schema_registry.json"))["keys"]


def load_quota(data_dir):
    return json.loads(_read(data_dir, "cluster_quota.json"))


def load_base(data_dir, schema):
    """Return the base_layer.yaml text layer as [(key, value)]."""
    base = []
    for line in _content_lines(_read(data_dir, "base_layer.yaml")):
        key, _, raw = line.partition(":")
        _text_layer_line(base, schema, key.strip(), raw)
    return base


def load_products(data_dir, schema):
    """Return {canonical id: {owner, tier, labels, lines}} from products.ini."""
    products = {}
    current = None
    for line in _content_lines(_read(data_dir, "products.ini")):
        if line.startswith("[product ") and line.endswith("]"):
            pid = canon(line[len("[product "):-1].strip())
            current = {"owner": None, "tier": None, "labels": [], "lines": []}
            products[pid] = current
            continue
        if current is None:
            continue
        key, _, raw = line.partition("=")
        key, raw = key.strip(), raw.strip()
        if key == "owner":
            current["owner"] = raw
        elif key == "tier":
            current["tier"] = raw
        elif key == "labels":
            current["labels"] = [item.strip() for item in raw.split(",")] if raw else []
        else:
            _text_layer_line(current["lines"], schema, key, raw)
    return products


def load_owners(data_dir):
    """Return {owner: [assignment rows]} from owners.csv."""
    with open(os.path.join(data_dir, "owners.csv"), encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_owner = {}
    for row in rows:
        by_owner.setdefault(row["owner"], []).append({
            "team": row["team"],
            "active_from": row["active_from"] or "",
            "active_to": row["active_to"] or "",
        })
    return by_owner


def load_deprecations(data_dir):
    """Return ({product id: date}, {owner: date}) from the RETIRE events."""
    products, owners = {}, {}
    for line in _content_lines(_read(data_dir, "deprecation.log")):
        parts = line.split()
        if len(parts) < 3 or parts[1] != "RETIRE":
            continue
        when = parts[0][:10]
        fields = dict(part.partition("=")[::2] for part in parts[2:])
        if "product" in fields:
            pid = canon(fields["product"])
            if pid not in products or when < products[pid]:
                products[pid] = when
        if "owner" in fields:
            owner = fields["owner"]
            if owner not in owners or when < owners[owner]:
                owners[owner] = when
    return products, owners


def load_rules(data_dir, schema):
    """Return [(field, name, key, value)] from selectors.rules in file order."""
    rules = []
    for line in _content_lines(_read(data_dir, "selectors.rules")):
        words = line.split(" ", 2)
        if len(words) < 3 or words[0] != "match" or " set " not in line:
            continue
        field, _, name = words[1].partition(":")
        key, _, raw = line.split(" set ", 1)[1].partition(" ")
        entry = []
        _text_layer_line(entry, schema, key.strip(), raw)
        if entry:
            rules.append((field, name, entry[0][0], entry[0][1]))
    return rules


def load_team_overrides(data_dir):
    return json.loads(_read(data_dir, "team_overrides.json"))


def load_product_overrides(data_dir):
    """Return the product_overrides.jsonl records with canonical product ids."""
    records = []
    for line in _read(data_dir, "product_overrides.jsonl").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record["product"] = canon(record["product"])
        records.append(record)
    return records


def load_env(data_dir, env, schema):
    """Return {section: [(key, value)]} from env_<env>.toml."""
    sections = {}
    current = None
    for line in _content_lines(_read(data_dir, "env_%s.toml" % env)):
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1].strip(), [])
            continue
        if current is None:
            continue
        key, _, raw = line.partition("=")
        _text_layer_line(current, schema, key.strip(), raw)
    return sections
