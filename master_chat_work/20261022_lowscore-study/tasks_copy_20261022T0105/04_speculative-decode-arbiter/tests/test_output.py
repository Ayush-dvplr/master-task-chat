"""Verifier for the SDA arbiter replay task.

The graded corpus is rebuilt from EVAL_SEED, which lives only in this file and
never enters the environment build context, so the driver tests grade records
the run has never seen.

Nothing here reads /app/data at grade time. That path belongs to the agent
image and is not propagated into the verifier container.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import zipfile

from rewardkit import criteria, criterion
from pathlib import Path


# ---------------------------------------------------------------------------
# Deterministic RNG (splitmix64). Hand rolled so the corpus is byte identical
# on every CPython version; random.Random is not contractually stable.
# ---------------------------------------------------------------------------

_M64 = 0xFFFFFFFFFFFFFFFF


class Rng:
    def __init__(self, seed: int) -> None:
        self.s = seed & _M64

    def next(self) -> int:
        self.s = (self.s + 0x9E3779B97F4A7C15) & _M64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M64
        return (z ^ (z >> 31)) & _M64

    def below(self, n: int) -> int:
        return self.next() % n

    def between(self, lo: int, hi: int) -> int:
        """Inclusive on both ends."""
        return lo + self.below(hi - lo + 1)

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def chance(self, num: int, den: int) -> bool:
        return self.below(den) < num


# ---------------------------------------------------------------------------
# Fixed vocabulary
# ---------------------------------------------------------------------------

TENANTS = ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "T10"]
SLOTS = [f"S{i:02d}" for i in range(16)]
PRIORITY_CLASSES = ["bulk", "standard", "interactive", "realtime"]
# Rank: higher number preempts lower. Stated in the shipped lease appendix.
PRIORITY_RANK = {"bulk": 1, "standard": 2, "interactive": 3, "realtime": 4}

STATUS_VALUES = ["active", "retired", "superseded"]

# Token identifiers are four characters: TK + two hex nibbles.
TOKEN_POOL = [f"TK{i:02X}" for i in range(256)]

# Terminal token classes for the conservation identity.
TERMINAL_CLASSES = ["accepted", "rejected", "expired", "reclaimed", "voided"]

# Documented malformation repair codes.
REPAIR_CODES = [
    "R01",  # negative k_requested, clamp to 1
    "R02",  # k_requested above cap, clamp to 8
    "R03",  # draft vector longer than k_requested, truncate to k_requested
    "R04",  # verdict vector shorter than draft, pad with the void token
    "R05",  # expiry tick at or before grant tick, void the window
    "R06",  # unknown token id in the draft vector, map to the void class
]

VOID_TOKEN = "TKFF"
VOID_CLASS = "CZZ"


# ---------------------------------------------------------------------------
# Canonical forms (trap 21, trap 26, trap 39)
# ---------------------------------------------------------------------------

def canon_stream(raw: str) -> str:
    """Canonical stream identifier.

    Arrives mixed case with underscores; the canonical form is uppercase with
    a hyphen separator. Documented once in the shipped glossary.
    """
    return raw.strip().upper().replace("_", "-")


def canon_window(stream_id: str, seq: int) -> str:
    """Window identifier: canonical stream, '#', sequence zero padded to 4."""
    return f"{stream_id}#{seq:04d}"


def half_even(value: float, places: int) -> float:
    """Round half to even at the given number of decimal places.

    Applied only at emission, never to an intermediate. Implemented on the
    integer grid so it does not inherit binary floating point surprises.
    """
    scale = 10 ** places
    scaled = value * scale
    floor = int(scaled // 1)
    frac = scaled - floor
    if frac > 0.5:
        out = floor + 1
    elif frac < 0.5:
        out = floor
    else:
        out = floor if floor % 2 == 0 else floor + 1
    return out / scale


def fmt_num(value: float, places: int) -> str:
    """Emit a rounded number with a fixed number of decimal places."""
    return f"{half_even(value, places):.{places}f}"


# ---------------------------------------------------------------------------
# Corpus construction
# ---------------------------------------------------------------------------

class Stream:
    __slots__ = (
        "stream_id", "raw_id", "tenant", "master_tenant", "priority",
        "rank", "k_seed", "admit_open", "admit_close", "status", "label",
        "agree_profile",
    )

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class Window:
    """A recorded window, exactly as the corpus ships it.

    Every field here is raw. No repair is applied at build time, because
    applying the repairs is the solver's work and doing it here would hand
    that work over in the shipped bytes.
    """

    __slots__ = (
        "window_id", "stream_id", "seq", "raw_k", "raw_draft", "raw_verdict",
        "correction", "slot", "grant_tick", "raw_expiry",
    )

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


def build_alias_table(rng: Rng) -> dict:
    """Map every token to an equivalence class.

    Most tokens are their own class. A documented minority collapse onto a
    shared class, so two windows can agree on a token without the ids being
    equal. The table ships in full.
    """
    table = {}
    for tok in TOKEN_POOL:
        table[tok] = "C" + tok[2:] + "0"
    # Collapse a documented set of pairs onto one class.
    for i in range(0, 240, 4):
        a = TOKEN_POOL[i]
        b = TOKEN_POOL[i + 1]
        table[b] = table[a]
    table[VOID_TOKEN] = VOID_CLASS
    return table


def build_streams(rng: Rng, count: int) -> list:
    streams = []
    for i in range(1, count + 1):
        # T10 is in the registry and owns no stream, so the rule that an
        # empty group still emits its row has a fixture.
        tenant = TENANTS[rng.below(len(TENANTS) - 1)]
        priority = PRIORITY_CLASSES[rng.below(len(PRIORITY_CLASSES))]
        canonical = f"SDA-{tenant}-{i:04d}"
        # The raw form arrives lowercase with underscores; roughly a third
        # arrive in mixed case so a naive upper() on the wrong field shows up.
        raw = canonical.replace("-", "_")
        raw = raw.lower() if rng.chance(2, 3) else raw.title()
        # streams-master carries an advisory tenant that disagrees for a
        # documented minority; streams-tenant.tsv is authoritative.
        master_tenant = tenant
        if rng.chance(1, 11):
            master_tenant = TENANTS[(TENANTS.index(tenant) + 1) % len(TENANTS)]
        admit_open = rng.between(0, 40)
        admit_close = admit_open + rng.between(60, 200)
        status = "active"
        roll = rng.below(20)
        if roll == 0:
            status = "retired"
        elif roll == 1:
            status = "superseded"
        # The draft service is well matched to some streams and badly matched
        # to others. The profile only shapes the recorded corpus; it is never
        # an input the solver needs, and it is not shipped.
        profile_roll = rng.below(100)
        if profile_roll < 30:
            agree_profile = "high"
        elif profile_roll < 72:
            agree_profile = "mid"
        else:
            agree_profile = "low"
        streams.append(Stream(
            stream_id=canonical,
            raw_id=raw,
            tenant=tenant,
            master_tenant=master_tenant,
            priority=priority,
            rank=PRIORITY_RANK[priority],
            k_seed=rng.between(1, 8),
            admit_open=admit_open,
            admit_close=admit_close,
            status=status,
            label=f"stream {i:04d} {priority} lane",
            agree_profile=agree_profile,
        ))
    # Section 12 closes both band boundaries from below, so a ratio of exactly
    # 0.85 is high rather than mid. Nothing the generator draws at random lands
    # on that value, so one stream is built to sit on it: five windows drafting
    # four tokens each and agreeing on 17 of the 20, which is 0.85 exactly.
    # Without it the high boundary is stated and never graded.
    streams.append(Stream(
        stream_id=f"SDA-T09-{count + 1:04d}",
        raw_id=f"sda_t09_{count + 1:04d}",
        tenant="T09",
        master_tenant="T09",
        priority="standard",
        rank=PRIORITY_RANK["standard"],
        k_seed=4,
        admit_open=0,
        admit_close=200,
        status="active",
        label=f"stream {count + 1:04d} standard lane",
        agree_profile="boundary",
    ))
    return streams


def build_windows(rng: Rng, streams: list, alias: dict) -> list:
    """Build the recorded speculative windows.

    Malformations are planted at documented rates so every repair code has
    instances in the shipped corpus. Nothing is repaired here.
    """
    windows = []
    for stream in streams:
        if stream.agree_profile == "boundary":
            continue
        n_windows = rng.between(8, 20)
        tick = stream.admit_open
        for seq in range(1, n_windows + 1):
            raw_k = rng.between(1, 8)
            if rng.chance(1, 40):
                raw_k = -rng.between(1, 3)
            elif rng.chance(1, 40):
                raw_k = rng.between(9, 14)
            k_size = 1 if raw_k < 1 else (8 if raw_k > 8 else raw_k)

            draft_len = k_size
            if rng.chance(1, 25):
                draft_len = k_size + rng.between(1, 3)
            draft = [TOKEN_POOL[rng.below(len(TOKEN_POOL) - 1)]
                     for _ in range(draft_len)]

            if rng.chance(1, 30) and draft:
                draft[rng.below(len(draft))] = "TKZZ"

            if stream.agree_profile == "high":
                agree = len(draft) if rng.chance(17, 20) else rng.between(0, len(draft))
            elif stream.agree_profile == "low":
                agree = 0 if rng.chance(3, 5) else rng.between(0, max(1, len(draft) // 3))
            else:
                agree = rng.between(0, len(draft))
            if agree > len(draft):
                agree = len(draft)

            verdict = []
            for idx in range(len(draft)):
                tok = draft[idx]
                if idx < agree:
                    same = [t for t in TOKEN_POOL
                            if alias.get(t) == alias.get(tok) and alias.get(tok) is not None]
                    if len(same) > 1 and rng.chance(1, 2):
                        verdict.append(rng.pick(same))
                    else:
                        verdict.append(tok)
                else:
                    other = TOKEN_POOL[rng.below(len(TOKEN_POOL) - 1)]
                    while alias.get(other) == alias.get(tok):
                        other = TOKEN_POOL[rng.below(len(TOKEN_POOL) - 1)]
                    verdict.append(other)
            if rng.chance(1, 28) and verdict:
                verdict = verdict[: max(0, len(verdict) - rng.between(1, 2))]

            correction = TOKEN_POOL[rng.below(len(TOKEN_POOL) - 1)]
            # S15 is in the registry and is never leased.
            slot = SLOTS[rng.below(len(SLOTS) - 1)]
            grant = tick
            expiry = grant + rng.between(1, 10)
            if rng.chance(1, 45):
                expiry = grant - rng.below(2)

            windows.append(Window(
                window_id=canon_window(stream.stream_id, seq),
                stream_id=stream.stream_id,
                seq=seq,
                raw_k=raw_k,
                raw_draft=draft,
                raw_verdict=verdict,
                correction=correction,
                slot=slot,
                grant_tick=grant,
                raw_expiry=expiry,
            ))
            tick += rng.between(2, 12)

    # The band boundary stream. Four tokens drafted per window at a policy K
    # that never moves, agreeing on every position of the first four windows
    # and on one position of the fifth: 17 agreed of 20 drafted, which is a
    # pooled ratio of exactly 0.85. None of these tokens collide in class, so
    # every agreement and disagreement here is decided by the alias table.
    for stream in streams:
        if stream.agree_profile != "boundary":
            continue
        draft = ["TK10", "TK14", "TK18", "TK1C"]
        tick = 10
        for seq in range(1, 6):
            verdict = list(draft) if seq < 5 else ["TK10", "TK20", "TK20", "TK20"]
            windows.append(Window(
                window_id=canon_window(stream.stream_id, seq),
                stream_id=stream.stream_id,
                seq=seq,
                raw_k=4,
                raw_draft=list(draft),
                raw_verdict=verdict,
                correction="TK10",
                slot="S14",
                grant_tick=tick,
                raw_expiry=tick + 10,
            ))
            tick += 12
    return windows


def build_cancels(rng: Rng, streams: list) -> list:
    """Cancellation events. A stream may be cancelled at most once."""
    cancels = []
    for stream in streams:
        if stream.agree_profile == "boundary":
            continue
        if rng.chance(1, 6):
            tick = stream.admit_open + rng.between(10, 140)
            cancels.append({
                "stream_id": stream.stream_id,
                "tick": tick,
                "origin": rng.pick(["client", "gateway", "supervisor"]),
            })
    return cancels


def build_revokes(rng: Rng, streams: list, windows: list) -> list:
    """Slot revocations. Some are issued by a lower ranked stream, which is
    the documented priority inversion condition.

    A documented minority of windows carry a second revocation, because the
    specification says a window may carry more than one and the shipped lease
    appendix works that case through: only the earliest revocation that takes
    effect moves the expiry, and an ignored one alongside it is still recorded
    as an inversion.
    """
    revokes = []
    by_stream = {s.stream_id: s for s in streams}
    for win in windows:
        if by_stream[win.stream_id].agree_profile == "boundary":
            continue
        if not rng.chance(1, 14):
            continue
        holder = by_stream[win.stream_id]
        challenger = streams[rng.below(len(streams))]
        if challenger.stream_id == holder.stream_id:
            continue
        tick = win.grant_tick + rng.below(max(1, win.raw_expiry - win.grant_tick))
        revokes.append({
            "slot": win.slot,
            "tick": tick,
            "by_stream": challenger.stream_id,
            "holder": win.stream_id,
            "window_id": win.window_id,
        })
        if not rng.chance(1, 3):
            continue
        second = streams[rng.below(len(streams))]
        if second.stream_id == holder.stream_id or second.stream_id == challenger.stream_id:
            continue
        tick2 = win.grant_tick + rng.below(max(1, win.raw_expiry - win.grant_tick))
        revokes.append({
            "slot": win.slot,
            "tick": tick2,
            "by_stream": second.stream_id,
            "holder": win.stream_id,
            "window_id": win.window_id,
        })
    return revokes


def build_cost_table(rng: Rng) -> dict:
    """Deterministic service unit costs. No wall clock anywhere."""
    return {
        "draft_unit": 3,
        "verify_unit": 7,
        "emit_unit": 2,
        "reclaim_unit": 5,
        "expire_unit": 4,
        "void_unit": 11,
        "inversion_unit": 13,
    }


def build_allocations(rng: Rng, streams: list) -> dict:
    """Per stream unit allocation.

    A tenant's cap is the sum of the allocations of the streams that
    streams-tenant.tsv assigns to it, so the cap is itself a join rather than
    a shipped constant.
    """
    return {s.stream_id: rng.between(155, 455) for s in streams}


class Corpus:
    __slots__ = ("streams", "windows", "cancels", "revokes", "alias",
                 "costs", "alloc", "seed")


def build_corpus(seed: int, n_streams: int) -> Corpus:
    """Assemble the whole corpus from one seed. Pure and deterministic."""
    corpus = Corpus()
    corpus.seed = seed
    corpus.alias = build_alias_table(Rng(seed ^ 0x5EED01))
    corpus.streams = build_streams(Rng(seed ^ 0x5EED02), n_streams)
    corpus.windows = build_windows(Rng(seed ^ 0x5EED03), corpus.streams, corpus.alias)
    corpus.cancels = build_cancels(Rng(seed ^ 0x5EED04), corpus.streams)
    corpus.revokes = build_revokes(Rng(seed ^ 0x5EED05), corpus.streams, corpus.windows)
    corpus.costs = build_cost_table(Rng(seed ^ 0x5EED06))
    corpus.alloc = build_allocations(Rng(seed ^ 0x5EED07), corpus.streams)
    return corpus


K_MIN = 1
K_MAX = 8
EMA_WINDOW = 25
EMA_LAMBDA = 2.0 / (EMA_WINDOW + 1)
EMA_SEED = 0.5
ALPHA_RAISE = 0.85
ALPHA_RESET = 0.30
RECAL_CAP = 6


# ---------------------------------------------------------------------------
# Tier 2: repairs and normalisation
# ---------------------------------------------------------------------------

def token_class(alias: dict, token: str) -> str:
    return alias.get(token, VOID_CLASS)


def repaired_windows(corpus) -> list:
    """Apply the documented repairs to the raw recorded windows.

    Repair codes are evaluated in code order R01 through R06 and every code
    that applies is recorded, so a window can carry more than one. R05 marks
    the window void; a void window still appears in every ledger, carrying its
    drafted tokens in the voided class.
    """
    out = []
    for win in corpus.windows:
        repairs = []

        k = win.raw_k
        if k < K_MIN:
            k = K_MIN
            repairs.append("R01")
        elif k > K_MAX:
            k = K_MAX
            repairs.append("R02")

        draft = list(win.raw_draft)
        if len(draft) > k:
            draft = draft[:k]
            repairs.append("R03")

        verdict = list(win.raw_verdict)
        answered = len(verdict) if len(verdict) < len(draft) else len(draft)
        if len(verdict) < len(draft):
            verdict = verdict + [VOID_TOKEN] * (len(draft) - len(verdict))
            repairs.append("R04")
        elif len(verdict) > len(draft):
            verdict = verdict[: len(draft)]

        void = win.raw_expiry <= win.grant_tick
        if void:
            repairs.append("R05")

        if any(tok not in corpus.alias for tok in draft):
            repairs.append("R06")

        out.append({
            "window_id": win.window_id,
            "stream_id": win.stream_id,
            "seq": win.seq,
            "k_requested": k,
            "draft": draft,
            "verdict": verdict,
            "correction": win.correction,
            "slot": win.slot,
            "grant_tick": win.grant_tick,
            "expiry_tick": win.raw_expiry,
            "repairs": repairs,
            "void": void,
            "answered": answered,
        })
    out.sort(key=lambda r: (r["stream_id"], r["seq"]))
    return out


# ---------------------------------------------------------------------------
# Tier 3: lease conflict resolution and priority inversion
# ---------------------------------------------------------------------------

def resolve_leases(corpus, wins: list) -> tuple:
    """Return (effective_expiry_by_window, inversions).

    A revoke preempts the holder only when the challenger's rank is strictly
    greater. A revoke from an equal or lower rank is ignored and recorded as a
    priority inversion.
    """
    rank = {s.stream_id: s.rank for s in corpus.streams}
    by_window = {}
    for rev in corpus.revokes:
        by_window.setdefault(rev["window_id"], []).append(rev)
    eff = {}
    inversions = []
    for win in wins:
        expiry = win["expiry_tick"]
        holder_rank = rank.get(win["stream_id"], 0)
        for rev in sorted(by_window.get(win["window_id"], []),
                          key=lambda r: (r["tick"], r["by_stream"])):
            challenger_rank = rank.get(rev["by_stream"], 0)
            if challenger_rank > holder_rank:
                if rev["tick"] < expiry:
                    expiry = rev["tick"]
            else:
                inversions.append({
                    "window_id": win["window_id"],
                    "slot": win["slot"],
                    "holder": win["stream_id"],
                    "holder_rank": holder_rank,
                    "challenger": rev["by_stream"],
                    "challenger_rank": challenger_rank,
                    "revoke_tick": rev["tick"],
                })
        eff[win["window_id"]] = expiry
    inversions.sort(key=lambda r: (r["window_id"], r["challenger"], r["revoke_tick"]))
    return eff, inversions


def cancel_map(corpus) -> dict:
    return {c["stream_id"]: c["tick"] for c in corpus.cancels}


# ---------------------------------------------------------------------------
# Tier 3: acceptance under a given K schedule
# ---------------------------------------------------------------------------

def accepted_prefix(alias: dict, draft: list, verdict: list) -> int:
    """Longest prefix where the draft and verdict tokens share a class.

    The void class never matches, including against itself.
    """
    n = 0
    for i in range(min(len(draft), len(verdict))):
        dc = token_class(alias, draft[i])
        vc = token_class(alias, verdict[i])
        if dc == VOID_CLASS or vc == VOID_CLASS or dc != vc:
            break
        n += 1
    return n


def score_window(corpus, win, k_policy, eff_expiry, cancel_tick):
    """Terminal token classes for one window under one policy K.

    Order is load bearing: the policy truncation and the acceptance prefix are
    resolved first, and only then does the lease bound how many of the
    accepted tokens actually left the buffer.
    """
    draft = win["draft"][:k_policy]
    verdict = win["verdict"][:k_policy]
    length = len(draft)
    counts = dict.fromkeys(TERMINAL_CLASSES, 0)

    if win["void"]:
        counts["voided"] = length
        return counts, 0, length

    if cancel_tick is not None and win["grant_tick"] >= cancel_tick:
        counts["reclaimed"] = length
        return counts, 0, length

    expiry = eff_expiry
    if cancel_tick is not None and cancel_tick < expiry:
        expiry = cancel_tick
    span = expiry - win["grant_tick"]
    if span < 0:
        span = 0

    prefix = accepted_prefix(corpus.alias, draft, verdict)
    accepted = prefix if prefix <= span else span
    answered = win["answered"]
    if answered > length:
        answered = length
    unanswered = length - answered
    counts["accepted"] = accepted
    counts["expired"] = prefix - accepted
    counts["voided"] = unanswered
    counts["rejected"] = length - prefix - unanswered
    return counts, prefix, length


# ---------------------------------------------------------------------------
# Tier 3: the K schedule fixed point
# ---------------------------------------------------------------------------

def forward_schedule(corpus, stream_wins, seed_k, eff, cancels):
    """One forward pass. Returns (schedule, per_window_rows, alpha_final)."""
    schedule = []
    rows = []
    alpha = EMA_SEED
    k = seed_k
    for win in stream_wins:
        k = K_MIN if k < K_MIN else (K_MAX if k > K_MAX else k)
        schedule.append(k)
        counts, prefix, length = score_window(
            corpus, win, k, eff[win["window_id"]],
            cancels.get(win["stream_id"]),
        )
        ratio = (prefix / length) if length else 0.0
        alpha = (1.0 - EMA_LAMBDA) * alpha + EMA_LAMBDA * ratio
        rows.append({
            "window_id": win["window_id"],
            "k_policy": k,
            "prefix": prefix,
            "drafted": length,
            "ratio": ratio,
            "alpha_after": alpha,
            "counts": counts,
        })
        if alpha > ALPHA_RAISE:
            k = min(K_MAX, k + 1)
        elif alpha < ALPHA_RESET:
            k = K_MIN
    return schedule, rows, alpha


def stream_fixed_point(corpus, stream, stream_wins, eff, cancels):
    """Recalibrate the seed K until the schedule stops moving.

    The seed is recalibrated from the stream's own pooled acceptance ratio,
    which the schedule itself determines, so the two chase each other. The
    loop stops when consecutive passes agree, or at the documented cap.
    """
    seed_k = stream.k_seed
    previous = None
    passes = 0
    schedule, rows, alpha = [], [], EMA_SEED
    converged = False
    while passes < RECAL_CAP:
        passes += 1
        schedule, rows, alpha = forward_schedule(
            corpus, stream_wins, seed_k, eff, cancels)
        if previous is not None and schedule == previous:
            converged = True
            break
        previous = schedule
        pooled_prefix = sum(r["prefix"] for r in rows)
        pooled_drafted = sum(r["drafted"] for r in rows)
        pooled = (pooled_prefix / pooled_drafted) if pooled_drafted else 0.0
        if pooled > ALPHA_RAISE:
            seed_k = min(K_MAX, seed_k + 1)
        elif pooled < ALPHA_RESET:
            seed_k = K_MIN
        else:
            # A pooled ratio inside the band leaves the seed alone, so the
            # next pass reproduces this one and the loop has converged.
            schedule, rows, alpha = forward_schedule(
                corpus, stream_wins, seed_k, eff, cancels)
            converged = True
            break
    return {
        "seed_k": seed_k,
        "schedule": schedule,
        "rows": rows,
        "alpha_final": alpha,
        "passes": passes,
        "converged": converged,
    }


def pooled_ratio(rows) -> float:
    """Pooled acceptance ratio for a stream: agreed tokens over drafted."""
    num = sum(r["prefix"] for r in rows)
    den = sum(r["drafted"] for r in rows)
    return (num / den) if den else 0.0


def band_for(ratio: float) -> str:
    """The band a stream's pooled acceptance ratio falls in.

    Boundaries are closed below: a ratio of exactly 0.85 is high and exactly
    0.30 is mid. Stated once in the shipped specification.
    """
    if ratio >= ALPHA_RAISE:
        return "high"
    if ratio >= ALPHA_RESET:
        return "mid"
    return "low"


# ---------------------------------------------------------------------------
# The whole run
# ---------------------------------------------------------------------------

def run(corpus) -> dict:
    """Compute every derived structure the artifacts serialise."""
    wins = repaired_windows(corpus)
    eff, inversions = resolve_leases(corpus, wins)
    cancels = cancel_map(corpus)

    by_stream = {}
    for win in wins:
        by_stream.setdefault(win["stream_id"], []).append(win)
    for rows in by_stream.values():
        rows.sort(key=lambda r: r["seq"])

    streams = sorted(corpus.streams, key=lambda s: s.stream_id)
    solved = {}
    for stream in streams:
        stream_wins = by_stream.get(stream.stream_id, [])
        solved[stream.stream_id] = stream_fixed_point(
            corpus, stream, stream_wins, eff, cancels)

    return {
        "wins": wins,
        "eff": eff,
        "inversions": inversions,
        "cancels": cancels,
        "by_stream": by_stream,
        "streams": streams,
        "solved": solved,
    }


# Declared artifact order. run_manifest.json lists them in exactly this order
# and excludes itself.
ARTIFACT_ORDER = [
    "/app/out/stream_registry.csv",
    "/app/out/token_classes.json",
    "/app/out/window_index.tsv",
    "/app/out/lease_grants.psv",
    "/app/out/cancel_timeline.jsonl",
    "/app/out/k_schedule.tsv",
    "/app/out/acceptance_ledger.csv",
    "/app/out/lease_conflicts.tsv",
    "/app/out/reclaim_ledger.csv",
    "/app/out/malformed_repairs.jsonl",
    "/app/out/window_disposition.csv",
    "/app/out/token_accounting.tsv",
    "/app/out/stream_metrics.json",
    "/app/out/tenant_cost.csv",
    "/app/out/inversion_report.tsv",
    "/app/out/nonconvergence_report.jsonl",
    "/app/out/slot_occupancy.tsv",
    "/app/out/conservation_ledger.json",
    "/app/out/reconciliation.tsv",
    "/app/out/arbiter_driver.py",
    "/app/out/run_manifest.json",
]


def _jdump(obj) -> str:
    """Compact JSON with a stable separator set and no key reordering."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Derived views shared by several artifacts
