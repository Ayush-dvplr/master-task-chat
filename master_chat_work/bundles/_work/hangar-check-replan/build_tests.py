"""Build BUNDLE/tests/test_output.py from tests_harness.py + the GEN block of datagen.py + shipped data."""
import base64
import os
import sys
import zlib

WORK = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(os.path.dirname(os.path.dirname(WORK)), "hangar-check-replan")
DATA = os.path.join(BUNDLE, "environment", "data")

src = open(os.path.join(WORK, "datagen.py")).read()
gen = src.split("# ---- GEN BEGIN ----\n", 1)[1].split("# ---- GEN END ----", 1)[0]
blobs = []
for name in sorted(os.listdir(DATA)):
    p = os.path.join(DATA, name)
    if os.path.isfile(p):
        b = base64.b64encode(zlib.compress(open(p, "rb").read(), 9)).decode()
        blobs.append('    "%s": "%s",' % (name, b))
shipped = "_SHIPPED_DATA: dict[str, str] = {\n" + "\n".join(blobs) + "\n}"

C = []  # (name, description, weight, call)
C.append(("program_runs_on_shipped_data", "Running the stated command on a fresh copy of the shipped data folder, "
          "from another working folder, writes all nine JSON reports and each parses.", 1,
          "_check_program_runs_shipped"))
C.append(("program_stops_on_a_missing_input", "Running the stated command on a copy of the shipped data folder with "
          "fleet_register.csv removed ends with a non-zero exit code and a standard error message that names "
          "fleet_register.csv.", 1, "_check_stops_on_missing_input"))
C.append(("shipped_plan_rows", "On the shipped data, the delivered policy_audit.json season and plan fields of every "
          "request match the expected values.", 3, "_check_shipped_rows"))
C.append(("shipped_data_quality", "On the shipped data, the delivered data_quality.json lists every rejected row "
          "with its line and reason, and the counts match.", 1, "_check_shipped_data_quality"))
C.append(("shipped_group_reports", "On the shipped data, the delivered region, segment and summary files match the "
          "expected counts, totals, dates and plan terms (settlement fields excluded).", 3, "_check_shipped_reports"))
C.append(("shipped_settlement", "On the shipped data, every settlement field of the delivered checks, regions, "
          "segments and summary matches the expected values.", 3, "_check_shipped_settlement"))
for h in ["h1", "h2", "h3", "h4", "h5", "h6"]:
    C.append(("%s_plan_rows" % h, "On held-out data folder %s, the policy_audit.json season and plan fields of "
              "every request match." % h, 3, 'lambda: _check_hidden_rows("%s")' % h))
    C.append(("%s_plan_group_totals" % h, "On held-out data folder %s, the non-settlement fields of the region, "
              "segment and summary reports match." % h, 1, 'lambda: _check_hidden_group_totals("%s")' % h))
    C.append(("%s_settlement_per_check" % h, "On held-out data folder %s, overtime_cost, allowance_shifts, "
              "paid_shifts, allowance_credit and settled_overtime_cost of every request match." % h, 5,
              'lambda: _check_hidden_settle("%s", "checks")' % h))
    C.append(("%s_settlement_by_base_and_segment" % h, "On held-out data folder %s, the settlement fields of every "
              "base report and segment report with requests match." % h, 5,
              'lambda: _check_hidden_settle("%s", "groups")' % h))
    C.append(("%s_settlement_summary" % h, "On held-out data folder %s, the summary settlement object and the "
              "allowance fields of the base rows match." % h, 5, 'lambda: _check_hidden_settle("%s", "summary")' % h))
for h in ["h1", "h2"]:
    C.append(("%s_base_and_segment_with_no_requests" % h, "On held-out data folder %s, the base and the segment "
              "that have no open request still get their report file and summary row with the stated zero and "
              "null values." % h, 1, 'lambda: _check_hidden_empty("%s")' % h))
C.append(("h1_data_quality", "On held-out data folder h1, data_quality.json lists every rejected row with its line "
          "and reason (rows with two faults and a row with a bad available_from included), and the counts match.", 3, 'lambda: _check_hidden_data_quality("h1")'))
C.append(("changed_allowance_grants", "On the shipped data with the allowance grants changed so the fleet allowance "
          "runs out, every settlement field matches.", 3, "_check_mutant_settlement"))
C.append(("revised_availability_removed", "On the shipped data with the revised availability table emptied, every "
          "plan and settlement field matches.", 3, "_check_mutant_all"))
C.append(("negative_hardcoded_sample_answers", "Penalty: the program text carries request ids of the shipped plan.",
          -5, "_check_negative_weight_hardcoded_sample_answers"))
C.append(("negative_reads_check_files", "Penalty: the program text names the check folder or the check result files.",
          -5, "_check_negative_weight_reads_check_files"))
C.append(("negative_writes_outside_out_dir", "Penalty: a run on a held-out or changed data folder leaves files in "
          "its working folder or beside OUT_DIR, or changes the data folder.", -3,
          "_check_negative_weight_writes_outside_out_dir"))

crit = []
for name, desc, w, call in C:
    crit.append('@criterion(description="%s")\ndef %s(workspace: Path) -> bool:\n    return _holds(%s)\n'
                % (desc, name, call))
crit.append("\n" + "\n".join("criteria.%s(weight=%d)" % (n, w) for n, _, w, _ in C) + "\n")

h = open(os.path.join(WORK, "tests_harness.py")).read()
h = h.replace("# @@GEN@@", "# ---- generator and expected outputs ----\n" + gen.strip() + "\n")
h = h.replace("# @@SHIPPED@@", shipped)
h = h.replace("# @@CRITERIA@@\n", "\n\n".join(crit))
open(os.path.join(BUNDLE, "tests", "test_output.py"), "w").write(h)
pos = sum(w for _, _, w, _ in C if w > 0)
print("checks", len(C), "positive", pos, "negative", sum(w for _, _, w, _ in C if w < 0))
