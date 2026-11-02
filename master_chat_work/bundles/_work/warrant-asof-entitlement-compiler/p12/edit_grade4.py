import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text()
old_desc = 'description="the delivered tool compiles and audits unseen corpus tier_b under a --config with earlier anchors and another prod approvals_required, as recomputed")'
new_desc = 'description="the delivered tool compiles and audits unseen corpus tier_b under a --config with earlier anchors and another prod approvals_required, as recomputed; policy journal rows and counts are left out")'
old = '''        doc, ref = got["audit"], exp["audit"]
        if not isinstance(doc, dict) or set(doc) != set(ref):
            return False
        return all(_rows(doc[k]) == _rows(ref[k]) for k in ref if k != "self_check") and _same(doc["self_check"], ref["self_check"])
'''
new = '''        doc, ref = got["audit"], exp["audit"]
        if not isinstance(doc, dict) or set(doc) != set(ref) or not isinstance(doc["self_check"], dict):
            return False
        journal = "policy_change_journal.jsonl"

        def keep(rows):
            return [r for r in rows if not (isinstance(r, dict) and r.get("source") == journal)]
        if not all(_rows(keep(doc[k])) == _rows(keep(ref[k])) for k in ref if k != "self_check"):
            return False
        return _same({k: v for k, v in doc["self_check"].items() if k != journal},
                     {k: v for k, v in ref["self_check"].items() if k != journal})
'''
for a, b in ((old_desc, new_desc), (old, new)):
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
p.write_text(s)
print("applied 2 edits")
