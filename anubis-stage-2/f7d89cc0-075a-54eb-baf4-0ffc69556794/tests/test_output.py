"""
Verifier for meridian-grid-tariff-reconciliation.

This module owns the ground truth for the task. It carries the shipped
reference tables as Python literals and derives deterministic staged profiles
that vary both reference and transaction files. SAMPLE builds the shipped
extract. CASCADE, REVERSAL, and CHALLENGE drive one persistent hidden session,
followed by a repeated CASCADE turn that proves state reset and determinism.

The reference reconciler `_reference_reconcile` is an independent
implementation of the contract in `environment/data/schema.md`, written as
plain functions over dicts with exact rational arithmetic; it is not a copy
of `solution/solve.py`. Both must produce byte-identical outputs on any
lawful input, because both implement the same contract.

Nothing here depends on `/app/data` or `/app/out/reconcile.py` being present
at import time. Every check returns a boolean or a score in [0, 1] and never raises, and every
execution of the agent's script runs as the unprivileged `nobody` user in
its own process group, which is killed before the check returns.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import io
import json
import math
import os
import pwd
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

# ─────────────────────────────────────────────────────────────────────────────
# Section 1 - seeds
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_SEED = 0x4d47494349422d3031  # "MIGCIB-01"
CHALLENGE_SEED = 0x4d47494349422d3032  # "MIGCIB-02"
EVAL_SEED = 0x4d47494349422d3033  # "MIGCIB-03"

PROFILE_SEEDS = {
    "SAMPLE": SAMPLE_SEED,
    "CASCADE": EVAL_SEED ^ 0x43415343414445,
    "REVERSAL": CHALLENGE_SEED ^ 0x524556455253414C,
    "CHALLENGE": EVAL_SEED ^ CHALLENGE_SEED ^ 0x4348414C4C454E47,
}
SESSION_SEQUENCE = ("CASCADE", "REVERSAL", "CHALLENGE", "CASCADE")

_U64 = 0xFFFFFFFFFFFFFFFF


def xorshift64(state: int) -> int:
    """Deterministic 64-bit xorshift PRNG. Independent of Python version."""
    state &= _U64
    state ^= (state << 13) & _U64
    state ^= (state >> 7) & _U64
    state ^= (state << 17) & _U64
    return state & _U64


class RNG:
    def __init__(self, seed: int) -> None:
        # Keep every low bit of the seed (the three seeds differ only in
        # their lowest bits) and fold it through xorshift a few times. A
        # zero state would stay zero forever, so it is replaced by 1.
        state = (seed & _U64) or 1
        for _ in range(8):
            state = xorshift64(state)
        self.state = state

    def next_u64(self) -> int:
        self.state = xorshift64(self.state)
        return self.state

    def randint(self, lo: int, hi: int) -> int:
        """Inclusive on both ends."""
        span = hi - lo + 1
        return lo + (self.next_u64() % span)


# ─────────────────────────────────────────────────────────────────────────────
# Section 2 - period constants
# ─────────────────────────────────────────────────────────────────────────────

PERIOD_START = date(2025, 10, 1)
PERIOD_END = date(2025, 10, 31)
DAYS_IN_PERIOD = 31

# DST fall-back for FY2025 in MIGC: Oct 26, 2025 (Sunday). The civil hour
# beginning at 01:00 MST is lived twice.
DST_FALLBACK_DATE = date(2025, 10, 26)
FALLBACK_HOUR_START = datetime(2025, 10, 26, 1, 0, 0)

LABELS = ("peak", "shoulder", "night", "weekend")  # also the §7.3 draw order


def round_half_up(value: Any) -> int:
    """§13 half-up to an integer on an exact value: x.5 rounds toward
    positive infinity, so 2.5 -> 3 and -1.5 -> -1."""
    return math.floor(Fraction(value) + Fraction(1, 2))



# ─────────────────────────────────────────────────────────────────────────────
# Section 3 - reference tables (byte-identical shipped values)
# ─────────────────────────────────────────────────────────────────────────────

# Twenty valid customers plus one customer whose premise is deliberately absent.
# Fields correspond one-for-one to `customers.csv` schema in §3.1.
# `grandfather_date` and `grandfather_expires_on` are empty strings when
# `grandfather_flag` is false.
CUSTOMERS: list[dict] = [
    {"customer_id": "C0001", "name": "Alder Ridge Homestead",     "rate_class": "RES", "premise_code": "P12", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "residential"},
    {"customer_id": "C0002", "name": "Basalt Court Estate",       "rate_class": "RES", "premise_code": "P3", "meter_class": "hybrid6", "billing_currency": "MRC", "grandfather_flag": True,  "grandfather_date": "2022-06-15", "grandfather_expires_on": "2026-01-01", "solar_enrolled": False, "fiscal_group": "residential"},
    {"customer_id": "C0003", "name": "Cedar Crest Residence",     "rate_class": "RES", "premise_code": "P101", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": True,  "fiscal_group": "residential"},
    {"customer_id": "C0004", "name": "Dune Hollow Farm",          "rate_class": "RES", "premise_code": "P27", "meter_class": "hybrid6", "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": True,  "fiscal_group": "residential"},
    {"customer_id": "C0005", "name": "Elm Row Cottage",           "rate_class": "RES", "premise_code": "P8", "meter_class": "mech5",   "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "residential"},
    {"customer_id": "C0006", "name": "Foxglen Manor",             "rate_class": "RES", "premise_code": "P40", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "residential"},
    {"customer_id": "C0007", "name": "Granite Bend Dwelling",     "rate_class": "RES", "premise_code": "P5", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": True,  "grandfather_date": "2022-06-15", "grandfather_expires_on": "2026-01-01", "solar_enrolled": True,  "fiscal_group": "residential"},
    {"customer_id": "C0008", "name": "Heather Point Bungalow",    "rate_class": "RES", "premise_code": "P19", "meter_class": "mech5",   "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "residential"},
    {"customer_id": "C0009", "name": "Ironwood Foundry LLP",      "rate_class": "COM", "premise_code": "P210", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": True,  "fiscal_group": "commercial"},
    {"customer_id": "C0010", "name": "Juniper Mercantile",        "rate_class": "COM", "premise_code": "P33", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0011", "name": "Kavik Cold Storage",        "rate_class": "COM", "premise_code": "P9", "meter_class": "hybrid6", "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0012", "name": "Larch Freight Yard",        "rate_class": "COM", "premise_code": "P64", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0013", "name": "Meridian North Consulate",  "rate_class": "COM", "premise_code": "P1", "meter_class": "smart7",  "billing_currency": "FTU", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "public"},
    {"customer_id": "C0014", "name": "Northwind Print Cooperative","rate_class":"COM", "premise_code": "P150", "meter_class": "hybrid6", "billing_currency": "MRC", "grandfather_flag": True,  "grandfather_date": "2021-11-01", "grandfather_expires_on": "2025-10-15", "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0015", "name": "Osprey Marine Repair",      "rate_class": "COM", "premise_code": "P22", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0016", "name": "Pinegrove Craft Hall",      "rate_class": "COM", "premise_code": "P7", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0017", "name": "Quarry Ridge Aggregates",   "rate_class": "IND", "premise_code": "P1020", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0018", "name": "Rimefield Chemical Works",  "rate_class": "IND", "premise_code": "P88", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0019", "name": "Southern Meridian Trade Office","rate_class":"IND","premise_code":"P2","meter_class":"smart7",  "billing_currency": "FTU", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "public"},
    {"customer_id": "C0020", "name": "Tallow Refinery No. 3",     "rate_class": "IND", "premise_code": "P305", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": True,  "grandfather_date": "2025-08-12", "grandfather_expires_on": "2026-01-01",           "solar_enrolled": False, "fiscal_group": "commercial"},
    {"customer_id": "C0021", "name": "Unmapped Harbor Account",  "rate_class": "COM", "premise_code": "P404", "meter_class": "smart7",  "billing_currency": "MRC", "grandfather_flag": False, "grandfather_date": "",           "grandfather_expires_on": "",           "solar_enrolled": False, "fiscal_group": "commercial"},
]

# Row order of the shipped customers.csv. It follows neither customer_id nor
# premise number, so every §14.3 / §16.2 list sort is exercised: a solver that
# keeps file order, or sorts premise codes as strings (P101 before P12), is
# graded wrong. Generation and the reference still iterate CUSTOMERS.
CUSTOMERS_CSV_ORDER: tuple[str, ...] = (
    "C0014", "C0003", "C0019", "C0007", "C0010", "C0001", "C0018", "C0012", "C0005", "C0020",
    "C0009", "C0016", "C0002", "C0013", "C0021", "C0008", "C0017", "C0011", "C0004", "C0015", "C0006",
)

PREMISES: list[dict] = [
    {"premise_code": "P12", "street": "12 Alder Lane",      "city": "Northport",   "region": "Meridian_North", "latitude": "47.2831", "longitude": "-119.4412", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P3", "street": "44 Basalt Rise",     "city": "Northport",   "region": "Meridian_North", "latitude": "47.2755", "longitude": "-119.4501", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P101", "street": "8 Cedar Court",      "city": "Sundowner",   "region": "Meridian_South", "latitude": "45.6109", "longitude": "-118.9020", "meter_channel_count": 1, "altitude_bracket": "low"},
    {"premise_code": "P27", "street": "17 Dune Hollow Rd",  "city": "Northport",   "region": "Meridian_North", "latitude": "47.3011", "longitude": "-119.4600", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P8", "street": "25 Elm Row",         "city": "Farholm",     "region": "Meridian_East",  "latitude": "46.0244", "longitude": "-117.2011", "meter_channel_count": 1, "altitude_bracket": "high"},
    {"premise_code": "P40", "street": "31 Foxglen Drive",   "city": "Westmarch",   "region": "Meridian_West",  "latitude": "46.8801", "longitude": "-120.5023", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P5", "street": "3 Granite Bend",     "city": "Northport",   "region": "Meridian_North", "latitude": "47.2601", "longitude": "-119.4700", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P19", "street": "12 Heather Point",   "city": "Sundowner",   "region": "Meridian_South", "latitude": "45.6520", "longitude": "-118.8912", "meter_channel_count": 1, "altitude_bracket": "low"},
    {"premise_code": "P210", "street": "202 Ironwood Way",   "city": "Northport",   "region": "Meridian_North", "latitude": "47.3155", "longitude": "-119.4300", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P33", "street": "88 Juniper Blvd",    "city": "Sundowner",   "region": "Meridian_South", "latitude": "45.6300", "longitude": "-118.9111", "meter_channel_count": 1, "altitude_bracket": "low"},
    {"premise_code": "P9", "street": "5 Kavik Industrial", "city": "Farholm",     "region": "Meridian_East",  "latitude": "46.0409", "longitude": "-117.2110", "meter_channel_count": 1, "altitude_bracket": "high"},
    {"premise_code": "P64", "street": "17 Larch Freight",   "city": "Westmarch",   "region": "Meridian_West",  "latitude": "46.9020", "longitude": "-120.5150", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P1", "street": "1 Consulate Plaza",  "city": "Northport",   "region": "Meridian_North", "latitude": "47.2900", "longitude": "-119.4550", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P150", "street": "60 Print Cooperative","city": "Sundowner",  "region": "Meridian_South", "latitude": "45.6150", "longitude": "-118.9050", "meter_channel_count": 1, "altitude_bracket": "low"},
    {"premise_code": "P22", "street": "88 Marina Drive",    "city": "Farholm",     "region": "Meridian_East",  "latitude": "46.0100", "longitude": "-117.2205", "meter_channel_count": 1, "altitude_bracket": "high"},
    {"premise_code": "P7", "street": "12 Pinegrove Rd",    "city": "Northport",   "region": "Meridian_North", "latitude": "47.2700", "longitude": "-119.4650", "meter_channel_count": 1, "altitude_bracket": "mid"},
    {"premise_code": "P1020", "street": "44 Quarry Ridge",    "city": "Farholm",     "region": "Meridian_East",  "latitude": "46.0300", "longitude": "-117.2005", "meter_channel_count": 2, "altitude_bracket": "high"},
    {"premise_code": "P88", "street": "99 Rimefield Chem",  "city": "Sundowner",   "region": "Meridian_South", "latitude": "45.6220", "longitude": "-118.9250", "meter_channel_count": 2, "altitude_bracket": "low"},
    {"premise_code": "P2", "street": "3 Trade Office",     "city": "Sundowner",   "region": "Meridian_South", "latitude": "45.6280", "longitude": "-118.9330", "meter_channel_count": 1, "altitude_bracket": "low"},
    {"premise_code": "P305", "street": "22 Refinery Way",    "city": "Westmarch",   "region": "Meridian_West",  "latitude": "46.8830", "longitude": "-120.4900", "meter_channel_count": 1, "altitude_bracket": "mid"},
]

# Tariff schedule. Rate/period key: (rate_class, tou_period, effective_from..until).
# Rate class RES has energy rows for peak/shoulder/night/weekend plus the
# `*` demand-and-customer-charge row (demand=0 for RES).
# Retroactive R-25-19 supersedes the COM demand row for Sept 2025 with a new
# higher rate at order_of_precedence=20.
# Grandfathered rows live BEFORE 2024-01-01 for grandfather-flag customers
# whose grandfather_date is 2022 or 2021. C0020 is frozen on 2025-08-12, a
# date inside the precedence-20 S-25-R15-0001 IND peak window: §3.3 freezes it
# on the precedence-10 S-24-03 rows (peak 30, not 33), and the non-immune
# R-25-15 must skip it (§3.8 / §10).
TARIFF_SCHEDULE: list[dict] = [
    # Pre-2024 rates (grandfathered customers keep these).
    {"schedule_id": "S-21-01-0001", "rate_class": "RES", "tou_period": "peak",     "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 22, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 700,  "order_of_precedence": 10},
    {"schedule_id": "S-21-01-0002", "rate_class": "RES", "tou_period": "shoulder", "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 16, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 700,  "order_of_precedence": 10},
    {"schedule_id": "S-21-01-0003", "rate_class": "RES", "tou_period": "night",    "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 10, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 700,  "order_of_precedence": 10},
    {"schedule_id": "S-21-01-0004", "rate_class": "RES", "tou_period": "weekend",  "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 13, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 700,  "order_of_precedence": 10},
    {"schedule_id": "S-21-01-0005", "rate_class": "RES", "tou_period": "*",        "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 0,  "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 700,  "order_of_precedence": 10},
    {"schedule_id": "S-21-02-0001", "rate_class": "COM", "tou_period": "peak",     "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 28, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 1800, "order_of_precedence": 10},
    {"schedule_id": "S-21-02-0002", "rate_class": "COM", "tou_period": "shoulder", "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 20, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 1800, "order_of_precedence": 10},
    {"schedule_id": "S-21-02-0003", "rate_class": "COM", "tou_period": "night",    "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 13, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 1800, "order_of_precedence": 10},
    {"schedule_id": "S-21-02-0004", "rate_class": "COM", "tou_period": "weekend",  "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 17, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 1800, "order_of_precedence": 10},
    {"schedule_id": "S-21-02-0005", "rate_class": "COM", "tou_period": "*",        "effective_from": "2020-01-01", "effective_until": "2023-12-31", "energy_rate_mrcc_per_kwh": 0,  "demand_rate_mrcc_per_kw": 1100, "customer_charge_mrcc": 1800, "order_of_precedence": 10},
    # Current rates (effective 2024-01-01 onward).
    {"schedule_id": "S-24-01-0001", "rate_class": "RES", "tou_period": "peak",     "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 28, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 900,  "order_of_precedence": 10},
    {"schedule_id": "S-24-01-0002", "rate_class": "RES", "tou_period": "shoulder", "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 20, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 900,  "order_of_precedence": 10},
    {"schedule_id": "S-24-01-0003", "rate_class": "RES", "tou_period": "night",    "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 12, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 900,  "order_of_precedence": 10},
    {"schedule_id": "S-24-01-0004", "rate_class": "RES", "tou_period": "weekend",  "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 15, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 900,  "order_of_precedence": 10},
    {"schedule_id": "S-24-01-0005", "rate_class": "RES", "tou_period": "*",        "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 0,  "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 900,  "order_of_precedence": 10},
    {"schedule_id": "S-24-02-0001", "rate_class": "COM", "tou_period": "peak",     "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 34, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 2400, "order_of_precedence": 10},
    {"schedule_id": "S-24-02-0002", "rate_class": "COM", "tou_period": "shoulder", "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 24, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 2400, "order_of_precedence": 10},
    {"schedule_id": "S-24-02-0003", "rate_class": "COM", "tou_period": "night",    "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 15, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 2400, "order_of_precedence": 10},
    {"schedule_id": "S-24-02-0004", "rate_class": "COM", "tou_period": "weekend",  "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 20, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 2400, "order_of_precedence": 10},
    {"schedule_id": "S-24-02-0005", "rate_class": "COM", "tou_period": "*",        "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 0,  "demand_rate_mrcc_per_kw": 1250, "customer_charge_mrcc": 2400, "order_of_precedence": 10},
    {"schedule_id": "S-24-03-0001", "rate_class": "IND", "tou_period": "peak",     "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 30, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 6400, "order_of_precedence": 10},
    {"schedule_id": "S-24-03-0002", "rate_class": "IND", "tou_period": "shoulder", "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 22, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 6400, "order_of_precedence": 10},
    {"schedule_id": "S-24-03-0003", "rate_class": "IND", "tou_period": "night",    "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 14, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 6400, "order_of_precedence": 10},
    {"schedule_id": "S-24-03-0004", "rate_class": "IND", "tou_period": "weekend",  "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 18, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 6400, "order_of_precedence": 10},
    {"schedule_id": "S-24-03-0005", "rate_class": "IND", "tou_period": "*",        "effective_from": "2024-01-01", "effective_until": "",           "energy_rate_mrcc_per_kwh": 0,  "demand_rate_mrcc_per_kw": 1800, "customer_charge_mrcc": 6400, "order_of_precedence": 10},
    # Retroactive R-25-19: COM demand rate for September 2025 rewritten to 1550.
    {"schedule_id": "S-25-R19-0001", "rate_class": "COM", "tou_period": "*",       "effective_from": "2025-09-01", "effective_until": "2025-09-30", "energy_rate_mrcc_per_kwh": 0,  "demand_rate_mrcc_per_kw": 1550, "customer_charge_mrcc": 2400, "order_of_precedence": 20},
    # Retroactive R-25-15: IND peak energy rate for August 2025 rewritten to 33.
    {"schedule_id": "S-25-R15-0001", "rate_class": "IND", "tou_period": "peak",    "effective_from": "2025-08-01", "effective_until": "2025-08-31", "energy_rate_mrcc_per_kwh": 33, "demand_rate_mrcc_per_kw": 0,    "customer_charge_mrcc": 6400, "order_of_precedence": 20},
]

FAC_INDEX: list[dict] = [
    {"month": "2025-06", "fac_mrcc_per_kwh": 2},
    {"month": "2025-07", "fac_mrcc_per_kwh": 3},
    {"month": "2025-08", "fac_mrcc_per_kwh": 4},
    {"month": "2025-09", "fac_mrcc_per_kwh": 3},
    {"month": "2025-10", "fac_mrcc_per_kwh": 5},
    {"month": "2025-11", "fac_mrcc_per_kwh": 4},
    {"month": "2025-12", "fac_mrcc_per_kwh": 6},
]

# Shipped out of date order on purpose: §14.3 sorts holiday_reclassifications
# by date, so a solver that echoes file order is graded wrong.
HOLIDAY_CALENDAR: list[dict] = [
    {"date": "2025-10-20", "name": "Regulatory Compliance Day",  "tou_treatment": "weekend"},
    {"date": "2025-10-13", "name": "Meridian Foundation Day",    "tou_treatment": "off"},
]

DST_CALENDAR: dict = {
    "fall_back":      [{"date": "2025-10-26", "civil_hour_repeated": 1}],
    "spring_forward": [],
}

# Currency: MRC per FTU. Rates for a subset of dates in Oct 2025. The
# reference §3.7 rule says the last-known-good rate applies to dates without
# an explicit entry.
CURRENCY_RATES: dict = {
    "base": "MRC",
    "rates": [
        {"date": "2025-10-01", "mrc_per_ftu": 12500},
        {"date": "2025-10-08", "mrc_per_ftu": 12480},
        {"date": "2025-10-15", "mrc_per_ftu": 12550},
        {"date": "2025-10-22", "mrc_per_ftu": 12600},
        {"date": "2025-10-29", "mrc_per_ftu": 12570},
        {"date": "2025-08-01", "mrc_per_ftu": 11950},
    ],
}

REGULATOR_ORDERS: list[dict] = [
    {"order_id": "R-25-15", "issued_on": "2025-09-20", "effective_on": "2025-09-20",
     "supersedes_schedule_id": "S-24-03-0001", "new_schedule_id": "S-25-R15-0001",
     "period_start": "2025-08-01", "period_end": "2025-08-31",
     "scope": "retroactive", "grandfather_immune": False},
    {"order_id": "R-25-19", "issued_on": "2025-10-05", "effective_on": "2025-10-05",
     "supersedes_schedule_id": "S-24-02-0005", "new_schedule_id": "S-25-R19-0001",
     "period_start": "2025-09-01", "period_end": "2025-09-30",
     "scope": "retroactive", "grandfather_immune": True},
    {"order_id": "R-25-21", "issued_on": "2025-10-25", "effective_on": "2026-01-01",
     "supersedes_schedule_id": "S-24-01-0005", "new_schedule_id": "",
     "period_start": "2026-01-01", "period_end": "2026-06-30",
     "scope": "forward_only", "grandfather_immune": False},
    {"order_id": "R-25-22", "issued_on": "2025-10-12", "effective_on": "2025-10-18",
     "supersedes_schedule_id": "S-24-02-0005", "new_schedule_id": "",
     "period_start": "2025-10-18", "period_end": "2026-03-31",
     "scope": "forward_only", "grandfather_immune": False},
]

NET_METERING_BANK: list[dict] = [
    {"customer_id": "C0003", "balance_kwh_start_of_period":   -120500, "last_true_up_date": "2024-10-31"},
    {"customer_id": "C0004", "balance_kwh_start_of_period":  2400000, "last_true_up_date": "2024-10-31"},
    {"customer_id": "C0007", "balance_kwh_start_of_period":  2200000, "last_true_up_date": "2024-10-31"},
    {"customer_id": "C0009", "balance_kwh_start_of_period": 18500000, "last_true_up_date": "2024-10-31"},
]


def _base_reference_tables() -> dict[str, Any]:
    return {
        "customers": copy.deepcopy(CUSTOMERS),
        "customer_order": list(CUSTOMERS_CSV_ORDER),
        "premises": copy.deepcopy(PREMISES),
        "tariff": copy.deepcopy(TARIFF_SCHEDULE),
        "fac": copy.deepcopy(FAC_INDEX),
        "holidays": copy.deepcopy(HOLIDAY_CALENDAR),
        "dst": copy.deepcopy(DST_CALENDAR),
        "currency": copy.deepcopy(CURRENCY_RATES),
        "orders": copy.deepcopy(REGULATOR_ORDERS),
        "nmb": copy.deepcopy(NET_METERING_BANK),
    }


def _row(rows: list[dict], key: str, value: str) -> dict:
    return next(r for r in rows if r[key] == value)


def _split_current_tariff(tables: dict[str, Any], rate_class: str, split_on: str,
                          prefix: str, rates: dict[str, int], demand: int,
                          customer_charge: int) -> None:
    split = date.fromisoformat(split_on)
    prior_end = (split - timedelta(days=1)).isoformat()
    labels = (*LABELS, "*")
    for label in labels:
        current = next(
            r for r in tables["tariff"]
            if r["rate_class"] == rate_class
            and r["tou_period"] == label
            and r["effective_until"] == ""
            and int(r["order_of_precedence"]) == 10
        )
        current["effective_until"] = prior_end
        tables["tariff"].append({
            "schedule_id": f"{prefix}-{'TOTAL' if label == '*' else label.upper()}",
            "rate_class": rate_class,
            "tou_period": label,
            "effective_from": split_on,
            "effective_until": "",
            "energy_rate_mrcc_per_kwh": 0 if label == "*" else rates[label],
            "demand_rate_mrcc_per_kw": demand if label == "*" else 0,
            "customer_charge_mrcc": customer_charge,
            "order_of_precedence": 10,
        })


def _profile_tables(profile: str) -> dict[str, Any]:
    tables = _base_reference_tables()
    if profile == "SAMPLE":
        return tables

    if profile == "CASCADE":
        _row(tables["customers"], "customer_id", "C0010")["billing_currency"] = "FTU"
        c14 = _row(tables["customers"], "customer_id", "C0014")
        c14["grandfather_expires_on"] = "2025-10-09"
        _row(tables["premises"], "premise_code", "P33")["region"] = "Meridian_East"
        _row(tables["premises"], "premise_code", "P1020")["region"] = "Meridian_South"
        _split_current_tariff(
            tables, "COM", "2025-10-17", "S-25-CAS",
            {"peak": 31, "shoulder": 29, "night": 11, "weekend": 26},
            1399, 2711,
        )
        _row(tables["fac"], "month", "2025-10")["fac_mrcc_per_kwh"] = -3
        tables["holidays"] = [
            {"date": "2025-10-26", "name": "Cutover Remembrance", "tou_treatment": "weekend"},
            {"date": "2025-10-13", "name": "Meridian Foundation Day", "tou_treatment": "weekend"},
            {"date": "2025-10-20", "name": "Regulatory Compliance Day", "tou_treatment": "off"},
        ]
        tables["currency"]["rates"] = list(reversed([
            {"date": "2025-08-01", "mrc_per_ftu": 11875},
            {"date": "2025-10-01", "mrc_per_ftu": 13125},
            {"date": "2025-10-11", "mrc_per_ftu": 12890},
            {"date": "2025-10-23", "mrc_per_ftu": 13440},
        ]))
        tables["tariff"].append({
            "schedule_id": "S-25-R23-0001", "rate_class": "RES", "tou_period": "peak",
            "effective_from": "2025-09-01", "effective_until": "2025-09-30",
            "energy_rate_mrcc_per_kwh": 19, "demand_rate_mrcc_per_kw": 0,
            "customer_charge_mrcc": 900, "order_of_precedence": 20,
        })
        tables["orders"].append({
            "order_id": "R-25-23", "issued_on": "2025-10-27", "effective_on": "2025-10-27",
            "supersedes_schedule_id": "S-24-01-0001", "new_schedule_id": "S-25-R23-0001",
            "period_start": "2025-09-01", "period_end": "2025-09-30",
            "scope": "retroactive", "grandfather_immune": True,
        })
        _row(tables["nmb"], "customer_id", "C0004")["balance_kwh_start_of_period"] = 3100000
        _row(tables["nmb"], "customer_id", "C0007")["balance_kwh_start_of_period"] = 2750000
        tables["customer_order"].reverse()
        tables["premises"].reverse()
        tables["tariff"] = tables["tariff"][::2] + tables["tariff"][1::2]
        return tables

    if profile == "REVERSAL":
        _row(tables["customers"], "customer_id", "C0012")["billing_currency"] = "FTU"
        _row(tables["customers"], "customer_id", "C0019")["billing_currency"] = "MRC"
        _row(tables["customers"], "customer_id", "C0020")["grandfather_expires_on"] = "2025-10-22"
        _row(tables["premises"], "premise_code", "P88")["region"] = "Meridian_North"
        _row(tables["premises"], "premise_code", "P2")["region"] = "Meridian_East"
        _split_current_tariff(
            tables, "IND", "2025-10-11", "S-25-REV",
            {"peak": 41, "shoulder": 17, "night": 23, "weekend": 12},
            2075, 5875,
        )
        _row(tables["fac"], "month", "2025-10")["fac_mrcc_per_kwh"] = 9
        tables["holidays"] = [
            {"date": "2025-10-26", "name": "Cutover Closure", "tou_treatment": "off"},
            {"date": "2025-10-13", "name": "Meridian Foundation Day", "tou_treatment": "weekend"},
            {"date": "2025-10-20", "name": "Regulatory Compliance Day", "tou_treatment": "weekend"},
        ]
        tables["currency"]["rates"] = [
            {"date": "2025-10-18", "mrc_per_ftu": 12110},
            {"date": "2025-08-01", "mrc_per_ftu": 11725},
            {"date": "2025-10-01", "mrc_per_ftu": 12240},
        ]
        _row(tables["tariff"], "schedule_id", "S-25-R19-0001")["demand_rate_mrcc_per_kw"] = 975
        _row(tables["nmb"], "customer_id", "C0009")["balance_kwh_start_of_period"] = 32000000
        tables["customer_order"] = tables["customer_order"][7:] + tables["customer_order"][:7]
        tables["orders"].reverse()
        tables["nmb"].reverse()
        return tables

    if profile == "CHALLENGE":
        _row(tables["customers"], "customer_id", "C0006")["billing_currency"] = "FTU"
        _row(tables["customers"], "customer_id", "C0002")["grandfather_expires_on"] = "2025-10-06"
        _row(tables["premises"], "premise_code", "P12")["region"] = "Meridian_East"
        _row(tables["premises"], "premise_code", "P7")["region"] = "Meridian_South"
        _split_current_tariff(
            tables, "RES", "2025-10-23", "S-25-CHA",
            {"peak": 37, "shoulder": 14, "night": 18, "weekend": 9},
            0, 1127,
        )
        _row(tables["fac"], "month", "2025-10")["fac_mrcc_per_kwh"] = -7
        tables["holidays"] = [
            {"date": "2025-10-24", "name": "Compact Audit Day", "tou_treatment": "off"},
            {"date": "2025-10-13", "name": "Meridian Foundation Day", "tou_treatment": "off"},
            {"date": "2025-10-20", "name": "Regulatory Compliance Day", "tou_treatment": "weekend"},
        ]
        tables["currency"]["rates"] = [
            {"date": "2025-10-29", "mrc_per_ftu": 14101},
            {"date": "2025-10-01", "mrc_per_ftu": 13777},
            {"date": "2025-08-01", "mrc_per_ftu": 11666},
            {"date": "2025-10-15", "mrc_per_ftu": 13903},
        ]
        _row(tables["nmb"], "customer_id", "C0007")["balance_kwh_start_of_period"] = 4100000
        # §7.3 draw order, made observable. Invariant this value must keep:
        # cum(peak, shoulder) < bank < cum(peak, shoulder, night), which here is
        # 244507.919463 < 305000 < 366761.879195. The bank is therefore spent
        # PART-WAY through `night`, so a wrong draw order charges a different
        # label instead of cancelling out, and the partial label spans the
        # 2025-10-23 RES split above, exercising the §7.3 proportional reduction
        # that a drawn-to-zero label would hide. Must stay positive: §14.5's
        # `customers_with_negative_nmb_start` is 0 only in this profile.
        _row(tables["nmb"], "customer_id", "C0003")["balance_kwh_start_of_period"] = 305000
        tables["customer_order"] = tables["customer_order"][::-2] + tables["customer_order"][-2::-2]
        tables["fac"].reverse()
        tables["holidays"].reverse()
        return tables

    raise ValueError(f"unknown profile: {profile}")




# ─────────────────────────────────────────────────────────────────────────────
# Section 4 - transaction generator (varies by seed)
# ─────────────────────────────────────────────────────────────────────────────

# Fixed per-customer starting register value (thousandths of a kWh) and daily
# consumption profile (thousandths of a kWh per day). mech5 customers ignore
# the starting value: they start a seeded distance below the register maximum
# so that every extract carries an in-period §4.1 rollover.
CUSTOMER_START_REG_KWHTH: dict[str, int] = {
    "C0001":   6250000, "C0002":  27500000,
    "C0003":   9012000, "C0004":  310540000,
    "C0005":     99880, "C0006":   4580000, "C0007":  3115000,
    "C0008":     97120, "C0009": 105220000,
    "C0010":   58330000, "C0011":  620180000,
    "C0012":   77840000, "C0013":   45170000,
    "C0014":  512040000, "C0015":   84600000,
    "C0016":   61370000, "C0017":  1230000000, "C0018": 1440500000,
    "C0019":  980200000, "C0020":  1620400000, "C0021": 73000000,
}

CUSTOMER_DAILY_KWHTH: dict[str, int] = {
    # RES daily 11-36 kWh
    "C0001": 22400, "C0002": 27100, "C0003": 18500, "C0004": 35700,
    "C0005": 12300, "C0006": 21050, "C0007": 24800, "C0008": 11440,
    # COM daily 220-615 kWh
    "C0009": 380000, "C0010": 520000, "C0011": 615000, "C0012": 470000,
    "C0013": 220000, "C0014": 260000, "C0015": 350000, "C0016": 290000,
    # IND daily 1980-3450 kWh
    "C0017": 2800000, "C0018": 3450000, "C0019": 1980000, "C0020": 3200000,
    "C0021": 410000,
}

# §15.1 orphan transaction rows use a customer_id that customers.csv lacks.
ORPHAN_CUSTOMER_ID = "C0090"

# Two-channel premises split their load 60/40 between the channels.
CHANNEL_SPLIT_PCT = (60, 40)

# Planted demand rows (§6.2 traps). Every value sits above the customer's
# ordinary interval demand.
DEMAND_TRAPS: dict[str, list[tuple[str, str]]] = {
    # Exact tie; the later interval wins.
    "C0011": [("2025-10-14T14:00:00", "999.500"), ("2025-10-24T14:00:00", "999.500")],
    # Exact tie straddling the Oct 15 grandfather expiry: the later interval
    # (current schedule) wins, and Oct 20 is a weekend-treated holiday that
    # stays eligible for demand.
    "C0014": [("2025-10-10T14:00:00", "777.250"), ("2025-10-20T14:00:00", "777.250")],
    # The highest row falls on the Oct 13 holiday_off date and is excluded.
    "C0015": [("2025-10-13T14:00:00", "950.000"), ("2025-10-19T14:00:00", "888.750")],
    # The peak lives in the second occurrence of the fall-back hour.
    "C0016": [("2025-10-26T25:00:00", "666.500")],
}


def _customer_max_register_kwhth(meter_class: str) -> int:
    """Maximum register value in thousandths of a kWh."""
    if meter_class == "mech5":
        return 99_999_999  # 99999.999
    if meter_class == "hybrid6":
        return 999_999_999
    return 9_999_999_999  # smart7


def _premise_channels(customer: dict, premises: list[dict] = PREMISES) -> int:
    for p in premises:
        if p["premise_code"] == customer["premise_code"]:
            return int(p["meter_channel_count"])
    return 1


def generate_service_tickets(seed: int) -> list[dict]:
    """Service tickets: the customers are fixed, the dates vary by seed."""
    rng = RNG(seed ^ 0xA5A5A5A5)
    migration_day = 10 + rng.randint(0, 6)  # in [10, 16]
    move_in_day = rng.randint(3, 9)
    move_out_day = rng.randint(18, 24)
    # §9: a COM -> IND migration that lands before the C0016 fall-back demand
    # peak (DEMAND_TRAPS), so the demand charge is priced at the class held on
    # the DDC date, not at the customers.csv class.
    demand_migration_day = rng.randint(18, 23)
    return [
        {"ticket_id": "T-0001", "customer_id": "C0007",
         "event_type": "rate_class_migration",
         "effective_date": date(2025, 10, migration_day).isoformat(),
         "new_rate_class": "COM", "note": "Home office conversion under MIGC Ruling 2024-P17."},
        {"ticket_id": "T-0002", "customer_id": "C0001",
         "event_type": "move_in",
         "effective_date": date(2025, 10, move_in_day).isoformat(),
         "new_rate_class": "", "note": "New occupant after a vacancy."},
        {"ticket_id": "T-0003", "customer_id": "C0004",
         "event_type": "move_out",
         "effective_date": date(2025, 10, move_out_day).isoformat(),
         "new_rate_class": "", "note": "Account closed at the occupant's request."},
        {"ticket_id": "T-0004", "customer_id": "C0016",
         "event_type": "rate_class_migration",
         "effective_date": date(2025, 10, demand_migration_day).isoformat(),
         "new_rate_class": "IND", "note": "Kiln hall expansion reclassified under MIGC Ruling 2025-P04."},
        {"ticket_id": "T-0005", "customer_id": "C0021",
         "event_type": "move_out", "effective_date": "2025-10-17",
         "new_rate_class": "", "note": "Orphan account closure retained in the raw transaction extract."},
    ]


def _tou_windows_for_class(rate_class: str) -> dict[str, list[tuple[int, int]]]:
    """§5.1 labelled [start_hour, end_hour) windows on an ordinary weekday."""
    if rate_class == "RES":
        return {"peak": [(16, 21)], "shoulder": [(7, 16), (21, 23)], "night": [(23, 24), (0, 7)]}
    if rate_class == "COM":
        return {"peak": [(12, 18)], "shoulder": [(8, 12), (18, 22)], "night": [(22, 24), (0, 8)]}
    return {"peak": [(10, 20)], "shoulder": [(6, 10), (20, 23)], "night": [(23, 24), (0, 6)]}


def _label_civil_hour(rate_class: str, d: date, h: int, is_repeat: bool,
                      holidays_off: set[date], holidays_weekend: set[date]) -> str:
    """§5 label for one civil hour (aware of the DST repeat and holidays)."""
    if d in holidays_off or d in holidays_weekend:
        return "weekend"
    if is_repeat:
        # §5.2: second 01:00 hour is `night` for RES/IND and `weekend` for COM.
        return "weekend" if rate_class == "COM" else "night"
    if d.weekday() >= 5:
        return "weekend"
    for label, ranges in _tou_windows_for_class(rate_class).items():
        for (a, b) in ranges:
            if a <= h < b:
                return label
    return "night"


def _daily_kwhth(base: int, rng: RNG) -> int:
    """One day's consumption: the base wobbled by up to 8% either way."""
    noise = rng.randint(-8, 8)
    return max(0, base + base * noise // 100)


def _fmt_th(th: int) -> str:
    """Format thousandths as a decimal with three fractional digits."""
    whole, frac = divmod(th, 1000)
    return f"{whole}.{frac:03d}"


def _parse_kwh(s: str) -> int:
    """Parse a decimal reading '123.456' into thousandths."""
    s = s.strip()
    if "." in s:
        whole, frac = s.split(".")
        frac = (frac + "000")[:3]
        return int(whole) * 1000 + int(frac)
    return int(s) * 1000


def _gap_secs(ts_a: str, ts_b: str) -> int:
    return sum(s[3] for s in _hour_slots(datetime.fromisoformat(ts_a),
                                         datetime.fromisoformat(ts_b)))


def _even_median_spike_reads(day_end: list[int], daily: list[int]) -> list[tuple[str, int]]:
    """C0012's reads after the opening one, closing read last (§15.2).

    Six inter-read gaps, so the median is the mean of the third and fourth
    rates: three ordinary gaps, an elevated closing gap, and two one-hour
    spikes. Spike A sits between 20x the lower middle rate and 20x the
    median, spike B between 20x the median and 20x the upper middle rate,
    so exactly one read is flagged only when the median is the mean of the
    two middle rates.
    """
    ts = ["2025-09-30T23:00:00", "2025-10-08T23:00:00", "2025-10-20T10:00:00",
          "2025-10-20T11:00:00", "2025-10-24T12:00:00", "2025-10-24T13:00:00",
          "2025-10-31T23:00:00"]
    secs = [_gap_secs(a, b) for a, b in zip(ts, ts[1:])]
    at10 = day_end[19] + daily[19] * 11 // 24
    at11 = at10 + daily[19] // 24
    at12 = day_end[23] + daily[23] * 13 // 24
    at13 = at12 + daily[23] // 24
    tail = day_end[DAYS_IN_PERIOD] - at13
    tail += tail * 4 // 5
    ordinary = [Fraction(day_end[8] - day_end[0], secs[0]),
                Fraction(at10 - day_end[8], secs[1]),
                Fraction(at12 - at11, secs[3])]
    lower, upper = max(ordinary), Fraction(tail, secs[5])
    median = (lower + upper) / 2
    spike_a = math.floor(10 * (lower + median) * secs[2])
    spike_b = math.floor(10 * (median + upper) * secs[4])
    assert lower < upper and 20 * lower < Fraction(spike_a, secs[2]) < 20 * median
    assert 20 * median < Fraction(spike_b, secs[4]) < 20 * upper
    off_a = at10 + spike_a - at11
    r4 = at12 + off_a
    r5 = r4 + spike_b
    return [(ts[1], day_end[8]), (ts[2], at10), (ts[3], at10 + spike_a),
            (ts[4], r4), (ts[5], r5), (ts[6], r5 + tail)]


def generate_meter_reads(seed: int, tickets: list[dict]) -> list[dict]:
    """Cumulative register reads per customer channel.

    Every channel gets an opening read on 2025-09-30T23:00 and a closing read
    on 2025-10-31T23:00, with day-end registers built from seeded daily
    consumption. A few customers carry a fixed data-quality situation that
    every extract repeats (§15.2 - §15.4); only the quantities vary by seed.
    """
    rng = RNG(seed ^ 0xDEADBEEF)
    rows: list[dict] = []
    for c in CUSTOMERS:
        cid = c["customer_id"]
        meter_class = c["meter_class"]
        max_reg = _customer_max_register_kwhth(meter_class)
        n_ch = _premise_channels(c)
        for ch in range(1, n_ch + 1):
            base = CUSTOMER_DAILY_KWHTH[cid]
            if n_ch > 1:
                base = base * CHANNEL_SPLIT_PCT[ch - 1] // 100
            daily = [_daily_kwhth(base, rng) for _ in range(DAYS_IN_PERIOD)]
            if cid == "C0005":
                # The wrap always lands between the Oct 15 read and the close
                # (15 days stay under 200 kWh, 31 days always exceed 300 kWh).
                start = max_reg - rng.randint(200_000, 300_000)
            elif meter_class == "mech5":
                start = max_reg - rng.randint(150_000, 250_000)
            else:
                start = CUSTOMER_START_REG_KWHTH[cid] // ch
            # day_end[k] = unwrapped register at 23:00 on Oct k (k=0: Sep 30).
            day_end = [start]
            for k in range(DAYS_IN_PERIOD):
                day_end.append(day_end[-1] + daily[k])
            reads: list[tuple[str, int]] = [("2025-09-30T23:00:00", start)]
            if meter_class == "mech5":
                reads.append(("2025-10-15T23:00:00", day_end[15]))
            if cid == "C0012":
                reads.extend(_even_median_spike_reads(day_end, daily))
                closing = reads.pop()[1]
            else:
                closing = day_end[DAYS_IN_PERIOD]
            reads.append(("2025-10-31T23:00:00", closing))
            if cid == "C0001":
                # §15.4 missing start: the first read after the move-in.
                reads = [("2025-10-12T23:00:00", day_end[12])] + reads[1:]
            if cid == "C0017" and ch == 2:
                # Only channel 2 lacks an opening boundary; channel 1 remains
                # complete, and the customer-level flag must still count once.
                reads = [("2025-10-12T23:00:00", day_end[12])] + reads[1:]
            if cid == "C0008":
                # §15.4 missing end: the closing read was never taken.
                reads = reads[:-1]
            if cid == "C0010":
                # §15.3 duplicate closing timestamp, the lower value first.
                reads.insert(len(reads) - 1, ("2025-10-31T23:00:00", closing - 1_500))
            if cid == "C0005":
                # §15.3 duplicate closing timestamp across the wrap: a stuck
                # pre-wrap 99999.998 read follows the true post-wrap read.
                # Only the rollover-aware rule keeps the true one; keeping
                # the numerically highest, or the last row, keeps the stuck one.
                reads.append(("2025-10-31T23:00:00", max_reg - 1))
            for ts, reg in reads:
                rows.append({"customer_id": cid, "channel": ch, "read_timestamp": ts,
                             "register_reading_kwh": _fmt_th(reg % (max_reg + 1))})
    # §15.1: one read for a customer_id absent from customers.csv. It is
    # counted in meter_read_count and dropped from every bill.
    orphan_rng = RNG(seed ^ 0x0BADF00D)
    rows.append({"customer_id": ORPHAN_CUSTOMER_ID, "channel": 1,
                 "read_timestamp": f"2025-10-{orphan_rng.randint(2, 28):02d}T{orphan_rng.randint(0, 23):02d}:00:00",
                 "register_reading_kwh": _fmt_th(orphan_rng.randint(1_000_000, 90_000_000))})
    for i, r in enumerate(rows, 1):
        r["read_id"] = f"MR-{i:06d}"
    return rows


def generate_demand_intervals(seed: int, tickets: list[dict]) -> list[dict]:
    """30-minute demand rows per channel for COM and IND customers.

    On the DST fall-back day the second occurrence of the 01:00 hour is
    stamped with the §3.12 `T25:00:00` / `T25:30:00` sentinels.
    """
    rng = RNG(seed ^ 0xCAFEBABE)
    rows: list[dict] = []
    for c in CUSTOMERS:
        if c["rate_class"] == "RES":
            continue
        cid = c["customer_id"]
        n_ch = _premise_channels(c)
        base_kw_th = CUSTOMER_DAILY_KWHTH[cid] // 24  # thousandths of a kW
        peak_day = rng.randint(1, 25)
        peak_hour = rng.randint(13, 17)
        peak_extra = rng.randint(4000, 12000)
        for ch in range(1, n_ch + 1):
            ch_base = base_kw_th
            if n_ch > 1:
                ch_base = base_kw_th * CHANNEL_SPLIT_PCT[ch - 1] // 100
            d = PERIOD_START
            while d <= PERIOD_END:
                for h in range(24):
                    stamps = [f"{h:02d}"]
                    if d == DST_FALLBACK_DATE and h == 1:
                        stamps.append("25")
                    for hh in stamps:
                        for m in (0, 30):
                            kw = ch_base + rng.randint(-500, 500)
                            if ch == 1 and hh != "25" and d.day == peak_day and h == peak_hour and m == 0:
                                kw = ch_base + peak_extra
                            rows.append({"customer_id": cid, "channel": ch,
                                         "interval_start": f"{d.isoformat()}T{hh}:{m:02d}:00",
                                         "demand_kw": _fmt_th(max(kw, 0))})
                d += timedelta(days=1)
    # §15.1: one interval for a customer_id absent from customers.csv, set
    # above every real customer's demand so a decoder that keeps it is visible.
    orphan_rng = RNG(seed ^ 0x0DEFACED)
    rows.append({"customer_id": ORPHAN_CUSTOMER_ID, "channel": 1,
                 "interval_start": f"2025-10-{orphan_rng.randint(2, 28):02d}T{orphan_rng.randint(0, 23):02d}:{30 * orphan_rng.randint(0, 1):02d}:00",
                 "demand_kw": _fmt_th(orphan_rng.randint(5_000_000, 6_000_000))})
    for r in rows:
        for ts, kw in DEMAND_TRAPS.get(r["customer_id"], []):
            if r["interval_start"] == ts and r["channel"] == 1:
                r["demand_kw"] = kw
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Section 5 - CSV / JSON writers for environment/data
# ─────────────────────────────────────────────────────────────────────────────

def _csv_dump(rows: list[dict], header: list[str]) -> str:
    out = io.StringIO()
    out.write(",".join(header) + "\n")
    for r in rows:
        vals = []
        for h in header:
            v = r[h]
            if isinstance(v, bool):
                vals.append("true" if v else "false")
            else:
                vals.append(str(v))
        out.write(",".join(vals) + "\n")
    return out.getvalue()


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_reference_tables(env_dir: Path, tables: dict[str, Any] | None = None) -> None:
    tables = _base_reference_tables() if tables is None else tables
    data_dir = env_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    by_id = {c["customer_id"]: c for c in tables["customers"]}
    (data_dir / "customers.csv").write_text(_csv_dump(
        [by_id[cid] for cid in tables["customer_order"]],
        ["customer_id", "name", "rate_class", "premise_code", "meter_class",
         "billing_currency", "grandfather_flag", "grandfather_date",
         "grandfather_expires_on", "solar_enrolled", "fiscal_group"]),
        encoding="utf-8")
    (data_dir / "premises.csv").write_text(_csv_dump(
        tables["premises"],
        ["premise_code", "street", "city", "region", "latitude", "longitude",
         "meter_channel_count", "altitude_bracket"]),
        encoding="utf-8")
    (data_dir / "tariff_schedule.csv").write_text(_csv_dump(
        tables["tariff"],
        ["schedule_id", "rate_class", "tou_period", "effective_from",
         "effective_until", "energy_rate_mrcc_per_kwh",
         "demand_rate_mrcc_per_kw", "customer_charge_mrcc",
         "order_of_precedence"]),
        encoding="utf-8")
    (data_dir / "fac_index.csv").write_text(_csv_dump(
        tables["fac"], ["month", "fac_mrcc_per_kwh"]), encoding="utf-8")
    _write_json(data_dir / "holiday_calendar.json", tables["holidays"])
    _write_json(data_dir / "dst_calendar.json", tables["dst"])
    _write_json(data_dir / "currency_rates.json", tables["currency"])
    _write_json(data_dir / "regulator_orders.json", tables["orders"])
    (data_dir / "net_metering_bank.csv").write_text(_csv_dump(
        tables["nmb"],
        ["customer_id", "balance_kwh_start_of_period", "last_true_up_date"]),
        encoding="utf-8")


def _write_transactions(env_dir: Path, seed: int) -> None:
    data_dir = env_dir / "data"
    tickets = generate_service_tickets(seed)
    _write_json(data_dir / "service_tickets.json", tickets)
    reads = generate_meter_reads(seed, tickets)
    (data_dir / "meter_reads.csv").write_text(_csv_dump(
        reads,
        ["read_id", "customer_id", "channel", "read_timestamp",
         "register_reading_kwh"]),
        encoding="utf-8")
    intervals = generate_demand_intervals(seed, tickets)
    (data_dir / "demand_intervals.csv").write_text(_csv_dump(
        intervals,
        ["customer_id", "channel", "interval_start", "demand_kw"]),
        encoding="utf-8")


def _write_corpus(env_dir: Path) -> None:
    """Authoring entry point: write reference tables + SAMPLE_SEED transactions."""
    _write_reference_tables(env_dir, _profile_tables("SAMPLE"))
    _write_transactions(env_dir, SAMPLE_SEED)


# ─────────────────────────────────────────────────────────────────────────────
# Section 6 - reference reconciler (function-and-dict style, exact arithmetic)
# ─────────────────────────────────────────────────────────────────────────────

# Every intermediate billing quantity is an exact Fraction (thousandths of a
# kWh, or mrcc times 1000). Each customer-level target is rounded half-up once
# where §13 / §14 names it; rollups sum the published customer integers
# without re-rounding (DS-24: independent of solution/solve.py).


def _lookup_currency(rates: list[dict], on_date: date) -> int:
    """§3.7 last-known-good MRC-per-FTU on or before `on_date`."""
    best = None
    for r in sorted(rates, key=lambda r: r["date"]):
        if date.fromisoformat(r["date"]) <= on_date:
            best = int(r["mrc_per_ftu"])
    if best is None:
        best = int(min(rates, key=lambda r: r["date"])["mrc_per_ftu"])
    return best


def _rate_row(tariff: list[dict], rate_class: str, tou_period: str, on_date: date,
              precedence_ceiling: int | None = None) -> dict | None:
    """Highest-precedence row for (class, tou_period) covering on_date,
    ignoring rows above precedence_ceiling when one is given."""
    best = None
    for row in tariff:
        if row["rate_class"] != rate_class or row["tou_period"] != tou_period:
            continue
        efrom = date.fromisoformat(row["effective_from"])
        eend = date.fromisoformat(row["effective_until"]) if row["effective_until"] else date(9999, 12, 31)
        if not (efrom <= on_date <= eend):
            continue
        op = int(row["order_of_precedence"])
        if precedence_ceiling is not None and op > precedence_ceiling:
            continue
        if best is None or op > int(best["order_of_precedence"]):
            best = row
    return best


def _fac_for_month(fac: list[dict], year_month: str) -> int:
    for row in fac:
        if row["month"] == year_month:
            return int(row["fac_mrcc_per_kwh"])
    return 0


def _holidays_by_treatment(holidays: list[dict]) -> tuple[set[date], set[date]]:
    off, wk = set(), set()
    for h in holidays:
        d = date.fromisoformat(h["date"])
        if h["tou_treatment"] == "off":
            off.add(d)
        elif h["tou_treatment"] == "weekend":
            wk.add(d)
    return off, wk


def _service_window(customer_id: str, tickets: list[dict]) -> tuple[date, date]:
    start, end = PERIOD_START, PERIOD_END
    for t in tickets:
        if t["customer_id"] != customer_id:
            continue
        dv = date.fromisoformat(t["effective_date"])
        if t["event_type"] == "move_in" and dv > start:
            start = dv
        elif t["event_type"] == "move_out" and dv < end:
            end = dv
    return start, end


def _hour_slots(t_a: datetime, t_b: datetime) -> list[tuple[date, int, bool, int]]:
    """Civil hours overlapped by [t_a, t_b) as (date, hour, is_repeat, seconds).
    The fall-back 01:00 hour is lived twice, so it is emitted twice (§4)."""
    slots = []
    h = t_a.replace(minute=0, second=0, microsecond=0)
    while h < t_b:
        secs = int((min(h + timedelta(hours=1), t_b) - max(h, t_a)).total_seconds())
        if secs > 0:
            slots.append((h.date(), h.hour, False, secs))
            if h == FALLBACK_HOUR_START:
                slots.append((h.date(), h.hour, True, secs))
        h += timedelta(hours=1)
    return slots


def _forward_th(r_a: int, r_b: int, max_reg: int) -> int:
    """§4.1 rollover-aware register delta in thousandths."""
    return r_b - r_a if r_b >= r_a else (max_reg + 1) - r_a + r_b


def _channel_reads(reads: list[dict], customer_id: str, channel: int,
                   max_reg: int) -> tuple[list[tuple[datetime, int]], int]:
    """Sorted retained reads for one channel and the §15.3 duplicate count."""
    by_ts: dict[str, list[int]] = defaultdict(list)
    for r in reads:
        if r["customer_id"] == customer_id and int(r["channel"]) == channel:
            by_ts[r["read_timestamp"]].append(_parse_kwh(r["register_reading_kwh"]))
    kept: list[tuple[datetime, int]] = []
    duplicates = 0
    for ts in sorted(by_ts):
        values = by_ts[ts]
        duplicates += len(values) - 1
        if kept:
            prev = kept[-1][1]
            value = max(values, key=lambda v: _forward_th(prev, v, max_reg))
        else:
            value = max(values)
        kept.append((datetime.fromisoformat(ts), value))
    return kept, duplicates


def _median(values: list[Fraction]) -> Fraction:
    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        return ordered[n // 2]
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def _channel_consumption(kept: list[tuple[datetime, int]], max_reg: int,
                         service_start: date, service_end: date) -> dict[str, Any]:
    """§4 / §15.2 / §15.4 for one channel: exact kWh per civil hour inside the
    service window, the boundary flags, and the high-variance count."""
    win_lo = datetime.combine(service_start, time(0, 0))
    win_hi = datetime.combine(service_end + timedelta(days=1), time(0, 0))
    hourly: dict[tuple[date, int, bool], Fraction] = defaultdict(Fraction)

    def spread(slots: list[tuple[date, int, bool, int]], per_second: Fraction) -> None:
        for d, h, rep, secs in slots:
            if service_start <= d <= service_end:
                hourly[(d, h, rep)] += per_second * secs

    gaps: list[Fraction] = []
    for (t_a, r_a), (t_b, r_b) in zip(kept, kept[1:]):
        slots = _hour_slots(t_a, t_b)
        total = sum(s[3] for s in slots)
        if total <= 0:
            continue
        rate = Fraction(_forward_th(r_a, r_b, max_reg), total)
        gaps.append(rate)
        spread(slots, rate)

    missing_start = not any(t.date() <= service_start for t, _ in kept)
    missing_end = not any(t.date() >= service_end for t, _ in kept)
    if gaps and missing_start and win_lo < kept[0][0]:
        spread(_hour_slots(win_lo, kept[0][0]), gaps[0])
    if gaps and missing_end and kept[-1][0] < win_hi:
        spread(_hour_slots(kept[-1][0], win_hi), gaps[-1])

    high_variance = 0
    if gaps:
        threshold = 20 * _median(gaps)
        high_variance = sum(1 for g in gaps if g > threshold)
    return {"hourly": hourly, "missing_start": missing_start,
            "missing_end": missing_end, "high_variance": high_variance}


def _pick_ddc(intervals: list[dict], customer_id: str, service_start: date,
              service_end: date, holidays_off: set[date]) -> tuple[Decimal, str] | None:
    """§6: channels summed per interval_start, holiday_off dates dropped, the
    maximum taken, exact ties going to the later interval_start string."""
    summed: dict[str, Decimal] = defaultdict(Decimal)
    for row in intervals:
        if row["customer_id"] != customer_id:
            continue
        iv = row["interval_start"]
        d = date.fromisoformat(iv.split("T")[0])
        if not (service_start <= d <= service_end) or d in holidays_off:
            continue
        summed[iv] += Decimal(row["demand_kw"])
    if not summed:
        return None
    top = max(summed.values())
    latest = max(iv for iv, kw in summed.items() if kw == top)
    return top, latest


def _customer_bill(customer: dict, premises: list[dict], tariff: list[dict], fac: list[dict],
                   holidays_off: set[date], holidays_weekend: set[date],
                   currency: dict, orders: list[dict], nmb_map: dict[str, dict],
                   tickets: list[dict], reads: list[dict], intervals: list[dict]) -> dict:
    """Return a bill dict for a single customer."""
    cid = customer["customer_id"]
    base_class = customer["rate_class"]
    max_reg = _customer_max_register_kwhth(customer["meter_class"])
    service_start, service_end = _service_window(cid, tickets)

    migration = next((t for t in tickets if t["customer_id"] == cid
                      and t["event_type"] == "rate_class_migration"), None)
    migration_date = date.fromisoformat(migration["effective_date"]) if migration else None

    grandfathered = bool(customer["grandfather_flag"] and customer["grandfather_date"])
    gexp: date | None = None
    if grandfathered:
        if customer["grandfather_expires_on"]:
            gexp = date.fromisoformat(customer["grandfather_expires_on"])
        if migration_date is not None and (gexp is None or migration_date < gexp):
            gexp = migration_date  # §9: a migration breaks the freeze

    def class_on(d: date) -> str:
        if migration_date is not None and d >= migration_date:
            return migration["new_rate_class"]
        return base_class

    def lookup(d: date) -> tuple[date, int | None]:
        if grandfathered and (gexp is None or d < gexp):
            return date.fromisoformat(customer["grandfather_date"]), 10
        return d, None

    # §4 consumption, channel by channel, summed per civil hour.
    hourly: dict[tuple[date, int, bool], Fraction] = defaultdict(Fraction)
    dq = {"missing_start": False, "missing_end": False, "duplicates": 0, "high_variance": 0}
    for ch in range(1, _premise_channels(customer, premises) + 1):
        kept, dups = _channel_reads(reads, cid, ch, max_reg)
        dq["duplicates"] += dups
        if not kept:
            dq["missing_start"] = dq["missing_end"] = True
            continue
        res = _channel_consumption(kept, max_reg, service_start, service_end)
        for k, v in res["hourly"].items():
            hourly[k] += v
        dq["missing_start"] = dq["missing_start"] or res["missing_start"]
        dq["missing_end"] = dq["missing_end"] or res["missing_end"]
        dq["high_variance"] += res["high_variance"]

    # §5 bucketing and per-label energy value (kWh-thousandths times rate).
    kwh = {lab: Fraction(0) for lab in LABELS}
    value = {lab: Fraction(0) for lab in LABELS}
    for (d, h, rep), q in hourly.items():
        rc = class_on(d)
        lab = _label_civil_hour(rc, d, h, rep, holidays_off, holidays_weekend)
        ld, ceiling = lookup(d)
        row = _rate_row(tariff, rc, lab, ld, ceiling)
        kwh[lab] += q
        if row is not None:
            value[lab] += q * int(row["energy_rate_mrcc_per_kwh"])
    original_kwh = dict(kwh)
    energy_kwh = round_half_up(sum(kwh.values()))

    # §7.3 net-metering draw, peak first; a label's value shrinks in proportion.
    nmb_start = 0
    if customer["solar_enrolled"] and cid in nmb_map:
        nmb_start = int(nmb_map[cid]["balance_kwh_start_of_period"])
    remaining = Fraction(max(0, nmb_start))
    for lab in LABELS:
        if kwh[lab] <= 0 or remaining <= 0:
            continue
        take = min(remaining, kwh[lab])
        value[lab] = value[lab] * (kwh[lab] - take) / kwh[lab]
        kwh[lab] -= take
        remaining -= take
    energy_mrcc = sum(round_half_up(value[lab] / 1000) for lab in LABELS)
    chargeable = sum(kwh.values())
    fac_mrcc = round_half_up(chargeable * _fac_for_month(fac, "2025-10") / 1000)

    # §7.2 fiscal true-up fires on every solar bill, move-out or not, using
    # the class held when the true-up occurs.
    payout = forfeited = 0
    if customer["solar_enrolled"] and remaining > 0:
        if class_on(PERIOD_END) == "RES":
            payout = round_half_up(remaining * 4 / 1000)
        else:
            forfeited = round_half_up(remaining)

    # §9 / §10 / §3.10 customer charge, prorated by service days, rounded once.
    bounds = {service_start, service_end + timedelta(days=1)}
    for cut in (gexp, migration_date):
        if cut is not None and service_start < cut <= service_end:
            bounds.add(cut)
    cuts = sorted(bounds)
    charge_exact = Fraction(0)
    for seg_a, seg_b in zip(cuts, cuts[1:]):
        ld, ceiling = lookup(seg_a)
        row = _rate_row(tariff, class_on(seg_a), "*", ld, ceiling)
        if row is not None:
            charge_exact += Fraction(int(row["customer_charge_mrcc"]) * (seg_b - seg_a).days,
                                     DAYS_IN_PERIOD)
    customer_charge = round_half_up(charge_exact)

    # §6 demand charge at the schedule in force on the DDC interval's date.
    pick = _pick_ddc(intervals, cid, service_start, service_end, holidays_off)
    demand_mrcc = 0
    if pick is not None:
        ddc_kw, ddc_ts = pick
        ddc_date = date.fromisoformat(ddc_ts.split("T")[0])
        ld, ceiling = lookup(ddc_date)
        row = _rate_row(tariff, class_on(ddc_date), "*", ld, ceiling)
        if row is not None:
            demand_mrcc = round_half_up(Fraction(ddc_kw) * int(row["demand_rate_mrcc_per_kw"]))

    # §11 retroactive orders on assumed-prior quantities.
    retro_lines: list[dict] = []
    for order in orders:
        if order["scope"] != "retroactive":
            continue
        superseded = next((r for r in tariff if r["schedule_id"] == order["supersedes_schedule_id"]), None)
        new_row = next((r for r in tariff if r["schedule_id"] == order["new_schedule_id"]), None)
        if superseded is None or new_row is None:
            continue
        aff_class = superseded["rate_class"]
        if base_class != aff_class:
            continue
        if grandfathered and not order["grandfather_immune"]:
            continue
        o_start = date.fromisoformat(order["period_start"])
        o_days = (date.fromisoformat(order["period_end"]) - o_start).days + 1
        adjustment = 0
        for lab in LABELS:
            if original_kwh[lab] <= 0:
                continue
            prior = original_kwh[lab] * o_days / DAYS_IN_PERIOD
            old = _rate_row(tariff, aff_class, lab, o_start, 10)
            new = _rate_row(tariff, aff_class, lab, o_start, None)
            if old is not None and new is not None:
                adjustment += (round_half_up(prior * int(new["energy_rate_mrcc_per_kwh"]) / 1000)
                               - round_half_up(prior * int(old["energy_rate_mrcc_per_kwh"]) / 1000))
        if pick is not None:
            old = _rate_row(tariff, aff_class, "*", o_start, 10)
            new = _rate_row(tariff, aff_class, "*", o_start, None)
            if old is not None and new is not None:
                adjustment += (round_half_up(Fraction(pick[0]) * int(new["demand_rate_mrcc_per_kw"]))
                               - round_half_up(Fraction(pick[0]) * int(old["demand_rate_mrcc_per_kw"])))
        if adjustment != 0:
            retro_lines.append({"adjustment_mrcc": adjustment, "customer_id": cid,
                                "order_id": order["order_id"], "_period_start": o_start})
    retro_total = sum(line["adjustment_mrcc"] for line in retro_lines)

    bill_mrcc = energy_mrcc + demand_mrcc + customer_charge + fac_mrcc + retro_total - payout
    bill_ftuc = 0
    if customer["billing_currency"] == "FTU":
        # §12: the current bill at the period-start rate, each retroactive
        # line at the rate on the first date of the period it rebills.
        rates = currency["rates"]
        bill_ftuc = round_half_up(Fraction((bill_mrcc - retro_total) * 100,
                                           _lookup_currency(rates, PERIOD_START)))
        for line in retro_lines:
            bill_ftuc += round_half_up(Fraction(line["adjustment_mrcc"] * 100,
                                                _lookup_currency(rates, line["_period_start"])))
        bill_mrcc = 0

    return {
        "customer_id": cid,
        "premise_code": customer["premise_code"],
        "rate_class": base_class,
        "energy_kwh": energy_kwh,
        "energy_charge_mrcc": energy_mrcc,
        "demand_charge_mrcc": demand_mrcc,
        "customer_charge_mrcc": customer_charge,
        "fac_mrcc": fac_mrcc,
        "net_metering": {
            "avoided_cost_payout_mrcc": payout,
            "credit_kwh_carried_forward": 0,
            "forfeited_kwh": forfeited,
        },
        "retroactive_adjustment_mrcc": retro_total,
        "_retroactive_adjustments": [{k: v for k, v in line.items() if not k.startswith("_")}
                                     for line in retro_lines],
        "bill_total_mrcc": bill_mrcc,
        "bill_total_ftuc": bill_ftuc,
        "_grandfather_applied": None if not grandfathered else {
            "customer_id": cid,
            "expires_on": customer["grandfather_expires_on"],
            "grandfather_date": customer["grandfather_date"],
            "prorata_split_at": gexp.isoformat() if (gexp and PERIOD_START < gexp <= PERIOD_END) else None,
        },
        "_migration": None if migration is None else {
            "customer_id": cid,
            "from_class": base_class,
            "migration_date": migration["effective_date"],
            "to_class": migration["new_rate_class"],
        },
        "_dq": dq,
    }


def _read_csv(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    header = lines[0].split(",")
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        while len(parts) < len(header):
            parts.append("")
        out.append(dict(zip(header, parts)))
    return out


def _load_reference_tables(data_dir: Path) -> dict[str, Any]:
    customers = _read_csv(data_dir / "customers.csv")
    for row in customers:
        row["grandfather_flag"] = row["grandfather_flag"].lower() == "true"
        row["solar_enrolled"] = row["solar_enrolled"].lower() == "true"
    premises = _read_csv(data_dir / "premises.csv")
    for row in premises:
        row["meter_channel_count"] = int(row["meter_channel_count"])
    tariff = _read_csv(data_dir / "tariff_schedule.csv")
    for row in tariff:
        for key in ("energy_rate_mrcc_per_kwh", "demand_rate_mrcc_per_kw",
                    "customer_charge_mrcc", "order_of_precedence"):
            row[key] = int(row[key])
    fac = _read_csv(data_dir / "fac_index.csv")
    for row in fac:
        row["fac_mrcc_per_kwh"] = int(row["fac_mrcc_per_kwh"])
    nmb = _read_csv(data_dir / "net_metering_bank.csv")
    for row in nmb:
        row["balance_kwh_start_of_period"] = int(row["balance_kwh_start_of_period"])
    return {
        "customers": customers,
        "premises": premises,
        "tariff": tariff,
        "fac": fac,
        "holidays": json.loads((data_dir / "holiday_calendar.json").read_text(encoding="utf-8")),
        "dst": json.loads((data_dir / "dst_calendar.json").read_text(encoding="utf-8")),
        "currency": json.loads((data_dir / "currency_rates.json").read_text(encoding="utf-8")),
        "orders": json.loads((data_dir / "regulator_orders.json").read_text(encoding="utf-8")),
        "nmb": nmb,
    }


def _premise_sort_key(pc: str) -> int:
    m = re.match(r"P(\d+)", pc)
    return int(m.group(1)) if m else 0


_ENTRY_KEYS = ("bill_total_ftuc", "bill_total_mrcc", "customer_charge_mrcc", "customer_id",
               "demand_charge_mrcc", "energy_charge_mrcc", "energy_kwh", "fac_mrcc",
               "net_metering", "premise_code", "retroactive_adjustment_mrcc")


def _rollup(bills: list[dict]) -> dict:
    """§14.1 top-level metrics; used both at corpus level and per scope."""
    return {
        "bill_total_ftuc": sum(b["bill_total_ftuc"] for b in bills),
        "bill_total_mrcc": sum(b["bill_total_mrcc"] for b in bills),
        "customer_charge_mrcc_total": sum(b["customer_charge_mrcc"] for b in bills),
        "customer_count": len(bills),
        "demand_charge_mrcc_total": sum(b["demand_charge_mrcc"] for b in bills),
        "energy_charge_mrcc_total": sum(b["energy_charge_mrcc"] for b in bills),
        "energy_kwh_total": sum(b["energy_kwh"] for b in bills),
        "fac_mrcc_total": sum(b["fac_mrcc"] for b in bills),
        "net_metering_avoided_cost_payout_mrcc_total": sum(b["net_metering"]["avoided_cost_payout_mrcc"] for b in bills),
        "net_metering_credit_kwh_carried_forward_total": sum(b["net_metering"]["credit_kwh_carried_forward"] for b in bills),
        "net_metering_forfeited_kwh_total": sum(b["net_metering"]["forfeited_kwh"] for b in bills),
        "period": {"civil_days": 31, "civil_hours": 745, "end": "2025-10-31", "start": "2025-10-01"},
        "retroactive_adjustment_mrcc_total": sum(b["retroactive_adjustment_mrcc"] for b in bills),
    }


def _rollup_with_customers(bills: list[dict]) -> dict:
    out = _rollup(bills)
    out["customers"] = sorted(({k: copy.deepcopy(b[k]) for k in _ENTRY_KEYS} for b in bills),
                              key=lambda e: _premise_sort_key(e["premise_code"]))
    return out


def _reference_reconcile(data_dir: Path) -> dict[str, Any]:
    """Compute all nine JSON artifacts from a data_dir. Returns name -> obj."""
    tables = _load_reference_tables(data_dir)
    tickets = json.loads((data_dir / "service_tickets.json").read_text(encoding="utf-8"))
    reads = _read_csv(data_dir / "meter_reads.csv")
    intervals = _read_csv(data_dir / "demand_intervals.csv")
    holidays_off, holidays_weekend = _holidays_by_treatment(tables["holidays"])
    nmb_map = {r["customer_id"]: r for r in tables["nmb"]}
    valid_premises = {p["premise_code"] for p in tables["premises"]}
    valid_customers = [c for c in tables["customers"] if c["premise_code"] in valid_premises]
    valid_customer_ids = {c["customer_id"] for c in valid_customers}
    bills = [_customer_bill(c, tables["premises"], tables["tariff"], tables["fac"],
                             holidays_off, holidays_weekend, tables["currency"],
                             tables["orders"], nmb_map, tickets, reads, intervals)
             for c in valid_customers]

    art: dict[str, Any] = {"summary.json": _rollup(bills)}
    for rc, key in (("RES", "rate_class_residential.json"), ("COM", "rate_class_commercial.json"),
                    ("IND", "rate_class_industrial.json")):
        art[key] = _rollup_with_customers([b for b in bills if b["rate_class"] == rc])
    region_of = {p["premise_code"]: p["region"] for p in tables["premises"]}
    for region in ("Meridian_North", "Meridian_South", "Meridian_East"):
        art[f"region_{region.lower()}.json"] = _rollup_with_customers(
            [b for b in bills if region_of[b["premise_code"]] == region])

    retro_lines = sorted((line for b in bills for line in b["_retroactive_adjustments"]),
                         key=lambda e: (e["order_id"], e["customer_id"]))
    fallbacks = [row for row in tables["dst"]["fall_back"]
                 if PERIOD_START <= date.fromisoformat(row["date"]) <= PERIOD_END]
    fallback_date = date.fromisoformat(fallbacks[0]["date"])
    art["policy_audit.json"] = {
        "dst_cutover_applied": {"civil_hours_in_day": 25, "date": fallback_date.isoformat()},
        "grandfather_applied": sorted((b["_grandfather_applied"] for b in bills if b["_grandfather_applied"]),
                                      key=lambda e: e["customer_id"]),
        "holiday_reclassifications": sorted(
            ({"date": h["date"], "name": h["name"], "tou_treatment": h["tou_treatment"]}
             for h in tables["holidays"]), key=lambda e: e["date"]),
        "rate_class_migrations": sorted((b["_migration"] for b in bills if b["_migration"]),
                                        key=lambda e: e["customer_id"]),
        "retroactive_orders_applied": retro_lines,
    }

    def count(event: str) -> int:
        return sum(1 for t in tickets
                   if t["customer_id"] in valid_customer_ids and t["event_type"] == event)

    art["data_quality.json"] = {
        "customers_with_missing_read_at_service_end": sum(1 for b in bills if b["_dq"]["missing_end"]),
        "customers_with_missing_read_at_service_start": sum(1 for b in bills if b["_dq"]["missing_start"]),
        "customers_with_negative_nmb_start": sum(
            1 for r in tables["nmb"] if int(r["balance_kwh_start_of_period"]) < 0),
        "demand_interval_count": len(intervals),
        "duplicate_read_timestamps_flagged": sum(b["_dq"]["duplicates"] for b in bills),
        "high_variance_reads_flagged": sum(b["_dq"]["high_variance"] for b in bills),
        "meter_read_count": len(reads),
        "regulator_orders_active_this_period": sum(
            1 for o in tables["orders"]
            if o["scope"] == "retroactive"
            or (o["scope"] == "forward_only" and date.fromisoformat(o["effective_on"]) <= PERIOD_END)),
        "regulator_orders_out_of_period_declared": sum(
            1 for o in tables["orders"]
            if o["scope"] == "forward_only" and date.fromisoformat(o["effective_on"]) > PERIOD_END),
        "service_tickets_by_type": {"move_in": count("move_in"), "move_out": count("move_out"),
                                    "rate_class_migration": count("rate_class_migration")},
    }
    return art


# ─────────────────────────────────────────────────────────────────────────────
# Section 7 - verifier checks
# ─────────────────────────────────────────────────────────────────────────────

ARTIFACT_NAMES = [
    "summary.json",
    "rate_class_residential.json",
    "rate_class_commercial.json",
    "rate_class_industrial.json",
    "region_meridian_north.json",
    "region_meridian_south.json",
    "region_meridian_east.json",
    "policy_audit.json",
    "data_quality.json",
]

ROLLUP_NAMES = ARTIFACT_NAMES[1:7]

_REFERENCE_CACHE: dict[str, dict[str, Any]] = {}
_SESSION_CACHE: dict[str, tuple[dict[str, Any] | None, str]] = {}
_ONESHOT_CACHE: dict[tuple[str, str], tuple[dict[str, Any] | None, str]] = {}
# rewardkit runs checks in parallel threads; the locks make each cache entry
# be computed exactly once instead of once per concurrent caller.
_REFERENCE_LOCK = threading.Lock()
_AGENT_LOCK = threading.Lock()
_STRAY_WRITES: set[str] = set()
_RUN_STATE_LOCK = threading.Lock()


def _out_dir(workspace: Path) -> Path:
    return Path(workspace) / "out"


def _reconcile_source(workspace: Path) -> Path:
    return _out_dir(workspace) / "reconcile.py"


def _load_out(workspace: Path, name: str) -> Any:
    return json.loads((_out_dir(workspace) / name).read_text(encoding="utf-8"))


def _materialise_extract(root: Path, profile: str) -> Path:
    env_dir = root / "env"
    _write_reference_tables(env_dir, _profile_tables(profile))
    _write_transactions(env_dir, PROFILE_SEEDS[profile])
    return env_dir / "data"


def _reference_for_profile(profile: str) -> dict[str, Any]:
    with _REFERENCE_LOCK:
        if profile not in _REFERENCE_CACHE:
            with tempfile.TemporaryDirectory() as td:
                _REFERENCE_CACHE[profile] = _reference_reconcile(
                    _materialise_extract(Path(td), profile))
        return copy.deepcopy(_REFERENCE_CACHE[profile])


def _shipped_reference_outputs() -> dict[str, Any]:
    return _reference_for_profile("SAMPLE")


def _snapshot_run_user_paths(out_dir: Path) -> dict[str, tuple[int, int, int, int]]:
    uid = pwd.getpwnam("nobody").pw_uid
    allowed = os.path.realpath(out_dir)
    roots = {os.path.realpath(path) for path in (
        tempfile.gettempdir(), "/tmp", "/var/tmp", "/dev/shm", "/dev/mqueue", "/run/lock")}
    snapshot: dict[str, tuple[int, int, int, int]] = {}
    for root in sorted(roots):
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _error: None):
            dirnames[:] = [
                name for name in dirnames
                if not os.path.commonpath((os.path.realpath(os.path.join(dirpath, name)), allowed))
                == allowed
            ]
            for name in dirnames + filenames:
                path = os.path.realpath(os.path.join(dirpath, name))
                if os.path.commonpath((path, allowed)) == allowed:
                    continue
                try:
                    stat = os.lstat(path)
                except OSError:
                    continue
                if stat.st_uid == uid:
                    snapshot[path] = (stat.st_mode, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return snapshot


def _record_stray_write_delta(
        before: dict[str, tuple[int, int, int, int]],
        after: dict[str, tuple[int, int, int, int]]) -> None:
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    with _RUN_STATE_LOCK:
        _STRAY_WRITES.update(changed)


def _run_agent_script(workspace: Path, data_dir: Path, out_dir: Path) -> None:
    """Run the agent's reconcile.py as the unprivileged nobody user in its own
    process group, and kill that whole group before returning, so nothing the
    script spawned outlives the check. Raises AssertionError on any failure."""
    setpriv = shutil.which("setpriv")
    if setpriv is None:
        raise AssertionError("setpriv unavailable; refusing to run agent code as root")
    for d in (data_dir, out_dir):
        cur = d
        while True:
            os.chmod(cur, 0o777 if cur == out_dir else 0o755)
            if cur.parent == Path(tempfile.gettempdir()) or cur.parent == cur:
                break
            cur = cur.parent
    for f in data_dir.iterdir():
        os.chmod(f, 0o644)
    # TS-30: an agent editor leaves reconcile.py 0600 owned by uid 1000, which
    # `nobody` cannot read, so run a verifier-owned 0644 copy. Keep the stage
    # 0755, never 0777, or the dropped uid writes a __pycache__ there and trips
    # negative_writes_outside_out_dir.
    source = _reconcile_source(workspace)
    if not source.is_file():
        raise AssertionError("reconcile.py missing")
    stage = out_dir.parent / "_verifier_program"
    stage.mkdir(parents=True, exist_ok=True)
    os.chmod(stage, 0o755)
    program = stage / "reconcile.py"
    shutil.copyfile(source, program)
    os.chmod(program, 0o644)
    cmd = [setpriv, "--reuid=nobody", "--regid=nogroup", "--init-groups", "--",
           sys.executable, str(program), str(data_dir), str(out_dir)]
    before = _snapshot_run_user_paths(out_dir)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        _, err = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        raise AssertionError("reconcile.py timed out") from None
    finally:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        if proc.returncode is None:
            proc.communicate()
        _record_stray_write_delta(before, _snapshot_run_user_paths(out_dir))
    if proc.returncode != 0:
        raise AssertionError(f"reconcile.py exited {proc.returncode}: {err[:400]}")


def _one_shot_outputs(workspace: Path, profile: str) -> dict[str, Any]:
    key = (str(workspace), profile)
    with _AGENT_LOCK:
        if key not in _ONESHOT_CACHE:
            try:
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    data_dir = _materialise_extract(root / "input", profile)
                    out_dir = root / "out"
                    out_dir.mkdir(parents=True, exist_ok=True)
                    _run_agent_script(workspace, data_dir, out_dir)
                    parsed = {
                        name: json.loads((out_dir / name).read_bytes())
                        for name in ARTIFACT_NAMES
                    }
                _ONESHOT_CACHE[key] = (parsed, "")
            except Exception as exc:
                _ONESHOT_CACHE[key] = (None, f"{type(exc).__name__}: {exc}")
        outputs, error = _ONESHOT_CACHE[key]
    if outputs is None:
        raise AssertionError(error)
    return copy.deepcopy(outputs)


def _session_outputs(workspace: Path) -> dict[str, Any]:
    key = str(workspace)
    with _AGENT_LOCK:
        _fill_session_cache(workspace, key)
    out, err = _SESSION_CACHE[key]
    if out is None:
        raise AssertionError(err)
    return copy.deepcopy(out)


def _fill_session_cache(workspace: Path, key: str) -> None:
    if key not in _SESSION_CACHE:
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                data_dirs = [
                    _materialise_extract(root / f"turn-{index}", profile)
                    for index, profile in enumerate(SESSION_SEQUENCE)
                ]
                out_dir = root / "out"
                out_dir.mkdir(parents=True, exist_ok=True)
                setpriv = shutil.which("setpriv")
                if setpriv is None:
                    raise AssertionError("setpriv unavailable; refusing to run agent code as root")
                for data_dir in data_dirs:
                    for d in (data_dir, out_dir):
                        cur = d
                        while True:
                            os.chmod(cur, 0o777 if cur == out_dir else 0o755)
                            if cur.parent == Path(tempfile.gettempdir()) or cur.parent == cur:
                                break
                            cur = cur.parent
                    for f in data_dir.iterdir():
                        os.chmod(f, 0o644)
                source = _reconcile_source(workspace)
                if not source.is_file():
                    raise AssertionError("reconcile.py missing")
                stage = root / "_verifier_program"
                stage.mkdir(parents=True, exist_ok=True)
                os.chmod(stage, 0o755)
                program = stage / "reconcile.py"
                shutil.copyfile(source, program)
                os.chmod(program, 0o644)
                cmd = [setpriv, "--reuid=nobody", "--regid=nogroup", "--init-groups", "--",
                       sys.executable, str(program), "--session", str(out_dir)]
                before = _snapshot_run_user_paths(out_dir)
                proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, start_new_session=True,
                )
                turns: list[dict[str, Any]] = []
                acks: list[Any] = []
                stderr = ""
                try:
                    assert proc.stdin is not None and proc.stdout is not None
                    for index, (profile, data_dir) in enumerate(zip(SESSION_SEQUENCE, data_dirs)):
                        turn_id = f"turn-{index + 1}-{profile.lower()}"
                        command = {"turn_id": turn_id, "data_dir": str(data_dir)}
                        proc.stdin.write(json.dumps(command, sort_keys=True) + "\n")
                        proc.stdin.flush()
                        ready, _, _ = select.select([proc.stdout], [], [], 300)
                        if not ready:
                            raise AssertionError(f"session acknowledgement timed out at {turn_id}")
                        line = proc.stdout.readline()
                        if not line:
                            raise AssertionError(f"session exited before acknowledging {turn_id}")
                        expected_ack = {"status": "ok", "turn_id": turn_id}
                        expected_line = json.dumps(
                            expected_ack, sort_keys=True, separators=(",", ":")) + "\n"
                        if line != expected_line:
                            raise AssertionError(
                                f"non-canonical acknowledgement for {turn_id}: {line[:200]!r}")
                        ack = json.loads(line)
                        if ack != expected_ack:
                            raise AssertionError(f"invalid acknowledgement for {turn_id}: {ack!r}")
                        parsed: dict[str, Any] = {}
                        raw: dict[str, bytes] = {}
                        for name in ARTIFACT_NAMES:
                            path = out_dir / name
                            if not path.is_file():
                                raise AssertionError(f"session did not emit {name} at {turn_id}")
                            raw[name] = path.read_bytes()
                            parsed[name] = json.loads(raw[name])
                        acks.append(ack)
                        turns.append({"profile": profile, "parsed": parsed, "raw": raw})
                    proc.stdin.close()
                    proc.stdin = None
                    extra_stdout, stderr = proc.communicate(timeout=30)
                    if extra_stdout.strip():
                        raise AssertionError(f"unexpected session stdout: {extra_stdout[:200]}")
                except subprocess.TimeoutExpired:
                    raise AssertionError("session did not exit after stdin EOF") from None
                finally:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(proc.pid, signal.SIGKILL)
                    if proc.returncode is None:
                        proc.communicate()
                    _record_stray_write_delta(before, _snapshot_run_user_paths(out_dir))
                if proc.returncode != 0:
                    raise AssertionError(f"session exited {proc.returncode}: {stderr[:400]}")
                result = {"acks": acks, "turns": turns}
            _SESSION_CACHE[key] = (result, "")
        except Exception as exc:  # recorded and re-raised for every caller
            _SESSION_CACHE[key] = (None, f"{type(exc).__name__}: {exc}")


def _assert_deep_equal(actual: Any, expected: Any, path: str = "") -> None:
    """Recursive strict equality (types included, so 1 never passes for true)."""
    if type(actual) is not type(expected):
        raise AssertionError(
            f"type mismatch at {path or '(root)'}: {type(actual).__name__} != {type(expected).__name__}")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"key set mismatch at {path or '(root)'}")
        for k in expected:
            _assert_deep_equal(actual[k], expected[k], f"{path}.{k}")
        return
    if isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f"list length mismatch at {path or '(root)'}")
        for i, (a, e) in enumerate(zip(actual, expected)):
            _assert_deep_equal(a, e, f"{path}[{i}]")
        return
    if actual != expected:
        raise AssertionError(f"value mismatch at {path or '(root)'}: {actual!r} != {expected!r}")


