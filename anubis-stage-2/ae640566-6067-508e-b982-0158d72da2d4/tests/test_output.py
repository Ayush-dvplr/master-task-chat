"""Verifier for the Helios gravimeter array calibration reconciliation bundle.

Positive tests assert that the reusable derivation program produced by the agent
reproduces an independent implementation of the shipped contract, both on the
archive the agent was given and on unseen archives generated here.

Negative tests are written so that the assertion HOLDS when the cheat is present.
An honest agent makes the assertion fail, so the negative weight is not added. Each
negative test first requires the artefact or program it audits to exist, so an empty
container errors out of every negative test instead of collecting free weight.
"""

# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

import ast
import csv
import io
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = 2563386167639298110
CHALLENGE_SEED = 1969987839303216534
EVAL_SEED = 8478492659518525054
DUPLICATE_PROBE_SEED = EVAL_SEED ^ 0x5D
SEQUENCE_PROBE_SEED = CHALLENGE_SEED ^ 0x2B
BUDGET_PROBE_SEED = EVAL_SEED ^ 0x02
RATIO_PROBE_SEED = EVAL_SEED ^ 0x3B
RESTORE_PROBE_SEED = CHALLENGE_SEED ^ 0x4C
INSTANT_PROBE_SEED = SAMPLE_SEED ^ 0x17
FLAG_PROBE_SEED = SAMPLE_SEED ^ 0x62
MALFORMED_PROBE_SEED = CHALLENGE_SEED ^ 0x71
EXPIRY_PROBE_SEED = EVAL_SEED ^ 0x4E
VALUE_PROBE_SEED = SAMPLE_SEED ^ 0x35
STANDING_PROBE_SEED = EVAL_SEED ^ 0x63
DRIFT_TIE_PROBE_SEED = SAMPLE_SEED ^ 0x29
LARGEST_TIE_PROBE_SEED = CHALLENGE_SEED ^ 0x3A
ALERT_GATE_PROBE_SEED = EVAL_SEED ^ 0x47

_BOUND = {"root": Path(os.environ.get("APP_ROOT", "/app"))}


def _bind(workspace):
    """Point every helper at the workspace the grader handed this check."""
    if workspace is not None:
        _BOUND["root"] = Path(workspace)
    return _BOUND["root"]


def _out():
    return _BOUND["root"] / "out"


def _script():
    return _out() / "derive_report.py"


def _need(condition, message):
    """Raise on a failed expectation; never `assert`, which -O would discard."""
    if not condition:
        raise AssertionError(message)
    return True

AREA_NAMES = ["East", "North", "South", "West"]
CLASS_NAMES = ["commercial", "public"]
ARTIFACT_NAMES = (
    ["summary.json", "policy_audit.json", "data_quality.json"]
    + ["region_%s.json" % name for name in AREA_NAMES]
    + ["segment_%s.json" % name for name in CLASS_NAMES]
)

MICRO = 1000000
REASON_ORDER = (
    "duplicate_sample",
    "unresolved_suspect",
    "malformed_sample",
    "unknown_channel",
    "no_deployment",
    "no_custody",
    "no_certificate",
    "unknown_unit",
    "broken_ladder",
    "unreported_array",
)

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


# --------------------------------------------------------------------------
# The archive shipped to the agent, held verbatim so the verifier can rebuild it.
# --------------------------------------------------------------------------

VISIBLE_FILES = {
    "contract.md": "# Helios gravimeter array derivation contract\n\nThe reference tables in this directory are authoritative.\n",
    "policy.json": """{
  "report_id": "HELIOS-2031-R07",
  "canonical_unit": "nm/s^2",
  "network_gain_micro": 998500,
  "network_offset_nano": -40,
  "network_drift_nano_per_sample": 12,
  "minimum_reported_nano": -800,
  "uncertainty_budget_nano": 9007199254741015
}
""",
    "thresholds.json": """{
  "reported_arrays": ["East", "North", "South", "West"],
  "reported_segments": ["commercial", "public"],
  "reporting_floor_bands": [
    {"reporting_arrays_at_least": 0, "minimum_qualifying_observations": 4},
    {"reporting_arrays_at_least": 1, "minimum_qualifying_observations": 3},
    {"reporting_arrays_at_least": 2, "minimum_qualifying_observations": 2}
  ],
  "custody_secondary_band": 2,
  "variance_alert_nano": 1000000,
  "quarantine_alert_ratio_ppm": 200000
}
""",
    "units.csv": """unit_token,factor_nano
nm/s^2,1
um/s^2,1000
uGal,10
microGal,10
mGal,10000000
nGal,1/100
ft/s^2, 3048000000 / 10
gu,10/0
""",
    "channel_registry.csv": """channel_id,model,provisional,reporting_area
HLS-0004,GRV-2,False,North
HLS-0011,GRV-2,true,North
HLS-0017,GRV-3,false,East
HLS-0023,GRV-3,false,Central
HLS-0031,GRV-1,TRUE,West
HLS-0042,GRV-3,false,East
HLS-0056,GRV-1,false,South
""",
    "channel_aliases.csv": """alias_token,channel_id
NORTHPIER-A,HLS-0004
RIDGE2,HLS-0017
OLDCAVE,HLS-0023
HLS-7,HLS-0056
DECOMM-9,HLS-0099
""",
    "stations.csv": """station_id,array_name,station_gain_micro,station_offset_nano,station_drift_nano_per_sample
ST-CENT-1,Central,,,25
ST-EAST-1,East,1001000,10,5
ST-NORTH-1,North,1002500,,15
ST-NORTH-2,North,,60,
ST-SOUTH-1,South,997000,-25,
ST-WEST-1,West,,,40
""",
    "deployments.csv": """deployment_id,channel_id,station_id,valid_from,valid_to
DEP-01,HLS-0004,ST-NORTH-1,2031-01-01T00:00:00,2031-03-31T23:59:59
DEP-02,HLS-0004,ST-WEST-1,2031-04-01T00:00:00,
DEP-03,HLS-0011,ST-NORTH-2,2031-01-01T00:00:00,
DEP-04,HLS-0017,ST-SOUTH-1,2031-01-01T00:00:00,2031-05-31T23:59:59
DEP-05,HLS-0017,ST-EAST-1,2031-05-01T00:00:00,
DEP-06,HLS-0023,ST-CENT-1,2031-02-15T00:00:00,
DEP-07,HLS-0031,ST-WEST-1,2031-01-01T00:00:00,2031-06-30T23:59:59
DEP-08,HLS-0042,ST-EAST-1,2031-03-01T00:00:00,
DEP-09,HLS-0056,ST-SOUTH-1,2031-01-01T00:00:00,
DEP-10,HLS-0056,ST-NORTH-2,2031-01-01T00:00:00,
""",
    "agencies.csv": """agency_id,agency_name,operator_class
AG-CRD,"Cordilleran Geophysics, Ltd",commercial
AG-KLV,Kelvin Instruments,commercial
AG-MSB,"Meridian Survey Bureau, Northern Division",public
AG-TVL,Tidewater Volunteers,public
""",
    "custody.csv": """custody_id,station_id,agency_id,effective_from,effective_to,array_channel_id,custodian_channel_id
CU-01,ST-NORTH-1,AG-MSB,2031-01-01T00:00:00,2031-02-28T23:59:59,,
CU-02,ST-NORTH-1,AG-CRD,2031-03-01T00:00:00,,,,
CU-03,ST-NORTH-2,AG-TVL,2031-01-01T00:00:00,,,,
CU-04,ST-SOUTH-1,AG-KLV,2031-01-01T00:00:00,,,,
CU-05,ST-WEST-1,AG-CRD,2031-02-01T00:00:00,,,,
CU-06,ST-EAST-1,AG-MSB,2031-01-01T00:00:00,2031-04-30T23:59:59,,
CU-07,ST-EAST-1,AG-KLV,2031-04-15T00:00:00,,,,
CU-08,ST-CENT-1,AG-TVL,2031-01-01T00:00:00,,,,
CU-09,ST-SOUTH-1,AG-MSB,2031-01-01T00:00:00,,,,
SC-01,,,,,HLS-0031,HLS-0004
SC-02,,,,,HLS-0056,HLS-0031
SC-03,,,,,HLS-0023,HLS-0056
""",
    "standards.csv": """standard_id,parent_standard_id,ratio_ppm
STD-PRIME,,0
STD-A,STD-PRIME,120
STD-B,STD-A,-45
STD-C,STD-B,30
STD-D,STD-PRIME,-200
STD-E,STD-D,65
""",
    "certificates.csv": """certificate_id,channel_id,valid_from,valid_to,gain_micro,offset_nano,drift_nano_per_sample,standard_id
CERT-0004-A,HLS-0004,2031-01-01T00:00:00,2031-03-31T23:59:59,1004000,25,8,STD-B
CERT-0004-B,HLS-0004,2031-04-10T00:00:00,,1003000,,,STD-C

CERT-0011-A,HLS-0011,2031-01-01T00:00:00,, 1000500 , -10 , 3 ,STD-A
CERT-0017-A,HLS-0017,2031-01-01T00:00:00,,999000,,6,STD-E
CERT-0017-B,HLS-0017,2031-05-05T00:00:00,,,15,,STD-D
CERT-0017-C,HLS-0017,2031-05-05T00:00:00,2031-06-01T00:00:00,1000100,,2,STD-A
CERT-0023-A,HLS-0023,2031-02-01T00:00:00,,,5,0,STD-A
CERT-0031-A,HLS-0031,2031-01-01T00:00:00,,1005000,,,STD-Z
CERT-0031-B,HLS-0031,2031-03-01T00:00:00,,1002000,20,4,STD-C
CERT-0042-A,HLS-0042,2031-03-01T00:00:00,,996000,-30,10,STD-D
CERT-0042-B,HLS-0042,2031-06-01T00:00:00,,1000200,0,1,STD-B
CERT-0056-A,HLS-0056,2031-02-01T00:00:00,2031-05-31T23:59:59,1001500,12,,STD-C
CERT-0042-C,HLS-0042,2031-03-01T00:00:00,2031-5-31 23:59:59,997500,-20,7,STD-A
""",
    "observations.csv": """sample_id,channel_token,epoch,raw_count,unit_token,status,standing_basis
S-0001,NORTHPIER-A,2031-01-12T04:00:00,4200,nm/s^2,observed,true
S-0002,hls_4,2031-02-03T09:30:00,3150,uGal,observed,true
S-0003,HLS-04,2031-03-21T18:15:00,-880,nm/s^2,observed,true
S-0004,HLS-0004,2031-04-18T02:05:00,512,um/s^2,observed,true
S-0005,hls-0004,2031-05-02T11:45:00,27,mGal,observed,false
S-0006,HLS-0011,2031-01-05T06:00:00,9100,nm/s^2,observed,true
S-0007,hls11,2031-02-19T22:10:00,640,microGal,observed,true
S-0008,HLS_0011,2031-03-08T13:20:00,1500,NM/S^2,suspect,false
S-0009,HLS-11,2031-04-27T07:55:00,-320,nm/s^2,observed,false
S-0010,RIDGE2,2031-01-30T15:00:00,7400,nm/s^2,observed,true
S-0011,hls-0017,2031-03-14T06:20:00,288,uGal,observed,true
S-0012,HLS0017,2031-05-12T10:00:00,5300,nm/s^2,observed,false
S-0013,OLDCAVE,2031-02-01T00:00:00,1200,nm/s^2,observed,true
S-0014,HLS-0023,2031-03-05T08:40:00,2500,nm/s^2,observed,true
S-0015,hls_23,2031-04-09T16:30:00,410,uGal,observed,false
S-0016,HLS-0031,2031-01-20T05:10:00,6600,nm/s^2,observed,true
S-0017,hls-31,2031-02-10T12:00:00,3300,nm/s^2,observed,true
S-0018,HLS_31,2031-03-18T19:25:00,780,uGal,observed,true
S-0019,HLS-0031,2031-05-23T03:35:00,-145,nm/s^2,observed,false
S-0020,HLS-0031,2031-07-15T09:00:00,900,nm/s^2,observed,false
S-0021,HLS-0042,2031-03-02T01:00:00,8800,nm/s^2,observed,true
S-0022,hls42,2031-04-20T14:45:00,96,mGal,observed,false
S-0023,HLS-42,2031-06-11T20:00:00,4100,nm/s^2,observed,false
S-0024,HLS-0042,2031-06-28T08:15:00,155,uGal,void,false
S-0025,HLS-7,2031-01-08T10:30:00,5000,nm/s^2,observed,false
S-0026,HLS-0056,2031-02-22T17:40:00,2200,nm/s^2,observed,true
S-0027,hls_56,2031-03-30T23:50:00,175,uGal,suspect,true
S-0028,HLS-56,2031-05-19T04:20:00,-640,nm/s^2,observed,true
S-0029,DECOMM-9,2031-03-11T11:11:00,1000,nm/s^2,observed,false
S-0030,HLS-0004,2031-06-05T13:00:00,3600,pGal,observed,false
S-0031,HLS-0017,2031-06-18T09:45:00,1850,nm/s^2,suspect,false
S-0032,HLS-0011,2031-05-30T21:05:00,720,uGal,observed,false
S-0033,HLS-0023,2031-05-08T07:30:00,3900,nm/s^2,void,true
S-0034,HLS-0056,2031-06-22T18:00:00,60,mGal,observed,false
S-0035,HLS-0004,2031-3-31 23:59:59,-1500,nm/s^2,observed,true
S-0036,HLS-0056,2031-2-1 0:00:00,-333,nm/s^2,observed,false
S-0011,hls-0017,2031-03-14T06:20:00,288,uGal,observed,true
S-0037,HLS-0017,2031-05-05T00:00:00,-7,uGal,observed,false
S-0021,HLS-0042,2031-03-02T01:00:00,8800,nm/s^2,observed,true
S-0038,HLS-0031,2031-6-30 23:59:59,450,nm/s^2,observed,TRUE
S-0039,HLS-0056,2031-04-02T08:00:00,-1,ft/s^2,observed,false
S-0040,HLS-0004,2031-2-14 10:00:00,250,nGal,observed,true
S-0041,hls_56,2031-04-09T12:00:00,-250,n-Gal,observed,false
S-0042,HLS-0042,2031-03-10T09:00:00,40,GU,observed,true
S-0043,HLS-0004,2031-02-20T08:00:00,1_200,nm/s^2,observed,true
S-0044,HLS-0031,2031-03-03T03:03:00,١٢,nm/s^2,observed,true
S-0045,HLS-0056,2031-03-05,700,nm/s^2,observed,true
S-0046,NOSUCH-1,2031-03-06T00:00:00,12.0,nm/s^2,observed,true
S-0047,HLS-0004,2031-02-25T10:00:00, +640 ,nm/s^2,observed,false
S-0048,HLS-0031,2031-04-04T04:00:00,3.5,nm/s^2,observed,false
""",
    "amendments.jsonl": """{"entry_id": "AM-01", "sequence": 70, "op": "revise", "sample_id": "S-0002", "raw_count": 3180}
{"entry_id": "AM-02", "sequence": 30, "op": "void", "sample_id": "S-0032"}
{"entry_id": "AM-03", "sequence": 10, "op": "revise", "sample_id": "S-0032", "raw_count": 999}
{"entry_id": "AM-04", "sequence": 40, "op": "certify", "sample_id": "S-0008"}
{"entry_id": "AM-05", "sequence": 20, "op": "reinstate", "sample_id": "S-0033"}
{"entry_id": "AM-06", "sequence": 60, "op": "revoke_certificate", "certificate_id": "CERT-0042-B"}
{"entry_id": "AM-07", "sequence": 15, "op": "revise", "sample_id": "S-0034", "raw_count": 58, "unit_token": "mGal"}
{"entry_id": "AM-08", "sequence": 90, "op": "revise", "sample_id": "S-0011", "epoch": "2031-06-02T06:20:00"}
{"entry_id": "AM-09", "sequence": 25, "op": "certify", "sample_id": "S-0027"}
{"entry_id": "AM-10", "sequence": 50, "op": "void", "sample_id": "S-0021"}
{"entry_id": "AM-11", "sequence": 20, "op": "reinstate", "sample_id": "S-0021"}
{"entry_id": "AM-12", "sequence": 80, "op": "revise", "sample_id": "S-0999", "raw_count": 1}
{"entry_id": "AM-13", "sequence": 35, "op": "revoke_certificate", "certificate_id": "CERT-9999-Z"}
{"entry_id": "AM-14", "sequence": 45, "op": "certify", "sample_id": "S-0026"}
{"entry_id": "AM-15", "sequence": 55, "op": "reinstate", "sample_id": "S-0014"}
{"entry_id": "AM-16", "sequence": 65, "op": "revise", "sample_id": "S-0015", "channel_token": "HLS-0042"}
{"entry_id": "AM-17", "sequence": 75, "op": "void", "sample_id": "S-0024"}
{"entry_id": "AM-06", "sequence": 85, "op": "revoke_certificate", "certificate_id": "CERT-0017-C"}
{"entry_id": "AM-18", "sequence": 95, "op": "revoke_certificate", "certificate_id": "CERT-0042-B"}
{"entry_id": "AM-19", "sequence": 5, "op": "annotate", "sample_id": "S-0001", "note": "field audit"}
{"entry_id": "AM-21", "sequence": 12, "op": "revoke_certificate", "certificate_id": "CERT-0004-B"}
{"entry_id": "AM-22", "sequence": 8, "op": "restore_certificate", "certificate_id": "CERT-0004-B"}
{"entry_id": "AM-24", "sequence": 47, "op": "restore_certificate", "certificate_id": "CERT-0017-C"}
{"entry_id": "AM-23", "sequence": 33, "op": "revoke_certificate", "certificate_id": "CERT-0017-C"}
{"entry_id": "AM-24", "sequence": 3.0, "op": "restore_certificate", "certificate_id": "CERT-0017-C"}
{"entry_id": "AM-25", "sequence": 58, "op": "void", "sample_id": "S-00
{"entry_id": "AM-26", "sequence": "52", "op": "void", "sample_id": "S-0026"}
["AM-27", 5, "void", "S-0001"]
{"entry_id": "AM-28", "sequence": true, "op": "certify", "sample_id": "S-0031"}
{"entry_id": "AM-29", "sequence": 68, "op": "revise", "sample_id": "S-0012", "standing_basis": true}
{"entry_id": "AM-20", "sequence": 62, "op": "restore_certificate", "certificate_id": "CERT-0042-B"}
{"entry_id": "AM-31", "sequence": 66, "op": "revise", "sample_id": "S-0048", "raw_count": 35}
{"entry_id": "AM-32", "sequence": 64, "op": "revise", "sample_id": "S-0016", "raw_count": "6600"}
{"entry_id": "AM-33", "sequence": 71, "op": "revise", "sample_id": "S-0026", "epoch": "2031-02-22"}
{"entry_id": "AM-99", "sequence": 77, "op": "void", "sample_id": "S-0013"}
{"entry_id": "am-30", "sequence": 72, "op": "revise", "sample_id": "S-0010", "raw_count": 7300}
{"entry_id": "AM-100", "sequence": 77, "op": "reinstate", "sample_id": "S-0013"}
{"entry_id": "AM-30", "sequence": 72, "op": "revise", "sample_id": "S-0010", "raw_count": 7500}
{"entry_id": "AM-38", "sequence": 87, "op": "revise_standard", "standard_id": "STD-C", "parent_standard_id": "STD-D"}
{"entry_id": "AM-35", "sequence": 54, "op": "revise_standard", "standard_id": "STD-E", "ratio_ppm": 80}
{"entry_id": "AM-37", "sequence": 41, "op": "revise_standard", "standard_id": "STD-X", "ratio_ppm": 5}
{"entry_id": "AM-34", "sequence": 87, "op": "revise_standard", "standard_id": "STD-C", "parent_standard_id": "STD-A"}
{"entry_id": "AM-36", "sequence": 54, "op": "revise_standard", "standard_id": "STD-E", "ratio_ppm": "95"}
""",
}
VISIBLE_FILES["calibration_example.json"] = "{}\n"
VISIBLE_FILES["calibration_slice.json"] = "{}\n"

