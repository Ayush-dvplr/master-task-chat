"""Tests for tools/dockfree.py (min plan D-1) using DOCKFREE_FAKE."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "dockfree.py"
GIB = 1024 ** 3
TOTAL = 16746086400  # live Docker VM (15,970 MiB)


class DockFree(unittest.TestCase):
    def run_with(self, containers, need, cpus=2, total=TOTAL):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"total": total, "containers": containers}, f)
        env = dict(os.environ, DOCKFREE_FAKE=f.name)
        r = subprocess.run([sys.executable, str(TOOL), "--need-mb", str(need), "--cpus", str(cpus)],
                           env=env, capture_output=True, text=True)
        os.unlink(f.name)
        return r.returncode, r.stdout.strip()

    def test_empty_docker(self):
        rc, out = self.run_with([], 4096)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "FREE_MB=12898 USED_MB=0 CONTAINERS=0 CPUS=0/12 START=yes")

    def test_memory_full(self):
        conts = [{"mem": 4 * GIB, "cpus": 2}] * 2 + [{"mem": 0, "cpus": 0}]  # 4+4+4 (no limit = 4096)
        rc, out = self.run_with(conts, 4096)
        self.assertEqual((rc, out.split()[0]), (1, "FREE_MB=610"))
        self.assertIn("START=no", out)

    def test_8gib_job_fits_next_to_one_4gib(self):
        rc, out = self.run_with([{"mem": 4 * GIB, "cpus": 2}], 8192)
        self.assertEqual(rc, 0, out)
        rc, out = self.run_with([{"mem": 8 * GIB, "cpus": 4}], 8192)
        self.assertEqual(rc, 1, out)

    def test_cpu_soft_cap(self):
        conts = [{"mem": 512 * 1024 ** 2, "cpus": 2}] * 5  # 10 CPUs, little memory
        rc, out = self.run_with(conts, 1024, cpus=4)
        self.assertEqual(rc, 1, out)
        self.assertIn("CPUS=10/12", out)
        rc, _ = self.run_with(conts, 1024, cpus=2)
        self.assertEqual(rc, 0)

    def test_unreachable(self):
        env = dict(os.environ, PATH="/nonexistent")
        r = subprocess.run([sys.executable, str(TOOL), "--need-mb", "1"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("unreachable", r.stdout)


if __name__ == "__main__":
    unittest.main()
