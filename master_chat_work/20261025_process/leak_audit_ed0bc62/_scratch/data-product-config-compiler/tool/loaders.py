"""Readers for the files of a dpcc data folder.

Every reader takes the data folder and returns plain Python structures. Product
ids are put in canonical form by canon() where the catalog is built.
"""

import csv
import json
import os

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


class InputError(Exception):
    """A problem with the data folder, reported on one stderr line."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def canon(pid):
    """Canonical product id: upper case, hyphens removed."""
    return pid.upper().replace("-", "")


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


def coerce(spec, value):
    """Turn a layer value into the Python value of the key's schema type.

    Raises ValueError when the value cannot be read as that type.
    """
    kind = spec["type"]
    if kind == "integer":
        return int(str(value).strip())
    if kind == "boolean":
        text = str(value).strip().lower()
        if text not in ("true", "false"):
            raise ValueError(value)
        return text == "true"
    if kind == "list":
        if isinstance(value, list):
            return [str(item) for item in value]
        text = str(value).strip()
        return [] if text == "" else [item.strip() for item in text.split(",")]
    if kind in ("enum", "string"):
        if isinstance(value, (list, dict)):
            raise ValueError(value)
        return str(value)
    raise ValueError(kind)


def _unquote(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]
    return raw


def text_value(spec, raw):
    """Read one text-layer value (yaml, ini, rules)."""
    return coerce(spec, _unquote(raw))


def load_manifest(data_dir):
    return json.loads(_read(data_dir, "release_manifest.json"))


def load_schema(data_dir):
    return json.loads(_read(data_dir, "schema_registry.json"))["keys"]


def load_quota(data_dir):
    return json.loads(_read(data_dir, "cluster_quota.json"))


def load_base(data_dir, schema):
    base = {}
    for line in _content_lines(_read(data_dir, "base_layer.yaml")):
        key, _, raw = line.partition(":")
        key = key.strip()
        base[key] = text_value(schema[key], raw)
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
        key, _, raw = line.partition("=")
        key, raw = key.strip(), raw.strip()
        if key == "owner":
            current["owner"] = raw
        elif key == "tier":
            current["tier"] = raw
        elif key == "labels":
            current["labels"] = [item.strip() for item in raw.split(",")] if raw else []
        else:
            current["lines"].append((key, text_value(schema[key], raw)))
    return products


def load_owners(data_dir):
    """Return the owners.csv rows as dicts."""
    with open(os.path.join(data_dir, "owners.csv"), encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_deprecations(data_dir):
    """Return {product id: retirement date} from the RETIRE events of deprecation.log."""
    retired = {}
    for line in _content_lines(_read(data_dir, "deprecation.log")):
        parts = line.split()
        if len(parts) < 3 or parts[1] != "RETIRE":
            continue
        fields = dict(part.partition("=")[::2] for part in parts[2:])
        if "product" in fields:
            when = parts[0][:10]
            pid = fields["product"]
            if pid not in retired or when < retired[pid]:
                retired[pid] = when
    return retired


def load_rules(data_dir, schema):
    """Return [(field, name, key, value)] from selectors.rules in file order."""
    rules = []
    for line in _content_lines(_read(data_dir, "selectors.rules")):
        words = line.split(" ", 3)
        if len(words) < 3 or words[0] != "match":
            continue
        field, _, name = words[1].partition(":")
        rest = line.split(" set ", 1)[1]
        key, _, raw = rest.partition(" ")
        rules.append((field, name, key, text_value(schema[key], raw)))
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
    name = None
    for line in _content_lines(_read(data_dir, "env_%s.toml" % env)):
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            sections[name] = []
            continue
        key, _, raw = line.partition("=")
        key, raw = key.strip(), raw.strip()
        if raw.lower() in ("true", "false"):
            value = bool(raw)
        else:
            value = text_value(schema[key], raw)
        sections[name].append((key, value))
    return sections
