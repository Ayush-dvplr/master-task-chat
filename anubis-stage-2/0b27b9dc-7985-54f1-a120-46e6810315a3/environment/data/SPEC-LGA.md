# SPEC-LGA: least grant admission control, version 4.2

This is the governing contract for the LGA confinement control plane. It is
authoritative and complete. Every definition, constant, boundary, encoding and
output shape the work depends on is stated here or in one of the five
appendices this file names. Where an engineer's instinct and this file
disagree, this file wins, including where the rule it states is not the rule a
reasonable engineer would have chosen.

The five appendices are `lga-pam-appendix.md`, `lga-selinux-appendix.md`,
`lga-capability-appendix.md`, `lga-seccomp-appendix.md` and
`lga-encodings-appendix.md`. `lga-glossary.md` fixes the meaning of the terms
this file uses as terms of art. All six sit beside this file in the corpus
directory and all six are part of the contract.

## 1. What LGA does

A privileged binary at `/usr/local/bin/vault_admin` runs under four independent
enforcement layers: a PAM stack that authenticates the principal, an SELinux
type enforcement policy that labels and confines the process, a Linux
capability regime that bounds what the process may ask the kernel for, and a
stack of seccomp filters that decides which system calls the process may
issue.

The site has recorded a population of runs. Each recorded run is an ordered
list of events. Replaying a run against the shipped policy tells you whether
that run would be admitted, and if it would be refused, which layer refused it
and at which event.

The site also carries a catalogue of grant atoms. An atom is one named,
bounded relaxation of the policy. The work is to decide, for the population as
a whole, the least set of atoms that admits every run the site marks
`must_admit` while leaving every run the site marks `must_deny` refused, and to
show that no smaller set would do.

## 2. Identifiers and canonical form

Identifiers arrive in the corpus in a producer form, or already in canonical
form, and are emitted in a canonical form. The canonical form of an identifier is the producer form
upper cased with every underscore and every full stop replaced by a hyphen.
So `run_00042` is emitted as `RUN-00042`, `atm_0007` as `ATM-0007`, `pam_0015`
as `PAM-0015`, `flt_0003` as `FLT-0003`, `unit_0620` as `UNIT-0620`,
`bin_0620` as `BIN-0620`, `prn_0031` as `PRN-0031`, `te_0088` as `TE-0088`,
`tr_0311` as `TR-0311`, `da_0402` as `DA-0402`, `sec_0900` as `SEC-0900`,
`op_0044` as `OP-0044` and `aud_0021` as `AUD-0021`. Canonical identifiers are
what every artifact carries and what every ordering rule sorts on.

Type names are different. An SELinux type name is canonicalised by lower
casing it and replacing every hyphen and every full stop with an underscore, so
`VAULT_017_EXEC_T`, `vault-017-exec-t` and `vault_017_exec_t` are the same
type. Type names are emitted in that lower form, never in the identifier form.

Capability names are canonicalised to the upper case `CAP_` spelling. A
capability may arrive as that spelling, as its lower case form, or as the
decimal index of its bit. The bit order is the order the capability table in
`lga-capability-appendix.md` lists, counting from zero, so `0` is `CAP_CHOWN`
and `29` is `CAP_AUDIT_WRITE`.

Text is normalised to Unicode NFC before it is compared or emitted. The corpus
carries principal display names in both NFC and NFD, and two names that differ
only in normalisation form are the same name. Every file this work writes is
UTF-8 with no byte order mark and with a single newline character ending every
line, including the last.

Integers are emitted without a decimal point and without leading zeros, except
where a field is documented as a fixed width code, in which case it carries the
leading zeros the width requires.

## 3. The corpus

The corpus directory holds flat files only. A file's group is its stem up to
and including the character before the final hyphen, so `runs-trace-a.jsonl`,
`runs-trace-b.rfc5424` and `runs-trace-c.logfmt` are three shards of the group
`runs-trace`. A group's records are the concatenation of its shards, and the
order in which shards or records are read never changes any answer this work
produces.

A file's extension names its encoding. The thirteen encodings and the exact
rules for reading each of them are in `lga-encodings-appendix.md`.

The groups and their fields are these.

`principals` carries `principal_id`, `uid`, `login`, `display`, `groups`,
`inh_thread` and `perm_thread`. `groups` is a vertical bar separated list.
`inh_thread` and `perm_thread` are capability sets written as a plus separated
list, or the word `none` for the empty set.

