You are the storage engineer on call for a fleet whose application filesystem is
being relocated off an ageing source estate onto a tier of target devices. The
control plane that decides what the relocation still has to do is called STRATA.
The previous relocation run stopped part way through, and the fleet cannot
resume the move until a planner has been implemented and the plan it emits has
been produced. No starter planner is supplied.

Your job is to implement that planner and to produce the plan it emits.

Everything the planner consumes sits under the directory `/app/data`. The
governing contract for the whole system is the file `/app/data/SPEC-STRATA.md`.
That specification is authoritative and complete. It states every definition,
every constant, every boundary, every encoding and every output shape this task
depends on. Where your instinct about filesystems and that file disagree, the
file wins, including where the rule it states is not the rule a reasonable
engineer would have chosen. Read it in full before you decide what the corpus
holds, because the corpus does not announce itself and the directory listing is
not a description of the work.

The corpus is flat and it is large. Nothing here tells you how many files there
are, what any one of them holds, or which encoding it uses. Working that out is
part of the task. Some files feed the plan and some carry material the
specification tells you to record rather than act on. A file being present is
not an argument that it feeds a particular output, and a field being present is
not an argument that it is trustworthy. The specification names the values that
are advisory and you are expected to notice them.

You have 7200 seconds to complete this task.

The work has two deliverables that stand or fall together. The first is the plan
itself, written as twenty-four artifacts. The second is the planner that
produced them, delivered as a source file so that it can be run again on a
corpus it has never seen. A plan that is correct but assembled by hand is not a
finished planner, and a planner that runs but emits a wrong plan is not a
finished plan. Both are graded.

The artifacts you write are exactly these, at exactly these paths:

```
/app/out/object_inventory.jsonl
/app/out/device_topology.json
/app/out/extent_map.tsv
/app/out/symlink_topology.jsonl
/app/out/mutation_replay.jsonl
/app/out/scope_resolution.csv
/app/out/link_clusters.jsonl
/app/out/resume_state.jsonl
/app/out/xattr_ledger.csv
/app/out/special_nodes.tsv
/app/out/placement.csv
/app/out/sharing_expansion.jsonl
/app/out/allocation_projection.csv
/app/out/delta_workset.tsv
/app/out/metadata_workset.jsonl
/app/out/window_schedule.tsv
/app/out/split_ledger.jsonl
/app/out/descriptor_budget.csv
/app/out/cutover_sequence.txt
/app/out/rollback_plan.jsonl
/app/out/conservation.json
/app/out/cli_contract.json
/app/out/manifest.json
/app/out/summary.json
```

The planner is delivered as `/app/out/stratactl.py`. It takes the corpus
directory as its first argument and the output directory as its second, and it
writes those same twenty-four artifacts into whatever output directory it is
handed. It reads nothing outside the corpus directory it is given, it reaches no
network, and it imports nothing beyond the Python standard library. The rules it
applies are the ones you have read and built into it, so it does not read this
specification at run time and does not require that file to be present in the
corpus it is handed. Both directories reach it through those two arguments
alone, so its source carries no path from this machine anywhere in the code it
runs, not as a default, not as a fallback and not inside a message it prints. It is run
again on a corpus built from inputs you have never seen, exercising only rules
the specification documents, and the plan it produces there is expected to be as
correct as the one you deliver.

The specification fixes the exact column order, key order, sort order, encoding
and line ending of every artifact. Content that is right at the wrong path, or
right in the wrong order, or right with a column omitted, is a wrong artifact.
The order of keys inside a JSON object is the order the specification lists,
which is not alphabetical order, and an artifact whose keys have been sorted is
wrong. Every file is UTF-8 without a byte order mark, uses LF line endings, and
ends with exactly one newline.

Several definitions in that specification carry more weight than their length
suggests, and the plan is wrong in a way that is hard to see if any one of them
is read loosely.

The word relocatable has a precise meaning and it carries four conditions rather
than one. A status field alone does not settle it, the conditions are tested in
a stated order, and an object that fails more than one of them still reports
exactly the first that failed. Objects that are not relocatable still appear in
every artifact the specification fills with every object, and they take no part
in placement, sharing, scheduling or cutover.

Physical space and logical space are different quantities and the plan reports
both. A hole occupies logical space and no physical space, and copying one turns
a sparse file into a dense file and fills the target. A preallocated range
occupies physical space on the target and is never copied. A range that lives
inside the inode occupies neither and is never copied. Only one class of range
is ever read from the source at all, and the specification says which.

