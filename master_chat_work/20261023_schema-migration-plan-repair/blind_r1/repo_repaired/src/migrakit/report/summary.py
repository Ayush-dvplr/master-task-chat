"""Run summary built from pipeline records."""

from __future__ import annotations

from collections import Counter

from ..parser.contracts import Registry
from .classify import category_of


def _partner_order(registry: Registry, partner_ids: set[str]) -> list[str]:
    ranked = sorted((pid for pid in partner_ids if pid in registry.partner_rank), key=lambda pid: (registry.partner_rank[pid], pid))
    unranked = sorted(pid for pid in partner_ids if pid not in registry.partner_rank)
    return ranked + unranked


def build_summary(registry: Registry, records: list[dict], invalid_corrections: list[str] | tuple = ()) -> dict:
    by_status = Counter(record["status"] for record in records)
    by_code = Counter(record["code"] for record in records if record["code"] is not None)
    by_category = {name: 0 for name, _ in registry.taxonomy}
    for record in records:
        try:
            name = category_of(registry, record["status"], record["code"])
        except ValueError:
            continue
        by_category[name] += 1
    per_partner: dict[str, Counter] = {}
    for record in records:
        if record["partner"] is not None:
            per_partner.setdefault(record["partner"], Counter())[record["status"]] += 1
    partners = [
        {
            "partner": pid,
            "records": sum(per_partner[pid].values()),
            "migrated": per_partner[pid]["migrated"],
            "failed": per_partner[pid]["failed"],
        }
        for pid in _partner_order(registry, set(per_partner))
    ]
    return {
        "records": len(records),
        "attempted": sum(1 for record in records if record["attempted"]),
        "by_status": dict(sorted(by_status.items())),
        "by_code": dict(sorted(by_code.items())),
        "by_category": by_category,
        "invalid_corrections": sorted(set(invalid_corrections)),
        "partners": partners,
    }
