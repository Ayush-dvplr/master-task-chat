"""Verifier checks for 11564348-6b1b-57f4-8851-490d0cbc1c5e.

Every expectation is embedded in this file. The verifier image carries no copy
of the agent evidence directory, so the checks below rebuild the reproducer
input from the constants declared here. Every positive check is graded on its
own, so partial recoveries earn partial credit. Agent code only ever runs as a
subprocess under an unprivileged user, in its own process group, with a
timeout.
"""

import copy
import csv
import io
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

from rewardkit import criteria, criterion

EXPECTED = json.loads(r'''{"active_sheet_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1488, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "d2fb7e04b1e65f0d", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "addendum_window_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "slot_bind": 2103, "timer_pause": 1547}, "control_digest": "6c29ea3f066dc717", "deprecation_window": 8, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm"], "surface_digest": "4448a6a64afc0330", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "admission_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1990, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.4.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "cd69862cd07569e4", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "anchor_applied_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2066, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "9dbb8999ec5603a6", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "base": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "bom_published_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "bom_shard_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "catalogue_fold_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "catalogue_rank_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "control": {"control_digest": "c5c9bd2a08672838", "first_divergent_seq": 35}, "core": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"]}, "decoy_supersede_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2111, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "395b86ef2c786841", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "generation_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "reminder_read": 1849}, "control_digest": "3691316683d0fa62", "deprecation_window": 6, "generation": 53, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind", "timer_pause", "focus_hold", "invite_decline"], "surface_digest": "4cdd8e5126f85935", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "journal_case_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "keep_value_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "e35c073ef749d932", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "metrics": {"surface_digest": "ac92eb1fc937ea1a", "urgency_totals": {"additive": 248, "breaking": 63, "internal": 12}}, "ordering_variant": {"active_scopes": {"agenda_open": 1219, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "18669cf456406b3f", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "params_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849}, "control_digest": "4513aa2aa6954e62", "deprecation_window": 5, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind", "timer_pause"], "surface_digest": "0749a6284c5e8cc3", "urgency_weights": {"additive": 6, "breaking": 10, "internal": 2}}, "params_wide_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "legacy_alarm": 1729, "reminder_read": 1849, "slot_bind": 2103, "timer_pause": 1547}, "control_digest": "4500e14be5516c90", "deprecation_window": 9, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write"], "surface_digest": "0f5453f5af5bc4f3", "urgency_weights": {"additive": 38, "breaking": 13, "internal": 1}}, "paths": {"control": "/app/out/control_replay.json", "core": "/app/out/scope_surface_core.json", "metrics": "/app/out/urgency_metrics.json", "rank": "/app/out/rank_order.json", "report": "/app/out/root_cause_report.json", "state": "/app/out/reproduced_state.json", "summary": "/app/out/reconciliation_summary.json", "trace": "/app/out/resolution_trace.json", "verdict": "/app/out/authority_verdict.json"}, "poison_variant": {"active_scopes": {"agenda_open": 1253, "agenda_seal": 1468, "calendar_scan": 1715, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1688, "inbox_flush": 1957, "inbox_open": 2050, "invite_accept": 1560, "invite_decline": 1663, "reminder_read": 1849, "timer_pause": 1560}, "control_digest": "83744d7d4a98b9da", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "dfad30feb9851332", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "rank": {"rank_total_order": ["contact_pack", "inbox_open", "inbox_flush", "reminder_read", "calendar_scan", "focus_hold", "invite_decline", "invite_accept", "timer_pause", "digest_emit", "agenda_seal", "agenda_open"]}, "reexport_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1666, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "33dcbb6503d5bfc0", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "report": {"minimal_delta": [{"authority_value": 1240, "scope": "agenda_open", "snapshot_value": 1219}, {"authority_value": 2088, "scope": "contact_pack", "snapshot_value": 2060}, {"authority_value": 1478, "scope": "digest_emit", "snapshot_value": 1431}, {"authority_value": 2037, "scope": "inbox_open", "snapshot_value": 2120}, {"authority_value": 1650, "scope": "invite_decline", "snapshot_value": 1611}], "rejected_hypothesis": {"falsified_by": "control_replay_digest_matches_snapshot", "name": "journal_backlog"}, "root_cause": {"layer": "generated_scope_snapshot.json", "observed_ordering_key": "seq"}}, "retired_anchor_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1502, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "cc7ff8822881399f", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "retirement_tie_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849}, "control_digest": "8d33e8de1d149a61", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "focus_hold", "slot_bind", "timer_pause"], "surface_digest": "b03ecc065522649e", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "rollback_rejected_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1560, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "accd19545738ba60", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "script_path": "/app/out/reproduce_scopes.py", "shifted_variant": {"active_scopes": {"agenda_open": 1247, "agenda_seal": 1462, "calendar_scan": 1709, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1682, "inbox_flush": 1957, "inbox_open": 2044, "invite_accept": 1554, "invite_decline": 1657, "reminder_read": 1849, "timer_pause": 1554}, "control_digest": "09ac894d9bc25abd", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "6918cc82bfa83123", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "state": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "summary": {"authority_ordering_key": "effective_generation,seq", "authority_source": "ledger/", "control_ordering_key": "seq", "effective_record_count": 43}, "trace": {"inert_records": [{"reason": "restore_rank_below_deprecation", "seq": 27}, {"reason": "rolled_back", "seq": 29}, {"reason": "rolled_back", "seq": 31}, {"reason": "restore_rank_below_deprecation", "seq": 41}, {"reason": "apply_change_rejected", "seq": 42}, {"reason": "revise_names_inactive_scope", "seq": 45}, {"reason": "publish_names_known_scope", "seq": 46}, {"reason": "revise_keeps_value", "seq": 51}, {"reason": "revise_keeps_value", "seq": 52}], "revisited_anchors": [{"canonical_value": 1849, "lineage_anchor": "sc-08-2", "scope": "reminder_read", "seq": 23}, {"canonical_value": 2120, "lineage_anchor": "sc-11-3", "scope": "inbox_open", "seq": 43}, {"canonical_value": 1478, "lineage_anchor": "sc-03-2", "scope": "digest_emit", "seq": 19}, {"canonical_value": 1957, "lineage_anchor": "sc-10-1", "scope": "inbox_flush", "seq": 30}, {"canonical_value": 2088, "lineage_anchor": "sc-12-3", "scope": "contact_pack", "seq": 48}], "transitions": ["seq:1:agenda_open:publish", "seq:2:agenda_seal:publish", "seq:3:digest_emit:publish", "seq:4:invite_accept:publish", "seq:5:invite_decline:publish", "seq:6:calendar_scan:publish", "seq:7:legacy_alarm:publish", "seq:8:reminder_read:publish", "seq:9:reminder_write:publish", "seq:10:inbox_flush:publish", "seq:11:inbox_open:publish", "seq:12:contact_pack:publish", "seq:13:slot_bind:publish", "seq:14:invite_decline:revise", "seq:15:calendar_scan:revise", "seq:16:legacy_alarm:deprecate", "seq:35:timer_pause:publish", "seq:18:agenda_open:revise", "seq:20:digest_emit:revise", "seq:21:inbox_open:revise", "seq:36:timer_pause:deprecate", "seq:39:focus_hold:publish", "seq:17:agenda_open:revise", "seq:23:reminder_read:revise", "seq:26:slot_bind:deprecate", "seq:43:inbox_open:revise", "seq:19:digest_emit:revise", "seq:24:contact_pack:deprecate", "seq:30:inbox_flush:revise", "seq:47:timer_pause:deprecate", "seq:22:inbox_open:revise", "seq:28:reminder_write:withdraw", "seq:37:timer_pause:deprecate", "seq:40:focus_hold:deprecate", "seq:49:contact_pack:revise", "seq:50:invite_decline:revise", "seq:25:contact_pack:restore", "seq:32:invite_accept:revise", "seq:44:invite_decline:deprecate", "seq:38:timer_pause:restore", "seq:48:contact_pack:revise", "seq:33:agenda_seal:revise", "seq:34:calendar_scan:revise"]}, "verdict": {"authority_anchored": true, "layers_compared": ["coverage_gate_report.json", "assistant_runtime_state.json", "household_index.json", "generated_scope_snapshot.json"], "post_repair_divergence_count": 0, "pre_repair_divergence_count": 5}, "xlsx_absolute_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "xlsx_gap_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "xlsx_no_refs_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}, "xlsx_phonetic_variant": {"active_scopes": {"agenda_open": 1240, "agenda_seal": 1455, "calendar_scan": 1702, "contact_pack": 2088, "digest_emit": 1478, "focus_hold": 1675, "inbox_flush": 1957, "inbox_open": 2037, "invite_accept": 1547, "invite_decline": 1650, "reminder_read": 1849, "timer_pause": 1547}, "control_digest": "c5c9bd2a08672838", "deprecation_window": 6, "generation": 49, "release_version": "9.3.0", "retired_scopes": ["reminder_write", "legacy_alarm", "slot_bind"], "surface_digest": "ac92eb1fc937ea1a", "urgency_weights": {"additive": 8, "breaking": 7, "internal": 1}}}''')

