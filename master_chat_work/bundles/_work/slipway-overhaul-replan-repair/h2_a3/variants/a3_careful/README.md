# slwopt

The replan desk's engine. It reads one round of working papers, builds the
derived state of the round, solves each precinct exactly, then applies the
amendments the desk lodged one at a time, reusing every derived value the
amendment leaves standing.

    python3 -m slwopt --data <papers> --out <destination>

Both options are accepted in either order. The destination is created when it
is absent. The paper directory is only ever read.

The engine is standard library only on the 3.12 series.
