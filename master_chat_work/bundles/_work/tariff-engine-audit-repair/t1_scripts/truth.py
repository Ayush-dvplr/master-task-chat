"""Rewrite solution/TRUTH.md for the 78d433c test-hardening round (run last)."""
import hashlib
import json
import re
import sys
from pathlib import Path

B = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair")
R = Path(sys.argv[1])  # docker run folder
p = B / "solution/TRUTH.md"
s = p.read_text()


def sub(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)


sub("""    recoded and renamed accounts are named by code on at least 40% of their rows.
""", """    recoded and renamed accounts are named by code on at least 40% of their rows.
16. (quiet rule Q1) `parser` ignores the `estimated` field of a read. The contract makes
    `duplicate_read` compare reads of the same `estimated` value and adds the reason
    `replaced_estimate`: an estimated read gives way to an accepted actual read of the same
    account, meter and day wherever that read stands in the file. The shipped reads carry
    no `estimated` field; every hidden corpus plants estimates before and after their
    actual read, a lone estimate, two estimates of one day, an estimate whose actual read is
    malformed and an explicit `false`.
17. (quiet rule Q2) `core` prices every day at the plan's `standing_charge`. A plan can
    carry `standing_changes`; the charge of a day is the entry with the latest `from` on or
    before it, and the standing line sums the charge of each active day over the length of
    that day's month. The shipped card has no `standing_changes`; hidden plans carry
    unsorted lists with entries before, inside and after the periods.
18. (quiet rule Q3) `report` keeps one billing row per account. An account can have
    several rows that never share a day; each row is its own invoice, invoices sort by
    account and then `start`, a read belongs to the row whose period holds its day, and a
    read in no row of its account is `outside_period`. Account position (N3) is counted
    per invoice row over the accepted reads that belong to that row, and the plan of each
    row is resolved by key or listed code (L11) from that row's own `plan` value. The
    shipped billing file has one row per account; hidden rows are written out of order.
19. (quiet rule Q4) allowance no energy line of an invoice can take is added to the
    allowance of the account's next invoice by `start`, and is dropped after the last one.
    Hidden chains of two and three rows, one with an empty middle row, carry it on.
20. (quiet rule Q5) `report` keeps one accounts row per meter. A meter can have several
    rows for its account that never share a day; it is active on the days of any of them
    and keeps one standing line whose units count all those days. Hidden meters have two
    windows with a gap read that is `inactive_meter`.
""")

sub("""- Carry the account position across the meters in `meter` order when placing tiers.
""", """- Carry the account position across the meters in `meter` order when placing tiers,
  counted per invoice row over the reads belonging to that row.
- Classify actual reads before estimated reads: `duplicate_read` keys on account, meter,
  day and `estimated`; an estimate whose actual read is accepted gets `replaced_estimate`.
- Price each active day at the standing charge in force that day (`standing_changes`).
- Bill every billing row as its own invoice, sorted by account then `start`, and carry
  allowance no energy line could take into the account's next invoice.
- Treat a meter as active on the days of any of its accounts rows.
""")

sub("""The test channel registers 37 positive checks worth 157 points and 2 negative checks,""",
    """The test channel registers 52 positive checks worth 226 points and 2 negative checks,""")

sub("""- Missing input named (3) and two runs byte-identical (3).
""", """- Missing input named (3) and two runs byte-identical (3).
- Owned quiet-rule accounts: every hidden corpus also holds 17 planted accounts (27
  invoices) owned by the quiet rules; the checks above compare only the other accounts
  and exception rows, and fifteen owned-account checks compare the planted ones whole:
  estimated reads, standing changes and meter rows (5 + 5 + 5 each, over fresh with
  rescaled, relocated with rotated, api with recoded and renamed), billing rows (5 + 5),
  carried allowance (5 + 3) and accounts combining two or three rules (3 + 3). The planted
  accounts use their own random stream (`_quiet`, seed x 31 + 7), plain plans with
  first tiers above every planted quantity, no half-cent line and allowance only on the
  carry chains; `_assert_quiet` checks that each rule, read the habitual way, changes
  exactly the accounts it owns and that the unowned part of every corpus is unchanged.
""")

sub("""Measured on real runs (test points of 157): the oracle scores 157. An unknown plan value
falling to the first or the last plan scores 117; a key-only lookup crashes on the
shipped data. Allowance shared in one or in two shares scores 97; allowance ignored 89;
standing by the month of `start` 112; standing by the period length 99; tiers per meter
112; a quoted-integer coercion 41. One energy line off by 0.01 on one recoded or fresh
account scores 127; on one api account 142; on one shipped code-named account 152. The
judge channel carries 14 criteria, 33 positive points.""",
    """Measured on real runs (test points of 226): the oracle scores 226. `estimated` ignored
205; `standing_changes` ignored 205; last billing row only 202; allowance not carried 212;
last accounts row only 205; all five quiet rules read the habitual way 157. An unknown
plan value falling to the first or the last plan scores 186; a key-only lookup crashes on
the shipped data. Allowance shared in one or in two shares scores 166; allowance ignored
144; standing by the month of `start` 181; standing by the period length 147; tiers per
meter 181; a quoted-integer coercion 110. The judge channel carries 14 criteria, 33
positive points.""")

sub("""2. Fix `parser`: strict quantity type, `outside_period` after `inactive_meter`,
   duplicates against earlier accepted reads only.""",
    """2. Fix `parser`: strict quantity type, `outside_period` after `inactive_meter`,
   duplicates against earlier accepted reads of the same `estimated` value only,
   `replaced_estimate`, several accounts rows and billing rows.""")

sub("""- Making the code match the two visible assertions.
""", """- Making the code match the two visible assertions.
- Ignoring `estimated`, or letting the first read of a day win whatever its kind.
- Pricing a day at the plan's own `standing_charge` when a change is in force, or taking
  the last listed change instead of the latest `from`.
- Keeping the last billing row or accounts row per key in a dict.
- Dropping allowance no line can take instead of carrying it to the next invoice.
""")

sh = hashlib.sha256((B / "solution/solve.sh").read_bytes()).hexdigest()
py = hashlib.sha256((B / "solution/solve.py").read_bytes()).hexdigest()
s = re.sub(r"fix_patch_sha256: [0-9a-f]{64}", "fix_patch_sha256: " + sh, s)
s = re.sub(r"solve_py_sha256: [0-9a-f]{64}", "solve_py_sha256: " + py, s)

trial = sorted(d.name for d in (R / "jobs/oracle-1").iterdir() if d.is_dir())[0]
rewards = []
for job in ("oracle-1", "oracle-2", "oracle-3"):
    rewards.append(json.loads((R / "jobs" / job / "result.json").read_text()))
s = re.sub(r"golden_score_trial_id: \S+", "golden_score_trial_id: " + trial, s)
sub("""  harbor 0.24.0 oracle agent, three runs on 2026-10-25 (harden round 1),
  tests channel reward 1.0 each; owner-only copy 1.0; nop agent reward 0.0.""",
    """  harbor 0.24.0 oracle agent, three runs on 2026-10-26 (test-hardening round
  78d433c), tests channel reward 1.0 each; owner-only copy 1.0; nop agent reward 0.0.""")
sub("""  The test channel carries 37 positive checks worth 157 weight and 2 negative""",
    """  The test channel carries 52 positive checks worth 226 weight and 2 negative""")
p.write_text(s)
print("TRUTH written", trial, sh[:12], py[:12])
