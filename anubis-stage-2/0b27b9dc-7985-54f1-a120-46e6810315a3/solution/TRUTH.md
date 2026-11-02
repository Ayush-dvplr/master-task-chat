# TRUTH.md - 0b27b9dc-7985-54f1-a120-46e6810315a3

Author side worked answer. It never reaches the agent: the agent image copies
only `environment/data`. Every number below was computed by running
`solution/solve.py` over the shipped corpus and checked against the reference
the verifier embeds in `tests/test_output.py`.

The corpus records 620 confined invocations of a privileged binary and the
policy four enforcement layers apply to them. The solver replays every run,
reports which layer refused it and at which event, and then settles the least
set of grant atoms that admits the 146 runs the site marked `must_admit` while
the 84 it marked `must_deny` stay refused. Twenty four artifacts and the solver
itself are delivered, and the closing summary states four figures that are
derivations over the artifacts rather than fields of them.

## Defect

There is no broken program to repair here. What the agent is handed is a
complete contract and a corpus that satisfies it, and the defect is in the
reading: load bearing rules that a competent engineer reaches past because the
ordinary meaning of the words is close enough to look right. Each one is
stated in the shipped contract and each one changes rows in a graded artifact.

1. (focal) **The strictest filter wins, not the first.** The seccomp appendix
   says every loaded filter answers on its own and the kernel returns the
   strictest of those answers. Under first match a run whose first filter
   allows a call is admitted while the contract refuses it. 92 runs are
   refused at this layer and `seccomp_decisions.jsonl` carries 2721 rows.

2. (focal) **Argument conditions are exact.** Admitted runs load private
   filters that no defaults record declares, holding conditions set on the
   exact recorded first argument: a refusing rule on the failing side of each
   boundary (`LT`, `GT`, `NE`, `MASKED_EQ`), a non refusing rule on the holding
   side (`LE`, `GE`, `EQ`, `MASKED_EQ`), and a refusing rule on argument index
   one that must never match. A comparison read one step off, an argument
   index ignored, or an undeclared filter treated as anything but `ALLOW`,
   refuses a run the policy admits.

3. (focal) **Rank decides the transition record, not file order.** Two
   transition records exist for most runs' source and executable pair, they
   name different landing domains, and the record written first carries the
   higher rank. A reader that takes the first record it meets lands the
   process in the decoy domain and misjudges that run's whole tail.

4. (focal) **The effective capability set is a derivation, not a field.** The
   capability appendix gives the computation over six sets and two flags.
   Treating the bounding set as the answer moves the verdict on the 66 runs
   refused at this layer and every row of `capability_ledger.csv`. The
   advisory `CAP_AUDIT_WRITE` is used by 62 `capuse` events, 25 of them outside
   the effective set, and none of those may refuse.

5. (focal) **An atom that would admit a refused run may never be used.** 94 of
   the 1200 atoms are ruled out this way, disproportionately the cheap broad
   ones. A cost first search that skips the check produces a plan that is
   cheaper, smaller and wrong, and breaks the `must_deny` guarantee.

6. (focal) **The plan settles rather than being computed.** Relaxing one layer
   exposes the next refusal in the same run. The first round admits 48 of the
   146 runs; eight rounds admit 128 and leave 18 recorded as `nonconvergent`.

7. (focal) **Labels are relabelling batches; the last record wins.** SPEC
   section 3 makes `runs-labels` the one exception to the first record rule.
   `runs-labels-a.csv` carries 78 stale labels, in producer form, for runs that
   `runs-labels-b.properties` labels again. The generic first record rule
   reads a different labelled population and settles a different plan.

8. (focal) **The note element runs to the end of the target.** SPEC section
   7. 97 atom targets carry a note whose text holds a further `key=value`
   after a semicolon. Splitting the whole target on semicolons reads that text
   as a real element, which overrides the true one, so the atom stops matching
   its refusal or stops being forbidden.

9. (focal) **The rfc5424 record element closes at its own bracket.** 40 lines
   of `runs-trace-b.rfc5424` whose event left `arch` empty carry a second
   structured data element with its own `arch` value after the record element,
   and 18 lines carry no record element at all. A reader that harvests
   `name="value"` pairs from the whole line takes the wrong `arch`, skips arch
   repairs and resolves those system calls on the wrong table.

