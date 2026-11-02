"""Write one mutant of solution/solve.py per rule into mut/<id>.py (each replacement must match exactly once)."""
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
DST = Path(sys.argv[2])

GREEDY = '''def greedy_lane(season, lane):
    order = sorted(lane, key=lambda q: (-q.weight * q.dur, q.aid))
    pos = {q.aid for q in lane}
    clash = {}
    for a, b in season.incompatible:
        if a in pos and b in pos:
            clash.setdefault(a, set()).add(b)
            clash.setdefault(b, set()).add(a)
    before = {}
    for a, b in season.precedence:
        if a in pos and b in pos:
            before.setdefault(b, []).append(a)
    cap = season.capacity[(lane[0].region, lane[0].crew_type)]
    load = {}
    got = {}
    for q in order:
        best = None
        for s in season.lane_starts(q):
            span = range(s, s + q.dur)
            if any(load.get(d, 0) + q.crews > cap[d] for d in span):
                continue
            bad = False
            for o in clash.get(q.aid, ()):
                if got.get(o) is not None:
                    oq = season.requests[o]
                    if got[o] <= s + q.dur - 1 and s <= got[o] + oq.dur - 1:
                        bad = True
            for p in before.get(q.aid, ()):
                if p in got and (got[p] is None or got[p] + season.requests[p].dur - 1 >= s):
                    bad = True
            if bad:
                continue
            key = (season.cost(q, s), is_moved(q, s), s)
            if best is None or key < best[0]:
                best = (key, s)
        day = None if best is None else best[1]
        got[q.aid] = day
        if day is not None:
            for d in range(day, day + q.dur):
                load[d] = load.get(d, 0) + q.crews
    return [got[q.aid] for q in lane]


def replan('''

