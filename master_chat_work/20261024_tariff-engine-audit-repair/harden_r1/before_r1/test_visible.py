import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tariff import build_invoices, render

CARD = {
    "currency": "EUR",
    "plans": {
        "HOME-A": {
            "standing_charge": 18.60,
            "credit_rate": 0.02,
            "tiers": [
                {"up_to": 200, "rate": 0.2153},
                {"up_to": 600, "rate": 0.1877},
                {"up_to": None, "rate": 0.1631},
            ],
        }
    },
}


def _money(value):
    return f"{float(value):.2f}"


def _read(read_id, day, quantity, account="A1", meter="M1"):
    return {"read_id": read_id, "account": account, "meter": meter, "day": day, "quantity": quantity}


def _write_data(root, reads, start="2026-04-01", end="2026-04-30", active_from="2025-01-01",
                active_to="", commitment="500.00"):
    (root / "meter_reads.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reads))
    (root / "accounts.csv").write_text(f"account,meter,active_from,active_to\nA1,M1,{active_from},{active_to}\n")
    (root / "billing_periods.csv").write_text(
        f"account,start,end,plan,commitment\nA1,{start},{end},HOME-A,{commitment}\n")
    (root / "rate_card.json").write_text(json.dumps(CARD))


class InvoiceCase(unittest.TestCase):
    def run_engine(self, reads, **period):
        with tempfile.TemporaryDirectory() as tmp:
            _write_data(Path(tmp), reads, **period)
            return build_invoices(tmp)

    @staticmethod
    def lines(document, kind=None):
        return [(l["meter"], l["kind"], l["tier"], l["units"], _money(l["amount"]))
                for l in document["invoices"][0]["lines"] if kind in (None, l["kind"])]

    def test_single_tier_energy_line(self):
        doc = self.run_engine([_read("R1", "2026-04-03", 120)])
        self.assertEqual(self.lines(doc, "energy"), [("M1", "energy", 1, 120, "25.84")])

    def test_standing_line_full_month(self):
        doc = self.run_engine([_read("R1", "2026-04-03", 120)])
        self.assertEqual(self.lines(doc, "standing"), [("M1", "standing", 0, 30, "18.60")])

    def test_bool_quantity_is_rejected(self):
        doc = self.run_engine([_read("R1", "2026-04-03", True), _read("R2", "2026-04-04", 40)])
        self.assertEqual(doc["exceptions"], [{"read_id": "R1", "account": "A1", "reason": "malformed_quantity"}])
        self.assertEqual(self.lines(doc, "energy"), [("M1", "energy", 1, 40, "8.61")])

    def test_decimal_quantity_is_rejected(self):
        doc = self.run_engine([_read("R1", "2026-04-03", 2.5)])
        self.assertEqual([e["reason"] for e in doc["exceptions"]], ["malformed_quantity"])
        self.assertEqual(self.lines(doc, "energy"), [])

    def test_unknown_meter_is_reported(self):
        doc = self.run_engine([_read("R1", "2026-04-03", 40, meter="M9")])
        self.assertEqual(doc["exceptions"], [{"read_id": "R1", "account": "A1", "reason": "unknown_meter"}])

    def test_read_on_inactive_day(self):
        doc = self.run_engine([_read("R1", "2026-04-05", 40), _read("R2", "2026-04-12", 60)],
                              active_from="2026-04-10")
        self.assertEqual([e["reason"] for e in doc["exceptions"]], ["inactive_meter"])
        self.assertEqual(self.lines(doc, "energy"), [("M1", "energy", 1, 60, "12.92")])

    def test_duplicate_read_keeps_first(self):
        doc = self.run_engine([_read("R1", "2026-04-08", 70), _read("R2", "2026-04-08", 90)])
        self.assertEqual(doc["exceptions"], [{"read_id": "R2", "account": "A1", "reason": "duplicate_read"}])
        self.assertEqual(self.lines(doc, "energy"), [("M1", "energy", 1, 70, "15.07")])

    def test_padded_identifiers_match(self):
        doc = self.run_engine([_read(" R1 ", "2026-04-03", 60, account=" A1 ", meter=" M1 ")])
        self.assertEqual(doc["exceptions"], [])
        self.assertEqual(self.lines(doc, "energy"), [("M1", "energy", 1, 60, "12.92")])

    def test_no_credit_below_commitment(self):
        invoice = self.run_engine([_read("R1", "2026-04-03", 120)])["invoices"][0]
        self.assertEqual(_money(invoice["credit"]), "0.00")
        self.assertEqual(_money(invoice["total"]), _money(invoice["subtotal"]))

    def test_render_round_trips(self):
        doc = self.run_engine([_read("R1", "2026-04-03", 120)])
        self.assertEqual(json.loads(render(doc)), doc)

    def test_cli_prints_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_data(Path(tmp), [_read("R1", "2026-04-03", 120)])
            src = str(Path(__file__).resolve().parents[1] / "src")
            done = subprocess.run([sys.executable, "-m", "tariff", tmp], capture_output=True, text=True,
                                  env=dict(os.environ, PYTHONPATH=src), check=True)
            self.assertEqual([i["account"] for i in json.loads(done.stdout)["invoices"]], ["A1"])

    def test_partial_period_standing_charge(self):
        doc = self.run_engine([_read("R1", "2026-02-20", 80)], start="2026-02-01", end="2026-02-28",
                              active_from="2026-02-15")
        self.assertEqual(self.lines(doc, "standing"), [("M1", "standing", 0, 14, "8.68")])

    def test_commitment_credit_base(self):
        doc = self.run_engine([_read("R1", "2026-04-03", 140), _read("R2", "2026-04-17", 2.5)],
                              commitment="49.00")
        invoice = doc["invoices"][0]
        self.assertEqual(_money(invoice["subtotal"]), "48.74")
        self.assertEqual(_money(invoice["credit"]), "0.99")
        self.assertEqual(_money(invoice["total"]), "47.75")


if __name__ == "__main__":
    unittest.main()