LOGICAL = json.loads(r'''{"addenda": [[1, ["Scope authority policy, addendum A1", "This addendum amends scope_authority_policy.md and urgency_class_catalogue.json.", "A1.1 Deprecation window. The deprecation window is 3 generations. This value replaces deprecation_window_generations in urgency_class_catalogue.json.", "A1.2 Urgency totals count the ledger records of each class."]], [2, ["Scope authority policy, addendum A2", "This addendum amends scope_authority_policy.md and urgency_class_catalogue.json.", "It supersedes addendum A1 in full.", "A2.1 Deprecation window. The deprecation window is no longer published in any document. It is recovered from the calibration controls as the parameter recovery section of scope_authority_policy.md describes, and deprecation_window_generations in urgency_class_catalogue.json binds nothing.", "A2.2 Urgency totals. The urgency total of a class is the sum, over every ledger record of that class, effective or inert, of the urgency weight of that class. The urgency weights are not published either; they are recovered together with the deprecation window."]]], "archive": [{"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-01-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "agenda_open", "seq": 1, "urgency_class": "additive", "value": 1207}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-02-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "agenda_seal", "seq": 2, "urgency_class": "additive", "value": 1362}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-03-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "digest_emit", "seq": 3, "urgency_class": "additive", "value": 1418}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-04-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_accept", "seq": 4, "urgency_class": "additive", "value": 1533}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-05-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 5, "urgency_class": "additive", "value": 1594}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-06-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "calendar_scan", "seq": 6, "urgency_class": "additive", "value": 1671}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-07-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "legacy_alarm", "seq": 7, "urgency_class": "additive", "value": 1729}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-08-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "reminder_read", "seq": 8, "urgency_class": "additive", "value": 1804}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-09-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 9, "urgency_class": "additive", "value": 1863}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-10-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_flush", "seq": 10, "urgency_class": "additive", "value": 1926}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-11-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_open", "seq": 11, "urgency_class": "additive", "value": 1988}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-12-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 12, "urgency_class": "additive", "value": 2041}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-13-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "slot_bind", "seq": 13, "urgency_class": "additive", "value": 2103}, {"authority_rank": 5, "effective_generation": 41, "lineage_anchor": "sc-05-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 14, "urgency_class": "internal", "value": 1611}, {"authority_rank": 5, "effective_generation": 41, "lineage_anchor": "sc-06-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "calendar_scan", "seq": 15, "urgency_class": "internal", "value": 1688}, {"authority_rank": 6, "effective_generation": 41, "lineage_anchor": "sc-07-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "legacy_alarm", "seq": 16, "urgency_class": "breaking", "value": 1729}, {"authority_rank": 5, "effective_generation": 43, "lineage_anchor": "sc-01-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "agenda_open", "seq": 17, "urgency_class": "additive", "value": 1240}, {"authority_rank": 3, "effective_generation": 42, "lineage_anchor": "sc-01-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "agenda_open", "seq": 18, "urgency_class": "internal", "value": 1219}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-03-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "digest_emit", "seq": 19, "urgency_class": "additive", "value": 1455}, {"authority_rank": 3, "effective_generation": 42, "lineage_anchor": "sc-03-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "digest_emit", "seq": 20, "urgency_class": "internal", "value": 1431}, {"authority_rank": 4, "effective_generation": 42, "lineage_anchor": "sc-11-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_open", "seq": 21, "urgency_class": "internal", "value": 2010}, {"authority_rank": 5, "effective_generation": 45, "lineage_anchor": "sc-11-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_open", "seq": 22, "urgency_class": "additive", "value": 2037}, {"authority_rank": 5, "effective_generation": 43, "lineage_anchor": "pending", "op": "revise", "recorded_by": "migration-service", "reference_domain": "restricted_scope_index", "scope": "reminder_read", "seq": 23, "urgency_class": "additive", "value": 4471}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-12-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 24, "urgency_class": "breaking", "value": 2041}, {"authority_rank": 6, "effective_generation": 46, "lineage_anchor": "sc-12-1", "op": "restore", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 25, "urgency_class": "additive", "value": 2041}, {"authority_rank": 6, "effective_generation": 43, "lineage_anchor": "sc-13-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "slot_bind", "seq": 26, "urgency_class": "breaking", "value": 2103}, {"authority_rank": 3, "effective_generation": 46, "lineage_anchor": "sc-13-1", "op": "restore", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "slot_bind", "seq": 27, "urgency_class": "additive", "value": 2103}, {"authority_rank": 7, "effective_generation": 45, "lineage_anchor": "sc-09-1", "op": "withdraw", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 28, "urgency_class": "breaking", "value": 1863}, {"authority_rank": 3, "effective_generation": 47, "lineage_anchor": "sc-09-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 29, "urgency_class": "internal", "value": 1899}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-10-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "restricted_scope_index", "scope": "inbox_flush", "seq": 30, "urgency_class": "additive", "value": 3358}, {"authority_rank": 4, "effective_generation": 47, "lineage_anchor": "sc-04-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_accept", "seq": 31, "urgency_class": "internal", "value": 1560}, {"authority_rank": 5, "effective_generation": 46, "lineage_anchor": "sc-04-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "invite_accept", "seq": 32, "urgency_class": "additive", "value": 1547}, {"authority_rank": 4, "effective_generation": 48, "lineage_anchor": "sc-02-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "agenda_seal", "seq": 33, "urgency_class": "internal", "value": 1390}, {"authority_rank": 5, "effective_generation": 48, "lineage_anchor": "sc-06-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "calendar_scan", "seq": 34, "urgency_class": "additive", "value": 1702}], "calibration": [["control_01", [{"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "cal-cal_p", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_p", "seq": 1, "urgency_class": "additive", "value": 1100}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "cal-cal_q", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_q", "seq": 2, "urgency_class": "additive", "value": 1200}, {"authority_rank": 6, "effective_generation": 41, "lineage_anchor": "cal-cal_p", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_p", "seq": 3, "urgency_class": "breaking", "value": 1000}, {"authority_rank": 5, "effective_generation": 48, "lineage_anchor": "cal-cal_q", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_q", "seq": 4, "urgency_class": "internal", "value": 1000}, {"authority_rank": 4, "effective_generation": 49, "lineage_anchor": "cal-cal_p", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_p", "seq": 5, "urgency_class": "internal", "value": 1110}, {"authority_rank": 4, "effective_generation": 50, "lineage_anchor": "cal-cal_q", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_q", "seq": 6, "urgency_class": "internal", "value": 1210}]], ["control_02", [{"authority_rank": 4, "effective_generation": 52, "lineage_anchor": "cal-cal_r", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_r", "seq": 1, "urgency_class": "additive", "value": 1300}, {"authority_rank": 4, "effective_generation": 53, "lineage_anchor": "cal-cal_s", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_s", "seq": 2, "urgency_class": "breaking", "value": 1400}, {"authority_rank": 6, "effective_generation": 54, "lineage_anchor": "cal-cal_r", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_r", "seq": 3, "urgency_class": "breaking", "value": 1000}, {"authority_rank": 5, "effective_generation": 55, "lineage_anchor": "cal-cal_s", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_s", "seq": 4, "urgency_class": "internal", "value": 1000}, {"authority_rank": 4, "effective_generation": 60, "lineage_anchor": "cal-cal_r", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_r", "seq": 5, "urgency_class": "internal", "value": 1310}]], ["control_03", [{"authority_rank": 4, "effective_generation": 61, "lineage_anchor": "cal-cal_t", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_t", "seq": 1, "urgency_class": "additive", "value": 1500}, {"authority_rank": 4, "effective_generation": 61, "lineage_anchor": "cal-cal_u", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_u", "seq": 2, "urgency_class": "additive", "value": 1600}, {"authority_rank": 4, "effective_generation": 62, "lineage_anchor": "cal-cal_v", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_v", "seq": 3, "urgency_class": "additive", "value": 1700}, {"authority_rank": 6, "effective_generation": 61, "lineage_anchor": "cal-cal_t", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_t", "seq": 4, "urgency_class": "breaking", "value": 1000}, {"authority_rank": 7, "effective_generation": 63, "lineage_anchor": "cal-cal_u", "op": "withdraw", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_u", "seq": 5, "urgency_class": "breaking", "value": 1000}, {"authority_rank": 5, "effective_generation": 64, "lineage_anchor": "cal-cal_v", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_v", "seq": 6, "urgency_class": "breaking", "value": 1000}, {"authority_rank": 3, "effective_generation": 66, "lineage_anchor": "cal-cal_v", "op": "restore", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_v", "seq": 7, "urgency_class": "internal", "value": 1000}, {"authority_rank": 4, "effective_generation": 65, "lineage_anchor": "cal-cal_t", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_t", "seq": 8, "urgency_class": "internal", "value": 1510}, {"authority_rank": 4, "effective_generation": 67, "lineage_anchor": "cal-cal_v", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_v", "seq": 9, "urgency_class": "internal", "value": 1710}, {"authority_rank": 4, "effective_generation": 68, "lineage_anchor": "cal-cal_t", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_t", "seq": 10, "urgency_class": "internal", "value": 1515}, {"authority_rank": 4, "effective_generation": 70, "lineage_anchor": "cal-cal_t", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "cal_t", "seq": 11, "urgency_class": "internal", "value": 1520}]]], "catalogue": "{\n  \"catalogue_generation\": 48,\n  \"deprecation_window_generations\": 4,\n  \"classes\": [\n    {\n      \"name\": \"breaking\",\n      \"rank\": 3,\n      \"fold\": \"major\"\n    },\n    {\n      \"name\": \"additive\",\n      \"rank\": 2,\n      \"fold\": \"minor\"\n    },\n    {\n      \"name\": \"internal\",\n      \"rank\": 1,\n      \"fold\": \"patch\"\n    }\n  ],\n  \"candidate_causes\": [\n    \"compiler_ordering_key\",\n    \"journal_backlog\",\n    \"restricted_anchor_ambiguity\",\n    \"runtime_restart_pending\"\n  ],\n  \"recorders\": [\n    \"authority-service\",\n    \"migration-service\"\n  ]\n}\n", "hidden": {"weights": {"additive": 8, "breaking": 7, "internal": 1}, "window": 6}, "journal": [{"op": "apply_change", "record_seq": 22, "retired_anchor": null, "scope": "inbox_open", "status": "applied", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-08-1", "scope": "reminder_read", "status": "pending", "surviving_anchor": "sc-08-2"}, {"op": "apply_change", "record_seq": 17, "retired_anchor": null, "scope": "agenda_open", "status": "applied", "surviving_anchor": null}, {"op": "apply_change", "record_seq": 32, "retired_anchor": null, "scope": "invite_accept", "status": "pending", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-03-1", "scope": "digest_emit", "status": "applied", "surviving_anchor": "sc-03-2"}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-12-1", "scope": "contact_pack", "status": "pending", "surviving_anchor": "sc-12-2"}, {"op": "rollback_change", "record_seq": 19, "retired_anchor": null, "scope": "digest_emit", "status": "rejected", "surviving_anchor": null}, {"op": "apply_change", "record_seq": 34, "retired_anchor": null, "scope": "calendar_scan", "status": "rejected", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-11-1", "scope": "inbox_open", "status": "applied", "surviving_anchor": "sc-11-2"}, {"op": "apply_change", "record_seq": 34, "retired_anchor": null, "scope": "calendar_scan", "status": "pending", "surviving_anchor": null}, {"op": "rollback_change", "record_seq": 31, "retired_anchor": null, "scope": "invite_accept", "status": "applied", "surviving_anchor": null}, {"op": "apply_change", "record_seq": 42, "retired_anchor": null, "scope": "inbox_flush", "status": "rejected", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-11-2", "scope": "inbox_open", "status": "pending", "surviving_anchor": "sc-11-3"}, {"op": "rollback_change", "record_seq": 29, "retired_anchor": null, "scope": "reminder_write", "status": "pending", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-11-3", "scope": "inbox_open", "status": "rejected", "surviving_anchor": "sc-11-4"}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-12-2", "scope": "contact_pack", "status": "applied", "surviving_anchor": "sc-12-3"}, {"op": "apply_change", "record_seq": 17, "retired_anchor": null, "scope": "agenda_open", "status": "rejected", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-12-3", "scope": "contact_pack", "status": "rejected", "surviving_anchor": "sc-12-4"}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-03-2", "scope": "digest_emit", "status": "rejected", "surviving_anchor": "sc-03-3"}], "ledger": [{"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-01-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "agenda_open", "seq": 1, "urgency_class": "additive", "value": 1207}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-02-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "agenda_seal", "seq": 2, "urgency_class": "additive", "value": 1362}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-03-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "digest_emit", "seq": 3, "urgency_class": "additive", "value": 1418}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-04-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_accept", "seq": 4, "urgency_class": "additive", "value": 1533}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-05-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 5, "urgency_class": "additive", "value": 1594}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-06-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "calendar_scan", "seq": 6, "urgency_class": "additive", "value": 1671}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-07-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "legacy_alarm", "seq": 7, "urgency_class": "additive", "value": 1729}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-08-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "reminder_read", "seq": 8, "urgency_class": "additive", "value": 1804}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-09-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 9, "urgency_class": "additive", "value": 1863}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-10-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_flush", "seq": 10, "urgency_class": "additive", "value": 1926}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-11-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_open", "seq": 11, "urgency_class": "additive", "value": 1988}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-12-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 12, "urgency_class": "additive", "value": 2041}, {"authority_rank": 4, "effective_generation": 40, "lineage_anchor": "sc-13-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "slot_bind", "seq": 13, "urgency_class": "additive", "value": 2103}, {"authority_rank": 5, "effective_generation": 41, "lineage_anchor": "sc-05-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 14, "urgency_class": "internal", "value": 1611}, {"authority_rank": 5, "effective_generation": 41, "lineage_anchor": "sc-06-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "calendar_scan", "seq": 15, "urgency_class": "internal", "value": 1688}, {"authority_rank": 6, "effective_generation": 41, "lineage_anchor": "sc-07-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "legacy_alarm", "seq": 16, "urgency_class": "breaking", "value": 1729}, {"authority_rank": 5, "effective_generation": 43, "lineage_anchor": "sc-01-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "agenda_open", "seq": 17, "urgency_class": "additive", "value": 1240}, {"authority_rank": 3, "effective_generation": 42, "lineage_anchor": "sc-01-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "agenda_open", "seq": 18, "urgency_class": "internal", "value": 1219}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-03-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "restricted_scope_index", "scope": "digest_emit", "seq": 19, "urgency_class": "additive", "value": 7710}, {"authority_rank": 3, "effective_generation": 42, "lineage_anchor": "sc-03-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "digest_emit", "seq": 20, "urgency_class": "internal", "value": 1431}, {"authority_rank": 4, "effective_generation": 42, "lineage_anchor": "sc-11-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_open", "seq": 21, "urgency_class": "internal", "value": 2010}, {"authority_rank": 5, "effective_generation": 45, "lineage_anchor": "sc-11-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "inbox_open", "seq": 22, "urgency_class": "additive", "value": 2037}, {"authority_rank": 5, "effective_generation": 43, "lineage_anchor": "pending", "op": "revise", "recorded_by": "migration-service", "reference_domain": "restricted_scope_index", "scope": "reminder_read", "seq": 23, "urgency_class": "additive", "value": 4471}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-12-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 24, "urgency_class": "breaking", "value": 2041}, {"authority_rank": 6, "effective_generation": 46, "lineage_anchor": "sc-12-1", "op": "restore", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 25, "urgency_class": "additive", "value": 2041}, {"authority_rank": 6, "effective_generation": 43, "lineage_anchor": "sc-13-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "slot_bind", "seq": 26, "urgency_class": "breaking", "value": 2103}, {"authority_rank": 3, "effective_generation": 46, "lineage_anchor": "sc-13-1", "op": "restore", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "slot_bind", "seq": 27, "urgency_class": "additive", "value": 2103}, {"authority_rank": 7, "effective_generation": 45, "lineage_anchor": "sc-09-1", "op": "withdraw", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 28, "urgency_class": "breaking", "value": 1863}, {"authority_rank": 3, "effective_generation": 47, "lineage_anchor": "sc-09-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 29, "urgency_class": "internal", "value": 1899}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-10-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "restricted_scope_index", "scope": "inbox_flush", "seq": 30, "urgency_class": "additive", "value": 3358}, {"authority_rank": 4, "effective_generation": 47, "lineage_anchor": "sc-04-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_accept", "seq": 31, "urgency_class": "internal", "value": 1560}, {"authority_rank": 5, "effective_generation": 46, "lineage_anchor": "sc-04-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "invite_accept", "seq": 32, "urgency_class": "additive", "value": 1547}, {"authority_rank": 4, "effective_generation": 48, "lineage_anchor": "sc-02-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "agenda_seal", "seq": 33, "urgency_class": "internal", "value": 1455}, {"authority_rank": 5, "effective_generation": 48, "lineage_anchor": "sc-06-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "calendar_scan", "seq": 34, "urgency_class": "additive", "value": 1702}, {"authority_rank": 4, "effective_generation": 41, "lineage_anchor": "sc-14-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "timer_pause", "seq": 35, "urgency_class": "additive", "value": 1547}, {"authority_rank": 4, "effective_generation": 42, "lineage_anchor": "sc-14-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "timer_pause", "seq": 36, "urgency_class": "breaking", "value": 1547}, {"authority_rank": 6, "effective_generation": 45, "lineage_anchor": "sc-14-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "timer_pause", "seq": 37, "urgency_class": "breaking", "value": 1547}, {"authority_rank": 6, "effective_generation": 47, "lineage_anchor": "sc-14-1", "op": "restore", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "timer_pause", "seq": 38, "urgency_class": "additive", "value": 1547}, {"authority_rank": 4, "effective_generation": 42, "lineage_anchor": "sc-15-1", "op": "publish", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "focus_hold", "seq": 39, "urgency_class": "additive", "value": 1675}, {"authority_rank": 5, "effective_generation": 45, "lineage_anchor": "sc-15-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "focus_hold", "seq": 40, "urgency_class": "breaking", "value": 1675}, {"authority_rank": 4, "effective_generation": 46, "lineage_anchor": "sc-15-1", "op": "restore", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "focus_hold", "seq": 41, "urgency_class": "additive", "value": 1675}, {"authority_rank": 5, "effective_generation": 47, "lineage_anchor": "sc-10-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "inbox_flush", "seq": 42, "urgency_class": "additive", "value": 1990}, {"authority_rank": 5, "effective_generation": 43, "lineage_anchor": "pending", "op": "revise", "recorded_by": "migration-service", "reference_domain": "restricted_scope_index", "scope": "inbox_open", "seq": 43, "urgency_class": "additive", "value": 5520}, {"authority_rank": 4, "effective_generation": 46, "lineage_anchor": "sc-05-1", "op": "deprecate", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 44, "urgency_class": "breaking", "value": 1611}, {"authority_rank": 3, "effective_generation": 46, "lineage_anchor": "sc-08-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "restricted_scope_index", "scope": "reminder_write", "seq": 45, "urgency_class": "internal", "value": 4471}, {"authority_rank": 3, "effective_generation": 49, "lineage_anchor": "sc-09-1", "op": "publish", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "reminder_write", "seq": 46, "urgency_class": "additive", "value": 1899}, {"authority_rank": 5, "effective_generation": 44, "lineage_anchor": "sc-14-1", "op": "deprecate", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "timer_pause", "seq": 47, "urgency_class": "breaking", "value": 1547}, {"authority_rank": 6, "effective_generation": 47, "lineage_anchor": "pending", "op": "revise", "recorded_by": "migration-service", "reference_domain": "restricted_scope_index", "scope": "contact_pack", "seq": 48, "urgency_class": "additive", "value": 6630}, {"authority_rank": 5, "effective_generation": 45, "lineage_anchor": "sc-12-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "contact_pack", "seq": 49, "urgency_class": "internal", "value": 2060}, {"authority_rank": 5, "effective_generation": 45, "lineage_anchor": "sc-05-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 50, "urgency_class": "additive", "value": 1650}, {"authority_rank": 4, "effective_generation": 45, "lineage_anchor": "sc-10-1", "op": "revise", "recorded_by": "authority-service", "reference_domain": "restricted_scope_index", "scope": "inbox_flush", "seq": 51, "urgency_class": "internal", "value": 3358}, {"authority_rank": 3, "effective_generation": 44, "lineage_anchor": "sc-05-1", "op": "revise", "recorded_by": "migration-service", "reference_domain": "scope_id", "scope": "invite_decline", "seq": 52, "urgency_class": "internal", "value": 1611}], "sheets": [["draft_map_v48", [["lineage_anchor", "alt_key", "canonical_value", "proposed_by"], ["sc-10-1", 3358, 1957, "migration-service"], ["sc-12-1", 3358, 1903, "migration-service"], ["sc-08-1", 4471, 1811, "migration-service"], ["sc-08-2", 4471, 1836, "migration-service"], ["sc-11-2", 5520, 2093, "migration-service"], ["sc-11-3", 5520, 2131, "migration-service"], ["sc-11-4", 5520, 2150, "migration-service"], ["sc-12-2", 6630, 2066, "migration-service"], ["sc-12-3", 6630, 2099, "migration-service"], ["sc-12-4", 6630, 2111, "migration-service"], ["sc-03-1", 7710, 1455, "migration-service"], ["sc-03-2", 7710, 1490, "migration-service"], ["sc-03-3", 7710, 1502, "migration-service"]]], ["active_map_v47", [["alt_key", "lineage_anchor", "canonical_value"], [3358, "sc-10-1", 1957], [3358, "sc-12-1", 1903], [4471, "sc-08-1", 1811], [4471, "sc-08-2", 1849], [5520, "sc-11-2", 2093], [5520, "sc-11-3", 2120], [5520, "sc-11-4", 2150], [6630, "sc-12-2", 2066], [6630, "sc-12-3", 2088], [6630, "sc-12-4", 2111], [7710, "sc-03-1", 1455], [7710, "sc-03-2", 1478], [7710, "sc-03-3", 1502]]], ["notes", [["note"], ["Sheets named draft_ hold proposals that the release desk has not adopted."], ["The sheet named active_ is the map the release train resolves against."]]]], "staging": [{"op": "rollback_change", "record_seq": 31, "retired_anchor": null, "scope": "invite_accept", "status": "rejected", "surviving_anchor": null}, {"op": "apply_change", "record_seq": 42, "retired_anchor": null, "scope": "inbox_flush", "status": "pending", "surviving_anchor": null}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-03-2", "scope": "digest_emit", "status": "pending", "surviving_anchor": "sc-03-3"}, {"op": "supersede_anchor", "record_seq": null, "retired_anchor": "sc-12-3", "scope": "contact_pack", "status": "applied", "surviving_anchor": "sc-12-4"}]}''')

