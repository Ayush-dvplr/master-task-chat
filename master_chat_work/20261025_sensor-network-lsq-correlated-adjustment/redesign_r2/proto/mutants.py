"""G11 rule coverage: drop one contract rule at a time from solution/solve.py
and score the mutant with the REAL tests (score.py).

usage: python3 mutants.py OUT_JSON
"""
import json
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).parent
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/"
              "sensor-network-lsq-correlated-adjustment")
SRC = (BUNDLE / "solution" / "solve.py").read_text()

# (rule, schema section, old text, new text)
MUTANTS = [
    ("abandoned registry rows not used", "1",
     'if row["mark_status"] != "active" or int(row["ordinal"]) in found:',
     'if int(row["ordinal"]) in found and row["mark_status"] != "abandoned":'),
    ("set_out_from centring variance (recursive)", "1",
     "            value += setup_variance(marks[parent], trail | {parent})",
     "            value += own_centring(marks[parent])"),
    ("higher revision record kept", "2",
     "if ident not in chosen or revision > chosen[ident][0]:",
     "if ident not in chosen:"),
    ("district = district of the kept shard", "2",
     "        obs.region = DISTRICT_OF_SHARD[shard]",
     '        obs.region = rec["region"].strip()'),
    ("authoritative unit registry rows only", "3",
     'if row["status"] != "authoritative":\n            continue',
     "if False:\n            continue"),
    ("sigma_kind stddev versus variance", "4",
     'if rec["sigma_kind"] == "stddev" else',
     'if rec["sigma_kind"] != "stddev" else'),
    ("tripod centring only", "1/4",
     'return sigma * sigma if row["mount"] == "tripod" else Fraction(0)',
     "return sigma * sigma"),
    ("dir=R negates observed and computed", "5",
     'if rec["dir"].strip() == "R":', "if False:"),
    ("azimuth_wrap reduction to [0,400)", "6",
     '    if angle and is_true(decl.get("azimuth_wrap")):\n        observed %= 400\n        nominal %= 400\n    misclosure = observed - nominal\n    if angle:',
     '    misclosure = observed - nominal\n    if angle and not is_true(decl.get("azimuth_wrap")):'),
    ("epoch-2 id transposition", "7",
     "            ident = ident[-3:] + ident[:-3]", "            ident = ident"),
    ("angle misclosure into (-200,200]", "8",
     "        misclosure %= 400\n        if misclosure > 200:\n            misclosure -= 400",
     "        pass"),
    ("closure fits branch", "8b",
     "    if sum(b for _, b in legs) <= total:\n        return {ident: b for ident, b in legs}\n",
     ""),
    ("closure remainder tie to lower obs_id", "8b",
     "key=lambda i: (-(quotas[i] - shares[i]), i))",
     "key=lambda i: (-(quotas[i] - shares[i]), tuple(-ord(c) for c in i)))"),
    ("closure floor drop", "8b",
     "if first[ident] >= floor]", "if first[ident] >= 0]"),
    ("closure second pass shares every micrometre", "8b",
     "        shares.update(largest_remainder(total, held))",
     "        shares.update(closure_shares(total, held, floor))"),
    ("closure sign", "8b",
     "        sign = 1 if closure > 0 else -1", "        sign = 1"),
    ("u from the workbook", "9",
     'dof = len(kept) - control["u"]', "dof = len(kept) - 3"),
    ("IRLS pass count from iteration_policy", "11",
     "for _ in range(self.passes):", "for _ in range(1):"),
    ("downweighted weight quantized", "11",
     "round_places(p * self.k_squared / test, self.places)",
     "p * self.k_squared / test"),
    ("session members never downweighted", "11",
     "if idx not in self.in_block and test > self.k_squared:",
     "if test > self.k_squared:"),
    ("tuning_k from the workbook", "11",
     '"k": Fraction(values["tuning_k"]),', '"k": Fraction(3),'),
    ("session block cross term", "11b",
     "round_places(-cov / det, places)", "Fraction(0)"),
    ("decoy session rows ignored", "11b",
     '            if row["status"] == "authoritative"]', "            ]"),
    ("blunder test against blunder_crit squared", "12",
     "> crit_squared)", '> control["crit"])'),
    ("datum origin shift", "13",
     "shifted = [free[i] - shift[i % 2] for i in range(UNKNOWN_COUNT)]",
     "shifted = list(free)"),
    ("datum origin from the workbook", "13",
     '"origin": int(values["datum_origin_station"])', '"origin": 2'),
    ("acceptance row centre +- 1/2", "14",
     "return centre - Fraction(1, 2), centre + Fraction(1, 2)",
     "return centre - 1, centre + 1"),
    ("half-even micrometres", "16",
     "    return round(value * 1_000_000)", "    return int(value * 1_000_000)"),
    ("first occurrence per key in maps", "16",
     "mapping.setdefault(cast(row[key]), row[value])",
     "mapping[cast(row[key])] = row[value]"),
    ("max residual tie lowest obs_id", "16",
     "min(o.ident for o, r in zip(obs, v) if abs(r) == largest)",
     "max(o.ident for o, r in zip(obs, v) if abs(r) == largest)"),
    ("superseded_records order", "16",
     'superseded.sort(key=lambda d: (d["obs_id"], d["superseded_shard"]))',
     'superseded.sort(key=lambda d: (d["obs_id"], d["superseded_shard"]), reverse=True)'),
    ("sorted JSON keys", "16", "indent=2, sort_keys=True)", "indent=2)"),
    ("decoys_ignored names shipped decoy files", "16",
     '    "stale_cached_solution.json",\n', '    "made_up_source.csv",\n'),
]


def run(item):
    idx, (rule, sec, old, new) = item
    assert SRC.count(old) >= 1, rule
    folder = Path(tempfile.mkdtemp(prefix="snlsq-mut-"))
    prog = folder / f"mutant_{idx:02d}.py"
    prog.write_text(SRC.replace(old, new))
    p = subprocess.run([sys.executable, str(HERE / "score.py"), str(prog)],
                       capture_output=True, text=True,
                       env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    failed = [ln.split()[2] for ln in p.stdout.splitlines()
              if ln.startswith("fail +")]
    score = re.search(r"SCORE (\S+)", p.stdout)
    return {"rule": rule, "section": sec, "mutant": f"{old.strip()[:60]} -> {new.strip()[:40]}",
            "failed": failed, "score": score.group(1) if score else p.stderr[-300:]}


def main():
    pick = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 else range(len(MUTANTS))
    with Pool(6) as pool:
        res = pool.map(run, [(i, MUTANTS[i]) for i in pick])
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
    for r in res:
        print(f"{len(r['failed']):3d} {r['score']:>8} s{r['section']:5} {r['rule']}")


if __name__ == "__main__":
    main()
