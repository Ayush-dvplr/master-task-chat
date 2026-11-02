"""Audit, summary and profile documents built from a compiled corpus."""

from __future__ import annotations

import wtime
from engine import CLASSES, Compiler
import policy

PROFILES = ("dev", "prod")


def profile_doc(result: dict) -> dict:
    return {key: wtime.fmt(value) for key, (value, _) in sorted(result["profile"].items())}


def build(corpus, config: dict) -> tuple[Compiler, dict]:
    _, journal_rejects, journal_stats = policy.resolve(corpus)
    comp = Compiler(corpus, config, journal_rejects)
    results = {env: comp.compile(env) for env in PROFILES}
    comp.journal_stats = journal_stats
    return comp, results


def audit_doc(comp: Compiler, results: dict) -> dict:
    rejects = list(comp.led.rejects) + list(comp.journal_rejects)
    self_check = {}
    for src, counts in comp.led.counts.items():
        entry = {cls: counts[cls] for cls in CLASSES}
        entry["records"] = sum(counts.values())
        self_check[src] = entry
    js = comp.journal_stats
    self_check[policy.JOURNAL_SRC] = {k: js[k] for k in ("records",) + CLASSES}
    return {
        "rejects": [
            {"source": s, "record": r, "reason": why} for s, r, why in sorted(set(rejects))
        ],
        "unresolved": [
            {"source": s, "record": r, "reason": why} for s, r, why in sorted(set(comp.led.unresolved))
        ],
        "held_grants": [
            {"profile": env, "ticket": t, "reason": why} for env, t, why in sorted(comp.held)
        ],
        "unattested": [
            {"profile": env, "principal": p, "permission": perm}
            for env in PROFILES for (_, p, perm) in sorted(results[env]["unattested"])
        ],
        "sod": [
            {"profile": env, "principal": p, "rule": rule, "outcome": outcome, "permission": perm}
            for env in PROFILES
            for (_, p, rule, outcome, perm) in sorted(results[env]["sod"], key=lambda x: (x[1], x[2]))
        ],
        "self_check": dict(sorted(self_check.items())),
    }


def summary_doc(corpus, comp: Compiler, results: dict, audit: dict) -> dict:
    profiles, eligibility, grants = {}, {}, {}
    for env in PROFILES:
        prof = results[env]["profile"]
        profiles[env] = {
            "keys": len(prof),
            "principals": len({k.split("|", 1)[0] for k in prof}),
            "open_keys": sum(1 for v, _ in prof.values() if v >= wtime.INF),
            "breakglass_keys": sum(1 for _, bg in prof.values() if bg),
        }
        counts = {"eligible": 0, "inactive": 0, "disabled": 0, "mfa_blocked": 0}
        for state in results[env]["eligibility"].values():
            counts[state] += 1
        eligibility[env] = counts
        grants[env] = {
            "active": results[env]["active"],
            "pending": sum(1 for e, _, why in comp.held if e == env and why == "pending"),
            "vetoed": sum(1 for e, _, why in comp.held if e == env and why == "vetoed"),
        }
    inputs = sorted(p.name for p in corpus.root.iterdir() if p.is_file())
    return {
        "as_of": comp.cfg["as_of"],
        "recorded_cutoff": comp.cfg["recorded_cutoff"],
        "profiles": profiles,
        "eligibility": eligibility,
        "grants": grants,
        "audit_counts": {name: len(audit[name]) for name in ("rejects", "unresolved", "held_grants", "unattested", "sod")},
        "inputs": inputs,
        "input_count": len(inputs),
    }
