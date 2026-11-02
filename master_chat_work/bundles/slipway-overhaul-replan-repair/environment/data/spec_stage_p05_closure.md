# Stage p05  the closure of a job

The closure of a job is every job that stands behind it through accepted
prerequisites, at any depth, the job itself left out. Taking a job takes its
whole closure with it; a closure member is never taken optionally.

A job is blocked when it is inadmissible itself, and then it carries the
reason of stage p04. A job is blocked under `JOB-CLOSUREBLOCKED` when anything
in its closure is inadmissible or has been set aside. A blocked job is never
selectable and, like an inadmissible job, carries no deferral penalty.
