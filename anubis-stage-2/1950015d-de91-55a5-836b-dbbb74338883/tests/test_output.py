"""Deterministic reward function for the LedgerPort settlement task."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import pwd
import random
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import zipfile
import zlib
from bisect import bisect_right
from datetime import date, datetime, timedelta
from decimal import (ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN,
                     ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal)
from pathlib import Path

from rewardkit import criteria, criterion



# ldg_contract
CONTRACT = """# Settlement normalization contract

This directory is the fourth quarter settlement drop for the LedgerPort
distribution network. It holds exactly 100 files. Thirty two of them are
transaction feeds; the other sixty eight are reference registries, policy
registers and published appendices. No file is optional and no file is
complete on its own: every registry is cut into disjoint shards, and a shard
holds the only copy of the rows it carries.

A file is a transaction feed if and only if `source_profiles` in
`postal_region_supplement.yaml` names it. Everything else is reference
material and never contributes a settlement record, however much it looks
like a transaction export.

## 1. Identifier canonical form

Every identifier (`event_id`, `customer_id`, `sku`, `warehouse`, `terminal`,
`ref_event`, `legacy_code`, `current_code`) is reduced to its canonical form
before it is compared to anything:

1. map every character through the homoglyph table in
   `code_crosswalk_overrides.ini`,
2. strip surrounding whitespace and upper case the result,
3. drop every character that is not A to Z, 0 to 9 or a hyphen,
4. split at the first hyphen and strip leading zeros from the part after it,
5. rejoin as `PREFIX-BODY`.

An identifier with no hyphen keeps the form reached at step 3.

## 2. Reference registries

Each registry below is spread over several files. The shards are disjoint by
key, so the full registry is the concatenation of every shard. Column names
are identical in every shard whatever the file format, except that a fixed
width file writes them in upper case.

| registry | key | columns |
| --- | --- | --- |
| parties | customer_id | customer_id, valid_from, valid_to, segment, postal_code |
| postal regions | postal_prefix | postal_prefix, valid_from, valid_to, region |
| items | sku | sku, valid_from, valid_to, category, active |
| price book | sku, version_id | sku, version_id, valid_from, valid_to, list_price_minor, currency |
| warehouses | warehouse | warehouse, valid_from, valid_to, postal_code |
| terminals | terminal | terminal, valid_from, valid_to, channel_group, utc_offset_minutes |
| fx rates | rate_date, currency, quote_source | rate_date, currency, quote_source, usd_rate |
| fiscal calendar | calendar_date, region, variant | calendar_date, region, variant, fiscal_week |
| code crosswalk | legacy_code, code_kind | legacy_code, code_kind, current_code |

Every registry except the crosswalk and the fx and calendar tables is
effective dated. A lookup for day D returns the row whose
`valid_from <= D` and `valid_to > D`. The window is half open at the upper
end; a row whose `valid_to` equals D does not cover D. Rows never overlap, so
at most one row can match.

The crosswalk maps a retired code to the code in use now. Look a code up in
the crosswalk after canonicalising it; if the crosswalk has no entry, the
canonical code is already current. Resolution is a single hop. The crosswalk
also publishes retired carrier codes under a `code_kind` of `carrier`; no step
of the chain looks a carrier code up, and a `current_code` reached through a
carrier row is a coincidence rather than a mapping.

## 2a. Container conventions

The same table is published in nineteen container formats. Whatever the
container, the column names are the ones in the tables above and the first row
is the header.

| container | where the rows are |
| --- | --- |
| csv, tsv | header row, then one row per line |
| txt | fixed width columns; the header line gives the column starts and the column names in upper case |
| jsonl | one JSON object per line |
| json | a `rows` array of objects, with the order in `columns` |
| xml | one `row` element per row, one child element per column |
| parquet | one column per field |
| db | a table named `lines` |
| xlsx | a sheet named `lines` |
| docx | the table at the end of the document |
| pdf | one line per row, columns separated by a space, a vertical bar and a space |
| md | a pipe table whose header row names the columns |
| html | a `table` element with a header row |
| log | one line of `key=value` pairs; a space inside a value is written as a non breaking space and a bare hyphen means empty |
| ini | one `row.N` section per row |
| toml | an array of tables named `lines` |
| yaml | a list under the key `lines` |
| mbox | one message per row, the columns written as `key: value` lines in the body |
| ics | one `VEVENT` per row, the columns written as `X-` properties with hyphens in place of underscores |

Three habits run through the text containers. A line whose first character is
a number sign is a comment and a blank line is filler; both appear inside the
body of a file and not only at the top. In a `jsonl` file an object whose only
key is `_note` is the same kind of filler. And a published text file may start
with a byte order mark, so the first column name has to be cleaned before it
is compared.

## 3. Reading a feed

`source_profiles` in `postal_region_supplement.yaml` gives, for each feed,
its `container` format, its text `encoding`, its `decimal_style`, its
`date_style`, its `utc_offset_minutes`, its `id_style` and whether it writes
`parenthesised_negatives`. Every feed carries the same twelve columns under
the same names, whatever the container:

`event_id, event_ts, customer_id, sku, warehouse, terminal, kind, quantity,
unit_price, currency, revision, ref_event`

In a workbook the rows live on the sheet named `lines`; in a database they
live in the table named `lines`; in XML each row is a `row` element; in a log
each line is a sequence of `key=value` pairs where a space inside a value is
written as a non breaking space; in the fixed width text files the column
widths are given by the header line.

`event_ts` is a local wall clock reading in the feed's own zone. Its written
form follows `date_style`:

| date_style | form |
| --- | --- |
| iso | YYYY-MM-DD HH:MM:SS |
| us_slash | MM/DD/YYYY HH:MM:SS |
| eu_dot | DD.MM.YYYY HH:MM:SS |
| epoch_s | whole seconds since 1970-01-01 00:00:00 |
| epoch_ms | whole milliseconds since 1970-01-01 00:00:00 |
| excel_serial | days since 1899-12-30, fractional part is the time of day |

`unit_price` is the price of one unit in major currency units. With
`decimal_style` of `point` the integer part carries no group separator and the
fraction follows a full stop. With `comma` the integer part is grouped with
full stops and the fraction follows a comma. The number of fraction digits is
the currency's minor unit exponent, so a JPY price carries none. A price
wrapped in round brackets is still a magnitude: the sign of a record comes
from its `kind` and never from the way the price is written.

`quantity` is a whole number written in digits.

## 4. Building one record

Work through these steps in order and stop at the first one that rejects the
row. The rejection code of a row is the code of the step that stopped it.

1. `MALFORMED_ROW` when `event_id`, `kind`, `currency` or `unit_price` is
   empty or cannot be read as its declared type, or when `event_ts` is not a
   readable timestamp in the feed's `date_style`.
2. `NON_NUMERIC_QUANTITY` when `quantity` is empty or is not a whole
   number written in digits.
3. Subtract `utc_offset_minutes` from `event_ts` to reach UTC. The date of
   that UTC instant is the capture date. For `kind` of `sale` or `refund`,
   canonicalise `terminal`, resolve it through the crosswalk, and look the
   result up in the terminal registry **on the capture date**. A terminal that
   resolves to no row is `UNKNOWN_TERMINAL`. The row's channel group and the
   terminal's own `utc_offset_minutes` come from that lookup. For `kind` of
   `fee` or `credit` there is no terminal: the channel group is `contract` and
   the terminal offset is zero.
4. The posting date is the capture date, except when the channel group is
   `branch`. For a branch row, add the terminal's `utc_offset_minutes` to the
   UTC instant and take the date of the result. Every later lookup uses the
   posting date.
5. `OUT_OF_SCOPE` when the posting date falls outside the settlement window
   in `terminal_channel_map.ini`, or outside the feed's own window in
   `scope_windows` of `code_crosswalk_supplement.yaml` when it declares one.
   Both windows are half open.
6. `SUPERSEDED_SOURCE` when the revision log in `price_policy_notes.md`
   retires the feed from a date on or before the posting date.
7. `VOIDED` when the canonical `event_id` appears in the void register in
   `counterparty_notice_board.html`.
8. `UNKNOWN_CUSTOMER` when the canonical `customer_id` has no party row on
   the posting date. The row's segment and the customer postal code come from
   that lookup.
9. `UNKNOWN_SKU` when the canonical `sku`, resolved through the crosswalk,
   has no item row on the posting date, and `INACTIVE_SKU` when that row
   carries `active` of `N`. The row's category comes from that lookup.
10. For `sale` and `refund`, canonicalise `warehouse`, resolve it through the
    crosswalk and look it up on the posting date: no row is
    `UNKNOWN_WAREHOUSE`. The region prefix is the part of that warehouse's
    postal code before the hyphen. For `fee` and `credit` the region prefix
    comes from the customer postal code instead. The region is the postal
    region row for that prefix on the posting date, and a prefix with no row
    is also `UNKNOWN_WAREHOUSE`.
11. For `sale` and `refund`, `NO_PRICE_VERSION` when the price book holds no
    version for the resolved sku covering the posting date. The record's
    `price_list_version` is that version id. For `fee` and `credit` the
    record's `price_list_version` is the literal `n/a` and no lookup happens.
12. `NO_FX_RATE` when the currency is absent from the minor unit table in
    `price_tier_registry.yaml`, or when no rate is available. The rate is the
    `usd_rate` for the posting date, the record's currency and the quote
    source named in `fx_policy_register.toml`. When that date has no such
    quote, step back one calendar day at a time, up to the carry forward
    limit in the same file, and take the first quote found.
13. `NO_FISCAL_WEEK` when the fiscal calendar holds no row for the posting
    date, the record's region and the calendar variant named in
    `fiscal_calendar_policy.yaml`. The record's fiscal week is the
    `fiscal_week` of that row.

The native amount is held in the currency's minor units as a signed whole
number. For `sale` it is `quantity * unit_price`; for `refund` it is the
negative of that; for `fee` it is `unit_price` and for `credit` the negative
of `unit_price`, with `quantity` recorded as zero in both. `unit_price` is
converted to minor units by shifting it by the currency's minor unit
exponent.

The USD amount in cents is
`native_amount_minor / 10 ** minor_units * usd_rate * 100`, evaluated once at
full precision and rounded a single time to a whole number of cents using the
rounding mode named in `fx_policy_register.toml`. There is no intermediate
rounding. The mode is one of `half_even`, `half_up`, `half_down`, `floor`,
`ceiling`, `up` and `down`: `half_up` and `half_down` send an exact half away
from and toward zero, `floor` and `ceiling` round toward negative and positive
infinity, and `up` and `down` round away from and toward zero.

## 5. Resolving duplicates

Rows that reach this point are grouped by canonical `event_id`. A group of
more than one is a duplicate group. The surviving row is the one with the
lowest authority rank for its feed and its `kind`; ranks for `sale` and
`refund` are in `warehouse_registry.toml` and ranks for `fee` and `credit`
are in `terminal_offsets.ini`, and a lower number outranks a higher one. Ties
are broken by the higher `revision`, then by the earlier file name in
ASCII order, then by the earlier position inside the file. Every other row in
the group is rejected as `DUPLICATE_LOWER_AUTHORITY`.

## 6. Resolving reversals

The surviving rows are then ordered by posting date, then canonical
`event_id`, then file name, and walked once in that order. A row of `kind`
`credit` whose `ref_event` is not empty is a reversal. When its canonical
`ref_event` names a row that is still live at that point in the walk, both
rows leave the ledger and both are rejected as `REVERSED`. When it names no
live row, or names itself, only the reversal leaves the ledger and it is
rejected as `REVERSAL_ORPHAN`. A row is live from the start of the walk until
it leaves the ledger, so a row the walk has not reached yet is live, and a
row that has already left is not. A reversal that has already left the ledger
when the walk reaches it does nothing. A credit with an empty `ref_event` is an
ordinary record.

The rows that remain are the ledger. They keep the order of the walk, and
`ledger_index` is their one based position in it.

## 7. Deliverables

`normalized.jsonl` holds one ledger record per line in ledger order, written
as compact JSON with sorted keys and no spaces. Each record carries exactly
these seventeen fields:

`amount_usd_cents, category, channel_group, currency, customer_id, event_id,
fiscal_week, kind, ledger_index, native_amount_minor, posting_date,
price_list_version, quantity, region, segment, sku, source_file`

`source_file` is the feed's file name exactly as `source_profiles` lists it,
and `accepted_by_source` and `rejected_by_source` below are keyed by the same
names. `event_id` and `customer_id` carry the canonical form of section 1,
`sku` carries the code the crosswalk resolves it to, and `posting_date` is
written as YYYY-MM-DD.

`summary.json` carries `accepted_count`, `by_category`, `by_channel_group`,
`by_currency`, `by_kind`, `by_region`, `by_segment`, `net_units`,
`rejected_count`, `settlement_window` and `total_usd_cents`. Every `by_`
field maps the value of that field to the sum of `amount_usd_cents` over the
ledger, with the keys in ASCII order and absent keys left out.
`settlement_window` carries `end_exclusive` and `start`. `net_units` adds
`quantity` for `sale`, subtracts it for `refund` and ignores the other kinds.
`rejected_count` counts every rejection raised anywhere in the chain,
including the two raised by one reversal.

`data_quality.json` carries `accepted_by_source`, `duplicate_groups`,
`input_file_count`, `rejected_by_code`, `rejected_by_source`,
`reversal_orphans`, `reversed_pairs`, `scoped_sources` and
`superseded_sources`. `accepted_by_source` and `rejected_by_source` name
every feed, zero included. `rejected_by_code` leaves out a code that never
fired. `input_file_count` is the number of files this directory holds.
`scoped_sources` and `superseded_sources` are the sorted feed names the two
registers name.

`product_summary.json` carries `product_count` and `products`. `products`
holds one object per sku that reached the ledger, in ASCII order of sku, each
with `category`, `net_units`, `price_list_versions`, `record_count`, `sku`
and `total_usd_cents`. `category` is the category of that sku's first ledger
record and `price_list_versions` is the sorted set of the distinct
`price_list_version` values its records carry, the literal `n/a` included
when the sku has fee or credit records.

`region_<name>.json` and `segment_<name>.json` each carry the grouping field
itself, `by_category`, `by_channel_group`, `by_kind`, `customer_count`,
`net_units`, `record_count`, `top_customers` and `total_usd_cents`.
`top_customers` holds the five customers with the largest
`total_usd_cents` inside the group, highest first, ties broken by ASCII order
of `customer_id`, each written as an object with `customer_id` and
`total_usd_cents`. A group with fewer than five customers lists all of them.
The region files cover `central`, `east`, `north`, `south` and `west`; the
segment files cover `consumer`, `corporate`, `enterprise` and `smb`. A group
with no records still gets its file, with empty maps, empty
`top_customers`, and zero counts and totals.

Every JSON file is written with sorted keys, an indent of two spaces and one
closing newline. `normalized.jsonl` is compact: sorted keys, no space after a
separator, one record per line, one closing newline. Money is always a whole
number of USD cents and is always an integer, never a string and never a
float.

## 8. Reference appendix

