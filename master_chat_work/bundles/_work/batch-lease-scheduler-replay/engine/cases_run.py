"""Case counts per hidden corpus / shipped book: sets carrying each case and total fires."""
import json
import sys
from collections import Counter

import gen
import refsim

KEYS = ["coinc3", "coinc_comp_exp", "coinc_x_ready", "token_at_deadline", "event_at_internal",
        "resume_before_old_finish", "preempt2_expire", "token_on_preempted", "stale_while_retry_runs",
        "cancel_running_resumed", "cancel_preempted_with_children", "cascade_waiting", "cascade_unsubmitted",
        "cascade_depth4", "redeliver_boost", "redeliver_cancel", "victim_tie_start", "victim_tie_prio",
        "preemption", "eviction", "expiry", "dead", "audit_redelivery", "audit_finished",
        "audit_stale_attempt", "audit_not_running", "event_submit", "event_heartbeat", "event_fail",
        "event_cancel", "event_boost", "event_worker_down", "event_worker_up", "redeliver_submit",
        "redeliver_heartbeat", "redeliver_fail", "redeliver_worker_down", "redeliver_worker_up", "boost_unsubmitted"]


def table(book):
    cc = refsim.case_counts(book)
    sets, fires = Counter(), Counter()
    for sid, c in cc.items():
        for k in KEYS:
            if c.get(k):
                sets[k] += 1
                fires[k] += c[k]
    core, met, dep, summ = refsim.documents(book)
    outc = Counter(e["outcome"] for s in dep["sets"].values() for e in s["edges"])
    return {k: (sets[k], fires[k]) for k in KEYS}, dict(outc), len(cc)


if __name__ == "__main__":
    prof, nsets = sys.argv[1], int(sys.argv[2])
    seeds = [int(x) for x in sys.argv[3:]]
    res = {}
    for sd in seeds:
        b = gen.make_book(sd, prof, nsets)
        t, o, n = table(b)
        ev = [len(s["events"]) for s in b["sets"].values()]
        res[sd] = t
        print("seed", sd, "sets", n, "events", min(ev), max(ev), "edges", o)
    print("%-32s" % "case" + "".join("%12s" % sd for sd in seeds))
    for k in KEYS:
        print("%-32s" % k + "".join("%12s" % ("%d/%d" % res[sd][k]) for sd in seeds))