# ---------------------------------------------------------------------------

class View:
    """Everything the artifact writers read, computed once."""

    def __init__(self, corpus, result):
        self.corpus = corpus
        self.result = result
        self.streams = result["streams"]
        self.wins = result["wins"]
        self.eff = result["eff"]
        self.inversions = result["inversions"]
        self.cancels = result["cancels"]
        self.solved = result["solved"]
        self.by_id = {s.stream_id: s for s in self.streams}

        # Per window final row, keyed by window_id.
        self.win_rows = {}
        self.stream_pool = {}
        self.stream_band = {}
        for sid, sol in self.solved.items():
            ratio = pooled_ratio(sol["rows"])
            self.stream_pool[sid] = ratio
            self.stream_band[sid] = band_for(ratio)
            for row in sol["rows"]:
                self.win_rows[row["window_id"]] = row

        self.win_by_id = {w["window_id"]: w for w in self.wins}

        # Preemption record: which challenger clamped each window, if any.
        rank = {s.stream_id: s.rank for s in self.streams}
        self.preempt = {}
        by_window = {}
        for rev in corpus.revokes:
            by_window.setdefault(rev["window_id"], []).append(rev)
        for win in self.wins:
            holder_rank = rank.get(win["stream_id"], 0)
            best = None
            for rev in sorted(by_window.get(win["window_id"], []),
                              key=lambda r: (r["tick"], r["by_stream"])):
                if rank.get(rev["by_stream"], 0) > holder_rank and rev["tick"] < win["expiry_tick"]:
                    if best is None or rev["tick"] < best["tick"]:
                        best = rev
            self.preempt[win["window_id"]] = best