CALIBRATION_FILES = {
    "contract.md": "# Calibration slice\n",
    "policy.json": json.dumps({
        "report_id": "HELIOS-CALIBRATION-CONTROL",
        "canonical_unit": "nm/s^2",
        "network_gain_micro": 1000000,
        "network_offset_nano": 0,
        "network_drift_nano_per_sample": 0,
        "minimum_reported_nano": -100,
        "uncertainty_budget_nano": 101,
    }),
    "thresholds.json": json.dumps({
        "reported_arrays": ["North", "South", "West", "East"],
        "reported_segments": ["commercial", "public"],
        "reporting_floor_bands": [
            {"reporting_arrays_at_least": 0, "minimum_qualifying_observations": 1},
            {"reporting_arrays_at_least": 1, "minimum_qualifying_observations": 1},
        ],
        "custody_secondary_band": 1,
        "variance_alert_nano": 1000,
        "quarantine_alert_ratio_ppm": 500000,
    }),
    "units.csv": "unit_token,factor_nano\nnm/s^2,1\nnGal,1/100\n",
    "channel_registry.csv": """channel_id,model,provisional,reporting_area
HLS-0001,CTRL,false,North
HLS-0002,CTRL,false,North
HLS-0003,CTRL,false,South
HLS-0004,CTRL,false,South
HLS-0005,CTRL,false,West
HLS-0006,CTRL,false,East
HLS-0007,CTRL,false,East
HLS-0008,CTRL,false,East
HLS-0009,CTRL,false,North
""",
    "channel_aliases.csv": "alias_token,channel_id\nHLS-9,HLS-0001\n",
    "stations.csv": """station_id,array_name,station_gain_micro,station_offset_nano,station_drift_nano_per_sample
ST-N,North,,,
ST-S,South,,,
ST-W,West,,,
ST-E,East,,,
""",
    "deployments.csv": """deployment_id,channel_id,station_id,valid_from,valid_to
DP-01,HLS-0001,ST-N,2031-01-01T00:00:00,
DP-02,HLS-0002,ST-MISSING,2031-01-01T00:00:00,
DP-03,HLS-0003,ST-S,2031-01-01T00:00:00,
DP-04,HLS-0004,ST-N,2031-01-01T00:00:00,
DP-05,HLS-0005,ST-W,2031-01-01T00:00:00,
DP-06,HLS-0006,ST-E,2031-01-01T00:00:00,
""",
    "agencies.csv": "agency_id,agency_name,operator_class\nAG-C,Control Commercial,commercial\nAG-P,Control Public,public\n",
    "custody.csv": """custody_id,station_id,agency_id,effective_from,effective_to,array_channel_id,custodian_channel_id
CU-N,ST-N,AG-P,2031-01-01T00:00:00,,,
CU-W,ST-W,AG-C,2031-01-01T00:00:00,,,
CU-E,ST-E,AG-P,2031-01-01T00:00:00,,,
""",
    "standards.csv": "standard_id,parent_standard_id,ratio_ppm\nSTD-P,,0\nSTD-X,STD-MISSING,10\n",
    "certificates.csv": """certificate_id,channel_id,valid_from,valid_to,gain_micro,offset_nano,drift_nano_per_sample,standard_id
CT-01-A,HLS-0001,2031-01-01T00:00:00,,1000000,0,0,STD-P
CT-01-B,HLS-0001,2031-01-02T00:00:00,,2000000,0,0,STD-P
CT-05-A,HLS-0005,2031-01-01T00:00:00,,1000000,0,0,STD-X
CT-06-A,HLS-0006,2031-01-01T00:00:00,2031-01-12T00:00:00,500000,0,0,STD-P
""",
    "observations.csv": """sample_id,channel_token,epoch,raw_count,unit_token,status,standing_basis
C-01,NOSUCH,2031-01-10T00:00:00,1,pGal,observed,true
C-02,HLS-0002,2031-01-10T00:00:00,1,pGal,observed,true
C-03,HLS-0003,2031-01-10T00:00:00,1,pGal,observed,true
C-04,HLS-0004,2031-01-10T00:00:00,1,pGal,observed,true
C-05,HLS-0005,2031-01-10T00:00:00,1,pGal,observed,true
C-06,HLS-0005,2031-01-11T00:00:00,1,nm/s^2,observed,true
C-07,HLS-0006,2031-01-10T00:00:00,1,nm/s^2,observed,true
C-08,HLS-0006,2031-01-11T00:00:00,-1,nm/s^2,observed,true
C-09,HLS-9,2031-01-12T00:00:00,10,nm/s^2,observed,true
C-09,NOSUCH-9,2031-01-12T00:00:00,999,nm/s^2,suspect,true
C-10,HLS-0001,2031-01-13T00:00:00,20,nm/s^2,observed,true
C-11,HLS-0001,2031-01-14T00:00:00,30,nm/s^2,observed,false
C-12,HLS-0007,2031-01-10T00:00:00,1,nm/s^2,suspect,true
C-13,HLS-0008,2031-01-10T00:00:00,1,nm/s^2,void,true
C-14,HLS-0006,2031-01-12T00:00:00,1,nm/s^2,observed,true
C-15,HLS-0001,2031-1-15 00:00:00,-50,ngal,observed,TRUE
C-16,NOSUCH-16,2031-01-16T00:00:00,1_0,nm/s^2,observed,true
C-17,HLS-0006,2031-01-13T00:00:00,1,nm/s^2,observed,true
C-18,HLS-0001,2031-01-16T00:00:00,2.5,nm/s^2,observed,false
C-19,HLS-0001,2031-01-17T00:00:00,5,nm/s^2,observed,false
""",
    "amendments.jsonl": (
        '{"entry_id":"CAL-VOID","sequence":40,"op":"void","sample_id":"C-13"}\n'
        '{"entry_id":"CAL-REV","sequence":10,"op":"revoke_certificate","certificate_id":"CT-01-B"}\n'
        '{"entry_id":"CAL-RST","sequence":30,"op":"reinstate","sample_id":"C-13"}\n'
        '{"entry_id":"CAL-REV","sequence":50,"op":"revoke_certificate","certificate_id":"CT-06-A"}\n'
        '{"entry_id":"CAL-DUP","sequence":20,"op":"revoke_certificate","certificate_id":"CT-01-B"}\n'
        '{"entry_id":"CAL-RES","sequence":5,"op":"restore_certificate","certificate_id":"CT-01-B"}\n'
        '{"entry_id":"CAL-BAD","sequence":"45","op":"void","sample_id":"C-10"}\n'
        '{"entry_id":"cal-fix","sequence":15,"op":"revise","sample_id":"C-18","raw_count":9}\n'
        '{"entry_id":"CAL-FIX","sequence":15,"op":"revise","sample_id":"C-18","raw_count":4}\n'
        '{"entry_id":"CAL-DMG","sequence":25,"op":"revise","sample_id":"C-19","raw_count":5.0}\n'
        '{"entry_id":"CAL-T10","sequence":45,"op":"reinstate","sample_id":"C-13"}\n'
        '{"entry_id":"CAL-T9","sequence":45,"op":"void","sample_id":"C-13"}\n'
    ),
    "control.json": "{}\n",
}


# --------------------------------------------------------------------------
# Deterministic pseudo random source used to build unseen archives.
# --------------------------------------------------------------------------


