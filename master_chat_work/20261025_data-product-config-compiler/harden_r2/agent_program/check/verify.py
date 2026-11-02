"""Independent re-derivation of the dpcc documents, straight from the contract.

Deliberately written apart from the tool: it re-reads the data folder, rebuilds the
five compile documents plus report.json and diffs them against the written files.
"""

import csv
import hashlib
import json
import re
import sys

DATA = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/app/out"


def path(name):
    return DATA + "/" + name


def canonical(pid):
    return pid.upper().replace("-", "")


def lines_of(name):
    out = []
    with open(path(name), encoding="utf-8") as fh:
        for raw in fh:
            s = raw.strip()
            if s and s[0] != "#":
                out.append(s)
    return out


SCHEMA = json.load(open(path("schema_registry.json")))["keys"]


def read_text(key, raw):
    """Contract 'Text layers': returns (ok, value)."""
    raw = raw.strip()
    if len(raw) > 1 and raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    kind = SCHEMA[key]["type"]
    if kind == "integer":
        return (True, int(raw)) if re.match(r"^[0-9]+$", raw) else (False, None)
    if kind == "boolean":
        if raw.lower() == "true":
            return True, True
        if raw.lower() == "false":
            return True, False
        return False, None
    if kind == "list":
        if raw == "":
            return True, []
        return True, [p.strip() for p in raw.split(",")]
    return True, raw


def text_layer(pairs):
    """Build a layer, dropping values that do not read as their key's type."""
    layer = []
    for key, raw in pairs:
        if key not in SCHEMA:
            continue
        ok, value = read_text(key, raw)
        if ok:
            layer.append((key, value))
    return layer


def json_ok(key, value):
    kind = SCHEMA[key]["type"]
    if kind == "integer":
        return value.__class__ is int
    if kind == "boolean":
        return value.__class__ is bool
    if kind in ("enum", "string"):
        return value.__class__ is str
    if kind == "list":
        return value.__class__ is list and all(i.__class__ is str for i in value)
    return False


def reason_for(key, value, known_product=True):
    if not known_product:
        return "unknown_product"
    if key not in SCHEMA:
        return "unknown_key"
    if value is None:
        return None if SCHEMA[key].get("optional") else "type"
    if not json_ok(key, value):
        return "type"
    spec = SCHEMA[key]
    if spec["type"] == "integer" and not spec["min"] <= value <= spec["max"]:
        return "bounds"
    if spec["type"] == "enum" and value not in spec["values"]:
        return "bounds"
    return None


def apply_layer(settings, layer):
    for key, value in layer:
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value


# ---------------------------------------------------------------- inputs
manifest = json.load(open(path("release_manifest.json")))
D = manifest["compile_date"]
catalog = [canonical(p) for p in manifest["catalog"]]
quotas = json.load(open(path("cluster_quota.json")))

base = text_layer([(l.split(":", 1)[0].strip(), l.split(":", 1)[1]) for l in lines_of("base_layer.yaml")])

meta = {}
cur = None
for line in lines_of("products.ini"):
    if line.startswith("[product "):
        cur = canonical(line[9:-1].strip())
        meta[cur] = {"owner": None, "tier": None, "labels": [], "raw": []}
        continue
    k, v = line.split("=", 1)
    k, v = k.strip(), v.strip()
    if k == "owner":
        meta[cur]["owner"] = v
    elif k == "tier":
        meta[cur]["tier"] = v
    elif k == "labels":
        meta[cur]["labels"] = [x.strip() for x in v.split(",")] if v else []
    else:
        meta[cur]["raw"].append((k, v))
for pid in meta:
    meta[pid]["lines"] = text_layer(meta[pid]["raw"])

assert sorted(meta) == sorted(set(catalog)), "catalog mismatch"

owner_rows = {}
for row in csv.DictReader(open(path("owners.csv"), newline="")):
    owner_rows.setdefault(row["owner"], []).append(row)

retired_product, retired_owner = {}, {}
for line in lines_of("deprecation.log"):
    bits = line.split()
    if len(bits) < 3 or bits[1] != "RETIRE":
        continue
    day = bits[0][:10]
    for bit in bits[2:]:
        if bit.startswith("product="):
            pid = canonical(bit[8:])
            retired_product[pid] = min(day, retired_product.get(pid, day))
        if bit.startswith("owner="):
            who = bit[6:]
            retired_owner[who] = min(day, retired_owner.get(who, day))

