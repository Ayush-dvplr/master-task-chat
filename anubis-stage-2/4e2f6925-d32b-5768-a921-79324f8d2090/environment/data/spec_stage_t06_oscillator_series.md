# T06 oscillator deviation series

## Input

The node offsets of T05, oscillator_catalogue.csv,
node_register_frozen.csv at the frozen revision and local_comparison_log.psv.

## The reference oscillator

Each node realises its clock with the oscillator the frozen register revision
names in reference_oscillator. The deviation of that oscillator at an epoch is
the offset of its node at that epoch.

The register carries several revisions and they do not agree. Two nodes change
their reference oscillator at a later revision. The revision that applies is
the one network_config.json freezes for this interval, and no other.

## Other oscillators

Every other oscillator at a node is measured against that node's reference
oscillator by the local monitor. Its deviation at an epoch is

    node offset at that epoch + local_offset_ps at that epoch

taken from the row of local_comparison_log.psv for that oscillator and epoch.
A row whose monitor_flag is not MON_VALID does not carry a measurement, and
neither does a missing row. In either case the oscillator has no deviation at
that epoch and the absence is recorded with scope SCOPE_OSCILLATOR.

That record covers the local monitor and nothing else. An oscillator whose node
carries no offset at an epoch also has no deviation there, and it takes no
SCOPE_OSCILLATOR record: the SCOPE_NODE record of stage T05 already says the
whole node is out at that epoch, and the ledger states each absence once. So a
SCOPE_OSCILLATOR record appears only where the node does carry an offset and
the oscillator's own monitor row is missing or is flagged other than
MON_VALID, which is why no reference oscillator ever takes one.

## Flags

A deviation carries SER_MEASURED when its node is in the anchored component,
and SER_UNANCHORED when its node is in an unanchored component, where the
deviation is against that component's own root and not against the hub. An
oscillator with no deviation at an epoch carries SER_ABSENT, and SER_ABSENT
takes precedence over SER_UNANCHORED.

## Output

A deviation or an absence for every catalogued oscillator at every epoch.
