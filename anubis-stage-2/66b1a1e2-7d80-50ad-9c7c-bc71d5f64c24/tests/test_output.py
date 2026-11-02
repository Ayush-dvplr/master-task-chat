"""Deterministic checks for the EXEC-OPS v5 calendar reconciliation task.

The module is self contained and imports only the standard library and
rewardkit. It carries the generator for every store the checks build, and the
SHA-256 digests of the exact report bytes the reference program writes on each
of them. It carries no implementation of the reconciliation rules.
"""

import csv
import hashlib
import io
import itertools
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import zipfile
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

from rewardkit import criteria, criterion

# =====================================================================
# Store generator.  Every store the checks run against is written here,
# from fixed seeds, using only the standard library: iCalendar, xCal and
# jCal replicas, a YAML status book, two change log shards, a pipe
# separated outbox, an XML itinerary, two SQLite databases, a PDF
# governance schedule and an XLSX office register, plus the lower
# authority copies that the authority audit compares against.
# =====================================================================


_MASK64 = (1 << 64) - 1


class _Rng(object):
    def __init__(self, seed):
        state = seed & _MASK64
        if state == 0:
            state = 0x9E3779B97F4A7C15
        self._state = state

    def next(self):
        x = self._state
        x ^= (x << 13) & _MASK64
        x ^= x >> 7
        x ^= (x << 17) & _MASK64
        self._state = x & _MASK64
        return self._state

    def below(self, n):
        return self.next() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def subset(self, seq, k):
        pool = list(seq)
        out = []
        for _ in range(min(k, len(pool))):
            out.append(pool.pop(self.below(len(pool))))
        return sorted(out)

    def shuffled(self, seq):
        pool = list(seq)
        out = []
        while pool:
            out.append(pool.pop(self.below(len(pool))))
        return out


def _fold(line):
    if len(line) <= 74:
        return line
    out = [line[:74]]
    rest = line[74:]
    while rest:
        out.append(" " + rest[:70])
        rest = rest[70:]
    return "\n".join(out)


def _fold_octets(line):
    raw = line.encode("utf-8")
    out = [raw[:75]]
    rest = raw[75:]
    while rest:
        out.append(b" " + rest[:74])
        rest = rest[74:]
    return b"\n".join(out)


def _plus_minutes(stamp, minutes):
    base = datetime(int(stamp[0:4]), int(stamp[4:6]), int(stamp[6:8]),
                    int(stamp[9:11]), int(stamp[11:13]), int(stamp[13:15]))
    return (base + timedelta(minutes=minutes)).strftime("%Y%m%dT%H%M%S")


def _put(dest, name, text):
    with open(os.path.join(dest, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _put_bytes(dest, name, blob):
    with open(os.path.join(dest, name), "wb") as fh:
        fh.write(blob)


ZONES_BASE = 'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//EXEC-OPS//Calendar Platform 4.0//EN\nCALSCALE:GREGORIAN\nX-WR-CALNAME:EXEC-OPS timezone authority\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/America-Pacific\nX-LIC-LOCATION:America/Los_Angeles\nBEGIN:STANDARD\nDTSTART:20071104T020000\nTZOFFSETFROM:-0700\nTZOFFSETTO:-0800\nTZNAME:PST\nRRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20070311T020000\nTZOFFSETFROM:-0800\nTZOFFSETTO:-0700\nTZNAME:PDT\nRRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/America-New-York\nX-LIC-LOCATION:America/New_York\nBEGIN:STANDARD\nDTSTART:20071104T020000\nTZOFFSETFROM:-0400\nTZOFFSETTO:-0500\nTZNAME:EST\nRRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20070311T020000\nTZOFFSETFROM:-0500\nTZOFFSETTO:-0400\nTZNAME:EDT\nRRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Europe-London\nX-LIC-LOCATION:Europe/London\nBEGIN:STANDARD\nDTSTART:20071028T020000\nTZOFFSETFROM:+0100\nTZOFFSETTO:+0000\nTZNAME:GMT\nRRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20070325T010000\nTZOFFSETFROM:+0000\nTZOFFSETTO:+0100\nTZNAME:BST\nRRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Australia-Central\nX-LIC-LOCATION:Australia/Adelaide\nBEGIN:STANDARD\nDTSTART:20080406T030000\nTZOFFSETFROM:+1030\nTZOFFSETTO:+0930\nTZNAME:ACST\nRRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20081005T020000\nTZOFFSETFROM:+0930\nTZOFFSETTO:+1030\nTZNAME:ACDT\nRRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Pacific-Auckland\nX-LIC-LOCATION:Pacific/Auckland\nBEGIN:STANDARD\nDTSTART:20080406T030000\nTZOFFSETFROM:+1300\nTZOFFSETTO:+1200\nTZNAME:NZST\nRRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20070930T020000\nTZOFFSETFROM:+1200\nTZOFFSETTO:+1300\nTZNAME:NZDT\nRRULE:FREQ=YEARLY;BYMONTH=9;BYDAY=-1SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Asia-Singapore\nX-LIC-LOCATION:Asia/Singapore\nBEGIN:STANDARD\nDTSTART:19960101T000000\nTZOFFSETFROM:+0800\nTZOFFSETTO:+0800\nTZNAME:SGT\nEND:STANDARD\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/America-Santiago-Ops\nX-LIC-LOCATION:America/Santiago\nX-EXEC-OPS-NOTE:Rule change published 2027-06-30 moves the 2027 forward transi\n tion earlier than the historical first Saturday of September.\nBEGIN:STANDARD\nDTSTART:20180407T000000\nTZOFFSETFROM:-0300\nTZOFFSETTO:-0400\nTZNAME:-04\nRRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SA;UNTIL=20270403T040000Z\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20180901T000000\nTZOFFSETFROM:-0400\nTZOFFSETTO:-0300\nTZNAME:-03\nRRULE:FREQ=YEARLY;BYMONTH=9;BYDAY=1SA;UNTIL=20260905T040000Z\nEND:DAYLIGHT\nBEGIN:DAYLIGHT\nDTSTART:20270814T000000\nTZOFFSETFROM:-0400\nTZOFFSETTO:-0300\nTZNAME:-03\nEND:DAYLIGHT\nBEGIN:STANDARD\nDTSTART:20280401T000000\nTZOFFSETFROM:-0300\nTZOFFSETTO:-0400\nTZNAME:-04\nRRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SA\nEND:STANDARD\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Asia-Kathmandu-Ops\nX-LIC-LOCATION:Asia/Kathmandu\nX-EXEC-OPS-NOTE:Operational offset moved from plus 5 hours 45 minutes to plus\n  6 hours on 2027-06-01 to align settlement cut off with Singapore.\nBEGIN:STANDARD\nDTSTART:20100101T000000\nTZOFFSETFROM:+0545\nTZOFFSETTO:+0545\nTZNAME:NPT\nEND:STANDARD\nBEGIN:STANDARD\nDTSTART:20270601T000000\nTZOFFSETFROM:+0545\nTZOFFSETTO:+0600\nTZNAME:NPT6\nRDATE:20270601T000000\nEND:STANDARD\nEND:VTIMEZONE\nEND:VCALENDAR\n'

ZONES_EXTRA = 'BEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Asia-Dubai\nX-EXEC-OPS-SOURCE:regional ops registry\nBEGIN:STANDARD\nDTSTART:19720101T000000\nTZOFFSETFROM:+0400\nTZOFFSETTO:+0400\nTZNAME:+04\nEND:STANDARD\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Asia-Kolkata\nX-EXEC-OPS-SOURCE:regional ops registry\nBEGIN:STANDARD\nDTSTART:19450101T000000\nTZOFFSETFROM:+0530\nTZOFFSETTO:+0530\nTZNAME:IST\nEND:STANDARD\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/America-Toronto\nX-EXEC-OPS-SOURCE:regional ops registry\nBEGIN:STANDARD\nDTSTART:20071104T020000\nTZOFFSETFROM:-0400\nTZOFFSETTO:-0500\nTZNAME:EST\nRRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20070311T020000\nTZOFFSETFROM:-0500\nTZOFFSETTO:-0400\nTZNAME:EDT\nRRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Europe-Dublin\nX-EXEC-OPS-SOURCE:regional ops registry\nBEGIN:STANDARD\nDTSTART:20080330T010000\nTZOFFSETFROM:+0000\nTZOFFSETTO:+0100\nTZNAME:IST\nRRULE:FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=25,26,27,28,29,30,31;BYDAY=SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20081026T020000\nTZOFFSETFROM:+0100\nTZOFFSETTO:+0000\nTZNAME:GMT\nRRULE:FREQ=YEARLY;BYMONTH=10;BYMONTHDAY=25,26,27,28,29,30,31;BYDAY=SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Australia-Lord-Howe\nX-EXEC-OPS-SOURCE:regional ops registry\nBEGIN:STANDARD\nDTSTART:20080406T020000\nTZOFFSETFROM:+1100\nTZOFFSETTO:+1030\nTZNAME:+1030\nRRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU\nEND:STANDARD\nBEGIN:DAYLIGHT\nDTSTART:20081005T020000\nTZOFFSETFROM:+1030\nTZOFFSETTO:+1100\nTZNAME:+11\nRRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU\nEND:DAYLIGHT\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Asia-Colombo-Ops\nX-EXEC-OPS-SOURCE:regional ops registry\nX-EXEC-OPS-NOTE:Pilot offsets for 2027 only. The second Sunday rule took effec\n t from 18 April and lapses after October.\nBEGIN:DAYLIGHT\nDTSTART:20270418T020000\nTZOFFSETFROM:+0530\nTZOFFSETTO:+0600\nTZNAME:+06\nRRULE:FREQ=YEARLY;BYMONTH=4,10;BYDAY=2SU;UNTIL=20271009T203000Z\nEND:DAYLIGHT\nBEGIN:STANDARD\nDTSTART:20270801T020000\nTZOFFSETFROM:+0600\nTZOFFSETTO:+0530\nTZNAME:+0530\nRDATE:20271107T020000\nEND:STANDARD\nEND:VTIMEZONE\nBEGIN:VTIMEZONE\nTZID:/EXEC-OPS/2027/Asia-Tehran-Ops\nX-EXEC-OPS-SOURCE:regional ops registry\nX-EXEC-OPS-NOTE:Onsets follow the solar calendar and are written as days of t\n he year.\nBEGIN:DAYLIGHT\nDTSTART:20080321T000000\nTZOFFSETFROM:+0330\nTZOFFSETTO:+0430\nTZNAME:+0430\nRRULE:FREQ=YEARLY;BYYEARDAY=81\nEND:DAYLIGHT\nBEGIN:STANDARD\nDTSTART:20080922T000000\nTZOFFSETFROM:+0430\nTZOFFSETTO:+0330\nTZNAME:+0330\nRRULE:FREQ=YEARLY;BYYEARDAY=-101\nEND:STANDARD\nEND:VTIMEZONE\n' + """BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/Europe-Central
BEGIN:STANDARD
DTSTART:19961027T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19810329T020000
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/Asia-Tokyo
BEGIN:STANDARD
DTSTART:19510908T000000
TZOFFSETFROM:+0900
TZOFFSETTO:+0900
TZNAME:JST
END:STANDARD
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/Australia-Eastern
BEGIN:STANDARD
DTSTART:20080406T030000
TZOFFSETFROM:+1100
TZOFFSETTO:+1000
TZNAME:AEST
RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20081005T020000
TZOFFSETFROM:+1000
TZOFFSETTO:+1100
TZNAME:AEDT
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/America-Sao-Paulo
BEGIN:STANDARD
DTSTART:20190217T000000
TZOFFSETFROM:-0200
TZOFFSETTO:-0300
TZNAME:-03
END:STANDARD
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/Africa-Johannesburg
BEGIN:STANDARD
DTSTART:19440319T020000
TZOFFSETFROM:+0300
TZOFFSETTO:+0200
TZNAME:SAST
END:STANDARD
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/America-Chicago
BEGIN:STANDARD
DTSTART:20071104T020000
TZOFFSETFROM:-0500
TZOFFSETTO:-0600
TZNAME:CST
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20070311T020000
TZOFFSETFROM:-0600
TZOFFSETTO:-0500
TZNAME:CDT
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/America-Denver
BEGIN:STANDARD
DTSTART:20071104T020000
TZOFFSETFROM:-0600
TZOFFSETTO:-0700
TZNAME:MST
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20070311T020000
TZOFFSETFROM:-0700
TZOFFSETTO:-0600
TZNAME:MDT
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/Pacific-Honolulu
BEGIN:STANDARD
DTSTART:19470608T020000
TZOFFSETFROM:-1030
TZOFFSETTO:-1000
TZNAME:HST
END:STANDARD
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/Asia-Hong-Kong
BEGIN:STANDARD
DTSTART:19791021T033000
TZOFFSETFROM:+0900
TZOFFSETTO:+0800
TZNAME:HKT
END:STANDARD
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:/EXEC-OPS/2027/America-Mexico-City
BEGIN:STANDARD
DTSTART:20221030T020000
TZOFFSETFROM:-0500
TZOFFSETTO:-0600
TZNAME:CST
END:STANDARD
END:VTIMEZONE
"""


def zone_text():
    return ZONES_BASE.replace("END:VCALENDAR\n", ZONES_EXTRA + "END:VCALENDAR\n")


# code, name, zone, longitude, work open, work close, solar open, solar close
OFFICES = [
    ("SFO", "San Francisco", "/EXEC-OPS/2027/America-Pacific", "-122.6250", 540, 1050, 480, 1080),
    ("LHR", "London", "/EXEC-OPS/2027/Europe-London", "-0.1276", 510, 1020, 465, 1065),
    ("ADL", "Adelaide", "/EXEC-OPS/2027/Australia-Central", "138.6250", 555, 1035, 495, 1095),
    ("AKL", "Auckland", "/EXEC-OPS/2027/Pacific-Auckland", "174.8749999999999999", 525, 1005, 450, 1050),
    ("SIN", "Singapore", "/EXEC-OPS/2027/Asia-Singapore", "103.8198", 540, 1080, 480, 1080),
    ("SCL", "Santiago", "/EXEC-OPS/2027/America-Santiago-Ops", "-70.6483", 570, 1110, 510, 1110),
    ("KTM", "Kathmandu", "/EXEC-OPS/2027/Asia-Kathmandu-Ops", "85.3125", 585, 1065, 495, 1095),
    ("JFK", "New York", "/EXEC-OPS/2027/America-New-York", "-73.9375", 510, 1050, 480, 1080),
    ("DXB", "Dubai", "/EXEC-OPS/2027/Asia-Dubai", "55.37499999999999999", 510, 1020, 465, 1065),
    ("BOM", "Mumbai", "/EXEC-OPS/2027/Asia-Kolkata", "72.6250", 555, 1095, 480, 1095),
    ("YYZ", "Toronto", "/EXEC-OPS/2027/America-Toronto", "-79.37499999999999999", 525, 1035, 480, 1080),
    ("DUB", "Dublin", "/EXEC-OPS/2027/Europe-Dublin", "-6.2603", 510, 1020, 465, 1065),
    ("LDH", "Lord Howe", "/EXEC-OPS/2027/Australia-Lord-Howe", "159.0775", 540, 1020, 480, 1080),
    ("CMB", "Colombo", "/EXEC-OPS/2027/Asia-Colombo-Ops", "79.8612", 510, 1050, 480, 1080),
    ("TEH", "Tehran", "/EXEC-OPS/2027/Asia-Tehran-Ops", "51.3890", 480, 990, 450, 1050),
    ("FRA", "Frankfurt", "/EXEC-OPS/2027/Europe-Central", "8.6821", 510, 1050, 480, 1080),
    ("NRT", "Tokyo", "/EXEC-OPS/2027/Asia-Tokyo", "139.6917", 540, 1080, 480, 1080),
    ("SYD", "Sydney", "/EXEC-OPS/2027/Australia-Eastern", "151.2093", 510, 1050, 465, 1065),
    ("GRU", "Sao Paulo", "/EXEC-OPS/2027/America-Sao-Paulo", "-46.6250", 540, 1080, 480, 1080),
    ("JNB", "Johannesburg", "/EXEC-OPS/2027/Africa-Johannesburg", "28.0473", 480, 1020, 450, 1050),
    ("ORD", "Chicago", "/EXEC-OPS/2027/America-Chicago", "-87.6298", 510, 1050, 480, 1080),
    ("DEN", "Denver", "/EXEC-OPS/2027/America-Denver", "-104.9903", 510, 1050, 480, 1080),
    ("HNL", "Honolulu", "/EXEC-OPS/2027/Pacific-Honolulu", "-157.8583", 480, 990, 450, 1050),
    ("HKG", "Hong Kong", "/EXEC-OPS/2027/Asia-Hong-Kong", "114.1694", 540, 1110, 480, 1080),
    ("MEX", "Mexico City", "/EXEC-OPS/2027/America-Mexico-City", "-99.1332", 540, 1080, 480, 1080),
    ("ZRH", "Zurich", "/EXEC-OPS/2027/Europe-Central", "8.5417", 510, 1050, 480, 1080),
]
# Offices that only fixed fixtures book; filler, homes and itineraries never draw them.
FIXTURE_OFFICES = ("ZRH",)
TZ_OF = dict((row[0], row[2]) for row in OFFICES)
WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")

# Offices whose week is not Monday to Friday.
WORKING_DAYS = {
    "DXB": ("SU", "MO", "TU", "WE", "TH"),
    "KTM": ("SU", "MO", "TU", "WE", "TH", "FR"),
    "TEH": ("SA", "SU", "MO", "TU", "WE"),
}

# Mid year changes to a working window: office, weekday codes, ISO date, open, close.
WINDOW_CHANGES = [
    ("SFO", ("MO", "TU", "WE", "TH"), "2027-06-01", 510, 1050),
    ("SFO", ("FR",), "2027-06-01", 510, 960),
    ("LHR", ("FR",), "2027-03-01", 510, 930),
    ("SIN", ("MO", "TU", "WE", "TH", "FR"), "2027-09-06", 570, 1080),
    ("JFK", ("FR",), "2027-05-28", 480, 900),
    ("DXB", ("TH",), "2027-03-07", 510, 900),
    ("NRT", ("MO", "TU", "WE", "TH", "FR"), "2027-04-01", 510, 1050),
    ("FRA", ("FR",), "2027-07-02", 480, 840),
    ("ADL", ("MO", "WE"), "2027-08-02", 525, 1035),
    ("HKG", ("SA",), "2027-01-02", 540, 780),
]

_FIRST = ["Dana", "Priya", "Tomas", "Wei Lin", "Harriet", "Nikhil", "Marcus", "Erin", "Bjorn", "Amara",
          "Rahul", "Claudia", "Sofia", "Kenji", "Ines", "Liam", "Aiko", "Mateo", "Nadia", "Oskar",
          "Leila", "Ravi", "Hana", "Diego", "Freya", "Tariq", "Mei", "Joao", "Anika", "Kwame",
          "Zara", "Pavel", "Lucia", "Emeka", "Yara", "Soren"]
_LAST = ["Okonkwo", "Raghunathan", "Ferreira", "Chua", "Bassey", "Shrestha", "Alder", "Fitzgerald",
         "Lindqvist", "Nwachukwu", "Deshpande", "Moreau", "Beltran", "Watanabe", "Duarte", "Carter",
         "Tanaka", "Silva", "Haddad", "Nilsen", "Karimi", "Iyer", "Kobayashi", "Ramirez", "Hansen",
         "Aziz", "Zhang", "Costa", "Mehta", "Mensah", "Petrova", "Rossi", "Adeyemi", "Morales",
         "Becker", "Novak", "Sato", "Gomez", "Larsen", "Osei"]

PEOPLE_COUNT = 240
# Attendees reserved for fixed scenarios; the seeded filler never draws them.
RESERVED_PEOPLE = ("ATT-013", "ATT-014", "ATT-015", "ATT-016")
SCENARIO_HOMES = ["SFO", "AKL", "SCL", "SIN", "LHR", "KTM", "JFK", "ADL", "LHR", "DXB",
                  "BOM", "YYZ", "SCL", "SIN", "DUB", "LDH"]


def people():
    rows = []
    for i in range(PEOPLE_COUNT):
        pid = "ATT-%03d" % (i + 1)
        first = _FIRST[(i * 7) % len(_FIRST)]
        last = _LAST[(i * 11 + i // len(_LAST)) % len(_LAST)]
        pool = [row[0] for row in OFFICES if row[0] not in FIXTURE_OFFICES]
        home = SCENARIO_HOMES[i] if i < len(SCENARIO_HOMES) else pool[(i * 7) % len(pool)]
        rows.append((pid, "%s %s" % (first, last), home))
    return rows


# ---------------------------------------------------------------- PDF writer


def _pdf_literal(text):
    out = []
    for ch in text:
        if ch in "()\\":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "(" + "".join(out) + ")"


def _pdf_hex(text):
    return "<" + text.encode("latin-1").hex().upper() + ">"


def _pdf_run(text, style):
    if style == 0:
        return _pdf_literal(text) + " Tj"
    if style == 1:
        return _pdf_hex(text) + " Tj"
    cut = max(1, len(text) // 2)
    return "[" + _pdf_literal(text[:cut]) + " -%d " % (10 + len(text) % 40) + _pdf_literal(text[cut:]) + "] TJ"


def write_pdf(path, title, tables, rng, rows_per_page=46):
    """tables: list of (caption, header, rows); every cell is a string."""
    pages = []
    lines = [("title", [title])]
    for caption, header, rows in tables:
        lines.append(("caption", [caption]))
        lines.append(("header", header))
        lines.extend(("row", row) for row in rows)
    page = []
    current_caption = None
    current_header = None
    for kind, cells in lines:
        if kind == "caption":
            current_caption = cells[0]
        if kind == "header":
            current_header = cells
        if len(page) >= rows_per_page and kind == "row":
            pages.append(page)
            page = [("caption", [current_caption + " (continued)"]), ("header", current_header)]
        page.append((kind, cells))
    pages.append(page)
    xs = [56, 150, 244, 338, 432, 526]
    streams = []
    for number, page in enumerate(pages):
        runs = []
        y = 780
        for kind, cells in page:
            if kind in ("title", "caption"):
                runs.append((y, 56, cells[0]))
            else:
                for col, cell in enumerate(cells):
                    runs.append((y, xs[col], cell))
            y -= 16
        runs.append((24, 280, "page %d of %d" % (number + 1, len(pages))))
        ops = ["/F1 9 Tf"]
        for y, x, text in rng.shuffled(runs):
            ops.append("BT 1 0 0 1 %d %d Tm %s ET" % (x, y, _pdf_run(text, rng.below(3))))
        streams.append(zlib.compress("\n".join(ops).encode("latin-1")))
    objects = []
    kids = []
    page_ids = []
    font_id = 3
    next_id = 4
    for stream in streams:
        page_ids.append(next_id)
        next_id += 2
    objects.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    objects.append((2, ("<< /Type /Pages /Kids [%s] /Count %d >>" % (
        " ".join("%d 0 R" % pid for pid in page_ids), len(page_ids))).encode("latin-1")))
    objects.append((font_id, b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"))
    for pid, stream in zip(page_ids, streams):
        objects.append((pid, ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                              "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                              % (font_id, pid + 1)).encode("latin-1")))
        objects.append((pid + 1, ("<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream)).encode("latin-1")
                        + stream + b"\nendstream"))
        kids.append(pid)
    objects.sort()
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for oid, body in objects:
        offsets[oid] = len(out)
        out += ("%d 0 obj\n" % oid).encode("latin-1") + body + b"\nendobj\n"
    xref = len(out)
    count = max(offsets) + 1
    out += ("xref\n0 %d\n" % count).encode("latin-1")
    out += b"0000000000 65535 f \n"
    for oid in range(1, count):
        out += ("%010d 00000 n \n" % offsets[oid]).encode("latin-1")
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (count, xref)).encode("latin-1")
    with open(path, "wb") as fh:
        fh.write(bytes(out))


# --------------------------------------------------------------- XLSX writer

_XLSX_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XLSX_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xml_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _col_letter(index):
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def write_xlsx(path, sheets, rng, date1904=True):
    """sheets: list of (name, rows); a cell is ('n', number) or ('s', text) or ('i', text) or None."""
    shared = []
    shared_index = {}
    sheet_xml = []
    for name, rows in sheets:
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<worksheet xmlns="%s"><sheetData>' % _XLSX_MAIN]
        for r, row in enumerate(rows):
            cells = []
            for c, cell in enumerate(row):
                if cell is None:
                    continue
                ref = "%s%d" % (_col_letter(c), r + 1)
                kind, value = cell
                if kind == "n":
                    cells.append('<c r="%s"><v>%s</v></c>' % (ref, value))
                elif kind == "s":
                    if value not in shared_index:
                        shared_index[value] = len(shared)
                        shared.append(value)
                    cells.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, shared_index[value]))
                else:
                    cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, _xml_escape(value)))
            parts.append('<row r="%d">%s</row>' % (r + 1, "".join(cells)))
        parts.append("</sheetData></worksheet>")
        sheet_xml.append("".join(parts))
    order = rng.shuffled(list(range(len(sheets))))
    file_of = dict((sheet_no, "sheet%d.xml" % (pos + 1)) for pos, sheet_no in enumerate(order))
    rid_of = dict((sheet_no, "rId%d" % (pos + 3)) for pos, sheet_no in enumerate(rng.shuffled(list(range(len(sheets))))))
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<workbook xmlns="%s" xmlns:r="%s"><workbookPr%s/><sheets>%s</sheets></workbook>'
                % (_XLSX_MAIN, _XLSX_REL, ' date1904="1"' if date1904 else "",
                   "".join('<sheet name="%s" sheetId="%d" r:id="%s"/>' % (_xml_escape(name), i + 1, rid_of[i])
                           for i, (name, _rows) in enumerate(sheets))))
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    rels.append('<Relationship Id="rId1" Type="%s/sharedStrings" Target="sharedStrings.xml"/>' % _XLSX_REL)
    rels.append('<Relationship Id="rId2" Type="%s/styles" Target="styles.xml"/>' % _XLSX_REL)
    for i in range(len(sheets)):
        rels.append('<Relationship Id="%s" Type="%s/worksheet" Target="worksheets/%s"/>'
                    % (rid_of[i], _XLSX_REL, file_of[i]))
    rels.append("</Relationships>")
    strings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="%s" count="%d" uniqueCount="%d">%s</sst>'
               % (_XLSX_MAIN, len(shared), len(shared), "".join("<si><t>%s</t></si>" % _xml_escape(s) for s in shared)))
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                     '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                     + "".join('<Override PartName="/xl/worksheets/%s" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                               % file_of[i] for i in range(len(sheets)))
                     + "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>' % _XLSX_REL)
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<styleSheet xmlns="%s"/>' % _XLSX_MAIN)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in (("[Content_Types].xml", content_types), ("_rels/.rels", root_rels),
                           ("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", "".join(rels)),
                           ("xl/sharedStrings.xml", strings), ("xl/styles.xml", styles)):
            info = zipfile.ZipInfo(name, date_time=(2027, 1, 4, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
        for i in range(len(sheets)):
            info = zipfile.ZipInfo("xl/worksheets/" + file_of[i], date_time=(2027, 1, 4, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, sheet_xml[i])


def serial_1904(iso):
    return (date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10])) - date(1904, 1, 1)).days


def serial_1900(iso):
    return (date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10])) - date(1899, 12, 30)).days


