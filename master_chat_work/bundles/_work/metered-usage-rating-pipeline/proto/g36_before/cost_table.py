"""G10 / CL-4 cost table: inject each lever's wrong reading into a patched copy of solve.py and score with the real tests.

Usage: python3 -B cost_table.py   (writes cost_table.json next to this file)
"""
import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "metered-usage-rating-pipeline"
SOLVE = (BUNDLE / "solution" / "solve.py").read_text(encoding="utf-8")
TESTS = BUNDLE / "tests" / "test_output.py"
SCRATCH = Path("/tmp/mu-p2/cost")
RUNALL = "/tmp/mu-p2/rk/runall.py"

CREDIT_CALL = """            share_with_floor(pool, counted[region], base[region], "credit")"""
TRUE_UP_CALL = """            share_with_floor(minimum - base[region], counted[region], base[region], "true_up")"""
CHAIN = """        for acct in parent:
            chain = []
            node = acct
            while node not in self.group and parent[node]:
                chain.append(node)
                node = parent[node]
            top = self.group.get(node, node)
            self.group[node] = top
            for member in chain:
                self.group[member] = top"""

FULL = {
    # H7 (A): the second pass re-enters the at-or-below branch (held lines get their own charge)
    "LV-MU-6": [(CREDIT_CALL, CREDIT_CALL + """
            held = [ln for ln in counted[region] if ln["credit"] > ZERO]
            if sum((ln["charge"] for ln in held), ZERO) <= pool:
                for ln in held:
                    ln["credit"] = ln["charge"]""")],
    # H6 (B): billing group read one level up the parent column
    "LV-MU-5": [(CHAIN, """        for acct in parent:
            self.group[acct] = parent[acct] or acct""")],
    # P-3 (wave 2): billing group found by walking the parent column again for every account
    "LV-MU-8": [(CHAIN, """        for acct in parent:
            top = acct
            while parent[top]:
                top = parent[top]
            self.group[acct] = top""")],
    # H7 (C): the second pass recomputes the shortfall from the lines still standing
    "LV-MU-7": [(TRUE_UP_CALL, TRUE_UP_CALL + """
            held = [ln for ln in counted[region] if ln["true_up"] > ZERO]
            kept = sum((ln["charge"] for ln in held), ZERO)
            for ln in held:
                ln["true_up"] = to_cents((minimum - kept) * ln["charge"] / kept)""")],
    # r1 levers kept as noise rows
    "LV-MU-1": [("""def json_units(raw):
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None""", """def json_units(raw):
    if isinstance(raw, bool):
        return None
    return text_units(str(raw))""")],
    "LV-MU-3": [("""        if ln["account_id"] in month.committed:
            counted[ln["region"]].append(ln)""", """        if ln["plan"] == "committed":
            counted[ln["region"]].append(ln)""")],
}

ONE = {
    # one line of one region takes its own charge in the second pass
    "LV-MU-6": [(CREDIT_CALL, CREDIT_CALL + """
            held = [ln for ln in counted[region] if ln["credit"] > ZERO]
            moved = [ln for ln in held if ln["credit"] != ln["charge"]]
            if sum((ln["charge"] for ln in held), ZERO) <= pool and moved and not getattr(month, "slip", False):
                month.slip = True
                moved[0]["credit"] = moved[0]["charge"]""")],
    # one account two or more levels down takes its parent as its billing group
    "LV-MU-5": [(CHAIN, CHAIN + """
        for acct in parent:
            if parent[acct] and parent[parent[acct]]:
                self.group[acct] = parent[acct]
                break""")],
    # one line of one region takes its share of the recomputed shortfall
    "LV-MU-7": [(TRUE_UP_CALL, TRUE_UP_CALL + """
            held = [ln for ln in counted[region] if ln["true_up"] > ZERO]
            kept = sum((ln["charge"] for ln in held), ZERO)
            moved = [ln for ln in held if ln["true_up"] != to_cents((minimum - kept) * ln["charge"] / kept)]
            if moved and not getattr(month, "slip", False):
                month.slip = True
                moved[0]["true_up"] = to_cents((minimum - kept) * moved[0]["charge"] / kept)""")],
}

LEVERS = ["LV-MU-6", "LV-MU-5", "LV-MU-7", "LV-MU-8"]
NOISE = ["LV-MU-1", "LV-MU-3"]


def patch(text, edits):
    for old, new in edits:
        assert text.count(old) == 1, old[:60]
        text = text.replace(old, new)
    return text


def score(label, source):
    app = SCRATCH / label
    if app.exists():
        shutil.rmtree(app)
    (app / "out").mkdir(parents=True)
    shutil.copytree(BUNDLE / "environment" / "data", app / "data")
    (app / "out" / "transform.py").write_text(source, encoding="utf-8")
    subprocess.run([sys.executable, "-B", str(app / "out" / "transform.py"), "--input", str(app / "data"),
                    "--output", str(app / "out")], check=True)
    proc = subprocess.run([sys.executable, "-B", RUNALL, str(TESTS)], capture_output=True, text=True,
                          env={"APP_ROOT": str(app), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"},
                          cwd="/tmp", check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main():
    if sys.argv[1:2] == ["one"]:
        print(score("one-" + sys.argv[2], patch(SOLVE, ONE[sys.argv[2]])))
        return
    rows = {}
    rows["oracle"] = score("oracle", SOLVE)
    for lever in LEVERS:
        rows["alone " + lever] = score("alone-" + lever, patch(SOLVE, FULL[lever]))
        rows["one-fact " + lever] = score("one-" + lever, patch(SOLVE, ONE[lever]))
        others = [e for k in LEVERS if k != lever for e in FULL[k]]
        rows["all-but " + lever] = score("allbut-" + lever, patch(SOLVE, others))
    rows["all wrong"] = score("allwrong", patch(SOLVE, [e for k in LEVERS for e in FULL[k]]))
    for lever in NOISE:
        rows["noise alone " + lever] = score("noise-" + lever, patch(SOLVE, FULL[lever]))
    for k, v in rows.items():
        print("%-20s lost %5.1f%%  failed %d" % (k, 100 - v["pct"], len(v["failed"])))
    (WORK / "cost_table.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
