#!/bin/bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1

mkdir -p /app/out

# The candidate space of every withheld quantity is enumerated into the record
# before a single line of the reusable program is put in place.
python3 - <<'PY'
import glob
import json
import os

slice_text = ""
for name in sorted(glob.glob(os.path.join("/app/data", "*.md"))):
    with open(name, encoding="utf-8") as handle:
        body = handle.read()
    if "| control | published figure |" in body:
        slice_text = body
        break

quantities = []
table = []
for line in slice_text.splitlines():
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) == 4 and cells[0].startswith("`") and " through " in cells[1]:
        low, _, high = cells[1].partition(" through ")
        quantities.append({"name": cells[0].strip("`"), "value": 0,
                           "control": cells[2],
                           "rejected": [{"candidate": step, "falsifier": ""}
                                        for step in range(int(low), int(high) + 1)]})
    if len(cells) == 2 and cells[0].startswith("CTRL-"):
        table.append({"control": cells[0], "published": cells[1].strip("`"),
                      "produced": ""})

with open("/app/out/bottleneck_analysis.json", "w", encoding="utf-8") as handle:
    handle.write(json.dumps({"quantities": quantities, "settling_passes": 0,
                             "calibration_table": table},
                            indent=2, sort_keys=False) + "\n")
PY

cp /solution/solve.py /app/out/optimize.py
chmod 0644 /app/out/optimize.py

python3 /app/out/optimize.py /app/data /app/out

# Every settlement report and the record are cleared once the last withheld
# quantity has settled, then rebuilt in one clean run; the program stays put.
rm -f /app/out/scenario_visible.json
rm -f /app/out/scenario_peak.json
rm -f /app/out/scenario_steady.json
rm -f /app/out/scenario_burst.json
rm -f /app/out/scenario_latency.json
rm -f /app/out/perf_report.json
rm -f /app/out/recommendations.json
rm -f /app/out/data_quality.json
rm -f /app/out/bottleneck_analysis.json

python3 /app/out/optimize.py /app/data /app/out

# Self check: three small capture sets built under /app/out/selfcheck put the
# delivered program through the allowance cap (R7), the renewal at a live
# window's first tick (R8) and a reversal that cancels a draw (R9). Each check
# compares a settled amount with the value worked out by hand and prints one
# line; the folder is removed afterwards, so the graded reports are untouched.
python3 - <<'PY'
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

KEY = b"MRD-2031"
WORDS = ("aurochs", "basilisk", "cockatrice", "dryad", "ettin", "fenrir", "golem",
         "hydra", "ifrit", "jotun", "kelpie", "lamia", "manticore", "nixie", "ogre",
         "pegasus", "quasit", "roc", "sylph", "troll", "undine", "vodyanoi", "wyvern",
         "xorn")
CLASSES = ("peak", "steady", "burst", "latency")
VALUES = [("frame_bias_limit", 4, "CTRL-A"), ("weave_seed_offset", 17, "CTRL-B"),
          ("sentinel_code_value", 200, "CTRL-C"), ("drift_modulus", 5, "CTRL-D"),
          ("seal_label_index", 0, "CTRL-E"), ("spin_modulus", 7, "CTRL-F"),
          ("shadow_pad_base", 3, "CTRL-G"), ("alias_donor_shift", 1, "CTRL-H"),
          ("echo_window_span", 2, "CTRL-I"), ("cadence_modulus", 7, "CTRL-J"),
          ("upkeep_target_scale", 11, "CTRL-K")]
# One allowance of 100 for azure (baseline 100, one unit) and a large one for crimson.
ROSTER = "word,charter,opened,closed,successor\naurochs,azure,100,,\nbasilisk,crimson,5000,,\n"
SCHEDULE = "window,first_tick,last_tick,live\nW1,1,100,1\nW2,101,200,1\n"
TARGET = 11 * 5100


def digest(label, *numbers):
    body = KEY + label.encode("ascii") + b"".join(b":" + str(n).encode("ascii") for n in numbers)
    return hashlib.sha256(body).digest()


def stamp(fragments):
    return hashlib.sha256(KEY + b"".join(b"|" + part.encode("utf-8") for part in fragments)).hexdigest()[:12]


def payload(tick, word, kind, amount, mark):
    body = (tick.to_bytes(2, "big") + WORDS.index(word).to_bytes(2, "big") + bytes([kind])
            + amount.to_bytes(4, "big") + bytes([mark]))
    return body + digest("entry", *body)[:2]


