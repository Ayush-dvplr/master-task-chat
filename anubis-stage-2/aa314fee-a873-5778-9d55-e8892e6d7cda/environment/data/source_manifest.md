# Source manifest

Source codes and tiers are declared in `source_declarations.properties`. Each
record file except `site_clock_marks.csv` opens with one comment line starting
with `#` that carries `declared_rows=`, the count the producing system
reported. The next line is the column header. The declared count is
informational and is not always the number of rows the file carries.

## Order book, code OBK

Columns `request_ref,customer_ref,site,node,quantity,quantity,unit,
effective_local,fold,recorded_utc,source_batch,row_note`. The file carries two
columns under the title `quantity`. The first is the governing figure. The
second is a restatement kept for audit and carries no weight. `unit` is
`wafers` or `lots`. `effective_local` is site local wall time and pairs with
`fold`. `recorded_utc` is the instant the row reached the system.

## Contract registry, code REG

Tab separated. Columns `request_ref,customer_ref,site,node,quantity,unit,
effective_utc,recorded_utc,batch,comment`. A node that was never stated
appears as an empty field or as the two characters `\N`. Some rows stop after
`recorded_utc` and carry neither batch nor comment.

## Legacy intake, code LGI

Fixed width, no header, one request per line. Columns by character position,
counting from one: reference 1 to 12, customer code 13 to 26, site 27 to 34,
node 35 to 40, quantity in hundredths of a wafer 41 to 50, effective site
local `YYYYMMDDHHMMSS` 51 to 64, recorded UTC `YYYYMMDDHHMMSS` 65 to 78, batch
79 to 84, note from 85 onward.

## State events, code EVT

JSON Lines with keys `event_id`, `request_ref`, `version`, `action`,
`recorded_utc`, `actor`, and for the `reinstate` action an `authority_ref`
that is a string, `null`, or absent.

## Amendment notices, code AMD

JSON Lines with keys `notice_id`, `request_ref`, `field`, `value`,
`supersedes`, `recorded_utc`, `approval_ref`.

## Approval audit

Each entry is one line, `<site local stamp> site=<site> apl=<identifier>
approver=<identifier> scope=<scope> ref=<identifier> action=endorse`. A line
beginning with two spaces continues the entry above it and carries no instant
of its own. Stamps are site local and carry the recorder skew of the site
declared in `derivation_policy.ini`. The three files hold thirds of the same
audit, newest first.

## Registers

`authority_roles.csv` columns `approver_id,role,scope,effective_utc,
expires_utc,recorded_utc,revision_seq,granted_by`.
`retraction_notices.csv` columns `retraction_id,target_id,target_kind,
recorded_utc,actor`, where `target_kind` is `notice`, `exception` or
`retraction`.
`entitlement_ceilings_p*.csv` columns `customer_id,epoch_seq,ceiling,unit,
declaring_site,effective_local,fold,recorded_utc,revision_seq`.
`commitment_agreements.csv` columns `agreement_id,customer_id,site,node,floor,
unit,recurrence,first_cycle,until_cycle,effective_local,recorded_utc,
revision_seq`.
`priority_register.csv` columns `agreement_id,priority_rank,effective_local,
recorded_utc,revision_seq`.
`commitment_exceptions.csv` columns `exception_id,agreement_id,cycle,action,
target_cycle,approval_ref,recorded_utc`.
`site_capacity_declarations.csv` columns `site,cycle,tool_group,basis,value,
unit,status,nodes,effective_local,fold,recorded_utc,revision_seq`, where a
negative value is written in parentheses and `nodes` is a pipe separated list.
`node_substitution_factors.csv` columns `site,cycle,from_node,to_node,
factor_per_100,factor_display,status,effective_local,fold,recorded_utc,
revision_seq`, where `factor_display` is a decimal comma rendering kept for
reading only.
`customer_master.csv` columns `customer_id,epoch_seq,epoch_from_utc,
epoch_to_utc,legal_name,segment,home_site,status,effective_utc,recorded_utc,
revision_seq`.
`customer_alias_map.csv` columns `alias_code,target_code,effective_utc,
expires_utc,recorded_utc,revision_seq`.
`site_clock_marks.csv` columns `site,local_date,from_local_time,
utc_offset_minutes,mark_kind`.

## Observation logs

`governance_observations.log` and `deficit_observations.log` hold settled
outcomes from periods before the horizon, labelled `P01` to `P24`. They carry
no request of this horizon. Each line is a sequence of `key=value` pairs.