`pam-stack` carries `rule_id`, `service`, `phase`, `rank`, `control`, `module`
and `flags`. `phase` is one of `auth`, `account`, `session`. `control` is one
of `required`, `requisite`, `sufficient`, `optional`, `binding`.

`pam-returns` carries `run_id`, `phase`, `module` and `code`.

`selinux-types` carries `type_name`, `attributes`, `is_domain` and `note`.
`attributes` is a vertical bar separated list.

`selinux-allow` carries `rule_id`, `source`, `target`, `tclass` and `perms`.
`perms` is a comma separated list.

`selinux-transition` carries `rule_id`, `source`, `exec_type`, `new_domain`
and `rank`.

`selinux-dontaudit` carries `rule_id`, `source`, `target`, `tclass`, `perms`
and `note`.

`cap-units` carries `unit_id`, `unit_name`, `bounding`, `ambient`,
`no_new_privs` and `filters`. `filters` is a vertical bar separated list of
filter identifiers.

`cap-filecaps` carries `binary_id`, `path`, `permitted_file`,
`inheritable_file` and `effective_bit`.

`cap-required` carries `op_id`, `operation`, `capability`, `advisory` and
`note`.

`seccomp-filters` carries `rule_id`, `filter_id`, `idx`, `arch`, `syscall`,
`arg_index`, `op`, `value`, `mask` and `action`.

`seccomp-defaults` carries `filter_id`, `default_action` and `priority`.

`arch-syscalls` carries `arch`, `nr`, `syscall` and `note`.

`runs-trace` carries `run_id`, `seq`, `kind`, `principal`, `service`, `unit`,
`binary`, `source_domain`, `exec_type`, `arch`, `phase`, `syscall_nr`, `arg0`,
`capability`, `tclass`, `perm`, `target_type` and `required`.

`runs-labels` carries `run_id`, `label` and `note`. `label` is one of
`must_admit`, `must_deny`, `unlabelled`.

`grant-atoms` carries `atom_id`, `layer`, `kind`, `cost` and `target`.

`audit-events` carries `event_id`, `run_id`, `ts`, `action` and `principal`.

`cost-controls` carries `control_id`, `atoms`, `total` and `note`. `atoms` names
a set of atom identifiers, written as a vertical bar separated list, and
`total` is a whole number.
Section 9.1 says what a control is for.

Where a record's identity key repeats across the corpus, the first record read
in canonical shard order wins and later records with the same key are ignored.
Canonical shard order is the ascending order of the shard file names compared
as text, and inside one shard the order its records are written in. Identity
keys are compared in canonical form, so `run_00042` and `RUN-00042` are one
key. The identity key is `principal_id` for principals, the triple of `run_id`,
`phase` and `module` for PAM returns, `unit_id` for units, `binary_id` for
binaries, `filter_id` for filter defaults, the pair of `arch` and `nr` for the
system call table, `run_id` for labels, `atom_id` for atoms and `control_id`
for cost controls.

The `runs-labels` group is the one exception to the first record rule. Its
shards are successive relabelling batches, so when a run is labelled in more
than one shard the record read last in canonical shard order wins and the
earlier ones are superseded. A run is never labelled twice inside one shard.

A filter identifier a unit names that no `seccomp-defaults` record declares has
the default action `ALLOW`.

## 4. Runs and events

A run is the set of `runs-trace` records sharing a `run_id`, ordered by `seq`
ascending. `seq` starts at one and has no gaps inside a run.

The `kind` of an event is one of `pam`, `exec`, `access`, `capuse`, `syscall`
and `audit`. A run carries exactly one `exec` event and exactly one `audit`
event. It carries one `pam` event per phase, in the phase order `auth`,
`account`, `session`. It carries zero or more `access`, `capuse` and `syscall`
events.

A run's dispatch architecture is the `arch` field of its `exec` event. If that
field is empty, the dispatch architecture is the `arch` field of the lowest
numbered event in the run that carries a non empty one. If no event carries
one, the dispatch architecture is `x86_64`.

The run's principal, service, unit, binary, source domain and executable type
are read from its lowest numbered event.

## 5. Repairs

Five malformations appear in the recorded trace. Each has a stated repair and
each repair is applied before the run is replayed. None of them is a reason to
reject a record.

An empty `arch` field on any event other than the `exec` event is repaired to
the run's dispatch architecture.

A `capability` field written in lower case or as a decimal bit index is
repaired to the canonical capability name.

