# emberforge-vault-settlement: note for the PL (P12 r3)

Fixed (both v4 fails were real):
- Oracle: a workshop's allocated units are now the sum over all its requisitions, as record_shapes.md says. Before, it kept only the last one.
- Fixture: no graded season had a workshop with two requisitions, so the wrong oracle still scored 1.0. The 24-requisition mixed season now has one workshop filing a second request. It sits inside a composed season, not a new isolated check, and no weight changed. An engine that drops the sum now loses 10 of 101 points; the oracle loses nothing.

Kept minor:
- JD-16 warn on R10 (network use). A test can block the network but cannot reliably see an attempt (no strace in the verifier image, and an import scan is easy to dodge). The judge reading the source stays the better owner. It is a warn only.

False positives: none. Questions: none.
