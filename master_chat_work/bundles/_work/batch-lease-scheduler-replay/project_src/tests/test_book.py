import os
import unittest

import bookfix
from leasebook.book import BookError, load_book


class LoadBookTest(unittest.TestCase):
    def test_reads_every_table(self):
        book = load_book(bookfix.write_book())
        self.assertEqual((book.lease, book.delay), (10, 2))
        self.assertEqual(book.pools, {"oak": True, "elm": False})
        spec = book.sets[1]
        self.assertEqual(spec["jobs"][6], ("oak", 2, 1))
        self.assertEqual(spec["work"][7], 5)
        self.assertEqual(spec["deps"], [(5, 6)])
        self.assertEqual(spec["checkpoints"], [3, 30])

    def test_blank_event_lines_are_skipped(self):
        book = load_book(bookfix.write_book(blank_lines=True))
        self.assertEqual(len(book.sets[1]["events"]), 3)

    def test_missing_file_is_named(self):
        root = bookfix.write_book()
        os.remove(os.path.join(root, "durations.csv"))
        with self.assertRaises(BookError) as caught:
            load_book(root)
        self.assertEqual(caught.exception.message(), "ERROR MISSING_INPUT durations.csv")

    def test_policy_out_of_range(self):
        root = bookfix.write_book(policy="[lease]\nticks = 0\n\n[retry]\ndelay = 2\n")
        with self.assertRaises(BookError) as caught:
            load_book(root)
        self.assertEqual(caught.exception.code, "INVALID_POLICY")

    def test_cycle_is_refused(self):
        root = bookfix.write_book(deps=[(1, 5, 6), (1, 6, 5)])
        with self.assertRaises(BookError) as caught:
            load_book(root)
        self.assertEqual(caught.exception.code, "DEPENDENCY_CYCLE")

    def test_unknown_job_is_refused(self):
        root = bookfix.write_book(work=bookfix.WORK + [(1, 99, 3)])
        with self.assertRaises(BookError) as caught:
            load_book(root)
        self.assertEqual(caught.exception.code, "UNKNOWN_ENTITY")


if __name__ == "__main__":
    unittest.main()