A `perm` field holding two permission names separated by a comma means the
event requires both of them. Every permission listed must be allowed for the
event to pass.

A `syscall_nr` field carrying a `0x` prefix is hexadecimal. A `syscall_nr`
field carrying leading zeros is decimal and the zeros are padding, not part of
the value.

A `target_type` field written in upper case or with hyphens in place of
underscores is repaired to the canonical type name.

The count of events repaired by each of these five rules is a figure the
closing summary reports.

## 6. The four layers

A run is replayed by walking its events in `seq` order. Each event is offered
to the layer that owns its kind. The first event any layer refuses decides the
run: the run is `denied`, the refusing layer is the run's layer, the event's
`seq` is the run's sequence, and the rule the layer names is the run's rule.
A run no layer refuses is `admitted`, and its layer, sequence and rule are the
literal `NONE`, zero and the literal `NONE`; where a reason is reported for it,
the reason is the literal `admitted`.

The layers and the event kinds they own are: PAM owns `pam`; SELinux owns
`exec` and `access`; the capability regime owns `capuse`; seccomp owns
`syscall`. An `audit` event is never refused and never decides a run; it feeds
the audit continuity report in section 11.

The layer ranking used by the ordering rules is PAM one, SELinux two,
capability three, seccomp four, and `NONE` nine.

### 6.1 PAM

`lga-pam-appendix.md` states the stack walk in full. In outline: the lines of
the stack for the run's service and the event's phase are ordered by `rank`
ascending, then by `module`, then by `rule_id`. A line whose `flags` carry
`skip_if_uid_below=N` is skipped when the principal's `uid` is strictly less
than `N`; a principal whose `uid` equals `N` is not skipped. Each surviving
line takes the return code recorded for the run, the phase and that line's
module, and a line with no recorded code returns `ignore`.

The walk then applies the control semantics in the appendix and yields one code
for the phase. A phase whose code is not `success` refuses the run, the reason
is the string `pam_` followed by that code, and the rule is the `rule_id` of
the line that produced the code.

### 6.2 SELinux

`lga-selinux-appendix.md` states the type enforcement algebra in full. In
outline: an allow record whose `source` or `target` names an attribute rather
than a type applies to every type carrying that attribute. A `dontaudit`
record never grants and never refuses; it is advisory and is recorded rather
than acted on.

At the `exec` event the transition records for the pair of source domain and
executable type are ordered by `rank` ascending then by `rule_id`, and the
first of them is the chosen record. Source order is not the ordering; rank is.
If there is no such record the process keeps its source domain and the event is
not refused. If there is one, naming a landing domain, the transition happens
only when all three of these hold: the source domain may `execute` the
executable type as a `file`, the landing domain may `entrypoint` the executable
type as a `file`, and the source domain may `transition` to the landing domain
as a `process`. When one or more of the three is absent the event is refused,
the reason is `te_missing_` followed by the alphabetically first of the missing
three, and the rule is the chosen transition record. The process then keeps its
source domain.

At an `access` event every permission the event names must be allowed for the
domain in force against the event's target type in the event's class. When one
or more is absent the event is refused, the reason is `te_denied_` followed by
the alphabetically first missing permission, and the rule is the literal
`NONE`.

### 6.3 Capabilities

`lga-capability-appendix.md` states the capability algebra in full. In outline,
with `B` the unit's bounding set, `A` the unit's ambient set, `Fp` and `Fi` the
binary's file permitted and file inheritable sets, `Ti` and `Tp` the
principal's thread inheritable and thread permitted sets, and `E` the binary's
effective bit:

```
from_file = (Fp and B)                      when no_new_privs is false
from_file = (Fp and B and Tp)               when no_new_privs is true
permitted = (Ti and Fi) or from_file or A
effective = permitted                       when the effective bit is 1
effective = A                               when the effective bit is 0
```

`and` and `or` are set intersection and set union.

A `capuse` event names one capability. The event is refused when that
capability is outside the effective set, the reason is `cap_absent` and the
rule is the capability name. A capability that the `cap-required` group marks
advisory is the exception: its absence never refuses an event. It is recorded
in the audit continuity report instead.

### 6.4 Seccomp

`lga-seccomp-appendix.md` states the filter algebra in full. In outline: the
filters loaded for a run are the ones its unit names. A `syscall` event carries
an architecture and a number. The number is resolved to a name through the
system call table for that architecture. A number with no entry for that
architecture refuses the event with reason `seccomp_kill_process` and rule
`NONE`.

