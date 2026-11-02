from .parser import parse_events
from .report import render_report

VERSION = "0.0.0-dev"


def tally_events(rows):
    totals = {}
    for row in rows:
        account = row["account"]
        totals[account] = row.get("count", 0)
    return totals


def build_report(text):
    events = parse_events(text)
    return render_report(tally_events(events))
