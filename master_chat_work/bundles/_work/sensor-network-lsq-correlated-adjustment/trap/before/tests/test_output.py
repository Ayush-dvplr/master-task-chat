"""SNLSQ combined core: exact WLS+IRLS sensor-network adjustment engine,
deterministic corpus generator, reader, reference solver and grader.
Single-file consolidation of the shared modules (stdlib only)."""
from __future__ import annotations
import sys

from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path
from typing import Sequence
import csv
import io
import json
import re
import re as _re
import sqlite3
import struct
import zipfile
import zlib
import threading
from rewardkit import criteria, criterion

# ===== from snlsq_engine.py =====


getcontext().prec = 60

# ---------------------------------------------------------------------------
# Documented exact unit-conversion factors (all EXACT rationals; no pi).
# Angles are carried in gons throughout; the design matrix partials are already
# expressed per-gon, so angles never require an irrational radian conversion.
# ---------------------------------------------------------------------------
# length -> metres (base unit)
LEN_TO_M: dict[str, Fraction] = {
    "m": Fraction(1),
    "metre": Fraction(1),
    "meter": Fraction(1),
    "ft_i": Fraction(3048, 10000),          # international foot = 0.3048 m exact
    "ft_intl": Fraction(3048, 10000),
    "ft_us": Fraction(1200, 3937),          # US survey foot exact
    "ft_ussurvey": Fraction(1200, 3937),
    "chain": Fraction(66, 1) * Fraction(1200, 3937),         # US survey chain = 66 US survey feet
    "link": Fraction(66, 100) * Fraction(1200, 3937),        # US survey link = 0.66 US survey feet
    "mm": Fraction(1, 1000),
}
# angle -> gon (base unit for angular observations)
ANG_TO_GON: dict[str, Fraction] = {
    "gon": Fraction(1),
    "grad": Fraction(1),
    "deg": Fraction(400, 360),              # 1 degree = 400/360 gon exact
    "degree": Fraction(400, 360),
    "arcmin": Fraction(400, 360) / Fraction(60),
    "arcsec": Fraction(400, 360) / Fraction(3600),
    "mgon": Fraction(1, 1000),
}

# default weight quantization (decimal places) and IRLS pass count used by the
# corpus generator; the reference solver reads both from iteration_policy.yaml.
WEIGHT_QUANT_PLACES = 34
# IRLS robust tuning: downweight iff  r_i^2 * p_i > K2  (studentized, squared).
# The multiplier applied to a flagged observation's weight is  K2 / (r_i^2 * p_i)
# (a rational redescending factor; no sqrt). K2 is supplied per-run (XLSX-gated
# tuning constant k, with K2 = k^2). Fixed iteration count IRLS_ITERS.
IRLS_ITERS = 4


