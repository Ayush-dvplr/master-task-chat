# W9 literal-reading self-test, calibration.md "Fragments each control reads" (P12 v3 r2 F1)

Each row: the other reading a careful reader could take, and the wording that closes it.
Proof that one reading survives: `grammar_check.py` was written from calibration.md alone
(no import of tests/ or solution/) and pins exactly one candidate per control on the shipped
corpus and three held-out seeds (`grammar_check_out/*.txt`, RESULT 11/11, hits=[one value]).

| control | other reading | closed by |
|---|---|---|
| all | fragments only for captures whose flag word is non-zero | "the captures whose flag word is zero included" |
| all | fragments in file-name or ring-file order | "in ascending capture ordinal" |
| all | body without the ordinal prefix | "the capture ordinal in decimal, a colon, and the body" |
| all | later quantities at true or default values | "takes the value the figures ahead of it pinned" |
| payload list | filler lines dropped; uppercase hex; spaces after commas | "every declared line counted, filler included", "lowercase", "no spaces" |
| A | bias written for every capture | "for a padded capture, and `0` for any other" plus example `1:0` |
| B | weave applied in the inverse direction | "the line read at restated position p moves to the position the finished order records at p" |
| B | doubled sentinel already collapsed | "A doubled reserved byte is still written twice." |
| C | unreadable payload dropped or written `none` | "written as twenty four zero digits" |
| D | key over block ordinal only | "over the capture ordinal and then the block counter" |
| E | which label word seals | "the label word `seal_label_index` names" |
| E | rotation undone before writing | "Its rotation is not undone." |
| F | flipped byte order by its real block | "unpacked as if it stood in block 0" |
| F | tick restored from the stepped series | "The tick is the field as stored" |
| G | filler at the start of block 0 | "the last `shadow_pad_base` less three payloads of block 0" |
| G | chain carry uses restored ticks, or carries over a `none` | "stored tick and amount", "0 and 0 ... for an entry after a `none`" |
| G | rotation amount per entry not the per-capture spin | "the entry ordinal plus one times `spin_modulus` taken against twelve" |
| H | `none` breaks or skips the stepped series | "a `none` entry counting as a stored 0" |
| H | out-of-range index fails | "taken against the length of the list" |
| I | echoes resolved from the original list | "as that entry stands once the echoes before it are resolved" |
| I | echo copies the tick too | "It keeps its own tick" |
| J | units ordered by unit index or locale collation | "ascending order of the unit word by character code" |
| K | decimal or unreduced fraction | "numerator, solidus and denominator in lowest terms" plus example `98472/1` |

Residual: the entry check label (`entry`) is named in charter-scale.md:24-28 mask table and settles
from the flag-zero captures; the format note only says "a digest over the ten bytes that precede it".
Reachable, recorded under Lessons.

# W9 literal-reading self-test, P12 v3 r6 (c45716e) edits

| sentence | other reading a careful reader could take | why the oracle does not lose |
|---|---|---|
| report-schema.md L13-15 "The decoded fields ... count every entry the captures decode, before unit identity, live windows and cancellation are applied." | a payload that reads back as `none` counts as a decoded entry | calibration.md:71 "A payload that unpacks to nothing is written `none`": it decodes to no entry; oracle walk skips the same payloads (tests walk_entries ghost skip) |
| same | echoes counted as their own entry kind rather than resolved | replay-format.md:54 resolves an echo while reading the wire, before any of the three listed steps; oracle counts the resolved entry |
| same | retired-unit or off-window entries left out | "before unit identity, live windows ... are applied" puts them in; oracle counts them (decoded_amount = every walked row) |
| engine-rules.md L79-81 "settled, dropped, held as surplus ..., or carried by a cancelled entry or the reversal that cancels it" | cancelled amounts taken away before the residual | residual sentence that follows names only settled and dropped amounts; oracle residual = decoded - settled - dropped |
| engine-rules.md L97-98 "contribute nothing to any settled total" | cancelled pairs also leave reversal_count | report-schema reversal_count "reversal entries the set holds after decoding" is a decoded-level count; oracle counts every reversal |
| instruction.md L3 "Some numeric quantities ... are withheld ... control figures" | no reading changes what is computed | requirement only; the calibration notes still name each quantity and its control |
| instruction.md L5 "The word an entry names is chased to the identity in force at that entry's tick before anything is counted." | chase at the capture's tick, or at the latest tick | "at that entry's tick" fixes it; unchanged wording from r5 |
| instruction.md L13 "Each report is graded whole on fresh capture sets, and only an exact match counts" | the derivation record is also exact-matched | L11 calls the deliverables "the eight settlement reports and the record"; the record is a separate noun; oracle record unchanged |

Result: no literal reading of an edited sentence makes the oracle lose a point.
