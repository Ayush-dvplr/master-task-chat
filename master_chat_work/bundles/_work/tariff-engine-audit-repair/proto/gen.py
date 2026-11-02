"""Prototype hidden statement accounts for the wave 1 kill test (scratch).

Each corpus: 3 ledger-scale accounts (scale-split vouchers), 3 small tie
accounts, 1 overpaid account. Output: proto/corpus_<n>.json
"""
import json
import random
import sys
from math import gcd
from pathlib import Path

HERE = Path(__file__).parent


def ids(rng, used, count):
    out = []
    while len(out) < count:
        name = rng.choice("KPVW") + str(rng.randrange(1, 10 ** rng.randrange(2, 6)))
        if name not in used:
            used.add(name)
            out.append(name)
    return out


def big_account(rng, used, P):
    g = rng.randrange(P["g_lo"], P["g_hi"])
    nl = rng.randrange(P["nl_lo"], P["nl_hi"])
    ns = rng.randrange(P["ns_lo"], P["ns_hi"])
    units = [rng.randrange(P["u_lo"], P["u_hi"]) for _ in range(nl)]
    # a few repeated face values so the large part has planted ties too
    for _ in range(3):
        units[rng.randrange(nl)] = units[rng.randrange(nl)]
    while True:
        small = [rng.randrange(g // (3 * ns), g // (ns + 1)) for _ in range(ns)]
        small[1] = small[0]  # tie on id among equal small vouchers
        if sum(small) < g and gcd(g, *small) == 1:
            break
    total_units = sum(units)
    target_units = rng.randrange(int(total_units * 0.3), int(total_units * 0.7))
    balance = target_units * g + rng.randrange(sum(small) // 3, g)
    amounts = [u * g for u in units] + small
    names = ids(rng, used, len(amounts))
    vouchers = list(zip(names, amounts))
    rng.shuffle(vouchers)
    return {"balance": balance, "vouchers": vouchers, "g": g, "nl": nl, "ns": ns}


def small_account(rng, used):
    target = rng.randrange(40_000, 400_000)
    count = rng.randrange(4, 9)
    amounts = [rng.randrange(target // 6, target // 2) for _ in range(count)]
    amounts.append(amounts[0])
    amounts.append(amounts[1] + amounts[2])
    names = ids(rng, used, len(amounts))
    return {"balance": target, "vouchers": list(zip(names, amounts))}


def corpus(seed, P):
    rng = random.Random(seed * 7919 + 4242)
    used = set()
    accounts = [big_account(rng, used, P) for _ in range(3)]
    accounts += [small_account(rng, used) for _ in range(3)]
    accounts.append({"balance": 0, "vouchers": list(zip(ids(rng, used, 1), [12345]))})
    for index, account in enumerate(accounts):
        account["account"] = "A9%03d" % index
    return {"seed": seed, "accounts": accounts}


PARAMS = {
    "g_lo": 50_000, "g_hi": 100_000,
    "nl_lo": 46, "nl_hi": 56,
    "ns_lo": 9, "ns_hi": 12,
    "u_lo": 1_000, "u_hi": 60_000,
}

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    for seed in range(1, count + 1):
        data = corpus(seed, PARAMS)
        (HERE / ("corpus_%d.json" % seed)).write_text(json.dumps(data))
        big = data["accounts"][:3]
        print(seed, [(a["balance"], len(a["vouchers"]), a["g"], a["ns"]) for a in big])