def build(folder, entries, settled_ticks):
    """Write one plain capture and its notes; settled_ticks holds each surviving unit's tick total."""
    folder.mkdir(parents=True)
    lines = [payload(*entry) for entry in entries]
    header = ("#RPL1 capture=selfcheck number=0 flags=0x0000 blocks=1 frames=%d words=%s seal=%s"
              % (len(lines), ",".join(WORDS), digest("seal", 0, len(lines))[:4].hex()))
    text = [header, "B 0 %d %s" % (len(lines), digest("block", 0, 0, len(lines))[:2].hex())]
    text += ["R " + line.hex() for line in lines]
    (folder / "selfcheck.rpl").write_text("\n".join(text) + "\n", encoding="utf-8")
    (folder / "roster.csv").write_text(ROSTER, encoding="utf-8")
    (folder / "schedule.csv").write_text(SCHEDULE, encoding="utf-8")
    (folder / "bench.csv").write_text("word,upkeep\nbench-01,%d\nbench-02,7\n" % TARGET,
                                      encoding="utf-8")
    flat = "0:" + ",".join(line.hex() for line in lines)
    raw = ["%d/%d/%d/%d/%d" % (t, WORDS.index(w), k, a, m) for t, w, k, a, m in entries]
    named = "0:" + ",".join("%d/%s/%d/%d/%d" % entry for entry in entries)
    figures = ["0:0", flat, flat, flat, "0:" + lines[0].hex(), "0:" + raw[0],
               "0:" + ",".join(raw), named, named]
    figures = [stamp([part]) for part in figures]
    figures.append(stamp(["%s:%s" % (word, CLASSES[total // 7 % 4])
                          for word, total in sorted(settled_ticks.items())]))
    figures.append(stamp(["%d/1" % TARGET]))
    rows = ["| quantity | candidate values | control | the control reads |", "| --- | --- | --- | --- |"]
    rows += ["| `%s` | %d through %d | %s | self check |" % (name, value, value, control)
             for name, value, control in VALUES]
    rows += ["", "| control | published figure |", "| --- | --- |"]
    rows += ["| %s | `%s` |" % (control, figure) for (_, _, control), figure in zip(VALUES, figures)]
    (folder / "calibration.md").write_text("# Self check slice\n\n" + "\n".join(rows) + "\n",
                                           encoding="utf-8")


def run(case, entries, settled_ticks):
    data, out = Path("/app/out/selfcheck") / case / "data", Path("/app/out/selfcheck") / case / "out"
    build(data, entries, settled_ticks)
    subprocess.run([sys.executable, "/app/out/optimize.py", str(data), str(out)], check=True,
                   capture_output=True)
    reports = {name: json.loads((out / name).read_text(encoding="utf-8"))
               for name in ("scenario_visible.json", "perf_report.json", "bottleneck_analysis.json")}
    for row in reports["bottleneck_analysis.json"]["calibration_table"]:
        if row["produced"] != row["published"]:
            raise SystemExit("check %s failed: %s produced %s" % (case, row["control"], row["produced"]))
    return reports


def expect(case, seen, wanted):
    if seen != wanted:
        raise SystemExit("check %s failed: got %s, expected %s" % (case, seen, wanted))
    print("check %s ok" % case)


def amount_of(reports, unit):
    return [seat["amount_total"] for seat in reports["scenario_visible.json"]["units"]
            if seat["unit"] == unit]


shutil.rmtree("/app/out/selfcheck", ignore_errors=True)
try:
    # R7: two settled azure entries in W1 ask for 70 and 50 of an allowance of 100,
    # so the later one settles 30 and aurochs totals 100.
    seen = run("R7", [(10, "aurochs", 0, 70, 0), (20, "aurochs", 0, 50, 0),
                      (30, "basilisk", 0, 40, 0)], {"aurochs": 30, "basilisk": 30})
    expect("R7", amount_of(seen, "aurochs"), ["100/1"])
    # R8: W1 spends the whole allowance (90, then 10 of 60); the entry at tick 101,
    # the first tick of W2, draws on a renewed allowance and settles all 80.
    seen = run("R8", [(10, "aurochs", 0, 90, 0), (50, "aurochs", 0, 60, 0),
                      (101, "aurochs", 0, 80, 0)], {"aurochs": 161})
    expect("R8", amount_of(seen, "aurochs"), ["180/1"])
    # R9: the reversal at tick 20 cancels the 80 at tick 10 before anything draws,
    # so the 60 at tick 30 settles whole and the settled total is 60.
    seen = run("R9", [(10, "aurochs", 0, 80, 0), (20, "aurochs", 3, 5, 0),
                      (30, "aurochs", 0, 60, 0)], {"aurochs": 30})
    expect("R9", seen["perf_report.json"]["settled_total"], "60/1")
finally:
    shutil.rmtree("/app/out/selfcheck", ignore_errors=True)
PY
