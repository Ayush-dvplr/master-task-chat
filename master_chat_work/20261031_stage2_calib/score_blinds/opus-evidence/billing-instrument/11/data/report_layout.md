# Report layout

This layout gives the form of every report of a billing cycle run. Each field takes its meaning from the rule of the billing standard or the column of the record dictionary that it names.

## Byte form

Every report ending in .json holds one JSON object. It is written compactly: no space or line break inside it, the separators , and : with nothing around them, the keys of every object in code point order, and every character outside ASCII written as a \u escape. One line feed follows it, and nothing else. normalized.jsonl holds one such object per line, each followed by one line feed; with no billed closing it is empty. Whole numbers are JSON integers, flags are true or false, and identifiers, instants, days and names are JSON strings. Every list of identifiers is in code point order.

## Standard output

A run prints one line for each report it writes, in code point order of the report file names, and nothing else. Each line is the word wrote, one space, the file name, one space and the size of the written file in bytes as a decimal integer.

## data_quality.json

- amendments_without_effect: the identifiers of every amendment that has no effect under the amendments rule, together with every amendment cancelled by a revert.
- closings_received: the number of received closings.
- duplicates: the closing references of the legacy rows that are duplicates under the duplicates rule.
- input_files: the names of every file in the extract.
- outside_cycle: the closing references of the received closings outside the cycle under the cycle rule, rejected closings left out.
- rejected: an object with one key per rejected closing reference, whose value is the rejection reason.
- unrated: the closing references of the closings that are unrated under the pricing rule, rejected, void and outside-cycle closings left out.
- void: the closing references of the void closings under the amendments rule, rejected and outside-cycle closings left out.

## normalized.jsonl

One object per billed closing, in order of completion instant and, for equal completion instants, in code point order of closing reference.

- billable_minutes: the billable minutes.
- charged_minutes: the charged minutes under the allowance credit rule.
- client, handset, ref: as recorded.
- completed_at: the completion instant.
- credited_minutes: the minutes credited under the allowance credit rule.
- gross_micro, net_micro: the gross and net amounts under the money rules.
- line, region, segment: those of the client in the client roster.
- local_day: the local business day.
- product_line: the product line of the service.
- rate_micro_per_minute: the rate under the pricing rule.
- seq: the handset sequence number, as an integer.
- service: the service, as its catalog code.
- tier: the tier.
- worked_minutes: the worked minutes after the amendments rule.

## product_summary.json

- product_lines: a list with one object per product line of the service catalog, in code point order of product line, each holding billable_minutes, closings, gross_micro, net_micro and product_line. closings counts the billed closings of the line and the other figures total them.

## region_central.json, region_east.json, region_north.json, region_south.json, region_west.json

One report per region, each written whatever its scope.

- by_tier: an object with one key per tier of at least one billed closing of the region, whose value is the net amount of those closings.
- clients: the clients with at least one billed closing in the region.
- closings: the number of billed closings of the region.
- credit_micro, gross_micro, net_micro: the totals of the billed closings of the region.
- in_scope: the region test of the minimum invoice rule.
- net_cents: net_micro in whole cents under the money rules.
- region: the region name.

## segment_consumer.json, segment_corporate.json, segment_enterprise.json, segment_smb.json

One report per segment, each written whatever its scope, with the keys of a region report except that segment, the segment name, takes the place of region, every figure covers the billed closings of the segment, and in_scope is the segment test of the minimum invoice rule.

## summary.json

- by_tier: as in a region report, over every billed closing.
- closings_billed: the number of billed closings.
- credit_micro, gross_micro, net_micro: the totals of every billed closing.
- cycle: the cycle name.
- net_cents: net_micro in whole cents under the money rules.
- reconciliation: an object holding normalized_net_micro, the total of net_micro over normalized.jsonl; product_net_micro, the total over the product lines of product_summary.json; region_net_micro, the total over the five region reports; segment_net_micro, the total over the four segment reports; and residual_micro, which is product_net_micro plus region_net_micro plus segment_net_micro minus three times normalized_net_micro.