10. (focal) **Two cost multipliers live only in the data.** SPEC section 9.1
    leaves the `cap_bounding_add` and `seccomp_rule_add` multipliers to the
    `cost-controls` group. On the shipped corpus two pairs reproduce every
    usable control, (2, 4) and (4, 1), and the cheaper shrunk plan keeps
    (4, 1), plan cost 739. One control repeats an identifier in a later shard
    with a total no pair satisfies (the first record stands) and one names an
    atom the catalogue does not carry (it is set aside).

11. (drift) **An artifact describing the settled state sits first in the
    delivery order.** `principal_registry.jsonl` carries `final_disposition`,
    which only the settled plan can supply.

12. (trap) **Five malformations are repairs, not rejections.** 2211 fields are
    malformed in the five documented ways. Dropping them loses rows from every
    artifact; ignoring them resolves the wrong system call or capability.

13. (trap) **The PAM walk has quiet branches.** Some runs are refused by a
    phase in which only an optional line speaks, so the phase answers that
    failure through the last branch of the phase result; 31 runs have a phase
    in which nothing speaks and are refused with `service_err`. Gated lines
    meet principals both below and exactly at the gate value, so whether a
    gated line is walked decides the deciding module in `pam_verdicts.csv`.

14. (trap) **First record wins for every other keyed group.**
    `pam-returns-c.ssv` repeats 60 keys that `pam-returns-a.jsonl` already
    answered, with a flipped code and the run in producer form. A reader that
    over-generalises the labels exception to last wins misjudges those phases.

15. (trap) **Hidden inputs the contract already covers.** Three variants of
    the unseen corpus, built only at grade time, exercise rules the shipped
    corpus states but does not happen to show:
    - line encoding: a byte order mark, CRLF endings, newlines inside quoted
      comma separated fields, and blank lines (empty or whitespace only, as the
      glossary fixes the term) between records of `.csv`, `.tsv` and `.fixed`
      shards. A reader that skips only empty lines turns a line of spaces into
      a record of empty fields;
    - every even numbered run records its audit event ahead of its exec event.
      The glossary and the SELinux appendix define the domain in force as the
      domain the exec event leaves the process in, and the audit event is
      judged against it wherever it sits; a replay that tracks the domain as it
      walks judges those audit events against the source domain;
    - one added cost control names a single `cap_bounding_add` atom twice, in
      producer and canonical form, with three times its base cost as total.
      A control names a set of atoms, so it pins that multiplier at three and
      leaves (3, 1) as the only consistent pair; a reader that sums the list
      as written finds no consistent pair.

    The unseen corpus itself also carries fixtures for rules the shipped
    corpus never has to apply: transition records that tie on rank (the rule
    identifier decides) and records ranked below the winner whose identifier
    sorts later (rank decides); two-permission access events, three of them a
    run's first refusal, listed in reverse alphabetical order; executable
    types missing execute and entrypoint, and others missing execute and
    transition; pam events recorded under another architecture than the exec
    event, exec events with an empty arch, and runs with every arch empty;
    PAM phases that succeed through the flag while an optional line fails, and
    phases with two failing required or two failing optional lines; two
    system calls on which two loaded filters each answer `KILL_PROCESS`
    through their own rule; a later-shard repeat of one key in each of six
    keyed groups (the first record stands); a `no` record for
    `CAP_AUDIT_WRITE` written first; and one system call table entry and one
    type the shipped corpus lacks. Its reduced shape drops the aarch64 runs,
    the capability atoms, the cost controls and every syscall event: both
    multipliers fall to one, the blocked system call artifact is its header
    alone, and the must_deny runs only a system call refused are admitted by
    the shipped policy, so every atom is forbidden, its witness is the
    canonically first must_deny run it alone admits, and the plan is empty.
    A variant check pays only when the
    solver is right on the plain unseen corpus for at least one artifact the
    variant moves, and then requires every artifact it gets right there to stay
    right on the variant.

## Load-bearing work

Read every file in the corpus directory, choose a reader by extension from the
thirteen encodings, and group records by the file stem up to the final hyphen.
Normalise once: identifiers to upper case with hyphens, type names to lower
case with underscores, capability names to the `CAP_` spelling whether they
arrived as a name, a lower case name or a decimal bit index, and text to NFC.

Build the event list for each run in `seq` order and apply the five repairs:
590 architecture repairs, 370 capability repairs, 588 number repairs, 68
permission repairs and 595 type repairs.

Replay each run event by event. The first refusal fixes the run's layer,
sequence and rule; later events are still walked for the per layer reports.