M = {
    # levers
    "S1_greedy": [("def replan(", GREEDY),
                  ("LanePlanner(season, lane, season.incompatible, season.precedence).solve()",
                   "greedy_lane(season, lane)")],
    "S2_nomove": [("m2 += is_moved(q[i], day)", "m2 += 0"),
                  ("m2 += is_moved(q[i], None)", "m2 += 0")],
    "S3_tie": [("if key not in nxt or val < nxt[key]:", "if key not in nxt or val[:2] < nxt[key][:2]:"),
               ("best = min(v for k, v in frontier.items() if not k[0])",
                "best = min((v for k, v in frontier.items() if not k[0]), key=lambda v: v[:2])")],
    # intake
    "R_unknown_asset": [('if rec["asset_id"] not in inp.assets:\n            why = "unknown_asset"\n        elif',
                         'if False:\n            why = "unknown_asset"\n        elif rec["asset_id"] not in inp.assets:\n            return\n        elif')],
    "R_out_of_season": [('rec["earliest_start"] < inp.first_day or rec["latest_finish"] > inp.last_day', 'False')],
    "R_window_short": [('rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]', 'False')],
    "R_duplicate_last": [('        elif rec["asset_id"] in accepted:\n            why = "duplicate_request"\n',
                          '        elif rec["asset_id"] in accepted and rec["asset_id"] in active:\n            why = "duplicate_request"\n')],
    "R_check_order": [('        elif rec["earliest_start"] < inp.first_day or rec["latest_finish"] > inp.last_day:\n            why = "out_of_season"\n        elif rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]:\n            why = "window_too_short"\n',
                       '        elif rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]:\n            why = "window_too_short"\n        elif rec["earliest_start"] < inp.first_day or rec["latest_finish"] > inp.last_day:\n            why = "out_of_season"\n')],
    "R_check_order_first": [('        if rec["asset_id"] not in inp.assets:\n            why = "unknown_asset"\n        elif rec["earliest_start"] < inp.first_day or rec["latest_finish"] > inp.last_day:\n            why = "out_of_season"\n',
                             '        if rec["earliest_start"] < inp.first_day or rec["latest_finish"] > inp.last_day:\n            why = "out_of_season"\n        elif rec["asset_id"] not in inp.assets:\n            why = "unknown_asset"\n')],
    "R_prepub_applied": [('if ev[0] == "heartbeat" or ev[0] <= inp.published_at:', 'if ev[0] == "heartbeat":')],
    "R_heartbeat_ignored": [('        return ("heartbeat",)\n', '        return None\n')],
    "R_withdraw_unknown_free": [('        else:\n                self.ignored += 1\n        self.days', '        else:\n                pass\n        self.days')],
    "R_loss_max": [('lost[key] = lost.get(key, 0) + f["count"]', 'lost[key] = max(lost.get(key, 0), f["count"])')],
    "R_loss_ignored": [('- lost.get((r, t, d), 0)', '- 0')],
    "R_malformed_counted_none": [('            if ev is None:\n                self.ignored += 1\n', '            if ev is None:\n                pass\n')],
    "R_log_pos_zero": [('enumerate(inp.log, 1)', 'enumerate(inp.log, 0)')],
    # feasibility
    "R_blackout_all_days": [('if s not in black and all(', 'if all(d not in black for d in range(s, s + q.dur)) and all(')],
    "R_incompat_ignored": [('self.incompatible = [(a, b) for a, b in inp.incompatible if a in live and b in live]',
                            'self.incompatible = []')],
    "R_prec_same_day": [('p in waiting or p in held or p in busy or', 'p in waiting or p in held or p in {k for e_, k in out if e_ > day} or')],
    "R_prec_ignored": [('self.precedence = [(a, b) for a, b in inp.precedence if a in live and b in live]',
                        'self.precedence = []')],
    # weights and factors
    "R_band_strict": [('if floor <= peak:', 'if floor < peak:')],
    "R_peak_mean": [('self.peak[key] = max(self.peak.get(key, mw), mw)', 'self.peak[key] = self.peak.get(key, mw)')],
    "R_public_weight_1": [('wp = inp.customers.get((aid, "public"), 0) * inp.class_weight["public"]',
                           'wp = inp.customers.get((aid, "public"), 0)')],
    "R_defer_fixed": [('return q.weight * q.dur * self.inp.defer_factor', 'return q.weight * q.dur * 4'),
                      ('unit = q.dur * season.inp.defer_factor', 'unit = q.dur * 4')],
    "R_roster_all": [('if row["status"] == "on_duty":', 'if row["status"] != "leave":')],
    # moved
    "R_moved_deferred_stays": [('return q.published != "none" and q.published != start',
                                'return q.published != "none" and (q.published != start or start is None)')],
    "R_moved_def_to_sched": [('return q.published != "none" and q.published != start',
                              'return q.published not in ("none", None) and q.published != start')],
    "R_moved_log_requests": [('return q.published != "none" and q.published != start',
                              'return q.published != start')],
    # reasons and reporting
    "R_reason_order": [('            if not season.lane_starts(q):\n                reason = "no_feasible_start"\n            elif any(start[p] is None for p in before_of.get(aid, ())):\n                reason = "predecessor_deferred"\n',
                        '            if any(start[p] is None for p in before_of.get(aid, ())):\n                reason = "predecessor_deferred"\n            elif not season.lane_starts(q):\n                reason = "no_feasible_start"\n')],
    "R_nofeasible_window_only": [('            if not season.lane_starts(q):\n', '            if q.last_start < q.early:\n')],
    "R_schedule_by_id": [('key=lambda r: (r["start"], r["asset_id"])', 'key=lambda r: r["asset_id"]')],
    "R_rejected_by_position": [('key=lambda r: (r["source"], r["position"])', 'key=lambda r: r["position"]')],
    "R_crew_days_no_crews": [('"crew_days": 0 if day is None else q.crews * q.dur', '"crew_days": 0 if day is None else q.dur')],
    "R_end_exclusive": [('"end": None if day is None else day + q.dur - 1', '"end": None if day is None else day + q.dur')],
    "R_segment_deferred_all": [('"deferred_risk_days": sum(r[seg] for r in rows if r["status"] == "deferred")',
                                '"deferred_risk_days": sum(r["risk_days"] for r in rows if r["status"] == "deferred")')],
    "R_missing_input_ok": [('        print(f"derive_report: error: {exc}", file=sys.stderr)\n        return 2\n',
                            '        print("derive_report: error", file=sys.stderr)\n        return 2\n')],
}

src = SRC.read_text()
DST.mkdir(parents=True, exist_ok=True)
for mid, reps in M.items():
    text = src
    for old, new in reps:
        n = text.count(old)
        if n != 1:
            raise SystemExit(f"{mid}: pattern found {n} times: {old[:60]!r}")
        text = text.replace(old, new)
    compile(text, mid, "exec")
    (DST / f"{mid}.py").write_text(text)
print(len(M), "mutants written")