def _mailbox(att):
    person = PEOPLE_INDEX.get(att)
    if person is None:
        return att.lower()
    return person[1].lower().replace(" ", ".")


def _attendee_lines(people, ids, optional=()):
    lines = []
    for att in ids:
        lines.append(_fold(
            'ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=%s:mailto:%s@example.invalid' % (att, _mailbox(att))))
    for att in optional:
        lines.append(_fold(
            'ATTENDEE;ROLE=OPT-PARTICIPANT;X-ATT-ID=%s:mailto:%s@example.invalid' % (att, _mailbox(att))))
    return lines


def _vevent(uid, office, tzid, cls, dtstart, summary, sequence, last_modified,
            attendees, people, dtend=None, duration=None, rrule=None,
            exdates=(), recurrence_id=None, recurrence_range=None, optional=(), extra=()):
    lines = ["UID:" + uid]
    if recurrence_id is not None:
        params = ";TZID=" + tzid
        if recurrence_range:
            params += ";RANGE=" + recurrence_range
        lines.append("RECURRENCE-ID" + params + ":" + recurrence_id)
    lines.append("DTSTART;TZID=%s:%s" % (tzid, dtstart))
    if dtend is not None:
        lines.append("DTEND;TZID=%s:%s" % (tzid, dtend))
    if duration is not None:
        lines.append("DURATION:" + duration)
    if rrule:
        lines.append("RRULE:" + rrule)
    for exdate in exdates:
        lines.append("EXDATE;TZID=%s:%s" % (tzid, exdate))
    lines.extend(_fold(line) for line in extra)
    lines.append("SEQUENCE:%d" % sequence)
    lines.append("LAST-MODIFIED:" + last_modified)
    lines.append("DTSTAMP:" + last_modified)
    lines.append(_fold("SUMMARY:" + summary))
    lines.append("X-OFFICE:" + office)
    lines.append("X-SERIES-CLASS:" + cls)
    lines.extend(_attendee_lines(people, attendees, optional))
    lines.append("STATUS:CONFIRMED")
    return "BEGIN:VEVENT\n" + "\n".join(lines) + "\nEND:VEVENT\n"


def _calendar(body, prodid="-//EXEC-OPS//Calendar Platform 4.0//EN"):
    return ("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:%s\nCALSCALE:GREGORIAN\n%sEND:VCALENDAR\n"
            % (prodid, body))


_FILLER_SHAPES = [
    ("FREQ=WEEKLY;BYDAY=TU;COUNT=%d", "PT60M"),
    ("FREQ=WEEKLY;INTERVAL=2;BYDAY=FR;COUNT=%d", "PT45M"),
    ("FREQ=MONTHLY;BYDAY=1MO;COUNT=%d", "PT90M"),
    ("FREQ=MONTHLY;BYMONTHDAY=15;COUNT=%d", "PT30M"),
    ("FREQ=DAILY;INTERVAL=30;COUNT=%d", "PT75M"),
    ("FREQ=MONTHLY;BYDAY=MO,WE,FR;BYSETPOS=2;COUNT=%d", "PT60M"),
    ("FREQ=WEEKLY;INTERVAL=4;BYDAY=TH;COUNT=%d", "P1D"),
    ("FREQ=MONTHLY;BYDAY=-1FR;COUNT=%d", "PT120M"),
]

_FILLER_START_DAYS = [
    "20270118", "20270205", "20270222", "20270308", "20270326",
    "20270412", "20270503", "20270517", "20270604", "20270621",
    "20270708", "20270726", "20270809", "20270827", "20270913",
    "20271004", "20271018", "20271105", "20271122", "20271206",
]



