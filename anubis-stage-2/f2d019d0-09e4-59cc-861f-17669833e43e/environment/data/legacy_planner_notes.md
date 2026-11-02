# Notes from the previous planner

These notes describe the planner that ran before the register was introduced.
They are kept for context and they are not the contract.

The old planner held capacity at the minimum first and aligned the result to the
bucket afterwards, so every capacity was a multiple of the bucket and the
`data_dependent_capacity` break never fired. It counted a shape as seen only
after its compilation finished, so promotion always lagged by one shape. It
sourced the balance term from accepted assignments rather than from demand, which
made the term shrink whenever capacity bit. It placed experts on ranks by integer
division of the expert index, which is not what the affinity table says.

Every one of those four behaviours has since been superseded.