Ranges arrive with generations, they overlap each other, and they reach past the
end of the file they belong to. Each of those is a documented malformation with
a stated repair rather than a rejection, the repairs compose in a stated order
where more than one applies, and a range repaired into nothing has its own
stated outcome and is still reported. A range that has been repaired is used in
its repaired form everywhere afterwards.

Two paths that differ only in Unicode normalisation form are one path, and the
corpus carries both forms. An inode reached by several paths is one inode
holding one copy of its data, and the paths that are not its primary become
metadata operations rather than second copies. Which path is primary is settled
by a chain of four keys applied in order, and the corpus drives that chain to
every one of its four levels, so a chain that stops early gets the primary path,
or the level that settled it, wrong somewhere in the tree, and the artifacts that
order themselves by path follow a wrong primary there.

Symlinks are never followed for their contents. Their targets are preserved as
they are, relative and absolute alike, and the plan classifies each of them by
where it would resolve rather than by rewriting it. Resolution has a stated hop
cap, a stated outcome when the cap is reached and a separate stated outcome when
a chain returns somewhere it has already been, and both occur in the corpus.
Whether a symlink occupies any space at all turns on one boundary, and the
corpus carries targets sitting exactly on it and one byte either side.

Named pipes, sockets and device nodes are recreated from their metadata and are
never opened as though they held data. A device number is built from two fields
by a stated formula, one of those fields carries values the formula cannot hold,
and that overflow has a stated repair and is reported. An inode of one of those
kinds that carries no record of its own still reaches the plan.

The activity that happened after the previous run stopped is replayed against
what that run had already done. Whether an event is replayed at all is a
question about one boundary, and the corpus contains events sitting exactly on
it and one past it. An event that names something the inventory does not hold
has a stated outcome rather than being dropped silently. Replaying is what
decides which paths still exist, which inodes are still live, and which of the
ranges the previous run had already committed are no longer any use, and a
committed range is undone by a write that meets it or by a truncation that cuts
below it, where meeting and merely touching at an endpoint are different things.
What the previous run committed and what it merely started are also different
things. A missing checkpoint group is distinct from a group whose committed
value is `NIL`, and neither is numeric zero. The specification distinguishes
these cases from partial and excess commitments and states their outcomes.

Shared physical ranges survive as sharing only between devices that sit in one
share domain. Where the objects holding one shared range end up in more than one
domain, the range is materialised once per domain, and the extra copies are what
turn a comfortable target into a full one. Exactly one object owns each copy, by
a stated rule, and every other holder of that range becomes a metadata operation
rather than a copy, reporting the bytes the specification states for it.

Where an object lands is not settled in one pass. A device that cannot hold what
it has been given sheds work to another device, shedding changes which domains
hold a shared range, and changing that changes what every device is holding. The
attribution is rebuilt from scratch at the start of each round, while inside a
round what each device is holding moves as the work is shed, so the order the
devices are taken in is part of the rule rather than an implementation detail.
The specification states
how many rounds this runs for, how much each device sheds in one round, which
object it sheds and what happens to a device that is still overcommitted when
the rounds run out. The corpus reaches the last round.

The schedule is bounded twice over, once by the bytes a window will carry and
once by the number of inodes it will hold open at a time, and an inode already
open in a window costs nothing further. Whether a copy that does not fit is
moved to a later window or cut into pieces across several is not a judgement
call; the specification states which happens and when, and it states what
becomes of the bytes that never fit anywhere. Those bytes decide which objects
reach the cutover at all.

Cutover is ordered so that a directory precedes everything beneath it, and the
key that produces that order is not the key the plan already sorts by
everywhere else. Each cutover step carries the guard that has to hold before it
is safe and the action that undoes it, both chosen by stated rules from what the
rest of the plan says about that object, and an object the schedule could not
finish carries its own stated outcome instead of a step.

The identity that has to close is that everything a device has been given is
either copied in this run, resumed from what the previous run finished,
reserved without being copied, or left over. The residual is that total minus
those four, it is stated to be zero for every device, and it is zero only when
everything upstream of it is right.