PAM: order the lines by rank, then module, then rule identifier. Skip a line
gated by `skip_if_uid_below=N` only when the uid is strictly below `N`. Take
each line's recorded code, defaulting to `ignore`, and walk with the five
control words. A phase with nothing spoken yields `service_err`.

SELinux: expand attributes on both sides of every allow record; 44 shipped
records name the `privileged` attribute as their source. At the `exec` event
pick the transition record with the lowest rank and require all three of
execute, entrypoint and transition. Judge each access and the audit event
against the domain in force. Dontaudit records decide nothing.

Capabilities: the permitted set is the union of the thread inheritable
intersected with the file inheritable, the file permitted intersected with the
bounding set (and with the thread permitted set under `no_new_privs`), and the
ambient set. The effective set is the permitted set when the effective bit is
set and the ambient set otherwise. `CAP_AUDIT_WRITE` is advisory.

Seccomp: resolve the number through the table for the event's architecture.
Each loaded filter answers with the strictest action among its matching rules,
earliest `idx` then lowest rule identifier on a tie, or its default when none
match, `ALLOW` for an undeclared filter. The strictest answer across filters
wins, and a default sorts before any rule on a tie. The five lethal actions
refuse; `ERRNO` refuses only a required call.

Then fix the multipliers from the cost controls, decide one atom at a time and
against the shipped policy alone which atoms admit a `must_deny` run (94 of
the 1200 do), and settle the plan in rounds, taking for each still refused run
the cheapest permissible atom by effective cost, not already chosen, that names
the refused target and moves the refusal later. Stop at the cap of eight
rounds. Shrink, which leaves 222 atoms with effective cost 739, and record for
each one the run that proves it necessary.

Measured on the shipped corpus before any atom: 186 runs admitted, 434 refused,
of which PAM 90, SELinux 186, capability 66 and seccomp 92. Labels: 146
`must_admit`, 84 `must_deny`, 390 `unlabelled`. After the plan: 323 admitted,
128 of the `must_admit` runs satisfied, all 84 `must_deny` runs still refused,
18 residual.

The corpus is 52 row files across thirteen encodings plus the specification,
five appendices and the glossary, so 59 files under `environment/data`; the
row files hold 40170 lines and 28033 records.

## Verification

Two channels read disjoint observables.

The deterministic tests (`tests/test_output.py`) compare each delivered
artifact byte for byte against the reference and, in the same check, the
artifact the delivered solver rebuilds on an unseen corpus; they also rerun the
solver on the shipped corpus, on the reduced shape of the unseen corpus and on
three variants of it, check the exit codes (including exit 3 for each of the
four needed groups stripped in turn), and parse the solver's source for a
hard coded corpus path and for imports. Thirty four checks: twenty nine
positive, summing to 85, and five negative controls, summing to minus 23.

```
weight   positive checks                                             subtotal
5        pam_verdicts, capability_ledger, domain_transitions,            40
         seccomp_decisions, denial_attribution, capability_gaps,
         audit_continuity, grant_plan
3        artifacts_written_by_delivered_solver, pam_stack_resolved,      36
         selinux_type_graph, seccomp_program, arch_dispatch,
         forbidden_atoms, minimality_witness, regenerates_on_reduced_corpus,
         contract_and_exit_codes, reads_encoding_features,
         audit_event_before_exec, cost_control_names_a_set
1        syscall_index, principal_registry, admission_ledger,             9
         blocked_syscalls, relaxation_atoms, iteration_trace,
         residual_denials, conservation, summary
                                                                         --
positive total, 29 checks                                                85
negative controls, 5 checks, four at minus 5 and one at minus 3        -23
```

`reward.toml` weights `test_output` at 0.5/85 and `judge` at 0.5/57.

The judged channel (`tests/judge.toml`) holds thirty three criteria, positive
weight 57 and negative minus 28. R1 to R6 are rules of engagement (R5 and R6
negative). R7 to R10 are four closing figures at weight 1. R11, R12 and R14 to
R16 are honesty negatives and R13 is a conduct negative. R17 judges whether the
delivered program replays runs through one shared function in its forbidding,
settling and witness passes. R18 to R33 are sixteen verification probes at
weight 3. The rubric reads the transcript, the final answer and the state of
`/app/out`; none of its observables is a file a test compares.

The four closing figures on the shipped corpus:

```
events the five repair rules corrected between them (R8)          2211
permissible atoms that repair no must_admit run (R7)              1033
mean effective cost of plan atoms, half to even (R9)              3.33
principals whose final disposition is granted (R10)                 70
```

Derivations. The repair figure adds the five repair counts,
`590 + 370 + 588 + 68 + 595`, an event two rules corrected counting once for
each. 1033 of the 1106 permissible atoms have `repairs_count` zero. The plan
holds no `cap_bounding_add` atom, so effective and base costs agree, and 739
over 222 is 3.3288, which rounds to 3.33. 70 of the 220 principals are
`granted`.

Measured with the bundle's own checks in a local reproduction of rewardkit,
test channel only: the oracle scores 85/85 and trips no negative control.

## Root cause

The difficulty is the interaction rather than the volume. Four real
enforcement layers resolve four different ways, none of them the way a first
reading suggests, and the output of each feeds the next. On top of them sits a
repair synthesis problem with a constraint that inverts the obvious search:
the cheapest atom naming the right object is frequently ruled out precisely
because it is broad, so the search has to establish what is forbidden before
it can choose anything, and the forbidden set is decided against a different
population than the one being repaired.

The dependency graph converts a single reading error into a whole file.
Seventeen of the twenty four artifacts sit three or more derivations deep,
grading is whole artifact, and the first artifact in the delivery order carries
a field only the last stage can supply.

## Solution shape

`solution/solve.py` is a standalone implementation of the contract, separate
from the reference the verifier embeds. Encoding readers keyed by extension
feed a `Policy` object that normalises every table once (types and attributes,
allow records, transitions by rank, the PAM stack and returns, units, binaries,
principals, the system call table, filters and defaults, atoms and controls).
A `State` object overlays a set of atoms on that policy, with one method per
layer. `build_runs` applies the five repairs; `replay` walks one run and
returns its first refusal, judging access and audit events against the domain
the exec event leaves; `build_scopes` limits each atom's single-atom replays to
the runs it can touch. `main` then rules out forbidden atoms, counts each
atom's repairs, settles and shrinks the plan once per consistent multiplier
pair (`multiplier_pairs` treats each control as a set of canonical atom
identifiers) and keeps the cheapest, finds the witnesses, writes the twenty
three data artifacts, the manifest over the bytes it wrote, and a byte copy of
itself as `lgactl.py`. It exits 2 on a wrong argument count or an absent
corpus and 3 when one of the four needed groups is empty.

On the shipped corpus, the unseen corpus, its reduced shape and the three
variants it writes the same bytes as the verifier's reference for all twenty
four artifacts, and it does on the shipped corpus with a shipped-admitted run
relabelled `must_deny` as well.

## Ordered plan

```
1  read and normalise every group; apply the five repairs
2  resolve the system call table and the PAM stack order
3  expand the type and attribute graph
4  settle each run's exec domain from the lowest ranked transition record
5  compute each run's capability sets
6  decide each recorded system call against the loaded filter stack
7  replay every run to its first refusal
8  rule out every atom that alone admits a must_deny run
9  fix the cost multipliers from the cost controls
10 settle the plan over rounds under the cap of eight, and shrink it
11 prove each surviving atom with a witness
12 emit the twenty three data artifacts, then the manifest over them
13 state the four closing figures
```

Steps 2 and 3 are independent of each other, as are steps 4 and 5 and steps 8
and 9; every other step needs the ones before it.

## Pitfalls

T1 precedence that is not source order: the lower ranked transition record
wins. Caught by `test_artifact_domain_transitions`.

T2 PAM lines ordered by rank, not by file order. Ranks never tie inside one
service and phase (the PAM appendix says so), so the module and rule
identifier keys of the ordering are never reached. Caught by
`test_artifact_pam_stack_resolved` and `test_artifact_pam_verdicts`.

T3 inclusive gate boundary: `skip_if_uid_below=N` walks at `N`. Caught by
`test_artifact_pam_verdicts`.

T4 the optional branch of the phase result. Caught by
`test_artifact_pam_verdicts` and `test_artifact_admission_ledger`.

T5 capability sets in three spellings, sometimes inside one field. Caught by
`test_artifact_capability_ledger`.

T6 a fixed point with a cap of eight. Caught by `test_artifact_iteration_trace`.

T7 comparison boundaries. `LT` against `LE`, `GT` against `GE`, `EQ` against
`NE`, and `MASKED_EQ` with the mask on the argument. Caught by
`test_artifact_seccomp_decisions` and `test_artifact_admission_ledger`.