Each loaded filter decides on its own. Inside one filter, every rule whose
architecture and system call name match the event is a candidate; a rule that
also names an argument index matches only when that index is zero and the
comparison the rule states holds against the event's `arg0`. The filter's
answer is the strictest action among its matching rules, or its default action
when none match. The action the kernel returns is the strictest answer across
the loaded filters, and a run whose unit names no filter is allowed.

The strictness order, strictest first, is `KILL_PROCESS`, `KILL_THREAD`,
`TRAP`, `ERRNO`, `USER_NOTIF`, `TRACE`, `LOG`, `ALLOW`. The rank of an action
is its position in that list counting from one.

An action of `KILL_PROCESS`, `KILL_THREAD`, `TRAP`, `USER_NOTIF` or `TRACE`
refuses the event. An action of `ERRNO` refuses the event when the event's
`required` field is `yes` and does not refuse it otherwise. `LOG` and `ALLOW`
never refuse. The reason for a refused event is the string `seccomp_` followed
by the action lower cased, and the rule is the `rule_id` of the rule that
produced the action, or the literal `NONE` when the default produced it. When
more than one loaded filter returns the same strictest action, or more than
one rule inside one filter ties for it, the appendix fixes which rule is named.

## 7. Grant atoms

An atom names one bounded relaxation. Its `target` is a semicolon separated
list of `key=value` elements. An element whose key is `note` is commentary and
changes nothing. A `note` element is always the last element of a target, and
its value runs to the end of the string: a semicolon or an equals sign after
`note=` belongs to the note and starts no element of its own. An element value
that names an identifier, a type or a capability may arrive in any of the forms
section 2 accepts and is read in canonical form. The seven kinds and the elements each carries are these.

`pam_control_relax` carries `rule`. The named stack line behaves as though its
control were `sufficient`.

`te_allow_add` carries `source`, `target`, `class` and `perm`. The named
permission is allowed. When the `target` element names an attribute, the
permission is allowed against every type carrying that attribute.

`cap_bounding_add` carries `unit` and `cap`. The named capability joins that
unit's bounding set.

`cap_ambient_add` carries `unit` and `cap`. The named capability joins that
unit's ambient set and its bounding set.

`seccomp_rule_add` carries `filter`, `arch` and `syscall`. That filter answers
`ALLOW` for that system call on that architecture, whatever rules it holds.

`seccomp_default_relax` carries `filter`. That filter's default action becomes
`ALLOW`. Its rules are unaffected, so a rule that matches still decides.

`filter_unload` carries `filter`. That filter leaves every unit's loaded set.

Every kind is relaxing: applying an atom never turns an admitted run into a
denied one, and never moves a denied run's refusal earlier.

## 8. Forbidden and permissible atoms

An atom is **forbidden** when applying that atom alone, with no other atom,
admits at least one run labelled `must_deny`. The witness for a forbidden atom
is the canonically first such run. Every other atom is **permissible**.

Forbidding is decided atom by atom against the shipped policy. It is not
decided against the plan, and an atom is never forbidden because of what some
other atom does.

## 9. The grant plan

The plan is built in rounds. The state carried between rounds is a set of
chosen atoms, which starts empty.

A round begins by replaying every run labelled `must_admit` under the atoms
chosen so far and collecting, in canonical run order, those still denied. When
that collection is empty the rounds stop.

For each still denied run, in canonical run order, the **candidate atoms** are
the permissible atoms that satisfy all of these: the atom's layer equals the
layer that refused the run; when that layer is capability, the atom's `unit`
element equals the run's unit and its `cap` element equals the refused
capability; when that layer is seccomp, the atom's `filter` element names a
filter the run's unit loads, and if the atom is a `seccomp_rule_add` its `arch`
and `syscall` elements equal the event's architecture and resolved name; when
that layer is PAM, the atom's `rule` element equals the rule the refusal named;
and when that layer is SELinux, the atom's `source` element is either the run's
source domain or its landing domain, and for a `te_allow_add` the atom's
`target` element either equals the refused target or names an attribute that
target carries. The refused target is the `target_type` field of the refused
event, after repair: for an `access` event the type the event named, and for
an `exec` event the executable type, whichever of the three permissions of
the transition triple was missing. An atom already in the chosen set is not a
candidate; a run whose only atoms naming the refused target are already chosen
has no candidate this round.