def build_hidden_events(spec, rng, model):
    """Fixed scenarios S1 to S36 followed by the seeded filler of one profile."""
    tz_of = TZ_OF
    people = PEOPLE
    all_ids = [p[0] for p in people if p[0] not in RESERVED_PEOPLE]
    filler_offices = [row[0] for row in OFFICES if row[0] not in ("DUB", "LDH", "CMB", "TEH") + FIXTURE_OFFICES]
    emit = model.emit
    record = model.record

    # S1 weekly operations: sequence and modification time disagree.
    uid = "HX-WEEKLY-OPS-2027"
    base_min = rng.between(0, 3) * 15
    start1 = _plus_minutes("20270113T081500", base_min)
    end1 = _plus_minutes(start1, 60)
    emit("cal-alpha", "local", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "exec-staff", start1,
        "Weekly operations review", 3, "20270120T101500Z",
        ["ATT-001", "ATT-005", "ATT-009"], people, dtend=end1,
        rrule="FREQ=WEEKLY;INTERVAL=3;BYDAY=SU,WE;WKST=MO;UNTIL=20270526T000000Z"))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "exec-staff", start1,
        "Weekly operations review", 8, "20270119T093700Z",
        ["ATT-001", "ATT-005", "ATT-009"], people, dtend=end1,
        rrule="FREQ=WEEKLY;INTERVAL=3;BYDAY=SU,WE;WKST=SU;UNTIL=20270526T000000Z"))
    record("cal-alpha", "local", uid, "", 4, "20270120T101500Z", "week start corrected by hand")
    record("cal-alpha", "server", uid, "", 11, "20270119T093700Z", "week start set from agenda")

    # S2 early Auckland call: lands on the ambiguous and the missing local hour.
    uid = "HX-AKL-EARLY-2027"
    emit("cal-alpha", "local", uid, _vevent(
        uid, "AKL", tz_of["AKL"], "regional-sync", "20270404T023000",
        "Pacific early sync", 6, "20270330T210000Z",
        ["ATT-002", "ATT-004"], people, duration="PT45M",
        rrule="FREQ=MONTHLY;BYMONTHDAY=4,26;BYDAY=SU;COUNT=4"))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "AKL", tz_of["AKL"], "regional-sync", "20270404T023000",
        "Pacific early sync with platform", 6, "20270330T213700Z",
        ["ATT-002", "ATT-004", "ATT-010"], people, duration="PT45M",
        rrule="FREQ=MONTHLY;BYMONTHDAY=4,26;BYDAY=SU;COUNT=4"))
    record("cal-alpha", "local", uid, "", 9, "20270330T210000Z", "attendee list refreshed")
    record("cal-alpha", "server", uid, "", 14, "20270330T213700Z", "platform lead added")

    # S3 month end close: one applied and one unmatched exception date.
    uid = "HX-MONTH-CLOSE-2027"
    emit("cal-alpha", "local", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "exec-staff", "20270131T140000",
        "Month end close", 9, "20270125T120000Z",
        ["ATT-005", "ATT-009", "ATT-001"], people,
        dtend="20270131T153000",
        rrule="FREQ=MONTHLY;BYMONTHDAY=31;COUNT=6",
        exdates=["20270531T140000", "20270228T140000"]))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "exec-staff", "20270131T140000",
        "Month end close", 4, "20270126T123700Z",
        ["ATT-005", "ATT-009"], people,
        dtend="20270131T153000",
        rrule="FREQ=MONTHLY;BYMONTHDAY=31;COUNT=6"))
    record("cal-alpha", "local", uid, "", 21, "20270125T120000Z", "exception dates recorded")
    record("cal-alpha", "server", uid, "", 12, "20270126T123700Z", "no change")

    # S4 quarterly review: equal sequence, decided by the change log, duplicated uid.
    uid = "HX-QUARTER-REVIEW-2027"
    emit("cal-alpha", "local", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "exec-staff", "20270126T140000",
        "Quarter review", 6, "20270120T085300Z",
        ["ATT-004", "ATT-001", "ATT-006"], people, duration="PT90M",
        rrule="FREQ=MONTHLY;INTERVAL=3;BYDAY=MO,WE;BYSETPOS=-1;COUNT=4"))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "exec-staff", "20270126T140000",
        "Quarter review\\, board pack due five working days ahead", 6, "20270120T093700Z",
        ["ATT-004", "ATT-001", "ATT-006", "ATT-011"], people, duration="PT90M",
        rrule="FREQ=MONTHLY;INTERVAL=3;BYDAY=MO,WE;BYSETPOS=-1;COUNT=4"))
    record("cal-alpha", "local", uid, "", 9, "20270120T085300Z", "attendee list refreshed")
    record("cal-alpha", "server", uid, "", 17, "20270120T093700Z", "summary extended")
    emit("cal-beta", "local", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "exec-staff", "20270126T140000",
        "Quarter review mirror", 2, "20270118T080000Z",
        ["ATT-004", "ATT-001"], people, duration="PT90M",
        rrule="FREQ=MONTHLY;INTERVAL=3;BYDAY=MO,WE;BYSETPOS=-1;COUNT=4"))
    record("cal-beta", "local", uid, "", 3, "20270118T080000Z", "mirror copy retained")

    # S5 Santiago regional call spanning the mid year rule change.
    uid = "HX-SCL-REGIONAL-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "SCL", tz_of["SCL"], "regional-sync", "20270708T093000",
        "Americas south regional call", 2, "20270701T120000Z",
        ["ATT-003", "ATT-007"], people, dtend="20270708T103000",
        rrule="FREQ=WEEKLY;BYDAY=TH;COUNT=8"))
    record("cal-gamma", "server", uid, "", 5, "20270701T120000Z", "series published")

    # S6 individual check in with two forward ranged overrides whose deltas
    # carry seconds, so the shift must be summed in seconds before rounding.
    uid = "HX-ONE-ON-ONE-2027"
    for replica, seq, stamp in (("local", 2, "20270301T090000Z"), ("server", 2, "20270301T093700Z")):
        emit("cal-alpha", replica, uid, _vevent(
            uid, "SFO", tz_of["SFO"], "one-on-one", "20270303T083000",
            "Operations check in", seq, stamp,
            ["ATT-001", "ATT-012"], people, dtend="20270303T090000",
            rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=5"))
    record("cal-alpha", "local", uid, "", 6, "20270301T090000Z", "series published")
    record("cal-alpha", "server", uid, "", 8, "20270301T093700Z", "series published")
    emit("cal-alpha", "local", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "one-on-one", "20270310T090000",
        "Operations check in moved", 1, "20270308T090000Z",
        ["ATT-001", "ATT-012"], people, dtend="20270310T093000",
        recurrence_id="20270310T083000", recurrence_range="THISANDFUTURE"))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "one-on-one", "20270310T074430",
        "Operations check in moved", 4, "20270308T083000Z",
        ["ATT-001", "ATT-012"], people, dtend="20270310T081430",
        recurrence_id="20270310T083000", recurrence_range="THISANDFUTURE"))
    record("cal-alpha", "local", uid, "20270310T083000", 3, "20270308T090000Z", "half hour shift")
    record("cal-alpha", "server", uid, "20270310T083000", 9, "20270308T083000Z", "pulled earlier")
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "one-on-one", "20270317T091630",
        "Operations check in moved again", 2, "20270315T083000Z",
        ["ATT-001", "ATT-012"], people, dtend="20270317T094630",
        recurrence_id="20270317T083000", recurrence_range="THISANDFUTURE"))
    record("cal-alpha", "server", uid, "20270317T083000", 4, "20270315T083000Z", "pushed later")

    # S7 series carrying an override that matches no generated instance.
    uid = "HX-ORPHAN-HOST-2027"
    emit("cal-gamma", "local", uid, _vevent(
        uid, "KTM", tz_of["KTM"], "regional-sync", "20270513T101500",
        "Delivery review", 1, "20270510T060000Z",
        ["ATT-006", "ATT-011"], people, dtend="20270513T111500",
        rrule="FREQ=WEEKLY;BYDAY=TH;COUNT=3"))
    emit("cal-gamma", "local", uid, _vevent(
        uid, "KTM", tz_of["KTM"], "regional-sync", "20270603T104500",
        "Delivery review rescheduled", 1, "20270601T060000Z",
        ["ATT-006", "ATT-011"], people, dtend="20270603T114500",
        recurrence_id="20270603T101500"))
    record("cal-gamma", "local", uid, "", 2, "20270510T060000Z", "series published")

    # S8 sparse daily interval series.
    uid = "HX-JFK-SYNC-2027"
    emit("cal-alpha", "server", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "regional-sync", "20270203T110000",
        "Finance sync", 3, "20270201T140000Z",
        ["ATT-007", "ATT-001"], people, duration="PT30M",
        rrule="FREQ=DAILY;INTERVAL=21;COUNT=4"))
    record("cal-alpha", "server", uid, "", 7, "20270201T140000Z", "series published")

    # S9 all day offsite whose length depends on the duration reading.
    uid = "HX-ADL-OFFSITE-2027"
    emit("cal-beta", "local", uid, _vevent(
        uid, "ADL", tz_of["ADL"], "board-statutory", "20270103T090000",
        "Assurance offsite\\; day one\\, planning", 5, "20270102T020000Z",
        ["ATT-008", "ATT-013"], people, duration="P1D",
        rrule="FREQ=MONTHLY;BYMONTHDAY=3;COUNT=6", optional=["ATT-005"]))
    emit("cal-beta", "server", uid, _vevent(
        uid, "ADL", tz_of["ADL"], "board-statutory", "20270103T090000",
        "Assurance offsite\\; day one\\, planning", 5, "20270102T023700Z",
        ["ATT-008", "ATT-013"], people, duration="P1D",
        rrule="FREQ=MONTHLY;BYMONTHDAY=3;COUNT=6", optional=["ATT-005"]))
    record("cal-beta", "local", uid, "", 6, "20270102T020000Z", "series published")
    record("cal-beta", "server", uid, "", 6, "20270102T023700Z", "series published")

    # S10 week long Toronto block that straddles a spring transition.
    uid = "HX-YYZ-PROGRAM-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "YYZ", tz_of["YYZ"], "exec-staff", "20270309T100000",
        "Programme increment window", 4, "20270305T150000Z",
        ["ATT-013", "ATT-014"], people, duration="P1W",
        rrule="FREQ=MONTHLY;BYMONTHDAY=9;COUNT=3"))
    record("cal-gamma", "server", uid, "", 4, "20270305T150000Z", "series published")

    # S11 board statutory series in Mumbai.
    uid = "HX-BOM-BOARD-2027"
    emit("cal-beta", "local", uid, _vevent(
        uid, "BOM", tz_of["BOM"], "board-statutory", "20270212T160000",
        "Board statutory session", 3, "20270205T110000Z",
        ["ATT-011", "ATT-005", "ATT-010"], people, dtend="20270212T180000",
        rrule="FREQ=MONTHLY;BYDAY=2FR;COUNT=4"))
    emit("cal-beta", "server", uid, _vevent(
        uid, "BOM", tz_of["BOM"], "board-statutory", "20270212T160000",
        "Board statutory session", 7, "20270204T113700Z",
        ["ATT-011", "ATT-005", "ATT-010"], people, dtend="20270212T190000",
        rrule="FREQ=MONTHLY;BYDAY=2FR;COUNT=4"))
    record("cal-beta", "local", uid, "", 5, "20270205T110000Z", "agenda updated")
    record("cal-beta", "server", uid, "", 13, "20270204T113700Z", "session lengthened")

    # S12 leap day audit series that yields nothing inside the window.
    uid = "HX-AUDIT-LEAP-2027"
    emit("cal-beta", "server", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "board-statutory", "20240229T140000",
        "Quadrennial audit", 1, "20240220T140000Z",
        ["ATT-007", "ATT-005"], people, dtend="20240229T160000",
        rrule="FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29;UNTIL=20320301T000000Z"))
    record("cal-beta", "server", uid, "", 1, "20240220T140000Z", "series published")

    # S13 Dubai regional call.
    uid = "HX-DXB-REGIONAL-2027"
    emit("cal-gamma", "local", uid, _vevent(
        uid, "DXB", tz_of["DXB"], "regional-sync", "20270210T130000",
        "Gulf regional call", 2, "20270208T090000Z",
        ["ATT-010", "ATT-011", "ATT-004"], people, dtend="20270210T134500",
        rrule="FREQ=DAILY;INTERVAL=45;COUNT=4"))
    record("cal-gamma", "local", uid, "", 3, "20270208T090000Z", "series published")

    # S14 cluster of identically timed meetings that drives stabilisation.
    for i in range(spec["cluster"]):
        uid = "HX-CLUSTER-%02d-2027" % (i + 1)
        emit("cal-alpha", "server", uid, _vevent(
            uid, "SFO", tz_of["SFO"], "exec-staff", "20270202T090000",
            "Portfolio stand up %02d" % (i + 1), 1, "20270201T170000Z",
            ["ATT-001", "ATT-009", "ATT-012"], people, duration="PT90M",
            rrule="FREQ=WEEKLY;BYDAY=TU;COUNT=2"))
        record("cal-alpha", "server", uid, "", 2, "20270201T170000Z", "stand up published")

    # S15 deferrals that cross both 2027 Pacific transitions. On the spring
    # night the deferred wall clock lands in the gap; on the autumn night it
    # lands on the repeated hour, so the earlier reading is taken.
    for uid, cls, start, duration, summary in (
            ("HX-SPRING-REVIEW-2027", "exec-staff", "20270314T010000", "PT60M", "Night desk review"),
            ("HX-SPRING-CHECKIN-2027", "one-on-one", "20270314T013000", "PT30M", "Night desk check in"),
            ("HX-AUTUMN-REVIEW-2027", "exec-staff", "20271107T003000", "PT120M", "Night desk review"),
            ("HX-AUTUMN-CHECKIN-2027", "one-on-one", "20271107T010000", "PT30M", "Night desk check in")):
        emit("cal-alpha", "server", uid, _vevent(
            uid, "SFO", tz_of["SFO"], cls, start, summary, 1, "20270301T170000Z",
            ["ATT-015"], people, duration=duration))
        record("cal-alpha", "server", uid, "", 1, "20270301T170000Z", "night desk published")

    # S16 a series that overlaps itself, which only settles by deferral.
    if spec["rotation"]:
        uid = "HX-ROTATION-2027"
        emit("cal-gamma", "server", uid, _vevent(
            uid, "SIN", tz_of["SIN"], "ad-hoc", "20270705T090000",
            "Platform rotation", 1, "20270701T020000Z",
            ["ATT-016"], people, duration="P3D",
            rrule="FREQ=DAILY;INTERVAL=2;COUNT=3"))
        record("cal-gamma", "server", uid, "", 1, "20270701T020000Z", "rotation published")

    # S17 meetings in the two zones whose rules are written as day sets or
    # carry a thirty minute transition.
    if spec["zones"]:
        uid = "HX-DUB-COUNCIL-2027"
        emit("cal-gamma", "local", uid, _vevent(
            uid, "DUB", tz_of["DUB"], "regional-sync", "20270315T100000",
            "Dublin council", 1, "20270301T100000Z",
            ["ATT-015"], people, duration="PT60M",
            rrule="FREQ=MONTHLY;BYMONTHDAY=15;COUNT=3"))
        record("cal-gamma", "local", uid, "", 1, "20270301T100000Z", "council published")
        uid = "HX-LDH-WATCH-2027"
        emit("cal-gamma", "server", uid, _vevent(
            uid, "LDH", tz_of["LDH"], "regional-sync", "20271003T021500",
            "Island watch handover", 1, "20270920T010000Z",
            ["ATT-016"], people, duration="PT45M"))
        record("cal-gamma", "server", uid, "", 1, "20270920T010000Z", "watch published")

    # S19 a briefing that starts on the very instant a leg lands, so the
    # attendee is already at the arrival office and the meeting is not airborne.
    uid = "HX-LHR-ARRIVAL-2027"
    emit("cal-beta", "server", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "one-on-one", "20270512T083000",
        "Arrival briefing", 1, "20270505T090000Z",
        ["ATT-011"], people, duration="PT30M"))
    record("cal-beta", "server", uid, "", 1, "20270505T090000Z", "briefing published")

    # S20 two Adelaide bookings whose solar minutes land exactly on the
    # opening and on the closing minute of the solar window.
    for uid, start in (("HX-ADL-FACILITIES-AM-2027", "20270622T083000"),
                       ("HX-ADL-FACILITIES-PM-2027", "20270622T183000")):
        emit("cal-gamma", "server", uid, _vevent(
            uid, "ADL", tz_of["ADL"], "regional-sync", start,
            "Facilities walk through", 1, "20270615T010000Z", [], people, duration="PT30M"))
        record("cal-gamma", "server", uid, "", 1, "20270615T010000Z", "booking published")

    # S21 exclusions written as a UTC instant and in another zone, one that
    # matches nothing, no SEQUENCE and neither DTEND nor DURATION.
    uid = "HX-SFO-BROADCAST-2027"
    emit("cal-alpha", "local", uid, (
        "BEGIN:VEVENT\nUID:%s\n"
        "DTSTART;TZID=%s:20270210T170000\n"
        "RRULE:FREQ=WEEKLY;BYDAY=WE;COUNT=4\n"
        "EXDATE:20270211T010000Z\n"
        "EXDATE;TZID=%s:20270225T010000\n"
        "EXDATE;TZID=%s:20270303T180000\n"
        "LAST-MODIFIED:20270205T170000Z\nDTSTAMP:20270205T170000Z\n"
        "SUMMARY:Evening operations broadcast\nX-OFFICE:SFO\nX-SERIES-CLASS:regional-sync\n"
        "STATUS:CONFIRMED\nEND:VEVENT\n") % (uid, tz_of["SFO"], tz_of["LHR"], tz_of["SFO"]))
    record("cal-alpha", "local", uid, "", 2, "20270205T170000Z", "broadcast published")

    # S22 an overnight watch whose DTEND span crosses the spring gap.
    uid = "HX-SFO-NIGHT-WATCH-2027"
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "regional-sync", "20270306T230000",
        "Overnight systems watch", 1, "20270301T170000Z", [], people,
        dtend="20270307T040000", rrule="FREQ=WEEKLY;BYDAY=SA;COUNT=3"))
    record("cal-alpha", "server", uid, "", 1, "20270301T170000Z", "watch published")

    # S23 a San Francisco day block written in London wall clock time.
    uid = "HX-SFO-LONDON-HANDOVER-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "SFO", tz_of["LHR"], "regional-sync", "20270313T180000",
        "Transatlantic handover day", 1, "20270301T180000Z", [], people, duration="P1D"))
    record("cal-gamma", "server", uid, "", 1, "20270301T180000Z", "handover published")

    # S26 a day and a half drill whose hour part, not its day part, spans the
    # spring gap, so the hours must be added as elapsed time after the day.
    uid = "HX-SFO-WEEKEND-DRILL-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "regional-sync", "20270312T180000",
        "Weekend continuity drill", 1, "20270301T190000Z", [], people, duration="P1DT12H"))
    record("cal-gamma", "server", uid, "", 1, "20270301T190000Z", "drill published")

    # S24 a monthly desk in the Colombo pilot zone, one instance per offset period.
    uid = "HX-CMB-PILOT-2027"
    emit("cal-gamma", "local", uid, _vevent(
        uid, "CMB", tz_of["CMB"], "regional-sync", "20270314T090000",
        "Colombo pilot desk", 1, "20270301T030000Z", [], people, duration="PT60M",
        rrule="FREQ=MONTHLY;BYMONTHDAY=14;COUNT=10"))
    record("cal-gamma", "local", uid, "", 1, "20270301T030000Z", "pilot published")

    # S25 a courtesy call and an unranked review at the same time for one
    # attendee: the class absent from the matrix takes the default rank.
    for uid, cls in (("HX-COURTESY-CALL-2027", "courtesy"), ("HX-ADHOC-REVIEW-2027", "ad-hoc")):
        emit("cal-gamma", "server", uid, _vevent(
            uid, "SIN", tz_of["SIN"], cls, "20270818T100000", "Platform follow up", 1,
            "20270810T020000Z", ["ATT-016"], people, duration="PT30M"))
        record("cal-gamma", "server", uid, "", 1, "20270810T020000Z", "follow up published")

    # S27 deletions in the change log. A master deleted by the other replica
    # after the holder last wrote it is tombstoned and leaves its surviving
    # override without a master; a stale deletion loses; a deletion recorded
    # against a contested object takes no part in the ladder; a duplicate whose
    # first holder was deleted stops being a duplicate; and a resource whose
    # every key was deleted stays in the synchronisation state.
    uid = "HX-TOMB-MASTER-2027"
    emit("cal-beta", "local", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "regional-sync", "20270407T090000",
        "Records retention review", 2, "20270402T080000Z", ["ATT-005"], people,
        duration="PT45M", rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=3"))
    emit("cal-beta", "local", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "regional-sync", "20270414T100000",
        "Records retention review moved", 3, "20270410T080000Z", ["ATT-005"], people,
        duration="PT45M", recurrence_id="20270414T090000"))
    record("cal-beta", "local", uid, "", 3, "20270402T080000Z", "series published")
    record("cal-beta", "local", uid, "20270414T090000", 4, "20270410T080000Z", "one week moved")
    record("cal-beta", "server", uid, "", 5, "20270405T093700Z", "series withdrawn", op="delete")

    uid = "HX-TOMB-STALE-2027"
    emit("cal-beta", "server", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "regional-sync", "20270519T150000",
        "Vendor escalation desk", 1, "20270512T153700Z", [], people,
        duration="PT30M", rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=2"))
    record("cal-beta", "server", uid, "", 9, "20270512T153700Z", "desk recreated")
    record("cal-beta", "local", uid, "", 4, "20270510T090000Z", "desk withdrawn locally", op="delete")

    uid = "HX-TOMB-REVIVED-2027"
    for replica, summary, length in (("local", "Capital planning sync", "PT45M"),
                                     ("server", "Capital planning sync\\, extended", "PT75M")):
        emit("cal-alpha", replica, uid, _vevent(
            uid, "JFK", tz_of["JFK"], "regional-sync", "20270602T130000", summary, 3,
            "20270525T140000Z", [], people, duration=length,
            rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=3"))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "regional-sync", "20270609T150000",
        "Capital planning sync moved", 4, "20270601T140000Z", [], people,
        duration="PT75M", recurrence_id="20270609T130000"))
    record("cal-alpha", "local", uid, "", 3, "20270525T140000Z", "series published")
    record("cal-alpha", "server", uid, "", 5, "20270525T140000Z", "length extended")
    record("cal-alpha", "local", uid, "", 20, "20270520T090000Z", "stale removal from an old import", op="delete")
    record("cal-alpha", "server", uid, "20270609T130000", 6, "20270601T140000Z", "one week moved")
    record("cal-alpha", "local", uid, "20270609T130000", 8, "20270603T090000Z", "move withdrawn", op="delete")

    uid = "HX-TOMB-GONE-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "regional-sync", "20270707T110000",
        "Vendor onboarding call", 1, "20270630T020000Z", [], people, duration="PT30M"))
    record("cal-gamma", "server", uid, "", 2, "20270630T020000Z", "call published")
    record("cal-gamma", "local", uid, "", 7, "20270701T020000Z", "call withdrawn", op="delete")

    uid = "HX-NO-MASTER-2027"
    emit("cal-gamma", "local", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "regional-sync", "20270615T110000",
        "Agenda slot without a series", 2, "20270610T080000Z", [], people,
        duration="PT30M", recurrence_id="20270615T100000"))
    record("cal-gamma", "local", uid, "20270615T100000", 2, "20270610T080000Z", "slot moved")

    uid = "HX-DUP-TOMB-2027"
    emit("cal-alpha", "local", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "regional-sync", "20270804T090000",
        "Platform capacity review", 2, "20270720T020000Z", [], people,
        duration="PT60M", rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=2"))
    record("cal-alpha", "local", uid, "", 2, "20270720T020000Z", "review published")
    record("cal-alpha", "server", uid, "", 6, "20270722T023700Z", "moved to the beta calendar", op="delete")
    emit("cal-beta", "server", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "regional-sync", "20270804T093000",
        "Platform capacity review", 1, "20270722T023700Z", [], people,
        duration="PT60M", rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=2"))
    record("cal-beta", "server", uid, "", 1, "20270722T023700Z", "review recreated")

    # S28 modification times under the older ladder: a component with no
    # LAST-MODIFIED is dated by its DTSTAMP, and one with neither is older.
    def bare_event(uid, start, summary, sequence, stamps):
        return "".join(line + "\n" for line in (
            ["BEGIN:VEVENT", "UID:" + uid, "DTSTART;TZID=%s:%s" % (tz_of["LHR"], start),
             "DURATION:PT30M", "SEQUENCE:%d" % sequence] + list(stamps)
            + ["SUMMARY:" + summary, "X-OFFICE:LHR", "X-SERIES-CLASS:regional-sync",
               "STATUS:CONFIRMED", "END:VEVENT"]))
    uid = "HX-STAMP-ONLY-2027"
    emit("cal-alpha", "local", uid, bare_event(
        uid, "20270420T140000", "Treasury stamp review\\, local agenda", 2, ["DTSTAMP:20270410T120000Z"]))
    emit("cal-alpha", "server", uid, bare_event(
        uid, "20270420T140000", "Treasury stamp review", 4,
        ["DTSTAMP:20270409T093700Z", "LAST-MODIFIED:20270409T093700Z"]))
    record("cal-alpha", "local", uid, "", 2, "20270410T120000Z", "agenda rewritten")
    record("cal-alpha", "server", uid, "", 3, "20270409T093700Z", "agenda published")
    uid = "HX-STAMP-NONE-2027"
    emit("cal-alpha", "local", uid, bare_event(uid, "20270421T140000", "Treasury stamp review unsigned", 1, []))
    emit("cal-alpha", "server", uid, bare_event(
        uid, "20270421T150000", "Treasury stamp review", 1, ["DTSTAMP:20270301T000000Z"]))
    record("cal-alpha", "local", uid, "", 6, "20270415T090000Z", "imported without stamps")
    record("cal-alpha", "server", uid, "", 2, "20270301T000000Z", "agenda published")

    # S29 hour lists, set positions and day filters on weekly and daily rules.
    uid = "HX-WEEKLY-SHIFTS-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "SIN", tz_of["SIN"], "regional-sync", "20270306T190000", "Weekend shift handover", 1,
        "20270301T020000Z", [], people, duration="PT20M",
        rrule="FREQ=WEEKLY;INTERVAL=2;WKST=SU;BYDAY=SA,SU;BYHOUR=7,19;BYMINUTE=0,30;"
              "BYSETPOS=2,-2;BYMONTH=3,4;COUNT=6"))
    record("cal-gamma", "server", uid, "", 1, "20270301T020000Z", "rota published")
    uid = "HX-DAILY-MONTHEND-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "regional-sync", "20270201T160000", "Ledger lock", 1,
        "20270125T100000Z", [], people, duration="PT30M",
        rrule="FREQ=DAILY;BYMONTH=2,5,7;BYMONTHDAY=-1,-2,15;BYDAY=MO,TU,WE,TH,FR;COUNT=5"))
    record("cal-gamma", "server", uid, "", 1, "20270125T100000Z", "lock published")

    # S30 yearly rules driven by week numbers and days of the year.
    for uid, office, start, rule in (
            ("HX-YEARLY-WEEKNO-2027", "LHR", "20260102T100000", "FREQ=YEARLY;BYWEEKNO=-1,20;BYDAY=FR,SA"),
            ("HX-YEARLY-WEEKSTART-2027", "JFK", "20270105T150000",
             "FREQ=YEARLY;WKST=TU;BYWEEKNO=1,53;BYDAY=TU,FR;BYHOUR=9,15"),
            ("HX-YEARLY-YEARDAY-2027", "JFK", "20260101T090000",
             "FREQ=YEARLY;BYYEARDAY=1,59,60,-306,-1,366;BYMONTH=1,2,3,12;BYMONTHDAY=1,-1"),
            ("HX-YEARLY-WEEKNO-NODAY-2027", "SIN", "20270316T080000",
             "FREQ=YEARLY;BYWEEKNO=11,30;BYHOUR=8,16;COUNT=3")):
        emit("cal-beta", "server", uid, _vevent(
            uid, office, tz_of[office], "regional-sync", start, "Calendar control " + uid[3:-5].lower(), 1,
            "20251201T120000Z", [], people, duration="PT30M", rrule=rule))
        record("cal-beta", "server", uid, "", 1, "20251201T120000Z", "control published")

    # S31 candidates that collide in the spring gap, and additional dates
    # written in other zones, inside a gap, in a repeated hour and in UTC.
    uid = "HX-SFO-NIGHT-SWEEP-2027"
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "regional-sync", "20270313T010000", "Night patch sweep", 1,
        "20270301T170000Z", [], people, duration="PT20M", rrule="FREQ=DAILY;BYHOUR=1,2,3;COUNT=6"))
    record("cal-alpha", "server", uid, "", 1, "20270301T170000Z", "sweep published")
    uid = "HX-SFO-RDATE-ZONES-2027"
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", tz_of["SFO"], "regional-sync", "20270301T020000", "Failover rehearsal", 1,
        "20270215T170000Z", [], people, duration="PT15M",
        extra=["RDATE;TZID=%s:20270314T023000" % tz_of["SFO"],
               "RDATE;TZID=%s:20271031T013000" % tz_of["LHR"],
               "RDATE:20271107T090000Z"]))
    record("cal-alpha", "server", uid, "", 1, "20270215T170000Z", "rehearsals published")

    # S32 additional dates carrying periods, measured across the Adelaide
    # autumn transition, and additional dates that exclusions remove.
    uid = "HX-ADL-RDATE-OFFSITE-2027"
    emit("cal-beta", "server", uid, _vevent(
        uid, "ADL", tz_of["ADL"], "regional-sync", "20270301T090000", "Assurance field days", 1,
        "20270220T010000Z", [], people, duration="PT2H",
        extra=["RDATE;VALUE=PERIOD;TZID=%s:20270403T090000/P1D,20270410T090000/20270410T123000"
               % tz_of["ADL"],
               "RDATE;TZID=%s:20270417T090000" % tz_of["ADL"]]))
    record("cal-beta", "server", uid, "", 1, "20270220T010000Z", "field days published")
    uid = "HX-RDATE-EXCL-2027"
    emit("cal-beta", "local", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "regional-sync", "20270405T090000", "Audit fieldwork check", 1,
        "20270320T130000Z", [], people, duration="PT30M", rrule="FREQ=WEEKLY;BYDAY=MO;COUNT=3",
        exdates=["20270421T090000", "20270426T090000", "20270329T090000"],
        extra=["RDATE;TZID=%s:20270329T090000,20270412T090000" % tz_of["JFK"],
               "RDATE;TZID=%s:20270421T090000" % tz_of["JFK"],
               "RDATE:20270423T130000Z",
               "RDATE;TZID=%s:20270503T090000" % tz_of["JFK"],
               "EXDATE:20270423T130000Z"]))
    record("cal-beta", "local", uid, "", 1, "20270320T130000Z", "checks published")

    # S33 a desk in the zone whose onsets are days of the year.
    uid = "HX-TEH-DESK-2027"
    emit("cal-gamma", "local", uid, _vevent(
        uid, "TEH", tz_of["TEH"], "regional-sync", "20270321T100000", "Tehran liaison desk", 1,
        "20270301T060000Z", [], people, duration="PT45M",
        rrule="FREQ=MONTHLY;BYMONTH=3,9;BYMONTHDAY=21,23;COUNT=4"))
    record("cal-gamma", "local", uid, "", 1, "20270301T060000Z", "desk published")

    # S34 forward ranged overrides that hand their content on. The first moves
    # the desk to New York, adds an attendee, raises the class and lengthens
    # the call; a plain override sits in its range; the second ranged override
    # carries no content of its own, so what it hands on is the master's; a
    # cancelled ranged override hands nothing. A New York debrief collides with
    # the handed occurrence only when office, attendees and length all move.
    uid = "HX-HANDOFF-2027"
    pacific = tz_of["SFO"]
    emit("cal-alpha", "server", uid, _vevent(
        uid, "SFO", pacific, "one-on-one", "20270401T100000", "Handoff desk", 2, "20270325T170000Z",
        ["ATT-015"], people, duration="PT30M", rrule="FREQ=WEEKLY;BYDAY=TH;COUNT=6"))
    emit("cal-alpha", "server", uid, _vevent(
        uid, "JFK", pacific, "exec-staff", "20270408T101500", "Handoff desk east", 3, "20270405T170000Z",
        ["ATT-015", "ATT-016"], people, duration="PT45M", recurrence_id="20270408T100000",
        recurrence_range="THISANDFUTURE"))
    for rid, range_param, start, tail in (
            ("20270401T100000", ";RANGE=THISANDFUTURE", "20270401T120000", ["STATUS:CANCELLED"]),
            ("20270422T100000", "", "20270422T110000", ["DURATION:PT20M"]),
            ("20270429T100000", ";RANGE=THISANDFUTURE", "20270429T103000",
             ["DTEND;TZID=%s:20270429T112000" % pacific])):
        emit("cal-alpha", "server", uid, "".join(line + "\n" for line in (
            ["BEGIN:VEVENT", "UID:" + uid, "RECURRENCE-ID;TZID=%s%s:%s" % (pacific, range_param, rid),
             "DTSTART;TZID=%s:%s" % (pacific, start), "SEQUENCE:3", "LAST-MODIFIED:20270405T170000Z",
             "DTSTAMP:20270405T170000Z"] + tail + ["END:VEVENT"])))
    record("cal-alpha", "server", uid, "", 2, "20270325T170000Z", "desk published")
    uid = "HX-JFK-DEBRIEF-2027"
    emit("cal-gamma", "server", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "regional-sync", "20270415T135000", "East coast debrief", 1,
        "20270410T150000Z", ["ATT-016"], people, duration="PT30M"))
    record("cal-gamma", "server", uid, "", 1, "20270410T150000Z", "debrief published")

    # S35 settling: a pinned courtesy call keeps its slot against a higher
    # ranked huddle; two pinned board sessions can never move; deferrals that
    # overrun the working window roll to the next opening, past a closure in
    # San Francisco and past the weekend of the Gulf office.
    for uid, cls, extra in (("HX-PINNED-COURTESY-2027", "courtesy", ["X-PINNED:TRUE"]),
                            ("HX-OPS-HUDDLE-2027", "exec-staff", [])):
        emit("cal-gamma", "server", uid, _vevent(
            uid, "SIN", tz_of["SIN"], cls, "20270901T100000", "Platform follow up", 1,
            "20270825T020000Z", ["ATT-016"], people, duration="PT30M", extra=extra))
        record("cal-gamma", "server", uid, "", 1, "20270825T020000Z", "follow up published")
    for uid in ("HX-BOARD-PAIR-A-2027", "HX-BOARD-PAIR-B-2027"):
        emit("cal-beta", "server", uid, _vevent(
            uid, "BOM", tz_of["BOM"], "board-statutory", "20271020T150000", "Statutory filing session", 1,
            "20271001T090000Z", ["ATT-014"], people, duration="PT60M"))
        record("cal-beta", "server", uid, "", 1, "20271001T090000Z", "session published")
    for uid, office, start, length, att in (
            ("HX-LATE-REVIEW-A-2027", "SFO", "20271124T163000", "PT60M", "ATT-015"),
            ("HX-LATE-REVIEW-B-2027", "SFO", "20271124T163000", "PT60M", "ATT-015"),
            ("HX-GULF-WRAP-A-2027", "DXB", "20271014T163000", "PT45M", "ATT-016"),
            ("HX-GULF-WRAP-B-2027", "DXB", "20271014T163000", "PT45M", "ATT-016")):
        emit("cal-gamma", "server", uid, _vevent(
            uid, office, tz_of[office], "regional-sync", start, "Close of day review", 1,
            "20271001T090000Z", [att], people, duration=length))
        record("cal-gamma", "server", uid, "", 1, "20271001T090000Z", "review published")

    # S36 attendance on days the effective office does not work.
    for uid, office, start, att in (
            ("HX-GULF-FRIDAY-2027", "DXB", "20270205T110000", "ATT-010"),
            ("HX-SFO-CLOSURE-SAT-2027", "SFO", "20270925T100000", "ATT-004"),
            ("HX-KTM-SATURDAY-2027", "KTM", "20270612T120000", "ATT-006"),
            ("HX-KTM-SUNDAY-2027", "KTM", "20270613T120000", "ATT-006")):
        emit("cal-gamma", "local", uid, _vevent(
            uid, office, tz_of[office], "regional-sync", start, "Weekend coverage", 1,
            "20270601T090000Z", [att], people, duration="PT60M"))
        record("cal-gamma", "local", uid, "", 1, "20270601T090000Z", "coverage published")

    for i, (pid, _name, _home) in enumerate(people[:6]):
        day = 3 + i * 2
        model.busy("FBX-%s-2027" % pid, pid, "BUSY", "202703%02dT080000Z" % day, "202703%02dT180000Z" % day)
    model.busy("FBX-ATT-007-OFFERED-2027", "ATT-007", "FREE", "20270224T150000Z", "20270224T180000Z")
    model.busy("FBX-ATT-007-OFFERED-2027", "ATT-007", "FREE", "20270407T140000Z", "PT2H")
    model.busy("FBX-ATT-007-OFFERED-2027", "ATT-007", "BUSY-TENTATIVE", "20270317T143000Z", "PT1H")
    model.busy("FBX-ATT-007-OFFERED-2027", "ATT-007", None, "20270317T140000Z", "20270317T144500Z")
    model.busy("FBX-ATT-001-EVENING-2027", "ATT-001", "BUSY-TENTATIVE", "20270303T180000Z", "20270303T190000Z")
    model.busy("FBX-ATT-001-EVENING-2027", "ATT-001", "X-TRAVEL", "20270303T190000Z", "PT1H")
    model.busy("FBX-ATT-004-GULF-2027", "ATT-004", "X-TRAVEL", "20270210T083000Z", "PT1H")
    model.busy("FBX-ATT-004-GULF-2027", "ATT-004", "X-TRAVEL", "20270210T093000Z", "PT15M")
    model.busy("FBX-ATT-004-GULF-2027", "ATT-004", "BUSY-UNAVAILABLE", "20270210T090000Z", "20270210T091500Z")
    model.busy("FBX-ATT-004-GULF-2027", "ATT-004", "BUSY-TENTATIVE", "20270210T093000Z", "PT10M")


PROBE_TEXT_UIDS = ("PX-TEXT-FOLD-2027", "PX-TEXT-ESCAPE-2027", "PX-TEXT-WRAP-2027")
PROBE_PARAM_UIDS = ("PX-PARAM-2027",)
PROBE_BOUND_UIDS = (
    "PX-BOUND-ANCHOR-2027",
    "PX-BOUND-COUNT-2027",
    "PX-BOUND-HOURS-2027",
    "PX-BOUND-MIDNIGHT-2027",
    "PX-BOUND-MONTHEND-2027",
    "PX-BOUND-NEWYEAR-2027",
    "PX-BOUND-RDATE-2027",
    "PX-BOUND-UNTIL-2027",
    "PX-BOUND-WEEKNO-2027",
    "PX-BOUND-WEEKSTART-2027",
    "PX-BOUND-YEARDAY-2027",
    "PX-BOUND-YEAREND-2027",
    "PX-BOUND-YEARLY-2027",
    "PX-BOUND-ZONE-2027",
)
PROBE_OVERRIDE_UIDS = (
    "PX-OVR-CANCEL-2027",
    "PX-OVR-COLLIDE-ORDER-2027",
    "PX-OVR-COLLIDE-SEQ-2027",
    "PX-OVR-COLLIDE-TIE-2027",
    "PX-OVR-EXCLUDED-2027",
    "PX-OVR-NOMASTER-2027",
    "PX-OVR-RDATE-2027",
)


def _probe_event(lines):
    return b"BEGIN:VEVENT\n" + b"".join(
        (line if isinstance(line, bytes) else _fold_octets(line)) + b"\n" for line in lines
    ) + b"END:VEVENT\n"


def _probe_master(uid, office, start, rule, duration, summary, attendees, sequence=1,
                  stamp="20270101T090000Z", extra=()):
    tzid = dict((row[0], row[2]) for row in OFFICES)[office]
    lines = ["UID:" + uid, "DTSTAMP:" + stamp, "SUMMARY:" + summary,
             "DTSTART;TZID=%s:%s" % (tzid, start), "DURATION:" + duration]
    if rule:
        lines.append("RRULE:" + rule)
    lines.extend(extra)
    lines.extend(["X-OFFICE:" + office, "X-SERIES-CLASS:regional-sync",
                  "SEQUENCE:%d" % sequence, "LAST-MODIFIED:" + stamp, "STATUS:CONFIRMED"])
    lines.extend("ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=%s:mailto:%s@example.invalid"
                 % (att, att.lower()) for att in attendees)
    return lines


