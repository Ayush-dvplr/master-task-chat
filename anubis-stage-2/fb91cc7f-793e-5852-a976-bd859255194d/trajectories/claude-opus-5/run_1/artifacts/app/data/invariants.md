# Invariants

These hold of every settlement this lab has ever published, and they hold of
the one being settled now. They are not a method for producing a settlement.
They are the properties a correct settlement has, and they are the properties
the lab checks a settlement against before it goes out.

A settlement that violates any of them is wrong, whatever produced it.

## Identity closure

Every reel identifier appearing anywhere in the cycle (in the scan book, in
the lineage book, on a shot) resolves to exactly one live reel or to a
retired one. No identifier resolves to something that is itself folded into a
third thing. No identifier resolves to nothing.

The live reels, the folded reels and the retired reels partition the reel
identifiers of the cycle: every identifier is in exactly one of the three.

## Conform closure

Every programme in the cycle is either conformed or voided, never both and
never neither. Every voided programme carries the reason it voided.

A conformed programme's frame count is the sum of the lengths of its shots,
and its shots tile its timeline from zero with no gap and no overlap.

Every shot of a conformed programme lies inside the usable span of the live
reel it resolves onto.

## Impairment conservation

For every conformed programme, the frames that impairment covers are at most
the frames the programme has, and the frames recovered are at most the frames
impaired.

For every defect, the frames recovered against it are at most the frames it
covers after clipping, and the sum of the frames recovered by its individual
repairs equals the frames recovered against it.

Across the cycle, the frames recovered by every repair that stands sum to the
cycle's recovered total, and every repair that does not stand recovers zero.

## Cadence consistency

Every conformed programme's frame count at its delivery cadence stands to its
frame count at its governing element's cadence in the ratio of those two
cadences, up to the whole frame the lab quantises to.

Every settled programme's condition grade is the grade its own settled figure
falls into, and where more than one grade holds that way it is the highest of
them. No programme has none.

## Admission conservation

Every settled programme is either admitted or held, never both and never
neither. Admitted count plus held count equals the number of settled
programmes.

For every settlement group, the frames its admitted programmes consume are at
most that group's quota for the cycle.

Every holder that the cycle counts as drawing holds at least one admitted
programme, and no holder outside the drawing set holds one.

## Seating conservation

Every admitted programme sits in exactly one vault. No vault's load exceeds
its capacity. The vault loads sum to the admitted frames.

Every held programme is either seated in exactly one lane or shed, never both
and never neither. No lane's load exceeds its capacity. The lane loads sum to
the lane frames, and the lane frames plus the shed frames equal the held
frames.

Every seated programme sits somewhere that accepts its deliverable class and
its settlement group.

## The cycle ledger

The cycle closes. Read down the stages (conform, impairment, admission,
seating, cascade) and each one balances what came into it against what left
it, with nothing unaccounted for. The residual over the whole cycle is zero,
and a settlement whose residual is not zero has lost something.

The settled total of the cycle equals the admitted frames plus the held
frames, and equals the vault loads plus the lane loads plus the shed frames.

## Cross report agreement

Any figure that appears in more than one report is the same figure in all of
them. A programme's settled frame count is one number, wherever it is written.

## Determinism and idempotence

Settling the same cycle twice gives the same bytes. Settling a settlement
changes nothing.
