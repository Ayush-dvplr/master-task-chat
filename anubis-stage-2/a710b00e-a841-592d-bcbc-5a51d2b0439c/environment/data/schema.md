# Telemetry settlement contract

This extract records four telemetry processing lanes. Their regional names are
North, South, West and East. Commercial is the account view of the East lane;
public is the eligibility view of the South lane. Those names identify processing
lanes, rather than customer geography. The extract's tables are independent of
file paths and row arrival order except where a table defines an ordering key.
All CSV files have one header, UTF-8 encoding with no BOM, comma delimiters, decimal integer
cells and LF line endings. Empty tables retain the header. Identifiers are
case-sensitive text unless explicitly called integers. A vertical bar separates
the members of a set. An empty atoms cell denotes the empty set. Repeated members
in a set are invalid. JSON integers are
unbounded. Arithmetic is exact; no floating-point operation or rounding is needed.

The policy.json object defines report_id, clock_multiplier, clock_modulus and
eligibility_threshold. The replay.json object defines modulus and initial for
the West lane. Neither file contains an expected output.

The North lane is defined in clock.md and its applicability in dictionary.md.
The East lane is defined in allocation.md. South and West are defined in replay.md.
Every output key and byte form is defined in reports.md.

Each extract is bounded by 11 sources, four epochs, 50000 events, 24 boards,
24 components per board, 11 groups per component, 39 candidates per group,
100000 requests, 64 cycle streams, cycle moduli as specified in replay.md,
10**18 rounds,
50000 fold records and 100000 amendments. Integer coefficients, quantities,
timestamps and revisions may be signed. Record and amendment identifiers and
positions are nonnegative integers. Clock coefficients and residues use the
residue system of clock.md. An epoch list is nonempty and has disjoint intervals.
Source identifiers and record positions are unique in their respective tables.
Event and request identifiers are also unique in their respective tables.
Cycle moduli are either at most 127, or are 1000000007 under the large-stream
rule in replay.md. All other moduli are positive integers.
Counts and round counts are nonnegative integers. Candidate values are signed integers.

An inconsistent or ambiguous clock assignment, allocation or event identity is
an error. Produce no reports in that case. Inactive empty lanes are valid.