def _customers_by_id(art: Any) -> Any:
    """Order-insensitive view of a rollup's customer list: list order is
    graded once, by customer_lists_sorted_by_premise_number."""
    if isinstance(art, dict) and isinstance(art.get("customers"), list):
        art = dict(art)
        art["customers"] = sorted(art["customers"], key=lambda c: json.dumps(c.get("customer_id")
                                                                            if isinstance(c, dict) else c))
    return art


_ROLLUP_SCOPE_KEYS = ("period", "customer_count")
_ROLLUP_ENERGY_KEYS = ("energy_kwh_total", "energy_charge_mrcc_total")
_ROLLUP_USAGE_FIXED_KEYS = (
    "demand_charge_mrcc_total", "customer_charge_mrcc_total", "fac_mrcc_total")
_ROLLUP_NMB_KEYS = (
    "net_metering_avoided_cost_payout_mrcc_total",
    "net_metering_credit_kwh_carried_forward_total",
    "net_metering_forfeited_kwh_total",
)
_ROLLUP_SETTLEMENT_KEYS = (
    "retroactive_adjustment_mrcc_total", "bill_total_mrcc", "bill_total_ftuc")
_ROLLUP_ALL_TOTAL_KEYS = (
    _ROLLUP_ENERGY_KEYS + _ROLLUP_USAGE_FIXED_KEYS +
    _ROLLUP_NMB_KEYS + _ROLLUP_SETTLEMENT_KEYS)


