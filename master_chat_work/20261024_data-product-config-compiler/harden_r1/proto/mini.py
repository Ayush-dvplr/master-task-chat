"""Shrunk four-product corpus: one planted case per new lever, oracle prototype vs probe agent program."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from proto_ref import ref_compute_p  # noqa: E402
from run_proto import agent_run  # noqa: E402

DATA = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/data-product-config-compiler/environment/data"
files = {n: open(os.path.join(DATA, n), "rb").read() for n in
         ("base_layer.yaml", "env_dev.toml", "env_prod.toml")}
schema = json.load(open(os.path.join(DATA, "schema_registry.json")))
schema["keys"]["quota_cap"] = {"type": "integer", "min": 1, "max": 100000, "optional": True}
files["schema_registry.json"] = json.dumps(schema).encode()
files["release_manifest.json"] = json.dumps({"release": "t-1", "compile_date": "2028-03-10",
                                             "catalog": ["DP1", "DP2", "DP3", "DP4"], "change_budget": 1}).encode()
files["products.ini"] = b"".join(b"[product DP%d]\nowner = %s\ntier = gold\nlabels =\n" % (i, o)
                                 for i, o in ((1, b"a"), (2, b"b"), (3, b"c"), (4, b"d")))
files["owners.csv"] = (b"owner,team,active_from,active_to\na,ingest,2020-01-01,\na,growth,2025-01-01,\n"
                       b"b,risk,2020-01-01,\nb,search,2026-01-01,2026-06-30\nc,risk,2021-01-01,\nd,risk,2021-01-01,\n")
files["deprecation.log"] = b"# none\n"
files["selectors.rules"] = b"# none\n"
files["team_overrides.json"] = b"{}\n"
files["product_overrides.jsonl"] = b"".join(json.dumps(o).encode() + b"\n" for o in (
    {"seq": 1, "product": "DP3", "key": "retention_days", "value": 30},
    {"seq": 2, "product": "DP4", "key": "retention_days", "value": 40},
    {"seq": 3, "product": "DP2", "key": "retention_days", "value": 50},
    {"seq": 4, "product": "DP1", "key": "quota_cap", "value": 10}))
files["cluster_quota.json"] = json.dumps({"shared": 101, "dev": 50, "prod": 80}).encode()


def view(out):
    P = out["config.json"]["products"]
    return {p: (v["status"], v["team"], v["settings"] and v["settings"].get("retention_days"), v["quota"])
            for p, v in P.items()}, [r["reason"] for r in out["validation_report.json"]["rejected_overrides"]]


print("oracle   ", view(ref_compute_p(files)))
print("restart  ", view(ref_compute_p(files, cap="restart")))
print("nullgroup", view(ref_compute_p(files, budget="nullgroup")))
print("probe    ", view(agent_run(files, None)))
