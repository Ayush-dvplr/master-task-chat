from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import re

REF_INPUTS = (
    "release_manifest.json", "schema_registry.json", "base_layer.yaml", "products.ini", "owners.csv",
    "deprecation.log", "selectors.rules", "team_overrides.json", "product_overrides.jsonl", "env_dev.toml",
    "env_prod.toml", "cluster_quota.json",
)


class RefError(Exception):
    def __init__(self, code: int, line: str):
        super().__init__(line)
        self.code = code
        self.line = line


def ref_canon(pid: str) -> str:
    return pid.upper().replace("-", "")


def _ref_lines(blob: bytes):
    for raw in blob.decode("utf-8").splitlines():
        text = raw.strip()
        if text and not text.startswith("#"):
            yield text


def _ref_text(spec: dict, raw: str):
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    kind = spec["type"]
    if kind == "integer":
        return int(text)
    if kind == "boolean":
        return text.lower() == "true"
    if kind == "list":
        return [] if text == "" else [part.strip() for part in text.split(",")]
    return text


REF_SKIP = object()


def _ref_read(spec: dict, raw: str, text: str = "strict"):
    word = raw.strip()
    if len(word) >= 2 and word[0] == '"' and word[-1] == '"':
        word = word[1:-1]
    kind = spec["type"]
    if text == "lenient":
        try:
            return _ref_text(spec, raw)
        except ValueError:
            return REF_SKIP
    if kind == "integer":
        if text == "isdigit":
            return int(word) if word.isdigit() else REF_SKIP
        if text == "sign":
            return int(word) if re.fullmatch(r"[+-]?[0-9]+", word) else REF_SKIP
        return int(word) if re.fullmatch(r"[0-9]+", word) else REF_SKIP
    if kind == "boolean" and word.lower() not in ("true", "false"):
        return REF_SKIP
    return _ref_text(spec, raw)


def _ref_judge(spec: dict | None, value) -> str | None:
    if spec is None:
        return "unknown_key"
    kind = spec["type"]
    if value is None:
        return None if spec.get("optional") else "type"
    if kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return "type"
        return None if spec["min"] <= value <= spec["max"] else "bounds"
    if kind == "boolean":
        return None if isinstance(value, bool) else "type"
    if kind == "enum":
        if not isinstance(value, str):
            return "type"
        return None if value in spec["values"] else "bounds"
    if kind == "string":
        return None if isinstance(value, str) else "type"
    ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
    return None if ok else "type"


