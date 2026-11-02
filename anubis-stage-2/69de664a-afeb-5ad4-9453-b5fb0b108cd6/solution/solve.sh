#!/bin/bash
# Oracle dispatcher for 69de664a-afeb-5ad4-9453-b5fb0b108cd6.
#
# Delivers the reusable program to its declared path, runs it on the shipped
# extract, then verifies it three ways before reporting anything: a second run
# compared byte for byte, a run over a row-reordered extract, and a run over an
# extract whose reference tables carry different values. The closing report
# states the stage order with its governing contract section, walks one named
# observation through the arithmetic, and explains the closure argument.
set -euo pipefail

DATA_DIR="${DATA_DIR:-/app/data}"
OUT_DIR="${OUT_DIR:-/app/out}"
PROG="${OUT_DIR}/derive_report.py"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${OUT_DIR}"

# Read the written contract and the role index BEFORE the program exists, since
# the application order and the authoritative source of each table live there.
cat "${DATA_DIR}/reconciliation_contract.md" >/dev/null
cat "${DATA_DIR}/pipeline_order_note.txt" >/dev/null
cat "${DATA_DIR}/file_role_index.md" >/dev/null
cat "${DATA_DIR}/relay_closure_rule.json" >/dev/null

# Record the one stage that refuses the convention of the layer above, before
# that stage is implemented.
echo "[plan] Contract section S1 fixes the settlement normalisation as a FLOOR"
echo "[plan] division toward negative infinity. It is the one place in this"
echo "[plan] contract that does NOT use the banker's rounding every stage of the"
echo "[plan] reconciliation layer above it uses, so the half-even habit is"
echo "[plan] rejected deliberately here. Implementing that divergence now."

cp /solution/solve.py "${PROG}"
chmod 0644 "${PROG}"

echo "[solve] run 1: shipped extract -> ${OUT_DIR}"
python3 "${PROG}" "${DATA_DIR}" "${OUT_DIR}"

# --------------------------------------------------------------------------
# Verification helper. Writes a sha256 manifest over every report artifact the
# program wrote, enumerated from the output directory rather than from a fixed
# list, so the comparison covers the whole delivered set and cannot fall behind
# it. The program file sitting alongside the artifacts is excluded, because the
# dispatcher copies it in and the program itself never rewrites it.
# --------------------------------------------------------------------------
cat >"${WORK}/manifest.py" <<'MANIFEST'
import hashlib
import pathlib
import sys

EXCLUDE = {"derive_report.py"}
d = pathlib.Path(sys.argv[1])
names = sorted(p.name for p in d.iterdir() if p.is_file() and p.name not in EXCLUDE)
for name in names:
    print(hashlib.sha256((d / name).read_bytes()).hexdigest(), name)
MANIFEST

python3 "${WORK}/manifest.py" "${OUT_DIR}" >"${WORK}/run1.sha256"
ART_COUNT="$(wc -l <"${WORK}/run1.sha256" | tr -d ' ')"

# --- check 1: determinism, the same extract run a second time --------------
echo "[verify] run 2: same extract, comparing the ${ART_COUNT} artifacts byte for byte"
mkdir -p "${WORK}/out_rerun"
python3 "${PROG}" "${DATA_DIR}" "${WORK}/out_rerun"
python3 "${WORK}/manifest.py" "${WORK}/out_rerun" >"${WORK}/run2.sha256"
if cmp -s "${WORK}/run1.sha256" "${WORK}/run2.sha256"; then
  echo "[verify] determinism OK: all ${ART_COUNT} artifacts byte-identical across the two runs"
else
  echo "[verify] determinism FAILED: reruns disagree" >&2
  diff "${WORK}/run1.sha256" "${WORK}/run2.sha256" >&2 || true
  exit 1
fi

