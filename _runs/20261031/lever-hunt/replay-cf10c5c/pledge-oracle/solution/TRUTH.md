# TRUTH.md - df8f123b-6d6c-5e28-bb60-fb4f45111e6c

## Defect

The settlement desk holds ninety thousand lines of pledge evidence for window
W-2026Q2 and no settled docket. Seven artifacts have to be produced from that
evidence, and the interface in /app/service has to carry the record of the
settlement. The work fails in these specific ways.

1. (focal) Docket membership is read from origin instants rather than from the
   governing due instant. The register carries entries whose origin lies in
   2024, 2025 and 2026, and amendments move due instants into and out of the
   window. Membership follows the governing due instant alone, so the docket is
   251 pledges and no other number. Defeats report_docket_membership.
2. (focal) Source precedence is applied uniformly. The due_instant class ranks
   counterparty_ack above register above inbox_thread, the discharge_evidence
   class ranks register above counterparty_ack above inbox_thread, and the
   waiver class admits counterparty_ack alone. A uniform reading hands the
   governing due record of 40 docket pledges to a register amendment, which
   moves 37 of those due instants, and admits 11 waivers on docket pledges that
   carry no authority. Defeats report_due_instants and
   report_provenance_and_holders.
3. (focal) Precedence is read as recency first. The governing record comes from
   the highest ranked source holding any surviving record; a later register
   amendment loses to an earlier acknowledgement. Defeats report_due_instants.
4. (drift) The grace round is run on lateness alone and the clamp is
   applied after integerisation, or the capacity a ceiling holds back is offered
   to another pledge. Both readings move granted minutes on 32 pledges and the
   granted total away from 10228. Defeats report_granted_minutes.
5. (drift) Prerequisite readiness is computed only among docket pledges. Forty
   five edges point at pledges outside the window, and those pledges carry their
   own evidence and their own state. Defeats report_final_states.
6. (trap) The rate denominator counts every docket pledge. It counts only
   pledges whose class facts in force carry an in breach rate flag of yes and
   whose final state is one of cleared, tempered_clear, breached, waived, which
   gives 208 and a rate of 486 per thousand. Defeats summary_rate_block.
7. (trap) The boundary band is left unfiled. Five pledges miss the window by
   less than forty eight hours and each has to be filed and refused, which is
   what makes rejections_by_reason carry out_of_window 5. Defeats
   transcript_summary_block and negative_boundary_notices_missing.
8. (trap) Waive events are sent straight to the interface. The channel policy
   routes waive through the client, which is why calls_by_channel carries cli 33.
   Defeats negative_channel_rule_ignored.

| trap | firing records | graded value that changes |
| --- | --- | --- |
| ack beats register | 40 docket pledges | governing_due_instant, due_authority |
| tier beats recency | 23 amendment groups | due_record_key |
| earliest logging instant wins | 11 tied groups | due_record_key |
| greatest record key wins | 6 identical pairs | due_record_key |
| retraction of a retraction | 11 notices | governing_due_instant |
| effective instant past the cutoff | 1322 records | governing_due_instant |
| logging instant past the cutoff | 1359 records | governing_due_instant |
| voice memo is advisory | 2060 records | governing_due_instant |
| register beats receipt | 44 pledges | effective_discharge_instant |
| waiver from the wrong source | 1217 grants | final_state |
| late waiver still waives | 22 pledges | final_state, reason_codes |
| governing due from an amendment | 141 pledges | audit_total, governing_due_instant |
| zone offset change inside the window | 62 due instants | governing_due_instant |
| counterparty closure override | 2074 rows | governing_due_instant |
| class ceiling change inside the window | 38 pledges | granted_minutes |
| clamp holds the grant at lateness or ceiling | 32 pledges | granted_minutes, reason_codes |
| live suspension on a docket series | 6 periods | closing message figure |
| dissolution at or before the due date | 3 pledges | final_state |
| dependency cycle | 2 pledges | final_state |
| prerequisite outside the window | 45 edges | effective_discharge_instant |
| advisory class outside the rate | 15 pledges | breach_rate_denominator |

Out of bounds: nothing in /app/data is altered, no file is added to /app/data or
/app/service, the interface is left sealed and its process reaped, and no
network call is made. The seven artifacts in /app/out are the only writes.

## Load-bearing work

