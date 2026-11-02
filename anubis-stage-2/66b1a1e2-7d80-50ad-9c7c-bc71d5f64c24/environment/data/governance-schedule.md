# The escalation and treasury schedule

The governance file named by the index is a PDF document. It is the only source
of the settling parameters, the series class ranks and the office conversion
rates. Plain text digests of the same figures exist; they are lower authority
copies and are never read for a computation (authority-and-audit.md).

## Reading the document

The document has several pages. Each page has one content stream compressed
with the Flate method. A page draws text runs at absolute positions: each run
sets its position with a text matrix `1 0 0 1 x y Tm` and then shows a string.
The string of a run is a literal string `( ... )`, in which a backslash escapes
the next character and `\ddd` is an octal character code, or a hexadecimal
string `< ... >` holding two hex digits per character, or an array shown with
`TJ`, whose strings are concatenated in order while the numbers between them
are spacing adjustments that add no text. Runs are drawn in no particular
order.

A table row is the set of runs on one page that share one y coordinate, read in
increasing x, and rows are read from the top of the page down, page after page.
Every page ends with a footer row `page i of n`, which is not table content.
The document starts with a title row. Each table starts with a caption row
`Table N. Name` followed by a header row; when a table runs onto the next page
the caption is repeated with ` (continued)` appended, followed again by the
header row, and the rows after it continue the same table.

## Tables

| Caption name | Columns |
|---|---|
| Revision register | revision, approved on, status |
| Settling parameters | revision, buffer min, quantum min, round cap, pin rank, default rank |
| Series class ranks | class, revision, rank |
| Office conversion | office, revision, basis points |

A revision whose status is `approved` is in force from its approval; a revision
whose status is `withdrawn` or `draft` never is.

## The effective revision

The effective revision is the smaller of the store's `policy_revision` and the
greatest approved revision in the revision register. The usable revisions are
the approved revisions that are less than or equal to the effective revision.

Every figure taken from the other three tables is read from the row of the
greatest usable revision that has a row for the thing looked up. Rows of
withdrawn and draft revisions, and rows of approved revisions above the
effective revision, are never read.

Worked example. Revisions 3, 4 and 6 are approved, 5 is withdrawn and 7 is a
draft, and the store declares `policy_revision` 7. The greatest approved
revision is 6, so the effective revision is min(7, 6) = 6 and the usable
revisions are 3, 4 and 6. A class with rows for revisions 3, 4 and 5 takes its
revision 4 rank: revision 5 is withdrawn, and there is no revision 6 row. A
class with no row at all in a usable revision has no listed rank and takes the
default rank of the settling parameters.

## What the tables decide

The settling parameters row gives the travel buffer in minutes, the deferral
quantum in minutes, the round cap of the settling loop, the pin rank and the
default rank (conflicts-and-settling.md). The class rank table gives the
escalation rank of each series class. The office conversion table gives, per
office, the basis points used to convert chargeback amounts into the office
ledger (chargeback.md); an office without a usable row converts at 10000 basis
points.
