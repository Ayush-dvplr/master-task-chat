"""Scratch: build kill-test solver variants from the probe agent program."""
import os
here = os.path.dirname(os.path.abspath(__file__))
base = open(os.path.join(here, "solvers", "s1_probe.py"), encoding="utf-8").read()

def variant(name, pairs):
    s = base
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:40])
        s = s.replace(old, new)
    open(os.path.join(here, "solvers", name + ".py"), "w", encoding="utf-8").write(s)

GROUPS = "    groups = billing_groups(accounts)\n"
WALK_CLASS = '''class LineWalk:
    """Resolve the top account at every lookup."""

    def __init__(self, accounts):
        self.accounts = accounts

    def __getitem__(self, account_id):
        current = account_id
        seen = {current}
        while True:
            parent = self.accounts[current]["parent"]
            if not parent or parent not in self.accounts or parent in seen:
                return current
            current = parent
            seen.add(current)


def load_plan_changes('''
INFORCE = """    moments, states, initial = timelines[account_id]
    index = bisect.bisect_right(moments, moment)
    return states[index - 1] if index else initial
"""
# s2: group resolved per line, nothing carried between lines
variant("s2_perline", [("def load_plan_changes(", WALK_CLASS), (GROUPS, "    groups = LineWalk(accounts)\n")])
# s3: carried state keyed by the parent text as written
variant("s3_label", [('"parent": canonical_account(parts[3]) if parts[3] else "",', '"parent": parts[3],')])
# s4: plan and segment applied at the end of the month only
variant("s4_endonly", [(INFORCE, "    moments, states, initial = timelines[account_id]\n    return states[-1] if states else initial\n")])
# s5: greedy one level group
variant("s5_greedy", [(GROUPS, "    groups = {a: (accounts[a]['parent'] if accounts[a]['parent'] in accounts else a) for a in accounts}\n")])
# s6: naive: per line walk and linear scan of the change list
variant("s6_naive", [("def load_plan_changes(", WALK_CLASS), (GROUPS, "    groups = LineWalk(accounts)\n"),
                     (INFORCE, """    moments, states, initial = timelines[account_id]
    found = initial
    for index, when in enumerate(moments):
        if when <= moment:
            found = states[index]
    return found
""")])
# s7: recursive memo
variant("s7_recursive", [(GROUPS, """    import functools

    @functools.lru_cache(maxsize=None)
    def top_of(account_id):
        parent = accounts[account_id]["parent"]
        if not parent or parent not in accounts:
            return account_id
        return top_of(parent)

    groups = {a: top_of(a) for a in accounts}
""")])
# s8: iterative memo (strong control)
variant("s8_memo", [(GROUPS, """    groups = {}
    for start in accounts:
        path, on_path, current = [], set(), start
        while current not in groups:
            parent = accounts[current]["parent"]
            if not parent or parent not in accounts or parent in on_path:
                groups[current] = current
                break
            path.append(current)
            on_path.add(current)
            current = parent
        top = groups[current]
        for member in path:
            groups[member] = top
""")])
print("ok")
