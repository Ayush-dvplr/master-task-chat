from pilot import PASS, assignment, event_date, owner_team, read_text, retire_events, split_quota

assert event_date("2026-04-02T23:30:00-02:00 RETIRE x") == "2026-04-03"
assert event_date("2026-04-02T01:30:00.123+05:30 RETIRE x") == "2026-04-01"
assert event_date("2026-04-02T10:16:34Z RETIRE x") == "2026-04-02"

p, o = retire_events([
    "2026-04-02T10:16:34Z RETIRE product=dp-910-50 ticket=1",
    "2025-04-02T10:16:34Z RETIRE product=DP91050",
    "2026-06-07T05:05:06Z NOTICE product=DP1",
    "2026-06-07T05:05:06Z RETIRE owner=a.b",
    "",
])
assert p == {"DP91050": "2025-04-02"} and o == {"a.b": "2026-06-07"}, (p, o)

rows = [
    {"owner": "a", "team": "t1", "active_from": "2020-01-01", "active_to": "2021-01-01"},
    {"owner": "a", "team": "t2", "active_from": "2022-01-01", "active_to": ""},
    {"owner": "b", "team": "t3", "active_from": "2020-01-01", "active_to": ""},
]
assert assignment(rows, "a", "2021-06-01")["team"] == "t1"
assert assignment(rows, "a", "2019-01-01") is None
assert owner_team(rows, {}, "a", "2021-06-01") is None
assert owner_team(rows, {}, "a", "2021-01-01") == "t1"
assert owner_team(rows, {}, "a", "2022-01-01") == "t2"
assert owner_team(rows, {"b": "2024-01-01"}, "b", "2024-01-01") is None
assert owner_team(rows, {"b": "2024-01-02"}, "b", "2024-01-01") == "t3"

assert read_text("integer", '"60"') == 60
assert read_text("integer", "-1") is PASS and read_text("integer", "") is PASS
assert read_text("boolean", "TrUe") is True and read_text("boolean", "yes") is PASS
assert read_text("string", '"x y"') == "x y" and read_text("enum", "a") == "a"
assert read_text("list", "") == [] and read_text("list", ' a , b,,c ') == ["a", "b", "", "c"]
assert read_text("list", '""') == []

r = split_quota(10, {"A": (1, None), "B": (1, None), "C": (1, None)})
assert r == {"A": 4, "B": 3, "C": 3}, r
r = split_quota(10, {"A": (1, 2), "B": (1, None), "C": (1, None)})
assert r == {"A": 2, "B": 4, "C": 4}, r
r = split_quota(10, {"A": (1, 1), "B": (1, 1)})
assert r == {"A": 1, "B": 1}, r
assert sum(split_quota(100, {"A": (3, None), "B": (5, 10), "C": (7, 20)}).values()) <= 100
print("ok")