A candidate is **effective** for that run when adding it to the chosen set
either admits the run or moves the run's refusal to a `seq` strictly later than
the one the round's opening replay recorded for that run. That opening `seq` is
the baseline for the whole round: a run keeps it even when an atom chosen
earlier in the same round for another run has already admitted it, so the run
is still offered an atom of its own.
The round chooses, from the effective candidates, the one with the least
effective cost (section 9.1),
and among equal costs the canonically first atom identifier. The chosen atom
joins the set. A run with no effective candidate is left alone this round.

Rounds stop when no `must_admit` run is still denied, or when a round chooses
no atom, or when eight rounds have run, whichever comes first. Eight is the
cap.

The set is then **shrunk**. Taking the chosen atoms in reverse canonical order,
an atom is dropped when dropping it leaves every `must_admit` run that the full
set admitted still admitted. The shrunk set is the grant plan. Its ordering in
the delivered artifact is by round ascending, then effective cost ascending
(section 9.1), then atom identifier; an atom that survives the shrink carries the round in which it was
first chosen.

A run labelled `must_admit` that the plan does not admit is a **residual**. Its
status is `nonconvergent` when the rounds reached the cap of eight, and
`unrepairable` when they stopped earlier.

### 9.1 Effective cost

An atom's `cost` field is its base cost. Its **effective cost** is its base
cost times the multiplier of its kind. Five kinds have the multiplier one. The
multipliers of `cap_bounding_add` and of `seccomp_rule_add` are whole numbers
from one to four that this specification does not state; the corpus fixes
them through the `cost-controls` group.

A control names a set of atoms and gives in `total` the sum of their effective
costs. A control is usable when every atom it names is in the catalogue; a
control naming any other atom is set aside. A pair of multipliers, written as
the `cap_bounding_add` multiplier then the `seccomp_rule_add` multiplier, is
consistent when it reproduces the total of every usable control. When no
control is usable both multipliers are one. When exactly one pair is
consistent, that pair is used. When more than one is consistent, the plan of
section 9 is settled and shrunk once under each consistent pair, and the pair
kept is the one whose shrunk plan has the least total effective cost, then the
smaller `cap_bounding_add` multiplier, then the smaller `seccomp_rule_add`
multiplier. Forbidding (section 8) and the shrink do not depend on cost, so
only the choices inside the rounds move with the pair.

Effective cost is what a round compares when it chooses among effective
candidates, what `cost_added` and `plan_cost` sum, what the plan ordering sorts
on, and what the closing figures over plan atom costs read. Every `cost` column
in a delivered artifact carries the base cost.

## 10. Minimality

For each atom in the plan, the **witness** is the canonically first
`must_admit` run that the plan admits and that the plan without that one atom
denies, together with the layer and sequence at which that run is then refused.
An atom the shrink left in the plan always has a witness, and the witness is
the proof that the plan holds no atom it could do without.

A witness is written as the run, the layer and the sequence. When no such run
exists the witness run and layer are the literal `NONE` and the witness
sequence is zero.

## 11. Audit continuity

`CAP_AUDIT_WRITE` is the capability the `cap-required` group marks advisory.
For each run, audit continuity is intact when both of these hold under the
shipped policy: `CAP_AUDIT_WRITE` is inside the run's effective set, and every
permission the run's `audit` event names is allowed for the domain in force
against that event's target type in that event's class. Otherwise continuity is
broken, and the break reason is `capability` when the capability is outside the
effective set and `access` when the capability is present and the access is
not. A run whose continuity is intact carries the empty string as its break
reason. The capability is tested first, so a run failing both reports
`capability`.

## 12. What the layers report before any atom is applied

Every artifact in section 13 describes the **shipped** policy, before any atom
is applied, except these seven, which describe the state after the plan is
built: the grant plan, the iteration trace, the minimality witnesses, the
residual denials, the conservation record, the `atom_kind_counts` field of the
summary record and the `final_disposition` field of the principal registry.
Every other field of the summary record, `layer_counts` included, describes
the shipped policy, and the conservation record's `admitted_initial` and
`denied_initial` describe the shipped policy as their names say.

## 13. The delivered artifacts

Twenty five artifacts are delivered. Twenty four are data. The twenty fifth is
the program that produced them.

Every delimited artifact ends with a newline. Where a header is stated it is
the first line. Where no header is stated none is written. Comma separated
artifacts quote a field that holds a comma, a double quote or a newline, and
double a quote inside a quoted field. Tab separated artifacts never quote; they
write a backslash followed by `t` for a tab, a backslash followed by `n` for a
newline and two backslashes for a backslash. JSON is written compact, with no
space after a comma or a colon, and with object keys in the order this section
states rather than sorted. A character outside ASCII is written as itself in
UTF-8, never as a `\u` escape. A JSON lines artifact writes one object per
line, and one with no rows is an empty file of zero bytes.

