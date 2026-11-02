import json

from task import build_report, tally_events


def test_tally_accumulates_rows():
    assert tally_events([
        {"account": "alpha", "delta": 2},
        {"account": "alpha", "delta": 3},
        {"account": "beta", "delta": -1},
    ]) == {"alpha": 5, "beta": -1}


def test_build_report_from_json_rows():
    report = build_report(json.dumps({"rows": [{"account": "alpha", "delta": 4}]}))
    assert report["accounts"] == {"alpha": 4}
    assert report["grand_total"] == 4
