"""Apply harden lp1 r1 rule-text edits to data docs and to the embedded copies in tests."""
import sys
from pathlib import Path
B = Path(sys.argv[1])
D = B / "environment/data"
T = B / "tests/test_output.py"
EDITS = {
"rulebook_charge.md": [
("""The base value of a forge entry is the base charge of the artifact it forges,
from the artifact catalogue, multiplied by the number of units the entry
forges.""",
"""The base value of a forge entry is the base charge of the artifact it forges,
from the artifact catalogue."""),
("""All three operators apply to every settled forge entry, each exactly once. The
order in which they compose is fixed for the whole season but is not recorded
in this rulebook; different orders give different ember, because each operator
yields a whole number before the next applies.""",
"""All three operators apply to the base value of every settled forge entry, each
exactly once, and each yields a whole number before the next applies. The order
in which they compose is fixed for the whole season but is not recorded in this
rulebook. The charge of the entry is the value the last operator yields,
multiplied by the number of units the entry forges."""),
("""A settled salvage entry carries no charge of its own and never moves a
workshop's accrued settled charge.""",
"""A settled salvage entry carries no charge of its own."""),
("""charged at eighty percent of the value the operators give.""",
"""charged at eighty percent of the charge H5 gives."""),
],
"rulebook_salvage.md": [
("""## S2. Credit window - the smith's last three admitted forges of that family

A salvage is credited only when the forge entry it names is among the **last
three forge entries of the same artifact family that were settled for the same
canonical smith, on days strictly before the salvage's own day**.

The canonical smith is the one the salvage's own handle resolves to on the
salvage day, and the three settled forges are read against that same canonical
smith, whatever handles they were filed under. Forge entries that were not
settled do not occupy a place in the window; the window holds the last three
that were. Forge entries of a different artifact family do not occupy a place
in the window either - each family carries its own window.
""",
"""## S2. Credit window

A salvage is credited only when the forge entry it names is among the last
three live forge entries of the same artifact family settled for the same
canonical smith on days strictly before the salvage's own day. The canonical
smith is the one the salvage's own handle resolves to on the salvage day, and
the forge entries are read against that canonical smith whatever handles they
were filed under. Each artifact family carries its own window.
"""),
("""## S5. Salvage does not consume

A salvage entry commits no reagents. It cannot be blocked by a shortage of
stock, and it never draws a workshop closer to its charge cap.""",
"""## S5. Salvage and the cap ledger

A salvage entry commits no reagents and cannot be blocked by a shortage of
stock. When a salvage is credited, the charge of its source forge entry leaves
the accrued settled charge of the workshop that filed that forge, for every
forge entry settled after the salvage. The charge stays in every charge figure
the season reports. A workshop already closed under A4 stays closed."""),
("""A salvage that the credit window turns away does not redeem its forge entry, so
a later salvage naming the same forge entry is still judged on its own.""",
"""A salvage the credit window turns away is not credited, and a later salvage
naming the same forge entry is judged on its own."""),
],
"rulebook_editions.md": [
("""## E3. Salvage entries - the settlement day for a salvage is the forge day

A salvage entry is governed by the edition in force on the day of the forge
entry it salvages, **not** by the edition in force on the day the salvage
itself was filed.

This is deliberate and it is the rule for this season. A salvage returns the
reagents that were actually committed when the artifact was made, so the
edition that was in force at the forge is the edition that governs the return.
When an artifact has been re-cut between the forge and the salvage, the two
entries are therefore governed by different editions, and the salvage follows
the older one.
""",
"""## E3. Salvage entries

A salvage entry is governed by the edition in force on the day of the forge
entry it salvages.
"""),
],
"rulebook_identity.md": [
("""to on that earlier day, and a handle filed after resolves to the later result.
Two entries filed under the same handle on either side of a rename or merge
therefore belong to different canonical smiths.""",
"""to on that earlier day, and a handle filed after resolves to the later result."""),
],
"rulebook_scarcity.md": [
("""charge cap. Retirement is a
condition of the forge in the same way as the floor in V4. It never stands in
for the charge cap or the floor, which are judged on the same forge as well.
Retirement stops draws only""",
"""charge cap.
Retirement stops draws only"""),
],
"invariants.md": [
("""Every claim below holds of a correctly settled season. They are properties of the
result, not instructions for producing it.
""",
"""Every claim below holds of a correctly settled season. They are properties of the
result, not instructions for producing it.

## Terms

The rulebooks use these terms as defined here.

**Live forge entry.** A settled forge entry that no salvage has yet been credited
against.

## Properties
"""),
],
}
ts = T.read_text()
for name, pairs in EDITS.items():
    p = D / name
    s = p.read_text()
    for a, b in pairs:
        if s.count(a) != 1:
            sys.exit("data %s: %d matches for %r" % (name, s.count(a), a[:60]))
        if ts.count(a) != 1:
            sys.exit("tests %s: %d matches for %r" % (name, ts.count(a), a[:60]))
        s = s.replace(a, b)
        ts = ts.replace(a, b)
    p.write_text(s)
T.write_text(ts)
print("ok")
