"""Redesign r4 data edits (run once on the r2 shipped data from bundle_pre_r4; writes into BUNDLE).

program.ini [grants]; site_allowances.tsv draws_from column (depth-1 pairs) and new comment; rate_cards.xml
comment (credited relief ticks); schema.md sections 1, 6, 7, 8.1; export_manifest.tsv site_allowances line.
usage: python3 -B r4_data.py
"""
from __future__ import annotations

import csv
from pathlib import Path

WORK = Path(__file__).resolve().parent
SRC = WORK / "bundle_pre_r4" / "environment" / "data"
DST = WORK.parent.parent / "district-heat-flex-procurement" / "environment" / "data"
CLAIM, MINIMUM, PAIRS_PER_REGION = 40, 25, 15

ALLOWANCE_COMMENT = """# Season relief allowance of each site, in energy ticks; one row per site_id of sites.csv.
# draws_from is blank or names another site_id of this file. A site whose draws_from is blank draws on
# its own allowance_ticks. A site whose draws_from names another site draws on the allowance that the
# named site draws on, and its own allowance_ticks figure carries no rule. No draws_from chain returns
# to a site already on it.
# An allowance is drawn by the events of the season, which reach it one at a time in the order of the
# instants at which they start (dispatch_start in events.json), events that start at the same instant
# following the programme conventions. When an event is reached, what remains of an allowance is its
# allowance_ticks less the relief ticks, over all intervals, of the offers chosen in the events reached
# before it at every site that draws on it. An offer whose relief ticks over all intervals are more than
# what remains of the allowance its site draws on when its event is reached is not a candidate offer.
"""


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old[:70]
    return text.replace(old, new)


def program_ini() -> None:
    text = (SRC / "program.ini").read_text(encoding="utf-8")
    text = replace_once(text, "\n[export]\n", f"\n[grants]\nclaim_cents_per_weight = {CLAIM}\n"
                        f"minimum_grant_cents = {MINIMUM}\n\n[export]\n")
    (DST / "program.ini").write_text(text, encoding="utf-8")


def site_allowances() -> None:
    lines = (SRC / "site_allowances.tsv").read_text(encoding="utf-8").splitlines()
    body = [x.split("\t") for x in lines if x and not x.startswith("#")]
    assert body[0] == ["site_id", "allowance_ticks"]
    rows = body[1:]
    region: dict[str, str] = {}
    with (SRC / "sites.csv").open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            region.setdefault(r["site_id"], r["region_code"][:1])
    by_region: dict[str, list[list[str]]] = {}
    for r in rows:
        by_region.setdefault(region[r[0]], []).append(r)
    draws: dict[str, str] = {}
    for code in sorted(by_region):
        group = sorted(by_region[code])[: 2 * PAIRS_PER_REGION]
        for holder, follower in zip(group[0::2], group[1::2]):
            draws[follower[0]] = holder[0]
            holder[1] = str((int(holder[1]) + int(follower[1])) * 6 // 10)
            follower[1] = "0"
    out = ALLOWANCE_COMMENT + "site_id\tallowance_ticks\tdraws_from\n"
    out += "".join(f"{r[0]}\t{r[1]}\t{draws.get(r[0], '')}\n" for r in rows)
    (DST / "site_allowances.tsv").write_text(out, encoding="utf-8")
    manifest = (SRC / "export_manifest.tsv").read_text(encoding="utf-8").splitlines()
    total = sum(int(r[1]) for r in rows)
    fixed = []
    for line in manifest:
        if line.startswith("site_allowances.tsv\t"):
            parts = line.split("\t")
            assert parts[1] == str(len(rows))
            line = f"site_allowances.tsv\t{len(rows)}\tallowance_ticks\t{total}"
        fixed.append(line)
    (DST / "export_manifest.tsv").write_text("\n".join(fixed) + "\n", encoding="utf-8")


def rate_cards() -> None:
    text = (SRC / "rate_cards.xml").read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  amounts. An interval amount is the offer's relief ticks in that interval times wh_per_tick, times\n"
        "  the effective rate of the offer's site row, divided by 1000 times millicents_per_cent, rounded\n"
        "  half to even to whole cents.\n",
        "  amounts. An interval amount is the offer's credited relief ticks in that interval times\n"
        "  wh_per_tick, times the effective rate of the offer's site row, divided by 1000 times\n"
        "  millicents_per_cent, rounded half to even to whole cents.\n")
    (DST / "rate_cards.xml").write_text(text, encoding="utf-8")