def _assert_partition(actual: Any, expected: Any, keys: tuple[str, ...] | None,
                      path: str, own_key_set: bool = False,
                      normalize_customers: bool = False) -> None:
    if keys is None:
        _assert_deep_equal(actual, expected, path)
        return
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        raise AssertionError(f"object expected at {path}")
    if own_key_set and set(actual) != set(expected):
        raise AssertionError(f"key set mismatch at {path}")
    for key in keys:
        actual_value = actual[key]
        expected_value = expected[key]
        if normalize_customers and key == "customers":
            actual_value = _customers_by_id({"customers": actual_value})["customers"]
            expected_value = _customers_by_id({"customers": expected_value})["customers"]
        _assert_deep_equal(actual_value, expected_value, f"{path}.{key}")


def _matches_shipped_partition(workspace: Path, name: str, keys: tuple[str, ...],
                               own_key_set: bool = False,
                               normalize_customers: bool = False) -> bool:
    try:
        _assert_partition(
            _load_out(workspace, name), _shipped_reference_outputs()[name], keys, name,
            own_key_set=own_key_set, normalize_customers=normalize_customers)
        return True
    except Exception:
        return False


def _matches_shipped_partitions(
        workspace: Path, name: str,
        partitions: tuple[tuple[tuple[str, ...], bool, bool], ...]) -> float:
    try:
        actual = _load_out(workspace, name)
        expected = _shipped_reference_outputs()[name]
    except Exception:
        return 0.0
    passed = 0
    for keys, own_key_set, normalize_customers in partitions:
        try:
            _assert_partition(
                actual, expected, keys, name, own_key_set=own_key_set,
                normalize_customers=normalize_customers)
            passed += 1
        except Exception:
            continue
    return passed / len(partitions)