# --- check 2: row-order invariance -----------------------------------------
echo "[verify] run 3: observation rows reversed, comparing against run 1"
cp -R "${DATA_DIR}" "${WORK}/data_reordered"
python3 - "${WORK}/data_reordered" <<'REORDER'
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "obs_capture_index.csv"
lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]
header, body = lines[0], lines[1:]
body.reverse()
path.write_text("\n".join([header] + body) + "\n", encoding="utf-8")
print(f"[verify] reversed {len(body)} observation rows in obs_capture_index.csv")
REORDER
mkdir -p "${WORK}/out_reordered"
python3 "${PROG}" "${WORK}/data_reordered" "${WORK}/out_reordered"
python3 "${WORK}/manifest.py" "${WORK}/out_reordered" >"${WORK}/run3.sha256"
if cmp -s "${WORK}/run1.sha256" "${WORK}/run3.sha256"; then
  echo "[verify] row-order invariance OK: all ${ART_COUNT} artifacts byte-identical under reversed rows"
else
  echo "[verify] row-order invariance FAILED" >&2
  diff "${WORK}/run1.sha256" "${WORK}/run3.sha256" >&2 || true
  exit 1
fi

# --- check 3: an extract whose reference tables hold different values ------
echo "[verify] run 4: reference tables altered, checking the figures follow them"
cp -R "${DATA_DIR}" "${WORK}/data_altered"
python3 - "${WORK}/data_altered" <<'PERTURB'
"""Shift every reference table the pipeline reads, including the workbook that
is the only publisher of the scale factor, so the next run can only agree with
an independent re-derivation if it read the tables rather than memorised them."""
import json
import pathlib
import re
import shutil
import sys
import zipfile

d = pathlib.Path(sys.argv[1])

path = d / "pedestal_authoritative.csv"
out = []
for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
    if i == 0 or not line:
        out.append(line)
        continue
    field = line.split(",")
    field[3] = str(int(field[3]) + 7)
    out.append(",".join(field))
path.write_text("\n".join(out) + "\n", encoding="utf-8")

path = d / "quantum_yield_micro.json"
doc = json.loads(path.read_text(encoding="utf-8"))
doc["channels"] = {k: int(v) + 60_000 for k, v in doc["channels"].items()}
path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

path = d / "thermal_drift_ppm.yml"
path.write_text(re.sub(r"drift_ppm: (\d+)",
                       lambda m: f"drift_ppm: {int(m.group(1)) + 250}",
                       path.read_text(encoding="utf-8")), encoding="utf-8")

path = d / "gain_scale_workbook.xlsx"
staged = path.with_name("workbook_source.xlsx")
shutil.move(str(path), str(staged))
with zipfile.ZipFile(staged) as zin:
    book = zin.read("xl/workbook.xml").decode("utf-8")
    sheet_id = dict(re.findall(r'<sheet name="([^"]+)"[^>]*sheetId="(\d+)"', book))[
        "scale_factor_authoritative"]
    target = f"xl/worksheets/sheet{sheet_id}.xml"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            payload = zin.read(item.filename)
            if item.filename == target:
                payload = re.sub(
                    rb't="n"><v>(\d+)</v>',
                    lambda m: b't="n"><v>%d</v>' % (int(m.group(1)) - 15_000),
                    payload)
            zout.writestr(item, payload)
staged.unlink()
print("[verify] altered tables: dark current +7, quantum yield +60000, "
      "drift +250 ppm, workbook scale factor -15000")
PERTURB
mkdir -p "${WORK}/out_altered"
python3 "${PROG}" "${WORK}/data_altered" "${WORK}/out_altered"
python3 "${WORK}/manifest.py" "${WORK}/out_altered" >"${WORK}/run4.sha256"
if cmp -s "${WORK}/run1.sha256" "${WORK}/run4.sha256"; then
  echo "[verify] altered-table run FAILED: output ignored the changed tables" >&2
  exit 1
fi
echo "[verify] altered-table run moved the output, as a table-driven pipeline must"

# --------------------------------------------------------------------------
# Independent re-derivation. Re-reads every table straight from an extract and
# walks one observation through the seven stages without using the delivered
# program, then compares against what that program wrote. Run against the
# shipped extract and against the altered-table extract, so the altered run is
# validated on its figures rather than only on having changed.
# --------------------------------------------------------------------------
cat >"${WORK}/independent.py" <<'INDEPENDENT'
"""Independent re-derivation of one observation, used to validate the delivered
program on the shipped extract and on an extract with different tables."""
import json
import re
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path


