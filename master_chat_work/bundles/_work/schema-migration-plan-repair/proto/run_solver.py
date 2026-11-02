"""Scratch: run one solver repo (optionally patched into a generic variant) on prototype corpora.

    python3 -B run_solver.py REPO_SRC CORPORA_DIR VARIANT

VARIANT: plain | name_keyed | end_resolve | file_order | greedy | exhaustive
Prints one line per corpus: name, seconds, whole-document ok, records differing.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import migrakit  # noqa: E402
from migrakit import pipeline  # noqa: E402

VARIANT = sys.argv[3]


def _patch() -> None:
    if VARIANT == "file_order":
        pipeline._ordered = lambda lines, received: sorted(lines, key=lambda item: item.line)
    elif VARIANT == "name_keyed":
        original_admit = pipeline._Run._admit
        original_init = pipeline._Run.__init__

        def init(self, registry, corrections):
            original_init(self, registry, corrections)
            self.steps, self.reissues = {}, {}
            for correction in corrections:
                if correction.correction_id in self.invalid:
                    continue
                target = self.reissues if correction.op == "REISSUE" else self.steps
                target.setdefault((correction.partner, correction.key), []).append(correction)

        def admit(self, item):
            # holders and corrections keyed by the partner text as written, not the resolved partner
            real = pipeline.resolve_partner
            try:
                pipeline.resolve_partner = lambda registry, value: (real(registry, value), value)[1]
                record = original_admit(self, item)
            finally:
                pipeline.resolve_partner = real
            if record.get("partner") is not None:
                record["partner"] = real(self.registry, record["partner"])
            return record

        pipeline._Run.__init__ = init
        pipeline._Run._admit = admit
    elif VARIANT == "end_resolve":
        from migrakit.core import executor
        original = executor.execute_plan

        def late(registry, schema_id, payload, plan, corrections):
            result = original(registry, schema_id, payload, plan, [])
            if result["status"] == "migrated":
                for correction in corrections:
                    executor._apply_correction(result["payload"], correction)
                    result["corrections_applied"].append(correction["id"])
            return result

        pipeline.execute_plan = late
    elif VARIANT == "greedy":
        from migrakit.core import planner
        from migrakit.core.records import FieldView, edge_allowed
        from migrakit.core.operations import apply_operations
        from migrakit.errors import MigrationError

        def greedy(registry, schema_id, payload):
            domain = registry.domain_of(schema_id)
            target = registry.canonical[domain]
            here, record, plan, seen = schema_id, dict(payload), [], set()
            while here != target:
                options = sorted((e.cost, e.edge_id, e) for e in registry.edges.values()
                                 if e.source == here and edge_allowed(registry, domain, FieldView.from_payload(record), e))
                options = [o for o in options if (o[1], json.dumps(record, sort_keys=True)) not in seen]
                if not options or len(plan) >= 80:
                    raise MigrationError("E_UNREACHABLE", schema_id)
                cost, edge_id, edge = options[0]
                seen.add((edge_id, json.dumps(record, sort_keys=True)))
                record = apply_operations(registry, domain, record, edge.operations)
                plan.append(edge_id)
                here = edge.target
            return plan

        pipeline.plan_migration = greedy


def main() -> None:
    _patch()
    for folder in sorted(Path(sys.argv[2]).iterdir()):
        if not (folder / "job.json").exists():
            continue
        job = json.loads((folder / "job.json").read_text())
        expected = json.loads((folder / "expected.json").read_text())
        start = time.time()
        try:
            records, summary = migrakit.run_pipeline(job["contracts"], job["feed"], job["corrections"], job["manifest"])
        except Exception as exc:  # scratch: report crashes as a line
            print(folder.name, f"{time.time() - start:.2f}s", "CRASH", type(exc).__name__, str(exc)[:120])
            continue
        took = time.time() - start
        got = json.loads(json.dumps(records, sort_keys=True))
        diff = sum(1 for x, y in zip(got, expected["records"]) if json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True))
        same_summary = json.dumps(summary, sort_keys=True) == json.dumps(expected["summary"], sort_keys=True)
        ok = diff == 0 and len(got) == len(expected["records"]) and same_summary
        print(folder.name, f"{took:.2f}s", "OK" if ok else "BAD", f"rows_diff={diff}/{len(got)}", f"summary={'ok' if same_summary else 'diff'}")


if __name__ == "__main__":
    main()
