# Stage p03  units, amounts and the normalised record

Every quantity is carried in the unit `unit_registry.toml` names, and the
register may state it in either of two units.

A crew quantity stated in shifts is multiplied by the shift length of the
precinct the job stands in. A crew quantity stated in minutes is already in
the unit. A berth quantity stated in days is multiplied by four. A berth
quantity stated in quarter days is already in the unit. A lift count is a
count. Money is whole mills throughout and a thousand mills is one pound.

An amount written by the desk is put into whole mills as follows. Thousands
separators are dropped. An amount that ends in `GBP` is read as pounds, with
up to three decimal places standing for the mills, so `4.800 GBP` is four
thousand eight hundred mills and `4 GBP` is four thousand. A fraction shorter
than three places is padded on the right to reach the mills, so `1.75 GBP` is
one thousand seven hundred and fifty mills and never one thousand and seventy
five. An amount that ends
in `mills`, or that carries no unit word at all, is already whole mills, and a
fractional part on such an amount is refused. Two amounts that reach the same
whole mills are the same amount, whatever the desk wrote.

The normalised record of a job carries its precinct, class, standing, base
charge in mills, crew minutes, berth quarter days, lift count, deferral weight
and whether it is admissible. It carries nothing of the title, the note, the
owner or the display order: those govern nothing and are the presentation
fields. The normalised record of a conditional charge rule carries its
precinct, its kind, the jobs or the pool it names, and its amount in whole
mills or its rebate in basis points. It carries nothing of the note or the
author.
