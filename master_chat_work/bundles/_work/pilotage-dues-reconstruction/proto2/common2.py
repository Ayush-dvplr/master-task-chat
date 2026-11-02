"""Shared due model for the L-CONV prototype (proto only; never shipped)."""
from itertools import product

B_LIST = [180, 195, 210, 225, 240]   # cents per 100 GT
D_LIST = [250, 300, 350, 400]        # cents per decimetre above 6.0 m
N_LIST = [125, 140, 150]             # surcharge multiplier x100
T_LIST = [3500, 5000, 6500]          # cents per tug
ASSIST_RATE = 4000                   # cents per 30-minute block
TARIFFS = list(product(B_LIST, D_LIST, N_LIST, T_LIST))  # 180, listed order
STATIONS = ["North", "South", "West", "East"]
CALENDARS = ["national", "north", "south", "west", "east", "harbour", "fishery"]
OWN = {"North": "north", "South": "south", "West": "west", "East": "east"}

# superset of readings the generator proves unique over
A_ALL = ["started", "completed", "half_up", "half_down"]
D_ALL = ["up", "down", "half_up", "half_down"]
S_ALL = ["sunday", "sunday_monday", "monday"]
BASE_ALL = ["with_assist", "without_assist"]
N_ALL = [(s, e) for s in range(24) for e in range(24) if s != e]
HEADLINE = {"A": "started", "D": "up", "S": "sunday_monday", "B": "with_assist", "N": (22, 6)}


def rhe(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        return q + 1
    return q


def blocks(minutes, a):
    q, r = divmod(minutes, 30)
    if r == 0:
        return q
    if a == "started":
        return q + 1
    if a == "completed":
        return q
    if a == "half_up":
        return q + (1 if r >= 15 else 0)
    return q + (1 if r > 15 else 0)


def tenth(cm, d):
    q, r = divmod(cm, 10)
    if r == 0:
        return q
    if d == "up":
        return q + 1
    if d == "down":
        return q
    if d == "half_up":
        return q + (1 if r >= 5 else 0)
    return q + (1 if r > 5 else 0)


def in_window(h, w):
    s, e = w
    return s <= h < e if s < e else (h >= s or h < e)


def is_holiday(day, cal_days, s):
    """day: date; cal_days: set of dates of the kept calendar."""
    from datetime import timedelta
    if s in ("sunday", "sunday_monday") and day in cal_days:
        return True
    prev = day - timedelta(days=1)
    if s in ("sunday_monday", "monday") and day.weekday() == 0 and prev in cal_days:
        return True
    return False


def due(t, v, conv, flag):
    """t tariff tuple, v visit dict, conv dict with A D B; flag surcharge bool."""
    b, d, n, tt = t
    l1 = rhe(b * v["gt"], 100)
    l2 = d * max(0, tenth(v["draft_cm"], conv["D"]) - 60)
    l3 = tt * v["tugs"]
    l4 = ASSIST_RATE * blocks(v["assist"], conv["A"])
    base = l1 + l2 + l3 + (l4 if conv["B"] == "with_assist" else 0)
    l5 = rhe((n - 100) * base, 100) if flag else 0
    return l1 + l2 + l3 + l4 + l5


def money(c):
    s = "-" if c < 0 else ""
    c = abs(c)
    return f"{s}{c // 100}.{c % 100:02d}"
