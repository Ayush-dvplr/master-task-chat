#!/usr/bin/env python3
"""Derive the 2026 assessment statements for a return batch.

Usage: python3 derive_report.py <DATA_DIR> <OUT_DIR>

The Consolidated Enterprise Levy Code of the Commonwealth of Arvenna
(``levy_code.md``, printed with the batch) is applied as it has effect under
section 1-004: the original provision is taken first and every modifying
provision then operates on the value produced by those applied before it, in
ascending order of section number.  The provisions of the Code that fix the
values in force for the levy year 2026, and the effect of each, are stated in
the constants below, each with the section that fixes the value.  The program
reads the batch manifest and the eight registers from <DATA_DIR> and writes the
nine statements into <OUT_DIR>.

All money is held in integer cents and every multiplication or division is
performed on exact integers (never on floats).  Rounding is to the nearest
whole cent, half to even (section 1-080), except for interest, which is half up
(section 12-040).
"""

import csv
import json
import os
import sys
from datetime import date, timedelta
from fractions import Fraction

# ---------------------------------------------------------------------------
# The Code as it has effect under section 1-004
# ---------------------------------------------------------------------------

YEAR_START = date(2026, 1, 1)
YEAR_END = date(2026, 12, 31)
DAYS_IN_YEAR = 365

# Section 1-090(1): public holidays.
PUBLIC_HOLIDAYS = {
    date(2026, 1, 1), date(2026, 1, 26), date(2026, 4, 3), date(2026, 4, 6),
    date(2026, 4, 30), date(2026, 5, 1), date(2026, 6, 8), date(2026, 8, 3),
    date(2026, 11, 2), date(2026, 12, 25), date(2026, 12, 28),
    date(2027, 1, 1), date(2027, 1, 26), date(2027, 3, 26), date(2027, 3, 29),
}

QUARTERS = ('Q1', 'Q2', 'Q3', 'Q4')
QUARTER_END = {'Q1': (3, 31), 'Q2': (6, 30), 'Q3': (9, 30), 'Q4': (12, 31)}

REGIONS = ('North', 'South', 'West', 'East')
RESIDUAL_CLASS = 'AC-199'


def _year(rate, auth):
    """A rate in force for every quarter of the levy year."""
    return {q: [rate, auth] for q in QUARTERS}


def _cls(section, band, band_auth, export, export_auth, rates):
    return {'section': section, 'band': band, 'band_auth': band_auth,
            'export_excluded': export, 'export_auth': export_auth,
            'rates': rates}


# Schedule 2 (sections 2-101 to 2-160) as it has effect.  For each class the
# band, the treatment of export receipts and the scheduled rate in force for
# each quarter are stated with the section that fixes the value in force.
CLASSES = {
    'AC-101': _cls('2-101', 'I', '2-101', True, '2-101', _year(1800, '2-101')),
    'AC-102': _cls('2-102', 'I', '2-102', False, '2-102', _year(4600, '2-102')),
    'AC-103': _cls('2-103', 'II', '2-103', False, '2-103', _year(6000, '2-103')),
    'AC-104': _cls('2-104', 'II', '2-104', False, '2-104', _year(9950, '2-104')),
    'AC-105': _cls('2-105', 'I', '2-105', False, '2-105', _year(9200, '2-105')),
    'AC-106': _cls('2-106', 'II', '2-106', False, '2-106',
                   _year(14000, '2-106')),
    'AC-107': _cls('2-107', 'III', '2-107', False, '2-107',
                   _year(10050, '2-107')),
    'AC-108': _cls('2-108', 'III', '2-108', False, '2-108',
                   _year(8750, '2-108')),
    'AC-109': _cls('2-109', 'III', '2-109', False, '2-109',
                   _year(6850, '2-109')),
    'AC-110': _cls('2-110', 'I', '2-110', False, '2-110',
                   {**_year(4900, '2-110'), 'Q4': [3550, '7-121']}),
    'AC-111': _cls('2-111', 'I', '2-111', True, '2-111', _year(8900, '2-111')),
    'AC-112': _cls('2-112', 'I', '2-112', False, '2-112', _year(6850, '2-112')),
    'AC-113': _cls('2-113', 'III', '2-113', False, '2-113',
                   _year(5050, '2-113')),
    'AC-114': _cls('2-114', 'III', '2-114', True, '2-114',
                   _year(7950, '2-114')),
    'AC-115': _cls('2-115', 'III', '2-115', False, '2-115',
                   _year(12850, '2-115')),
    'AC-116': _cls('2-116', 'III', '7-149', True, '2-116',
                   _year(10650, '2-116')),
    'AC-117': _cls('2-117', 'III', '2-117', False, '2-117',
                   _year(3450, '7-257')),
    'AC-118': _cls('2-118', 'I', '2-118', False, '2-118', _year(5950, '2-118')),
    'AC-119': _cls('2-119', 'II', '2-119', False, '2-119', _year(1850, '2-119')),
    'AC-120': _cls('2-120', 'I', '2-120', False, '2-120',
                   {**_year(12650, '2-120'),
                    'Q2': [12150, '7-111'], 'Q3': [12150, '7-111'],
                    'Q4': [12150, '7-111']}),
    'AC-121': _cls('2-121', 'II', '2-121', True, '2-121',
                   {**_year(7650, '2-121'), 'Q4': [7900, '7-174']}),
    'AC-122': _cls('2-122', 'III', '2-122', False, '2-122',
                   _year(9750, '2-122')),
    'AC-123': _cls('2-123', 'III', '2-123', False, '2-123',
                   _year(2750, '2-123')),
    'AC-124': _cls('2-124', 'II', '2-124', False, '2-124',
                   {**_year(9100, '2-124'), 'Q2': [8450, '7-137'],
                    'Q3': [8450, '7-137'], 'Q4': [8450, '7-137']}),
    'AC-125': _cls('2-125', 'II', '2-125', False, '2-125',
                   _year(13100, '2-125')),
    'AC-126': _cls('2-126', 'II', '2-126', True, '2-126', _year(1800, '2-126')),
    'AC-127': _cls('2-127', 'III', '2-127', False, '2-127',
                   {**_year(13100, '7-203'), 'Q3': [12000, '7-136'],
                    'Q4': [12000, '7-136']}),
    'AC-128': _cls('2-128', 'I', '2-128', False, '2-128',
                   _year(12650, '2-128')),
    'AC-129': _cls('2-129', 'II', '2-129', False, '2-129', _year(6100, '2-129')),
    'AC-130': _cls('2-130', 'II', '2-130', False, '2-130', _year(3050, '2-130')),
    'AC-131': _cls('2-131', 'III', '2-131', False, '7-142',
                   _year(12150, '2-131')),
    'AC-132': _cls('2-132', 'III', '2-132', True, '2-132',
                   {**_year(5300, '2-132'), 'Q2': [6400, '7-144'],
                    'Q3': [6400, '7-144'], 'Q4': [6400, '7-144']}),
    'AC-133': _cls('2-133', 'II', '2-133', False, '2-133',
                   _year(13150, '2-133')),
    'AC-134': _cls('2-134', 'II', '2-134', True, '2-134',
                   {**_year(3900, '2-134'), 'Q3': [4100, '7-188'],
                    'Q4': [4100, '7-188']}),
    'AC-135': _cls('2-135', 'II', '2-135', True, '2-135', _year(5550, '2-135')),
    'AC-136': _cls('2-136', 'III', '2-136', False, '7-104',
                   _year(11850, '2-136')),
    'AC-137': _cls('2-137', 'II', '2-137', False, '2-137',
                   _year(9250, '2-137')),
    'AC-138': _cls('2-138', 'III', '2-138', False, '2-138',
                   {**_year(2050, '2-138'), 'Q3': [2250, '7-202'],
                    'Q4': [2250, '7-202']}),
    'AC-139': _cls('2-139', 'II', '2-139', True, '2-139',
                   {**_year(2150, '2-139'), 'Q3': [1950, '7-172'],
                    'Q4': [1950, '7-172']}),
    'AC-140': _cls('2-140', 'I', '2-140', True, '2-140', _year(5800, '2-140')),
    'AC-141': _cls('2-141', 'III', '7-182', False, '2-141',
                   {**_year(9050, '2-141'), 'Q3': [9500, '7-153'],
                    'Q4': [10000, '7-194']}),
    'AC-142': _cls('2-142', 'II', '7-156', True, '2-142',
                   _year(13000, '2-142')),
    'AC-143': _cls('2-143', 'III', '7-127', True, '2-143',
                   {**_year(5700, '2-143'), 'Q4': [6200, '7-194']}),
    'AC-144': _cls('2-144', 'III', '2-144', False, '2-144',
                   {**_year(11400, '2-144'), 'Q4': [11900, '7-194']}),
    'AC-145': _cls('2-145', 'I', '2-145', True, '7-155', _year(4400, '2-145')),
    'AC-146': _cls('2-146', 'II', '2-146', True, '2-146', _year(2400, '2-146')),
    'AC-147': _cls('2-147', 'III', '2-147', False, '2-147',
                   {**_year(6700, '2-147'), 'Q4': [7200, '7-194']}),
    'AC-148': _cls('2-148', 'II', '2-148', False, '2-148',
                   {**_year(10700, '2-148'), 'Q4': [9800, '7-148']}),
    'AC-149': _cls('2-149', 'III', '2-149', False, '2-149',
                   {**_year(5100, '2-149'), 'Q4': [5600, '7-194']}),
    'AC-150': _cls('2-150', 'III', '2-150', True, '2-150',
                   {**_year(3900, '2-150'), 'Q4': [4400, '7-194']}),
    'AC-151': _cls('2-151', 'III', '2-151', False, '2-151', _year(6100, '2-151')),
    'AC-152': _cls('2-152', 'II', '2-152', False, '2-152', _year(1950, '7-242')),
    'AC-153': _cls('2-153', 'I', '2-153', True, '2-153', _year(5250, '2-153')),
    'AC-154': _cls('2-154', 'I', '2-154', False, '2-154', _year(8400, '2-154')),
    'AC-155': _cls('2-155', 'I', '2-155', False, '2-155', _year(7150, '2-155')),
    'AC-156': _cls('2-156', 'I', '2-156', True, '2-156',
                   _year(10200, '2-156')),
    'AC-157': _cls('2-157', 'III', '2-157', False, '2-157',
                   _year(6950, '2-157')),
    'AC-158': _cls('2-158', 'II', '2-158', False, '2-158',
                   _year(2350, '7-218')),
    'AC-159': _cls('2-159', 'II', '2-159', False, '2-159', _year(7800, '2-159')),
    'AC-160': _cls('2-160', 'II', '2-160', False, '2-160',
                   _year(10850, '2-160')),
    # The residual class, established by section 7-308.
    RESIDUAL_CLASS: _cls('7-308', 'II', '7-308', False, '7-308',
                         _year(5500, '7-308')),
}


