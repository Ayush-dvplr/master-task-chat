# Sealed evidence

Two decisions are withheld from the prose: the field order of the routing tie
break key, and the precedence order of the rejection causes. Both are recoverable
from the shipped digests without guessing.

`sealed_tiebreak_digests.json` maps a configuration name to a step count and to
the SHA-256 of the canonical serialisation of the list of tie break events that
the correct key produces over those leading steps of that configuration. Events
are concatenated in ascending step and, within a step, in the order the router
recorded them.

`sealed_precedence_digests.json` maps a configuration name to the SHA-256 of the
canonical serialisation of the per cause count map produced by the correct order
over the settlement sweep of that configuration. The map holds all seven cause
names, including the ones that never fire.

The named configurations are `calibration`, which is `calibration_config.json`,
and `probe_alpha`, which is the entry of that name in
`probe_configurations.json`.

Canonical serialisation is the shape described in `output_schema.md`: two space
indentation, keys sorted at every level, no ASCII escaping, one trailing newline,
UTF-8 bytes.

A candidate order that reproduces the digest for every named configuration is the
order in force. Should more than one candidate reproduce every digest, the one
that sorts first when the candidate orders are compared as lists of strings is
the one in force. If no candidate reproduces them, something upstream of the digest
is wrong; the digests are not a substitute for the pipeline.
