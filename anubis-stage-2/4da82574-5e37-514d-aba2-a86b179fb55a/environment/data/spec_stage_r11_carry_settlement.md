# Stage r11: Carry settlement

After every applied transition and every applied compensation each
station the event touched settles on its own balance.

A station whose balance stands at or below the ceiling for the frozen
register revision and its class does not settle. Otherwise the spill is
the balance less the ceiling, the carried part is the spill floored to a
whole number of the class carry quantum, the balance comes down by the
carried part and `spilled_cu` goes up by the carried part. A carried
part of zero leaves the balance where it stands.

The class carry quantum appears on the live workbook sheet and in no
other paper in this directory. The superseded scale table restates a
shifted quantum and governs nothing.