# ---------------------------------------------------------------------------
# Tier 1
# ---------------------------------------------------------------------------

def stream_registry(v: View) -> str:
    out = ["stream_id,tenant_id,priority_class,priority_rank,k_seed,admit_open,admit_close,status"]
    for s in sorted(v.streams, key=lambda x: x.stream_id):
        out.append(",".join([
            s.stream_id, s.tenant, s.priority, str(s.rank), str(s.k_seed),
            str(s.admit_open), str(s.admit_close), s.status,
        ]))
    return _lines(out)


def token_classes(v: View) -> str:
    """Keys are emitted in token pool order, never sorted."""
    obj = {}
    for tok in TOKEN_POOL:
        obj[tok] = v.corpus.alias[tok]
    obj[VOID_TOKEN] = v.corpus.alias[VOID_TOKEN]
    return _jdump(obj) + "\n"


# ---------------------------------------------------------------------------
# Tier 2
# ---------------------------------------------------------------------------

def window_index(v: View) -> str:
    out = ["window_id\tstream_id\tseq\tk_requested\tdrafted_recorded\tslot\t"
           "grant_tick\texpiry_tick\trepair_codes\tterminal_band"]
    for w in sorted(v.wins, key=lambda x: x["window_id"]):
        out.append("\t".join([
            w["window_id"], w["stream_id"], f'{w["seq"]:04d}', str(w["k_requested"]),
            str(len(w["draft"])), w["slot"], str(w["grant_tick"]),
            str(w["expiry_tick"]), ";".join(w["repairs"]),
            v.stream_band[w["stream_id"]],
        ]))
    return _lines(out)


def lease_grants(v: View) -> str:
    out = ["window_id|slot|grant_tick|recorded_expiry|effective_expiry|preempted_by|span"]
    rows = sorted(v.wins, key=lambda x: (x["slot"], x["grant_tick"], x["window_id"]))
    for w in rows:
        eff = v.eff[w["window_id"]]
        pre = v.preempt.get(w["window_id"])
        span = eff - w["grant_tick"]
        if span < 0:
            span = 0
        out.append("|".join([
            w["window_id"], w["slot"], str(w["grant_tick"]), str(w["expiry_tick"]),
            str(eff), pre["by_stream"] if pre else "", str(span),
        ]))
    return _lines(out)


def cancel_timeline(v: View) -> str:
    out = []
    for sid in sorted(v.cancels):
        tick = v.cancels[sid]
        origin = next(c["origin"] for c in v.corpus.cancels if c["stream_id"] == sid)
        after = 0
        straddling = 0
        for w in v.result["by_stream"].get(sid, []):
            if w["grant_tick"] >= tick:
                after += 1
            elif v.eff[w["window_id"]] > tick:
                straddling += 1
        out.append(_jdump({
            "stream_id": sid, "cancel_tick": tick, "origin": origin,
            "windows_after": after, "windows_straddling": straddling,
        }))
    return _lines(out)


# ---------------------------------------------------------------------------
# Tier 3
# ---------------------------------------------------------------------------

def k_schedule(v: View) -> str:
    out = ["stream_id\tseed_k_recorded\tseed_k_final\tpasses\tconverged\tschedule"]
    for s in sorted(v.streams, key=lambda x: x.stream_id):
        sol = v.solved[s.stream_id]
        out.append("\t".join([
            s.stream_id, str(s.k_seed), str(sol["seed_k"]), str(sol["passes"]),
            "true" if sol["converged"] else "false",
            ",".join(str(k) for k in sol["schedule"]),
        ]))
    return _lines(out)


def acceptance_ledger(v: View) -> str:
    out = ["window_id,k_policy,drafted,agreed_prefix,accepted,rejected,expired,reclaimed,voided"]
    for wid in sorted(v.win_rows):
        r = v.win_rows[wid]
        c = r["counts"]
        out.append(",".join([
            wid, str(r["k_policy"]), str(r["drafted"]), str(r["prefix"]),
            str(c["accepted"]), str(c["rejected"]), str(c["expired"]),
            str(c["reclaimed"]), str(c["voided"]),
        ]))
    return _lines(out)


