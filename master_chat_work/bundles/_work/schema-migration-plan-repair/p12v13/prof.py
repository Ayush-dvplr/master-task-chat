"""prof.py REPO GRAPH: cProfile one plan_migration call, top 25 by cumulative time."""
import cProfile, json, pstats, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "src"))
from migrakit.core.planner import plan_migration
from migrakit.parser.contracts import load_contracts
case = json.loads((Path(sys.argv[2]) / "case.json").read_text())
reg = load_contracts(sys.argv[2])
cProfile.run("plan_migration(reg, case['start'], case['payload'])", "/tmp/p.out")
pstats.Stats("/tmp/p.out").sort_stats("cumulative").print_stats(25)
