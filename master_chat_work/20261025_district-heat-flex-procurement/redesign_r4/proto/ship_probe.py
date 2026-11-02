"""W5 probe on the shipped data: add candidate [grants] keys and depth-1 draws_from rows to a scratch copy and
check that no wrong reading of M1/M2/M3 separates from the reference there, and what the saved agent program
loses on the visible family tests.

usage: python3 -B ship_probe.py CLAIM MINIMUM N_PAIRS
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fuzz  # noqa: E402

DATA = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement/environment/data")


def build(dst: Path, claim: int, minimum: int, n_pairs: int) -> None:
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(DATA, dst)
    ini = dst / "program.ini"
    ini.write_text(ini.read_text() + f"\n[grants]\nclaim_cents_per_weight = {claim}\nminimum_grant_cents = {minimum}\n")
    path = dst / "site_allowances.tsv"
    lines = path.read_text().splitlines()
    head = [x for x in lines if x.startswith("#")]
    body = [x.split("\t") for x in lines if x and not x.startswith("#")]
    rows = body[1:]
    region = {}
    with open(dst / "sites.csv") as fh:
        for r in csv.DictReader(fh):
            region.setdefault(r["site_id"], r["region_code"][:1])
    by_r: dict[str, list[list[str]]] = {}
    for r in rows:
        by_r.setdefault(region.get(r[0], "?"), []).append(r)
    draws = {}
    for code, group in sorted(by_r.items()):
        group = sorted(group)[: 2 * (n_pairs // 4)]
        for holder, follower in zip(group[0::2], group[1::2]):
            draws[follower[0]] = holder[0]
            holder[1] = str((int(holder[1]) + int(follower[1])) * 6 // 10)
            follower[1] = "0"
    out = head + ["site_id\tallowance_ticks\tdraws_from"] + [f"{r[0]}\t{r[1]}\t{draws.get(r[0], '')}" for r in rows]
    path.write_text("\n".join(out) + "\n")


def main() -> None:
    claim, minimum, n_pairs = map(int, sys.argv[1:4])
    dst = Path("/tmp/dhfp-r4-ship")
    build(dst, claim, minimum, n_pairs)
    ref = fuzz.oracle(dst, "ref")
    print("ref quality", {k: ref["data_quality.json"][k] for k in ("allowance_blocked_offer_count", "unallocated_pool_count")})
    for v in ("w_REENTRY", "w_DROPLEFT", "w_NODROP", "w_CHAIN1", "w_CHAIN0", "w_RELIEF", "nocarry", "ab_M1"):
        got = fuzz.oracle(dst, v)
        bad = fuzz.failing("H1", got, ref) | fuzz.failing("H2", got, ref)
        print(f"{v:12s} visible families differing: {sorted(bad)}")
    got = fuzz.agent("blind", dst, Path("/tmp/dhfp-r4-ship-out"))
    bad = fuzz.failing("H1", got, ref) | fuzz.failing("H2", got, ref)
    print(f"blind        visible families differing ({len(bad)}): {sorted(bad)}")


if __name__ == "__main__":
    main()