def build_probe_events(model):
    """Fixed probe fixtures, written as raw octets into one iCalendar collection."""
    tz = TZ_OF
    local = model.raw["cal-probe"]["local"]
    server = model.raw["cal-probe"]["server"]

    def record(replica, uid, rid, revision, stamp):
        model.record("cal-probe", replica, uid, rid, revision, stamp, "probe", op="create")

    # Text values: an octet fold inside a two octet character, escapes that
    # must be decoded in one pass, and continuation lines that keep part of
    # their leading whitespace.
    fold = _probe_master("PX-TEXT-FOLD-2027", "LHR", "20270601T100000", "", "PT60M", "-", ["ATT-005"])
    fold[2] = ("SUMMARY:Revisi\u00f3n del cierre trimestral de junio con Bj\u00f6rn Lindqvist, "
               "Tom\u00e1s Ferreira y el equipo de Londres")
    server.append(_probe_event(fold))
    record("server", "PX-TEXT-FOLD-2027", "", 1, "20270101T090000Z")

    escape = _probe_master("PX-TEXT-ESCAPE-2027", "SFO", "20270602T100000", "", "PT60M", "-", ["ATT-001"])
    escape[2] = ("Summary:Board pack F:\\\\packs\\\\nq3\\, final\\nsecond line "
                 "\\\\N stays\\;closed and\\Nthird line\\: done")
    server.append(_probe_event(escape))
    record("server", "PX-TEXT-ESCAPE-2027", "", 1, "20270101T090000Z")

    wrap = _probe_master("PX-TEXT-WRAP-2027", "KTM", "20270603T100000", "", "PT60M", "-", ["ATT-006"])
    wrap[2] = b"SUMMARY:Quarterly close\n  review for the Pacific\n\t desk"
    server.append(_probe_event(wrap))
    record("server", "PX-TEXT-WRAP-2027", "", 1, "20270101T090000Z")

    # Attendee parameters: quoted values holding separators, case, roles.
    param = _probe_master("PX-PARAM-2027", "JFK", "20270601T090000", "FREQ=WEEKLY;BYDAY=TU;COUNT=2",
                          "PT30M", "Treasury parameter review", [])
    param.extend([
        'ATTENDEE;CN="Ferreira, Tomas: Americas; South";ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-003'
        ':mailto:tomas.ferreira@example.invalid',
        'attendee;x-att-id=ATT-007;role=req-participant:mailto:marcus.alder@example.invalid',
        'Attendee;Role=Chair;X-Att-Id=ATT-005:mailto:harriet.bassey@example.invalid',
        'ATTENDEE;X-ATT-ID=ATT-009;CN=Bjorn Lindqvist:mailto:bjorn.lindqvist@example.invalid',
        'ATTENDEE;ROLE="REQ-PARTICIPANT";X-ATT-ID="ATT-011":mailto:rahul.deshpande@example.invalid',
        'ATTENDEE;ROLE=OPT-PARTICIPANT;X-ATT-ID=ATT-001:mailto:dana.okonkwo@example.invalid',
        'ATTENDEE;CN="Moreau; Role=Opt-Participant";X-ATT-ID=ATT-012:mailto:claudia.moreau@example.invalid',
    ])
    local.append(_probe_event(param))
    record("local", "PX-PARAM-2027", "", 1, "20270101T090000Z")

    # Window, COUNT, UNTIL and anchor boundaries.
    for uid, office, start, rule in (
            ("PX-BOUND-COUNT-2027", "LHR", "20261115T100000", "FREQ=MONTHLY;BYMONTHDAY=15;COUNT=4"),
            ("PX-BOUND-NEWYEAR-2027", "AKL", "20270101T090000", "FREQ=DAILY;COUNT=2"),
            ("PX-BOUND-YEAREND-2027", "SFO", "20271230T170000", "FREQ=DAILY;COUNT=2"),
            ("PX-BOUND-UNTIL-2027", "JFK", "20270301T090000", "FREQ=WEEKLY;BYDAY=MO;UNTIL=20270315T130000Z"),
            ("PX-BOUND-ANCHOR-2027", "LHR", "20270104T100000", "FREQ=WEEKLY;BYDAY=WE;COUNT=3"),
            ("PX-BOUND-WEEKSTART-2027", "LHR", "20270607T100000", "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,SU;COUNT=4"),
            ("PX-BOUND-MONTHEND-2027", "LHR", "20270128T100000", "FREQ=MONTHLY;BYMONTHDAY=-1,-30;COUNT=4"),
            ("PX-BOUND-YEARLY-2027", "LHR", "20260715T100000", "FREQ=YEARLY;BYMONTHDAY=15;COUNT=3"),
            ("PX-BOUND-MIDNIGHT-2027", "LHR", "20270101T000000", "")):
        local.append(_probe_event(_probe_master(uid, office, start, rule, "PT30M", "Boundary " + uid[9:-5].lower(), ["ATT-002"])))
        record("local", uid, "", 1, "20270101T090000Z")
    # A San Francisco meeting whose rule is written in London wall clock time.
    zoned = _probe_master("PX-BOUND-ZONE-2027", "SFO", "20270329T090000", "FREQ=WEEKLY;BYDAY=MO;COUNT=2",
                          "PT30M", "Boundary zone", ["ATT-002"])
    zoned[3] = "DTSTART;TZID=%s:20270329T090000" % tz["LHR"]
    local.append(_probe_event(zoned))
    record("local", "PX-BOUND-ZONE-2027", "", 1, "20270101T090000Z")
    # Additional dates before DTSTART and beyond COUNT, one outside the window
    # and one that lands on a rule instance; hour and minute lists on the
    # DTSTART day; a week number whose last week spills into the next year;
    # days of the year counted from either end.
    for uid, start, rule, extra in (
            ("PX-BOUND-RDATE-2027", "20270310T100000", "FREQ=WEEKLY;BYDAY=WE;COUNT=2",
             ["RDATE;TZID=%s:20270303T100000,20270324T100000,20261230T100000" % tz["LHR"],
              "RDATE:20270317T100000Z"]),
            ("PX-BOUND-HOURS-2027", "20270601T093000", "FREQ=DAILY;BYHOUR=8,9,17;BYMINUTE=0,30;COUNT=5", []),
            ("PX-BOUND-WEEKNO-2027", "20261230T100000", "FREQ=YEARLY;BYWEEKNO=1,-1;BYDAY=WE,FR", []),
            ("PX-BOUND-YEARDAY-2027", "20270101T120000", "FREQ=YEARLY;BYYEARDAY=-365,366,-366,100", [])):
        local.append(_probe_event(_probe_master(
            uid, "LHR", start, rule, "PT30M", "Boundary " + uid[9:-5].lower(), ["ATT-002"], extra=extra)))
        record("local", uid, "", 1, "20270101T090000Z")

    # Overrides. Two replicas write one recurrence identifier in two forms.
    uid = "PX-OVR-COLLIDE-SEQ-2027"
    master = _probe_master(uid, "SFO", "20270401T100000", "FREQ=WEEKLY;BYDAY=TH;COUNT=4", "PT60M",
                           "Collision by sequence", ["ATT-012"])
    local.append(_probe_event(master))
    server.append(_probe_event(master))
    local.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270402T090000Z", "SUMMARY:Collision by sequence",
        "RECURRENCE-ID;TZID=%s;RANGE=THISANDFUTURE:20270408T100000" % tz["SFO"],
        "DTSTART;TZID=%s:20270408T110000" % tz["SFO"], "DURATION:PT60M",
        "X-OFFICE:SFO", "SEQUENCE:2", "LAST-MODIFIED:20270402T090000Z",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-012:mailto:att-12@example.invalid"]))
    server.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270402T093700Z", "SUMMARY:Collision by sequence",
        "RECURRENCE-ID:20270408T170000Z",
        "DTSTART;TZID=%s:20270408T103000" % tz["SFO"], "DURATION:PT60M",
        "X-OFFICE:SFO", "SEQUENCE:3", "LAST-MODIFIED:20270402T093700Z",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-012:mailto:att-12@example.invalid"]))
    record("local", uid, "", 1, "20270101T090000Z")
    record("server", uid, "", 1, "20270101T090000Z")

    uid = "PX-OVR-COLLIDE-TIE-2027"
    master = _probe_master(uid, "LHR", "20270429T140000", "FREQ=WEEKLY;BYDAY=TH;COUNT=3", "PT60M",
                           "Collision by identifier", ["ATT-009"])
    server.append(_probe_event(master))
    local.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270502T090000Z", "SUMMARY:Collision by identifier",
        "RECURRENCE-ID;TZID=%s:20270506T140000" % tz["LHR"],
        "DTSTART;TZID=%s:20270506T150000" % tz["LHR"], "DURATION:PT60M",
        "X-OFFICE:LHR", "SEQUENCE:2", "LAST-MODIFIED:20270502T090000Z",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-009:mailto:att-09@example.invalid"]))
    server.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270502T093700Z", "SUMMARY:Collision by identifier",
        "RECURRENCE-ID:20270506T130000Z",
        "DTSTART;TZID=%s:20270506T160000" % tz["LHR"], "DURATION:PT60M",
        "X-OFFICE:LHR", "SEQUENCE:2", "LAST-MODIFIED:20270502T093700Z",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-009:mailto:att-09@example.invalid"]))
    record("server", uid, "", 1, "20270101T090000Z")

    uid = "PX-OVR-EXCLUDED-2027"
    master = _probe_master(uid, "KTM", "20270602T101500", "FREQ=WEEKLY;BYDAY=WE;COUNT=4", "PT60M",
                           "Override against an exclusion", ["ATT-006"],
                           extra=["EXDATE;TZID=%s:20270609T101500,20270630T101500" % tz["KTM"]])
    local.append(_probe_event(master))
    # The applied ranged override moves desks, renames itself and lists only an
    # optional attendee, so its office and summary are its own and its required
    # list and series class come from the master.
    for rid, start, rng, office, summary, attendee in (
            ("20270609T101500", "20270609T113000", "", "KTM", "Override against an exclusion",
             "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-006:mailto:att-06@example.invalid"),
            ("20270616T101500", "20270616T111500", ";Range=thisandfuture", "SIN",
             "Override against an exclusion\\, Singapore desk",
             "ATTENDEE;ROLE=OPT-PARTICIPANT;X-ATT-ID=ATT-004:mailto:att-04@example.invalid")):
        local.append(_probe_event([
            "UID:" + uid, "DTSTAMP:20270605T090000Z", "SUMMARY:" + summary,
            "RECURRENCE-ID;TZID=%s%s:%s" % (tz["KTM"], rng, rid),
            "DTSTART;TZID=%s:%s" % (tz["KTM"], start), "DURATION:PT60M",
            "X-OFFICE:" + office, "SEQUENCE:2", "LAST-MODIFIED:20270605T090000Z", attendee]))
    record("local", uid, "", 1, "20270101T090000Z")

    # Two overrides resolve to one instant; the higher SEQUENCE carries the raw
    # identifier that sorts first, so the sequence step has to decide.
    uid = "PX-OVR-COLLIDE-ORDER-2027"
    server.append(_probe_event(_probe_master(uid, "JFK", "20270506T100000", "FREQ=WEEKLY;BYDAY=TH;COUNT=3",
                                             "PT60M", "Collision by sequence order", ["ATT-010"])))
    local.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270508T090000Z", "SUMMARY:Collision by sequence order",
        "RECURRENCE-ID;TZID=%s:20270513T100000" % tz["JFK"],
        "DTSTART;TZID=%s:20270513T120000" % tz["JFK"], "DURATION:PT60M",
        "X-OFFICE:JFK", "SEQUENCE:5", "LAST-MODIFIED:20270508T090000Z",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-010:mailto:att-10@example.invalid"]))
    server.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270508T093700Z", "SUMMARY:Collision by sequence order",
        "RECURRENCE-ID:20270513T140000Z",
        "DTSTART;TZID=%s:20270513T113000" % tz["JFK"], "DURATION:PT60M",
        "X-OFFICE:JFK", "SEQUENCE:3", "LAST-MODIFIED:20270508T093700Z",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-010:mailto:att-10@example.invalid"]))
    record("server", uid, "", 1, "20270101T090000Z")

    # A ranged override that cancels its instance moves nothing after it.
    uid = "PX-OVR-CANCEL-2027"
    master = _probe_master(uid, "JFK", "20270705T090000", "FREQ=WEEKLY;BYDAY=MO;COUNT=4", "PT45M",
                           "Cancelled ranged override", ["ATT-007"])
    server.append(_probe_event(master))
    server.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270706T090000Z", "SUMMARY:Cancelled ranged override",
        "RECURRENCE-ID;TZID=%s;RANGE=THISANDFUTURE:20270712T090000" % tz["JFK"],
        "DTSTART;TZID=%s:20270712T100000" % tz["JFK"], "DURATION:PT45M",
        "X-OFFICE:JFK", "SEQUENCE:2", "LAST-MODIFIED:20270706T090000Z", "STATUS:CANCELLED",
        "ATTENDEE;ROLE=REQ-PARTICIPANT;X-ATT-ID=ATT-007:mailto:att-07@example.invalid"]))
    record("server", uid, "", 1, "20270101T090000Z")

    # An override aimed at an additional date, and a ranged override with no
    # length of its own whose one hour default replaces the length of the
    # period it displaces.
    uid = "PX-OVR-RDATE-2027"
    server.append(_probe_event(_probe_master(
        uid, "JFK", "20270705T090000", "FREQ=WEEKLY;BYDAY=MO;COUNT=2", "PT45M", "Additional date override",
        ["ATT-007"], extra=["RDATE;VALUE=PERIOD;TZID=%s:20270721T090000/PT2H" % tz["JFK"],
                           "RDATE;TZID=%s:20270728T090000" % tz["JFK"]])))
    server.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270706T090000Z", "SUMMARY:Additional date override moved",
        "RECURRENCE-ID;TZID=%s;RANGE=THISANDFUTURE:20270712T090000" % tz["JFK"],
        "DTSTART;TZID=%s:20270712T093000" % tz["JFK"],
        "X-OFFICE:JFK", "SEQUENCE:2", "LAST-MODIFIED:20270706T090000Z"]))
    server.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270706T090000Z",
        "RECURRENCE-ID;TZID=%s:20270728T090000" % tz["JFK"],
        "DTSTART;TZID=%s:20270728T110000" % tz["JFK"], "DURATION:PT15M",
        "SEQUENCE:2", "LAST-MODIFIED:20270706T090000Z"]))
    record("server", uid, "", 1, "20270101T090000Z")
    # Overrides with no master in either replica.
    uid = "PX-OVR-NOMASTER-2027"
    local.append(_probe_event([
        "UID:" + uid, "DTSTAMP:20270801T090000Z", "SUMMARY:Detached override",
        "RECURRENCE-ID;TZID=%s:20270804T100000" % tz["SFO"],
        "DTSTART;TZID=%s:20270804T110000" % tz["SFO"], "DURATION:PT30M",
        "X-OFFICE:SFO", "SEQUENCE:1", "LAST-MODIFIED:20270801T090000Z"]))
    record("local", uid, "20270804T100000", 1, "20270801T090000Z")

    for uid in PROBE_TEXT_UIDS + PROBE_PARAM_UIDS + PROBE_BOUND_UIDS + PROBE_OVERRIDE_UIDS:
        model.hrefs["cal-probe"].add(uid)




PEOPLE = people()
PEOPLE_INDEX = dict((p[0], p) for p in PEOPLE)

CLASS_NAMES = [
    "board-statutory", "exec-staff", "regional-sync", "one-on-one", "courtesy",
    "risk-committee", "vendor-review", "audit-liaison", "treasury-call", "hiring-panel",
    "product-council", "security-bridge", "legal-hold", "investor-prep", "town-hall",
    "site-visit", "budget-review", "ops-standup", "incident-review", "customer-escalation",
    "partner-sync", "training-block", "offsite-planning", "press-briefing", "compliance-check",
    "facilities-walk", "data-council", "procurement-board", "strategy-session", "mentoring",
    "recruiting-sync", "quarterly-close", "pricing-committee", "ethics-panel", "tax-review",
    "crisis-drill", "brand-review", "supply-review", "health-safety",
]
FILLER_CLASSES = CLASS_NAMES[1:] + ["ad-hoc", "ad-hoc", "unlisted-review"]
REVISIONS = (3, 4, 5, 6, 7, 8)
REGIONS = {
    "amer": ("SFO", "JFK", "YYZ", "ORD", "DEN", "MEX", "GRU", "SCL", "HNL"),
    "emea": ("LHR", "DUB", "FRA", "JNB", "DXB", "TEH"),
    "apac": ("SIN", "AKL", "ADL", "SYD", "NRT", "HKG", "BOM", "KTM", "CMB", "LDH"),
}


class StoreModel(object):
    def __init__(self, collections):
        self.collections = list(collections)
        self.raw = dict((cid, {"local": [], "server": []}) for cid in collections)
        self.hrefs = dict((cid, set()) for cid in collections)
        self.log = []
        self.busy_rows = []
        self.v3_counts = {}
        self.anchors = []

    def emit(self, collection, replica, uid, text):
        self.raw[collection][replica].append(text)
        self.hrefs[collection].add(uid)

    def record(self, collection, replica, uid, rid, revision, stamp, note, op="update"):
        self.log.append({"revision": revision, "collection": collection, "replica": replica,
                         "uid": uid, "recurrence_id": rid, "op": op, "recorded_utc": stamp, "note": note})

    def busy(self, source, attendee, fbtype, start, finish, withdrawn=0):
        self.busy_rows.append((source, attendee, fbtype, start, finish, withdrawn))


# ------------------------------------------------------------ ultra scenarios


def build_ultra_events(spec, rng, model):
    """Aliased attendees, settling clusters and journal fixtures added for v5."""
    tz_of = TZ_OF
    # U1 an on call handle whose holder changes every week, a delegation of a
    # registered identifier, a handle that points at another handle, a cycle
    # and a handle nobody maps.
    uid = "HX-ROTA-EMEA-2027"
    model.emit("cal-beta", "server", uid, _vevent(
        uid, "LHR", tz_of["LHR"], "ops-standup", "20270201T080000", "EMEA duty handover", 1,
        "20270120T080000Z", ["duty-emea", "ATT-005"], PEOPLE, duration="PT30M",
        rrule="FREQ=WEEKLY;BYDAY=MO,TH;COUNT=16"))
    model.record("cal-beta", "server", uid, "", 3, "20270120T080000Z", "rota published")
    uid = "HX-DELEGATED-REVIEW-2027"
    model.emit("cal-alpha", "local", uid, _vevent(
        uid, "JFK", tz_of["JFK"], "budget-review", "20270602T140000", "Budget line review", 2,
        "20270520T140000Z", ["ATT-007", "chief-of-staff"], PEOPLE, duration="PT45M",
        rrule="FREQ=WEEKLY;BYDAY=WE;COUNT=8"))
    model.record("cal-alpha", "local", uid, "", 4, "20270520T140000Z", "series published")
    uid = "HX-CLERK-LOOP-2027"
    model.emit("cal-gamma", "server", uid, _vevent(
        uid, "DUB", tz_of["DUB"], "legal-hold", "20270510T110000", "Board clerk filing", 1,
        "20270501T100000Z", ["board-clerk", "ops-bridge", "ATT-015"], PEOPLE, duration="PT30M",
        rrule="FREQ=MONTHLY;BYMONTHDAY=10;COUNT=5"))
    model.record("cal-gamma", "server", uid, "", 2, "20270501T100000Z", "filing published")

    # U3 planning blocks booked on top of each other; only deferral separates them.
    for k in range(spec["clusters"]):
        office = rng.pick(["SFO", "LHR", "SIN", "JFK", "FRA", "SYD"])
        day = ["20270118", "20270215", "20270322", "20270419", "20270517", "20270614",
               "20270712", "20270816", "20270913", "20271011", "20271115"][k % 11]
        hour = rng.between(9, 11)
        team = rng.subset([p[0] for p in PEOPLE[16:]], 3)
        for j in range(spec["cluster_size"]):
            uid = "HX-PLAN-%02d-%02d-2027" % (k + 1, j + 1)
            cls = rng.pick(FILLER_CLASSES)
            length = rng.pick(["PT30M", "PT45M", "PT60M"])
            model.emit(rng.pick(model.collections[:3]), "server", uid, _vevent(
                uid, office, tz_of[office], cls, "%sT%02d0000" % (day, hour), "Planning block %d.%d" % (k + 1, j + 1),
                1, "20270110T090000Z", team, PEOPLE, duration=length))
    for collection in model.collections[:3]:
        for text in model.raw[collection]["server"]:
            uid = text.split("UID:", 1)[1].split("\n", 1)[0]
            if uid.startswith("HX-PLAN-"):
                model.record(collection, "server", uid, "", 1, "20270110T090000Z", "block booked")

    # U4 one attendee books the Zurich desk once for two hours from cal-alpha and
    # twice for one hour from cal-beta: equal base cents, an odd converted total,
    # so the leftover cent of the allocation is a tie the smaller id wins.
    for collection, uid, day, length in (("cal-alpha", "HX-ZRH-DESK-A-2027", "20270615", "PT2H"),
                                         ("cal-beta", "HX-ZRH-DESK-B-2027", "20270616", "PT1H"),
                                         ("cal-beta", "HX-ZRH-DESK-C-2027", "20270617", "PT1H")):
        model.emit(collection, "server", uid, _vevent(
            uid, "ZRH", tz_of["ZRH"], "regional-sync", day + "T100000", "Zurich treasury desk", 1,
            "20270601T090000Z", ["ATT-152"], PEOPLE, duration=length))
        model.record(collection, "server", uid, "", 1, "20270601T090000Z", "desk booked")


def alias_rows(rng):
    rows = []
    pools = dict((region, [p[0] for p in PEOPLE[16:] if p[2] in offices])
                 for region, offices in REGIONS.items())
    start = date(2026, 10, 19)
    for region in ("amer", "emea", "apac"):
        holders = rng.shuffled(pools[region])
        for week in range(64):
            rows.append(("duty-%s" % region, holders[week % len(holders)],
                         (start + timedelta(days=7 * week)).isoformat(), "active"))
    rows.append(("duty-gulf", "ATT-010", "2026-12-28", "active"))
    rows.append(("duty-gulf", "duty-emea", "2027-04-05", "active"))
    rows.append(("chief-of-staff", "duty-amer", "2027-01-01", "active"))
    rows.append(("chief-of-staff", "ATT-021", "2027-06-16", "active"))
    rows.append(("chief-of-staff", "ATT-022", "2027-06-16", "active"))
    rows.append(("board-clerk", "clerk-backup", "2027-01-01", "active"))
    rows.append(("clerk-backup", "ATT-090", "2027-01-01", "active"))
    rows.append(("clerk-backup", "board-clerk", "2027-07-01", "active"))
    rows.append(("ATT-007", "ATT-031", "2027-06-09", "active"))
    rows.append(("ATT-007", "ATT-007", "2027-06-30", "active"))
    rows.append(("ATT-012", "ATT-044", "2027-03-01", "retired"))
    rows.append(("ATT-033", "ATT-034", "2027-02-01", "active"))
    rows.append(("ATT-034", "ATT-035", "2027-02-15", "active"))
    rows.append(("duty-apac", "ATT-099", "2027-08-02", "retired"))
    return rows


_SHAPE_STEP = {0: 7, 1: 14, 4: 30, 6: 28}
_SHAPE_WEEKDAY = {0: 1, 1: 4, 6: 3}
STANDARD_OFFSET = {
    "SFO": -480, "LHR": 0, "ADL": 630, "AKL": 780, "SIN": 480, "SCL": -180, "KTM": 345, "JFK": -300,
    "DXB": 240, "BOM": 330, "YYZ": -300, "DUB": 0, "LDH": 660, "CMB": 330, "TEH": 210, "FRA": 60,
    "NRT": 540, "SYD": 660, "GRU": -180, "JNB": 120, "ORD": -360, "DEN": -420, "HNL": -600, "HKG": 480,
    "MEX": -360, "ZRH": 60,
}


