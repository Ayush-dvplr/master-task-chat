from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import {{PACKAGE_NAME}}


class PackageSmokeTests(unittest.TestCase):
    def test_version_and_batch_summary(self):
        self.assertEqual({{PACKAGE_NAME}}.__version__, "{{REQUIRED_VERSION}}")
        entries = [
            {"name": "alpha", "expected": 100, "observed": 100, "seconds": 3},
            {"name": "beta", "expected": 100, "observed": 130, "seconds": 40, "critical": True},
        ]
        summary = {{PACKAGE_NAME}}.summarize(entries)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["items"][0]["bucket"], "ok")
        self.assertEqual(summary["items"][1]["bucket"], "critical")

    def test_load_manifest_and_report(self):
        text = "[[entries]]\nname='gamma'\nexpected=80\nobserved=82\nseconds=4\n"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.toml"
            path.write_text(text)
            doc = {{PACKAGE_NAME}}.load_manifest(path)
        report = {{PACKAGE_NAME}}.render_report(doc["entries"])
        self.assertIn("{{FORMAT_TAG}} manifest report", report)
        self.assertIn("gamma: ok", report)


if __name__ == "__main__":
    unittest.main()
