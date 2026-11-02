# Provenance rules

Sections of this document are amended by `errata_2031-07.md`.

## 1. One request, several rows

A request is identified by a customer and a site, not by a reference string.
Admitted rows with the same canonical identity and the same site describe one
request when their governing effective instants lie within the collapse window
declared in `derivation_policy.ini` of the earliest effective instant among
them. Grouping starts from the earliest remaining row and admits every row
within the window of that row, then repeats. Rows outside the window describe
a different request, even when the customer and site agree. Each row is
resolved at its own effective instant before grouping.

Within a single source two rows that carry the same `request_ref` and an
identical payload are one row. Where the payload differs the row recorded
later governs, and where the recorded instants agree the greater reference
text governs. These are tallied as `duplicate_identical` and
`duplicate_conflicting`. Rows absorbed by grouping across sources are tallied
as `cross_source_collapsed`.

## 2. Field by field precedence

Each field of a request takes its value from the source that governs that
field, and the governing source can differ from field to field. The table in
`source_declarations.properties` states, for each field and each side of the
cutover, which source governs. The cutover is the start of cycle `C14` at the
site of the request. The side of the cutover is decided by the earliest
effective instant among the admitted rows of the request, and no later
correction moves a request across the cutover.

Where the governing source carries no row for a request, the field takes the
value of the next source that does, in the order order book, contract
registry, legacy intake. The legacy intake is the lowest ranked source for
every field, so it governs only a request that no other source carries. Where
no admitted source states a node the request carries the reason
`NODE_NOT_STATED`. The reference reported for a request is the one on the
highest ranked source present, in the same order.

## 3. The quantity before the cutover

The precedence table carries no entry for the quantity of a request whose
earliest effective instant falls before the cutover. Three readings are
consistent with the rest of these documents: the order book governs, the
contract registry governs, or the row recorded later governs.

`governance_observations.log` holds settled divergences from the periods
before the horizon. Each line names the site, the period, the figure each
source carried, which of the two rows was recorded later, and the source that
governed. Exactly one of the three readings reproduces every settled line.
Read the log, keep the reading that survives, and apply it to this horizon.
Report the reading you settled on in `policy_audit.json` under `withheld` as
`quantity_governed_before_cutover`, spelled `order_book`, `contract_registry`
or `later_recorded`.