def _aligned_start(shape_no, day):
    base = date(int(day[0:4]), int(day[4:6]), int(day[6:8]))
    if shape_no in _SHAPE_WEEKDAY:
        base += timedelta(days=(_SHAPE_WEEKDAY[shape_no] - base.weekday()) % 7)
    elif shape_no == 3:
        base = date(base.year, base.month, 15)
    elif shape_no == 2:
        base = date(base.year, base.month, 1)
        base += timedelta(days=(0 - base.weekday()) % 7)
    return base


def build_filler(spec, rng, model, prefix="HX-FILL"):
    tz_of = TZ_OF
    all_ids = [p[0] for p in PEOPLE if p[0] not in RESERVED_PEOPLE]
    offices = [row[0] for row in OFFICES if row[0] not in ("DUB", "LDH", "CMB", "TEH") + FIXTURE_OFFICES]
    handles = ["duty-amer", "duty-emea", "duty-apac", "duty-gulf", "chief-of-staff"]
    model.anchors = []
    for i in range(spec["filler"]):
        uid = "%s-%03d-2027" % (prefix, i + 1)
        office = rng.pick(offices)
        collection = rng.pick(model.collections[:3])
        cls = rng.pick(FILLER_CLASSES)
        shape_no = rng.below(len(_FILLER_SHAPES))
        shape, dur = _FILLER_SHAPES[shape_no]
        count = rng.between(3, 6) if shape_no in _SHAPE_STEP else rng.between(2, 5)
        rrule = shape % count
        first = _aligned_start(shape_no, _FILLER_START_DAYS[rng.below(len(_FILLER_START_DAYS))])
        hour = rng.between(7, 17)
        minute = rng.pick([0, 15, 30, 45])
        dtstart = "%sT%02d%02d00" % (first.strftime("%Y%m%d"), hour, minute)
        attendees = rng.subset(all_ids, rng.between(2, 4))
        registered = list(attendees)
        if rng.below(4) == 0:
            attendees[0] = rng.pick(handles)
        seq_local = rng.between(1, 9)
        seq_server = rng.between(1, 9)
        replicas = rng.below(4)
        stamp_local = "202701%02dT%02d0000Z" % (rng.between(10, 28), rng.between(1, 20))
        stamp_server = "202701%02dT%02d3700Z" % (rng.between(10, 28), rng.between(1, 20))
        summary = "Working session %03d" % (i + 1)
        model.v3_counts[(collection, uid)] = count
        step = _SHAPE_STEP.get(shape_no)
        exdates = []
        if step and count >= 3:
            roll = rng.below(10)
            if roll < 7:
                exdates.append(_plus_minutes(dtstart, 1440 * step))
            if roll in (2, 5):
                exdates.append(_plus_minutes(dtstart, 1440 * step + 1440))
        for k in range(count):
            moment = datetime(first.year, first.month, first.day, hour, minute) + timedelta(days=(step or 31) * k)
            model.anchors.append((registered, office, moment - timedelta(minutes=STANDARD_OFFSET[office])))
        sides = []
        if replicas != 1:
            sides.append(("local", seq_local, stamp_local))
        if replicas != 0:
            sides.append(("server", seq_server, stamp_server))
        for side, seq, stamp in sides:
            model.emit(collection, side, uid, _vevent(
                uid, office, tz_of[office], cls, dtstart, summary, seq,
                stamp, attendees, PEOPLE, duration=dur, rrule=rrule, exdates=exdates))
            model.record(collection, side, uid, "", rng.between(1, 30), stamp, "published")
        if step and count >= 3 and rng.below(3) != 0:
            side = sides[-1][0]
            k = rng.between(1, count - 1)
            rid = _plus_minutes(dtstart, 1440 * step * k)
            ranged = rng.below(3) == 0
            moved = _plus_minutes(rid, rng.pick([-45, -15, 15, 30, 45, 90]))
            model.emit(collection, side, uid, _vevent(
                uid, office, tz_of[office], cls, moved, summary + " moved", sides[-1][1] + 1,
                sides[-1][2], attendees, PEOPLE, duration=dur, recurrence_id=rid,
                recurrence_range="THISANDFUTURE" if ranged else None))
            model.record(collection, side, uid, rid, rng.between(1, 30), sides[-1][2], "instance moved")


# --------------------------------------------------------- iCalendar parsing


def _unfold_text(text):
    out = []
    for line in text.split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        elif line:
            out.append(line)
    return out


def _split_line(line):
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ":" and not quoted:
            head, value = line[:i], line[i + 1:]
            break
    else:
        head, value = line, ""
    parts = []
    cur = ""
    quoted = False
    for ch in head:
        if ch == '"':
            quoted = not quoted
            cur += ch
        elif ch == ";" and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    params = []
    for piece in parts[1:]:
        key, _, val = piece.partition("=")
        params.append((key.lower(), val.strip('"')))
    return parts[0].upper(), params, value


def _unescape(value):
    out = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            out.append("\n" if nxt in "nN" else nxt)
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def parse_vevents(text):
    events = []
    current = None
    for line in _unfold_text(text):
        name, params, value = _split_line(line)
        if name == "BEGIN" and value.upper() == "VEVENT":
            current = []
        elif name == "END" and value.upper() == "VEVENT":
            events.append(current)
            current = None
        elif current is not None:
            current.append((name, params, value))
    return events


def _iso(stamp):
    stamp = stamp.strip()
    if len(stamp) == 8:
        return "%s-%s-%s" % (stamp[0:4], stamp[4:6], stamp[6:8])
    out = "%s-%s-%sT%s:%s:%s" % (stamp[0:4], stamp[4:6], stamp[6:8], stamp[9:11], stamp[11:13], stamp[13:15])
    return out + ("Z" if stamp.endswith("Z") else "")


_INT_PARTS = ("INTERVAL", "COUNT", "BYMONTH", "BYMONTHDAY", "BYYEARDAY", "BYWEEKNO", "BYHOUR",
              "BYMINUTE", "BYSETPOS")


def _recur(value):
    out = []
    for chunk in value.split(";"):
        if "=" not in chunk:
            continue
        key, val = chunk.split("=", 1)
        key = key.upper()
        if key == "UNTIL":
            out.append((key.lower(), _iso(val)))
        elif key in _INT_PARTS:
            items = [int(x) for x in val.split(",")]
            out.append((key.lower(), items[0] if len(items) == 1 else items))
        else:
            items = val.split(",")
            out.append((key.lower(), items[0] if len(items) == 1 else items))
    return out


def _typed(name, value):
    """(type, list of values) for one property, with text already unescaped."""
    if name in ("DTSTART", "DTEND", "RECURRENCE-ID", "LAST-MODIFIED", "DTSTAMP"):
        return ("date" if len(value.strip()) == 8 else "date-time"), [_iso(value)]
    if name in ("EXDATE", "RDATE"):
        pieces = [p.strip() for p in value.split(",") if p.strip()]
        if name == "RDATE" and any("/" in p for p in pieces):
            out = []
            for p in pieces:
                left, right = p.split("/", 1)
                out.append([_iso(left), right if right.startswith(("P", "+P", "-P")) else _iso(right)])
            return "period", out
        return "date-time", [_iso(p) for p in pieces]
    if name == "DURATION":
        return "duration", [value.strip()]
    if name == "RRULE":
        return "recur", [_recur(value)]
    if name == "SEQUENCE":
        return "integer", [int(value.strip())]
    if name in ("ATTENDEE", "ORGANIZER"):
        return "cal-address", [value]
    return "text", [_unescape(value)]


def to_jcal(events, prodid):
    comps = []
    for props in events:
        out = []
        for name, params, value in props:
            ptype, values = _typed(name, value)
            jparams = {}
            for key, val in params:
                jparams[key] = val
            if ptype == "recur":
                values = [dict(values[0])]
            out.append([name.lower(), jparams, ptype] + values)
        comps.append(["vevent", out, []])
    doc = ["vcalendar", [["version", {}, "text", "2.0"], ["prodid", {}, "text", prodid]], comps]
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def _x(text):
    return _xml_escape(text)


def to_xcal(events, prodid):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<icalendar xmlns="urn:ietf:params:xml:ns:icalendar-2.0">',
             "  <vcalendar>", "    <properties>",
             "      <prodid><text>%s</text></prodid>" % _x(prodid),
             "      <version><text>2.0</text></version>", "    </properties>", "    <components>"]
    for props in events:
        lines.append("      <vevent>")
        lines.append("        <properties>")
        for name, params, value in props:
            ptype, values = _typed(name, value)
            tag = name.lower()
            lines.append("          <%s>" % tag)
            if params:
                lines.append("            <parameters>")
                for key, val in params:
                    lines.append("              <%s><text>%s</text></%s>" % (key, _x(val), key))
                lines.append("            </parameters>")
            for item in values:
                if ptype == "recur":
                    lines.append("            <recur>")
                    for key, val in item:
                        for single in (val if isinstance(val, list) else [val]):
                            lines.append("              <%s>%s</%s>" % (key, _x(str(single)), key))
                    lines.append("            </recur>")
                elif ptype == "period":
                    second = "duration" if item[1].startswith(("P", "+P", "-P")) else "end"
                    lines.append("            <period><start>%s</start><%s>%s</%s></period>"
                                 % (item[0], second, item[1], second))
                else:
                    lines.append("            <%s>%s</%s>" % (ptype, _x(str(item)), ptype))
            lines.append("          </%s>" % tag)
        lines.append("        </properties>")
        lines.append("      </vevent>")
    lines.extend(["    </components>", "  </vcalendar>", "</icalendar>", ""])
    return "\n".join(lines)


def _calendar_bytes(items, prodid):
    head = ("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:%s\nCALSCALE:GREGORIAN\n" % prodid).encode("utf-8")
    body = b"".join(item if isinstance(item, bytes) else item.encode("utf-8") for item in items)
    return head + body + b"END:VCALENDAR\n"


# ------------------------------------------------------------- the outbox


def _component_keys(items):
    keys = []
    for item in items:
        text = item.decode("utf-8", "replace") if isinstance(item, bytes) else item
        uid = ""
        rid = ""
        seq = 0
        for name, _params, value in parse_vevents(text)[0]:
            if name == "UID":
                uid = value.strip()
            elif name == "RECURRENCE-ID":
                rid = value.strip()
            elif name == "SEQUENCE":
                seq = int(value.strip())
        keys.append((uid, rid, seq))
    return keys


def build_outbox(spec, rng, model):
    ops = []
    state = {}
    for collection in model.collections:
        for uid, rid, seq in _component_keys(model.raw[collection]["server"]):
            state[(collection, uid, rid)] = seq
    candidates = sorted(k for k in state if k[1].startswith(("HX-FILL", "HX-PLAN")))
    fixed = [("cal-alpha", "HX-WEEKLY-OPS-2027", ""), ("cal-alpha", "HX-ONE-ON-ONE-2027", "20270317T083000"),
             ("cal-beta", "HX-BOM-BOARD-2027", "")]
    seq_no = 100
    deleted = set()

    def add(key, op, base, field, value, stamp):
        ops.append((seq_no, key[0], key[1], key[2], op, base, field, value, stamp))

    for key in fixed:
        if key not in state:
            continue
        seq_no += 7
        add(key, "SET", state[key] + 1, "SUMMARY", "Rewritten while offline", "20270301T101500Z")
        seq_no += 7
        add(key, "SET", state[key], "SEQUENCE", str(state[key] + 2), "20270301T102000Z")
        state[key] += 2
        seq_no += 7
        add(key, "SET", state[key], "SUMMARY", "Agenda | revised offline", "20270301T103000Z")
    for _ in range(spec["outbox"]):
        if not candidates:
            break
        key = rng.pick(candidates)
        seq_no += rng.between(1, 9)
        stamp = "20270%d%02dT%02d%02d00Z" % (rng.between(2, 9), rng.between(1, 28), rng.between(0, 23), rng.pick([0, 15, 30, 45]))
        roll = rng.below(20)
        if key in deleted:
            add(key, "SET", state.get(key, 0), "SUMMARY", "Edited after removal", stamp)
            continue
        base = state[key]
        if roll < 7:
            add(key, "SET", base, "SUMMARY", "Working session note %d" % seq_no, stamp)
        elif roll < 11:
            new = base + rng.between(1, 6)
            add(key, "SET", base, "SEQUENCE", str(new), stamp)
            state[key] = new
        elif roll < 14:
            add(key, "SET", base + rng.pick([-1, 1, 2]), "SEQUENCE", str(base + 9), stamp)
        elif roll < 15:
            add(key, "DELETE", base, "", "", stamp)
            deleted.add(key)
        elif roll < 16:
            add(("cal-gamma", "HX-GHOST-%03d-2027" % seq_no, ""), "SET", 1, "SUMMARY", "Ghost edit", stamp)
        elif roll < 18:
            add(key, "SET", base, "X-SERIES-CLASS", rng.pick(FILLER_CLASSES), stamp)
        else:
            add(key, "SET", base, "DURATION", rng.pick(["PT20M", "PT50M", "PT1H15M"]), stamp)
    return ops


# ------------------------------------------------------------- registries


def governance_tables(rng):
    status = {3: "approved", 4: "approved", 5: "withdrawn", 6: "approved", 7: "draft", 8: "withdrawn"}
    approved_on = {3: "2025-02-03", 4: "2025-09-15", 5: "2026-03-02", 6: "2026-11-23", 7: "", 8: "2027-02-01"}
    revisions = [(str(r), approved_on[r] or "pending", status[r]) for r in REVISIONS]
    params = []
    for r in REVISIONS:
        params.append((str(r), str(45 if r < 6 else 40 + (r % 3) * 5), "30" if r != 8 else "20",
                       str(96 + 64 * (r - 3)), str(90 if r < 6 else 85), str(10 if r < 4 else 12)))
    ranks = []
    for c, cls in enumerate(CLASS_NAMES):
        base = 95 - (c * 7) % 90
        for r in REVISIONS:
            if (c + r) % 4 == 0 and r != 3:
                continue
            ranks.append((cls, str(r), str(max(1, base + ((c * r) % 5) - 2 * (r - 3)))))
    fx = []
    for o, row in enumerate(OFFICES):
        for r in REVISIONS:
            fx.append((row[0], str(r), str(6000 + (o * 397 + r * 131) % 9000)))
    return revisions, params, ranks, fx


def write_governance_pdf(path, rng):
    revisions, params, ranks, fx = governance_tables(rng)
    write_pdf(path, "EXEC-OPS escalation and treasury schedule", [
        ("Table 1. Revision register", ["revision", "approved on", "status"], revisions),
        ("Table 2. Settling parameters", ["revision", "buffer min", "quantum min", "round cap", "pin rank",
                                          "default rank"], params),
        ("Table 3. Series class ranks", ["class", "revision", "rank"], ranks),
        ("Table 4. Office conversion", ["office", "revision", "basis points"], fx),
    ], rng)


def register_rows(edition_shift):
    rows = []
    for code, name, tzid, lon, wo, wc, so, sc in OFFICES:
        days = WORKING_DAYS.get(code, ("MO", "TU", "WE", "TH", "FR"))
        longitude = lon
        if edition_shift:
            longitude = ("%.4f" % (float(lon) + 0.0125 * edition_shift)) if code in ("AKL", "SFO", "ADL", "DXB", "YYZ") else lon
        for wd in WEEKDAY_CODES:
            working = wd in days
            rows.append([code, tzid, longitude, wd, "Y" if working else "N",
                         wo if working else 0, wc if working else 0, so, sc, "2026-01-01"])
        for office, wds, when, opn, cls in WINDOW_CHANGES:
            if office == code:
                for wd in wds:
                    rows.append([code, tzid, longitude, wd, "Y", opn - 15 * edition_shift, cls, so, sc, when])
    return rows


def rate_rows(rng, stale=False):
    rows = []
    for i, (pid, _name, _home) in enumerate(PEOPLE):
        cents = 4500 + (i * 977) % 21000
        if stale:
            cents -= 250 + (i % 7) * 50
        rows.append([pid, cents, "2026-01-01"])
        if i % 9 == 4 and not stale:
            rows.append([pid, cents + 1250 + (i % 5) * 25, "2027-%02d-01" % (2 + i % 10)])
    return rows


def write_register_xlsx(path, rng, edition, date1904=True):
    serial = serial_1904 if date1904 else serial_1900

    def sheet(kind, label, status, rows, shift):
        header = [("s", "office"), ("s", "tzid"), ("s", "longitude"), ("s", "weekday"), ("s", "working"),
                  ("s", "open minute"), ("s", "close minute"), ("s", "solar open"), ("s", "solar close"),
                  ("s", "effective from")]
        out = [[("s", kind), ("s", label)], [("s", "status"), ("s", status)],
               [("i", "Serial dates count days from the workbook epoch.")], header]
        for row in rows:
            cells = []
            for c, value in enumerate(row):
                if c == 2:
                    cells.append(("i", value))
                elif c in (5, 6, 7, 8):
                    cells.append(("s", str(value)) if (len(out) + c) % 5 == 0 else ("n", value))
                elif c == 9:
                    cells.append(("n", serial(value)))
                else:
                    cells.append(("s", value))
            out.append(cells)
        return out

    previous = "R%d" % (int(edition[1:]) - 1)
    following = "R%d" % (int(edition[1:]) + 1)
    rates = [[("s", "attendee rates"), ("s", edition)], [("s", "status"), ("s", "in force")],
             [("i", "Rates are cents per hour.")], [("s", "attendee"), ("s", "cents per hour"), ("s", "effective from")]]
    for pid, cents, when in rate_rows(rng):
        text = "{:,}".format(cents) if cents % 3 == 0 else None
        rates.append([("s", pid), ("i", text) if text else ("n", cents), ("n", serial(when))])
    draft_rates = [[("s", "attendee rates"), ("s", following)], [("s", "status"), ("s", "draft")],
                   [("i", "Proposed rates.")], [("s", "attendee"), ("s", "cents per hour"), ("s", "effective from")]]
    for pid, cents, when in rate_rows(rng):
        draft_rates.append([("s", pid), ("n", cents + 333), ("n", serial(when))])
    sheets = [
        ("Register %s" % edition, sheet("office register", edition, "superseded", register_rows(1), 1)),
        ("Register %s (2)" % edition, sheet("office register", edition, "in force", register_rows(0), 0)),
        ("Register %s" % previous, sheet("office register", previous, "withdrawn", register_rows(2), 2)),
        ("Register %s draft" % following, sheet("office register", following, "draft", register_rows(3), 3)),
        ("Rates", rates),
        ("Rates proposal", draft_rates),
    ]
    write_xlsx(path, sheets, rng, date1904)


def _closure_rows(rng):
    base = [
        ("ADL", "2027-06-14", "King's Birthday"), ("ADL", "2027-12-28", "Proclamation Day"),
        ("AKL", "2027-04-26", "Anzac Day observed"), ("AKL", "2027-10-25", "Labour Day"),
        ("BOM", "2027-08-15", "Independence Day"), ("BOM", "2027-11-08", "Diwali"),
        ("DUB", "2027-03-17", "Saint Patrick's Day"), ("DXB", "2027-12-02", "National Day"),
        ("DXB", "2027-03-19", "Ramadan office closure"), ("JFK", "2027-08-12", "Building services closure"),
        ("JFK", "2027-11-25", "Thanksgiving"), ("KTM", "2027-09-13", "Constitution Day"),
        ("LDH", "2027-10-04", "Labour Day"), ("LHR", "2027-05-31", "Spring bank holiday"),
        ("LHR", "2027-12-27", "Christmas Day observed"), ("SCL", "2027-08-05", "Regional civic holiday"),
        ("SCL", "2027-09-18", "Independence Day"), ("SFO", "2027-09-25", "Campus maintenance closure"),
        ("SFO", "2027-11-25", "Thanksgiving"), ("SIN", "2027-06-17", "Hari Raya Haji"),
        ("SIN", "2027-08-09", "National Day"), ("SIN", "2027-10-27", "Deepavali"),
        ("YYZ", "2027-07-01", "Canada Day"), ("YYZ", "2027-10-11", "Thanksgiving"),
    ]
    rows = [(o, d, n, 1, "open") for o, d, n in base]
    for o, row in enumerate(OFFICES):
        for k in range(8):
            day = date(2027, 1, 1) + timedelta(days=(o * 37 + k * 45 + 11) % 360)
            rows.append((row[0], day.isoformat(), "Office closure %d" % (k + 1), 1, "open"))
    rows.append(("SFO", "2027-07-02", "Facilities shutdown", 1, "open"))
    rows.append(("SFO", "2027-07-02", "Facilities shutdown", 2, "withdrawn"))
    rows.append(("SFO", "2027-07-06", "Facilities shutdown", 2, "open"))
    rows.append(("LHR", "2027-08-30", "Summer bank holiday", 1, "withdrawn"))
    rows.append(("LHR", "2027-08-30", "Summer bank holiday", 3, "open"))
    rows.append(("SIN", "2027-01-29", "Lunar new year eve", 2, "withdrawn"))
    return rows


def _leg_rows(rng, model):
    legs = [
        ("LEG-001", "ATT-002", "AKL", "SFO", "20270404T023000", "20270403T190000", "NZ0008", "confirmed"),
        ("LEG-002", "ATT-001", "SFO", "SIN", "20270115T013000", "20270116T083000", "SQ0031", "confirmed"),
        ("LEG-003", "ATT-004", "SIN", "SFO", "20270419T063000", "20270419T073000", "SQ0032", "confirmed"),
        ("LEG-004", "ATT-003", "SCL", "JFK", "20270810T091000", "20270810T173000", "LA0532", "confirmed"),
        ("LEG-005", "ATT-005", "LHR", "AKL", "20270920T210000", "20270922T060000", "NZ0001", "confirmed"),
        ("LEG-006", "ATT-006", "KTM", "SIN", "20270615T081500", "20270615T160000", "SQ0447", "confirmed"),
        ("LEG-007", "ATT-009", "LHR", "YYZ", "20270311T104500", "20270311T133000", "AC0857", "confirmed"),
        ("LEG-008", "ATT-009", "YYZ", "LHR", "20270318T203000", "20270319T080000", "AC0856", "confirmed"),
        ("LEG-009", "ATT-010", "DXB", "BOM", "20270210T081500", "20270210T130000", "EK0500", "confirmed"),
        ("LEG-010", "ATT-011", "BOM", "LHR", "20270512T033000", "20270512T083000", "BA0138", "confirmed"),
        ("LEG-011", "ATT-012", "YYZ", "AKL", "20270701T190000", "20270703T053000", "NZ0007", "confirmed"),
        ("LEG-012", "ATT-014", "SIN", "SCL", "20271104T063000", "20271104T220000", "LA0801", "confirmed"),
    ]
    homes = dict((p[0], p[2]) for p in PEOPLE)
    pool = [p[0] for p in PEOPLE[16:]]
    codes = [row[0] for row in OFFICES if row[0] not in FIXTURE_OFFICES]
    n = 12
    for attendees, office, moment in model.anchors[::2] + model.anchors[1::4]:
        att = rng.pick(attendees)
        home = homes[att]
        dest = rng.pick([c for c in codes if c != home])
        dep = moment + timedelta(minutes=STANDARD_OFFSET[home] + rng.pick([-150, -100, -40, 20, 45, 60, 90, 150]))
        arr = dep + timedelta(minutes=STANDARD_OFFSET[dest] - STANDARD_OFFSET[home] + 60 * rng.between(2, 14))
        status = "cancelled" if rng.below(11) == 0 else "confirmed"
        legs.append(("LEG-%03d" % (n + 1), att, home, dest, dep.strftime("%Y%m%dT%H%M%S"),
                     arr.strftime("%Y%m%dT%H%M%S"), "XA%04d" % (n + 1), status))
        n += 1
    while n < 420:
        att = rng.pick(pool)
        home = homes[att]
        dest = rng.pick([c for c in codes if c != home])
        day = date(2027, 1, 5) + timedelta(days=rng.below(350))
        hours = rng.between(3, 15)
        dep = datetime(day.year, day.month, day.day, rng.between(6, 21), rng.pick([0, 15, 30, 45]))
        arr = dep + timedelta(hours=hours + rng.between(-6, 6))
        back = dep + timedelta(days=rng.between(3, 9))
        backarr = back + timedelta(hours=hours + rng.between(-6, 6))
        status = "cancelled" if rng.below(13) == 0 else "confirmed"
        legs.append(("LEG-%03d" % (n + 1), att, home, dest, dep.strftime("%Y%m%dT%H%M%S"),
                     arr.strftime("%Y%m%dT%H%M%S"), "XX%04d" % (n + 1), status))
        legs.append(("LEG-%03d" % (n + 2), att, dest, home, back.strftime("%Y%m%dT%H%M%S"),
                     backarr.strftime("%Y%m%dT%H%M%S"), "XX%04d" % (n + 2), "confirmed"))
        n += 2
    return legs


