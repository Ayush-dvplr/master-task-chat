# Output schema reference

Column names, column order and row order are part of every artifact. Delimited
artifacts carry a header row. An artifact with no data rows carries its header
row and nothing else. A line oriented json artifact with no records is a file
of zero bytes.

## reading_ledger.csv

    link_id,epoch_index,session_id,receiver_id,attempt_no,acq_time_s,
    raw_offset_ps,report_id,correction_ps,corrected_ps,sense,difference_ps,
    cluster_rows

Ordered by link_id then epoch_index. cluster_rows is the number of rows the
cluster held after the row by row predicates and before selection.

## withdrawal_ledger.tsv

    drop_reason,link_id,epoch_index,session_id,attempt_no,lock_state

Ordered by drop_reason, then link_id, then epoch_index compared as text, then
session_id, then attempt_no. epoch_index is the whole number of the epoch the
row was attributed to, or the text NONE when it was attributed to none.

## calibration_selection.csv

    link_id,epoch_index,report_id,revision,status,effective_epoch_s,
    delay_delta_ps

Ordered by link_id then epoch_index. A reading with no applicable report
carries report_id REPORT_NONE, revision 0, status CAL_ABSENT,
effective_epoch_s 0 and delay_delta_ps 0.

## link_differences.psv

    epoch_index|link_id|node_a|node_b|technique|sense|difference_ps

Ordered by epoch_index then link_id. Epoch first, not link first.

## link_graph.json

    {"hub_node", "component_count", "components": [
       {"component_id", "role", "root_node", "member_nodes",
        "tree_edges": [{"link_id","parent_node","child_node","technique",
                        "published_uncertainty_ps"}],
        "excluded_link_ids"} ]}

Components in identifier order. tree_edges in the order the edges were
admitted. member_nodes and excluded_link_ids in ascending order.

## epoch_grid.csv

    epoch_index,epoch_instant_s,canonical_readings,tree_links_present,
    contributing_oscillators,epoch_state

One row per grid epoch, in epoch order. tree_links_present counts the links
that are tree edges of any component and carry a canonical reading at that
epoch.

## deadtime_ledger.jsonl

One compact object per line, keys epoch_index, scope, subject, cause. Ordered
by epoch_index, scope, subject, cause. scope is SCOPE_LINK, SCOPE_NODE or
SCOPE_OSCILLATOR. cause is the link identifier for SCOPE_NODE,
CAUSE_NO_READING for SCOPE_LINK and CAUSE_NO_MONITOR for SCOPE_OSCILLATOR.

Each absence is stated once. A node that is out at an epoch takes one
SCOPE_NODE record and its oscillators take none, so a SCOPE_OSCILLATOR record
only ever carries CAUSE_NO_MONITOR.

## oscillator_series.csv

    osc_id,node_id,epoch_index,deviation_ps,series_flag

One row per catalogued oscillator per grid epoch, ordered by osc_id then
epoch_index. deviation_ps is empty on an absent epoch.

## prediction_book.json

    {"window_epochs", "history_minimum", "oscillators": [
      {"osc_id","node_id","osc_class","window_first","window_last",
       "valid_count","anchor_epoch","anchor_deviation_ps","frequency_atto",
       "included","exclusion_reason"} ]}

anchor_deviation_ps and frequency_atto are whole numbers and are written as
json numbers.

valid_count is the number of valid deviations the oscillator holds in its
history window and is published for every oscillator, whether it was included
or excluded and whatever the reason. It is zero only when the window really
holds no valid deviation.

Oscillators in identifier order. An excluded oscillator carries anchor_epoch 0,
anchor_deviation_ps 0, frequency_atto 0 and its reason; an included one carries
an empty reason. frequency_atto is the exact frequency rendered as a whole
number.

## dispersion_table.csv

    osc_id,node_id,osc_class,valid_count,dispersion_ps,weight_source,raw_weight

One row per included oscillator, ordered by dispersion_ps ascending then
osc_id. raw_weight is a ratio.

## weight_book.json

    {"ensemble_size","total_weight","oscillator_cap","node_cap",
     "oscillator_cap_outcome","node_cap_outcome","final_sweep_outcome",
     "sweeps_used","damping_numerator","damping_denominator","weight_places",
     "terminal_residual",
     "oscillators":[{"osc_id","node_id","raw_weight","after_oscillator_cap",
                     "after_node_cap","final_weight"}],
     "node_totals":[{"node_id","weight"}]}

Oscillators in identifier order, node totals in node order. Every weight, the
two cap values and the total are ratios and are written as json strings.
ensemble_size, sweeps_used, damping_numerator, damping_denominator and
weight_places are whole numbers and are written as json numbers.
terminal_residual is a ratio and is written as a json string. sweeps_used
counts the passes of the first pass only.

## weight_sweep_trace.jsonl

One compact object per pass, keys phase, sweep, offenders, excess_ratio,
holders, residual_ratio. excess_ratio and residual_ratio are ratios and are
written as json strings. The records of the first pass come first, then the node cap pass, then
the third pass. offenders is an ascending list of identifiers, of oscillators
in an oscillator phase and of nodes in the node phase.