class Rng:
    def __init__(self, seed):
        self.state = (seed & 0xFFFFFFFFFFFFFFFF) or 0x9E3779B97F4A7C15

    def draw(self):
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 7
        x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return x

    def below(self, n):
        return self.draw() % n

    def span(self, low, high):
        return low + self.below(high - low + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def flag(self, numerator, denominator):
        return self.below(denominator) < numerator


# --------------------------------------------------------------------------
# Independent implementation of the shipped contract.
# --------------------------------------------------------------------------


def round_half_away(numerator, denominator, arithmetic="exact"):
    """Round numerator/denominator to an integer, exact halves away from zero.

    `exact` is integer arithmetic of unbounded width. `float` and `decimal` model the
    fixed precision paths (binary double, default 28 digit decimal) a shortcut takes.
    """
    if arithmetic == "float":
        quotient = numerator / denominator
        magnitude = int(math.floor(abs(quotient) + 0.5))
        return magnitude if quotient >= 0 else -magnitude
    if arithmetic == "decimal":
        quotient = Decimal(numerator) / Decimal(denominator)
        return int(quotient.to_integral_value(rounding=ROUND_HALF_UP))
    whole, rest = divmod(abs(numerator), abs(denominator))
    if 2 * rest >= abs(denominator):
        whole += 1
    return whole if (numerator >= 0) == (denominator > 0) else -whole


def label_key(text):
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def unit_key(text):
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def split_rows(text):
    records = [
        record for record in csv.reader(io.StringIO(text))
        if record and any(cell.strip() for cell in record)
    ]
    if not records:
        return []
    header = [cell.strip() for cell in records[0]]
    rows = []
    for record in records[1:]:
        cells = [cell.strip() for cell in record]
        cells += [""] * (len(header) - len(cells))
        rows.append({header[index]: cells[index] for index in range(len(header))})
    return rows


def load_tables(data_dir):
    data_dir = Path(data_dir)
    tables = {}
    for stem in (
        "units", "channel_registry", "channel_aliases", "stations", "deployments",
        "agencies", "custody", "certificates", "standards", "observations",
    ):
        tables[stem] = split_rows((data_dir / (stem + ".csv")).read_text(encoding="utf-8"))
    tables["policy"] = json.loads((data_dir / "policy.json").read_text(encoding="utf-8"))
    tables["thresholds"] = json.loads((data_dir / "thresholds.json").read_text(encoding="utf-8"))
    tables["ledger_lines"] = (data_dir / "amendments.jsonl").read_text(encoding="utf-8").split("\n")
    tables["file_count"] = sum(1 for item in data_dir.iterdir() if item.is_file())
    return tables


def maybe_int(text):
    text = (text or "").strip()
    return None if text == "" else int(text)


_INSTANT = re.compile(r"^([0-9]+)-([0-9]+)-([0-9]+)[T ]([0-9]+):([0-9]+):([0-9]+)$")
_WHOLE = re.compile(r"^[+-]?[0-9]+$")


def instant(text, parse=True):
    """Reduce any admitted timestamp spelling to a comparable instant."""
    text = (text or "").strip()
    if not parse or text == "":
        return text
    match = _INSTANT.match(text)
    if match is None:
        raise ValueError("unreadable timestamp %r" % text)
    return tuple(int(part) for part in match.groups())


def sample_instant(text, parse=True):
    """Read an observation epoch, returning None when it names no readable instant."""
    if text is None:
        return None
    text = text.strip()
    if text == "":
        return None
    if not parse:
        return text
    match = _INSTANT.match(text)
    return None if match is None else tuple(int(part) for part in match.groups())


def whole_count(text, strict=True):
    """Read a raw count, returning None when it is not a whole number in the contract's form."""
    if text is None:
        return None
    text = text.strip()
    if strict:
        return int(text) if _WHOLE.match(text) else None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return int(float(text))
    except (ValueError, OverflowError):
        return None


def ledger_rank(entry, codepoint=True):
    """Sort key for ledger replay: sequence, then entry identifier."""
    marker = entry["entry_id"]
    if codepoint:
        return (entry["sequence"], marker)
    pieces = re.split(r"([0-9]+)", marker.casefold())
    return (entry["sequence"], tuple(
        (1, int(piece)) if piece.isdigit() else (0, piece) for piece in pieces if piece
    ))


def flag_value(text, blank, fold=True):
    text = (text or "").strip()
    if text == "":
        return blank
    return (text.lower() if fold else text) == "true"


def unit_ratio(text, exact=True, zero_rule=True):
    """Return (numerator, denominator) for a well formed positive factor, else None."""
    text = (text or "").strip()
    pieces = [piece.strip() for piece in text.split("/")] if "/" in text else [text, "1"]
    if len(pieces) != 2:
        return None
    if exact:
        if not all(re.fullmatch(r"[0-9]+", piece) for piece in pieces):
            return None
        top, bottom = int(pieces[0]), int(pieces[1])
        if not zero_rule and top == 0 and bottom > 0:
            return (top, bottom)
        return (top, bottom) if top > 0 and bottom > 0 else None
    try:
        top, bottom = float(pieces[0]), float(pieces[1])
    except ValueError:
        return None
    return None if bottom == 0 else (top / bottom, None)


def canonical_of(raw, ratio, arithmetic="exact"):
    top, bottom = ratio
    if bottom is None:
        return int(round(raw * top))
    return round_half_away(raw * top, bottom, arithmetic)


def inside(row, start_key, end_key, epoch, parse=True):
    start = instant(row[start_key], parse)
    end = instant(row[end_key], parse)
    if epoch < start:
        return False
    return not (end != "" and epoch > end)


def choose_interval(rows, start_key, end_key, id_key, epoch, temporal, parse=True):
    if not temporal:
        return rows[-1] if rows else None
    live = [row for row in rows if inside(row, start_key, end_key, epoch, parse)]
    if not live:
        return None
    latest = max(instant(row[start_key], parse) for row in live)
    return min(
        (row for row in live if instant(row[start_key], parse) == latest),
        key=lambda row: row[id_key],
    )


def chain_ppm(standards, standard_id, strict_cycles=True):
    total = 0
    seen = []
    cursor = standard_id
    while cursor in standards and cursor not in seen:
        seen.append(cursor)
        parent = standards[cursor]["parent_standard_id"]
        if parent == "":
            return total
        total += int(standards[cursor]["ratio_ppm"])
        cursor = parent
    if not strict_cycles and cursor in seen:
        return total
    return None


def largest_remainder(budget, counts, names, exact):
    total = sum(counts.get(name, 0) for name in names)
    if total <= 0:
        return {name: 0 for name in names}
    if not exact:
        return {name: round_half_away(budget * counts.get(name, 0), total) for name in names}
    shares = {}
    rest = {}
    for name in names:
        weight = budget * counts.get(name, 0)
        shares[name] = weight // total
        rest[name] = weight - shares[name] * total
    ranked = sorted(names, key=lambda name: (-rest[name], name))
    spare = budget - sum(shares.values())
    position = 0
    while spare > 0:
        shares[ranked[position % len(ranked)]] += 1
        position += 1
        spare -= 1
    return shares


def parse_ledger(lines, strict=True, empty_rule=True):
    """Split the ledger into well formed entries and a count of malformed lines."""
    entries = []
    malformed = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if strict:
            marker = entry.get("entry_id") if isinstance(entry, dict) else None
            order = entry.get("sequence") if isinstance(entry, dict) else None
            if not (isinstance(marker, str) and (marker or not empty_rule) and type(order) is int):
                malformed += 1
                continue
        else:
            if not isinstance(entry, dict):
                continue
            try:
                entry = dict(entry, sequence=int(entry.get("sequence", 0)))
            except (TypeError, ValueError):
                continue
        entries.append(entry)
    return entries, malformed


def _standard_revision(entry, standards):
    """Classify a revise_standard entry as unmatched, ignored or apply, with its changes."""
    target = entry.get("standard_id")
    if not isinstance(target, str) or target not in standards:
        return "unmatched", None
    changes = {}
    if "parent_standard_id" in entry:
        parent = entry["parent_standard_id"]
        if not isinstance(parent, str):
            return "ignored", None
        changes["parent_standard_id"] = parent
    if "ratio_ppm" in entry:
        ratio = entry["ratio_ppm"]
        if type(ratio) is not int:
            return "ignored", None
        changes["ratio_ppm"] = str(ratio)
    if not changes:
        return "ignored", None
    return "apply", changes


def replay(tables, use_ledger, ledger_order=True, dedupe=True, strict_ledger=True, restore=True,
           strict_values=True, codepoint_ties=True, standard_mode="ledger", empty_rule=True):
    """Replay the ledger. `standard_mode` is `ledger` (the contract), `none` (revise_standard
    treated as an unknown operation) or `file` (standard revisions applied in file line order)."""
    standards = {row["standard_id"]: dict(row) for row in tables["standards"]}
    status = {}
    values = {}
    duplicates = 0
    for row in tables["observations"]:
        if dedupe and row["sample_id"] in status:
            duplicates += 1
            continue
        status[row["sample_id"]] = row["status"]
        values[row["sample_id"]] = {
            "channel_token": row["channel_token"],
            "epoch": row["epoch"],
            "raw_count": row["raw_count"],
            "unit_token": row["unit_token"],
            "standing_basis": row.get("standing_basis", ""),
        }
    cert_ids = {row["certificate_id"] for row in tables["certificates"]}
    revoked = set()
    ignored = 0
    unmatched = 0
    if not use_ledger:
        return status, values, revoked, ignored, unmatched, duplicates, standards
    ledger, unmatched = parse_ledger(tables["ledger_lines"], strict_ledger, empty_rule)
    if standard_mode == "file":
        claimed = set()
        for entry in ledger:
            if entry.get("op") != "revise_standard" or entry["entry_id"] in claimed:
                continue
            claimed.add(entry["entry_id"])
            verdict, changes = _standard_revision(entry, standards)
            if verdict == "apply":
                standards[entry["standard_id"]].update(changes)
    if ledger_order:
        ledger.sort(key=lambda item: ledger_rank(item, codepoint_ties))
    applied = set()
    for entry in ledger:
        marker = str(entry.get("entry_id", ""))
        if marker in applied:
            ignored += 1
            continue
        applied.add(marker)
        operation = entry.get("op")
        if operation == "revoke_certificate" or (restore and operation == "restore_certificate"):
            target = entry.get("certificate_id")
            if target not in cert_ids:
                unmatched += 1
            elif operation == "revoke_certificate":
                if target in revoked:
                    ignored += 1
                else:
                    revoked.add(target)
            elif target in revoked:
                revoked.discard(target)
            else:
                ignored += 1
            continue
        if operation == "revise_standard" and standard_mode != "none":
            verdict, changes = _standard_revision(entry, standards)
            if verdict == "unmatched":
                unmatched += 1
            elif verdict == "ignored":
                ignored += 1
            elif standard_mode == "ledger":
                standards[entry["standard_id"]].update(changes)
            continue
        target = entry.get("sample_id")
        if target not in status:
            unmatched += 1
            continue
        now = status[target]
        if operation == "revise":
            if now == "void":
                ignored += 1
                continue
            for key in ("channel_token", "unit_token", "standing_basis"):
                if key in entry:
                    values[target][key] = str(entry[key])
            if "epoch" in entry:
                stamp = entry["epoch"]
                if not strict_values:
                    values[target]["epoch"] = str(stamp)
                else:
                    values[target]["epoch"] = stamp if isinstance(stamp, str) else None
            if "raw_count" in entry:
                count = entry["raw_count"]
                if not strict_values:
                    values[target]["raw_count"] = str(count)
                else:
                    values[target]["raw_count"] = str(count) if type(count) is int else None
        elif operation == "void":
            if now == "void":
                ignored += 1
            else:
                status[target] = "void"
        elif operation == "reinstate":
            if now == "void":
                status[target] = "observed"
            else:
                ignored += 1
        elif operation == "certify":
            if now == "suspect":
                status[target] = "observed"
            else:
                ignored += 1
        else:
            unmatched += 1
    return status, values, revoked, ignored, unmatched, duplicates, standards


def derive(
    data_dir,
    use_ledger=True,
    honour_revocation=True,
    temporal=True,
    drift_reset=True,
    provisional=True,
    alias_first=True,
    exact_apportion=True,
    apply_floor=True,
    earned_standing=True,
    ledger_order=True,
    dedupe=True,
    rational_units=True,
    restore=True,
    parse_epochs=True,
    fold_flags=True,
    strict_ledger=True,
    honour_expiry=True,
    strict_values=True,
    codepoint_ties=True,
    arithmetic="exact",
    strict_cycles=True,
    standard_mode="ledger",
    zero_factor_rule=True,
    empty_entry_rule=True,
    drift_ties=True,
    inclusive_gate=True,
    largest_ties=True,
):
    tables = load_tables(data_dir)
    policy = tables["policy"]
    thresholds = tables["thresholds"]

    factors = {}
    for row in tables["units"]:
        ratio = unit_ratio(row["factor_nano"], rational_units, zero_factor_rule)
        if ratio is not None:
            factors[unit_key(row["unit_token"])] = ratio
    channels = {row["channel_id"]: row for row in tables["channel_registry"]}
    aliases = {label_key(row["alias_token"]): row["channel_id"] for row in tables["channel_aliases"]}
    stations = {row["station_id"]: row for row in tables["stations"]}
    agencies = {row["agency_id"]: row for row in tables["agencies"]}
    certificates = tables["certificates"]

    def provisional_flag(row):
        return flag_value(row.get("provisional", ""), False, fold_flags)

    status, values, revoked, ignored, unmatched, duplicates, standards = replay(
        tables, use_ledger, ledger_order, dedupe, strict_ledger, restore,
        strict_values, codepoint_ties, standard_mode, empty_entry_rule,
    )
    blocked = revoked if honour_revocation else set()

    voided = [sid for sid in status if status[sid] == "void"]
    quarantined = {sid: "unresolved_suspect" for sid in status if status[sid] == "suspect"}
    kept = {}

    walked = set()
    for row in tables["observations"]:
        sid = row["sample_id"]
        if sid in walked:
            continue
        walked.add(sid)
        if status[sid] != "observed":
            continue
        item = values[sid]
        count = whole_count(item["raw_count"], strict_values)
        when = sample_instant(item["epoch"], parse_epochs)
        if count is None or when is None:
            quarantined[sid] = "malformed_sample"
            continue
        token = label_key(item["channel_token"])
        structural = None
        if token.startswith("HLS") and token[3:].isdigit():
            structural = "HLS-" + token[3:].zfill(4)
        order = [aliases.get(token), structural] if alias_first else [structural, aliases.get(token)]
        channel_id = next((c for c in order if c), None)
        if channel_id is None or channel_id not in channels:
            quarantined[sid] = "unknown_channel"
            continue
        deployment = choose_interval(
            [d for d in tables["deployments"] if d["channel_id"] == channel_id],
            "valid_from", "valid_to", "deployment_id", when, temporal, parse_epochs,
        )
        if deployment is None or deployment["station_id"] not in stations:
            quarantined[sid] = "no_deployment"
            continue
        station = stations[deployment["station_id"]]
        holder = choose_interval(
            [c for c in tables["custody"] if c["station_id"] == station["station_id"]],
            "effective_from", "effective_to", "custody_id", when, temporal, parse_epochs,
        )
        if holder is None or holder["agency_id"] not in agencies:
            quarantined[sid] = "no_custody"
            continue
        agency = agencies[holder["agency_id"]]
        live = [
            cert for cert in certificates
            if cert["channel_id"] == channel_id
            and cert["certificate_id"] not in blocked
            and instant(cert["valid_from"], parse_epochs) <= when
            and not (
                honour_expiry
                and cert.get("valid_to", "") != ""
                and when > instant(cert["valid_to"], parse_epochs)
            )
        ]
        if not live:
            quarantined[sid] = "no_certificate"
            continue
        live.sort(key=lambda cert: (instant(cert["valid_from"], parse_epochs), cert["certificate_id"]))
        certificate = live[-1]
        factor = factors.get(unit_key(item["unit_token"]))
        if factor is None:
            quarantined[sid] = "unknown_unit"
            continue
        ppm = chain_ppm(standards, certificate["standard_id"], strict_cycles)
        if ppm is None:
            quarantined[sid] = "broken_ladder"
            continue
        kept[sid] = {
            "sample_id": sid,
            "channel_id": channel_id,
            "epoch": when,
            "canonical_nano": canonical_of(count, factor, arithmetic),
            "station_id": station["station_id"],
            "array_name": station["array_name"],
            "agency_id": agency["agency_id"],
            "segment": agency["operator_class"],
            "certificate_id": certificate["certificate_id"],
            "ladder_ppm": ppm,
            "is_provisional": provisional_flag(channels[channel_id]),
            "_station": station,
            "_cert": certificate,
            "standing_basis": flag_value(item["standing_basis"], True, fold_flags),
        }

    standing_custody = {
        row.get("array_channel_id", ""): row.get("custodian_channel_id", "")
        for row in tables["custody"] if row.get("array_channel_id", "")
    }
    qualifying = {channel_id: 0 for channel_id in channels}
    for entry in kept.values():
        if entry["standing_basis"] or not earned_standing:
            qualifying[entry["channel_id"]] += 1
    bands = sorted(
        thresholds.get("reporting_floor_bands", [
            {"reporting_arrays_at_least": 0, "minimum_qualifying_observations": 0}
        ]),
        key=lambda band: band["reporting_arrays_at_least"],
    )
    secondary = thresholds.get("custody_secondary_band", 0)
    reporting = set()
    reporting_round = {}
    turn = 0
    while True:
        turn += 1
        area_reporting = {}
        if earned_standing:
            for channel_id in reporting:
                area = channels[channel_id].get("reporting_area", "")
                area_reporting[area] = area_reporting.get(area, 0) + 1
        else:
            for row in channels.values():
                area = row.get("reporting_area", "")
                area_reporting[area] = area_reporting.get(area, 0) + 1
        additions = []
        for channel_id in sorted(channels):
            if channel_id in reporting:
                continue
            area = channels[channel_id].get("reporting_area", "")
            floor_count = bands[0]["minimum_qualifying_observations"]
            for band in bands:
                if area_reporting.get(area, 0) >= band["reporting_arrays_at_least"]:
                    floor_count = band["minimum_qualifying_observations"]
            direct = qualifying.get(channel_id, 0) >= floor_count
            inherited = (
                standing_custody.get(channel_id) in reporting
                and qualifying.get(channel_id, 0) >= secondary
            )
            if direct or inherited:
                additions.append(channel_id)
        if not additions:
            break
        for channel_id in additions:
            reporting.add(channel_id)
            reporting_round[channel_id] = turn

    standing_excluded = {}
    for sid in sorted(kept):
        entry = kept[sid]
        if not entry["standing_basis"] and entry["channel_id"] not in reporting:
            quarantined[sid] = "unreported_array"
            standing_excluded[sid] = entry["certificate_id"]
    kept = {sid: entry for sid, entry in kept.items() if sid not in standing_excluded}

    sources = {
        key: {"certificate": 0, "network": 0, "station": 0}
        for key in ("drift", "gain", "offset")
    }
    lookup = {
        "gain": ("gain_micro", "station_gain_micro", "network_gain_micro"),
        "offset": ("offset_nano", "station_offset_nano", "network_offset_nano"),
        "drift": (
            "drift_nano_per_sample",
            "station_drift_nano_per_sample",
            "network_drift_nano_per_sample",
        ),
    }
    for entry in kept.values():
        station_first = provisional and entry["is_provisional"]
        for name, (cert_key, station_key, policy_key) in lookup.items():
            options = [
                ("certificate", maybe_int(entry["_cert"].get(cert_key))),
                ("station", maybe_int(entry["_station"].get(station_key))),
            ]
            if station_first:
                options.reverse()
            options.append(("network", policy[policy_key]))
            for origin, candidate in options:
                if candidate is not None:
                    entry[name] = candidate
                    sources[name][origin] += 1
                    break

    runs = {}
    for entry in kept.values():
        key = entry["channel_id"] if not drift_reset else (entry["channel_id"], entry["certificate_id"])
        runs.setdefault(key, []).append(entry)
    for members in runs.values():
        members.sort(key=lambda item: (item["epoch"], item["sample_id"]) if drift_ties else (item["epoch"],))
        for position, entry in enumerate(members):
            entry["drift_index"] = position

    floor = policy["minimum_reported_nano"]
    for entry in kept.values():
        scaled = round_half_away(entry["canonical_nano"] * entry["gain"], MICRO, arithmetic)
        traced = round_half_away(scaled * (MICRO + entry["ladder_ppm"]), MICRO, arithmetic)
        drift = entry["drift_index"] * entry["drift"]
        corrected = traced - drift + entry["offset"]
        entry["traced_nano"] = traced
        entry["drift_nano"] = drift
        entry["reported_nano"] = max(floor, corrected) if apply_floor else corrected

    rows = [kept[sid] for sid in sorted(kept)]
    areas = list(thresholds["reported_arrays"])
    classes = list(thresholds["reported_segments"])
    gate = thresholds["variance_alert_nano"]
    budget = policy["uncertainty_budget_nano"]

    def blank(name, extras):
        shell = {
            "name": name,
            "accepted_count": 0,
            "canonical_nano": 0,
            "traced_nano": 0,
            "drift_nano": 0,
            "reported_nano": 0,
            "channel_totals": {},
        }
        shell.update({key: {} for key in extras})
        return shell

    def collect(shell, entry):
        shell["accepted_count"] += 1
        for key in ("canonical_nano", "traced_nano", "drift_nano", "reported_nano"):
            shell[key] += entry[key]
        chan = shell["channel_totals"]
        chan[entry["channel_id"]] = chan.get(entry["channel_id"], 0) + entry["reported_nano"]

    def tally(store, key, amount):
        store[key] = store.get(key, 0) + amount

    area_shell, class_shell = {}, {}
    array_counts, array_totals, segment_counts = {}, {}, {}
    station_totals, channel_totals = {}, {}
    grand = {"canonical_nano": 0, "traced_nano": 0, "drift_nano": 0, "reported_nano": 0}

    for entry in rows:
        one = area_shell.setdefault(
            entry["array_name"], blank(entry["array_name"], ("station_totals", "segment_counts"))
        )
        collect(one, entry)
        tally(one["station_totals"], entry["station_id"], entry["reported_nano"])
        tally(one["segment_counts"], entry["segment"], 1)
        two = class_shell.setdefault(
            entry["segment"], blank(entry["segment"], ("agency_totals", "array_counts"))
        )
        collect(two, entry)
        tally(two["agency_totals"], entry["agency_id"], entry["reported_nano"])
        tally(two["array_counts"], entry["array_name"], 1)
        tally(array_counts, entry["array_name"], 1)
        tally(array_totals, entry["array_name"], entry["reported_nano"])
        tally(segment_counts, entry["segment"], 1)
        tally(station_totals, entry["station_id"], entry["reported_nano"])
        tally(channel_totals, entry["channel_id"], entry["reported_nano"])
        for key in grand:
            grand[key] += entry[key]

    area_alloc = largest_remainder(budget, array_counts, areas, exact_apportion)
    class_alloc = largest_remainder(budget, segment_counts, classes, exact_apportion)

    def seal(shell, allocation):
        gap = shell["reported_nano"] - shell["canonical_nano"]
        shell["allocation_nano"] = allocation
        shell["alerts"] = (
            [{"delta_nano": gap, "name": shell["name"]}]
            if (abs(gap) >= gate if inclusive_gate else abs(gap) > gate) else []
        )
        return shell

    area_reports = {
        name: seal(
            area_shell.get(name) or blank(name, ("station_totals", "segment_counts")),
            area_alloc[name],
        )
        for name in areas
    }
    class_reports = {
        name: seal(
            class_shell.get(name) or blank(name, ("agency_totals", "array_counts")),
            class_alloc[name],
        )
        for name in classes
    }

    banner = []
    for name in sorted(areas):
        banner.extend(area_reports[name]["alerts"])

    top = None
    for entry in rows:
        rank = (-entry["reported_nano"], entry["sample_id"]) if largest_ties else (-entry["reported_nano"],)
        if top is None or rank < top[0] or (not largest_ties and rank == top[0]):
            top = (rank, entry["sample_id"], entry["reported_nano"])

    observed = len(tables["observations"])
    accepted = len(rows)
    held = len(quarantined) + duplicates

    summary = {
        "report_id": policy["report_id"],
        "observed_count": observed,
        "accepted_count": accepted,
        "voided_count": len(voided),
        "quarantined_count": held,
        "canonical_nano": grand["canonical_nano"],
        "traced_nano": grand["traced_nano"],
        "drift_nano": grand["drift_nano"],
        "reported_nano": grand["reported_nano"],
        "array_counts": array_counts,
        "array_totals": array_totals,
        "segment_counts": segment_counts,
        "station_totals": station_totals,
        "channel_totals": channel_totals,
        "largest_sample": {
            "reported_nano": top[2] if top else 0,
            "sample_id": top[1] if top else None,
        },
        "budget_nano": budget,
        "array_allocation_nano": area_alloc,
        "segment_allocation_nano": class_alloc,
        "alerts": banner,
    }

    used = sorted({entry["certificate_id"] for entry in rows})
    audit = {
        "report_id": policy["report_id"],
        "certificates_applied": used,
        "certificates_revoked": sorted(revoked),
        "certificates_unused": sorted(
            cert["certificate_id"] for cert in certificates
            if cert["certificate_id"] not in revoked and cert["certificate_id"] not in used
        ),
        "ladder_ppm_by_certificate": {
            entry["certificate_id"]: entry["ladder_ppm"] for entry in rows
        },
        "parameter_sources": sources,
        "provisional_channels": sorted(
            row["channel_id"] for row in tables["channel_registry"] if provisional_flag(row)
        ),
        "minimum_reported_nano": floor,
        "variance_alert_nano": gate,
        "budget_nano": budget,
        "reporting_arrays": sorted(reporting),
        "unreported_arrays": sorted(set(channels) - reporting),
        "reporting_round_by_array": {
            channel_id: reporting_round[channel_id] for channel_id in sorted(reporting_round)
        },
        "qualifying_observations_by_array": {
            channel_id: qualifying[channel_id] for channel_id in sorted(qualifying)
        },
        "reporting_array_count_by_area": {
            area: sum(
                1 for channel_id in reporting
                if channels[channel_id].get("reporting_area", "") == area
            )
            for area in sorted({row.get("reporting_area", "") for row in channels.values()})
        },
        "standing_exclusions_by_certificate": {
            sid: standing_excluded[sid] for sid in sorted(standing_excluded)
        },
    }

    reason_counts = {}
    for reason in quarantined.values():
        tally(reason_counts, reason, 1)
    if duplicates:
        tally(reason_counts, "duplicate_sample", duplicates)
    ratio = round_half_away(held * MICRO, observed) if observed else 0
    quality = {
        "input_file_count": tables["file_count"],
        "observed_count": observed,
        "accepted_count": accepted,
        "voided_count": len(voided),
        "quarantined_count": held,
        "conservation_ok": accepted + len(voided) + held == observed,
        "quarantine_reasons": {
            name: reason_counts[name] for name in REASON_ORDER if name in reason_counts
        },
        "ignored_amendments": ignored,
        "unmatched_amendments": unmatched,
        "orphan_alias_tokens": sorted(
            row["alias_token"] for row in tables["channel_aliases"]
            if row["channel_id"] not in channels
        ),
        "unreported_array_counts": {
            name: count for name, count in array_counts.items() if name not in areas
        },
        "quarantine_ratio_ppm": ratio,
        "quarantine_alert": ratio >= thresholds["quarantine_alert_ratio_ppm"],
    }

    bundle = {
        "summary.json": summary,
        "policy_audit.json": audit,
        "data_quality.json": quality,
    }
    for name in areas:
        bundle["region_" + name + ".json"] = area_reports[name]
    for name in classes:
        bundle["segment_" + name + ".json"] = class_reports[name]
    return bundle


# --------------------------------------------------------------------------
# Archive construction.
# --------------------------------------------------------------------------


def _materialise(root, files):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        target = root / name
        target.write_text(text, encoding="utf-8")
        try:
            os.chmod(target, 0o644)
        except OSError:
            pass
    try:
        os.chmod(root, 0o755)
    except OSError:
        pass
    return root


_VISIBLE_CACHE = []


def visible_inputs():
    if not _VISIBLE_CACHE:
        _VISIBLE_CACHE.append(
            _materialise(tempfile.mkdtemp(prefix="helios-visible-"), VISIBLE_FILES)
        )
    return _VISIBLE_CACHE[0]


_BASE = date(2031, 1, 1)
_UNIT_FORMS = {
    "nm/s^2": ["nm/s^2", "NM/S^2", "nm_s2", "Nm/S^2"],
    "um/s^2": ["um/s^2", "UM_S2", "um/S^2"],
    "uGal": ["uGal", "UGAL", "u-gal"],
    "microGal": ["microGal", "Micro-Gal", "MICROGAL"],
    "mGal": ["mGal", "MGAL", "m_gal"],
}


def _stamp(day_offset, rng):
    day = _BASE + timedelta(days=day_offset)
    return "%sT%02d:%02d:%02d" % (day.isoformat(), rng.below(24), rng.below(60), rng.below(60))


def _midnight(day_offset):
    return (_BASE + timedelta(days=day_offset)).isoformat() + "T00:00:00"


def _eod(day_offset):
    return (_BASE + timedelta(days=day_offset)).isoformat() + "T23:59:59"


def _maybe(rng, numerator, denominator, low, high):
    return str(rng.span(low, high)) if rng.flag(numerator, denominator) else ""


_RATIO_FORMS = ["nGal", "n-gal", "NGAL", "ft/s^2", "FT_S2", "gu", "GU"]


def _loosen(stamp, rng):
    """Respell a padded timestamp without leading zeros, keeping the same instant."""
    if not stamp:
        return stamp
    day, clock = stamp.split("T")
    year, month, dom = day.split("-")
    hour, minute, second = clock.split(":")
    return "%d-%d-%d%s%d:%s:%s" % (
        int(year), int(month), int(dom), rng.pick(["T", " "]), int(hour), minute, second,
    )


_DAMAGED_COUNTS = ["1_%d", "%d.0", "%de0", "0x%d", "", "\u0661\u0662", " +%d ", "-%d"]
_DAMAGED_EPOCHS = ["2031-04-05", "2031/04/05 10:00:00", "2031-04-05T10:00", "unknown"]


def _damage_count(rng):
    form = rng.pick(_DAMAGED_COUNTS)
    return form % rng.span(1, 900) if "%d" in form else form


def _recase(flag, rng):
    return rng.pick([flag, flag.upper(), flag.title()])


def _twist_case(rng, observations, deployments, custody, certificates, registry, ledger, doomed):
    """Overlay ratio units, loose timestamps, recased flags and ledger damage on a case."""
    for index, row in enumerate(observations):
        row = list(row)
        if rng.flag(1, 3):
            row[2] = _loosen(row[2], rng)
        if rng.flag(1, 3):
            row[6] = _recase(row[6], rng)
        elif rng.flag(1, 12):
            row[6] = ""
        if index >= 26 and rng.flag(1, 6):
            row[4] = rng.pick(_RATIO_FORMS)
        if index >= 31 and rng.flag(1, 10):
            row[3] = _damage_count(rng)
        elif index >= 31 and rng.flag(1, 25):
            row[2] = rng.pick(_DAMAGED_EPOCHS)
        observations[index] = tuple(row)
    for index, half in ((24, -1), (25, 1)):
        if index < len(observations):
            row = list(observations[index])
            row[3] = str(half * (100 * rng.span(0, 40) + 50))
            row[4] = rng.pick(["nGal", "n-gal", "NGAL"])
            observations[index] = tuple(row)
    for rows, start, end in ((deployments, 3, 4), (custody, 3, 4)):
        for index, row in enumerate(rows):
            row = list(row)
            if rng.flag(1, 3):
                row[start] = _loosen(row[start], rng)
            if rng.flag(1, 3):
                row[end] = _loosen(row[end], rng)
            rows[index] = tuple(row)
    for cert in certificates:
        if rng.flag(1, 3):
            cert["valid_from"] = _loosen(cert["valid_from"], rng)
        if cert["valid_to"] and rng.flag(1, 3):
            cert["valid_to"] = _loosen(cert["valid_to"], rng)
    for index, row in enumerate(registry):
        registry[index] = (row[0], row[1], _recase(row[2], rng), row[3])
    for entry in ledger:
        if "epoch" in entry and rng.flag(1, 2):
            entry["epoch"] = _loosen(entry["epoch"], rng)

    top = max(entry["sequence"] for entry in ledger) + 10
    sample_ids = [row[0] for row in observations]
    revoke_at = next(entry["sequence"] for entry in ledger if entry["entry_id"] == "LG-A")
    others = [cert["certificate_id"] for cert in certificates if cert is not doomed]
    target = rng.pick(others)
    struck = rng.span(1, top)
    extra = [
        {"entry_id": "LG-R1", "op": "restore_certificate",
         "certificate_id": doomed["certificate_id"], "sequence": revoke_at - 1},
        {"entry_id": "LG-R2", "op": "revoke_certificate", "certificate_id": target,
         "sequence": struck},
        {"entry_id": "LG-R3", "op": "restore_certificate", "certificate_id": target,
         "sequence": struck + 1},
        {"entry_id": "LG-S1", "op": "revise", "sample_id": rng.pick(sample_ids),
         "standing_basis": True, "sequence": rng.span(0, top)},
        {"entry_id": "LG-S2", "op": "revise", "sample_id": rng.pick(sample_ids),
         "standing_basis": False, "sequence": rng.span(0, top)},
    ]
    if rng.flag(1, 2):
        extra.append({"entry_id": "LG-R4", "op": "revoke_certificate", "certificate_id": target,
                      "sequence": struck + 3})
    # Malformed values written by revisions, and a late repair of a damaged row.
    extra.extend([
        {"entry_id": "LG-V1", "op": "revise", "sample_id": rng.pick(sample_ids),
         "raw_count": str(rng.span(1, 900)), "sequence": rng.span(0, top)},
        {"entry_id": "LG-V2", "op": "revise", "sample_id": rng.pick(sample_ids),
         "raw_count": float(rng.span(1, 900)), "sequence": rng.span(0, top)},
        {"entry_id": "LG-V4", "op": "revise", "sample_id": rng.pick(sample_ids),
         "epoch": rng.pick(_DAMAGED_EPOCHS), "sequence": rng.span(0, top)},
    ])
    if len(sample_ids) > 30:
        extra.append({"entry_id": "LG-V3", "op": "revise", "sample_id": sample_ids[30],
                      "raw_count": rng.span(-900, 900), "sequence": top + 5})
    # Tied sequences whose identifiers order differently by code point than by
    # natural or case-folded reading. The lower-case twin is filed first.
    tied = rng.pick(sample_ids)
    twin = rng.pick(sample_ids)
    first = rng.span(1, 900)
    extra.extend([
        {"entry_id": "LG-T10", "op": "reinstate", "sample_id": tied, "sequence": top + 7},
        {"entry_id": "LG-T9", "op": "void", "sample_id": tied, "sequence": top + 7},
        {"entry_id": "lg-c5", "op": "revise", "sample_id": twin, "raw_count": first,
         "sequence": top + 8},
        {"entry_id": "LG-C5", "op": "revise", "sample_id": twin, "raw_count": first + 37,
         "sequence": top + 8},
    ])
    lines = [json.dumps(entry, sort_keys=True) for entry in ledger + extra]
    damaged = [
        json.dumps({"entry_id": "LG-R3", "op": "restore_certificate", "certificate_id": target,
                    "sequence": float(max(struck - 5, 0))}, sort_keys=True),
        json.dumps({"entry_id": "LG-M2", "op": "void", "sample_id": rng.pick(sample_ids),
                    "sequence": str(rng.span(0, top))}, sort_keys=True),
        json.dumps({"entry_id": "LG-M3", "op": "certify", "sample_id": rng.pick(sample_ids),
                    "sequence": True}, sort_keys=True),
        '{"entry_id": "LG-M4", "op": "void", "sample_id": "%s' % rng.pick(sample_ids)[:4],
        json.dumps(["LG-M5", rng.span(0, top), "void", rng.pick(sample_ids)]),
    ]
    for line in damaged:
        lines.insert(rng.below(len(lines) + 1), line)
    return lines


def build_case(seed, sample_count, huge=False, cyclic=False, restandard=False, edges=()):
    """Build an unseen archive that exercises the whole contract."""
    rng = Rng(seed)
    arrays = ["East", "North", "South", "West", "Central", "North"]
    station_rows = []
    for index, array in enumerate(arrays):
        station_rows.append({
            "station_id": "ST-%02d" % (index + 1),
            "array_name": array,
            "gain": _maybe(rng, 1, 2, 995000, 1005000),
            "offset": _maybe(rng, 1, 2, -90, 90),
            "drift": _maybe(rng, 1, 2, 0, 55),
        })
    agency_rows = [
        ("AG-A1", "Alpha Geodesy, Ltd", "commercial"),
        ("AG-B2", "Basin Survey Office", "public"),
        ("AG-C3", "Cirrus Metrology", "commercial"),
        ("AG-D4", "Delta Civic Trust", "public"),
    ]
    custody_rows = []
    counter = 0
    for station in station_rows:
        start = rng.span(0, 14)
        counter += 1
        first = "CU-%02d" % counter
        if rng.flag(1, 2):
            cut = rng.span(80, 150)
            custody_rows.append((first, station["station_id"], rng.pick(agency_rows)[0],
                                 _midnight(start), _eod(cut)))
            counter += 1
            custody_rows.append(("CU-%02d" % counter, station["station_id"],
                                 rng.pick(agency_rows)[0], _midnight(cut - rng.below(12)), ""))
        else:
            custody_rows.append((first, station["station_id"], rng.pick(agency_rows)[0],
                                 _midnight(start), ""))

    channel_ids = []
    while len(channel_ids) < 6:
        candidate = "HLS-%04d" % rng.span(1, 900)
        if candidate not in channel_ids:
            channel_ids.append(candidate)
    channel_ids.sort()
    home_areas = ["East", "North", "South", "West", "Central", "North"]
    registry_rows = [
        (
            cid,
            rng.pick(["GRV-1", "GRV-2", "GRV-3"]),
            "true" if rng.flag(1, 3) else "false",
            home_areas[position % len(home_areas)],
        )
        for position, cid in enumerate(channel_ids)
    ]
    standing_links = [
        ("SC-01", channel_ids[1], channel_ids[0]),
        ("SC-02", channel_ids[3], channel_ids[1]),
        ("SC-03", channel_ids[5], channel_ids[3]),
    ]

    alias_rows = [
        ("RIDGEPOINT-%d" % rng.span(1, 9), channel_ids[0]),
        ("CAVERN-%d" % rng.span(1, 9), channel_ids[2]),
        ("HLS-%d" % rng.span(901, 990), channel_ids[4]),
        ("RETIRED-%d" % rng.span(1, 9), "HLS-9999"),
    ]

    standard_rows = [("STD-P", "", "0")]
    for index, name in enumerate(["STD-Q", "STD-R", "STD-S", "STD-T"]):
        parent = "STD-P" if index < 2 else standard_rows[rng.span(1, len(standard_rows) - 1)][0]
        standard_rows.append((name, parent, str(rng.span(-260, 260))))
    standard_names = [row[0] for row in standard_rows[1:]]

    cert_rows = []
    for cid in channel_ids:
        for slot in range(2):
            standard = "STD-MISSING" if rng.flag(1, 9) else rng.pick(standard_names)
            cert_rows.append({
                "certificate_id": "CT-%s-%d" % (cid[-4:], slot + 1),
                "channel_id": cid,
                "valid_from": _midnight(rng.span(0, 22) + slot * 95),
                "valid_to": (
                    _eod(rng.span(60, 150)) if slot == 0 and rng.flag(1, 3)
                    else _eod(rng.span(170, 225)) if slot == 1 and rng.flag(1, 5)
                    else ""
                ),
                "gain": _maybe(rng, 2, 3, 994000, 1006000),
                "offset": _maybe(rng, 2, 3, -60, 60),
                "drift": _maybe(rng, 2, 3, 0, 30),
                "standard_id": standard,
            })

    deployment_rows = []
    counter = 0
    for cid in channel_ids:
        start = rng.span(0, 12)
        counter += 1
        if rng.flag(1, 2):
            cut = rng.span(95, 165)
            deployment_rows.append(("DP-%02d" % counter, cid,
                                    rng.pick(station_rows)["station_id"],
                                    _midnight(start), _eod(cut)))
            counter += 1
            deployment_rows.append(("DP-%02d" % counter, cid,
                                    rng.pick(station_rows)["station_id"],
                                    _midnight(cut - rng.below(15)),
                                    "" if rng.flag(5, 6) else _eod(rng.span(215, 250))))
        else:
            deployment_rows.append(("DP-%02d" % counter, cid,
                                    rng.pick(station_rows)["station_id"],
                                    _midnight(start), ""))

    unit_names = list(_UNIT_FORMS)
    observation_rows = []
    for index in range(sample_count):
        sid = "OB-%03d" % (index + 1)
        pick = rng.below(10)
        if pick == 0:
            token = rng.pick([row[0] for row in alias_rows])
        elif pick == 1:
            token = "NOSUCH-%d" % rng.span(1, 40)
        else:
            base = rng.pick(channel_ids)
            digits = base[4:]
            token = rng.pick([
                base, base.lower(), "hls_" + str(int(digits)), "HLS" + digits,
                "HLS-" + str(int(digits)), "hls-" + digits,
            ])
        unit = "pGal" if rng.flag(1, 14) else rng.pick(_UNIT_FORMS[rng.pick(unit_names)])
        magnitude = rng.pick([rng.span(1, 40), rng.span(50, 9000), rng.span(100, 9999)])
        raw = -magnitude if rng.flag(1, 4) else magnitude
        state = "observed"
        if rng.flag(1, 8):
            state = "suspect"
        elif rng.flag(1, 12):
            state = "void"
        basis = "false" if rng.flag(1, 3) else "true"
        observation_rows.append(
            (sid, token, _stamp(rng.span(0, 230), rng), str(raw), unit, state, basis)
        )

    def _reshape(position, column, value):
        row = list(observation_rows[position])
        row[column] = value
        observation_rows[position] = tuple(row)

    # Guarantee that every probe archive exercises the branches the contract turns on.
    shadow_channel = alias_rows[2][1]
    late_certs = sorted(
        (c for c in cert_rows if sum(1 for o in cert_rows if o["channel_id"] == c["channel_id"]) > 1),
        key=lambda c: (c["channel_id"], c["valid_from"]),
    )
    doomed = late_certs[-1] if late_certs else cert_rows[-1]
    early_cert = min(cert_rows, key=lambda c: (c["valid_from"], c["certificate_id"]))
    _reshape(3, 1, alias_rows[2][0])
    _reshape(4, 1, alias_rows[2][0])
    _reshape(7, 1, alias_rows[3][0])
    _reshape(11, 5, "suspect")
    _reshape(12, 5, "void")
    _reshape(13, 4, "pGal")
    _reshape(14, 1, doomed["channel_id"])
    _reshape(14, 2, _midnight(rng.span(200, 240)))
    _reshape(15, 1, doomed["channel_id"])
    _reshape(15, 2, doomed["valid_from"].replace("T00:00:00", "T12:00:00"))
    _reshape(16, 1, early_cert["channel_id"])
    _reshape(16, 2, _midnight(0))
    _reshape(17, 1, shadow_channel)
    straddler = min(cert_rows, key=lambda c: (c["channel_id"], c["valid_from"]))["channel_id"]
    crossing = max(
        c["valid_from"] for c in cert_rows if c["channel_id"] == straddler
    )
    for step, day in enumerate((30, 60, 0, 0, 0, 0)):
        slot = 18 + step
        _reshape(slot, 1, straddler)
        _reshape(slot, 4, "nm/s^2")
        _reshape(slot, 5, "observed")
        if step < 2:
            _reshape(slot, 2, _midnight(day))
        else:
            _reshape(slot, 2, crossing.replace("T00:00:00", "T0%d:30:00" % (step - 1)))
    if sample_count > 30:
        # An expiring certificate with samples on and after its inclusive last instant.
        expiring = next(c for c in cert_rows if c["channel_id"] == channel_ids[2])
        expiring["valid_to"] = _eod(70)
        for slot, stamp in ((26, _midnight(80)), (27, _eod(70))):
            _reshape(slot, 1, channel_ids[2])
            _reshape(slot, 2, stamp)
            _reshape(slot, 4, "nm/s^2")
            _reshape(slot, 5, "observed")
        # Raw counts outside the contract's whole number form, one of them repaired later.
        for slot, raw in ((28, "1_%03d" % rng.span(0, 999)), (29, "%d.0" % rng.span(1, 900)),
                          (30, "x%d" % rng.span(1, 900))):
            _reshape(slot, 1, channel_ids[0])
            _reshape(slot, 3, raw)
            _reshape(slot, 4, "nm/s^2")
            _reshape(slot, 5, "observed")

    ledger = []
    ids = [row[0] for row in observation_rows]
    cert_ids = [row["certificate_id"] for row in cert_rows]
    ledger.append({"entry_id": "LG-A", "op": "revoke_certificate",
                   "certificate_id": doomed["certificate_id"]})
    ledger.append({"entry_id": "LG-B", "op": "certify", "sample_id": observation_rows[11][0]})
    ledger.append({"entry_id": "LG-C", "op": "reinstate", "sample_id": observation_rows[12][0]})
    ledger.append({"entry_id": "LG-D", "op": "revise", "sample_id": observation_rows[6][0],
                   "epoch": _midnight(rng.span(150, 220))})
    ledger.append({"entry_id": "LG-E", "op": "revise", "sample_id": observation_rows[8][0],
                   "channel_token": rng.pick(channel_ids)})
    ledger.append({"entry_id": "LG-F", "op": "void", "sample_id": observation_rows[9][0]})
    ledger.append({"entry_id": "LG-G", "op": "revise", "sample_id": observation_rows[9][0],
                   "raw_count": 12345})
    for index in range(max(6, sample_count // 3)):
        kind = rng.below(12)
        target = rng.pick(ids)
        if kind == 0:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "revoke_certificate",
                           "certificate_id": rng.pick(cert_ids)})
        elif kind == 1:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "revise",
                           "sample_id": "OB-999", "raw_count": 7})
        elif kind in (2, 3):
            ledger.append({"entry_id": "LG-%02d" % index, "op": "void", "sample_id": target})
        elif kind == 4:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "reinstate", "sample_id": target})
        elif kind in (5, 6):
            ledger.append({"entry_id": "LG-%02d" % index, "op": "certify", "sample_id": target})
        elif kind == 7:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "revise", "sample_id": target,
                           "epoch": _stamp(rng.span(0, 230), rng)})
        elif kind == 8:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "revise", "sample_id": target,
                           "channel_token": rng.pick(channel_ids)})
        elif kind == 9:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "revise", "sample_id": target,
                           "unit_token": rng.pick(_UNIT_FORMS[rng.pick(unit_names)])})
        else:
            ledger.append({"entry_id": "LG-%02d" % index, "op": "revise", "sample_id": target,
                           "raw_count": rng.span(-9000, 9000)})

    observation_rows.append(observation_rows[2])
    observation_rows.append(observation_rows[18])
    observation_rows.append(observation_rows[11])

    contested = observation_rows[5][0]
    ledger.append({"entry_id": "LG-X1", "op": "void", "sample_id": contested})
    ledger.append({"entry_id": "LG-X2", "op": "reinstate", "sample_id": contested})

    shuffle = list(range(len(ledger)))
    for position in range(len(shuffle) - 1, 0, -1):
        swap = rng.below(position + 1)
        shuffle[position], shuffle[swap] = shuffle[swap], shuffle[position]
    for position, entry in enumerate(ledger):
        entry["sequence"] = (shuffle[position] // 2) * 2
    ledger[-1]["sequence"] = len(ledger) * 2 + 2
    ledger[-2]["sequence"] = len(ledger) * 2 + 4
    ledger.append(dict(ledger[0], sequence=len(ledger) * 2 + 6))
    ledger_lines = _twist_case(
        Rng(seed ^ 0x5EED5EED), observation_rows, deployment_rows, custody_rows, cert_rows,
        registry_rows, ledger, doomed,
    )
    if cyclic:
        # A traceability ladder that loops back on itself, entered from a tail link and
        # selected by the certificate that retroactive revocation falls back to.
        loop = Rng(seed ^ 0xC1C1E5)
        standard_rows.extend([
            ("STD-U", "STD-V", str(loop.span(-260, 260))),
            ("STD-V", "STD-U", str(loop.span(-260, 260))),
            ("STD-W", "STD-W", str(loop.span(-260, 260))),
            ("STD-Y", "STD-U", str(loop.span(-260, 260))),
        ])
        for cert in cert_rows:
            if cert["channel_id"] == doomed["channel_id"] and cert is not doomed:
                cert["standard_id"] = "STD-Y"
        loop.pick([c for c in cert_rows if c["channel_id"] != doomed["channel_id"]])[
            "standard_id"] = "STD-W"
    if restandard:
        # Ledger revisions of the traceability standards, filed out of ledger order: a
        # reparent pair that closes a loop only when replayed by sequence, code point ties,
        # a standard turned primary, malformed and empty revisions, an unknown standard and
        # a replayed entry identifier that must not post twice.
        shift = Rng(seed ^ 0x57A4D)
        first_ratio = shift.span(-300, 300)
        revisions = [
            {"entry_id": "LG-Q4", "standard_id": "STD-R", "parent_standard_id": "STD-T",
             "sequence": 5005},
            {"entry_id": "LG-Q3", "standard_id": "STD-T", "parent_standard_id": "STD-R",
             "sequence": 5006},
            {"entry_id": "LG-Q9", "standard_id": "STD-Q", "ratio_ppm": first_ratio,
             "sequence": 5010},
            {"entry_id": "LG-Q10", "standard_id": "STD-Q",
             "ratio_ppm": first_ratio + shift.span(1, 200), "sequence": 5010},
            {"entry_id": "LG-Q15", "standard_id": "STD-S", "parent_standard_id": "",
             "ratio_ppm": shift.span(-300, 300), "sequence": 5015},
            {"entry_id": "LG-Q11", "standard_id": "STD-Q",
             "ratio_ppm": str(shift.span(-300, 300)), "sequence": 5011},
            {"entry_id": "LG-Q12", "standard_id": "STD-Q", "parent_standard_id": None,
             "sequence": 5012},
            {"entry_id": "LG-Q13", "standard_id": "STD-NOPE", "ratio_ppm": 9, "sequence": 5013},
            {"entry_id": "LG-Q14", "standard_id": "STD-Q", "sequence": 5014},
            {"entry_id": "LG-Q5", "standard_id": "STD-R", "parent_standard_id": "STD-P",
             "ratio_ppm": shift.span(-300, 300), "sequence": 5004},
            {"entry_id": "LG-Q4", "standard_id": "STD-R", "parent_standard_id": "STD-P",
             "sequence": 5100},
        ]
        if cyclic:
            revisions.append({"entry_id": "LG-Q6", "standard_id": "STD-W",
                              "parent_standard_id": "STD-Q", "sequence": 5020})
        for entry in revisions:
            entry["op"] = "revise_standard"
            ledger_lines.append(json.dumps(entry, sort_keys=True))
    if huge:
        # Widen every well formed count far beyond binary double and default 28 digit
        # decimal precision, keeping its sign, and turn ratio unit rows into exact halves.
        wide = Rng(seed ^ 0xB16B0055)
        for position, row in enumerate(observation_rows):
            written = row[3].strip()
            if not _WHOLE.match(written):
                continue
            digits = wide.span(29, 44)
            magnitude = wide.span(10 ** (digits - 1), 10 ** digits - 1)
            if unit_key(row[4]) == "ngal":
                magnitude = magnitude // 100 * 100 + 50
            sign = "-" if written.startswith("-") else wide.pick(["", "+"])
            _reshape(position, 3, "%s%d" % (sign, magnitude))

    files = {
        "contract.md": VISIBLE_FILES["contract.md"],
        "policy.json": json.dumps({
            "report_id": "HELIOS-CASE-%d" % (seed % 100000),
            "canonical_unit": "nm/s^2",
            "network_gain_micro": rng.span(996000, 1004000),
            "network_offset_nano": rng.span(-70, 70),
            "network_drift_nano_per_sample": rng.span(0, 30),
            "minimum_reported_nano": -rng.span(200, 1500),
            "uncertainty_budget_nano": 9007199254740993 + rng.span(0, 4000000),
        }, indent=2, sort_keys=True) + "\n",
        "thresholds.json": json.dumps({
            "reported_arrays": AREA_NAMES,
            "reported_segments": CLASS_NAMES,
            "reporting_floor_bands": [
                {"reporting_arrays_at_least": 0, "minimum_qualifying_observations": 4},
                {"reporting_arrays_at_least": 1, "minimum_qualifying_observations": 3},
                {"reporting_arrays_at_least": 2, "minimum_qualifying_observations": 2},
            ],
            "custody_secondary_band": 2,
            "variance_alert_nano": rng.span(100000, 3000000),
            "quarantine_alert_ratio_ppm": rng.span(100000, 400000),
        }, indent=2, sort_keys=True) + "\n",
        "units.csv": VISIBLE_FILES["units.csv"],
        "channel_registry.csv": "channel_id,model,provisional,reporting_area\n" + "".join(
            "%s,%s,%s,%s\n" % row for row in registry_rows
        ),
        "channel_aliases.csv": "alias_token,channel_id\n" + "".join(
            "%s,%s\n" % row for row in alias_rows
        ),
        "stations.csv": (
            "station_id,array_name,station_gain_micro,station_offset_nano,"
            "station_drift_nano_per_sample\n"
        ) + "".join(
            "%s,%s,%s,%s,%s\n" % (r["station_id"], r["array_name"], r["gain"], r["offset"], r["drift"])
            for r in station_rows
        ),
        "deployments.csv": "deployment_id,channel_id,station_id,valid_from,valid_to\n" + "".join(
            "%s,%s,%s,%s,%s\n" % row for row in deployment_rows
        ),
        "agencies.csv": "agency_id,agency_name,operator_class\n" + "".join(
            '%s,"%s",%s\n' % row for row in agency_rows
        ),
        "custody.csv": (
            "custody_id,station_id,agency_id,effective_from,effective_to,"
            "array_channel_id,custodian_channel_id\n"
        ) + "".join(
            "%s,%s,%s,%s,%s,,\n" % row for row in custody_rows
        ) + "".join(
            "%s,,,,,%s,%s\n" % row for row in standing_links
        ),
        "standards.csv": "standard_id,parent_standard_id,ratio_ppm\n" + "".join(
            "%s,%s,%s\n" % row for row in standard_rows
        ),
        "certificates.csv": (
            "certificate_id,channel_id,valid_from,valid_to,gain_micro,offset_nano,"
            "drift_nano_per_sample,standard_id\n"
        ) + "".join(
            "%s,%s,%s,%s,%s,%s,%s,%s\n" % (
                c["certificate_id"], c["channel_id"], c["valid_from"], c["valid_to"], c["gain"],
                c["offset"], c["drift"], c["standard_id"],
            ) for c in cert_rows
        ),
        "observations.csv": (
            "sample_id,channel_token,epoch,raw_count,unit_token,status,standing_basis\n"
        ) + "".join(
            "%s,%s,%s,%s,%s,%s,%s\n" % row for row in observation_rows
        ),
        "amendments.jsonl": "".join(line + "\n" for line in ledger_lines),
    }
    return _contract_edges(files, huge, edges) if edges else files


def _contract_edges(files, huge, edges):
    """Add the fixture for each named contract tie break or boundary random rows rarely meet.

    `drift_tie` gives a dedicated North channel two baseline rows sharing an epoch inside
    one drift run; `largest_tie` gives it two rows tied for the largest reported value;
    `empty_entry` gives it a row that a ledger line with an empty entry identifier tries to
    void; `zero_numerator` adds a unit whose ratio has a zero numerator and a row in it;
    `alert_gate` moves the variance gate onto one roster area's exact gap. The dedicated
    channel's certificates trace to a primary standard whose own ratio is nonzero.
    """
    files = dict(files)
    floor = json.loads(files["policy.json"])["minimum_reported_nano"]
    top = 10 ** 60 if huge else 10 ** 14
    edge_rows = []
    if "drift_tie" in edges:
        edge_rows += [
            ("OB-T2", _BASE + timedelta(days=150), floor + 20, "nm/s^2"),
            ("OB-T1", _BASE + timedelta(days=150), floor + 5, "nm/s^2"),
        ]
    if "largest_tie" in edges:
        edge_rows += [
            ("OB-U2", _BASE + timedelta(days=220), top, "nm/s^2"),
            ("OB-U1", _BASE + timedelta(days=220), top, "nm/s^2"),
        ]
    if "empty_entry" in edges:
        edge_rows.append(("OB-V1", _BASE + timedelta(days=160), 1000, "nm/s^2"))
        files["amendments.jsonl"] += json.dumps(
            {"entry_id": "", "op": "void", "sample_id": "OB-V1", "sequence": 3}, sort_keys=True
        ) + "\n"
    if "zero_numerator" in edges:
        files["units.csv"] += "eGal, 0 / 7\n"
        edge_rows.append(("OB-W1", _BASE + timedelta(days=170), 4000, "eGal"))
    if edge_rows:
        files["standards.csv"] += "STD-EDGE,,250\n"
        files["channel_registry.csv"] += "HLS-0997,GRV-9,false,Spare\n"
        files["deployments.csv"] += "DP-997,HLS-0997,ST-02,%s,\n" % _midnight(0)
        files["certificates.csv"] += (
            "CT-0997-1,HLS-0997,%s,,1000000,0,11,STD-EDGE\n" % _midnight(0)
            + "CT-0997-2,HLS-0997,%s,,1000000,0,0,STD-EDGE\n" % _midnight(210)
        )
        files["observations.csv"] += "".join(
            "%s,HLS-0997,%sT12:00:00,%d,%s,observed,true\n" % (sid, day.isoformat(), count, unit)
            for sid, day, count, unit in edge_rows
        )
    if "alert_gate" in edges:
        thresholds = json.loads(files["thresholds.json"])
        with tempfile.TemporaryDirectory(prefix="helios-edge-") as scratch:
            reports = derive(_materialise(Path(scratch) / "data", files))
        gaps = sorted(set(
            abs(reports["region_%s.json" % name]["reported_nano"]
                - reports["region_%s.json" % name]["canonical_nano"])
            for name in thresholds["reported_arrays"]
        ) - {0})
        if gaps:
            wanted = thresholds["variance_alert_nano"]
            thresholds["variance_alert_nano"] = min(gaps, key=lambda gap: (abs(gap - wanted), gap))
            files["thresholds.json"] = json.dumps(thresholds, indent=2, sort_keys=True) + "\n"
    return files


def write_case(root, seed, sample_count, **overlays):
    return _materialise(root, build_case(seed, sample_count, **overlays))


# --------------------------------------------------------------------------
# Execution helpers.
# --------------------------------------------------------------------------


def _grading_uid():
    """Pick a fresh unprivileged uid for one program run, shared with no other check."""
    return 200000 + int.from_bytes(os.urandom(3), "big") % 800000


def _untrusted_command(command, uid):
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0:
        return [_SETPRIV[0], "--reuid=%d" % uid] + _SETPRIV[2:] + command
    return command


def _relax(path):
    """Open an output location so the unprivileged program can replace what it holds."""
    for item in Path(path).rglob("*"):
        try:
            os.chmod(item, 0o777 if item.is_dir() else 0o666)
        except OSError:
            pass
    try:
        os.chmod(path, 0o777)
    except OSError:
        pass


def _seal(room):
    """Leave a scratch room traversable but every archive under it read only.

    The unprivileged program may read the archive and write only its output location,
    so the expected reports derived from the archive afterwards see the bytes as built.
    """
    room = Path(room)
    for item in sorted(room.rglob("*"), key=lambda one: len(one.parts), reverse=True):
        if item.is_symlink() or item.parent.name == "out" or item.name == "out":
            continue
        try:
            os.chmod(item, 0o555 if item.is_dir() else 0o444)
        except OSError:
            pass
    try:
        os.chmod(room, 0o755)
    except OSError:
        pass


def _uids_of(entry):
    try:
        with open("/proc/%s/status" % entry, encoding="ascii", errors="replace") as handle:
            for line in handle:
                if line.startswith("Uid:"):
                    return {int(part) for part in line.split()[1:]}
    except (OSError, ValueError):
        pass
    return set()


def _sweep_uid(uid):
    """Kill every process still running under the uid one program run was given."""
    for _ in range(5):
        hits = 0
        for entry in os.listdir("/proc"):
            if entry.isdigit() and uid in _uids_of(entry):
                try:
                    os.kill(int(entry), signal.SIGKILL)
                    hits += 1
                except OSError:
                    pass
        if not hits:
            return


def _reap(proc, uid):
    """Kill the program and every descendant it left behind, after every run.

    Under the verifier each run owns a fresh uid, so every process carrying that uid
    is killed even after the leader exits or a child leaves the session, and a daemon
    left behind can never rewrite an archive or a report after the check.
    """
    privileged = os.name == "posix" and os.geteuid() == 0 and Path("/proc").is_dir()
    if privileged:
        _sweep_uid(uid)
    elif proc.poll() is None:
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        pass


def run_script_raw(data_dir, out_dir, create=True):
    """Run the agent's reusable program over an archive and return the bytes it wrote.

    With create=False the output location is left absent so the program has to make it,
    parents included, as the instruction requires.
    """
    _need(_script().is_file(), "no reusable derivation program at %s" % _script())
    # an agent editor writes through a temp file and renames it, so the program
    # can land at mode 0600 and the unprivileged child cannot open it; the
    # verifier runs as root, so grant read on the program and its parent
    try:
        _script().parent.chmod(0o755)
        _script().chmod(0o644)
    except OSError:
        pass
    out_dir = Path(out_dir)
    if create:
        out_dir.mkdir(parents=True, exist_ok=True)
        _relax(out_dir)
    else:
        _need(not out_dir.exists(), "the absent output location already exists")
    options = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "posix":
        options["start_new_session"] = True
    uid = _grading_uid()
    proc = subprocess.Popen(
        _untrusted_command([sys.executable, str(_script()), str(data_dir), str(out_dir)], uid),
        **options
    )
    try:
        code = proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        _reap(proc, uid)
        raise AssertionError("derivation program did not finish within the grading window")
    finally:
        _reap(proc, uid)
    _need(code == 0, "derivation program exited with status %d" % code)
    thresholds = json.loads((Path(data_dir) / "thresholds.json").read_text(encoding="utf-8"))
    artifact_names = (
        ["summary.json", "policy_audit.json", "data_quality.json"]
        + ["region_%s.json" % name for name in thresholds["reported_arrays"]]
        + ["segment_%s.json" % name for name in thresholds["reported_segments"]]
    )
    produced = {}
    for name in artifact_names:
        target = out_dir / name
        _need(target.is_file(), "derivation program did not write %s" % name)
        produced[name] = target.read_text(encoding="utf-8")
    return produced


def run_script(data_dir, out_dir, create=True):
    """Run the agent's reusable program over an archive and load what it wrote."""
    raw = run_script_raw(data_dir, out_dir, create)
    return dict((name, json.loads(text)) for name, text in raw.items())


def case_run(seed, sample_count, prefix="helios-case-", **overlays):
    """Build an unseen archive, run the agent program on it, return (actual, reference)."""
    room = tempfile.mkdtemp(prefix=prefix)
    data_dir = write_case(Path(room) / "data", seed, sample_count, **overlays)
    _seal(room)
    produced = run_script(data_dir, Path(room) / "out")
    return produced, data_dir


def actual(name):
    target = _out() / name
    _need(target.is_file(), "missing artefact %s" % name)
    return json.loads(target.read_text(encoding="utf-8"))


def actual_bundle():
    """Load every report so global checks cannot pass on a truncated partition set."""
    return {name: actual(name) for name in ARTIFACT_NAMES}


def _py_source_text():
    chunks = []
    for path in sorted(_out().glob("*.py")):
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return "\n".join(chunks)


def _source_text():
    chunks = [_py_source_text()]
    for name in ARTIFACT_NAMES:
        target = _out() / name
        if target.is_file():
            try:
                chunks.append(target.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return "\n".join(chunks)


def _strict(left, right):
    """Compare two decoded JSON values so that a bool never satisfies an int and back."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_strict(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(_strict(one, two) for one, two in zip(left, right))
    if type(left) is not type(right):
        return False
    return left == right


def _same(left, right, label):
    _need(_strict(left, right), "%s does not match the reference derivation" % label)


# Archive inventory facts that no probe rule touches. The shipped-archive checks and the
# regeneration check grade them; the probes leave them out so one inventory slip costs
# about one fact rather than every probe that happens to read the same report.
INVENTORY_KEYS = {"data_quality.json": ("input_file_count", "orphan_alias_tokens")}


# Standing facts: the keys the earned standing closure decides. The fixpoint probes grade
# only these, so a slip in an unrelated money rule is charged by its own checks.
STANDING_FACTS = {
    "policy_audit.json": (
        "reporting_arrays", "unreported_arrays", "reporting_round_by_array",
        "qualifying_observations_by_array", "reporting_array_count_by_area",
        "standing_exclusions_by_certificate",
    ),
    "data_quality.json": (
        "accepted_count", "quarantined_count", "quarantine_reasons", "unreported_array_counts",
    ),
}


def _moved_keys(expected, contrasts, name, only=None):
    """Top level keys of one report that the probe's rule moves away from a contrast."""
    skip = INVENTORY_KEYS.get(name, ())
    moved = []
    for key, value in expected[name].items():
        if key in skip:
            continue
        if only is not None and key not in only.get(name, ()):
            continue
        if any(not _strict(value, contrast[name].get(key)) for contrast in contrasts):
            moved.append(key)
    return moved


def _focused_same(produced, expected, contrasts, names, label, only=None):
    """Grade only the facts a probe moves, so one unrelated slip costs about one fact.

    Each probe exists to exercise one rule. The keys it grades are the ones whose value
    under the full derivation differs from the value under at least one contrast
    derivation (a misreading of that rule, or the archive before the mutation). Facts the
    probe leaves untouched are graded by the shipped-archive checks instead.
    """
    graded = 0
    for name in names:
        report = produced.get(name)
        _need(isinstance(report, dict), "%s is not a report object" % name)
        for key in _moved_keys(expected, contrasts, name, only):
            _need(key in report, "%s lacks %s" % (name, key))
            _same(report[key], expected[name][key], "%s %s %s" % (label, name, key))
            graded += 1
    _need(graded > 0, "the %s probe moves no graded fact" % label)
    return True


def _slice(report, keys):
    return dict((key, report.get(key)) for key in keys)



def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _program_strings():
    """Collect the non-docstring string literals of the program."""
    source = _py_source_text()
    if not source.strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [source]
    prose = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                prose.add(doc)
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value not in prose]


def _program_facts():
    """Collect literals, imports and attribute paths from the program, ignoring commentary."""
    source = _py_source_text()
    facts = []
    if not source.strip():
        return facts
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [source]
    prose = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                prose.add(doc)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                if node.value not in prose:
                    facts.append(node.value)
            elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                facts.append(repr(node.value))
        elif isinstance(node, ast.Import):
            facts.extend("import " + alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            facts.append("import " + (node.module or ""))
        elif isinstance(node, ast.Attribute):
            facts.append(_dotted(node))
        elif isinstance(node, ast.Name):
            facts.append(node.id)
    return facts


def _foreign_imports():
    """Return the import roots the program uses that the standard library does not provide."""
    source = _py_source_text()
    if not source.strip():
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if getattr(node.func, "id", "") == "__import__" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    roots.add(first.value.split(".")[0])
    known = set(getattr(sys, "stdlib_module_names", ()))
    return set(name for name in roots if name and name not in known)


def _fact_hits(probes, extra=()):
    """Count probes that appear in the program's own code, plus any extra text supplied."""
    facts = _program_facts()
    facts.extend(extra)
    return [probe for probe in probes if any(probe in fact for fact in facts)]


# Figures that belong to the shipped archive's answers alone. A program that derives
# its answers never needs to write them; one that carries the answers does. This looks
# for carried figures only; it does not detect branching on shipped identifiers.
SHIPPED_ANSWER_MARKS = (
    "304719443", "305124596", "50871", "35244", "31946",
)


def _answers_embedded_in_source():
    """True when the program's own literals carry answers lifted from the shipped archive."""
    return len(_fact_hits(SHIPPED_ANSWER_MARKS)) >= 3

# --------------------------------------------------------------------------
# Shared probe helpers.
# --------------------------------------------------------------------------


_CALIBRATION_CACHE = []


def calibration_run():
    if not _CALIBRATION_CACHE:
        room = tempfile.mkdtemp(prefix="helios-calibration-")
        data_dir = _materialise(Path(room) / "data", CALIBRATION_FILES)
        _seal(room)
        _CALIBRATION_CACHE.append((run_script(data_dir, Path(room) / "out"), data_dir))
    return _CALIBRATION_CACHE[0]


_TWIN_CACHE = []


def calibration_twin_run():
    """Run the program on a perturbed control whose figures differ from the published ones.

    Sample identifiers, the report identity and the budget change, one suspect row is
    dropped and one count moves, so copying the worked example cannot pass.
    """
    if not _TWIN_CACHE:
        files = dict(CALIBRATION_FILES)
        policy = json.loads(files["policy.json"])
        policy["report_id"] = "HELIOS-CONTROL-TWIN"
        policy["uncertainty_budget_nano"] = 977
        files["policy.json"] = json.dumps(policy)
        rows = [
            row for row in files["observations.csv"].split("\n") if not row.startswith("C-12,")
        ]
        rows = [
            row.replace("2031-01-13T00:00:00,20,", "2031-01-13T00:00:00,23,")
            if row.startswith("C-10,") else row
            for row in rows
        ]
        files["observations.csv"] = re.sub(r"(?m)^C-", "K-", "\n".join(rows))
        files["amendments.jsonl"] = files["amendments.jsonl"].replace('"C-', '"K-')
        room = tempfile.mkdtemp(prefix="helios-twin-")
        data_dir = _materialise(Path(room) / "data", files)
        _seal(room)
        _TWIN_CACHE.append((run_script(data_dir, Path(room) / "out"), derive(data_dir)))
    return _TWIN_CACHE[0]


def _twin_matches(report, keys, published):
    """The perturbed control's slice must move away from the published one and be derived."""
    produced, expected = calibration_twin_run()
    want = _slice(expected[report], keys)
    _need(want != published, "the perturbed control does not move %s" % report)
    _same(_slice(produced[report], keys), want, "the perturbed control %s" % report)


def mutated_visible(overrides, prefix, nested=False):
    files = dict(VISIBLE_FILES)
    files.update(overrides)
    room = tempfile.mkdtemp(prefix=prefix)
    data_dir = _materialise(Path(room) / "data", files)
    _seal(room)
    if not nested:
        return run_script(data_dir, Path(room) / "out"), data_dir
    # A writable scratch area whose nested output location does not exist yet.
    scratch = Path(room) / "scratch"
    scratch.mkdir()
    os.chmod(scratch, 0o777)
    return run_script(data_dir, scratch / "deep" / "nested" / "out", create=False), data_dir


def _float_shares(budget, counts, names):
    """Largest-remainder apportionment carried through binary floating point."""
    total = sum(counts.get(name, 0) for name in names)
    if total <= 0:
        return dict((name, 0) for name in names)
    scale = float(budget) / float(total)
    raw = dict((name, scale * float(counts.get(name, 0))) for name in names)
    shares = dict((name, int(raw[name])) for name in names)
    spare = budget - sum(shares.values())
    order = sorted(names, key=lambda name: (-(raw[name] - shares[name]), name))
    index = 0
    while spare > 0 and order:
        shares[order[index % len(order)]] += 1
        spare -= 1
        index += 1
    return shares


# --------------------------------------------------------------------------
# Positive checks.
# --------------------------------------------------------------------------


@criterion(description="The network summary for the shipped archive matches the reference derivation exactly.")
def visible_summary_matches_reference(workspace):
    """POSITIVE: summary.json is exactly right for the shipped archive."""
    try:
        _bind(workspace)
        expected = derive(visible_inputs())["summary.json"]
        _same(actual_bundle()["summary.json"], expected, "the network summary")
        return True
    except Exception:
        return False


@criterion(description="The policy audit for the shipped archive matches the reference derivation exactly.")
def visible_policy_audit_matches_reference(workspace):
    """POSITIVE: policy_audit.json is exactly right for the shipped archive."""
    try:
        _bind(workspace)
        expected = derive(visible_inputs())["policy_audit.json"]
        _same(actual_bundle()["policy_audit.json"], expected, "the policy audit")
        return True
    except Exception:
        return False


@criterion(description="The data quality report for the shipped archive matches the reference derivation exactly.")
def visible_data_quality_matches_reference(workspace):
    """POSITIVE: data_quality.json is exactly right for the shipped archive."""
    try:
        _bind(workspace)
        expected = derive(visible_inputs())["data_quality.json"]
        _same(actual_bundle()["data_quality.json"], expected, "the data quality report")
        return True
    except Exception:
        return False


@criterion(description="The four area reports and both operator class reports for the shipped archive match the reference derivation exactly.")
def visible_bucket_reports_match_reference(workspace):
    """POSITIVE: every region_*.json and segment_*.json is exactly right for the shipped archive."""
    try:
        _bind(workspace)
        expected = derive(visible_inputs())
        for key in ["region_%s.json" % name for name in AREA_NAMES] + [
                "segment_%s.json" % name for name in CLASS_NAMES]:
            _same(actual(key), expected[key], "bucket report %s" % key)
        return True
    except Exception:
        return False


@criterion(description="The delivered program replaces in full every report a stale earlier run left in the output location.")
def reusable_script_regenerates_full_artifact_set(workspace):
    """POSITIVE: the transform is reusable and replaces stale output in full."""
    try:
        _bind(workspace)
        room = tempfile.mkdtemp(prefix="helios-replay-")
        stale = Path(room) / "out"
        stale.mkdir()
        for name in ARTIFACT_NAMES:
            (stale / name).write_text('{"report_id": "STALE", "accepted_count": ', encoding="utf-8")
        _seal(room)
        produced = run_script(visible_inputs(), Path(room) / "out")
        expected = derive(visible_inputs())
        for name in ARTIFACT_NAMES:
            _same(produced[name], expected[name], "regenerated %s" % name)
        return True
    except Exception:
        return False


@criterion(description="The delivered program creates an absent nested output location and writes the complete report set for an archive holding no observation.")
def empty_archive_yields_complete_report_set(workspace):
    """POSITIVE: an archive with no observation and no ledger entry still yields every report."""
    try:
        _bind(workspace)
        header = VISIBLE_FILES["observations.csv"].split("\n", 1)[0] + "\n"
        produced, data_dir = mutated_visible(
            {"observations.csv": header, "amendments.jsonl": ""}, "helios-empty-", nested=True
        )
        expected = derive(data_dir)
        _need(expected["summary.json"]["observed_count"] == 0, "empty archive still observes")
        for name in ARTIFACT_NAMES:
            _same(produced[name], expected[name], "empty archive %s" % name)
        return True
    except Exception:
        return False


@criterion(description="Revoked certificates are never valid at any epoch and the fallback certificate's own ladder, walked over the ledger-revised standards, decides traceability on an unseen archive.")
def retroactive_revocation_falls_back(workspace):
    """POSITIVE: the certificate a retroactive revocation falls back to is traced over the
    ledger-revised standards, whose loops leave its samples on a broken ladder."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            CHALLENGE_SEED ^ 0x81, 52, "helios-revocation-",
            [("honour_revocation", False), ("strict_cycles", False),
             ("standard_mode", "none"), ("standard_mode", "file")],
            ["summary.json", "policy_audit.json", "data_quality.json"],
            cyclic=True, restandard=True,
        )
    except Exception:
        return False


@criterion(description="The reporting floor clamps corrected sample values on an unseen archive.")
def reporting_floor_clamps_unseen_archive(workspace):
    """POSITIVE: the policy floor is applied per sample before any total is formed."""
    try:
        _bind(workspace)
        produced, data_dir = case_run(EVAL_SEED ^ 0x0E, 69)
        expected = derive(data_dir)
        unclamped = derive(data_dir, apply_floor=False)
        _need(expected["summary.json"]["reported_nano"]
              != unclamped["summary.json"]["reported_nano"], "probe archive clamps nothing")
        _same(produced["summary.json"]["reported_nano"],
              expected["summary.json"]["reported_nano"], "the clamped network total")
        for name in CLASS_NAMES:
            key = "segment_%s.json" % name
            _same(produced[key]["reported_nano"], expected[key]["reported_nano"],
                  "the clamped total for class %s" % name)
        return True
    except Exception:
        return False


@criterion(description="Reports are serialised with sorted keys, a two space indent and a trailing newline.")
def canonical_serialisation_format(workspace):
    """POSITIVE: the serialisation convention is reproduced byte for byte."""
    try:
        _bind(workspace)
        for name in ARTIFACT_NAMES:
            raw = (_out() / name).read_text(encoding="utf-8")
            _need(raw.endswith("\n"), "%s has no trailing newline" % name)
            parsed = json.loads(raw)
            _need(isinstance(parsed, dict) and bool(parsed), "%s is not a populated report" % name)
            _need(raw == json.dumps(parsed, indent=2, sort_keys=True) + "\n", name)
        return True
    except Exception:
        return False


@criterion(description="The quarantine reason census on the calibration control and its perturbed twin follows the precedence order the control demonstrates.")
def precedence_order_inferred_correctly(workspace):
    """POSITIVE: the census the control publishes is reproduced, and the twin moves with it."""
    try:
        _bind(workspace)
        produced, _ = calibration_run()
        published = {
            "duplicate_sample": 1,
            "unresolved_suspect": 1,
            "malformed_sample": 2,
            "unknown_channel": 1,
            "no_deployment": 1,
            "no_custody": 1,
            "no_certificate": 2,
            "unknown_unit": 1,
            "broken_ladder": 1,
        }
        _need(produced["data_quality.json"]["quarantine_reasons"] == published,
              "the delivered census does not use the inferred order")
        _twin_matches("data_quality.json", ["quarantine_reasons"],
                      {"quarantine_reasons": published})
        return True
    except Exception:
        return False


@criterion(description="Non cancelling exact halves on both sides of zero reproduce the published rounded total.")
def rounding_mode_inferred_correctly(workspace):
    """POSITIVE: half away from zero is the single rounding convention used."""
    try:
        _bind(workspace)
        produced, _ = calibration_run()
        summary = produced["summary.json"]
        _need(summary["reported_nano"] == 69, "the published rounded total is not reproduced")
        _need(summary["canonical_nano"] == 69, "the ratio unit half is not rounded away from zero")
        _need(summary["channel_totals"]["HLS-0006"] == 1, "signed halves cancel the wrong way")
        _need(summary["channel_totals"]["HLS-0001"] == 68, "the ratio unit half is rounded the wrong way")
        _twin_matches("summary.json", ["reported_nano", "canonical_nano", "channel_totals"],
                      {"reported_nano": 69, "canonical_nano": 69,
                       "channel_totals": {"HLS-0001": 68, "HLS-0006": 1}})
        return True
    except Exception:
        return False


@criterion(description="The standing set is the earned closure rather than the naive single pass on an unseen archive.")
def naive_single_pass_is_rejected(workspace):
    """POSITIVE: standing is earned by fixpoint, not granted by one sweep, on an unseen archive."""
    try:
        _bind(workspace)
        produced, data_dir = case_run(STANDING_PROBE_SEED, 58, "helios-standing-")
        earned = derive(data_dir)["policy_audit.json"]
        naive = derive(data_dir, earned_standing=False)["policy_audit.json"]
        _need(set(naive["reporting_arrays"]) - set(earned["reporting_arrays"]),
              "the probe archive does not separate a single sweep")
        _need(max(earned["reporting_round_by_array"].values(), default=0) >= 2,
              "the probe archive has no custody propagation round")
        delivered = produced["policy_audit.json"]
        _same(delivered["reporting_arrays"], earned["reporting_arrays"], "the earned standing set")
        _same(delivered["reporting_round_by_array"], earned["reporting_round_by_array"],
              "the earned rounds")
        return True
    except Exception:
        return False


@criterion(description="Standing closure generalises to a rewired custody dependency graph.")
def fixpoint_generalises_to_restructured_dependency_graph(workspace):
    """POSITIVE: a different three link propagation path is resolved from scratch."""
    try:
        _bind(workspace)
        custody = VISIBLE_FILES["custody.csv"].replace(
            "SC-01,,,,,HLS-0031,HLS-0004\nSC-02,,,,,HLS-0056,HLS-0031\nSC-03,,,,,HLS-0023,HLS-0056",
            "SC-11,,,,,HLS-0011,HLS-0004\nSC-12,,,,,HLS-0017,HLS-0011\nSC-13,,,,,HLS-0042,HLS-0017",
        )
        produced, data_dir = mutated_visible({"custody.csv": custody}, "helios-graph-")
        expected = derive(data_dir)
        _need(expected["policy_audit.json"]["reporting_round_by_array"] == {
            "HLS-0004": 1, "HLS-0011": 2, "HLS-0017": 3,
        }, "the rewired closure is not the expected one")
        _focused_same(produced, expected, [derive(visible_inputs())],
                      sorted(STANDING_FACTS), "rewired", STANDING_FACTS)
        return True
    except Exception:
        return False


@criterion(description="Standing closure generalises to stronger reporting floor bands.")
def fixpoint_generalises_to_threshold_mutation(workspace):
    """POSITIVE: with no seed available the closure is empty and every report follows."""
    try:
        _bind(workspace)
        thresholds = json.loads(VISIBLE_FILES["thresholds.json"])
        for band in thresholds["reporting_floor_bands"]:
            band["minimum_qualifying_observations"] = 7
        produced, data_dir = mutated_visible(
            {"thresholds.json": json.dumps(thresholds)}, "helios-threshold-"
        )
        expected = derive(data_dir)
        _need(expected["policy_audit.json"]["reporting_arrays"] == [],
              "the stronger bands still admit a seed")
        _focused_same(produced, expected, [derive(visible_inputs())],
                      sorted(STANDING_FACTS), "threshold-mutated", STANDING_FACTS)
        return True
    except Exception:
        return False


@criterion(description="Standing closure generalises after effective date resolution changes.")
def fixpoint_generalises_to_effective_date_mutation(workspace):
    """POSITIVE: interval selection runs before closure, so a later start breaks the chain."""
    try:
        _bind(workspace)
        custody = VISIBLE_FILES["custody.csv"].replace(
            "CU-05,ST-WEST-1,AG-CRD,2031-02-01T00:00:00",
            "CU-05,ST-WEST-1,AG-CRD,2031-06-01T00:00:00",
        )
        produced, data_dir = mutated_visible({"custody.csv": custody}, "helios-effective-")
        expected = derive(data_dir)
        _need(expected["policy_audit.json"]["reporting_arrays"] == ["HLS-0004"],
              "the custody chain still propagates")
        _focused_same(produced, expected, [derive(visible_inputs())],
                      sorted(STANDING_FACTS), "effective-mutated", STANDING_FACTS)
        return True
    except Exception:
        return False


@criterion(description="Standing closure generalises to a larger qualifying population.")
def fixpoint_generalises_to_population_mutation(workspace):
    """POSITIVE: one extra qualifying observation moves a channel into a later round."""
    try:
        _bind(workspace)
        observations = VISIBLE_FILES["observations.csv"] + (
            "S-0099,HLS-0011,2031-05-29T00:00:00,100,nm/s^2,observed,true\n"
        )
        produced, data_dir = mutated_visible({"observations.csv": observations}, "helios-population-")
        expected = derive(data_dir)
        _need(expected["policy_audit.json"]["reporting_round_by_array"]["HLS-0011"] == 2,
              "the larger population does not admit the channel")
        _focused_same(produced, expected, [derive(visible_inputs())],
                      sorted(STANDING_FACTS), "population-mutated", STANDING_FACTS)
        return True
    except Exception:
        return False


@criterion(description="Standing closure generalises to changed area membership in the roster.")
def fixpoint_generalises_to_partition_membership_mutation(workspace):
    """POSITIVE: band selection follows the mutated area population."""
    try:
        _bind(workspace)
        registry = VISIBLE_FILES["channel_registry.csv"].replace(
            "HLS-0031,GRV-1,TRUE,West", "HLS-0031,GRV-1,TRUE,North"
        )
        produced, data_dir = mutated_visible({"channel_registry.csv": registry}, "helios-partition-")
        expected = derive(data_dir)
        _need("HLS-0011" in expected["policy_audit.json"]["reporting_arrays"],
              "the changed band does not admit the channel")
        _focused_same(produced, expected, [derive(visible_inputs())],
                      sorted(STANDING_FACTS), "partition-mutated", STANDING_FACTS)
        return True
    except Exception:
        return False


@criterion(description="Repeated sample rows are held under their own reason on an unseen archive.")
def duplicate_rows_held_under_their_own_reason(workspace):
    """POSITIVE: a repeated sample_id is carried by its first row alone."""
    try:
        _bind(workspace)
        produced, data_dir = case_run(DUPLICATE_PROBE_SEED, 58, "helios-duplicate-")
        expected = derive(data_dir)
        merged = derive(data_dir, dedupe=False)
        census = expected["data_quality.json"]["quarantine_reasons"]
        _need(census.get("duplicate_sample", 0) > 0, "probe archive carries no repeated rows")
        _need(expected["summary.json"] != merged["summary.json"], "probe archive is inert")
        _focused_same(produced, expected, [merged], ["data_quality.json", "summary.json"],
                      "duplicate")
        return True
    except Exception:
        return False


@criterion(description="Amendment replay follows ascending sequence then code point identifier order on an unseen archive.")
def ledger_sequence_governs_amendment_replay(workspace):
    """POSITIVE: file order carries no meaning, ties use code points and a repeated entry posts once."""
    try:
        _bind(workspace)
        produced, data_dir = case_run(SEQUENCE_PROBE_SEED, 61, "helios-sequence-")
        expected = derive(data_dir)
        filed = derive(data_dir, ledger_order=False)
        _need(expected["summary.json"] != filed["summary.json"]
              or expected["policy_audit.json"] != filed["policy_audit.json"],
              "probe archive is inert")
        natural = derive(data_dir, codepoint_ties=False)
        _need(expected["summary.json"] != natural["summary.json"]
              or expected["data_quality.json"] != natural["data_quality.json"],
              "probe archive does not separate code point ties")
        _focused_same(produced, expected, [filed, natural],
                      ["policy_audit.json", "data_quality.json", "summary.json"], "sequence")
        return True
    except Exception:
        return False


@criterion(description="Quoted archive fields holding a separator are read as one field.")
def quoted_archive_fields_read_faithfully(workspace):
    """POSITIVE: the quoting moves to a different row and the partition follows it."""
    try:
        _bind(workspace)
        agencies = VISIBLE_FILES["agencies.csv"].replace(
            'AG-CRD,"Cordilleran Geophysics, Ltd",commercial',
            "AG-CRD,Cordilleran Geophysics Ltd,commercial",
        ).replace(
            "AG-KLV,Kelvin Instruments,commercial",
            'AG-KLV,"Kelvin Instruments, PLC",public',
        )
        _need(agencies != VISIBLE_FILES["agencies.csv"], "the roster mutation did not apply")
        produced, data_dir = mutated_visible({"agencies.csv": agencies}, "helios-quoted-")
        expected = derive(data_dir)
        shipped = derive(visible_inputs())
        _need(expected["segment_public.json"] != shipped["segment_public.json"],
              "probe archive is inert")
        _focused_same(produced, expected, [shipped], ARTIFACT_NAMES, "requoted")
        return True
    except Exception:
        return False


@criterion(description="The uncertainty budget is apportioned to the unit beyond exact binary float range.")
def budget_apportioned_exactly_beyond_float_precision(workspace):
    """POSITIVE: shares sum to the budget exactly where a float path drifts."""
    try:
        _bind(workspace)
        produced, data_dir = case_run(BUDGET_PROBE_SEED, 55, "helios-budget-")
        expected = derive(data_dir)["summary.json"]
        summary = produced["summary.json"]
        budget = expected["budget_nano"]
        _need(budget > 2 ** 53, "probe archive budget is inside exact float range")
        _need(sum(summary["array_allocation_nano"].values()) == budget,
              "area shares do not sum to the budget")
        _need(sum(summary["segment_allocation_nano"].values()) == budget,
              "class shares do not sum to the budget")
        drifted = _float_shares(budget, expected["array_counts"], AREA_NAMES)
        _need(drifted != expected["array_allocation_nano"],
              "probe archive tolerates float apportionment across areas")
        slipped = _float_shares(budget, expected["segment_counts"], CLASS_NAMES)
        _need(slipped != expected["segment_allocation_nano"],
              "probe archive tolerates float apportionment across classes")
        _same(summary["array_allocation_nano"], expected["array_allocation_nano"], "area shares")
        _same(summary["segment_allocation_nano"], expected["segment_allocation_nano"],
              "class shares")
        return True
    except Exception:
        return False


def _shortcut_probe(seed, sample_count, prefix, shortcut, names, **overlays):
    """Run the program on an unseen archive the named shortcuts misread, then compare."""
    produced, data_dir = case_run(seed, sample_count, prefix, **overlays)
    expected = derive(data_dir)
    misreads = shortcut if isinstance(shortcut, list) else [(shortcut, False)]
    contrasts = []
    for key, value in misreads:
        misread = derive(data_dir, **{key: value})
        _need(any(expected[name] != misread[name] for name in names),
              "probe archive is inert for %s=%r" % (key, value))
        contrasts.append(misread)
    return _focused_same(produced, expected, contrasts, names, prefix.strip("-"))


@criterion(description="Ratio unit factors and counts beyond fixed precision range become exact canonical integers on an unseen archive.")
def ratio_unit_factors_normalised_exactly(workspace):
    """POSITIVE: ratio factors, exact halves and very wide counts survive without precision loss."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            RATIO_PROBE_SEED, 64, "helios-ratio-",
            [("rational_units", False), ("arithmetic", "float"), ("arithmetic", "decimal"),
             ("zero_factor_rule", False)],
            ["summary.json"] + ["region_%s.json" % name for name in AREA_NAMES],
            huge=True, edges=("zero_numerator",),
        )
    except Exception:
        return False


@criterion(description="Certificate restoration is replayed in ledger order on an unseen archive.")
def certificate_restoration_follows_ledger_order(workspace):
    """POSITIVE: a restore before its revoke is ignored and a later one reopens the certificate."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            RESTORE_PROBE_SEED, 57, "helios-restore-", "restore",
            ["summary.json", "policy_audit.json", "data_quality.json"],
        )
    except Exception:
        return False


@criterion(description="Loosely written timestamps compare as instants on an unseen archive.")
def loose_timestamps_compare_as_instants(workspace):
    """POSITIVE: unpadded and space separated epochs resolve intervals and drift order."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            INSTANT_PROBE_SEED, 62, "helios-instant-", "parse_epochs",
            ["summary.json", "policy_audit.json"]
            + ["region_%s.json" % name for name in AREA_NAMES],
        )
    except Exception:
        return False