def half_even(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), ROUND_HALF_EVEN))


def delimited(path: Path, delim: str) -> list[dict[str, str]]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]
    header = lines[0].split(delim)
    return [dict(zip(header, ln.split(delim))) for ln in lines[1:]]


def workbook_factors(path: Path) -> dict[str, int]:
    with zipfile.ZipFile(path) as archive:
        book = archive.read("xl/workbook.xml").decode("utf-8")
        sheet_id = dict(re.findall(r'<sheet name="([^"]+)"[^>]*sheetId="(\d+)"', book))[
            "scale_factor_authoritative"]
        xml = archive.read(f"xl/worksheets/sheet{sheet_id}.xml").decode("utf-8")
    factors: dict[str, int] = {}
    for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
        cells = []
        for cell in re.findall(r"<c\b[^>]*>(.*?)</c>", row, re.S):
            found = (re.search(r"<t[^>]*>(.*?)</t>", cell, re.S)
                     or re.search(r"<v>(.*?)</v>", cell, re.S))
            cells.append(found.group(1) if found else "")
        if len(cells) >= 2 and re.fullmatch(r"\d+", cells[1] or ""):
            factors[cells[0]] = int(cells[1])
    return factors


def horner_coefficients(path: Path) -> dict[str, list[int]]:
    coefficients: dict[str, list[int]] = {}
    current = None
    started = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("coefficients:"):
            started = True
            continue
        if not started:
            continue
        head = re.fullmatch(r"  (\w+):", line)
        if head:
            current = head.group(1)
            coefficients[current] = []
        elif line.strip().startswith("- ") and current:
            coefficients[current].append(int(line.strip()[2:]))
    return coefficients


def drift_table(path: Path) -> dict[tuple[str, str], int]:
    drift: dict[tuple[str, str], int] = {}
    instrument = epoch = None
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text.startswith("instrument:"):
            instrument = text.split(":", 1)[1].strip()
        elif text.startswith("epoch:"):
            epoch = text.split(":", 1)[1].strip()
        elif text.startswith("drift_ppm:"):
            drift[(instrument, epoch)] = int(text.split(":", 1)[1].strip())
    return drift


def load(data_dir: str) -> dict:
    d = Path(data_dir)
    windows = {
        epoch: (int(v["mjd_start"]), int(v["mjd_end"]))
        for epoch, v in json.loads(
            (d / "epoch_window_bounds.json").read_text(encoding="utf-8"))["epochs"].items()
    }
    return {
        "obs": {r["obs_id"]: r for r in delimited(d / "obs_capture_index.csv", ",")},
        "windows": windows,
        "dark": {(r["instrument"], r["band"], r["epoch"]): int(r["dark_current_counts"])
                 for r in delimited(d / "pedestal_authoritative.csv", ",")},
        "gain": {k: int(v) for k, v in json.loads(
            (d / "quantum_yield_micro.json").read_text(encoding="utf-8"))["channels"].items()},
        "fold": {(r["written_label"], r["epoch"]): r["resolved_channel"]
                 for r in delimited(d / "channel_lineage_fold.psv", "|")},
        "nonlin": horner_coefficients(d / "response_curve_horner.yaml"),
        "drift": drift_table(d / "thermal_drift_ppm.yml"),
        "factor": workbook_factors(d / "gain_scale_workbook.xlsx"),
        "full_well": {r["instrument"]: int(r["full_well_counts"])
                      for r in delimited(d / "full_well_capacity.tsv", "\t")},
    }


