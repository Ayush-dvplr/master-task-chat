You are the confinement engineer on call for a vault estate whose privileged
administration binary runs under four independent enforcement layers. The
control plane that decides whether any given invocation is allowed to proceed
is called LGA. The engineer who was to write its solver left before starting
it, the estate has a backlog of recorded invocations nobody has checked, and
the change window cannot open until the solver exists and the grant plan it
emits has been produced.

Your job is to write that solver and to produce the plan it emits.

Everything the solver consumes sits under the directory `/app/data`. The
governing contract for the whole system is the file `/app/data/SPEC-LGA.md`,
and that file names five appendices and a glossary that sit beside it and are
part of the same contract. The specification is authoritative and complete. It
states every definition, every constant, every boundary, every encoding and
every output shape this task depends on. Where your instinct about Linux
confinement and that file disagree, the file wins, including where the rule it
states is not the rule a reasonable engineer would have chosen, and including
where it fixes the meaning of an ordinary word.

The corpus is flat and it is large. Nothing here tells you how many files there
are, what any one of them holds, or which encoding it uses. Working that out is
part of the task. Some files feed the decision and some carry material the
specification tells you to record rather than act on. A file being present is
not an argument that it feeds a particular output, and a field being present is
not an argument that it is trustworthy. The specification names the records
that are advisory and you are expected to notice them.

You have 7200 seconds to complete this task.

The work has two deliverables that stand or fall together. The first is the
plan itself, written as twenty-four artifacts. The second is the solver that
produced them, delivered as a source file so that it can be run again on a
corpus it has never seen. A plan that is correct but assembled by hand is not a
finished solver, and a solver that runs but emits a wrong plan is not a
finished plan. Both are graded.

The artifacts you write are exactly these, at exactly these paths:

```
/app/out/principal_registry.jsonl
/app/out/syscall_index.tsv
/app/out/pam_stack_resolved.csv
/app/out/selinux_type_graph.json
/app/out/seccomp_program.jsonl
/app/out/pam_verdicts.csv
/app/out/capability_ledger.csv
/app/out/domain_transitions.tsv
/app/out/seccomp_decisions.jsonl
/app/out/arch_dispatch.tsv
/app/out/admission_ledger.csv
/app/out/denial_attribution.jsonl
/app/out/blocked_syscalls.tsv
/app/out/capability_gaps.csv
/app/out/audit_continuity.jsonl
/app/out/relaxation_atoms.csv
/app/out/forbidden_atoms.tsv
/app/out/grant_plan.csv
/app/out/iteration_trace.jsonl
/app/out/minimality_witness.csv
/app/out/residual_denials.tsv
/app/out/conservation.json
/app/out/summary.json
/app/out/manifest.json
```

The solver itself is delivered as `/app/out/lgactl.py`, and it is the same
program, byte for byte, that wrote the twenty-four artifacts beside it.

The estate has recorded a population of runs. Each run is an ordered sequence
of events, and replaying one against the shipped policy either admits it or
refuses it. A run is admitted when no layer refuses any of its events. A run is
refused by the first event any layer refuses, and that one event fixes the
layer, the sequence and the rule the run is described by, whatever happens at
its later events. The four layers own different kinds of event and each has its
own algebra, and no two of those algebras resolve the same way. Getting one of
them right and the other three approximately right produces a population
verdict that looks plausible and is wrong.

Some of the recorded events are malformed. Every malformation that appears has
a stated repair, and a repair is a correction to apply rather than a reason to
drop a record. Repairs happen before a run is replayed, never during, and the
number of events each repair corrected is a figure you report at the end. An
architecture field left empty is not the same as an architecture field holding
a name, a capability written as a decimal index is the same capability as the
one written in full, and a permission field holding two names means the event
needs both of them.

Beside the policy the estate carries a catalogue of grant atoms. An atom is one
named, bounded relaxation, and each atom carries a cost. Some atoms are narrow
and name one object; others are broad and change a whole filter or a whole
stack line. Breadth and cost do not move together, and the cheapest atom that
touches the right object is frequently the wrong choice, because an atom that
would also let through a run the estate has marked as one that must stay
refused may never be used, however cheap it is and however well it would serve
the run in front of you. Deciding which atoms are ruled out that way is
something you do against the shipped policy, one atom at a time, and never
against a set of atoms taken together.

What you owe is the least set of permissible atoms that admits every run the
estate marked as one that must be admitted, while every run it marked as one
that must stay refused is still refused. Least here has a precise meaning the
specification fixes, and it is a property you have to demonstrate rather than
assert: for every atom your plan keeps, there is a run that your plan admits
and that the same plan without that one atom refuses, and you name that run,
the layer that then refuses it and the sequence at which it does. An atom with
no such run has no business in the plan.

Relaxing one layer does not finish a run. A run whose authentication was the
thing standing in its way can reach the executable label check and be refused
there instead, and a run whose label check clears can reach a capability it
does not hold. The plan therefore settles rather than being computed in one
pass, and it settles under a cap on how many passes it may take. A run that has
not been admitted when the cap is reached is recorded as such, with the status
the specification names for that case, rather than being quietly dropped from
the population or counted as satisfied.

Most of the artifacts describe the estate as it stands today, before any atom
is applied. A small number describe it after the plan is settled, and the
specification says which ones. One of them is the first artifact in the list
above, which carries for every principal the disposition its runs end in, and
that disposition cannot be known until the plan has settled. An artifact that
reports the wrong side of that line is wrong even when every number in it is
internally consistent.