@criterion(description="Flags read in any letter case and standing basis revisions reach the closure on an unseen archive.")
def case_folded_flags_and_basis_revisions(workspace):
    """POSITIVE: recased flags and boolean revisions change qualifying counts and sources."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            FLAG_PROBE_SEED, 60, "helios-flags-", "fold_flags",
            ["summary.json", "policy_audit.json", "data_quality.json"],
        )
    except Exception:
        return False


@criterion(description="Malformed ledger lines are counted as unmatched and never post or claim an entry on an unseen archive.")
def malformed_ledger_lines_never_post(workspace):
    """POSITIVE: damaged lines cannot void samples or shadow a later well formed entry."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            MALFORMED_PROBE_SEED, 59, "helios-malformed-",
            [("strict_ledger", False), ("empty_entry_rule", False)],
            ["summary.json", "policy_audit.json", "data_quality.json"],
            edges=("empty_entry",),
        )
    except Exception:
        return False


@criterion(description="Certificates stop applying after their inclusive expiry instant on an unseen archive.")
def certificate_expiry_bounds_selection(workspace):
    """POSITIVE: an expired certificate is skipped, falling back or leaving no certificate."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            EXPIRY_PROBE_SEED, 63, "helios-expiry-", "honour_expiry",
            ["summary.json", "policy_audit.json", "data_quality.json"],
        )
    except Exception:
        return False


@criterion(description="Raw counts and epochs outside the contract form are held as malformed on an unseen archive.")
def malformed_sample_values_quarantined(workspace):
    """POSITIVE: damaged rows and revisions are isolated, repaired rows recover, nothing crashes."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            VALUE_PROBE_SEED, 66, "helios-values-", "strict_values",
            ["summary.json", "policy_audit.json", "data_quality.json"],
        )
    except Exception:
        return False


