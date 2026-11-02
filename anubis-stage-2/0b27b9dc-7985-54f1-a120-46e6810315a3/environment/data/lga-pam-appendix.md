# LGA appendix: the PAM stack walk

This appendix is part of the LGA contract and states the authentication stack
algebra in full. `SPEC-LGA.md` section 6.1 gives the outline; this file gives
the rule.

## Ordering

The lines that apply to one run and one phase are the `pam-stack` records whose
`service` equals the run's service and whose `phase` equals the phase being
walked. They are ordered by `rank` ascending, then by `module` ascending, then
by `rule_id` ascending. The order the records appear in the corpus is not the
order they are walked in, and two lines never share a rank inside one service
and phase.

## Gating

A line whose `flags` field contains `skip_if_uid_below=N` is walked only when
the principal's `uid` is greater than or equal to `N`. The boundary is
inclusive on the upper side: a principal whose `uid` is exactly `N` walks the
line, and a principal whose `uid` is `N` minus one does not. Other flag words
such as `audit` and `try_first_pass` change nothing about the walk.

## Return codes

The code a line returns is the `code` of the `pam-returns` record whose
`run_id`, `phase` and `module` match the run, the phase and the line's module.
A line with no matching record returns `ignore`.

The codes are `success`, `ignore`, `auth_err`, `user_unknown`, `perm_denied`,
`maxtries`, `cred_insufficient`, `abort` and `service_err`. Every code other
than `success` and `ignore` is a failure code.

## The walk

Three values are carried through the walk: the first recorded failure, which
starts unset; the first optional failure, which starts unset; and a flag
recording whether any line that is not `optional` produced a code other than
`ignore`, which starts false.

Each line in order:

A line returning `ignore` changes nothing and the walk continues.

A line whose control is `optional` records its code as the first optional
failure when the code is a failure and no optional failure is recorded yet, and
the walk continues. An `optional` line never sets the flag.

Every other control sets the flag, and then:

A `requisite` line returning a failure ends the walk at once and the phase
yields that code.

A `binding` line returning a failure ends the walk at once and the phase yields
that code. A `binding` line returning `success` ends the walk at once and the
phase yields `success`.

A `sufficient` line returning `success` ends the walk at once and the phase
yields `success`, unless a failure is already recorded, in which case the walk
continues. A `sufficient` line returning a failure records nothing and the walk
continues.

A `required` line returning a failure records that code as the first recorded
failure when none is recorded yet, and the walk continues.

## The phase result

When the walk finishes without ending early, the phase yields, in this order of
preference: the first recorded failure when one is recorded; otherwise
`success` when the flag is set; otherwise the first optional failure when one
is recorded; otherwise `service_err`.

## The deciding line

A phase that yields a failure names the line that produced it: the line that
ended the walk early, or the line whose code was the first recorded failure, or
the line whose code was the first optional failure. A phase that yields
`success` from a `sufficient` or `binding` line that ended the walk names no
rule, but it does name that line's module as the deciding module, because that
module is what answered the phase. A phase that yields `success` because the
flag was set names neither a rule nor a module. A phase yielding `service_err`
with no deciding line names neither.

Where the specification asks for a deciding rule or a deciding module and the
phase names none, the literal `NONE` is written.

## Phases

The three phases are walked in the order `auth`, `account`, `session`, and each
is one event in the recorded trace. The first phase yielding a code other than
`success` refuses the run at that event. A phase yielding `success` is not
recorded as a refusal even when a later phase fails.

## What a control relax atom changes

A `pam_control_relax` atom names one `rule_id`. The line carrying that
`rule_id` is walked as though its control were `sufficient`, whatever control
the corpus records for it. Nothing else about the line changes: its rank, its
module, its gate and its return code are unaffected, and the ordering does not
move.
