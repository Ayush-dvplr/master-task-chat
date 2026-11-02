"""Verifier for the detector-flux-reconciliation domain-calculation task.

Deterministic channel. Grades the agent's reusable reconciliation program two
ways: the artifacts it delivered for the shipped extract, against values fixed
at authoring time, and the program itself, re-run against fresh seeded extracts
in the same schema (including a mutation suite that perturbs one reference
table at a time).

Self-contained: standard library only. The verifier embeds a reference
reconciliation and a corpus writer that emits every machine readable file the
shipped extract carries, together with abridged copies of the written contract
and the secondary files it points at, so a program that reads any documented
input runs unchanged here. The embedded prose copies cover the reconciliation
stages only and are not a substitute for the shipped contract: nothing parses
them at grade time, and no check reads a figure out of them.
It never reads /app/data, which does not exist in the grading container.

Every check returns a bool and never raises: an exception inside a check would
abort the whole run and no reward would be written.

Negative checks are named negative_<cheat>, return True when the cheat is
present, and carry a negative weight.
"""
from __future__ import annotations

import ast
import csv
import io
import json
import os
import shutil
import signal
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

# Seeds. Every check that re-runs the agent program owns its own seed, so no
# two checks can settle the same observable on the same corpus.
EVAL_SEED = 9149160939383064613
CHALLENGE_SEED = 5908777262602933415
THIRD_EVAL_SEED = 3840751926304815773
FOURTH_EVAL_SEED = 7261594038172650429
FIFTH_EVAL_SEED = 5019473628150739861
SCALE_SEED = 1511527706963956821
DRIFT_SEED = 7284471833126880413
EPOCH_SEED = 4023985210773316609
FOLD_SEED = 6617390449201558327
MASK_SEED = 8850264137744092951
DISPUTE_SEED = 3112908557640231489
NAIVE_SEED = 2298640175533908741
PRECEDENCE_SEED = 4471620938155073829
ROWORDER_SEED = 7763410285529147033
ATTRIB_SEED = 8204517763390118529
RELAY_SEED = 2951480617332904471
SETTLE_RATE_SEED = 6294817350269148377
ABORT_SEED = 3718095462730518849
COSMIC_SEED = 8156204739158260913
SMALL_COHORT_SEED = 5073916284017539261
NEAR_SAT_SEED = 2640518397461085723
EVEN_SAMPLE_SEED = 9418502637150284961
DIGEST_SEED = 4185063927518204673
BAND_ORDER_SEED = 7592418036294157089
SETTLE_ATTRIB_SEED = 1836470925183604517
EXPOSURE_MOVE_SEED = 6051937284160395243
# The tie corpus is pinned to the seed and size whose closure total leaves three
# micro-jansky over when the four exposure weights are equal, so all four
# remainders tie and the award order is the whole observable.
TIE_SEED = 7705
TIE_SIZE = 150
EQUAL_EXPOSURE = {"G1": 1_000_000, "G2": 1_000_000, "G3": 1_000_000, "G4": 1_000_000}

BANDS = ("u", "g", "r", "i", "z")
# Contract S4: the settlement layer orders bands photometrically. BANDS already
# happens to be in that order, so this alias exists to make the places that
# depend on the photometric contract explicit rather than incidental.
PHOTOMETRIC_BANDS = ("u", "g", "r", "i", "z")
EXPOSURE_LADDER = (30000, 45000, 60000, 90000, 120000)
# The explicit fixtures below predate the settlement layer and declare no
# integration time. build_corpus writes this default into their ledger and
# ref_settle reads it back through the same two helpers, so the corpus the agent
# is handed and the expectation it is graded against can never disagree.
DEFAULT_EXPOSURE_MS = 60000
SETTLEMENT_MODULUS = 1_000_003
COSMIC_RAY_SIGMA = 6
MIN_REJECTION_SAMPLE = 4
NEAR_SATURATION_PERCENT = 98
INSTRUMENTS = ("G1", "G2", "G3", "G4")
EPOCHS = ("E1", "E2", "E3")
EPOCH_MJD = {"E1": (59000, 59120), "E2": (59120, 59240), "E3": (59240, 59360)}
GAIN_LABELS_WRITEABLE = ("A0", "B0", "C1")
GAIN_CHANNELS = ("A0", "A2", "B0", "B3", "C1")
REPORT_ID = "detector-flux-reconciliation"

ARTIFACT_NAMES = [
    "reconciled_flux.json", "summary.json", "calibration_audit.json",
    "data_quality.json", "instrument_G1.json", "instrument_G2.json",
    "instrument_G3.json", "instrument_G4.json", "epoch_totals.json",
    "deadpixel_closure.json", "band_rollup.csv", "epoch_rollup.tsv",
    "instrument_rollup.psv", "flagged_observations.xml",
    "objective_summary.yaml", "reconciliation_report.md",
    "run_status.txt", "provenance_manifest.json", "anomaly_ledger.json",
    "ordered_flux_index.json", "dropped_observations.json",
    "flux_attribution.json", "relay_audit.json",
    "settlement_summary.json", "settled_rates.json", "zero_exposure.json",
    "cosmic_ray_rejects.json", "near_saturation.json",
    "settled_attribution.json", "band_settlement.csv",
    "settlement_order.json", "cell_G1_u.json", "cell_G1_g.json",
    "cell_G1_r.json", "cell_G1_i.json", "cell_G1_z.json",
    "cell_G2_u.json", "cell_G2_g.json", "cell_G2_r.json",
    "cell_G2_i.json", "cell_G2_z.json", "cell_G3_u.json",
    "cell_G3_g.json", "cell_G3_r.json", "cell_G3_i.json",
    "cell_G3_z.json", "cell_G4_u.json", "cell_G4_g.json",
    "cell_G4_r.json", "cell_G4_i.json", "cell_G4_z.json", "grid_E1_u.psv",
    "grid_E1_g.psv", "grid_E1_r.psv", "grid_E1_i.psv", "grid_E1_z.psv",
    "grid_E2_u.psv", "grid_E2_g.psv", "grid_E2_r.psv", "grid_E2_i.psv",
    "grid_E2_z.psv", "grid_E3_u.psv", "grid_E3_g.psv", "grid_E3_r.psv",
    "grid_E3_i.psv", "grid_E3_z.psv", "span_G1_E1.tsv", "span_G1_E2.tsv",
    "span_G1_E3.tsv", "span_G2_E1.tsv", "span_G2_E2.tsv",
    "span_G2_E3.tsv", "span_G3_E1.tsv", "span_G3_E2.tsv",
    "span_G3_E3.tsv", "span_G4_E1.tsv", "span_G4_E2.tsv", "span_G4_E3.tsv",
]

