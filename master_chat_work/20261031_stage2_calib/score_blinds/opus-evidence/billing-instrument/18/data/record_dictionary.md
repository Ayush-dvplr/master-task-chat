# Record dictionary

This dictionary gives the layout and the meaning of every input of a billing cycle extract. Files are listed in alphabetical order. The billing rules that use these columns are in the billing standard; the reports are described in the report layout.

## Conventions

Every file is UTF-8 text. A byte order mark at the very start of a file belongs to no column or value. CSV files have one header row, separate fields with commas and may quote a field with double quotes. Every value is read with surrounding spaces removed. Identifiers compare exactly after that, except service codes and alias codes, which compare after conversion to upper case. An instant is written YYYY-MM-DDTHH:MM:SS and a day is written YYYY-MM-DD. The exchange clock of the desk keeps UTC, and every instant in this extract is on the exchange clock unless its column says otherwise.

## amendments.jsonl

One JSON object per non-empty line, with the keys amendment, issued_at, action, handset, seq, minutes and reverts. amendment is the amendment identifier. issued_at is the issue instant. action is void, minutes or revert. For void and minutes, handset and seq name the closing (seq is an integer) and reverts is null. For minutes, minutes is the new worked minutes as a positive integer; it is null for the other actions. For revert, handset and seq are null and reverts holds the identifier of the amendment the revert names.

## clients.csv

The client roster, with the columns client, line, segment, region, plan and zone. line is the exchange line the client is reached on; no two clients share a line. segment is one of consumer, corporate, enterprise and smb. region is one of central, east, north, south and west. plan names a row of the plan register and zone names a zone of the zone rules.

## closings.csv

The main export of handset closings, with the columns ref, handset, seq, client, service, stamped_at and worked_minutes. ref is the closing reference. handset names the handset that recorded the closing and seq is its handset sequence number, an integer. client names the client served and service is the service code as recorded on the handset. worked_minutes is a positive integer. stamped_at is the instant on the handset clock at which the assistant closed the task. A handset clock is set when the handset is issued to an assistant and is never adjusted afterwards, so each handset differs from the exchange clock by one whole number of minutes, its clock offset: the exchange clock reading minus the handset clock reading, from -19 to 19. The completion instant of a closing is its stamped_at moved onto the exchange clock by adding the clock offset of its handset.

## code_aliases.csv

The alias table, with the columns alias and service. Each alias is an older service code and service is the catalog code it maps to.

## cycle.json

The cycle header, one JSON object with the keys cycle, first_day, last_day, rate_card and minimum_invoice_micro. cycle is the cycle name. first_day and last_day are days. rate_card is the file name of the rate card in force. minimum_invoice_micro is an integer amount in micro-units.

## exchange_register.csv

The traffic register of the exchange, with the columns day, slot, line and calls. Every received closing makes one closing call on the line of its client at its completion instant. The day of a call is the date of its completion instant, and its slot is the minute of that day holding the completion instant: the slot written HH:MM starts at that time of day, includes its start and ends one minute later, excluding its end. A row gives the number of calls registered on one line in one slot of one day, as a positive integer. The exchange can lose a call, and a lost call is counted in no row; a row never counts more calls than the closings of that line whose completion instants fall in that slot. A slot of a line with no registered call has no row.

## holidays.csv

Regional holidays, with the columns region, day and name. A holiday applies to the clients of its region on that day.

## legacy_closings.txt

The legacy export of handset closings. Lines that start with # are header lines, and blank lines carry nothing. Every other line is one closing with seven fields separated by the character |, in this order: ref, handset, seq, client, service, stamped and duration. The first five fields mean what the same columns of the main export mean. stamped is the instant on the handset clock written DD.MM.YYYY HH:MM:SS, and it plays the part of stamped_at. duration is a positive integer in the unit named by the header line that begins # duration unit: followed by seconds or minutes. A duration in minutes is the worked minutes. A duration in seconds becomes worked minutes when divided by 60 and rounded up to a whole minute. The received closings of an extract are every row of the main export and every legacy row that is not a duplicate.

## plans.csv

The plan register, with the columns plan, included_minutes and credit_tiers. included_minutes is a non-negative integer. credit_tiers lists the credit tiers of the plan as tier names separated by single spaces.

## Rate cards

A rate card is a CSV file with the columns service, tier, rate_micro_per_minute, effective_from and effective_to. service is a catalog code, tier is a tier name and rate_micro_per_minute is a positive integer in micro-units per billable minute. effective_from is a day and effective_to is a day or empty. The rows of one rate card for one service and tier have effective intervals that do not overlap.

## service_catalog.csv

The service catalog, with the columns service, product_line and increment_minutes. service is the catalog code, product_line names the product line of the service, and increment_minutes is the billing increment as a positive integer.

## zone_rules.csv

The zone rules, with the columns zone, from_utc and utc_offset_minutes. A row gives the UTC offset in minutes that the zone keeps from its from_utc instant, which it includes, until the from_utc instant of the next row of the same zone. Local time is the exchange clock reading plus the UTC offset in force.
