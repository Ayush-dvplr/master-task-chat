"""Build salvage_day_window.py from solution/solve.py (P12 v3 r1, board 5336aa7).

One change: the S2 window reads each settled forge's handle on the SALVAGE day
instead of on the forge's own day (mirrors p14_a7 agent_settle.py:733-735).
The ledger is sorted by (day, entry_id), so sorting the gathered (day, id)
pairs keeps ledger order.
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SOLVE = pathlib.Path(
    "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/emberforge-vault-settlement/solution/solve.py"
)

OLD = """            for day, forge_id in walk.windows.get((here["smith"], family), ())
            if day < entry["day"] and forge_id not in walk.redeemed
"""
NEW = """            for day, forge_id in sorted(
                item
                for (_smith, fam), items in walk.windows.items()
                if fam == family
                for item in items
                if corpus.roster.canonical(corpus.forges[item[1]]["smith_ref"], entry["day"])
                == here["smith"]
            )
            if day < entry["day"] and forge_id not in walk.redeemed
"""

text = SOLVE.read_text()
assert text.count(OLD) == 1, text.count(OLD)
(HERE / "salvage_day_window.py").write_text(text.replace(OLD, NEW))
print("wrote", HERE / "salvage_day_window.py")