def chain(obs_id: str, tables: dict, show: bool) -> dict:
    o = tables["obs"][obs_id]
    instrument, band, mjd = o["instrument"], o["band"], int(o["mjd"])
    epoch = next(e for e, (lo, hi) in sorted(tables["windows"].items()) if lo <= mjd < hi)
    lo, hi = tables["windows"][epoch]

    raw = int(o["raw_counts"])
    ceiling = tables["full_well"][instrument]
    saturated = raw > ceiling
    effective = ceiling if saturated else raw
    dark = tables["dark"][(instrument, band, epoch)]
    net = effective - dark

    coefficients = tables["nonlin"][instrument]
    acc = Decimal(0)
    for c in coefficients:
        acc = acc * Decimal(net) + Decimal(c)
    linearized = half_even(acc / Decimal(1_000_000))

    channel = tables["fold"][(o["gain_label"], epoch)]
    yield_micro = tables["gain"][channel]
    gained = Decimal(linearized) * Decimal(yield_micro) / Decimal(1_000_000)

    factor = tables["factor"][instrument]
    scaled = gained * Decimal(factor) / Decimal(1_000_000)

    ppm = tables["drift"][(instrument, epoch)]
    correction = half_even(scaled * Decimal(ppm) / Decimal(1_000_000))
    drifted = scaled - Decimal(correction)
    flux = half_even(drifted)

    if show:
        print(f"  observation {obs_id}: instrument {instrument}, band {band}, "
              f"written gain label {o['gain_label']}, mjd {mjd}")
        print(f"  epoch       mjd {mjd} falls in the half-open window "
              f"{lo} up to {hi}, so epoch = {epoch}")
        print(f"  stage 1 clip          raw_counts {raw} against full well {ceiling} "
              f"= effective_counts {effective}, saturated {str(saturated).lower()}")
        print(f"  stage 2 dark          effective_counts {effective} minus dark current "
              f"{dark} = net_counts {net}")
        print(f"  stage 3 nonlinearity  Horner on net with coefficients "
              f"{coefficients} (stored x1e6), divided by 1e6 half-even "
              f"= linearized {linearized}")
        print(f"  stage 4 gain          label {o['gain_label']} in {epoch} folds to "
              f"channel {channel}; {linearized} x {yield_micro} / 1e6 = {gained}")
        print(f"  stage 5 scale         x workbook factor_micro {factor} / 1e6 "
              f"= {scaled}")
        print(f"  stage 6 drift         {ppm} ppm of {scaled} = {correction}, "
              f"SUBTRACTED, giving {drifted}")
        print(f"  stage 7 quantize      half-even of {drifted} "
              f"= calibrated_flux_ujy {flux}")
    return {"epoch": epoch, "effective_counts": effective, "saturated": saturated,
            "net_counts": net, "linearized": linearized,
            "resolved_channel": channel, "drift_ppm": ppm,
            "drift_correction": correction, "calibrated_flux_ujy": flux}


def main(argv: list[str]) -> int:
    data_dir, out_dir, label, show = argv[1], argv[2], argv[3], argv[4] == "show"
    tables = load(data_dir)
    report = json.loads(
        (Path(out_dir) / "reconciled_flux.json").read_text(encoding="utf-8"))
    entries = {e["obs_id"]: e for e in report["observations"]}
    obs_id = sorted(entries)[0]

    expected = chain(obs_id, tables, show)
    actual = entries[obs_id]
    fields = ["epoch", "effective_counts", "saturated", "net_counts", "linearized",
              "resolved_channel", "drift_ppm", "drift_correction",
              "calibrated_flux_ujy"]
    bad = [f for f in fields if actual[f] != expected[f]]
    if bad:
        print(f"[verify] {label}: independent re-derivation disagrees on {bad}",
              file=sys.stderr)
        print(f"  independent {expected}", file=sys.stderr)
        print(f"  program     {actual}", file=sys.stderr)
        return 1
    print(f"[verify] {label}: independent re-derivation of {obs_id} agrees with the "
          f"delivered program on all {len(fields)} stage fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
INDEPENDENT

python3 "${WORK}/independent.py" "${WORK}/data_altered" "${WORK}/out_altered" \
  "altered-table extract" quiet
echo "[verify] the altered-table extract is validated on its figures, so the program "\
"generalizes to reference tables it has never seen"

# --- check 4: the exposure ledger is read, not assumed ---------------------
# Separate from check 3: that one moves the reconciliation tables, this one moves
# only the integration times, which no table above the settlement layer carries.
echo "[verify] run 5: integration times moved, checking every settled rate follows them"
cp -R "${DATA_DIR}" "${WORK}/data_exposure"
python3 - "${WORK}/data_exposure" <<'LEDGER'
"""Scale every completed frame's integration time. An aborted shutter keeps its
0 ms, so the set of frames S1 holds out of the settlement does not move and the
only thing under test is whether the settled rates track the ledger."""
import pathlib
import sys

path = pathlib.Path(sys.argv[1]) / "exposure_ledger.csv"
lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]
out = [lines[0]]
moved = 0
for line in lines[1:]:
    obs_id, exposure_ms, shutter = line.split(",")
    if int(exposure_ms):
        exposure_ms = str(int(exposure_ms) * 3 + 1500)
        moved += 1
    out.append(",".join([obs_id, exposure_ms, shutter]))
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"[verify] moved the integration time of {moved} frames in exposure_ledger.csv")
LEDGER
mkdir -p "${WORK}/out_exposure"
python3 "${PROG}" "${WORK}/data_exposure" "${WORK}/out_exposure"
python3 - "${WORK}/data_exposure" "${WORK}/out_exposure" <<'CHECK_LEDGER'
"""Re-derive every settled rate from the altered ledger with the S1 floor
division, independently of the delivered program, and compare."""
import csv
import json
import pathlib
import sys

data, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
with (data / "exposure_ledger.csv").open(newline="", encoding="utf-8") as fh:
    ledger = {r["obs_id"]: int(r["exposure_ms"]) for r in csv.DictReader(fh)}
rates = json.loads((out / "settled_rates.json").read_text(encoding="utf-8"))["rates"]
bad = []
for row in rates:
    held = ledger[row["obs_id"]]
    if row["exposure_ms"] != held:
        bad.append((row["obs_id"], "exposure_ms", row["exposure_ms"], held))
        continue
    want = (row["calibrated_flux_ujy"] * 1_000_000) // held
    if row["rate_ujy_per_ks"] != want:
        bad.append((row["obs_id"], "rate_ujy_per_ks", row["rate_ujy_per_ks"], want))
if bad:
    print(f"[verify] moved-ledger run FAILED on {len(bad)}: {bad[:3]}", file=sys.stderr)
    raise SystemExit(1)
print(f"[verify] moved-ledger run OK: all {len(rates)} settled rates follow the altered "
      f"integration times under the S1 floor division")
CHECK_LEDGER

# --- check 5: the published calibration slice is reproduced ----------------
# The slice observations are not in the shipped extract, so they are appended to
# a copy of it and the program's own figures are compared against the published
# expected values.
echo "[verify] run 6: published calibration slice, checking the figures are reproduced"
cp -R "${DATA_DIR}" "${WORK}/data_slice"
python3 - "${WORK}/data_slice" <<'SLICE'
"""Append the published calibration-slice observations to the extract. Each one
needs a row in the observation stream and a row in the exposure ledger, and a
pixel outside the relay graph so the closure leaves its flux where it lands."""
import json
import pathlib
import sys

d = pathlib.Path(sys.argv[1])
rows = json.loads((d / "worked_reference_slice.json").read_text(encoding="utf-8"))["observations"]
obs_path, ledger_path = d / "obs_capture_index.csv", d / "exposure_ledger.csv"
obs_lines = [ln for ln in obs_path.read_text(encoding="utf-8").splitlines() if ln]
ledger_lines = [ln for ln in ledger_path.read_text(encoding="utf-8").splitlines() if ln]
for n, r in enumerate(rows, 1):
    obs_lines.append(",".join([r["obs_id"], r["instrument"], r["band"], str(r["mjd"]),
                               r["written_gain_label"], str(r["raw_counts"]),
                               f"pcal{n:03d}", "ok"]))
    ledger_lines.append(f'{r["obs_id"]},60000,complete')
