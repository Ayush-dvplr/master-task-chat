# Epoch applicability and identity dictionary

epochs.csv contains epoch,start,end. The epoch of an event is the unique interval
whose start is at most the event's captured value and whose end is greater than
captured. The event's stamp never selects this interval. Captured is the
collector's independent clock and stamp is the source clock discussed in clock.md.
An event outside every epoch is an error. Epoch names carry no ordering meaning.
The last epoch is the one with the greatest start, even if it has no events.

aliases.csv contains alias,start,end,identity. Alias validity uses the corrected
event instant defined in clock.md. Intervals are closed at start and open at end.
Adjacent intervals may give one alias different identities. Historical events
keep the identity at their own instant. Identity text is emitted verbatim.
