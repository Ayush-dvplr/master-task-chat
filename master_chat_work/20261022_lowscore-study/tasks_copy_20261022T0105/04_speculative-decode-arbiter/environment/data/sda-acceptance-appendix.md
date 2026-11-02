# SDA acceptance appendix

Worked examples of the acceptance algebra of the replay specification, section
5, section 6 and section 10. The tables here restate rules that document
defines; where they appear to differ, the specification wins.

## The alias table

The shipped alias table maps every token identifier to a class identifier. Most
tokens sit alone in their class. A documented minority share a class with one
other token, so two positions can agree without carrying the same token
identifier. The void token `TKFF` maps to the void class `CZZ`, and `CZZ`
agrees with nothing at all.

Read the table as shipped rather than assuming the pattern. A replay that
derives a class from the token identifier by arithmetic rather than by looking
it up will disagree with the table on exactly the shared entries, which is the
minority that decides most of the interesting prefixes.

## Worked example one, a prefix that ends on a class disagreement

A window with a repaired `k_requested` of 5 and a policy K of 5. The draft and
verdict vectors, and the classes each resolves to.

    position   0      1      2      3      4
    draft      TK04   TK11   TK2C   TK30   TK42
    class      C040   C100   C2C0   C300   C420
    verdict    TK04   TK10   TK2C   TK56   TK42
    class      C040   C100   C2C0   C560   C420

Position 0 agrees. Position 1 agrees, because `TK11` and `TK10` share the class
`C100` even though the identifiers differ. Position 2 agrees. Position 3
disagrees. The agreed prefix is therefore 3.

The agreed prefix stops at the first disagreement and never resumes, so
position 4 agreeing does not extend it.

## Worked example two, the void class

The same window, with a draft vector carrying an identifier absent from the
alias table.

    position   0      1      2
    draft      TK04   TKZZ   TK2C
    class      C040   CZZ    C2C0
    verdict    TK04   TKFF   TK2C
    class      C040   CZZ    C2C0

Position 0 agrees. Position 1 carries the void class on both sides, and the
void class agrees with nothing including itself, so position 1 disagrees. The
agreed prefix is 1.

## Worked example three, the policy truncation

A window whose repaired draft vector holds 6 tokens, replayed at a policy K of
4. Only the leading 4 positions take part. The window drafted 4 tokens, not 6,
and its agreed prefix is computed over those 4 positions alone. Tokens at
positions 4 and 5 are not drafted under this policy and belong to no terminal
class.

## Worked example four, the span bound

The window of example one, with an agreed prefix of 3 and 5 tokens drafted. Its
lease was granted at tick 40 and its effective expiry is tick 42, so its span
is 2.

The agreed prefix is resolved first, giving 3. The span then bounds how many of
those agreed tokens are accepted, giving 2. The remaining agreed token is
expired. Every drafted token after the agreed prefix is rejected, giving 2.

    accepted   2
    expired    1
    rejected   2
    reclaimed  0
    voided     0
    drafted    5

The five classes sum to 5, which is the number drafted, so the residual is 0.

Applying the span before the agreed prefix would truncate the vectors to 2
positions, find an agreed prefix of 2, and report 2 accepted, 0 expired and 0
rejected against 2 drafted. Both readings are self consistent and only one
matches the specification.

## Worked example four b, a verdict the target never finished

A window drafting 5 tokens whose recorded verdict vector holds only 3. Repair
`R04` extends the verdict to 5 positions with the void token, and positions 3
and 4 are positions the target never answered.

    position   0      1      2      3      4
    draft      TK04   TK11   TK2C   TK30   TK42
    verdict    TK04   TK10   TK56   TKFF   TKFF

Positions 0 and 1 agree and position 2 disagrees, so the agreed prefix is 2.
With a span of 4, both agreed tokens are accepted. Positions 3 and 4 are voided
because the target answered neither. Position 2 is the only rejection.

    accepted   2
    expired    0
    rejected   1
    reclaimed  0
    voided     2
    drafted    5

A replay that records `R04` and then treats the extended positions as ordinary
disagreements reports 3 rejected and 0 voided, which still sums to 5 and is
still wrong.

## Worked example five, the moving average across three windows

A stream whose seed K is 3, with three windows whose agreement ratios come out
at 1.0, 1.0 and 0.25. The moving average begins at 0.5 and `L` is `2 / 26`,
which is `0.076923...` carried at full precision.

    window 1   policy K 3   ratio 1.00   alpha 0.538461...
    window 2   policy K 3   ratio 1.00   alpha 0.573964...
    window 3   policy K 3   ratio 0.25   alpha 0.549044...

After window 1 alpha is not above 0.85 and not below 0.30, so the policy K
carried to window 2 is unchanged at 3. The same holds after window 2 and after
window 3. No intermediate alpha is rounded; the four decimal place rendering
applies only when a ratio reaches an artifact.

## Worked example six, a seed recalibration that changes the schedule

The same stream, whose three windows drafted 3, 3 and 4 tokens and agreed on 3,
3 and 1 of them. Its pooled acceptance ratio is `7 / 10`, which is 0.7. That
lies inside the band, so the seed K is unchanged, the next pass reproduces the
same schedule, and the stream converged after one pass.

Had the pooled ratio come out above 0.85, the seed K would have risen to 4 and
a second pass would have run at the new seed. A higher policy K draws more
tokens into each window, which usually lowers the pooled ratio, so the seed and
the ratio move against each other and a stream can take several passes to
settle. A stream still moving after six passes stops at six and is recorded as
not converged.
