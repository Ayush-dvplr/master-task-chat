"""Stats of far-reaching books (sites, cold rooms, links per project) from the embedded builder."""
import csv, json, sys, types, importlib.util
from collections import defaultdict
stub = types.ModuleType("rewardkit")
class C:
    def __getattr__(self, n): return lambda weight: None
stub.criteria = C(); stub.criterion = lambda description: (lambda f: f)
sys.modules["rewardkit"] = stub
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for name in t.WIDE_BOOKS + t.HELD_WIDE_BOOKS:
    b = t._book(name)
    sites = defaultdict(int); cold = defaultdict(int); links = defaultdict(int)
    for r in csv.DictReader(open(b / "sites.csv")):
        sites[r["project"]] += 1; cold[r["project"]] += r["role"] == "cold_room"
    for line in open(b / "links.jsonl"):
        links[json.loads(line)["project"]] += 1
    print(name, len(sites), "sites", min(sites.values()), max(sites.values()), "cold", min(cold.values()), max(cold.values()), "links", min(links.values()), max(links.values()))