def _busy_rows(rng, model):
    rows = list(model.busy_rows)
    pool = [p[0] for p in PEOPLE[16:]]
    for k, (attendees, _office, moment) in enumerate(model.anchors):
        start = moment - timedelta(minutes=rng.pick([30, 60, 90]))
        kind = rng.pick(["BUSY", "BUSY-TENTATIVE", "BUSY-UNAVAILABLE", "FREE", None, "X-TRAVEL"])
        rows.append(("FBX-ANCHOR-%03d" % k, rng.pick(attendees), kind, start.strftime("%Y%m%dT%H%M%SZ"),
                     "PT%dM" % rng.pick([60, 90, 120]), 1 if rng.below(19) == 0 else 0))
    for k in range(120):
        att = rng.pick(pool)
        day = date(2027, 1, 4) + timedelta(days=rng.below(355))
        start = datetime(day.year, day.month, day.day, rng.between(0, 22), rng.pick([0, 15, 30, 45]))
        kind = rng.pick(["BUSY", "BUSY", "BUSY-TENTATIVE", "BUSY-UNAVAILABLE", "FREE", None, "X-TRAVEL"])
        if rng.below(2):
            finish = "PT%dM" % rng.pick([30, 45, 60, 90, 120, 240])
        else:
            finish = (start + timedelta(minutes=rng.pick([30, 60, 75, 180]))).strftime("%Y%m%dT%H%M%SZ")
        rows.append(("FBX-GEN-%03d" % k, att, kind, start.strftime("%Y%m%dT%H%M%SZ"), finish,
                     1 if rng.below(17) == 0 else 0))
    return rows


ZONE_ALIASES = [
    ("Pacific Standard Time", "US-Pacific", "active"),
    ("US-Pacific", "/EXEC-OPS/2027/America-Pacific", "active"),
    ("GMT Standard Time", "/EXEC-OPS/2027/Europe-London", "active"),
    ("Europe/London-Legacy", "GMT Standard Time", "active"),
    ("Eastern Standard Time", "/EXEC-OPS/2027/America-New-York", "active"),
    ("Singapore Standard Time", "/EXEC-OPS/2027/Asia-Singapore", "active"),
    ("Cen. Australia Standard Time", "/EXEC-OPS/2027/Australia-Central", "active"),
    ("US-Pacific-Old", "/EXEC-OPS/2027/America-New-York", "retired"),
]
ALIAS_FOR = {
    "/EXEC-OPS/2027/America-Pacific": ["Pacific Standard Time", "US-Pacific"],
    "/EXEC-OPS/2027/Europe-London": ["GMT Standard Time", "Europe/London-Legacy"],
    "/EXEC-OPS/2027/America-New-York": ["Eastern Standard Time"],
    "/EXEC-OPS/2027/Asia-Singapore": ["Singapore Standard Time"],
    "/EXEC-OPS/2027/Australia-Central": ["Cen. Australia Standard Time"],
}

PROFILES = {
    "shipped": {"seed": 20270113, "cluster": 2, "filler": 900, "rotation": False, "zones": True,
                "clusters": 13, "cluster_size": 6, "outbox": 220, "policy": "mtime-major", "semantics": "exact",
                "revision": 7, "edition": "R7", "authority": "server", "names": 11, "alias_rate": 7,
                "encodings": {"cal-alpha": ("ics", "xcal"), "cal-beta": ("jcal", "ics"), "cal-gamma": ("ics", "jcal")}},
    "challenge": {"seed": 20270926, "cluster": 0, "filler": 50, "rotation": False, "zones": False,
                  "clusters": 3, "cluster_size": 5, "outbox": 120, "policy": "sequence-major", "semantics": "nominal",
                  "revision": 6, "edition": "R7", "authority": "local", "names": 23, "alias_rate": 5,
                  "encodings": {"cal-alpha": ("xcal", "ics"), "cal-beta": ("ics", "jcal"), "cal-gamma": ("jcal", "xcal")}},
    "eval": {"seed": 20270404, "cluster": 8, "filler": 70, "rotation": True, "zones": False,
             "clusters": 6, "cluster_size": 6, "outbox": 160, "policy": "sequence-major", "semantics": "nominal",
             "revision": 8, "edition": "R4", "authority": "local", "names": 37, "alias_rate": 4,
             "date1904": False,
             "encodings": {"cal-alpha": ("jcal", "xcal"), "cal-beta": ("xcal", "ics"), "cal-gamma": ("ics", "ics")}},
    "dense": {"seed": 20270814, "cluster": 2, "filler": 120, "rotation": True, "zones": True,
              "clusters": 6, "cluster_size": 6, "outbox": 240, "policy": "sequence-major", "semantics": "nominal",
              "revision": 9, "edition": "R9", "authority": "local", "names": 41, "alias_rate": 6,
              "encodings": {"cal-alpha": ("ics", "jcal"), "cal-beta": ("xcal", "xcal"), "cal-gamma": ("jcal", "ics")}},
}
PROFILES["mtime"] = dict(PROFILES["challenge"], policy="mtime-major", names=53)
PROFILES["encshift"] = dict(PROFILES["challenge"], names=61,
                            encodings={"cal-alpha": ("jcal", "jcal"), "cal-beta": ("xcal", "ics"), "cal-gamma": ("ics", "xcal")})
PROFILES["revshift"] = dict(PROFILES["challenge"], revision=4, names=67)
PROFILES["renamed"] = dict(PROFILES["shipped"], names=71)
PROFILES["mutant"] = dict(PROFILES["shipped"], policy="sequence-major", semantics="nominal", revision=4, names=73)

_ROLES = [
    ("index", "json"), ("zones", "txt"), ("zone_aliases", "json"), ("register", "xlsx"), ("governance", "pdf"),
    ("attendees", "tsv"), ("aliases", "csv"), ("itineraries", "xml"), ("closures", "sqlite"), ("freebusy", "db"),
    ("status", "yaml"), ("journal", "ndjson"), ("journal_legacy", "jsonl"), ("outbox", "psv"),
    ("escalation_draft", "yml"), ("office_snapshot", "csv"), ("payroll_export", "csv"), ("zone_cache", "tsv"),
    ("previous_run", "json"),
]
_STEMS = ["ledger", "shard", "drop", "vault", "spool", "batch", "relay", "bundle", "stack", "trace", "parcel",
          "frame", "hold", "store", "mesh", "node", "slot", "lane", "cell", "pane"]


def file_names(profile_spec, collections, encodings):
    rng = _Rng(0xC0FFEE + profile_spec["names"])
    used = set()
    names = {}

    def fresh(ext):
        while True:
            stem = "%s-%04x" % (rng.pick(_STEMS), rng.below(65536))
            name = "%s.%s" % (stem, ext)
            if name not in used:
                used.add(name)
                return name

    for role, ext in _ROLES:
        names[role] = fresh(ext)
    ext_of = {"ics": "ics", "xcal": "xml", "jcal": "json"}
    for cid in collections:
        for side, enc in zip(("local", "server"), encodings[cid]):
            names[(cid, side)] = fresh(ext_of[enc])
    return names


def _apply_zone_aliases(text, rng, rate):
    if not rate:
        return text
    out = []
    for block in text.split("BEGIN:VEVENT\n"):
        if block and rng.below(rate) == 0:
            for canonical, aliases in ALIAS_FOR.items():
                if "TZID=" + canonical in block:
                    block = block.replace("TZID=" + canonical, "TZID=" + rng.pick(aliases))
        out.append(block)
    return "BEGIN:VEVENT\n".join(out)


def _encode_replica(items, encoding, prodid):
    if encoding == "ics":
        return _calendar_bytes(items, prodid)
    text = "".join(item.decode("utf-8") if isinstance(item, bytes) else item for item in items)
    events = parse_vevents(text)
    if encoding == "xcal":
        return to_xcal(events, prodid).encode("utf-8")
    return to_jcal(events, prodid).encode("utf-8")


def _yaml_quote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_status_yaml(path, model, rng):
    lines = ["# synchronisation agent status book", "format: vdirsyncer-status/3", "collections:"]
    for cid in model.collections:
        lines.append("  %s:" % cid)
        for side in ("local", "server"):
            token = hashlib.sha256((cid + side).encode("utf-8")).hexdigest()[:6]
            lines.append("    %s:" % side)
            lines.append("      sync_token: '%s-%s-%s'" % (cid, side, token))
            lines.append("      entries:")
            for i, uid in enumerate(sorted(model.hrefs[cid])):
                digest = hashlib.sha256(("%s|%s|%s" % (cid, side, uid)).encode("utf-8")).hexdigest()[:10]
                revision = (i % 7) + 1
                lines.append("        - href: /cal/%s/%s.ics" % (cid, uid))
                lines.append("          etag: '\"%s\"'" % digest)
                style = rng.below(5)
                if style == 0:
                    lines.append('          revision: "%d"' % revision)
                elif style == 1:
                    lines.append("          revision: %d  # bumped by the agent" % revision)
                else:
                    lines.append("          revision: %d" % revision)
            lines.append("")
    _put(os.path.dirname(path), os.path.basename(path), "\n".join(lines) + "\n")


def write_journals(dest, names, model, rng):
    current = []
    legacy = []
    side_code = {"local": "L", "server": "S"}
    for rec in model.log:
        roll = rng.below(10)
        if roll < 6:
            current.append(rec)
        else:
            rid = rec["recurrence_id"]
            legacy.append({"rev": rec["revision"], "cal": rec["collection"], "side": side_code[rec["replica"]],
                           "object": rec["uid"], "rid": _iso(rid) if rid else None,
                           "action": "DEL" if rec["op"] == "delete" else "PUT", "at": rec["recorded_utc"]})
            if roll == 9:
                current.append(dict(rec))
                legacy[-1]["action"] = "PUT" if rec["op"] == "delete" else "DEL"
    _put(dest, names["journal"], "".join(json.dumps(r, sort_keys=False) + "\n" for r in current))
    _put(dest, names["journal_legacy"], "".join(json.dumps(r, sort_keys=True) + "\n" for r in legacy))


def _psv(value):
    return value.replace("\\", "\\\\").replace("|", "\\|")


def write_outbox(path, ops, rng):
    lines = ["op_seq|collection|uid|recurrence_id|op|base_sequence|field|value|stamp",
             "# pending writes captured while the hosted collection was unreachable"]
    for op in rng.shuffled(ops):
        seq, collection, uid, rid, kind, base, field, value, stamp = op
        lines.append("|".join([str(seq), collection, uid, rid, kind, str(base), field, _psv(value), stamp]))
    _put(os.path.dirname(path), os.path.basename(path), "\n".join(lines) + "\n")


def write_itineraries(path, legs, rng):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<itineraries format="exec-ops-itineraries/2">']
    for leg_id, att, dep, arr, dep_local, arr_local, carrier, status in legs:
        attrs = 'id="%s" attendee="%s"' % (leg_id, att)
        if status != "confirmed":
            attrs += ' status="%s"' % status
        lines.append("  <leg %s>" % attrs)
        first = '    <depart office="%s" local="%s"/>' % (dep, dep_local)
        second = '    <arrive local="%s" office="%s"/>' % (arr_local, arr)
        lines.extend([second, first] if rng.below(4) == 0 else [first, second])
        lines.append("    <carrier>%s</carrier>" % carrier)
        lines.append("  </leg>")
    lines.append("</itineraries>")
    _put(os.path.dirname(path), os.path.basename(path), "\n".join(lines) + "\n")


def write_sqlite(path, create, rows):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute(create)
    marks = ",".join("?" * len(rows[0]))
    table = create.split()[2]
    con.executemany("INSERT INTO %s VALUES (%s)" % (table, marks), rows)
    con.commit()
    con.close()