@criterion(description="Baseline rows sharing an epoch inside one drift run take drift positions in sample identifier order on an unseen archive.")
def drift_positions_break_epoch_ties_by_sample(workspace):
    """POSITIVE: two rows of one run at the same instant are positioned by sample identifier."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            DRIFT_TIE_PROBE_SEED, 57, "helios-drift-tie-", "drift_ties",
            ["summary.json"] + ["region_%s.json" % name for name in AREA_NAMES],
            edges=("drift_tie",),
        )
    except Exception:
        return False


@criterion(description="The largest sample tie on reported value goes to the lower sample identifier on an unseen archive.")
def largest_sample_tie_breaks_on_sample_identifier(workspace):
    """POSITIVE: two samples reporting the same greatest value resolve to the lower identifier."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            LARGEST_TIE_PROBE_SEED, 56, "helios-largest-tie-", "largest_ties",
            ["summary.json"],
            edges=("largest_tie",),
        )
    except Exception:
        return False


@criterion(description="A variance alert is raised when an area gap equals the alert gate exactly on an unseen archive.")
def variance_alert_fires_at_exact_gate(workspace):
    """POSITIVE: the alert comparison is inclusive at the gate."""
    try:
        _bind(workspace)
        return _shortcut_probe(
            ALERT_GATE_PROBE_SEED, 60, "helios-alert-gate-", "inclusive_gate",
            ["summary.json"] + ["region_%s.json" % name for name in AREA_NAMES],
            edges=("alert_gate",),
        )
    except Exception:
        return False