def frac(x) -> Fraction:
    """Parse a scalar to an exact Fraction without float rounding."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, Decimal):
        return Fraction(x)
    s = str(x).strip()
    if s == "":
        raise ValueError("empty numeric field")
    return Fraction(Decimal(s))


def quantize_weight(p: Fraction, places: int = WEIGHT_QUANT_PLACES) -> Fraction:
    """Exact half-even rounding of a rational weight to `places` decimals."""
    scale = 10 ** places
    return Fraction(round(Fraction(p) * scale), scale)


def azimuth_reduce_gon(value: Fraction) -> Fraction:
    """Reduce an azimuth in gon into [0, 400) exactly (trap 7 inverse)."""
    full = Fraction(400)
    r = value % full
    if r < 0:
        r += full
    return r


def sigma_to_variance_base(
    raw_value,
    stored_as: str,
    obs_kind: str,
    unit: str,
) -> Fraction:
    """Return the a-priori VARIANCE in base units (m^2 or gon^2).

    THE CORE CORRECTION LIVES HERE: the sigma/variance is converted to base
    units *before* it is turned into a weight. `stored_as` is either 'stddev'
    or 'variance' (documented per file). obs_kind selects length vs angle.
    """
    v = frac(raw_value)
    if obs_kind == "length":
        scale = LEN_TO_M[unit.strip().lower()]
    elif obs_kind == "angle":
        scale = ANG_TO_GON[unit.strip().lower()]
    else:
        raise ValueError(f"bad obs_kind {obs_kind!r}")
    stored_as = stored_as.strip().lower()
    if stored_as == "stddev":
        sigma_base = v * scale
        return sigma_base * sigma_base
    if stored_as == "variance":
        # variance scales by the square of the unit factor
        return v * scale * scale
    raise ValueError(f"bad stored_as {stored_as!r}")


class Observation:
    __slots__ = (
        "obs_id",
        "kind",
        "value_base",
        "variance_base",
        "coeffs",
        "downweighted",
        "epoch",
        "region",
    )

    def __init__(
        self,
        obs_id: str,
        kind: str,
        value_base: Fraction,
        variance_base: Fraction,
        coeffs: dict[int, Fraction],
        epoch: int = 0,
        region: str = "",
    ) -> None:
        self.obs_id = obs_id
        self.kind = kind
        self.value_base = value_base
        self.variance_base = variance_base
        self.coeffs = coeffs
        self.downweighted = False
        self.epoch = epoch
        self.region = region

    def weight(self) -> Fraction:
        return Fraction(1) / self.variance_base


def solve_linear_exact(
    matrix: list[list[Fraction]], rhs: list[Fraction]
) -> list[Fraction]:
    """Exact Gaussian elimination with documented pivoting.

    Pivot = row (at or below current) with the largest absolute value in the
    current column; ties broken by lowest row index. All arithmetic exact.
    """
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = col
        best = abs(a[col][col])
        for r in range(col + 1, n):
            cand = abs(a[r][col])
            if cand > best:
                best = cand
                pivot = r
        if a[pivot][col] == 0:
            raise ZeroDivisionError("singular normal-equation system")
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        piv = a[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col] / piv
            if factor == 0:
                continue
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def residuals(
    obs: Sequence[Observation], x: list[Fraction]
) -> list[Fraction]:
    """v_i = (A x)_i - l_i (predicted minus observed)."""
    out: list[Fraction] = []
    for o in obs:
        pred = Fraction(0)
        for i, ai in o.coeffs.items():
            pred += ai * x[i]
        out.append(pred - o.value_base)
    return out


def _block_weight(va: Fraction, vb: Fraction, cov: Fraction,
                  places: int = WEIGHT_QUANT_PLACES):
    # Exact 2x2 correlated weight block P = C^{-1} for C = [[va, cov],[cov, vb]],
    # each entry quantized to the documented weight grid. No sqrt.
    det = va * vb - cov * cov
    p00 = quantize_weight(vb / det, places)
    p01 = quantize_weight(-cov / det, places)
    p11 = quantize_weight(va / det, places)
    return [[p00, p01], [p01, p11]]


def adjust(
    obs: list[Observation],
    n_unknowns: int,
    k2: Fraction,
    pairs: dict | None = None,
    iters: int = IRLS_ITERS,
    places: int = WEIGHT_QUANT_PLACES,
) -> dict:
    """Reference WLS + IRLS pass (schema sections 10, 11, 11b).

    Uncorrelated observations: diagonal quantized 1/variance base weight; in each
    of `iters` passes an observation with v^2*p > k2 gets weight q(p*k2/(v^2*p)).
    Session members: the quantized 2x2 block C^{-1}, never tested, never flagged.
    Returns x, residuals, flags, vTPv, the reported final weights and the trace
    of the normal matrix of the last solve.
    """
    pairs = pairs or {}
    base_weight = [quantize_weight(o.weight(), places) for o in obs]
    blocks = {}
    for idx, (other, cov) in pairs.items():
        if idx < other:
            blocks[idx] = (other, _block_weight(obs[idx].variance_base,
                                                obs[other].variance_base, cov, places))

    def assemble(weights):
        N = [[Fraction(0)] * n_unknowns for _ in range(n_unknowns)]
        b = [Fraction(0)] * n_unknowns
        for idx, (o, w) in enumerate(zip(obs, weights)):
            if idx in pairs:
                continue
            for i, ai in o.coeffs.items():
                for j, aj in o.coeffs.items():
                    N[i][j] += w * ai * aj
                b[i] += w * ai * o.value_base
        for ia, (ib, pblk) in blocks.items():
            rows = [obs[ia].coeffs, obs[ib].coeffs]
            lvec = [obs[ia].value_base, obs[ib].value_base]
            for r in range(2):
                for c in range(2):
                    pw = pblk[r][c]
                    for i, ai in rows[r].items():
                        for j, aj in rows[c].items():
                            N[i][j] += pw * ai * aj
                        b[i] += pw * ai * lvec[c]
        return N, b

    cur_weight = base_weight[:]
    flags = [False] * len(obs)
    N, b = assemble(cur_weight)
    x = solve_linear_exact([row[:] for row in N], b[:])
    for _ in range(iters):
        v = residuals(obs, x)
        new_weight, new_flags = [], []
        for idx, (bw, vi) in enumerate(zip(base_weight, v)):
            studentized = vi * vi * bw
            if idx not in pairs and studentized > k2:
                new_weight.append(quantize_weight(bw * (k2 / studentized), places))
                new_flags.append(True)
            else:
                new_weight.append(bw)
                new_flags.append(False)
        cur_weight, flags = new_weight, new_flags
        N, b = assemble(cur_weight)
        x = solve_linear_exact([row[:] for row in N], b[:])

    for o, fl in zip(obs, flags):
        o.downweighted = fl
    v_final = residuals(obs, x)
    vtpv = Fraction(0)
    for idx, (vi, w) in enumerate(zip(v_final, cur_weight)):
        if idx not in pairs:
            vtpv += w * vi * vi
    reported = list(cur_weight)
    for ia, (ib, pblk) in blocks.items():
        vr = [v_final[ia], v_final[ib]]
        for r in range(2):
            for c in range(2):
                vtpv += vr[r] * pblk[r][c] * vr[c]
        reported[ia] = pblk[0][0]
        reported[ib] = pblk[1][1]
    return {
        "x": x,
        "weights_final": reported,
        "residuals": v_final,
        "vtpv": vtpv,
        "flags": flags,
        "trace": sum((N[i][i] for i in range(n_unknowns)), Fraction(0)),
    }


def sigma0_squared(vtpv: Fraction, n_obs: int, u: int) -> Fraction:
    dof = n_obs - u
    if dof <= 0:
        raise ValueError("non-positive degrees of freedom")
    return vtpv / Fraction(dof)


def chi_square_gate(
    vtpv: Fraction, dof: int, crit_lo: Fraction, crit_hi: Fraction
) -> str:
    """Two-sided model test on the quadratic form vTPv (which under H0 is
    distributed as sigma_apriori^2 * chi^2_dof; a-priori sigma0^2 = 1 by
    construction). PASS iff crit_lo <= vtpv <= crit_hi (exact rational compare).
    """
    if vtpv < crit_lo:
        return "REJECT_LOW"
    if vtpv > crit_hi:
        return "REJECT_HIGH"
    return "PASS"


def frac_to_str(x: Fraction, places: int = 10) -> str:
    """Exact half-even fixed-point rendering; negative zero has no sign."""
    n = round(Fraction(x) * 10 ** places)
    sign = "-" if n < 0 else ""
    digits = str(abs(n)).rjust(places + 1, "0")
    if places == 0:
        return sign + digits
    return f"{sign}{digits[:-places]}.{digits[-places:]}"


def frac_to_int_micro(x: Fraction) -> int:
    """Exact rational -> signed integer micro-units, half-even."""
    return round(Fraction(x) * 1_000_000)

# ===== from snlsq_corpus.py =====



# ---------------------------------------------------------------------------
# deterministic RNG (xorshift64*), stdlib-free of `random`
# ---------------------------------------------------------------------------
class Rng:
    __slots__ = ("s",)

    def __init__(self, seed: int) -> None:
        self.s = (seed & 0xFFFFFFFFFFFFFFFF) or 0x9E3779B97F4A7C15

    def _n(self) -> int:
        x = self.s
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.s = x & 0xFFFFFFFFFFFFFFFF
        return (self.s * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def randint(self, lo: int, hi: int) -> int:
        return lo + self._n() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self._n() % len(seq)]

    def chance(self, num: int, den: int) -> bool:
        return (self._n() % den) < num


# ---------------------------------------------------------------------------
# Network definition. Unknowns = per-station (dx, dy) corrections in metres.
# We fix the true corrections to small exact rationals so observations are
# derived exactly; the datum constraint (below) determines u.
# ---------------------------------------------------------------------------
STATIONS = ["ALPHA", "BRAVO", "CIVET", "DELTA", "EAGLE", "FICUS"]
# unknown index layout: station i -> dx at 2i, dy at 2i+1
N_STATIONS = len(STATIONS)
N_UNKNOWNS = 2 * N_STATIONS  # 12


def true_correction() -> list[Fraction]:
    # Exact "true" unknown vector in metres (small corrections).
    vals = [
        Fraction(0), Fraction(0),           # ALPHA fixed by datum (dx,dy = 0)
        Fraction(3, 1000), Fraction(-2, 1000),
        Fraction(-5, 1000), Fraction(4, 1000),
        Fraction(2, 1000), Fraction(-3, 1000),
        Fraction(-1, 1000), Fraction(6, 1000),
        Fraction(0), Fraction(-4, 1000),    # FICUS: dy free, dx height-only fixed
    ]
    return vals


# Correlated observation sessions. A subset of length baselines are
# correlated in 2-member sessions, so the weight matrix P is BLOCK-diagonal, not
# diagonal. A naive diagonal-P solver gets every coordinate, the blunder set,
# n, dof, sigma0^2, the verdict and every rollup wrong. The per-session exact
# covariance is cov = rho * min(v_a, v_b) (rational; no sqrt), and the 2x2 weight
# block is C^{-1} with C = [[v_a, cov],[cov, v_b]]. Sessions are keyed by their
# two member obs_ids in the shipped session_correlation file; the solver must
# reconstruct the pairing and assemble the block (with the cross-term in b).
CORRELATED_SESSIONS = 150
RHO_CHOICES = [Fraction(3, 5), Fraction(-2, 3), Fraction(5, 7),
               Fraction(-6, 7), Fraction(4, 7), Fraction(-3, 5)]


class Obs:
    """Authoritative observation before any file-format trap is applied.

    value_base is the RAW OBSERVED value (base units). nominal_base is the value
    computed from the approximate station coordinates. The misclosure fed to the
    normal equations is l = value_base - nominal_base (small, noise-scale).
    """

    __slots__ = ("oid", "kind", "value_base", "nominal_base", "sigma_base",
                 "coeffs", "epoch", "region")

    def __init__(self, oid, kind, value_base, nominal_base, sigma_base, coeffs,
                 epoch, region):
        self.oid = oid
        self.kind = kind
        self.value_base = value_base
        self.nominal_base = nominal_base
        self.sigma_base = sigma_base
        self.coeffs = coeffs
        self.epoch = epoch
        self.region = region

    def misclosure(self) -> Fraction:
        return self.value_base - self.nominal_base


REGIONS = ["North", "South", "West", "East"]

# Nominal (approximate) station coordinates in metres. Observations are formed
# against these EXACT nominal values so every observation of the same quantity
# is mutually consistent. The unknowns are small corrections dx,dy to these.
NOMINAL_COORD = {
    "ALPHA": (Fraction(1000), Fraction(1000)),
    "BRAVO": (Fraction(1420), Fraction(1035)),
    "CIVET": (Fraction(1180), Fraction(1390)),
    "DELTA": (Fraction(880), Fraction(1330)),
    "EAGLE": (Fraction(1310), Fraction(1610)),
    "FICUS": (Fraction(760), Fraction(980)),
}


def _small_noise(rng: Rng, scale_num: int, scale_den: int) -> Fraction:
    """Deterministic small signed rational noise in +/- scale (exact)."""
    span = 2 * scale_num + 1
    step = rng.randint(0, span - 1) - scale_num
    return Fraction(step, scale_den)


def build_authoritative_obs(rng: Rng) -> list[Obs]:
    """Build a well-conditioned authoritative observation set (base units).

    Each unknown component is observed many times through consistent geometry
    plus tiny noise, so the corrected WLS lands near the true corrections and
    the chi-square model test PASSes. A handful of deliberate gross outliers are
    injected so IRLS downweighting has real work to do (and a trap-blind solver
    that skips reweighting fails the residual/verdict tests).
    """
    x = true_correction()
    nom = [c for st in STATIONS for c in NOMINAL_COORD[st]]
    obs: list[Obs] = []
    target = 1040
    outlier_every = 65
    medium_every = 91          # medium outliers (see the misclosure block below)
    medium_scale = Fraction(3)  # studentized v^2*p approx 9: in (k^2=6.25, blunder_crit^2=12.25)
    n = 0
    while len(obs) < target:
        n += 1
        region = REGIONS[(n - 1) % len(REGIONS)]
        epoch = 1 + (n % 3)
        kind = "angle" if rng.chance(1, 5) else "length"
        pick = rng.randint(0, 2)
        if pick == 0:
            i = rng.randint(0, N_STATIONS - 1)
            axis = rng.randint(0, 1)
            comp = 2 * i + axis
            coeffs = {comp: Fraction(1)}
            base_nominal = nom[comp]
        else:
            i = rng.randint(0, N_STATIONS - 1)
            j = (i + rng.randint(1, N_STATIONS - 1)) % N_STATIONS
            axis = rng.randint(0, 1)
            ci, cj = 2 * i + axis, 2 * j + axis
            coeffs = {ci: Fraction(1), cj: Fraction(-1)}
            base_nominal = nom[ci] - nom[cj]
        if kind == "angle":
            angle_scale = Fraction(1, 100)
            coeffs = {k: v * angle_scale for k, v in coeffs.items()}
            ang_nominal = Fraction(rng.randint(0, 39999), 100)
            base_nominal = (base_nominal * angle_scale + ang_nominal) % Fraction(400)
            sigma_base = Fraction(rng.randint(5, 20), 10000)
        else:
            sigma_base = Fraction(rng.randint(5, 20), 1000)
        model = sum(a * x[k] for k, a in coeffs.items())
        noise = sigma_base * Fraction(rng.randint(-17, 17), 10)
        misclosure = model + noise
        if n % outlier_every == 0:
            misclosure += sigma_base * Fraction(rng.randint(12, 40))
        elif n % medium_every == 0:
            # v_i^2*p_i approx 9 lands in (k^2=6.25, blunder_crit^2=12.25): kept by
            # data-snooping, downweighted by stage-2 IRLS. No rng draw here, so the
            # byte-stream stays identical to a normal row.
            misclosure = model + sigma_base * medium_scale
        value_base = base_nominal + misclosure
        if kind == "angle":
            value_base = value_base % Fraction(400)
        obs.append(
            Obs(f"OB{len(obs)+1:05d}", kind, value_base, base_nominal, sigma_base,
                dict(coeffs), epoch, region)
        )
    return obs


# ===== from snlsq_emit.py =====



FIXED_ZIP_DT = (1980, 1, 1, 0, 0, 0)


def d(x: Fraction, places: int) -> str:
    return frac_to_str(x, places)


def trap_block(file_role: str, comment: str = "# ", extra: list[str] | None = None) -> str:
    """Return the one-line role header every shipped table carries."""
    return f"{comment}SNLSQ file role: {file_role}. schema.md is the contract.\n"


def value_in_unit(value_base: Fraction, kind: str, unit: str) -> Fraction:
    if kind == "length":
        return value_base / LEN_TO_M[unit]
    return value_base / ANG_TO_GON[unit]


def sigma_in_unit(sigma_base: Fraction, kind: str, unit: str, stored_as: str) -> Fraction:
    if kind == "length":
        s = sigma_base / LEN_TO_M[unit]
    else:
        s = sigma_base / ANG_TO_GON[unit]
    return s * s if stored_as == "variance" else s


def coeffs_str(coeffs: dict[int, Fraction]) -> str:
    return ";".join(f"{k}:{v.numerator}/{v.denominator}" for k, v in sorted(coeffs.items()))


# ---------------------------------------------------------------------------
# Trap-annotated observation shard record builder.
# ---------------------------------------------------------------------------
def build_shard_records(shard, length_unit, angle_unit, stored_as,
                        *, sign_flip_rev=False, azimuth_wrap=False,
                        transpose_ids=False):
    recs = []
    for k, o in enumerate(shard):
        unit = length_unit if o.kind == "length" else angle_unit
        val = value_in_unit(o.value_base, o.kind, unit)
        nom = value_in_unit(o.nominal_base, o.kind, unit)
        sig = sigma_in_unit(o.sigma_base, o.kind, unit, stored_as)
        direction = "F"
        if sign_flip_rev and len(o.coeffs) == 2 and (k % 2 == 1):
            val = -val
            nom = -nom
            direction = "R"
        if azimuth_wrap and o.kind == "angle":
            if k % 3 == 0:
                shift = value_in_unit(Fraction(400), "angle", unit)
                val = val - shift
                nom = nom - shift
            elif k % 3 == 1:
                shift = value_in_unit(Fraction(400), "angle", unit)
                val = val + shift
                nom = nom + shift
        oid_field = o.oid
        if transpose_ids and o.epoch == 2:
            oid_field = o.oid[3:] + o.oid[:3]
        recs.append({
            "oid": o.oid,
            "oid_field": oid_field,
            "kind": o.kind,
            "value": d(val, 16),
            "nominal": d(nom, 16),
            "sigma": d(sig, 18),
            "unit": unit,
            "sigma_kind": stored_as,
            "direction": direction,
            "coeffs": coeffs_str(o.coeffs),
            "epoch": str(o.epoch),
            "region": o.region,
        })
    return recs


# ===========================================================================
# Format writers.  Each returns (bytes, trap_list).
# ===========================================================================
def write_csv(recs, header_note, delimiter=","):
    buf = io.StringIO()
    buf.write(header_note)
    w = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
    w.writerow(["obs_id", "kind", "observed_value", "computed_nominal",
                "apriori_sigma", "unit", "sigma_kind", "dir", "partials",
                "epoch", "region"])
    for r in recs:
        w.writerow([r["oid_field"], r["kind"], r["value"], r["nominal"],
                    r["sigma"], r["unit"], r["sigma_kind"], r["direction"],
                    r["coeffs"], r["epoch"], r["region"]])
    return buf.getvalue().encode("utf-8")


def write_jsonl(recs, meta):
    meta = dict(meta)
    lines = [json.dumps(meta, sort_keys=True)]
    for r in recs:
        lines.append(json.dumps({
            "id": r["oid_field"], "k": r["kind"], "v": r["value"],
            "c": r["nominal"], "s": r["sigma"], "u": r["unit"],
            "sk": r["sigma_kind"], "d": r["direction"], "A": r["coeffs"],
            "e": r["epoch"], "reg": r["region"],
        }, sort_keys=True))
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_json(recs, meta):
    obj = {"meta": meta, "observations": [{
        "id": r["oid_field"], "kind": r["kind"], "value": r["value"],
        "sigma": r["sigma"], "unit": r["unit"], "sigma_kind": r["sigma_kind"],
        "direction": r["direction"], "partials": r["coeffs"],
        "epoch": r["epoch"], "region": r["region"]} for r in recs]}
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_xml(recs, meta):
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<shard>"]
    parts.append("  <meta>")
    for k, v in sorted(meta.items()):
        parts.append(f"    <{k}>{v}</{k}>")
    parts.append("  </meta>")
    parts.append("  <observations>")
    for r in recs:
        parts.append(
            f'    <obs id="{r["oid_field"]}" kind="{r["kind"]}" unit="{r["unit"]}" '
            f'sigma_kind="{r["sigma_kind"]}" dir="{r["direction"]}" epoch="{r["epoch"]}" '
            f'region="{r["region"]}">'
        )
        parts.append(f"      <value>{r['value']}</value>")
        parts.append(f"      <sigma>{r['sigma']}</sigma>")
        parts.append(f"      <partials>{r['coeffs']}</partials>")
        parts.append("    </obs>")
    parts.append("  </observations>")
    parts.append("</shard>")
    return ("\n".join(parts) + "\n").encode("utf-8")


def write_yaml(recs, meta):
    parts = ["meta:"]
    for k, v in sorted(meta.items()):
        parts.append(f"  {k}: {json.dumps(v)}")
    parts.append("observations:")
    for r in recs:
        parts.append(f"  - id: {r['oid_field']}")
        parts.append(f"    kind: {r['kind']}")
        parts.append(f"    value: '{r['value']}'")
        parts.append(f"    sigma: '{r['sigma']}'")
        parts.append(f"    unit: {r['unit']}")
        parts.append(f"    sigma_kind: {r['sigma_kind']}")
        parts.append(f"    direction: {r['direction']}")
        parts.append(f"    partials: '{r['coeffs']}'")
        parts.append(f"    epoch: {r['epoch']}")
        parts.append(f"    region: {r['region']}")
    return ("\n".join(parts) + "\n").encode("utf-8")


def write_txt_fixedwidth(recs, header_note):
    lines = [header_note.rstrip("\n")]
    lines.append(f"{'OBS_ID':<10}{'KIND':<8}{'VALUE':>16}{'SIGMA':>16}"
                 f"{'UNIT':>10}{'SKIND':>10}{'DIR':>4}{'EPOCH':>6}{'REGION':>8}  PARTIALS")
    for r in recs:
        lines.append(f"{r['oid_field']:<10}{r['kind']:<8}{r['value']:>16}{r['sigma']:>16}"
                     f"{r['unit']:>10}{r['sigma_kind']:>10}{r['direction']:>4}"
                     f"{r['epoch']:>6}{r['region']:>8}  {r['coeffs']}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_md_table(recs, header_note):
    lines = [header_note.rstrip("\n"), ""]
    lines.append("| obs_id | kind | value | sigma | unit | sigma_kind | dir | epoch | region | partials |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in recs:
        lines.append(f"| {r['oid_field']} | {r['kind']} | {r['value']} | {r['sigma']} | "
                     f"{r['unit']} | {r['sigma_kind']} | {r['direction']} | {r['epoch']} | "
                     f"{r['region']} | `{r['coeffs']}` |")
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_sqlite(path: Path, recs, meta, table="observations"):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    cur.execute("CREATE TABLE meta(key TEXT, value TEXT)")
    for k, v in sorted(meta.items()):
        cur.execute("INSERT INTO meta VALUES(?,?)", (k, str(v)))
    cur.execute(
        f"CREATE TABLE {table}(obs_id TEXT, kind TEXT, value TEXT, sigma TEXT, "
        "unit TEXT, sigma_kind TEXT, direction TEXT, partials TEXT, epoch TEXT, region TEXT)"
    )
    for r in recs:
        cur.execute(
            f"INSERT INTO {table} VALUES(?,?,?,?,?,?,?,?,?,?)",
            (r["oid_field"], r["kind"], r["value"], r["sigma"], r["unit"],
             r["sigma_kind"], r["direction"], r["coeffs"], r["epoch"], r["region"]),
        )
    con.commit()
    con.close()


# ===========================================================================
# Binary office writers (pure stdlib; readable back with zipfile + ElementTree).
# ===========================================================================
def _col_ref(idx: int) -> str:
    s = ""
    n = idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _zip_bytes(members: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members:
            zi = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DT)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, payload)
    return buf.getvalue()


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def write_xlsx(recs, meta_rows, header_rows):
    """Write a structurally valid XLSX (inline-string cells only).

    `header_rows` is a list of list-of-strings written before the observation
    table (used to carry the load-bearing datum/tuning metadata). `meta_rows` is
    a second sheet. All cells are inline strings so a stdlib reader needs only
    zipfile + ElementTree.
    """
    def sheet_xml(rows):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
               "<sheetData>"]
        for ri, row in enumerate(rows, start=1):
            out.append(f'<row r="{ri}">')
            for ci, val in enumerate(row):
                ref = f"{_col_ref(ci)}{ri}"
                out.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
                           f'{_xml_escape(str(val))}</t></is></c>')
            out.append("</row>")
        out.append("</sheetData></worksheet>")
        return "".join(out).encode("utf-8")

    obs_rows = [["obs_id", "kind", "value", "sigma", "unit", "sigma_kind",
                 "direction", "partials", "epoch", "region"]]
    for r in recs:
        obs_rows.append([r["oid_field"], r["kind"], r["value"], r["sigma"],
                         r["unit"], r["sigma_kind"], r["direction"], r["coeffs"],
                         r["epoch"], r["region"]])
    sheet1 = sheet_xml(header_rows + [[]] + obs_rows)
    sheet2 = sheet_xml(meta_rows)

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    ).encode("utf-8")
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        '<sheet name="network" sheetId="1" r:id="rId1"/>'
        '<sheet name="datum" sheetId="2" r:id="rId2"/>'
        "</sheets></workbook>"
    ).encode("utf-8")
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    return _zip_bytes([
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", workbook),
        ("xl/_rels/workbook.xml.rels", wb_rels),
        ("xl/worksheets/sheet1.xml", sheet1),
        ("xl/worksheets/sheet2.xml", sheet2),
    ])


def write_docx(paragraphs):
    """Write a minimal valid DOCX carrying documented text paragraphs."""
    def p_xml(text):
        return ('<w:p><w:r><w:t xml:space="preserve">'
                f'{_xml_escape(text)}</w:t></w:r></w:p>')
    body = "".join(p_xml(t) for t in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}<w:sectPr/></w:body></w:document>'
    ).encode("utf-8")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    ).encode("utf-8")
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    ).encode("utf-8")
    return _zip_bytes([
        ("[Content_Types].xml", content_types),
        ("_rels/.rels", root_rels),
        ("word/document.xml", document),
    ])


def write_pdf(lines):
    """Write a minimal valid multi-page PDF whose text is extractable by a
    documented rule: each data row is a single `(...) Tj` text-show operator in
    a content stream, one per line. A stdlib reader inflates the FlateDecode
    stream and reads the parenthesized strings in order.
    """
    def esc(s):
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    per_page = 45
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objects = []
    # 1: catalog, 2: pages tree; then per page: page obj + content obj
    n_pages = len(pages)
    kids_ids = [3 + 2 * i for i in range(n_pages)]
    objects.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    kids = " ".join(f"{k} 0 R" for k in kids_ids)
    objects.append((2, f"<< /Type /Pages /Count {n_pages} /Kids [{kids}] "
                       f"/MediaBox [0 0 612 792] >>".encode("ascii")))
    font_id = 3 + 2 * n_pages
    for pi, page_lines in enumerate(pages):
        page_id = kids_ids[pi]
        content_id = page_id + 1
        stream_lines = ["BT", "/F1 9 Tf", "40 760 Td", "11 TL"]
        for ln in page_lines:
            stream_lines.append(f"({esc(ln)}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        raw = ("\n".join(stream_lines)).encode("latin-1", "replace")
        comp = zlib.compress(raw, 9)
        content_obj = (b"<< /Length " + str(len(comp)).encode() +
                       b" /Filter /FlateDecode >>\nstream\n" + comp + b"\nendstream")
        page_obj = (f"<< /Type /Page /Parent 2 0 R /Resources << /Font << "
                    f"/F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>").encode("ascii")
        objects.append((page_id, page_obj))
        objects.append((content_id, content_obj))
    objects.append((font_id, b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"))

    objects.sort(key=lambda o: o[0])
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num, body in objects:
        offsets[num] = out.tell()
        out.write(f"{num} 0 obj\n".encode("ascii"))
        out.write(body)
        out.write(b"\nendobj\n")
    xref_pos = out.tell()
    max_id = max(offsets)
    out.write(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for i in range(1, max_id + 1):
        out.write(f"{offsets.get(i, 0):010d} 00000 n \n".encode("ascii"))
    out.write(f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n"
              f"{xref_pos}\n%%EOF\n".encode("ascii"))
    return out.getvalue()


# ===========================================================================
# Corpus layout driver.  Emits the full 50-60 file corpus into `data_dir`.
# Every shipped file's role, unit convention, sigma convention, sign/azimuth
# convention and any decoy columns are DOCUMENTED in schema.md and in each
# file's own header block, so the reference reader inverts every trap exactly.
# ===========================================================================

# Four SOURCE-OF-RECORD observation shards, 260 authoritative observations each
# (>=200 rows). Each shard presents its slice under a DIFFERENT unit + sigma +
# sign + azimuth convention, all documented. The solver must normalise each
# shard back to base units (m, gon) and correct sigma BEFORE forming weights.
# (filename, fmt, length_unit, angle_unit, sigma_kind, sign_flip_rev,
#  azimuth_wrap, transpose_ids)
SOURCE_SHARD_PLAN = [
    ("obs_source_district_north.csv",  "csv",    "m",     "gon",    "stddev",   False, False, False),
    ("obs_source_district_south.tsv",  "tsv",    "ft_i",  "deg",    "stddev",   False, False, True),
    ("obs_source_district_west.psv",   "psv",    "ft_us", "gon",    "variance", True,  True,  False),
    ("obs_source_district_east.jsonl", "jsonl",  "chain", "arcsec", "variance", True,  True,  True),
]

SAMPLE_SEED = 730025190474123
CHALLENGE_SEED = 555512349901
EVAL_SEED = 288844451170022

# Per-extract configuration. The shipped extract uses DEFAULT_CFG; the held-out
# extracts change every value the contract tells the solver to READ (workbook
# control values, datum components, shard conventions, iteration policy, the
# acceptance-table centre, the frame/campaign maps), so a program that memorised
# this extract fails them.
_COMPONENTS_3 = [("ALPHA", "x", 0), ("ALPHA", "y", 1), ("FICUS", "x", 10)]
DEFAULT_CFG = {
    "components": _COMPONENTS_3,
    "k": Fraction(5, 2), "crit": Fraction(7, 2), "origin": 2,
    "irls_iters": IRLS_ITERS, "quant_places": WEIGHT_QUANT_PLACES,
    "chi_center": Fraction(1077253, 1000000),
    "shard_plan": SOURCE_SHARD_PLAN,
    "mounts": {"ALPHA": ("pillar", "0.5"), "BRAVO": ("tripod", "3.0"),
               "CIVET": ("pillar", "0.8"), "DELTA": ("tripod", "2.5"),
               "EAGLE": ("pillar", "0.6"), "FICUS": ("tripod", "4.0")},
    "revisions": (3, 5, 2, 4),
    "dup_count": 6,
    "straddle_count": 2,
}
AUDIT_SEED = 914477302281
CORPUS_VARIANTS = {
    CHALLENGE_SEED: {
        "components": _COMPONENTS_3 + [("FICUS", "y", 11)],
        "k": Fraction(11, 5), "crit": Fraction(16, 5), "origin": 4,
        "irls_iters": 3, "quant_places": 30, "chi_center": Fraction(1),
        "mounts": {"ALPHA": ("tripod", "2.0"), "BRAVO": ("pillar", "0.7"),
                   "CIVET": ("tripod", "3.5"), "DELTA": ("pillar", "0.5"),
                   "EAGLE": ("tripod", "1.5"), "FICUS": ("pillar", "0.9")},
        "revisions": (6, 2, 7, 1), "dup_count": 8, "straddle_count": 3,
        # Trigger fixture: the ft_us decoy registry row comes after every
        # authoritative ft_us row, so a status-blind last-row-wins reader fails.
        "registry_ft_us_decoy_last": True,
        "station_frame": {"ALPHA": "FrameB", "BRAVO": "FrameA", "CIVET": "FrameC",
                          "DELTA": "FrameB", "EAGLE": "FrameC", "FICUS": "FrameA"},
        "shard_plan": [
            ("obs_source_district_north.csv",  "csv",   "ft_us", "mgon",   "variance", True,  True,  True),
            ("obs_source_district_south.tsv",  "tsv",   "m",     "gon",    "stddev",   False, False, False),
            ("obs_source_district_west.psv",   "psv",   "chain", "deg",    "stddev",   True,  False, True),
            ("obs_source_district_east.jsonl", "jsonl", "ft_i",  "arcsec", "variance", False, True,  False),
        ],
    },
    EVAL_SEED: {
        "components": _COMPONENTS_3,
        "k": Fraction(12, 5), "crit": Fraction(4), "origin": 0,
        "irls_iters": 5, "quant_places": 34, "chi_center": Fraction(1077253, 1000000),
        "mounts": {"ALPHA": ("pillar", "0.4"), "BRAVO": ("tripod", "2.5"),
                   "CIVET": ("tripod", "3.0"), "DELTA": ("pillar", "1.0"),
                   "EAGLE": ("tripod", "4.5"), "FICUS": ("pillar", "0.6")},
        "revisions": (1, 4, 3, 2), "dup_count": 7, "straddle_count": 2,
        # Trigger fixtures: a session whose partner is a gross blunder leaves a
        # survivor that must then be downweighted (schema 11b), and the YAML
        # sigma mirror disagrees with the authoritative JSON manifest (schema 4).
        "survivor_probe": True, "yaml_mirror_flip": True,
        # Trigger fixtures: decoy session rows name real uncorrelated length
        # observations (schema 11b), and two observations carry an exact
        # max-|v| residual tie (schema 16 residual_summary).
        "decoy_session_probe": True, "tie_probe": True,
        "station_frame": {"ALPHA": "FrameA", "BRAVO": "FrameB", "CIVET": "FrameB",
                          "DELTA": "FrameC", "EAGLE": "FrameA", "FICUS": "FrameC"},
        "epoch_campaign": {1: "Campaign1", 2: "Campaign2", 3: "Campaign2"},
        "shard_plan": [
            ("obs_source_district_north.csv",  "csv",   "mm",    "deg",    "variance", True,  True,  False),
            ("obs_source_district_south.tsv",  "tsv",   "ft_us", "gon",    "stddev",   True,  False, True),
            ("obs_source_district_west.psv",   "psv",   "m",     "mgon",   "stddev",   False, True,  True),
            ("obs_source_district_east.jsonl", "jsonl", "chain", "gon",    "variance", True,  False, False),
        ],
    },
    AUDIT_SEED: {
        "components": _COMPONENTS_3,
        "k": Fraction(13, 5), "crit": Fraction(18, 5), "origin": 5,
        "irls_iters": 4, "quant_places": 32, "chi_center": Fraction(21, 20),
        "mounts": {"ALPHA": ("tripod", "1.0"), "BRAVO": ("tripod", "2.0"),
                   "CIVET": ("pillar", "0.5"), "DELTA": ("tripod", "3.5"),
                   "EAGLE": ("pillar", "0.9"), "FICUS": ("pillar", "0.7")},
        "revisions": (2, 3, 9, 8), "dup_count": 9, "straddle_count": 1,
        "station_frame": {"ALPHA": "FrameC", "BRAVO": "FrameB", "CIVET": "FrameA",
                          "DELTA": "FrameA", "EAGLE": "FrameB", "FICUS": "FrameC"},
        "epoch_campaign": {1: "Campaign2", 2: "Campaign1", 3: "Campaign1"},
        "shard_plan": [
            ("obs_source_district_north.csv",  "csv",   "link",  "gon",    "stddev",   False, True,  True),
            ("obs_source_district_south.tsv",  "tsv",   "chain", "arcmin", "variance", True,  True,  False),
            ("obs_source_district_west.psv",   "psv",   "ft_i",  "gon",    "variance", True,  False, True),
            ("obs_source_district_east.jsonl", "jsonl", "m",     "deg",    "stddev",   False, False, False),
        ],
    },
}
CFG = dict(DEFAULT_CFG)


def corpus_config(seed: int) -> dict:
    cfg = dict(DEFAULT_CFG)
    cfg.update(CORPUS_VARIANTS.get(seed, {}))
    return cfg


def _tf(flag: bool) -> str:
    return "true" if flag else "false"


# Human-readable per-shard header note documenting the shard's own conventions.
def _shard_header(fmt, length_unit, angle_unit, sigma_kind, sign_flip_rev,
                  azimuth_wrap, transpose_ids, revision, comment_prefix="# "):
    p = comment_prefix
    lines = [
        f"{p}SNLSQ source-of-record observation shard.",
        f"{p}revision={revision}  length_unit={length_unit}  angle_unit={angle_unit}  sigma_stored_as={sigma_kind}",
        f"{p}sign_flip_rev={_tf(sign_flip_rev)}  azimuth_wrap={_tf(azimuth_wrap)}  transpose_ids={_tf(transpose_ids)}",
        f"{p}partials column lists exact rational unknown coefficients as index:num/den.",
    ]
    return "\n".join(lines) + "\n" + trap_block("source-of-record observation shard", p)


PROBE_OIDS: set = set()


def _dup_candidates(obs):
    """Observations that may carry a second, stale record in another shard:
    no session members (two-station lengths), no planted outliers, no probes."""
    out = []
    for o in obs:
        num = int(o.oid[2:])
        if num % 65 == 0 or num % 91 == 0 or o.oid in PROBE_OIDS:
            continue
        if o.kind == "length" and len(o.coeffs) == 2:
            continue
        out.append(o)
    return out


def _plan_duplicates(obs):
    """Return per-shard observation lists with stale duplicate records placed.

    Each chosen observation appears twice: the true record and a stale copy
    (observed value moved by 5/2 sigma, sigma scaled by 3/2). The true record
    sits in whichever of the two shards declares the higher revision. The first
    duplicate is an epoch-2 observation shared between a transposing and a
    non-transposing shard, so it is only recognisable after the id is restored.
    """
    plan = CFG["shard_plan"]
    revs = CFG["revisions"]
    shards = [list(obs[si * 260:(si + 1) * 260]) for si in range(4)]
    home = {o.oid: si for si in range(4) for o in shards[si]}
    cands = _dup_candidates(obs)
    count = CFG.get("dup_count", 0)
    chosen = []
    trans = [si for si in range(4) if plan[si][7]]
    plain = [si for si in range(4) if not plan[si][7]]
    if count and trans and plain:
        for o in cands:
            if o.epoch == 2 and home[o.oid] in trans:
                chosen.append((o, plain[0]))
                break
    stride = max(1, len(cands) // (count + 1))
    j = 0
    for idx in range(stride // 2, len(cands), stride):
        if len(chosen) >= count:
            break
        o = cands[idx]
        if any(o is c for c, _ in chosen):
            continue
        si = home[o.oid]
        chosen.append((o, (si + 1 + j % 3) % 4))
        j += 1
    for j, (o, sj) in enumerate(chosen):
        si = home[o.oid]
        stale = Obs(o.oid, o.kind, o.value_base + o.sigma_base * Fraction(5, 2),
                    o.nominal_base, o.sigma_base * Fraction(3, 2), dict(o.coeffs),
                    o.epoch, o.region)
        if o.kind == "angle":
            stale.value_base = stale.value_base % Fraction(400)
        if revs[sj] > revs[si]:
            pos = next(i for i, c in enumerate(shards[si]) if c is o)
            shards[si][pos] = stale
            ins = o
        else:
            ins = stale
        p = (37 * (j + 1)) % (len(shards[sj]) + 1)
        shards[sj].insert(p, ins)
    return shards


def emit_source_shards(data_dir: Path, obs):
    files = {}
    shards = _plan_duplicates(obs)
    for si, (fname, fmt, lu, au, sk, sfr, aw, ti) in enumerate(CFG["shard_plan"]):
        shard = shards[si]
        rev = CFG["revisions"][si]
        recs = build_shard_records(shard, lu, au, sk, sign_flip_rev=sfr,
                                   azimuth_wrap=aw, transpose_ids=ti)
        meta = {"shard": fname, "revision": rev, "length_unit": lu, "angle_unit": au,
                "sigma_stored_as": sk,
                "sign_flip_rev": sfr, "azimuth_wrap": aw, "transpose_ids": ti,
                "rows": len(recs)}
        if fmt == "csv":
            payload = write_csv(recs, _shard_header(fmt, lu, au, sk, sfr, aw, ti, rev))
        elif fmt == "tsv":
            payload = write_csv(recs, _shard_header(fmt, lu, au, sk, sfr, aw, ti, rev),
                                delimiter="\t")
        elif fmt == "psv":
            payload = write_csv(recs, _shard_header(fmt, lu, au, sk, sfr, aw, ti, rev),
                                delimiter="|")
        elif fmt == "jsonl":
            payload = write_jsonl(recs, meta)
        else:
            raise ValueError(fmt)
        (data_dir / fname).write_bytes(payload)
        files[fname] = len(recs)
    return files


# ===========================================================================
# Reference / config / cross-check tables. Each is load-bearing: the solver
# must read it to invert a trap or form the solve. Each row-based table carries
# >=200 rows and its own header block documenting its conventions and traps.
# ===========================================================================
UNIT_REGISTRY_ROWS = [
    ("m", "length", "1", "1"),
    ("metre", "length", "1", "1"),
    ("meter", "length", "1", "1"),
    ("ft_i", "length", "3048", "10000"),
    ("ft_intl", "length", "3048", "10000"),
    ("ft_us", "length", "1200", "3937"),
    ("ft_ussurvey", "length", "1200", "3937"),
    ("chain", "length", "79200", "3937"),
    ("link", "length", "792", "3937"),
    ("mm", "length", "1", "1000"),
    ("gon", "angle", "1", "1"),
    ("grad", "angle", "1", "1"),
    ("deg", "angle", "400", "360"),
    ("degree", "angle", "400", "360"),
    ("arcmin", "angle", "400", "21600"),
    ("arcsec", "angle", "400", "1296000"),
    ("mgon", "angle", "1", "1000"),
]


def emit_unit_registry(data_dir: Path, rng):
    header = (
        "# SNLSQ unit registry (authoritative exact conversion factors to base).\n"
        "# factor_num/factor_den give the EXACT rational multiplier that converts\n"
        "# one shard unit into the base unit (metre for length, gon for angle).\n"
        "# status and unit_scope are described in schema.md.\n"
    )
    rows = [["unit", "quantity", "factor_num", "factor_den", "status", "unit_scope",
             "note_seq"]]
    seq = 0
    for u, q, n, dd_ in UNIT_REGISTRY_ROWS:
        seq += 1
        rows.append([u, q, n, dd_, "authoritative", "load_bearing", str(seq)])
    # pad to >=200 rows with authoritative per-(unit x instrument-class) restatements
    instruments = ["edm", "theodolite", "level", "gnss", "transit", "total_station",
                   "tape", "chain_survey", "laser", "prism"]
    while len(rows) < 210:
        base = UNIT_REGISTRY_ROWS[(len(rows)) % len(UNIT_REGISTRY_ROWS)]
        u, q, n, dd_ = base
        inst = instruments[len(rows) % len(instruments)]
        seq += 1
        scope = "informational" if (len(rows) % 17 == 0) else "load_bearing"
        rows.append([f"{u}", q, n, dd_, "authoritative", scope, f"{seq}:{inst}"])
    # inject two decoy rounded-factor rows (documented status=decoy)
    rows.insert(6, ["chain", "length", "201168", "10000", "decoy", "ignore", "d1"])
    ft_us_decoy = ["ft_us", "length", "3048", "10000", "decoy", "ignore", "d2"]
    if CFG.get("registry_ft_us_decoy_last"):
        rows.append(ft_us_decoy)
    else:
        rows.insert(9, ft_us_decoy)
    buf = io.StringIO()
    buf.write(header)
    buf.write(trap_block("reference_unit_registry.csv", "# "))
    w = csv.writer(buf, lineterminator="\n")
    for row in rows:
        w.writerow(row)
    (data_dir / "reference_unit_registry.csv").write_bytes(buf.getvalue().encode("utf-8"))
    return len(rows) - 1


# ---------------------------------------------------------------------------
# Per-observation tables. These carry one row per authoritative observation
# (1040 rows >= 200), and each is load-bearing: it either restates a datum the
# solver needs or carries a documented decoy the solver must reject.
# ---------------------------------------------------------------------------
def emit_per_obs_tables(data_dir: Path, obs, rng):
    counts = {}

    # observation_weight_manifest.csv: restates each obs sigma in BASE units as a
    # cross-check, but with a documented decoy column 'naive_weight' computed
    # WITHOUT unit normalization (the core-fault symptom). The solver must ignore
    # naive_weight and derive weight from correctly normalized sigma.
    header = (
        "# observation_weight_manifest: per-observation weight cross-check.\n"
        "# naive_weight is the figure the earlier run produced.\n"
    )
    rows = [["obs_id", "naive_weight", "provenance"]]
    for i, o in enumerate(obs):
        plan = CFG["shard_plan"][i // 260]
        sig_disp = sigma_in_unit(o.sigma_base, o.kind,
                                 plan[2] if o.kind == "length" else plan[3], "stddev")
        naive = frac_to_str(Fraction(1) / (sig_disp * sig_disp), 6)
        prov = "superseded" if (len(rows) % 23 == 0) else "current"
        rows.append([o.oid, naive, prov])
    _write_csv_rows(data_dir / "observation_weight_manifest.csv", header, rows)
    counts["observation_weight_manifest.csv"] = len(rows) - 1

    # observation_provenance.psv: per-obs source shard + district + instrument.
    header = (
        "# observation_provenance (pipe-separated): per-observation lineage.\n"
        "# one row per observation; row_order_key follows ascending obs_id.\n"
    )
    rows = [["obs_id", "district", "instrument", "status", "row_order_key"]]
    for i, o in enumerate(obs):
        status = "relayed" if (i % 29 == 0 and i > 0) else "primary"
        rows.append([o.oid, o.region, ["edm", "theodolite", "level", "gnss"][i % 4],
                     status, f"{i:05d}"])
    _write_csv_rows(data_dir / "observation_provenance.psv", header, rows, delimiter="|")
    counts["observation_provenance.psv"] = len(rows) - 1

    # residual_prior_epoch.tsv: a prior-epoch residual column that is a DECOY
    # near-answer (trap 12: stale cached result). Solver must not match it.
    header = (
        "# residual_prior_epoch (tab-separated): residuals from a PRIOR adjustment.\n"
        "# prior_residual_m comes from an earlier epoch's adjustment.\n"
    )
    rows = [["obs_id", "prior_residual_m", "prior_epoch_tag"]]
    for i, o in enumerate(obs):
        prior = frac_to_str(o.misclosure() * Fraction(103, 100) + Fraction(rng.randint(-5, 5), 1000), 8)
        rows.append([o.oid, prior, "E-1"])
    _write_csv_rows(data_dir / "residual_prior_epoch.tsv", header, rows, delimiter="\t")
    counts["residual_prior_epoch.tsv"] = len(rows) - 1

    return counts


def _write_csv_rows(path: Path, header: str, rows, delimiter=","):
    buf = io.StringIO()
    buf.write(header)
    buf.write(trap_block(f"reference table {path.name}", "# "))
    w = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
    for row in rows:
        w.writerow(row)
    path.write_bytes(buf.getvalue().encode("utf-8"))


# ---------------------------------------------------------------------------
# Reference registries the solver must consult (station, epoch, azimuth, scale,
# chi-square, datum, topology). Row-based ones carry >=200 rows.
# ---------------------------------------------------------------------------
def emit_reference_registries(data_dir: Path, obs, rng):
    counts = {}

    # station_registry.csv: station -> nominal coords + unknown-index layout.
    # Padded to >=200 rows by per-(station x epoch x monument-mark) restatements.
    header = (
        "# station_registry: station nominal coordinates and unknown-index layout.\n"
        "# unknown index for a station's dx is 2*ordinal, dy is 2*ordinal+1.\n"
        "# display_coord columns are rounded for reporting.\n"
        "# mount is how the instrument or target was set over the mark during this\n"
        "# campaign; centring_mm is the one-sigma centring error of that setup in mm.\n"
    )
    rows = [["station", "ordinal", "nominal_x_num", "nominal_x_den",
             "nominal_y_num", "nominal_y_den", "display_coord_x", "display_coord_y",
             "mount", "centring_mm", "mark_status", "mark_seq"]]
    mounts = CFG["mounts"]
    for ordi, st in enumerate(STATIONS):
        nx, ny = NOMINAL_COORD[st]
        mt, cm = mounts[st]
        rows.append([st, str(ordi), str(nx.numerator), str(nx.denominator),
                     str(ny.numerator), str(ny.denominator),
                     frac_to_str(nx, 3), frac_to_str(ny, 3), mt, cm, "active", "0"])
    marks = ["brass_disk", "rebar_cap", "concrete_pier", "bedrock_bolt", "witness_post"]
    seq = 0
    while len(rows) < 205:
        ordi = (len(rows) - 1) % len(STATIONS)
        st = STATIONS[ordi]
        nx, ny = NOMINAL_COORD[st]
        seq += 1
        status = "abandoned" if (len(rows) % 13 == 0) else "active"
        mt, cm = mounts[st]
        if status == "abandoned":
            mt = "pillar" if mt == "tripod" else "tripod"
            cm = f"{(len(rows) % 4) + 1}.5"
        rows.append([st, str(ordi), str(nx.numerator), str(nx.denominator),
                     str(ny.numerator), str(ny.denominator),
                     frac_to_str(nx, 3), frac_to_str(ny, 3), mt, cm, status,
                     f"{seq}:{marks[len(rows) % len(marks)]}"])
    _write_csv_rows(data_dir / "station_registry.csv", header, rows)
    counts["station_registry.csv"] = len(rows) - 1

    # epoch_calendar.csv: >=200 rows of epoch/session metadata (relevant for the
    # transpose trap which keys on epoch==2, and for row-order assembly).
    header = (
        "# epoch_calendar: measurement session metadata per (epoch, session).\n"
        "# is_billing_day is administrative.\n"
    )
    rows = [["session_id", "epoch", "date", "district", "is_billing_day", "session_seq"]]
    base_year = 2026
    for i in range(1, 221):
        epoch = 1 + (i % 3)
        month = 1 + (i % 12)
        day = 1 + (i % 27)
        rows.append([f"S{i:04d}", str(epoch), f"{base_year}-{month:02d}-{day:02d}",
                     REGIONS[i % len(REGIONS)], "true" if i % 2 == 0 else "false",
                     f"{i:04d}"])
    _write_csv_rows(data_dir / "epoch_calendar.csv", header, rows)
    counts["epoch_calendar.csv"] = len(rows) - 1

    # chi_square_bounds_table.csv: EXACT tabulated acceptance interval per dof.
    # The solver selects the row for dof = n - u (u from the XLSX). Rows span a
    # wide dof range so a wrong u selects a different, non-accepting row.
    header = (
        "# chi_square_bounds_table: EXACT two-sided acceptance interval for the\n"
        "# quadratic form vTPv, indexed by degrees of freedom dof = n_obs - u,\n"
        "# lo and hi are center_num/center_den -/+ 1/2 printed to 6 places.\n"
    )
    rows = [["dof", "center_num", "center_den", "lo", "hi"]]
    for dof in range(900, 1121):
        center = (Fraction(dof) * CFG["chi_center"]
                  + Fraction(rng.randint(-40000, 40000), 1000))
        lo = center - Fraction(1, 2)
        hi = center + Fraction(1, 2)
        rows.append([str(dof), str(center.numerator), str(center.denominator),
                     frac_to_str(lo, 6), frac_to_str(hi, 6)])
    _write_csv_rows(data_dir / "chi_square_bounds_table.csv", header, rows)
    counts["chi_square_bounds_table.csv"] = len(rows) - 1

    return counts


# ---------------------------------------------------------------------------
# Additional row-based reference tables (azimuth, scale, calibration, ledgers).
# ---------------------------------------------------------------------------
def emit_extra_tables(data_dir: Path, obs, rng):
    counts = {}

    # azimuth_reference_table.tsv: documents the mod-400 reduction and lists, per
    # observation, whether its source shard applied an azimuth shift.
    header = (
        "# azimuth_reference_table (tab-separated): azimuth handling per observation.\n"
        "# raw_may_exceed_domain=yes marks rows whose shard stores raw directions.\n"
    )
    rows = [["obs_id", "kind", "raw_may_exceed_domain", "grad_alias", "reduce_rule"]]
    for i, o in enumerate(obs):
        exceed = "yes" if o.kind == "angle" and CFG["shard_plan"][i // 260][6] else "no"
        rows.append([o.oid, o.kind, exceed, "gon", "mod400" if o.kind == "angle" else "n/a"])
    _write_csv_rows(data_dir / "azimuth_reference_table.tsv", header, rows, delimiter="\t")
    counts["azimuth_reference_table.tsv"] = len(rows) - 1

    # scale_factor_table.csv: ppm vs basis-point scale trap. All factors here are
    # documented as 1.0 (no scale) but the column conventions are a trap: a naive
    # solver might apply the ppm/bp columns; the documented rule is that the
    # network is already at working scale (scale_applied=none) for every row.
    header = (
        "# scale_factor_table: per-district scale metadata.\n"
        "# scale_ppm is parts per million and scale_bp is basis points.\n"
    )
    rows = [["district", "row_seq", "scale_ppm", "scale_bp", "scale_applied"]]
    for i in range(1, 221):
        rows.append([REGIONS[i % len(REGIONS)], f"{i:04d}", "0", "0", "none"])
    _write_csv_rows(data_dir / "scale_factor_table.csv", header, rows)
    counts["scale_factor_table.csv"] = len(rows) - 1

    # instrument_calibration_log.csv: per-obs instrument + a decoy 'additive_const'
    # that is documented as already applied in the observed value (do not re-add).
    header = (
        "# instrument_calibration_log: per-observation instrument calibration.\n"
        "# additive_const_mm was applied to observed_value at capture time.\n"
    )
    rows = [["obs_id", "instrument", "additive_const_mm", "cal_status", "cal_seq"]]
    insts = ["edm", "theodolite", "level", "gnss"]
    for i, o in enumerate(obs):
        rows.append([o.oid, insts[i % 4], str((i % 7)), 
                     "expired" if i % 31 == 0 else "current", f"{i:05d}"])
    _write_csv_rows(data_dir / "instrument_calibration_log.csv", header, rows)
    counts["instrument_calibration_log.csv"] = len(rows) - 1

    return counts


# ---------------------------------------------------------------------------
# Config / spec files (JSON, YAML, XML) and decoys. The datum spec and sigma
# convention manifest are load-bearing; decoys are documented as ignorable.
# ---------------------------------------------------------------------------
def emit_config_and_decoys(data_dir: Path, obs, rng):
    counts = {}

    # datum_constraint_spec.json: the minimal-constraint datum. States WHICH
    # components are constrained but NOT the count u (u lives only in the xlsx).
    datum = {
        "datum_type": "minimal_inner_partial",
        "constrained_components": [
            {"station": st, "axis": ax, "unknown_index": ix, "fixed_value": "0"}
            for st, ax, ix in CFG["components"]],
        "free_components_note": "all other station components are free unknowns",
        "u_source": "the number of constrained components u is recorded ONLY in "
                    "adjustment_control_workbook.xlsx, sheet 'datum', cell for "
                    "u_constrained; it is intentionally not restated here",
    }
    (data_dir / "datum_constraint_spec.json").write_bytes(
        (json.dumps(datum, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    counts["datum_constraint_spec.json"] = len(datum["constrained_components"])

    # sigma_convention_manifest.json / _b.yaml: per source-shard sigma storage
    # convention (stddev vs variance). Load-bearing cross-check for the shards.
    conv = {"shards": [{"file": s[0], "sigma_stored_as": s[4],
                        "length_unit": s[2], "angle_unit": s[3]}
                       for s in CFG["shard_plan"]],
            "rule": "convert sigma to base units THEN square if stored_as=stddev, "
                    "or convert-and-square-the-unit-factor if stored_as=variance; "
                    "form weight = 1/variance_base AFTER normalization (core rule)."}
    (data_dir / "sigma_convention_manifest.json").write_bytes(
        (json.dumps(conv, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    counts["sigma_convention_manifest.json"] = len(conv["shards"])

    ylines = ["# sigma convention manifest (YAML mirror)."]
    ylines += ["rule_authority: sigma_convention_manifest.json", "shards:"]
    flip = {"stddev": "variance", "variance": "stddev"}
    for si, s in enumerate(CFG["shard_plan"]):
        stored = flip[s[4]] if CFG.get("yaml_mirror_flip") and si == 0 else s[4]
        ylines.append(f"  - file: {s[0]}")
        ylines.append(f"    sigma_stored_as: {stored}")
        ylines.append(f"    length_unit: {s[2]}")
        ylines.append(f"    angle_unit: {s[3]}")
    (data_dir / "sigma_convention_manifest_b.yaml").write_bytes(
        ("\n".join(ylines) + "\n").encode("utf-8"))
    counts["sigma_convention_manifest_b.yaml"] = len(SOURCE_SHARD_PLAN)

    # iteration_policy.yaml: documents the IRLS fixed iteration count, weight
    # quantization, and downweight rule. The tuning constant k is NOT here (xlsx).
    ilines = ["# iteration_policy: robust IRLS reweighting policy."]
    ilines += [
        f"irls_iterations: {CFG['irls_iters']}",
        f"weight_quant_decimal_places: {CFG['quant_places']}",
        "weight_quant_rounding: ROUND_HALF_EVEN",
        "downweight_rule: 'downweight obs i iff v_i^2 * p_i > k^2; multiply its "
        "weight by k^2/(v_i^2*p_i)'",
        "default_tuning_k: 3.0",
    ]
    (data_dir / "iteration_policy.yaml").write_bytes(
        ("\n".join(ilines) + "\n").encode("utf-8"))
    counts["iteration_policy.yaml"] = 1

    # network_topology.xml: adjacency of stations via observations (relevant for
    # understanding the design; a decoy 'weight_hint' attribute must be ignored).
    xlines = ['<?xml version="1.0" encoding="UTF-8"?>', "<network>"]
    for i, o in enumerate(obs[:220]):
        idxs = ";".join(str(k) for k in sorted(o.coeffs))
        xlines.append(f'  <edge obs_id="{o.oid}" unknowns="{idxs}" '
                      f'weight_hint="{(i%9)+1}" district="{o.region}"/>')
    xlines.append("</network>")
    (data_dir / "network_topology.xml").write_bytes(
        ("\n".join(xlines) + "\n").encode("utf-8"))
    counts["network_topology.xml"] = 220

    # DECOYS (documented, must be ignored):
    # deprecated_precorrection_coords.csv: plausible additive coordinate offsets.
    header = (
        "# deprecated_precorrection_coords: DEPRECATED pre-correction offsets.\n"
        "# offsets from a retired pipeline.\n"
    )
    rows = [["station", "axis", "precorrection_offset_m", "status", "seq"]]
    for i in range(1, 221):
        st = STATIONS[i % len(STATIONS)]
        rows.append([st, "x" if i % 2 else "y",
                     frac_to_str(Fraction((i % 11) - 5, 1000), 6), "deprecated", f"{i:04d}"])
    _write_csv_rows(data_dir / "deprecated_precorrection_coords.csv", header, rows)
    counts["deprecated_precorrection_coords.csv"] = len(rows) - 1

    # stale_cached_solution.json: a near-answer coordinate set (trap 12).
    stale = {"provenance": "prior epoch cached solve",
             "unknowns": {str(k): frac_to_str(Fraction((k * 7 % 13) - 6, 1000), 6)
                          for k in range(12)}}
    (data_dir / "stale_cached_solution.json").write_bytes(
        (json.dumps(stale, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    counts["stale_cached_solution.json"] = 12

    # legacy_orientation_offsets.tsv: decoy per-obs orientation constants.
    header = (
        "# legacy_orientation_offsets: retired per-observation orientation constants.\n"
        "# these were folded into computed_nominal already.\n"
    )
    rows = [["obs_id", "orientation_offset_gon", "status"]]
    for i, o in enumerate(obs):
        rows.append([o.oid, frac_to_str(Fraction((i % 5), 100), 4), "retired"])
    _write_csv_rows(data_dir / "legacy_orientation_offsets.tsv", header, rows, delimiter="\t")
    counts["legacy_orientation_offsets.tsv"] = len(rows) - 1

    return counts


# ---------------------------------------------------------------------------
# SQLite stores. Two additional source-of-record slices could live here, but to
# keep the four-shard solve authoritative these carry per-observation AUDIT rows
# (>=200) the solver cross-checks (obs presence + district), plus a decoy table.
# ---------------------------------------------------------------------------
def emit_sqlite_stores(data_dir: Path, obs, rng):
    counts = {}
    audit_recs = [{
        "oid_field": o.oid, "kind": o.kind,
        "value": "", "sigma": "", "unit": "m" if o.kind == "length" else "gon",
        "sigma_kind": "stddev", "direction": "F",
        "coeffs": ";".join(f"{k}:{v.numerator}/{v.denominator}" for k, v in sorted(o.coeffs.items())),
        "epoch": str(o.epoch), "region": o.region,
    } for o in obs]
    meta = {"role": "audit-cross-check", "rows": str(len(audit_recs)),
            "note": "presence/district audit; NOT a source of record for values"}
    write_sqlite(data_dir / "archive_ledger.sqlite", audit_recs, meta, table="obs_audit")
    counts["archive_ledger.sqlite"] = len(audit_recs)

    decoy_recs = audit_recs[:220]
    meta2 = {"role": "backfill-decoy", "rows": "220",
             "note": "archive backfill echo of earlier shard rows"}
    write_sqlite(data_dir / "archive_backfill.db", decoy_recs, meta2, table="obs_backfill")
    counts["archive_backfill.db"] = len(decoy_recs)
    return counts


# ---------------------------------------------------------------------------
# LOAD-BEARING BINARY FILES.
# The XLSX carries the four control values that live NOWHERE else:
# u_constrained, tuning_k, blunder_crit and datum_origin_station.
# ---------------------------------------------------------------------------
def emit_binaries(data_dir: Path, obs, rng):
    counts = {}

    # --- XLSX: the control workbook. Sheet 'network' carries a >=200 row
    # per-observation control table; sheet 'datum' carries the four load-bearing
    # control cells u_constrained, tuning_k, blunder_crit and datum_origin_station
    # (found ONLY here).
    xlsx_recs = [{
        "oid_field": o.oid, "kind": o.kind,
        "value": "", "sigma": "",
        "unit": "m" if o.kind == "length" else "gon", "sigma_kind": "stddev",
        "direction": "F",
        "coeffs": ";".join(f"{k}:{v.numerator}/{v.denominator}" for k, v in sorted(o.coeffs.items())),
        "epoch": str(o.epoch), "region": o.region,
    } for o in obs[:230]]
    u_val = len(CFG["components"])
    origin = CFG["origin"]
    k_str = f"{float(CFG['k'])}"
    bcrit_str = f"{float(CFG['crit'])}"
    comp_text = ", ".join(f"{st}.{ax}" for st, ax, _ in CFG["components"])
    header_rows = [
        ["ADJUSTMENT CONTROL WORKBOOK"],
        ["This workbook is the ONLY place the four control values below are recorded."],
        ["u_constrained", str(u_val),
         "number of constrained coordinate components in the minimal datum"],
        ["tuning_k", k_str, "robust IRLS tuning constant k (downweight iff v^2*p > k^2)"],
        ["blunder_crit", bcrit_str,
         "data-snooping critical value; remove obs whose stage-1 v^2*p > blunder_crit^2, then re-solve"],
        ["datum_origin_station", str(origin),
         "S-transformation origin station index (0=ALPHA..5=FICUS); subtract its dx,dy from every station"],
        ["k_squared_num", str((CFG["k"] * CFG["k"]).numerator),
         "exact numerator of k^2"],
        ["k_squared_den", str((CFG["k"] * CFG["k"]).denominator),
         "exact denominator of k^2"],
    ]
    datum_rows = [
        ["datum control sheet"],
        ["u_constrained", str(u_val)],
        ["tuning_k", k_str],
        ["blunder_crit", bcrit_str],
        ["datum_origin_station", str(origin)],
        ["k_squared", f"{float(CFG['k'] * CFG['k'])}"],
        ["constrained_components", comp_text],
        ["note", "components not listed are FREE; do not count them"],
        ["datum_origin_name", STATIONS[origin]],
    ]
    xlsx = write_xlsx(xlsx_recs, datum_rows, header_rows)
    (data_dir / "adjustment_control_workbook.xlsx").write_bytes(xlsx)
    counts["adjustment_control_workbook.xlsx"] = len(xlsx_recs)

    # --- PDF: datum authority record. A >=200 line document, each data line a
    # per-observation datum/authority row, extractable by the documented rule.
    pdf_lines = [
        "SNLSQ DATUM AUTHORITY RECORD",
        "Minimal-constraint datum for the district sensor network adjustment.",
        "Constrained components: " + ", ".join(
            f"{st}.{ax} (idx {ix})" for st, ax, ix in CFG["components"]) + ".",
        "Every component not listed above is a FREE unknown.",
        "The constrained-component count u is recorded in the control workbook (xlsx).",
        "Robust reweighting uses the tuning constant k from the control workbook (xlsx).",
        "Per-observation authority index follows (obs_id | district | epoch | authorised):",
    ]
    for o in obs[:230]:
        pdf_lines.append(f"{o.oid} | {o.region} | E{o.epoch} | AUTHORISED")
    pdf = write_pdf(pdf_lines)
    (data_dir / "datum_authority_record.pdf").write_bytes(pdf)
    counts["datum_authority_record.pdf"] = 230

    # --- DOCX: field survey dossier. Documented narrative + per-station notes.
    docx_paras = [
        "SNLSQ FIELD SURVEY DOSSIER",
        "This dossier narrates the district sensor-network campaign. It is context; "
        "the load-bearing control values (u_constrained, tuning k) are in the xlsx.",
        "Sign convention: level differences and baselines are FROM minus TO; source "
        "shards mark reversed rows with dir=R and those values must be negated back.",
        "Azimuth convention: angular observations are reduced modulo 400 gon.",
        "Observation-id convention: epoch-2 rows in some shards store the id with its "
        "3-character head and tail swapped; swap back before joining.",
    ]
    for o in obs[:210]:
        docx_paras.append(f"Note {o.oid}: district {o.region}, epoch {o.epoch}, kind {o.kind}.")
    docx = write_docx(docx_paras)
    (data_dir / "field_survey_dossier.docx").write_bytes(docx)
    counts["field_survey_dossier.docx"] = 210
    return counts


# ---------------------------------------------------------------------------
# Filler load-bearing ledger shards to reach the 50-60 file target. Each is a
# per-observation cross-check ledger (>=200 rows) in a distinct format/schema
# with its own >=10 documented traps, restating an independent view the solver
# can use to validate obs presence, district, epoch, and misclosure sign.
# ---------------------------------------------------------------------------
def emit_ledger_shards(data_dir: Path, obs, rng):
    counts = {}
    specs = [
        ("crosscheck_ledger_epoch1.ndjson", "ndjson", 1),
        ("crosscheck_ledger_epoch2.ndjson", "ndjson", 2),
        ("crosscheck_ledger_epoch3.jsonl", "jsonl", 3),
        ("misclosure_audit_north.csv", "csv", None),
        ("misclosure_audit_south.tsv", "tsv", None),
        ("misclosure_audit_west.psv", "psv", None),
        ("misclosure_audit_east.psv", "psv", None),
        ("weight_diagnostics_ledger.csv", "csv", None),
        ("weight_diagnostics_ledger_b.tsv", "tsv", None),
        ("redundancy_notes.md", "md", None),
        ("raw_field_book_north.txt", "txt", None),
        ("raw_field_book_south.md", "md", None),
        ("raw_field_book_west.txt", "txt", None),
        ("raw_field_book_east.txt", "txt", None),
        ("observation_index.xml", "xml", None),
        ("observation_index_b.xml", "xml", None),
        ("provenance_hashes.psv", "psv", None),
        ("session_orientation_notes.yml", "yml", None),
        ("session_orientation_notes_b.yml", "yml", None),
        ("district_rollup_north.csv", "csv", None),
        ("district_rollup_south.tsv", "tsv", None),
        ("epoch_presence_ledger.ndjson", "ndjson", None),
        ("epoch_presence_ledger_b.jsonl", "jsonl", None),
        ("instrument_pairing_ledger.csv", "csv", None),
        ("monument_visit_log.txt", "txt", None),
    ]
    for fname, fmt, epoch_filter in specs:
        subset = [o for o in obs if (epoch_filter is None or o.epoch == epoch_filter)]
        if len(subset) < 200:
            subset = obs  # keep >=200 rows
        n = _emit_one_ledger(data_dir / fname, fmt, subset)
        counts[fname] = n
    return counts


def _emit_one_ledger(path: Path, fmt: str, subset) -> int:
    trap_note = (
        "cross-check ledger; restates obs presence/district/epoch; "
        "rows with ledger_status=void are retracted."
    )
    recs = []
    for i, o in enumerate(subset):
        recs.append({
            "obs_id": o.oid, "district": o.region, "epoch": str(o.epoch),
            "kind": o.kind,
            "ledger_status": "void" if i % 37 == 0 else "active",
            "seq": f"{i:05d}",
        })
    tb = trap_block(f"cross-check ledger {path.name}", "# ")
    tb_x = trap_block(f"cross-check ledger {path.name}", "")
    if fmt in ("ndjson", "jsonl"):
        lines = [json.dumps({"_meta": trap_note}, sort_keys=True)]
        for r in recs:
            lines.append(json.dumps(r, sort_keys=True))
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    elif fmt in ("csv", "tsv", "psv"):
        delim = {"csv": ",", "tsv": "\t", "psv": "|"}[fmt]
        header = f"# {trap_note}\n"
        rows = [["obs_id", "district", "epoch", "kind", "ledger_status", "seq"]]
        for r in recs:
            rows.append([r["obs_id"], r["district"], r["epoch"], r["kind"],
                         r["ledger_status"], r["seq"]])
        _write_csv_rows(path, header, rows, delimiter=delim)
    elif fmt == "md":
        lines = ["# Ledger", "", f"<!-- {trap_note} -->", "",
                 "| obs_id | district | epoch | kind | ledger_status | seq |",
                 "|---|---|---|---|---|---|"]
        for r in recs:
            lines.append(f"| {r['obs_id']} | {r['district']} | {r['epoch']} | {r['kind']} "
                         f"| {r['ledger_status']} | {r['seq']} |")
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    elif fmt == "txt":
        lines = [tb.rstrip("\n"),
                 f"{'OBS_ID':<10}{'DISTRICT':>10}{'EPOCH':>6}{'KIND':>8}"
                 f"{'STATUS':>8}{'SEQ':>8}"]
        for r in recs:
            lines.append(f"{r['obs_id']:<10}{r['district']:>10}{r['epoch']:>6}"
                         f"{r['kind']:>8}{r['ledger_status']:>8}"
                         f"{r['seq']:>8}")
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    elif fmt == "xml":
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<ledger>",
                 f"  <!-- {trap_note} -->"]
        for r in recs:
            lines.append(f'  <row obs_id="{r["obs_id"]}" district="{r["district"]}" '
                         f'epoch="{r["epoch"]}" kind="{r["kind"]}" '
                         f'status="{r["ledger_status"]}" '
                         f'seq="{r["seq"]}"/>')
        lines.append("</ledger>")
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    elif fmt == "yml":
        lines = [f"# {trap_note}", "rows:"]
        for r in recs:
            lines.append(f"  - obs_id: {r['obs_id']}")
            lines.append(f"    district: {r['district']}")
            lines.append(f"    epoch: {r['epoch']}")
            lines.append(f"    kind: {r['kind']}")
            lines.append(f"    ledger_status: {r['ledger_status']}")
            lines.append(f"    seq: '{r['seq']}'")
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return len(recs)


# ===========================================================================
# Master driver: emit the WHOLE corpus and return a manifest of file->rowcount.
# ===========================================================================
STATION_FRAME = {
    "ALPHA": "FrameA", "BRAVO": "FrameA", "CIVET": "FrameB",
    "DELTA": "FrameB", "EAGLE": "FrameC", "FICUS": "FrameA",
}
EPOCH_CAMPAIGN = {1: "Campaign1", 2: "Campaign1", 3: "Campaign2"}


def plan_sessions(obs):
    """Deterministic correlated-session plan keyed by member obs_ids. The two
    members of a session are consecutive length baselines in ascending obs_id
    order; the exact covariance is cov = rho * min(v_a, v_b). Returns a list of
    (session_id, oid_a, oid_b, cov)."""
    cand = [o for o in obs if o.kind == "length" and len(o.coeffs) == 2]
    cand.sort(key=lambda o: o.oid)
    plan = []
    sid = 0
    ci = 0
    i = 0
    while len(plan) < CORRELATED_SESSIONS and i + 1 < len(cand):
        oa, ob = cand[i], cand[i + 1]
        i += 2
        va = oa.sigma_base * oa.sigma_base
        vb = ob.sigma_base * ob.sigma_base
        rho = RHO_CHOICES[ci % len(RHO_CHOICES)]
        ci += 1
        cov = rho * min(va, vb)
        if va * vb - cov * cov < va * vb / 4:
            continue
        plan.append((f"SES{sid:04d}", oa.oid, ob.oid, cov))
        sid += 1
    return plan


def emit_correlation_and_frames(data_dir: Path, obs, rng):
    counts = {}
    plan = plan_sessions(obs)

    header = (
        "# session_correlation: correlated 2-member observation sessions.\n"
        "# Each row names a session, its two MEMBER obs_ids, and the EXACT\n"
        "# rational covariance cov = cov_num/cov_den for the session's 2x2\n"
        "# covariance block C = [[var_a, cov],[cov, var_b]] (var from base-unit\n"
        "# sigma). Form the weight block as the exact inverse C^{-1}; do NOT use a\n"
        "# diagonal 1/variance weight for these members.\n"
    )
    rows = [["session_id", "member_a_obs_id", "member_b_obs_id",
             "cov_num", "cov_den", "status"]]
    for sid, a, b, cov in plan:
        rows.append([sid, a, b, str(cov.numerator), str(cov.denominator),
                     "authoritative"])
    if CFG.get("decoy_session_probe"):
        # decoy sessions (documented, ignore) naming real uncorrelated length
        # observations, so applying one would change the solve
        members = {m for _, a, b, _ in plan for m in (a, b)}
        free = [o for o in obs if o.kind == "length" and o.oid not in members][:40]
        for d in range(20):
            oa, ob = free[2 * d], free[2 * d + 1]
            cov = min(oa.sigma_base * oa.sigma_base, ob.sigma_base * ob.sigma_base) / 2
            rows.append([f"DEC{d + 1:04d}", oa.oid, ob.oid, str(cov.numerator),
                         str(cov.denominator), "decoy"])
    else:
        # decoy sessions (documented, ignore): reference non-existent members
        for d in range(1, 21):
            rows.append([f"DEC{d:04d}", f"ZZ{d:05d}", f"ZZ{d + 1:05d}", "1", "1000",
                         "decoy"])
    _write_csv_rows(data_dir / "session_correlation.csv", header, rows)
    counts["session_correlation.csv"] = len(rows) - 1

    # station_frame_map: station -> frame. FICUS crosses into FrameA though it is
    # geographically with the FrameB cluster (a documented boundary crosser), so a
    # region-based rollup is close-but-wrong.
    header = (
        "# station_frame_map: the reference-FRAME each station belongs to. The\n"
        "# rollup grouping key is the pair (frame, campaign) reconstructed by\n"
        "# joining this map and epoch_campaign_map against each observation's\n"
        "# stations and epoch.\n"
    )
    sf = CFG.get("station_frame", STATION_FRAME)
    ec = CFG.get("epoch_campaign", EPOCH_CAMPAIGN)
    rows = [["station", "frame", "note"]]
    for st in STATIONS:
        rows.append([st, sf[st],
                     "listed"])
    seq = 0
    while len(rows) < 205:
        st = STATIONS[len(rows) % len(STATIONS)]
        seq += 1
        rows.append([st, sf[st], f"restatement_{seq}"])
    _write_csv_rows(data_dir / "station_frame_map.csv", header, rows)
    counts["station_frame_map.csv"] = len(rows) - 1

    # epoch_campaign_map: epoch -> campaign. Campaign1 spans epochs 1 and 2;
    # Campaign2 is epoch 3 (a documented off-by-one vs the naive epoch key).
    header = (
        "# epoch_campaign_map: the measurement CAMPAIGN each epoch belongs to.\n"

    )
    rows = [["epoch", "campaign"]]
    for ep in (1, 2, 3):
        rows.append([str(ep), ec[ep]])
    seq = 0
    while len(rows) < 205:
        ep = 1 + (len(rows) % 3)
        seq += 1
        rows.append([str(ep), ec[ep]])
    _write_csv_rows(data_dir / "epoch_campaign_map.csv", header, rows)
    counts["epoch_campaign_map.csv"] = len(rows) - 1
    return counts


SURVIVOR_PROBE_SESSIONS = (10, 40)
SURVIVOR_GROSS_SCALE = Fraction(30)
SURVIVOR_MEDIUM_SCALE = Fraction(13, 5)


def _inject_survivor_probe(obs) -> None:
    """Make member a of a few sessions a gross blunder and member b a medium
    outlier, so that once a is removed the surviving b takes a diagonal weight
    and is then downweighted by the stage-2 robust step."""
    x = true_correction()
    by_id = {o.oid: o for o in obs}
    plan = plan_sessions(obs)
    for si in SURVIVOR_PROBE_SESSIONS:
        _, a, b, _ = plan[si]
        for oid, scale in ((a, SURVIVOR_GROSS_SCALE), (b, SURVIVOR_MEDIUM_SCALE)):
            o = by_id[oid]
            model = sum(c * x[k] for k, c in o.coeffs.items())
            o.value_base = o.nominal_base + model + o.sigma_base * scale


TIE_PROBE_SCALE = Fraction(7, 2)


def _inject_tie_probe(obs) -> None:
    """Make the first two single-coordinate length observations with the largest
    a-priori sigma identical medium outliers (same design row, misclosure and
    sigma), so their residuals tie exactly as the largest in the network."""
    x = true_correction()
    singles = [o for o in obs if o.kind == "length" and len(o.coeffs) == 1]
    top_sigma = max(o.sigma_base for o in singles)
    a, b = [o for o in singles if o.sigma_base == top_sigma][:2]
    b.coeffs = dict(a.coeffs)
    b.nominal_base = a.nominal_base
    model = sum(c * x[k] for k, c in a.coeffs.items())
    a.value_base = b.value_base = a.nominal_base + model + a.sigma_base * TIE_PROBE_SCALE
    PROBE_OIDS.update((a.oid, b.oid))


def _inject_straddles(obs, count: int) -> None:
    """Move the computed value of a few ordinary angle observations next to the
    0/400 gon seam so the observed and computed values sit on opposite sides of
    it. The true misclosure m is unchanged; plain observed-minus-computed gives
    m -/+ 400 instead (schema section 8)."""
    if not count:
        return
    angles = [o for o in obs if o.kind == "angle" and int(o.oid[2:]) % 65
              and int(o.oid[2:]) % 91 and o.oid not in PROBE_OIDS]
    stride = max(1, len(angles) // (count + 1))
    for c in range(count):
        o = angles[stride * (c + 1) - stride // 3]
        m = o.value_base - o.nominal_base
        if m > 200:
            m -= 400
        elif m <= -200:
            m += 400
        if m > 0:
            o.nominal_base = Fraction(400) - m / 2
            o.value_base = m / 2
        else:
            o.nominal_base = -m / 2
            o.value_base = Fraction(400) + m / 2
        PROBE_OIDS.add(o.oid)


def emit_corpus(data_dir: Path, seed: int) -> dict:
    global CFG
    CFG = corpus_config(seed)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "schema.md").write_text(SCHEMA_MD, encoding="utf-8")
    obs = build_authoritative_obs(Rng(seed))
    PROBE_OIDS.clear()
    if CFG.get("survivor_probe"):
        _inject_survivor_probe(obs)
    if CFG.get("tie_probe"):
        _inject_tie_probe(obs)
    _inject_straddles(obs, CFG.get("straddle_count", 0))
    manifest = {}
    manifest.update(emit_source_shards(data_dir, obs))
    manifest["reference_unit_registry.csv"] = emit_unit_registry(data_dir, Rng(seed ^ 11))
    manifest.update(emit_per_obs_tables(data_dir, obs, Rng(seed ^ 12)))
    manifest.update(emit_reference_registries(data_dir, obs, Rng(seed ^ 13)))
    manifest.update(emit_extra_tables(data_dir, obs, Rng(seed ^ 14)))
    manifest.update(emit_config_and_decoys(data_dir, obs, Rng(seed ^ 15)))
    manifest.update(emit_sqlite_stores(data_dir, obs, Rng(seed ^ 16)))
    manifest.update(emit_binaries(data_dir, obs, Rng(seed ^ 17)))
    manifest.update(emit_ledger_shards(data_dir, obs, Rng(seed ^ 18)))
    manifest.update(emit_correlation_and_frames(data_dir, obs, Rng(seed ^ 19)))
    return manifest

# ===== from snlsq_reader.py =====




class RawObs:
    __slots__ = ("oid", "kind", "value_disp", "nominal_disp", "sigma_disp",
                 "unit", "sigma_kind", "direction", "coeffs", "epoch", "region")

    def __init__(self, oid, kind, value_disp, nominal_disp, sigma_disp, unit,
                 sigma_kind, direction, coeffs, epoch, region):
        self.oid = oid
        self.kind = kind
        self.value_disp = value_disp
        self.nominal_disp = nominal_disp
        self.sigma_disp = sigma_disp
        self.unit = unit
        self.sigma_kind = sigma_kind
        self.direction = direction
        self.coeffs = coeffs
        self.epoch = epoch
        self.region = region


def parse_coeffs(text: str) -> dict[int, Fraction]:
    out: dict[int, Fraction] = {}
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        idx, frac = part.split(":")
        num, den = frac.split("/")
        out[int(idx)] = Fraction(int(num), int(den))
    return out


def untranspose_oid(oid_field: str, epoch: str, transpose_ids: bool) -> str:
    if transpose_ids and str(epoch) == "2":
        return oid_field[len(oid_field) - 3:] + oid_field[: len(oid_field) - 3]
    return oid_field


def to_base_observation(r: RawObs, azimuth_wrap: bool) -> Observation:
    """Invert unit, sigma, sign, azimuth traps and reduce O-C -> Observation.

    The value fed to the normal equations is the misclosure l = observed -
    computed_nominal in base units. Every trap inverse is applied to BOTH the
    observed and nominal display values before differencing.
    """
    kind = r.kind
    unit = r.unit
    value_unit = Fraction(Decimal(r.value_disp))
    nominal_unit = Fraction(Decimal(r.nominal_disp))
    if r.direction == "R":
        value_unit = -value_unit
        nominal_unit = -nominal_unit
    if kind == "length":
        value_base = value_unit * LEN_TO_M[unit]
        nominal_base = nominal_unit * LEN_TO_M[unit]
    else:
        value_base = value_unit * ANG_TO_GON[unit]
        nominal_base = nominal_unit * ANG_TO_GON[unit]
        if azimuth_wrap:
            value_base = azimuth_reduce_gon(value_base)
            nominal_base = azimuth_reduce_gon(nominal_base)
    misclosure = value_base - nominal_base
    if kind == "angle":
        misclosure = misclosure % 400
        if misclosure > 200:
            misclosure -= 400
    variance_base = sigma_to_variance_base(r.sigma_disp, r.sigma_kind, kind, unit)
    return Observation(r.oid, kind, misclosure, variance_base, dict(r.coeffs),
                         epoch=int(r.epoch), region=r.region)


# ---------------------------------------------------------------------------
# per-format readers -> list[RawObs] + shard metadata
# ---------------------------------------------------------------------------
SHARD_FILES = [
    ("obs_source_district_north.csv", ","),
    ("obs_source_district_south.tsv", "\t"),
    ("obs_source_district_west.psv", "|"),
    ("obs_source_district_east.jsonl", None),
]


def _header_tokens(lines) -> dict:
    """key=value tokens declared in a shard's '#' header block."""
    meta = {}
    for line in lines:
        for token in line.lstrip("#").split():
            if "=" in token:
                k, v = token.split("=", 1)
                meta.setdefault(k, v)
    return meta