rules = []
for line in lines_of("selectors.rules"):
    head, tail = line.split(" set ", 1)
    field, name = head.split(" ", 1)[1].split(":", 1)
    key, _, raw = tail.partition(" ")
    layer = text_layer([(key, raw)])
    if layer:
        rules.append((field, name, layer[0]))

team_json = json.load(open(path("team_overrides.json")))
prod_json = [json.loads(l) for l in open(path("product_overrides.jsonl")) if l.strip()]

envs = {}
for env in ("dev", "prod"):
    sections, name = {}, None
    for line in lines_of("env_%s.toml" % env):
        if line.startswith("["):
            name = line[1:-1].strip()
            sections[name] = []
            continue
        k, v = line.split("=", 1)
        sections[name].append((k.strip(), v))
    envs[env] = {sec: text_layer(pairs) for sec, pairs in sections.items()}

# ---------------------------------------------------------------- status
status, team = {}, {}
for pid in catalog:
    if pid in retired_product and retired_product[pid] <= D:
        status[pid], team[pid] = "retired", None
        continue
    owner = meta[pid]["owner"]
    past = [r for r in owner_rows.get(owner, []) if r["active_from"] <= D]
    assigned = max(past, key=lambda r: r["active_from"]) if past else None
    live = (assigned is not None
            and (assigned["active_to"] == "" or assigned["active_to"] >= D)
            and not (owner in retired_owner and retired_owner[owner] <= D))
    status[pid] = "active" if live else "orphaned"
    team[pid] = assigned["team"] if live else None

compiled = set(pid for pid in catalog if status[pid] != "retired")
active = sorted(pid for pid in catalog if status[pid] == "active")

# ---------------------------------------------------------------- overrides
rejected = []
team_layer = {}
for tname in sorted(team_json):
    for key in sorted(team_json[tname]):
        value = team_json[tname][key]
        why = reason_for(key, value)
        if why:
            rejected.append({"source": "team_overrides", "team": tname, "key": key, "reason": why})
        else:
            team_layer.setdefault(tname, []).append((key, value))

prod_layer = {}
for rec in sorted(prod_json, key=lambda r: r["seq"]):
    pid = canonical(rec["product"])
    why = reason_for(rec["key"], rec["value"], known_product=pid in compiled)
    if why:
        rejected.append({"source": "product_overrides", "seq": rec["seq"], "product": pid,
                         "key": rec["key"], "reason": why})
    else:
        prod_layer.setdefault(pid, []).append((rec["key"], rec["value"]))


def settings_of(pid, env=None):
    out = {}
    apply_layer(out, base)
    if env:
        apply_layer(out, envs[env].get("defaults", []))
        apply_layer(out, envs[env].get("tier." + meta[pid]["tier"], []))
    for field, name, entry in rules:
        hit = ((field == "team" and team[pid] == name)
               or (field == "tier" and meta[pid]["tier"] == name)
               or (field == "label" and name in meta[pid]["labels"]))
        if hit:
            apply_layer(out, [entry])
    if team[pid] is not None:
        apply_layer(out, team_layer.get(team[pid], []))
    apply_layer(out, meta[pid]["lines"])
    apply_layer(out, prod_layer.get(pid, []))
    return out


