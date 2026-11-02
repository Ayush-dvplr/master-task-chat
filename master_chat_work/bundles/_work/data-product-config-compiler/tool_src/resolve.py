"""Status, team and settings resolution for a compile date."""

from loaders import coerce


def owner_team(owner, owner_rows, day):
    """Team of an owner on day, or None when the owner is not active on day."""
    for row in owner_rows:
        if row["owner"] != owner:
            continue
        if row["active_from"] <= day and (row["active_to"] == "" or row["active_to"] >= day):
            return row["team"]
    return None


def classify(products, owner_rows, retired, day):
    """Return ({pid: status}, {pid: team}) for every catalog product."""
    by_owner = {}
    for row in owner_rows:
        by_owner.setdefault(row["owner"], []).append(row)
    status, team = {}, {}
    for pid, product in products.items():
        if pid in retired and retired[pid] <= day:
            status[pid], team[pid] = "retired", None
            continue
        owner_now = owner_team(product["owner"], by_owner.get(product["owner"], []), day)
        if owner_now is None:
            status[pid], team[pid] = "orphaned", None
        else:
            status[pid], team[pid] = "active", owner_now
    return status, team


def check_override(spec, value):
    """Return (reason, value) for one JSON-layer value; reason is None when accepted."""
    if spec is None:
        return "unknown_key", None
    if value is None:
        if spec.get("optional"):
            return None, None
        return "type", None
    try:
        value = coerce(spec, value)
    except ValueError:
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
    rejected_products, product_layer = [], {}
    for record in product_records:
        if record["product"] not in compiled:
            reason, value = "unknown_product", None
        else:
            reason, value = check_override(schema.get(record["key"]), record["value"])
        if reason:
            rejected_products.append({"source": "product_overrides", "seq": record["seq"],
                                      "product": record["product"], "key": record["key"], "reason": reason})
        else:
            product_layer.setdefault(record["product"], []).append((record["key"], value))
    rejected_products.sort(key=lambda entry: entry["seq"])
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
        elif value or isinstance(value, (bool, int)):
            settings[key] = value


def resolve(pid, product, team_name, base, rules, team_layer, product_layer, env_sections=None):
    """Resolved settings of one compiled product, optionally for an env profile."""
    settings = dict(base)
    if env_sections is not None:
        merge(settings, env_sections.get("defaults", []))
        merge(settings, env_sections.get("tier." + product["tier"], []))
    for rule in rules:
        if rule_matches(rule, product, team_name):
            merge(settings, [(rule[2], rule[3])])
    if team_name is not None:
        merge(settings, team_layer.get(team_name, []))
    merge(settings, product["lines"])
    merge(settings, product_layer.get(pid, []))
    return settings