# ─── positive checks ──────────────────────────────────────────────────────

@criterion(description="reconcile.py exists and all nine JSON artifacts exist and parse")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    try:
        if not _reconcile_source(workspace).is_file():
            return False
        for name in ARTIFACT_NAMES:
            _load_out(workspace, name)
        return True
    except Exception:
        return False


@criterion(description="Shipped summary scope and period match the independent reference")
def shipped_summary_scope_matches(workspace: Path) -> bool:
    return _matches_shipped_partition(
        workspace, "summary.json", _ROLLUP_SCOPE_KEYS, own_key_set=True)


@criterion(description="Shipped summary energy and demand totals independently match the reference")
def shipped_summary_energy_matches(workspace: Path) -> float:
    return _matches_shipped_partitions(
        workspace, "summary.json",
        ((('energy_kwh_total',), False, False),
         (('energy_charge_mrcc_total',), False, False),
         (('demand_charge_mrcc_total',), False, False)))


@criterion(description="Shipped summary customer, FAC and net-metering totals independently match the reference")
def shipped_summary_usage_nmb_matches(workspace: Path) -> float:
    return _matches_shipped_partitions(
        workspace, "summary.json",
        ((('customer_charge_mrcc_total', 'fac_mrcc_total'), False, False),
         (('net_metering_credit_kwh_carried_forward_total',), False, False),
         (('net_metering_avoided_cost_payout_mrcc_total',
           'net_metering_forfeited_kwh_total'), False, False)))


