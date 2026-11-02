"""Build kill-table program variants under <work>/h2_a3/variants.

Usage: python3 -B variants.py <work_dir>
a3 plus each crosswalk place, a3 plus all three (careful enumerator), and
oracle_fixed less each new crosswalk repair (all-but-one).
"""
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
import oracle_repairs as O  # noqa: E402

A3_EDITS = {
    "groups": [
        ("src/slwopt/cells.py",
         "        self.groups, group_rejected = graph.groups(root, self.jobs)\n",
         "        self.groups, group_rejected = graph.groups(root, self.jobs, alias)\n"),
        ("src/slwopt/graph.py",
         "def groups(root, jobs):\n",
         "def groups(root, jobs, alias):\n"),
        ("src/slwopt/graph.py",
         "    rows = [row for row in reading.delimited(root / \"exclusive_slot_groups.csv\")\n"
         "            if row[\"state\"] == \"open\" and row[\"member_job\"] in jobs]\n",
         "    rows = []\n"
         "    for row in reading.delimited(root / \"exclusive_slot_groups.csv\"):\n"
         "        row = dict(row)\n"
         "        row[\"member_job\"] = alias.get(row[\"member_job\"], row[\"member_job\"])\n"
         "        if row[\"state\"] == \"open\" and row[\"member_job\"] in jobs:\n"
         "            rows.append(row)\n"),
    ],
    "rules": [
        ("src/slwopt/cells.py",
         "            if record.get(\"state\") == \"in_force\":\n"
         "                self.rules[record[\"rule_id\"]] = dict(record)\n",
         "            if record.get(\"state\") == \"in_force\":\n"
         "                record = dict(record)\n"
         "                for field in (\"first_job\", \"second_job\", \"anchor_job\"):\n"
         "                    if record.get(field):\n"
         "                        record[field] = alias.get(record[field], record[field])\n"
         "                self.rules[record[\"rule_id\"]] = record\n"),
    ],
    "amendments": [
        ("src/slwopt/mutate.py",
         "    out = []\n"
         "    for record in sorted(rows, key=lambda r: int(r[\"sequence\"])):\n",
         "    alias = normalise.crosswalk(root)[0]\n"
         "    out = []\n"
         "    for record in sorted(rows, key=lambda r: int(r[\"sequence\"])):\n"),
        ("src/slwopt/mutate.py",
         "            payload[field] = value\n"
         "        out.append(",
         "            payload[field] = value\n"
         "        for field in (\"job_id\", \"requiring_job\", \"required_job\",\n"
         "                      \"member_job\"):\n"
         "            if field in payload:\n"
         "                payload[field] = alias.get(payload[field], payload[field])\n"
         "        out.append("),
    ],
}
ORACLE_DROPS = {"groups": ("DFC-17", "DFC-18"), "rules": ("DFC-19",),
                "amendments": ("DFC-20", "DFC-21")}


def edit(root, relative, old, new):
    path = root / relative
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(str(root) + " " + relative + " anchor matches "
                         + str(text.count(old)))
    path.write_text(text.replace(old, new), encoding="utf-8")


def main():
    work = Path(sys.argv[1])
    dest = work / "h2_a3" / "variants"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    plans = {"a3_groups": ["groups"], "a3_rules": ["rules"],
             "a3_amendments": ["amendments"],
             "a3_careful": ["groups", "rules", "amendments"]}
    for name, places in plans.items():
        root = dest / name
        shutil.copytree(work / "a3_program", root)
        for place in places:
            for relative, old, new in A3_EDITS[place]:
                edit(root, relative, old, new)
    for place, codes in ORACLE_DROPS.items():
        root = dest / ("oracle_less_" + place)
        shutil.copytree(work / "oracle_program", root)
        for code, relative, old, new in O.REPAIRS:
            if code not in codes:
                edit(root, relative, old, new)
    print("built", sorted(p.name for p in dest.iterdir()))


if __name__ == "__main__":
    main()