def _flag(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


def read_delimited(path: Path, delimiter: str) -> tuple[list[RawObs], bool, int]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    meta = _header_tokens(ln for ln in lines if ln.startswith("#"))
    transpose = _flag(meta.get("transpose_ids"))
    wrap = _flag(meta.get("azimuth_wrap"))
    body = "\n".join(ln for ln in lines if not ln.startswith("#"))
    raws = []
    for row in csv.DictReader(io.StringIO(body), delimiter=delimiter):
        oid = untranspose_oid(row["obs_id"], row["epoch"], transpose)
        raws.append(RawObs(oid, row["kind"], row["observed_value"],
                           row["computed_nominal"], row["apriori_sigma"],
                           row["unit"], row["sigma_kind"], row["dir"],
                           parse_coeffs(row["partials"]), row["epoch"],
                           row["region"]))
    return raws, wrap, int(meta["revision"])


def read_jsonl(path: Path) -> tuple[list[RawObs], bool, int]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    meta = json.loads(lines[0])
    transpose = _flag(meta.get("transpose_ids"))
    wrap = _flag(meta.get("azimuth_wrap"))
    raws = []
    for ln in lines[1:]:
        o = json.loads(ln)
        oid = untranspose_oid(o["id"], o["e"], transpose)
        raws.append(RawObs(oid, o["k"], o["v"], o["c"], o["s"], o["u"], o["sk"],
                           o["d"], parse_coeffs(o["A"]), o["e"], o["reg"]))
    return raws, wrap, int(meta["revision"])


def read_station_mounts(data_dir: Path) -> dict:
    """station ordinal -> centring variance (m^2) from active tripod rows."""
    text = (Path(data_dir) / "station_registry.csv").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    out = {}
    for row in csv.DictReader(io.StringIO(body)):
        if row["mark_status"] != "active":
            continue
        ordi = int(row["ordinal"])
        if ordi in out:
            continue
        if row["mount"] == "tripod":
            c = Fraction(Decimal(row["centring_mm"])) / 1000
            out[ordi] = c * c
        else:
            out[ordi] = Fraction(0)
    return out


def read_source_shards(data_dir: Path):
    """Returns (observations sorted by obs_id, superseded record list)."""
    best = {}
    seen = {}
    for fname, delim in SHARD_FILES:
        path = Path(data_dir) / fname
        raws, wrap, rev = (read_jsonl(path) if delim is None
                           else read_delimited(path, delim))
        for r in raws:
            seen.setdefault(r.oid, []).append((rev, fname))
            cur = best.get(r.oid)
            if cur is None or rev > cur[0]:
                best[r.oid] = (rev, fname, r, wrap)
    centring = read_station_mounts(data_dir)
    all_obs = []
    superseded = []
    for oid in sorted(best):
        rev, fname, r, wrap = best[oid]
        o = to_base_observation(r, wrap)
        if o.kind == "length":
            for st in sorted({idx // 2 for idx, c in o.coeffs.items() if c != 0}):
                o.variance_base += centring[st]
        all_obs.append(o)
        for other_rev, other_f in seen[oid]:
            if other_f != fname:
                superseded.append({"obs_id": oid, "kept_shard": fname,
                                   "superseded_shard": other_f})
    superseded.sort(key=lambda d: (d["obs_id"], d["superseded_shard"]))
    return all_obs, superseded


def read_iteration_policy(data_dir: Path) -> tuple[int, int]:
    iters = places = None
    for line in (Path(data_dir) / "iteration_policy.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith("irls_iterations:"):
            iters = int(line.split(":", 1)[1])
        elif line.startswith("weight_quant_decimal_places:"):
            places = int(line.split(":", 1)[1])
    if iters is None or places is None:
        raise ValueError("iteration_policy.yaml incomplete")
    return iters, places


# ---------------------------------------------------------------------------
# Load-bearing values that live ONLY in the XLSX control workbook.
# A stdlib reader (zipfile + regex over inline strings) extracts them.
# ---------------------------------------------------------------------------


def _xlsx_cells(data_dir: Path, fname: str) -> list[str]:
    raw = (data_dir / fname).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        text = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    return _re.findall(r"<t[^>]*>(.*?)</t>", text)


def read_control_values(data_dir: Path) -> dict:
    """Extract the four control values from the xlsx (found only there):
    u_constrained, tuning_k, blunder_crit and datum_origin_station."""
    cells = _xlsx_cells(data_dir, "adjustment_control_workbook.xlsx")
    u = k = blunder_crit = origin = None
    for i, c in enumerate(cells):
        if c == "u_constrained" and i + 1 < len(cells):
            u = int(cells[i + 1])
        if c == "tuning_k" and i + 1 < len(cells):
            k = Fraction(Decimal(cells[i + 1]))
        if c == "blunder_crit" and i + 1 < len(cells):
            blunder_crit = Fraction(Decimal(cells[i + 1]))
        if c == "datum_origin_station" and i + 1 < len(cells):
            origin = int(cells[i + 1])
    if u is None or k is None or blunder_crit is None or origin is None:
        raise ValueError("control workbook missing a required control value")
    return {"u": u, "k": k, "k2": k * k,
            "blunder_crit": blunder_crit, "blunder_crit2": blunder_crit * blunder_crit,
            "datum_origin_station": origin}


def read_chi_bounds(data_dir: Path, dof: int) -> tuple[Fraction, Fraction]:
    """Read the exact acceptance interval for a given dof from the table."""
    text = (data_dir / "chi_square_bounds_table.csv").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    for row in csv.DictReader(io.StringIO(body)):
        if int(row["dof"]) == dof:
            center = Fraction(int(row["center_num"]), int(row["center_den"]))
            return center - Fraction(1, 2), center + Fraction(1, 2)
    raise KeyError(f"dof {dof} not in chi_square_bounds_table")


def read_sessions(data_dir: Path) -> list[tuple[str, str, Fraction]]:
    """Read the correlated sessions: each authoritative row names its two member
    obs_ids and the exact rational covariance. Decoy rows are ignored."""
    text = (data_dir / "session_correlation.csv").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    out = []
    for row in csv.DictReader(io.StringIO(body)):
        if row["status"] != "authoritative":
            continue
        cov = Fraction(int(row["cov_num"]), int(row["cov_den"]))
        out.append((row["member_a_obs_id"], row["member_b_obs_id"], cov))
    return out


def build_pairs(obs: list, sessions) -> dict:
    """Map obs index to (other index, cov) for members present in the list."""
    by_id = {o.obs_id: idx for idx, o in enumerate(obs)}
    pairs = {}
    for a, b, cov in sessions:
        if a in by_id and b in by_id:
            ia, ib = by_id[a], by_id[b]
            pairs[ia] = (ib, cov)
            pairs[ib] = (ia, cov)
    return pairs


def read_frames(data_dir: Path) -> tuple[dict, dict]:
    """Read station->frame and epoch->campaign maps used to reconstruct the
    derived rollup grouping key (frame, campaign). Restatement rows are
    idempotent; the first occurrence per key is authoritative."""
    sf = {}
    text = (data_dir / "station_frame_map.csv").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    for row in csv.DictReader(io.StringIO(body)):
        sf.setdefault(row["station"], row["frame"])
    ec = {}
    text = (data_dir / "epoch_campaign_map.csv").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in text.splitlines() if not ln.startswith("#"))
    for row in csv.DictReader(io.StringIO(body)):
        ec.setdefault(int(row["epoch"]), row["campaign"])
    return sf, ec


def rollup_key(o, station_frame: dict, epoch_campaign: dict) -> tuple[str, str]:
    """Derived grouping key for an observation: the frame of its PRIMARY station
    (the lowest-indexed station among its unknowns) joined with the campaign of
    its epoch. The observation's region and epoch fields are decoys and are not
    used as the grouping key."""
    primary_station = min(o.coeffs) // 2
    frame = station_frame[STATIONS[primary_station]]
    campaign = epoch_campaign[o.epoch]
    return frame, campaign

# ===== from snlsq_solver.py =====



REGIONS = ("North", "South", "West", "East")
STATIONS = ("ALPHA", "BRAVO", "CIVET", "DELTA", "EAGLE", "FICUS")


def solve(data_dir: Path) -> dict:
    """Reference two-stage adjustment (schema sections 10-14)."""
    obs_all, superseded = read_source_shards(data_dir)
    control = read_control_values(data_dir)
    sessions = read_sessions(data_dir)
    iters, places = read_iteration_policy(data_dir)
    u = control["u"]
    k2 = control["k2"]
    crit2 = control["blunder_crit2"]
    origin = control["datum_origin_station"]

    stage1 = adjust(obs_all, N_UNKNOWNS, k2, build_pairs(obs_all, sessions), iters, places)
    kept, removed_ids = [], []
    for o, vi in zip(obs_all, stage1["residuals"]):
        if vi * vi * quantize_weight(o.weight(), places) > crit2:
            removed_ids.append(o.obs_id)
        else:
            kept.append(o)
    removed_ids.sort()

    res = adjust(kept, N_UNKNOWNS, k2, build_pairs(kept, sessions), iters, places)
    x = list(res["x"])
    ox, oy = x[2 * origin], x[2 * origin + 1]
    x_shifted = []
    for st in range(N_UNKNOWNS // 2):
        x_shifted.append(x[2 * st] - ox)
        x_shifted.append(x[2 * st + 1] - oy)

    n_obs = len(kept)
    dof = n_obs - u
    s0 = sigma0_squared(res["vtpv"], n_obs, u)
    lo, hi = read_chi_bounds(data_dir, dof)
    verdict = chi_square_gate(res["vtpv"], dof, lo, hi)
    return {
        "obs": kept, "x": x_shifted, "x_free": x,
        "residuals": res["residuals"], "flags": res["flags"],
        "weights_final": res["weights_final"], "trace": res["trace"],
        "vtpv": res["vtpv"], "sigma0_sq": s0, "dof": dof, "n_obs": n_obs,
        "u": u, "k": control["k"], "blunder_crit": control["blunder_crit"],
        "datum_origin_station": origin, "removed_ids": removed_ids,
        "verdict": verdict, "accept_lo": lo, "accept_hi": hi,
        "superseded": superseded,
    }


# ===========================================================================
# Channel A verifier. The delivered program is run on three regenerated
# extracts that the agent never sees, and every downstream document it writes
# is compared with an independent derivation of the same extract. One check
# reads the shipped run in /app/out. Stdlib only; /app/data is never read.
# ===========================================================================
import ast as _ast
import subprocess as _subprocess
import tempfile as _tempfile

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
ARTIFACT_NAMES = [
    "adjusted_state.json", "model_test.json", "downweighted_observations.json",
    "residual_summary.json", "unknowns.csv", "residuals.csv", "residuals.tsv",
    "final_weights.psv", "district_North.json", "district_South.json",
    "district_West.json", "district_East.json", "epoch_1.json", "epoch_2.json",
    "epoch_3.json", "adjustment_report.xml", "adjustment_summary.yaml",
    "adjustment_report.md", "observation_stream.jsonl", "observation_stream.ndjson",
    "normal_matrix_trace.json", "provenance_summary.json", "status.txt",
    "removed_blunders.json", "datum_transformation.json",
] + [f"rollup_Frame{f}_Campaign{c}.json" for f in "ABC" for c in (1, 2)]

LABELS = [f"{STATIONS[i // 2]}.{'x' if i % 2 == 0 else 'y'}" for i in range(N_UNKNOWNS)]

HIDDEN_SEEDS = {"challenge": CHALLENGE_SEED, "eval": EVAL_SEED, "audit": AUDIT_SEED}
DOCUMENTED_DECOY_FILES = {
    "deprecated_precorrection_coords.csv", "stale_cached_solution.json",
    "legacy_orientation_offsets.tsv", "residual_prior_epoch.tsv",
    "observation_weight_manifest.csv", "scale_factor_table.csv",
    "archive_backfill.db", "iteration_policy.yaml", "reference_unit_registry.csv",
    "session_correlation.csv", "azimuth_reference_table.tsv", "epoch_calendar.csv",
    "network_topology.xml", "instrument_calibration_log.csv", "station_registry.csv",
    "observation_provenance.psv",
}

_HIDDEN_CACHE: dict = {}
_REFERENCE_CACHE: dict = {}
_RUN_LOCK_PATH = "/tmp/snlsq-grader-run.lock"


def _build_corpus(seed: int) -> Path:
    root = Path(_tempfile.mkdtemp(prefix=f"snlsq-corpus-{seed}-"))
    emit_corpus(root, seed)
    return root


def _shipped_reference() -> dict:
    """Reference for the shipped extract, regenerated from SAMPLE_SEED (the
    generator reproduces the shipped files byte for byte)."""
    if "ref" not in _REFERENCE_CACHE:
        _REFERENCE_CACHE["ref"] = solve(_build_corpus(SAMPLE_SEED))
    return _REFERENCE_CACHE["ref"]


def _grant_read(src: Path) -> Path:
    """Stage a readable copy of the delivered program for the unprivileged run.

    The verifier runs as root, so it can read the program whatever its mode
    (0600 included) and whatever the mode of /app/out. The copy lives in a
    fresh grader directory: directory 0755, file 0644."""
    import os as _os
    import shutil as _shutil
    stage = Path(_tempfile.mkdtemp(prefix="snlsq-prog-"))
    _os.chmod(stage, 0o755)
    dst = stage / "derive_report.py"
    _shutil.copyfile(src, dst)
    _os.chmod(dst, 0o644)
    return dst


def _kill_uid_leftovers(uid: int) -> None:
    """Kill any process still running as the grading uid. Only called while
    the run lock is held, so no other grading run can own such a process."""
    import os as _os
    import signal as _signal
    for entry in _os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/status", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("Uid:"):
                        if int(line.split()[1]) == uid:
                            _os.kill(int(entry), _signal.SIGKILL)
                        break
        except (OSError, ValueError):
            continue


def _run_agent_program(data_dir: Path, out_dir: Path) -> int:
    """Run the delivered program on a regenerated extract as `nobody`, in its
    own session, with a 120 s limit. Runs are serialised by a file lock; the
    run's process group and any process left under that uid are killed
    before the lock is released. Returns the exit status (-9 on timeout)."""
    import fcntl as _fcntl
    import grp as _grp
    import os as _os
    import pwd as _pwd
    import signal as _signal
    uid = _pwd.getpwnam("nobody").pw_uid
    gid = _grp.getgrnam("nogroup").gr_gid
    for dirpath, _dirs, files in _os.walk(data_dir):
        _os.chmod(dirpath, 0o755)
        for f in files:
            _os.chmod(_os.path.join(dirpath, f), 0o644)
    out_dir.mkdir(parents=True, exist_ok=True)
    _os.chmod(out_dir.parent, 0o755)
    _os.chown(out_dir, uid, gid)
    _os.chmod(out_dir, 0o755)
    prog = _grant_read(SCRIPT)
    cmd = ["/usr/bin/setpriv", f"--reuid={uid}", f"--regid={gid}", "--clear-groups",
           "--", sys.executable, str(prog), str(data_dir), str(out_dir)]
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"}
    with open(_RUN_LOCK_PATH, "w", encoding="utf-8") as lock:
        _fcntl.flock(lock, _fcntl.LOCK_EX)
        try:
            proc = _subprocess.Popen(cmd, start_new_session=True, env=env, cwd="/tmp")
            try:
                code = proc.wait(timeout=120)
            except _subprocess.TimeoutExpired:
                code = -9
            finally:
                try:
                    _os.killpg(proc.pid, _signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                proc.wait()
            _kill_uid_leftovers(uid)
        finally:
            _fcntl.flock(lock, _fcntl.LOCK_UN)
    return code


def _hidden(name: str) -> dict:
    """Regenerate one hidden extract, run the delivered program on it once and
    derive the reference. Cached per extract."""
    if name not in _HIDDEN_CACHE:
        seed = HIDDEN_SEEDS[name]
        root = _build_corpus(seed)
        out = Path(_tempfile.mkdtemp(prefix=f"snlsq-run-{name}-")) / "out"
        code = _run_agent_program(root, out) if SCRIPT.is_file() else None
        _HIDDEN_CACHE[name] = {"root": root, "out": out, "code": code,
                               "ref": solve(root)}
    return _HIDDEN_CACHE[name]


def _ran_cleanly(name: str) -> bool:
    return _hidden(name)["code"] == 0


def _jload(out: Path, name: str):
    text = (out / name).read_text(encoding="utf-8")
    return json.loads(text)


def _rows(out: Path, name: str, delimiter: str = ","):
    text = (out / name).read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def _jsonl(out: Path, name: str):
    return [json.loads(ln) for ln in (out / name).read_text(encoding="utf-8").splitlines() if ln]


def _ref_flags(ref: dict) -> dict:
    return {o.obs_id: f for o, f in zip(ref["obs"], ref["flags"])}


def _ref_downweighted(ref: dict) -> list:
    return sorted(o.obs_id for o, f in zip(ref["obs"], ref["flags"]) if f)


def _ref_micro_unknowns(ref: dict, key: str = "x") -> dict:
    return {lab: frac_to_int_micro(ref[key][i]) for i, lab in enumerate(LABELS)}


# ---- chain documents, one family per hidden extract ----------------------

def _check_model_test(name: str) -> None:
    h = _hidden(name)
    ref, out = h["ref"], h["out"]
    assert h["code"] == 0, f"program exit status {h['code']}"
    got = _jload(out, "model_test.json")
    adj = _jload(out, "adjusted_state.json")
    vtpv = frac_to_str(ref["vtpv"], 10)
    assert got["quadratic_form_vtpv"] == vtpv and adj["quadratic_form_vtpv"] == vtpv
    assert adj["variance_of_unit_weight"] == frac_to_str(ref["sigma0_sq"], 10)
    assert got["degrees_of_freedom"] == ref["dof"] and adj["degrees_of_freedom"] == ref["dof"]
    assert adj["n_observations"] == ref["n_obs"]
    assert got["acceptance_low"] == frac_to_str(ref["accept_lo"], 6)
    assert got["acceptance_high"] == frac_to_str(ref["accept_hi"], 6)
    assert got["verdict"] == ref["verdict"] and adj["model_test_verdict"] == ref["verdict"]
    assert got["passed"] is (ref["verdict"] == "PASS")


def _check_unknowns(name: str) -> None:
    h = _hidden(name)
    ref, out = h["ref"], h["out"]
    assert h["code"] == 0, f"program exit status {h['code']}"
    want_um = _ref_micro_unknowns(ref)
    want_m = {lab: frac_to_str(ref["x"][i], 10) for i, lab in enumerate(LABELS)}
    adj = _jload(out, "adjusted_state.json")
    assert adj["unknowns_micrometres"] == want_um
    assert all(type(v) is int for v in adj["unknowns_micrometres"].values())
    assert adj["unknowns"] == want_m
    rows = _rows(out, "unknowns.csv")
    assert [(int(r["unknown_index"]), r["label"], r["correction_metres"],
             int(r["correction_micrometres"])) for r in rows] == [
        (i, lab, want_m[lab], want_um[lab]) for i, lab in enumerate(LABELS)]
    dt = _jload(out, "datum_transformation.json")
    assert dt["shifted_corrections_micrometres"] == want_um
    assert dt["free_corrections_micrometres"] == _ref_micro_unknowns(ref, "x_free")
    import xml.etree.ElementTree as _ET
    root = _ET.parse(out / "adjustment_report.xml").getroot()
    assert {u.get("label"): int(u.get("correction_micrometres"))
            for u in root.iter("unknown")} == want_um


def _check_residuals(name: str) -> None:
    h = _hidden(name)
    ref, out = h["ref"], h["out"]
    assert h["code"] == 0, f"program exit status {h['code']}"
    want = {o.obs_id: frac_to_int_micro(v) for o, v in zip(ref["obs"], ref["residuals"])}
    kinds = {o.obs_id: o.kind for o in ref["obs"]}
    rows = _rows(out, "residuals.csv")
    assert len(rows) == len(want)
    assert {r["obs_id"]: int(r["residual_micrometres"]) for r in rows} == want
    assert all(r["kind"] == kinds[r["obs_id"]] for r in rows)
    lines = (out / "residuals.tsv").read_text(encoding="utf-8").splitlines()
    tsv = [ln.split("\t") for ln in lines[1:] if ln]
    assert len(tsv) == len(want) and {a: int(b) for a, b in tsv} == want
    jl = _jsonl(out, "observation_stream.jsonl")
    assert len(jl) == len(want)
    assert {d["obs_id"]: d["residual_micrometres"] for d in jl} == want
    assert all(d["kind"] == kinds[d["obs_id"]] for d in jl)
    nd = _jsonl(out, "observation_stream.ndjson")
    assert len(nd) == len(want) and {d["id"]: d["r"] for d in nd} == want
    res = list(zip(ref["obs"], ref["residuals"]))
    top = max(abs(v) for _, v in res)
    got = _jload(out, "residual_summary.json")
    assert got == {
        "n": len(res),
        "sum_signed_micrometres": frac_to_int_micro(sum(v for _, v in res)),
        "max_abs_residual_micrometres": frac_to_int_micro(top),
        "max_abs_residual_obs_id": min(o.obs_id for o, v in res if abs(v) == top),
    }


def _check_sets(name: str) -> None:
    h = _hidden(name)
    ref, out = h["ref"], h["out"]
    assert h["code"] == 0, f"program exit status {h['code']}"
    rb = _jload(out, "removed_blunders.json")
    assert rb["obs_ids"] == ref["removed_ids"] and rb["count"] == len(ref["removed_ids"])
    adj = _jload(out, "adjusted_state.json")
    assert adj["blunders_removed"] == len(ref["removed_ids"])
    want_dw = _ref_downweighted(ref)
    dw = _jload(out, "downweighted_observations.json")
    assert dw["obs_ids"] == want_dw and dw["count"] == len(want_dw)
    flags = _ref_flags(ref)
    rows = _rows(out, "residuals.csv")
    assert {r["obs_id"] for r in rows} == set(flags)
    assert all(r["downweighted"] == ("1" if flags[r["obs_id"]] else "0") for r in rows)
    assert all(d["downweighted"] is flags[d["obs_id"]]
               for d in _jsonl(out, "observation_stream.jsonl"))
    want_w = {o.obs_id: (w.numerator, w.denominator)
              for o, w in zip(ref["obs"], ref["weights_final"])}
    wr = _rows(out, "final_weights.psv", "|")
    assert len(wr) == len(want_w)
    assert {r["obs_id"]: (int(r["weight_num"]), int(r["weight_den"])) for r in wr} == want_w


def _check_rollups(name: str) -> None:
    h = _hidden(name)
    ref, out, root = h["ref"], h["out"], h["root"]
    assert h["code"] == 0, f"program exit status {h['code']}"
    triples = list(zip(ref["obs"], ref["residuals"], ref["flags"]))
    for reg in ("North", "South", "West", "East"):
        rr = [(v, f) for o, v, f in triples if o.region == reg]
        got = _jload(out, f"district_{reg}.json")
        assert got == {"district": reg, "observation_count": len(rr),
                       "downweighted_count": sum(1 for _, f in rr if f),
                       "sum_abs_residual_micrometres": frac_to_int_micro(
                           sum(abs(v) for v, _ in rr))}, reg
    for ep in (1, 2, 3):
        rr = [v for o, v, _ in triples if o.epoch == ep]
        got = _jload(out, f"epoch_{ep}.json")
        assert got == {"epoch": ep, "observation_count": len(rr),
                       "sum_abs_residual_micrometres": frac_to_int_micro(
                           sum(abs(v) for v in rr))}, ep
    station_frame, epoch_campaign = read_frames(root)
    groups: dict = {(f"Frame{f}", f"Campaign{c}"): [] for f in "ABC" for c in (1, 2)}
    for o, v, f in triples:
        groups[rollup_key(o, station_frame, epoch_campaign)].append((v, f))
    for (frame, campaign), rr in groups.items():
        got = _jload(out, f"rollup_{frame}_{campaign}.json")
        assert got == {"frame": frame, "campaign": campaign,
                       "observation_count": len(rr),
                       "downweighted_count": sum(1 for _, f in rr if f),
                       "sum_abs_residual_micrometres": frac_to_int_micro(
                           sum(abs(v) for v, _ in rr))}, (frame, campaign)


def _check_reports(name: str) -> None:
    h = _hidden(name)
    ref, out = h["ref"], h["out"]
    assert h["code"] == 0, f"program exit status {h['code']}"
    verdict, dof = ref["verdict"], ref["dof"]
    s0 = frac_to_str(ref["sigma0_sq"], 10)
    k = frac_to_str(ref["k"], 6)
    n_dw = len(_ref_downweighted(ref))
    status = (out / "status.txt").read_text(encoding="utf-8").strip()
    assert status == (
        f"verdict={verdict} dof={dof} u={ref['u']} n={ref['n_obs']} "
        f"blunders_removed={len(ref['removed_ids'])} "
        f"datum_origin={STATIONS[ref['datum_origin_station']]} "
        f"sigma0_sq={s0} downweighted={n_dw}")
    yml = {}
    for ln in (out / "adjustment_summary.yaml").read_text(encoding="utf-8").splitlines():
        if ":" in ln:
            key, val = ln.split(":", 1)
            yml[key.strip()] = val.strip().strip("'\"")
    assert yml.get("model_test_verdict") == verdict
    assert yml.get("degrees_of_freedom") == str(dof)
    assert yml.get("u_constrained") == str(ref["u"])
    assert yml.get("variance_of_unit_weight") == s0
    assert yml.get("downweighted_count") == str(n_dw)
    assert yml.get("tuning_constant_k") == k
    md = (out / "adjustment_report.md").read_text(encoding="utf-8")
    for token in (verdict, str(dof), s0, str(n_dw), k):
        assert token in md, token
    import xml.etree.ElementTree as _ET
    root = _ET.parse(out / "adjustment_report.xml").getroot()
    assert root.tag == "adjustment"
    assert (root.findtext("verdict") or "").strip() == verdict
    assert (root.findtext("degrees_of_freedom") or "").strip() == str(dof)
    assert (root.findtext("u_constrained") or "").strip() == str(ref["u"])
    assert (root.findtext("variance_of_unit_weight") or "").strip() == s0
    trace = ref["trace"]
    got = _jload(out, "normal_matrix_trace.json")
    assert (got["trace_num"], got["trace_den"]) == (trace.numerator, trace.denominator)
    assert got["trace_decimal"] == frac_to_str(trace, 6)


# ---- checks of a single rule, across the hidden extracts -----------------

def _check_control_values() -> None:
    for name in HIDDEN_SEEDS:
        h = _hidden(name)
        ref, out = h["ref"], h["out"]
        assert h["code"] == 0, f"{name}: program exit status {h['code']}"
        k = frac_to_str(ref["k"], 6)
        crit = frac_to_str(ref["blunder_crit"], 6)
        origin = ref["datum_origin_station"]
        adj = _jload(out, "adjusted_state.json")
        assert adj["u_constrained"] == ref["u"]
        assert adj["tuning_constant_k"] == k
        assert adj["blunder_critical_value"] == crit
        assert adj["datum_origin_station"] == STATIONS[origin]
        assert _jload(out, "removed_blunders.json")["critical_value"] == crit
        dt = _jload(out, "datum_transformation.json")
        assert dt["origin_station"] == STATIONS[origin]
        assert dt["origin_station_index"] == origin
        prov = _jload(out, "provenance_summary.json")
        assert prov["control_values_source"] == "adjustment_control_workbook.xlsx"
        assert prov["u_constrained"] == ref["u"] and prov["tuning_constant_k"] == k
        assert prov["blunder_critical_value"] == crit
        assert prov["datum_origin_station"] == STATIONS[origin]
        decoys = prov["decoys_ignored"]
        assert isinstance(decoys, list) and len(decoys) >= 3
        for d in decoys:
            fname = str(d).split(":", 1)[0]
            assert fname in DOCUMENTED_DECOY_FILES and (h["root"] / fname).is_file(), d


def _check_superseded_records() -> None:
    for name in HIDDEN_SEEDS:
        h = _hidden(name)
        assert h["code"] == 0, f"{name}: program exit status {h['code']}"
        got = _jload(h["out"], "provenance_summary.json")["superseded_records"]
        assert got == h["ref"]["superseded"], name


def _keys_sorted(obj) -> bool:
    if isinstance(obj, dict):
        return list(obj) == sorted(obj) and all(_keys_sorted(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_keys_sorted(v) for v in obj)
    return True


def _check_canonical_serialization() -> None:
    for name in HIDDEN_SEEDS:
        h = _hidden(name)
        out = h["out"]
        assert h["code"] == 0, f"{name}: program exit status {h['code']}"
        for art in ARTIFACT_NAMES:
            if art.endswith(".json"):
                text = (out / art).read_text(encoding="utf-8")
                assert text.endswith("\n"), art
                assert _keys_sorted(json.loads(text)), art
        for art in ("observation_stream.jsonl", "observation_stream.ndjson"):
            for ln in (out / art).read_text(encoding="utf-8").splitlines():
                if ln:
                    assert _keys_sorted(json.loads(ln)), art


# ---- named tests ----------------------------------------------------------

def test_artifact_set_exists_and_parses():
    """POSITIVE (shipped run): the program and every declared artifact exist in
    /app/out and every JSON artifact parses to an object."""
    assert SCRIPT.is_file(), "missing /app/out/derive_report.py"
    for name in ARTIFACT_NAMES:
        assert (OUT / name).is_file(), f"missing /app/out/{name}"
        if name.endswith(".json"):
            assert isinstance(_jload(OUT, name), dict), name


def test_challenge_model_test_document():
    """POSITIVE (hidden extract 1): model_test.json and the stage-2 figures of
    adjusted_state.json (n, dof, vTPv, variance of unit weight, verdict)."""
    _check_model_test("challenge")


def test_challenge_unknowns_documents():
    """POSITIVE (hidden extract 1): shifted and free unknowns in
    adjusted_state.json, unknowns.csv, datum_transformation.json and the XML."""
    _check_unknowns("challenge")


def test_challenge_residual_documents():
    """POSITIVE (hidden extract 1): every residual row in the four residual
    files and residual_summary.json."""
    _check_residuals("challenge")


def test_challenge_observation_sets():
    """POSITIVE (hidden extract 1): removed blunders, downweighted set and
    flags, and every final weight."""
    _check_sets("challenge")


def test_challenge_rollup_documents():
    """POSITIVE (hidden extract 1): district, epoch and frame-campaign rollups."""
    _check_rollups("challenge")


def test_challenge_summary_reports():
    """POSITIVE (hidden extract 1): status.txt, YAML, Markdown and XML summaries
    and the normal matrix trace, against the derived figures."""
    _check_reports("challenge")


def test_eval_model_test_document():
    """POSITIVE (hidden extract 2): model_test.json and the stage-2 figures."""
    _check_model_test("eval")


def test_eval_unknowns_documents():
    """POSITIVE (hidden extract 2): shifted and free unknowns in every file."""
    _check_unknowns("eval")


def test_eval_residual_documents():
    """POSITIVE (hidden extract 2): residual files and residual_summary.json."""
    _check_residuals("eval")


def test_eval_observation_sets():
    """POSITIVE (hidden extract 2): removed, downweighted and final weights."""
    _check_sets("eval")


def test_eval_rollup_documents():
    """POSITIVE (hidden extract 2): district, epoch and frame-campaign rollups."""
    _check_rollups("eval")


def test_eval_summary_reports():
    """POSITIVE (hidden extract 2): summaries and the normal matrix trace."""
    _check_reports("eval")


def test_audit_model_test_document():
    """POSITIVE (hidden extract 3): model_test.json and the stage-2 figures."""
    _check_model_test("audit")


def test_audit_unknowns_documents():
    """POSITIVE (hidden extract 3): shifted and free unknowns in every file."""
    _check_unknowns("audit")


def test_audit_residual_documents():
    """POSITIVE (hidden extract 3): residual files and residual_summary.json."""
    _check_residuals("audit")


def test_audit_observation_sets():
    """POSITIVE (hidden extract 3): removed, downweighted and final weights."""
    _check_sets("audit")


def test_audit_rollup_documents():
    """POSITIVE (hidden extract 3): district, epoch and frame-campaign rollups."""
    _check_rollups("audit")


def test_audit_summary_reports():
    """POSITIVE (hidden extract 3): summaries and the normal matrix trace."""
    _check_reports("audit")


def test_control_values_on_hidden_extracts():
    """POSITIVE (isolated): workbook control values, datum origin, control
    source and the decoy list on all three hidden extracts."""
    _check_control_values()


def test_superseded_records_on_hidden_extracts():
    """POSITIVE (isolated): provenance_summary.json superseded_records on all
    three hidden extracts."""
    _check_superseded_records()


def test_canonical_serialization_on_hidden_extracts():
    """POSITIVE (isolated): sorted keys at every level and a trailing newline
    in every JSON artifact written for the hidden extracts."""
    _check_canonical_serialization()


def _program_constants() -> list:
    src = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return []
    doc_ids = set()
    for node in _ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (_ast.Module, _ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef))
                and body and isinstance(body[0], _ast.Expr)
                and isinstance(body[0].value, _ast.Constant)
                and isinstance(body[0].value.value, str)):
            doc_ids.add(id(body[0].value))
    consts = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Constant) and id(node) not in doc_ids:
            v = node.value
            consts.append(repr(v) if isinstance(v, float) else str(v))
    return consts


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: catches a program that embeds the shipped extract's answers."""
    # Inverted polarity: the assertion HOLDS only when the program ran cleanly
    # on a hidden extract AND its literal constants outside docstrings carry at
    # least two exact answer strings of the shipped extract. A program that
    # did not run stands this detector down; an honest program makes it FAIL.
    assert any(_ran_cleanly(n) for n in HIDDEN_SEEDS), "program did not run; detector stands down"
    consts = _program_constants()
    ref = _shipped_reference()
    tokens = [frac_to_str(ref["sigma0_sq"], 10), frac_to_str(ref["vtpv"], 10),
              str(ref["trace"].numerator)] + [frac_to_str(v, 10) for v in ref["x"] if v != 0]
    hits = sum(any(tok in c for c in consts) for tok in tokens)
    assert hits >= 2, "no hardcoded shipped-sample answers detected"


def test_negative_weight_external_dependency():
    """NEGATIVE: catches a third-party numeric-library dependency in the program."""
    # Inverted polarity: the assertion HOLDS only when the program ran cleanly
    # on a hidden extract AND imports numpy, scipy or pandas. A program that did
    # not run stands this detector down; a stdlib program makes it FAIL.
    assert any(_ran_cleanly(n) for n in HIDDEN_SEEDS), "program did not run; detector stands down"
    src = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        tree = None
    found = set()
    if tree is not None:
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                found |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, _ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
    assert {"numpy", "scipy", "pandas"} & found, "no external numeric-library dependency detected"


# The written data contract shipped as /app/data/schema.md; every generated
# extract (shipped and held-out) carries it.
SCHEMA_MD = r'''# SNLSQ Data Contract (authoritative)

This extract describes one district geodetic sensor-network adjustment. This
document is the contract for reading the extract and for the reports derived
from it. All load-bearing arithmetic is exact: the design coefficients are
shipped as exact rationals, so no trigonometry, square root or floating point
is needed for any reported figure.

## 1. The unknowns and the network

The unknowns are per-station coordinate corrections `dx, dy` in metres for the
six stations, in this fixed order: `ALPHA, BRAVO, CIVET, DELTA, EAGLE, FICUS`.
The unknown index of a station's `dx` is `2*ordinal`, of its `dy` is
`2*ordinal+1` (ALPHA ordinal 0 ... FICUS ordinal 5), giving 12 unknown columns.
`station_registry.csv` lists each station's exact nominal coordinates as
`nominal_x_num/den` and `nominal_y_num/den` (the `display_coord_*` columns are
rounded for reading), and the instrument setup of the campaign in `mount` and
`centring_mm`. Rows with `mark_status=abandoned` describe historical monuments
and are not used; the remaining rows of a station agree with each other.

## 2. Observation shards (source of record)

The four files `obs_source_district_north.csv`, `obs_source_district_south.tsv`,
`obs_source_district_west.psv`, `obs_source_district_east.jsonl` are the source
of record for all observations. Each carries, per row: `obs_id`, `kind`
(`length` or `angle`), `observed_value`, `computed_nominal`, `apriori_sigma`,
`unit`, `sigma_kind`, `dir`, `partials`, `epoch`, `region`. The `partials`
column lists the exact rational design-row coefficients as
`index:num/den;index:num/den`. Every other file restates, cross-checks, or
decoys these observations; none of the other files is a source of observation
values.

Each shard's header block declares the conventions that shard uses as
`key=value` tokens: `revision`, `length_unit`, `angle_unit`, `sigma_stored_as`,
`sign_flip_rev`, `azimuth_wrap` and `transpose_ids` (the last three are `true` or
`false`). The JSON-lines shard carries the same keys in the metadata object on
its first line, and abbreviates the row fields as `id` (obs_id), `k` (kind), `v`
(observed_value), `c` (computed_nominal), `s` (apriori_sigma), `u` (unit), `sk`
(sigma_kind), `d` (dir), `A` (partials), `e` (epoch) and `reg` (region). The
conventions vary by shard and between extracts; apply each shard's own
declaration.

An observation can be carried by more than one shard when a district re-issued
it. Records are matched by their true `obs_id` (section 7). The record in the
shard with the higher `revision` is the observation; any other record of that
`obs_id` is superseded, is not counted, and contributes nothing to the solve.

## 3. Units

Convert every `observed_value`, `computed_nominal`, and `apriori_sigma` to base
units before it is used: metre for `length`, gon for `angle`.
`reference_unit_registry.csv` gives the exact rational factor
(`factor_num/factor_den`) that multiplies a shard-unit value to the base unit.
Use only rows with `status=authoritative`; rows with `unit_scope=informational`
are display-only restatements.

## 4. Uncertainty and weight

Each shard declares `sigma_stored_as` = `stddev` or `variance` (also mirrored,
per shard, in `sigma_convention_manifest.json` with a YAML mirror
`sigma_convention_manifest_b.yaml`; if the two disagree the JSON is
authoritative). The base-unit variance of an observation, `variance_base`, is
formed as follows. Convert to base units first, then, if `sigma_kind=stddev`,
square the base-unit sigma; if `sigma_kind=variance`, multiply the stored value
by the square of the unit factor. A length observation is also affected by the
centring of the instrument and target over the marks: for every station with a
non-zero coefficient in its `partials` whose registry row (section 1) has
`mount=tripod`, add `(centring_mm / 1000)^2` square metres to its
`variance_base`. A `pillar` mount adds nothing. The weight is
`1 / variance_base`.

## 5. Sign convention

All differenced observations are `FROM minus TO`. Rows whose `dir` field is `R`
are stored reversed (`sign_flip_rev=true` declares that a shard contains such
rows): negate BOTH `observed_value` and `computed_nominal` for those rows before
any further use. Rows with `dir=F` are already correct.

## 6. Azimuth reduction

Some shards declare `azimuth_wrap=true`: their raw angular values may be
negative or may exceed 400 gon. For those shards, reduce every angular
`observed_value` and `computed_nominal` (after unit conversion and any sign
restoration) modulo 400 gon into the range `[0, 400)`.
`azimuth_reference_table.tsv` restates, per observation, whether reduction
applies; `grad` and `gon` are the same unit.

## 7. Identifier transposition

Some shards declare `transpose_ids=true`: for rows with `epoch=2` the `obs_id` is
stored with its 3-character head and its tail swapped (a 7-character id `OB00262`
appears as `0262OB0`). Restore the true id by moving the last 3 characters to
the front. Shards without this declaration store ids verbatim.

## 8. Misclosure (reduced observation)

The value that enters the adjustment for each observation is the misclosure
`l = observed_value_base - computed_nominal_base`, in base units, after sections
3 and 5-7 have been applied. For an angle the difference is a direction
difference: it is reduced modulo 400 gon into the half-open range
`(-200, 200]` gon.

## 9. Minimal datum and the constrained-component count u

`datum_constraint_spec.json` lists the constrained coordinate components of
the minimal datum by station, axis and unknown index; any component it does not
list is free. The number of constrained components `u` is recorded in the
control workbook `adjustment_control_workbook.xlsx` (sheet `datum`, cell
labelled `u_constrained`). It counts constrained components, not whole
stations. The degrees of freedom are `dof = n_observations - u`.

## 10. Weighted least squares

Form the normal equations `N = A^T P A`, `b = A^T P l`, with `P` the weight
matrix (sections 4, 11 and 11b) and `A` the design rows from the `partials`
column. Assemble observations in ascending `obs_id` order
(`observation_provenance.psv` gives `row_order_key`). Solve `N x = b` exactly by
Gaussian elimination. All arithmetic is exact rational.

## 11. Robust reweighting (IRLS)

`iteration_policy.yaml` documents the policy: run exactly `irls_iterations`
reweighting iterations after the initial solve, and quantize every weight to
`weight_quant_decimal_places` decimal places. Quantizing a weight `p` to `d`
places means taking the exact rational `p`, rounding `p * 10^d` to an integer
with `ROUND_HALF_EVEN`, and dividing by `10^d`. The base a-priori weight of
every observation is the quantized `1/variance_base`, formed once before the
initial solve. The downweight rule is: observation `i` is downweighted iff
`v_i^2 * p_i > k^2`, where `v_i` is the current residual, `p_i` the base
a-priori weight, and `k` the robust tuning constant; a downweighted
observation's weight is the base weight multiplied by `k^2 / (v_i^2 * p_i)`,
quantized. Each iteration starts again from the base weights. The rule applies
only to observations outside an authoritative correlated session (section 11b):
a session member is never tested for downweighting, is never reported as
downweighted, and keeps its quantized block weight through every pass. The
tuning constant `k` is the workbook cell labelled `tuning_k` (sheet `datum`).
Residuals are `v = A x - l`. This is stage 1.

## 11b. Correlated observation sessions (block-diagonal weights)

Some length baselines were observed in correlated 2-member sessions, so the
weight matrix is block-diagonal. `session_correlation.csv` lists, per
authoritative session (`status=authoritative`), the two member observations by
their `obs_id` (`member_a_obs_id`, `member_b_obs_id`) and the exact rational
covariance `cov = cov_num/cov_den` between their misclosures. For each session,
form `C = [[var_a, cov], [cov, var_b]]`, where `var_a` and `var_b` are the
members' `variance_base` (section 4). The session's weight is the exact inverse
`C^{-1}`, placed as a 2x2 block that couples the two members' rows in both `N`
and `b`, including the off-diagonal cross term; a member takes its block weight
instead of a diagonal weight. Quantize each block-inverse entry as in section
11. Rows with `status=decoy` are retired sessions and are ignored; an
observation belongs to at most one authoritative session. A session applies only
while both members are in the network: if one member is removed as a blunder
(section 12), the surviving member takes the ordinary diagonal weight in stage 2
and is subject to the robust downweight rule like any other observation.
`session_orientation_notes.yml` and `session_orientation_notes_b.yml` are
commentary.

## 12. Data-snooping blunder removal and stage-2 re-solve

After the stage-1 robust solve, an observation `i` is a blunder when
`v_i^2 * p_i` exceeds `blunder_crit^2`, where `p_i` is the base a-priori weight
of section 11 (used for session members too) and `blunder_crit` is the workbook
cell labelled `blunder_crit`. Remove every flagged observation and re-solve the
reduced network with the same robust reweighting of section 11. All reported
figures are the stage-2 figures.

## 13. Datum S-transformation

The stage-2 solve is a free-network solution. Transform it to the working datum
whose origin is the station whose index is the workbook cell
`datum_origin_station` (`0` is ALPHA, `5` is FICUS): subtract the origin
station's `dx` and `dy` corrections from the `dx` and `dy` corrections of every
station, so the origin station ends with zero correction in both axes. The
reported adjusted state is the datum-shifted correction vector; the free-network
vector is reported as well.

## 14. Global model test

After the stage-2 solve, compute the quadratic form `vTPv` with the stage-2 final
weights and the variance of unit weight `sigma0^2 = vTPv / (n - u)`, where `n` is
the stage-2 observation count. Take the acceptance interval from the row of
`chi_square_bounds_table.csv` whose `dof` equals `n - u`: `center_num/center_den`
minus and plus 1/2. The verdict is `PASS` if `lo <= vTPv <= hi`, else
`REJECT_LOW` or `REJECT_HIGH`.

## 15. Files that are not sources

- `deprecated_precorrection_coords.csv`: retired coordinate offsets.
- `stale_cached_solution.json`: a prior-epoch cached solve.
- `legacy_orientation_offsets.tsv`: already folded into `computed_nominal`.
- `residual_prior_epoch.tsv`: prior-epoch residual history.
- `observation_weight_manifest.csv` column `naive_weight`: the earlier faulty
  weights.
- `scale_factor_table.csv`: no scale is applied (`scale_applied=none`).
- `archive_backfill.db`: backfill echoes of shard rows.
- Rows anywhere flagged `status=duplicate`, `status=void`, `status=superseded`,
  `status=retired`, `mark_status=abandoned`, `provenance=superseded`, or
  `ledger_status=void` are informational and are not a source of any value.

## 16. Output shape

Every numeric field is the exact rational value rendered deterministically with
`ROUND_HALF_EVEN`: a field with `d` decimals is the exact value rounded half-even
to `d` places. Residuals and coordinate corrections are signed integer
micrometres: the exact value times 10^6, rounded half-even to an integer. Every
sum in a rollup or summary (`sum_abs_residual_micrometres`,
`sum_signed_micrometres`) is taken over the exact residuals and rounded once at
the end. All JSON is serialized with sorted keys and a trailing newline. The
twelve unknown labels are, in order, `ALPHA.x`, `ALPHA.y`, `BRAVO.x`, `BRAVO.y`,
`CIVET.x`, `CIVET.y`, `DELTA.x`, `DELTA.y`, `EAGLE.x`, `EAGLE.y`, `FICUS.x`,
`FICUS.y` (station order from section 1, dx then dy). Residual micrometres are
in the observation's base unit (micrometres for a length, micro-gon for an
angle).

The residual rollups come in three families. The four district rollups key on
the observation `region` field and the three epoch rollups key on the
observation `epoch` field, both taken from the shards. The six derived-key
rollups key on the pair `(frame, campaign)`: `station_frame_map.csv` maps a
station to its `frame` and `epoch_campaign_map.csv` maps an `epoch` to its
`campaign`; each observation belongs to the frame of its primary station (the
lowest station index among its `partials`) and the campaign of its `epoch`. In
both maps the first occurrence per key is authoritative. Write exactly these
artifacts, each with exactly these fields:

- `adjusted_state.json`: `unknowns` (label to correction in metres, a string with
  10 decimals), `unknowns_micrometres` (label to integer micrometres),
  `n_observations` (int, the stage-2 count), `u_constrained` (int),
  `degrees_of_freedom` (int), `variance_of_unit_weight` (string, 10 decimals),
  `quadratic_form_vtpv` (string, 10 decimals), `tuning_constant_k` (string, 6
  decimals), `blunder_critical_value` (string, 6 decimals), `blunders_removed`
  (int), `datum_origin_station` (string, the origin station name),
  `model_test_verdict` (string, one of `PASS`, `REJECT_LOW`, `REJECT_HIGH`). The
  `unknowns` are the datum-shifted corrections.
- `model_test.json`: `degrees_of_freedom` (int), `quadratic_form_vtpv` (string, 10
  decimals), `acceptance_low` (string, 6 decimals), `acceptance_high` (string, 6
  decimals), `verdict` (string), `passed` (boolean, true only when the verdict is
  `PASS`).
- `downweighted_observations.json`: `count` (int) and `obs_ids` (array of obs_id
  strings in ascending order).
- `residual_summary.json`: `n` (int), `sum_signed_micrometres` (int),
  `max_abs_residual_micrometres` (int), `max_abs_residual_obs_id` (string; on an
  exact tie the lowest obs_id).
- `unknowns.csv`: comma-separated, header
  `unknown_index,label,correction_metres,correction_micrometres`, one row per
  unknown index 0 to 11; `correction_metres` has 10 decimals.
- `residuals.csv`: comma-separated, header
  `obs_id,kind,residual_micrometres,downweighted`; `downweighted` is `1` or `0`.
- `residuals.tsv`: tab-separated, header row `obs_id` and `residual_micrometres`
  joined by a tab.
- `final_weights.psv`: pipe-separated, header `obs_id|weight_num|weight_den`, one
  row per stage-2 observation; the weight is its exact integer numerator and
  denominator in lowest terms. For an observation outside any session it is the
  final quantized robust weight; for a session member it is the quantized
  diagonal entry of its session's block `C^{-1}` on that member's own row.
- `district_North.json`, `district_South.json`, `district_West.json`,
  `district_East.json`: `district` (string), `observation_count` (int),
  `downweighted_count` (int), `sum_abs_residual_micrometres` (int).
- `epoch_1.json`, `epoch_2.json`, `epoch_3.json`: `epoch` (int),
  `observation_count` (int), `sum_abs_residual_micrometres` (int).
- `rollup_FrameA_Campaign1.json`, `rollup_FrameA_Campaign2.json`,
  `rollup_FrameB_Campaign1.json`, `rollup_FrameB_Campaign2.json`,
  `rollup_FrameC_Campaign1.json`, `rollup_FrameC_Campaign2.json`: `frame`
  (string), `campaign` (string), `observation_count` (int), `downweighted_count`
  (int), `sum_abs_residual_micrometres` (int).
- `normal_matrix_trace.json`: `trace_num` (int) and `trace_den` (int), the
  exact trace as a fraction in lowest terms, and `trace_decimal` (string, 6
  decimals); the trace of the normal matrix `N` assembled for the last stage-2
  solve, session blocks included.
- `provenance_summary.json`: `control_values_source` (string, exactly the bare
  file name `adjustment_control_workbook.xlsx`), `u_constrained` (int),
  `tuning_constant_k` (string, 6 decimals), `blunder_critical_value` (string, 6
  decimals), `datum_origin_station` (string, origin station name),
  `superseded_records` (array, one object per superseded shard record with
  `obs_id` (the true id), `kept_shard` and `superseded_shard` (shard file
  names), ordered by `obs_id` then `superseded_shard`; empty when there are
  none), and `decoys_ignored` (array of at least three strings naming files or
  columns you did not use as sources; each string is an exact shipped file name,
  or `file_name:column` for a column, and the file must be one of
  `deprecated_precorrection_coords.csv`, `stale_cached_solution.json`,
  `legacy_orientation_offsets.tsv`, `residual_prior_epoch.tsv`,
  `observation_weight_manifest.csv`, `scale_factor_table.csv`,
  `archive_backfill.db`, `iteration_policy.yaml`, `reference_unit_registry.csv`,
  `session_correlation.csv`, `azimuth_reference_table.tsv`, `epoch_calendar.csv`,
  `network_topology.xml`, `instrument_calibration_log.csv`,
  `station_registry.csv` or `observation_provenance.psv`).
- `status.txt`: one line
  `verdict=<verdict> dof=<dof> u=<u> n=<n> blunders_removed=<count> datum_origin=<name> sigma0_sq=<variance> downweighted=<count>`
  where the variance is rendered with 10 decimals.
- `removed_blunders.json`: `count` (int), `obs_ids` (array of obs_id strings in
  ascending order, the stage-1 gross errors removed before stage 2),
  `critical_value` (string, 6 decimals).
- `datum_transformation.json`: `origin_station` (string), `origin_station_index`
  (int), `free_corrections_micrometres` (label to integer micrometres, the
  free-network stage-2 solution), `shifted_corrections_micrometres` (label to
  integer micrometres, after the S-transformation).
- `adjustment_report.xml`: an `<adjustment>` root carrying `<verdict>`,
  `<degrees_of_freedom>`, `<u_constrained>`, `<variance_of_unit_weight>` (10
  decimals), and an `<unknowns>` block with one
  `<unknown label=... correction_micrometres=.../>` per unknown.
- `adjustment_summary.yaml`: keys `model_test_verdict`, `degrees_of_freedom`,
  `u_constrained`, `variance_of_unit_weight` (10 decimals), `downweighted_count`,
  `tuning_constant_k` (6 decimals).
- `adjustment_report.md`: a short human-readable report stating the verdict,
  degrees of freedom (integer), variance of unit weight (10 decimals),
  downweighted count and tuning constant (6 decimals), each figure written
  exactly as it appears in `adjusted_state.json`.
- `observation_stream.jsonl`: one JSON object per line with `obs_id`, `kind`,
  `residual_micrometres` (int) and `downweighted` (boolean).
- `observation_stream.ndjson`: one JSON object per line with `id` (obs_id) and
  `r` (residual micrometres).
- `derive_report.py`: the reusable program itself, runnable as
  `python3 derive_report.py DATA_DIR OUT_DIR`.
'''


def _write_corpus(root: Path) -> None:
    emit_corpus(Path(root), SAMPLE_SEED)


# rewardkit checks. Each one passes when the test function above raises nothing.
# One lock runs the checks one at a time because rewardkit calls checks from
# parallel worker threads.
_GRADE_LOCK = threading.Lock()


def _passes(test) -> bool:
    with _GRADE_LOCK:
        try:
            test()
        except Exception:
            return False
        return True


@criterion(description="the program and every declared artifact exist in /app/out and every JSON artifact parses.")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    return _passes(test_artifact_set_exists_and_parses)


@criterion(description="hidden extract 1: model_test.json and the stage-2 figures of adjusted_state.json match the independent derivation.")
def challenge_model_test_document(workspace: Path) -> bool:
    return _passes(test_challenge_model_test_document)

@criterion(description="hidden extract 1: shifted and free unknowns match in adjusted_state.json, unknowns.csv, datum_transformation.json and adjustment_report.xml.")
def challenge_unknowns_documents(workspace: Path) -> bool:
    return _passes(test_challenge_unknowns_documents)

@criterion(description="hidden extract 1: every residual row in residuals.csv, residuals.tsv, both observation streams and residual_summary.json matches.")
def challenge_residual_documents(workspace: Path) -> bool:
    return _passes(test_challenge_residual_documents)

@criterion(description="hidden extract 1: the removed blunder set, the downweighted set and flags, and every final weight match.")
def challenge_observation_sets(workspace: Path) -> bool:
    return _passes(test_challenge_observation_sets)

@criterion(description="hidden extract 1: the district, epoch and frame-campaign rollups match.")
def challenge_rollup_documents(workspace: Path) -> bool:
    return _passes(test_challenge_rollup_documents)

@criterion(description="hidden extract 1: status.txt, the YAML, Markdown and XML summaries and the normal matrix trace match the derived figures.")
def challenge_summary_reports(workspace: Path) -> bool:
    return _passes(test_challenge_summary_reports)

@criterion(description="hidden extract 2: model_test.json and the stage-2 figures of adjusted_state.json match the independent derivation.")
def eval_model_test_document(workspace: Path) -> bool:
    return _passes(test_eval_model_test_document)

@criterion(description="hidden extract 2: shifted and free unknowns match in adjusted_state.json, unknowns.csv, datum_transformation.json and adjustment_report.xml.")
def eval_unknowns_documents(workspace: Path) -> bool:
    return _passes(test_eval_unknowns_documents)

@criterion(description="hidden extract 2: every residual row in residuals.csv, residuals.tsv, both observation streams and residual_summary.json matches.")
def eval_residual_documents(workspace: Path) -> bool:
    return _passes(test_eval_residual_documents)

@criterion(description="hidden extract 2: the removed blunder set, the downweighted set and flags, and every final weight match.")
def eval_observation_sets(workspace: Path) -> bool:
    return _passes(test_eval_observation_sets)

@criterion(description="hidden extract 2: the district, epoch and frame-campaign rollups match.")
def eval_rollup_documents(workspace: Path) -> bool:
    return _passes(test_eval_rollup_documents)

@criterion(description="hidden extract 2: status.txt, the YAML, Markdown and XML summaries and the normal matrix trace match the derived figures.")
def eval_summary_reports(workspace: Path) -> bool:
    return _passes(test_eval_summary_reports)

@criterion(description="hidden extract 3: model_test.json and the stage-2 figures of adjusted_state.json match the independent derivation.")
def audit_model_test_document(workspace: Path) -> bool:
    return _passes(test_audit_model_test_document)

@criterion(description="hidden extract 3: shifted and free unknowns match in adjusted_state.json, unknowns.csv, datum_transformation.json and adjustment_report.xml.")
def audit_unknowns_documents(workspace: Path) -> bool:
    return _passes(test_audit_unknowns_documents)

@criterion(description="hidden extract 3: every residual row in residuals.csv, residuals.tsv, both observation streams and residual_summary.json matches.")
def audit_residual_documents(workspace: Path) -> bool:
    return _passes(test_audit_residual_documents)

@criterion(description="hidden extract 3: the removed blunder set, the downweighted set and flags, and every final weight match.")
def audit_observation_sets(workspace: Path) -> bool:
    return _passes(test_audit_observation_sets)

@criterion(description="hidden extract 3: the district, epoch and frame-campaign rollups match.")
def audit_rollup_documents(workspace: Path) -> bool:
    return _passes(test_audit_rollup_documents)

@criterion(description="hidden extract 3: status.txt, the YAML, Markdown and XML summaries and the normal matrix trace match the derived figures.")
def audit_summary_reports(workspace: Path) -> bool:
    return _passes(test_audit_summary_reports)

@criterion(description="on all three hidden extracts the workbook control values, the datum origin, the control-value source and the decoy list are reported correctly.")
def control_values_on_hidden_extracts(workspace: Path) -> bool:
    return _passes(test_control_values_on_hidden_extracts)

@criterion(description="on all three hidden extracts provenance_summary.json lists exactly the superseded shard records.")
def superseded_records_on_hidden_extracts(workspace: Path) -> bool:
    return _passes(test_superseded_records_on_hidden_extracts)

@criterion(description="every JSON artifact written for the hidden extracts has sorted keys at every level and a trailing newline.")
def canonical_serialization_on_hidden_extracts(workspace: Path) -> bool:
    return _passes(test_canonical_serialization_on_hidden_extracts)

@criterion(description="catches a program that embeds the shipped extract's answers.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _passes(test_negative_weight_hardcoded_sample_answers)

@criterion(description="catches a third-party numeric-library dependency in the program.")
def negative_external_dependency(workspace: Path) -> bool:
    return _passes(test_negative_weight_external_dependency)


criteria.artifact_set_exists_and_parses(weight=1)
criteria.challenge_model_test_document(weight=3)
criteria.challenge_unknowns_documents(weight=3)
criteria.challenge_residual_documents(weight=3)
criteria.challenge_observation_sets(weight=3)
criteria.challenge_rollup_documents(weight=3)
criteria.challenge_summary_reports(weight=3)
criteria.eval_model_test_document(weight=3)
criteria.eval_unknowns_documents(weight=3)
criteria.eval_residual_documents(weight=3)
criteria.eval_observation_sets(weight=3)
criteria.eval_rollup_documents(weight=3)
criteria.eval_summary_reports(weight=3)
criteria.audit_model_test_document(weight=3)
criteria.audit_unknowns_documents(weight=3)
criteria.audit_residual_documents(weight=3)
criteria.audit_observation_sets(weight=3)
criteria.audit_rollup_documents(weight=3)
criteria.audit_summary_reports(weight=3)
criteria.control_values_on_hidden_extracts(weight=3)
criteria.superseded_records_on_hidden_extracts(weight=3)
criteria.canonical_serialization_on_hidden_extracts(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_external_dependency(weight=-3)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))