@criterion(description="Shipped summary retroactive and bill totals independently match the reference")
def shipped_summary_settlement_matches(workspace: Path) -> float:
    return _matches_shipped_partitions(
        workspace, "summary.json",
        ((('retroactive_adjustment_mrcc_total',), False, False),
         (('bill_total_mrcc',), False, False),
         (('bill_total_ftuc',), False, False)))


@criterion(description="Shipped policy structure, DST and holiday audits independently match the reference")
def shipped_policy_calendar_matches(workspace: Path) -> float:
    return _matches_shipped_partitions(
        workspace, "policy_audit.json",
        (((), True, False),
         (('dst_cutover_applied',), False, False),
         (('holiday_reclassifications',), False, False)))


@criterion(description="Shipped policy grandfather, migration and regulator-order audits independently match the reference")
def shipped_policy_customer_order_matches(workspace: Path) -> float:
    return _matches_shipped_partitions(
        workspace, "policy_audit.json",
        ((('grandfather_applied',), False, False),
         (('rate_class_migrations',), False, False),
         (('retroactive_orders_applied',), False, False)))


@criterion(description="Shipped raw row, ticket and regulator declaration counts independently match the reference")
def shipped_data_quality_raw_declarations_match(workspace: Path) -> float:
    return _matches_shipped_partitions(
        workspace, "data_quality.json",
        ((('meter_read_count', 'demand_interval_count'), False, False),
         (('service_tickets_by_type',), False, False),
         (('regulator_orders_active_this_period',
           'regulator_orders_out_of_period_declared'), True, False)))


