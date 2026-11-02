"""End-to-end run: feed lines in, one record per line out."""

from __future__ import annotations

import csv
from pathlib import Path

from .core.executor import execute_plan
from .core.fingerprint import record_fingerprint
from .core.planner import plan_migration
from .errors import MigrationError
from .parser.contracts import Registry, load_contracts
from .parser.corrections import Correction, parse_corrections
from .parser.feed import FeedLine, read_feed
from .parser.identity import resolve_partner
from .report.classify import classify_result
from .report.summary import build_summary


def _read_manifest(path: str | Path) -> tuple[dict[str, int], dict[str, tuple[int, str]]]:
    """Return each batch's received_seq and its receipt (lines, fp_xor)."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    received = {row["batch_id"]: int(row["received_seq"]) for row in rows}
    receipts = {row["batch_id"]: (int(row["lines"]), row["fp_xor"]) for row in rows}
    return received, receipts


def _blank_record(line: int, document: dict | None) -> dict:
    document = document or {}
    return {
        "line": line,
        "batch": document.get("batch"),
        "partner": None,
        "key": document.get("key"),
        "status": "rejected",
        "code": None,
        "schema": document.get("schema"),
        "plan": None,
        "completed_steps": 0,
        "failed_edge": None,
        "payload": None,
        "attempted": False,
        "fingerprint": None,
    }


def _replace_tokens(payload: dict, tokens: tuple[str, ...]) -> dict:
    """Replace the partner's null tokens with explicit nulls; a value must equal a token exactly."""
    return {name: (None if isinstance(value, str) and value in tokens else value) for name, value in payload.items()}


def _receipt_mismatches(items: list[FeedLine], receipts: dict[str, tuple[int, str]]) -> list[str]:
    """Batches whose lines or fingerprint XOR differ from the manifest receipt."""
    counts: dict[str, int] = {}
    xors: dict[str, int] = {}
    for item in items:
        document = item.record
        if document is None or document["batch"] not in receipts:
            continue
        batch = document["batch"]
        counts[batch] = counts.get(batch, 0) + 1
        fingerprint = record_fingerprint(document["schema"], document["payload"])
        xors[batch] = xors.get(batch, 0) ^ int(fingerprint[:8], 16)
    return sorted(
        batch
        for batch, (lines, fp_xor) in receipts.items()
        if counts.get(batch, 0) != lines or f"{xors.get(batch, 0):08x}" != fp_xor
    )


def _ordered(lines: list[FeedLine], received: dict[str, int]) -> list[FeedLine]:
    """Processing order of the admitted lines."""
    return sorted(lines, key=lambda item: (received[item.record["batch"]], item.line))


class _Run:
    def __init__(self, registry: Registry, corrections: list[Correction]) -> None:
        self.registry = registry
        self.invalid: set[str] = set()
        self.steps: dict[tuple[str, str], list[Correction]] = {}
        self.reissues: dict[tuple[str, str], list[Correction]] = {}
        for correction in corrections:
            try:
                partner_id = resolve_partner(registry, correction.partner)
            except MigrationError:
                self.invalid.add(correction.correction_id)
                continue
            target = self.reissues if correction.op == "REISSUE" else self.steps
            target.setdefault((partner_id, correction.key), []).append(correction)
        self.holders: dict[tuple[str, str], dict] = {}
        self.fingerprints: dict[tuple[str, str], set[str]] = {}
        self.used: set[str] = set()

    def _admit(self, item: FeedLine) -> dict:
        document = item.record
        record = _blank_record(item.line, document)
        try:
            partner_id = resolve_partner(self.registry, document["partner"])
        except MigrationError as exc:
            record["code"] = exc.code
            return record
        record["partner"] = partner_id
        fingerprint = record_fingerprint(document["schema"], document["payload"])
        record["fingerprint"] = fingerprint
        identity = (partner_id, document["key"])
        self.fingerprints.setdefault(identity, set()).add(fingerprint)
        holder = self.holders.get(identity)
        if holder is not None:
            if holder["fingerprint"] == fingerprint:
                record["status"] = "replayed"
                return record
            if not any(fingerprint.startswith(r.fingerprint_prefix) for r in self.reissues.get(identity, ())):
                record["code"] = "E_REPLAY_CONFLICT"
                return record
            holder.update(status="superseded", code=None, payload=None)
        self.holders[identity] = record
        self._migrate(record, document, identity)
        return record

    def _migrate(self, record: dict, document: dict, identity: tuple[str, str]) -> None:
        payload = _replace_tokens(document["payload"], self.registry.tokens_for(identity[0]))
        try:
            plan = plan_migration(self.registry, document["schema"], payload)
        except MigrationError as exc:
            record["code"] = exc.code
            return
        steps = [correction.as_step() for correction in self.steps.get(identity, ())]
        result = execute_plan(self.registry, document["schema"], payload, plan, steps)
        self.used.update(result["corrections_applied"])
        status, code = classify_result(plan, result)
        record.update(
            status=status,
            code=code,
            schema=result["schema"],
            plan=plan,
            completed_steps=result["completed_steps"],
            failed_edge=result["failed_edge"],
            payload=result["payload"],
            attempted=True,
        )

    def unused_corrections(self) -> set[str]:
        unused = {c.correction_id for group in self.steps.values() for c in group if c.correction_id not in self.used}
        for identity, group in self.reissues.items():
            seen = self.fingerprints.get(identity, set())
            for correction in group:
                if not any(fp.startswith(correction.fingerprint_prefix) for fp in seen):
                    unused.add(correction.correction_id)
        return unused


def run_pipeline(contracts: str | Path, feed: str | Path, corrections: str | Path, manifest: str | Path) -> tuple[list[dict], dict]:
    """Process every feed line; return the records in line order and the run summary."""
    registry = load_contracts(contracts)
    received, receipts = _read_manifest(manifest)
    parsed, malformed = parse_corrections(Path(corrections).read_text(encoding="utf-8"))
    run = _Run(registry, parsed)
    records: dict[int, dict] = {}
    admitted: list[FeedLine] = []
    items = read_feed(feed)
    for item in items:
        if item.record is None or item.record["batch"] not in received:
            rejected = _blank_record(item.line, None)
            rejected["code"] = "E_PARSE"
            records[item.line] = rejected
        else:
            admitted.append(item)
    for item in _ordered(admitted, received):
        records[item.line] = run._admit(item)
    ordered_records = [records[line] for line in sorted(records)]
    invalid = set(malformed) | run.invalid | run.unused_corrections()
    summary = build_summary(registry, ordered_records, sorted(invalid))
    summary["receipt_mismatches"] = _receipt_mismatches(items, receipts)
    return ordered_records, summary