# ---- evidence builders (shared verbatim by the data generator and the verifier) ----

LEDGER_FIELDS = ["seq", "scope", "op", "value", "urgency_class", "authority_rank",
                 "reference_domain", "lineage_anchor", "effective_generation", "recorded_by"]
SHARD_LAYOUT = [
    ("ledger/shard_01.csv", "csv", ["seq", "effective_generation", "scope", "op", "value", "reference_domain",
                                    "lineage_anchor", "urgency_class", "authority_rank", "recorded_by"]),
    ("ledger/shard_02.psv", "psv", ["recorded_by", "seq", "scope", "op", "urgency_class", "value",
                                    "authority_rank", "effective_generation", "lineage_anchor", "reference_domain"]),
    ("ledger/shard_03.ndjson", "ndjson", ["scope", "seq", "op", "value", "lineage_anchor", "reference_domain",
                                          "effective_generation", "urgency_class", "authority_rank", "recorded_by"]),
]
JOURNAL_COLUMNS = ["line_no", "op", "scope", "record_seq", "retired_anchor", "surviving_anchor", "status"]
ZIP_TIME = (2026, 10, 1, 0, 0, 0)


def shard_of(seq):
    return (seq * 7 + seq // 5) % 3


def _shard_order(rows):
    return sorted(rows, key=lambda r: ((r["seq"] * 5) % 11, r["seq"]))


def build_shards(rows):
    out = {}
    for index, (path, kind, fields) in enumerate(SHARD_LAYOUT):
        mine = _shard_order([r for r in rows if shard_of(r["seq"]) == index])
        if kind == "ndjson":
            text = "".join(json.dumps({k: r[k] for k in fields}) + "\n" for r in mine)
        else:
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter="," if kind == "csv" else "|", lineterminator="\n")
            writer.writerow(fields)
            for r in mine:
                writer.writerow([r[k] for k in fields])
            text = buf.getvalue()
        out[path] = text.encode("utf-8")
    return out