`/app/out/principal_registry.jsonl` holds one object per principal that appears
in at least one run, ordered by canonical principal identifier. Keys in order:
`principal_id`, `uid`, `login`, `display`, `groups`, `inheritable`,
`permitted`, `run_count`, `final_disposition`. `groups` is a list sorted
ascending. `inheritable` and `permitted` are lists of canonical capability
names sorted by bit index. `run_count` counts the runs the principal appears
in. `final_disposition` is `residual` when any of the principal's runs is a
residual, otherwise `granted` when any of its runs is denied under the shipped
policy and admitted under the plan, otherwise `admitted` when all of its runs
are admitted under the shipped policy, otherwise `denied`. The four tests are
applied in that order.

`/app/out/syscall_index.tsv` holds a header `arch`, `nr`, `syscall`,
`nr_padded` and one row per entry of the system call table, ordered by
architecture ascending then number ascending. `nr_padded` is the number as a
four character fixed width code with leading zeros.

`/app/out/pam_stack_resolved.csv` holds a header `service`, `phase`,
`position`, `rank`, `control`, `module`, `rule_id`, `gated_uid` and one row per
stack line, ordered by service ascending, then by phase in the order `auth`,
`account`, `session`, then by the stack ordering of section 6.1. `position`
counts from one inside each service and phase. `gated_uid` is the number from a
`skip_if_uid_below` flag, or the empty string when the line carries no such
flag. The column is always written.

`/app/out/selinux_type_graph.json` holds one object with keys in this order:
`types`, `attributes`, `domains`, `file_types`. `types` maps every type name to
its attribute list sorted ascending, with the type names in ascending order.
`attributes` maps every attribute to the sorted list of types carrying it, with
the attribute names in ascending order. `domains` is the sorted list of types
carrying the `domain` attribute. `file_types` is the sorted list of the rest.

`/app/out/seccomp_program.jsonl` holds one object per filter rule, ordered by
filter identifier ascending, then by `idx` ascending, then by rule identifier.
Keys in order: `rule_id`, `filter_id`, `idx`, `arch`, `syscall`, `nr`,
`arg_index`, `op`, `value`, `mask`, `action`, `action_rank`. `nr` is the lowest
number the rule's architecture maps to the rule's system call name, or null
when that architecture maps no number to it. `arg_index` is null when the rule
names no argument index, and the number when it does; zero and null are
different values and mean different things. `value` and `mask` are numbers,
zero when the field is empty.

`/app/out/pam_verdicts.csv` holds a header `run_id`, `phase`, `result`,
`deciding_rule`, `deciding_module` and one row per run and phase, ordered by
canonical run identifier then by phase in the order `auth`, `account`,
`session`. `deciding_rule` carries the literal `NONE` whenever the phase yields
`success`. `deciding_module` carries the module of the `sufficient` or
`binding` line that ended the walk with `success`, and the literal `NONE` when
the phase yields `success` because the flag was set or yields `service_err`
with no deciding line; `lga-pam-appendix.md` states which line decides.

`/app/out/capability_ledger.csv` holds a header `run_id`, `unit`, `binary`,
`nnp`, `bounding_count`, `ambient_count`, `permitted`, `effective` and one row
per run, ordered by canonical run identifier. `nnp` is `yes` or `no`. The two
counts are set sizes. `permitted` and `effective` are plus separated lists of
canonical capability names sorted by bit index, or the literal `NONE` for an
empty set.

`/app/out/domain_transitions.tsv` holds no header and one row per run, ordered
by canonical run identifier, with the columns `run_id`, `source_domain`,
`exec_type`, `transition_rule`, `new_domain`, `execute_ok`, `entrypoint_ok`,
`transition_ok`. `transition_rule` is the literal `NONE` when no transition
record matched. `new_domain` is the domain in force after the event. The three
flags are `yes` or `no` and are `yes` when no transition record matched.

`/app/out/seccomp_decisions.jsonl` holds one object per `syscall` event,
ordered by canonical run identifier then by `seq`. Keys in order: `run_id`,
`seq`, `arch`, `nr`, `syscall`, `action`, `rule_id`, `matched_count`, `denies`.
`syscall` is the literal `NONE` when the number resolves to no name.
`matched_count` counts the rules that matched across every loaded filter.
`denies` is a boolean.

