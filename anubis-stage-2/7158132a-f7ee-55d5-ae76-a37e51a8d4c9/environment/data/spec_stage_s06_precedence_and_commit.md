# S06 precedence and commit

## the registered class

The registered priority class of a mission is on its current
mission_register.csv row. reference_lookups.sqlite table priority_rank
gives the rank value of each class. A lower rank value outranks a higher
one.

## overrides

precedence_override_register.jsonl carries one row per override. An
override applies to a canonical row when it names the same mission, it
names the same aperture_uid, and its half open window [valid_from_s,
valid_to_s) contains the pass scheduled_start_s. An override that names a
different aperture of the same station does not apply.

Where more than one override applies, the one granting the strongest
class wins, and where two grant the same class the lower override_id
wins.

An override may only raise a mission. When the granted class is weaker
than the registered class, the registered class stands. This is clause
three of precedence_directive.docx.

effective_class is the resulting class and effective_rank its rank.

## the commit boundary and protection

The commit boundary is scheduled_start_s less the station commit lead
from network_operations_memo.pdf.

A canonical row is protected when both hold:

  the operational event event_recorded_s is at or before the commit
  boundary, and

  the operator who signed the event holds a grade that carries commit
  evidence.

operator_roster.tsv gives the authority_grade of every operator code.
reference_lookups.sqlite table grade_authority says which grades carry
commit evidence. An event signed by a grade that does not carry it is no
evidence of commitment however early it was recorded.

An event recorded exactly on the commit boundary is protection.

## why protection is not a priority

Clause two of precedence_directive.docx states the exception that makes
the whole of S07 state dependent: a protected pass outranks every
unprotected pass whatever their classes say. An emergency override pass
that was never committed loses its aperture to an ordinary priority pass
that was. Protection is the first key of the ordering, not a tie break
inside a class.