def build_archive(rows):
    text = "".join(json.dumps(r) + "\n" for r in rows)
    return {"ledger/archive/shard_00_export_2026-09.ndjson": text.encode("utf-8")}


def build_sqlite(journal, staging, column_case=False):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ops.sqlite")
        con = sqlite3.connect(path)
        names = [c.title() if column_case else c for c in JOURNAL_COLUMNS]
        cols = ", ".join(names)
        for table, ops in (("journal", journal), ("journal_staging", staging)):
            con.execute("CREATE TABLE %s (%s INTEGER NOT NULL, %s TEXT NOT NULL, %s TEXT NOT NULL, "
                        "%s INTEGER, %s TEXT, %s TEXT, %s TEXT NOT NULL)" % tuple([table] + names))
            numbered = [dict(op, line_no=i + 1) for i, op in enumerate(ops)]
            # rows are stored out of line order on purpose; line_no carries the journal order
            for op in sorted(numbered, key=lambda o: ((o["line_no"] * 7) % 13, o["line_no"])):
                con.execute("INSERT INTO %s (%s) VALUES (%s)" % (table, cols, ", ".join("?" * len(JOURNAL_COLUMNS))),
                            [op.get(c) for c in JOURNAL_COLUMNS])
        con.commit()
        con.execute("VACUUM")
        con.close()
        with open(path, "rb") as fh:
            return fh.read()


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_xlsx(sheets, absolute=False, refs=True, phonetic=False, gap=False):
    """sheets: list of (name, rows) where rows is a list of lists of str/int."""
    strings = []
    index = {}

    def sid(value):
        if value not in index:
            index[value] = len(strings)
            strings.append(value)
        return index[value]

    def col(n):
        name = ""
        n += 1
        while n:
            n, rem = divmod(n - 1, 26)
            name = chr(65 + rem) + name
        return name

    sheet_xml = []
    for _, rows in sheets:
        body = []
        for r, row in enumerate(rows, 1):
            cells = []
            for c, value in enumerate(row):
                place = c + 1 if gap and c >= 1 else c
                ref = ' r="%s%d"' % (col(place), r) if refs else ""
                if isinstance(value, int):
                    cells.append('<c%s><v>%d</v></c>' % (ref, value))
                else:
                    cells.append('<c%s t="s"><v>%d</v></c>' % (ref, sid(value)))
            body.append('<row r="%d">%s</row>' % (r, "".join(cells)))
        sheet_xml.append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                         '<sheetData>%s</sheetData></worksheet>' % "".join(body))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' \
         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook %s><sheets>%s</sheets></workbook>' % (
        ns, "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_esc(n), i + 1, i + 1)
                    for i, (n, _) in enumerate(sheets)))
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s%s</Relationships>' % (
               "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                       'Target="%sworksheets/sheet%d.xml"/>' % (i + 1, "/xl/" if absolute else "", i + 1) for i in range(len(sheets))),
               '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
               'Target="sharedStrings.xml"/>' % (len(sheets) + 1))
    shared = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
             '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%d" uniqueCount="%d">%s</sst>' % (
                 len(strings), len(strings), "".join(
                     ('<si><t>%s</t><rPh sb="0" eb="1"><t>%s</t></rPh></si>' % (_esc(s), "\u30e8\u30df") if phonetic
                      else "<si><t>%s</t></si>" % _esc(s)) for s in strings))
    types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' \
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' \
            '<Default Extension="xml" ContentType="application/xml"/>' \
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' \
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>' \
            '%s</Types>' % "".join('<Override PartName="/xl/worksheets/sheet%d.xml" '
                                   'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1)
                                   for i in range(len(sheets)))
    root_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' \
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" ' \
                'Target="xl/workbook.xml"/></Relationships>'
    entries = [("[Content_Types].xml", types), ("_rels/.rels", root_rels), ("xl/workbook.xml", workbook),
               ("xl/_rels/workbook.xml.rels", rels), ("xl/sharedStrings.xml", shared)]
    entries += [("xl/worksheets/sheet%d.xml" % (i + 1), x) for i, x in enumerate(sheet_xml)]
    return _zip(entries)


