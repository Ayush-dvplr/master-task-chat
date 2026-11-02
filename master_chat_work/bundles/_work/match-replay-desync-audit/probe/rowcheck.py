"""For a staged room: does the agent program's figure for the TRUE value of each quantity match the published one? Usage: python3 -B rowcheck.py <agent.py> <room>"""
import importlib.util, json, sys, os
agent, room = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("agent", agent); a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
cap = os.path.join(room, "data")
notes = a.parse_notes(cap); rows, published = a.parse_calibration(cap); register, order = a.parse_roster(cap)
charters = list(notes['charters'])
for w in order:
    if register[w]['charter'] not in charters: charters.append(register[w]['charter'])
charters.sort(); baselines, counts = a.charter_baselines(register, order, charters)
context = {'key': notes['key'], 'labels': notes['labels'], 'unit_words': notes['unit_words'], 'cadence': notes['cadence'],
           'charters': charters, 'captures': a.parse_captures(cap), 'register': register, 'order': order,
           'opening_charter': {w: register[w]['charter'] for w in order}, 'windows': a.parse_windows(cap),
           'bench': a.parse_bench(cap), 'baselines': baselines, 'counts': counts, 'settled_cache': {}}
truth = dict(json.load(open(os.path.join(room, "truth_q.json"))), labels=context['labels'], unit_words=context['unit_words'], cadence=context['cadence'])
for row in rows:
    got = a.produce(row['name'], truth, context)
    print(row['control'], row['name'], "ok" if got == published.get(row['control']) else "DIFF %s vs %s" % (got, published.get(row['control'])))