T8 a condition on an argument the trace does not carry never matches. Caught
by `test_artifact_seccomp_decisions`.

T9 an empty group that still emits a row: the reduced unseen corpus has an
architecture with no events. Caught by `test_regenerates_on_reduced_corpus`.

T10 malformed input with a specified recovery. Caught by
`test_artifact_summary` and `test_artifact_arch_dispatch`, and by R8.

T11 the residual status depends on whether the cap was reached. The shipped
corpus reaches it; the reduced unseen corpus stops early with `unrepairable`
residuals. Caught by `test_artifact_residual_denials` and
`test_regenerates_on_reduced_corpus`.

T12 `arg_index` null against zero. Caught by `test_artifact_seccomp_program`.

T13 JSON object keys in stated order. Caught by every JSON artifact test.

T14 identifiers and type names canonicalise in opposite directions. Caught by
every artifact test.

T15 a column present and empty on most rows: `gated_uid`, `witness_run`.

T16 sort stability over a repeating key in the admission ledger.

T17 a header on some artifacts and none on others: domain transitions and
forbidden atoms carry none.

T18 a fixed width code: `nr_padded` is four wide.

T19 a signed quantity: `delta` is minus one when the bounding set dropped a
capability the binary offered. Caught by `test_artifact_capability_gaps`.

T20 a value defined by a later stage: `final_disposition`. Caught by
`test_artifact_principal_registry`.

T21 an ordering key computed in another artifact: `first_round` in the blocked
system call artifact. Caught by `test_artifact_blocked_syscalls`.

T22 ties between equally strict seccomp answers, across filters and inside one
filter. Caught by `test_artifact_seccomp_decisions`.

T23 the advisory capability used by runs that must not be refused for it.
Caught by `test_artifact_admission_ledger` and `test_artifact_capability_gaps`.

T24 source side attribute expansion of allow records. Caught by
`test_artifact_admission_ledger`.

T25 a filter no defaults record declares answers `ALLOW`. Caught by
`test_artifact_seccomp_decisions`.

T26 the refused target of an exec refusal is the executable type, and an atom
already chosen is not a candidate again. Caught by `test_artifact_grant_plan`
and `test_artifact_iteration_trace`.

T27 display names in NFC and NFD emitted in NFC. Caught by
`test_artifact_principal_registry`.

T28 labels last wins, notes to the end, the rfc5424 record element, and
pam-returns first wins (Defect 7, 8, 9 and 14). Caught by the plan, forbidden,
trace and witness artifacts and by `test_artifact_pam_verdicts`.

T29 the hidden cost multipliers (Defect 10). Caught by
`test_artifact_grant_plan`, `test_artifact_iteration_trace` and
`test_artifact_conservation`.

T30 the three hidden variants (Defect 15). Caught by
`test_reads_encoding_features`, `test_audit_event_before_exec` and
`test_cost_control_names_a_set`, each charging only artifacts the solver gets
right on the plain unseen corpus.

## Provenance

```yaml
uuid: 0b27b9dc-7985-54f1-a120-46e6810315a3
instance_id: 0b27b9dc-7985-54f1-a120-46e6810315a3
task_name: terminal-bench/0b27b9dc-7985-54f1-a120-46e6810315a3
language: python
category: Security
solve_py_sha256: 05e77d8a65313f6a786480cfdb78a5b290e206cd188676d59e9e5cdf085c348c
solve_py_lines: 2023
spec_sha256: a1992985c3df41494416030f5097af7e01d91ba36b2bde96d6d7299804c776af
corpus_files: 59
corpus_row_files: 52
corpus_row_lines: 40170
corpus_records: 28033
corpus_formats: 13
declared_artifacts: 25
positive_total: 85
negative_total: -23
rubric_positive_total: 57
rubric_negative_total: -28
```

An oracle or test-only run exercises the deterministic `test_output` channel
alone, which `tests/reward.toml` weights at 0.5, so the highest combined reward
such a run can report is 0.5; the judged channel is reached only when a model
is run under a judge. harbor 0.24.0 writes each trial's reward to
`/logs/verifier/reward.json`.

Verifier concurrency: rewardkit runs criteria on parallel threads, and every
check shares the module-level corpus, expected-artifact and solver-run caches,
so `_pass` holds one module-level `threading.Lock` and the checks run one at a
time. Scoring is unchanged.
