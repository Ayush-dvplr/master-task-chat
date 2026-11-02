# LGA appendix: the seccomp filter stack

This appendix is part of the LGA contract and states the system call filter
algebra in full. `SPEC-LGA.md` section 6.4 gives the outline.

## Architectures and numbers

Three architectures appear: `x86_64`, `i386` and `aarch64`. A system call
number means nothing on its own; it means a name only together with an
architecture. The `arch-syscalls` group carries that mapping, and the same
number maps to different names on different architectures.

A `syscall` event carries an architecture, after the repair rule of
`SPEC-LGA.md` section 5 has filled an empty one from the run's dispatch
architecture, and a number, after the same section's rule has read a `0x`
prefix as hexadecimal and treated leading zeros as padding.

The number is resolved through the table for that architecture. A number the
table does not carry for that architecture resolves to no name. Such an event
is refused, the action reported is `KILL_PROCESS`, the reason is
`seccomp_kill_process` and the rule is the literal `NONE`. The event is
counted in the unknown column of the architecture dispatch artifact.

The system call table carries more numbers than the filters name, and it
carries the same name at more than one number. Where a name has to be resolved
back to a number, for the `nr` field of the filter program artifact, the lowest
number that architecture maps to that name is the answer.

## Loaded filters

The filters loaded for a run are the ones its unit's `filters` field names, in
whatever order the field lists them. A unit naming no filter loads none, and a
run whose unit loads no filter has every system call allowed.

A filter identifier a unit names that no `seccomp-defaults` record declares has
the default action `ALLOW` and holds whatever rules the `seccomp-filters` group
carries for it. The corpus carries such filters; a reader that refuses to load
an undeclared filter, or treats it as anything but `ALLOW`, is wrong.

## Matching inside one filter

A rule matches an event when the rule's architecture equals the event's
architecture and the rule's system call name equals the resolved name of the
event's number.

A rule whose `arg_index` field is empty carries no argument condition and
matches on architecture and name alone.

A rule whose `arg_index` field holds a number carries an argument condition.
The recorded trace carries only argument zero, so a rule naming an argument
index other than zero never matches. A rule naming argument zero matches only
when its comparison holds between the event's `arg0` and the rule's `value`:

```
EQ          arg0 equals value
NE          arg0 differs from value
LT          arg0 is less than value
LE          arg0 is less than or equal to value
GT          arg0 is greater than value
GE          arg0 is greater than or equal to value
MASKED_EQ   arg0 bitwise and mask equals value
```

Comparisons are on whole numbers. An empty `value` field is zero and an empty
`mask` field is zero.

## The answer of one filter

The answer of one filter is the strictest action among its matching rules. When
no rule matches, the answer is that filter's default action. The `idx` field
orders the rules inside a filter for reporting and has no part in deciding:
the strictest matching rule wins whatever its position, and a rule earlier in
`idx` order does not shadow a stricter rule later.

## The answer of the stack

The action the kernel returns is the strictest answer across the loaded
filters. Relaxing one filter therefore changes nothing while a second loaded
filter still answers more strictly.

The strictness order, strictest first, and the rank of each action:

```
1 KILL_PROCESS      5 USER_NOTIF
2 KILL_THREAD       6 TRACE
3 TRAP              7 LOG
4 ERRNO             8 ALLOW
```

## Which actions refuse

`KILL_PROCESS`, `KILL_THREAD`, `TRAP`, `USER_NOTIF` and `TRACE` refuse the
event. No supervisor is attached to this population, so the two actions that
would hand the call to one refuse it here.

`ERRNO` refuses the event when the event's `required` field is `yes`, and does
not refuse it otherwise. A system call the run can proceed without is allowed
to fail; one it cannot is not.

`LOG` and `ALLOW` never refuse.

## The rule a refusal names

A refusal names the `rule_id` of the rule that produced the deciding action. A
refusal produced by a filter's default action names the literal `NONE`, and so
does a refusal caused by a number that resolved to no name.

Ties are settled the same way in every artifact. Inside one filter, when two
or more matching rules carry the strictest action, the rule named is the one
earliest in `idx` order, then the lowest rule identifier. Across the loaded
filters, when two or more filters return the same strictest action, the answer
kept is the one whose named rule sorts first as text, and an answer a default
produced sorts before every rule identifier, so a default and a rule that tie
report the literal `NONE`.

The matched count reported for an event is the number of rules that matched it
across every loaded filter, whatever action those rules carry. An event decided
by defaults alone has a matched count of zero.

## What the three seccomp atoms change

A `seccomp_rule_add` atom names a `filter`, an `arch` and a `syscall`. That
filter answers `ALLOW` for that pair whatever rules it holds, so the atom
overrides the filter's own rules rather than joining them. It changes nothing
about the other loaded filters.

A `seccomp_default_relax` atom names a `filter`. That filter's default action
becomes `ALLOW`. Its rules still decide when one of them matches, so this atom
changes nothing for an event a rule already matched.

A `filter_unload` atom names a `filter`. That filter leaves the loaded set of
every unit that names it, so it contributes no answer at all.