obs_path.write_text("\n".join(obs_lines) + "\n", encoding="utf-8")
ledger_path.write_text("\n".join(ledger_lines) + "\n", encoding="utf-8")
print(f"[verify] added the {len(rows)} published calibration-slice observations")
SLICE
mkdir -p "${WORK}/out_slice"
python3 "${PROG}" "${WORK}/data_slice" "${WORK}/out_slice"
python3 - "${WORK}/data_slice" "${WORK}/out_slice" <<'CHECK_SLICE'
"""Compare the program's reconciliation of each published slice observation
against every expected stage figure worked_reference_slice.json publishes."""
import json
import pathlib
import sys

d, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
published = json.loads(
    (d / "worked_reference_slice.json").read_text(encoding="utf-8"))["observations"]
produced = {e["obs_id"]: e for e in json.loads(
    (out / "reconciled_flux.json").read_text(encoding="utf-8"))["observations"]}
FIELDS = [("expected_epoch", "epoch"),
          ("expected_net_counts", "net_counts"),
          ("expected_linearized", "linearized"),
          ("expected_resolved_channel", "resolved_channel"),
          ("expected_drift_ppm", "drift_ppm"),
          ("expected_drift_correction", "drift_correction"),
          ("expected_calibrated_flux_ujy", "calibrated_flux_ujy")]
bad = []
for row in published:
    mine = produced.get(row["obs_id"])
    if mine is None:
        bad.append((row["obs_id"], "missing from reconciled_flux.json"))
        continue
    for published_key, mine_key in FIELDS:
        if mine[mine_key] != row[published_key]:
            bad.append((row["obs_id"], mine_key, mine[mine_key], row[published_key]))
if bad:
    print(f"[verify] calibration slice FAILED: {bad[:4]}", file=sys.stderr)
    raise SystemExit(1)
print(f"[verify] calibration slice OK: all {len(published)} published observations "
      f"reproduced on every one of the {len(FIELDS)} stage figures")
for row in published:
    print(f"    {row['obs_id']}: raw {row['raw_counts']} -> net "
          f"{row['expected_net_counts']} -> linearized {row['expected_linearized']} "
          f"-> channel {row['expected_resolved_channel']} -> calibrated_flux_ujy "
          f"{row['expected_calibrated_flux_ujy']}")
CHECK_SLICE

# --------------------------------------------------------------------------
# Closing report. Every figure is read back out of the artifacts the run wrote
# or re-derived from the extract, so the message and the artifacts agree.
# --------------------------------------------------------------------------
echo
echo "================ reconciliation report ================"
ls -1 "${OUT_DIR}"
echo

echo "Correction-stage application order, as implemented:"
echo "  1 clip  ->  2 dark  ->  3 nonlinearity  ->  4 gain  ->  5 scale  ->  6 drift  ->  7 quantize"
echo "That order is fixed by the section 'Pipeline (correct application order)' of"
echo "${DATA_DIR}/reconciliation_contract.md, whose numbered list runs CLIP at the"
echo "detector full well, DARK,"
echo "NONLINEARITY (before gain), GAIN on the resolved channel, SCALE, DRIFT"
echo "(subtracted) and QUANTIZE with banker's rounding. The same section warns that"
echo "the order the correction files are shipped in is a different order, and"
echo "pipeline_order_note.txt repeats the warning, so the file-listing order was"
echo "rejected deliberately."
echo

echo "Worked arithmetic chain for one observation, re-derived from the extract"
echo "independently of the delivered program:"
python3 "${WORK}/independent.py" "${DATA_DIR}" "${OUT_DIR}" "shipped extract" show
echo

echo "Dead-pixel closure, and why it is a least fixed point:"
echo "relay_closure_rule.json sets resolution to least_fixed_point, order to"
echo "ascending_pixel_id and split to even_remainder_to_first_target, and the"
echo "'Dead-pixel redistribution' section of reconciliation_contract.md states that a"
echo "masked pixel relays its FULLY ACCUMULATED flux. A target of a masked pixel may"
echo "itself be masked, so the amount a pixel relays depends on the amounts relayed"
echo "into it: the definition is recursive, and its solution is the least fixed point"
echo "of that relay map. One pass over base flux would relay only pre-redistribution"
echo "amounts and would lose every hop past the first, which the contract calls out as"
echo "wrong wherever a chain runs longer than one hop. The implementation resolves each"
echo "pixel on demand and caches the result, so a chain of any length reaches the same"
echo "fixed point, and the relay graph is a DAG over ascending pixel ids, which is what"
echo "makes the recursion terminate; a cycle guard turns a malformed graph into an error"
echo "rather than unbounded recursion."
echo