`/app/out/arch_dispatch.tsv` holds a header `arch`, `event_count`, `run_count`,
`unknown_count`, `repaired_count` and exactly three rows, one for each of
`x86_64`, `i386` and `aarch64` in that order. An architecture with no events
still carries a row, with zeros. `event_count` counts `syscall` events
dispatched under that architecture, `run_count` counts runs whose dispatch
architecture it is, `unknown_count` counts `syscall` events under it whose
number resolved to no name, and `repaired_count` counts events whose empty
`arch` field was repaired to it.

`/app/out/admission_ledger.csv` holds a header `run_id`, `label`, `verdict`,
`layer`, `seq`, `rule_id`, `reason` and one row per run. `verdict` is
`admitted` or `denied`. `label` is the run's label under section 3, or `unlabelled` when the
corpus carries none. An admitted run carries `NONE`, `0`, `NONE` and
`admitted` in the last four columns. The rows are ordered by layer rank ascending then by `seq`
ascending, and rows that tie on both keep canonical run order.

`/app/out/denial_attribution.jsonl` holds one object per run denied under the
shipped policy, ordered by canonical run identifier. Keys in order: `run_id`,
`layer`, `seq`, `rule_id`, `reason`, `detail`. `detail` is a human sentence
naming the refused thing: for PAM it is `pam ` then the service then ` phase `
then the phase then ` rule ` then the rule; for SELinux it is `allow ` then the
run's source domain then a space then the target type then ` : ` then the class then
` { ` then the comma separated permissions then ` }`; for the capability layer
it is `capability ` then the capability then ` absent from the effective set`;
and for seccomp it is `seccomp ` then the reason then ` on ` then the
architecture then ` nr ` then the system call number after the repair of
section 5, written in decimal without padding.

`/app/out/blocked_syscalls.tsv` holds a header `arch`, `syscall`,
`block_count`, `first_round`, `worst_action` and one row for each pair of
architecture and system call name that at least one `syscall` event was refused
on under the shipped policy. An event whose number resolved to no name
contributes under the name `NONE`. `block_count` counts those events.
`worst_action` is the strictest action seen for that pair. `first_round` is the
smallest `round` of the grant plan's atoms (the shrunk set, as `grant_plan.csv`
reports them) whose `arch` and `syscall` elements equal that pair, and zero
when no atom of the grant plan matches; an atom a round chose and the shrink
dropped does not count. The rows are ordered by
`first_round` ascending, then architecture ascending, then system call name
ascending.

`/app/out/capability_gaps.csv` holds a header `run_id`, `capability`, `unit`,
`in_bounding`, `in_permitted`, `delta` and one row for each `capuse` event
whose capability is outside the effective set, including events whose
capability is advisory. The rows are ordered by canonical run identifier then
by capability name. `in_bounding` and `in_permitted` are `yes` or `no` and
report membership of the unit's bounding set and of the permitted set. `delta`
is the whole number minus one when the capability is inside the binary's file
permitted set, meaning the bounding set dropped it, and plus one when it is
outside, meaning nothing offered it.

`/app/out/audit_continuity.jsonl` holds one object per run, ordered by
canonical run identifier. Keys in order: `run_id`, `audit_capability`,
`audit_access`, `continuity`, `break_reason`. The first two are booleans.
`continuity` is `intact` or `broken`. `break_reason` is `capability`, `access`
or the empty string.

`/app/out/relaxation_atoms.csv` holds a header `atom_id`, `layer`, `kind`,
`cost`, `target`, `repairs_count`, `forbidden`, `witness_run` and one row per
atom in the catalogue, ordered by canonical atom identifier. `target` is the
atom's target string as the corpus carries it. `repairs_count` counts the runs
labelled `must_admit`, refused at that atom's layer, that the atom alone
admits. `forbidden` is `yes` or `no`. `witness_run` is the forbidden witness of
section 8, or the empty string for a permissible atom. The column is always
written.

`/app/out/forbidden_atoms.tsv` holds no header and one row per forbidden atom,
ordered by canonical atom identifier, with the columns `atom_id`, `layer`,
`kind`, `cost`, `admitted_run`.

`/app/out/grant_plan.csv` holds a header `atom_id`, `layer`, `kind`, `cost`,
`round`, `target` and one row per atom in the plan, in the plan ordering of
section 9.

