# Headway primer

One worked admission on invented figures, so the ladder of stage 7 can be
checked against arithmetic.

Take a section of class mainline whose minimum headway in force is 15 minutes,
a deferral step of 6 minutes and a maximum of 2 deferrals. Four movements name
routes whose only section is that one, with an offset of 0 minutes, and the walk
has already put them in this order:

| movement | stage 6 entry |
|---|---|
| M1 | 2030-06-01T09:00:00Z |
| M2 | 2030-06-01T09:15:00Z |
| M3 | 2030-06-01T09:10:00Z |
| M4 | 2030-06-01T09:01:00Z |

M1 is walked first. The admitted set of the section is empty, so count 0 clears
and M1 is admitted with a deferral of 0. The admitted set now holds 09:00.

M2 is walked next. At count 0 the gap to 09:00 is exactly 15 minutes, which is
the minimum, so the count clears. A reading that treats the minimum itself as a
conflict would defer M2 for no reason. M2 is admitted with a deferral of 0 and
the admitted set holds 09:00 and 09:15.

M3 is walked next. At count 0 its entry is 09:10, five minutes from 09:15 and
ten from 09:00, so the count conflicts. At count 1 the entry is 09:16, one
minute from 09:15, so that conflicts too. At count 2 the entry is 09:22, seven
minutes from 09:15, so that conflicts as well. No count clears, so M3 is
withheld with the reason headway and none of its entries joins the admitted set,
which still holds 09:00 and 09:15.

M4 is walked last. At count 0 its entry is 09:01, one minute from 09:00, which
conflicts. At count 1 the entry is 09:07, seven minutes from 09:00 and eight
from 09:15, which conflicts. At count 2 the entry is 09:13, thirteen minutes
from 09:00, which conflicts. M4 is withheld as well.

Two movements are admitted, both at a deferral of 0, and two are withheld. Had
M3 been walked before M2, M3 would have cleared at count 0 and M2 would have
been the one to defer, which is why the walk order of stage 7 is part of the
contract rather than a convenience.