sweep counts within its own phase and starts at 1 in each of them, so the first
pass numbers its sweeps 1, 2 and upward, and the node cap pass and the third
pass each carry the single record sweep 1. A pass that moved nothing writes no
record at all. holders is the count of holders that took the redistributed
excess and excess_ratio is the mass that moved, written as a ratio.

## ensemble_scale.csv

    epoch_index,epoch_state,contributing_oscillators,denominator_weight,
    free_scale_ps

One row per grid epoch, in epoch order. free_scale_ps is empty on a void epoch
and denominator_weight is the ratio zero there.

## steering_plan.json

    {"decision_epoch","horizon_epochs","grid_atto","departure_ps",
     "raw_step_atto","step_atto","outcome"}

departure_ps and raw_step_atto are ratios and are written as json strings.
step_atto, decision_epoch, horizon_epochs and grid_atto are whole numbers and
are written as json numbers.

## steered_scale.csv

    epoch_index,epoch_state,free_scale_ps,correction_ps,steered_scale_ps

One row per grid epoch, in epoch order. correction_ps is written at every
epoch, including a void one.

## node_offsets.csv

    node_id,epoch_index,offset_ps,offset_flag

One row per registered node per grid epoch, ordered by node_id then
epoch_index.

## uncertainty_budget.tsv

    node_id,component_id,role,path_length,term_count,u_combined_ps2,
    u_linear_ps

One row per registered node, ordered by node_id.

## dissemination_ledger.psv

    node_id|status|epochs_available|offset_mean_ps|u_combined_ps2|u_linear_ps

One row per registered node, ordered by epochs_available descending then
node_id ascending. offset_mean_ps is a ratio.

## node_report_<node>.json

    {"node_id","component_id","role","register_revision","reference_oscillator",
     "path_link_ids","path_length","epochs_available","offset_mean_ps",
     "u_combined_ps2","u_linear_ps","status",
     "oscillators":[{"osc_id","osc_class","status","included",
                     "exclusion_reason","dispersion_ps","final_weight"}]}

Oscillators in catalogue order. An oscillator that holds no weight carries
dispersion_ps 0 and final_weight the ratio zero. offset_mean_ps and
final_weight are ratios and are written as json strings; path_length,
epochs_available, u_combined_ps2, u_linear_ps and dispersion_ps are whole
numbers and are written as json numbers.

## network_reconciliation.xml

The declaration is the first line and is written exactly as below.

    <?xml version="1.0" encoding="UTF-8"?>
    <network_reconciliation>
      <interval>...</interval>
      <closures count="N">
        <closure><link_id/><epoch_index/><closure_ps/></closure>
      </closures>
      <unreconciled count="M"><link_id/></unreconciled>
    </network_reconciliation>

Two space indent, closures ordered by link_id then epoch_index, unreconciled
link identifiers ascending. An element with no children is written as an
opening tag immediately followed by its closing tag, never self closed.

## timescale_report.md

An H1, then four H2 sections in this order, one blank line after every heading
and one blank line before the next heading. The interval label follows the H1
title. Each body line is a label, a colon, one space and the value.

    # Timescale report <interval label>

    ## Network

    hub node: <hub node>
    register revision: <frozen register revision>
    components: <number of components>
    registered nodes: <nodes at the frozen revision>
    published nodes: <nodes whose status is DS_PUBLISHED>

    ## Readings

    canonical readings: <rows in reading_ledger.csv>
    set aside rows: <rows in withdrawal_ledger.tsv>
    dead time records: <records in deadtime_ledger.jsonl>

    ## Ensemble

    oscillators catalogued: <rows in the oscillator catalogue>
    oscillators weighted: <oscillators holding a final weight>
    oscillator cap outcome: <outcome of the first capping pass>
    node cap outcome: <outcome of the second capping pass>
    void epochs: <epochs whose state is EP_ENSEMBLE_VOID>

    ## Steering

    decision epoch: <decision epoch>
    step atto: <applied step, a whole number>
    outcome: <steering outcome>

## ensemble_summary.md

An H1 carrying the interval label, one blank line, then a markdown table with
the header row and separator row exactly as below and one row per registered
node in node order. The pipe characters carry one space either side.

    # Ensemble summary <interval label>

    | node | status | epochs | offset mean ps | u linear ps |
    | --- | --- | --- | --- | --- |
    | <node_id> | <status> | <epochs_available> | <offset mean ratio> | <u_linear_ps> |

The offset mean is a ratio and carries its twelve decimal places. Every other
value in the table is a whole number or a status token, written as the
dissemination ledger writes it.

## publication_manifest.json

    {"interval","document_count","core_order","digest","publication_digest",
     "rule_count","ensemble_size","oscillator_cap_outcome","steering_outcome"}

document_count is 27 and rule_count is 32. digest is the core digest and
publication_digest is the digest over the other twenty six artifacts.

## node_index.conf

Lines of the form key = value with one space either side of the equals sign.
The header keys interval, hub_node, register_revision, node_count and
published_node_count come first, then three lines per node in node order, keyed
node.component, node.status and node.epochs_available.
