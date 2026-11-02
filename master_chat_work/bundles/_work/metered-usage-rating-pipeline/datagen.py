"""Seeded stdlib generator for the shipped month of metered-usage-rating-pipeline.

Writes BUNDLE/environment/data/ from gen_core.gen_month (seed 461927, month 2026-09)
plus rating_contract.md, removes every other file there, and checks volume.
"""
import os
import pathlib
import sys

WORK = pathlib.Path(__file__).resolve().parent
BUNDLE = pathlib.Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/metered-usage-rating-pipeline")
DATA = BUNDLE / "environment" / "data"
SEED = 461927
MONTH = "2026-09"

sys.dont_write_bytecode = True
sys.path.insert(0, str(WORK))
from ref_core import ref_compute  # noqa: E402
from gen_core import gen_month  # noqa: E402


def main():
    files = gen_month(SEED, MONTH, 3200, 2400, False, ref_compute)
    files["rating_contract.md"] = (WORK / "rating_contract.md").read_bytes()
    DATA.mkdir(parents=True, exist_ok=True)
    for old in DATA.iterdir():
        if old.name not in files:
            old.unlink()
    total = 0
    for name, blob in sorted(files.items()):
        (DATA / name).write_bytes(blob)
        n = blob.count(b"\n")
        total += n
        if name.rsplit(".", 1)[-1] in ("csv", "tsv", "jsonl", "txt", "log"):
            assert n >= 2000, (name, n)
        print("%-26s %6d lines %8d bytes" % (name, n, len(blob)))
    assert total >= 20000, total
    docs = ref_compute(files)
    print("total lines", total, "| accepted", docs["summary.json"]["lines"],
          "| charge", docs["summary.json"]["charge"], "| credit", docs["summary.json"]["credit"])
    os.sync()


if __name__ == "__main__":
    main()
