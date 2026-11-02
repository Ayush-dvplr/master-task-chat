# Stage p04  admissibility of one job

A job is admissible when both tests below pass, and the first test it fails is
the reason it is inadmissible.

`JOB-LICENCE`  the licence code the job carries stands in
`licence_validity_register.csv` with the state `valid`, and the round index
lies between `valid_from_round` and `valid_to_round` inclusive.
`JOB-OUTOFROUND`  the round index lies between `earliest_round` and
`latest_round` inclusive.

An inadmissible job stays in the round and holds its cells. It is never
selectable and, because it could not have been taken, it carries no deferral
penalty. That is what separates it from a job that was admissible and was left
out.