def _v3_transitions(year):
    rows = []
    blocks = zone_text().split("BEGIN:VTIMEZONE\n")[1:]
    for block in blocks:
        tzid = block.split("TZID:", 1)[1].split("\n", 1)[0]
        seen = set()
        for sub in ("STANDARD", "DAYLIGHT"):
            if "BEGIN:%s\n" % sub not in block:
                continue
            body = block.split("BEGIN:%s\n" % sub, 1)[1].split("END:%s" % sub, 1)[0]
            fields = dict(line.split(":", 1) for line in body.strip().split("\n") if ":" in line)
            start = fields["DTSTART"]
            frm, to = fields["TZOFFSETFROM"], fields["TZOFFSETTO"]
            rule = dict(p.split("=", 1) for p in fields.get("RRULE", "").split(";") if "=" in p)
            local = None
            if "BYMONTH" in rule and "BYDAY" in rule and rule["BYDAY"][:-2].lstrip("+-").isdigit():
                month = int(rule["BYMONTH"].split(",")[0])
                ordinal = int(rule["BYDAY"][:-2])
                weekday = WEEKDAY_CODES.index(rule["BYDAY"][-2:])
                if ordinal > 0:
                    first = date(year, month, 1)
                    day = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (ordinal - 1))
                else:
                    last = (date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
                    day = last - timedelta(days=(last.weekday() - weekday) % 7)
                local = datetime(day.year, day.month, day.day, int(start[9:11]), int(start[11:13]))
            elif rule:
                local = datetime(year, int(start[4:6]), int(start[6:8]), int(start[9:11]), int(start[11:13]))
            elif int(start[0:4]) == year:
                local = datetime(year, int(start[4:6]), int(start[6:8]), int(start[9:11]), int(start[11:13]))
            if local is None:
                continue
            sign = -1 if frm.startswith("-") else 1
            off = sign * (int(frm[1:3]) * 60 + int(frm[3:5]))
            sign_to = -1 if to.startswith("-") else 1
            off_to = sign_to * (int(to[1:3]) * 60 + int(to[3:5]))
            onset = local - timedelta(minutes=off)
            if onset in seen:
                continue
            seen.add(onset)
            rows.append((tzid, onset.strftime("%Y%m%dT%H%M%SZ"), str(off), str(off_to)))
    return rows


def write_decoys(dest, names, rng, edition):
    revisions, params, ranks, fx = governance_tables(rng)
    lines = ["# escalation digest circulated with the draft revision", "status: draft", "revision: 7",
             "settling:", "  buffer_minutes: 45", "  quantum_minutes: 30", "  round_cap: 96", "  pin_rank: 90",
             "  default_rank: 10", "class_ranks:"]
    for c, cls in enumerate(CLASS_NAMES):
        lines.append("  %s: %d" % (cls, 95 - (c * 7) % 90))
    lines.append("conversion_bps:")
    for o, row in enumerate(OFFICES):
        lines.append("  %s: %d" % (row[0], 6000 + (o * 397 + 7 * 131) % 9000 + (25 if o % 4 == 0 else 0)))
    _put(dest, names["escalation_draft"], "\n".join(lines) + "\n")

    snap = ["code,tzid,longitude,weekday,open_minute,close_minute,captured"]
    for row in register_rows(2):
        if row[9] == "2026-01-01":
            lon = row[2]
            if row[0] in ("AKL", "DXB", "YYZ"):
                lon = "%.3f" % float(lon)
            snap.append("%s,%s,%s,%s,%d,%d,2026-11-30" % (row[0], row[1], lon, row[3], row[5], row[6]))
    _put(dest, names["office_snapshot"], "\n".join(snap) + "\n")

    pay = ["attendee;cents_per_hour;exported"]
    for pid, cents, when in rate_rows(rng, stale=True):
        pay.append("%s;%d;2026-12-15" % (pid, cents))
    _put(dest, names["payroll_export"], "\n".join(pay) + "\n")

    cache = ["# transitions cached by the v3 scheduler", "tzid\tonset_utc\tfrom_minutes\tto_minutes"]
    for year in range(2019, 2032):
        for tzid, onset, frm, to in _v3_transitions(year):
            cache.append("\t".join([tzid, onset, frm, to]))
    _put(dest, names["zone_cache"], "\n".join(cache) + "\n")


def write_previous_run(path, model):
    series = {}
    for cid in model.collections:
        for side in ("local", "server"):
            for item in model.raw[cid][side]:
                text = item.decode("utf-8", "replace") if isinstance(item, bytes) else item
                events = parse_vevents(text)
                if not events:
                    continue
                props = dict((name, value) for name, _p, value in events[0])
                if "RECURRENCE-ID" in props:
                    continue
                rule = props.get("RRULE", "")
                count = 1
                for part in rule.split(";"):
                    if part.startswith("COUNT="):
                        count = int(part[6:])
                    elif part.startswith("UNTIL="):
                        count = 0
                series[(cid, props.get("UID", ""))] = count
    for key, count in model.v3_counts.items():
        series[key] = count
    rows = [{"collection": c, "uid": u, "occurrence_count": n} for (c, u), n in sorted(series.items())]
    doc = {"generator": "exec-ops-scheduler/3.2.1", "policy_revision": "v3", "series_summary": rows}
    _put(os.path.dirname(path), os.path.basename(path), json.dumps(doc, indent=2) + "\n")


def build_model(profile):
    spec = PROFILES[profile]
    if profile == "probe":
        model = StoreModel(["cal-probe"])
        build_probe_events(model)
        return spec, model
    rng = _Rng(spec["seed"])
    model = StoreModel(["cal-alpha", "cal-beta", "cal-gamma"])
    build_hidden_events(spec, rng, model)
    build_ultra_events(spec, rng, model)
    build_filler(spec, rng, model)
    return spec, model


PROFILES["probe"] = {"seed": 20270601, "policy": "sequence-major", "semantics": "exact", "revision": 6,
                     "edition": "R7", "authority": "server", "names": 79, "alias_rate": 0, "outbox": 0,
                     "encodings": {"cal-probe": ("ics", "ics")}}


def write_store(profile, dest):
    os.makedirs(dest, exist_ok=True)
    spec, model = build_model(profile)
    rng = _Rng(spec["seed"] ^ 0x5DEECE66D)
    names = file_names(spec, model.collections, spec["encodings"])
    _put(dest, names["zones"], zone_text())
    _put(dest, names["zone_aliases"], json.dumps({
        "format": "exec-ops-zone-aliases/1",
        "aliases": [{"alias": a, "target": t, "status": s} for a, t, s in ZONE_ALIASES]}, indent=2) + "\n")
    write_register_xlsx(os.path.join(dest, names["register"]), rng, spec["edition"], spec.get("date1904", True))
    write_governance_pdf(os.path.join(dest, names["governance"]), rng)
    _put(dest, names["attendees"], "id\tname\thome_office\ttitle\n" + "".join(
        "%s\t%s\t%s\tExecutive staff\n" % p for p in PEOPLE))
    _put(dest, names["aliases"], "handle,target,effective_from,status\n" + "".join(
        "%s,%s,%s,%s\n" % row for row in rng.shuffled(alias_rows(_Rng(spec["seed"] + 7)))))
    write_itineraries(os.path.join(dest, names["itineraries"]), _leg_rows(_Rng(spec["seed"] + 11), model), rng)
    write_sqlite(os.path.join(dest, names["closures"]),
                 "CREATE TABLE closures (office TEXT, day TEXT, name TEXT, revision INTEGER, state TEXT)",
                 rng.shuffled(_closure_rows(rng)))
    busy = _busy_rows(_Rng(spec["seed"] + 13), model)
    write_sqlite(os.path.join(dest, names["freebusy"]),
                 "CREATE TABLE periods (source TEXT, attendee TEXT, fbtype TEXT, start TEXT, finish TEXT, withdrawn INTEGER)",
                 busy)
    ops = build_outbox(spec, _Rng(spec["seed"] + 17), model) if spec.get("outbox") else []
    write_outbox(os.path.join(dest, names["outbox"]), ops, rng)
    write_journals(dest, names, model, _Rng(spec["seed"] + 19))
    write_status_yaml(os.path.join(dest, names["status"]), model, _Rng(spec["seed"] + 23))
    write_decoys(dest, names, rng, spec["edition"])
    write_previous_run(os.path.join(dest, names["previous_run"]), model)
    alias_rng = _Rng(spec["seed"] + 29)
    collections = []
    for cid in model.collections:
        replicas = {}
        for side, encoding in zip(("local", "server"), spec["encodings"][cid]):
            items = model.raw[cid][side]
            if profile != "probe":
                items = [_apply_zone_aliases(item, alias_rng, spec["alias_rate"]) for item in items]
            _put_bytes(dest, names[(cid, side)], _encode_replica(items, encoding, "-//EXEC-OPS//Calendar Platform 5.0//EN"))
            replicas[side] = names[(cid, side)]
        collections.append({"id": cid, "href": "/cal/%s/" % cid, "replicas": replicas})
    index = {
        "format": "exec-ops-store/2",
        "generated_utc": "20271231T235900Z",
        "files": dict((role, names[role]) for role, _ext in _ROLES if role != "index"),
        "store": {
            "id": profile if profile not in ("renamed", "mutant", "encshift") else "primary",
            "conflict_policy": spec["policy"],
            "duration_semantics": spec["semantics"],
            "authority_replica": spec["authority"],
            "policy_revision": spec["revision"],
            "register_edition": spec["edition"],
            "window": {"start": "2027-01-01", "end": "2027-12-31"},
            "collections": collections,
        },
    }
    if profile in ("challenge", "mtime", "revshift", "eval", "dense", "shipped", "probe"):
        index["store"]["id"] = "primary"
    _put(dest, names["index"], json.dumps(index, indent=2) + "\n")
    return names


# =====================================================================
# Grading harness.
#
# rewardkit runs the checks concurrently in worker threads, so every shared
# cache is filled through _cached(), which builds each entry once under a per
# key lock. The delivered program is hostile input: it runs only as a
# subprocess with a timeout, in its own session, under an unprivileged uid of
# its own when grading runs as root, and every process left behind under that
# uid is killed before the check continues. Every check returns a bool and
# never raises.
# =====================================================================

PROGRAM_PATH = "/app/schedule_repair.py"
DELIVERED_OUT = "/app/out"
SHIPPED_STORE_PATH = "/app/data"
RUN_TIMEOUT_SEC = 900

ARTIFACTS = [
    "decisions.jsonl", "reconciliation.json", "outbox_replay.jsonl", "occurrences.csv", "alias_resolutions.tsv",
    "resolutions.tsv", "exceptions.jsonl", "zone_transitions.tsv", "conflicts.jsonl", "settle_moves.csv",
    "settled_schedule.csv", "settle_summary.json", "load_steps.tsv", "load_summary.json", "attendance.psv",
    "legs.json", "travel_blocks.csv", "busy_conflicts.tsv", "sync_entries.tsv", "sync_tokens.json",
    "chargeback_offices.json", "chargeback_collections.json", "authority_audit.csv", "drift.csv",
]
REPORTS = ARTIFACTS + ["manifest.json"]
CORE = ("decisions.jsonl", "occurrences.csv", "settled_schedule.csv")
HEADERS = {
    "occurrences.csv": "occurrence_id,collection,uid,office,original_utc,start_utc,end_utc,duration_seconds,"
                       "duration_source,applied_shift_minutes,override,local_start,local_end,utc_offset_minutes,"
                       "solar_minutes,solar_in_window,series_class,required_attendees,summary",
    "alias_resolutions.tsv": "occurrence_id\tref\tresolved\thops\toutcome",
    "resolutions.tsv": "occurrence_id\ttzid\tnominal_local\tclassification\tshift_minutes\tutc_offset_minutes",
    "zone_transitions.tsv": "tzid\tobservance_count\tonset_utc\tfrom_offset_minutes\tto_offset_minutes",
    "settle_moves.csv": "round,occurrence_id,from_utc,to_utc,deferred_minutes,gap_shift_minutes,reason_first,reason_second",
    "settled_schedule.csv": "occurrence_id,office,start_utc,end_utc",
    "load_steps.tsv": "attendee\tstep\toccurrence_id\teffective_office\tdeviation_minutes\tcost_units\trest_days\t"
                      "decay_applied\toffice_changed\tdebt_after",
    "attendance.psv": "attendee|occurrence_id|effective_office|kind|local_start|minutes_outside",
    "travel_blocks.csv": "occurrence_id,attendee,leg_id,kind",
    "busy_conflicts.tsv": "occurrence_id\tattendee\tblock_start_utc\tblock_end_utc\tfbtype",
    "sync_entries.tsv": "collection\thref\tetag\trevision\tchanged_local\tchanged_server",
    "authority_audit.csv": "subject,key,in_force,source,lower_value,agrees",
    "drift.csv": "collection,uid,v3_count,v5_count,delta",
}

_LOCK_GUARD = threading.Lock()
_KEY_LOCKS = {}
_WORK = {}
_STORES = {}
_PROGRAM = {}
_SUBMISSIONS = {}
_UID_COUNTER = itertools.count(41000)
_DECOY_LOCK = threading.Lock()


class _Failed(object):
    def __init__(self, exc):
        self.message = str(exc)


def _cached(cache, key, make):
    with _LOCK_GUARD:
        lock = _KEY_LOCKS.setdefault((id(cache), key), threading.Lock())
    with lock:
        if key not in cache:
            try:
                cache[key] = make()
            except Exception as exc:
                cache[key] = _Failed(exc)
        value = cache[key]
    if isinstance(value, _Failed):
        raise AssertionError(value.message)
    return value


def _holds(probe, *args):
    try:
        probe(*args)
    except Exception:
        return False
    return True


def _make_work():
    root = tempfile.mkdtemp(prefix="exec-ops-grade-")
    os.chmod(root, 0o755)
    return root


def _work():
    return _cached(_WORK, "root", _make_work)


def _scratch(prefix):
    path = tempfile.mkdtemp(prefix=prefix + "-", dir=_work())
    os.chmod(path, 0o755)
    return path


def _build_store(profile):
    path = os.path.join(_scratch("store-" + profile), "store")
    write_store(profile, path)
    os.chmod(path, 0o755)
    return path


def _store(profile):
    return _cached(_STORES, profile, lambda: _build_store(profile))


def _stage_program():
    if not os.path.isfile(PROGRAM_PATH):
        raise AssertionError("the repair program is absent from " + PROGRAM_PATH)
    staged = _scratch("bin")
    target = os.path.join(staged, "schedule_repair.py")
    shutil.copyfile(PROGRAM_PATH, target)
    os.chmod(target, 0o644)
    return target


def _program():
    return _cached(_PROGRAM, "path", _stage_program)


def _drop_privileges():
    return getattr(os, "geteuid", lambda: 1)() == 0 and shutil.which("setpriv") is not None


def _kill_uid(uid):
    if not os.path.isdir("/proc"):
        return
    for _attempt in range(5):
        found = False
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open("/proc/%s/status" % entry, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if line.startswith("Uid:"):
                            if int(line.split()[1]) == uid:
                                found = True
                                os.kill(int(entry), signal.SIGKILL)
                            break
            except (OSError, ValueError):
                continue
        if not found:
            return


def _run_raw(store_dir, out_dir, timeout=RUN_TIMEOUT_SEC, cwd=None, home=None, create_out=True):
    program = _program()
    if create_out:
        os.makedirs(out_dir, exist_ok=True)
    scratch = cwd or _scratch("cwd")
    home = home or scratch
    prefix = []
    uid = None
    if _drop_privileges():
        uid = next(_UID_COUNTER)
        owned = [path for path in (out_dir, scratch, home) if os.path.isdir(path)]
        parent = os.path.dirname(os.path.abspath(out_dir))
        if os.path.dirname(parent) == _work():
            owned.append(parent)
        for path in owned:
            os.chown(path, uid, uid)
            os.chmod(path, 0o700)
        prefix = [shutil.which("setpriv"), "--reuid=%d" % uid, "--regid=%d" % uid, "--clear-groups"]
    command = prefix + [sys.executable, program, store_dir, out_dir]
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": home, "TMPDIR": home, "LANG": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(command, cwd=scratch, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=errors, start_new_session=True, env=env)
        status = None
        try:
            status = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = None
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            if status is None:
                proc.wait()
            if uid is not None:
                _kill_uid(uid)
        errors.seek(0, os.SEEK_END)
        errors.seek(max(0, errors.tell() - 65536))
        stderr = errors.read()
    return status, stderr.decode("utf-8", "replace")


def _invoke(store_dir, out_dir, timeout=RUN_TIMEOUT_SEC, cwd=None, home=None, create_out=True):
    status, stderr = _run_raw(store_dir, out_dir, timeout=timeout, cwd=cwd, home=home, create_out=create_out)
    if status is None:
        raise AssertionError("the repair program did not finish within %d seconds" % timeout)
    if status != 0:
        tail = stderr.strip().splitlines()[-4:]
        raise AssertionError("the repair program exited with status %d: %s" % (status, " | ".join(tail)))
    return out_dir


def _make_submission(profile, tag):
    path = os.path.join(_scratch("sub-%s-%s" % (profile, tag)), "out")
    _invoke(_store(profile), path)
    return path


def _submission(profile, tag="a"):
    return _cached(_SUBMISSIONS, (profile, tag), lambda: _make_submission(profile, tag))


def _raw(directory, name):
    path = os.path.join(directory, name)
    if not os.path.isfile(path):
        raise AssertionError("report %s is absent from %s" % (name, directory))
    with open(path, "rb") as fh:
        return fh.read()


def _digest_of(directory, name):
    return hashlib.sha256(_raw(directory, name)).hexdigest()


# ---------------------------------------------------------------------
# Expected values: the SHA-256 digest of the exact bytes of every report,
# recorded from the reference program on every store the checks build.
# The encoding shifted store must reproduce the challenge store exactly and
# the renamed store must reproduce the shipped store exactly.
# ---------------------------------------------------------------------

EXPECTED = {
    "challenge": {
        "alias_resolutions.tsv": "c56e81a4466c3f33249659557ab0fb5f473519459cb41db5da439daaffdc146b",
        "attendance.psv": "e1a16acd1b5ed73f0c3a2c7b6977b9c8b0adccaf9b9446ad6df684e43e1085c0",
        "authority_audit.csv": "bedb31e3020f492c92e0b42ea9b1a27fa207efcab59b1195eac2743dbc68f3a5",
        "busy_conflicts.tsv": "98e077d168718d7ce306efae7dd473507eaeea13570645659ca3fb299a3b9941",
        "chargeback_collections.json": "98dc128e414da2c55f3055d538823a86ec7afb9ca02cc3c8c5e546410a753ff4",
        "chargeback_offices.json": "c7f59651612dd90695447b691d15d0b9438fc4b7a522d71321fdb272e8e74651",
        "conflicts.jsonl": "a8447fd860b9ee181e565891b4d7301c0c40cfbf3e2dbe908364e90d454b7744",
        "decisions.jsonl": "3825bcde49214b00f903adaad25edd2995b592d9a97b0d1afb3e9ebbea93afc9",
        "drift.csv": "41463e07de2f7406376fc6667aec3a3707f6e1f70b18abb6c77887413269397d",
        "exceptions.jsonl": "4dc9c03a5523f73d5193b5014e333017e98fc8a4d06a5d1f7c97bcf1fc87df69",
        "legs.json": "7fd520959812ad4b98bf06bc194461690afd3ed68f0c43efac66f3046d0ba205",
        "load_steps.tsv": "1cdfbe03ea7eb8a11cd18be353c815cf2550ce68838a25fd92b3ac05494dde1f",
        "load_summary.json": "fba3873dc897c0c20cd974175cf6a42935ecd1faf59fd8d633596eff02e1096b",
        "manifest.json": "cda8ac989f349f49289123ec65efbd7e38216c915da510fde4d38d046a7497e0",
        "occurrences.csv": "ecbc3a9916e1d0ffb76430b987ea15553a9bb08b2a8bb24cee830e52fe79af02",
        "outbox_replay.jsonl": "c5e11f6aa74f6464c7c19df9f0042ada9df68b2d7e8caf939b6fb8285dc43dc9",
        "reconciliation.json": "ab2938d4d2c68905d4bcfe0776747d05787eb6c21fe9445152451f92ee1fe8b4",
        "resolutions.tsv": "f5fbfa8b92588b359a2d509300b1cfd737bf43d69a7db0ac0e02a53cde8427c7",
        "settle_moves.csv": "04e48b7582474f0271b5ff9de8dd1464e8bc3e44e34f7df8c390fd5f3474fd59",
        "settle_summary.json": "7397d8e04466c89b39b0a68c4c4433629ca5f2db08d042f0d2ead2641f192c9e",
        "settled_schedule.csv": "4019fe8b79d0149bcc0fb084d4e692869153b4be191618ec4c7921b02a3f16e8",
        "sync_entries.tsv": "ab07b93411f6d6c3318974de6ff4d8af87e8451a6020c456f73c5812660e1f10",
        "sync_tokens.json": "179a587bd3fb6bd6723650b76e14a2a0497b669005577eeb1caa3bbb03094981",
        "travel_blocks.csv": "7ff606398fe35febd6e72752d7bdb23b0093df2994ee5463518dda033ef44853",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    },
    "dense": {
        "alias_resolutions.tsv": "b4736e0c48ec76372b98514e2981f8158c4bc41d7ef8599a909a2f094b864081",
        "attendance.psv": "473274cb9a454e18798eeb4201ee7ab8ac314071bcdc00222dd48848ca4ea863",
        "authority_audit.csv": "bedb31e3020f492c92e0b42ea9b1a27fa207efcab59b1195eac2743dbc68f3a5",
        "busy_conflicts.tsv": "130323c33e40d553c11669bb4f0cd2fd8750702646bdf7e568eb1b3a5d2bc7a3",
        "chargeback_collections.json": "c28472dc7e64175869207e188bc804942a4e9affdb8d3419f0efd7fcbad9b87f",
        "chargeback_offices.json": "50401e756956d827b981ec881aab050169b7d2274001e2170d2eec00c7b4376a",
        "conflicts.jsonl": "04661963d2eaa787ad0708cee9c9cdfd3509db8e7d6e2ff67f254a213098ac9f",
        "decisions.jsonl": "0cc28c63a2384577d1f2cfe91116af60db7399296e07e49eb7f73dadab0e896a",
        "drift.csv": "40b4a2494a8cdee4bc8f7d6224cfd2cd76cdad436f5beb9e343fd6aa3fe88390",
        "exceptions.jsonl": "9946f458431d743dc476992a9f4a788f96dfbd02ef6dd3aecfea976b4bceb908",
        "legs.json": "d540fc85ccc5f42595ae0301d4bf9154bcbf2bd02e0a193df9a841ad7285b5b2",
        "load_steps.tsv": "cce05ed6fb3d3a7e9df6eace810b36e6e70378ea0a4c395b9a69656f7e8be61a",
        "load_summary.json": "36737443e69f186a24be9b60920555073f6d7d2365ed29fbcd35fef8bd548f18",
        "manifest.json": "045d8df023247f7948d42f4240dc9ae760e356f5bf408f630535fdea407b9c8e",
        "occurrences.csv": "8a98d22bf758f1a5c4bfda51acdda0cda68313af445c5713c96da7d14b54a9e9",
        "outbox_replay.jsonl": "c3212e095f4594339aa8d2d49b71cfcfdcf4d284a1759f26c4d9a05d64ff37f5",
        "reconciliation.json": "45246181f86351d2532a39daa269eacf8960c39441796cd6f549f618346042af",
        "resolutions.tsv": "35537273a1744a369cb52240d28f83bf6cdcca7a13303fd46688cd7d9ad6e7f4",
        "settle_moves.csv": "cfcb7e10b9d529a81c8a10e98df7b9a71ffee7ae421fd16a985e5db0b7563410",
        "settle_summary.json": "467c23f945009cb3c7cddabccba6e01b684e756ba26488251b4dc40941e7a260",
        "settled_schedule.csv": "b816e99ab4a835621c5348538808b13a7f7177a05cc833c3bc47f7657a1e016c",
        "sync_entries.tsv": "037f1f539ebf19508e89223999d23980ff62305afc243026b13e5e9d3aeae778",
        "sync_tokens.json": "f7213b76fd94fa3a809aa95c84f8639582bc13a2e7436593b2cef6306d12016a",
        "travel_blocks.csv": "9397e43a576f6557ea473d5ce29bc3ef424e696766780562d1ad0232e13e01d5",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    },
    "eval": {
        "alias_resolutions.tsv": "93b128bf7d54d048178e8a51eeb39d572e0d4c08ccdcde3f7625faf18217e71e",
        "attendance.psv": "2706627a7b926ac71e51edc47ae08045b3af10c64b96028a20d7b37903459818",
        "authority_audit.csv": "bedb31e3020f492c92e0b42ea9b1a27fa207efcab59b1195eac2743dbc68f3a5",
        "busy_conflicts.tsv": "93e8e0828b1b3bfe1b8146f0a950c19a025f5daeec33866ce014069f359447b4",
        "chargeback_collections.json": "94966601e5a91546347aeb67a9660dda2c8c3cfee4e21d9c1a5427fd28f5ddf3",
        "chargeback_offices.json": "66c17277d1537f8dfc00629558408b3f2cc699290be10ba0f3f5ef980b149a33",
        "conflicts.jsonl": "494933e0716ff14a9b2e470565bb131cb71cc45c27a6c12ce63bde786529571d",
        "decisions.jsonl": "63dd1f0521a206710eec13237c9ae4dce948915c298a20609a01ffcbf3662be4",
        "drift.csv": "93076726c2b5347cc49371beea86172ba5b695b0e279dded06e07b978f8ecffd",
        "exceptions.jsonl": "ea903c3ee1cfa9483559ffcd6cfac12844c5025d96e6fcea772f332ce00f960c",
        "legs.json": "bced81a9a744590d5a04c6fd583af49982b97535af381d25d4168539aa037742",
        "load_steps.tsv": "f7cdd81006c9f4bee090bde6c68ec4c7062a227ece97fcab76c7ab330935c963",
        "load_summary.json": "b6072d7c4174ab22c90c4617eb804345170f6a07267a088440b48228e7f58b90",
        "manifest.json": "4f0162790a5ab657c5881632b6b418c786161d1910d3f116595833a9f07b31da",
        "occurrences.csv": "d565ec2155eb1e0973ae70bfc41300b22821f371f12fa9f625244931d1832b73",
        "outbox_replay.jsonl": "e16b3ea05b7aab0fd417aeb5d1b11a460aaa4dffacc5aeb74d6e05dbbc789dd2",
        "reconciliation.json": "d3e1b1894dc40c32f5a0f436935aab64f133ffd48fb4b28f435bc2722b695d97",
        "resolutions.tsv": "5d83eb6014d4645d9d020b7a2a5e1864f2ab3672197f1179c2f48a1b19f079c4",
        "settle_moves.csv": "5f0a5f7992f3898a6005f772a5382fdfca9b159c3c6fa0a95ac531e6b7fb7dac",
        "settle_summary.json": "82a09e94ce38119dca63fb482edb801f7adea77d756136a5696b8a7ea5164f5c",
        "settled_schedule.csv": "291e9769f50304a1c3875974529f7bb2acfdfb6de29cd1988cfe22100e0eb344",
        "sync_entries.tsv": "ef86fee4ea17000a2805f1b2f4c370c2b453ceddf73c364bcc870f40eb35e0ca",
        "sync_tokens.json": "420491be98d2bb253a97fc7da718f7cf54b62039b39145427ccb9c88ecdd009e",
        "travel_blocks.csv": "68266ed19a19cd29a8d55ffe7737d6d067f6f5378a67e4b5336c7ed8fdc9c3e7",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    },
    "mtime": {
        "alias_resolutions.tsv": "1b75da90cf99883e53e61879450b81cdc8f5f136d475275003f921cd0e21cc5f",
        "attendance.psv": "f107840eb2fff0ed86598cf90789f03955593dfe56366743626fe843df1c8a41",
        "authority_audit.csv": "bedb31e3020f492c92e0b42ea9b1a27fa207efcab59b1195eac2743dbc68f3a5",
        "busy_conflicts.tsv": "98e077d168718d7ce306efae7dd473507eaeea13570645659ca3fb299a3b9941",
        "chargeback_collections.json": "a32e6d4f31ca02cee16fa352e673b7c3456bd4728c555fe706ac9ecb6eb8fc01",
        "chargeback_offices.json": "dcbff18bc453c51a88ce4864ee9b0c9cbfb131550cdd7d78ed5ef67da6024664",
        "conflicts.jsonl": "a8447fd860b9ee181e565891b4d7301c0c40cfbf3e2dbe908364e90d454b7744",
        "decisions.jsonl": "6fc29ab079a9375794868f510e0f164a1695fe5aa2eb4ea084192356fe8255b2",
        "drift.csv": "839fcc7468f3301899bf6cbf3812cb5be6a1e49d77dc3262f7888d4fa32c9a90",
        "exceptions.jsonl": "b312839be15fd848fc3ff9ac9acce6c219d9fbe1340e0d7d54203f35b4ea3576",
        "legs.json": "7fd520959812ad4b98bf06bc194461690afd3ed68f0c43efac66f3046d0ba205",
        "load_steps.tsv": "598309e888662f1b875810cb4ab02f5272a277239b05268fa713234315c6bbdc",
        "load_summary.json": "9b137bff8d841181850120fae0673162b981073f3b9f2778bf590b75af22cc0a",
        "manifest.json": "028c675b9120702c925e16db21cf4e12efceb7c0eccabbd07d7618c28bc108ce",
        "occurrences.csv": "fbd35420c3f685487fd239ddca6e790191d80d6c18432886bc2402026401a2b1",
        "outbox_replay.jsonl": "c5e11f6aa74f6464c7c19df9f0042ada9df68b2d7e8caf939b6fb8285dc43dc9",
        "reconciliation.json": "686769eca04a1fe4476fa7b348944dac251569a71d42a38e8c4ea414b39d39fc",
        "resolutions.tsv": "d43338562cc30a1e723ce85195ddfe1e7c4823e25b2c2a9526d72a6b28d11ca9",
        "settle_moves.csv": "04e48b7582474f0271b5ff9de8dd1464e8bc3e44e34f7df8c390fd5f3474fd59",
        "settle_summary.json": "7397d8e04466c89b39b0a68c4c4433629ca5f2db08d042f0d2ead2641f192c9e",
        "settled_schedule.csv": "54c9789870a8be14982061d666401895d2af7235f1f1059a793cbf657f000119",
        "sync_entries.tsv": "e2e1911348577efcbe5efeb8394359e043b7e1cc1d376fdee157e5eb3e14ce31",
        "sync_tokens.json": "0840a500220f779ede929ce887fde218b483633d74c84157e9c16894038ac76e",
        "travel_blocks.csv": "7ff606398fe35febd6e72752d7bdb23b0093df2994ee5463518dda033ef44853",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    },
    "probe": {
        "alias_resolutions.tsv": "dbd2a17dee65e166b0d65d1bee9a6802bafd553e6fb2855cab2f33d098bfdadb",
        "attendance.psv": "ed2af11cbd336ee897e907a7b32d2f81c376c9d4bb1745db63d5ec1c30b99948",
        "authority_audit.csv": "bedb31e3020f492c92e0b42ea9b1a27fa207efcab59b1195eac2743dbc68f3a5",
        "busy_conflicts.tsv": "0db10fc634b9fd8a799da22c525dd350a5c4ec146d01ce7a8a36c9f4216a532a",
        "chargeback_collections.json": "4b492b5a870e6c66fbabe74d90ac0d691f2dafbb772e210446ab55dfa6922988",
        "chargeback_offices.json": "4d176ae0b93138535f7b998a3c09f104f2f226ebc06e0dc3d3995304f8bf63e3",
        "conflicts.jsonl": "716998e986606867a24938b82963019f8867915fe1956b7f9a4e78ee1c7e925c",
        "decisions.jsonl": "3bdf88c9e8854ca69392f75255d199fa171ea31651351955c9ef6af56f47a031",
        "drift.csv": "1420cdfe6c11d7e6aceafeac9aa6dd2ce8584d8013a5a3e05bc95294d48c2ccb",
        "exceptions.jsonl": "552d5632a87d6e47ea96c4f650b6409931232ba737931a5d6dae972ff59a7f30",
        "legs.json": "61c2654b96bf9a5c20dca93f24f70753f012f97a049195fe7d408b5a493cb40b",
        "load_steps.tsv": "61c30264027dd0d936e145aa52cc4cd86952397215d5470b9c44b80f4af6a64a",
        "load_summary.json": "656b1dcd60896db6d3453f5c85f5320506bc8b3b6d63e3aff3d05a8f6fbfd65c",
        "manifest.json": "f45b1b70891ad01d100fb790c7ea3c55070348bd081b65e708b84cc75217159f",
        "occurrences.csv": "574a2ba62500d0f2012b978331c76a7518e78fd9c1732991366ecc1d4c583fbc",
        "outbox_replay.jsonl": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "reconciliation.json": "598908f0dcf0bc3c0ce7f4bed08896336c29516435bd856f40a75bf0292f8b82",
        "resolutions.tsv": "32ab023471a807384462f865f5a18389c00d93745fc4e9241f7e8169d33e751b",
        "settle_moves.csv": "08acf4835ed3b390074c613e258b249d04dd8a772d7e3e8bac87498de7abfd3f",
        "settle_summary.json": "3528e9bfd3b628736c0d085e339eee7f050606b90d7ffa8292f5de261f60442a",
        "settled_schedule.csv": "9d2310e98abef313cfd575eb67a2c3a930598bd49cea21aa495e7ee70547978a",
        "sync_entries.tsv": "888c04fcaa4004c95acc5aac2b25d7ed635c926f31e41a0a9f4e277cf37c7fe8",
        "sync_tokens.json": "726fb8b5ad90d58591b10e0cff247ea985d0a9bb46fc473baf4bd343559d8268",
        "travel_blocks.csv": "4bc487d4f0411cf54a950c8ea750d5cd5a250577fb5621bd40837755055c568f",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    },
    "revshift": {
        "alias_resolutions.tsv": "c56e81a4466c3f33249659557ab0fb5f473519459cb41db5da439daaffdc146b",
        "attendance.psv": "dc5781eed6d1564dd3ade16e2806fd2d57574f51531f303d18e44c03f9bd6277",
        "authority_audit.csv": "9c40062b751b3497023773fbcfb08e24e09f84783a256f845de7e3ded21a5e2b",
        "busy_conflicts.tsv": "98e077d168718d7ce306efae7dd473507eaeea13570645659ca3fb299a3b9941",
        "chargeback_collections.json": "e196d30e2177d26b3c2c45fc7abf485293b0529e4f0295f2e55f36f553659501",
        "chargeback_offices.json": "1f1af44bcf09548db44833425d73abdb1df386b7263f6b75ad974b82c59242ba",
        "conflicts.jsonl": "ab7b26b000ef738eec508efc35aad359d123f8275fd599d07927a0d55b40cb36",
        "decisions.jsonl": "3825bcde49214b00f903adaad25edd2995b592d9a97b0d1afb3e9ebbea93afc9",
        "drift.csv": "41463e07de2f7406376fc6667aec3a3707f6e1f70b18abb6c77887413269397d",
        "exceptions.jsonl": "4dc9c03a5523f73d5193b5014e333017e98fc8a4d06a5d1f7c97bcf1fc87df69",
        "legs.json": "7fd520959812ad4b98bf06bc194461690afd3ed68f0c43efac66f3046d0ba205",
        "load_steps.tsv": "1cdfbe03ea7eb8a11cd18be353c815cf2550ce68838a25fd92b3ac05494dde1f",
        "load_summary.json": "fba3873dc897c0c20cd974175cf6a42935ecd1faf59fd8d633596eff02e1096b",
        "manifest.json": "e8e058f716f6b781e9dd8c992b5c0272ab55a263b5df1223f97d789678b1c72c",
        "occurrences.csv": "ecbc3a9916e1d0ffb76430b987ea15553a9bb08b2a8bb24cee830e52fe79af02",
        "outbox_replay.jsonl": "c5e11f6aa74f6464c7c19df9f0042ada9df68b2d7e8caf939b6fb8285dc43dc9",
        "reconciliation.json": "a896073f35168166f665c66935677c6b8d7e013a57dae0237e164da28b1626cf",
        "resolutions.tsv": "f5fbfa8b92588b359a2d509300b1cfd737bf43d69a7db0ac0e02a53cde8427c7",
        "settle_moves.csv": "afb8a47a6dc8e5c2d18e7ebd6b14371216d83082dd5d824df56b63595f71432e",
        "settle_summary.json": "ae1a02ea9c3d4079a34f17139568a2e0319ca1c1b9eca372128fdbdbf8bb8876",
        "settled_schedule.csv": "243a91baf38519ec03f8334c4fdf51d0a8d9076c212ceb68416df93fd3bf3f89",
        "sync_entries.tsv": "ab07b93411f6d6c3318974de6ff4d8af87e8451a6020c456f73c5812660e1f10",
        "sync_tokens.json": "179a587bd3fb6bd6723650b76e14a2a0497b669005577eeb1caa3bbb03094981",
        "travel_blocks.csv": "7ff606398fe35febd6e72752d7bdb23b0093df2994ee5463518dda033ef44853",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    },
    "shipped": {
        "alias_resolutions.tsv": "96963af6b052c074e1429c2dccda47f7a3acdb82874db6ec00f0a9069b3b9b83",
        "attendance.psv": "f4be93348508a6a76e668a34eea85b0938c6517e861ff019dbb174d5f8b31e5a",
        "authority_audit.csv": "bedb31e3020f492c92e0b42ea9b1a27fa207efcab59b1195eac2743dbc68f3a5",
        "busy_conflicts.tsv": "1fedaab890e8f689fefeac540f9c0749d7dc6e12705a9ccd6c419bafdfbf051c",
        "chargeback_collections.json": "c05dd6d974e1b13b3b7d9247a6aa65f85e2c64528a4ab9b9e6eb292d565f7950",
        "chargeback_offices.json": "428c78cfda63bc63b1755dbdcc33ba98e5956dfdd9509cd1fc5b47de640ef2f3",
        "conflicts.jsonl": "37383f82f335baf074d42e39778718c7dc753c7180b1a64375d07a4a37450ba0",
        "decisions.jsonl": "d183e009354e960c68f970084ab47d92e9178821de5a4ecf533a1482fe64e043",
        "drift.csv": "ae90326b42c0eb1e6fa6c5a48421b05bd1cb88897a21337d697b6bbf6e400faa",
        "exceptions.jsonl": "cdad5f441f621b35bed24e8315e72aea0d4c8ebf7bcbf710572602e894f048c1",
        "legs.json": "eea362ae01e86d074658be8047d30a5500426f9514a4ab4903aba3bf46ff981a",
        "load_steps.tsv": "5b3d0a60471c8fe2d2a6f90d9ff0235771f71c09f0c5ae97cb93ea22fc1f172e",
        "load_summary.json": "6c04486b501878c56b5a4b923f7a35bc43452158ac18337a34e2e5cb26611211",
        "manifest.json": "91514cfdee3becc6cd7473ac670da661257720c19ba7cfb530291f5df9639026",
        "occurrences.csv": "3c763871314fd1cc3726c7e4910038264cf0d01dce6b5425a0ba5ba4a54bcf25",
        "outbox_replay.jsonl": "2124148ddcf869bd6b0632d41cf8df7435482beaf63ece21a01b023838e0f9bd",
        "reconciliation.json": "5abcb1a6ce2c84f11861fd87c47445881991c032941a60cad2e74a37fdbbdb7c",
        "resolutions.tsv": "eae6500538aa75628d8bb2c673bdb0648523edd7f532d667eb874dbe74a817e0",
        "settle_moves.csv": "d84835d97238b7252c40b9e20457798523435cae831aac157cb1653440ddb161",
        "settle_summary.json": "7a9112041c1f728d5d875bec3486dd603fa61aae4b715e4fdef525efbe00fb59",
        "settled_schedule.csv": "6c489720170db287f5393d6f2e71139fa7981b243105f68a53e608122123c35e",
        "sync_entries.tsv": "aba3e1a566e0044edbd1e66dde10ab86e0948e819c92f01f4b6e7817ee190dfb",
        "sync_tokens.json": "ab9c7ec2f47bef18b51bbc0054d9b29567358e03a1568a07dab1a5db91960937",
        "travel_blocks.csv": "1249b3c2a05e6febb4f51317b2170a2ed1f58ddaaf33a04fca1ef7bb2ccf4094",
        "zone_transitions.tsv": "277f48dd60ed6ea1310b50b6f2747a953a19ec72296240c47feaee9609c71f71"
    }
}
ROUND_ONCE_CHARGEBACK = '4f52461946cf45726eec26ce52b61488a1141184af474ce8200ee7e91cf6185e'
_ALIASED = {"encshift": "challenge", "renamed": "shipped"}


def _expected(profile, name):
    return EXPECTED[_ALIASED.get(profile, profile)][name]


def _reports_agree(directory, profile, names):
    wrong = [name for name in names if _digest_of(directory, name) != _expected(profile, name)]
    if wrong:
        raise AssertionError("reports differ on the %s store: %s" % (profile, ", ".join(wrong)))


def _assert_full_core(profile):
    """The spine gate: no exact check on a store pays unless the merge
    decisions, the occurrence list and the settled schedule are byte exact on
    that same store."""
    if profile == "delivered":
        _reports_agree(DELIVERED_OUT, "shipped", CORE)
        return DELIVERED_OUT
    directory = _submission(profile)
    _reports_agree(directory, profile, CORE)
    return directory


def _gated(profile, names):
    directory = _assert_full_core(profile)
    _reports_agree(directory, "shipped" if profile == "delivered" else profile, names)


# =====================================================================
# Probes. Each raises AssertionError when its property fails.
# =====================================================================


def _make_fresh_run():
    out = os.path.join(_scratch("fresh"), "out")
    _invoke(_store("probe"), out, create_out=False)
    return out


def _p_runs():
    out = _cached(_SUBMISSIONS, ("probe", "fresh"), _make_fresh_run)
    missing = [name for name in REPORTS if not os.path.isfile(os.path.join(out, name))]
    if missing:
        raise AssertionError("reports absent after a run: " + ", ".join(missing))


def _canonical_json(blob):
    text = blob.decode("utf-8")
    return json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n" == text


def _p_serialisation():
    _assert_serialised(DELIVERED_OUT)


def _assert_serialised(directory):
    for name in REPORTS:
        blob = _raw(directory, name)
        if not blob.endswith(b"\n") or b"\r\n" in blob:
            raise AssertionError("%s does not end its lines with a single line feed" % name)
        if name.endswith(".json"):
            if not _canonical_json(blob):
                raise AssertionError("%s is not canonical JSON" % name)
        elif name.endswith(".jsonl"):
            for line in blob.decode("utf-8").split("\n")[:-1]:
                if not _canonical_json((line + "\n").encode("utf-8")):
                    raise AssertionError("%s holds a line that is not canonical JSON" % name)
        else:
            delimiter = {"csv": ",", "tsv": "\t", "psv": "|"}[name.rsplit(".", 1)[1]]
            rows = list(csv.reader(io.StringIO(blob.decode("utf-8"), newline=""), delimiter=delimiter))
            if not rows or any(len(row) != len(rows[0]) for row in rows):
                raise AssertionError("%s holds a row whose field count differs from its header" % name)


def _p_manifest():
    manifest = json.loads(_raw(DELIVERED_OUT, "manifest.json").decode("utf-8"))
    if manifest.get("order") != ARTIFACTS or manifest.get("algorithm") != "sha256-chain":
        raise AssertionError("the manifest order or algorithm is wrong")
    chain = hashlib.sha256(b"").hexdigest()
    if manifest.get("chain_root") != chain:
        raise AssertionError("the chain root is wrong")
    links = manifest.get("links") or []
    if [link.get("name") for link in links] != ARTIFACTS:
        raise AssertionError("the manifest links do not follow the order")
    for name, link in zip(ARTIFACTS, links):
        digest = _digest_of(DELIVERED_OUT, name)
        chain = hashlib.sha256(("%s\n%s\n%s" % (chain, name, digest)).encode("utf-8")).hexdigest()
        if link.get("file_sha256") != digest or link.get("chain_sha256") != chain:
            raise AssertionError("the manifest link of %s is wrong" % name)
    if manifest.get("chain_head") != chain:
        raise AssertionError("the chain head is wrong")


def _p_header_rows_on_held_out():
    out = _submission("challenge")
    for name, header in HEADERS.items():
        if _raw(out, name).decode("utf-8").split("\n", 1)[0] != header:
            raise AssertionError("%s carries the wrong header row on a held out store" % name)


def _p_encoding_shift():
    _assert_full_core("challenge")
    _reports_agree(_submission("encshift"), "encshift", REPORTS)


def _copy_store(profile, label):
    moved = os.path.join(_scratch("moved"), label)
    shutil.copytree(_store(profile), moved)
    os.chmod(moved, 0o755)
    return moved


def _p_hardcoded():
    _reports_agree(DELIVERED_OUT, "shipped", REPORTS)
    for profile in ("challenge", "eval", "dense"):
        if _holds(_reports_agree, _submission(profile), "shipped", CORE):
            return
    raise AssertionError("no held out run replays the shipped reports")


def _p_filename_dependent():
    if _holds(_p_hardcoded):
        raise AssertionError("already priced by the hardcoding check")
    if _holds(_p_nondeterministic):
        raise AssertionError("already priced by the determinism check")
    baseline = _submission("shipped")
    _reports_agree(baseline, "shipped", CORE)
    renamed = _submission("renamed")
    if all(_raw(renamed, name) == _raw(baseline, name) for name in REPORTS):
        raise AssertionError("the run is indifferent to the file names")


def _p_reads_shipped_store_path():
    store = _copy_store("challenge", "handed-store")
    decoy = _store("mutant")
    with _DECOY_LOCK:
        if os.path.exists(SHIPPED_STORE_PATH):
            raise AssertionError("a directory already sits at the shipped store path")
        plain = os.path.join(_scratch("plain"), "out")
        status, _err = _run_raw(store, plain)
        plain_ok = status == 0
        if plain_ok:
            again = os.path.join(_scratch("plain-again"), "out")
            _invoke(store, again)
            if [_raw(plain, n) for n in REPORTS] != [_raw(again, n) for n in REPORTS]:
                raise AssertionError("the run is not repeatable, so the probe is inconclusive")
        shutil.copytree(decoy, SHIPPED_STORE_PATH)
        try:
            os.chmod(SHIPPED_STORE_PATH, 0o755)
            with_decoy = os.path.join(_scratch("with-decoy"), "out")
            _invoke(store, with_decoy)
        finally:
            shutil.rmtree(SHIPPED_STORE_PATH, ignore_errors=True)
    if plain_ok and [_raw(plain, n) for n in REPORTS] == [_raw(with_decoy, n) for n in REPORTS]:
        raise AssertionError("the run ignores whatever sits at the shipped store path")


def _p_nondeterministic():
    store = _store("challenge")
    runs = []
    for tag in ("nd-a", "nd-b", "nd-c", "nd-d"):
        out = os.path.join(_scratch(tag), "out")
        _invoke(store, out)
        runs.append([_raw(out, name) for name in REPORTS])
    if all(run == runs[0] for run in runs):
        raise AssertionError("repeated runs agree byte for byte")


def _p_round_once():
    out = _submission("mtime")
    if _digest_of(out, "chargeback_offices.json") != ROUND_ONCE_CHARGEBACK:
        raise AssertionError("the chargeback is not the round once reading")


def _p_draft_settling():
    summary = json.loads(_raw(_submission("probe"), "settle_summary.json").decode("utf-8"))
    if not (summary.get("buffer_minutes") == 45 and summary.get("pin_rank") == 90 and summary.get("round_cap") == 96):
        raise AssertionError("the settling parameters are not the draft digest values")


def _p_extra_output_files():
    out = _submission("challenge")
    if not sorted(set(os.listdir(out)) - set(REPORTS)):
        raise AssertionError("the output directory holds only the reports")


def _p_writes_beside_output():
    parent = _scratch("beside")
    out = os.path.join(parent, "out")
    _invoke(_store("probe"), out, cwd=parent, home=_scratch("beside-tmp"))
    if not sorted(set(os.listdir(parent)) - {"out"}):
        raise AssertionError("nothing was written beside the output directory")


# =====================================================================
# Checks.
# =====================================================================


@criterion(description="the delivered program writes every report into an output directory that does not exist before the run")
def program_runs_and_writes_every_report(workspace: Path) -> bool:
    return _holds(_p_runs)


@criterion(description="the delivered reports follow the serialisation contract")
def delivered_reports_follow_the_serialisation_contract(workspace: Path) -> bool:
    return _holds(_p_serialisation)


@criterion(description="the delivered manifest chain is recomputable from the reports beside it")
def manifest_chain_recomputable(workspace: Path) -> bool:
    return _holds(_p_manifest)


@criterion(description="table reports written for a held out store carry the documented header rows")
def held_out_header_rows(workspace: Path) -> bool:
    return _holds(_p_header_rows_on_held_out)


@criterion(description="the delivered reports for the shipped store are exact")
def delivered_shipped_reports_exact(workspace: Path) -> bool:
    return _holds(_gated, "delivered", REPORTS)


@criterion(description="the merge decisions, occurrence list and settled schedule are exact on the challenge store")
def core_spine_exact_on_challenge(workspace: Path) -> bool:
    return _holds(_assert_full_core, "challenge")


@criterion(description="the core spine is exact on the store that reaches the round cap")
def core_spine_exact_on_eval(workspace: Path) -> bool:
    return _holds(_assert_full_core, "eval")


@criterion(description="the core spine is exact on the largest held out store")
def core_spine_exact_on_dense(workspace: Path) -> bool:
    return _holds(_assert_full_core, "dense")


@criterion(description="the core spine is exact on the store declaring the modification time ladder")
def core_spine_exact_on_mtime(workspace: Path) -> bool:
    return _holds(_assert_full_core, "mtime")


@criterion(description="the core spine is exact on the content line, boundary and override probe store")
def core_spine_exact_on_probe(workspace: Path) -> bool:
    return _holds(_assert_full_core, "probe")


@criterion(description="the core spine is exact on a store whose effective revision is an earlier approved revision")
def core_spine_exact_on_revision_shift(workspace: Path) -> bool:
    return _holds(_assert_full_core, "revshift")


@criterion(description="the challenge store written in other encodings under other file names gives the same reports")
def encoding_shift_reproduces_challenge(workspace: Path) -> bool:
    return _holds(_p_encoding_shift)


@criterion(description="every report is exact on the largest held out store")
def all_reports_exact_on_dense(workspace: Path) -> bool:
    return _holds(_gated, "dense", REPORTS)


@criterion(description="the outbox replay ledger is exact on the challenge store")
def outbox_replay_ledger_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["outbox_replay.jsonl", "reconciliation.json"])


@criterion(description="the attendee resolution ledger is exact on the eval store")
def alias_resolution_ledger_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["alias_resolutions.tsv"])


