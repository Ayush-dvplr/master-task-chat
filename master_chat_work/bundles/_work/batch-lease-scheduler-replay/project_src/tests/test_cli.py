import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest

import bookfix
import leasebook

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)


class CliTest(unittest.TestCase):
    def test_version_matches_project(self):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertEqual(leasebook.__version__, project["version"])

    def test_main_writes_four_documents(self):
        out = tempfile.mkdtemp()
        self.assertEqual(leasebook.main([bookfix.write_book(), out]), 0)
        names = sorted(os.listdir(out))
        self.assertEqual(names, ["dependency_resolution.json", "module_core.json",
                                 "module_metrics.json", "summary.json"])
        with open(os.path.join(out, "summary.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["set_count"], 1)

    def test_module_entry_point(self):
        out = tempfile.mkdtemp()
        env = dict(os.environ, PYTHONPATH=bookfix.SRC)
        done = subprocess.run([sys.executable, "-m", "leasebook", bookfix.write_book(), out],
                              env=env, capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(os.path.isfile(os.path.join(out, "module_core.json")))

    def test_refusal_prints_one_line(self):
        root = bookfix.write_book()
        os.remove(os.path.join(root, "pools.json"))
        out = os.path.join(tempfile.mkdtemp(), "out")
        env = dict(os.environ, PYTHONPATH=bookfix.SRC)
        done = subprocess.run([sys.executable, "-m", "leasebook", root, out],
                              env=env, capture_output=True, text=True, check=False)
        self.assertEqual((done.returncode, done.stdout), (2, "ERROR MISSING_INPUT pools.json\n"))
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