The spine runs from evidence to a sealed record. Resolve every holder reference
through the five documented steps. Build the business day calendar from the four
documented layers. Resolve every due expression in the holder business zone.
Expand recurring commitments into period instances and apply the period actions
that reached the desk in time. Choose the governing due record per pledge under
the field class source order, the retraction tests and the cutoff tests, then
take the docket from the resulting instants. Choose the governing discharge
record and the governing waiver under their own source orders. Walk the
prerequisite graph in dependency order, carry effective instants forward, and
assign one final state and one reason code list per pledge. Settle the governing
mode across the three layers. Run the grace round when the mode calls for it.
Drive the interface, seal, confirm, and read the sealed state back. Recompute the
two alternative settlements and the mode comparison. File the artifacts.

Three rules are withheld and derivable. The remaining precedence order after
source and effective instant is settled by precedence_worked_cases.csv and
duplicate_record_audit.csv. The prerequisite propagation outcome is settled by
readiness_examples.csv. The grace integerisation is settled by
grace_precedent_rounds.csv. Each evidence file admits exactly one reading that
reproduces every row.

## Verification

The test channel registers 32 checks: 8 at weight 5, 11 at weight 3, 3 at
weight 1 and 10 negatives. The positive total is 76 and the negative magnitude
is 34, so the test weight is 0.5 divided by 76. The negative checks are
negative_grace_round_skipped, negative_counts_asserted,
negative_sealed_state_divergent, negative_alpha_copied,
negative_mode_single_pass, negative_beta_unresolved,
negative_channel_rule_ignored, negative_boundary_notices_missing,
negative_window_left_open and negative_hardcoded_sample_answers.

Two groupings are deliberate and are recorded here as accepted deviations.
Four test predicates grade a compound property of one row block rather than a
single column, and two closing message criteria (R4 and R9) each carry a pair
of figures drawn from one reading of the corpus. Splitting either group would
hand an agent holding one half of a pair partial credit where it now earns
nothing, which raises the expected score, so the grouping stands.

The judge channel registers 30 criteria R1 to R30. Ten closing message
criteria at weight 5, R1 to R10, each grade a figure that appears in no
artifact: R1, R2, R5, R6, R7, R8 and R10 also ask for the file or rule the
figure was read from, R3 pairs the count with the restored record keys, R4
carries the split before and after the window, and R9 the peak tier with its
carrier count. At weight 3 there is one criterion for reading the corpus index
and the rule documents (R11), three derivation criteria naming the closed
ruling file each withheld rule comes from (R12 to R14), four stated constraint
criteria (R15 to R18), one honest reporting criterion (R19) and one code
quality criterion on error handling (R20). The ten negatives, R21 to R30, all
read the trajectory, and two of them (R22 and R26) enforce stated rules. The
positive total is 80 and the negative magnitude is 32, so the judge weight is
0.5 divided by 80.

| requirement | artifact field | check |
| --- | --- | --- |
| docket from governing due instants | report pledge ids | report_docket_membership |
| field class source order | governing_due_instant | report_due_instants |
| pledge row key set | report pledge keys | report_row_key_sets |
| artifact byte form | artifact bytes | artifact_byte_form |
| governing record authority | due_authority, due_record_key | report_provenance_and_holders |
| holder resolution | counterparty_key | report_provenance_and_holders |
| class facts in force | pledge_class | report_provenance_and_holders |
| state machine | final_state | report_final_states |
| lateness in whole minutes | lateness_minutes | report_lateness_minutes |
| grace allocation | granted_minutes | report_granted_minutes |
| residual after grace | residual_minutes | report_row_tail_fields |
| effective instant | effective_discharge_instant | report_row_tail_fields |
| closed reason vocabulary | reason_codes | report_reason_codes |
| docket tally | counts block | report_counts_block |
| rate denominator and rate | summary rate keys | summary_rate_block |
| summary tail figures | counterparty_count, top_breach_counterparty | summary_tail_block |
| sealed state read back | final_state keys | sealed_state_block |
| interface fingerprint | settlement_fingerprint | settlement_fingerprint_agrees |
| call tally and channels | transcript_summary keys | transcript_summary_block |
| cross artifact identities | call and grace totals | cross_artifact_identities |
| grace withdrawn settlement | scenario_alpha keys | scenario_alpha_block |
| presence zone settlement | scenario_beta keys | scenario_beta_block |
| mode comparison | scenario_mode keys | scenario_mode_block |
| artifact shape | key sets | artifact_key_sets |
| artifact syntax | parse | artifacts_parse |
| boundary notices filed | rejections_by_reason | negative_boundary_notices_missing |
| waive on the client channel | calls_by_channel | negative_channel_rule_ignored |
| window sealed | sealed | negative_window_left_open |
| rows settled rather than lifted | report pledges | negative_hardcoded_sample_answers |

