"""Second lever pass: weights in {1,3,5}, six more held-out rounds."""
import re, sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

def once(old, new):
    global text
    assert text.count(old) == 1, old[:80]
    text = text.replace(old, new)

once('HELD_PUBLISHED = (8507130061071785379, ("groups", "rules", "amendments"))\n',
     'HELD_PUBLISHED = (8507130061071785379, ("groups", "rules", "amendments"))\n'
     'HELD_GROUPS_CASCADE = (3181624921004179892, ("groups",))\n'
     'HELD_GROUPS_PUBLISHED = (5312478116728989745, ("groups",))\n'
     'HELD_RULES_CASCADE = (8134192291377319089, ("rules",))\n'
     'HELD_RULES_PUBLISHED = (1923352942072717872, ("rules",))\n'
     'HELD_AMENDMENTS_PUBLISHED = (8190252848473934209, ("amendments",))\n'
     'HELD_EVERY_CASCADE = (7518129537147583783, ("groups", "rules", "amendments"))\n')

once('''    by their legacy identifiers, and which lodges one edge whose two ends are
    one job and reverses a lodgement, the classification, invalidation sets,
    work ledger, store summary and amendment optima come out exactly."""''',
     '''    by their legacy identifiers, and which reverses a lodgement, the
    classification, invalidation sets, work ledger, store summary and
    amendment optima come out exactly."""''')

once('''    derived state and the accepted sets come out exactly."""
    _held(HELD_EVERY, STATE_FAMILY + CASCADE_FAMILY)''',
     '''    derived state and the accepted sets come out exactly."""
    _held(HELD_EVERY, STATE_FAMILY)''')

NEW = [
    ("groups_cascade", "HELD_GROUPS_CASCADE", "CASCADE_FAMILY",
     "on a held-out round of its own whose slot group memberships name some\n    jobs by their legacy identifiers, the classification, invalidation sets,\n    work ledger, store summary and amendment optima come out exactly.",
     "on a held-out round of its own whose slot group memberships name jobs by legacy identifiers the cascade documents come out exactly"),
    ("groups_publication", "HELD_GROUPS_PUBLISHED", "PUBLICATION_FAMILY",
     "on a held-out round of its own whose slot group memberships name some\n    jobs by their legacy identifiers, the graph documents, defect register,\n    verification notes, manifest and summary come out exactly.",
     "on a held-out round of its own whose slot group memberships name jobs by legacy identifiers the publication documents come out exactly"),
    ("rules_cascade", "HELD_RULES_CASCADE", "CASCADE_FAMILY",
     "on a held-out round of its own whose charge rules name some jobs by\n    their legacy identifiers, the classification, invalidation sets, work\n    ledger, store summary and amendment optima come out exactly.",
     "on a held-out round of its own whose charge rules name jobs by legacy identifiers the cascade documents come out exactly"),
    ("rules_publication", "HELD_RULES_PUBLISHED", "PUBLICATION_FAMILY",
     "on a held-out round of its own whose charge rules name some jobs by\n    their legacy identifiers, the graph documents, defect register,\n    verification notes, manifest and summary come out exactly.",
     "on a held-out round of its own whose charge rules name jobs by legacy identifiers the publication documents come out exactly"),
    ("amendments_publication", "HELD_AMENDMENTS_PUBLISHED", "PUBLICATION_FAMILY",
     "on a held-out round of its own whose amendment payloads name some jobs\n    by their legacy identifiers, the graph documents, defect register,\n    verification notes, manifest and summary come out exactly.",
     "on a held-out round of its own whose amendment payloads name jobs by legacy identifiers the publication documents come out exactly"),
    ("every_cascade", "HELD_EVERY_CASCADE", "CASCADE_FAMILY",
     "on a held-out round of its own that names jobs by legacy identifiers\n    in group memberships, charge rules and amendment payloads at once, the\n    classification, invalidation sets, work ledger, store summary and\n    amendment optima come out exactly.",
     "on a held-out round of its own naming jobs by legacy identifiers in groups, rules and amendments at once the cascade documents come out exactly"),
]

tests = "".join(
    f'\n\ndef test_package_crosswalk_{n}_exact():\n    """POSITIVE: {doc}"""\n    _held({c}, {f})\n'
    for n, c, f, doc, _ in NEW)
anchor = '    _held(HELD_PUBLISHED, PUBLICATION_FAMILY)\n'
once(anchor, anchor + tests.rstrip("\n") + "\n")

wrappers = "".join(
    f'@criterion(description="{d}")\ndef package_crosswalk_{n}_exact(workspace: Path) -> bool:\n    return _graded(workspace, test_package_crosswalk_{n}_exact)\n\n\n'
    for n, _, _, _, d in NEW)
anchor = '@criterion(description="the crew quantities were converted at one flat'
once(anchor, wrappers + anchor)

once('@criterion(description="on a held-out round naming jobs by legacy identifiers in groups, rules and amendments at once the state and cascade documents come out exactly")',
     '@criterion(description="on a held-out round naming jobs by legacy identifiers in groups, rules and amendments at once the derived state and accepted sets come out exactly")')
once('@criterion(description="on that round the graph documents, defect register, verification notes, manifest and summary come out exactly")\ndef package_crosswalk_every_publication_exact',
     '@criterion(description="on a held-out round of its own naming jobs by legacy identifiers in groups, rules and amendments at once the publication documents come out exactly")\ndef package_crosswalk_every_publication_exact')

def reweight(m):
    name, w = m.group(1), int(m.group(2))
    if name.startswith("package_crosswalk_"):
        w = 5
    elif w > 0 and name not in ("delivered_documents_present_and_parse", "delivered_package_shape"):
        w = 3
    return f"criteria.{name}(weight={w})"
text = re.sub(r"criteria\.(\w+)\(weight=(-?\d+)\)", reweight, text)
anchor = "criteria.package_crosswalk_every_publication_exact(weight=5)\n"
once(anchor, anchor + "".join(f"criteria.package_crosswalk_{n}_exact(weight=5)\n" for n, *_ in NEW))
path.write_text(text)
pos = sum(int(w) for w in re.findall(r"criteria\.\w+\(weight=(\d+)\)", text))
print("patched; positive", pos)
