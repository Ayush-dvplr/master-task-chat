# V13 minutage compliance

Inputs: the admitted spots from V9, `daypart_calendar.csv`, and the
regulatory minutes published in Sections 1 and 2 of
`regulatory_minutage_memo.pdf`. V13 runs before V11.

## The clock hours

The broadcast day is twenty four clock hours long. Hour `H06` runs from the
day start to one hour of channel timecode frames later, which is `107892`
frames, and each following hour runs for the same count. The hours are
labelled `H06` through `H29`, so the small hours of the following calendar
day carry the labels `H24` through `H29` and sit at the end of the day.

The last hour of the day, `H29`, absorbs anything that runs past the end of
the day.

## R33 the advertising frames

The advertising frames of a market in a clock hour are the channel frames of
admitted spots that lie inside that hour. A spot that straddles an hour
boundary contributes to each hour exactly the frames that lie inside it. A
spot is not assigned whole to the hour its first frame falls in.

## R37 the minutes of one market hour

Section 1 of the memo publishes `regulatory_minutes_per_clock_hour`, the
standing figure. Section 2 lists permitted minutes per market and clock
hour. Where Section 2 lists a market and hour, its minutes govern that
market hour and replace the standing figure; where it does not list one,
the standing figure governs. Each market hour has its own cap.

## R34 the cap

The cap in channel frames of a market hour is its regulatory minutes under
R37 multiplied by sixty seconds, converted into channel frames by the exact rational
`seconds * 30000 / 1001`, and floored. It is not the minutes multiplied by
sixty and then by the timecode base of thirty. The channel does not run at
thirty frames per second and the two figures differ by several frames an
hour.

An hour whose advertising frames are greater than the cap is a breach and
publishes the state `MB_BREACH`. An hour that lands exactly on the cap is
not a breach and publishes `MB_WITHIN`. The published `headroom_frames` is
the cap less the advertising frames and is negative in a breach.

## R41 the frames above the cap go unbilled

In every breaching market hour, the frames by which the advertising frames
exceed that hour's cap go unbilled. They are taken from the admitted spots
of that market that have frames inside the hour, latest first: in
descending `start_frame`, ties broken by descending `order_ref`. Each spot
in turn gives up the smaller of its frames inside that hour and the frames
still to be taken, until the excess is taken. A spot that straddles two
breaching hours can give up frames to each, never more than it has inside
each. A spot's unbilled frames are the sum of what it gave up over the day.
V11 bills the rest, and V12 owes the grains it lost.

## Published

`minutage_report.csv` publishes one row per market per clock hour, ordered
by market reference and then by hour label, for all four markets and all
twenty four hours whether or not any spot fell in them. `cap_frames` is
that market hour's own cap under R37, and `headroom_frames` and
`breach_state` are judged against it.
