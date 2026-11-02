# Entitlement ceilings

Sections of this document are amended by `errata_2031-07.md`.

## 1. The governing ceiling

`entitlement_ceilings_p*.csv` declares a ceiling for a customer id and an
epoch sequence. `unit` is `wafers` or `lots`. `effective_local` is a wall
stamp of the site in `declaring_site` and pairs with `fold`.

The governing ceiling of a request is taken from the admitted rows for the
canonical id and the epoch of that request whose effective instant is at or
before the start of the cycle of the request, keeping the row with the
greatest effective instant, ties broken by the greater `revision_seq`. The
figure then converts at the equivalent conversion stage along the walk of the
request and is reported as `ceiling_equiv`.

## 2. Effect

The ceiling limits what a request may claim in a cycle. It is a ceiling on
the claim and never a ceiling on a grant or on a committed minimum. A
governing ceiling of zero gives a claim of zero and the reason `CAP_ZERO`.
Where no row is in force the claim is not limited and `ceiling_equiv` is
reported as zero with no reason.

Ceilings that bind are tallied as `ceiling_binding` and ceilings of zero as
`ceiling_zero`.
