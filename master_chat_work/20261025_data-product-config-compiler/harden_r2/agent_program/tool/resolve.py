"""Status, team and settings resolution for a compile date."""

from loaders import json_type_ok


def assignment(rows, day):
    """The owner's assignment on day: the latest active_from on or before day."""
    chosen = None
    for row in rows:
        if row["active_from"] <= day and (chosen is None or row["active_from"] > chosen["active_from"]):
            chosen = row
    return chosen


def owner_team(owner, owners, retired_owners, day):
    """Team of owner on day, or None when the owner is not active on day."""
    if owner in retired_owners and retired_owners[owner] <= day:
        return None
    current = assignment(owners.get(owner, []), day)
    if current is None:
        return None
    if current["active_to"] != "" and current["active_to"] < day:
        return None
    return current["team"]


def classify(products, owners, retired_products, retired_owners, day):
    """Return ({pid: status}, {pid: team}) for every catalog product."""
    status, team = {}, {}
    for pid, product in products.items():
        if pid in retired_products and retired_products[pid] <= day:
            status[pid], team[pid] = "retired", None
            continue
        team_now = owner_team(product["owner"], owners, retired_owners, day)
        if team_now is None:
            status[pid], team[pid] = "orphaned", None
        else:
            status[pid], team[pid] = "active", team_now
    return status, team


def check_override(spec, value):
    """Return (reason, value) for one JSON-layer value; reason is None when accepted."""
    if spec is None:
        return "unknown_key", None
    if value is None:
        if spec.get("optional"):
            return None, None
        return "type", None
    if not json_type_ok(spec, value):
        return "type", None
    if spec["type"] == "integer" and not spec["min"] <= value <= spec["max"]:
        return "bounds", None
    if spec["type"] == "enum" and value not in spec["values"]:
        return "bounds", None
    return None, value


def screen_overrides(schema, team_overrides, product_records, compiled):
    """Split the JSON layers into accepted layers and rejected entries."""
    rejected_team, team_layer = [], {}
    for team_name in sorted(team_overrides):
        entries = team_overrides[team_name]
        for key in sorted(entries):
            reason, value = check_override(schema.get(key), entries[key])
            if reason:
                rejected_team.append({"source": "team_overrides", "team": team_name, "key": key, "reason": reason})
            else:
                team_layer.setdefault(team_name, []).append((key, value))
    rejected_products, accepted = [], {}
    for record in product_records:
        if record["product"] not in compiled:
            reason, value = "unknown_product", None
        else:
            reason, value = check_override(schema.get(record["key"]), record["value"])
        if reason:
            rejected_products.append({"source": "product_overrides", "seq": record["seq"],
                                      "product": record["product"], "key": record["key"], "reason": reason})
        else:
            accepted.setdefault(record["product"], []).append((record["seq"], record["key"], value))
    rejected_products.sort(key=lambda entry: entry["seq"])
    product_layer = {pid: [(key, value) for _, key, value in sorted(entries, key=lambda item: item[0])]
                     for pid, entries in accepted.items()}
    return rejected_team + rejected_products, team_layer, product_layer


def rule_matches(rule, product, team_name):
    field, name = rule[0], rule[1]
    if field == "team":
        return team_name == name
    if field == "tier":
        return product["tier"] == name
    if field == "label":
        return name in product["labels"]
    return False


def merge(settings, layer):
    """Apply one layer of (key, value) pairs onto settings in place."""
    for key, value in layer:
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value


def resolve(pid, product, team_name, base, rules, team_layer, product_layer, env_sections=None):
    """Resolved settings of one compiled product, optionally for an env profile."""
    settings = {}
    merge(settings, base)
    if env_sections is not None:
        merge(settings, env_sections.get("defaults", []))
        merge(settings, env_sections.get("tier." + str(product["tier"]), []))
    for rule in rules:
        if rule_matches(rule, product, team_name):
            merge(settings, [(rule[2], rule[3])])
    if team_name is not None:
        merge(settings, team_layer.get(team_name, []))
    merge(settings, product["lines"])
    merge(settings, product_layer.get(pid, []))
    return settings