def _ref_shares(quota: int, weights: dict) -> dict:
    total = sum(weights.values())
    base = {pid: quota * w // total for pid, w in weights.items()}
    left = quota - sum(base.values())
    order = sorted(weights, key=lambda pid: (-(quota * weights[pid] % total), pid))
    for pid in order[:left]:
        base[pid] += 1
    return base


def _ref_capped(quota: int, weights: dict, caps: dict, cap: str = "oracle") -> dict:
    if not weights:
        return {}
    if cap == "off" or not any(pid in caps for pid in weights):
        return _ref_shares(quota, weights)
    if cap == "restart":
        fixed = {}
        while True:
            rest = {pid: w for pid, w in weights.items() if pid not in fixed}
            got = _ref_shares(quota - sum(fixed.values()), rest) if rest else {}
            over = [pid for pid in rest if pid in caps and got[pid] > caps[pid]]
            if not over:
                return {**fixed, **got}
            for pid in over:
                fixed[pid] = caps[pid]
    held = {pid: 0 for pid in weights}
    pool, taking, rounds = quota, dict(weights), 0
    while pool > 0 and taking:
        got = _ref_shares(pool, taking)
        for pid in taking:
            held[pid] += got[pid]
        rounds += 1
        over = [pid for pid in taking if pid in caps and held[pid] > caps[pid]]
        if not over:
            break
        pool = sum(held[pid] - caps[pid] for pid in over)
        for pid in over:
            held[pid] = caps[pid]
        taking = {pid: w for pid, w in taking.items() if not (pid in caps and held[pid] >= caps[pid])}
        if cap == "single" and rounds == 1:
            got = _ref_shares(pool, taking) if taking else {}
            for pid in taking:
                held[pid] += got[pid]
            break
    return held


def ref_compute(files: dict, date: str | None = None, quota_override: dict | None = None,
                lenient_json: bool = False, owner_events: bool = True, canon_log: bool = True,
                assign: str = "latest", text: str = "strict", cap: str = "oracle") -> dict:
    for name in REF_INPUTS:
        if name not in files:
            raise RefError(2, f"error: missing input {name}")
    manifest = json.loads(files["release_manifest.json"])
    day = manifest["compile_date"] if date is None else date
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise RefError(2, f"error: invalid date {day}")
    try:
        _dt.date.fromisoformat(day)
    except ValueError:
        raise RefError(2, f"error: invalid date {day}") from None
    schema = json.loads(files["schema_registry.json"])["keys"]

    base = {}
    for line in _ref_lines(files["base_layer.yaml"]):
        key, _, raw = line.partition(":")
        value = _ref_read(schema[key.strip()], raw, text)
        if value is not REF_SKIP:
            base[key.strip()] = value

    products = {}
    current = None
    for line in _ref_lines(files["products.ini"]):
        if line.startswith("[product ") and line.endswith("]"):
            current = {"id": ref_canon(line[9:-1].strip()), "lines": []}
            products[current["id"]] = current
            continue
        key, _, raw = line.partition("=")
        key, raw = key.strip(), raw.strip()
        if key == "owner":
            current["owner"] = raw
        elif key == "tier":
            current["tier"] = raw
        elif key == "labels":
            current["labels"] = [x.strip() for x in raw.split(",")] if raw else []
        else:
            value = _ref_read(schema[key], raw, text)
            if value is not REF_SKIP:
                current["lines"].append((key, value))

    catalog = {ref_canon(pid) for pid in manifest["catalog"]}
    diff = sorted(catalog ^ set(products))
    if diff:
        raise RefError(3, f"error: catalog mismatch {diff[0]}")

    rows = list(csv.DictReader(io.StringIO(files["owners.csv"].decode("utf-8"))))
    gone_products, gone_owners = set(), set()
    for line in _ref_lines(files["deprecation.log"]):
        parts = line.split()
        if len(parts) < 3 or parts[1] != "RETIRE" or parts[0][:10] > day:
            continue
        field, _, value = parts[2].partition("=")
        if field == "product":
            gone_products.add(ref_canon(value) if canon_log else value)
        elif field == "owner" and owner_events:
            gone_owners.add(value)

    team_on_day = {}
    if assign in ("latest", "latest_covering"):
        latest = {}
        for row in rows:
            covers = row["active_to"] == "" or row["active_to"] >= day
            if row["active_from"] <= day and (assign == "latest" or covers):
                if row["owner"] not in latest or row["active_from"] > latest[row["owner"]]["active_from"]:
                    latest[row["owner"]] = row
        for owner, row in latest.items():
            if (row["active_to"] == "" or row["active_to"] >= day) and owner not in gone_owners:
                team_on_day[owner] = row["team"]
    else:
        for row in rows:
            if row["active_from"] <= day and (row["active_to"] == "" or row["active_to"] >= day):
                if row["owner"] not in gone_owners and (assign == "last" or row["owner"] not in team_on_day):
                    team_on_day[row["owner"]] = row["team"]

    status, team = {}, {}
    for pid, prod in products.items():
        if pid in gone_products:
            status[pid], team[pid] = "retired", None
        elif prod["owner"] in team_on_day:
            status[pid], team[pid] = "active", team_on_day[prod["owner"]]
        else:
            status[pid], team[pid] = "orphaned", None
    compiled = [pid for pid in sorted(products) if status[pid] != "retired"]
    active = [pid for pid in compiled if status[pid] == "active"]

    def judge(spec, value):
        if lenient_json and spec is not None and isinstance(value, str) and spec["type"] in ("integer", "boolean"):
            if spec["type"] == "integer" and value.isdigit():
                return _ref_judge(spec, int(value))
            if spec["type"] == "boolean" and value.lower() in ("true", "false"):
                return None
        return _ref_judge(spec, value)

    def lenient_value(spec, value):
        if lenient_json and isinstance(value, str) and spec["type"] == "integer":
            return int(value)
        if lenient_json and isinstance(value, str) and spec["type"] == "boolean":
            return value.lower() == "true"
        return value

    rejected_team, team_layer = [], {}
    for tname in sorted(json.loads(files["team_overrides.json"])):
        entries = json.loads(files["team_overrides.json"])[tname]
        for key in sorted(entries):
            reason = judge(schema.get(key), entries[key])
            if reason:
                rejected_team.append({"source": "team_overrides", "team": tname, "key": key, "reason": reason})
            else:
                team_layer.setdefault(tname, []).append((key, lenient_value(schema[key], entries[key])))

    compiled_set = set(compiled)
    over = [json.loads(line) for line in files["product_overrides.jsonl"].decode("utf-8").splitlines() if line.strip()]
    over.sort(key=lambda o: o["seq"])
    rejected_prod, prod_layer = [], {}
    for o in over:
        pid = ref_canon(o["product"])
        if pid not in compiled_set:
            reason = "unknown_product"
        else:
            reason = judge(schema.get(o["key"]), o["value"])
        if reason:
            rejected_prod.append({"source": "product_overrides", "seq": o["seq"], "product": pid,
                                  "key": o["key"], "reason": reason})
        else:
            prod_layer.setdefault(pid, []).append((o["key"], lenient_value(schema[o["key"]], o["value"])))

    rules = []
    for line in _ref_lines(files["selectors.rules"]):
        m = re.match(r"match (team|tier|label):(\S+) set (\S+) ?(.*)$", line)
        value = _ref_read(schema[m.group(3)], m.group(4), text)
        if value is not REF_SKIP:
            rules.append((m.group(1), m.group(2), m.group(3), value))

    def env_layers(blob):
        sections, name = {}, None
        for line in _ref_lines(blob):
            if line.startswith("["):
                name = line[1:-1].strip()
                sections[name] = []
                continue
            key, _, raw = line.partition("=")
            value = _ref_read(schema[key.strip()], raw, text)
            if value is not REF_SKIP:
                sections[name].append((key.strip(), value))
        return sections

    def resolve(pid, env):
        prod = products[pid]
        s = dict(base)
        chain = []
        if env is not None:
            chain += env.get("defaults", []) + env.get("tier." + prod["tier"], [])
        for field, name, key, value in rules:
            hit = (field == "team" and team[pid] == name) or (field == "tier" and prod["tier"] == name) or \
                  (field == "label" and name in prod["labels"])
            if hit:
                chain.append((key, value))
        if team[pid] is not None:
            chain += team_layer.get(team[pid], [])
        chain += prod["lines"]
        chain += prod_layer.get(pid, [])
        for key, value in chain:
            if value is None:
                s.pop(key, None)
            else:
                s[key] = value
        return s

    quotas = json.loads(files["cluster_quota.json"])
    if quota_override:
        quotas = dict(quotas, **quota_override)
    out = {}
    settings = {pid: resolve(pid, None) for pid in compiled}
    shares = _ref_capped(quotas["shared"], {pid: settings[pid]["weight"] for pid in active},
                         {pid: settings[pid]["quota_cap"] for pid in active if "quota_cap" in settings[pid]}, cap)
    out["config.json"] = {
        "release": manifest["release"], "compile_date": day, "cluster_quota": quotas["shared"],
        "products": {pid: {"status": status[pid], "owner": products[pid]["owner"], "tier": products[pid]["tier"],
                           "team": team[pid], "settings": settings.get(pid), "quota": shares.get(pid, 0)}
                     for pid in sorted(products)},
    }
    totals = {"config": sum(shares.values())}
    for env_name in ("dev", "prod"):
        layers = env_layers(files[f"env_{env_name}.toml"])
        es = {pid: resolve(pid, layers) for pid in active}
        eq = _ref_capped(quotas[env_name], {pid: es[pid]["weight"] for pid in active},
                         {pid: es[pid]["quota_cap"] for pid in active if "quota_cap" in es[pid]}, cap)
        totals[env_name] = sum(eq.values())
        out[f"profile_{env_name}.json"] = {
            "env": env_name, "release": manifest["release"], "compile_date": day, "cluster_quota": quotas[env_name],
            "products": {pid: {"alerts_enabled": es[pid]["alerts_enabled"], "pii_scan": es[pid]["pii_scan"],
                               "replicas": es[pid]["replicas"], "quota": eq[pid]} for pid in active},
        }
    out["validation_report.json"] = {"release": manifest["release"], "rejected_overrides": rejected_team + rejected_prod}
    by_team = {}
    for pid in active:
        by_team[team[pid]] = by_team.get(team[pid], 0) + 1
    counts = {"active": 0, "orphaned": 0, "retired": 0}
    for pid in products:
        counts[status[pid]] += 1
    out["summary.json"] = {
        "release": manifest["release"], "compile_date": day, "status_counts": counts, "active_by_team": by_team,
        "rejected_overrides": {"team_overrides": len(rejected_team), "product_overrides": len(rejected_prod)},
        "quota_total": totals,
    }
    return out


def ref_dump(doc) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("ascii")
