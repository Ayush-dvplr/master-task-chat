# Operator questions

**Does an excluded asset still get a row in the asset register?**
Yes. It is published with the inclusion state `AS_EXCLUDED`, with its house
number and its anchor, and with every derived field empty.

**Which attempt supplies the house number?**
The anchor, which is the first received attempt. Not the canonical attempt.

**Is the end of media timecode inclusive?**
No. An asset whose start and end labels are equal spans zero frames.

**What happens when the end label is earlier than the start label?**
The asset wraps the timecode day and one whole timecode day is added to the
difference.

**Does a trimmed black part consume carry?**
No. It makes no conversion, so the scope's held fraction is unchanged and
the part publishes the fraction that was already held.

**Can a break snap outside the material?**
It can snap forward past the material end when the index runs that far. The
index is published for the content and the conditioning does not clip it.

**Does a deferred spot use capacity?**
No. It consumes no capacity and takes no position in the break.

**Can a spot be moved to a different break?**
No. A spot is sold against one break and is either admitted there or
deferred.

**Which currencies have an exponent that is not two?**
The exponent table publishes them. One of the four settlement currencies has
an exponent of zero and one has an exponent of three.

**Is an hour that lands exactly on the cap a breach?**
No. A breach is strictly above the cap.

**Is a rate card dated exactly on the transmission date eligible?**
Yes. The rule is on or before.

**Is a blackout window inclusive at both ends?**
Yes.
