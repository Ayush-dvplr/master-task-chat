# Restatement notes

A publication states, for each zone cell, the settled watt-hours and the settled
event count the network published for that cell. A later materialization of the
same calendar can reach a different figure for a cell, because a revision
delivered after the publication changes the canonical revision of an event,
because a merge instant moves an event onto a different canonical site, or
because an effective dated attribute places an event in a different zone.

A restatement is the difference between what this run computes for a zone cell
and what the publication states for it. It is signed. A cell whose figures both
agree with the publication is not restated and no adjustment record is written
for it.

The cells a restatement covers are the cells the publication states together
with the cells this run computes, and never one of the two alone. A zone the
network has retired since the publication is stated by the publication and
computed by nothing here, so this run restates that cell to zero: its restated
watt-hours and its restated event count are both zero and its deltas are the
negatives of the published figures. A cell this run computes that the
publication never stated is restated from zero in the same way.

The publication is an input. It is never rewritten, and the figures it carries
are never substituted for the figures this run computes. A run whose adjustment
record simply repeats the publication's figures has computed nothing.

The publication is granular to the zone cell and never to the partition, so the
figures it carries do not state any partition total and cannot be read as one.