def lease_conflicts(v: View) -> str:
    out = ["window_id\tslot\tholder\tholder_rank\tchallenger\tchallenger_rank\trevoke_tick\tdisposition"]
    rank = {s.stream_id: s.rank for s in v.streams}
    rows = []
    for rev in v.corpus.revokes:
        w = v.win_by_id.get(rev["window_id"])
        if w is None:
            continue
        hr = rank.get(rev["holder"], 0)
        cr = rank.get(rev["by_stream"], 0)
        rows.append((rev["window_id"], w["slot"], rev["holder"], hr,
                     rev["by_stream"], cr, rev["tick"],
                     "preempted" if cr > hr else "inverted"))
    rows.sort(key=lambda r: (r[0], r[4], r[6]))
    for r in rows:
        out.append("\t".join(str(x) for x in r))
    return _lines(out)


def reclaim_ledger(v: View) -> str:
    out = ["stream_id,cancel_tick,windows_reclaimed,tokens_reclaimed,slots_released"]
    for sid in sorted(v.cancels):
        tick = v.cancels[sid]
        wins = 0
        toks = 0
        slots = set()
        for w in v.result["by_stream"].get(sid, []):
            row = v.win_rows.get(w["window_id"])
            if row and row["counts"]["reclaimed"]:
                wins += 1
                toks += row["counts"]["reclaimed"]
                slots.add(w["slot"])
        out.append(",".join([sid, str(tick), str(wins), str(toks), str(len(slots))]))
    return _lines(out)


def malformed_repairs(v: View) -> str:
    """Exactly one line per documented repair code, including codes with no
    instances, which carry zero."""
    counts = {code: [0, 0] for code in REPAIR_CODES}
    for w in v.wins:
        row = v.win_rows.get(w["window_id"])
        drafted = row["drafted"] if row else 0
        for code in w["repairs"]:
            if code in counts:
                counts[code][0] += 1
                counts[code][1] += drafted
    out = []
    for code in REPAIR_CODES:
        out.append(_jdump({
            "repair_code": code,
            "windows": counts[code][0],
            "tokens_affected": counts[code][1],
        }))
    return _lines(out)


# ---------------------------------------------------------------------------
# Tier 4
# ---------------------------------------------------------------------------

def _disposition(counts) -> str:
    best = None
    for cls in TERMINAL_CLASSES:
        if best is None or counts[cls] > counts[best]:
            best = cls
    return best


def window_disposition(v: View) -> str:
    out = ["window_id,stream_id,seq,terminal_band,k_policy,drafted,accepted,"
           "rejected,expired,reclaimed,voided,disposition"]
    for wid in sorted(v.win_rows):
        r = v.win_rows[wid]
        w = v.win_by_id[wid]
        c = r["counts"]
        out.append(",".join([
            wid, w["stream_id"], f'{w["seq"]:04d}', v.stream_band[w["stream_id"]],
            str(r["k_policy"]), str(r["drafted"]), str(c["accepted"]),
            str(c["rejected"]), str(c["expired"]), str(c["reclaimed"]),
            str(c["voided"]), _disposition(c),
        ]))
    return _lines(out)


def _stream_totals(v: View, sid):
    tot = dict.fromkeys(TERMINAL_CLASSES, 0)
    drafted = 0
    for w in v.result["by_stream"].get(sid, []):
        row = v.win_rows.get(w["window_id"])
        if not row:
            continue
        drafted += row["drafted"]
        for cls in TERMINAL_CLASSES:
            tot[cls] += row["counts"][cls]
    return drafted, tot


def token_accounting(v: View) -> str:
    out = ["stream_id\tdrafted\taccepted\trejected\texpired\treclaimed\tvoided\tresidual"]
    for s in sorted(v.streams, key=lambda x: x.stream_id):
        drafted, tot = _stream_totals(v, s.stream_id)
        residual = drafted - sum(tot[c] for c in TERMINAL_CLASSES)
        out.append("\t".join([
            s.stream_id, str(drafted), str(tot["accepted"]), str(tot["rejected"]),
            str(tot["expired"]), str(tot["reclaimed"]), str(tot["voided"]),
            str(residual),
        ]))
    return _lines(out)


def stream_metrics(v: View) -> str:
    obj = {}
    for s in sorted(v.streams, key=lambda x: x.stream_id):
        sol = v.solved[s.stream_id]
        obj[s.stream_id] = {
            "pooled_ratio": fmt_num(v.stream_pool[s.stream_id], 4),
            "band": v.stream_band[s.stream_id],
            "alpha_final": fmt_num(sol["alpha_final"], 4),
            "windows": len(sol["rows"]),
            "passes": sol["passes"],
            "converged": sol["converged"],
        }
    return _jdump(obj) + "\n"


def tenant_cost(v: View) -> str:
    costs = v.corpus.costs
    inv_by_stream = {}
    for row in v.inversions:
        inv_by_stream[row["holder"]] = inv_by_stream.get(row["holder"], 0) + 1
    gross = {t: 0 for t in TENANTS}
    for s in v.streams:
        drafted, tot = _stream_totals(v, s.stream_id)
        windows = len(v.result["by_stream"].get(s.stream_id, []))
        units = (drafted * costs["draft_unit"]
                 + windows * costs["verify_unit"]
                 + tot["accepted"] * costs["emit_unit"]
                 + tot["reclaimed"] * costs["reclaim_unit"]
                 + tot["expired"] * costs["expire_unit"]
                 + tot["voided"] * costs["void_unit"]
                 + inv_by_stream.get(s.stream_id, 0) * costs["inversion_unit"])
        gross[s.tenant] = gross.get(s.tenant, 0) + units
    caps = {t: 0 for t in TENANTS}
    for s in v.streams:
        caps[s.tenant] = caps.get(s.tenant, 0) + v.corpus.alloc[s.stream_id]
    out = ["tenant_id,gross_units,capped_units,cap,over_cap"]
    for t in TENANTS:
        cap = caps[t]
        g = gross.get(t, 0)
        capped = g if g <= cap else cap
        out.append(",".join([t, str(g), str(capped), str(cap),
                             "true" if g > cap else "false"]))
    return _lines(out)


def inversion_report(v: View) -> str:
    out = ["window_id\tslot\tholder\tchallenger\trevoke_tick\ttokens_preserved"]
    for row in sorted(v.inversions, key=lambda r: (r["window_id"], r["challenger"], r["revoke_tick"])):
        wr = v.win_rows.get(row["window_id"])
        preserved = wr["counts"]["accepted"] if wr else 0
        out.append("\t".join([
            row["window_id"], row["slot"], row["holder"], row["challenger"],
            str(row["revoke_tick"]), str(preserved),
        ]))
    return _lines(out)


def nonconvergence_report(v: View) -> str:
    out = []
    for s in sorted(v.streams, key=lambda x: x.stream_id):
        sol = v.solved[s.stream_id]
        if sol["converged"]:
            continue
        out.append(_jdump({
            "stream_id": s.stream_id,
            "passes": sol["passes"],
            "final_schedule": sol["schedule"],
            "pooled_ratio": fmt_num(v.stream_pool[s.stream_id], 4),
        }))
    return _lines(out)


def slot_occupancy(v: View) -> str:
    out = ["slot\twindows\tgranted_ticks\teffective_ticks\tpeak_concurrent"]
    per = {s: [0, 0, 0] for s in SLOTS}
    spans = {s: [] for s in SLOTS}
    for w in v.wins:
        slot = w["slot"]
        if slot not in per:
            continue
        eff = v.eff[w["window_id"]]
        rec = w["expiry_tick"] - w["grant_tick"]
        e = eff - w["grant_tick"]
        per[slot][0] += 1
        per[slot][1] += rec if rec > 0 else 0
        per[slot][2] += e if e > 0 else 0
        if e > 0:
            spans[slot].append((w["grant_tick"], eff))
    for slot in SLOTS:
        events = []
        for a, b in spans[slot]:
            events.append((a, 1))
            events.append((b, -1))
        events.sort()
        cur = peak = 0
        for _, delta in events:
            cur += delta
            if cur > peak:
                peak = cur
        n, g, e = per[slot]
        out.append("\t".join([slot, str(n), str(g), str(e), str(peak)]))
    return _lines(out)


# ---------------------------------------------------------------------------
# Tier 5
# ---------------------------------------------------------------------------

def _grand_totals(v: View):
    drafted = 0
    tot = dict.fromkeys(TERMINAL_CLASSES, 0)
    for row in v.win_rows.values():
        drafted += row["drafted"]
        for cls in TERMINAL_CLASSES:
            tot[cls] += row["counts"][cls]
    return drafted, tot


def conservation_ledger(v: View) -> str:
    drafted, tot = _grand_totals(v)
    obj = {"drafted": drafted}
    for cls in TERMINAL_CLASSES:
        obj[cls] = tot[cls]
    obj["residual"] = drafted - sum(tot[c] for c in TERMINAL_CLASSES)
    return _jdump(obj) + "\n"


def reconciliation(v: View) -> str:
    """Two independent derivations of the same six figures.

    from_windows aggregates the per window ledger. from_streams aggregates the
    per stream accounting. Neither is defined in terms of the other.
    """
    drafted_w, tot_w = _grand_totals(v)
    drafted_s = 0
    tot_s = dict.fromkeys(TERMINAL_CLASSES, 0)
    for s in v.streams:
        d, t = _stream_totals(v, s.stream_id)
        drafted_s += d
        for cls in TERMINAL_CLASSES:
            tot_s[cls] += t[cls]
    out = ["class\tfrom_windows\tfrom_streams\tdelta"]
    out.append("\t".join(["drafted", str(drafted_w), str(drafted_s),
                          str(drafted_w - drafted_s)]))
    for cls in TERMINAL_CLASSES:
        out.append("\t".join([cls, str(tot_w[cls]), str(tot_s[cls]),
                              str(tot_w[cls] - tot_s[cls])]))
    return _lines(out)


def run_manifest(payloads: dict) -> str:
    """Digest every declared artifact except this manifest, in declared order."""
    entries = []
    for path in ARTIFACT_ORDER:
        if path.endswith("run_manifest.json"):
            continue
        data = payloads[path].encode("utf-8")
        entries.append({
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })
    return _jdump({"artifacts": entries}) + "\n"


# ---------------------------------------------------------------------------
# Whole run
# ---------------------------------------------------------------------------

BUILDERS = [
    ("/app/out/stream_registry.csv", stream_registry),
    ("/app/out/token_classes.json", token_classes),
    ("/app/out/window_index.tsv", window_index),
    ("/app/out/lease_grants.psv", lease_grants),
    ("/app/out/cancel_timeline.jsonl", cancel_timeline),
    ("/app/out/k_schedule.tsv", k_schedule),
    ("/app/out/acceptance_ledger.csv", acceptance_ledger),
    ("/app/out/lease_conflicts.tsv", lease_conflicts),
    ("/app/out/reclaim_ledger.csv", reclaim_ledger),
    ("/app/out/malformed_repairs.jsonl", malformed_repairs),
    ("/app/out/window_disposition.csv", window_disposition),
    ("/app/out/token_accounting.tsv", token_accounting),
    ("/app/out/stream_metrics.json", stream_metrics),
    ("/app/out/tenant_cost.csv", tenant_cost),
    ("/app/out/inversion_report.tsv", inversion_report),
    ("/app/out/nonconvergence_report.jsonl", nonconvergence_report),
    ("/app/out/slot_occupancy.tsv", slot_occupancy),
    ("/app/out/conservation_ledger.json", conservation_ledger),
    ("/app/out/reconciliation.tsv", reconciliation),
]