def _dist(section, region, coastal, edz, periods):
    """periods: [(from, to, cents_per_m2, authority)] in date order."""
    return {'section': section, 'region': region, 'coastal': coastal,
            'edz': edz, 'rate_periods': periods}


def _p(rate, auth, start=None, end=None):
    return [(start or YEAR_START.isoformat(), end or YEAR_END.isoformat(),
             rate, auth)]


def _p2(rate1, auth1, split, rate2, auth2):
    """Two periods, the second beginning on the day after ``split``."""
    return _p(rate1, auth1, end=split) + _p(rate2, auth2,
                                            start=(date.fromisoformat(split)
                                                   + timedelta(days=1)).isoformat())


# Schedule 3 (sections 3-101 to 3-148) as it has effect.  Where the rate of a
# district changes during the levy year, each period during which a single rate
# is in force is stated separately (sections 3-010, 14-037).
DISTRICTS = {
    'D-01': _dist('3-101', 'North', False, False, _p(275, '3-101')),
    'D-02': _dist('3-102', 'South', False, False, _p(275, '3-102')),
    'D-03': _dist('3-103', 'North', False, True, _p(105, '3-103')),
    'D-04': _dist('3-104', 'West', False, False, _p(420, '3-104')),
    'D-05': _dist('3-105', 'North', False, False, _p(212, '3-105')),
    'D-06': _dist('3-106', 'East', True, False, _p(352, '3-106')),
    'D-07': _dist('3-107', 'South', False, True,
                  _p2(217, '3-107', '2026-08-31', 202, '7-183')),
    'D-08': _dist('3-108', 'East', False, True, _p(237, '3-108')),
    'D-09': _dist('3-109', 'West', False, False, _p(64, '3-109')),
    'D-10': _dist('3-110', 'North', True, False, _p(334, '7-249')),
    'D-11': _dist('3-111', 'North', False, False, _p(83, '3-111')),
    'D-12': _dist('3-112', 'East', False, False, _p(220, '7-259')),
    'D-13': _dist('3-113', 'East', True, False, _p(316, '3-113')),
    'D-14': _dist('3-114', 'West', False, False, _p(332, '3-114')),
    'D-15': _dist('3-115', 'South', True, False, _p(198, '3-115')),
    'D-16': _dist('3-116', 'North', False, False,
                  _p2(143, '3-116', '2026-08-15', 113, '7-158')),
    'D-17': _dist('3-117', 'West', False, True,
                  _p2(46, '3-117', '2026-11-30', 65, '7-110')),
    'D-18': _dist('3-118', 'South', False, False, _p(66, '3-118')),
    'D-19': _dist('3-119', 'East', True, False, _p(142, '3-119')),
    'D-20': _dist('3-120', 'South', False, False, _p(305, '3-120')),
    'D-21': _dist('3-121', 'West', True, True, _p(193, '3-121')),
    'D-22': _dist('3-122', 'South', False, False, _p(208, '3-122')),
    'D-23': _dist('3-123', 'South', False, False, _p(388, '3-123')),
    'D-24': _dist('3-124', 'East', True, False, _p(345, '3-124')),
    'D-25': _dist('3-125', 'North', False, False, _p(52, '3-125')),
    'D-26': _dist('3-126', 'North', False, False,
                  _p2(233, '3-126', '2026-06-30', 289, '7-138')),
    'D-27': _dist('3-127', 'South', False, True,
                  _p2(110, '3-127', '2026-08-31', 95, '7-183')),
    'D-28': _dist('3-128', 'North', False, False,
                  _p2(48, '3-128', '2026-03-14', 61, '7-171')),
    'D-29': _dist('3-129', 'West', False, False, _p(348, '3-129')),
    'D-30': _dist('3-130', 'West', False, True, _p(366, '3-130')),
    'D-31': _dist('3-131', 'South', False, False, _p(93, '3-131')),
    'D-32': _dist('3-132', 'East', False, False, _p(50, '3-132')),
    'D-33': _dist('3-133', 'South', False, True,
                  _p2(112, '3-133', '2026-08-31', 97, '7-183')),
    'D-34': _dist('3-134', 'East', True, True, _p(310, '3-134')),
    'D-35': _dist('3-135', 'East', False, False, _p(307, '3-135')),
    'D-36': _dist('3-136', 'North', True, True,
                  _p2(322, '3-136', '2026-09-30', 307, '7-108')),
    'D-37': _dist('3-137', 'East', True, False, _p(313, '3-137')),
    'D-38': _dist('3-138', 'North', False, False, _p(82, '3-138')),
    'D-39': _dist('3-139', 'North', False, False, _p(415, '7-239')),
    'D-40': _dist('3-140', 'East', True, False, _p(44, '3-140')),
    'D-41': _dist('3-141', 'West', False, False, _p(267, '3-141')),
    'D-42': _dist('3-142', 'West', True, True, _p(383, '3-142')),
    'D-43': _dist('3-143', 'South', True, False, _p(91, '3-143')),
    'D-44': _dist('3-144', 'West', False, False, _p(252, '3-144')),
    'D-45': _dist('3-145', 'East', False, False,
                  _p2(127, '3-145', '2026-04-30', 74, '7-205')),
    'D-46': _dist('3-146', 'South', False, False, _p(312, '3-146')),
    'D-47': _dist('3-147', 'West', False, False, _p(57, '3-147')),
    'D-48': _dist('3-148', 'West', True, False, _p(223, '3-148')),
}

