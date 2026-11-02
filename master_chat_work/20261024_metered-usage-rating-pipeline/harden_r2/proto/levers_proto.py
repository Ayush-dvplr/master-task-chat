"""Scratch prototypes of the proposed r2 levers (not shipped). Oracle reading vs the reflex reading.

A  LV-MU-6 credit re-share (H7): floor 0.50 per line share, 'the whole credit pool is shared again by the same rule'.
B  LV-MU-5 rewrite (H6 + recursive definition): billing group of an account = billing group of its parent.
C  LV-MU-7 shortfall re-share (H7, amount fixed once): 'the whole shortfall is shared again by the same rule'.
Money in integer cents; half-even on exact fractions.
"""
import sys
from fractions import Fraction as F

FLOOR = 50  # 0.50


def he(x):
    """half-even of a Fraction to an int (cents)."""
    n, r = divmod(x.numerator, x.denominator)
    two_r = 2 * r
    if two_r > x.denominator or (two_r == x.denominator and n % 2):
        n += 1
    return n


# ---------- A: credit re-share ----------
def credit_oracle(pool, charges):
    base = sum(charges.values())
    if base <= pool:
        return dict(charges)
    share = {k: he(F(pool * c, base)) for k, c in charges.items()}
    keep = {k: c for k, c in charges.items() if share[k] >= FLOOR}
    if len(keep) == len(charges):
        return share
    if not keep:
        return {k: 0 for k in charges}
    base2 = sum(keep.values())
    out = {k: 0 for k in charges}
    out.update({k: he(F(pool * c, base2)) for k, c in keep.items()})  # the whole pool, proportional
    return out


def credit_reflex(pool, charges, _all=None):
    """Recursive helper: the second pass re-enters the at-or-below branch."""
    _all = _all if _all is not None else charges
    base = sum(charges.values())
    out = {k: 0 for k in _all}
    if base <= pool:
        out.update(charges)
        return out
    share = {k: he(F(pool * c, base)) for k, c in charges.items()}
    keep = {k: c for k, c in charges.items() if share[k] >= FLOOR}
    if len(keep) == len(charges):
        out.update(share)
        return out
    if not keep:
        return out
    return credit_reflex(pool, keep, _all)


# ---------- B: billing group ----------
def group_oracle(parent, a):
    while parent.get(a):
        a = parent[a]
    return a


def group_reflex(parent, a):  # the probe-2 agent program, transform.py L174-187
    return parent.get(a) or a


def tiers(lines, parent, grp, steps=((0, 1), (100, 2), (500, 3))):
    counter, out = {}, []
    for acct, prod, units in lines:
        key = (grp(parent, acct), prod)
        before = counter.get(key, 0)
        out.append(max(t for frm, t in steps if frm <= before))
        counter[key] = before + units
    return out


# ---------- C: shortfall re-share ----------
def shortfall_oracle(minimum, charges):
    total = sum(charges.values())
    if total >= minimum:
        return {k: 0 for k in charges}
    short = minimum - total
    share = {k: he(F(short * c, total)) for k, c in charges.items()}
    keep = {k: c for k, c in charges.items() if share[k] >= FLOOR}
    if len(keep) == len(charges):
        return share
    out = {k: 0 for k in charges}
    if keep:
        b2 = sum(keep.values())
        out.update({k: he(F(short * c, b2)) for k, c in keep.items()})  # the whole shortfall
    return out


def shortfall_reflex(minimum, charges, _all=None):
    _all = _all if _all is not None else charges
    total = sum(charges.values())
    out = {k: 0 for k in _all}
    if total >= minimum:
        return out
    short = minimum - total  # recomputed from the survivors
    share = {k: he(F(short * c, total)) for k, c in charges.items()}
    keep = {k: c for k, c in charges.items() if share[k] >= FLOOR}
    if len(keep) == len(charges):
        out.update(share)
        return out
    if not keep:
        return out
    return shortfall_reflex(minimum, keep, _all)


if __name__ == "__main__":
    print("A shrunk corpus: region pool 10.00, counted lines L1 9.80, L2 0.30, L3 0.25")
    ch = {"L1": 980, "L2": 30, "L3": 25}
    print("  oracle", credit_oracle(1000, ch), " reflex", credit_reflex(1000, ch))
    print("B shrunk corpus: C parent B, B parent A; product CMP; tiers from 0/100/500")
    par = {"C": "B", "B": "A", "A": ""}
    ln = [("A", "CMP", 450), ("C", "CMP", 80), ("B", "CMP", 10), ("C", "CMP", 5)]
    print("  oracle tiers", tiers(ln, par, group_oracle), " reflex tiers", tiers(ln, par, group_reflex))
    print("C shrunk corpus: region minimum 100.00, committed charges A 60.00, B 1.00, C 0.40")
    ch = {"A": 6000, "B": 100, "C": 40}
    print("  oracle", shortfall_oracle(10000, ch), " reflex", shortfall_reflex(10000, ch))
    sys.exit(0)