The table below is this file's shard of the postal region registry.
"""


FEED_PROFILE_NOTE = (
    "source_profiles names every transaction feed in this drop. A file that "
    "does not appear here is reference material, even when its columns look "
    "like transaction columns."
)


SCOPE_NOTE = (
    "scope_windows narrows a feed to the half open window given. Rows whose "
    "posting date falls outside the window are out of scope; rows inside it "
    "are as authoritative as any other feed and still compete in the "
    "authority ladder."
)


VOID_NOTE = (
    "This board is the only register of voided settlement events. The board "
    "itself is not a transaction source."
)


REVISION_NOTE = (
    "The revision log retires a feed from a date. A row from a retired feed "
    "whose posting date is on or after that date is superseded; earlier rows "
    "from the same feed stand."
)


# ldg_manifest
REFERENCE_FILES = [
    ("party_master_core.csv", "customers", 0, 8, ""),
    ("party_master_delta.tsv", "customers", 1, 8, ""),
    ("party_master_archive.xlsx", "customers", 2, 8, ""),
    ("party_register.db", "customers", 3, 8, ""),
    ("party_segment_history.jsonl", "customers", 4, 8, ""),
    ("party_directory_appendix.pdf", "customers", 5, 8, ""),
    ("party_change_log.docx", "customers", 6, 8, ""),
    ("counterparty_notice_board.html", "customers", 7, 8, "voids"),
    ("postal_region_map.csv", "prefixes", 0, 8, ""),
    ("postal_region_delta.tsv", "prefixes", 1, 8, ""),
    ("postal_region_index.json", "prefixes", 2, 8, ""),
    ("postal_region_proposed.xml", "prefixes", 3, 8, ""),
    ("postal_region_supplement.yaml", "prefixes", 4, 8, "feed_profiles"),
    ("postal_zone_gazetteer.pdf", "prefixes", 5, 8, ""),
    ("postal_zone_handbook.docx", "prefixes", 6, 8, ""),
    ("settlement_contract.md", "prefixes", 7, 8, "contract"),
    ("item_master_core.csv", "skus", 0, 8, ""),
    ("item_master_extended.tsv", "skus", 1, 8, ""),
    ("item_master_snapshot.json", "skus", 2, 8, ""),
    ("item_master_history.parquet", "skus", 3, 8, ""),
    ("item_status_register.jsonl", "skus", 4, 8, ""),
    ("item_catalogue_appendix.pdf", "skus", 5, 8, ""),
    ("item_revision_notes.docx", "skus", 6, 8, ""),
    ("item_master_mirror.xlsx", "skus", 7, 8, ""),
    ("price_book_core.csv", "prices", 0, 10, ""),
    ("price_book_versions.jsonl", "prices", 1, 10, ""),
    ("price_book_2027_draft.xlsx", "prices", 2, 10, ""),
    ("price_book_segments.xml", "prices", 3, 10, ""),
    ("price_register.db", "prices", 4, 10, ""),
    ("price_book_appendix_a.pdf", "prices", 5, 10, ""),
    ("price_tier_registry.yaml", "prices", 6, 10, "money_policy"),
    ("legacy_pricing_appendix.md", "prices", 7, 10, ""),
    ("price_policy_notes.md", "prices", 8, 10, "revision_log"),
    ("price_board_extract.html", "prices", 9, 10, ""),
    ("warehouse_master.csv", "warehouses", 0, 7, ""),
    ("warehouse_registry.toml", "warehouses", 1, 7, "ladder_trade"),
    ("warehouse_history.parquet", "warehouses", 2, 7, ""),
    ("warehouse_relocations.docx", "warehouses", 3, 7, ""),
    ("warehouse_gazetteer.pdf", "warehouses", 4, 7, ""),
    ("warehouse_sites.toml", "warehouses", 5, 7, ""),
    ("warehouse_closures.ics", "warehouses", 6, 7, ""),
    ("terminal_master.csv", "terminals", 0, 7, ""),
    ("terminal_groups.tsv", "terminals", 1, 7, ""),
    ("terminal_history.jsonl", "terminals", 2, 7, ""),
    ("terminal_offsets.ini", "terminals", 3, 7, "ladder_memo"),
    ("terminal_channel_map.ini", "terminals", 4, 7, "window"),
    ("terminal_bulletin.pdf", "terminals", 5, 7, ""),
    ("terminal_decommission_log.docx", "terminals", 6, 7, ""),
    ("fx_rates_core.csv", "fx", 0, 8, ""),
    ("fx_rates_board.json", "fx", 1, 8, ""),
    ("fx_rates_quarterly.xlsx", "fx", 2, 8, ""),
    ("fx_rates_history.parquet", "fx", 3, 8, ""),
    ("fx_rates_supplement.xml", "fx", 4, 8, ""),
    ("fx_policy_register.toml", "fx", 5, 8, "fx_policy"),
    ("fx_rate_appendix.pdf", "fx", 6, 8, ""),
    ("fx_rate_commentary.docx", "fx", 7, 8, ""),
    ("fiscal_calendar_core.csv", "calendar", 0, 6, ""),
    ("fiscal_calendar_variants.json", "calendar", 1, 6, ""),
    ("fiscal_calendar_extract.xlsx", "calendar", 2, 6, ""),
    ("fiscal_calendar_notes.docx", "calendar", 3, 6, ""),
    ("fiscal_calendar_board.html", "calendar", 4, 6, ""),
    ("fiscal_calendar_policy.yaml", "calendar", 5, 6, "calendar_policy"),
    ("code_crosswalk_core.xml", "xwalk", 0, 6, ""),
    ("code_crosswalk.db", "xwalk", 1, 6, ""),
    ("code_crosswalk_legacy.txt", "xwalk", 2, 6, ""),
    ("code_crosswalk_notice.mbox", "xwalk", 3, 6, ""),
    ("code_crosswalk_supplement.yaml", "xwalk", 4, 6, "scope_registry"),
    ("code_crosswalk_overrides.ini", "xwalk", 5, 6, "identity_policy"),
]


DECOY_FILES = {
    "consolidated_settlement_extract_final.xlsx",
    "ledger_mirror_2026q4.parquet",
    "gl_posting_journal_v4.json",
    "archive_orders_2026.db",
    "dw_fact_sales_snapshot.tsv",
    "staging_dump_latest.jsonl",
    "regional_rollup_workbook.xlsx",
    "counterparty_notice_board.html",
    "postal_region_proposed.xml",
    "item_master_mirror.xlsx",
    "price_book_2027_draft.xlsx",
    "warehouse_closures.ics",
    "terminal_decommission_log.docx",
    "fx_rates_board.json",
    "code_crosswalk_notice.mbox",
}


CONTRACT_FILE = "settlement_contract.md"


def shard_of(key, count):
    """Stable, interpreter independent shard selector."""
    total = 0
    for ch in str(key):
        total = (total * 31 + ord(ch)) % 1000003
    return total % count


def split(rows, key_at, index, count):
    return [row for row in rows if shard_of(row[key_at], count) == index]


def split_round_robin(rows, key_at, index, count):
    """Every shard gets at least one key, which a hash cannot promise."""
    order = sorted({row[key_at] for row in rows})
    slot = {key: position % count for position, key in enumerate(order)}
    return [row for row in rows if slot[row[key_at]] == index]


# ldg_writers
CYRILLIC = {"A": "\u0410", "B": "\u0412", "E": "\u0415", "K": "\u041a",
            "M": "\u041c", "H": "\u041d", "P": "\u0420", "C": "\u0421",
            "T": "\u0422", "X": "\u0425"}


EXCEL_EPOCH = datetime(1899, 12, 30)


FEED_COLUMNS = ["event_id", "event_ts", "customer_id", "sku", "warehouse",
                "terminal", "kind", "quantity", "unit_price", "currency",
                "revision", "ref_event"]


MINOR = {"USD": 2, "EUR": 2, "GBP": 2, "CAD": 2, "CHF": 2, "AUD": 2,
         "JPY": 0, "CLP": 0, "ISK": 0, "KWD": 3, "BHD": 3, "TND": 3}


def _stable(text):
    total = 0
    for ch in str(text):
        total = (total * 131 + ord(ch)) % 1000003
    return total


def render_id(value, style, glyphs=CYRILLIC):
    if not value:
        return ""
    if style == "pad" and "-" in value:
        prefix, _, body = value.partition("-")
        return prefix + "-" + "0" * (1 + _stable(value) % 3) + body
    if style == "homoglyph" and _stable(value) % 5 < 2:
        out = []
        swapped = False
        for ch in value:
            if not swapped and ch in glyphs:
                out.append(glyphs[ch])
                swapped = True
            else:
                out.append(ch)
        return "".join(out)
    return value


def render_ts(ts, style):
    stamp = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    if style == "iso":
        return stamp.isoformat(sep=" ")
    if style == "epoch_s":
        return str(int((stamp - datetime(1970, 1, 1)).total_seconds()))
    if style == "epoch_ms":
        return str(int((stamp - datetime(1970, 1, 1)).total_seconds()) * 1000)
    if style == "excel_serial":
        delta = stamp - EXCEL_EPOCH
        return "%.8f" % (delta.days + delta.seconds / 86400.0)
    if style == "us_slash":
        return stamp.strftime("%m/%d/%Y %H:%M:%S")
    return stamp.strftime("%d.%m.%Y %H:%M:%S")


def render_money(minor_value, currency, decimal_style, paren, kind, minor=MINOR):
    places = minor.get(currency, 2)
    sign = "-" if minor_value < 0 else ""
    digits = str(abs(int(minor_value))).rjust(places + 1, "0")
    whole, frac = (digits[:-places], digits[-places:]) if places else (digits, "")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    if decimal_style == "comma":
        body = ".".join(groups) + ("," + frac if frac else "")
    else:
        body = "".join(groups) + ("." + frac if frac else "")
    if paren and kind in ("refund", "credit"):
        return "(" + body + ")"
    return sign + body


def feed_rows(name, rows, meta, minor=MINOR, glyphs=CYRILLIC):
    """Render one feed's logical rows into the twelve shipped string columns."""
    style = meta["id_style"]
    rid = lambda value: render_id(value, style, glyphs)  # noqa: E731
    out = []
    for row in rows:
        defect = row["defect"]
        kind = row["kind"]
        qty = row["quantity"]
        unit = row["unit_price_minor"]
        currency = row["currency"]
        quantity_text = str(qty)
        if defect == "qty_text":
            quantity_text = "two"
        elif defect == "qty_decimal":
            quantity_text = "%d.0" % qty
        if row.get("qty_defect") == "qty_text":
            quantity_text = "two"
        amount_text = render_money(unit, currency, meta["decimal"], meta["paren"], kind, minor)
        if defect == "bad_amount":
            amount_text = "N/A"
        stamp = render_ts(row["ts"], meta["date_style"])
        if defect == "bad_date":
            stamp = "0000-00-00 00:00:00"
        out.append([
            "" if defect == "blank_event" else rid(row["event_id"]),
            stamp,
            rid(row["customer"]),
            rid(row["sku"]),
            rid(row["warehouse"]),
            rid(row["terminal"]),
            "" if defect == "blank_kind" else kind,
            quantity_text,
            amount_text,
            currency,
            str(row["revision"]),
            rid(row["ref_event"]),
        ])
    return out


def _write(path, text, encoding="utf-8"):
    data = text.encode(encoding, errors="replace")
    with open(path, "wb") as handle:
        handle.write(data)


