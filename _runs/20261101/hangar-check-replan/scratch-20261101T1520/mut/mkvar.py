src = open('solve.py').read()
def rep(s, a, b, n=1):
    assert s.count(a) == n, (a, s.count(a))
    return s.replace(a, b)
# finish tie flipped (prefer later finishes)
f = src
f = rep(f, "layer = {(0, 1): {0: (0, 0, 0, (after_season,) * count, (after_season,) * count, (0,) * count)}}",
           "layer = {(0, 1): {0: (0, 0, 0, (after_season,) * count, (-after_season,) * count, (0,) * count)}}")
f = rep(f, "step = (request.penalty, 0, 1, after_season, after_season, 0, 0)", "step = (request.penalty, 0, 1, after_season, -after_season, 0, 0)")
f = rep(f, "0 if start == request.published else 1, start, finish, squeeze, shifts)", "0 if start == request.published else 1, start, -finish, squeeze, shifts)")
f = rep(f, "combos = {0: (0, 0, 0, (after_season,) * len(order), (after_season,) * len(order), ())}", "combos = {0: (0, 0, 0, (after_season,) * len(order), (-after_season,) * len(order), ())}")
f = rep(f, "placement[request.request_id] = (chosen[3][k], chosen[4][k], chosen[5][k])", "placement[request.request_id] = (chosen[3][k], -chosen[4][k], chosen[5][k])")
open('v_finish.py','w').write(f)
s = src
s = rep(s, "layer = {(0, 1): {0: (0, 0, 0, (after_season,) * count, (after_season,) * count, (0,) * count)}}",
           "layer = {(0, 1): {0: (0, 0, 0, (-after_season,) * count, (after_season,) * count, (0,) * count)}}")
s = rep(s, "step = (request.penalty, 0, 1, after_season, after_season, 0, 0)", "step = (request.penalty, 0, 1, -after_season, after_season, 0, 0)")
s = rep(s, "0 if start == request.published else 1, start, finish, squeeze, shifts)", "0 if start == request.published else 1, -start, finish, squeeze, shifts)")
s = rep(s, "combos = {0: (0, 0, 0, (after_season,) * len(order), (after_season,) * len(order), ())}", "combos = {0: (0, 0, 0, (-after_season,) * len(order), (after_season,) * len(order), ())}")
s = rep(s, "placement[request.request_id] = (chosen[3][k], chosen[4][k], chosen[5][k])", "placement[request.request_id] = (-chosen[3][k], chosen[4][k], chosen[5][k])")
open('v_start.py','w').write(s)
K = "key=lambda row: (CLASS_RANK[row[\"aircraft_class\"]], due_of[row[\"request_id\"]], row[\"request_id\"]))"
open('v_nodue.py','w').write(rep(src, K, "key=lambda row: (CLASS_RANK[row[\"aircraft_class\"]], row[\"request_id\"]))"))
open('v_noclass.py','w').write(rep(src, K, "key=lambda row: (due_of[row[\"request_id\"]], row[\"request_id\"]))"))
open('v_revid.py','w').write(rep(src, K, "key=lambda row: (CLASS_RANK[row[\"aircraft_class\"]], due_of[row[\"request_id\"]], [-ord(c) for c in row[\"request_id\"]]))"))
print('ok')