@criterion(description="Shipped data-quality customer and read flags match the independent reference")
def shipped_data_quality_flags_match(workspace: Path) -> bool:
    return _matches_shipped_partition(
        workspace, "data_quality.json",
        ("customers_with_missing_read_at_service_end",
         "customers_with_missing_read_at_service_start",
         "customers_with_negative_nmb_start", "duplicate_read_timestamps_flagged",
         "high_variance_reads_flagged"))


def _rollup_totals_score(workspace: Path, name: str) -> float:
    return _matches_shipped_partitions(
        workspace, name,
        ((_ROLLUP_SCOPE_KEYS, True, False),
         (_ROLLUP_ENERGY_KEYS + _ROLLUP_USAGE_FIXED_KEYS, False, False),
         (_ROLLUP_NMB_KEYS + _ROLLUP_SETTLEMENT_KEYS, False, False)))


def _customer_rows_score(workspace: Path, name: str, group_count: int) -> float:
    try:
        actual = _load_out(workspace, name)["customers"]
        expected = _shipped_reference_outputs()[name]["customers"]
        if not isinstance(actual, list) or not isinstance(expected, list):
            return 0.0
        actual_groups: list[list[Any]] = [[] for _ in range(group_count)]
        expected_groups: list[list[Any]] = [[] for _ in range(group_count)]
        for rows, groups in ((actual, actual_groups), (expected, expected_groups)):
            for row in rows:
                customer_id = row.get("customer_id", "") if isinstance(row, dict) else ""
                index = sum(str(customer_id).encode("utf-8")) % group_count
                groups[index].append(row)
            for group in groups:
                group.sort(key=lambda value: json.dumps(value, sort_keys=True))
        passed = 0
        for actual_group, expected_group in zip(actual_groups, expected_groups):
            try:
                _assert_deep_equal(actual_group, expected_group, f"{name}.customers")
                passed += 1
            except Exception:
                continue
        return passed / group_count
    except Exception:
        return 0.0