def write_delimited(path, header, rows, sep, encoding, preamble=()):
    buf = io.StringIO()
    for line in preamble:
        buf.write("# " + line + "\n")
    writer = csv.writer(buf, delimiter=sep, lineterminator="\n")
    writer.writerow(header)
    for index, row in enumerate(rows):
        if index and index % 701 == 0:
            buf.write("# block %d continues\n" % (index // 701))
        if index and index % 907 == 0:
            buf.write("\n")
        writer.writerow(row)
    _write(path, buf.getvalue(), encoding)


def write_jsonl(path, header, rows, encoding, preamble=()):
    lines = []
    for line in preamble:
        lines.append(json.dumps({"_note": line}, separators=(",", ":")))
    for index, row in enumerate(rows):
        if index and index % 653 == 0:
            lines.append(json.dumps({"_note": "block %d" % (index // 653)},
                                    separators=(",", ":")))
        lines.append(json.dumps(dict(zip(header, row)), separators=(",", ":")))
    _write(path, "\n".join(lines) + "\n", encoding)


def write_json(path, header, rows, encoding, meta=None):
    payload = {"meta": meta or {}, "columns": list(header),
               "rows": [dict(zip(header, row)) for row in rows]}
    _write(path, json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding)


def _xml_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def write_xml(path, header, rows, encoding, root="table", note=""):
    parts = ['<?xml version="1.0" encoding="utf-8"?>', "<%s>" % root]
    if note:
        parts.append("  <note>%s</note>" % _xml_escape(note))
    parts.append("  <rows>")
    for row in rows:
        fields = "".join("<%s>%s</%s>" % (h, _xml_escape(v), h)
                         for h, v in zip(header, row))
        parts.append("    <row>%s</row>" % fields)
    parts.append("  </rows>")
    parts.append("</%s>" % root)
    _write(path, "\n".join(parts) + "\n", encoding)


def write_html(path, header, rows, encoding, title="", note_lines=()):
    parts = ["<!DOCTYPE html>", '<html><head><meta charset="utf-8">',
             "<title>%s</title></head><body>" % _xml_escape(title),
             "<h1>%s</h1>" % _xml_escape(title)]
    for line in note_lines:
        parts.append("<p>%s</p>" % _xml_escape(line))
    parts.append("<table>")
    parts.append("<tr>" + "".join("<th>%s</th>" % _xml_escape(h) for h in header) + "</tr>")
    for row in rows:
        parts.append("<tr>" + "".join("<td>%s</td>" % _xml_escape(v) for v in row) + "</tr>")
    parts.append("</table></body></html>")
    _write(path, "\n".join(parts) + "\n", encoding)


def write_md(path, header, rows, encoding, prose=""):
    parts = [prose.rstrip(), "", "| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        parts.append("| " + " | ".join(str(v) for v in row) + " |")
    _write(path, "\n".join(parts) + "\n", encoding)


def write_fixed(path, header, rows, encoding, widths, preamble=()):
    parts = ["# " + line for line in preamble]
    parts.append("".join(h.upper().ljust(w) for h, w in zip(header, widths)))
    for index, row in enumerate(rows):
        if index and index % 743 == 0:
            parts.append("# page %d" % (index // 743))
        parts.append("".join(str(v)[:w].ljust(w) for v, w in zip(row, widths)))
    _write(path, "\n".join(parts) + "\n", encoding)


def write_log(path, header, rows, encoding, service="settlement"):
    parts = []
    for index, row in enumerate(rows):
        if index and index % 811 == 0:
            parts.append("# rotated log segment %d" % (index // 811))
        pairs = " ".join("%s=%s" % (h, str(v).replace(" ", "\u00a0") or "-")
                         for h, v in zip(header, row))
        level = "WARN" if index % 97 == 0 else "INFO"
        parts.append("%s %s seq=%d %s" % (level, service, index, pairs))
    _write(path, "\n".join(parts) + "\n", encoding)


def write_ini(path, header, rows, encoding, key_at=0, preamble=(), extra=()):
    parts = ["; " + line for line in preamble]
    for name, body in extra:
        parts.append("[%s]" % name)
        for key, value in body:
            parts.append("%s = %s" % (key, value))
        parts.append("")
    for index, row in enumerate(rows):
        parts.append("[row.%d]" % index)
        for h, v in zip(header, row):
            parts.append("%s = %s" % (h, v))
        parts.append("")
    _write(path, "\n".join(parts) + "\n", encoding)


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return '"%s"' % str(value).replace("\\", "\\\\").replace('"', '\\"')


def write_toml(path, header, rows, encoding, table="row", preamble=(), extra=()):
    parts = ["# " + line for line in preamble]
    for name, body in extra:
        parts.append("[%s]" % name)
        for key, value in body:
            parts.append('"%s" = %s' % (key, _toml_value(value)))
        parts.append("")
    for row in rows:
        parts.append("[[%s]]" % table)
        for h, v in zip(header, row):
            parts.append("%s = %s" % (h, _toml_value(v)))
        parts.append("")
    _write(path, "\n".join(parts) + "\n", encoding)


def _yaml_scalar(value):
    text = str(value)
    if text == "":
        return '""'
    if any(ch in text for ch in ":#{}[]&*!|>'\"%@`,") or text != text.strip():
        return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')
    return text


def write_yaml(path, header, rows, encoding, key="rows", preamble=(), extra=()):
    parts = ["# " + line for line in preamble]
    for name, body in extra:
        parts.append("%s:" % name)
        for sub, value in body:
            if isinstance(value, list):
                parts.append("  %s:" % sub)
                for item in value:
                    parts.append("    - %s" % _yaml_scalar(item))
            elif isinstance(value, dict):
                parts.append("  %s:" % sub)
                for k2 in sorted(value):
                    parts.append("    %s: %s" % (k2, _yaml_scalar(value[k2])))
            else:
                parts.append("  %s: %s" % (sub, _yaml_scalar(value)))
    parts.append("%s:" % key)
    for row in rows:
        first = True
        for h, v in zip(header, row):
            lead = "  - " if first else "    "
            parts.append("%s%s: %s" % (lead, h, _yaml_scalar(v)))
            first = False
    _write(path, "\n".join(parts) + "\n", encoding)


def write_sqlite(path, header, rows, table="records", extra=None):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE %s (%s)" % (table, ", ".join('"%s" TEXT' % h for h in header)))
    cur.executemany("INSERT INTO %s VALUES (%s)" % (table, ",".join("?" * len(header))),
                    [[str(v) for v in row] for row in rows])
    if extra:
        cur.execute("CREATE TABLE notes (key TEXT, value TEXT)")
        cur.executemany("INSERT INTO notes VALUES (?,?)", extra)
    conn.commit()
    cur.execute("VACUUM")
    conn.close()


def write_parquet(path, header, rows, note=""):
    import pyarrow
    import pyarrow.parquet as pq

    columns = {h: [str(row[i]) for row in rows] for i, h in enumerate(header)}
    table = pyarrow.table(columns, metadata={"note": note} if note else None)
    pq.write_table(table, path, compression="snappy", version="2.6")


def write_mbox(path, header, rows, encoding, subject="registry notice"):
    parts = []
    base = datetime(2026, 10, 1, 6, 0, 0)
    for index, row in enumerate(rows):
        when = base + timedelta(minutes=index * 7)
        parts.append("From registry@ledgerport.example %s" %
                     when.strftime("%a %b %d %H:%M:%S %Y"))
        parts.append("From: registry@ledgerport.example")
        parts.append("To: settlement@ledgerport.example")
        parts.append("Subject: %s %d" % (subject, index))
        parts.append("Date: %s" % when.strftime("%a, %d %b %Y %H:%M:%S +0000"))
        parts.append("Message-Id: <notice-%06d@ledgerport.example>" % index)
        parts.append("")
        for h, v in zip(header, row):
            parts.append("%s: %s" % (h, v))
        parts.append("")
    _write(path, "\n".join(parts) + "\n", encoding)


def write_ics(path, header, rows, encoding, calname="registry"):
    parts = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//ledgerport//settlement registry//EN",
             "X-WR-CALNAME:%s" % calname]
    for index, row in enumerate(rows):
        parts.append("BEGIN:VEVENT")
        parts.append("UID:reg-%06d@ledgerport.example" % index)
        parts.append("DTSTAMP:20261001T060000Z")
        parts.append("SUMMARY:%s" % row[0])
        for h, v in zip(header, row):
            parts.append("X-%s:%s" % (h.upper().replace("_", "-"), v))
        parts.append("END:VEVENT")
    parts.append("END:VCALENDAR")
    _write(path, "\n".join(parts) + "\n", encoding)


def _zip(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob in members:
            info = zipfile.ZipInfo(name, date_time=(2027, 1, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, blob)


def write_xlsx(path, sheets):
    """sheets: list of (sheet name, header, rows)."""
    content = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
               '<Default Extension="xml" ContentType="application/xml"/>',
               '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    for i in range(len(sheets)):
        content.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1))
    content.append("</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
    book = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    book_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    members = []
    for i, (name, header, rows) in enumerate(sheets, start=1):
        book.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_xml_escape(name), i, i))
        book_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate([header, *rows], start=1):
            cells = []
            for c, value in enumerate(row):
                ref = _col_ref(c) + str(r)
                cells.append('<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                             % (ref, _xml_escape(value)))
            out.append('<row r="%d">%s</row>' % (r, "".join(cells)))
        out.append("</sheetData></worksheet>")
        members.append(("xl/worksheets/sheet%d.xml" % i, "".join(out)))
    book.append("</sheets></workbook>")
    book_rels.append("</Relationships>")
    _zip(path, [
        ("[Content_Types].xml", "".join(content)),
        ("_rels/.rels", rels),
        ("xl/workbook.xml", "".join(book)),
        ("xl/_rels/workbook.xml.rels", "".join(book_rels)),
        *members,
    ])


def _col_ref(index):
    out = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def write_docx(path, paragraphs, header, rows):
    body = []
    for text in paragraphs:
        body.append('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % _xml_escape(text))
    cells = "".join('<w:tc><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                    % _xml_escape(h) for h in header)
    table = ['<w:tbl><w:tr>%s</w:tr>' % cells]
    for row in rows:
        cells = "".join('<w:tc><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                        % _xml_escape(v) for v in row)
        table.append("<w:tr>%s</w:tr>" % cells)
    table.append("</w:tbl>")
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>" + "".join(body) + "".join(table) +
                '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:body></w:document>')
    content = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
               '<Default Extension="xml" ContentType="application/xml"/>'
               '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
               "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>")
    _zip(path, [("[Content_Types].xml", content), ("_rels/.rels", rels),
                ("word/document.xml", document)])


def _pdf_escape(text):
    return (str(text).replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))


def write_pdf(path, title, intro, header, rows, per_page=58):
    lines = [title, ""]
    lines.extend(intro)
    lines.append("")
    lines.append(" | ".join(header))
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[title]]
    objects = {}
    page_ids = [4 + 2 * i for i in range(len(pages))]
    objects[1] = "<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                  % (" ".join("%d 0 R" % pid for pid in page_ids), len(pages)))
    objects[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    streams = {}
    for index, page in enumerate(pages):
        pid = page_ids[index]
        cid = pid + 1
        objects[pid] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                        "/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % cid)
        body = ["BT", "/F1 8 Tf", "10 TL", "36 756 Td"]
        for line in page:
            body.append("(%s) Tj T*" % _pdf_escape(line))
        body.append("ET")
        streams[cid] = zlib.compress("\n".join(body).encode("latin-1", errors="replace"))
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(set(list(objects) + list(streams))):
        offsets[num] = len(out)
        if num in objects:
            out += ("%d 0 obj\n%s\nendobj\n" % (num, objects[num])).encode("latin-1")
        else:
            blob = streams[num]
            out += ("%d 0 obj\n<< /Length %d /Filter /FlateDecode >>\nstream\n"
                    % (num, len(blob))).encode("latin-1")
            out += blob + b"\nendstream\nendobj\n"
    start = len(out)
    top = max(offsets) + 1
    out += ("xref\n0 %d\n" % top).encode("latin-1")
    out += b"0000000000 65535 f \n"
    for num in range(1, top):
        out += ("%010d 00000 n \n" % offsets.get(num, 0)).encode("latin-1")
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (top, start)).encode("latin-1")
    with open(path, "wb") as handle:
        handle.write(bytes(out))


# ldg_pipeline
MINOR_UNITS = {
    "USD": 2, "EUR": 2, "GBP": 2, "CAD": 2, "CHF": 2, "AUD": 2,
    "JPY": 0, "CLP": 0, "ISK": 0,
    "KWD": 3, "BHD": 3, "TND": 3,
}


HOMOGLYPHS = {
    "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K", "\u041c": "M",
    "\u041d": "H", "\u041e": "O", "\u0420": "P", "\u0421": "C", "\u0422": "T",
    "\u0425": "X",
}


GREEK_HOMOGLYPHS = {
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0397": "H", "\u039a": "K",
    "\u039c": "M", "\u039d": "N", "\u039f": "O", "\u03a1": "P", "\u03a4": "T",
    "\u03a7": "X",
}


KIND_SIGN = {"sale": 1, "refund": -1, "fee": 1, "credit": -1}


ROUNDERS = {
    "half_even": ROUND_HALF_EVEN, "half_up": ROUND_HALF_UP, "half_down": ROUND_HALF_DOWN,
    "floor": ROUND_FLOOR, "ceiling": ROUND_CEILING, "up": ROUND_UP, "down": ROUND_DOWN,
}


FX_CARRY_FORWARD_DAYS = 3


FX_QUOTE_SOURCE = "central"


FISCAL_CALENDAR_VARIANT = "retail454"


TOP_CUSTOMER_COUNT = 5


CANON_KEEP = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


def canon_id(raw, table=HOMOGLYPHS):
    text = "".join(table.get(ch, ch) for ch in str(raw or "")).strip().upper()
    text = "".join(ch for ch in text if ch in CANON_KEEP)
    if "-" not in text:
        return text
    prefix, _, body = text.partition("-")
    body = body.lstrip("0")
    return prefix + "-" + body


def policy(seed, feed_names, rules):
    rng = random.Random(seed ^ 0x5A5A5A5A)
    ladder = {}
    for kind in ("credit", "fee", "refund", "sale"):
        order = list(feed_names)
        rng.shuffle(order)
        for rank, name in enumerate(order, start=1):
            ladder.setdefault(name, {})[kind] = rank
    return {
        "authority": ladder,
        "scope": dict(rules["scope"]),
        "superseded": dict(rules["superseded"]),
        "fx_quote_source": rules["quote"],
        "fiscal_calendar_variant": rules["variant"],
        "fx_carry_forward_days": rules["carry"],
        "minor_units": dict(rules["minor_units"]),
        "rounding": rules["rounding"],
        "homoglyphs": dict(rules["homoglyphs"]),
    }


class Timeline:
    """Half-open effective-dated lookup: valid_from <= day < valid_to."""

    def __init__(self, rows, key_at=0, lo_at=1, hi_at=2):
        table = {}
        for row in rows:
            table.setdefault(row[key_at], []).append((row[lo_at], row[hi_at], row))
        self.table = {}
        for key, spans in table.items():
            spans.sort(key=lambda s: s[0])
            self.table[key] = ([s[0] for s in spans], spans)

    def at(self, key, day):
        entry = self.table.get(key)
        if entry is None:
            return None
        starts, spans = entry
        pos = bisect_right(starts, day) - 1
        if pos < 0:
            return None
        lo, hi, row = spans[pos]
        return row if lo <= day < hi else None


def _as_date(text):
    return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))


def run(corpus, pol):
    feeds = corpus["feeds"]
    window_lo, window_hi = corpus["window"]
    glyph_table = pol["homoglyphs"]
    rounding = ROUNDERS[pol["rounding"]]

    def canon(raw):
        return canon_id(raw, glyph_table)

    def keyed(rows):
        return [(canon(row[0]), *row[1:]) for row in rows]

    cust = Timeline(keyed(corpus["customers"]))
    pfx = Timeline(keyed(corpus["prefixes"]))
    sku = Timeline(keyed(corpus["skus"]))
    wh = Timeline(keyed(corpus["warehouses"]))
    tm = Timeline(keyed(corpus["terminals"]))
    price = {}
    for row in keyed(corpus["prices"]):
        price.setdefault(row[0], []).append(row)
    for spans in price.values():
        spans.sort(key=lambda s: s[2])
    price_index = {k: ([s[2] for s in v], v) for k, v in price.items()}

    xwalk = {}
    for old, kind, new in corpus["xwalk"]:
        xwalk[(kind, canon(old))] = canon(new)

    variant = pol["fiscal_calendar_variant"]
    cal = {}
    for day, region, var, label in corpus["calendar"]:
        if var == variant:
            cal[(day, region)] = label

    source = pol["fx_quote_source"]
    fx = {}
    for day, ccy, src, rate in corpus["fx"]:
        if src == source:
            fx[(day, ccy)] = rate

    voids = set(canon(e) for e in corpus["voids"])
    minor = pol["minor_units"]
    carry = pol["fx_carry_forward_days"]

    rejects = []
    live = []

    def reject(feed, code):
        rejects.append((feed, code))

    for feed in sorted(feeds):
        meta = corpus["feed_meta"][feed]
        tz_off = meta["tz_offset"]
        # The scope and revision registers name a feed by its file stem.
        stem = feed.rsplit(".", 1)[0]
        scope = pol["scope"].get(stem)
        sup = pol["superseded"].get(stem)
        for order, row in enumerate(feeds[feed]):
            defect = row["defect"]
            if defect in ("blank_kind", "blank_event", "bad_amount", "bad_date"):
                reject(feed, "MALFORMED_ROW")
                continue
            if defect in ("qty_text", "qty_decimal"):
                reject(feed, "NON_NUMERIC_QUANTITY")
                continue
            kind = row["kind"]
            stamp = datetime.strptime(row["ts"], "%Y-%m-%d %H:%M:%S")
            utc = stamp - timedelta(minutes=tz_off)
            capture = utc.date()
            if kind in ("sale", "refund"):
                term_raw = canon(row["terminal"])
                term = xwalk.get(("terminal", term_raw), term_raw)
                tver = tm.at(term, capture.isoformat())
                if tver is None:
                    reject(feed, "UNKNOWN_TERMINAL")
                    continue
                group, term_off = tver[3], tver[4]
            else:
                group, term_off = "contract", 0
            if group == "branch":
                posting = (utc + timedelta(minutes=term_off)).date()
            else:
                posting = capture
            pday = posting.isoformat()
            if not (window_lo <= pday < window_hi):
                reject(feed, "OUT_OF_SCOPE")
                continue
            if scope is not None and not (scope[0] <= pday < scope[1]):
                reject(feed, "OUT_OF_SCOPE")
                continue
            if sup is not None and pday >= sup:
                reject(feed, "SUPERSEDED_SOURCE")
                continue
            event = canon(row["event_id"])
            if event in voids:
                reject(feed, "VOIDED")
                continue
            cver = cust.at(canon(row["customer"]), pday)
            if cver is None:
                reject(feed, "UNKNOWN_CUSTOMER")
                continue
            segment, postal = cver[3], cver[4]
            sku_raw = canon(row["sku"])
            sku_id = xwalk.get(("sku", sku_raw), sku_raw)
            sver = sku.at(sku_id, pday)
            if sver is None:
                reject(feed, "UNKNOWN_SKU")
                continue
            if sver[4] == "N":
                reject(feed, "INACTIVE_SKU")
                continue
            category = sver[3]
            if kind in ("sale", "refund"):
                wh_raw = canon(row["warehouse"])
                wh_id = xwalk.get(("warehouse", wh_raw), wh_raw)
                wver = wh.at(wh_id, pday)
                if wver is None:
                    reject(feed, "UNKNOWN_WAREHOUSE")
                    continue
                postal_for_region = wver[3]
            else:
                postal_for_region = postal
            rver = pfx.at(postal_for_region.split("-")[0], pday)
            if rver is None:
                reject(feed, "UNKNOWN_WAREHOUSE")
                continue
            region = rver[3]
            if kind in ("sale", "refund"):
                entry = price_index.get(sku_id)
                version = None
                if entry is not None:
                    starts, spans = entry
                    pos = bisect_right(starts, pday) - 1
                    if pos >= 0 and spans[pos][2] <= pday < spans[pos][3]:
                        version = spans[pos][1]
                if version is None:
                    reject(feed, "NO_PRICE_VERSION")
                    continue
            else:
                version = "n/a"
            ccy = str(row["currency"]).strip().upper()
            if ccy not in minor:
                reject(feed, "NO_FX_RATE")
                continue
            rate = None
            probe = posting
            for _ in range(carry + 1):
                rate = fx.get((probe.isoformat(), ccy))
                if rate is not None:
                    break
                probe = probe - timedelta(days=1)
            if rate is None:
                reject(feed, "NO_FX_RATE")
                continue
            week = cal.get((pday, region))
            if week is None:
                reject(feed, "NO_FISCAL_WEEK")
                continue
            qty = int(row["quantity"]) if kind in ("sale", "refund") else 0
            unit = int(row["unit_price_minor"])
            native = KIND_SIGN[kind] * (qty * unit if kind in ("sale", "refund") else unit)
            cents = int((Decimal(native) / (10 ** minor[ccy]) * Decimal(rate)
                         * 100).quantize(Decimal(1), rounding=rounding))
            live.append({
                "amount_usd_cents": cents,
                "category": category,
                "channel_group": group,
                "currency": ccy,
                "customer_id": canon(row["customer"]),
                "event_id": event,
                "fiscal_week": week,
                "kind": kind,
                "native_amount_minor": native,
                "posting_date": pday,
                "price_list_version": version,
                "quantity": qty,
                "region": region,
                "segment": segment,
                "sku": sku_id,
                "source_file": feed,
                "_rank": pol["authority"][feed][kind],
                "_revision": int(row["revision"]),
                "_order": order,
                "_ref": canon(row["ref_event"]) if row["ref_event"] else "",
            })

    # ---- duplicate resolution by the authority ladder -------------------
    groups = {}
    for rec in live:
        groups.setdefault(rec["event_id"], []).append(rec)
    kept = []
    duplicate_groups = 0
    for event in sorted(groups):
        bucket = groups[event]
        if len(bucket) > 1:
            duplicate_groups += 1
            bucket = sorted(bucket, key=lambda r: (r["_rank"], -r["_revision"],
                                                   r["source_file"], r["_order"]))
            for loser in bucket[1:]:
                rejects.append((loser["source_file"], "DUPLICATE_LOWER_AUTHORITY"))
        kept.append(bucket[0])

    # ---- reversal chain, walked in canonical order ----------------------
    kept.sort(key=lambda r: (r["posting_date"], r["event_id"], r["source_file"]))
    alive = {rec["event_id"]: rec for rec in kept}
    removed = set()
    reversed_pairs = 0
    orphans = 0
    for rec in kept:
        if rec["kind"] != "credit" or not rec["_ref"]:
            continue
        if rec["event_id"] in removed:
            continue
        target = alive.get(rec["_ref"])
        if target is None or target["event_id"] in removed or target is rec:
            removed.add(rec["event_id"])
            rejects.append((rec["source_file"], "REVERSAL_ORPHAN"))
            orphans += 1
            continue
        removed.add(rec["event_id"])
        removed.add(target["event_id"])
        rejects.append((rec["source_file"], "REVERSED"))
        rejects.append((target["source_file"], "REVERSED"))
        reversed_pairs += 1

    final = [rec for rec in kept if rec["event_id"] not in removed]
    for index, rec in enumerate(final, start=1):
        rec["ledger_index"] = index
    records = []
    for rec in final:
        records.append({k: v for k, v in rec.items() if not k.startswith("_")})
    return _shape(corpus, pol, records, rejects, duplicate_groups,
                  reversed_pairs, orphans)


def _bucket(records, field):
    out = {}
    for rec in records:
        out[rec[field]] = out.get(rec[field], 0) + rec["amount_usd_cents"]
    return dict(sorted(out.items()))


def _units(rec):
    return rec["quantity"] if rec["kind"] == "sale" else (
        -rec["quantity"] if rec["kind"] == "refund" else 0)


def _group_payload(key, name, records):
    mine = [r for r in records if r[key] == name]
    totals = {}
    for rec in mine:
        totals[rec["customer_id"]] = totals.get(rec["customer_id"], 0) + rec["amount_usd_cents"]
    top = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_CUSTOMER_COUNT]
    return {
        key: name,
        "by_category": _bucket(mine, "category"),
        "by_channel_group": _bucket(mine, "channel_group"),
        "by_kind": _bucket(mine, "kind"),
        "customer_count": len(totals),
        "net_units": sum(_units(r) for r in mine),
        "record_count": len(mine),
        "top_customers": [{"customer_id": c, "total_usd_cents": v} for c, v in top],
        "total_usd_cents": sum(r["amount_usd_cents"] for r in mine),
    }


def _product_payload(records):
    per_sku = {}
    for rec in records:
        per_sku.setdefault(rec["sku"], []).append(rec)
    products = []
    for sid in sorted(per_sku):
        mine = per_sku[sid]
        products.append({
            "category": mine[0]["category"],
            "net_units": sum(_units(r) for r in mine),
            "price_list_versions": sorted({r["price_list_version"] for r in mine}),
            "record_count": len(mine),
            "sku": sid,
            "total_usd_cents": sum(r["amount_usd_cents"] for r in mine),
        })
    return {"product_count": len(products), "products": products}


def _shape(corpus, pol, records, rejects, duplicate_groups, reversed_pairs, orphans):
    window_lo, window_hi = corpus["window"]
    by_code = {}
    by_source_rej = {}
    for feed, code in rejects:
        by_code[code] = by_code.get(code, 0) + 1
        by_source_rej[feed] = by_source_rej.get(feed, 0) + 1
    accepted_by_source = {}
    for rec in records:
        accepted_by_source[rec["source_file"]] = accepted_by_source.get(rec["source_file"], 0) + 1
    for name in corpus["feeds"]:
        accepted_by_source.setdefault(name, 0)
        by_source_rej.setdefault(name, 0)

    total = sum(r["amount_usd_cents"] for r in records)
    summary = {
        "accepted_count": len(records),
        "by_category": _bucket(records, "category"),
        "by_channel_group": _bucket(records, "channel_group"),
        "by_currency": _bucket(records, "currency"),
        "by_kind": _bucket(records, "kind"),
        "by_region": _bucket(records, "region"),
        "by_segment": _bucket(records, "segment"),
        "net_units": sum(_units(r) for r in records),
        "rejected_count": len(rejects),
        "settlement_window": {"end_exclusive": window_hi, "start": window_lo},
        "total_usd_cents": total,
    }
    quality = {
        "accepted_by_source": dict(sorted(accepted_by_source.items())),
        "duplicate_groups": duplicate_groups,
        "input_file_count": corpus["file_count"],
        "rejected_by_code": dict(sorted(by_code.items())),
        "rejected_by_source": dict(sorted(by_source_rej.items())),
        "reversal_orphans": orphans,
        "reversed_pairs": reversed_pairs,
        "scoped_sources": sorted(pol["scope"]),
        "superseded_sources": sorted(pol["superseded"]),
    }
    payloads = {
        "normalized.jsonl": records,
        "summary.json": summary,
        "data_quality.json": quality,
        "product_summary.json": _product_payload(records),
    }
    for region in ("central", "east", "north", "south", "west"):
        payloads["region_%s.json" % region] = _group_payload("region", region, records)
    for segment in ("consumer", "corporate", "enterprise", "smb"):
        payloads["segment_%s.json" % segment] = _group_payload("segment", segment, records)
    return payloads


# ldg_logical
ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ"


DIGITS = "0123456789"


ALNUM = ALPHA + "23456789"


CAL_VARIANTS = ("iso", "broadcast", "retail445", "retail454", "fiscalq", "julian")


QUOTE_SOURCES = ("board", "central", "custodian", "desk", "street")


FEED_SPECS = [
    # (stem, ext, encoding, decimal_style, date_style, tz_offset_min, id_style, paren)
    ("order_capture_portal_oct", "csv", "utf-8", "point", "iso", 0, "plain", False),
    ("order_capture_portal_nov", "csv", "utf-8-sig", "point", "iso", 0, "plain", False),
    ("order_capture_portal_dec", "csv", "latin-1", "comma", "eu_dot", 60, "pad", True),
    ("branch_till_export_a", "csv", "utf-8", "comma", "eu_dot", 120, "pad", True),
    ("branch_till_export_b", "csv", "utf-8", "comma", "eu_dot", 120, "homoglyph", False),
    ("contract_billing_run", "csv", "utf-8", "point", "us_slash", -300, "plain", True),
    ("wholesale_edi_inbound", "tsv", "utf-8", "point", "iso", 330, "plain", False),
    ("wholesale_edi_backfill", "tsv", "latin-1", "comma", "eu_dot", 330, "pad", False),
    ("field_service_tickets", "tsv", "utf-8", "point", "epoch_s", -480, "homoglyph", False),
    ("dw_fact_sales_snapshot", "tsv", "utf-8", "point", "iso", 0, "plain", False),
    ("pos_stream_primary", "jsonl", "utf-8", "point", "epoch_ms", 0, "plain", False),
    ("pos_stream_replay", "jsonl", "utf-8", "point", "epoch_ms", 0, "pad", False),
    ("staging_dump_latest", "jsonl", "utf-8", "point", "iso", 570, "plain", False),
    ("adjustment_queue_q4", "jsonl", "utf-8", "point", "iso", 0, "plain", True),
    ("consolidated_settlement_extract_final", "xlsx", "utf-8", "point", "excel_serial", 0, "plain", False),
    ("regional_rollup_workbook", "xlsx", "utf-8", "point", "excel_serial", 0, "pad", False),
    ("credit_memo_workbook", "xlsx", "utf-8", "point", "excel_serial", -210, "plain", True),
    ("gl_posting_journal_v4", "json", "utf-8", "point", "iso", 0, "plain", False),
    ("gl_posting_journal_v5", "json", "utf-8", "point", "iso", 0, "plain", False),
    ("partner_invoice_feed", "xml", "utf-8", "comma", "eu_dot", 60, "plain", True),
    ("partner_credit_feed", "xml", "utf-8", "comma", "eu_dot", 60, "homoglyph", True),
    ("ledger_mirror_2026q4", "parquet", "utf-8", "point", "iso", 0, "plain", False),
    ("warehouse_issue_lines", "parquet", "utf-8", "point", "iso", 0, "plain", False),
    ("returns_intake_lines", "parquet", "utf-8", "point", "iso", -420, "pad", False),
    ("gateway_access_oct", "log", "utf-8", "point", "epoch_s", 0, "plain", False),
    ("gateway_access_nov", "log", "utf-8", "point", "epoch_s", 0, "plain", False),
    ("gateway_access_dec", "log", "utf-8", "point", "epoch_s", 0, "pad", False),
    ("terminal_sync_errors", "log", "latin-1", "point", "iso", 0, "plain", False),
    ("nightly_batch_trace", "log", "utf-8", "point", "iso", 0, "homoglyph", False),
    ("mainframe_extract_block", "txt", "utf-8", "point", "iso", 0, "pad", False),
    ("mainframe_extract_tail", "txt", "latin-1", "point", "iso", 0, "plain", False),
    ("archive_orders_2026", "db", "utf-8", "point", "iso", 0, "plain", False),
]


FEED_SCOPE = {
    "consolidated_settlement_extract_final": ("2026-12-01", "2027-01-01"),
    "archive_orders_2026": ("2026-01-01", "2026-10-01"),
    "staging_dump_latest": ("2026-10-01", "2026-10-15"),
    "dw_fact_sales_snapshot": ("2026-10-01", "2026-11-01"),
    "ledger_mirror_2026q4": ("2026-11-15", "2026-12-10"),
    "regional_rollup_workbook": ("2026-10-08", "2026-12-20"),
}


FEED_SUPERSEDED = {
    "gl_posting_journal_v4": "2026-11-01",
    "order_capture_portal_nov": "2026-11-21",
    "pos_stream_replay": "2026-12-05",
    "mainframe_extract_tail": "2026-10-20",
    "partner_credit_feed": "2026-12-18",
}


# The policy registers every drop publishes. The shipped and the first unseen
# drop use these; the second unseen drop publishes its own values, so a
# pipeline that copied the registers into its code instead of reading them
# at run time cannot reproduce it.
DEFAULT_RULES = {
    "quote": FX_QUOTE_SOURCE,
    "carry": FX_CARRY_FORWARD_DAYS,
    "variant": FISCAL_CALENDAR_VARIANT,
    "scope": FEED_SCOPE,
    "superseded": FEED_SUPERSEDED,
    "quiet_segment": None,
    "window": ("2026-10-01", "2027-01-01"),
    "rounding": "half_even",
    "minor_units": MINOR_UNITS,
    "homoglyphs": HOMOGLYPHS,
    "render_glyphs": CYRILLIC,
    "profiles": {},
    "unregistered_feed_table": None,
}


SEGMENTS = ("consumer", "corporate", "enterprise", "smb")


DECOY_FEEDS = (
    "consolidated_settlement_extract_final",
    "ledger_mirror_2026q4",
    "gl_posting_journal_v4",
    "archive_orders_2026",
    "dw_fact_sales_snapshot",
    "staging_dump_latest",
    "regional_rollup_workbook",
)


DEFECTS = (
    "blank_kind",
    "blank_event",
    "bad_amount",
    "bad_date",
    "qty_text",
    "qty_decimal",
)


UNKNOWN_IDS = {
    "customer": "CU-ZZZZZZZ",
    "sku": "SK-ZZZZZZZZ",
    "warehouse": "WH-ZZZZZ",
    "terminal": "TM-ZZZZZZ",
}


UNKNOWN_CURRENCY = "XYZ"


def _ids(rng, prefix, width, count):
    seen = set()
    out = []
    while len(out) < count:
        body = "".join(rng.choice(ALNUM) for _ in range(width))
        value = prefix + "-" + body
        if value not in seen:
            seen.add(value)
            out.append(value)
    return sorted(out)


def _span(rng, start, end, pieces):
    """Split [start, end) into `pieces` half-open windows as ISO date pairs."""
    total = (end - start).days
    cuts = sorted(rng.sample(range(1, total), min(pieces - 1, total - 1)))
    bounds = [0, *cuts, total]
    out = []
    for i in range(len(bounds) - 1):
        a = start + timedelta(days=bounds[i])
        b = start + timedelta(days=bounds[i + 1])
        out.append((a.isoformat(), b.isoformat()))
    return out


def _daterange(start, days):
    return [start + timedelta(days=i) for i in range(days)]


def build(seed, scale, rules=DEFAULT_RULES):
    """Return the whole logical corpus for one seed.

    `scale` multiplies every population; 1.0 is the shipped corpus.
    """
    quote, carry, week_variant = rules["quote"], rules["carry"], rules["variant"]
    rng = random.Random(seed)
    n = lambda base: max(4, int(round(base * scale)))  # noqa: E731

    hist_start = date(2024, 1, 1)
    hist_end = date(2027, 7, 1)
    win_start = date.fromisoformat(rules["window"][0])
    win_end = date.fromisoformat(rules["window"][1])
    win_days = (win_end - win_start).days

    corpus = {}

    # ---- customers: effective dated segment and postal code -------------
    cust_ids = _ids(rng, "CU", 7, n(4500))
    prefixes = ["%05d" % p for p in sorted(rng.sample(range(10000, 99999), n(5700)))]
    cust_rows = []
    for cid in cust_ids:
        home = rng.choice(prefixes)
        for lo, hi in _span(rng, hist_start, hist_end, 10):
            seg = rng.choice(("consumer", "corporate", "enterprise", "smb"))
            pc = home if rng.random() < 0.82 else rng.choice(prefixes)
            cust_rows.append((cid, lo, hi, seg, pc + "-" + "%03d" % rng.randrange(1000)))
    corpus["customers"] = cust_rows
    corpus["customer_ids"] = cust_ids

    # ---- postal prefix -> region, effective dated ------------------------
    prefix_rows = []
    for pfx in prefixes:
        base = rng.choice(("central", "east", "north", "south", "west"))
        for lo, hi in _span(rng, hist_start, hist_end, 8):
            region = base if rng.random() < 0.86 else rng.choice(
                ("central", "east", "north", "south", "west"))
            prefix_rows.append((pfx, lo, hi, region))
    corpus["prefixes"] = prefix_rows
    corpus["prefix_ids"] = prefixes

    # ---- skus: effective dated category and active flag ------------------
    sku_ids = _ids(rng, "SK", 8, n(6600))
    cats = ("abrasives", "bearings", "castings", "fasteners", "gaskets",
            "hoses", "insulators", "lubricants", "seals", "valves")
    sku_rows = []
    for sid in sku_ids:
        base = rng.choice(cats)
        for lo, hi in _span(rng, hist_start, hist_end, 7):
            cat = base if rng.random() < 0.9 else rng.choice(cats)
            active = "N" if rng.random() < 0.08 else "Y"
            sku_rows.append((sid, lo, hi, cat, active))
    corpus["skus"] = sku_rows
    corpus["sku_ids"] = sku_ids

    # ---- price list versions --------------------------------------------
    price_rows = []
    for sid in sku_ids:
        ccy = rng.choice(("USD", "USD", "EUR", "GBP", "JPY", "CAD", "CHF", "KWD"))
        windows = _span(rng, hist_start, hist_end, 10)
        for idx, (lo, hi) in enumerate(windows):
            # a deliberate gap: one window in twelve is simply not published
            if rng.random() < 0.08:
                continue
            vid = "PL%s-%02d" % (sid.split("-")[1][:4], idx + 1)
            price_rows.append((sid, vid, lo, hi, rng.randrange(50, 900000), ccy))
    corpus["prices"] = price_rows

    # ---- warehouses and terminals ---------------------------------------
    wh_ids = _ids(rng, "WH", 5, n(2750))
    wh_rows = []
    for wid in wh_ids:
        home = rng.choice(prefixes)
        for lo, hi in _span(rng, hist_start, hist_end, 15):
            pc = home if rng.random() < 0.88 else rng.choice(prefixes)
            wh_rows.append((wid, lo, hi, pc + "-" + "%03d" % rng.randrange(1000)))
    corpus["warehouses"] = wh_rows
    corpus["warehouse_ids"] = wh_ids

    tm_ids = _ids(rng, "TM", 6, n(2950))
    groups = ("branch", "contract", "field", "portal", "wholesale")
    offsets = (-480, -420, -300, -210, 0, 60, 120, 330, 345, 570)
    tm_rows = []
    for tid in tm_ids:
        base = rng.choice(groups)
        off = rng.choice(offsets)
        for lo, hi in _span(rng, hist_start, hist_end, 14):
            grp = base if rng.random() < 0.87 else rng.choice(groups)
            tm_rows.append((tid, lo, hi, grp, off))
    corpus["terminals"] = tm_rows
    corpus["terminal_ids"] = tm_ids

    # ---- fx rates per date, currency and quote source --------------------
    fx_start = date(2026, 9, 1)
    fx_days = _daterange(fx_start, max(150, n(1060)))
    level = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "CHF": 1.12,
             "AUD": 0.66, "JPY": 0.0066, "CLP": 0.0011, "ISK": 0.0072,
             "KWD": 3.26, "BHD": 2.65, "TND": 0.32}
    fx_rows = []
    gaps = set()
    for day in fx_days:
        iso = day.isoformat()
        for ccy in sorted(level):
            if ccy != "USD":
                level[ccy] = max(level[ccy] * (1 + rng.uniform(-0.005, 0.005)), 1e-6)
            for src in QUOTE_SOURCES:
                # The quote source the policy register names is the one with gaps,
                # which is what makes the carry forward limit load bearing.
                if ccy != "USD" and src == quote and rng.random() < 0.035:
                    gaps.add((iso, ccy))
                    continue
                bias = {"board": 1.0, "central": 1.0, "custodian": 1.0,
                        "desk": 1.0035, "street": 0.9965}[src]
                rate = 1.0 if ccy == "USD" else level[ccy] * bias
                fx_rows.append((iso, ccy, src, "%.6f" % rate))
    # A second stream keeps every draw above unchanged. Each currency loses the
    # named quote source for one run as long as the carry forward limit and for
    # one run a day longer, so both sides of the limit are graded.
    extra = random.Random(seed ^ 0x0F0F1234)
    outage = set()
    for ccy in sorted(level):
        if ccy == "USD":
            continue
        for length in (carry, carry + 1):
            first = win_start + timedelta(days=extra.randrange(1, win_days - length - 1))
            for step in range(length):
                outage.add(((first + timedelta(days=step)).isoformat(), ccy))
    fx_rows = [row for row in fx_rows
               if not (row[2] == quote and (row[0], row[1]) in outage)]
    corpus["fx"] = fx_rows

    # ---- fiscal calendar, one row per date, region and variant -----------
    cal_days = _daterange(date(2026, 9, 1), max(150, n(1140)))
    cal_rows = []
    for day in cal_days:
        iso = day.isoformat()
        ic = day.isocalendar()
        for region in ("central", "east", "north", "south", "west"):
            for variant in CAL_VARIANTS:
                if variant == "iso":
                    label = "%04d-W%02d" % (ic.year, ic.week)
                elif variant == "broadcast":
                    label = "%04d-B%02d" % (day.year, ((day.timetuple().tm_yday + 6) // 7))
                elif variant == "retail445":
                    label = "%04d-R%02d" % (day.year, ((day.timetuple().tm_yday + 13) // 14))
                elif variant == "retail454":
                    label = "%04d-S%02d" % (day.year, ((day.timetuple().tm_yday + 5) // 7))
                elif variant == "fiscalq":
                    label = "%04d-Q%d" % (day.year, (day.month - 1) // 3 + 1)
                else:
                    label = "%04d-J%03d" % (day.year, day.timetuple().tm_yday)
                cal_rows.append((iso, region, variant, label))
    corpus["calendar"] = cal_rows

    # ---- legacy code crosswalk -------------------------------------------
    xwalk = []
    for pool, kind, prefix in ((wh_ids, "warehouse", "LW"), (tm_ids, "terminal", "LT"),
                               (sku_ids, "sku", "LS")):
        legacy = _ids(rng, prefix, 6, len(pool))
        for old, new in zip(legacy, pool):
            xwalk.append((old, kind, new))
            tails = set()
            while len(tails) < rng.randrange(2, 6):
                tails.add("%02d" % rng.randrange(100))
            for tail in sorted(tails):
                xwalk.append((old + "/" + tail, kind, new))
    carriers = _ids(rng, "LC", 6, n(900))
    for old in carriers:
        # A carrier row points at a live warehouse code by coincidence, so a
        # solver that follows carrier rows accepts a row the contract rejects.
        xwalk.append((old, "carrier", extra.choice(wh_ids)))
    corpus["xwalk"] = xwalk

    # ---- transaction feeds ------------------------------------------------
    legacy_wh = [row[0] for row in xwalk if row[1] == "warehouse"]
    legacy_tm = [row[0] for row in xwalk if row[1] == "terminal"]
    legacy_sku = [row[0] for row in xwalk if row[1] == "sku"]
    ccy_pool = ("USD", "USD", "USD", "EUR", "GBP", "JPY", "CAD", "CHF",
                "KWD", "BHD", "AUD", "CLP", "ISK", "TND")
    event_pool = _ids(rng, "EV", 10, n(5000) * len(FEED_SPECS) * 86 // 100)
    taken = 0
    feeds = {}
    all_events = []
    for stem, ext, enc, dec, dstyle, tz, idstyle, paren in FEED_SPECS:
        name = stem + "." + ext
        rows = []
        count = n(5000)
        for i in range(count):
            if taken < len(event_pool) and rng.random() < 0.88:
                eid = event_pool[taken]
                taken += 1
            else:
                eid = rng.choice(event_pool)
            kind = rng.choices(("sale", "refund", "fee", "credit"),
                               weights=(64, 16, 12, 8))[0]
            qty = rng.randrange(1, 40) if kind in ("sale", "refund") else 0
            unit = rng.randrange(25, 450000)
            day = win_start + timedelta(days=rng.randrange(-8, win_days + 8))
            ts = datetime(day.year, day.month, day.day,
                          rng.randrange(24), rng.randrange(60), rng.randrange(60))
            wh = rng.choice(wh_ids) if rng.random() < 0.8 else rng.choice(legacy_wh)
            tm = rng.choice(tm_ids) if rng.random() < 0.8 else rng.choice(legacy_tm)
            defect = None
            if rng.random() < 0.03:
                defect = rng.choice(DEFECTS)
            customer = rng.choice(cust_ids)
            sku = rng.choice(sku_ids) if rng.random() < 0.86 else rng.choice(legacy_sku)
            currency = rng.choice(ccy_pool)
            if rng.random() < 0.012:
                field = rng.choice(("customer", "sku", "warehouse", "terminal"))
                if field == "customer":
                    customer = UNKNOWN_IDS["customer"]
                elif field == "sku":
                    sku = UNKNOWN_IDS["sku"]
                elif field == "warehouse":
                    wh = UNKNOWN_IDS["warehouse"]
                else:
                    tm = UNKNOWN_IDS["terminal"]
            if rng.random() < 0.008:
                currency = UNKNOWN_CURRENCY
            row = {
                "event_id": eid,
                "ts": ts.isoformat(sep=" "),
                "customer": customer,
                "sku": sku,
                "warehouse": wh if kind in ("sale", "refund") else "",
                "terminal": tm if kind in ("sale", "refund") else "",
                "kind": kind,
                "quantity": qty,
                "unit_price_minor": unit,
                "currency": currency,
                "revision": rng.randrange(1, 6),
                "ref_event": "",
                "defect": defect,
            }
            if kind == "credit" and rng.random() < 0.45 and all_events:
                row["ref_event"] = rng.choice(all_events)
            rows.append(row)
            all_events.append(eid)
        feeds[name] = rows
    corpus["feeds"] = feeds
    corpus["feed_meta"] = {
        stem + "." + ext: {
            "ext": ext, "encoding": enc, "decimal": dec, "date_style": dstyle,
            "tz_offset": tz, "id_style": idstyle, "paren": paren,
        }
        for stem, ext, enc, dec, dstyle, tz, idstyle, paren in FEED_SPECS
    }
    corpus["window"] = (win_start.isoformat(), win_end.isoformat())
    corpus["file_count"] = 100

    # ---- void register ----------------------------------------------------
    voided = sorted(rng.sample(all_events, min(len(all_events), n(900))))
    corpus["voids"] = voided

    # ---- retired carrier codes written where a warehouse belongs ---------
    for name in sorted(feeds):
        for row in feeds[name]:
            if row["kind"] in ("sale", "refund") and extra.random() < 0.006:
                row["warehouse"] = extra.choice(carriers)

    # Later streams leave every draw above unchanged. Each one plants the case
    # that makes one documented rule or precedence observable in the output.
    holes = random.Random(seed ^ 0x3C3C5151)
    # A row that fails both step 1 and step 2 must carry the step 1 code.
    for name in sorted(feeds):
        for row in feeds[name]:
            if row["defect"] in ("blank_kind", "blank_event", "bad_amount", "bad_date") \
                    and holes.random() < 0.3:
                row["qty_defect"] = "qty_text"
    # A region and day with no row for the named calendar variant.
    gone_weeks = set()
    while len(gone_weeks) < n(6):
        day = win_start + timedelta(days=holes.randrange(win_days))
        region = holes.choice(("central", "east", "north", "south", "west"))
        gone_weeks.add((day.isoformat(), region))
    corpus["calendar"] = [row for row in cal_rows
                          if not (row[2] == week_variant
                                  and (row[0], row[1]) in gone_weeks)]
    # A warehouse postal prefix whose region history has a gap in the quarter.
    homes = sorted({pc.split("-")[0] for _, lo, hi, pc in wh_rows
                    if lo < win_end.isoformat() and hi > win_start.isoformat()})
    gone_spans = set()
    for pfx in holes.sample(homes, min(len(homes), n(12))):
        day = (win_start + timedelta(days=holes.randrange(win_days))).isoformat()
        for row in prefix_rows:
            if row[0] == pfx and row[1] <= day < row[2]:
                gone_spans.add(row)
    corpus["prefixes"] = [row for row in prefix_rows if row not in gone_spans]

    plant = random.Random(seed ^ 0x6B1D2E77)
    # A retired code whose crosswalk row points at another retired code. One
    # hop stops at a code no registry carries, so the row rejects; a lookup
    # that keeps resolving reaches a live code and accepts it.
    known = {row[0] for row in xwalk}
    chained = {}
    for kind, prefix, pool in (("warehouse", "LW", legacy_wh),
                               ("terminal", "LT", legacy_tm),
                               ("sku", "LS", legacy_sku)):
        bases = sorted(code for code in pool if "/" not in code)
        chained[kind] = []
        for _ in range(max(6, int(round(30 * scale)))):
            code = prefix + "-" + "".join(plant.choice(ALNUM) for _ in range(6))
            while code in known:
                code = prefix + "-" + "".join(plant.choice(ALNUM) for _ in range(6))
            known.add(code)
            xwalk.append((code, kind, plant.choice(bases)))
            chained[kind].append(code)
    trade = [row for name in sorted(feeds) for row in feeds[name]
             if row["kind"] in ("sale", "refund") and not row["defect"]]
    for kind in ("warehouse", "terminal", "sku"):
        for code in chained[kind]:
            for _ in range(2):
                plant.choice(trade)[kind] = code
    # A reversal that names its own event leaves the ledger as an orphan.
    credits = [row for name in sorted(feeds) for row in feeds[name]
               if row["kind"] == "credit" and not row["defect"]]
    for row in plant.sample(credits, min(len(credits), max(12, int(round(60 * scale))))):
        row["ref_event"] = row["event_id"]
    # A drop may carry no customer at all for one segment; its file still ships.
    quiet = rules["quiet_segment"]
    if quiet:
        corpus["customers"] = [(cid, lo, hi, "consumer" if seg == quiet else seg, pc)
                               for cid, lo, hi, seg, pc in corpus["customers"]]
    # Two new counterparties settle one identical fee each, large enough to
    # lead their segment and region, so the top customer tie break decides
    # their order. The feed lists the later identifier first.
    spans = {}
    for pfx_id, lo, hi, region in corpus["prefixes"]:
        spans.setdefault(pfx_id, []).append((lo, hi, region))
    weeks = {(row[0], row[1]) for row in corpus["calendar"] if row[2] == week_variant}
    while True:
        iso = (win_start + timedelta(days=plant.randrange(2, win_days - 2))).isoformat()
        home = plant.choice(prefixes)
        region = next((r for lo, hi, r in spans.get(home, ()) if lo <= iso < hi), None)
        if region and (iso, region) in weeks:
            break
    item = None
    while item is None:
        sid, lo, hi, _cat, active = plant.choice(sku_rows)
        if active == "Y" and lo <= iso < hi:
            item = sid
    taken_customers = set(cust_ids)
    pair = []
    while len(pair) < 2:
        cid = "CU-" + "".join(plant.choice(ALNUM) for _ in range(7))
        if cid not in taken_customers:
            taken_customers.add(cid)
            pair.append(cid)
    taken_events = set(event_pool)
    tags = []
    while len(tags) < 2:
        eid = "EV-" + "".join(plant.choice(ALNUM) for _ in range(10))
        if eid not in taken_events:
            taken_events.add(eid)
            tags.append(eid)
    pair.sort(reverse=True)
    tags.sort()
    segment = plant.choice([s for s in SEGMENTS if s != quiet])
    postal = home + "-" + "%03d" % plant.randrange(1000)
    for cid in pair:
        corpus["customers"].append((cid, hist_start.isoformat(), hist_end.isoformat(),
                                    segment, postal))
    open_feeds = sorted(name for name in feeds
                        if name.rsplit(".", 1)[0] not in rules["scope"]
                        and name.rsplit(".", 1)[0] not in rules["superseded"])
    host = plant.choice(open_feeds)
    amount = plant.randrange(40, 60) * 100000000
    for slot, cid, eid, hour in zip(sorted(plant.sample(range(len(feeds[host])), 2)),
                                    pair, tags, (11, 13)):
        feeds[host][slot] = {
            "event_id": eid, "ts": "%s %02d:00:00" % (iso, hour), "customer": cid,
            "sku": item, "warehouse": "", "terminal": "", "kind": "fee",
            "quantity": 0, "unit_price_minor": amount, "currency": "USD",
            "revision": 1, "ref_event": "", "defect": None,
        }
    corpus["render_glyphs"] = dict(rules["render_glyphs"])
    by_stem = {name.rsplit(".", 1)[0]: name for name in corpus["feed_meta"]}
    for stem, changes in sorted(rules["profiles"].items()):
        corpus["feed_meta"][by_stem[stem]].update(changes)
    # Feed shaped rows inside a reference file: the contract keeps them out of the
    # ledger, so only a pipeline that sniffs headers instead of reading
    # source_profiles changes its result.
    corpus["unregistered_feed_table"] = rules["unregistered_feed_table"]
    corpus["unregistered_rows"] = []
    if rules["unregistered_feed_table"]:
        stray = random.Random(seed ^ 0x2D4E6F81)
        pool = [row for name in sorted(feeds) for row in feeds[name] if not row["defect"]]
        corpus["unregistered_rows"] = [dict(row) for row in stray.sample(pool, n(1500))]
    return corpus


# ldg_build
HEADERS = {
    "customers": ["customer_id", "valid_from", "valid_to", "segment", "postal_code"],
    "prefixes": ["postal_prefix", "valid_from", "valid_to", "region"],
    "skus": ["sku", "valid_from", "valid_to", "category", "active"],
    "prices": ["sku", "version_id", "valid_from", "valid_to", "list_price_minor", "currency"],
    "warehouses": ["warehouse", "valid_from", "valid_to", "postal_code"],
    "terminals": ["terminal", "valid_from", "valid_to", "channel_group", "utc_offset_minutes"],
    "fx": ["rate_date", "currency", "quote_source", "usd_rate"],
    "calendar": ["calendar_date", "region", "variant", "fiscal_week"],
    "xwalk": ["legacy_code", "code_kind", "current_code"],
}


SHARD_KEY = {"customers": 0, "prefixes": 0, "skus": 0, "prices": 0,
             "warehouses": 0, "terminals": 0, "fx": 0, "calendar": 0, "xwalk": 0}


TITLES = {
    "customers": "Party master shard",
    "prefixes": "Postal region shard",
    "skus": "Item master shard",
    "prices": "Price book shard",
    "warehouses": "Warehouse registry shard",
    "terminals": "Terminal registry shard",
    "fx": "Exchange rate shard",
    "calendar": "Fiscal calendar shard",
    "xwalk": "Code crosswalk shard",
}


WIDTHS = {
    "xwalk": [22, 12, 14],
    "feed": [20, 24, 14, 18, 16, 16, 8, 10, 18, 10, 10, 20],
}


def _rows_for(corpus, registry, index, count):
    if registry == "fx":
        chosen = split_round_robin(corpus[registry], 1, index, count)
    else:
        chosen = split(corpus[registry], SHARD_KEY[registry], index, count)
    return [list(row) for row in chosen]


def _policy_payload(corpus, pol, block):
    meta = corpus["feed_meta"]
    if block == "feed_profiles":
        body = []
        for name in sorted(meta):
            info = meta[name]
            body.append((name, {
                "container": info["ext"],
                "encoding": info["encoding"],
                "decimal_style": info["decimal"],
                "date_style": info["date_style"],
                "utc_offset_minutes": info["tz_offset"],
                "id_style": info["id_style"],
                "parenthesised_negatives": "yes" if info["paren"] else "no",
            }))
        return [("source_profiles", body)]
    if block == "scope_registry":
        body = []
        for name in sorted(pol["scope"]):
            lo, hi = pol["scope"][name]
            body.append((name, {"scope_start": lo, "scope_end_exclusive": hi}))
        return [("scope_windows", body)]
    if block == "money_policy":
        return [("minor_units", sorted(pol["minor_units"].items())),
                ("rounding", [("mode", pol["rounding"]),
                              ("applied_at", "usd_cents_once")])]
    if block == "fx_policy":
        return [("fx", [("quote_source", pol["fx_quote_source"]),
                        ("carry_forward_days", pol["fx_carry_forward_days"]),
                        ("rounding_mode", pol["rounding"])])]
    if block == "calendar_policy":
        return [("fiscal_calendar", [("variant", pol["fiscal_calendar_variant"])])]
    if block == "window":
        lo, hi = corpus["window"]
        return [("settlement_window", [("start", lo), ("end_exclusive", hi)]),
                ("inventory", [("input_file_count", str(corpus["file_count"]))])]
    if block == "identity_policy":
        return [("homoglyphs", [(hex(ord(k))[2:], v) for k, v in sorted(pol["homoglyphs"].items())]),
                ("identifier", [("strip_leading_zeros_after_hyphen", "yes"),
                                ("upper_case", "yes")])]
    if block == "ladder_trade":
        return [("authority_sale", sorted((n, str(v["sale"])) for n, v in pol["authority"].items())),
                ("authority_refund", sorted((n, str(v["refund"])) for n, v in pol["authority"].items()))]
    if block == "ladder_memo":
        return [("authority_fee", sorted((n, str(v["fee"])) for n, v in pol["authority"].items())),
                ("authority_credit", sorted((n, str(v["credit"])) for n, v in pol["authority"].items()))]
    return []


def _policy_prose(corpus, pol, block):
    if block == "contract":
        return CONTRACT
    if block == "revision_log":
        lines = ["# Price and source revision log", "", REVISION_NOTE, "",
                 "| retired_source | superseded_from |", "| --- | --- |"]
        for name in sorted(pol["superseded"]):
            lines.append("| %s | %s |" % (name, pol["superseded"][name]))
        lines.append("")
        lines.append("The table below is this file's shard of the price book.")
        return "\n".join(lines)
    return ""


BOM_SAFE = {"csv", "tsv", "jsonl", "json", "xml", "md", "html", "txt", "ini", "yaml"}


PLAIN_FEED_META = {"id_style": "plain", "decimal": "point", "paren": False,
                   "date_style": "iso"}


def _encoding_for(name, ext):
    """Some published text files carry a byte order mark, as the contract says."""
    if ext not in BOM_SAFE:
        return "utf-8"
    total = 0
    for ch in name:
        total = (total * 37 + ord(ch)) % 99991
    return "utf-8-sig" if total % 3 == 0 else "utf-8"


def write_reference(path, name, ext, registry, rows, corpus, pol, block):
    header = HEADERS[registry]
    enc = _encoding_for(name, ext)
    title = TITLES[registry]
    extra = _policy_payload(corpus, pol, block)
    note = {"voids": VOID_NOTE, "feed_profiles": FEED_PROFILE_NOTE,
            "scope_registry": SCOPE_NOTE}.get(block, "")
    if name == "counterparty_notice_board.html":
        void_rows = [[event] for event in corpus["voids"]]
        write_html(path, ["voided_event_id"], void_rows, "utf-8",
                   title="Void register", note_lines=[VOID_NOTE])
        extra_rows = rows
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("<h2>%s</h2>\n<table>\n" % title)
            handle.write("<tr>" + "".join("<th>%s</th>" % h for h in header) + "</tr>\n")
            for row in extra_rows:
                handle.write("<tr>" + "".join("<td>%s</td>" % v for v in row) + "</tr>\n")
            handle.write("</table>\n")
        return
    if ext == "csv":
        write_delimited(path, header, rows, ",", enc, [title])
    elif ext == "tsv":
        write_delimited(path, header, rows, "\t", enc, [title])
    elif ext == "jsonl":
        write_jsonl(path, header, rows, enc, [title])
    elif ext == "json":
        write_json(path, header, rows, enc, {"title": title, "note": note})
    elif ext == "xml":
        write_xml(path, header, rows, enc, root="registry", note=note or title)
    elif ext == "parquet":
        write_parquet(path, header, rows, note=title)
    elif ext == "db":
        write_sqlite(path, header, rows, table="lines", extra=[("title", title)])
    elif ext == "xlsx":
        write_xlsx(path, [("notes", ["key", "value"], [["title", title], ["note", note or title]]),
                          ("lines", header, rows)])
    elif ext == "yaml":
        write_yaml(path, header, rows, enc, key="lines", preamble=[title], extra=extra)
    elif ext == "toml":
        write_toml(path, header, rows, "utf-8", table="lines", preamble=[title], extra=extra)
    elif ext == "ini":
        write_ini(path, header, rows, enc, preamble=[title], extra=extra)
    elif ext == "md":
        write_md(path, header, rows, enc,
                 prose=_policy_prose(corpus, pol, block) or ("# " + title))
    elif ext == "html":
        write_html(path, header, rows, enc, title=title, note_lines=[note or title])
        if name == corpus["unregistered_feed_table"]:
            excerpt = feed_rows(name, corpus["unregistered_rows"], PLAIN_FEED_META,
                                pol["minor_units"], corpus["render_glyphs"])
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("<h2>Settlement activity excerpt</h2>\n<table>\n")
                handle.write("<tr>" + "".join("<th>%s</th>" % h for h in FEED_COLUMNS) + "</tr>\n")
                for row in excerpt:
                    handle.write("<tr>" + "".join("<td>%s</td>" % _xml_escape(v) for v in row)
                                 + "</tr>\n")
                handle.write("</table>\n")
    elif ext == "txt":
        write_fixed(path, header, rows, enc, WIDTHS["xwalk"], [title])
    elif ext == "mbox":
        write_mbox(path, header, rows, "utf-8", subject="crosswalk notice")
    elif ext == "ics":
        write_ics(path, header, rows, "utf-8", calname=title)
    elif ext == "docx":
        write_docx(path, [title, note or
                          "This appendix is published as part of the settlement drop."],
                   header, rows)
    elif ext == "pdf":
        write_pdf(path, title, [note or "Published appendix."], header, rows)
    else:
        raise ValueError(ext)


def write_feed(path, name, ext, rows, meta):
    header = FEED_COLUMNS
    if ext == "csv":
        write_delimited(path, header, rows, ",", meta["encoding"], ["settlement feed"])
    elif ext == "tsv":
        write_delimited(path, header, rows, "\t", meta["encoding"], ["settlement feed"])
    elif ext == "jsonl":
        write_jsonl(path, header, rows, meta["encoding"], ["settlement feed"])
    elif ext == "json":
        write_json(path, header, rows, meta["encoding"], {"title": "settlement feed"})
    elif ext == "xml":
        write_xml(path, header, rows, meta["encoding"], root="feed", note="settlement feed")
    elif ext == "parquet":
        write_parquet(path, header, rows, note="settlement feed")
    elif ext == "db":
        write_sqlite(path, header, rows, table="lines", extra=[("title", "settlement feed")])
    elif ext == "xlsx":
        write_xlsx(path, [("notes", ["key", "value"], [["title", "settlement feed"]]),
                          ("lines", header, rows)])
    elif ext == "log":
        write_log(path, header, rows, meta["encoding"], service=name.split(".")[0])
    elif ext == "txt":
        write_fixed(path, header, rows, meta["encoding"], WIDTHS["feed"], ["settlement feed"])
    else:
        raise ValueError(ext)


def write_corpus(corpus, pol, outdir):
    os.makedirs(outdir, exist_ok=True)
    written = []
    for name, rows in sorted(corpus["feeds"].items()):
        meta = corpus["feed_meta"][name]
        write_feed(os.path.join(outdir, name), name, meta["ext"],
                   feed_rows(name, rows, meta, pol["minor_units"], corpus["render_glyphs"]),
                   meta)
        written.append(name)
    for name, registry, index, count, block in REFERENCE_FILES:
        ext = name.rsplit(".", 1)[1]
        rows = _rows_for(corpus, registry, index, count)
        write_reference(os.path.join(outdir, name), name, ext, registry, rows,
                        corpus, pol, block)
        written.append(name)
    assert len(written) == 100, len(written)
    assert len(set(written)) == 100
    assert len(DECOY_FILES & set(written)) == 15
    return written


APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
SAMPLE_SEED = int("20261021")
CHALLENGE_SEED = int("760114853299")
EVAL_SEED = int("418920573361")
CHALLENGE_RULES = {
    "quote": "desk",
    "carry": 2,
    "variant": "retail445",
    "scope": {
        "consolidated_settlement_extract_final": ("2026-11-20", "2027-01-01"),
        "archive_orders_2026": ("2026-01-01", "2026-10-01"),
        "staging_dump_latest": ("2026-10-10", "2026-10-28"),
        "dw_fact_sales_snapshot": ("2026-10-15", "2026-11-20"),
        "ledger_mirror_2026q4": ("2026-11-01", "2026-12-01"),
        "regional_rollup_workbook": ("2026-10-01", "2026-12-05"),
    },
    "superseded": {
        "gl_posting_journal_v4": "2026-11-15",
        "order_capture_portal_nov": "2026-12-01",
        "pos_stream_replay": "2026-11-20",
        "mainframe_extract_tail": "2026-11-05",
        "partner_credit_feed": "2026-12-10",
    },
    "quiet_segment": "smb",
    "window": ("2026-10-04", "2027-01-03"),
    "rounding": "floor",
    "minor_units": {**MINOR_UNITS, "ISK": 2},
    "homoglyphs": {**HOMOGLYPHS, **GREEK_HOMOGLYPHS},
    "render_glyphs": {latin: glyph for glyph, latin in GREEK_HOMOGLYPHS.items()},
    "profiles": {"gl_posting_journal_v5": {"decimal": "comma", "date_style": "us_slash",
                                           "tz_offset": 345, "id_style": "homoglyph",
                                           "paren": True}},
    "unregistered_feed_table": "price_board_extract.html",
}
SAMPLE_SCALE = 1.0
PROBE_SCALE = 0.04
ARTIFACTS = [
    "transform.py",
    "normalized.jsonl",
    "summary.json",
    "data_quality.json",
    "product_summary.json",
    "region_central.json",
    "region_east.json",
    "region_north.json",
    "region_south.json",
    "region_west.json",
    "segment_consumer.json",
    "segment_corporate.json",
    "segment_enterprise.json",
    "segment_smb.json",
]
PAYLOAD_NAMES = [name for name in ARTIFACTS if name != "transform.py"]
IDENTITY_FIELDS = ("event_id", "posting_date", "ledger_index")
DIMENSION_FIELDS = ("region", "segment", "category", "channel_group", "fiscal_week")
MONEY_FIELDS = ("currency", "native_amount_minor", "quantity")
PARTY_FIELDS = ("customer_id", "kind", "sku")
LEDGER_KEYS = frozenset((
    "amount_usd_cents", "category", "channel_group", "currency", "customer_id",
    "event_id", "fiscal_week", "kind", "ledger_index", "native_amount_minor",
    "posting_date", "price_list_version", "quantity", "region", "segment", "sku",
    "source_file",
))
DUPLICATE_CODE = "DUPLICATE_LOWER_AUTHORITY"
REVERSAL_CODES = ("REVERSED", "REVERSAL_ORPHAN")
SCOPE_CODES = ("OUT_OF_SCOPE", "SUPERSEDED_SOURCE")
OWNED_CODES = frozenset((DUPLICATE_CODE, *REVERSAL_CODES, *SCOPE_CODES))
SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
FULL_RUN_TIMEOUT = 1200
PROBE_RUN_TIMEOUT = 300
MIN_SHARED_FRACTION = 0.5
MIN_OWN_PRECISION = 0.7

_LOCK = threading.RLock()
_LOGICAL = {}
_EXPECTED = {}
_DROPS = {}
_TRANSFORMED = {}
_FINGERPRINTS = {}
_LEDGER = {}
_STALLED = set()
_STRAY_TMP = set()


# ----------------------------------------------------------------- scaffolding

def _logical_corpus(seed, scale):
    key = (seed, scale)
    if key not in _LOGICAL:
        drop_rules = CHALLENGE_RULES if seed == CHALLENGE_SEED else DEFAULT_RULES
        corpus = build(seed, scale, drop_rules)
        rules = policy(seed, sorted(corpus["feeds"]), drop_rules)
        _LOGICAL[key] = (corpus, rules)
    return _LOGICAL[key]


def _reference(seed, scale):
    key = (seed, scale)
    if key not in _EXPECTED:
        corpus, rules = _logical_corpus(seed, scale)
        _EXPECTED[key] = run(corpus, rules)
    return _EXPECTED[key]


def _drop(seed, scale, label):
    """Serialize one drop into a scratch directory the submission may read."""
    key = (seed, scale, label)
    if key not in _DROPS:
        root = Path(tempfile.mkdtemp(prefix="ldg-%s-" % label))
        corpus, rules = _logical_corpus(seed, scale)
        write_corpus(corpus, rules, str(root / "data"))
        _relax(root)
        _DROPS[key] = root / "data"
    return _DROPS[key]


def _relax(root):
    root.chmod(0o755)
    for path in root.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)


def _open_up(target):
    """Let the dropped privilege user reach a scratch directory."""
    base = Path(tempfile.gettempdir()).resolve()
    node = target.resolve()
    chain = []
    while node != base and node != node.parent:
        chain.append(node)
        node = node.parent
    for path in reversed(chain):
        try:
            path.chmod(0o777 if path == target.resolve() else 0o755)
        except OSError:
            pass


def _grant_read(program):
    """An agent editor leaves its files at 0600; the dropped uid must still read them."""
    node = program.resolve()
    node.chmod(node.stat().st_mode | 0o444)
    for parent in node.parents:
        if parent == parent.parent:
            break
        parent.chmod(parent.stat().st_mode | 0o555)


def _tmp_entries():
    try:
        return set(os.listdir(tempfile.gettempdir()))
    except OSError:
        return set()


def _note_tmp_writes(before):
    """Remember every top level temp entry an agent run created.

    Every run is recorded, whichever check started it, so a write the script
    makes only once (a cache it creates when absent) is seen however rewardkit
    happens to order its checks.
    """
    tmp = Path(tempfile.gettempdir())
    fresh = _tmp_entries() - before
    if os.name == "posix" and os.geteuid() == 0:
        # The script runs as nobody, so only entries nobody owns are its writes.
        try:
            nobody = pwd.getpwnam("nobody").pw_uid
        except KeyError:
            return
        mine = set()
        for name in fresh:
            try:
                if os.lstat(tmp / name).st_uid == nobody:
                    mine.add(name)
            except OSError:
                continue
        fresh = mine
    _STRAY_TMP.update(fresh)


def _sandboxed(command):
    if os.name == "posix" and os.geteuid() == 0:
        return [*SETPRIV, *command]
    return command


def _kill_strays(proc):
    """Kill the run's process group and anything else the sandbox user left running."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    if not (os.name == "posix" and os.geteuid() == 0):
        return
    try:
        nobody = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text()
        except OSError:
            continue
        for line in status.splitlines():
            if line.startswith("Uid:"):
                if int(line.split()[1]) == nobody:
                    try:
                        os.kill(int(entry.name), signal.SIGKILL)
                    except OSError:
                        pass
                break


def _run(source, target, scale, cwd=None):
    script = OUT_DIR / "transform.py"
    if not script.is_file():
        raise AssertionError("no delivered script")
    if scale in _STALLED:
        raise AssertionError("an earlier run at this scale timed out")
    _grant_read(script)
    target.mkdir(parents=True, exist_ok=True)
    _open_up(target)
    if cwd is None:
        cwd = Path(tempfile.mkdtemp(prefix="ldg-cwd-"))
        _open_up(cwd)
    limit = FULL_RUN_TIMEOUT if scale >= SAMPLE_SCALE else PROBE_RUN_TIMEOUT
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        tmp_before = _tmp_entries()
        proc = subprocess.Popen(
            _sandboxed([sys.executable, str(script), str(source), str(target)]),
            cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=out, stderr=err,
            start_new_session=True)
        try:
            code = proc.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            _STALLED.add(scale)
            _kill_strays(proc)
            proc.wait()
            _note_tmp_writes(tmp_before)
            raise AssertionError("delivered script timed out") from None
        _kill_strays(proc)
        _note_tmp_writes(tmp_before)
        err.seek(0)
        tail = err.read()[-400:].decode("utf-8", "replace")
    if code != 0:
        raise AssertionError(tail)
    return target


def _invoke(source, target, scale):
    return _marks_of_dir(_run(source, target, scale))


def _canonical_text(name, payload):
    if name.endswith(".jsonl"):
        return "".join(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n"
                       for rec in payload)
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _marks_of_payloads(payloads):
    return {name: hashlib.sha256(
        _canonical_text(name, payloads[name]).encode("utf-8")).hexdigest()
        for name in PAYLOAD_NAMES}


def _marks_of_dir(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in PAYLOAD_NAMES}


def _delivered_marks():
    if "out" not in _FINGERPRINTS:
        _FINGERPRINTS["out"] = _marks_of_dir(OUT_DIR)
    return _FINGERPRINTS["out"]


def _reference_marks(seed, scale):
    key = (seed, scale)
    if key not in _FINGERPRINTS:
        _FINGERPRINTS[key] = _marks_of_payloads(_reference(seed, scale))
    return _FINGERPRINTS[key]


def _transform_drop(seed, scale, label):
    key = (seed, scale, label)
    if key not in _TRANSFORMED:
        try:
            source = _drop(seed, scale, label)
            target = Path(tempfile.mkdtemp(prefix="ldg-out-%s-" % label)) / "out"
            _TRANSFORMED[key] = _invoke(source, target, scale)
        except Exception as exc:
            _TRANSFORMED[key] = exc
    found = _TRANSFORMED[key]
    if isinstance(found, Exception):
        raise found
    return found


def _parse(path):
    text = path.read_text(encoding="utf-8")
    if path.name.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line]
    return json.loads(text)


def _delivered(name):
    return _parse(OUT_DIR / name)


def _sample():
    return _reference(SAMPLE_SEED, SAMPLE_SCALE)


def _ledger():
    if "ledger" not in _LEDGER:
        _LEDGER["ledger"] = _delivered("normalized.jsonl")
    return _LEDGER["ledger"]


def _projection(records, fields):
    return [tuple(rec[field] for field in fields) for rec in records]


def _by_event(records):
    return {rec.get("event_id"): rec for rec in records if isinstance(rec, dict)}


def _shared_fields_match(fields, same_source=True):
    """Compare fields per event over the events both ledgers carry.

    Ledger membership and order belong to ledger_identity and the surviving
    copy of a repeated event belongs to duplicate_authority, so a field check
    reads only the events whose delivered record comes from the same feed as
    the expected one. One missing, extra or differently resolved record then
    costs the check that owns it rather than every field check. A ledger
    sharing under half of the expected events earns nothing here.
    """
    want = _by_event(_sample()["normalized.jsonl"])
    got = _by_event(_ledger())
    shared = [event for event in want if event in got]
    if same_source:
        shared = [event for event in shared
                  if got[event].get("source_file") == want[event]["source_file"]]
    assert shared and len(shared) >= MIN_SHARED_FRACTION * len(want)
    for event in shared:
        mine, theirs = got[event], want[event]
        for field in fields:
            assert field in mine, field
            assert mine[field] == theirs[field], (event, field)
            assert type(mine[field]) is type(theirs[field]), (event, field)


def _own_ledger():
    """The delivered ledger, which the roll-up files must summarise.

    Roll-ups are graded against the ledger the agent delivered, so a wrong
    ledger record costs the ledger check that reads it and not every roll-up
    built on it. The ledger must still share half of the expected events, so
    a roll-up of an invented ledger earns nothing, and most of its own events
    must be expected ones, so a ledger that keeps every event of every feed
    without applying the chain earns nothing either.
    """
    records = _ledger()
    want = _by_event(_sample()["normalized.jsonl"])
    got = _by_event(records)
    shared = sum(1 for event in want if event in got)
    assert shared >= MIN_SHARED_FRACTION * len(want)
    assert shared >= MIN_OWN_PRECISION * len(got)
    return records


def _whole_numbers(value):
    if isinstance(value, dict):
        return all(_whole_numbers(item) for item in value.values())
    if isinstance(value, list):
        return all(_whole_numbers(item) for item in value)
    if isinstance(value, (int, float)):
        return type(value) is int
    return True


def _rollup_matches(got, want):
    assert got == want
    assert _whole_numbers(got)


def _same(got, want):
    return got == want and type(got) is type(want)


def _cached(key, compute):
    if key not in _FINGERPRINTS:
        try:
            _FINGERPRINTS[key] = compute()
        except Exception as exc:
            _FINGERPRINTS[key] = exc
    found = _FINGERPRINTS[key]
    if isinstance(found, Exception):
        raise found
    return found


def _without(mapping, keys):
    return {k: v for k, v in mapping.items() if k not in keys}


def _decoy_feeds():
    corpus = _logical_corpus(SAMPLE_SEED, SAMPLE_SCALE)[0]
    return sorted(name for name in DECOY_FILES if name in corpus["feeds"])


def _rate_table(seed, scale):
    corpus, rules = _logical_corpus(seed, scale)
    quotes = {}
    for day, money, source, rate in corpus["fx"]:
        if source == rules["fx_quote_source"]:
            quotes[(day, money)] = rate
    return quotes, rules


def _rate_for(quotes, rules, day, money):
    cursor = date(int(day[0:4]), int(day[5:7]), int(day[8:10]))
    for _ in range(rules["fx_carry_forward_days"] + 1):
        rate = quotes.get((cursor.isoformat(), money))
        if rate is not None:
            return rate
        cursor = cursor - timedelta(days=1)
    return None


# ----------------------------------------------------------------- shape tests

def _c_artifacts_exist():
    for name in ARTIFACTS:
        assert (OUT_DIR / name).is_file(), name


def _c_json_layout():
    for name in PAYLOAD_NAMES:
        text = (OUT_DIR / name).read_text(encoding="utf-8")
        assert text.endswith("\n")
        if name.endswith(".jsonl"):
            for line in text.splitlines():
                assert line == json.dumps(json.loads(line), sort_keys=True,
                                          separators=(",", ":"))
        else:
            assert text == json.dumps(json.loads(text), sort_keys=True,
                                      indent=2) + "\n"


# --------------------------------------------------------------- summary slices

def _c_summary_counts():
    records = _own_ledger()
    got = _delivered("summary.json")
    tally = _delivered("data_quality.json")["rejected_by_code"]
    assert got["accepted_count"] == len(records)
    assert got["net_units"] == sum(_units(r) for r in records)
    assert got["total_usd_cents"] == sum(r["amount_usd_cents"] for r in records)
    assert got["rejected_count"] == sum(tally.values())
    assert _whole_numbers([got[field] for field in (
        "accepted_count", "net_units", "rejected_count", "total_usd_cents")])


def _summary_slice(field):
    got = _delivered("summary.json")["by_" + field]
    _rollup_matches(got, _bucket(_own_ledger(), field))


def _c_summary_by_region():
    _summary_slice("region")


def _c_summary_by_segment():
    _summary_slice("segment")


def _c_summary_by_category():
    _summary_slice("category")


def _c_summary_by_channel_group():
    _summary_slice("channel_group")


def _c_summary_by_currency():
    _summary_slice("currency")


def _c_summary_by_kind():
    _summary_slice("kind")


# --------------------------------------------------------------- quality slices

def _c_quality_codes():
    """Every rejection code not owned by a rule check below."""
    got = _delivered("data_quality.json")["rejected_by_code"]
    want = _sample()["data_quality.json"]["rejected_by_code"]
    _rollup_matches(_without(got, OWNED_CODES), _without(want, OWNED_CODES))


def _c_quality_accepted_by_source():
    """The inventory side of the health report: every feed's accepted count and the file count."""
    records = _own_ledger()
    expected = _sample()["data_quality.json"]
    want = {name: 0 for name in expected["accepted_by_source"]}
    for rec in records:
        want[rec["source_file"]] = want.get(rec["source_file"], 0) + 1
    quality = _delivered("data_quality.json")
    _rollup_matches(quality["accepted_by_source"], want)
    assert _same(quality["input_file_count"], expected["input_file_count"])


def _c_quality_rejected_by_source():
    want = _sample()["data_quality.json"]["rejected_by_source"]
    _rollup_matches(_delivered("data_quality.json")["rejected_by_source"], want)


# ----------------------------------------------------------------- roll-up files

def _c_product_summary():
    _rollup_matches(_delivered("product_summary.json"), _product_payload(_own_ledger()))


def _c_region_files():
    records = _own_ledger()
    for region in ("central", "east", "north", "south", "west"):
        _rollup_matches(_delivered("region_%s.json" % region),
                        _group_payload("region", region, records))


def _c_segment_files():
    records = _own_ledger()
    for segment in ("consumer", "corporate", "enterprise", "smb"):
        _rollup_matches(_delivered("segment_%s.json" % segment),
                        _group_payload("segment", segment, records))


# ------------------------------------------------------------------ ledger views

def _c_ledger_identity():
    want = _sample()["normalized.jsonl"]
    got = _ledger()
    assert len(got) == len(want)
    assert _projection(got, IDENTITY_FIELDS) == _projection(want, IDENTITY_FIELDS)
    assert all(type(mine[field]) is type(theirs[field])
               for mine, theirs in zip(got, want) for field in IDENTITY_FIELDS)


def _c_ledger_dimensions():
    _shared_fields_match(DIMENSION_FIELDS)


def _c_ledger_money():
    _shared_fields_match(MONEY_FIELDS)


def _c_ledger_record_fields():
    for rec in _own_ledger():
        assert set(rec) == LEDGER_KEYS


def _c_ledger_customer_kind_sku():
    _shared_fields_match(PARTY_FIELDS)


def _c_ledger_price_versions():
    _shared_fields_match(("price_list_version",))


def _c_ledger_cent_amounts():
    """Every cent amount, with fixtures that exercise one step rounding and carry forward."""
    quotes, rules = _rate_table(SAMPLE_SEED, SAMPLE_SCALE)
    per_unit = 0
    carried = 0
    for rec in _sample()["normalized.jsonl"]:
        rate = _rate_for(quotes, rules, rec["posting_date"], rec["currency"])
        if (rec["posting_date"], rec["currency"]) not in quotes:
            carried += 1
        count = rec["quantity"]
        if count and rate is not None:
            places = rules["minor_units"][rec["currency"]]
            unit = abs(rec["native_amount_minor"]) // count
            sign = 1 if rec["native_amount_minor"] > 0 else -1
            each = (Decimal(unit) / (10 ** places) * Decimal(rate) * 100).quantize(
                Decimal(1), rounding=ROUNDERS[rules["rounding"]])
            if sign * count * int(each) != rec["amount_usd_cents"]:
                per_unit += 1
    assert per_unit > 0 and carried > 0
    _shared_fields_match(("amount_usd_cents",))


def _c_duplicate_authority():
    """The surviving source of every event and the count of rows the ladder dropped."""
    _shared_fields_match(("source_file",), same_source=False)
    got = _delivered("data_quality.json")
    want = _sample()["data_quality.json"]
    assert _same(got["rejected_by_code"].get(DUPLICATE_CODE),
                 want["rejected_by_code"].get(DUPLICATE_CODE))
    assert _same(got["duplicate_groups"], want["duplicate_groups"])


def _c_reversal_chain():
    want = _sample()["data_quality.json"]
    got = _delivered("data_quality.json")
    assert _same(got["reversed_pairs"], want["reversed_pairs"])
    assert _same(got["reversal_orphans"], want["reversal_orphans"])
    for code in REVERSAL_CODES:
        assert _same(got["rejected_by_code"].get(code), want["rejected_by_code"].get(code))


def _c_scope_windows():
    """Step 5: the settlement window and each feed's own scope window."""
    want = _sample()
    quality = _delivered("data_quality.json")
    assert _same(quality["rejected_by_code"].get("OUT_OF_SCOPE"),
                 want["data_quality.json"]["rejected_by_code"].get("OUT_OF_SCOPE"))
    assert _same(quality["scoped_sources"], want["data_quality.json"]["scoped_sources"])
    window = want["summary.json"]["settlement_window"]
    assert _delivered("summary.json")["settlement_window"] == window
    rules = _logical_corpus(SAMPLE_SEED, SAMPLE_SCALE)[1]
    for rec in _ledger():
        assert window["start"] <= rec["posting_date"] < window["end_exclusive"]
        scope = rules["scope"].get(str(rec["source_file"]).rsplit(".", 1)[0])
        if scope:
            assert scope[0] <= rec["posting_date"] < scope[1], rec["source_file"]


def _c_source_supersession():
    """Step 6: the revision log retires a feed from a date."""
    want = _sample()["data_quality.json"]
    quality = _delivered("data_quality.json")
    assert _same(quality["rejected_by_code"].get("SUPERSEDED_SOURCE"),
                 want["rejected_by_code"].get("SUPERSEDED_SOURCE"))
    assert _same(quality["superseded_sources"], want["superseded_sources"])
    rules = _logical_corpus(SAMPLE_SEED, SAMPLE_SCALE)[1]
    for rec in _ledger():
        retire = rules["superseded"].get(str(rec["source_file"]).rsplit(".", 1)[0])
        if retire:
            assert rec["posting_date"] < retire, rec["source_file"]


def _c_non_authoritative_sources():
    want = _sample()["data_quality.json"]["accepted_by_source"]
    got = _delivered("data_quality.json")["accepted_by_source"]
    for name in _decoy_feeds():
        assert _same(got.get(name), want[name]), name


# ------------------------------------------------------------- reusability tier

def _c_hidden_drop():
    # A full size drop, so the run is held to the 1200 second limit.
    marks = _transform_drop(EVAL_SEED, SAMPLE_SCALE, "eval-full")
    assert marks == _reference_marks(EVAL_SEED, SAMPLE_SCALE)


def _c_second_hidden_drop():
    marks = _transform_drop(CHALLENGE_SEED, PROBE_SCALE, "challenge")
    assert marks == _reference_marks(CHALLENGE_SEED, PROBE_SCALE)


# ------------------------------------------------------------------- negatives

def _c_negative_hardcoded_sample_answers():
    # Inverted polarity: completes only when the cheat is seen; the weight is negative.
    text = (OUT_DIR / "transform.py").read_text(encoding="utf-8")
    sample = _sample()
    digest = hashlib.sha256(json.dumps(sample["summary.json"],
                                       sort_keys=True).encode()).hexdigest()
    if digest in text or str(EVAL_SEED) in text or str(CHALLENGE_SEED) in text:
        return
    ids = [rec["customer_id"] for rec in sample["normalized.jsonl"][:400]]
    ids += [rec["sku"] for rec in sample["normalized.jsonl"][:400]]
    if sum(1 for token in set(ids) if token in text) >= 10:
        return
    marks = _transform_drop(EVAL_SEED, PROBE_SCALE, "eval")
    assert marks["summary.json"] == _reference_marks(
        SAMPLE_SEED, SAMPLE_SCALE)["summary.json"]


def _renamed_runs():
    origin = _drop(EVAL_SEED, PROBE_SCALE, "eval")
    root = Path(tempfile.mkdtemp(prefix="ldg-name-"))
    first = root / "drop_alpha"
    second = root / "zz_quarter_four_final"
    shutil.copytree(origin, first)
    shutil.copytree(origin, second)
    _relax(root)
    return (_invoke(first, root / "out_a", PROBE_SCALE),
            _invoke(second, root / "out_b", PROBE_SCALE))


def _repeated_runs():
    source = _drop(CHALLENGE_SEED, PROBE_SCALE, "challenge")
    return (_invoke(source, Path(tempfile.mkdtemp(prefix="ldg-det-a-")) / "out", PROBE_SCALE),
            _invoke(source, Path(tempfile.mkdtemp(prefix="ldg-det-b-")) / "out", PROBE_SCALE))


def _c_negative_filename_dependent_behaviour():
    # Inverted polarity: completes only when renaming the directory changes the output.
    # Nondeterminism carries its own negative, so it stands this one down.
    first, second = _cached("repeated", _repeated_runs)
    assert first == second
    left, right = _cached("renamed", _renamed_runs)
    assert left != right


def _c_negative_reads_training_corpus_at_runtime():
    # Inverted polarity: completes only when the output follows a sibling directory.
    root = Path(tempfile.mkdtemp(prefix="ldg-reach-"))
    shutil.copytree(_drop(EVAL_SEED, PROBE_SCALE, "eval"), root / "given")
    shutil.copytree(_drop(CHALLENGE_SEED, PROBE_SCALE, "challenge"), root / "data")
    _relax(root)
    marks = _invoke(root / "given", root / "out", PROBE_SCALE)
    assert marks == _reference_marks(CHALLENGE_SEED, PROBE_SCALE)


def _c_negative_nondeterministic_output():
    # Inverted polarity: completes only when two runs over one drop disagree.
    first, second = _cached("repeated", _repeated_runs)
    assert first != second


def _c_negative_delivered_artifacts_not_from_script():
    # Inverted polarity: completes only when the delivered files differ from what
    # the delivered script writes for a copy of the shipped drop. Path dependence
    # and nondeterminism carry their own negatives, so either one stands this down.
    left, right = _cached("renamed", _renamed_runs)
    first, second = _cached("repeated", _repeated_runs)
    assert left == right and first == second
    mirror = _transform_drop(SAMPLE_SEED, SAMPLE_SCALE, "mirror")
    assert mirror != _delivered_marks()


def _c_negative_writes_outside_the_output_directory():
    # Inverted polarity: completes only when a write lands outside the output directory.
    # Temp writes are collected by _run over every agent run, so the verdict does
    # not depend on which check happened to run the script first.
    root = Path(tempfile.mkdtemp(prefix="ldg-stray-"))
    shutil.copytree(_drop(EVAL_SEED, PROBE_SCALE, "eval"), root / "given")
    workdir = root / "cwd"
    workdir.mkdir()
    _relax(root)
    workdir.chmod(0o777)
    target = root / "nested" / "out"
    before = {str(path) for path in root.rglob("*")}
    _run(root / "given", target, PROBE_SCALE, cwd=workdir)
    after = {str(path) for path in root.rglob("*")}
    inside = str(target) + os.sep
    stray = [path for path in after - before
             if path not in (str(target), str(target.parent)) and not path.startswith(inside)]
    assert stray or _STRAY_TMP


# ------------------------------------------------------------------ registration

def _holds(check):
    # rewardkit runs checks on parallel threads; one lock keeps the shared
    # caches consistent and stops every thread rebuilding the same corpus.
    with _LOCK:
        try:
            check()
        except Exception:
            return False
        return True


@criterion(description="All fourteen declared deliverables exist.")
def artifacts_exist(workspace: Path) -> bool:
    return _holds(_c_artifacts_exist)


@criterion(description="Every deliverable uses the published JSON layout.")
def json_layout(workspace: Path) -> bool:
    return _holds(_c_json_layout)


@criterion(description="The quarter roll-up counts and totals agree with the delivered ledger and rejection tally.")
def summary_counts(workspace: Path) -> bool:
    return _holds(_c_summary_counts)


@criterion(description="The roll-up by region sums the delivered ledger in whole cents.")
def summary_by_region(workspace: Path) -> bool:
    return _holds(_c_summary_by_region)


@criterion(description="The roll-up by segment sums the delivered ledger in whole cents.")
def summary_by_segment(workspace: Path) -> bool:
    return _holds(_c_summary_by_segment)


@criterion(description="The roll-up by category sums the delivered ledger in whole cents.")
def summary_by_category(workspace: Path) -> bool:
    return _holds(_c_summary_by_category)


@criterion(description="The roll-up by channel group sums the delivered ledger in whole cents.")
def summary_by_channel_group(workspace: Path) -> bool:
    return _holds(_c_summary_by_channel_group)


@criterion(description="The roll-up by settlement currency sums the delivered ledger in whole cents.")
def summary_by_currency(workspace: Path) -> bool:
    return _holds(_c_summary_by_currency)


@criterion(description="The roll-up by record kind sums the delivered ledger in whole cents.")
def summary_by_kind(workspace: Path) -> bool:
    return _holds(_c_summary_by_kind)


@criterion(description="The rejection tally matches the reference for every code the rule checks do not own.")
def quality_codes(workspace: Path) -> bool:
    return _holds(_c_quality_codes)


@criterion(description="The health report's inventory names every feed with its delivered accepted count and counts every file of the drop.")
def quality_accepted_by_source(workspace: Path) -> bool:
    return _holds(_c_quality_accepted_by_source)


@criterion(description="The rejected tally of every feed matches the reference.")
def quality_rejected_by_source(workspace: Path) -> bool:
    return _holds(_c_quality_rejected_by_source)


@criterion(description="The per item roll-up summarises the delivered ledger for every item.")
def product_summary(workspace: Path) -> bool:
    return _holds(_c_product_summary)


@criterion(description="All five region files summarise the delivered ledger field for field.")
def region_files(workspace: Path) -> bool:
    return _holds(_c_region_files)


@criterion(description="All four segment files summarise the delivered ledger field for field.")
def segment_files(workspace: Path) -> bool:
    return _holds(_c_segment_files)


@criterion(description="The ledger holds the reference events in the reference order with their posting dates and positions.")
def ledger_identity(workspace: Path) -> bool:
    return _holds(_c_ledger_identity)


@criterion(description="Ledger dimension fields match the reference for every shared event.")
def ledger_dimensions(workspace: Path) -> bool:
    return _holds(_c_ledger_dimensions)


@criterion(description="Ledger currency, native amount and quantity match the reference for every shared event.")
def ledger_money(workspace: Path) -> bool:
    return _holds(_c_ledger_money)


@criterion(description="Every ledger record carries exactly the seventeen contract fields.")
def ledger_record_fields(workspace: Path) -> bool:
    return _holds(_c_ledger_record_fields)


@criterion(description="Ledger customer, kind and item match the reference for every shared event.")
def ledger_customer_kind_sku(workspace: Path) -> bool:
    return _holds(_c_ledger_customer_kind_sku)


@criterion(description="Every shared ledger event carries the price book version covering its posting date.")
def ledger_price_versions(workspace: Path) -> bool:
    return _holds(_c_ledger_price_versions)


@criterion(description="Ledger cent amounts match the reference, half even ties and carry forward quotes included.")
def ledger_cent_amounts(workspace: Path) -> bool:
    return _holds(_c_ledger_cent_amounts)


@criterion(description="Repeated events survive from the source the authority ladder ranks first, with the reference group and loser counts.")
def duplicate_authority(workspace: Path) -> bool:
    return _holds(_c_duplicate_authority)


@criterion(description="The reversal walk removes the same pairs and orphans as the reference.")
def reversal_chain(workspace: Path) -> bool:
    return _holds(_c_reversal_chain)


@criterion(description="The settlement window and the feed scope windows reject the reference rows, are reported, and keep no ledger row outside them.")
def scope_windows(workspace: Path) -> bool:
    return _holds(_c_scope_windows)


@criterion(description="The revision log retires the reference rows, is reported, and keeps no ledger row from a feed after its retirement date.")
def source_supersession(workspace: Path) -> bool:
    return _holds(_c_source_supersession)


@criterion(description="Each non authoritative feed contributes the reference number of accepted rows.")
def non_authoritative_sources(workspace: Path) -> bool:
    return _holds(_c_non_authoritative_sources)


@criterion(description="The delivered script transforms an unseen full size drop to the reference result within the full size time limit.")
def hidden_drop(workspace: Path) -> bool:
    return _holds(_c_hidden_drop)


@criterion(description="The delivered script transforms a second unseen drop, which publishes its own policy registers and source profiles, to the reference result.")
def second_hidden_drop(workspace: Path) -> bool:
    return _holds(_c_second_hidden_drop)


@criterion(description="The delivered script carries the shipped answers or the shipped identifiers.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_c_negative_hardcoded_sample_answers)


@criterion(description="The delivered script changes its result when the input directory is renamed.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_c_negative_filename_dependent_behaviour)


@criterion(description="The delivered script reads a sibling directory in place of the one it was given.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _holds(_c_negative_reads_training_corpus_at_runtime)


@criterion(description="Two runs of the delivered script over one drop disagree.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_c_negative_nondeterministic_output)


@criterion(description="The delivered script writes files outside the output directory it was given.")
def negative_writes_outside_the_output_directory(workspace: Path) -> bool:
    return _holds(_c_negative_writes_outside_the_output_directory)


@criterion(description="The delivered artifacts differ from what the delivered script writes for a copy of the shipped drop.")
def negative_delivered_artifacts_not_from_script(workspace: Path) -> bool:
    return _holds(_c_negative_delivered_artifacts_not_from_script)


criteria.artifacts_exist(weight=1)
criteria.json_layout(weight=1)
criteria.summary_counts(weight=1)
criteria.summary_by_region(weight=1)
criteria.summary_by_segment(weight=1)
criteria.summary_by_category(weight=1)
criteria.summary_by_channel_group(weight=1)
criteria.summary_by_currency(weight=1)
criteria.summary_by_kind(weight=1)
criteria.quality_codes(weight=3)
criteria.quality_accepted_by_source(weight=3)
criteria.quality_rejected_by_source(weight=3)
criteria.product_summary(weight=3)
criteria.region_files(weight=3)
criteria.segment_files(weight=3)
criteria.ledger_identity(weight=3)
criteria.ledger_dimensions(weight=5)
criteria.ledger_money(weight=5)
criteria.ledger_record_fields(weight=1)
criteria.ledger_customer_kind_sku(weight=5)
criteria.ledger_price_versions(weight=5)
criteria.ledger_cent_amounts(weight=5)
criteria.duplicate_authority(weight=5)
criteria.reversal_chain(weight=5)
criteria.scope_windows(weight=5)
criteria.source_supersession(weight=3)
criteria.non_authoritative_sources(weight=5)
criteria.hidden_drop(weight=5)
criteria.second_hidden_drop(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_writes_outside_the_output_directory(weight=-3)
criteria.negative_delivered_artifacts_not_from_script(weight=-3)


if __name__ == "__main__":
    print(json.dumps({"checks": len([n for n in dir() if n.startswith("_c_")])},
                     sort_keys=True))