def build_docx(paragraphs):
    body = "".join('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % _esc(p) for p in paragraphs)
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
               '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>%s</w:body></w:document>' % body
    types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' \
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' \
            '<Default Extension="xml" ContentType="application/xml"/>' \
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' \
            '</Types>'
    root_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' \
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' \
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" ' \
                'Target="word/document.xml"/></Relationships>'
    return _zip([("[Content_Types].xml", types), ("_rels/.rels", root_rels), ("word/document.xml", document)])


def addendum_paragraphs(number, supersedes, window, extra):
    paras = ["Scope authority policy, addendum A%d" % number,
             "This addendum amends scope_authority_policy.md and urgency_class_catalogue.json."]
    if supersedes:
        paras.append("It supersedes addendum A%d in full." % supersedes)
    if window is None:
        paras.append("A%d.1 Deprecation window. The deprecation window is no longer published in any document. "
                     "It is recovered from the calibration controls as the parameter recovery section of "
                     "scope_authority_policy.md describes, and deprecation_window_generations in "
                     "urgency_class_catalogue.json binds nothing." % number)
    else:
        paras.append("A%d.1 Deprecation window. The deprecation window is %d generations. This value replaces "
                     "deprecation_window_generations in urgency_class_catalogue.json." % (number, window))
    paras.extend(extra)
    return paras


def _control_outcome(records, window):
    """Retired list of one calibration control under a candidate window (controls carry no journal)."""
    active, retired, stacks = set(), [], {}
    for rec in sorted(records, key=lambda r: (r["effective_generation"], r["seq"])):
        scope, op = rec["scope"], rec["op"]
        if op == "publish" and scope not in active and scope not in retired:
            active.add(scope)
        elif op == "deprecate" and scope in active:
            stacks.setdefault(scope, []).append((rec["authority_rank"], rec["effective_generation"]))
        elif op == "restore" and scope in active and stacks.get(scope) and rec["authority_rank"] >= stacks[scope][-1][0]:
            stacks[scope].pop()
        elif op == "withdraw" and scope in active:
            active.discard(scope)
            retired.append(scope)
            stacks.pop(scope, None)
    top = max(r["effective_generation"] for r in records)
    aged = sorted((s[-1][1], name) for name, s in stacks.items() if name in active and s and top - s[-1][1] >= window)
    return retired + [name for _, name in aged]


def build_calibration(controls, hidden):
    out = {}
    lines = ["control|retired_scopes|urgency_grand_total"]
    for name, records in controls:
        out["calibration/%s.ndjson" % name] = "".join(json.dumps(r) + "\n" for r in records).encode("utf-8")
        retired = _control_outcome(records, hidden["window"])
        total = sum(hidden["weights"][r["urgency_class"]] for r in records)
        lines.append("%s|%s|%d" % (name, ";".join(retired) if retired else "-", total))
    out["calibration/published_controls.psv"] = ("\n".join(lines) + "\n").encode("utf-8")
    return out


def apply_duplicate(files, rows, dup):
    """Re-export one record, with changes, into another shard."""
    record = dict(next(r for r in rows if r["seq"] == dup["seq"]), **dup.get("changes", {}))
    for path, kind, fields in SHARD_LAYOUT:
        if path != dup["path"]:
            continue
        if kind == "ndjson":
            line = json.dumps({k: record[k] for k in fields}) + "\n"
        else:
            buf = io.StringIO()
            csv.writer(buf, delimiter="," if kind == "csv" else "|", lineterminator="\n").writerow([record[k] for k in fields])
            line = buf.getvalue()
        files[path] = files[path] + line.encode("utf-8")


def materialize(logical):
    files = {}
    files.update(build_shards(logical["ledger"]))
    files.update(build_archive(logical["archive"]))
    quirks = logical.get("quirks", {})
    files["release_ops.sqlite"] = build_sqlite(logical["journal"], logical["staging"], quirks.get("journal_column_case", False))
    files["restricted_scope_map.xlsx"] = build_xlsx(
        logical["sheets"], quirks.get("xlsx_absolute", False), not quirks.get("xlsx_no_refs", False),
        quirks.get("xlsx_phonetic", False), quirks.get("xlsx_gap", False))
    for number, paragraphs in logical["addenda"]:
        files["policy_addendum_A%d.docx" % number] = build_docx(paragraphs)
    files["urgency_class_catalogue.json"] = logical["catalogue"].encode("utf-8")
    files.update(build_calibration(logical["calibration"], logical["hidden"]))
    for dup in quirks.get("dup", []):
        apply_duplicate(files, logical["ledger"], dup)
    for path in quirks.get("bom", []):
        files[path] = b"\xef\xbb\xbf" + files[path]
    return files
# ---- end of evidence builders ----


STATE_KEYS = (
    "surface_digest",
    "generation",
    "release_version",
    "control_digest",
    "active_scopes",
    "retired_scopes",
    "deprecation_window",
    "urgency_weights",
)
JSON_ROLES = ("core", "summary", "metrics", "verdict", "trace", "report", "control", "rank", "state")
KEY_SET_ROLES = ("summary", "verdict", "state")
UNPRIVILEGED = 65534
SETPRIV = "/usr/bin/setpriv"
# Checks run on worker threads; every reproducer run and the planted evidence
# probe share this lock so no run ever observes another check's fixture.
RUN_LOCK = threading.Lock()


def _read_text(path):
    return Path(path).read_text(encoding="utf-8")


def _read_json(path):
    return json.loads(_read_text(path))


def _section(role):
    return _read_json(EXPECTED["paths"][role])


SHADOWING_NAMES = frozenset(
    ("sitecustomize.py", "usercustomize.py", "conftest.py", "pytest.ini", "json.py", "hashlib.py",
     "pathlib.py")
)


def _reproducer_source():
    return _read_text(EXPECTED["script_path"])


def _sibling_modules():
    """Python modules delivered beside the reproducer, read as root whatever their mode."""
    holder = Path(EXPECTED["script_path"]).parent
    siblings = {}
    if holder.is_dir():
        for path in sorted(holder.glob("*.py")):
            if path.name == Path(EXPECTED["script_path"]).name or path.name in SHADOWING_NAMES:
                continue
            try:
                siblings[path.name] = path.read_bytes()
            except OSError:
                continue
    return siblings


def _logical():
    return copy.deepcopy(LOGICAL)


def _files_of(logical):
    return materialize(logical)


def _clean_inputs():
    return _files_of(_logical())


def _edit_rows(logical, seq, **changes):
    for row in logical["ledger"]:
        if row["seq"] == seq:
            row.update(changes)
    return logical


def _shifted(step):
    logical = _logical()
    for row in logical["ledger"]:
        if row["reference_domain"] == "scope_id":
            row["value"] = row["value"] + step
    return _files_of(logical)


def _journal_edit(edit):
    logical = _logical()
    logical["journal"] = [op for op in (edit(dict(op)) for op in logical["journal"]) if op is not None]
    return _files_of(logical)


def _reorder_variant():
    return _files_of(_edit_rows(_logical(), 18, effective_generation=44))


def _generation_variant():
    """The inert publish at the tail of the ledger moves to a later generation."""
    return _files_of(_edit_rows(_logical(), 46, effective_generation=53))


def _keep_value_variant():
    """Record 52 moves to the last generation and rewrites the value its scope
    already carries there, so it must stay out of the household version fold."""
    return _files_of(_edit_rows(_logical(), 52, effective_generation=49, value=1650))


def _status_edit(kind, key, value, status):
    def edit(op):
        if op["op"] == kind and op.get(key) == value:
            op["status"] = status
        return op
    return edit


def _rollback_rejected_variant():
    """The rollback of record 31 is refused by the release desk."""
    return _journal_edit(_status_edit("rollback_change", "record_seq", 31, "rejected"))


def _admission_variant():
    """The refused admission of record 42 is turned into a pending one."""
    return _journal_edit(_status_edit("apply_change", "record_seq", 42, "pending"))


def _decoy_supersede_variant():
    """The refused supersede on contact_pack becomes a pending one."""
    return _journal_edit(_status_edit("supersede_anchor", "surviving_anchor", "sc-12-4", "pending"))


def _anchor_applied_variant():
    """The applied supersede on contact_pack is refused instead."""
    return _journal_edit(_status_edit("supersede_anchor", "surviving_anchor", "sc-12-3", "rejected"))


def _retired_anchor_variant():
    """The refused supersede on digest_emit becomes a pending one."""
    return _journal_edit(_status_edit("supersede_anchor", "surviving_anchor", "sc-03-3", "pending"))


def _catalogue_edit(edit):
    logical = _logical()
    catalogue = json.loads(logical["catalogue"])
    for entry in catalogue["classes"]:
        edit(entry)
    logical["catalogue"] = json.dumps(catalogue, indent=2) + "\n"
    return _files_of(logical)


def _catalogue_rank_variant():
    """The catalogue prints the class ranks the other way round; the tie rule names classes."""
    ranks = {"breaking": 1, "additive": 2, "internal": 3}
    return _catalogue_edit(lambda entry: entry.update(rank=ranks[entry["name"]]))


def _catalogue_fold_variant():
    """The catalogue prints swapped fold labels; the policy fold names classes."""
    folds = {"breaking": "patch", "additive": "minor", "internal": "major"}
    return _catalogue_edit(lambda entry: entry.update(fold=folds[entry["name"]]))


def _quirk(**quirks):
    logical = _logical()
    logical["quirks"] = quirks
    return _files_of(logical)


def _bom_shard_variant():
    """The NDJSON ledger shard starts with a UTF-8 byte order mark."""
    return _quirk(bom=["ledger/shard_03.ndjson"])


def _bom_published_variant():
    """The published calibration outputs start with a UTF-8 byte order mark."""
    return _quirk(bom=["calibration/published_controls.psv"])


def _reexport_variant():
    """Record 50 is re-exported, with a new value, into the shard that sorts last."""
    return _quirk(dup=[{"seq": 50, "path": "ledger/shard_03.ndjson", "changes": {"value": 1666}}])


def _xlsx_absolute_variant():
    """The workbook names its worksheet parts by absolute part name."""
    return _quirk(xlsx_absolute=True)


def _xlsx_no_refs_variant():
    """Workbook cells omit the optional r attribute."""
    return _quirk(xlsx_no_refs=True)


def _xlsx_phonetic_variant():
    """Every shared string carries a phonetic rPh run after its text."""
    return _quirk(xlsx_phonetic=True)


def _xlsx_gap_variant():
    """An empty column separates the first column from the others."""
    return _quirk(xlsx_gap=True)


def _journal_case_variant():
    """The journal table declares its column names in title case."""
    return _quirk(journal_column_case=True)


def _params_variant():
    """Fresh hidden parameters behind the calibration controls."""
    logical = _logical()
    logical["hidden"] = {"window": 4, "weights": {"breaking": 9, "additive": 2, "internal": 5}}
    return _files_of(logical)


def _params_wide_variant():
    """A wider family of weights fits every control; the tie rule settles it."""
    logical = _logical()
    logical["hidden"] = {"window": 9, "weights": {"breaking": 11, "additive": 30, "internal": 7}}
    return _files_of(logical)


def _addendum_window_variant():
    """A third addendum republishes the window, overriding A2's recovery rule."""
    logical = _logical()
    logical["addenda"] = logical["addenda"] + [[3, addendum_paragraphs(3, 2, 8, [])]]
    return _files_of(logical)


def _retirement_tie_variant():
    """Three scopes share the deprecation generation that retires them.

    focus_hold and timer_pause join slot_bind at generation 43, so the window
    retires all three at once and only the scope name settles their order in the
    retired list. Their order of first deprecation in the replay is timer_pause,
    slot_bind, focus_hold, which is not the name order.
    """
    logical = _edit_rows(_logical(), 40, effective_generation=43)
    return _files_of(_edit_rows(logical, 47, effective_generation=43))


def _active_sheet_variant():
    """The active sheet carries a new value for digest_emit's surviving anchor."""
    logical = _logical()
    for name, rows in logical["sheets"]:
        if name.startswith("active_"):
            for row in rows[1:]:
                if row[0] == 7710 and row[1] == "sc-03-2":
                    row[2] = 1488
    return _files_of(logical)


def _launch(argv, cwd, env):
    """Run agent code as an unprivileged user in its own process group."""
    privileged = hasattr(os, "geteuid") and os.geteuid() == 0
    if privileged:
        argv = [
            SETPRIV,
            "--reuid=%d" % UNPRIVILEGED,
            "--regid=%d" % UNPRIVILEGED,
            "--clear-groups",
            "--",
        ] + argv
    proc = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        proc.wait()
    return proc.returncode


def _run_unlocked(source, files):
    """Execute a candidate reproducer over a synthetic input tree.

    The interpreter runs with -E -s -S (no environment variables, no user or
    system site-packages), so a reproducer that imports anything beyond the
    standard library cannot run; its own directory stays importable so that
    sibling modules delivered beside it in /app/out still load.
    """
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        indir = root / "input"
        outdir = root / "produced"
        indir.mkdir()
        outdir.mkdir()
        for name, data in files.items():
            target = indir.joinpath(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o644)
        # The agent may deliver its program with mode 0600 and the run is
        # unprivileged, so the program and its siblings are copied into a fresh
        # directory that the unprivileged user can read.
        program = root / "program"
        program.mkdir()
        for name, data in _sibling_modules().items():
            program.joinpath(name).write_bytes(data)
            os.chmod(program / name, 0o644)
        script = program / "reproduce_scopes.py"
        script.write_text(source, encoding="utf-8")
        os.chmod(script, 0o644)
        for folder, dirs, _ in os.walk(indir):
            os.chmod(folder, 0o755)
        os.chmod(program, 0o755)
        os.chmod(root, 0o755)
        os.chmod(outdir, 0o777)
        code = _launch(
            [sys.executable, "-E", "-s", "-S", str(script), "--input", str(indir), "--out", str(outdir)],
            str(root),
            env,
        )
        produced = outdir / "reproduced_state.json"
        if code != 0 or not produced.is_file():
            return None
        try:
            state = json.loads(produced.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return state if isinstance(state, dict) else None


def _run(source, files):
    with RUN_LOCK:
        return _run_unlocked(source, files)


VARIANT_INPUTS = {
    "ordering_variant": _reorder_variant,
    "generation_variant": _generation_variant,
    "rollback_rejected_variant": _rollback_rejected_variant,
    "admission_variant": _admission_variant,
    "decoy_supersede_variant": _decoy_supersede_variant,
    "params_variant": _params_variant,
    "bom_shard_variant": _bom_shard_variant,
    "bom_published_variant": _bom_published_variant,
    "reexport_variant": _reexport_variant,
    "xlsx_absolute_variant": _xlsx_absolute_variant,
    "xlsx_no_refs_variant": _xlsx_no_refs_variant,
    "xlsx_phonetic_variant": _xlsx_phonetic_variant,
    "xlsx_gap_variant": _xlsx_gap_variant,
    "journal_case_variant": _journal_case_variant,
    "catalogue_rank_variant": _catalogue_rank_variant,
    "catalogue_fold_variant": _catalogue_fold_variant,
    "params_wide_variant": _params_wide_variant,
    "anchor_applied_variant": _anchor_applied_variant,
    "retired_anchor_variant": _retired_anchor_variant,
    "keep_value_variant": _keep_value_variant,
    "active_sheet_variant": _active_sheet_variant,
    "addendum_window_variant": _addendum_window_variant,
    "retirement_tie_variant": _retirement_tie_variant,
}

# Each held out variant is graded only on the fields its rule moves, so one
# missed rule does not erase the credit earned on the others.
VARIANT_FIELDS = {
    "ordering_variant": [("active_scopes", "agenda_open")],
    "generation_variant": [("generation",), ("retired_scopes",)],
    "rollback_rejected_variant": [("active_scopes", "invite_accept")],
    "admission_variant": [("active_scopes", "inbox_flush")],
    "decoy_supersede_variant": [("active_scopes", "contact_pack")],
    "params_variant": [("deprecation_window",), ("urgency_weights",), ("retired_scopes",)],
    "params_wide_variant": [("deprecation_window",), ("urgency_weights",)],
    "catalogue_rank_variant": [("urgency_weights",)],
    "bom_shard_variant": [("active_scopes",), ("release_version",)],
    "bom_published_variant": [("deprecation_window",), ("urgency_weights",)],
    "reexport_variant": [("active_scopes", "invite_decline")],
    "xlsx_absolute_variant": [("active_scopes",)],
    "xlsx_no_refs_variant": [("active_scopes",)],
    "xlsx_phonetic_variant": [("active_scopes",)],
    "xlsx_gap_variant": [("active_scopes",)],
    "journal_case_variant": [("active_scopes",), ("control_digest",)],
    "catalogue_fold_variant": [("release_version",)],
    "anchor_applied_variant": [("active_scopes", "contact_pack")],
    "retired_anchor_variant": [("active_scopes", "digest_emit")],
    "keep_value_variant": [("release_version",)],
    "active_sheet_variant": [("active_scopes", "digest_emit")],
    "addendum_window_variant": [("deprecation_window",), ("retired_scopes",),
                                ("active_scopes", "slot_bind")],
    "retirement_tie_variant": [("retired_scopes",)],
}


def _dig(obj, path):
    for part in path:
        obj = obj[part]
    return obj


def _check_variant(name):
    """Grade one held out corpus against the expectation declared in this file.

    Every variant, format ones included, is compared against EXPECTED rather than
    against the reproducer's own output on the unvaried evidence: a self
    comparison pays any program that is merely deterministic, including one that
    reads nothing at all.
    """
    state = _run(_reproducer_source(), VARIANT_INPUTS[name]())
    assert state is not None
    reference = EXPECTED[name]
    for path in VARIANT_FIELDS[name]:
        assert _same(_dig(state, path), _dig(reference, path)), path


def _contract_view(state):
    return {key: state.get(key) for key in STATE_KEYS}


# rewardkit evaluates criteria on worker threads; grading is serialised so no
# check ever observes another check's fixture or a half written temp tree.
GRADE_LOCK = threading.RLock()


def _grade(check):
    with GRADE_LOCK:
        try:
            return bool(check())
        except Exception:
            return False


def _same(found, wanted):
    """Exact comparison that refuses the bool/int confusion.

    The contract says every count is an integer, and Python evaluates False == 0
    as true, so a bare == would accept a boolean where an integer is promised.
    """
    if isinstance(wanted, bool) != isinstance(found, bool):
        return False
    if isinstance(wanted, int) and not isinstance(found, int):
        return False
    return found == wanted


def _equal(role, key):
    return _same(_section(role)[key], EXPECTED[role][key])


def _contract_keys_hold():
    return all(sorted(_section(r).keys()) == sorted(EXPECTED[r].keys()) for r in KEY_SET_ROLES)


@criterion(description="the summary, verdict and state artifacts carry the declared key sets and every JSON artifact uses the declared layout")
def contract_and_layout(workspace: Path) -> bool:
    if not _grade(_contract_keys_hold):
        return False
    return serialization_layout_check(workspace)


def serialization_layout_check(workspace: Path) -> bool:
    def check():
        for role in JSON_ROLES:
            try:
                text = _read_text(EXPECTED["paths"][role])
                canonical = json.dumps(json.loads(text), indent=2) + "\n"
            except (OSError, ValueError):
                return False
            if "\r" in text or text != canonical:
                return False
        maps = [
            _section("core")["active_scopes"],
            _section("metrics")["urgency_totals"],
            _section("state")["active_scopes"],
        ]
        return all(list(m.keys()) == sorted(m.keys()) for m in maps)
    return _grade(check)


@criterion(description="the surface generation is the largest generation on any ledger record")
def core_generation(workspace: Path) -> bool:
    return _grade(lambda: _equal("core", "generation"))


@criterion(description="the retired list carries withdrawn then window expired scopes in policy order")
def core_retired_scope_order(workspace: Path) -> bool:
    return _grade(lambda: _equal("core", "retired_scopes"))


@criterion(description="the active surface carries the authority value for every live scope")
def core_active_scope_surface(workspace: Path) -> bool:
    return _grade(lambda: _equal("core", "active_scopes"))


@criterion(description="the household version folds the effective records in authority order")
def core_release_version_fold(workspace: Path) -> bool:
    return _grade(lambda: _equal("core", "release_version"))


@criterion(description="the effective record count excludes the inert records")
def summary_effective_record_count(workspace: Path) -> bool:
    return _grade(lambda: _equal("summary", "effective_record_count"))


@criterion(description="the summary names the authority source and both ordering keys")
def summary_declared_ordering_keys(workspace: Path) -> bool:
    def check():
        return all(
            _equal("summary", key)
            for key in ("authority_source", "authority_ordering_key", "control_ordering_key")
        )
    return _grade(check)


@criterion(description="the verdict lists every derived layer it weighed in the order the policy introduces them")
def verdict_layers_compared(workspace: Path) -> bool:
    return _grade(lambda: _equal("verdict", "layers_compared"))


@criterion(description="the urgency metrics carry the authority surface digest and the per class record totals")
def metrics_values(workspace: Path) -> bool:
    return _grade(lambda: _equal("metrics", "surface_digest") and _equal("metrics", "urgency_totals"))


@criterion(description="the verdict counts the scopes the snapshot disagreed on and none after the repair")
def verdict_divergence_counts(workspace: Path) -> bool:
    def check():
        return _equal("verdict", "pre_repair_divergence_count") and _equal(
            "verdict", "post_repair_divergence_count"
        )
    return _grade(check)


@criterion(description="the transition list follows the authority replay order")
def trace_transition_order(workspace: Path) -> bool:
    return _grade(lambda: _equal("trace", "transitions"))


@criterion(description="the revisited anchors list the effective restricted records in authority order")
def trace_revisited_anchor_resolution(workspace: Path) -> bool:
    return _grade(lambda: _equal("trace", "revisited_anchors"))


@criterion(description="the trace names every inert record with the reason the policy assigns")
def trace_inert_record_identification(workspace: Path) -> bool:
    return _grade(lambda: _equal("trace", "inert_records"))


@criterion(description="the report settles the faulty layer and the ordering it used")
def report_root_cause_layer_and_ordering(workspace: Path) -> bool:
    def check():
        found = _section("report")["root_cause"]
        return all(found[k] == v for k, v in EXPECTED["report"]["root_cause"].items())
    return _grade(check)


@criterion(description="the report names the eliminated cause and what falsified it")
def report_rejected_hypothesis(workspace: Path) -> bool:
    def check():
        found = _section("report")["rejected_hypothesis"]
        return all(found[k] == v for k, v in EXPECTED["report"]["rejected_hypothesis"].items())
    return _grade(check)


@criterion(description="the report lists exactly the scopes whose snapshot value differs from the authority")
def report_minimal_delta(workspace: Path) -> bool:
    return _grade(lambda: _equal("report", "minimal_delta"))


@criterion(description="the control replay artifact carries the record sequence digest and the first divergent record")
def control_replay_values(workspace: Path) -> bool:
    # Both fields are graded together: the digest alone can be copied from the
    # snapshot, the first divergent record has to be worked out.
    def check():
        return _equal("control", "control_digest") and _equal("control", "first_divergent_seq")
    return _grade(check)


@criterion(description="the rank order artifact sorts the active scopes by value descending and settles equal values by scope name")
def rank_total_order_values(workspace: Path) -> bool:
    return _grade(lambda: _equal("rank", "rank_total_order"))


@criterion(description="the delivered reproducer rebuilds the full state from a fresh copy of the evidence and the reproduced state beside the artifacts carries the same values")
def reproducer_rebuilds_shipped_evidence(workspace: Path) -> bool:
    def check():
        state = _run(_reproducer_source(), _clean_inputs())
        written = _section("state")
        return (state is not None and all(state[k] == EXPECTED["base"][k] for k in STATE_KEYS)
                and all(written[k] == EXPECTED["state"][k] for k in STATE_KEYS))
    return _grade(check)


@criterion(description="the reproducer tracks a ledger whose ordering inversion is removed and one whose inert tail record moves to a later generation")
def reproducer_variant_ledger_edits(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("ordering_variant") is None and _check_variant("generation_variant") is None)


@criterion(description="the reproducer follows journal status changes on a rollback and on an admission")
def reproducer_variant_journal_status(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("rollback_rejected_variant") is None and _check_variant("admission_variant") is None)


@criterion(description="the reproducer settles the contact_pack anchor on the last non rejected supersede when either supersede changes status")
def reproducer_variant_supersede_settlement(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("decoy_supersede_variant") is None and _check_variant("anchor_applied_variant") is None)


@criterion(description="the reproducer recovers the window and the urgency weights from calibration controls built on fresh hidden values, including a wide family of fitting weights")
def reproducer_variant_recovered_parameters(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("params_variant") is None and _check_variant("params_wide_variant") is None)


@criterion(description="the reproducer resolves restricted references through retired written anchors and the active_ sheet")
def reproducer_variant_restricted_resolution(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("retired_anchor_variant") is None and _check_variant("active_sheet_variant") is None)


@criterion(description="the reproducer applies the tie rule and the version fold by class name when the catalogue prints other ranks and fold labels")
def reproducer_variant_catalogue_names(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("catalogue_rank_variant") is None and _check_variant("catalogue_fold_variant") is None)


@criterion(description="the reproducer reads a ledger shard and published calibration outputs that begin with a byte order mark")
def reproducer_variant_bom(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("bom_shard_variant") is None and _check_variant("bom_published_variant") is None)


@criterion(description="the reproducer reads workbook cells that carry no cell reference attribute")
def reproducer_variant_workbook_without_references(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("xlsx_no_refs_variant") is None)


@criterion(description="the reproducer reads shared strings that carry phonetic runs as their main text only")
def reproducer_variant_workbook_phonetic_runs(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("xlsx_phonetic_variant") is None)


@criterion(description="the reproducer reads workbook columns by header when an empty column separates them")
def reproducer_variant_workbook_column_gap(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("xlsx_gap_variant") is None)


@criterion(description="the reproducer reads the journal table when its column names are declared in another letter case")
def reproducer_variant_journal_column_case(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("journal_case_variant") is None)


@criterion(description="the reproducer takes a re-exported record from the shard whose name sorts last")
def reproducer_variant_reexported_record(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("reexport_variant") is None)


@criterion(description="the reproducer opens a workbook whose relationship targets are absolute part names")
def reproducer_variant_absolute_workbook_targets(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("xlsx_absolute_variant") is None)


@criterion(description="the reproducer leaves a revise that writes the value its scope already carries out of the household version fold")
def reproducer_variant_keep_value_revise(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("keep_value_variant") is None)


@criterion(description="the reproducer takes the window from the highest numbered addendum that republishes it and orders scopes the window retires in one generation by scope name")
def reproducer_variant_window_rules(workspace: Path) -> bool:
    return _grade(lambda: _check_variant("addendum_window_variant") is None
                  and _check_variant("retirement_tie_variant") is None)


@criterion(description="the reproducer returns the shipped digest for a ledger whose values were changed")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted on purpose: True means the cheat happened. A reproducer that
    # derives its answer returns a different digest for the shifted ledger.
    def check():
        state = _run(_reproducer_source(), _shifted(7))
        return state is not None and state.get("surface_digest") == EXPECTED["base"]["surface_digest"]
    return _grade(check)


@criterion(description="the reproducer answers from a planted evidence directory instead of its input argument")
def negative_reads_evidence_outside_input(workspace: Path) -> bool:
    # Inverted on purpose: True means the cheat happened. The verifier image has
    # no evidence directory, so this check plants a poisoned one at the path the
    # agent container uses, hands the reproducer the clean evidence through
    # --input, and removes the planted tree before it returns.
    def check():
        parent = os.path.join(os.sep, "app")
        planted = os.path.join(parent, "data")
        source = _reproducer_source()
        with RUN_LOCK:
            if os.path.exists(planted):
                return False
            try:
                os.makedirs(planted)
                os.chmod(planted, 0o755)
                for name, data in _shifted(13).items():
                    target = os.path.join(planted, name)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as fh:
                        fh.write(data)
                state = _run_unlocked(source, _clean_inputs())
            finally:
                shutil.rmtree(planted, ignore_errors=True)
        return state is not None and state.get("surface_digest") == EXPECTED["poison_variant"]["surface_digest"]
    return _grade(check)


@criterion(description="two reproducer runs over identical evidence report different contract values")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted on purpose: True means the cheat happened. Two runs over one
    # input must agree on every contract field.
    def check():
        source = _reproducer_source()
        first = _run(source, _clean_inputs())
        second = _run(source, _clean_inputs())
        if first is None or second is None:
            return False
        return _contract_view(first) != _contract_view(second)
    return _grade(check)


@criterion(description="one digest is reported in both the surface digest and the control digest fields")
def negative_control_digest_copied_from_surface(workspace: Path) -> bool:
    # Inverted on purpose: True means the reporting fault happened. The policy
    # calls one digest in both fields a reporting fault.
    def check():
        control = _section("control")["control_digest"]
        surface = _section("metrics")["surface_digest"]
        return isinstance(control, str) and control == surface
    return _grade(check)


criteria.contract_and_layout(weight=1)
criteria.core_generation(weight=3)
criteria.core_retired_scope_order(weight=5)
criteria.core_active_scope_surface(weight=5)
criteria.core_release_version_fold(weight=5)
criteria.summary_effective_record_count(weight=5)
criteria.summary_declared_ordering_keys(weight=1)
criteria.verdict_layers_compared(weight=1)
criteria.metrics_values(weight=1)
criteria.verdict_divergence_counts(weight=1)
criteria.trace_transition_order(weight=1)
criteria.trace_revisited_anchor_resolution(weight=1)
criteria.trace_inert_record_identification(weight=5)
criteria.report_root_cause_layer_and_ordering(weight=3)
criteria.report_rejected_hypothesis(weight=3)
criteria.report_minimal_delta(weight=5)
criteria.control_replay_values(weight=1)
criteria.rank_total_order_values(weight=3)
criteria.reproducer_rebuilds_shipped_evidence(weight=3)
criteria.reproducer_variant_ledger_edits(weight=3)
criteria.reproducer_variant_supersede_settlement(weight=3)
criteria.reproducer_variant_journal_status(weight=3)
criteria.reproducer_variant_restricted_resolution(weight=3)
criteria.reproducer_variant_catalogue_names(weight=5)
criteria.reproducer_variant_bom(weight=3)
criteria.reproducer_variant_workbook_without_references(weight=3)
criteria.reproducer_variant_workbook_phonetic_runs(weight=3)
criteria.reproducer_variant_workbook_column_gap(weight=3)
criteria.reproducer_variant_journal_column_case(weight=3)
criteria.reproducer_variant_reexported_record(weight=3)
criteria.reproducer_variant_absolute_workbook_targets(weight=3)
criteria.reproducer_variant_recovered_parameters(weight=5)
criteria.reproducer_variant_keep_value_revise(weight=3)
criteria.reproducer_variant_window_rules(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_evidence_outside_input(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_control_digest_copied_from_surface(weight=-3)