@criterion(description="Shipped residential scope, operating and settlement totals independently match the reference")
def shipped_residential_totals_match(workspace: Path) -> float:
    return _rollup_totals_score(workspace, "rate_class_residential.json")


@criterion(description="Shipped residential customer groups independently match the reference")
def shipped_residential_customers_match(workspace: Path) -> float:
    return _customer_rows_score(workspace, "rate_class_residential.json", 5)


@criterion(description="Shipped commercial scope, operating and settlement totals independently match the reference")
def shipped_commercial_totals_match(workspace: Path) -> float:
    return _rollup_totals_score(workspace, "rate_class_commercial.json")


@criterion(description="Shipped commercial customer groups independently match the reference")
def shipped_commercial_customers_match(workspace: Path) -> float:
    return _customer_rows_score(workspace, "rate_class_commercial.json", 5)


@criterion(description="Shipped industrial scope, operating and settlement totals independently match the reference")
def shipped_industrial_totals_match(workspace: Path) -> float:
    return _rollup_totals_score(workspace, "rate_class_industrial.json")


@criterion(description="Shipped industrial customer groups independently match the reference")
def shipped_industrial_customers_match(workspace: Path) -> float:
    return _customer_rows_score(workspace, "rate_class_industrial.json", 5)


@criterion(description="Shipped north scope, operating and settlement totals independently match the reference")
def shipped_north_totals_match(workspace: Path) -> float:
    return _rollup_totals_score(workspace, "region_meridian_north.json")


