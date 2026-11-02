# Stage r06: Replay window construction

A replay is asked for a half open range of canonical positions: the
start is included and the end is excluded. The window it actually
replays opens at the later of the requested start and the restored
watermark plus one, and closes one before the requested end or at the
last canonical position, whichever comes first.

The count of positions skipped because the checkpoint already covers
them is the watermark less the requested start plus one, and never less
than zero.

The event at the watermark position is never replayed. The event at the
end position is never replayed either.