# ---------------------------------------------------------------- quota
def proportional(Q, weight):
    W = sum(weight.values())
    if Q <= 0 or W <= 0:
        return {p: 0 for p in weight}
    got = {p: (Q * w) // W for p, w in weight.items()}
    rank = sorted(weight, key=lambda p: (-((Q * weight[p]) % W), p))
    for p in rank[:Q - sum(got.values())]:
        got[p] += 1
    return got


def hand_out(Q, weight, cap):
    held = proportional(Q, weight)
    while True:
        back = 0
        for p in held:
            if p in cap and held[p] > cap[p]:
                back += held[p] - cap[p]
                held[p] = cap[p]
        if back == 0:
            return held
        takers = {p: w for p, w in weight.items() if p not in cap or held[p] < cap[p]}
        if not takers or sum(takers.values()) <= 0:
            return held
        for p, extra in proportional(back, takers).items():
            held[p] += extra


cfg_settings = {pid: settings_of(pid) for pid in compiled}
weight = {pid: cfg_settings[pid]["weight"] for pid in active}
cap = {pid: cfg_settings[pid]["quota_cap"] for pid in active if "quota_cap" in cfg_settings[pid]}
cfg_quota = hand_out(quotas["shared"], weight, cap)

docs = {}
docs["config.json"] = {
    "release": manifest["release"], "compile_date": D, "cluster_quota": quotas["shared"],
    "products": {pid: {"status": status[pid], "owner": meta[pid]["owner"], "tier": meta[pid]["tier"],
                       "team": team[pid],
                       "settings": cfg_settings[pid] if status[pid] != "retired" else None,
                       "quota": cfg_quota.get(pid, 0)} for pid in catalog}}
totals = {"config": sum(cfg_quota.values())}
caps_seen = {"config": (cap, {p: cfg_quota[p] for p in cap})}
for env in ("dev", "prod"):
    es = {pid: settings_of(pid, env) for pid in active}
    ew = {pid: es[pid]["weight"] for pid in active}
    ec = {pid: es[pid]["quota_cap"] for pid in active if "quota_cap" in es[pid]}
    eq = hand_out(quotas[env], ew, ec)
    totals[env] = sum(eq.values())
    caps_seen[env] = (ec, {p: eq[p] for p in ec})
    docs["profile_%s.json" % env] = {
        "env": env, "release": manifest["release"], "compile_date": D, "cluster_quota": quotas[env],
        "products": {pid: {"alerts_enabled": es[pid]["alerts_enabled"], "pii_scan": es[pid]["pii_scan"],
                           "replicas": es[pid]["replicas"], "quota": eq[pid]} for pid in active}}
docs["validation_report.json"] = {"release": manifest["release"], "rejected_overrides": rejected}
counts = {"active": 0, "orphaned": 0, "retired": 0}
by_team = {}
for pid in catalog:
    counts[status[pid]] += 1
    if status[pid] == "active":
        by_team[team[pid]] = by_team.get(team[pid], 0) + 1
docs["summary.json"] = {
    "release": manifest["release"], "compile_date": D, "status_counts": counts, "active_by_team": by_team,
    "rejected_overrides": {"team_overrides": sum(1 for r in rejected if r["source"] == "team_overrides"),
                           "product_overrides": sum(1 for r in rejected if r["source"] == "product_overrides")},
    "quota_total": totals}

# ---------------------------------------------------------------- compare
failures = 0
for name in ("config.json", "profile_dev.json", "profile_prod.json", "validation_report.json", "summary.json"):
    want = docs[name]
    text = json.dumps(want, indent=2, sort_keys=True) + "\n"
    got = open(OUT + "/" + name, encoding="utf-8").read()
    same = got == text
    print("%-24s %s" % (name, "MATCH" if same else "DIFFERS"))
    if not same:
        failures += 1
        g = json.loads(got)
        for key in sorted(set(g) | set(want)):
            if g.get(key) == want.get(key):
                continue
            if key in ("products", "rejected_overrides") and isinstance(want[key], dict):
                bad = [p for p in set(g[key]) | set(want[key]) if g[key].get(p) != want[key].get(p)]
                print("   %s differ: %d ids" % (key, len(bad)))
                for p in sorted(bad)[:3]:
                    print("     ", p, "\n       tool:", g[key].get(p), "\n       mine:", want[key].get(p))
            else:
                print("   %s\n     tool: %r\n     mine: %r" % (key, g.get(key), want.get(key)))

want_report = {"tool": "dpcc",
               "documents": {n: hashlib.sha256(open(OUT + "/" + n, "rb").read()).hexdigest() for n in docs},
               "ok": True}
text = json.dumps(want_report, indent=2, sort_keys=True) + "\n"
got = open(OUT + "/report.json", encoding="utf-8").read()
print("%-24s %s" % ("report.json", "MATCH" if got == text else "DIFFERS"))
failures += got != text

print("\nfigures of record")
print("  status:", counts, "teams:", len(by_team))
print("  rejected:", docs["summary.json"]["rejected_overrides"], "total", len(rejected))
print("  quota totals:", totals, "of", quotas)
for where, (cp, held) in caps_seen.items():
    print("  caps %s: %s -> held %s" % (where, cp, held))
print("\nFAILURES: %d" % failures)
