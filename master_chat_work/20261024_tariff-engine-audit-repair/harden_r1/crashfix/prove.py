"""Crash-fix proof: the reference document is byte-identical before and after the fix
on the shipped tier and on every seeded hidden tier, and the fixed reference no longer
crashes on an integer standing_charge.

    python3 prove.py BEFORE_TEST_FILE AFTER_TEST_FILE
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
STUB = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair/rewardkit_stub"
sys.path.insert(0, STUB)
TIERS = ["shipped", "fresh", "rescaled", "relocated", "rotated", "api"]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    before, after = load(sys.argv[1], "before"), load(sys.argv[2], "after")
    same = True
    for tier in TIERS:
        a = json.dumps(before._expected(tier), sort_keys=True, indent=2).encode()
        b = json.dumps(after._expected(tier), sort_keys=True, indent=2).encode()
        print(f"{tier:10s} invoices={len(json.loads(a)['invoices']):5d} bytes={len(a):9d} identical={a == b}")
        same &= a == b
    texts = after._corpus_texts("fresh")
    card = json.loads(texts["rate_card.json"])
    for plan in card["plans"].values():
        plan["standing_charge"] = 45
    texts = dict(texts, **{"rate_card.json": json.dumps(card)})
    for mod, label in ((before, "before"), (after, "after")):
        try:
            doc = mod._Ledger(texts).document()
            print(f"integer standing_charge {label}: ok, {len(doc['invoices'])} invoices")
        except Exception as exc:  # report the crash class, this is the point of the probe
            print(f"integer standing_charge {label}: {type(exc).__name__}: {exc}")
    print("ALL_IDENTICAL" if same else "DIFFERENT")


if __name__ == "__main__":
    main()