# --------------------------------------------------------------------------
# Negative checks. Each returns True only when the cheat is present.
# --------------------------------------------------------------------------


@criterion(description="The agent program embeds shipped archive answers as literals in its own source.")
def negative_hardcoded_sample_answers(workspace):
    """NEGATIVE: holds when the program carries the shipped answers as constants."""
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        _bind(workspace)
        _need(_py_source_text().strip(), "no reusable derivation program source found")
        _need(_answers_embedded_in_source(), "no shipped answers embedded in the program source")
        return True
    except Exception:
        return False


@criterion(description="The agent program reaches for verifier or grading material outside the archive.")
def negative_reads_tests_or_reward_files(workspace):
    """NEGATIVE: holds when grading material is named by the program or its output."""
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        _bind(workspace)
        _need(_source_text().strip(), "nothing produced to audit")
        # Only string literals and report text count: an identifier such as
        # latest_output is honest code, a path literal naming grading material is not.
        probes = (r"(?<![\w.])/tests(?![\w-])", r"(?<![A-Za-z0-9])test_output(?![A-Za-z0-9])",
                  r"test_weights", r"ctrf\.json", r"rewa" r"rd\.json", r"rewa" r"rd\.txt",
                  r"/logs/" r"verifier", r"(?<![\w.])/solution(?![\w-])")
        texts = _program_strings()
        texts.extend((_out() / name).read_text(encoding="utf-8", errors="replace")
                     for name in ARTIFACT_NAMES if (_out() / name).is_file())
        _need([probe for probe in probes if any(re.search(probe, text) for text in texts)],
              "no verifier access detected")
        return True
    except Exception:
        return False