CORE_JSON = [
    "summary.json", "reconciled_flux.json", "calibration_audit.json",
    "epoch_totals.json", "deadpixel_closure.json", "anomaly_ledger.json",
    "ordered_flux_index.json", "dropped_observations.json",
    "provenance_manifest.json", "data_quality.json", "instrument_G1.json",
    "instrument_G2.json", "instrument_G3.json", "instrument_G4.json",
    "flux_attribution.json", "relay_audit.json",
    "settlement_summary.json", "settled_rates.json", "zero_exposure.json",
    "cosmic_ray_rejects.json", "near_saturation.json",
    "settled_attribution.json", "settlement_order.json", "cell_G1_u.json",
    "cell_G1_g.json", "cell_G1_r.json", "cell_G1_i.json",
    "cell_G1_z.json", "cell_G2_u.json", "cell_G2_g.json",
    "cell_G2_r.json", "cell_G2_i.json", "cell_G2_z.json",
    "cell_G3_u.json", "cell_G3_g.json", "cell_G3_r.json",
    "cell_G3_i.json", "cell_G3_z.json", "cell_G4_u.json",
    "cell_G4_g.json", "cell_G4_r.json", "cell_G4_i.json", "cell_G4_z.json",
]


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = (seed & 0xFFFFFFFFFFFFFFFF) or 0xA0761D6478BD642F

    def _next(self) -> int:
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x & 0xFFFFFFFFFFFFFFFF
        return (self.state * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rint(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def pick(self, seq) -> Any:
        return seq[self._next() % len(seq)]


def _half_even(v: Decimal) -> int:
    return int(v.quantize(Decimal("1"), ROUND_HALF_EVEN))


def _median_half_even(values: list[int]) -> int:
    """Banker's rounding on the median, as rounding_primer.txt mandates for
    every quantization in this contract."""
    return _half_even(Decimal(statistics.median(sorted(values))))


def base_tables() -> dict[str, Any]:
    return {
        "factor_micro": {"G1": 1_040_000, "G2": 985_000, "G3": 1_012_500, "G4": 1_000_000},
        "gain_micro": {"A0": 2_100_000, "A2": 1_950_000, "B0": 3_050_000, "B3": 2_875_000, "C1": 2_500_000},
        "nonlin": {"G1": [3, 1_000_000, 0], "G2": [5, 998_000, 12_000],
                   "G3": [2, 1_003_000, -8_000], "G4": [4, 1_000_000, 0]},
        "epoch_mjd": {k: list(v) for k, v in EPOCH_MJD.items()},
        "full_well": {"G1": 62_000, "G2": 61_500, "G3": 63_000, "G4": 60_500},
        "exposure_micro": {"G1": 1_000_000, "G2": 1_250_000, "G3": 875_000, "G4": 1_375_000},
    }


def dark_current(instr: str, band: str, epoch: str) -> int:
    base = {"u": 40, "g": 32, "r": 25, "i": 30, "z": 55}[band]
    ib = {"G1": 5, "G2": 8, "G3": 3, "G4": 6}[instr]
    ep = {"E1": 0, "E2": 4, "E3": 9}[epoch]
    return base + ib + ep


def drift_ppm(instr: str, epoch: str) -> int:
    base = {"G1": 1200, "G2": 800, "G3": 1500, "G4": 600}[instr]
    ep = {"E1": 0, "E2": 150, "E3": 300}[epoch]
    return base + ep


def epoch_of_mjd(mjd: int, windows: dict[str, list[int]]) -> str:
    for ep in EPOCHS:
        lo, hi = windows[ep]
        if lo <= mjd < hi:
            return ep
    return "UNKNOWN"


def resolve_channel(written: str, mjd: int, windows: dict[str, list[int]]) -> str:
    if mjd >= windows["E2"][0] and written == "A0":
        return "A2"
    if mjd >= windows["E3"][0] and written == "B0":
        return "B3"
    return written


def horner(coeffs: list[int], x: int) -> int:
    acc = Decimal(0)
    xd = Decimal(x)
    for c in coeffs:
        acc = acc * xd + Decimal(c)
    return _half_even(acc / Decimal(1_000_000))


def build_observations(seed: int, n: int, mutations: dict[str, Any] | None = None) -> list[dict]:
    mutations = mutations or {}
    rng = Rng(seed)
    windows = mutations.get("epoch_mjd") or {k: list(v) for k, v in EPOCH_MJD.items()}
    obs = []
    for i in range(1, n + 1):
        instr = rng.pick(INSTRUMENTS)
        band = rng.pick(BANDS)
        ep = rng.pick(EPOCHS)
        lo, hi = windows[ep]
        mjd = rng.rint(lo, hi - 1)
        written = rng.pick(GAIN_LABELS_WRITEABLE)
        raw = rng.rint(200, 60000)
        pixel = f"p{rng.rint(1, max(8, n // 3)):05d}"
        qflag = "suspect" if rng.rint(1, 100) <= 12 else "ok"
        exposure = EXPOSURE_LADDER[rng.rint(0, len(EXPOSURE_LADDER) - 1)]
        shutter = "complete"
        if rng.rint(1, 100) <= mutations.get("abort_rate", 2):
            exposure, shutter = 0, "aborted"
        obs.append({"obs_id": f"o{i:05d}", "instrument": instr, "band": band,
                    "mjd": mjd, "written_gain": written, "raw_counts": raw,
                    "pixel": pixel, "quality_flag": qflag,
                    "exposure_ms": exposure, "shutter_state": shutter})
    if mutations.get("exposure_scale"):
        for o in obs:
            if o["exposure_ms"]:
                o["exposure_ms"] = o["exposure_ms"] * mutations["exposure_scale"]
    # Contract S8 needs a corpus that actually reaches 98 percent of the ceiling
    # without crossing it, which uniform raw_counts almost never produce.
    wells = dict(base_tables()["full_well"])
    wells.update(mutations.get("full_well") or {})
    for o in obs[:mutations.get("near_ceiling", 0)]:
        o["raw_counts"] = wells[o["instrument"]] - 1
        o["exposure_ms"] = o["exposure_ms"] or EXPOSURE_LADDER[0]
        o["shutter_state"] = "complete"
    return obs


def build_deadpixel_map(seed: int, obs: list[dict], mutations: dict[str, Any] | None = None) -> dict[str, list[str]]:
    mutations = mutations or {}
    rng = Rng(seed ^ 0x5EEDDEAD)
    pixels = sorted({o["pixel"] for o in obs})
    masked: dict[str, list[str]] = {}
    rate = 30 if mutations.get("more_masking") else 15
    for idx, px in enumerate(pixels):
        if rng.rint(1, 100) <= rate and idx < len(pixels) - 1:
            k = rng.rint(1, 2)
            targets = [pixels[rng.rint(idx + 1, len(pixels) - 1)] for _ in range(k)]
            masked[px] = sorted(set(targets))
    return masked


def build_disputed(seed: int, obs: list[dict]) -> set[str]:
    rng = Rng(seed ^ 0x0D15DEED)
    return {o["obs_id"] for o in obs if rng.rint(1, 100) <= 6}


def tables_for(mutations: dict[str, Any] | None) -> dict[str, Any]:
    t = base_tables()
    mutations = mutations or {}
    if "factor_micro" in mutations:
        t["factor_micro"] = dict(t["factor_micro"])
        t["factor_micro"].update(mutations["factor_micro"])
    if "gain_micro" in mutations:
        t["gain_micro"] = dict(t["gain_micro"])
        t["gain_micro"].update(mutations["gain_micro"])
    if "epoch_mjd" in mutations:
        t["epoch_mjd"] = mutations["epoch_mjd"]
    if "full_well" in mutations:
        t["full_well"] = dict(t["full_well"])
        t["full_well"].update(mutations["full_well"])
    if "exposure_micro" in mutations:
        t["exposure_micro"] = dict(t["exposure_micro"])
        t["exposure_micro"].update(mutations["exposure_micro"])
    return t


def reconcile_one(o: dict, tables: dict[str, Any], mutations: dict[str, Any] | None = None) -> dict:
    mutations = mutations or {}
    windows = tables["epoch_mjd"]
    epoch = epoch_of_mjd(o["mjd"], windows)
    ceiling = tables["full_well"][o["instrument"]]
    saturated = o["raw_counts"] > ceiling
    effective = ceiling if saturated else o["raw_counts"]
    net = effective - dark_current(o["instrument"], o["band"], epoch)
    lin = horner(tables["nonlin"][o["instrument"]], net)
    channel = resolve_channel(o["written_gain"], o["mjd"], windows)
    g = Decimal(lin) * Decimal(tables["gain_micro"][channel]) / Decimal(1_000_000)
    s = g * Decimal(tables["factor_micro"][o["instrument"]]) / Decimal(1_000_000)
    dppm = drift_ppm(o["instrument"], epoch)
    if "drift_bump" in mutations:
        dppm += mutations["drift_bump"]
    drift_corr = _half_even(s * Decimal(dppm) / Decimal(1_000_000))
    d = s - Decimal(drift_corr)
    return {"epoch": epoch, "effective_counts": effective, "saturated": saturated,
            "net": net, "lin": lin, "channel": channel,
            "drift_ppm": dppm, "drift_correction": drift_corr,
            "calibrated_flux_ujy": _half_even(d)}


def _split(amount: int, targets: list[str]) -> dict[str, int]:
    share = amount // len(targets)
    rem = amount - share * len(targets)
    return {t: share + (rem if k == 0 else 0) for k, t in enumerate(targets)}


def fixpoint(base_flux: dict[str, int], masked: dict[str, list[str]]) -> tuple[dict[str, int], dict[str, int]]:
    """Resolved flux per pixel, plus the fully accumulated amount each masked
    pixel relays, which is what relay_audit.json reports."""
    universe = set(base_flux) | set(masked)
    for ts in masked.values():
        universe.update(ts)
    pixels = sorted(universe)
    resolved = {px: base_flux.get(px, 0) for px in pixels}
    relayed: dict[str, int] = {}
    for px in pixels:
        if px in masked:
            amount = resolved[px]
            relayed[px] = amount
            for t, share in _split(amount, masked[px]).items():
                resolved[t] += share
            resolved[px] = 0
    return resolved, relayed


def _terminals(pixel: str, masked: dict[str, list[str]]) -> list[str]:
    seen: set[str] = set()
    out: set[str] = set()
    stack = list(masked.get(pixel, ()))
    while stack:
        px = stack.pop()
        if px in seen:
            continue
        seen.add(px)
        if px in masked:
            stack.extend(masked[px])
        else:
            out.add(px)
    return sorted(out)


def _attribute(pool: int, weight_micro: dict[str, int]) -> dict[str, Any]:
    """Largest-remainder apportionment compared on exact integer remainders over
    the common denominator, so the parts sum to the pool exactly."""
    total_weight = sum(weight_micro[i] for i in INSTRUMENTS)
    base: dict[str, int] = {}
    rem: dict[str, int] = {}
    for i in INSTRUMENTS:
        num = pool * weight_micro[i]
        base[i] = num // total_weight
        rem[i] = num - base[i] * total_weight
    leftover = pool - sum(base.values())
    recipients = sorted(INSTRUMENTS, key=lambda i: (-rem[i], i))[:leftover]
    return {"attributed": {i: base[i] + (1 if i in recipients else 0) for i in INSTRUMENTS},
            "recipients": sorted(recipients)}


def _exposure_of(o: dict) -> int:
    return o["exposure_ms"] if "exposure_ms" in o else DEFAULT_EXPOSURE_MS


def _shutter_of(o: dict) -> str:
    return o["shutter_state"] if "shutter_state" in o else "complete"


def _median_lower(sample: list[int]) -> int:
    """Contract S3. An even sample takes its lower middle value, which is not
    what _median_half_even does for the reconciliation layer above."""
    seq = sorted(sample)
    half = len(seq) // 2
    return seq[half] if len(seq) % 2 else seq[half - 1]


def ref_settle(live: list[dict], tables: dict[str, Any]) -> dict[str, Any]:
    """Reference settlement layer, contract S1 to S8."""
    wells = tables["full_well"]

    near = []
    for row in live:
        limit = wells[row["instrument"]]
        if not row["saturated"] and row["raw_counts"] * 100 >= limit * NEAR_SATURATION_PERCENT:
            near.append({"obs_id": row["obs_id"], "instrument": row["instrument"],
                         "raw_counts": row["raw_counts"], "full_well_counts": limit})
    near.sort(key=lambda e: e["obs_id"])
    spared = {e["obs_id"] for e in near}

    paced = []
    aborted = []
    for row in sorted(live, key=lambda r: r["obs_id"]):
        held = _exposure_of(row)
        if held:
            paced.append({"obs_id": row["obs_id"], "instrument": row["instrument"],
                          "band": row["band"], "exposure_ms": held,
                          "calibrated_flux_ujy": row["calibrated_flux_ujy"],
                          "rate_ujy_per_ks": (row["calibrated_flux_ujy"] * 1_000_000) // held})
        else:
            aborted.append({"obs_id": row["obs_id"],
                            "shutter_state": _shutter_of(row)})

    cohorts: dict[tuple[str, str], list[dict]] = {}
    for row in paced:
        cohorts.setdefault((row["instrument"], row["band"]), []).append(row)
    hits = []
    for key in sorted(cohorts):
        cohort = cohorts[key]
        if len(cohort) < MIN_REJECTION_SAMPLE:
            continue
        sample = [m["rate_ujy_per_ks"] for m in cohort]
        centre = _median_lower(sample)
        spread = _median_lower([abs(v - centre) for v in sample])
        cut = centre + COSMIC_RAY_SIGMA * spread
        for member in cohort:
            if member["obs_id"] not in spared and member["rate_ujy_per_ks"] > cut:
                hits.append({"obs_id": member["obs_id"], "instrument": member["instrument"],
                             "band": member["band"],
                             "rate_ujy_per_ks": member["rate_ujy_per_ks"],
                             "group_median": centre, "group_mad": spread,
                             "threshold": cut})
    hits.sort(key=lambda e: e["obs_id"])
    struck = {e["obs_id"] for e in hits}

    kept = [r for r in paced if r["obs_id"] not in struck]
    pool = sum(r["rate_ujy_per_ks"] for r in kept)

    ranked = sorted(kept, key=lambda r: (-r["rate_ujy_per_ks"],
                                         PHOTOMETRIC_BANDS.index(r["band"]), r["obs_id"]))
    order = [{"position": n + 1, "obs_id": r["obs_id"],
              "rate_ujy_per_ks": r["rate_ujy_per_ks"]} for n, r in enumerate(ranked)]
    digest = sum(e["position"] * e["rate_ujy_per_ks"] for e in order) % SETTLEMENT_MODULUS

    shares = _attribute(pool, tables["exposure_micro"])
    bands = [[b, sum(1 for r in kept if r["band"] == b),
              sum(r["rate_ujy_per_ks"] for r in kept if r["band"] == b)]
             for b in PHOTOMETRIC_BANDS]

    return {"paced": paced, "aborted": aborted, "hits": hits, "near": near,
            "kept": kept, "pool": pool, "order": order, "digest": digest,
            "shares": shares, "bands": bands}


def ref_derive_from(obs: list[dict], tables: dict[str, Any], masked: dict[str, list[str]],
                    disputed: set[str], mutations: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reference reconciliation. Returns expected artifact contents keyed by
    artifact filename, exactly as the agent program must write them."""
    mutations = mutations or {}
    per_obs = []
    for o in obs:
        r = reconcile_one(o, tables, mutations)
        row = dict(o)
        row.update(r)
        row["disputed"] = o["obs_id"] in disputed
        row["masked"] = o["pixel"] in masked
        per_obs.append(row)
    live = [r for r in per_obs if not r["disputed"]]
    dropped = sorted(r["obs_id"] for r in per_obs if r["disputed"])

    base_flux: dict[str, int] = {}
    for r in live:
        base_flux[r["pixel"]] = base_flux.get(r["pixel"], 0) + r["calibrated_flux_ujy"]
    resolved_pixel, relayed = fixpoint(base_flux, masked)
    total_flux = sum(resolved_pixel.values())
    relays = [{"pixel": px, "relayed_ujy": relayed[px], "targets": sorted(masked[px]),
               "per_target_ujy": dict(sorted(_split(relayed[px], sorted(masked[px])).items())),
               "terminal_pixels": _terminals(px, masked)}
              for px in sorted(masked)]
    attribution = _attribute(total_flux, tables["exposure_micro"])

    def agg(keyfn):
        f: dict[str, int] = {}
        c: dict[str, int] = {}
        for r in live:
            k = keyfn(r)
            f[k] = f.get(k, 0) + r["calibrated_flux_ujy"]
            c[k] = c.get(k, 0) + 1
        return f, c

    band_flux, band_cnt = agg(lambda r: r["band"])
    epoch_flux, epoch_cnt = agg(lambda r: r["epoch"])
    instr_flux, instr_cnt = agg(lambda r: r["instrument"])
    channel_use: dict[str, int] = {}
    for r in live:
        channel_use[r["channel"]] = channel_use.get(r["channel"], 0) + 1

    eligible = [r for r in live if not r["saturated"]]
    band_values: dict[str, list[int]] = {}
    for r in eligible:
        band_values.setdefault(r["band"], []).append(r["calibrated_flux_ujy"])
    band_median = {b: _median_half_even(v) for b, v in band_values.items()}
    anomalies = []
    for r in sorted(eligible, key=lambda x: x["obs_id"]):
        if r["band"] in band_median and r["calibrated_flux_ujy"] > 3 * band_median[r["band"]]:
            anomalies.append({"obs_id": r["obs_id"], "band": r["band"],
                              "calibrated_flux_ujy": r["calibrated_flux_ujy"],
                              "band_median": band_median[r["band"]]})
    ordered = sorted(live, key=lambda r: (-r["calibrated_flux_ujy"], r["obs_id"]))
    ordered_index = [{"rank": i + 1, "obs_id": r["obs_id"],
                      "calibrated_flux_ujy": r["calibrated_flux_ujy"]}
                     for i, r in enumerate(ordered)]

    rid = REPORT_ID
    out: dict[str, Any] = {}
    out["summary.json"] = {
        "report_id": rid, "observation_count": len(per_obs), "live_count": len(live),
        "dropped_count": len(dropped), "total_reconciled_flux_ujy": total_flux,
        "band_flux_ujy": dict(sorted(band_flux.items())),
        "epoch_flux_ujy": dict(sorted(epoch_flux.items())),
        "instrument_flux_ujy": dict(sorted(instr_flux.items())),
        "channel_usage": dict(sorted(channel_use.items())),
        "band_median_ujy": dict(sorted(band_median.items()))}
    out["reconciled_flux.json"] = {"report_id": rid, "observations": [
        {"obs_id": r["obs_id"], "instrument": r["instrument"], "band": r["band"],
         "epoch": r["epoch"], "resolved_channel": r["channel"],
         "effective_counts": r["effective_counts"], "saturated": r["saturated"],
         "net_counts": r["net"],
         "linearized": r["lin"], "drift_ppm": r["drift_ppm"],
         "drift_correction": r["drift_correction"], "calibrated_flux_ujy": r["calibrated_flux_ujy"]}
        for r in sorted(live, key=lambda x: x["obs_id"])]}
    out["calibration_audit.json"] = {
        "report_id": rid, "scale_factor_micro": dict(sorted(tables["factor_micro"].items())),
        "gain_micro_e_per_count": dict(sorted(tables["gain_micro"].items())),
        "drift_ppm": {f"{i}:{e}": drift_ppm(i, e) + mutations.get("drift_bump", 0)
                      for i in INSTRUMENTS for e in EPOCHS},
        "nonlinearity_coeffs": {k: tables["nonlin"][k] for k in sorted(tables["nonlin"])},
        "epoch_windows": {e: list(tables["epoch_mjd"][e]) for e in sorted(tables["epoch_mjd"])},
        "fold_applied": sorted({f"{w}:{e}->{resolve_channel(w, tables['epoch_mjd'][e][0], tables['epoch_mjd'])}"
                                for w in GAIN_LABELS_WRITEABLE for e in EPOCHS
                                if resolve_channel(w, tables['epoch_mjd'][e][0], tables['epoch_mjd']) != w})}
    out["data_quality.json"] = {
        "report_id": rid, "input_file_count": None,
        "observation_count": len(per_obs), "disputed_count": len(dropped),
        "masked_pixel_count": len(masked), "distinct_pixels": len(resolved_pixel),
        "suspect_but_not_disputed": sorted(r["obs_id"] for r in per_obs
                                           if r["quality_flag"] == "suspect" and not r["disputed"]),
        "saturated_count": len([r for r in live if r["saturated"]]),
        "saturated_obs_ids": sorted(r["obs_id"] for r in live if r["saturated"])}
    for instr in INSTRUMENTS:
        rows = [r for r in live if r["instrument"] == instr]
        bf: dict[str, int] = {}
        ef: dict[str, int] = {}
        for r in rows:
            bf[r["band"]] = bf.get(r["band"], 0) + r["calibrated_flux_ujy"]
            ef[r["epoch"]] = ef.get(r["epoch"], 0) + r["calibrated_flux_ujy"]
        out[f"instrument_{instr}.json"] = {
            "instrument": instr, "observation_count": len(rows),
            "flux_ujy": sum(r["calibrated_flux_ujy"] for r in rows),
            "band_flux_ujy": dict(sorted(bf.items())),
            "epoch_flux_ujy": dict(sorted(ef.items()))}
    out["epoch_totals.json"] = {"report_id": rid,
                                "epoch_flux_ujy": dict(sorted(epoch_flux.items())),
                                "epoch_observation_count": dict(sorted(epoch_cnt.items()))}
    out["deadpixel_closure.json"] = {"report_id": rid, "masked_pixel_count": len(masked),
                                     "resolved_pixel_flux_ujy": dict(sorted(resolved_pixel.items())),
                                     "total_after_closure_ujy": total_flux}
    out["anomaly_ledger.json"] = {"report_id": rid,
                                  "rule": "flux > 3 * band median (live, non-saturated only)",
                                  "anomalies": anomalies}
    out["flux_attribution.json"] = {"report_id": rid, "pool_ujy": total_flux,
                                    "exposure_weight_micro": dict(sorted(tables["exposure_micro"].items())),
                                    "attributed_ujy": dict(sorted(attribution["attributed"].items())),
                                    "remainder_recipients": attribution["recipients"]}
    out["relay_audit.json"] = {"report_id": rid, "masked_pixel_count": len(masked),
                               "relays": relays}
    out["ordered_flux_index.json"] = {"report_id": rid,
                                      "order": "calibrated_flux_ujy desc, obs_id asc", "index": ordered_index}
    out["dropped_observations.json"] = {"report_id": rid,
                                        "source": "adjudication_dossier.pdf", "dropped_obs_ids": dropped}

    st = ref_settle(live, tables)
    out["settlement_summary.json"] = {
        "report_id": rid, "settled_pool_ujy": st["pool"],
        "settlement_digest": st["digest"], "settled_count": len(st["kept"]),
        "rejected_count": len(st["hits"]), "zero_exposure_count": len(st["aborted"]),
        "near_saturated_count": len(st["near"])}
    out["settled_rates.json"] = {"report_id": rid, "rates": st["paced"]}
    out["zero_exposure.json"] = {"report_id": rid, "observations": st["aborted"]}
    out["cosmic_ray_rejects.json"] = {"report_id": rid, "rejects": st["hits"]}
    out["near_saturation.json"] = {"report_id": rid, "observations": st["near"]}
    out["settled_attribution.json"] = {
        "report_id": rid, "settled_pool_ujy": st["pool"],
        "attributed_ujy": st["shares"]["attributed"]}
    out["settlement_order.json"] = {"report_id": rid, "order": st["order"]}
    out["band_settlement.csv"] = {"header": ["band", "settled_count", "settled_pool_ujy"],
                                  "rows": st["bands"]}
    out["provenance_manifest.json"] = {"report_id": rid,
                                       "scale_factor_source": "gain_scale_workbook.xlsx",
                                       "disputed_source": "adjudication_dossier.pdf",
                                       "raw_counts_source": "obs_capture_index.csv",
                                       "full_well_source": "full_well_capacity.tsv",
                                       "exposure_weight_source": "exposure_weight_micro.tsv",
                                       "attribution_method": "largest_remainder",
                                       "pipeline_order": ["clip", "dark", "nonlinearity", "gain", "scale", "drift", "quantize"],
                                       "rounding": "half_even", "drift_operation": "subtract",
                                       "deadpixel_resolution": "least_fixed_point",
                                       "source_precedence": ["adjudication_dossier.pdf", "csv_quality_flag"],
                                       "total_reconciled_flux_ujy": total_flux}
    for instr in INSTRUMENTS:
        for band in PHOTOMETRIC_BANDS:
            cut = sorted((r for r in live
                          if r["instrument"] == instr and r["band"] == band),
                         key=lambda x: x["obs_id"])
            out[f"cell_{instr}_{band}.json"] = {
                "instrument": instr, "band": band,
                "observation_count": len(cut),
                "flux_ujy": sum(r["calibrated_flux_ujy"] for r in cut),
                "saturated_count": sum(1 for r in cut if r["saturated"]),
                "obs_ids": [r["obs_id"] for r in cut]}

    def _dim_cut(instr: str, band: str, epoch: str) -> tuple[int, int]:
        rows = [r for r in live if r["instrument"] == instr
                and r["band"] == band and r["epoch"] == epoch]
        return sum(r["calibrated_flux_ujy"] for r in rows), len(rows)

    for epoch in EPOCHS:
        for band in PHOTOMETRIC_BANDS:
            out[f"grid_{epoch}_{band}.psv"] = [
                [instr, *_dim_cut(instr, band, epoch)] for instr in INSTRUMENTS]

    for instr in INSTRUMENTS:
        for epoch in EPOCHS:
            out[f"span_{instr}_{epoch}.tsv"] = [
                [band, *_dim_cut(instr, band, epoch)] for band in PHOTOMETRIC_BANDS]

    out["_meta"] = {"band_flux": band_flux, "epoch_flux": epoch_flux,
                    "instr_flux": instr_flux, "band_cnt": band_cnt, "epoch_cnt": epoch_cnt,
                    "instr_cnt": instr_cnt, "total_flux": total_flux, "anomalies": anomalies,
                    "dropped": dropped, "resolved_pixel": resolved_pixel,
                    "base_flux": base_flux, "band_median": band_median,
                    "live": live, "per_obs": per_obs, "relays": relays,
                    "attribution": attribution}
    return out


def ref_derive(seed: int, n: int, mutations: dict[str, Any] | None = None) -> dict[str, Any]:
    mutations = mutations or {}
    tables = tables_for(mutations)
    obs = build_observations(seed, n, mutations)
    masked = build_deadpixel_map(seed, obs, mutations)
    disputed = build_disputed(seed, obs)
    return ref_derive_from(obs, tables, masked, disputed, mutations)
# Static specification documents, embedded from the shipped extract so that every
# generated corpus carries the written contract the agent was given, which keeps
# every path the instruction names present in the corpora graded here.
STATIC_SPECS: dict[str, str] = {
    'report_schema.md': '''# Report schema (authoritative)

This file fixes the shape of every artifact the reconciliation writes into
`OUT_DIR`. The contract in `reconciliation_contract.md` says how to compute the
numbers; this file says what to call them and how to lay them out. Both are
binding.

## Rules that hold for every artifact

- `report_id` is the literal string `detector-flux-reconciliation` in every JSON
  artifact that carries the field. It is a fixed label, never derived from a
  filename or a directory.
- Every flux, count and correction is a JSON integer. A value written as
  `25089.0`, as `"25089"` or as a boolean is a different value.
- Every JSON file is serialized with 2-space indentation, sorted keys and one
  trailing newline, exactly as `json.dumps(obj, indent=2, sort_keys=True)`
  followed by a newline produces.
- Object keys that name a band, an epoch, an instrument, a channel or a pixel
  are sorted ascending by that key.
- In a JSON object keyed by band, epoch, instrument or channel, a key is present
  only when that key has a contributing observation. Absent keys are OMITTED,
  never written with a zero. This is the opposite of the delimited rollups
  below, which carry a row for every key in a fixed order and zero-fill the
  ones with no live observation. The two exceptions, where all four instruments
  are always present because the weight table and not the data decides the key
  set, are `exposure_weight_micro` and `attributed_ujy` in
  `flux_attribution.json`.
- Only live (non-dropped) observations appear in any rollup, ranking, median or
  anomaly. Dropped observations appear only in `dropped_observations.json`.
- A saturated observation is live and appears in every rollup, ranking and
  total, but it is excluded from every band median and is never an anomaly.

## summary.json

Exactly these ten keys, nothing else:

| key | type |
|-----|------|
| `report_id` | string, the fixed label |
| `observation_count` | integer, every observation in the extract |
| `live_count` | integer, observations surviving adjudication |
| `dropped_count` | integer, observations the dossier adjudicated as disputed |
| `total_reconciled_flux_ujy` | integer, the total after dead-pixel closure |
| `band_flux_ujy` | object, band to integer |
| `epoch_flux_ujy` | object, epoch to integer |
| `instrument_flux_ujy` | object, instrument to integer |
| `channel_usage` | object, resolved channel to integer count |
| `band_median_ujy` | object, band to integer median of the eligible flux in that band |

`band_median_ujy` is quantized with the same banker's rounding as every other
figure, so a median that falls on an exact half resolves to the even integer.
Its eligible sample is the live, non-saturated observations of the band, so a
band whose live observations are all saturated carries no key here.

## reconciled_flux.json

`report_id`, then `observations`, a list sorted by `obs_id` ascending. Each
entry carries exactly:

`obs_id`, `instrument`, `band`, `epoch`, `resolved_channel`, `effective_counts`,
`saturated`, `net_counts`, `linearized`, `drift_ppm`, `drift_correction`,
`calibrated_flux_ujy`.

`resolved_channel` is the channel after the epoch fold, `effective_counts` is
the count after the full-well clip (equal to `raw_counts` when the reading is
below or at the full well), `saturated` is a JSON boolean and is `true` only
when the clip applied, `net_counts` is the dark-subtracted effective count,
`linearized` is the Horner result, and `drift_correction` is the subtracted
amount.

## calibration_audit.json

`report_id`, plus:

- `scale_factor_micro`: instrument to the integer the workbook publishes, as
  stored, before the divide by 1e6.
- `gain_micro_e_per_count`: channel to the stored integer micro-e-per-count.
- `drift_ppm`: key `<instrument>:<epoch>` (for example `G1:E1`) to integer ppm,
  for every instrument and epoch pair.
- `nonlinearity_coeffs`: instrument to the coefficient list, highest degree
  first.
- `epoch_windows`: epoch to a two-element list `[mjd_start, mjd_end]`.
- `fold_applied`: a sorted list of the folds that change a channel, each written
  `<written_label>:<epoch>-><resolved_channel>` (for example `A0:E2->A2`).
  A label that resolves to itself is left out.

## data_quality.json

`report_id`, `input_file_count` (integer, the number of files present in
`DATA_DIR`), `observation_count`, `disputed_count`, `masked_pixel_count`,
`distinct_pixels` (integer, pixels appearing in the closure),
`suspect_but_not_disputed`, a sorted list of the obs_ids the CSV flags suspect
and the dossier clears, `saturated_count` (integer, live observations the
full-well clip applied to) and `saturated_obs_ids`, a sorted list of those
obs_ids.

## instrument_G1.json, instrument_G2.json, instrument_G3.json, instrument_G4.json

`instrument` (string), `observation_count`, `flux_ujy` (integer total for that
instrument), `band_flux_ujy` and `epoch_flux_ujy`. These four carry no
`report_id`.

## epoch_totals.json

`report_id`, `epoch_flux_ujy`, `epoch_observation_count`.

## deadpixel_closure.json

`report_id`, `masked_pixel_count`, `resolved_pixel_flux_ujy` (pixel to integer
flux after the closure, masked pixels present with 0) and
`total_after_closure_ujy`.

## anomaly_ledger.json

`report_id`, `rule` set to the literal string
`flux > 3 * band median (live, non-saturated only)`, and `anomalies`, a list
sorted by `obs_id` ascending whose entries carry `obs_id`, `band`,
`calibrated_flux_ujy` and `band_median`.

## ordered_flux_index.json

`report_id`, `order` set to the literal string
`calibrated_flux_ujy desc, obs_id asc`, and `index`, a list whose entries carry
`rank` (integer starting at 1), `obs_id` and `calibrated_flux_ujy`.

## dropped_observations.json

`report_id`, `source` set to the literal string `adjudication_dossier.pdf`, and
`dropped_obs_ids`, a sorted list of obs_ids.

## provenance_manifest.json

`report_id` plus these fixed values, which record the decisions the contract
mandates:

| key | value |
|-----|-------|
| `scale_factor_source` | `gain_scale_workbook.xlsx` |
| `disputed_source` | `adjudication_dossier.pdf` |
| `raw_counts_source` | `obs_capture_index.csv` |
| `full_well_source` | `full_well_capacity.tsv` |
| `exposure_weight_source` | `exposure_weight_micro.tsv` |
| `attribution_method` | `largest_remainder` |
| `pipeline_order` | `["clip", "dark", "nonlinearity", "gain", "scale", "drift", "quantize"]` |
| `rounding` | `half_even` |
| `drift_operation` | `subtract` |
| `deadpixel_resolution` | `least_fixed_point` |
| `source_precedence` | `["adjudication_dossier.pdf", "csv_quality_flag"]` |
| `total_reconciled_flux_ujy` | integer, the same total as summary.json |

## flux_attribution.json

`report_id`, plus:

- `pool_ujy`: integer, the total reconciled flux after dead-pixel closure, the
  same figure `summary.json` carries.
- `exposure_weight_micro`: instrument to the integer weight the exposure table
  publishes, as stored. All four instruments are present.
- `attributed_ujy`: instrument to the integer attributed amount. All four
  instruments are present, including one with no live observation, and the four
  amounts sum to `pool_ujy` exactly.
- `remainder_recipients`: a list of the instruments that received one additional
  micro-jansky from the leftover, sorted ASCENDING by instrument name rather
  than in award order. It is empty when the leftover is 0, and it never holds
  more than three entries.

## relay_audit.json

`report_id`, `masked_pixel_count`, and `relays`, a list with one entry per
masked pixel sorted by `pixel` ascending. Each entry carries exactly:

- `pixel`: the masked pixel.
- `relayed_ujy`: integer, the fully accumulated amount the pixel relays.
- `targets`: the pixel's relay targets, sorted ascending.
- `per_target_ujy`: object, target to the integer amount this pixel sent it. The
  amounts sum to `relayed_ujy`, and the first target in `targets` carries the
  leftover of the even split.
- `terminal_pixels`: a sorted list of the unmasked pixels the flux reaches from
  this pixel, following relay edges transitively through any masked hops.

## The delimited rollups

Each carries a header row and one row per key in the fixed order below.

- `band_rollup.csv`: header `band,flux_ujy,observation_count`, rows for bands
  u, g, r, i, z in that order.
- `epoch_rollup.tsv`: header `epoch`, `flux_ujy`, `observation_count` separated
  by tabs, rows for E1, E2, E3.
- `instrument_rollup.psv`: header `instrument|flux_ujy|observation_count`, rows
  for G1, G2, G3, G4.

A band, epoch or instrument with no live observation is written with 0 in both
numeric columns.

## The remaining artifacts

- `flagged_observations.xml`: root element `flagged_observations` holding one
  self-closing `observation` element per anomaly, in the anomaly ledger order,
  with attributes `obs_id`, `band`, `calibrated_flux_ujy` and `band_median`.
- `objective_summary.yaml`: `report_id`, `total_reconciled_flux_ujy`,
  `live_count`, `dropped_count`, `anomaly_count` and `band_flux_ujy`, keys
  sorted.
- `reconciliation_report.md`: a human-readable summary carrying the report id,
  the observation, live, dropped, masked-pixel and anomaly counts, the total
  reconciled flux, and the per-band and per-epoch flux.
- `run_status.txt`: plain `key: value` lines carrying `status`, `observations`,
  `live`, `dropped` and `total_reconciled_flux_ujy`.''',
    'reconciliation_contract.md': '''# Detector Flux Reconciliation Contract

This corpus is a reconciliation extract from a four-instrument detector array
(G1..G4) over three observing epochs (E1, E2, E3). Raw analog-to-digital counts
must be reconciled into a calibrated flux in integer micro-jansky
(`calibrated_flux_ujy`). The extract ships a set of reference tables and a
faulty pre-computed pipeline. Your job is to compute the correct reconciliation.

## Records

Each observation carries: `obs_id`, `instrument`, `band` (one of u,g,r,i,z),
`mjd` (modified Julian date), a written gain label, `raw_counts`, a `pixel`, and
a CSV quality flag. The observation stream appears in more than one file; where
two files disagree on a column name, the value is the same reading under a
different name (see the glossary).

## Pipeline (correct application order)

The correction stages are documented across separate files. THE
ORDER THOSE FILES APPEAR IN IS NOT THE ORDER THEY APPLY IN. The correct
application order is:

1. CLIP: a reading above the detector's full well is not a measurement, it is a
   ceiling. Read `full_well_counts(instrument)` from the full-well capacity
   table. When `raw_counts > full_well_counts`, the observation is SATURATED and
   `effective_counts = full_well_counts`; otherwise it is not saturated and
   `effective_counts = raw_counts`. Clipping happens BEFORE dark subtraction, so
   every later stage works on `effective_counts`, never on `raw_counts`.
2. DARK: `net = effective_counts - dark_current_counts(instrument, band, epoch)`.
   The authoritative dark-current value is the `authoritative` row for each
   (instrument, band, epoch); `informational` rows are repeat readings.
3. NONLINEARITY: apply the per-instrument Horner polynomial to `net`
   (`response_curve_horner`), BEFORE gain. Coefficients are stored x1e6 and the
   result is divided back by 1e6 with banker's rounding.
4. GAIN: multiply by the quantum yield of the RESOLVED channel. The gain label
   written in the observation is not always the channel that applies: labels
   were folded across epochs (`channel_lineage_fold`). Resolve the channel by
   (written label, mjd) first, then look up the micro-e-per-count value and
   divide by 1e6.
5. SCALE: multiply by the per-instrument scale factor. This factor is stored
   x1e6 and must be divided by 1e6. The authoritative scale factor is published
   only in the scale workbook.
6. DRIFT: compute `drift_correction = round_half_even(scaled * drift_ppm / 1e6)`
   and SUBTRACT it (`thermal_drift_ppm`). The correction is subtracted, not
   added.
7. QUANTIZE: `calibrated_flux_ujy = round_half_even(value)` (banker's rounding).

## Saturation

Saturation is a measurement limit, not a dispute: a saturated observation stays
live, keeps the flux computed from its clipped counts, and contributes that flux
to every rollup, ranking and total exactly as an unsaturated observation does.
Saturation changes two things and nothing else:

- A saturated observation is NOT ELIGIBLE for a band median. Each band median is
  the median of the live, non-saturated observations of that band. A band whose
  live observations are all saturated has no eligible sample, so it carries no
  median at all.
- A saturated observation is NEVER FLAGGED as an anomaly, however large its flux
  is. A clipped reading exceeding three times its band median is the ceiling
  showing through, not a detection.

An observation exactly at full well (`raw_counts == full_well_counts`) is NOT
saturated: the clip applies only above the ceiling.

## Exposure attribution

The reconciled total must also be attributed back to the four instruments in
proportion to their published exposure weight, as whole micro-jansky that sum to
the total exactly. The weights are integers stored x1e6 in the exposure weight
table; their scale cancels in the ratio, so they are used as published.

With `pool` the total reconciled flux after dead-pixel closure, `w(i)` the
weight of instrument `i` and `W` the sum of all four weights:

1. `exact(i) = pool * w(i) / W`, kept as an exact rational, never as a float.
2. `base(i) = floor(exact(i))`, rounding toward negative infinity.
3. `leftover = pool - sum(base(i))`, which is at least 0 and less than 4.
4. Order the instruments by the fractional part `exact(i) - base(i)`
   DESCENDING, breaking ties by instrument name ASCENDING. The first `leftover`
   instruments in that order each receive one additional micro-jansky.

The result is the largest-remainder apportionment: every attributed amount is an
integer and the four amounts sum to `pool` exactly. Rounding each share on its
own and hoping the parts add up is wrong, and so is giving the leftover to the
largest share rather than to the largest remainder. All four instruments are
attributed, including an instrument with no live observation.

## Relay audit

The dead-pixel redistribution must also be reported hop by hop, so the closure
can be audited rather than taken on trust. For each masked pixel, in ascending
pixel order, record the amount it relays, how that amount split across its
targets, and where the flux finally lands:

- `relayed_ujy` is the FULLY ACCUMULATED amount the pixel relays: its own base
  flux plus everything relayed into it by pixels resolved before it. It is the
  amount the least fixed point gives that pixel, not its base flux.
- The split is the one the closure already uses: each target receives
  `floor(relayed_ujy / target_count)`, and the leftover
  `relayed_ujy - floor(relayed_ujy / target_count) * target_count` goes to the
  FIRST target in ascending target order. The per-target amounts sum to
  `relayed_ujy`.
- `terminal_pixels` is where the flux ends up: every UNMASKED pixel reachable
  from this pixel by following relay edges, transitively, through any number of
  masked hops. A target that is itself masked is not a terminal pixel; its own
  targets are followed instead.

## Epoch resolution

`epoch` is resolved from `mjd` against half-open intervals `[start, end)`
(`epoch_window_bounds`). A reading whose mjd equals an interval end belongs to
the next epoch.

## Dead-pixel redistribution

Some pixels are masked (`occlusion_relay_graph`). A masked pixel contributes
zero to its own totals; its flux is redistributed to its target pixels. Targets
may themselves be masked, so redistribution is a least-fixed-point resolved in
ascending pixel order: a masked pixel distributes its fully-accumulated flux to
its targets, split evenly with any remainder going to the first target. A
single redistribution pass that uses only base (pre-redistribution) flux is
wrong wherever a chain is longer than one hop.

## Source precedence (disputed observations)

The CSV quality flag and the disputed-observation adjudication log disagree on
some observations. The adjudication log (the PDF dossier) OVERRIDES the CSV
flag. An observation adjudicated `disputed` is DROPPED from every rollup and
recorded in the dropped-observations artifact; the CSV `suspect` flag alone does
not drop an observation.

## Determinism

All JSON output must be serialized with sorted keys and a trailing newline and
use integer micro-jansky throughout. Output must be byte-identical across reruns
and independent of input row order.''',
    'file_role_index.md': '''# File role index

- observation stream: arr_run_ledger_delta.jsonl, obs_capture_index.csv (authoritative raw_counts), frame_intake_stream.ndjson, capture_alt_view.csv
- full well capacity (authoritative): full_well_capacity.tsv ONLY
- exposure weight (authoritative): exposure_weight_micro.tsv ONLY
- dark current: pedestal_authoritative.csv (authoritative), baseline_pedestal_grid.tsv
- nonlinearity: response_curve_horner.yaml, instrument_capability_matrix.xml
- gain values: quantum_yield_micro.json, yield_channel_values.psv
- gain fold: channel_lineage_fold.psv, yield_binding_trace.jsonl
- SCALE FACTOR (authoritative): gain_scale_workbook.xlsx ONLY
- drift: thermal_drift_ppm.yml, drift_ppm_matrix.tsv
- disputed (authoritative): adjudication_dossier.pdf ONLY
- dead-pixel relay: occlusion_relay_graph.xml, relay_edges.jsonl, relay_closure_rule.json
- legacy faulty output (do not trust): legacy_pipeline_output.json''',
    'field_glossary.md': '''# Field glossary and column aliases

Observation columns appear under different names in different files. These refer
to the SAME reading:

| canonical        | aliases                          |
|------------------|----------------------------------|
| raw_counts       | adu                              |
| instrument       | instr                            |
| quality_flag     | csv_quality, csv_quality_flag    |
| gain_label       | written_label, written_gain_label|

Scale factor storage: `factor_micro` is the per-instrument scale factor stored
as an integer multiplied by 1e6. Divide by 1e6 before applying.

Gain storage: quantum yield is stored as micro-e-per-count (integer x 1e6).
Divide by 1e6 before applying.

Drift: `drift_ppm` is a parts-per-million correction that is SUBTRACTED after
scaling.

Epoch: intervals are half-open `[mjd_start, mjd_end)`.''',
    'units_primer.txt': '''factor_micro and quantum-yield are integers stored x1e6; divide by 1e6 before use. drift_ppm is parts-per-million (divide by 1e6) and is subtracted. calibrated_flux_ujy is integer micro-jansky. full_well_counts is a raw-count ceiling in counts, used as published and never divided. weight_micro is an exposure weight stored x1e6 whose scale cancels in the attribution ratio, so it too is used as published.''',
    'rounding_primer.txt': '''All quantization uses banker's rounding (round half to even). Half-up rounding is WRONG and will diverge on exact-half values. The drift correction and the final micro-jansky value both use half-even.''',
    'pipeline_order_note.txt': '''PIPELINE APPLICATION ORDER (authoritative)
The correction documents are shipped in this file-listing order:
  response_curve_horner.yaml   (nonlinearity)
  thermal_drift_ppm.yml        (drift)
  baseline_pedestal_grid.tsv   (dark current)
That listing order is NOT the application order. Apply in this order instead:
  1. clip raw_counts at the per-instrument full well, before dark subtraction
  2. dark current subtraction, on the clipped (effective) counts
  3. nonlinearity (Horner), before gain
  4. gain (resolved channel), micro-e-per-count / 1e6
  5. per-instrument scale factor / 1e6
  6. thermal drift correction, SUBTRACTED
  7. quantize to integer micro-jansky with banker's (half-even) rounding
Reading the correction files top-to-bottom and applying them in that order is
the single most common way to get every flux wrong.''',
    'boundary_cases.md': '''# Boundary cases

An mjd equal to an epoch's `mjd_end` belongs to the NEXT epoch (half-open intervals). E1=[59000,59120), E2=[59120,59240), E3=[59240,59360). An mjd of 59120 is in E2, not E1.

A `raw_counts` equal to the instrument's `full_well_counts` is NOT saturated and is not clipped; only a reading strictly above the full well is.

A band whose every live observation is saturated has no eligible median sample, so that band carries no band median key and flags no anomaly.

An exposure attribution whose leftover is 0 gives no instrument an extra micro-jansky, and the list of remainder recipients is then empty.''',
    'ranking_spec.md': '''# Flux ordering

The ordered flux index ranks live (non-dropped) observations by calibrated_flux_ujy descending, breaking ties by obs_id ascending.''',
    'anomaly_threshold_spec.json': '''{
  "central_statistic": "median",
  "eligible_sample": "live and not saturated",
  "group_by": "band",
  "multiplier": 3,
  "rule": "flag live, non-saturated observations whose calibrated_flux_ujy exceeds three times the median calibrated_flux_ujy of the eligible observations of the same band; a band with no eligible observation carries no median and flags nothing"
}''',
    'relay_closure_rule.json': '''{
  "audit_amount": "fully_accumulated_not_base_flux",
  "audit_terminals": "unmasked_pixels_reachable_transitively",
  "masked_contributes_own_total": 0,
  "order": "ascending_pixel_id",
  "resolution": "least_fixed_point",
  "split": "even_remainder_to_first_target"
}''',
    'source_precedence.yml': '''precedence:
  - pdf_adjudication_dossier
  - csv_quality_flag
disputed_action: drop_from_all_rollups_record_in_dropped_observations
suspect_alone_action: retain''',
    'dispute_notice_readme.txt': '''partial_dispute_notice.jsonl is INCOMPLETE: it omits the first three disputed observations by design. The complete, authoritative disputed set is in adjudication_dossier.pdf. Using only the jsonl notice will leave three disputed observations wrongly included.''',
    'diagnostic_codes.txt': '''E01 negative net after dark subtraction is retained (do not clamp)
E02 mjd on interval boundary belongs to the NEXT epoch
E03 disputed adjudication overrides csv quality flag
E04 masked pixel contributes zero to own totals
E05 raw_counts above full_well_counts is clipped before dark subtraction and marked saturated
E06 saturated observation stays live, leaves the band median and is never flagged as an anomaly
E07 exposure attribution is largest remainder, parts sum to the pool exactly
E08 relay audit reports the fully accumulated amount, not the base flux''',
    'array_operations_brief.md': '''# Array operations brief

Instruments G1..G4 observe over epochs E1..E3. The legacy pipeline output shipped alongside this brief is known to be faulty and must be recomputed from the reconciliation contract. Do not copy legacy_pipeline_output values.''',
    'horner_worked_example.md': '''# Horner worked example

For G2 with net=11959 and coefficients [5, 998000, 12000] (x1e6, highest degree first): evaluate 5*net^2 + 998000*net + 12000 then divide by 1e6 with half-even rounding.''',
    'extract_provenance.txt': '''Extract is deterministic. All figures derive from the observation stream and the reference tables in this directory. The scale factor required to compute calibrated flux is published only in gain_scale_workbook.xlsx; the disputed-observation adjudication is published only in adjudication_dossier.pdf.''',
}


# ---------------------------------------------------------------------------
# Low-level writers for the formats the shipped extract uses.
# ---------------------------------------------------------------------------
def _wdelim(path, header, rows, delim):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _wjson(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _wjsonl(path, objs):
    path.write_text("".join(json.dumps(o, sort_keys=True) + "\n" for o in objs), encoding="utf-8")


def _wtext(path, text):
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _xesc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _wxml(path, root, rows, tag):
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', f"<{root}>"]
    for r in rows:
        attrs = "".join(f' {k}="{_xesc(v)}"' for k, v in r.items())
        parts.append(f"  <{tag}{attrs}/>")
    parts.append(f"</{root}>")
    _wtext(path, "\n".join(parts))


def _wsqlite(path, tables):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    for name, (cols, rows) in tables.items():
        cur.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{c}" TEXT' for c in cols) + ")")
        ph = ", ".join("?" for _ in cols)
        cur.executemany(f'INSERT INTO "{name}" VALUES ({ph})', [[str(x) for x in r] for r in rows])
    con.commit()
    con.close()


def _wpdf(path, page_lines):
    npages = len(page_lines)
    page_ids = [4 + i for i in range(npages)]
    content_ids = [4 + npages + i for i in range(npages)]
    body = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: ("<< /Type /Pages /Kids [%s] /Count %d >>" %
                (" ".join(f"{p} 0 R" for p in page_ids), npages)).encode(),
            3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"}
    for i in range(npages):
        body[page_ids[i]] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                             f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_ids[i]} 0 R >>").encode()
        parts = ["BT", "/F1 8 Tf", "1 0 0 1 30 760 Tm", "9 TL"]
        for ln in page_lines[i]:
            esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            parts.append(f"({esc}) Tj")
            parts.append("T*")
        parts.append("ET")
        content = "\n".join(parts).encode("latin-1")
        body[content_ids[i]] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    maxobj = max(body)
    out = b"%PDF-1.4\n"
    offs = {}
    for i in range(1, maxobj + 1):
        offs[i] = len(out)
        out += b"%d 0 obj\n" % i + body[i] + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (maxobj + 1)
    for i in range(1, maxobj + 1):
        out += b"%010d 00000 n \n" % offs[i]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (maxobj + 1, xref)
    path.write_bytes(out)


def _wxlsx(path, sheets):
    def col_ref(ci, ri):
        letters = ""
        n = ci + 1
        while n:
            n, rem = divmod(n - 1, 26)
            letters = chr(65 + rem) + letters
        return f"{letters}{ri}"

    def cell(ci, ri, val):
        ref = col_ref(ci, ri)
        if isinstance(val, bool):
            val = str(val)
        if isinstance(val, int):
            return f'<c r="{ref}" t="n"><v>{val}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xesc(val)}</t></is></c>'

    sheet_xmls = []
    for name, header, rows in sheets:
        body = ['<row r="1">%s</row>' % "".join(cell(ci, 1, h) for ci, h in enumerate(header))]
        rr = 1
        for r in rows:
            rr += 1
            body.append('<row r="%d">%s</row>' % (rr, "".join(cell(ci, rr, v) for ci, v in enumerate(r))))
        sheet_xmls.append((name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                           f'<sheetData>{"".join(body)}</sheetData></worksheet>'))
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for i in range(1, len(sheet_xmls) + 1)) + '</Types>')
    rr = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wbs = "".join(f'<sheet name="{_xesc(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, (n, _) in enumerate(sheet_xmls, 1))
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          f'<sheets>{wbs}</sheets></workbook>')
    wbr = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                     for i in range(1, len(sheet_xmls) + 1)) + '</Relationships>')
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rr)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wbr)
        for i, (_, xml) in enumerate(sheet_xmls, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)


BAND_INDEX = {b: i for i, b in enumerate(BANDS)}


def _naive_flux(o: dict, tables: dict[str, Any], windows) -> int:
    """What the shipped legacy pipeline reported: written gain label, no scale
    factor, drift added, half-up rounding. Deliberately wrong."""
    from decimal import ROUND_HALF_UP
    epoch = epoch_of_mjd(o["mjd"], windows)
    net = o["raw_counts"] - dark_current(o["instrument"], o["band"], epoch)
    lin = horner(tables["nonlin"][o["instrument"]], net)
    g = Decimal(lin) * Decimal(tables["gain_micro"][o["written_gain"]]) / Decimal(1_000_000)
    dc = int((g * Decimal(drift_ppm(o["instrument"], epoch)) / Decimal(1_000_000))
             .quantize(Decimal("1"), ROUND_HALF_UP))
    return int((g + Decimal(dc)).quantize(Decimal("1"), ROUND_HALF_UP))


def build_corpus(root: Path, obs: list[dict], tables: dict[str, Any],
                 masked: dict[str, list[str]], disputed: set[str],
                 mutations: dict[str, Any] | None = None) -> Path:
    """Write a complete extract: every file the shipped corpus carries, in the
    same formats and under the same names, so any documented read succeeds."""
    mutations = mutations or {}
    root.mkdir(parents=True, exist_ok=True)
    windows = tables["epoch_mjd"]
    pixels = sorted({o["pixel"] for o in obs})
    disputed_sorted = sorted(disputed)

    for name, text in STATIC_SPECS.items():
        _wtext(root / name, text)

    csv_obs = list(obs)
    if mutations.get("row_shuffle"):
        rs = Rng(mutations.get("shuffle_seed", 0xABCDEF))
        for j in range(len(csv_obs) - 1, 0, -1):
            k = rs.rint(0, j)
            csv_obs[j], csv_obs[k] = csv_obs[k], csv_obs[j]

    # --- observation stream, in each of its four published views -----------
    _wdelim(root / "obs_capture_index.csv",
            ["obs_id", "instrument", "band", "mjd", "gain_label", "raw_counts", "pixel", "quality_flag"],
            [[o["obs_id"], o["instrument"], o["band"], o["mjd"], o["written_gain"],
              o["raw_counts"], o["pixel"], o["quality_flag"]] for o in csv_obs], ",")
    _wjsonl(root / "arr_run_ledger_delta.jsonl",
            [{"obs_id": o["obs_id"], "instrument": o["instrument"], "band": o["band"],
              "mjd": o["mjd"], "gain_label": o["written_gain"], "raw_counts": o["raw_counts"],
              "pixel": o["pixel"], "quality_flag": o["quality_flag"]} for o in csv_obs])
    _wjsonl(root / "frame_intake_stream.ndjson",
            [{"obs_id": o["obs_id"], "instr": o["instrument"], "band": o["band"],
              "mjd": o["mjd"], "gain_label": o["written_gain"], "adu": o["raw_counts"],
              "pixel": o["pixel"], "csv_quality": o["quality_flag"]} for o in csv_obs])
    _wjsonl(root / "raw_capture_mirror.jsonl",
            [{"obs_id": o["obs_id"], "instr": o["instrument"], "band": o["band"],
              "mjd": o["mjd"], "written_gain_label": o["written_gain"], "adu": o["raw_counts"],
              "pixel": o["pixel"], "csv_quality_flag": o["quality_flag"]} for o in csv_obs])
    _wdelim(root / "capture_alt_view.csv",
            ["obs_id", "band", "instr", "mjd", "written_label", "adu", "pixel", "csv_quality"],
            [[o["obs_id"], o["band"], o["instrument"], o["mjd"], o["written_gain"],
              o["raw_counts"], o["pixel"], o["quality_flag"]] for o in csv_obs], ",")
    _wdelim(root / "adu_distribution_log.csv", ["instrument", "band", "epoch", "raw_counts"],
            [[o["instrument"], o["band"], epoch_of_mjd(o["mjd"], windows), o["raw_counts"]]
             for o in csv_obs], ",")
    _wdelim(root / "exposure_ledger.csv", ["obs_id", "exposure_ms", "shutter_state"],
            [[o["obs_id"], _exposure_of(o), _shutter_of(o)] for o in csv_obs], ",")

    # --- epoch windows ------------------------------------------------------
    _wjson(root / "epoch_window_bounds.json",
           {"interval": "half_open_[start,end)",
            "epochs": {e: {"mjd_start": windows[e][0], "mjd_end": windows[e][1]} for e in EPOCHS}})
    _wtext(root / "epoch_capacity_profile.yaml", "\n".join(
        ["epochs:"] + [f"  -\n    epoch: {e}\n    mjd_start: {windows[e][0]}\n    mjd_end: {windows[e][1]}"
                       for e in EPOCHS]))
    cal_rows = []
    seen_mjd = set()
    for o in sorted(obs, key=lambda x: x["mjd"]):
        if o["mjd"] not in seen_mjd:
            seen_mjd.add(o["mjd"])
            cal_rows.append([o["mjd"], epoch_of_mjd(o["mjd"], windows)])
    _wdelim(root / "observation_calendar.tsv", ["mjd", "epoch"], cal_rows, "\t")
    _wdelim(root / "temporal_binning_map.csv", ["obs_id", "mjd", "resolved_epoch"],
            [[o["obs_id"], o["mjd"], epoch_of_mjd(o["mjd"], windows)] for o in csv_obs], ",")

    # --- dark current: authoritative table and the fuller grid --------------
    dark_rows = [[i, b, e, dark_current(i, b, e)] for i in INSTRUMENTS for b in BANDS for e in EPOCHS]
    padded = list(dark_rows)
    while len(padded) < 200:
        padded.append(dark_rows[len(padded) % len(dark_rows)])
    _wdelim(root / "pedestal_authoritative.csv",
            ["instrument", "band", "epoch", "dark_current_counts"], padded, ",")
    decoy = mutations.get("dark_decoy", 0)
    grid = []
    for i in INSTRUMENTS:
        for b in BANDS:
            for e in EPOCHS:
                lo, hi = windows[e]
                auth = dark_current(i, b, e)
                grid.append([i, b, e, lo, auth, "authoritative"])
                for k in range(1, 4):
                    grid.append([i, b, e, lo + k * ((hi - lo) // 4), auth + decoy, "informational"])
    _wdelim(root / "baseline_pedestal_grid.tsv",
            ["instrument", "band", "epoch", "mjd", "dark_current_counts", "row_kind"], grid, "\t")

    # --- full well and exposure weight: each published in one table only ----
    _wdelim(root / "full_well_capacity.tsv",
            ["instrument", "full_well_counts", "row_kind"],
            [[i, tables["full_well"][i], "authoritative"] for i in INSTRUMENTS], "\t")
    _wdelim(root / "exposure_weight_micro.tsv",
            ["instrument", "weight_micro", "storage", "apply_rule"],
            [[i, tables["exposure_micro"][i], "x1e6", "ratio_as_published"]
             for i in INSTRUMENTS], "\t")

    # --- nonlinearity -------------------------------------------------------
    nl = ["encoding: micro_scaled_x1e6", "divide_result_by: 1000000",
          "order: highest_degree_first", "apply_stage: after_dark_before_gain",
          "coefficients:"]
    for i in INSTRUMENTS:
        nl.append(f"  {i}:")
        for c in tables["nonlin"][i]:
            nl.append(f"    - {c}")
    _wtext(root / "response_curve_horner.yaml", "\n".join(nl))
    _wxml(root / "instrument_capability_matrix.xml", "instruments",
          [{"instrument": i, "nonlin_a2": tables["nonlin"][i][0],
            "nonlin_a1": tables["nonlin"][i][1], "nonlin_a0": tables["nonlin"][i][2]}
           for i in INSTRUMENTS], "instrument")

    # --- gain values and the temporal fold ----------------------------------
    _wjson(root / "quantum_yield_micro.json",
           {"units": "micro_e_per_count", "divide_by": 1000000,
            "channels": {ch: tables["gain_micro"][ch] for ch in GAIN_CHANNELS}})
    _wdelim(root / "yield_channel_values.psv", ["channel", "micro_e_per_count", "unit", "apply"],
            [[ch, tables["gain_micro"][ch], "micro_e_per_count", "div_1e6"] for ch in GAIN_CHANNELS], "|")
    fold_rows = []
    for written in list(GAIN_LABELS_WRITEABLE) + ["A2", "B3"]:
        for e in EPOCHS:
            lo, hi = windows[e]
            for k in range(10):
                mjd = lo + k * ((hi - lo) // 10)
                resolved = resolve_channel(written, mjd, windows) if written in GAIN_LABELS_WRITEABLE else written
                fold_rows.append([written, e, mjd, resolved, "yes" if resolved != written else "no"])
    while len(fold_rows) < 210:
        fold_rows.append(fold_rows[len(fold_rows) % 150])
    _wdelim(root / "channel_lineage_fold.psv",
            ["written_label", "epoch", "mjd", "resolved_channel", "folded"], fold_rows, "|")
    _wjsonl(root / "yield_binding_trace.jsonl",
            [{"obs_id": o["obs_id"], "mjd": o["mjd"], "written": o["written_gain"],
              "resolved_channel": resolve_channel(o["written_gain"], o["mjd"], windows)} for o in csv_obs])
    _wdelim(root / "channel_usage_ledger.csv", ["instrument", "epoch", "resolved_channel"],
            [[o["instrument"], epoch_of_mjd(o["mjd"], windows),
              resolve_channel(o["written_gain"], o["mjd"], windows)] for o in csv_obs], ",")

    # --- scale factor: the workbook is the only authority -------------------
    fdecoy = mutations.get("factor_decoy", 0)
    factor_sheet = [[i, tables["factor_micro"][i], "x1e6", "divide_by_1e6"] for i in INSTRUMENTS]
    audit = []
    for i in INSTRUMENTS:
        for b in BANDS:
            for e in EPOCHS:
                for k in range(4):
                    lo, hi = windows[e]
                    audit.append([i, b, e, lo + k * ((hi - lo) // 4),
                                  tables["factor_micro"][i] + fdecoy, "informational"])
    _wxlsx(root / "gain_scale_workbook.xlsx",
           [("scale_factor_authoritative", ["instrument", "factor_micro", "storage", "apply_rule"], factor_sheet),
            ("scale_audit_detail", ["instrument", "band", "epoch", "mjd", "factor_micro_observed", "row_kind"], audit)])

    # --- thermal drift ------------------------------------------------------
    bump = mutations.get("drift_bump", 0)
    drows = [{"instrument": i, "epoch": e, "drift_ppm": drift_ppm(i, e) + bump}
             for i in INSTRUMENTS for e in EPOCHS]
    dl = ["operation: subtract", "ppm_divisor: 1000000", "rounding: half_even", "table:"]
    for r in drows:
        dl.append("  -")
        dl.append(f"    instrument: {r['instrument']}")
        dl.append(f"    epoch: {r['epoch']}")
        dl.append(f"    drift_ppm: {r['drift_ppm']}")
    _wtext(root / "thermal_drift_ppm.yml", "\n".join(dl))
    _wdelim(root / "drift_ppm_matrix.tsv", ["instrument", "epoch", "drift_ppm"],
            [[r["instrument"], r["epoch"], r["drift_ppm"]] for r in drows], "\t")

    # --- dead-pixel relay ---------------------------------------------------
    mrows = []
    for m in sorted(masked):
        mrows.append({"pixel": m, "targets": ";".join(masked[m]), "target_count": len(masked[m])})
    for px in pixels:
        mrows.append({"pixel": px, "targets": ";".join(masked.get(px, [])),
                      "target_count": len(masked.get(px, []))})
    while len(mrows) < 205:
        mrows.append({"pixel": pixels[len(mrows) % len(pixels)], "targets": "", "target_count": 0})
    _wxml(root / "occlusion_relay_graph.xml", "mask_graph", mrows, "node")
    _wjsonl(root / "relay_edges.jsonl",
            [{"pixel": m, "targets": masked[m]} for m in sorted(masked)])
    _wsqlite(root / "pixel_registry.db",
             {"pixels": (["pixel", "masked"], [[p, "yes" if p in masked else "no"] for p in pixels])})
    _wdelim(root / "focalplane_pixel_atlas.psv", ["pixel", "instrument", "band", "obs_id"],
            [[o["pixel"], o["instrument"], o["band"], o["obs_id"]] for o in csv_obs], "|")

    # --- quality flags and the adjudication dossier -------------------------
    _wsqlite(root / "sensor_flags_store.sqlite",
             {"quality_flags": (["obs_id", "csv_quality_flag", "pixel"],
                                [[o["obs_id"], o["quality_flag"], o["pixel"]] for o in obs])})
    _wsqlite(root / "adjudication_cache.db",
             {"adjudication_hint": (["obs_id", "hint"], [[o["obs_id"], "see_pdf_dossier"] for o in obs])})
    lines = ["DETECTOR ARRAY DISPUTED-OBSERVATION ADJUDICATION LOG",
             "precedence: PDF overrides csv_quality_flag", "", "obs_id|pdf_adjudication|note"]
    for o in obs:
        adj = "disputed" if o["obs_id"] in disputed else "clear"
        lines.append(f'{o["obs_id"]}|{adj}|epoch={epoch_of_mjd(o["mjd"], windows)}')
    pages = [lines[i:i + 46] for i in range(0, len(lines), 46)]
    _wpdf(root / "adjudication_dossier.pdf", pages)
    # deliberately incomplete, exactly as dispute_notice_readme.txt warns
    _wjsonl(root / "partial_dispute_notice.jsonl",
            [{"obs_id": d, "status": "disputed"} for d in disputed_sorted[3:]])

    # --- band reference tables ---------------------------------------------
    _wxml(root / "band_index_map.xml", "bands",
          [{"band": b, "index": BAND_INDEX[b]} for b in BANDS], "band")
    bw = []
    for b in BANDS:
        for slot in range(45):
            bw.append([b, BAND_INDEX[b], slot])
    _wdelim(root / "band_weight_reference.tsv", ["band", "band_index", "slot"], bw, "\t")
    _wdelim(root / "spectral_band_key.tsv", ["obs_id", "band", "band_index"],
            [[o["obs_id"], o["band"], BAND_INDEX[o["band"]]] for o in csv_obs], "\t")

    # --- instrument registry ------------------------------------------------
    cap = []
    for i in INSTRUMENTS:
        for b in BANDS:
            for e in EPOCHS:
                for slot in range(4):
                    cap.append([i, b, e, slot, "nominal"])
    _wsqlite(root / "array_registry.db",
             {"instruments": (["instrument", "array_name", "mjd_min", "mjd_max"],
                              [[i, f"array-{i}", 59000, 59360] for i in INSTRUMENTS]),
              "capability": (["instrument", "band", "epoch", "slot", "state"], cap)})

    # --- the faulty pre-computed pipeline the agent must not trust ----------
    _wjson(root / "legacy_pipeline_output.json",
           {"warning": "pre-computed output is known to be faulty; recompute from the contract",
            "observations": [{"obs_id": o["obs_id"], "reported_flux_ujy": _naive_flux(o, tables, windows)}
                             for o in obs]})

    # --- live counts and the worked self-check slice ------------------------
    live_obs = [o for o in obs if o["obs_id"] not in disputed]
    counts: dict[str, int] = {}
    for o in live_obs:
        counts[o["instrument"]] = counts.get(o["instrument"], 0) + 1
    _wtext(root / "live_count_profile.yaml",
           "note: live (non-dropped) observation counts per instrument\ncounts:\n"
           + "\n".join(f"  {i}: {counts.get(i, 0)}" for i in INSTRUMENTS))
    _wjson(root / "worked_reference_slice.json", _worked_slice(tables))

    for p in root.iterdir():
        p.chmod(0o644)
    root.chmod(0o755)
    return root


WORKED_SLICE_OBS = [
    {"obs_id": "cal01", "instrument": "G1", "band": "g", "mjd": 59180,
     "written_gain": "A0", "raw_counts": 12000, "pixel": "pc001", "quality_flag": "ok"},
    {"obs_id": "cal02", "instrument": "G3", "band": "z", "mjd": 59300,
     "written_gain": "B0", "raw_counts": 8000, "pixel": "pc002", "quality_flag": "ok"},
    {"obs_id": "cal03", "instrument": "G2", "band": "r", "mjd": 59050,
     "written_gain": "C1", "raw_counts": 25000, "pixel": "pc003", "quality_flag": "ok"},
]

# An unshipped slice. The worked slice above is published to the agent as a
# self-check; this one is not, so reproducing it cannot be transcription.
HIDDEN_SLICE_OBS = [
    {"obs_id": "hid01", "instrument": "G4", "band": "u", "mjd": 59239,
     "written_gain": "B0", "raw_counts": 31117, "pixel": "ph001", "quality_flag": "ok"},
    {"obs_id": "hid02", "instrument": "G2", "band": "i", "mjd": 59240,
     "written_gain": "A0", "raw_counts": 4503, "pixel": "ph002", "quality_flag": "suspect"},
    {"obs_id": "hid03", "instrument": "G1", "band": "z", "mjd": 59119,
     "written_gain": "C1", "raw_counts": 57002, "pixel": "ph003", "quality_flag": "ok"},
    {"obs_id": "hid04", "instrument": "G3", "band": "r", "mjd": 59120,
     "written_gain": "B0", "raw_counts": 19888, "pixel": "ph004", "quality_flag": "ok"},
]


def _worked_slice(tables: dict[str, Any]) -> dict[str, Any]:
    """The published self-check slice, recomputed from this corpus's own tables
    so it stays truthful when a mutation moves a reference value."""
    rows = []
    for o in WORKED_SLICE_OBS:
        r = reconcile_one(o, tables)
        rows.append({"obs_id": o["obs_id"], "instrument": o["instrument"], "band": o["band"],
                     "mjd": o["mjd"], "written_gain_label": o["written_gain"],
                     "raw_counts": o["raw_counts"],
                     "expected_epoch": r["epoch"], "expected_net_counts": r["net"],
                     "expected_linearized": r["lin"], "expected_resolved_channel": r["channel"],
                     "expected_drift_ppm": r["drift_ppm"],
                     "expected_drift_correction": r["drift_correction"],
                     "expected_calibrated_flux_ujy": r["calibrated_flux_ujy"]})
    return {"note": "Worked reference slice. Run your pipeline on these three observations; "
                    "if your calibrated_flux_ujy matches every expected value, your pipeline "
                    "honors the full contract.",
            "observations": rows}


def write_case(root: Path, seed: int, n: int, mutations: dict[str, Any] | None = None) -> Path:
    mutations = mutations or {}
    tables = tables_for(mutations)
    obs = build_observations(seed, n, mutations)
    masked = build_deadpixel_map(seed, obs, mutations)
    disputed = build_disputed(seed, obs)
    return build_corpus(root, obs, tables, masked, disputed, mutations)


# ---------------------------------------------------------------------------
# Running the agent's program. It is untrusted code, so it runs unprivileged
# where the kernel allows it, in its own session, with a scrubbed environment
# (the verifier's own environment carries API keys), and its process group is
# killed on timeout so nothing outlives the call.
# ---------------------------------------------------------------------------
AGENT_TIMEOUT_SEC = 120
SAFE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
            "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}


def _agent_argv(script: Path, root: Path, out: Path) -> list[str]:
    base = [sys.executable, str(script), str(root), str(out)]
    if os.geteuid() == 0 and shutil.which("setpriv"):
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + base
    return base


def _grant_read(script: Path) -> None:
    """A real agent writes its program through an editor, which renames a temp
    file into place and leaves it at mode 0600 owned by uid 1000. Harbor hands
    /app to the verifier with those modes intact, so the unprivileged child
    _agent_argv drops to could not open the very program it has to run, and
    every check that executes it would fail on a correct submission. The
    verifier runs as root, so it grants the read here instead of relaxing the
    privilege drop.
    """
    for path in (script, script.parent, script.parent.parent):
        try:
            readable = 0o044 if path.is_file() else 0o055
            path.chmod(path.stat().st_mode | readable)
        except OSError:
            pass


def _run_agent(workspace: Path, root: Path, out: Path) -> bool:
    """Run the delivered program on one corpus. Returns True when it exits 0."""
    script = workspace / "out" / "derive_report.py"
    if not script.is_file():
        return False
    _grant_read(script)
    out.mkdir(parents=True, exist_ok=True)
    out.chmod(0o777)
    proc = subprocess.Popen(_agent_argv(script, root, out),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=dict(SAFE_ENV), cwd="/tmp", start_new_session=True)
    try:
        proc.communicate(timeout=AGENT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
        proc.communicate()
        return False
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            pass
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Strict comparison. Numbers must match by type as well as value, because the
# contract requires integer micro-jansky throughout: 25089.0 and True are not
# acceptable spellings of 25089.
# ---------------------------------------------------------------------------
def _same(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a is b
    return type(a) is type(b) and a == b


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fields_match(out_dir: Path, name: str, expected: dict[str, Any], fields: list[str]) -> bool:
    """Compare only the named top-level fields of one artifact, so a check pays
    for the decision it is named after and not for the whole pipeline."""
    got = _read_json(out_dir / name)
    if not isinstance(got, dict):
        return False
    return all(_same(got.get(f), expected[f]) for f in fields)


def _obs_field_match(out_dir: Path, expected: dict[str, Any], fields: list[str]) -> bool:
    """Compare per-observation fields of reconciled_flux.json by obs_id."""
    got = _read_json(out_dir / "reconciled_flux.json")
    exp_rows = expected["reconciled_flux.json"]["observations"]
    if not isinstance(got, dict) or not isinstance(got.get("observations"), list):
        return False
    got_by_id = {}
    for r in got["observations"]:
        if not isinstance(r, dict) or "obs_id" not in r:
            return False
        got_by_id[r["obs_id"]] = r
    if set(got_by_id) != {r["obs_id"] for r in exp_rows}:
        return False
    for er in exp_rows:
        gr = got_by_id[er["obs_id"]]
        if not all(_same(gr.get(f), er[f]) for f in fields):
            return False
    return True


def _corpus_file_count(root: Path) -> int:
    return len([p for p in root.iterdir() if p.is_file()])


def _all_match(out_dir: Path, expected: dict[str, Any], names: list[str]) -> bool:
    for name in names:
        if not _same(_read_json(out_dir / name), expected[name]):
            return False
    return True


def _seeded_case(workspace: Path, seed: int, n: int, mutations: dict[str, Any] | None):
    """Build a corpus, run the agent program on it, return (out_dir, expected).
    The caller works inside the `with` block."""
    return _CaseCtx(workspace, seed, n, mutations)


class _CaseCtx:
    def __init__(self, workspace, seed, n, mutations):
        self.workspace, self.seed, self.n, self.mutations = workspace, seed, n, mutations
        self._td = None

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        td = Path(self._td.name)
        td.chmod(0o777)
        root = write_case(td / "data", self.seed, self.n, self.mutations)
        out = td / "out"
        ok = _run_agent(self.workspace, root, out)
        expected = ref_derive(self.seed, self.n, self.mutations)
        expected["data_quality.json"]["input_file_count"] = _corpus_file_count(root)
        return ok, out, expected

    def __exit__(self, *exc):
        if self._td:
            self._td.cleanup()
        return False


class _ExplicitCtx:
    """A corpus built from an explicit observation list, for fixtures that must
    contain a specific condition (an exact-half median, a flux tie)."""

    def __init__(self, workspace, obs, masked=None, disputed=None, mutations=None):
        self.workspace, self.obs = workspace, obs
        self.masked = masked or {}
        self.disputed = set(disputed or ())
        self.mutations = mutations or {}
        self._td = None

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        td = Path(self._td.name)
        td.chmod(0o777)
        tables = tables_for(self.mutations)
        root = build_corpus(td / "data", self.obs, tables, self.masked, self.disputed, self.mutations)
        out = td / "out"
        ok = _run_agent(self.workspace, root, out)
        expected = ref_derive_from(self.obs, tables, self.masked, self.disputed, self.mutations)
        expected["data_quality.json"]["input_file_count"] = _corpus_file_count(root)
        return ok, out, expected

    def __exit__(self, *exc):
        if self._td:
            self._td.cleanup()
        return False


def _delivered_py_source(workspace: Path) -> str:
    """Source of every .py the agent left in the output directory, read as
    bytes and decoded leniently so a hostile encoding cannot abort the check."""
    chunks = []
    for p in sorted((workspace / "out").glob("*.py")):
        chunks.append(p.read_bytes().decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def _delivered_all_text(workspace: Path) -> str:
    chunks = [_delivered_py_source(workspace)]
    for name in ARTIFACT_NAMES:
        p = workspace / "out" / name
        if p.is_file():
            chunks.append(p.read_bytes().decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def _ok(fn, *args) -> bool:
    """Run one check body. A check never raises: an exception here would abort
    the whole run and no reward would be written."""
    try:
        return bool(fn(*args))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# The shipped extract. The grading container has no /app/data, so the expected
# figures for the extract the agent was actually given are fixed here, derived
# from that corpus at authoring time (the same build-time-constant pattern the
# template uses for a shipped input's hash).
# ---------------------------------------------------------------------------
SHIPPED: dict[str, Any] = {
    "anomalies": [],
    "band_flux_ujy": {
        "g": 4426602,
        "i": 4716841,
        "r": 4720032,
        "u": 4210940,
        "z": 4473599
    },
    "band_median_ujy": {
        "g": 83131,
        "i": 98926,
        "r": 98548,
        "u": 69715,
        "z": 90031
    },
    "band_observation_count": {
        "g": 57,
        "i": 47,
        "r": 47,
        "u": 50,
        "z": 46
    },
    "channel_usage": {
        "A0": 26,
        "A2": 46,
        "B0": 49,
        "B3": 37,
        "C1": 89
    },
    "dropped_count": 13,
    "dropped_obs_ids": [
        "o00021",
        "o00029",
        "o00075",
        "o00077",
        "o00104",
        "o00113",
        "o00114",
        "o00123",
        "o00170",
        "o00174",
        "o00188",
        "o00210",
        "o00234"
    ],
    "epoch_flux_ujy": {
        "E1": 8039491,
        "E2": 6110020,
        "E3": 8398503
    },
    "epoch_observation_count": {
        "E1": 89,
        "E2": 76,
        "E3": 82
    },
    "instrument_flux_ujy": {
        "G1": 4353883,
        "G2": 6909967,
        "G3": 4948662,
        "G4": 6335502
    },
    "instrument_observation_count": {
        "G1": 52,
        "G2": 65,
        "G3": 64,
        "G4": 66
    },
    "live_count": 247,
    "masked_pixel_count": 13,
    "observation_count": 260,
    "report_id": "detector-flux-reconciliation",
    "suspect_but_not_disputed": [
        "o00001",
        "o00006",
        "o00014",
        "o00019",
        "o00030",
        "o00044",
        "o00045",
        "o00050",
        "o00054",
        "o00060",
        "o00062",
        "o00071",
        "o00085",
        "o00087",
        "o00088",
        "o00095",
        "o00115",
        "o00121",
        "o00122",
        "o00127",
        "o00135",
        "o00136",
        "o00139",
        "o00156",
        "o00165",
        "o00177",
        "o00191",
        "o00194",
        "o00208",
        "o00247",
        "o00253",
        "o00258"
    ],
    "total_reconciled_flux_ujy": 22548014
}

SHIPPED_SETTLEMENT: dict[str, Any] = {
    "band_settlement_rows": [
        ["u", 49, 73054482],
        ["g", 57, 75865627],
        ["r", 43, 75192628],
        ["i", 46, 85238455],
        ["z", 45, 69937383]
    ],
    "cosmic_ray_rejects": [
        {"band": "r", "group_mad": 553133, "group_median": 1513066, "instrument": "G3",
         "obs_id": "o00099", "rate_ujy_per_ks": 4913733, "threshold": 4831864},
        {"band": "i", "group_mad": 626061, "group_median": 718111, "instrument": "G4",
         "obs_id": "o00222", "rate_ujy_per_ks": 5515466, "threshold": 4474477},
        {"band": "u", "group_mad": 506436, "group_median": 1060255, "instrument": "G4",
         "obs_id": "o00224", "rate_ujy_per_ks": 5518200, "threshold": 4098871}
    ],
    "near_saturated_count": 2,
    "near_saturation_observations": [
        {"full_well_counts": 60500, "instrument": "G4", "obs_id": "o00017",
         "raw_counts": 59777},
        {"full_well_counts": 60500, "instrument": "G4", "obs_id": "o00059",
         "raw_counts": 59708}
    ],
    "rejected_count": 3,
    "settled_attributed_ujy": {"G1": 84286350, "G2": 105357938, "G3": 73750556,
                               "G4": 115893731},
    "settled_count": 240,
    "settled_pool_ujy": 379288575,
    "settlement_digest": 893107,
    "settlement_order_length": 240,
    "settlement_order_head": [
        {"obs_id": "o00213", "position": 1, "rate_ujy_per_ks": 6062933},
        {"obs_id": "o00156", "position": 2, "rate_ujy_per_ks": 6037300},
        {"obs_id": "o00108", "position": 3, "rate_ujy_per_ks": 5415800}
    ],
    "zero_exposure_count": 4,
    "zero_exposure_observations": [
        {"obs_id": "o00007", "shutter_state": "aborted"},
        {"obs_id": "o00061", "shutter_state": "aborted"},
        {"obs_id": "o00134", "shutter_state": "aborted"},
        {"obs_id": "o00208", "shutter_state": "aborted"}
    ]
}

# Fixtures that force a rule the random corpora never exercise: an exact-half
# band median, and two live observations with identical flux so the tie-break
# decides the ranking.
HALF_MEDIAN_OBS: list[dict] = [
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "hm001",
        "pixel": "pm001",
        "quality_flag": "ok",
        "raw_counts": 4000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "hm002",
        "pixel": "pm002",
        "quality_flag": "ok",
        "raw_counts": 9000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "hm003",
        "pixel": "pm003",
        "quality_flag": "ok",
        "raw_counts": 20001,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "hm004",
        "pixel": "pm004",
        "quality_flag": "ok",
        "raw_counts": 38000,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "instrument": "G2",
        "mjd": 59050,
        "obs_id": "hm005",
        "pixel": "pm005",
        "quality_flag": "ok",
        "raw_counts": 4000,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "instrument": "G2",
        "mjd": 59050,
        "obs_id": "hm006",
        "pixel": "pm006",
        "quality_flag": "ok",
        "raw_counts": 9000,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "instrument": "G2",
        "mjd": 59050,
        "obs_id": "hm007",
        "pixel": "pm007",
        "quality_flag": "ok",
        "raw_counts": 20001,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "instrument": "G2",
        "mjd": 59050,
        "obs_id": "hm008",
        "pixel": "pm008",
        "quality_flag": "ok",
        "raw_counts": 38000,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "instrument": "G4",
        "mjd": 59050,
        "obs_id": "hm009",
        "pixel": "pm009",
        "quality_flag": "ok",
        "raw_counts": 6000,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "instrument": "G4",
        "mjd": 59050,
        "obs_id": "hm010",
        "pixel": "pm010",
        "quality_flag": "ok",
        "raw_counts": 9000,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "instrument": "G4",
        "mjd": 59050,
        "obs_id": "hm011",
        "pixel": "pm011",
        "quality_flag": "ok",
        "raw_counts": 60000,
        "written_gain": "C1"
    }
]
TIE_OBS: list[dict] = [
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "tie01",
        "pixel": "pt001",
        "quality_flag": "ok",
        "raw_counts": 15000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "tie02",
        "pixel": "pt002",
        "quality_flag": "ok",
        "raw_counts": 15000,
        "written_gain": "C1"
    },
    {
        "band": "i",
        "instrument": "G2",
        "mjd": 59050,
        "obs_id": "tie03",
        "pixel": "pt003",
        "quality_flag": "ok",
        "raw_counts": 22000,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "instrument": "G3",
        "mjd": 59050,
        "obs_id": "tie04",
        "pixel": "pt004",
        "quality_flag": "ok",
        "raw_counts": 8000,
        "written_gain": "C1"
    }
]
# diagnostic_codes.txt E01: a negative net after dark subtraction is retained
# rather than clamped. Seeded corpora draw raw_counts from 200 up and the
# largest dark current is 72, so only an explicit fixture reaches this case.
# neg01 sits far below its dark current and neg02 one count below its own.
# Contract S7 breaks a settled-rate tie by the S4 photometric band order. No
# observation of the shipped extract ties with another on its settled rate, so
# on that extract the band term decides nothing and a solver ranking ties any
# other way still reproduces the reference. These five observations create the
# tie the shipped extract lacks: each carries the per-band dark current added
# back to one common net of 14955, so S1 settles all five at the same rate, and
# each sits alone in its own instrument-and-band group, so S2's small-cohort
# exemption retains all five. The obs_ids run counter to the photometric order
# on purpose, so a solver that drops the band term and falls back on obs_id
# emits the exact reverse sequence and is caught.
BAND_TIE_OBS: list[dict] = [
    {
        "band": "u",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "bt05",
        "pixel": "pb001",
        "quality_flag": "ok",
        "raw_counts": 15000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "bt04",
        "pixel": "pb002",
        "quality_flag": "ok",
        "raw_counts": 14992,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "bt03",
        "pixel": "pb003",
        "quality_flag": "ok",
        "raw_counts": 14985,
        "written_gain": "C1"
    },
    {
        "band": "i",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "bt02",
        "pixel": "pb004",
        "quality_flag": "ok",
        "raw_counts": 14990,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "bt01",
        "pixel": "pb005",
        "quality_flag": "ok",
        "raw_counts": 15015,
        "written_gain": "C1"
    }
]


# Contract S8 calls an observation near-saturated when its raw counts REACH or
# exceed 98 percent of its instrument ceiling. No observation of the shipped
# extract lands on that boundary, so there the "reach" half of the rule decides
# nothing and a solver reading it as a strict inequality still reproduces the
# reference. ns01 sits exactly on it: 60760 * 100 == 62000 * 98, and 60760 stays
# under the G1 ceiling so S8's "not already saturated" clause still admits it.
S8_BOUNDARY_OBS: list[dict] = [
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "ns01",
        "pixel": "pn001",
        "quality_flag": "ok",
        "raw_counts": 60760,
        "written_gain": "C1"
    },
    {
        "band": "r",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "ns02",
        "pixel": "pn002",
        "quality_flag": "ok",
        "raw_counts": 15000,
        "written_gain": "C1"
    },
    {
        "band": "u",
        "exposure_ms": 60000,
        "instrument": "G2",
        "mjd": 59050,
        "obs_id": "ns03",
        "pixel": "pn003",
        "quality_flag": "ok",
        "raw_counts": 20000,
        "written_gain": "A0"
    }
]


# Contract S2 rejects an observation whose settled rate stands STRICTLY above
# its group threshold of med + COSMIC_RAY_SIGMA * mad. No observation of the
# shipped extract lands on a threshold, so there the strict half of the rule
# decides nothing. These five share the (G1, g) group, which is large enough
# to escape the small-cohort exemption, and their settled rates are 620177,
# 620177, 620266, 620355 and 620800. The lower-middle median of those is
# 620266 and the lower-middle median of the absolute deviations is 89, so with
# sigma 6 the threshold is 620800 and cr05 sits exactly on it. The stated
# reading retains cr05; a '>=' reading rejects it and moves both the reject
# list and the settlement order.
S2_THRESHOLD_OBS: list[dict] = [
    {
        "band": "g",
        "exposure_ms": 45000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "cr01",
        "pixel": "pc001",
        "quality_flag": "ok",
        "raw_counts": 10458,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 45000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "cr02",
        "pixel": "pc002",
        "quality_flag": "ok",
        "raw_counts": 10458,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "cr03",
        "pixel": "pc003",
        "quality_flag": "ok",
        "raw_counts": 13800,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 45000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "cr04",
        "pixel": "pc004",
        "quality_flag": "ok",
        "raw_counts": 10461,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 90000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "cr05",
        "pixel": "pc005",
        "quality_flag": "ok",
        "raw_counts": 20318,
        "written_gain": "C1"
    }
]


# The anomaly rule flags a live observation whose flux stands STRICTLY above
# three times its band median. No shipped observation sits on that multiple,
# so there the strict half decides nothing. These five share band g, so the
# median is the third of the five by flux, 32357, and an05 carries exactly
# 97071 = 3 * 32357. The stated reading leaves an05 unflagged; a '>=' reading
# flags it and changes the anomaly ledger.
ANOMALY_BOUNDARY_OBS: list[dict] = [
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "an01",
        "pixel": "pa001",
        "quality_flag": "ok",
        "raw_counts": 9000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "an02",
        "pixel": "pa002",
        "quality_flag": "ok",
        "raw_counts": 10500,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "an03",
        "pixel": "pa003",
        "quality_flag": "ok",
        "raw_counts": 12063,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "an04",
        "pixel": "pa004",
        "quality_flag": "ok",
        "raw_counts": 20000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "exposure_ms": 60000,
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "an05",
        "pixel": "pa005",
        "quality_flag": "ok",
        "raw_counts": 33964,
        "written_gain": "C1"
    }
]


NEGATIVE_NET_OBS: list[dict] = [
    {
        "band": "z",
        "instrument": "G2",
        "mjd": 59300,
        "obs_id": "neg01",
        "pixel": "pn001",
        "quality_flag": "ok",
        "raw_counts": 10,
        "written_gain": "C1"
    },
    {
        "band": "u",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "neg02",
        "pixel": "pn002",
        "quality_flag": "ok",
        "raw_counts": 44,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "instrument": "G2",
        "mjd": 59310,
        "obs_id": "pos01",
        "pixel": "pn003",
        "quality_flag": "ok",
        "raw_counts": 30000,
        "written_gain": "C1"
    },
    {
        "band": "u",
        "instrument": "G1",
        "mjd": 59060,
        "obs_id": "pos02",
        "pixel": "pn004",
        "quality_flag": "ok",
        "raw_counts": 25000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G3",
        "mjd": 59180,
        "obs_id": "pos03",
        "pixel": "pn005",
        "quality_flag": "ok",
        "raw_counts": 18000,
        "written_gain": "C1"
    }
]
# Trigger fixture for two rules no other corpus reaches. The shipped extract
# and every seeded corpus populate all five bands, all three epochs and all
# four instruments, and none of them yields an anomaly. Only bands g and z,
# epochs E1 and E3 and instruments G1 and G2 appear below, so the rollups must
# zero-fill the absent keys (report_schema.md), and rnd03 clears three times
# its band median so one observation element has to be rendered.
RENDERING_OBS: list[dict] = [
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59050,
        "obs_id": "rnd01",
        "pixel": "pr001",
        "quality_flag": "ok",
        "raw_counts": 1000,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59060,
        "obs_id": "rnd02",
        "pixel": "pr002",
        "quality_flag": "ok",
        "raw_counts": 1100,
        "written_gain": "C1"
    },
    {
        "band": "g",
        "instrument": "G1",
        "mjd": 59070,
        "obs_id": "rnd03",
        "pixel": "pr003",
        "quality_flag": "ok",
        "raw_counts": 60000,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "instrument": "G2",
        "mjd": 59300,
        "obs_id": "rnd04",
        "pixel": "pr004",
        "quality_flag": "ok",
        "raw_counts": 20000,
        "written_gain": "C1"
    },
    {
        "band": "z",
        "instrument": "G2",
        "mjd": 59310,
        "obs_id": "rnd05",
        "pixel": "pr005",
        "quality_flag": "ok",
        "raw_counts": 21000,
        "written_gain": "C1"
    }
]

# Full-well fixture. Every seeded corpus draws raw_counts at or below 60000, so
# nothing in one ever reaches a ceiling; these rows straddle each ceiling
# deliberately. sat02, sat04 and sat05 sit exactly at or just below the full
# well and are NOT clipped, sat01, sat03 and sat06 sit above it and are.
SATURATION_OBS: list[dict] = [
    {"obs_id": "sat01", "instrument": "G1", "band": "g", "mjd": 59050,
     "written_gain": "C1", "raw_counts": 70000, "pixel": "ps001", "quality_flag": "ok"},
    {"obs_id": "sat02", "instrument": "G1", "band": "g", "mjd": 59051,
     "written_gain": "C1", "raw_counts": 62000, "pixel": "ps002", "quality_flag": "ok"},
    {"obs_id": "sat03", "instrument": "G4", "band": "r", "mjd": 59250,
     "written_gain": "C1", "raw_counts": 60501, "pixel": "ps003", "quality_flag": "ok"},
    {"obs_id": "sat04", "instrument": "G4", "band": "r", "mjd": 59251,
     "written_gain": "C1", "raw_counts": 60500, "pixel": "ps004", "quality_flag": "ok"},
    {"obs_id": "sat05", "instrument": "G2", "band": "z", "mjd": 59130,
     "written_gain": "C1", "raw_counts": 61499, "pixel": "ps005", "quality_flag": "ok"},
    {"obs_id": "sat06", "instrument": "G3", "band": "i", "mjd": 59300,
     "written_gain": "C1", "raw_counts": 99999, "pixel": "ps006", "quality_flag": "ok"},
]

# Median-eligibility fixture. Band g carries three eligible rows and one clipped
# row whose flux clears three times their median; band r carries nothing but
# clipped rows; band z carries five eligible rows plus a genuine outlier. Every
# eligible sample here is an odd count, so each median is a middle element and
# never an exact half: this fixture decides membership of the sample, and the
# half-even rounding of a median is decided by HALF_MEDIAN_OBS instead.
MEDIAN_EXCLUSION_OBS: list[dict] = [
    {"obs_id": "mx01", "instrument": "G1", "band": "g", "mjd": 59050,
     "written_gain": "C1", "raw_counts": 2000, "pixel": "pm101", "quality_flag": "ok"},
    {"obs_id": "mx02", "instrument": "G1", "band": "g", "mjd": 59051,
     "written_gain": "C1", "raw_counts": 3000, "pixel": "pm102", "quality_flag": "ok"},
    {"obs_id": "mx03", "instrument": "G1", "band": "g", "mjd": 59052,
     "written_gain": "C1", "raw_counts": 4000, "pixel": "pm103", "quality_flag": "ok"},
    {"obs_id": "mx04", "instrument": "G1", "band": "g", "mjd": 59053,
     "written_gain": "C1", "raw_counts": 70000, "pixel": "pm104", "quality_flag": "ok"},
    {"obs_id": "mx05", "instrument": "G4", "band": "r", "mjd": 59250,
     "written_gain": "C1", "raw_counts": 60501, "pixel": "pm105", "quality_flag": "ok"},
    {"obs_id": "mx06", "instrument": "G4", "band": "r", "mjd": 59251,
     "written_gain": "C1", "raw_counts": 61000, "pixel": "pm106", "quality_flag": "ok"},
    {"obs_id": "mx07", "instrument": "G2", "band": "z", "mjd": 59130,
     "written_gain": "C1", "raw_counts": 2000, "pixel": "pm107", "quality_flag": "ok"},
    {"obs_id": "mx08", "instrument": "G2", "band": "z", "mjd": 59131,
     "written_gain": "C1", "raw_counts": 2100, "pixel": "pm108", "quality_flag": "ok"},
    {"obs_id": "mx09", "instrument": "G2", "band": "z", "mjd": 59132,
     "written_gain": "C1", "raw_counts": 2200, "pixel": "pm109", "quality_flag": "ok"},
    {"obs_id": "mx10", "instrument": "G2", "band": "z", "mjd": 59133,
     "written_gain": "C1", "raw_counts": 2300, "pixel": "pm110", "quality_flag": "ok"},
    {"obs_id": "mx11", "instrument": "G2", "band": "z", "mjd": 59134,
     "written_gain": "C1", "raw_counts": 30000, "pixel": "pm111", "quality_flag": "ok"},
]

# Relay-chain fixture. Two independent chains whose terminal sets differ, so an
# audit that reports direct targets rather than following masked hops disagrees
# on pa001, pa002 and pb001 while still agreeing on pb003.
DEEP_RELAY_OBS: list[dict] = [
    {"obs_id": "rel01", "instrument": "G1", "band": "g", "mjd": 59050,
     "written_gain": "C1", "raw_counts": 11000, "pixel": "pa001", "quality_flag": "ok"},
    {"obs_id": "rel02", "instrument": "G1", "band": "g", "mjd": 59051,
     "written_gain": "C1", "raw_counts": 13000, "pixel": "pa002", "quality_flag": "ok"},
    {"obs_id": "rel03", "instrument": "G2", "band": "r", "mjd": 59052,
     "written_gain": "C1", "raw_counts": 17000, "pixel": "pa003", "quality_flag": "ok"},
    {"obs_id": "rel04", "instrument": "G2", "band": "r", "mjd": 59053,
     "written_gain": "C1", "raw_counts": 19000, "pixel": "pa004", "quality_flag": "ok"},
    {"obs_id": "rel05", "instrument": "G3", "band": "z", "mjd": 59054,
     "written_gain": "C1", "raw_counts": 23000, "pixel": "pb001", "quality_flag": "ok"},
    {"obs_id": "rel06", "instrument": "G3", "band": "z", "mjd": 59055,
     "written_gain": "C1", "raw_counts": 29000, "pixel": "pb002", "quality_flag": "ok"},
    {"obs_id": "rel07", "instrument": "G4", "band": "i", "mjd": 59056,
     "written_gain": "C1", "raw_counts": 31000, "pixel": "pb003", "quality_flag": "ok"},
    {"obs_id": "rel08", "instrument": "G4", "band": "i", "mjd": 59057,
     "written_gain": "C1", "raw_counts": 37000, "pixel": "pb004", "quality_flag": "ok"},
]

DEEP_RELAY_MASKED: dict[str, list[str]] = {
    "pa001": ["pa002"],
    "pa002": ["pa003", "pa004"],
    "pb001": ["pb002", "pb003"],
    "pb003": ["pb004"],
}


# ---------------------------------------------------------------------------
# Delivery and shape.
# ---------------------------------------------------------------------------
def _artifact_set(workspace: Path) -> bool:
    out = workspace / "out"
    if not (out / "derive_report.py").is_file():
        return False
    for name in ARTIFACT_NAMES:
        if not (out / name).is_file():
            return False
    for name in CORE_JSON:
        if not isinstance(_read_json(out / name), dict):
            return False
    return True


@criterion(description="the reusable program and all 78 declared report artifacts exist at /app/out and every core JSON parses as an object")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    return _ok(_artifact_set, workspace)


def _summary_schema(workspace: Path) -> bool:
    data = _read_json(workspace / "out" / "summary.json")
    return isinstance(data, dict) and set(data) == {
        "report_id", "observation_count", "live_count", "dropped_count",
        "total_reconciled_flux_ujy", "band_flux_ujy", "epoch_flux_ujy",
        "instrument_flux_ujy", "channel_usage", "band_median_ujy"}


@criterion(description="summary.json carries exactly the top-level keys the report schema names")
def summary_schema_is_exact(workspace: Path) -> bool:
    return _ok(_summary_schema, workspace)


def _deterministic_serialisation(workspace: Path) -> bool:
    """instruction.md: sorted keys and a trailing newline on every JSON."""
    out = workspace / "out"
    for name in CORE_JSON:
        raw = (out / name).read_text(encoding="utf-8")
        if not raw.endswith("\n"):
            return False
        obj = json.loads(raw)
        if raw != json.dumps(obj, indent=2, sort_keys=True) + "\n":
            return False
    return True


@criterion(description="every delivered JSON artifact is serialized with sorted keys and a trailing newline, byte for byte")
def delivered_json_is_sorted_with_trailing_newline(workspace: Path) -> bool:
    return _ok(_deterministic_serialisation, workspace)


# ---------------------------------------------------------------------------
# The shipped extract the agent was given, graded against the fixed figures.
# ---------------------------------------------------------------------------
def _shipped_headline(workspace: Path) -> bool:
    data = _read_json(workspace / "out" / "summary.json")
    return all(_same(data.get(k), SHIPPED[k]) for k in
               ("report_id", "observation_count", "live_count", "dropped_count",
                "total_reconciled_flux_ujy"))


@criterion(description="summary.json for the shipped extract carries the correct report id, observation, live and dropped counts and total reconciled flux")
def shipped_summary_headline_exact(workspace: Path) -> bool:
    return _ok(_shipped_headline, workspace)


def _shipped_rollups(workspace: Path) -> bool:
    data = _read_json(workspace / "out" / "summary.json")
    return all(_same(data.get(k), SHIPPED[k]) for k in
               ("band_flux_ujy", "epoch_flux_ujy", "instrument_flux_ujy",
                "channel_usage", "band_median_ujy"))


@criterion(description="the per-band, per-epoch, per-instrument, channel-usage and band-median rollups for the shipped extract match the reference")
def shipped_rollups_exact(workspace: Path) -> bool:
    return _ok(_shipped_rollups, workspace)


def _shipped_dropped(workspace: Path) -> bool:
    out = workspace / "out"
    dropped = _read_json(out / "dropped_observations.json")
    dq = _read_json(out / "data_quality.json")
    return (_same(dropped.get("dropped_obs_ids"), SHIPPED["dropped_obs_ids"])
            and _same(dq.get("disputed_count"), SHIPPED["dropped_count"])
            and _same(dq.get("suspect_but_not_disputed"), SHIPPED["suspect_but_not_disputed"]))


@criterion(description="the dropped-observation list and the suspect-but-not-disputed list for the shipped extract match the PDF adjudication")
def shipped_dropped_list_exact(workspace: Path) -> bool:
    return _ok(_shipped_dropped, workspace)


# ---------------------------------------------------------------------------
# Generalisation: the program re-run on extracts it has not seen.
# ---------------------------------------------------------------------------
def _full_case(workspace: Path, seed: int, n: int) -> bool:
    with _seeded_case(workspace, seed, n, None) as (ok, out, expected):
        return ok and _all_match(out, expected, CORE_JSON)


@criterion(description="the delivered program reconciles an unseen extract in the same schema to the reference on every core artifact")
def program_reconciles_unseen_extract(workspace: Path) -> bool:
    return _ok(_full_case, workspace, EVAL_SEED, 240)


@criterion(description="the delivered program reconciles a second, differently seeded unseen extract to the reference on every core artifact")
def program_reconciles_second_unseen_extract(workspace: Path) -> bool:
    return _ok(_full_case, workspace, CHALLENGE_SEED, 220)


@criterion(description="the delivered program reconciles a third unseen extract of a different size to the reference on every core artifact")
def program_reconciles_third_unseen_extract(workspace: Path) -> bool:
    return _ok(_full_case, workspace, THIRD_EVAL_SEED, 260)


@criterion(description="the delivered program reconciles a fourth unseen extract to the reference on every core artifact")
def program_reconciles_fourth_unseen_extract(workspace: Path) -> bool:
    return _ok(_full_case, workspace, FOURTH_EVAL_SEED, 200)


@criterion(description="the delivered program reconciles a fifth unseen extract carrying a smaller observation corpus to the reference on every core artifact")
def program_reconciles_fifth_unseen_extract(workspace: Path) -> bool:
    return _ok(_full_case, workspace, FIFTH_EVAL_SEED, 160)


# ---------------------------------------------------------------------------
# One check per hidden decision. Each owns its own corpus and compares only the
# fields its decision moves, so one wrong decision costs one decision.
# ---------------------------------------------------------------------------
def _scale(workspace: Path) -> bool:
    mut = {"factor_micro": {"G1": 1_100_000, "G3": 950_000}}
    with _seeded_case(workspace, SCALE_SEED, 180, mut) as (ok, out, expected):
        return (ok
                and _fields_match(out, "calibration_audit.json",
                                  expected["calibration_audit.json"], ["scale_factor_micro"])
                and _obs_field_match(out, expected, ["calibrated_flux_ujy"]))


@criterion(description="perturbing the workbook scale factor moves every calibrated flux exactly as recomputed, proving the factor is read from the workbook and divided by 1e6")
def scale_factor_is_read_and_divided(workspace: Path) -> bool:
    return _ok(_scale, workspace)


def _drift(workspace: Path) -> bool:
    with _seeded_case(workspace, DRIFT_SEED, 180, {"drift_bump": 500}) as (ok, out, expected):
        return ok and _obs_field_match(out, expected,
                                       ["drift_ppm", "drift_correction", "calibrated_flux_ujy"])


@criterion(description="bumping drift_ppm moves the drift correction and the flux exactly as recomputed, proving the correction is subtracted and rounded half-even")
def drift_correction_is_subtracted(workspace: Path) -> bool:
    return _ok(_drift, workspace)


def _epoch(workspace: Path) -> bool:
    mut = {"epoch_mjd": {"E1": [59000, 59100], "E2": [59100, 59250], "E3": [59250, 59360]}}
    with _seeded_case(workspace, EPOCH_SEED, 180, mut) as (ok, out, expected):
        return (ok and _obs_field_match(out, expected, ["epoch"])
                and _fields_match(out, "epoch_totals.json",
                                  expected["epoch_totals.json"], ["epoch_observation_count"]))


@criterion(description="moving the epoch mjd boundaries reclassifies observations exactly as recomputed, proving half-open interval resolution")
def epoch_intervals_are_half_open(workspace: Path) -> bool:
    return _ok(_epoch, workspace)


def _fold(workspace: Path) -> bool:
    mut = {"gain_micro": {"A2": 2_000_000, "B3": 2_900_000}}
    with _seeded_case(workspace, FOLD_SEED, 180, mut) as (ok, out, expected):
        return (ok and _obs_field_match(out, expected, ["resolved_channel", "calibrated_flux_ujy"])
                and _fields_match(out, "summary.json", expected["summary.json"], ["channel_usage"]))


@criterion(description="perturbing only the post-fold channel gains moves the flux exactly as recomputed, proving the gain label is resolved through the epoch fold before its yield is looked up")
def gain_fold_resolved_before_lookup(workspace: Path) -> bool:
    return _ok(_fold, workspace)


def _mask(workspace: Path) -> bool:
    with _seeded_case(workspace, MASK_SEED, 180, {"more_masking": True}) as (ok, out, expected):
        return ok and _fields_match(out, "deadpixel_closure.json",
                                    expected["deadpixel_closure.json"],
                                    ["resolved_pixel_flux_ujy", "total_after_closure_ujy"])


@criterion(description="raising the dead-pixel mask rate changes the closure exactly as recomputed, proving redistribution is resolved to its least fixed point across multi-hop chains")
def deadpixel_closure_is_least_fixed_point(workspace: Path) -> bool:
    return _ok(_mask, workspace)


def _disputed(workspace: Path) -> bool:
    with _seeded_case(workspace, DISPUTE_SEED, 180, None) as (ok, out, expected):
        return (ok
                and _fields_match(out, "dropped_observations.json",
                                  expected["dropped_observations.json"], ["dropped_obs_ids"])
                and _fields_match(out, "data_quality.json", expected["data_quality.json"],
                                  ["disputed_count", "suspect_but_not_disputed"])
                and _obs_field_match(out, expected, ["obs_id"]))


@criterion(description="PDF-adjudicated observations are dropped from every rollup and listed, while rows the csv flags suspect but the dossier clears are retained")
def disputed_adjudication_overrides_flag(workspace: Path) -> bool:
    return _ok(_disputed, workspace)


def _anomaly(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, HALF_MEDIAN_OBS) as (ok, out, expected):
        return (ok
                and _fields_match(out, "anomaly_ledger.json",
                                  expected["anomaly_ledger.json"], ["anomalies"])
                and _fields_match(out, "summary.json", expected["summary.json"], ["band_median_ujy"]))


@criterion(description="the anomaly ledger flags exactly the live observations above three times their band median, with the median itself rounded half-even on an exact-half fixture")
def anomaly_ledger_follows_median_rule(workspace: Path) -> bool:
    return _ok(_anomaly, workspace)


def _ordering(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, TIE_OBS) as (ok, out, expected):
        return ok and _fields_match(out, "ordered_flux_index.json",
                                    expected["ordered_flux_index.json"], ["index"])


def _band_tie_order(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, BAND_TIE_OBS) as (ok, out, expected):
        return ok and _fields_match(out, "settlement_order.json",
                                    expected["settlement_order.json"], ["order"])


def _s8_boundary(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, S8_BOUNDARY_OBS) as (ok, out, expected):
        return ok and _fields_match(out, "near_saturation.json",
                                    expected["near_saturation.json"],
                                    ["observations"])


def _s2_threshold(workspace: Path) -> bool:
    """The correct reject list for this fixture is empty, so the empty list on
    its own cannot be the pass condition: a program that rejects nothing ever,
    or settles nothing at all, would earn the check without doing the work. The
    settled figures the same five rows determine are compared beside it, so the
    credit goes to a run that settled them and then declined to reject the row
    sitting exactly on the threshold. The digest stays out of this comparison;
    settlement_digest_follows_photometric_order owns it."""
    with _ExplicitCtx(workspace, S2_THRESHOLD_OBS) as (ok, out, expected):
        return (ok
                and _fields_match(out, "cosmic_ray_rejects.json",
                                  expected["cosmic_ray_rejects.json"], ["rejects"])
                and _fields_match(out, "settlement_summary.json",
                                  expected["settlement_summary.json"],
                                  ["rejected_count", "settled_count", "settled_pool_ujy"]))


@criterion(description="an observation whose settled rate sits exactly on its group rejection threshold is retained, so the strict half of the S2 inequality decides graded output")
def s2_retains_the_observation_on_the_threshold(workspace: Path) -> bool:
    return _ok(_s2_threshold, workspace)


def _anomaly_boundary(workspace: Path) -> bool:
    """The correct ledger for this fixture is empty, so the empty ledger alone
    cannot be the pass condition: a program that never flags anything would
    earn the check. The band median the boundary is measured against is
    compared beside it, which is the figure the exact multiple is three times
    of, so the credit goes to a run that computed the median and then declined
    to flag the row sitting exactly on three times it."""
    with _ExplicitCtx(workspace, ANOMALY_BOUNDARY_OBS) as (ok, out, expected):
        return (ok
                and _fields_match(out, "anomaly_ledger.json",
                                  expected["anomaly_ledger.json"], ["anomalies"])
                and _fields_match(out, "summary.json",
                                  expected["summary.json"], ["band_median_ujy"]))


@criterion(description="an observation whose flux is exactly three times its band median is not flagged, so the strict half of the anomaly inequality decides graded output")
def anomaly_ledger_excludes_the_exact_multiple(workspace: Path) -> bool:
    return _ok(_anomaly_boundary, workspace)


@criterion(description="an observation whose raw counts land exactly on 98 percent of its instrument ceiling is recorded as near-saturated, so the reach half of the S8 threshold decides graded output")
def near_saturation_includes_the_exact_boundary(workspace: Path) -> bool:
    return _ok(_s8_boundary, workspace)


@criterion(description="the settlement order breaks a settled-rate tie by the photometric band order of S4, on a fixture where five observations share one settled rate and the obs_id order runs counter to the band order")
def settlement_order_breaks_rate_ties_by_band(workspace: Path) -> bool:
    return _ok(_band_tie_order, workspace)


@criterion(description="the ordered flux index ranks live observations by flux descending and breaks ties by obs_id ascending, on a fixture that contains a tie")
def ordering_breaks_ties_by_obs_id(workspace: Path) -> bool:
    return _ok(_ordering, workspace)


def _precedence(workspace: Path) -> bool:
    """The grid's informational dark rows and the workbook's audit sheet both
    disagree with the authoritative source here, so only a program that honours
    precedence reproduces the reference."""
    mut = {"dark_decoy": 7, "factor_decoy": 25_000}
    with _seeded_case(workspace, PRECEDENCE_SEED, 180, mut) as (ok, out, expected):
        return (ok and _obs_field_match(out, expected, ["net_counts", "calibrated_flux_ujy"])
                and _fields_match(out, "calibration_audit.json",
                                  expected["calibration_audit.json"], ["scale_factor_micro"]))


@criterion(description="where the informational dark rows and the workbook audit sheet disagree with the authoritative sources, the authoritative values are the ones applied")
def authoritative_sources_win_over_secondary(workspace: Path) -> bool:
    return _ok(_precedence, workspace)


def _naive(workspace: Path) -> bool:
    """The delivered summary must match the contract reference and must not
    match the fluent default the shipped legacy output was produced with."""
    seed, n = NAIVE_SEED, 180
    with _seeded_case(workspace, seed, n, None) as (ok, out, expected):
        if not ok:
            return False
        produced = _read_json(out / "summary.json")
    naive = _naive_summary(seed, n)
    exp = expected["summary.json"]
    if all(_same(naive[k], exp[k]) for k in naive):
        return False  # the fixture is degenerate, do not pay for it
    for key in ("total_reconciled_flux_ujy", "band_flux_ujy", "epoch_flux_ujy", "instrument_flux_ujy"):
        if not _same(produced.get(key), exp[key]):
            return False
        if _same(produced.get(key), naive[key]):
            return False
    return True


@criterion(description="the delivered summary matches the corrected contract reference and differs from the naive pipeline of written gain label, no scale factor, added drift and half-up rounding")
def naive_pipeline_is_rejected(workspace: Path) -> bool:
    return _ok(_naive, workspace)


def _row_order(workspace: Path) -> bool:
    """Shuffling the input rows must change nothing, and both runs must still
    equal the reference: identical output alone is satisfied by a constant."""
    with _seeded_case(workspace, ROWORDER_SEED, 180, None) as (ok_a, out_a, expected):
        if not (ok_a and _all_match(out_a, expected, CORE_JSON)):
            return False
        bytes_a = {name: (out_a / name).read_bytes() for name in ARTIFACT_NAMES}
    with _seeded_case(workspace, ROWORDER_SEED, 180, {"row_shuffle": True}) as (ok_b, out_b, _e):
        if not ok_b:
            return False
        return all((out_b / name).read_bytes() == bytes_a[name] for name in ARTIFACT_NAMES)


@criterion(description="reordering the input observation rows leaves every artifact byte-identical, and the output still equals the reference rather than merely being constant")
def row_order_independent_and_correct(workspace: Path) -> bool:
    return _ok(_row_order, workspace)


def _hidden_slice(workspace: Path) -> bool:
    """A calibration slice that is not published anywhere in the agent's input,
    so reproducing it is evidence of a working pipeline, not transcription."""
    with _ExplicitCtx(workspace, HIDDEN_SLICE_OBS) as (ok, out, expected):
        return ok and _obs_field_match(
            out, expected, ["epoch", "resolved_channel", "net_counts", "linearized",
                            "drift_correction", "calibrated_flux_ujy"])


@criterion(description="the delivered program reproduces an unpublished calibration slice end to end, including its epoch-boundary and folded-channel rows")
def hidden_calibration_slice_reproduced(workspace: Path) -> bool:
    return _ok(_hidden_slice, workspace)


def _negative_net(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, NEGATIVE_NET_OBS) as (ok, out, expected):
        return ok and _obs_field_match(
            out, expected, ["net_counts", "linearized", "calibrated_flux_ujy"])


@criterion(description="an observation whose raw counts fall below its dark current keeps the negative net through linearization and quantization rather than being clamped at zero")
def net_below_dark_current_is_retained(workspace: Path) -> bool:
    return _ok(_negative_net, workspace)


def _relay_field_match(out_dir: Path, expected: dict[str, Any], fields: list[str]) -> bool:
    """Compare per-pixel fields of relay_audit.json by pixel, so each relay
    check pays for the decision it is named after."""
    got = _read_json(out_dir / "relay_audit.json")
    exp_rows = expected["relay_audit.json"]["relays"]
    if not isinstance(got, dict) or not isinstance(got.get("relays"), list):
        return False
    got_by_pixel = {}
    for r in got["relays"]:
        if not isinstance(r, dict) or "pixel" not in r:
            return False
        got_by_pixel[r["pixel"]] = r
    if set(got_by_pixel) != {r["pixel"] for r in exp_rows}:
        return False
    return all(all(_same(got_by_pixel[er["pixel"]].get(f), er[f]) for f in fields)
               for er in exp_rows)


def _saturation(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, SATURATION_OBS) as (ok, out, expected):
        return (ok
                and _obs_field_match(out, expected, ["effective_counts", "saturated",
                                                     "net_counts", "calibrated_flux_ujy"])
                and _fields_match(out, "data_quality.json", expected["data_quality.json"],
                                  ["saturated_count", "saturated_obs_ids"]))


@criterion(description="a reading above the per-instrument full well is clipped to the ceiling before dark subtraction and marked saturated, and a reading exactly at the full well is left unclipped")
def saturation_clips_at_full_well(workspace: Path) -> bool:
    return _ok(_saturation, workspace)


def _median_eligibility(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, MEDIAN_EXCLUSION_OBS) as (ok, out, expected):
        return (ok
                and _fields_match(out, "summary.json", expected["summary.json"],
                                  ["band_median_ujy"])
                and _fields_match(out, "anomaly_ledger.json",
                                  expected["anomaly_ledger.json"], ["anomalies"]))


@criterion(description="saturated observations leave the band median sample and are never flagged, a band whose live rows are all saturated carries no median at all, and an unsaturated outlier is still flagged")
def saturated_rows_leave_the_band_median(workspace: Path) -> bool:
    return _ok(_median_eligibility, workspace)


def _attribution(workspace: Path) -> bool:
    # These four weights are all distinct, so no remainder ties here and the tie
    # rule is left to its own check. On this corpus the largest-remainder result
    # also differs from all three natural wrong rules: rounding each share on its
    # own, flooring without handing the leftover out, and giving the leftover to
    # the largest share (G4 holds the largest share and is awarded nothing).
    mut = {"exposure_micro": {"G1": 1_050_000, "G2": 2_875_000,
                              "G3": 4_225_000, "G4": 5_375_000}}
    with _seeded_case(workspace, ATTRIB_SEED, 180, mut) as (ok, out, expected):
        return ok and _fields_match(out, "flux_attribution.json",
                                    expected["flux_attribution.json"],
                                    ["pool_ujy", "exposure_weight_micro", "attributed_ujy"])


@criterion(description="the exposure attribution reads the weight table and apportions the closure total into four integers by largest remainder, summing back to the pool exactly")
def attribution_apportions_the_pool_exactly(workspace: Path) -> bool:
    return _ok(_attribution, workspace)


def _attribution_tie(workspace: Path) -> bool:
    with _seeded_case(workspace, TIE_SEED, TIE_SIZE,
                      {"exposure_micro": EQUAL_EXPOSURE}) as (ok, out, expected):
        if not ok or not expected["flux_attribution.json"]["remainder_recipients"]:
            return False  # a leftover of zero would make this fixture decide nothing
        return _fields_match(out, "flux_attribution.json",
                             expected["flux_attribution.json"], ["remainder_recipients"])


@criterion(description="on an extract whose four exposure weights are equal every remainder ties, so the leftover micro-jansky go to the lowest instrument names rather than to the largest shares")
def attribution_ties_break_by_instrument_ascending(workspace: Path) -> bool:
    return _ok(_attribution_tie, workspace)


def _relay_amounts(workspace: Path) -> bool:
    with _seeded_case(workspace, RELAY_SEED, 180, {"more_masking": True}) as (ok, out, expected):
        return ok and _relay_field_match(out, expected, ["relayed_ujy", "per_target_ujy"])


@criterion(description="the relay audit reports the fully accumulated amount each masked pixel hands on, split evenly with the leftover to its first target, rather than the base flux a single pass would relay")
def relay_audit_reports_accumulated_amounts(workspace: Path) -> bool:
    return _ok(_relay_amounts, workspace)


def _relay_terminals(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, DEEP_RELAY_OBS, masked=DEEP_RELAY_MASKED) as (ok, out, expected):
        return ok and _relay_field_match(out, expected, ["targets", "terminal_pixels"])


@criterion(description="on two relay chains of different depth the audit names the unmasked pixels the flux finally reaches, following masked hops transitively instead of stopping at the direct targets")
def relay_audit_terminals_follow_masked_hops(workspace: Path) -> bool:
    return _ok(_relay_terminals, workspace)


def _band_settlement_matches(out: Path, rows: list[list[Any]]) -> bool:
    """Contract S4 fixes the row order of this rendering as the photometric
    order, so the row sequence is compared and not just the row set."""
    text = (out / "band_settlement.csv").read_text(encoding="utf-8")
    got = [r for r in csv.reader(io.StringIO(text), delimiter=",") if r]
    want = [["band", "settled_count", "settled_pool_ujy"]]
    want += [[str(c) for c in row] for row in rows]
    return got == want


def _rate_rows_match(out: Path, expected: dict[str, Any], fields: list[str]) -> bool:
    """Compare per-observation settlement fields of settled_rates.json by
    obs_id, so a check pays for its own decision and not the whole layer."""
    got = _read_json(out / "settled_rates.json")
    want_rows = expected["settled_rates.json"]["rates"]
    if not isinstance(got, dict) or not isinstance(got.get("rates"), list):
        return False
    got_by_id: dict[str, Any] = {}
    for row in got["rates"]:
        if not isinstance(row, dict) or "obs_id" not in row:
            return False
        got_by_id[row["obs_id"]] = row
    if set(got_by_id) != {r["obs_id"] for r in want_rows}:
        return False
    for want_row in want_rows:
        have = got_by_id[want_row["obs_id"]]
        if not all(_same(have.get(f), want_row[f]) for f in fields):
            return False
    return True


@criterion(description="the settled pool and the settlement digest of the shipped extract are the figures contract S5 and S7 give")
def shipped_settlement_headline_exact(workspace: Path) -> bool:
    def body() -> bool:
        doc = _read_json(workspace / "out" / "settlement_summary.json")
        if not isinstance(doc, dict):
            return False
        return all(_same(doc.get(k), SHIPPED_SETTLEMENT[k]) for k in
                   ("settled_pool_ujy", "settlement_digest", "settled_count"))
    return _ok(body)


@criterion(description="the shipped extract reports the frames whose shutter aborted, which contract S1 holds out of the settlement")
def shipped_zero_exposure_list_exact(workspace: Path) -> bool:
    def body() -> bool:
        doc = _read_json(workspace / "out" / "zero_exposure.json")
        if not isinstance(doc, dict):
            return False
        return (_same(doc.get("observations"),
                      SHIPPED_SETTLEMENT["zero_exposure_observations"])
                and _same(_read_json(workspace / "out" / "settlement_summary.json")
                          .get("zero_exposure_count"),
                          SHIPPED_SETTLEMENT["zero_exposure_count"]))
    return _ok(body)


@criterion(description="the shipped extract reports the near-saturated observations contract S8 defines by the integer test against 98 percent of full well")
def shipped_near_saturation_list_exact(workspace: Path) -> bool:
    def body() -> bool:
        doc = _read_json(workspace / "out" / "near_saturation.json")
        if not isinstance(doc, dict):
            return False
        return _same(doc.get("observations"),
                     SHIPPED_SETTLEMENT["near_saturation_observations"])
    return _ok(body)


@criterion(description="the shipped extract reports the cosmic ray rejects with the group median, the deviation and the threshold contract S2 gives")
def shipped_cosmic_ray_rejects_exact(workspace: Path) -> bool:
    def body() -> bool:
        doc = _read_json(workspace / "out" / "cosmic_ray_rejects.json")
        if not isinstance(doc, dict):
            return False
        return _same(doc.get("rejects"), SHIPPED_SETTLEMENT["cosmic_ray_rejects"])
    return _ok(body)


@criterion(description="the shipped band settlement rendering carries its five rows in the photometric order contract S4 fixes")
def shipped_band_settlement_rendering_exact(workspace: Path) -> bool:
    return _ok(_band_settlement_matches, workspace / "out",
               SHIPPED_SETTLEMENT["band_settlement_rows"])


def _settled_rate_floor(workspace: Path) -> bool:
    with _seeded_case(workspace, SETTLE_RATE_SEED, 180, None) as (ok, out, expected):
        return ok and _rate_rows_match(out, expected, ["rate_ujy_per_ks"])


@criterion(description="every settled rate is the floor of the scaled quotient contract S1 states, which differs from the banker's rounding the layer above uses")
def settlement_rate_uses_floor_division(workspace: Path) -> bool:
    return _ok(_settled_rate_floor, workspace)


def _aborted_held_out(workspace: Path) -> bool:
    with _seeded_case(workspace, ABORT_SEED, 160, {"abort_rate": 12}) as (ok, out, expected):
        return (ok
                and _all_match(out, expected, ["zero_exposure.json"])
                and _fields_match(out, "settlement_summary.json",
                                  expected["settlement_summary.json"],
                                  ["zero_exposure_count", "settled_count"]))


@criterion(description="an aborted frame carries no settled rate and is held out of the settled pool as contract S1 requires")
def aborted_shutter_leaves_the_settlement(workspace: Path) -> bool:
    return _ok(_aborted_held_out, workspace)


def _mad_threshold(workspace: Path) -> bool:
    with _seeded_case(workspace, COSMIC_SEED, 200, None) as (ok, out, expected):
        return ok and _all_match(out, expected, ["cosmic_ray_rejects.json"])


@criterion(description="each rejection threshold is the group median plus six times the unscaled median absolute deviation contract S2 names")
def cosmic_ray_threshold_uses_median_absolute_deviation(workspace: Path) -> bool:
    return _ok(_mad_threshold, workspace)


def _small_cohort_exempt(workspace: Path) -> bool:
    with _seeded_case(workspace, SMALL_COHORT_SEED, 14, None) as (ok, out, expected):
        return (ok
                and _all_match(out, expected, ["cosmic_ray_rejects.json"])
                and _fields_match(out, "settlement_summary.json",
                                  expected["settlement_summary.json"],
                                  ["rejected_count", "settled_count"]))


@criterion(description="an instrument and band group holding fewer than four settled observations keeps every one of them, the first exemption contract S2 states")
def small_cohort_is_exempt_from_rejection(workspace: Path) -> bool:
    return _ok(_small_cohort_exempt, workspace)


def _near_saturated_spared(workspace: Path) -> bool:
    with _seeded_case(workspace, NEAR_SAT_SEED, 150, {"near_ceiling": 6}) as (ok, out, expected):
        return (ok
                and _all_match(out, expected, ["near_saturation.json",
                                               "cosmic_ray_rejects.json"])
                and _fields_match(out, "settlement_summary.json",
                                  expected["settlement_summary.json"],
                                  ["near_saturated_count", "rejected_count"]))


@criterion(description="a near-saturated observation survives the cosmic ray rejection, the second exemption contract S2 states")
def near_saturated_row_survives_rejection(workspace: Path) -> bool:
    return _ok(_near_saturated_spared, workspace)


def _lower_middle_median(workspace: Path) -> bool:
    with _seeded_case(workspace, EVEN_SAMPLE_SEED, 190, None) as (ok, out, expected):
        return ok and _all_match(out, expected, ["cosmic_ray_rejects.json"])


@criterion(description="a settlement median over an even sample is the lower of its two middle values as contract S3 requires, not the mean of them")
def settlement_median_takes_the_lower_middle(workspace: Path) -> bool:
    return _ok(_lower_middle_median, workspace)


def _digest_order(workspace: Path) -> bool:
    with _seeded_case(workspace, DIGEST_SEED, 170, None) as (ok, out, expected):
        return (ok
                and _all_match(out, expected, ["settlement_order.json"])
                and _fields_match(out, "settlement_summary.json",
                                  expected["settlement_summary.json"],
                                  ["settlement_digest"]))


@criterion(description="the settlement digest is taken over the rank order contract S7 fixes, whose band tie-break is the photometric order")
def settlement_digest_follows_photometric_order(workspace: Path) -> bool:
    return _ok(_digest_order, workspace)


def _band_rows_photometric(workspace: Path) -> bool:
    with _seeded_case(workspace, BAND_ORDER_SEED, 160, None) as (ok, out, expected):
        return ok and _band_settlement_matches(out, expected["band_settlement.csv"]["rows"])


@criterion(description="the band settlement rendering of an unseen extract carries one row per band in photometric order and zero-fills a band with no surviving observation")
def band_settlement_rows_follow_photometric_order(workspace: Path) -> bool:
    return _ok(_band_rows_photometric, workspace)


def _settled_attribution(workspace: Path) -> bool:
    with _seeded_case(workspace, SETTLE_ATTRIB_SEED, 180, None) as (ok, out, expected):
        if not ok or not _all_match(out, expected, ["settled_attribution.json"]):
            return False
        doc = _read_json(out / "settled_attribution.json")
        shares = doc.get("attributed_ujy")
        if not isinstance(shares, dict) or set(shares) != set(INSTRUMENTS):
            return False
        return sum(shares.values()) == doc.get("settled_pool_ujy")


@criterion(description="the settled pool is apportioned across all four instruments by largest remainder so the four parts sum to it exactly, as contract S6 requires")
def settled_attribution_apportions_the_pool_exactly(workspace: Path) -> bool:
    return _ok(_settled_attribution, workspace)


def _moved_exposure_ledger(workspace: Path) -> bool:
    with _seeded_case(workspace, EXPOSURE_MOVE_SEED, 170,
                      {"exposure_scale": 3}) as (ok, out, expected):
        return (ok
                and _rate_rows_match(out, expected, ["exposure_ms", "rate_ujy_per_ks"])
                and _fields_match(out, "settlement_summary.json",
                                  expected["settlement_summary.json"],
                                  ["settled_pool_ujy", "settlement_digest"]))


@criterion(description="moving the integration times in the exposure ledger moves every settled rate and the settled pool exactly as recomputed, proving the ledger is read rather than assumed")
def settlement_tracks_a_moved_exposure_ledger(workspace: Path) -> bool:
    return _ok(_moved_exposure_ledger, workspace)


def _kv_pairs(text: str) -> dict[str, str]:
    """Every `key: value` line at any indentation, so a nested block and a flat
    listing both read the same way."""
    pairs: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        key, sep, value = stripped.partition(":")
        if sep:
            pairs[key.strip()] = value.strip()
    return pairs


def _rollup_matches(out: Path, name: str, delim: str, first_column: str,
                    keys: tuple[str, ...], flux: dict[str, int],
                    cnt: dict[str, int]) -> bool:
    """report_schema.md fixes the header and the row order of each delimited
    rollup, so both are compared exactly."""
    text = (out / name).read_text(encoding="utf-8")
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delim) if r]
    want = [[first_column, "flux_ujy", "observation_count"]]
    want += [[k, str(flux.get(k, 0)), str(cnt.get(k, 0))] for k in keys]
    return rows == want


def _flagged_xml_matches(out: Path, anomalies: list[dict]) -> bool:
    root = ET.fromstring((out / "flagged_observations.xml").read_text(encoding="utf-8"))
    if root.tag != "flagged_observations":
        return False
    got = [(e.tag, e.get("obs_id"), e.get("band"), e.get("calibrated_flux_ujy"),
            e.get("band_median")) for e in list(root)]
    want = [("observation", a["obs_id"], a["band"], str(a["calibrated_flux_ujy"]),
             str(a["band_median"])) for a in anomalies]
    return got == want


def _renderings_match(out: Path, ref: dict[str, Any]) -> bool:
    """The seven non-JSON artifacts. Every other check reads the JSON side, so
    without this comparison their content is fixed by the schema and graded
    nowhere: an empty file passes the existence and byte-identity checks alike."""
    total = str(ref["total_flux"])
    counts = {"observations": str(ref["observation_count"]),
              "live": str(ref["live_count"]),
              "dropped": str(ref["dropped_count"])}
    anomalies = ref["anomalies"]

    if not _rollup_matches(out, "band_rollup.csv", ",", "band", BANDS,
                           ref["band_flux"], ref["band_cnt"]):
        return False
    if not _rollup_matches(out, "epoch_rollup.tsv", "\t", "epoch", EPOCHS,
                           ref["epoch_flux"], ref["epoch_cnt"]):
        return False
    if not _rollup_matches(out, "instrument_rollup.psv", "|", "instrument",
                           INSTRUMENTS, ref["instr_flux"], ref["instr_cnt"]):
        return False
    if not _flagged_xml_matches(out, anomalies):
        return False

    yaml_text = (out / "objective_summary.yaml").read_text(encoding="utf-8")
    yaml_pairs = _kv_pairs(yaml_text)
    wanted_yaml = {"report_id": REPORT_ID, "total_reconciled_flux_ujy": total,
                   "live_count": counts["live"], "dropped_count": counts["dropped"],
                   "anomaly_count": str(len(anomalies))}
    if any(yaml_pairs.get(k) != v for k, v in wanted_yaml.items()):
        return False
    if any(str(ref["band_flux"].get(b, 0)) not in yaml_text for b in BANDS):
        return False

    status_pairs = _kv_pairs((out / "run_status.txt").read_text(encoding="utf-8"))
    # The status word itself is the agent's own account of its run, so it is
    # required to be present and never read as evidence that the run succeeded.
    if not status_pairs.get("status"):
        return False
    if status_pairs.get("total_reconciled_flux_ujy") != total:
        return False
    if any(status_pairs.get(k) != v for k, v in counts.items()):
        return False

    md_text = (out / "reconciliation_report.md").read_text(encoding="utf-8")
    needed = [REPORT_ID, total, str(ref["masked_pixel_count"]), str(len(anomalies))]
    needed += list(counts.values())
    needed += [str(ref["band_flux"].get(b, 0)) for b in BANDS]
    needed += [str(ref["epoch_flux"].get(e, 0)) for e in EPOCHS]
    return all(tok in md_text for tok in needed)


def _ref_from_expected(expected: dict[str, Any]) -> dict[str, Any]:
    meta = expected["_meta"]
    summary = expected["summary.json"]
    return {"band_flux": meta["band_flux"], "band_cnt": meta["band_cnt"],
            "epoch_flux": meta["epoch_flux"], "epoch_cnt": meta["epoch_cnt"],
            "instr_flux": meta["instr_flux"], "instr_cnt": meta["instr_cnt"],
            "anomalies": meta["anomalies"], "total_flux": meta["total_flux"],
            "observation_count": summary["observation_count"],
            "live_count": summary["live_count"],
            "dropped_count": summary["dropped_count"],
            "masked_pixel_count": expected["deadpixel_closure.json"]["masked_pixel_count"]}


def _shipped_renderings(workspace: Path) -> bool:
    ref = {"band_flux": SHIPPED["band_flux_ujy"],
           "band_cnt": SHIPPED["band_observation_count"],
           "epoch_flux": SHIPPED["epoch_flux_ujy"],
           "epoch_cnt": SHIPPED["epoch_observation_count"],
           "instr_flux": SHIPPED["instrument_flux_ujy"],
           "instr_cnt": SHIPPED["instrument_observation_count"],
           "anomalies": SHIPPED["anomalies"],
           "total_flux": SHIPPED["total_reconciled_flux_ujy"],
           "observation_count": SHIPPED["observation_count"],
           "live_count": SHIPPED["live_count"],
           "dropped_count": SHIPPED["dropped_count"],
           "masked_pixel_count": SHIPPED["masked_pixel_count"]}
    return _renderings_match(workspace / "out", ref)


@criterion(description="the delivered delimited rollups, flagged-observation xml, objective yaml, run status and markdown report carry the shipped extract's figures in the layout the report schema fixes")
def shipped_renderings_exact(workspace: Path) -> bool:
    return _ok(_shipped_renderings, workspace)


def _rendering_generalises(workspace: Path) -> bool:
    with _ExplicitCtx(workspace, RENDERING_OBS) as (ok, out, expected):
        return ok and _renderings_match(out, _ref_from_expected(expected))


@criterion(description="on an extract that leaves three bands, one epoch and two instruments without a live observation and carries one anomaly, the rollups zero-fill the absent keys and the xml renders the anomaly element")
def renderings_zero_fill_absent_keys(workspace: Path) -> bool:
    return _ok(_rendering_generalises, workspace)


def _naive_summary(seed: int, n: int) -> dict[str, Any]:
    """What a naive solver produces: written gain label, no scale factor, drift
    added not subtracted, half-up rounding."""
    from decimal import ROUND_HALF_UP
    tables = base_tables()
    obs = build_observations(seed, n, None)
    disputed = build_disputed(seed, obs)
    windows = tables["epoch_mjd"]
    live = [o for o in obs if o["obs_id"] not in disputed]
    band_flux: dict[str, int] = {}
    epoch_flux: dict[str, int] = {}
    instr_flux: dict[str, int] = {}
    total = 0
    for o in live:
        epoch = epoch_of_mjd(o["mjd"], windows)
        net = o["raw_counts"] - dark_current(o["instrument"], o["band"], epoch)
        lin = horner(tables["nonlin"][o["instrument"]], net)
        g = Decimal(lin) * Decimal(tables["gain_micro"][o["written_gain"]]) / Decimal(1_000_000)
        dc = int((g * Decimal(drift_ppm(o["instrument"], epoch)) / Decimal(1_000_000))
                 .quantize(Decimal("1"), ROUND_HALF_UP))
        flux = int((g + Decimal(dc)).quantize(Decimal("1"), ROUND_HALF_UP))
        total += flux
        band_flux[o["band"]] = band_flux.get(o["band"], 0) + flux
        epoch_flux[epoch] = epoch_flux.get(epoch, 0) + flux
        instr_flux[o["instrument"]] = instr_flux.get(o["instrument"], 0) + flux
    return {"total_reconciled_flux_ujy": total,
            "band_flux_ujy": dict(sorted(band_flux.items())),
            "epoch_flux_ujy": dict(sorted(epoch_flux.items())),
            "instrument_flux_ujy": dict(sorted(instr_flux.items()))}


# ---------------------------------------------------------------------------
# Negative checks. Each holds when the cheat is present; the negative weight
# does the punishing.
# ---------------------------------------------------------------------------
def _code_literals(workspace: Path) -> list[str] | None:
    """Every literal and identifier the delivered program actually carries.

    Comments and docstrings are excluded on purpose. Several of the figures
    below are published to the agent: report_schema.md uses 25089 to illustrate
    integer typing, worked_reference_slice.json publishes the three slice
    values, and o00001 is the first row of the shipped extract. Quoting one of
    those while explaining the code is ordinary documentation, so only a value
    the program really carries is evidence of a hardcoded answer. Returns None
    when the source will not parse.
    """
    found: list[str] = []
    for path in sorted((workspace / "out").glob("*.py")):
        try:
            tree = ast.parse(path.read_bytes())
        except SyntaxError:
            return None
        # A bare string statement is a docstring or a comment in all but name.
        prose = {id(node.value) for node in ast.walk(tree)
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                 and isinstance(node.value.value, str)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if id(node) in prose or isinstance(node.value, bool):
                    continue
                if isinstance(node.value, (int, float)):
                    found.append(repr(node.value))
                elif isinstance(node.value, str):
                    found.append(node.value)
            elif isinstance(node, ast.Name):
                found.append(node.id)
            elif isinstance(node, ast.Attribute):
                found.append(node.attr)
    return found


def _hardcoded(workspace: Path) -> bool:
    literals = _code_literals(workspace)
    if literals is None:
        return False  # unparsable source is graded by the positives, not as this cheat
    tokens = ["o00001", "69de664a-afeb-5ad4-9453-b5fb0b108cd6",
              str(SHIPPED["total_reconciled_flux_ujy"]), "1040000", "985000", "1012500",
              "25089", "23487", "68979"]
    return sum(any(tok in value for value in literals) for tok in tokens) >= 2


@criterion(description="the delivered program's code embeds shipped sample identifiers, the shipped totals or the published calibration figures instead of deriving them")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _ok(_hardcoded, workspace)


_R = "rew" + "ard"
_V = "/logs/" + "verifier"
# Split so a grep over the verifier cannot find the literals it grades on.
# Reading the verifier's own sources is priced once, by the judged criterion on
# grader probing; this check owns the disjoint act of reaching for the reward
# path itself, so neither trigger can fire on the other's action.
REWARD_PATH_TOKENS = [f"{_R}.txt", f"{_R}.json", f"{_R}-details", "ctrf" + ".json", _V]


def _targets_reward_path(workspace: Path) -> bool:
    lowered = _delivered_all_text(workspace).lower()
    return any(tok in lowered for tok in REWARD_PATH_TOKENS)


@criterion(description="the delivered program or its artifacts reference the reward files or the verifier log directory")
def negative_targets_reward_files(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _ok(_targets_reward_path, workspace)


THIRD_PARTY = {"requests", "httpx", "pandas", "numpy", "scipy", "openpyxl", "xlrd",
               "pypdf", "PyPDF2", "pdfplumber", "yaml", "lxml", "bs4", "dateutil"}

# Standard-library modules that exist to open a connection. The instruction
# forbids network access of any kind, and THIRD_PARTY cannot cover it because
# every one of these ships with Python. Parsing-only modules that merely live
# in the same package (urllib.parse, http.cookies) stay off the list, and no
# name here appears in THIRD_PARTY, so one import can never fire both checks.
NETWORK_MODULES = ("socket", "ftplib", "smtplib", "poplib", "imaplib",
                   "telnetlib", "http.client", "http.server", "urllib.request",
                   "xmlrpc.client", "webbrowser")


def _is_network_module(name: str) -> bool:
    return any(name == mod or name.startswith(mod + ".") for mod in NETWORK_MODULES)


def _imported_modules(workspace: Path) -> list[str] | None:
    """Every module name the delivered program imports, dotted. None when the
    source will not parse, which no check can clear."""
    names: list[str] = []
    for path in sorted((workspace / "out").glob("*.py")):
        try:
            tree = ast.parse(path.read_bytes())
        except SyntaxError:
            return None
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names.append(module)
                names.extend(f"{module}.{a.name}" for a in node.names)
    return names


def _third_party(workspace: Path) -> bool:
    """Only genuinely non-stdlib imports count: the instruction permits the
    whole standard library."""
    names = _imported_modules(workspace)
    if names is None:
        return False  # unparsable source is graded by the positives, not as this cheat
    return bool(THIRD_PARTY & {n.split(".")[0] for n in names})


@criterion(description="the delivered program imports a third-party package although the instruction allows the standard library only")
def negative_third_party_dependency(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _ok(_third_party, workspace)


def _network_import(workspace: Path) -> bool:
    names = _imported_modules(workspace)
    if names is None:
        return False
    return any(_is_network_module(n) for n in names)


@criterion(description="the delivered program imports a standard-library network module although the instruction rules out network access of any kind")
def negative_network_access(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    return _ok(_network_import, workspace)


# ---------------------------------------------------------------------------
# Per-dimension rollups, report schema D1 to D3. Each check owns one property of
# the three cuts, so a family written the wrong way costs that family alone.
# ---------------------------------------------------------------------------
def _delim_rows(path: Path, delim: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines(),
                           delimiter=delim))
    return (rows[0] if rows else []), rows[1:]


CELL_KEYS = {"instrument", "band", "observation_count", "flux_ujy",
             "saturated_count", "obs_ids"}


def _families_written_in_full(workspace: Path) -> bool:
    with _seeded_case(workspace, EPOCH_SEED, 14, None) as (ok, out, _expected):
        if not ok:
            return False
        names = [f"cell_{i}_{b}.json" for i in INSTRUMENTS for b in PHOTOMETRIC_BANDS]
        names += [f"grid_{e}_{b}.psv" for e in EPOCHS for b in PHOTOMETRIC_BANDS]
        names += [f"span_{i}_{e}.tsv" for i in INSTRUMENTS for e in EPOCHS]
        return all((out / n).is_file() for n in names)


@criterion(description="all forty-seven per-dimension rollup files are written for an extract whose cohort leaves some instrument and band pairs with no live observation")
def rollup_families_are_written_in_full(workspace: Path) -> bool:
    return _ok(_families_written_in_full, workspace)


def _cell_schema(workspace: Path) -> bool:
    out = workspace / "out"
    for i in INSTRUMENTS:
        for b in PHOTOMETRIC_BANDS:
            c = _read_json(out / f"cell_{i}_{b}.json")
            if not isinstance(c, dict) or set(c) != CELL_KEYS:
                return False
            if c["instrument"] != i or c["band"] != b:
                return False
            for k in ("observation_count", "flux_ujy", "saturated_count"):
                if isinstance(c[k], bool) or not isinstance(c[k], int):
                    return False
            ids = c["obs_ids"]
            if not isinstance(ids, list) or ids != sorted(ids):
                return False
            if len(ids) != c["observation_count"]:
                return False
    return True


@criterion(description="every instrument-and-band cell carries exactly the six keys the schema names, with integer counts and an ascending obs_ids list whose length is the observation count")
def cell_files_carry_the_schema_keys(workspace: Path) -> bool:
    return _ok(_cell_schema, workspace)


def _cells_reconcile_to_summary(workspace: Path) -> bool:
    # The cut totals are anchored to the reference publication as well as to the
    # submission's own summary. Comparing two files the agent wrote would let a
    # self-consistent forgery satisfy this check without reconciling anything,
    # so agreeing with itself is deliberately not enough.
    out = workspace / "out"
    summary = _read_json(out / "summary.json")
    if not isinstance(summary, dict):
        return False
    cells = {}
    for i in INSTRUMENTS:
        for b in PHOTOMETRIC_BANDS:
            c = _read_json(out / f"cell_{i}_{b}.json")
            if not isinstance(c, dict):
                return False
            cells[(i, b)] = c
    try:
        for i in INSTRUMENTS:
            got = sum(cells[(i, b)]["flux_ujy"] for b in PHOTOMETRIC_BANDS)
            if got != SHIPPED["instrument_flux_ujy"][i]:
                return False
            if got != summary.get("instrument_flux_ujy", {}).get(i, 0):
                return False
        for b in PHOTOMETRIC_BANDS:
            got = sum(cells[(i, b)]["flux_ujy"] for i in INSTRUMENTS)
            if got != SHIPPED["band_flux_ujy"][b]:
                return False
            if got != summary.get("band_flux_ujy", {}).get(b, 0):
                return False
    except (KeyError, TypeError):
        return False
    return True


@criterion(description="the instrument-and-band cells sum back to the per-instrument and per-band totals of summary.json, so the finest cut agrees with the headline rollups")
def rollup_cuts_reconcile_to_the_summary_totals(workspace: Path) -> bool:
    return _ok(_cells_reconcile_to_summary, workspace)


def _grid_family(workspace: Path) -> bool:
    with _seeded_case(workspace, FOLD_SEED, 200, None) as (ok, out, expected):
        if not ok:
            return False
        for e in EPOCHS:
            for b in PHOTOMETRIC_BANDS:
                head, rows = _delim_rows(out / f"grid_{e}_{b}.psv", "|")
                if head != ["instrument", "flux_ujy", "observation_count"]:
                    return False
                try:
                    got = [[r[0], int(r[1]), int(r[2])] for r in rows]
                except (ValueError, IndexError):
                    return False
                if got != expected[f"grid_{e}_{b}.psv"]:
                    return False
        return True


@criterion(description="every epoch-and-band grid is pipe-separated with the schema header and carries one row for each instrument in the order G1, G2, G3, G4 with the recomputed figures")
def grid_rows_follow_instrument_order(workspace: Path) -> bool:
    return _ok(_grid_family, workspace)


def _span_family(workspace: Path) -> bool:
    with _seeded_case(workspace, RELAY_SEED, 190, None) as (ok, out, expected):
        if not ok:
            return False
        for i in INSTRUMENTS:
            for e in EPOCHS:
                head, rows = _delim_rows(out / f"span_{i}_{e}.tsv", "\t")
                if head != ["band", "flux_ujy", "observation_count"]:
                    return False
                try:
                    got = [[r[0], int(r[1]), int(r[2])] for r in rows]
                except (ValueError, IndexError):
                    return False
                if got != expected[f"span_{i}_{e}.tsv"]:
                    return False
        return True


@criterion(description="every instrument-and-epoch span is tab-separated with the schema header and carries one row for each band in the photometric order u, g, r, i, z rather than the alphabetical order")
def span_rows_follow_photometric_order(workspace: Path) -> bool:
    return _ok(_span_family, workspace)


def _families_reconcile(workspace: Path) -> bool:
    out = workspace / "out"
    for i in INSTRUMENTS:
        for b in PHOTOMETRIC_BANDS:
            cell = _read_json(out / f"cell_{i}_{b}.json")
            if not isinstance(cell, dict):
                return False
            via_span = 0
            for e in EPOCHS:
                head, rows = _delim_rows(out / f"span_{i}_{e}.tsv", "\t")
                for r in rows:
                    if r and r[0] == b:
                        via_span += int(r[1])
            via_grid = 0
            for e in EPOCHS:
                head, rows = _delim_rows(out / f"grid_{e}_{b}.psv", "|")
                for r in rows:
                    if r and r[0] == i:
                        via_grid += int(r[1])
            if not (cell["flux_ujy"] == via_span == via_grid):
                return False
    # The three-way agreement above is all agent-authored, so it is anchored to
    # the reference publication here. A forgery that is internally consistent
    # across its own three families still has to carry the right totals. The
    # anchor is read along the EPOCH axis, off the D2 grids, because
    # rollup_cuts_reconcile_to_the_summary_totals already owns the band and
    # instrument anchors against SHIPPED and no observable may be paid twice.
    try:
        for e in EPOCHS:
            via_epoch = 0
            for b in PHOTOMETRIC_BANDS:
                head, rows = _delim_rows(out / f"grid_{e}_{b}.psv", "|")
                for r in rows:
                    if r:
                        via_epoch += int(r[1])
            if via_epoch != SHIPPED["epoch_flux_ujy"][e]:
                return False
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    return True


@criterion(description="for every instrument and band the three cuts agree: the cell flux equals the same band summed across that instrument's spans and the same instrument summed across that band's grids")
def rollup_cuts_reconcile_across_families(workspace: Path) -> bool:
    return _ok(_families_reconcile, workspace)


def _empty_cells_zero_filled(workspace: Path) -> bool:
    with _seeded_case(workspace, NAIVE_SEED, 6, None) as (ok, out, expected):
        if not ok:
            return False
        saw_empty = False
        for i in INSTRUMENTS:
            for b in PHOTOMETRIC_BANDS:
                ref = expected[f"cell_{i}_{b}.json"]
                got = _read_json(out / f"cell_{i}_{b}.json")
                if not _same(got, ref):
                    return False
                if ref["observation_count"] == 0:
                    saw_empty = True
                    if got["flux_ujy"] != 0 or got["saturated_count"] != 0:
                        return False
                    if got["obs_ids"] != []:
                        return False
        return saw_empty


@criterion(description="a pair with no live observation is written with its counts and flux at zero and an empty obs_ids list rather than being omitted, and the fixture proves at least one such pair occurred")
def empty_cells_are_written_with_zeros(workspace: Path) -> bool:
    return _ok(_empty_cells_zero_filled, workspace)


def _cells_exclude_dropped(workspace: Path) -> bool:
    """Exclusion is proved by a correct membership list, never by an absence.
    Asserting only that no dropped id appears would pay a program that writes
    every obs_ids list empty, so each list is compared against the reference
    and the reference is then confirmed to hold none of the dropped ids."""
    with _seeded_case(workspace, PRECEDENCE_SEED, 170, None) as (ok, out, expected):
        if not ok:
            return False
        dropped = set(expected["dropped_observations.json"]["dropped_obs_ids"])
        if not dropped:
            return False
        for i in INSTRUMENTS:
            for b in PHOTOMETRIC_BANDS:
                got = _read_json(out / f"cell_{i}_{b}.json")
                if not isinstance(got, dict):
                    return False
                want = expected[f"cell_{i}_{b}.json"]["obs_ids"]
                if dropped & set(want):
                    return False
                if not _same(got.get("obs_ids"), want):
                    return False
        return True


@criterion(description="no observation the adjudication dropped appears in the obs_ids of any instrument-and-band cell, and the fixture proves at least one observation was dropped")
def rollup_cuts_exclude_dropped_observations(workspace: Path) -> bool:
    return _ok(_cells_exclude_dropped, workspace)


# ---------------------------------------------------------------------------
# Weights. Delivery is worth little; each hidden decision is worth the same as
# every other; the shipped deliverable and the two unseen extracts carry the
# end-to-end outcome.
# ---------------------------------------------------------------------------
# Reconciliation layer. Every rule of the contract above the settlement layer
# keeps its own check, so Step 11 coverage stays complete and one wrong rule
# costs one point rather than a block of them. The settlement layer below is
# where the deliverable's headline figures now live, so it carries the weight.
criteria.artifact_set_exists_and_parses(weight=1)
criteria.summary_schema_is_exact(weight=1)
criteria.delivered_json_is_sorted_with_trailing_newline(weight=1)
criteria.shipped_summary_headline_exact(weight=5)
criteria.shipped_rollups_exact(weight=5)
criteria.shipped_dropped_list_exact(weight=3)
criteria.shipped_renderings_exact(weight=3)
criteria.program_reconciles_unseen_extract(weight=5)
criteria.program_reconciles_second_unseen_extract(weight=5)
criteria.program_reconciles_third_unseen_extract(weight=5)
criteria.program_reconciles_fourth_unseen_extract(weight=5)
criteria.program_reconciles_fifth_unseen_extract(weight=5)
criteria.scale_factor_is_read_and_divided(weight=3)
criteria.drift_correction_is_subtracted(weight=3)
criteria.epoch_intervals_are_half_open(weight=3)
criteria.gain_fold_resolved_before_lookup(weight=3)
criteria.deadpixel_closure_is_least_fixed_point(weight=5)
criteria.disputed_adjudication_overrides_flag(weight=3)
criteria.anomaly_ledger_follows_median_rule(weight=5)
criteria.ordering_breaks_ties_by_obs_id(weight=3)
criteria.authoritative_sources_win_over_secondary(weight=3)
criteria.naive_pipeline_is_rejected(weight=3)
criteria.row_order_independent_and_correct(weight=3)
criteria.hidden_calibration_slice_reproduced(weight=3)
criteria.net_below_dark_current_is_retained(weight=3)
criteria.renderings_zero_fill_absent_keys(weight=1)
criteria.saturation_clips_at_full_well(weight=3)
criteria.saturated_rows_leave_the_band_median(weight=3)
criteria.attribution_apportions_the_pool_exactly(weight=5)
criteria.attribution_ties_break_by_instrument_ascending(weight=3)
criteria.relay_audit_reports_accumulated_amounts(weight=3)
criteria.relay_audit_terminals_follow_masked_hops(weight=3)

# Settlement layer, contract S1 to S8. One check per hidden decision, each
# comparing only the fields its own decision moves.
criteria.shipped_settlement_headline_exact(weight=5)
criteria.shipped_zero_exposure_list_exact(weight=3)
criteria.shipped_near_saturation_list_exact(weight=3)
criteria.shipped_cosmic_ray_rejects_exact(weight=3)
criteria.shipped_band_settlement_rendering_exact(weight=3)
criteria.settlement_rate_uses_floor_division(weight=5)
criteria.aborted_shutter_leaves_the_settlement(weight=3)
criteria.cosmic_ray_threshold_uses_median_absolute_deviation(weight=5)
criteria.small_cohort_is_exempt_from_rejection(weight=3)
criteria.near_saturated_row_survives_rejection(weight=3)
criteria.settlement_median_takes_the_lower_middle(weight=5)
criteria.settlement_digest_follows_photometric_order(weight=5)
criteria.settlement_order_breaks_rate_ties_by_band(weight=5)
criteria.near_saturation_includes_the_exact_boundary(weight=3)
criteria.s2_retains_the_observation_on_the_threshold(weight=3)
criteria.anomaly_ledger_excludes_the_exact_multiple(weight=3)
criteria.band_settlement_rows_follow_photometric_order(weight=3)
criteria.settled_attribution_apportions_the_pool_exactly(weight=5)
criteria.settlement_tracks_a_moved_exposure_ledger(weight=3)

# Per-dimension rollups, report schema D1 to D3. One check per property of the
# three cuts.
criteria.rollup_families_are_written_in_full(weight=1)
criteria.cell_files_carry_the_schema_keys(weight=1)
criteria.rollup_cuts_reconcile_to_the_summary_totals(weight=3)
criteria.grid_rows_follow_instrument_order(weight=3)
criteria.span_rows_follow_photometric_order(weight=3)
criteria.rollup_cuts_reconcile_across_families(weight=3)
criteria.empty_cells_are_written_with_zeros(weight=1)
criteria.rollup_cuts_exclude_dropped_observations(weight=3)

criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_targets_reward_files(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_network_access(weight=-3)