@criterion(description="Shipped north region customer groups independently match the reference")
def shipped_north_customers_match(workspace: Path) -> float:
    return _customer_rows_score(workspace, "region_meridian_north.json", 3)


@criterion(description="Shipped south scope, operating and settlement totals independently match the reference")
def shipped_south_totals_match(workspace: Path) -> float:
    return _rollup_totals_score(workspace, "region_meridian_south.json")


@criterion(description="Shipped south region customer groups independently match the reference")
def shipped_south_customers_match(workspace: Path) -> float:
    return _customer_rows_score(workspace, "region_meridian_south.json", 3)


@criterion(description="Shipped east scope, operating and settlement totals independently match the reference")
def shipped_east_totals_match(workspace: Path) -> float:
    return _rollup_totals_score(workspace, "region_meridian_east.json")


@criterion(description="Shipped east region customer groups independently match the reference")
def shipped_east_customers_match(workspace: Path) -> float:
    return _customer_rows_score(workspace, "region_meridian_east.json", 3)


def _session_turn(workspace: Path, profile: str, occurrence: int = 0) -> dict[str, Any]:
    matches = [turn for turn in _session_outputs(workspace)["turns"]
               if turn["profile"] == profile]
    return matches[occurrence]


def _session_partitions_match(
        workspace: Path, profile: str,
        partitions: tuple[tuple[str, tuple[str, ...] | None, bool], ...]) -> bool:
    try:
        actual = _session_turn(workspace, profile)["parsed"]
        expected = _reference_for_profile(profile)
        for name, keys, own_key_set in partitions:
            _assert_partition(
                actual[name], expected[name], keys, f"{profile}.{name}",
                own_key_set=own_key_set)
        return True
    except Exception:
        return False


def _session_partition_groups_score(
        workspace: Path, profile: str,
        groups: tuple[tuple[tuple[str, tuple[str, ...] | None, bool], ...], ...]) -> float:
    try:
        actual = _session_turn(workspace, profile)["parsed"]
        expected = _reference_for_profile(profile)
    except Exception:
        return 0.0
    passed = 0
    for group in groups:
        try:
            for name, keys, own_key_set in group:
                _assert_partition(
                    actual[name], expected[name], keys, f"{profile}.{name}",
                    own_key_set=own_key_set)
            passed += 1
        except Exception:
            continue
    return passed / len(groups)


@criterion(description="Persistent session accepts four NDJSON turns and acknowledges each exact turn_id in order")
def persistent_session_protocol(workspace: Path) -> bool:
    try:
        result = _session_outputs(workspace)
        return result["acks"] == [
            {"status": "ok", "turn_id": f"turn-{index + 1}-{profile.lower()}"}
            for index, profile in enumerate(SESSION_SEQUENCE)
        ]
    except Exception:
        return False


def _full_artifact_partition(name: str) -> tuple[str, None, bool]:
    return name, None, False


@criterion(description="CASCADE summary sections and class rollups independently match the staged reference")
def cascade_billing_matches(workspace: Path) -> float:
    return _session_partition_groups_score(
        workspace, "CASCADE",
        ((('summary.json', _ROLLUP_SCOPE_KEYS + _ROLLUP_ENERGY_KEYS, True),),
         (('summary.json', _ROLLUP_USAGE_FIXED_KEYS + _ROLLUP_NMB_KEYS +
           _ROLLUP_SETTLEMENT_KEYS, False),),
         ((_full_artifact_partition(ARTIFACT_NAMES[1])),),
         ((_full_artifact_partition(ARTIFACT_NAMES[2])),),
         ((_full_artifact_partition(ARTIFACT_NAMES[3])),)))


@criterion(description="CASCADE regional rollups independently match the staged reference")
def cascade_regions_match(workspace: Path) -> float:
    return _session_partition_groups_score(
        workspace, "CASCADE",
        ((('region_meridian_north.json', _ROLLUP_SCOPE_KEYS + _ROLLUP_ALL_TOTAL_KEYS,
           True),),
         (('region_meridian_north.json', ('customers',), False),),
         ((_full_artifact_partition('region_meridian_south.json')),),
         (('region_meridian_east.json', _ROLLUP_SCOPE_KEYS + _ROLLUP_ALL_TOTAL_KEYS,
           True),),
         (('region_meridian_east.json', ('customers',), False),)))


@criterion(description="CASCADE calendar, customer-policy and data-quality audits independently match the staged reference")
def cascade_audits_match(workspace: Path) -> float:
    return _session_partition_groups_score(
        workspace, "CASCADE",
        ((("policy_audit.json", ("dst_cutover_applied", "holiday_reclassifications"),
            True),),
         (("policy_audit.json", ("grandfather_applied",), False),),
         (("policy_audit.json", ("rate_class_migrations",), False),),
         (("policy_audit.json", ("retroactive_orders_applied",), False),),
         ((_full_artifact_partition("data_quality.json")),)))


@criterion(description="REVERSAL artifacts match the independent staged reference")
def reversal_profile_matches(workspace: Path) -> bool:
    return _session_partitions_match(
        workspace, "REVERSAL", tuple(_full_artifact_partition(name) for name in ARTIFACT_NAMES))


@criterion(description="CHALLENGE artifacts match the independent staged reference")
def challenge_profile_matches(workspace: Path) -> bool:
    try:
        actual = _one_shot_outputs(workspace, "CHALLENGE")
        expected = _reference_for_profile("CHALLENGE")
        for name in ARTIFACT_NAMES:
            _assert_deep_equal(actual[name], expected[name], f"CHALLENGE.{name}")
        return True
    except Exception:
        return False


@criterion(description="Repeated CASCADE turn after two different snapshots is byte-identical to the first CASCADE turn")
def persistent_session_resets_state(workspace: Path) -> bool:
    try:
        first = _session_turn(workspace, "CASCADE", 0)["raw"]
        repeated = _session_turn(workspace, "CASCADE", 1)["raw"]
        return all(first[name] == repeated[name] for name in ARTIFACT_NAMES)
    except Exception:
        return False


@criterion(description="Every artifact is a non-empty JSON object serialised with sorted keys, two-space indentation and a trailing newline")
def artifacts_canonically_serialised(workspace: Path) -> bool:
    try:
        for name in ARTIFACT_NAMES:
            text = (_out_dir(workspace) / name).read_text(encoding="utf-8")
            parsed = json.loads(text)
            if not isinstance(parsed, dict) or not parsed:
                return False
            if json.dumps(parsed, sort_keys=True, indent=2) + "\n" != text:
                return False
        return True
    except Exception:
        return False


@criterion(description="Every rollup carries a non-empty customers list sorted by numeric premise_code suffix")
def customer_lists_sorted_by_premise_number(workspace: Path) -> bool:
    try:
        for name in ROLLUP_NAMES:
            customers = _load_out(workspace, name).get("customers")
            if not isinstance(customers, list) or not customers:
                return False
            codes = [c["premise_code"] for c in customers]
            if not all(isinstance(pc, str) and re.fullmatch(r"P\d+", pc) for pc in codes):
                return False
            if codes != sorted(codes, key=_premise_sort_key):
                return False
        return True
    except Exception:
        return False




# ─── negative checks (each returns True when the cheat is present) ─────────

def _embeds_shipped_totals(src: str) -> bool:
    """True when the source carries at least four of the shipped extract's
    summary totals as literals."""
    shipped = _shipped_reference_outputs()["summary.json"]
    checks = [shipped["energy_charge_mrcc_total"], shipped["demand_charge_mrcc_total"],
              shipped["customer_charge_mrcc_total"], shipped["fac_mrcc_total"],
              shipped["bill_total_mrcc"], shipped["retroactive_adjustment_mrcc_total"]]
    hits = 0
    for value in checks:
        if abs(value) < 10:
            continue
        if re.search(rf"(?<![0-9]){abs(value)}(?![0-9])", src):
            hits += 1
    return hits >= 4


@criterion(description="reconcile.py embeds at least four of the shipped extract's summary totals as literals")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted: True means the cheat is present; the -5 weight punishes it.
    try:
        p = _reconcile_source(workspace)
        if not p.is_file():
            return False
        return _embeds_shipped_totals(p.read_text(encoding="utf-8"))
    except Exception:
        return False


@criterion(description="reconcile.py is a stub with fewer than 80 substantive lines of Python and no embedded shipped totals")
def negative_missing_substantive_sections(workspace: Path) -> bool:
    # Inverted: True means the cheat is present; the -3 weight punishes it.
    # A short script that embeds the shipped totals is already priced by
    # negative_hardcoded_sample_answers, so it is excluded here: one decision
    # never pays two test-channel penalties.
    try:
        p = _reconcile_source(workspace)
        if not p.is_file():
            return False
        src = p.read_text(encoding="utf-8")
        substantive = 0
        for line in src.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                substantive += 1
        return substantive < 80 and not _embeds_shipped_totals(src)
    except Exception:
        return False


_VERIFIER_PATH = re.compile(r"(?<!\w)/(?:tests|logs)(?:/|$)")


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _names_verifier_files(src: str) -> bool:
    """True when executable code (string literals outside docstrings, or
    imports) names a /tests or /logs path or the test_output module. Comments
    and docstrings are prose, so an honest note about them never trips it."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))
        return bool(_VERIFIER_PATH.search(code)) or "test_output" in code
    if any("test_output" in name for name in _imported_modules(src)):
        return True
    skip = _docstring_nodes(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            if _VERIFIER_PATH.search(node.value) or "test_output" in node.value:
                return True
    return False


@criterion(description="reconcile.py code names a /tests or /logs path or the verifier module")
def negative_reads_tests_or_reward_files(workspace: Path) -> bool:
    # Inverted: True means the cheat is present; the -5 weight punishes it.
    try:
        p = _reconcile_source(workspace)
        if not p.is_file():
            return False
        return _names_verifier_files(p.read_text(encoding="utf-8"))
    except Exception:
        return False


# Standard-library modules whose only purpose is network traffic.
_NETWORK_MODULES = {"socket", "ssl", "socketserver", "http", "urllib.request", "ftplib",
                    "smtplib", "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc"}


def _imported_modules(src: str) -> set[str]:
    """Absolute module names imported anywhere in the source."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@criterion(description="reconcile.py imports a third-party package or a standard-library network module")
def negative_external_dependency_or_network(workspace: Path) -> bool:
    # Inverted: True means the cheat is present; the -3 weight punishes it.
    try:
        p = _reconcile_source(workspace)
        if not p.is_file():
            return False
        for name in _imported_modules(p.read_text(encoding="utf-8")):
            if "test_output" in name:
                continue
            top = name.split(".")[0]
            if top not in sys.stdlib_module_names:
                return True
            if any(name == m or name.startswith(m + ".") for m in _NETWORK_MODULES):
                return True
        return False
    except Exception:
        return False


@criterion(description="reconcile.py creates, changes or removes scratch paths outside its assigned OUT_DIR during hidden runs")
def negative_writes_outside_out_dir(workspace: Path) -> bool:
    # Inverted: True means the cheat is present; the -3 weight punishes it.
    # The agent's script runs as nobody, which can write only its OUT_DIR and
    # the world-writable scratch areas, so anything nobody owns there is a
    # write outside OUT_DIR.
    try:
        if not _reconcile_source(workspace).is_file():
            return False
        with contextlib.suppress(Exception):
            _session_outputs(workspace)
        with contextlib.suppress(Exception):
            _one_shot_outputs(workspace, "CHALLENGE")
        with _RUN_STATE_LOCK:
            return bool(_STRAY_WRITES)
    except Exception:
        return False


# ─── registrations ────────────────────────────────────────────────────────

criteria.artifact_set_exists_and_parses(weight=1)
criteria.shipped_summary_scope_matches(weight=1)
criteria.shipped_summary_energy_matches(weight=1)
criteria.shipped_summary_usage_nmb_matches(weight=1)
criteria.shipped_summary_settlement_matches(weight=1)
criteria.shipped_policy_calendar_matches(weight=1)
criteria.shipped_policy_customer_order_matches(weight=1)
criteria.shipped_data_quality_raw_declarations_match(weight=1)
criteria.shipped_data_quality_flags_match(weight=1)
criteria.shipped_residential_totals_match(weight=1)
criteria.shipped_residential_customers_match(weight=5)
criteria.shipped_commercial_totals_match(weight=1)
criteria.shipped_commercial_customers_match(weight=5)
criteria.shipped_industrial_totals_match(weight=1)
criteria.shipped_industrial_customers_match(weight=5)
criteria.shipped_north_totals_match(weight=1)
criteria.shipped_north_customers_match(weight=3)
criteria.shipped_south_totals_match(weight=1)
criteria.shipped_south_customers_match(weight=3)
criteria.shipped_east_totals_match(weight=1)
criteria.shipped_east_customers_match(weight=3)
criteria.persistent_session_protocol(weight=3)
criteria.cascade_billing_matches(weight=5)
criteria.cascade_regions_match(weight=5)
criteria.cascade_audits_match(weight=5)
criteria.reversal_profile_matches(weight=1)
criteria.challenge_profile_matches(weight=1)
criteria.artifacts_canonically_serialised(weight=1)
criteria.customer_lists_sorted_by_premise_number(weight=3)
criteria.persistent_session_resets_state(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_missing_substantive_sections(weight=-3)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-3)
criteria.negative_writes_outside_out_dir(weight=-3)
