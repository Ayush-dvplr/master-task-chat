# T13 reports, reconciliation and the manifest

## Loop closures

Every link the tree excluded still carries readings, and the difference it
records disagrees with the difference the tree implies. At every epoch where
the excluded link carries a canonical reading and both of its nodes carry an
offset,

    closure_ps = difference_ps of the excluded link
                 minus (offset of node_a minus offset of node_b)

An excluded link that never reaches that condition carries no closure and is
listed as unreconciled instead.

## Per node reports

A report is published for each of the four nodes the output artifact contract
names. It carries the node's component, role, register revision, reference
oscillator, the link identifiers on its tree path in order from the root
outward, the length of that path, the count of epochs at which it carries a
published offset, its mean offset, the two uncertainty statistics, its status
and one entry for every oscillator catalogued at it.

## The two digests

The publication manifest carries two sha256 digests.

The core digest, published as digest, runs over the bytes of the six core
artifacts concatenated in the order ordering_dependencies.yaml lists under
digest_order. That order is the order of the chain and it is not alphabetical.

The publication digest, published as publication_digest, runs over the bytes of
every other artifact, concatenated in the order the table in
output_artifact_contract.md lists them, with the manifest itself left out
because it carries the digest. The manifest is the last document written, and
it moves whenever anything else in the publication moves.

## Output

The reconciliation document, the four node reports, the two markdown reports,
the node index and the publication manifest.