echo "Exposure attribution, and why the parts add up:"
echo "exposure_weight_micro.tsv publishes one integer weight per instrument, and the"
echo "'Exposure attribution' section of reconciliation_contract.md fixes the"
echo "largest-remainder rule: floor each exact share pool*w(i)/W toward negative"
echo "infinity, then hand the leftover micro-jansky one at a time to the largest"
echo "fractional remainders, ties going to the lower instrument name. Shares are"
echo "compared as exact integer remainders over the common denominator W, never as"
echo "floats, which is what makes the four attributed amounts sum to the pool exactly."
echo "Rounding each share on its own would leave the parts off by up to two."
echo
echo "Relay audit, hop by hop:"
echo "relay_audit.json reports, for each masked pixel, the FULLY ACCUMULATED amount it"
echo "relays rather than its base flux, how that amount split across its targets with"
echo "the leftover to the first, and the unmasked pixels the flux finally reaches,"
echo "following masked hops transitively. A target that is itself masked is not a"
echo "terminal pixel, so a chain of any length resolves to the pixels that keep the"
echo "flux rather than to the next hop."
echo

python3 - "${OUT_DIR}" <<'HEADLINE'
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
closure = json.loads((out / "deadpixel_closure.json").read_text(encoding="utf-8"))
dropped = json.loads((out / "dropped_observations.json").read_text(encoding="utf-8"))
quality = json.loads((out / "data_quality.json").read_text(encoding="utf-8"))
attribution = json.loads((out / "flux_attribution.json").read_text(encoding="utf-8"))
audit = json.loads((out / "relay_audit.json").read_text(encoding="utf-8"))

print("Headline figures, read back out of the written artifacts:")
print("  observations in extract   :", summary["observation_count"])
print("  live after adjudication   :", summary["live_count"])
print("  dropped by the dossier    :", summary["dropped_count"],
      dropped["dropped_obs_ids"])
print("  masked pixels             :", closure["masked_pixel_count"])
print("  total_reconciled_flux_ujy :", summary["total_reconciled_flux_ujy"])
print("  total after closure       :", closure["total_after_closure_ujy"])
print("  per-band flux             :", summary["band_flux_ujy"])
print("  per-epoch flux            :", summary["epoch_flux_ujy"])
print("  saturated observations    :", quality["saturated_count"],
      quality["saturated_obs_ids"])
print("  attributed by exposure    :", attribution["attributed_ujy"])
print("  attributed sum            :", sum(attribution["attributed_ujy"].values()),
      "against pool", attribution["pool_ujy"])
print("  remainder recipients      :", attribution["remainder_recipients"])
print("  relay audit entries       :", len(audit["relays"]),
      "for", audit["masked_pixel_count"], "masked pixels")
HEADLINE

echo
python3 - "${OUT_DIR}" <<'SETTLE'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
def load(name):
    return json.loads((out / name).read_text(encoding="utf-8"))

summ = load("settlement_summary.json")
rates = load("settled_rates.json")["rates"]
bursts = load("cosmic_ray_rejects.json")["rejects"]
near = load("near_saturation.json")["observations"]
order = load("settlement_order.json")["order"]
shares = load("settled_attribution.json")

