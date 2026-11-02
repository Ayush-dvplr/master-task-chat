"""The suite the yard runs before it accepts a build of the engine.

It covers the parts of the engine the desk has never had trouble with: the
arithmetic, the amount grammar, the working store and the command line. It
says nothing about the derivation, which is why it passes on a build whose
figures are wrong.
"""
import unittest
from fractions import Fraction

from slwopt import cache, graph, normalise, objective
from slwopt.__main__ import parse


class Arithmetic(unittest.TestCase):

    def test_half_away_from_zero(self):
        self.assertEqual(normalise.half_up(Fraction(5, 2)), 3)
        self.assertEqual(normalise.half_up(Fraction(-5, 2)), -3)
        self.assertEqual(normalise.half_up(Fraction(7, 3)), 2)
        self.assertEqual(normalise.half_up(Fraction(4, 1)), 4)

    def test_ratio_carries_twelve_places(self):
        self.assertEqual(normalise.ratio(Fraction(1, 4)), "0.250000000000")
        self.assertEqual(normalise.ratio(0), "0.000000000000")
        self.assertEqual(normalise.ratio_of(3, 0), "0.000000000000")

    def test_ratio_publishes_no_negative_zero(self):
        self.assertEqual(normalise.ratio(Fraction(-1, 10 ** 16)),
                         "0.000000000000")


class Amounts(unittest.TestCase):

    def test_forms_of_one_amount_agree(self):
        self.assertEqual(normalise.amount("4800"), 4800)
        self.assertEqual(normalise.amount("4,800 mills"), 4800)
        self.assertEqual(normalise.amount("4.800 GBP"), 4800)
        self.assertEqual(normalise.amount("4 GBP"), 4000)

    def test_an_empty_amount_is_nothing(self):
        self.assertEqual(normalise.amount(""), 0)

    def test_a_fraction_of_a_mill_is_refused(self):
        with self.assertRaises(ValueError):
            normalise.amount("12.5")


class WorkingStore(unittest.TestCase):

    def test_a_key_already_held_is_a_hit(self):
        store = cache.Store(4)
        store.put("norm|A", "k1", {"v": 1}, "d1")
        self.assertEqual(store.take("norm|A", "k1")[1], "d1")
        self.assertEqual(store.hits, 1)
        self.assertEqual(store.misses, 0)

    def test_a_superseded_key_comes_back(self):
        store = cache.Store(4)
        store.put("norm|A", "k1", {"v": 1}, "d1")
        store.put("norm|A", "k2", {"v": 2}, "d2")
        self.assertEqual(store.take("norm|A", "k1")[1], "d1")

    def test_the_retained_count_is_held(self):
        store = cache.Store(2)
        for step in range(6):
            store.put("norm|A", "k" + str(step), {"v": step}, "d" + str(step))
        self.assertLessEqual(len(store.retired), 2)
        self.assertEqual(store.evictions, 3)


class Graph(unittest.TestCase):

    def test_depth_counts_the_longest_chain(self):
        accepted = {"c": ["b"], "b": ["a"]}
        depth = graph.depths(accepted, ["a", "b", "c"])
        self.assertEqual([depth["a"], depth["b"], depth["c"]], [0, 1, 2])

    def test_a_prerequisite_is_found_through_the_chain(self):
        accepted = {"c": ["b"], "b": ["a"]}
        self.assertTrue(graph.stands_behind(accepted, "c", "a"))
        self.assertFalse(graph.stands_behind(accepted, "a", "c"))

    def test_the_reverse_index_turns_the_edges_around(self):
        self.assertEqual(graph.reverse({"c": ["a", "b"]}),
                         {"a": ["c"], "b": ["c"]})


class Objective(unittest.TestCase):

    def test_usage_adds_each_job_once(self):
        own = {"a": {"berth_quarter_days": 2, "crane_lifts": 1,
                     "crew_minutes": 60},
               "b": {"berth_quarter_days": 3, "crane_lifts": 0,
                     "crew_minutes": 30}}
        usage = objective.usage_of(["a", "b"], own)
        self.assertEqual(usage["berth_quarter_days"], 5)
        self.assertEqual(usage["crew_minutes"], 90)

    def test_weighting_stays_exact(self):
        usage = {"berth_quarter_days": 1, "crane_lifts": 1, "crew_minutes": 1}
        weights = {"berth_quarter_days": (25, 1), "crane_lifts": (7, 1),
                   "crew_minutes": (1, 60)}
        self.assertEqual(objective.weighted_of(usage, weights),
                         Fraction(1921, 60))


class CommandLine(unittest.TestCase):

    def test_the_two_options_come_in_either_order(self):
        first = parse(["--data", "papers", "--out", "here"])
        second = parse(["--out", "here", "--data", "papers"])
        self.assertEqual(str(first[0]), str(second[0]))
        self.assertEqual(str(first[1]), str(second[1]))

    def test_a_missing_option_is_refused(self):
        with self.assertRaises(SystemExit):
            parse(["--data", "papers"])


if __name__ == "__main__":
    unittest.main()