Two of the artifacts are reconciliations rather than reports. One of them
closes the population over the whole run set and over the labelled part of it
separately, and the other summarises the shape of the work. Neither is derived
from the other, and copying a figure from one into the other rather than
deriving both from the run set is a way to produce two artifacts that agree and
are both wrong.

The audit trail matters on its own account. One capability in this estate is
advisory, meaning that a run missing it is not refused for missing it, and the
specification says how to tell which one that is rather than naming it here.
That capability is also what carries the audit trail, so a run that proceeds
without it proceeds with its audit continuity broken, and the artifact that
reports continuity distinguishes a run that lost the capability from a run that
held the capability and was refused the channel.

Output shape is part of the answer and not a matter of taste. Header rows are
written for some artifacts and suppressed for others, and the specification
says which. Columns appear in the order it states. Identifiers are emitted in
one canonical form and type names in a different one. A column the
specification declares is written on every row even when it is empty on most of
them. Every set is ordered by the key the specification states for it, which
is not always alphabetical. Mappings
emitted as JSON objects carry their keys in the order the specification lists
rather than sorted, numbers are emitted without a decimal point, a field
documented as a fixed-width code keeps its leading zeros, and files are written
as UTF-8 without a byte order mark and end with a newline. Two of the ordering
rules are stable sorts over keys that repeat across many rows, and one artifact
is ordered by a value that only a different artifact produces.

An atom names what it changes through a small structured target string, and one
of the elements that string can carry is commentary that changes nothing at
all. A solver that treats every element as meaningful will rule out atoms that
were never in question and will match atoms against refusals they have no
bearing on. The plan records, for each atom it keeps, the settling pass in
which that atom was first chosen, so an atom chosen early and kept through the
shrink carries the pass it was chosen in rather than the pass the plan
finished in.

One of the artifacts that reports what the shipped policy blocks is ordered by
a number that only the plan produces, so it cannot be written until the plan
has settled even though every other column in it describes the estate as it
stands today. Rows the plan never reached share a single value for that number
and fall back to the remaining ordering keys, so the ordering is total and two
correct solvers produce the same file.

The figures in your closing summary and the figures in your artifacts describe
one estate and must agree. A summary that reports a count the delivered ledger
contradicts is a summary of work that was not done, and the two reconciliation
artifacts exist so that an inconsistency upstream shows up as a number that
refuses to close rather than as a file that merely looks tidy.

Every artifact is written, including the ones that turn out to have nothing to
report. An artifact whose rows all vanished still carries its header line and
still ends with a newline (a JSON lines artifact with no rows is an empty
file), and an architecture that dispatched no event at all still carries its
row with zeros in every count. The catalogue artifact reports
every atom the estate carries, not only the ones the plan uses, so an atom that
repairs nothing and an atom that is ruled out both appear there with the
figures the specification asks for. The witness artifact carries exactly one
row for each atom the plan keeps and no rows for anything else, so its row
count and the plan's row count are the same number.

Runs the estate left unlabelled constrain nothing about the plan and are
reported exactly like the rest. They are replayed, they are attributed, they
are counted in the population totals and they appear in the ledgers. A solver
that filters the population down to the labelled part before it starts will
produce artifacts that are short by hundreds of rows and totals that no
reconciliation can close. The same goes for units, binaries and principals that
no run names: they exist in the corpus, they belong to no run, and nothing that
is keyed by run may invent a row for them.

The last artifact describes the other twenty-three as they were actually
written, giving for each of them the byte length, the count of newline
characters and the digest of its bytes, keyed by file name in the order the
specification lists them. It is written after the others and it describes them
rather than predicting them, so an artifact revised after the manifest was
built leaves the manifest wrong.

Nothing here tells you how many runs the estate recorded, how many atoms the
catalogue carries, how many of them are ruled out, how many passes the plan
takes to settle or how many runs end up recorded as not having settled. Every
one of those is something the corpus decides and your solver reports, and a
figure carried over from a guess rather than derived from the corpus will
disagree with the artifact that states it.

The solver you deliver is run as `lgactl.py CORPUS_DIR OUT_DIR`. It reads only
the corpus directory it is handed and writes only into the output directory it
is handed. It uses the Python standard library and nothing else, and it reaches
no network host at any point. Given one corpus it writes the same bytes every
time it runs. Given a corpus whose records are listed in a different order it
writes the same bytes, because every ordering the contract states is one the
solver imposes rather than one it inherits from whichever file a record
happened to land in. It exits zero when it has written every artifact, exits
two when it is called with the wrong number of arguments or handed a corpus
directory that is absent, and exits three when the corpus is there but a group
it needs is empty.

Leave `/app/data` exactly as you found it. Nothing under that directory is
yours to edit, rename, extend or delete, and a solver that rewrites its own
input is a solver nobody can re-run. Write nothing into `/app/out` beyond the
twenty-five files named above, so no scratch file, no intermediate dump and no
backup copy sits beside the deliverables when you finish.

Do not cheat by using online solutions or hints specific to this task.

When the work is done, finish with a short written summary. It confirms that
the twenty-five files were written under `/app/out`, naming `lgactl.py` among
them, it states that the solver used the standard library alone and reached
no network host, and it states each of the closing figures the specification
lists, by name and by value. Not one of them is a number you can copy out of
an artifact; each has to be worked out across the rows. They are the total
number of events the five repair rules corrected between them, counting an
event once for each rule that corrected it, the count of atoms that are not
ruled out and still repair no run that must be admitted, the mean cost of the
atoms in the plan rounded to two decimal places, and the count of principals
whose final disposition is that they were granted.