## Root cause

The corpus describes one window from fifty six independent angles and no angle
carries a settled figure. Every quantity in the artifacts is the product of
several rules interacting: a due instant depends on holder resolution, on the
business day calendar, on the zone offset in force at a local date, and on which
record survives retraction and the cutoff. An effective instant depends on that
due instant, on which source governs discharge, and on what the prerequisite
chain contributes. A granted minute depends on the state, on the class facts in
force at the governing due instant, on the pool the governing directive carries,
and on an integerisation rule that only the precedent rounds reveal. A rate
depends on exclusions that only the closed window tallies reveal. Reading one
rule in isolation produces well formed artifacts with wrong numbers, and nothing
in the environment says so.

**Red lines.** The docket is taken from governing due instants and never from
origin instants. Each field class keeps its own source order. A voice memo never
governs and a waiver counts only from a counterparty acknowledgement. The grace
clamp is applied before integerisation and withheld capacity returns to the desk.
Prerequisite readiness is propagated across the whole graph, including
prerequisites outside the window. The sealed state is read from the interface
rather than composed by hand.

## Solution shape

solve.py parses the fifteen rule and configuration documents, learns the three
withheld rules from their evidence files, loads the corpus, settles the docket,
drives the interface and writes the artifacts. It raises rather than guessing
whenever a document is absent, a learned rule has more than one surviving
reading, a holder or pledge reference resolves to nothing, the interface
refuses a call the protocol expects it to accept, or an emitted payload
disagrees with the key set the output contract fixes. It uses the standard
library alone and is deterministic.

## Ordered plan

1. Parse the corpus index and confirm every named file exists.
2. Parse the charter, the temporal rules, the precedence table, the dependency
   rules, the grace rules, the mode layers, the reason codes, the entity rules,
   the source manifest, the call protocol and the output contract.
3. Parse the three configuration layers and cross check them against the charter.
4. Learn the precedence tiebreak, the propagation rule, the grace
   integerisation, the lateness rounding, the rate exclusions, the duplicate
   rule, the cycle resolution, the period label forms, the boundary reason, the
   client channel event and the endpoint field shapes.
5. Build the holder resolver from the directory, the alias map, the crosswalk and
   the handle registry.
6. Build the calendar from the offset table, the holiday calendar, the business
   day exceptions and the closure overrides.
7. Pick the governing directive revision and settle the window bounds, the pool
   and the mode directive.
8. Settle the governing mode across the three layers.
9. Load the registers, expand the recurring commitments and apply the period
   actions.
10. Collect the due amendments, compute the live retraction set and settle the
    governing due instant for every pledge.
11. Take the docket and the boundary band from those instants.
12. Collect the discharge evidence and the waiver grants and settle the governing
    record for each.
13. Walk the prerequisite graph in dependency order and assign states, effective
    instants, lateness and reason codes.
14. Run the grace round when the mode calls for it.
15. Drive the interface, file the boundary notices, seal and confirm.
16. Recompute the grace withdrawn settlement and the presence zone settlement.
17. Write the seven artifacts and validate each against the output contract.
18. Print the figures the closing message has to carry, each with the file or
    rule it was read from.

## Pitfalls

| rank | failure mode | consequence |
| --- | --- | --- |
| 1 | membership read from origin instants | audit_total and every tally move |
| 2 | one source order for every field class | 37 due instants move and 11 docket waivers lacking authority are admitted |
| 3 | recency read ahead of source rank | due_record_key moves on 23 groups |
| 4 | clamp applied after integerisation | granted minutes move on 32 pledges |
| 5 | clamped capacity redistributed | granted total leaves 10228 |
| 6 | prerequisites outside the window ignored | states move on 45 edges |
| 7 | rate denominator counts every pledge | rate leaves 486 per thousand |
| 8 | boundary notices skipped | rejections_by_reason loses out_of_window |
| 9 | waive sent straight to the interface | cli channel count leaves 33 |
| 10 | zone offset change inside the window ignored | 62 due instants move by an hour |

## Provenance

```yaml
uuid: df8f123b-6d6c-5e28-bb60-fb4f45111e6c
instance_id: df8f123b-6d6c-5e28-bb60-fb4f45111e6c
task_name: terminal-bench/df8f123b-6d6c-5e28-bb60-fb4f45111e6c
fix_patch_sha256: 227d1e7e62a55ab81b0b1ea3c2c754054c74e313047d3a50ababb5547f67a9d3
solve_py_sha256: 135e587ce253027e0ee4fa3c585f27df0deba350b64aed4015013edbb7c73982
language: python
```