# Section 6-010, as modified by section 7-120.
REGIONAL_SURCHARGE_PPM = {
    'North': [45000, '6-010'],
    'South': [38000, '6-010'],
    'West': [55000, '7-120'],
    'East': [41000, '6-010'],
}
# Section 6-020, as modified by section 13-065(3) for the levy year 2026.
COASTAL_SUPPLEMENT_PPM = [15000, '13-065']
# Section 8-020.
PUBLIC_FLOOR_FACTOR_PERCENT = [60, '8-020']
# Section 4-010, corrected by section 7-215.
PAYROLL_RATE_PPM = [12500, '7-215']
# Section 4-020(1).
PAYROLL_ANNUAL_EXEMPTION_CENTS = [30000000, '4-020']
# Binding Ruling BR 2026/07 (section 14-022).
MUTUAL_EXEMPTION_MULTIPLIER = [2, '14-022']
# Section 5-020(1), as modified by section 7-364.
BAND_III_ENERGY_REDUCTION_PERCENT = [45, '7-364']
# Section 2-040(1)(b), as modified by section 7-193.
SMALL_ENTERPRISE_THRESHOLD_CENTS = [40000000, '7-193']
# Section 2-040(3).
SMALL_ENTERPRISE_RATE_FACTOR_PERCENT = [60, '2-040']
# Section 9-001, as modified by section 7-332.
GLOBAL_CREDIT_CAP_PERCENT = [70, '7-332']

# Section 5-010, as modified by sections 7-141 and 7-160: millicents per
# kilowatt-hour, for each quarter.
ENERGY_RATES = {
    'grid_electricity': _year(210, '5-010'),
    'natural_gas': _year(165, '5-010'),
    'biomass': {'Q1': [90, '5-010'], 'Q2': [90, '5-010'],
                'Q3': [120, '7-141'], 'Q4': [120, '7-141']},
    'diesel': {'Q1': [480, '5-010'], 'Q2': [480, '5-010'],
               'Q3': [480, '5-010'], 'Q4': [520, '7-160']},
    'solar_onsite': _year(0, '5-010'),
}


def _credit(section, code, rate, rate_auth, cap_basis, cap_amount, cap_auth,
            carry, carry_auth, on_claim=True, base=None):
    return {
        'section': section, 'code': code, 'on_claim': on_claim, 'base': base,
        'rate_ppm': [rate, rate_auth], 'cap_basis': cap_basis,
        'cap_amount': cap_amount, 'cap_auth': cap_auth,
        'carry_years': [carry, carry_auth],
    }


# Every credit established by the Code, in the order in which they are applied
# under sections 9-002 and 1-086.  carry_years 0 means no carry-forward period.
CREDITS = [
    _credit('4-060', 'K-11', 150000, '4-060', 'payroll_levy', 1000000, '4-060',
            0, '4-060', on_claim=False, base='apprentice_payroll'),
    _credit('5-040', 'K-03', 300000, '5-040', 'energy_levy', 1000000, '5-040',
            2, '5-040'),
    _credit('7-143', 'K-12', 250000, '7-143', 'primary_levy', 100000, '7-143',
            3, '7-143'),
    _credit('9-104', 'K-05', 500000, '9-104', 'gross_levy', 300000, '9-104',
            0, '9-104'),
    _credit('9-109', 'K-07', 250000, '9-109', 'primary_levy', 150000, '9-109',
            3, '9-109'),
    _credit('9-112', 'K-09', 180000, '9-112', 'gross_levy', 120000, '9-112',
            3, '7-131'),
    _credit('9-118', 'K-02', 100000, '9-118', 'gross_levy', 200000, '9-118',
            4, '9-118'),
    _credit('9-125', 'K-06', 150000, '9-125', 'fixed', 550000, '13-083',
            2, '9-125'),
    _credit('9-131', 'K-04', 400000, '7-211', 'primary_levy', 250000, '9-131',
            5, '9-131'),
    _credit('9-140', 'K-01', 200000, '9-140', 'fixed', 250000, '9-140',
            1, '9-140'),
    _credit('9-147', 'K-10', 200000, '9-147', 'fixed', 300000, '9-147',
            1, '9-147'),
    _credit('9-152', 'K-08', 8000, '9-152', 'primary_levy', 50000, '7-112',
            0, '9-152', on_claim=False, base='export_receipts'),
]
CREDIT_BY_CODE = {c['code']: c for c in CREDITS}

