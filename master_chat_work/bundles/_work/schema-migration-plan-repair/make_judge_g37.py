from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
PROBES = (
    (21, "missing_declared_file", "The agent runs the repaired package on a copy of a contract folder from which it removed one of the seven files rule K2 names and checks the exit status or error reported by that run."),
    (22, "empty_feed", "The agent runs the repaired package with a feed file holding no lines and checks the run summary it writes."),
    (23, "malformed_edge_cost", "The agent runs the repaired package on a copy of a contract folder in which it replaced one migration_edges.csv cost with non-integer text and checks the exit status or error reported by that run."),
    (24, "altered_field_policy", "The agent runs the repaired package on a copy of /app/ci in which it changed one field_policy.tsv row and compares one record of that row's domain with the run on /app/ci."),
    (25, "altered_explicit_null", "The agent runs the repaired package on a copy of /app/ci in which it changed the explicit_null line in the presence section of null_semantics.ini and compares one record holding an explicit null with the run on /app/ci."),
)


def main() -> None:
    old = (WORK / "before_g37/tests/judge.toml").read_text()
    header, *blocks = re.split(r"(?=\[\[criterion\]\])", old)
    kept = [b for b in blocks if tomllib.loads(b)["criterion"][0]["id"] not in {"R5", "R13"}]
    for number, name, description in PROBES:
        kept.append(
            f'[[criterion]]\nid = "R{number}"\nname = "r{number}_probes_{name}"\n'
            f'description = {json.dumps(description)}\ntype = "binary"\nweight = 3\n\n'
            '[criterion.annotations]\nmode = "judged"\ntype = "agent behavior"\n'
            'evaluation_target = "trajectory"\nimportance = "important"\n\n'
        )
    sequential = [re.sub(r'^id = "R\d+"', f'id = "R{index}"', block, count=1, flags=re.M) for index, block in enumerate(kept, 1)]
    text = header + "".join(sequential)
    criteria = tomllib.loads(text)["criterion"]
    assert len(criteria) == 23
    assert sum(c["weight"] for c in criteria if c["weight"] > 0) == 49
    (BUNDLE / "tests/judge.toml").write_text(text)
    print("23 criteria; positive 49; sequential IDs; logical names preserved")


if __name__ == "__main__":
    main()
