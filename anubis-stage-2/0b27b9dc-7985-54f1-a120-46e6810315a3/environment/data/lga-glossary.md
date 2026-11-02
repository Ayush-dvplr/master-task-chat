# LGA glossary

Terms of art used by `SPEC-LGA.md` and its appendices. Each of these words has
an ordinary meaning that is close to the one fixed here and not the same as it.
Where this file and an instinct disagree, this file wins.

**admitted**. A run no layer refused at any of its events. A run that reaches
its last event without a refusal is admitted even when its audit continuity is
broken, because an audit event never refuses.

**denied**. A run some layer refused. A denied run is described by the first
refusal only: the layer, the sequence and the rule of the first event refused.
Later events of a denied run are still walked for reporting, and a run with
three refusals is still one denial.

**effective set**. The capability set the process actually holds, computed by
the formula in `lga-capability-appendix.md`. It is not the bounding set, not
the permitted set and not the union of the sets the corpus carries. A
capability in the bounding set but outside the effective set is not held.

**advisory capability**. A capability that at least one `cap-required` record
marks `advisory`. Its absence is recorded and never refuses an event.

**dispatch architecture**. The architecture of a run as a whole, taken from its
`exec` event. It is what an empty architecture field on another event is
repaired to. It is not necessarily the architecture of every event of that run,
because an event may carry its own.

**domain in force**. The domain the `exec` event leaves the process in: the
landing domain when the transition happens, and the source domain otherwise.
It is a property of the run rather than of a moment in it, and the access
events and the audit event of a run are judged against it.

**landing domain**. The domain a transition record names as the destination. It
is the domain in force after the `exec` event only when all three parts of the
transition triple are allowed. When one is absent the domain in force stays the
source domain, and the landing domain is still the landing domain of the
chosen record.

**repair**. One of the five corrections in `SPEC-LGA.md` section 5, applied to
a recorded event before the run is replayed. A repair never rejects a record
and never changes which run a record belongs to.

**group**. The set of corpus records sharing a stem up to the final hyphen of
the file name. A group's shards are read in whatever order and the result is
the same, because where a key repeats the winner is fixed by canonical shard
order rather than by reading order.

**canonical shard order**. Ascending order of shard file names compared as
text, then the order records are written inside a shard. It decides which of
two records with one identity key stands: the first, for every keyed group but
`runs-labels`, and the last, for `runs-labels`.

**canonical order**. Ascending order of canonical identifiers, compared as
text. Because identifiers are fixed width with leading zeros, text order and
numeric order agree.

**blank line**. A line of a corpus file that holds nothing before its line
ending, or nothing but whitespace characters. It carries no record in any
encoding, wherever it appears.

**atom**. One named, bounded relaxation of the shipped policy, drawn from the
`grant-atoms` group. An atom is not one of the five repairs and not a fix to
the corpus: it changes the policy, never the recorded runs. Where the
specification says an atom repairs a run, it means the atom alone admits that
run, which is what the `repairs_count` column counts.

**effective cost**. An atom's base cost times the multiplier of its kind.
Two of the seven multipliers are not stated anywhere; `SPEC-LGA.md` section
9.1 says how the cost controls fix them, and how a tie between consistent
pairs is settled. Every choice, sum and ordering over costs in the plan reads
the effective cost; every `cost` column in an artifact shows the base cost.

**forbidden atom**. An atom that, applied alone, admits at least one run
labelled `must_deny`. Forbidding is decided atom by atom and never against a
set of atoms.

**permissible atom**. Any atom that is not forbidden. A plan is built only from
permissible atoms.

**effective candidate**. A permissible atom that both names the object a
refusal named and, when added to the atoms chosen so far, either admits the run
or moves its refusal past the sequence the round's opening replay recorded for
that run. That recorded sequence is the baseline for the whole round. An atom
that names the right object and leaves that recorded sequence where it was is a
candidate and is not effective.

**round**. One pass over the `must_admit` runs still denied, choosing at most
one atom for each. Rounds run until none is denied, or until a round chooses
nothing, or until the cap of eight is reached.

**shrink**. The pass that drops every atom the plan can do without, taking
atoms in reverse canonical order. What survives is the plan.

**witness**. For an atom in the plan, the canonically first `must_admit` run
that the plan admits and that the plan without that atom denies. A witness is
the evidence that an atom earns its place.

**residual**. A run labelled `must_admit` that the plan does not admit. Its
status is `nonconvergent` when the rounds reached the cap and `unrepairable`
when they stopped before it.

**shipped policy**. The policy as the corpus carries it, with no atom applied.
Most artifacts describe the shipped policy; section 12 of the specification
lists the seven that do not.

**site**. The operator whose labels the work must satisfy. The site marks runs
`must_admit` and `must_deny`; a run the site left `unlabelled` constrains
nothing and is still replayed and reported.