Some rules of engagement apply to how you work rather than to what you compute.
The corpus under `/app/data` is read-only material and it arrives unmodified at
the end of the run, so nothing you do edits, moves, deletes or rewrites anything
inside it. `/app/out` is the complete, flat delivery root: it contains exactly
the twenty-five named regular files (the twenty-four artifacts listed above and
`stratactl.py`), with no extra entries, subdirectories or symlinks. No scratch
file, backup copy, intermediate dump or log is left there. Every figure you
report is one you computed from the corpus in this run rather than one you
assumed, and where you state a count it
agrees with the artifact it describes.

The plan has to account for the parts of the estate that are excluded as well as
the parts that move. An object that takes no part in the relocation is still
counted with its reason visible, a window that carries nothing still produces
its row, a device that receives nothing still produces its row, and an object
with no extended attributes at all still produces its row carrying zero and the
empty string. An artifact that silently drops the cases it decided were
uninteresting is a wrong artifact even when every row it kept is right. Where a
record has no value for an output text field, the field is present and carries
the empty string, and where it has no value for an output count, the field is
present and carries zero, except where the specification gives an explicit
sentinel such as the checkpoint committed value -1. These output conventions do
not change the input's `NIL`-only absence rule. A field is never omitted and a
row is never dropped to avoid stating an empty value.

The tables that report counts and the tables that report amounts have to agree
with each other. The bytes a device is said to hold are the bytes its objects
are attributed in another artifact, the bytes a window is said to carry are the
bytes the schedule placed in it, the number of objects a device holds is the
number of rows that name it, and the totals in the closure artifacts are the
totals of the tables they summarise. Producing each artifact independently and
never reconciling them is the failure this design is built to catch, because the
digests and the residual agree only when the whole plan agrees.

The closure artifacts carry a digest over an ordered list. The order is stated
and it is the order of the table the parts are drawn from, so a digest computed
over a sorted copy, or over a set, or over the parts in the order they happened
to be produced where the specification names a different order, is a wrong
digest even when every part is individually correct.

The planner decides what to do with malformed input rather than refusing it.
Every malformation the corpus carries has a stated repair, the repairs compose
in a stated order where more than one applies to a record, and a record that has
been repaired is used in its repaired form from that point on. A run that
rejects a malformed record, or that raises on it, or that repairs it for one
artifact and uses the raw form for another, produces a plan that disagrees with
itself.

The planner exits zero when it produces a plan. It exits with the usage code
when it is invoked with the wrong number of arguments, and with the policy code
when the path it was handed as a corpus fails to resolve to a directory. Those
two codes are stated in the specification and the contract artifact you deliver
reports them, so the numbers in that artifact and the behaviour of the planner
agree with each other.

Treat the run as one that has to be repeatable by somebody else. Running the
planner twice into two clean directories yields the same bytes both times, with
no timestamp, no host name, no absolute path of the machine it ran on, no random
identifier and no iteration order of a hash table leaking into any artifact.
Feeding it the same records in a different row order yields the same bytes as
well, because the ordering of every table is a property of the specification
rather than of the input.

Work only from the corpus and the specification beside it. Do not look up
solutions online. The domain is invented for this task, so an answer taken from
documentation elsewhere is an answer to a different question, and any figure
that came from a source other than the corpus in front of you is a fabricated
figure whatever it happens to match.

When the work is done, finish with a short written summary. Open it by naming
every one of the twenty-five files you delivered, each at its full absolute
path, so a reader can see the whole delivery without listing the directory.
Then state each of the following figures by name and value. The sum of the
utilisation figures in parts per million across every window row of the
descriptor budget. The number of window placements that opened a descriptor,
summed across every window. The total bytes the schedule placed across every
window. The total copy bytes across every row of the delta work set. The total
bytes recorded against the metadata operations. The total attributed bytes
across every device. The sum of the headroom across every device, which runs
negative where the tier is overcommitted. The inode on the five hundredth data
row of the window schedule in its canonical order. The total bytes the schedule
placed in window index zero across every device. The total bytes added across
the estate by sharing that spans more than one domain. The total bytes left
deferred across every device. The total length in UTF-8 bytes of every path in
the cutover sequence. The number of rollback rows that carry a step of zero. The
number of metadata operations whose verb is reflink. The number of objects shed
in the last shedding round. The number of devices that end overcommitted. The
number of shared physical ranges materialised into three or more copies. The
total bytes resumed from durable checkpoint entries across every device. The
number of hard link clusters whose primary path was settled at the fourth key.
The path on the first line of the cutover sequence.
