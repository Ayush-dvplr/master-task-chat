import unittest
from decimal import Decimal

from helios_close.domain import Ver, caret, cvss_base, parse_canon_ver, severity_of, canon_spdx
from helios_close.formats import dec_hours, dec_ts, norm_name, norm_vid, parse_ver


class VersionTests(unittest.TestCase):
    def test_semver_spellings(self):
        self.assertEqual(str(parse_ver("1.4.0rc2")), "1.4.0-rc.2")
        self.assertEqual(str(parse_ver("v2.0.1+build.7")), "2.0.1")
        self.assertEqual(str(parse_ver("3.1.0-RC4")), "3.1.0-rc.4")

    def test_prerelease_numbers(self):
        self.assertTrue(parse_canon_ver("1.4.0-rc.9") < parse_canon_ver("1.4.0-rc.10"))

    def test_caret_zero_minor(self):
        c = caret(parse_canon_ver("0.2.3"))
        self.assertEqual(c.canon(), ">=0.2.3 <0.3.0")


class ScoreTests(unittest.TestCase):
    def test_reference_vectors(self):
        self.assertEqual(cvss_base("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"), Decimal("9.8"))
        self.assertEqual(cvss_base("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:L/A:N"), Decimal("6.4"))
        self.assertEqual(severity_of(Decimal("7.0")), "high")


class CellTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(norm_name("pypi", "Fast_JSON.tools"), "fast-json-tools")
        self.assertEqual(norm_name("maven", "org.acme:JsonKit"), "org.acme:JsonKit")

    def test_ids(self):
        self.assertEqual(norm_vid("cve-2025-123"), "CVE-2025-0123")

    def test_cells(self):
        self.assertEqual(dec_hours("150", "min"), Decimal("2.5"))
        self.assertEqual(dec_ts("2025-08-14 14:05:00", "naive:IE"), 1755176700)
        self.assertEqual(canon_spdx("mit or gpl-2.0+"), "MIT OR GPL-2.0-or-later")


if __name__ == "__main__":
    unittest.main()