print("Settlement layer, as implemented:")
print("  The settlement layer is fixed by the 'Settlement layer' section of")
print("  reconciliation_contract.md, sections S1 to S8. It runs after dead-pixel")
print("  closure and revises no figure of the reconciliation layer above it.")
print()
print("S1 rounding mode. The settled rate is")
print("    rate_ujy_per_ks = floor(calibrated_flux_ujy * 1000000 / exposure_ms)")
print("  a FLOOR division that truncates toward negative infinity. Section S1 states")
print("  this is the one place in the contract that does NOT use banker's rounding,")
print("  so the half-even habit every other stage teaches was rejected deliberately.")
sample = rates[0]
print(f"  Worked rate for observation {sample['obs_id']}: calibrated flux "
      f"{sample['calibrated_flux_ujy']} x 1000000 / exposure {sample['exposure_ms']} ms "
      f"= {sample['rate_ujy_per_ks']} after the floor.")
print()
print("S2 cosmic ray rejection. The threshold of each instrument-and-band group is")
print("    threshold = median + 6 * median_absolute_deviation")
print("  with the median absolute deviation used UNSCALED, carrying no 1.4826")
print("  consistency factor.")
if bursts:
    b = bursts[0]
    print(f"  Worked threshold for group {b['instrument']} band {b['band']}: median "
          f"{b['group_median']} + 6 x mad {b['group_mad']} = {b['threshold']}, and "
          f"observation {b['obs_id']} at rate {b['rate_ujy_per_ks']} exceeds it, so it "
          f"is rejected.")
print("  S2 states two absolute exemptions. A group holding FEWER THAN FOUR settled")
print("  observations is too small a sample to reject from, so every observation of")
print("  such a group survives however large its rate is. And a near-saturated")
print("  observation survives rejection, because its rate is the ceiling of the")
print("  detector showing through rather than a cosmic ray hit.")
print()
print("S3 median convention. A settlement median over an EVEN sample takes the LOWER")
print("  of its two middle values, never their mean. This differs from the band median")
print("  of the reconciliation layer above, which keeps the banker's rounding of its")
print("  two middle values, so the two layers settle an even sample differently.")
print()
print("S4 band order. Every settlement artifact orders bands in the photometric order")
print("  u, g, r, i, z, fixed by section S4, and never in the alphabetical order of the")
print("  band letters.")
print()
print(f"S5 and S7. The settled pool is {summ['settled_pool_ujy']} over "
      f"{summ['settled_count']} surviving observations. The digest is the positional")
print("  sum over the S7 order, reduced by the modulus:")
print(f"    settlement_digest = (sum over i of i * rate(i)) mod 1000003 = "
      f"{summ['settlement_digest']}")
if order:
    head = ", ".join(f"{e['position']}x{e['rate_ujy_per_ks']}" for e in order[:3])
    print(f"  The first terms of that sum are {head}, continuing to position "
          f"{order[-1]['position']}.")
print()
att = shares["attributed_ujy"]
print("S6 settled attribution. The settled pool is apportioned across the four")
print("  instruments by largest remainder:")
for k in sorted(att):
    print(f"    {k}: {att[k]}")
print(f"  Those four amounts sum to {sum(att.values())}, which equals the settled pool "
      f"{shares['settled_pool_ujy']} exactly.")
print()
print(f"S1 aborted frames. {summ['zero_exposure_count']} frames carry a shutter state of")
print("  aborted and an exposure of 0 ms, so they measured nothing and are held out of")
print("  the settlement entirely, carrying no settled rate.")
print(f"S8 near saturation. {summ['near_saturated_count']} observations reach 98 percent")
print("  of their instrument's full well while staying at or below that ceiling, by the")
print("  integer test raw_counts * 100 >= full_well_counts * 98.")
SETTLE

echo
echo "Verification actually run, in order: a second run of the delivered program on"
echo "the shipped extract compared byte for byte over all ${ART_COUNT} artifacts; a run on an"
echo "extract with the observation rows reversed, compared the same way; a run on"
echo "an extract whose dark-current, quantum-yield, drift and workbook scale-factor"
echo "tables all hold different values, validated against an independent re-derivation"
echo "of one observation; a run on an extract whose exposure ledger holds different"
echo "integration times, with every settled rate re-derived from the altered ledger"
echo "under the S1 floor division; and a run on an extract carrying the published"
echo "calibration slice, with all three published observations reproduced on every"
echo "stage figure. All five passed before this report was written."
echo "======================================================="
