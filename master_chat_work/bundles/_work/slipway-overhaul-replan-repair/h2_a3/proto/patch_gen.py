"""Generator variant for held-out rounds: active crosswalk legacy ids planted in
group memberships, charge rule subjects and amendment payloads, plus two
quiet amendment shapes. Default legacy=() keeps every old corpus byte identical.

usage: python3 -B patch_gen.py <test_output.py>
"""
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
count = 0


def sub(old, new):
    global text, count
    n = text.count(old)
    if n != 1:
        raise SystemExit("anchor matched %d times: %r" % (n, old[:80]))
    text = text.replace(old, new)
    count += 1


# 1 the helper that picks the written form of one job identifier
sub('''def write_edge_journal(dest, E):
''', '''def _legacy(E, place, job_id):
    """The identifier written for one job in one place. A held-out round may
    write a job under the legacy identifier its active crosswalk row carries;
    every other round writes the canonical identifier."""
    if place not in E.get("legacy", ()) or job_id not in E["by_id"]:
        return job_id
    if child_seed(str(E["seed"]) + "|" + place + "|" + job_id, "legacy") % 3:
        return "OLD-" + job_id.split("-")[1]
    return job_id


def write_edge_journal(dest, E):
''')

# 2 group memberships
sub('''            rows.append([g["group_id"], member, g["precinct"], g["precedence"],
                         "open", "lodged by the berth desk"])''',
    '''            rows.append([g["group_id"], _legacy(E, "groups", member),
                         g["precinct"], g["precedence"],
                         "open", "lodged by the berth desk"])''')

# 3 charge rule subjects
sub('''    for r in E["rules"]:
        rows.append(dict(r))
    for i in range(200):''', '''    for r in E["rules"]:
        rec = dict(r)
        for field in JOB_FIELDS_OF_RULES:
            if field in rec:
                rec[field] = _legacy(E, "rules", rec[field])
        rows.append(rec)
    for i in range(200):''')

# 4 amendment payloads
sub('''               "note": a["note"], "payload": dict(a["payload"])}
''', '''               "note": a["note"], "payload": dict(a["payload"])}
        for field in JOB_FIELDS_OF_PAYLOADS:
            if field in rec["payload"]:
                rec["payload"][field] = _legacy(E, "amendments",
                                                rec["payload"][field])
''')

# 5 the two quiet amendment shapes and the plant assertion
sub('''def write_amendments(dest, E):
''', '''def _lever_amendments(E):
    """The reversal of the round's first lodgement."""
    out = [
        {"amendment_id": "AMD-120", "sequence": 20, "kind": "reversal",
         "payload": {"amendment_id": "AMD-102"},
         "note": "the desk took the first lodgement back"},
    ]
    for a in out:
        a["state"] = "lodged"
        a["raised_round"] = E["round_index"]
        a["raised_by"] = OWNERS[a["sequence"] % len(OWNERS)]
    return out


def _assert_legacy(root, E):
    """Every place a held-out round plants legacy identifiers in carries at
    least one live row that names a job by its legacy identifier."""
    planted = {"groups": False, "rules": False, "amendments": False}
    for row in read_delim(root / "exclusive_slot_groups.csv", ","):
        if row["state"] == "open" and row["member_job"].startswith("OLD-"):
            planted["groups"] = True
    for rec in read_jsonl(root / "conditional_charge_rules.jsonl"):
        if rec.get("state") == "in_force" and any(
                str(rec.get(f, "")).startswith("OLD-")
                for f in JOB_FIELDS_OF_RULES):
            planted["rules"] = True
    for rec in read_jsonl(root / "amendment_journal.jsonl"):
        if (rec.get("state") == "lodged"
                and any(str(rec["payload"].get(f, "")).startswith("OLD-")
                        for f in JOB_FIELDS_OF_PAYLOADS)):
            planted["amendments"] = True
    for place in E.get("legacy", ()):
        if not planted[place]:
            raise SystemExit("the held-out round planted no legacy identifier"
                             " in " + place)


def write_amendments(dest, E):
''')

# 6 write_corpus takes the legacy places
sub('''def write_corpus(dest, seed=None):
    """Write one paper directory. Running this twice over one seed comes out
    byte identical."""''', '''def write_corpus(dest, seed=None, legacy=()):
    """Write one paper directory. Running this twice over one seed comes out
    byte identical. A held-out round names the places that write legacy
    identifiers; the shipped round and the old minted rounds name none."""''')
sub('''    E = mint(seed)
    _write_tables(root, E)''', '''    E = mint(seed)
    E["legacy"] = tuple(legacy)
    _write_tables(root, E)''')
sub('''    E["amendments"] = _amendments(E)
    write_amendments(root, E)
    write_papers(root, E)''', '''    E["amendments"] = _amendments(E)
    if "amendments" in E["legacy"]:
        E["amendments"] += _lever_amendments(E)
    write_amendments(root, E)
    _assert_legacy(root, E)
    write_papers(root, E)''')

path.write_text(text)
print("patched", count)
