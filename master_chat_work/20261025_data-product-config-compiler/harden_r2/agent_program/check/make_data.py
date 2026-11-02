"""Build a small synthetic dpcc data folder that exercises the awkward corners.

Usage: python3 make_data.py <folder>
"""

import json
import os
import sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
D = "2030-06-15"


def put(name, text):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(text)


# hyphenated / lower-case ids in the manifest, plain ids in the ini: same canonical set
catalog = ["dp-1", "DP2", "dp3", "DP-4", "DP5", "DP6", "DP7", "DP8", "DP9", "DP10", "DP11", "dp-12"]
put("release_manifest.json", json.dumps({"release": "synth-1", "compile_date": D, "catalog": catalog}, indent=2))

put("schema_registry.json", json.dumps({"keys": {
    "weight": {"type": "integer", "min": 1, "max": 100},
    "retention_days": {"type": "integer", "min": 1, "max": 3650},
    "replicas": {"type": "integer", "min": 1, "max": 7},
    "partitions": {"type": "integer", "min": 1, "max": 256},
    "freshness_sla_min": {"type": "integer", "min": 5, "max": 1440},
    "pii_scan": {"type": "boolean"},
    "alerts_enabled": {"type": "boolean"},
    "encryption": {"type": "enum", "values": ["none", "kms", "hsm"]},
    "notify": {"type": "list"},
    "tags": {"type": "list"},
    "cost_center": {"type": "string", "optional": True},
    "quota_cap": {"type": "integer", "min": 1, "max": 100000, "optional": True},
}}, indent=2))

put("base_layer.yaml", """# base
weight: 1
retention_days: 30
replicas: 2
partitions: "8"
freshness_sla_min: 60
pii_scan: FALSE
alerts_enabled: true
encryption: none
notify: "ops, data-oncall"
tags:
""")

# DP1 w=1 cap=1 (ini), DP2 w=1 cap=2 (override), DP3 w=98 cap=3 -> several cap rounds
put("products.ini", """# synthetic catalog
[product DP1]
owner = o.open
tier = gold
labels = pii, finance
quota_cap = 1

[product DP2]
owner = o.open
tier = silver
labels =

[product DP3]
owner = o.multi
tier = bronze
labels = ml
weight = 98

[product DP4]
owner = o.expired
tier = gold
labels = archive
partitions = +16
alerts_enabled = on
retention_days = "45"

[product DP5]
owner = o.gone
tier = silver
labels = realtime

[product DP6]
owner = o.retired
tier = bronze
labels = batch

[product DP7]
owner = o.open
tier = gold
labels = shared
encryption = hsm

[product DP8]
owner = o.future
tier = silver
labels =

[product DP9]
owner = o.multi
tier = bronze
labels = pii
notify = ""

[product DP10]
owner = o.open
tier = silver
labels = ml, finance
pii_scan = 1

[product DP11]
owner = o.edge
tier = gold
labels =
cost_center = CC-9

[product DP12]
owner = o.open
tier = bronze
labels =
""")

# o.expired: latest assignment on D has run out although an earlier one is open
# o.edge: assignment whose active_to is exactly D -> still active
# o.future: every assignment starts after D
put("owners.csv", """owner,team,active_from,active_to
o.open,ingest,2020-01-01,
o.multi,search,2020-01-01,2025-01-01
o.multi,ops,2029-01-01,
o.expired,ingest,2019-01-01,
o.expired,media,2029-01-01,2030-01-01
o.gone,media,2020-01-01,2030-06-14
o.retired,ingest,2020-01-01,
o.future,ingest,2031-01-01,
o.edge,ops,2028-01-01,2030-06-15
""")

put("deprecation.log", """2030-01-01T00:00:00Z NOTICE owner=o.open note=hi ticket=T-1
2030-05-05T10:00:00Z RETIRE product=dp-6 ticket=T-2
2029-05-05T10:00:00Z RETIRE owner=o.retired ticket=T-3
2030-06-16T10:00:00Z RETIRE product=DP7 ticket=T-4
2031-01-01T00:00:00Z RETIRE owner=o.open ticket=T-5
2030-02-02T00:00:00Z INFO catalog=refreshed ticket=T-6
2030-03-03T00:00:00Z RETIRE product=DP-404 ticket=T-7
""")

put("selectors.rules", """# rules in file order
match label:pii set pii_scan TRUE
match tier:gold set replicas 3
match team:ingest set notify ops
match label:shared set notify ""
match tier:gold set replicas "+5"
match label:ml set tags ml, feature-store
match team:ops set weight 4
match label:finance set encryption hsm
match tier:bronze set freshness_sla_min oops
match label:archive set retention_days 1825
""")

put("team_overrides.json", json.dumps({
    "ingest": {"cost_center": "CC-1", "retention_days": 60, "weight": True},
    "ops": {"replicas": 9, "notify": [], "tags": ["a", 2], "cost_center": None},
    "nobody": {"retention_days": "90", "mystery": 1},
}, indent=2))

overrides = [
    {"seq": 50, "product": "DP2", "key": "quota_cap", "value": 2, "ticket": "T"},
    {"seq": 40, "product": "dp-3", "key": "quota_cap", "value": 3, "ticket": "T"},
    {"seq": 30, "product": "DP1", "key": "retention_days", "value": 7, "ticket": "T"},
    {"seq": 10, "product": "DP1", "key": "retention_days", "value": 9, "ticket": "T"},
    {"seq": 20, "product": "DP1", "key": "cost_center", "value": None, "ticket": "T"},
    {"seq": 60, "product": "DP6", "key": "replicas", "value": 2, "ticket": "T"},
    {"seq": 70, "product": "DP404", "key": "replicas", "value": 2, "ticket": "T"},
    {"seq": 80, "product": "DP5", "key": "replicas", "value": 2.0, "ticket": "T"},
    {"seq": 90, "product": "DP5", "key": "replicas", "value": 99, "ticket": "T"},
    {"seq": 100, "product": "DP5", "key": "encryption", "value": "aes", "ticket": "T"},
    {"seq": 110, "product": "DP5", "key": "pii_scan", "value": "true", "ticket": "T"},
    {"seq": 120, "product": "DP5", "key": "weight", "value": None, "ticket": "T"},
    {"seq": 130, "product": "DP5", "key": "sla", "value": 1, "ticket": "T"},
    {"seq": 140, "product": "DP5", "key": "notify", "value": ["a", None], "ticket": "T"},
    {"seq": 150, "product": "DP9", "key": "tags", "value": [], "ticket": "T"},
    {"seq": 160, "product": "DP11", "key": "cost_center", "value": None, "ticket": "T"},
    {"seq": 170, "product": "DP10", "key": "weight", "value": True, "ticket": "T"},
    {"seq": 180, "product": "DP12", "key": "freshness_sla_min", "value": 5, "ticket": "T"},
]
put("product_overrides.jsonl", "".join(json.dumps(o) + "\n" for o in overrides))

put("env_dev.toml", """# dev
[defaults]
replicas = 1
alerts_enabled = "false"
retention_days = +14

[tier.gold]
replicas = 2
weight = 3

[tier.bronze]
pii_scan = yes
""")

put("env_prod.toml", """[defaults]
replicas = "3"
pii_scan = TRUE

[tier.gold]
weight = "+6"
replicas = 5

[tier.silver]
alerts_enabled = False
""")

put("cluster_quota.json", json.dumps({"shared": 100, "dev": 7, "prod": 1}, indent=2))
print("wrote", OUT, "compile_date", D)