@criterion(description="candidate resolutions and zone transitions are exact on the eval store")
def zone_resolution_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["resolutions.tsv", "zone_transitions.tsv"])


@criterion(description="the exclusion and override records are exact on the challenge store")
def exceptions_ledger_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["exceptions.jsonl"])


@criterion(description="the conflicts before settling are exact on the challenge store")
def conflicts_before_settling_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["conflicts.jsonl"])


@criterion(description="the settling trace and summary are exact on the store that reaches the round cap")
def settle_trace_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["settle_moves.csv", "settle_summary.json"])


@criterion(description="the settling trace and summary are exact on a store that stops on pinned pairs")
def settle_trace_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["settle_moves.csv", "settle_summary.json"])


@criterion(description="the load fold is exact on the eval store")
def load_fold_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["load_steps.tsv", "load_summary.json"])


@criterion(description="attendance violations are exact on the challenge store")
def attendance_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["attendance.psv"])


@criterion(description="legs and travel blocks are exact on the challenge store")
def travel_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["legs.json", "travel_blocks.csv"])


@criterion(description="busy conflicts on coalesced periods are exact on the eval store")
def busy_conflicts_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["busy_conflicts.tsv"])


@criterion(description="the synchronisation entries and tokens are exact on the challenge store")
def sync_state_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["sync_entries.tsv", "sync_tokens.json"])


@criterion(description="the chargeback office rollup is exact on the challenge store")
def chargeback_offices_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["chargeback_offices.json"])


@criterion(description="the chargeback collection allocation is exact on the eval store")
def chargeback_collections_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["chargeback_offices.json", "chargeback_collections.json"])


@criterion(description="the authority audit is exact on the challenge store")
def authority_audit_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ["authority_audit.csv"])


@criterion(description="the drift report is exact on the eval store")
def drift_report_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ["drift.csv"])


@criterion(description="the outbox replay ledger is exact on the store that reaches the round cap")
def outbox_replay_ledger_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ['outbox_replay.jsonl'])


@criterion(description="the attendee resolution ledger is exact on the earlier revision store")
def alias_resolution_ledger_revshift(workspace: Path) -> bool:
    return _holds(_gated, "revshift", ['alias_resolutions.tsv'])


@criterion(description="the exclusion and override records are exact on the probe store")
def exceptions_ledger_probe(workspace: Path) -> bool:
    return _holds(_gated, "probe", ['exceptions.jsonl'])


@criterion(description="candidate resolutions and zone transitions are exact on the probe store")
def zone_resolution_probe(workspace: Path) -> bool:
    return _holds(_gated, "probe", ['resolutions.tsv', 'zone_transitions.tsv'])


@criterion(description="the conflicts before settling are exact on the modification time ladder store")
def conflicts_before_settling_mtime(workspace: Path) -> bool:
    return _holds(_gated, "mtime", ['conflicts.jsonl'])


@criterion(description="the settling trace and summary are exact on the modification time ladder store")
def settle_trace_mtime(workspace: Path) -> bool:
    return _holds(_gated, "mtime", ['settle_moves.csv', 'settle_summary.json'])


@criterion(description="the load fold is exact on the earlier revision store")
def load_fold_revshift(workspace: Path) -> bool:
    return _holds(_gated, "revshift", ['load_steps.tsv', 'load_summary.json'])


@criterion(description="attendance violations are exact on the probe store")
def attendance_probe(workspace: Path) -> bool:
    return _holds(_gated, "probe", ['attendance.psv'])


@criterion(description="legs and travel blocks are exact on the eval store")
def travel_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ['legs.json', 'travel_blocks.csv'])


@criterion(description="busy conflicts on coalesced periods are exact on the challenge store")
def busy_conflicts_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ['busy_conflicts.tsv'])


@criterion(description="the synchronisation entries and tokens are exact on the eval store")
def sync_state_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ['sync_entries.tsv', 'sync_tokens.json'])


@criterion(description="the chargeback office rollup is exact on the earlier revision store")
def chargeback_offices_revshift(workspace: Path) -> bool:
    return _holds(_gated, "revshift", ['chargeback_offices.json'])


@criterion(description="the authority audit is exact on the eval store")
def authority_audit_eval(workspace: Path) -> bool:
    return _holds(_gated, "eval", ['authority_audit.csv'])


@criterion(description="the drift report is exact on the challenge store")
def drift_report_challenge(workspace: Path) -> bool:
    return _holds(_gated, "challenge", ['drift.csv'])


@criterion(description="the shipped reports are replayed unchanged as the core reports of a held out store")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True when the cheat happened: the shipped answers come back for another store.
    return _holds(_p_hardcoded)


@criterion(description="the reports change once the files of one store carry different names")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # True when the cheat happened: renaming the files moved the reports.
    return _holds(_p_filename_dependent)


@criterion(description="the reports depend on a store placed at the shipped store path rather than the store named on the command line")
def negative_reads_input_corpus_at_runtime(workspace: Path) -> bool:
    # True when the cheat happened: a decoy at /app/data changed or enabled the run.
    return _holds(_p_reads_shipped_store_path)


@criterion(description="four runs over one store disagree")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # True when the cheat happened: repeated runs differ.
    return _holds(_p_nondeterministic)


@criterion(description="the chargeback carries every line at full precision and rounds once per office")
def negative_round_once_chargeback(workspace: Path) -> bool:
    # True when the wrong reading happened: the round once rollup was written.
    return _holds(_p_round_once)


@criterion(description="the settling parameters come from the draft digest rather than the governance schedule")
def negative_draft_ruleset_used(workspace: Path) -> bool:
    # True when the wrong reading happened: the draft buffer, pin rank and round cap were used.
    return _holds(_p_draft_settling)


@criterion(description="the output directory of a run holds files other than the twenty-five reports")
def negative_extra_files_in_output_directory(workspace: Path) -> bool:
    # True when the violation happened: something besides the reports was left in OUT_DIR.
    return _holds(_p_extra_output_files)


@criterion(description="a run writes files beside its output directory")
def negative_writes_beside_output_directory(workspace: Path) -> bool:
    # True when the violation happened: the run left files next to OUT_DIR, outside its temporary directory.
    return _holds(_p_writes_beside_output)


criteria.program_runs_and_writes_every_report(weight=1)
criteria.delivered_reports_follow_the_serialisation_contract(weight=1)
criteria.manifest_chain_recomputable(weight=1)
criteria.held_out_header_rows(weight=1)
criteria.delivered_shipped_reports_exact(weight=5)
criteria.core_spine_exact_on_challenge(weight=5)
criteria.core_spine_exact_on_eval(weight=5)
criteria.core_spine_exact_on_dense(weight=5)
criteria.core_spine_exact_on_mtime(weight=5)
criteria.core_spine_exact_on_probe(weight=5)
criteria.core_spine_exact_on_revision_shift(weight=5)
criteria.encoding_shift_reproduces_challenge(weight=5)
criteria.all_reports_exact_on_dense(weight=5)
criteria.outbox_replay_ledger_challenge(weight=3)
criteria.alias_resolution_ledger_eval(weight=3)
criteria.zone_resolution_eval(weight=3)
criteria.exceptions_ledger_challenge(weight=3)
criteria.conflicts_before_settling_challenge(weight=3)
criteria.settle_trace_eval(weight=3)
criteria.settle_trace_challenge(weight=3)
criteria.load_fold_eval(weight=3)
criteria.attendance_challenge(weight=3)
criteria.travel_challenge(weight=3)
criteria.busy_conflicts_eval(weight=3)
criteria.sync_state_challenge(weight=3)
criteria.chargeback_offices_challenge(weight=3)
criteria.chargeback_collections_eval(weight=3)
criteria.authority_audit_challenge(weight=3)
criteria.drift_report_eval(weight=3)
criteria.outbox_replay_ledger_eval(weight=3)
criteria.alias_resolution_ledger_revshift(weight=3)
criteria.exceptions_ledger_probe(weight=3)
criteria.zone_resolution_probe(weight=3)
criteria.conflicts_before_settling_mtime(weight=3)
criteria.settle_trace_mtime(weight=3)
criteria.load_fold_revshift(weight=3)
criteria.attendance_probe(weight=3)
criteria.travel_eval(weight=3)
criteria.busy_conflicts_challenge(weight=3)
criteria.sync_state_eval(weight=3)
criteria.chargeback_offices_revshift(weight=3)
criteria.authority_audit_eval(weight=3)
criteria.drift_report_challenge(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_input_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_round_once_chargeback(weight=-3)
criteria.negative_draft_ruleset_used(weight=-3)
criteria.negative_extra_files_in_output_directory(weight=-1)
criteria.negative_writes_beside_output_directory(weight=-1)
