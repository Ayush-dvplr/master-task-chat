# Footprint policy

The footprint of a lock plan is the sum of the artifact bytes of its locked versions. A workspace
receives the valid lock plan with the smallest footprint. When several valid plans share the smallest
footprint, the workspace receives the one whose locked version codes have the largest sum. When
several of those also share that sum, it receives the one whose plan text sorts first, where the plan
text lists every locked package in ascending reported name as the name, an at sign and the version
code in eight lowercase hexadecimal digits, joined by commas.

Every workspace of a population drawn from this policy admits at least one valid lock plan.

A locked package is held back in a workspace when its locked version code is below the largest
version code among its versions eligible for that workspace.

## Byte conservation

The decoded bytes of the field population total the artifact bytes of every version record of every
field shard. The excluded bytes total the artifact bytes of every record of an unregistered package,
whatever its status, and of every yanked record of a registered package. The locked bytes total the
artifact bytes of every distinct package version that at least one workspace locks, each such version
counted once. The byte residual is the decoded bytes less the excluded bytes less the locked bytes.
