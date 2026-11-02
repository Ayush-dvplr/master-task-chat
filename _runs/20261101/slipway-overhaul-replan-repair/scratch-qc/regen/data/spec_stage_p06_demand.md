# Stage p06  what a job draws

Two vectors are carried for each job. The own vector is what that job draws by
itself, in the three pools of `unit_registry.toml`. The closed vector is what
the job and its whole closure draw together, counting each distinct job once.

The usage of an accepted set is taken over the closed set of that selection,
each distinct job counted once, from the own vectors. Adding the closed
vectors of the jobs selected would charge a shared prerequisite twice and is
not what the yard is billed.