`/app/out/iteration_trace.jsonl` holds one object per round that ran, in round
order. Keys in order: `round`, `denied_before`, `denied_after`, `atoms_added`,
`cost_added`. `atoms_added` is the sorted list of atom identifiers the round
chose; because a chosen atom is never a candidate again, no atom appears in
more than one round.
`denied_before` counts the `must_admit` runs the round found denied and
`denied_after` counts those still denied when the round ended. `cost_added` is
the total cost of the atoms the round chose.

`/app/out/minimality_witness.csv` holds a header `atom_id`, `witness_run`,
`witness_layer`, `witness_seq` and one row per atom in the plan, ordered by
canonical atom identifier.

`/app/out/residual_denials.tsv` holds a header `run_id`, `label`, `status`,
`rounds_used`, `last_layer` and one row per residual, ordered by canonical run
identifier. `rounds_used` is the number of rounds that ran. `last_layer` is the
layer that still refuses the run under the plan.

`/app/out/conservation.json` holds one object with keys in this order:
`total_runs`, `admitted_initial`, `denied_initial`, `admitted_final`,
`must_admit_total`, `must_admit_satisfied`, `must_deny_total`,
`must_deny_held`, `residual_count`, `plan_cost`, `plan_size`, `rounds_used`.
`admitted_final` counts the runs the plan admits, over the whole population and
not only the labelled part. `must_deny_held` counts the `must_deny` runs the
plan still refuses.

`/app/out/summary.json` holds one object with keys in this order:
`layer_counts`, `label_counts`, `arch_runs`, `repair_counts`,
`atom_kind_counts`, `blocked_syscall_rows`, `capability_gap_rows`,
`audit_broken_runs`, `forbidden_atom_rows`. `layer_counts` maps each layer that
decided at least one run, including `NONE`, to the count of runs it decided,
with the keys in ascending order. `label_counts` maps each label to its run
count with the keys in ascending order. `arch_runs` maps each of the three
architectures, in the order `x86_64`, `i386`, `aarch64`, to the count of runs
dispatched under it. `repair_counts` maps each of the five repair names `arch`,
`capability`, `number`, `perm`, `type` in ascending order to the count of
events it repaired. `atom_kind_counts` maps each atom kind present in the plan
to its count, keys ascending. The last four are whole numbers:
the row count of the blocked system call artifact excluding its header, the row
count of the capability gap artifact excluding its header, the count of runs
whose audit continuity is broken, and the count of forbidden atoms.

`/app/out/manifest.json` holds one object whose keys are the names of the other
twenty three data artifacts, in the order this section lists them, each mapping
to an object with keys in this order: `bytes`, `lines`, `sha256`. `bytes` is
the length of the artifact in bytes as written. `lines` is the number of
newline characters in it. `sha256` is the lower case hexadecimal SHA-256 digest
of its bytes.

`/app/out/lgactl.py` is the program itself, written as it was run.

## 14. The command contract

The program is run as `lgactl.py CORPUS_DIR OUT_DIR`. It reads only the record
files of the corpus directory it is given; the specification, its appendices
and the glossary are written for the engineer, and a corpus the program is
handed need not carry them. It reads nothing else, writes only into the
output directory it is given, uses only the Python standard library, and
reaches no network host. Given the same
corpus it writes the same bytes every time. Given a corpus whose records are
listed in a different order it writes the same bytes, because every ordering
this specification states is imposed by the program and never inherited from
the input.

It exits zero when it has written every artifact, exits two when it is called
with the wrong number of arguments or the corpus directory is absent, and exits
three when the corpus is present but a group it needs is empty. The groups it
needs are `runs-trace`, `selinux-allow`, `cap-units` and `grant-atoms`. It finishes
one corpus of the size the site records inside five minutes on ordinary
hardware; a program that takes longer than that on one corpus is not finished.

## 15. The closing figures

Beyond the artifacts, the work reports a set of closing figures. Each is a
derivation over the artifacts rather than a field of one, and each is stated
by name and value in the written summary that ends the work. No figure here
is a field of an artifact: every one has to be worked out across rows, so
reading a number straight out of a delivered file never answers one of them.
They are the total number of events the five repair rules corrected between
them (the sum of the five repair counts, so an event two rules corrected
counts once for each), the count of permissible atoms that repair no
`must_admit` run at all, the mean cost of the atoms in the plan rounded half
to even to two decimal places, and the count of principals whose
`final_disposition` is `granted`.