# Section 11-010, as corrected by section 7-246 (trust).  Binding Ruling
# BR 2026/05 (section 14-016) prorates these by reference to active days.
MINIMUM_LEVY_CENTS = {
    'sole_trader': [5000, '11-010'],
    'partnership': [12000, '11-010'],
    'company': [30000, '11-010'],
    'trust': [20000, '7-246'],
    'cooperative': [9000, '11-010'],
    'statutory_body': [0, '11-010'],
}

# Section 12-020, corrected by section 7-253, as modified by section 7-185.
INTEREST_RATE_PERIODS = [
    ['2026-01-01', '2026-12-31', 75000, '7-253'],
    ['2027-01-01', None, 82500, '7-185'],
]


def interest_ppm_on(day):
    """The rate of interest in force on a day, in parts per million."""
    iso = day.isoformat()
    for start, end, ppm, _authority in INTEREST_RATE_PERIODS:
        if start <= iso and (end is None or iso <= end):
            return ppm
    return 0


def is_business_day(day):
    return day.weekday() < 5 and day not in PUBLIC_HOLIDAYS


def last_day_of_month(year, month):
    return (date(year + (month // 12), (month % 12) + 1, 1)
            - timedelta(days=1))


def instalment_due_date(quarter):
    """Section 12-005, with section 1-090(2)."""
    month, last_day = QUARTER_END[quarter]
    end_of_quarter = date(YEAR_START.year, month, last_day)
    following_month = end_of_quarter.month + 1
    following_year = end_of_quarter.year
    if following_month > 12:
        following_month -= 12
        following_year += 1
    due = last_day_of_month(following_year, following_month)
    while not is_business_day(due):
        due += timedelta(days=1)
    return due


INSTALMENT_DUE_DATES = {q: instalment_due_date(q) for q in QUARTERS}

# ---------------------------------------------------------------------------
# Money: exact integer arithmetic only
# ---------------------------------------------------------------------------


def round_half_even(value):
    """Nearest whole cent, half-way to the even cent (section 1-080)."""
    if not isinstance(value, Fraction):
        value = Fraction(value)
    whole = value.numerator // value.denominator
    rem = value - whole
    if rem > Fraction(1, 2):
        return whole + 1
    if rem < Fraction(1, 2):
        return whole
    return whole if whole % 2 == 0 else whole + 1


def round_half_up(value):
    """Nearest whole cent, half-way rounded up (section 12-040)."""
    if not isinstance(value, Fraction):
        value = Fraction(value)
    whole = value.numerator // value.denominator
    return whole + 1 if value - whole >= Fraction(1, 2) else whole


def apply_ppm(amount, ppm):
    """amount cents multiplied by a rate in parts per million."""
    return round_half_even(Fraction(amount * ppm, 1000000))


def apply_percent(amount, percent):
    """amount cents multiplied by a percentage (section 1-092(2))."""
    return round_half_even(Fraction(amount * percent, 100))


def prorate(amount, days):
    """Section 1-084: amount x days / 365, rounded under section 1-080."""
    return round_half_even(Fraction(amount * days, DAYS_IN_YEAR))


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def _int(text):
    return int(text) if text else 0


def _date(text):
    return date.fromisoformat(text) if text else None


def count_days(start, end):
    return (end - start).days + 1 if start <= end else 0


def clip(start, end, other_start, other_end):
    """Days of [start, end] that fall within [other_start, other_end]."""
    lo = max(start, other_start)
    hi = min(end, other_end)
    return count_days(lo, hi) if lo <= hi else 0


class Filer(object):
    """One filer, assessed under the Code."""

    def __init__(self, row):
        self.filer_id = row['filer_id']
        self.filer_class = row['filer_class']
        self.entity_form = row['entity_form']
        self.registered_district = row['registered_district']
        self.commenced = _date(row['commenced_on']) or YEAR_START
        self.ceased = _date(row['ceased_on']) or YEAR_END
        self.elected = row['small_enterprise_election'] == 'Y'
        self.establishments = []
        self.receipts = []
        self.payroll = []
        self.energy = []
        self.claims = []
        self.carryforwards = []
        self.payments = []
        self.issues = []

        start = max(self.commenced, YEAR_START)
        end = min(self.ceased, YEAR_END)
        self.active_start, self.active_end = start, end
        self.active_days = count_days(start, end)

    # -- principal district (Binding Ruling BR 2026/03) -----------------------
    def principal_district(self):
        areas = {}
        for est in self.establishments:
            if est['active_days'] > 0:
                areas[est['district']] = areas.get(est['district'], 0) + \
                    est['floor_area']
        if not areas:
            district = self.registered_district
        else:
            greatest = max(areas.values())
            district = min(d for d, a in areas.items() if a == greatest)
        if district not in DISTRICTS:
            raise ValueError('filer %s: %s is not a district of Schedule 3'
                             % (self.filer_id, district))
        return district

    # -- Part 2 ---------------------------------------------------------------
    def compute_activity(self):
        for line in self.receipts:
            if line['quarter'] not in QUARTERS:
                # no rate is in force for a line with no quarter: it is not
                # assessed and produces no levy
                line['assessed_code'] = None
                line['assessable_cents'] = 0
                line['rate_ppm'] = 0
                line['levy_cents'] = 0
                continue
            reported = line['activity_code']
            assessed = reported if reported in CLASSES else RESIDUAL_CLASS
            line['assessed_code'] = assessed
            info = CLASSES[assessed]
            assessable = line['gross_cents']
            if info['export_excluded']:
                assessable -= line['export_cents']
            line['assessable_cents'] = assessable

        # Section 2-040, with sections 2-041 and 7-193.
        self.small_enterprise_applied = False
        if self.filer_class == 'public':
            if self.elected:
                self.issues.append(
                    '%s: small enterprise election by a public-class filer '
                    'disregarded' % self.filer_id)
        elif self.elected:
            total = sum(l['assessable_cents'] for l in self.receipts
                        if l['assessable_cents'] > 0)
            if total <= SMALL_ENTERPRISE_THRESHOLD_CENTS[0]:
                self.small_enterprise_applied = True

        for line in self.receipts:
            if line['assessed_code'] is None:
                continue
            info = CLASSES[line['assessed_code']]
            scheduled = Fraction(info['rates'][line['quarter']][0])
            if self.small_enterprise_applied:
                # section 2-040(3): the factor is applied before rounding
                rate = scheduled * SMALL_ENTERPRISE_RATE_FACTOR_PERCENT[0] / 100
            else:
                rate = scheduled
            if line['assessable_cents'] > 0:
                line['levy_cents'] = round_half_even(
                    Fraction(line['assessable_cents']) * rate / 1000000)
            else:
                line['levy_cents'] = 0
            # the rates of the Code are whole multiples of 50 parts per million,
            # so the rate in force is always a whole number of parts per million
            line['rate_ppm'] = rate.numerator // rate.denominator
            if line['assessed_code'] != line['activity_code']:
                self.issues.append(
                    '%s/%s/%s: unscheduled activity code %s assessed under %s'
                    % (self.filer_id, line['establishment_id'],
                       line['quarter'], line['activity_code'], RESIDUAL_CLASS))
            if line['establishment_active'] is False:
                self.issues.append(
                    '%s/%s/%s: receipts reported for an inactive establishment'
                    % (self.filer_id, line['establishment_id'],
                       line['quarter']))

        self.activity_levy = sum(l['levy_cents'] for l in self.receipts)

        # Predominant class and band (section 2-045).
        totals = {}
        for line in self.receipts:
            if line['assessable_cents'] > 0:
                totals[line['assessed_code']] = \
                    totals.get(line['assessed_code'], 0) + \
                    line['assessable_cents']
        if totals:
            greatest = max(totals.values())
            self.predominant_class = min(c for c, t in totals.items()
                                         if t == greatest)
        else:
            self.predominant_class = None
        self.band = (CLASSES[self.predominant_class]['band']
                     if self.predominant_class else None)

    # -- Part 3, with Part 8 --------------------------------------------------
    def compute_establishment(self):
        total = 0
        for est in self.establishments:
            lines = 0
            for start, end, rate, _authority in est['rate_periods']:
                days = clip(est['active_start'], est['active_end'],
                            date.fromisoformat(start), date.fromisoformat(end))
                if days <= 0:
                    continue
                if self.filer_class == 'public':
                    factor = PUBLIC_FLOOR_FACTOR_PERCENT[0]
                    lines += round_half_even(Fraction(
                        est['floor_area'] * rate * days * factor,
                        DAYS_IN_YEAR * 100))
                else:
                    lines += round_half_even(Fraction(
                        est['floor_area'] * rate * days, DAYS_IN_YEAR))
            est['levy_cents'] = lines
            total += lines
        self.floor_levy = total

    # -- Part 4 ---------------------------------------------------------------
    def compute_payroll(self):
        payroll_total = sum(r['payroll_cents'] for r in self.payroll)
        apprentice_total = sum(r['apprentice_cents'] for r in self.payroll)
        self.payroll_base = payroll_total - apprentice_total
        self.apprentice_payroll = apprentice_total
        if self.entity_form == 'statutory_body':
            self.payroll_levy = 0
            return
        exemption = PAYROLL_ANNUAL_EXEMPTION_CENTS[0]
        if self.filer_class == 'mutual':
            exemption *= MUTUAL_EXEMPTION_MULTIPLIER[0]
        exemption = prorate(exemption, self.active_days)
        if self.payroll_base > exemption:
            self.payroll_levy = apply_ppm(self.payroll_base - exemption,
                                          PAYROLL_RATE_PPM[0])
        else:
            self.payroll_levy = 0

    # -- Part 5 ---------------------------------------------------------------
    def compute_energy(self):
        lines = []
        for record in self.energy:
            rate = ENERGY_RATES.get(record['fuel'], {}).get(record['quarter'])
            if rate is None:
                amount = 0
            else:
                amount = round_half_even(
                    Fraction(record['kwh'] * rate[0], 1000))
            lines.append(amount)
        self.energy_lines = lines
        self.energy_gross = sum(lines)
        self.energy_reduction = 0
        if self.band == 'III':
            self.energy_reduction = apply_percent(
                self.energy_gross, BAND_III_ENERGY_REDUCTION_PERCENT[0])
        self.energy_levy = self.energy_gross - self.energy_reduction

    # -- Part 6 ---------------------------------------------------------------
    def compute_surcharge(self):
        district = DISTRICTS[self.principal_district()]
        rate = REGIONAL_SURCHARGE_PPM[district['region']][0]
        if district['coastal']:
            rate += COASTAL_SUPPLEMENT_PPM[0]
        self.surcharge = apply_ppm(self.activity_levy + self.floor_levy, rate)

    # -- Parts 9 and 10 -------------------------------------------------------
    def is_eligible(self, credit):
        code = credit['code']
        if code == 'K-11':
            return (self.filer_class in ('commercial', 'mutual')
                    and self.entity_form != 'statutory_body')
        if code == 'K-03':
            return self.band in ('I', 'II')
        if code == 'K-12':
            return DISTRICTS[self.principal_district()]['coastal']
        if code == 'K-05':
            return self.filer_class == 'public'
        if code == 'K-07':
            return (self.filer_class == 'mutual'
                    or self.entity_form == 'cooperative')
        if code == 'K-09' or code == 'K-06':
            return True
        if code == 'K-02':
            return any(est['edz'] and est['active_days'] > 0
                       for est in self.establishments)
        if code == 'K-04':
            return (self.filer_class == 'commercial'
                    and self.entity_form == 'company')
        if code == 'K-01':
            return self.small_enterprise_applied
        if code == 'K-10':
            district = DISTRICTS[self.principal_district()]
            return district['edz'] and not district['coastal']
        if code == 'K-08':
            return self.band in ('II', 'III')
        raise ValueError('unknown credit %s' % code)

    def current_year_amount(self, credit):
        """The current-year amount of a credit (sections 9-004 and 9-006)."""
        if not self.eligible[credit['code']]:
            return 0
        if not credit['on_claim']:
            if credit['base'] == 'apprentice_payroll':
                return apply_ppm(self.apprentice_payroll, credit['rate_ppm'][0])
            if credit['base'] == 'export_receipts':
                total = sum(l['export_cents'] for l in self.receipts)
                return apply_ppm(total, credit['rate_ppm'][0])
            raise ValueError('unknown base %s' % credit['base'])
        expenditure = sum(c['expenditure_cents'] for c in self.claims
                          if c['credit_code'] == credit['code'])
        return apply_ppm(expenditure, credit['rate_ppm'][0])

    def prepare_credits(self):
        self.eligible = {c['code']: self.is_eligible(c) for c in CREDITS}

        # Claim records: section 7-346.
        for claim in self.claims:
            credit = CREDIT_BY_CODE.get(claim['credit_code'])
            if credit is None:
                self.issues.append(
                    '%s: claim %s under %s disregarded: no such credit'
                    % (self.filer_id, claim['claim_id'], claim['credit_code']))
            elif not credit['on_claim']:
                self.issues.append(
                    '%s: claim %s under %s disregarded: credit arises without '
                    'claim'
                    % (self.filer_id, claim['claim_id'], claim['credit_code']))
        for code in sorted({c['credit_code'] for c in self.claims}):
            credit = CREDIT_BY_CODE.get(code)
            if credit is not None and credit['on_claim'] and \
                    not self.eligible[code]:
                self.issues.append(
                    '%s: claim under %s disregarded: filer not eligible'
                    % (self.filer_id, code))

        # Carried-forward amounts: sections 10-003 and 10-004.
        self.carried = {}
        for row in self.carryforwards:
            code = row['credit_code']
            year = row['origin_year']
            credit = CREDIT_BY_CODE.get(code)
            if credit is None or credit['carry_years'][0] == 0:
                self.issues.append(
                    '%s: carryforward %s/%d disregarded: not permitted'
                    % (self.filer_id, code, year))
                continue
            if YEAR_START.year > year + credit['carry_years'][0]:
                self.issues.append(
                    '%s: carryforward %s/%d disregarded: expired'
                    % (self.filer_id, code, year))
                continue
            amounts = self.carried.setdefault(code, {})
            amounts[year] = amounts.get(year, 0) + row['remaining_cents']

    def compute_credits(self):
        self.prepare_credits()

        # Limits: sections 9-001 and 9-005.
        global_limit = apply_percent(self.gross_levy,
                                     GLOBAL_CREDIT_CAP_PERCENT[0])
        levies = {'primary_levy': self.primary_levy,
                  'gross_levy': self.gross_levy,
                  'payroll_levy': self.payroll_levy,
                  'energy_levy': self.energy_levy}
        limits = {}
        for credit in CREDITS:
            if credit['cap_basis'] == 'fixed':
                limits[credit['code']] = credit['cap_amount']
            else:
                limits[credit['code']] = apply_ppm(
                    levies[credit['cap_basis']], credit['cap_amount'])

        # Amounts available, in order (sections 9-002, 10-002 and 10-005(2)).
        amounts = []
        for credit in CREDITS:
            code = credit['code']
            for year in sorted(self.carried.get(code, {})):
                amounts.append([credit, year, self.carried[code][year]])
            amounts.append([credit, YEAR_START.year,
                            self.current_year_amount(credit)])

        # Application, in sequence (section 9-003).
        self.credits_applied = []
        self.unused = {}
        applied_of_credit = {}
        remaining_global = global_limit
        remaining_gross = self.gross_levy
        for credit, year, available in amounts:
            if available <= 0:
                used = self.unused.setdefault(credit['code'], {})
                used[year] = used.get(year, 0) + available
                continue
            code = credit['code']
            cap_left = limits[code] - applied_of_credit.get(code, 0)
            applied = min(available, cap_left, remaining_gross,
                          remaining_global)
            if applied < 0:
                applied = 0
            if applied > 0:
                self.credits_applied.append(
                    {'credit_code': code, 'origin_year': year,
                     'applied_cents': applied})
                applied_of_credit[code] = applied_of_credit.get(code, 0) + \
                    applied
                remaining_global -= applied
                remaining_gross -= applied
            used = self.unused.setdefault(code, {})
            used[year] = used.get(year, 0) + available - applied
        self.credits_total = sum(a['applied_cents']
                                 for a in self.credits_applied)

        # Unused amounts carried forward to 2027 (section 10-005).
        self.carryforward_out = []
        for credit in CREDITS:
            code = credit['code']
            carry = credit['carry_years'][0]
            for year in sorted(self.unused.get(code, {})):
                unused = self.unused[code][year]
                if unused > 0 and year + carry >= YEAR_END.year + 1:
                    self.carryforward_out.append(
                        {'credit_code': code, 'origin_year': year,
                         'remaining_cents': unused})
        self.carryforward_out.sort(key=lambda r: (r['credit_code'],
                                                  r['origin_year']))

    # -- Parts 11 and 12 ------------------------------------------------------
    def compute_net_levy(self):
        minimum = MINIMUM_LEVY_CENTS.get(self.entity_form)
        if minimum is None:
            raise ValueError('filer %s: %s is not an entity form of section '
                             '11-010' % (self.filer_id, self.entity_form))
        self.minimum_levy = prorate(minimum[0], self.active_days)
        after_credits = self.gross_levy - self.credits_total
        if after_credits < self.minimum_levy:
            self.minimum_topup = self.minimum_levy - after_credits
        else:
            self.minimum_topup = 0
        self.net_levy = after_credits + self.minimum_topup

    def compute_instalments(self, assessment_date):
        # Section 12-001.
        quarter_amount = self.net_levy // 4
        amounts = [quarter_amount, quarter_amount, quarter_amount,
                   self.net_levy - 3 * quarter_amount]
        unpaid = list(amounts)

        # Section 12-010.
        payments = sorted(self.payments,
                          key=lambda p: (p['paid_on'], p['payment_id']))
        taken = []
        for payment in payments:
            if payment['paid_on'] is None:
                continue
            if payment['paid_on'] > assessment_date:
                self.issues.append(
                    '%s: payment %s dated after the assessment date '
                    'disregarded' % (self.filer_id, payment['payment_id']))
            else:
                taken.append(payment)
        self.payments_cents = sum(p['amount_cents'] for p in taken)

        # Section 12-012.
        allocations = [[] for _ in QUARTERS]
        for payment in taken:
            left = payment['amount_cents']
            for index in range(len(QUARTERS)):
                if left <= 0:
                    break
                if unpaid[index] <= 0:
                    continue
                part = min(left, unpaid[index])
                unpaid[index] -= part
                left -= part
                allocations[index].append((payment['paid_on'], part))

        # Sections 12-030 and 12-040.
        interest = []
        for index, quarter in enumerate(QUARTERS):
            due = INSTALMENT_DUE_DATES[quarter]
            total = 0
            for paid_on, part in allocations[index]:
                if paid_on > due:
                    total += self.interest_on(part, due, paid_on)
            if unpaid[index] > 0 and assessment_date > due:
                total += self.interest_on(unpaid[index], due, assessment_date)
            interest.append(total)
        self.instalment_amounts = amounts
        self.instalment_paid = [sum(part for _paid, part in allocations[i])
                                for i in range(len(QUARTERS))]
        self.instalment_interest = interest
        self.interest_cents = sum(interest)
        self.balance = self.net_levy + self.interest_cents - self.payments_cents

    @staticmethod
    def interest_on(part, due, until):
        """Interest on one part of an instalment, half up (sections 12-030,
        12-040)."""
        total = Fraction(0)
        day = due + timedelta(days=1)
        while day <= until:
            total += Fraction(part * interest_ppm_on(day),
                              DAYS_IN_YEAR * 1000000)
            day += timedelta(days=1)
        return round_half_up(total)

    # -- driver ---------------------------------------------------------------
    def assess(self, assessment_date):
        self.compute_activity()
        self.compute_establishment()
        self.compute_payroll()
        self.compute_energy()
        self.compute_surcharge()
        self.primary_levy = self.activity_levy + self.floor_levy + self.surcharge
        self.gross_levy = (self.primary_levy + self.payroll_levy
                           + self.energy_levy)
        self.compute_credits()
        self.compute_net_levy()
        self.compute_instalments(assessment_date)

    def assessment_object(self):
        lines = sorted(self.receipts,
                       key=lambda l: (l['establishment_id'], l['quarter'],
                                     l['activity_code']))
        return {
            'filer_id': self.filer_id,
            'filer_class': self.filer_class,
            'entity_form': self.entity_form,
            'principal_district': self.principal_district(),
            'active_days': self.active_days,
            'predominant_class': self.predominant_class,
            'band': self.band,
            'small_enterprise_applied': self.small_enterprise_applied,
            'activity_lines': [{
                'establishment_id': l['establishment_id'],
                'reported_code': l['activity_code'],
                'assessed_code': l['assessed_code'],
                'quarter': l['quarter'],
                'assessable_cents': l['assessable_cents'],
                'rate_ppm': l['rate_ppm'],
                'levy_cents': l['levy_cents'],
            } for l in lines],
            'activity_levy_cents': self.activity_levy,
            'floor_levy_cents': self.floor_levy,
            'payroll_levy_cents': self.payroll_levy,
            'energy_levy_cents': self.energy_levy,
            'surcharge_cents': self.surcharge,
            'primary_levy_cents': self.primary_levy,
            'gross_levy_cents': self.gross_levy,
            'credits_applied': [
                {'credit_code': a['credit_code'],
                 'origin_year': a['origin_year'],
                 'applied_cents': a['applied_cents']}
                for a in self.credits_applied],
            'credits_total_cents': self.credits_total,
            'carryforward_out': self.carryforward_out,
            'minimum_levy_cents': self.minimum_levy,
            'minimum_topup_cents': self.minimum_topup,
            'net_levy_cents': self.net_levy,
            'instalments': [{
                'quarter': quarter,
                'due_date': INSTALMENT_DUE_DATES[quarter].isoformat(),
                'amount_cents': self.instalment_amounts[i],
                'paid_cents': self.instalment_paid[i],
                'interest_cents': self.instalment_interest[i],
            } for i, quarter in enumerate(QUARTERS)],
            'payments_cents': self.payments_cents,
            'interest_cents': self.interest_cents,
            'balance_cents': self.balance,
        }

    def totals(self):
        return {
            'activity_levy_cents': self.activity_levy,
            'floor_levy_cents': self.floor_levy,
            'payroll_levy_cents': self.payroll_levy,
            'energy_levy_cents': self.energy_levy,
            'surcharge_cents': self.surcharge,
            'primary_levy_cents': self.primary_levy,
            'gross_levy_cents': self.gross_levy,
            'credits_total_cents': self.credits_total,
            'minimum_topup_cents': self.minimum_topup,
            'net_levy_cents': self.net_levy,
            'payments_cents': self.payments_cents,
            'interest_cents': self.interest_cents,
            'balance_cents': self.balance,
        }


TOTAL_KEYS = [('activity_levy_cents', 'activity_levy'),
              ('floor_levy_cents', 'floor_levy'),
              ('payroll_levy_cents', 'payroll_levy'),
              ('energy_levy_cents', 'energy_levy'),
              ('surcharge_cents', 'surcharge'),
              ('primary_levy_cents', 'primary_levy'),
              ('gross_levy_cents', 'gross_levy'),
              ('credits_total_cents', 'credits_total'),
              ('minimum_topup_cents', 'minimum_topup'),
              ('net_levy_cents', 'net_levy'),
              ('payments_cents', 'payments_cents'),
              ('interest_cents', 'interest_cents'),
              ('balance_cents', 'balance')]


def sum_totals(filers):
    return {key: sum(getattr(f, attr) for f in filers)
            for key, attr in TOTAL_KEYS}


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


def load_batch(data_dir):
    """Read the batch manifest and the eight registers of a return batch.

    Returns (manifest, filers, counts) where counts holds the number of data
    rows of each register.
    """
    with open(os.path.join(data_dir, 'batch.json'), encoding='utf-8') as fh:
        manifest = json.load(fh)

    counts = {}

    filers = {}
    rows = read_csv(os.path.join(data_dir, 'filers.csv'))
    counts['filer_count'] = len(rows)
    for row in rows:
        filer = Filer(row)
        filers[filer.filer_id] = filer

    establishments = {}
    rows = read_csv(os.path.join(data_dir, 'establishments.csv'))
    counts['establishment_count'] = len(rows)
    for row in rows:
        owner = filers.get(row['filer_id'])
        if owner is None:
            continue
        opened = _date(row['opened_on']) or YEAR_START
        closed = _date(row['closed_on']) or YEAR_END
        district = DISTRICTS.get(row['district'])
        est = {
            'establishment_id': row['establishment_id'],
            'filer_id': row['filer_id'],
            'district': row['district'],
            'floor_area': _int(row['floor_area_m2']),
            'active_start': max(opened, owner.active_start),
            'active_end': min(closed, owner.active_end),
            'rate_periods': district['rate_periods'] if district else [],
            'edz': district['edz'] if district else False,
        }
        est['active_days'] = count_days(est['active_start'],
                                        est['active_end'])
        establishments[(row['filer_id'], row['establishment_id'])] = est
        owner.establishments.append(est)

    rows = read_csv(os.path.join(data_dir, 'receipts.csv'))
    counts['receipts_line_count'] = len(rows)
    for row in rows:
        filer = filers.get(row['filer_id'])
        if filer is None:
            continue
        quarter = row['quarter']
        est = establishments.get((row['filer_id'], row['establishment_id']))
        active = None
        if est is not None:
            month, last_day = QUARTER_END[quarter]
            first_month = month - 2
            extra_year = 0
            if first_month < 1:
                first_month += 12
                extra_year = -1
            days_in_quarter = clip(
                est['active_start'], est['active_end'],
                date(YEAR_START.year + extra_year, first_month, 1),
                date(YEAR_START.year, month, last_day))
            active = days_in_quarter > 0
        filer.receipts.append({
            'establishment_id': row['establishment_id'],
            'activity_code': row['activity_code'],
            'quarter': quarter,
            'gross_cents': _int(row['gross_cents']),
            'export_cents': _int(row['export_cents']),
            'establishment_active': active,
        })

    rows = read_csv(os.path.join(data_dir, 'payroll.csv'))
    counts['payroll_row_count'] = len(rows)
    for row in rows:
        filer = filers.get(row['filer_id'])
        if filer is None:
            continue
        filer.payroll.append({
            'payroll_cents': _int(row['payroll_cents']),
            'apprentice_cents': _int(row['apprentice_payroll_cents']),
        })

    rows = read_csv(os.path.join(data_dir, 'energy.csv'))
    counts['energy_row_count'] = len(rows)
    for row in rows:
        filer = filers.get(row['filer_id'])
        if filer is None:
            continue
        filer.energy.append({
            'fuel': row['fuel'],
            'quarter': row['quarter'],
            'kwh': _int(row['kwh']),
        })

    rows = read_csv(os.path.join(data_dir, 'credit_claims.csv'))
    counts['claim_count'] = len(rows)
    for row in rows:
        filer = filers.get(row['filer_id'])
        if filer is None:
            continue
        filer.claims.append({
            'claim_id': row['claim_id'],
            'credit_code': row['credit_code'],
            'expenditure_cents': _int(row['expenditure_cents']),
        })

    rows = read_csv(os.path.join(data_dir, 'carryforwards.csv'))
    counts['carryforward_count'] = len(rows)
    for row in rows:
        filer = filers.get(row['filer_id'])
        if filer is None:
            continue
        filer.carryforwards.append({
            'credit_code': row['credit_code'],
            'origin_year': int(row['origin_year']),
            'remaining_cents': _int(row['remaining_cents']),
        })

    rows = read_csv(os.path.join(data_dir, 'payments.csv'))
    counts['payment_count'] = len(rows)
    for row in rows:
        filer = filers.get(row['filer_id'])
        if filer is None:
            continue
        filer.payments.append({
            'payment_id': row['payment_id'],
            'paid_on': _date(row['paid_on']),
            'amount_cents': _int(row['amount_cents']),
        })

    return manifest, filers, counts


def value(pair):
    return {'value': pair[0], 'authority': pair[1]}


def policy_audit(batch_id):
    classes = {}
    for code in sorted(CLASSES):
        info = CLASSES[code]
        classes[code] = {
            'band': value([info['band'], info['band_auth']]),
            'export_excluded': value([info['export_excluded'],
                                       info['export_auth']]),
            'rates_ppm': {q: value(info['rates'][q]) for q in QUARTERS},
        }
    districts = {}
    for code in sorted(DISTRICTS):
        info = DISTRICTS[code]
        districts[code] = {
            'region': info['region'],
            'coastal': info['coastal'],
            'edz': info['edz'],
            'rate_periods': [{
                'from': start, 'to': end, 'rate_cents_per_m2': rate,
                'authority': authority,
            } for start, end, rate, authority in info['rate_periods']],
        }
    credits = []
    for credit in CREDITS:
        credits.append({
            'credit_code': credit['code'],
            'section': credit['section'],
            'rate_ppm': value(credit['rate_ppm']),
            'cap': {'basis': credit['cap_basis'],
                    'amount': credit['cap_amount'],
                    'authority': credit['cap_auth']},
            'carry_years': value(credit['carry_years']),
        })
    return {
        'report_id': batch_id,
        'residual_class': RESIDUAL_CLASS,
        'activity_classes': classes,
        'districts': districts,
        'regional_surcharge_ppm': {r: value(REGIONAL_SURCHARGE_PPM[r])
                                   for r in REGIONS},
        'coastal_supplement_ppm': value(COASTAL_SUPPLEMENT_PPM),
        'public_floor_factor_percent': value(PUBLIC_FLOOR_FACTOR_PERCENT),
        'payroll_rate_ppm': value(PAYROLL_RATE_PPM),
        'payroll_annual_exemption_cents': value(PAYROLL_ANNUAL_EXEMPTION_CENTS),
        'mutual_exemption_multiplier': value(MUTUAL_EXEMPTION_MULTIPLIER),
        'band_iii_energy_reduction_percent':
            value(BAND_III_ENERGY_REDUCTION_PERCENT),
        'small_enterprise_threshold_cents':
            value(SMALL_ENTERPRISE_THRESHOLD_CENTS),
        'small_enterprise_rate_factor_percent':
            value(SMALL_ENTERPRISE_RATE_FACTOR_PERCENT),
        'global_credit_cap_percent': value(GLOBAL_CREDIT_CAP_PERCENT),
        'energy_rates_millicents_per_kwh': {
            fuel: {q: value(ENERGY_RATES[fuel][q]) for q in QUARTERS}
            for fuel in sorted(ENERGY_RATES)},
        'credits': credits,
        'minimum_levy_cents': {form: value(MINIMUM_LEVY_CENTS[form])
                               for form in sorted(MINIMUM_LEVY_CENTS)},
        'interest_rate_periods': [{
            'from': start, 'to': end, 'rate_ppm': ppm, 'authority': authority,
        } for start, end, ppm, authority in INTEREST_RATE_PERIODS],
        'instalment_due_dates': {q: INSTALMENT_DUE_DATES[q].isoformat()
                                 for q in QUARTERS},
    }


def write_json(path, obj):
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        sys.stderr.write('not a directory: %s\n' % data_dir)
        return 2
    os.makedirs(out_dir, exist_ok=True)

    manifest, filers, counts = load_batch(data_dir)
    assessment_date = date.fromisoformat(manifest['assessment_date'])
    batch_id = manifest['batch_id']

    assessed = []
    for filer_id in sorted(filers):
        filer = filers[filer_id]
        filer.assess(assessment_date)
        assessed.append(filer)

    # summary.json
    summary = {
        'report_id': batch_id,
        'assessment_date': manifest['assessment_date'],
        'filer_count': len(assessed),
        'totals': sum_totals(assessed),
        'region_totals': {},
        'class_filer_counts': {c: 0 for c in ('commercial', 'mutual', 'public')},
        'balance_status_counts': {'balance_due': 0, 'settled': 0,
                                  'credit_balance': 0},
    }
    by_region = {r: [] for r in REGIONS}
    for filer in assessed:
        summary['class_filer_counts'][filer.filer_class] = \
            summary['class_filer_counts'].get(filer.filer_class, 0) + 1
        if filer.balance > 0:
            summary['balance_status_counts']['balance_due'] += 1
        elif filer.balance < 0:
            summary['balance_status_counts']['credit_balance'] += 1
        else:
            summary['balance_status_counts']['settled'] += 1
        region = DISTRICTS[filer.principal_district()]['region']
        by_region[region].append(filer)
    for region in REGIONS:
        summary['region_totals'][region] = sum_totals(by_region[region])
    write_json(os.path.join(out_dir, 'summary.json'), summary)

    # region_<Region>.json
    for region in REGIONS:
        members = sorted(by_region[region], key=lambda f: f.filer_id)
        write_json(os.path.join(out_dir, 'region_%s.json' % region), {
            'region': region,
            'filer_count': len(members),
            'totals': sum_totals(members),
            'filers': [f.assessment_object() for f in members],
        })

    # segment_<class>.json
    for segment in ('commercial', 'public'):
        members = sorted((f for f in assessed if f.filer_class == segment),
                         key=lambda f: f.filer_id)
        credit_totals = {}
        for filer in members:
            for applied in filer.credits_applied:
                code = applied['credit_code']
                credit_totals[code] = credit_totals.get(code, 0) + \
                    applied['applied_cents']
        write_json(os.path.join(out_dir, 'segment_%s.json' % segment), {
            'segment': segment,
            'filer_count': len(members),
            'totals': sum_totals(members),
            'credit_totals': credit_totals,
            'filer_ids': [f.filer_id for f in members],
        })

    # policy_audit.json
    write_json(os.path.join(out_dir, 'policy_audit.json'),
               policy_audit(batch_id))

    # data_quality.json
    issues = []
    for filer in assessed:
        issues.extend(filer.issues)
    issues.sort()
    counts['input_file_count'] = sum(
        1 for name in sorted(os.listdir(data_dir))
        if os.path.isfile(os.path.join(data_dir, name)))
    counts['quality_issue_count'] = len(issues)
    counts['quality_issues'] = issues
    write_json(os.path.join(out_dir, 'data_quality.json'), counts)

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
