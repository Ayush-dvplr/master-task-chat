A film and tape restoration lab settles its restoration cycles against the frames
it actually delivers. The settlement run for the current cycle was lost before it
was filed. The catalogue that fed it survives intact, and so does a complete,
audited earlier cycle that was published with its control figures. Rebuild the
settlement.

Everything you need sits under `/app/data`. Nobody will tell you which file holds
what, so read the lot before you write any code. Among it you will find the
scanned elements and their lineage, the cut lists, the defect and repair records,
the holder accounts, the charters that open the vaults and the overflow lanes, a
rulebook for each subsystem, a statement of the properties any correct settlement
satisfies, a schedule setting out the shape of every document the settlement
files, and the published earlier cycle carried under separately marked names.

Three standing conventions of this lab are deliberately left unwritten: how a
frame count is quantised when it is converted between cadences, the order in which
the three settlement operators compose, and the fraction of a repair ceiling that
carries through to the next repair worked on the same defect. Each rule is stated
on its own; only their composition is missing. The published cycle exists so you
can recover them: exactly one combination of the three reproduces every figure
published for it, and no other combination reproduces even its per-programme
figures.

The rulebooks are filed by subsystem, not in the order the rules apply. Work the
order out from the properties the result must satisfy and from what the published
cycle can be made to reproduce.

Write a reusable settlement program at `/app/out/cadence_settle.py`. It takes two
positional arguments, a catalogue directory and an output directory, and it must
settle whatever cycle it is pointed at, not this one in particular. It will be run
against other cycles whose elements, programmes, rules in play, charters and
partition counts differ from these. Use the Python standard library only. Every
figure you deliver must come from the catalogue.

Into `/app/out`, alongside the program, file the settlement documents:

```
summary.json            the cycle as a whole
reconciliation.json     the cycle as a whole
reel_audit.json         the elements and their resolved identity
conform_report.json     the programmes and their shots
defect_findings.json    the condition work
repair_ledger.json      the condition work
cadence_ledger.json     the settled frame counts
allocation_ledger.json  the allocation
vault_index.json        the allocation
vault_<vault id>.json   one for each vault the charter opens
lane_<lane id>.json     one for each overflow lane the charter opens
```

How many vault and lane reports there are, and what they are called, is for you to
work out from the catalogue. A vault or lane that ends up carrying nothing still
gets its report.

Every report must agree with every other. The cycle must reconcile: each stage
balances, and the residual over the whole cycle is zero. There is exactly one
correct settlement. The delivery schedule in the catalogue gives the field names
and the presentation order of every document, and one fully formed example report
from the published cycle sits beside it. Keys sorted, two space indent, one
trailing newline, whole numbers written as whole numbers. Running the program
twice on the same catalogue must produce byte-identical files.

Do not modify anything under `/app/data`. Do not hardcode any figure from this
cycle into the program, and do not branch on file or directory names.

In your final message, state plainly the quantisation convention you recovered and
that you recovered rather than assumed it; the composition order of the three
settlement operators; the fraction of a repair ceiling that carries through to the
next repair worked on the same defect; at which cadence a programme settles, and
which programmes gained and which lost because of it; the settled total for the
cycle, and how many programmes were admitted, held, shed and voided; which
programmes voided and why; the reconciliation residual, and the settled total
shown two different ways; the vaults and lanes you opened and what each carries;
which elements were folded, which retired, and which lineage event does not bear
on this cycle; and the condition grade you settled for each programme.

You have 7200 seconds to complete this task.
