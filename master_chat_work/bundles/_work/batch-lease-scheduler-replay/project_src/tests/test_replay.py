import unittest

import bookfix  # noqa: F401  (puts src on the path)
from leasebook.replay import SetReplay


def spec(jobs, work, events, checkpoints, deps=(), workers=None):
    return {
        "workers": workers or {11: ("oak", True)},
        "jobs": jobs,
        "work": work,
        "deps": list(deps),
        "events": events,
        "checkpoints": checkpoints,
    }


class ReplayTest(unittest.TestCase):
    def test_single_job_completes(self):
        replay = SetReplay(spec({5: ("oak", 1, 0)}, {5: 4}, [{"id": 1, "t": 0, "type": "submit", "job": 5}], [20]),
                           10, 2, {"oak": True}).run()
        self.assertEqual(replay.jobs[5].state, "completed")
        self.assertEqual(replay.dispatches, [[0, 5, 11, 1]])

    def test_child_runs_after_parent(self):
        events = [{"id": 1, "t": 0, "type": "submit", "job": 5}, {"id": 2, "t": 1, "type": "submit", "job": 6}]
        replay = SetReplay(spec({5: ("oak", 1, 0), 6: ("oak", 1, 0)}, {5: 3, 6: 2}, events, [3, 20], deps=[(5, 6)]),
                           10, 2, {"oak": True}).run()
        self.assertEqual([row[1] for row in replay.dispatches], [5, 6])
        self.assertEqual(replay.jobs[6].state, "completed")

    def test_cancel_frees_the_worker(self):
        events = [
            {"id": 1, "t": 0, "type": "submit", "job": 5},
            {"id": 2, "t": 0, "type": "submit", "job": 6},
            {"id": 3, "t": 2, "type": "cancel", "job": 5},
        ]
        replay = SetReplay(spec({5: ("oak", 2, 0), 6: ("oak", 1, 0)}, {5: 6, 6: 2}, events, [20]),
                           10, 2, {"oak": True}).run()
        self.assertEqual(replay.jobs[5].state, "cancelled")
        self.assertEqual(replay.jobs[6].state, "completed")
        self.assertEqual(replay.dispatches, [[0, 5, 11, 1], [2, 6, 11, 1]])

    def test_failure_retries_then_dies(self):
        events = [
            {"id": 1, "t": 0, "type": "submit", "job": 5},
            {"id": 2, "t": 2, "type": "fail", "job": 5, "attempt": 1},
            {"id": 3, "t": 7, "type": "fail", "job": 5, "attempt": 2},
        ]
        replay = SetReplay(spec({5: ("oak", 1, 1)}, {5: 9}, events, [4, 30]), 10, 2, {"oak": True}).run()
        self.assertEqual(replay.jobs[5].state, "dead")
        self.assertEqual(replay.jobs[5].counts["attempts_ended"], 2)


if __name__ == "__main__":
    unittest.main()
