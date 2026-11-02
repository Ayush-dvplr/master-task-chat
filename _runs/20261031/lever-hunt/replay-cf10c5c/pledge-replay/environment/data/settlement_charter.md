# Settlement charter

The desk closes one settlement window at a time. A window is named by its window
identifier and is described by the directive revisions issued for it.

| setting | value |
| --- | --- |
| window_id | W-2026Q2 |
| directive_source | window_directives.jsonl |
| horizon_field | settlement_cutoff |
| settlement_cutoff | 2026-06-19T12:00:00+00:00 |
| boundary_notice_hours | 48 |
| home_zone | ZN-BLR |
| canonical_order | ascending pledge identifier compared as text |
| instant_form | ISO 8601 with a +00:00 offset and whole seconds |

A directive revision is live when its issue instant and its logging instant both
fall at or before the settlement cutoff and no retraction notice names it. The
highest live revision for the window carries the window opening instant, the
window closing instant, the grace pool in minutes and the mode directive.

The window interval is half open. An instant at the opening belongs to the
window and an instant at the closing belongs to the next window.

A pledge sits on the docket when its governing due instant falls inside the
window interval. The origin instant of a pledge has no bearing on membership.
A pledge whose governing due instant falls outside the window interval but
within the boundary notice band on either side is filed as a boundary notice so
that the exclusion is recorded. The band is measured in hours from the window
opening instant and from the window closing instant.

Pledges reach the register in three ways. Register entries are filed directly.
Recurring commitments are expanded into period instances. Prerequisite edges can
name a pledge that sits in an earlier or later window, and such a pledge keeps
its own effective instant even though it never joins the docket.

The settlement bar is exact. An artifact counts only when every field matches the
contract, every identifier resolves to the same holder the corpus names, every
instant carries whole seconds in the declared form and every minute figure is the
exact integer the rules produce. A figure that is close is a figure that is wrong.
