STAGE Y02  Unit normalisation
shift KP-2042-S23

This stage puts every box in the terminal's base units.

RULE Y02.1  The applicable box record.
Read box_master_register.csv through revision_precedence.toml.
Rows of another shift, and rows marked retired, are set aside.
The applicable row of a box is the surviving row with the
highest revision_seq.

RULE Y02.2  The applicable mass declaration.
In mass_declaration_returns.psv a declaration counts only when
its state is filed. Among the filed declarations of one box the
one with the highest declaration_seq is applicable. Superseded
declarations are set aside whatever they carry.

RULE Y02.3  The unit register.
A declaration is written in the register its mass_unit column
names. A kg declaration is already in kilograms. A dt
declaration is multiplied by the kilograms in one decitonne and a
ct declaration by the kilograms in one centner. Both factors are
issued by the live sheet of quay_capacity_workbook.xlsx and are
carried in no other paper of this shift.

RULE Y02.4  An absent mass.
A box whose applicable declaration carries the not supplied
marker, and a box with no filed declaration at all, is published
with mass_state of not_declared and a published mass_kg of 0.
The published zero is a form, not a measurement: such a box is
excluded from every mass total this publication carries. Reading
an absent mass as a declared zero puts it into those totals and
is wrong.

RULE Y02.5  The length spellings.
The iso_length column is written as a bare number, or with the
suffix FT, or with the suffix ft. The three are one length. The
published iso_length is the bare number.

RULE Y02.6  The teu factor.
The teu factor of a length is issued by the live workbook sheet.
A length the sheet does not carry has a teu factor of 0.

PUBLISHES  container_dimensions.csv