@criterion(description="The agent program imports a third party package or reaches the network.")
def negative_external_dependency_or_network(workspace):
    """NEGATIVE: holds when a foreign import or a network token is present."""
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        _bind(workspace)
        _need(_py_source_text().strip(), "no reusable derivation program source found")
        if _foreign_imports():
            return True
        probes = ("urllib.request", "urllib.error", "socket.socket", "http.client",
                  "ftplib", "telnetlib", "requests.get", "httpx.get", "aiohttp",
                  "http://", "https://", "pip install")
        _need(_fact_hits(probes), "no external dependency detected")
        return True
    except Exception:
        return False


@criterion(description="The agent program writes different bytes on two runs over one archive.")
def negative_nondeterministic_output(workspace):
    """NEGATIVE: holds when the transform is not byte stable."""
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        _bind(workspace)
        room = tempfile.mkdtemp(prefix="helios-neg-determinism-")
        data_dir = write_case(Path(room) / "data", CHALLENGE_SEED ^ 0x44, 50)
        _seal(room)
        first = run_script_raw(data_dir, Path(room) / "one")
        second = run_script_raw(data_dir, Path(room) / "two")
        _need(first != second, "output is byte stable across runs")
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# Weight registrations.
# --------------------------------------------------------------------------


criteria.visible_summary_matches_reference(weight=5)
criteria.visible_policy_audit_matches_reference(weight=5)
criteria.visible_data_quality_matches_reference(weight=5)
criteria.visible_bucket_reports_match_reference(weight=5)
criteria.reusable_script_regenerates_full_artifact_set(weight=3)
criteria.empty_archive_yields_complete_report_set(weight=3)
criteria.retroactive_revocation_falls_back(weight=5)
criteria.reporting_floor_clamps_unseen_archive(weight=5)
criteria.canonical_serialisation_format(weight=1)
criteria.precedence_order_inferred_correctly(weight=5)
criteria.rounding_mode_inferred_correctly(weight=5)
criteria.naive_single_pass_is_rejected(weight=5)
criteria.fixpoint_generalises_to_restructured_dependency_graph(weight=5)
criteria.fixpoint_generalises_to_threshold_mutation(weight=5)
criteria.fixpoint_generalises_to_effective_date_mutation(weight=5)
criteria.fixpoint_generalises_to_population_mutation(weight=5)
criteria.fixpoint_generalises_to_partition_membership_mutation(weight=5)
criteria.duplicate_rows_held_under_their_own_reason(weight=5)
criteria.ledger_sequence_governs_amendment_replay(weight=5)
criteria.quoted_archive_fields_read_faithfully(weight=3)
criteria.budget_apportioned_exactly_beyond_float_precision(weight=5)
criteria.ratio_unit_factors_normalised_exactly(weight=5)
criteria.certificate_restoration_follows_ledger_order(weight=5)
criteria.loose_timestamps_compare_as_instants(weight=5)
criteria.case_folded_flags_and_basis_revisions(weight=3)
criteria.malformed_ledger_lines_never_post(weight=5)
criteria.certificate_expiry_bounds_selection(weight=5)
criteria.malformed_sample_values_quarantined(weight=5)
criteria.drift_positions_break_epoch_ties_by_sample(weight=3)
criteria.largest_sample_tie_breaks_on_sample_identifier(weight=1)
criteria.variance_alert_fires_at_exact_gate(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-5)
criteria.negative_nondeterministic_output(weight=-5)