def schema() -> None:
    text = (SRC / "schema.md").read_text(encoding="utf-8")
    text = replace_once(
        text,
        "  - `[export]` belongs to the export tool",
        "  - `[grants]`: `claim_cents_per_weight` and `minimum_grant_cents`, integers in cents;\n"
        "    section 7 says how they apply.\n"
        "  - `[export]` belongs to the export tool")
    text = replace_once(
        text,
        "  other line is the header `site_id`, `allowance_ticks`, and every line after it is a\n"
        "  data row, one per `site_id` of `sites.csv`. The comment at the top of the file says how\n"
        "  an allowance is drawn.\n",
        "  other line is the header `site_id`, `allowance_ticks`, `draws_from`, and every line after\n"
        "  it is a data row, one per `site_id` of `sites.csv`. The comment at the top of the file\n"
        "  says how an allowance is drawn and which allowance a site draws on.\n")
    text = replace_once(
        text,
        "site row; the comment at the top of `rate_cards.xml` defines it. Credits are separate\n"
        "from bid costs and from grants.\n",
        "site row; the comment at the top of `rate_cards.xml` defines it. Credits are separate\n"
        "from bid costs and from grants. An offer's credited relief ticks in an interval are its\n"
        "relief ticks in that interval less its recovery ticks in that same interval, or 0 when\n"
        "its recovery ticks there are the larger.\n")
    text = replace_once(
        text,
        "pool, then the apportionment below. The funded pool F is the grant pool minus the\n"
        "event-region's credit cents (the sum of the credits of its chosen offers), or 0 when that\n"
        "difference is negative.\n",
        "pool, then the apportionment below. The funded pool F is the grant pool plus the carried\n"
        "cents, minus the event-region's credit cents (the sum of the credits of its chosen offers),\n"
        "or 0 when that is negative. The carried cents of an event-region are the unallocated cents\n"
        "of the same region in the event reached just before it in season order (the order the\n"
        "`site_allowances.tsv` comment sets); the first event of a region carries nothing.\n")
    text = replace_once(
        text,
        "When there are no recipients, the whole funded pool is unallocated. For every other\n"
        "event-region F is shared by largest remainder: every beneficiary with a positive weight\n"
        "w first gets floor(F times w / W) cents, and its remainder is (F times w) mod W. The cents left over\n"
        "are handed out one cent at a time to beneficiaries in decreasing order of remainder;\n"
        "equal remainders follow the programme conventions. The allocated cents are the sum\n"
        "handed to beneficiaries, and the unallocated cents are F minus the allocated cents.\n"
        "Beneficiaries with weight 0 receive nothing and are not listed.\n"
        "\n"
        "The residual cents of a pool are the cents of its funded pool handed out by remainder. A\n"
        "pool has a residual tie when two or more of its beneficiaries with positive weight share\n"
        "the same non-zero remainder.\n",
        "`program.ini` section `[grants]` gives `claim_cents_per_weight` and `minimum_grant_cents`.\n"
        "The claim of a beneficiary is its weight times `claim_cents_per_weight`.\n"
        "\n"
        "When there are no recipients, or W is 0, the whole funded pool is unallocated. When the\n"
        "claims of the beneficiaries with a positive weight add up to F or less, each of them\n"
        "receives its claim and the rest of F is unallocated. Otherwise F is shared by largest\n"
        "remainder: every beneficiary with a positive weight w first gets floor(F times w / W)\n"
        "cents, and its remainder is (F times w) mod W. The cents left over are handed out one cent\n"
        "at a time to beneficiaries in decreasing order of remainder; equal remainders follow the\n"
        "programme conventions. A beneficiary whose share is less than `minimum_grant_cents`\n"
        "receives nothing. When some beneficiaries receive nothing this way and others do not,\n"
        "every cent of F is shared again, in proportion to weight by largest remainder, across\n"
        "only the beneficiaries whose share was `minimum_grant_cents` or more, with W now the sum\n"
        "of their weights; each of them receives this second share. When every beneficiary\n"
        "receives nothing this way, the whole of F is unallocated.\n"
        "\n"
        "The allocated cents are the sum handed to beneficiaries, and the unallocated cents are F\n"
        "minus the allocated cents. Beneficiaries with weight 0 receive nothing and are not\n"
        "listed; a beneficiary with a positive weight that receives nothing is listed with 0 cents.\n"
        "\n"
        "The residual cents of a pool are the cents handed out by remainder in its last\n"
        "largest-remainder share. A pool has a residual tie when two or more of the beneficiaries\n"
        "in that share have the same non-zero remainder. A pool whose claims are paid, and a pool\n"
        "that is unallocated because it has no recipients or W is 0, has no residual cents and no\n"
        "residual tie.\n")
    text = replace_once(
        text,
        "  - `grants`: `{beneficiary_id, cents}` objects for beneficiaries with positive weight,\n"
        "    ascending by `beneficiary_id`; empty when the pool is unallocated\n",
        "  - `grants`: one `{beneficiary_id, cents}` object for every beneficiary with a positive\n"
        "    weight, ascending by `beneficiary_id`\n")
    (DST / "schema.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    program_ini()
    site_allowances()
    rate_cards()
    schema()
    print("r4 data edits written")
