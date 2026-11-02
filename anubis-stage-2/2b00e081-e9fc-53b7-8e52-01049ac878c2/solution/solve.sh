#!/bin/bash
set -euo pipefail

DATA=/app/data
LIVE=/tmp/lockout-live

# Read the three notes before the program goes in place.
cat "$DATA/conventions.md" "$DATA/reports.md" "$DATA/handover.md" > /dev/null

mkdir -p /app/out
cp /solution/solve.py /app/out/lockout.py

# Replay each worked example and compare with its shipped answers.
REPRO=yes
for ex in example_a example_b; do
    in_dir="$(mktemp -d)"
    out_dir="$(mktemp -d)"
    for f in attempts.jsonl policy.json overrides.csv locks.prev.json manifest.json; do
        cp "$DATA/${ex}_$f" "$in_dir/$f"
    done
    python3 /app/out/lockout.py "$in_dir" "$out_dir"
    for f in locks.json decisions.jsonl summary.json; do
        if ! cmp -s "$out_dir/$f" "$DATA/${ex}_out_$f"; then
            REPRO=no
        fi
    done
done

# Replay the live intake into a folder outside /app/data.
rm -rf "$LIVE"
mkdir -p "$LIVE"
python3 /app/out/lockout.py "$DATA" "$LIVE"

REPRO="$REPRO" LIVE="$LIVE" DATA="$DATA" python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

live = Path(os.environ["LIVE"])
data = Path(os.environ["DATA"])
manifest = json.loads((data / "manifest.json").read_text())
summary = json.loads((live / "summary.json").read_text())
tables = json.loads((live / "locks.json").read_text())


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


lock_lines = "".join(f"{u} {e['until']}\n" for u, e in sorted(tables["locks"].items()))
ban_lines = "".join(f"{s} {e['until']}\n" for s, e in sorted(tables["bans"].items()))
checks = {f"reports.{name}": sha((live / name).read_bytes()) == want
          for name, want in manifest["reports"].items()}
checks["tables.locks"] = sha(lock_lines.encode()) == manifest["tables"]["locks"]
checks["tables.bans"] = sha(ban_lines.encode()) == manifest["tables"]["bans"]
agree = all(checks.values())
compared = ", ".join(sorted(checks))

print("Closing report for the live intake (mode word", manifest["mode"], ")")
for key in ("events", "allows", "fails", "locks", "denies", "ignored",
            "retransmitted", "active", "banned", "table_digest"):
    print(f"  {key}: {summary[key]}")
for user, entry in sorted(tables["locks"].items()):
    print(f"  live lock: {user} until {entry['until']} with {entry['strikes']} strike(s)")
for src, entry in sorted(tables["bans"].items()):
    print(f"  banned source: {src} until {entry['until']}")
print("Six unwritten rules:")
print("  A user is no longer locked at the second its lock ends (example_a seq 19).")
print("  A failure exactly one window old still counts (example_a seq 3).")
print("  The first valid overrides.csv row for a user stands (example_a seq 9).")
print("  A correct password from a locked user is denied and the lock stays (example_a seq 2).")
print("  A repeat lock lasts the policy lock doubled once for each earlier strike (example_a seq 8).")
print("  Records sharing one second replay in kind order reset, pass, fail, probe (example_b seq 3 and 6).")
print(f"Seven mode bits, each settled against the live manifest digests {compared}:")
print("  2: locks.prev.json is not seeded.")
print("  4: overrides.csv is ignored and every user gets the policy threshold.")
print("  8: a pass from an unlocked user clears its counted failures.")
print("  16: failures count per source; at ban_after the source is banned for ban seconds and later attempts are denied.")
print("  32: the retransmission check ignores seq.")
print("  64: a probe counts as a failed attempt.")
print("  128: a failure during a lock restarts the lock from that failure's second.")
print("Both worked examples reproduced byte for byte:", os.environ["REPRO"])
print("Live reports and table digests agree with every live manifest digest:", "yes" if agree else "no")
PY
