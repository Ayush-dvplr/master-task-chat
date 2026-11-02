import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pagerecover import recovery, reports  # noqa: E402


def image(records, disk, master=0):
    return {"id": "img1", "pages": {"Pa": 4}, "disk": disk, "records": records, "master": master}


class RecoveryTest(unittest.TestCase):
    def test_committed_update_is_redone(self):
        records = [
            {"lsn": 10, "type": "begin", "txn": 7, "prev": None},
            {"lsn": 11, "type": "update", "txn": 7, "prev": 10,
             "changes": [{"page": "Pa", "slot": 2, "delta": 5}]},
            {"lsn": 12, "type": "commit", "txn": 7, "prev": 11},
        ]
        disk = {"Pa": {"page_lsn": 0, "slots": [1, 2, 3, 4]}}
        result = recovery.recover_image(image(records, disk))
        self.assertEqual(result["status"], "recovered")
        self.assertEqual(result["pages"]["Pa"]["slots"], [1, 2, 8, 4])
        self.assertEqual(result["winners"], [7])
        self.assertEqual(result["losers"], [])

    def test_flushed_loser_update_is_undone(self):
        records = [
            {"lsn": 20, "type": "begin", "txn": 9, "prev": None},
            {"lsn": 21, "type": "update", "txn": 9, "prev": 20,
             "changes": [{"page": "Pa", "slot": 0, "delta": -4}]},
        ]
        disk = {"Pa": {"page_lsn": 21, "slots": [6, 0, 0, 0]}}
        result = recovery.recover_image(image(records, disk))
        self.assertEqual(result["losers"], [9])
        self.assertEqual(result["pages"]["Pa"]["slots"], [10, 0, 0, 0])
        clrs = [r for r in result["appended"] if r["type"] == "clr"]
        self.assertEqual(len(clrs), 1)
        self.assertEqual(clrs[0]["undo_next"], 20)

    def test_duplicate_lsn_is_rejected(self):
        records = [
            {"lsn": 30, "type": "begin", "txn": 3, "prev": None},
            {"lsn": 30, "type": "commit", "txn": 3, "prev": 30},
        ]
        disk = {"Pa": {"page_lsn": 0, "slots": [0, 0, 0, 0]}}
        result = recovery.recover_image(image(records, disk))
        self.assertEqual(result, {"status": "rejected", "error": "E_DUP_LSN"})

    def test_digest_is_hex(self):
        digest = reports.image_digest({"Pa": {"page_lsn": 1, "slots": [0, 0, 0, 0]}})
        self.assertEqual(len(digest), 64)
        int(digest, 16)


if __name__ == "__main__":
    unittest.main()
