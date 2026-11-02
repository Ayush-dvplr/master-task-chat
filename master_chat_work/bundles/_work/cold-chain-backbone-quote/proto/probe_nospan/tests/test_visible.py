import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from task import core, parser, report

SRC = Path(__file__).resolve().parents[1] / "src"

CHAIN = {
    "case": "V0001",
    "sites": [
        {"site": "S900", "role": "depot", "charge": 3, "position": 0},
        {"site": "S101", "role": "cold_room", "charge": 4, "position": 1},
        {"site": "S102", "role": "relay", "charge": 5, "position": 2},
        {"site": "S103", "role": "cold_room", "charge": 6, "position": 3},
    ],
    "links": [
        {"link": "L01", "a": "S900", "b": "S101", "cost": 7},
        {"link": "L02", "a": "S101", "b": "S102", "cost": 2},
        {"link": "L03", "a": "S102", "b": "S103", "cost": 2},
        {"link": "L04", "a": "S101", "b": "S103", "cost": 12},
    ],
}


def write_book(root: Path, slots=(1, 2, 3), overrides="", closed=()):
    (root / "sites.csv").write_text(
        "project,site,role,class\n"
        "P0001,S900,depot,yard\n"
        "P0001,S101,cold_room,store\n"
        "P0001,S102,relay,hut\n"
        "P0001,S103,cold_room,store\n",
        encoding="utf-8",
    )
    rows = ["project\tsite\tcorridor\tslot"]
    for site, slot in zip(("S101", "S102", "S103"), slots):
        rows.append(f"P0001\t{site}\tmill\t{slot}")
    (root / "layout.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    links = [
        ("L01", "S900", "S101", 1),
        ("L02", "S101", "S102", 1),
        ("L03", "S102", "S103", 1),
    ]
    with (root / "links.jsonl").open("w", encoding="utf-8") as handle:
        for lid, a, b, km in links:
            handle.write(json.dumps({"project": "P0001", "link": lid, "a": a, "b": b, "band": "B1", "km": km}) + "\n")
    closed_list = ", ".join(f'"{lid}"' for lid in closed)
    (root / "access_rules.toml").write_text(
        '[corridors]\norder = ["mill"]\n\n[tariff.B1]\nbase = 2\nper_km = 3\n\n'
        f"[closed]\nlinks = [{closed_list}]\n",
        encoding="utf-8",
    )
    (root / "activation.ini").write_text(
        "[classes]\nyard = 3\nstore = 4\nhut = 5\n\n[overrides]\n" + overrides,
        encoding="utf-8",
    )


class VisibleTests(unittest.TestCase):
    def test_chain_quote(self):
        project = parser.load_inline(CHAIN)
        network = core.best_network(project)
        self.assertEqual(network.links, ("L01", "L02", "L03"))
        self.assertEqual(network.quote, 29)

    def test_site_line_charges_once(self):
        case = {
            "case": "V0002",
            "sites": [
                {"site": "S900", "role": "depot", "charge": 3, "position": 0},
                {"site": "S101", "role": "cold_room", "charge": 4, "position": 1},
                {"site": "S102", "role": "cold_room", "charge": 5, "position": 2},
            ],
            "links": [
                {"link": "L01", "a": "S900", "b": "S102", "cost": 7},
                {"link": "L02", "a": "S101", "b": "S102", "cost": 2},
            ],
        }
        project = parser.load_inline(case)
        network = core.best_network(project)
        self.assertEqual(network.quote, 21)
        self.assertEqual(core.site_lines(project, network.links), {0: 3, 1: 4, 2: 14})

    def test_tie_goes_to_the_smaller_vector(self):
        case = {
            "case": "V0003",
            "sites": [
                {"site": "S900", "role": "depot", "charge": 1, "position": 0},
                {"site": "S101", "role": "cold_room", "charge": 1, "position": 1},
                {"site": "S102", "role": "relay", "charge": 1, "position": 2},
            ],
            "links": [
                {"link": "L01", "a": "S900", "b": "S101", "cost": 5},
                {"link": "L02", "a": "S900", "b": "S102", "cost": 2},
                {"link": "L03", "a": "S102", "b": "S101", "cost": 2},
            ],
        }
        network = core.best_network(parser.load_inline(case))
        self.assertEqual(network.quote, 7)
        self.assertEqual(network.links, ("L02", "L03"))

    def test_cli_writes_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            book, out = Path(tmp, "book"), Path(tmp, "out")
            book.mkdir()
            write_book(book)
            subprocess.run(
                [sys.executable, "-m", "task", "--book", str(book), "--out", str(out)],
                check=True,
                env={"PYTHONPATH": str(SRC)},
            )
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, ["module_core.json", "module_parser.json", "module_report.json", "summary.json"])

    def test_slot_order_is_numeric(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_book(Path(tmp), slots=(8, 9, 10))
            project = parser.load_book(tmp)["projects"]["P0001"]
            self.assertEqual(project.ids, ["S900", "S101", "S102", "S103"])

    def test_activation_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_book(Path(tmp), overrides="P0001/S102 = 1\n")
            project = parser.load_book(tmp)["projects"]["P0001"]
            self.assertEqual(project.charges[2], 1)

    def test_closed_link_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_book(Path(tmp), closed=("L02",))
            book = parser.load_book(tmp)
            self.assertEqual(book["rejected"]["P0001"], "E_NO_NETWORK")

    def test_share_rounds_down(self):
        self.assertEqual(report.share_bp(2, 3), 6666)


if __name__ == "__main__":
    unittest.main()
