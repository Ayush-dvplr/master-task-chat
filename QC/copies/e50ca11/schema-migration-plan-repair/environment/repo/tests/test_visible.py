"""Visible regression tests. Run from the repository root:

    PYTHONPATH=src python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import migrakit  # noqa: E402

SCHEMAS = {
    "schemas": [
        {"id": "ledger.v1", "domain": "ledger", "canonical": False},
        {"id": "ledger.v2", "domain": "ledger", "canonical": False},
        {"id": "ledger.v3", "domain": "ledger", "canonical": True},
    ]
}
EDGES = [
    "edge_id,source,target,requires,operations,cost",
    "L01,ledger.v1,ledger.v2,has:amt,rename:amt>amount,2",
    "L02,ledger.v2,ledger.v3,,cast:amount:int,1",
]
POLICY = ["domain\tfield\tdefault\tfill\tnull_counts_as", "ledger\tcurrency\t\"EUR\"\t\t"]
INI = "[presence]\nexplicit_null = present\n[fill]\nmode = absent_only\n[tokens]\ndefault = NULL|N/A\n"
ALIASES = (
    '<partners>\n  <partner id="P001"><alias>north-books</alias></partner>\n'
    '  <partner id="P002"><alias>south-books</alias></partner>\n</partners>\n'
)
TAXONOMY = {
    "categories": [
        {"name": "complete", "members": ["migrated"]},
        {"name": "duplicate", "members": ["replayed", "superseded"]},
        {"name": "execution_failure", "members": ["E_PREREQ_FAILED"]},
        {"name": "conflict", "members": ["E_REPLAY_CONFLICT"]},
        {"name": "input_error", "members": ["E_PARSE", "E_UNKNOWN_PARTNER", "E_ALIAS_CYCLE"]},
        {"name": "planning_error", "members": ["E_UNKNOWN_SCHEMA", "E_UNREACHABLE"]},
    ]
}


def write_contracts(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "schema_versions.json").write_text(json.dumps(SCHEMAS), encoding="utf-8")
    (folder / "migration_edges.csv").write_text("\n".join(EDGES) + "\n", encoding="utf-8")
    (folder / "field_policy.tsv").write_text("\n".join(POLICY) + "\n", encoding="utf-8")
    (folder / "null_semantics.ini").write_text(INI, encoding="utf-8")
    (folder / "partner_aliases.xml").write_text(ALIASES, encoding="utf-8")
    (folder / "report_taxonomy.json").write_text(json.dumps(TAXONOMY), encoding="utf-8")
    (folder / "partner_order.tsv").write_text("partner_id\trank\nP002\t1\nP001\t2\n", encoding="utf-8")


class VisibleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = Path(tempfile.mkdtemp(prefix="migrakit-visible-"))
        write_contracts(self.scratch / "contracts")
        self.registry = migrakit.load_contracts(self.scratch / "contracts")

    def test_one_edge_plan(self) -> None:
        self.assertEqual(migrakit.plan_migration(self.registry, "ledger.v2", {"amount": "4"}), ["L02"])

    def test_rename_then_cast_execution(self) -> None:
        plan = migrakit.plan_migration(self.registry, "ledger.v1", {"amt": "12"})
        result = migrakit.execute_plan(self.registry, "ledger.v1", {"amt": "12"}, plan, [])
        self.assertEqual(result["status"], "migrated")
        self.assertEqual(result["payload"], {"amount": 12})

    def test_signature_without_nulls(self) -> None:
        signature = migrakit.state_signature(self.registry, "ledger.v1", {"amt": 3, "memo": "x"})
        self.assertEqual(signature, {"amt": "value"})

    def test_single_hop_alias(self) -> None:
        self.assertEqual(migrakit.resolve_partner(self.registry, "south-books"), "P002")

    def test_unknown_schema_code(self) -> None:
        with self.assertRaises(migrakit.MigrationError) as caught:
            migrakit.plan_migration(self.registry, "ledger.v9", {})
        self.assertEqual(caught.exception.code, "E_UNKNOWN_SCHEMA")

    def test_empty_plan_at_target(self) -> None:
        self.assertEqual(migrakit.plan_migration(self.registry, "ledger.v3", {"amount": 1}), [])

    def test_fingerprint_stable(self) -> None:
        first = migrakit.record_fingerprint("ledger.v1", {"b": 1, "a": [1, 2]})
        second = migrakit.record_fingerprint("ledger.v1", {"a": [1, 2], "b": 1})
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_module_entry_help(self) -> None:
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        done = subprocess.run([sys.executable, "-m", "migrakit", "--help"], capture_output=True, text=True, env=env, cwd=self.scratch)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_cli_runs_from_other_folder(self) -> None:
        feed = self.scratch / "feed.jsonl"
        feed.write_text(
            json.dumps({"batch": "B1", "partner": "north-books", "key": "k1", "schema": "ledger.v1", "payload": {"amt": "5"}}) + "\n",
            encoding="utf-8",
        )
        (self.scratch / "corrections.txt").write_text("# none\n", encoding="utf-8")
        (self.scratch / "manifest.csv").write_text("batch_id,received_seq,lines,fp_xor\nB1,1,1,db4e5a9d\n", encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        script = "import sys; from migrakit.cli import main; sys.exit(main(sys.argv[1:]))"
        args = ["run", "--contracts", "contracts", "--feed", "feed.jsonl", "--corrections", "corrections.txt", "--manifest", "manifest.csv", "--out", "out"]
        done = subprocess.run([sys.executable, "-c", script, *args], capture_output=True, text=True, env=env, cwd=self.scratch)
        self.assertEqual(done.returncode, 0, done.stderr)
        record = json.loads((self.scratch / "out" / "records.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "migrated")
        self.assertEqual(record["payload"], {"amount": 5})


if __name__ == "__main__":
    unittest.main()