def build_all(corpus, result, driver_source: str) -> dict:
    """Return {artifact_path: text} for every declared artifact."""
    view = View(corpus, result)
    payloads = {}
    for path, fn in BUILDERS:
        payloads[path] = fn(view)
    payloads["/app/out/arbiter_driver.py"] = driver_source
    payloads["/app/out/run_manifest.json"] = run_manifest(payloads)
    return payloads


def _w(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _lines(rows) -> str:
    return "".join(r + "\n" for r in rows)


def _shard(items, n):
    """Split a list into n contiguous shards of near equal size."""
    out = [[] for _ in range(n)]
    per = (len(items) + n - 1) // n
    for i, item in enumerate(items):
        out[min(i // per, n - 1)].append(item)
    return out


def _tick_stamp(tick: int) -> str:
    """A deterministic pseudo timestamp derived only from the tick index."""
    minute = tick % 60
    hour = (tick // 60) % 24
    day = 1 + (tick // 1440) % 28
    return f"2026-04-{day:02d}T{hour:02d}:{minute:02d}:00Z"


# ---------------------------------------------------------------------------
# Stream files
# ---------------------------------------------------------------------------

def emit_streams(d: Path, c) -> None:
    rows = ["stream_ref,tenant_hint,priority_class,k_seed,admit_open,admit_close"]
    for s in c.streams:
        rows.append(",".join([
            s.raw_id, s.master_tenant, s.priority, str(s.k_seed),
            str(s.admit_open), str(s.admit_close),
        ]))
    _w(d / "streams-master.csv", _lines(rows))

    rows = ["stream_ref\ttenant_id"]
    for s in c.streams:
        rows.append(f"{s.raw_id}\t{s.tenant}")
    _w(d / "streams-tenant.tsv", _lines(rows))

    rows = ["# priority class per stream reference",
            "# one entry per stream, key is the stream reference as recorded"]
    for s in c.streams:
        rows.append(f"{s.raw_id} = {s.priority}")
    _w(d / "streams-priority.properties", _lines(rows))

    rows = []
    for s in c.streams:
        rows.append(f"stream={s.raw_id} status={s.status} rank={s.rank} "
                    f"profile=lane_{s.priority}")
    _w(d / "streams-status.logfmt", _lines(rows))

    blocks = []
    for s in c.streams:
        blocks.append(
            f"Stream-Ref: {s.raw_id}\n"
            f"Label: {s.label}\n"
            f"Lane: {s.priority}\n"
            f"Admit-Open: {s.admit_open}\n"
        )
    _w(d / "streams-labels.rfc822", "\n".join(blocks))

    rows = ["stream_ref|admit_open|admit_close|slots_permitted"]
    for s in c.streams:
        permitted = ";".join(SLOTS[:: (1 + (s.rank % 3))][:6])
        rows.append(f"{s.raw_id}|{s.admit_open}|{s.admit_close}|{permitted}")
    _w(d / "streams-admit.psv", _lines(rows))

    rows = ["stream_ref,allocated_units"]
    for s in c.streams:
        rows.append(f"{s.raw_id},{c.alloc[s.stream_id]}")
    _w(d / "stream-budget-allocation.csv", _lines(rows))


# ---------------------------------------------------------------------------
# Window files
# ---------------------------------------------------------------------------

def emit_windows(d: Path, c) -> None:
    raw_of = {s.stream_id: s.raw_id for s in c.streams}
    wins = list(c.windows)

    # Drafts: ten JSONL shards.
    for idx, shard in enumerate(_shard(wins, 10), start=1):
        rows = []
        for w in shard:
            rows.append(json.dumps({
                "stream_ref": raw_of[w.stream_id],
                "seq": w.seq,
                "k_requested": w.raw_k,
                "draft": w.raw_draft,
            }, ensure_ascii=False, separators=(",", ":")))
        _w(d / f"windows-draft-{idx:02d}.jsonl", _lines(rows))

    # Verdicts: six pipe separated shards.
    for idx, shard in enumerate(_shard(wins, 6), start=1):
        rows = ["stream_ref|seq|verdict_tokens"]
        for w in shard:
            rows.append(f"{raw_of[w.stream_id]}|{w.seq}|" + ";".join(w.raw_verdict))
        _w(d / f"windows-verdict-{idx:02d}.psv", _lines(rows))

    # Meta: four tab separated shards.
    for idx, shard in enumerate(_shard(wins, 4), start=1):
        rows = ["stream_ref\tseq\tslot\tissued_tick"]
        for w in shard:
            rows.append(f"{raw_of[w.stream_id]}\t{w.seq}\t{w.slot}\t{w.grant_tick}")
        _w(d / f"windows-meta-{idx:02d}.tsv", _lines(rows))

    # Corrections: three space separated shards.
    for idx, shard in enumerate(_shard(wins, 3), start=1):
        rows = ["stream_ref seq correction_token"]
        for w in shard:
            rows.append(f"{raw_of[w.stream_id]} {w.seq} {w.correction}")
        _w(d / f"windows-correction-{idx:02d}.ssv", _lines(rows))

    # Leases: six logfmt shards.
    for idx, shard in enumerate(_shard(wins, 6), start=1):
        rows = []
        for w in shard:
            rows.append(
                f"stream={raw_of[w.stream_id]} seq={w.seq} slot={w.slot} "
                f"grant={w.grant_tick} expiry={w.raw_expiry}")
        _w(d / f"leases-grant-{idx:02d}.logfmt", _lines(rows))

    rows = ["slot,revoke_tick,by_stream_ref,holder_stream_ref,holder_seq"]
    for rev in c.revokes:
        holder_seq = int(rev["window_id"].split("#")[1])
        rows.append(",".join([
            rev["slot"], str(rev["tick"]), raw_of[rev["by_stream"]],
            raw_of[rev["holder"]], str(holder_seq),
        ]))
    _w(d / "leases-revoke.csv", _lines(rows))


# ---------------------------------------------------------------------------
# Cancellation log
# ---------------------------------------------------------------------------

def emit_cancels(d: Path, c) -> None:
    """RFC5424 style journal.

    Only records whose MSGID is STREAM_CANCEL are cancellations. The file also
    carries admission, heartbeat and audit records at other MSGIDs, which the
    specification says carry no cancellation meaning.
    """
    raw_of = {s.stream_id: s.raw_id for s in c.streams}
    rows = []
    cancel_by = {x["stream_id"]: x for x in c.cancels}
    for i, s in enumerate(c.streams):
        ev = cancel_by.get(s.stream_id)
        if ev is not None:
            rows.append(
                f"<133>1 {_tick_stamp(ev['tick'])} arbiter sda-gateway {1000 + i} "
                f"STREAM_CANCEL [sda stream=\"{raw_of[s.stream_id]}\" "
                f"tick=\"{ev['tick']}\" origin=\"{ev['origin']}\"] "
                f"cancellation accepted for {raw_of[s.stream_id]}")
        rows.append(
            f"<134>1 {_tick_stamp(s.admit_open)} arbiter sda-gateway {2000 + i} "
            f"STREAM_ADMIT [sda stream=\"{raw_of[s.stream_id]}\" "
            f"tick=\"{s.admit_open}\"] admission granted")
        if i % 3 == 0:
            rows.append(
                f"<134>1 {_tick_stamp(s.admit_close)} arbiter sda-gateway {3000 + i} "
                f"LANE_HEARTBEAT [sda stream=\"{raw_of[s.stream_id]}\" "
                f"tick=\"{s.admit_close}\"] lane heartbeat observed")
    _w(d / "cancel-events.rfc5424", _lines(rows))


# ---------------------------------------------------------------------------
# Token tables
# ---------------------------------------------------------------------------

def emit_tokens(d: Path, c) -> None:
    rows = ["token_id\tclass_id"]
    for tok in TOKEN_POOL:
        rows.append(f"{tok}\t{c.alias[tok]}")
    _w(d / "token-alias.tsv", _lines(rows))

    rows = ["token_id lexeme_rank surface_family"]
    for i, tok in enumerate(TOKEN_POOL):
        rows.append(f"{tok} {i} fam{i % 12:02d}")
    _w(d / "token-vocab.ssv", _lines(rows))

    # Fixed width: token_id at columns 1 to 4, class_id at 6 to 10,
    # emit_width at 12 to 14. Documented in the specification.
    rows = []
    for tok in TOKEN_POOL:
        cls = c.alias[tok]
        rows.append(f"{tok:<4} {cls:<5} {len(tok) + 1:>3}")
    _w(d / "token-widths.fixed", _lines(rows))

    rows = ["# canonical surface form per token identifier"]
    for tok in TOKEN_POOL:
        rows.append(f"{tok} = tok.{tok.lower()}")
    _w(d / "token-normalisation.properties", _lines(rows))

    rows = []
    for i, tok in enumerate(TOKEN_POOL):
        rows.append(json.dumps({
            "token_id": tok, "ordinal": i, "class_id": c.alias[tok],
            "void": tok == VOID_TOKEN,
        }, ensure_ascii=False, separators=(",", ":")))
    _w(d / "token-index.jsonl", _lines(rows))


# ---------------------------------------------------------------------------
# Cost policy
# ---------------------------------------------------------------------------

def emit_cost(d: Path, c) -> None:
    lines = [
        "# Service unit costs for the arbiter accounting lane.",
        "# Every figure is a whole number of service units. These are the only",
        "# cost constants; nothing in this task is measured against a clock.",
        "",
        "[units]",
    ]
    for key in ["draft_unit", "verify_unit", "emit_unit", "reclaim_unit",
                "expire_unit", "void_unit", "inversion_unit"]:
        lines.append(f"{key} = {c.costs[key]}")
    lines += [
        "",
        "[priority_rank]",
    ]
    for name, rank in PRIORITY_RANK.items():
        lines.append(f"{name} = {rank}")
    lines += [
        "",
        "[slots]",
        "registry = [" + ", ".join(f'"{s}"' for s in SLOTS) + "]",
        "",
        "[tenants]",
        "registry = [" + ", ".join(f'"{t}"' for t in TENANTS) + "]",
    ]
    _w(d / "cost-units.toml", _lines(lines))


# ---------------------------------------------------------------------------
# The service simulator
# ---------------------------------------------------------------------------

SIMULATOR = '''"""SDA arbiter simulator: a local service over CLI and HTTP.

Standard library only. No network egress: the HTTP listener binds loopback.
Start it with

    python3 arbiter_service.py serve --port 8713 --data /app/data

and drive it with the CLI subcommands or with plain HTTP requests to the same
port. Both channels reach the same in process state.
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

STATE = {"admitted": [], "cancelled": [], "leases": {}, "notes": []}
LOCK = threading.Lock()


def _snapshot():
    with LOCK:
        return {
            "admitted": sorted(STATE["admitted"]),
            "cancelled": sorted(STATE["cancelled"]),
            "leases": dict(sorted(STATE["leases"].items())),
            "notes": list(STATE["notes"]),
        }


def op_admit(stream):
    with LOCK:
        if stream not in STATE["admitted"]:
            STATE["admitted"].append(stream)
    return {"ok": True, "admitted": stream}


def op_cancel(stream):
    with LOCK:
        if stream not in STATE["cancelled"]:
            STATE["cancelled"].append(stream)
    return {"ok": True, "cancelled": stream}


def op_lease(slot, stream):
    with LOCK:
        STATE["leases"][slot] = stream
    return {"ok": True, "slot": slot, "holder": stream}


def op_note(text):
    with LOCK:
        STATE["notes"].append(text)
    return {"ok": True, "notes": len(STATE["notes"])}


OPS = {"admit": op_admit, "cancel": op_cancel, "lease": op_lease, "note": op_note}


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("/state", "/v1/state"):
            self._send(200, _snapshot())
        elif self.path.rstrip("/") in ("/health", "/v1/health"):
            self._send(200, {"ok": True, "service": "sda-arbiter"})
        else:
            self._send(404, {"ok": False, "error": "no such route"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"ok": False, "error": "body is not JSON"})
            return
        route = self.path.rstrip("/").rsplit("/", 1)[-1]
        fn = OPS.get(route)
        if fn is None:
            self._send(404, {"ok": False, "error": "no such operation"})
            return
        try:
            if route == "lease":
                self._send(200, fn(payload["slot"], payload["stream"]))
            elif route == "note":
                self._send(200, fn(payload["text"]))
            else:
                self._send(200, fn(payload["stream"]))
        except KeyError as exc:
            self._send(400, {"ok": False, "error": "missing field " + str(exc)})

    def log_message(self, *args):
        return


def serve(port):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        httpd.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="arbiter_service")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8713)
    p.add_argument("--data", default="/app/data")
    for name in ("admit", "cancel"):
        q = sub.add_parser(name)
        q.add_argument("--stream", required=True)
    q = sub.add_parser("lease")
    q.add_argument("--slot", required=True)
    q.add_argument("--stream", required=True)
    q = sub.add_parser("note")
    q.add_argument("--text", required=True)
    q = sub.add_parser("state")
    q.add_argument("--port", type=int, default=8713)
    args = parser.parse_args(argv)

    if args.cmd == "serve":
        serve(args.port)
        return 0
    if args.cmd == "state":
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/v1/state") as r:
            sys.stdout.write(r.read().decode("utf-8") + "\\n")
        return 0

    import urllib.request
    body = {}
    if args.cmd in ("admit", "cancel"):
        body["stream"] = args.stream
    elif args.cmd == "lease":
        body["slot"] = args.slot
        body["stream"] = args.stream
    else:
        body["text"] = args.text
    req = urllib.request.Request(
        f"http://127.0.0.1:8713/v1/{args.cmd}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req) as r:
        sys.stdout.write(r.read().decode("utf-8") + "\\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def emit_service(d: Path) -> None:
    (d / "arbiter_service.py").write_text(SIMULATOR, encoding="utf-8", newline="\n")


def emit_all(data_dir: Path, seed: int, n_streams: int):
    corpus = build_corpus(seed, n_streams)
    data_dir.mkdir(parents=True, exist_ok=True)
    emit_streams(data_dir, corpus)
    emit_windows(data_dir, corpus)
    emit_cancels(data_dir, corpus)
    emit_tokens(data_dir, corpus)
    emit_service(data_dir)
    return corpus


# ---------------------------------------------------------------------------
# Grading harness.
#
# The graded corpus is rebuilt here from EVAL_SEED, which lives only in this
# file and never enters the environment build context, so every figure the
# driver tests grade comes from records the run has never seen.
#
# Nothing below reads /app/data. That path exists in the agent image and is not
# propagated into the verifier container, so a grade time read of it would
# crash every trial. Eval corpora are written under the system temp directory.
# ---------------------------------------------------------------------------

OUT = Path("/app/out")
DRIVER = OUT / "arbiter_driver.py"

SHIPPED_SEED = 20260908
SHIPPED_STREAMS = 240
EVAL_SEED = 815522743
EVAL_STREAMS = 96
SCALE_SEED = 977310684
SCALE_STREAMS = 420

ARTIFACT_NAMES = [p.rsplit("/", 1)[-1] for p in ARTIFACT_ORDER]


# ---------------------------------------------------------------------------
# Reference construction
# ---------------------------------------------------------------------------

def _reference(seed, n_streams, driver_source=""):
    corpus = build_corpus(seed, n_streams)
    result = run(corpus)
    return build_all(corpus, result, driver_source)


def shipped_expected():
    """Expected artifacts for the corpus the run was given."""
    src = DRIVER.read_text(encoding="utf-8", errors="replace") if DRIVER.is_file() else ""
    return _reference(SHIPPED_SEED, SHIPPED_STREAMS, src)


def delivered(name):
    path = OUT / name
    assert path.is_file(), f"missing declared artifact {name}"
    return path.read_text(encoding="utf-8", errors="replace")


def _same(name, expected_text):
    """Whole artifact equality, reported with the first differing line."""
    got = delivered(name)
    if got == expected_text:
        return
    g = got.split("\n")
    e = expected_text.split("\n")
    for i in range(max(len(g), len(e))):
        a = g[i] if i < len(g) else "<absent>"
        b = e[i] if i < len(e) else "<absent>"
        if a != b:
            raise AssertionError(
                f"{name} differs at line {i + 1}\n  delivered: {a[:200]!r}\n"
                f"  expected:  {b[:200]!r}\n"
                f"  ({len(g)} delivered lines, {len(e)} expected lines)")
    raise AssertionError(f"{name} differs in length only")


# ---------------------------------------------------------------------------
# Eval corpora and driver execution
# ---------------------------------------------------------------------------

_CORPUS_CACHE = {}
_CORPUS_LOCK = threading.Lock()


def eval_corpus(seed, n_streams, tag):
    """Write a fresh corpus the run has never seen, under the temp directory.

    rewardkit runs checks concurrently in threads, so the corpus is built once
    per key under a lock, into a directory of its own, and never removed while
    another check may still be reading it. Checks treat it as read only.
    """
    key = (seed, n_streams, tag)
    with _CORPUS_LOCK:
        if key not in _CORPUS_CACHE:
            root = Path(tempfile.mkdtemp(prefix=f"sda_eval_{tag}_"))
            emit_all(root, seed, n_streams)
            _share(root)
            _CORPUS_CACHE[key] = root
        return _CORPUS_CACHE[key]


def _private_copy(data, tag):
    """A private, writable copy of a corpus for a check that edits its input."""
    twin = Path(tempfile.mkdtemp(prefix=f"sda_eval_{tag}_")) / tag
    shutil.copytree(data, twin)
    return twin


# The delivered driver is agent authored code and this container holds the
# ground truth, so the driver runs as an unprivileged user. /tests is mode 700
# and owned by root, so a dropped driver cannot read EVAL_SEED or the reference
# implementation out of it. setpriv and the nobody account are installed by
# tests/Dockerfile; when neither is present (a developer running these tests on
# a workstation) the driver runs in process and the isolation is simply absent.
SETPRIV = shutil.which("setpriv")
UNPRIV_USER = "nobody"
UNPRIV_GROUP = "nogroup"


def _drop_privileges(command):
    """Wrap a command so it runs as the unprivileged user, where possible."""
    if not SETPRIV or os.name != "posix" or os.geteuid() != 0:
        return command
    return [SETPRIV, "--reuid", UNPRIV_USER, "--regid", UNPRIV_GROUP,
            "--clear-groups", "--"] + command


def _share(path, writable=False):
    """Let the unprivileged user reach a temp path the driver needs."""
    if os.name != "posix":
        return
    target = Path(path)
    dir_mode = 0o777 if writable else 0o755
    file_mode = 0o666 if writable else 0o644
    try:
        if target.is_file():
            os.chmod(target, file_mode)
            return
        os.chmod(target, dir_mode)
        for root, dirs, files in os.walk(target):
            for name in dirs:
                os.chmod(os.path.join(root, name), dir_mode)
            for name in files:
                os.chmod(os.path.join(root, name), file_mode)
    except OSError:
        pass


def _staged_driver():
    """Copy the delivered driver somewhere the unprivileged user can read.

    Each call stages into a directory of its own, because rewardkit runs
    checks concurrently. The declared artifact itself is never chmodded, so
    nothing this function does can change what the artifact tests grade.
    """
    stage = Path(tempfile.mkdtemp(prefix="sda_driver_"))
    target = stage / "arbiter_driver.py"
    shutil.copyfile(DRIVER, target)
    _share(stage)
    _share(target)
    return target


_LAUNCH_LOCK = threading.Lock()
_IN_FLIGHT = 0


def _reap(proc):
    """Kill everything the driver left behind, after any exit.

    The driver runs in its own session as the unprivileged user, so its process
    group goes first. rewardkit runs checks concurrently, so the sweep over
    every remaining process of that user, which catches a child that called
    setsid() to leave the group, waits until no other check has a driver
    running and so cannot kill a sibling check's live driver.
    """
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        pass


def _release(proc):
    global _IN_FLIGHT
    _reap(proc)
    with _LAUNCH_LOCK:
        _IN_FLIGHT -= 1
        if (_IN_FLIGHT == 0 and os.name == "posix" and os.geteuid() == 0
                and shutil.which("pkill")):
            subprocess.run(["pkill", "-KILL", "-u", UNPRIV_USER], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=10)


def run_driver(data_dir, out_dir, timeout=900):
    """Run the delivered driver over a corpus directory."""
    assert DRIVER.is_file(), "the run delivered no arbiter_driver.py"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    driver = _staged_driver()
    _share(out, writable=True)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(out),
           "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    # stderr goes to a private file and only the driver itself is waited on, so
    # a detached child holding an inherited descriptor cannot stall the check.
    global _IN_FLIGHT
    with _LAUNCH_LOCK:
        _IN_FLIGHT += 1
    with tempfile.TemporaryFile() as errlog:
        try:
            proc = subprocess.Popen(
                _drop_privileges(
                    [sys.executable, str(driver), "--data", str(data_dir), "--out", str(out)]),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=errlog,
                env=env, start_new_session=True)
        except Exception:
            with _LAUNCH_LOCK:
                _IN_FLIGHT -= 1
            raise
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _reap(proc)
            proc.wait()
        finally:
            _release(proc)
        errlog.seek(0)
        stderr = errlog.read()[-4000:].decode("utf-8", "replace")
    return subprocess.CompletedProcess(proc.args, proc.returncode, "", stderr), out


def driver_outputs(data_dir, out_dir):
    proc, out = run_driver(data_dir, out_dir)
    assert proc.returncode == 0, (
        f"arbiter_driver.py exited {proc.returncode}\n{proc.stderr[-2000:]}")
    got = {}
    for name in ARTIFACT_NAMES:
        if name == "arbiter_driver.py":
            continue
        p = out / name
        got[name] = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
    return got


def _tmp(tag):
    """A fresh output directory private to this call (checks run concurrently).

    The parent is opened to the unprivileged user too, because a driver may
    remove and recreate its own output directory.
    """
    parent = Path(tempfile.mkdtemp(prefix=f"sda_out_{tag}_"))
    _share(parent, writable=True)
    return parent / "out"


# ===========================================================================
# Positive tests. One whole artifact per test; the three largest artifacts are
# graded in three sections, each still graded whole.
# ===========================================================================

def _impl_test_declared_artifacts_exist_and_parse():
    """POSITIVE: every declared artifact is present and the structured ones parse."""
    for name in ARTIFACT_NAMES:
        p = OUT / name
        assert p.is_file(), f"missing declared artifact {name}"
        assert p.stat().st_size > 0, f"empty declared artifact {name}"
    json.loads(delivered("conservation_ledger.json"))
    json.loads(delivered("stream_metrics.json"))
    json.loads(delivered("token_classes.json"))
    json.loads(delivered("run_manifest.json"))
    for line in delivered("malformed_repairs.jsonl").splitlines():
        json.loads(line)


def _impl_test_stream_registry_matches_reference():
    """POSITIVE: the canonical stream registry, whole file."""
    _same("stream_registry.csv", shipped_expected()["/app/out/stream_registry.csv"])


def _impl_test_token_classes_matches_reference():
    """POSITIVE: the token to class map, in token ordinal order."""
    _same("token_classes.json", shipped_expected()["/app/out/token_classes.json"])


def _impl_test_window_index_matches_reference():
    """POSITIVE: the window index including the band each stream ends in."""
    _same("window_index.tsv", shipped_expected()["/app/out/window_index.tsv"])


def _impl_test_lease_grants_matches_reference():
    """POSITIVE: lease grants with effective expiry and span, in slot order."""
    _same("lease_grants.psv", shipped_expected()["/app/out/lease_grants.psv"])


def _impl_test_cancel_timeline_matches_reference():
    """POSITIVE: the cancellation timeline with after and straddling counts."""
    _same("cancel_timeline.jsonl", shipped_expected()["/app/out/cancel_timeline.jsonl"])


def _impl_test_k_schedule_matches_reference():
    """POSITIVE: the settled policy K schedule per stream."""
    _same("k_schedule.tsv", shipped_expected()["/app/out/k_schedule.tsv"])


def _impl_test_acceptance_ledger_matches_reference():
    """POSITIVE: per window acceptance under the settled schedule."""
    _same("acceptance_ledger.csv", shipped_expected()["/app/out/acceptance_ledger.csv"])


def _impl_test_lease_conflicts_matches_reference():
    """POSITIVE: every recorded revocation and its disposition."""
    _same("lease_conflicts.tsv", shipped_expected()["/app/out/lease_conflicts.tsv"])


def _impl_test_reclaim_ledger_matches_reference():
    """POSITIVE: reclaim totals for each cancelled stream."""
    _same("reclaim_ledger.csv", shipped_expected()["/app/out/reclaim_ledger.csv"])


def _impl_test_malformed_repairs_matches_reference():
    """POSITIVE: the six repair codes with their instance counts."""
    _same("malformed_repairs.jsonl", shipped_expected()["/app/out/malformed_repairs.jsonl"])


def _disposition_section(index):
    text = delivered("window_disposition.csv")
    expect = shipped_expected()["/app/out/window_disposition.csv"]
    g = text.split("\n")
    e = expect.split("\n")
    body_e = e[1:-1] if e and e[-1] == "" else e[1:]
    third = (len(body_e) + 2) // 3
    lo, hi = index * third, (index + 1) * third
    got_body = g[1:len(g) - 1] if g and g[-1] == "" else g[1:]
    if g[:1] != e[:1]:
        raise AssertionError(
            f"window_disposition.csv header differs\n  delivered: {g[:1]}\n"
            f"  expected:  {e[:1]}")
    want = body_e[lo:hi]
    have = got_body[lo:hi]
    for i, (a, b) in enumerate(zip(have + [None] * (len(want) - len(have)), want)):
        if a != b:
            raise AssertionError(
                f"window_disposition.csv section {index + 1} differs at body row "
                f"{lo + i + 1}\n  delivered: {a!r}\n  expected:  {b!r}")
    assert len(got_body) == len(body_e), (
        f"window_disposition.csv has {len(got_body)} body rows, expected {len(body_e)}")


def _impl_test_window_disposition_first_section_matches_reference():
    """POSITIVE: window disposition, first third, graded whole."""
    _disposition_section(0)


def _impl_test_window_disposition_second_section_matches_reference():
    """POSITIVE: window disposition, second third, graded whole."""
    _disposition_section(1)


def _impl_test_window_disposition_third_section_matches_reference():
    """POSITIVE: window disposition, final third, graded whole."""
    _disposition_section(2)


def _impl_test_token_accounting_matches_reference():
    """POSITIVE: per stream five class accounting with its residual."""
    _same("token_accounting.tsv", shipped_expected()["/app/out/token_accounting.tsv"])


def _impl_test_stream_metrics_matches_reference():
    """POSITIVE: per stream pooled ratio, band, moving average and pass count."""
    _same("stream_metrics.json", shipped_expected()["/app/out/stream_metrics.json"])


def _impl_test_tenant_cost_matches_reference():
    """POSITIVE: tenant service units with the cap applied after aggregation."""
    _same("tenant_cost.csv", shipped_expected()["/app/out/tenant_cost.csv"])


def _impl_test_inversion_report_matches_reference():
    """POSITIVE: every priority inversion and the tokens it preserved."""
    _same("inversion_report.tsv", shipped_expected()["/app/out/inversion_report.tsv"])


def _impl_test_nonconvergence_report_matches_reference():
    """POSITIVE: the streams that stopped at the recalibration cap."""
    _same("nonconvergence_report.jsonl",
          shipped_expected()["/app/out/nonconvergence_report.jsonl"])


def _impl_test_slot_occupancy_matches_reference():
    """POSITIVE: per slot occupancy including peak concurrency."""
    _same("slot_occupancy.tsv", shipped_expected()["/app/out/slot_occupancy.tsv"])


def _impl_test_conservation_ledger_matches_reference():
    """POSITIVE: the run wide conservation identity."""
    _same("conservation_ledger.json",
          shipped_expected()["/app/out/conservation_ledger.json"])


def _impl_test_reconciliation_matches_reference():
    """POSITIVE: the two independent derivations agree line for line."""
    _same("reconciliation.tsv", shipped_expected()["/app/out/reconciliation.tsv"])


def _impl_test_run_manifest_matches_delivered_files():
    """POSITIVE: the manifest digests the files actually delivered.

    Recomputed against the delivered bytes rather than against the reference,
    so a manifest is correct exactly when it describes what was shipped.
    """
    manifest = json.loads(delivered("run_manifest.json"))
    assert list(manifest.keys()) == ["artifacts"], (
        f"run_manifest.json keys are {list(manifest.keys())}, expected ['artifacts']")
    entries = manifest["artifacts"]
    expect_paths = [p for p in ARTIFACT_ORDER if not p.endswith("run_manifest.json")]
    assert [e.get("path") for e in entries] == expect_paths, (
        "run_manifest.json does not list every declared artifact in declared order")
    for entry in entries:
        assert list(entry.keys()) == ["path", "sha256", "bytes"], (
            f"manifest entry keys are {list(entry.keys())}")
        name = entry["path"].rsplit("/", 1)[-1]
        raw = (OUT / name).read_bytes()
        assert entry["bytes"] == len(raw), (
            f"manifest byte length for {name} is {entry['bytes']}, file holds {len(raw)}")
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest(), (
            f"manifest digest for {name} does not match the delivered bytes")


def _impl_test_driver_reproduces_unseen_corpus():
    """POSITIVE: the delivered driver replays a corpus the run never saw."""
    data = eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary")
    got = driver_outputs(data, _tmp("primary"))
    src = DRIVER.read_text(encoding="utf-8", errors="replace")
    expect = _reference(EVAL_SEED, EVAL_STREAMS, src)
    bad = []
    for name, text in got.items():
        if text != expect["/app/out/" + name]:
            bad.append(name)
    assert not bad, f"driver output differs on an unseen corpus for: {sorted(bad)}"


# Reproducibility across two runs of one corpus is graded once, by
# test_negative_weight_nondeterministic_output. A positive test of the same
# observable would pay twice for one property, and it would pay a driver that
# writes nothing at all, because two empty runs agree.


# ===========================================================================
# Negative controls. Each asserts that its cheat IS present, so it passes only
# when the cheat happened and its negative weight is earned only then.
# ===========================================================================

def _impl_test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: fires when the driver replays the shipped figures whatever corpus it is given."""
    data = eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary")
    try:
        got = driver_outputs(data, _tmp("hard"))
    except Exception:
        assert False, "the driver ran on an unseen corpus"
    shipped = _reference(SHIPPED_SEED, SHIPPED_STREAMS,
                         DRIVER.read_text(encoding="utf-8", errors="replace"))
    echoed = sum(1 for name, text in got.items()
                 if text is not None and text == shipped["/app/out/" + name])
    assert echoed >= 3, (
        "the driver produced the unseen corpus's own figures rather than the "
        "shipped ones")


def _impl_test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: fires when the same corpus under a different directory name grades differently."""
    data = eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary")
    twin = _private_copy(data, "sda_eval_renamed_lane")
    _share(twin)
    a = driver_outputs(data, _tmp("nameA"))
    b = driver_outputs(twin, _tmp("nameB"))
    differing = [name for name in a if a[name] != b[name]]
    assert differing, "the driver keys on the corpus directory name"


# The alias table control was withdrawn. It asserted that the output does not
# move when the shipped token to class table is rewritten, which fires on any
# driver that never reads that table. A driver comparing token identifiers
# rather than classes is doing exactly that, and it is an honest misreading of
# the specification rather than a shortcut: the positive tests already price it
# at roughly two thirds of the total. Worse, a driver with the answers baked in
# also never reads the table, so this control stacked a second penalty on the
# cheat that test_negative_weight_hardcoded_sample_answers already owns.


def _impl_test_negative_weight_nondeterministic_output():
    """NEGATIVE: fires when two replays of one corpus disagree."""
    data = eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary")
    a = driver_outputs(data, _tmp("ndA"))
    b = driver_outputs(data, _tmp("ndB"))
    differing = [name for name in a if a[name] != b[name]]
    assert differing, "the driver is deterministic across runs"


# The cancellation journal control was withdrawn for the same reason as the
# alias table control: a driver that ignores the journal misreads the
# specification, and cancel_timeline and reclaim_ledger already price that.


def _impl_test_negative_weight_degenerate_at_scale():
    """NEGATIVE: fires when a corpus larger than anything shipped yields a truncated replay."""
    # Inverted: holds only when the driver replays an ordinary unseen corpus in
    # full and then truncates one larger than anything shipped. A driver that
    # writes nothing, or fails everywhere, is not this shortcut.
    src = DRIVER.read_text(encoding="utf-8", errors="replace")
    normal = driver_outputs(eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary"), _tmp("norm"))
    want_normal = _reference(EVAL_SEED, EVAL_STREAMS, src)["/app/out/acceptance_ledger.csv"]
    assert normal.get("acceptance_ledger.csv") == want_normal, (
        "the driver does not replay an ordinary corpus in full")
    data = eval_corpus(SCALE_SEED, SCALE_STREAMS, "scale")
    got = driver_outputs(data, _tmp("scale"))
    expect = _reference(SCALE_SEED, SCALE_STREAMS, src)
    rows_got = len((got.get("acceptance_ledger.csv") or "").splitlines())
    rows_want = len(expect["/app/out/acceptance_ledger.csv"].splitlines())
    assert rows_got < rows_want, (
        f"the driver replayed the oversized corpus in full ({rows_got} rows)")


def _impl_test_negative_weight_order_dependent_output():
    """NEGATIVE: fires when reordering the recorded rows changes the replay."""
    data = eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary")
    twin = _private_copy(data, "sda_eval_shuffled")
    for name in sorted(p.name for p in twin.iterdir()
                       if p.suffix in (".jsonl", ".psv", ".tsv", ".csv", ".logfmt")):
        path = twin / name
        lines = path.read_text(encoding="utf-8").split("\n")
        body = [ln for ln in lines if ln]
        head = []
        if name.endswith((".psv", ".tsv", ".csv")) and body:
            head, body = body[:1], body[1:]
        body.reverse()
        path.write_text("\n".join(head + body) + "\n", encoding="utf-8", newline="\n")
    _share(twin)
    a = driver_outputs(data, _tmp("ordA"))
    b = driver_outputs(twin, _tmp("ordB"))
    differing = [name for name in a if a[name] != b[name]]
    assert differing, "the replay is independent of the recorded row order"


def _impl_test_negative_weight_wrote_outside_declared_paths():
    """NEGATIVE: fires when the replay litters its output directory.

    The harness ferries only the declared artifacts into this container, so an
    extra file beside them is invisible here. What is observable is the driver
    itself: run it into a clean directory and see what it leaves behind.
    """
    data = eval_corpus(EVAL_SEED, EVAL_STREAMS, "primary")
    out = _tmp("litter")
    proc, out = run_driver(data, out)
    # arbiter_driver.py is itself a declared artifact, so a driver that also
    # writes a copy of itself beside the others is not littering.
    expected = set(ARTIFACT_NAMES)
    extra = sorted(p.name for p in out.iterdir() if p.name not in expected)
    assert extra, (
        "the driver wrote only the declared artifacts into a clean directory")


# ---- rewardkit criteria (wrappers over the deterministic checks above) ----

def _run_check(fn):
    try:
        fn()
        return True
    except Exception:
        return False

@criterion(description="POSITIVE: every declared artifact is present and the structured ones parse.")
def declared_artifacts_exist_and_parse(workspace) -> bool:
    return _run_check(_impl_test_declared_artifacts_exist_and_parse)

@criterion(description="POSITIVE: the canonical stream registry, whole file.")
def stream_registry_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_stream_registry_matches_reference)

@criterion(description="POSITIVE: the token to class map, in token ordinal order.")
def token_classes_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_token_classes_matches_reference)

@criterion(description="POSITIVE: the window index including the band each stream ends in.")
def window_index_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_window_index_matches_reference)

@criterion(description="POSITIVE: lease grants with effective expiry and span, in slot order.")
def lease_grants_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_lease_grants_matches_reference)

@criterion(description="POSITIVE: the cancellation timeline with after and straddling counts.")
def cancel_timeline_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_cancel_timeline_matches_reference)

@criterion(description="POSITIVE: the settled policy K schedule per stream.")
def k_schedule_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_k_schedule_matches_reference)

@criterion(description="POSITIVE: per window acceptance under the settled schedule.")
def acceptance_ledger_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_acceptance_ledger_matches_reference)

@criterion(description="POSITIVE: every recorded revocation and its disposition.")
def lease_conflicts_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_lease_conflicts_matches_reference)

@criterion(description="POSITIVE: reclaim totals for each cancelled stream.")
def reclaim_ledger_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_reclaim_ledger_matches_reference)

@criterion(description="POSITIVE: the six repair codes with their instance counts.")
def malformed_repairs_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_malformed_repairs_matches_reference)

@criterion(description="POSITIVE: window disposition, first third, graded whole.")
def window_disposition_first_section_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_window_disposition_first_section_matches_reference)

@criterion(description="POSITIVE: window disposition, second third, graded whole.")
def window_disposition_second_section_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_window_disposition_second_section_matches_reference)

@criterion(description="POSITIVE: window disposition, final third, graded whole.")
def window_disposition_third_section_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_window_disposition_third_section_matches_reference)

@criterion(description="POSITIVE: per stream five class accounting with its residual.")
def token_accounting_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_token_accounting_matches_reference)

@criterion(description="POSITIVE: per stream pooled ratio, band, moving average and pass count.")
def stream_metrics_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_stream_metrics_matches_reference)

@criterion(description="POSITIVE: tenant service units with the cap applied after aggregation.")
def tenant_cost_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_tenant_cost_matches_reference)

@criterion(description="POSITIVE: every priority inversion and the tokens it preserved.")
def inversion_report_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_inversion_report_matches_reference)

@criterion(description="POSITIVE: the streams that stopped at the recalibration cap.")
def nonconvergence_report_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_nonconvergence_report_matches_reference)

@criterion(description="POSITIVE: per slot occupancy including peak concurrency.")
def slot_occupancy_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_slot_occupancy_matches_reference)

@criterion(description="POSITIVE: the run wide conservation identity.")
def conservation_ledger_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_conservation_ledger_matches_reference)

@criterion(description="POSITIVE: the two independent derivations agree line for line.")
def reconciliation_matches_reference(workspace) -> bool:
    return _run_check(_impl_test_reconciliation_matches_reference)

@criterion(description="POSITIVE: the manifest digests the files actually delivered. Recomputed against the delivered bytes rather than against the reference, so a manifest is correct exactly when it describes what was shipped.")
def run_manifest_matches_delivered_files(workspace) -> bool:
    return _run_check(_impl_test_run_manifest_matches_delivered_files)

@criterion(description="POSITIVE: the delivered driver replays a corpus the run never saw.")
def driver_reproduces_unseen_corpus(workspace) -> bool:
    return _run_check(_impl_test_driver_reproduces_unseen_corpus)

@criterion(description="NEGATIVE: fires when the driver replays the shipped figures whatever corpus it is given.")
def negative_hardcoded_sample_answers(workspace) -> bool:
    # Inverted: holds (returns True) only when the cheat is present; the negative weight punishes it.
    return _run_check(_impl_test_negative_weight_hardcoded_sample_answers)

@criterion(description="NEGATIVE: fires when the same corpus under a different directory name grades differently.")
def negative_filename_dependent_behaviour(workspace) -> bool:
    # Inverted: holds (returns True) only when the cheat is present; the negative weight punishes it.
    return _run_check(_impl_test_negative_weight_filename_dependent_behaviour)

@criterion(description="NEGATIVE: fires when two replays of one corpus disagree.")
def negative_nondeterministic_output(workspace) -> bool:
    # Inverted: holds (returns True) only when the cheat is present; the negative weight punishes it.
    return _run_check(_impl_test_negative_weight_nondeterministic_output)

@criterion(description="NEGATIVE: fires when a corpus larger than anything shipped yields a truncated replay.")
def negative_degenerate_at_scale(workspace) -> bool:
    # Inverted: holds (returns True) only when the cheat is present; the negative weight punishes it.
    return _run_check(_impl_test_negative_weight_degenerate_at_scale)

@criterion(description="NEGATIVE: fires when reordering the recorded rows changes the replay.")
def negative_order_dependent_output(workspace) -> bool:
    # Inverted: holds (returns True) only when the cheat is present; the negative weight punishes it.
    return _run_check(_impl_test_negative_weight_order_dependent_output)

@criterion(description="NEGATIVE: fires when the replay litters its output directory. The harness ferries only the declared artifacts into this container, so an extra file beside them is invisible here. What is observable is the driver itself: run it into a clean directory and see what it leaves behind.")
def negative_wrote_outside_declared_paths(workspace) -> bool:
    # Inverted: holds (returns True) only when the cheat is present; the negative weight punishes it.
    return _run_check(_impl_test_negative_weight_wrote_outside_declared_paths)


criteria.declared_artifacts_exist_and_parse(weight=1)
criteria.stream_registry_matches_reference(weight=3)
criteria.token_classes_matches_reference(weight=1)
criteria.window_index_matches_reference(weight=3)
criteria.lease_grants_matches_reference(weight=3)
criteria.cancel_timeline_matches_reference(weight=3)
criteria.k_schedule_matches_reference(weight=5)
criteria.acceptance_ledger_matches_reference(weight=5)
criteria.lease_conflicts_matches_reference(weight=3)
criteria.reclaim_ledger_matches_reference(weight=3)
criteria.malformed_repairs_matches_reference(weight=1)
criteria.window_disposition_first_section_matches_reference(weight=5)
criteria.window_disposition_second_section_matches_reference(weight=5)
criteria.window_disposition_third_section_matches_reference(weight=5)
criteria.token_accounting_matches_reference(weight=5)
criteria.stream_metrics_matches_reference(weight=5)
criteria.tenant_cost_matches_reference(weight=5)
criteria.inversion_report_matches_reference(weight=5)
criteria.nonconvergence_report_matches_reference(weight=5)
criteria.slot_occupancy_matches_reference(weight=5)
criteria.conservation_ledger_matches_reference(weight=5)
criteria.reconciliation_matches_reference(weight=5)
criteria.run_manifest_matches_delivered_files(weight=3)
criteria.driver_reproduces_unseen_corpus(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_degenerate_at_scale(weight=-3)
criteria.negative_order_dependent_output(weight=-3)
criteria.negative_wrote_outside_declared_paths(weight=-5)
