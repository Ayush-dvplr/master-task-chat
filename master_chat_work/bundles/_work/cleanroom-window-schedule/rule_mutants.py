"""G11: one mutant of solve.py per stated rule, each dropping that rule alone.

Writes WORK/rule_mut/<id>.py and a manifest rule_mut/manifest.json {id: [rule, contract ref]}.
Lever mutants (greedy, no_initial, touching_only, reset_nightly, no_crew, naive_collapse) come from
mutants.py and are listed in RULE_COVERAGE.md from tmp/cost results.
"""
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
SOLVE = WORK.parent.parent / "cleanroom-window-schedule" / "solution" / "solve.py"
OUTDIR = WORK / "rule_mut"

REJ_OLD = '''    for r in rows:
        w = book.windows.get(r["window_id"])
        if w is None or not 0 <= w[0] < w[1] <= DAY_END:
            return "E_BAD_WINDOW"
    if any(r["family"] not in book.catalog or r["client_id"] not in book.site_of for r in rows):
        return "E_UNKNOWN_RESOURCE"
'''
REJ_SWAP = '''    if any(r["family"] not in book.catalog or r["client_id"] not in book.site_of for r in rows):
        return "E_UNKNOWN_RESOURCE"
    for r in rows:
        w = book.windows.get(r["window_id"])
        if w is None or not 0 <= w[0] < w[1] <= DAY_END:
            return "E_BAD_WINDOW"
'''

M = {
    "missing_input_exit": ("missing input file: nonzero exit naming it", "contract.md:11-13",
                           [('            return 1\n    book = Book', '            return 0\n    book = Book')]),
    "night_order_by_id": ("nights run in audit.toml date order", "contract.md:42",
                          [('key=lambda n: n["date"]', 'key=lambda n: n["id"]')]),
    "dup_job_unchecked": ("E_DUP_JOB", "contract.md:47",
                          [('if any(book.row_count[r["job_id"]] > 1 for r in rows):', 'if False:')]),
    "absent_window_unchecked": ("E_BAD_WINDOW absent window", "contract.md:48-49",
                                [('if w is None or not 0 <= w[0] < w[1] <= DAY_END:',
                                  'if w is not None and not 0 <= w[0] < w[1] <= DAY_END:')]),
    "window_bounds_unchecked": ("E_BAD_WINDOW 0 <= start < end <= 1440", "contract.md:48-49",
                                [('not 0 <= w[0] < w[1] <= DAY_END', 'not w[0] < w[1]')]),
    "unknown_family_unchecked": ("E_UNKNOWN_RESOURCE family", "contract.md:50-51",
                                 [('r["family"] not in book.catalog or ', '')]),
    "unknown_client_unchecked": ("E_UNKNOWN_RESOURCE client", "contract.md:50-51",
                                 [(' or r["client_id"] not in book.site_of for r', ' for r')]),
    "fee_table_unchecked": ("E_BAD_FEE", "contract.md:52",
                            [('                return "E_BAD_FEE"', '                return None')]),
    "code_priority_swapped": ("first applicable code in the stated order", "contract.md:45-52",
                              [(REJ_OLD, REJ_SWAP)]),
    "message_format": ("message `night <night_id> rejected: <code>`", "contract.md:53",
                       [('"night %s rejected: %s"', '"night %s rejected (%s)"')]),
    "rejected_resets_families": ("a rejected night leaves every bay's family as it was", "contract.md:54-55",
                                 [('                               "families_after": dict(holding), "flags": []})\n            continue',
                                   '                               "families_after": dict(holding), "flags": []})\n'
                                   '            holding = {b["bay_id"]: b["initial_family"] for b in book.bays}\n            continue')]),
    "qualification_ignored": ("a job runs only on a bay qualified for its family", "contract.md:61",
                              [('if fam not in book.qualified[bay]:', 'if False:')]),
    "touching_forbidden": ("windows are half-open; touching jobs share no minute", "contract.md:60-62",
                           [('if start < free:', 'if start < free or (free and start == free):')]),
    "mandatory_optional": ("every mandatory job runs", "contract.md:63",
                           [('if job["job_id"] not in must:', 'if True:')]),
    "fee_not_charged": ("a changeover charges the fee of the ordered family pair", "contract.md:74-76",
                        [('(int(r["fee"]), int(r["crew_minutes"]))', '(0, int(r["crew_minutes"]))')]),
    "bay_busy_in_window": ("the bay's earlier job ends at or before the crew window starts", "contract.md:76-77",
                           [('if start - minutes < max(free, crew):', 'if start - minutes < crew:')]),
    "window_before_zero": ("no crew window starts before minute 0", "contract.md:78",
                           [('if start - minutes < max(free, crew):',
                             'if start - minutes < max(free, crew) and not (free == 0 and crew == 0):')]),
    "bay_charge_inclusive": ("bay charge = minute rate x (end - start)", "contract.md:85",
                             [('rate[bay] * (end - start)', 'rate[bay] * (end - start + 1)'),
                              ('rate[bay] * (j["end"] - j["start"])', 'rate[bay] * (j["end"] - j["start"] + 1)')]),
    "job_net_without_fee": ("job net = value - bay charge - its changeover fee", "contract.md:86",
                            [('j["net"] = j["value"] - charge - fee', 'j["net"] = j["value"] - charge')]),
    "plan_lines_by_job_id": ("plan items ordered by start then job id", "contract.md:107",
                             [('        holding = last_family\n', '        lines.sort(key=lambda x: x["job_id"])\n        holding = last_family\n')]),
    "crew_windows_by_job_id": ("crew windows ordered by start", "contract.md:118",
                               [('windows.sort(key=lambda w: w["start"])', 'windows.sort(key=lambda w: w["job_id"])')]),
    "crew_flag_dropped": ("flag crew_load_high when crew minutes exceed the limit", "contract.md:121-122",
                          [('if crew_minutes > book.crew_limit:', 'if False:')]),
    "margin_flag_dropped": ("flag low_margin when net is below the floor", "contract.md:121-122",
                            [('if net < book.margin_floor:', 'if False:')]),
    "flags_unsorted": ("flags sorted", "contract.md:121",
                       [('"flags": sorted(flags)', '"flags": flags[::-1]')]),
    "families_after_dropped": ("families_after holds each bay's family at night end", "contract.md:120",
                               [('"crew_minutes": crew_minutes, "families_after": dict(holding)',
                                 '"crew_minutes": crew_minutes, "families_after": {}')]),
    "region_not_by_site": ("a job's region is its client's site's region", "contract.md:102",
                           [('lambda j: book.region_of[book.site_of[j["client_id"]]]', 'lambda j: "North"')]),
    "segment_not_by_client": ("a job's segment is its client's segment", "contract.md:102",
                              [('lambda j: book.segment_of[j["client_id"]]', 'lambda j: "commercial"')]),
    "rollup_skips_empty_nights": ("rollups list every accepted night, including nights with no job", "contract.md:136-140",
                                  [('                mine = [j for j in running if key_of(j) == g]\n',
                                    '                mine = [j for j in running if key_of(j) == g]\n'
                                    '                if not mine:\n                    continue\n')]),
    "rollup_totals_partial": ("rollup totals of jobs_run, gross and net", "contract.md:140",
                              [('("jobs_run", "gross", "net")}}', '("jobs_run", "gross")}}')]),
    "summary_totals_partial": ("summary totals", "contract.md:112-114",
                               [('"rejected_nights": len(rejected), ', '')]),
    "rejected_night_omitted": ("rejected nights listed with empty plan and zero figures", "contract.md:110-111",
                               [('            summary.append({"night_id": nid, "date": night["date"], "status": "rejected", "plan": [],\n'
                                 '                            "gross": 0, "bay_charge": 0, "fees": 0, "net": 0})\n', '')]),
    "output_paths_lowercase": ("instruction.md output paths region_North.json and others", "instruction.md:5-11",
                               [('"%s_%s.json" % (label, g)', '"%s_%s.json" % (label, g.lower())')]),
    "data_dir_ignored": ("the program reads <data_dir>", "instruction.md:3",
                         [('data, out = Path(argv[1]), Path(argv[2])', 'data, out = Path("/app/data"), Path(argv[2])')]),
}


def main():
    OUTDIR.mkdir(exist_ok=True)
    src = SOLVE.read_text()
    manifest = {}
    for mid, (rule, ref, subs) in M.items():
        text = src
        for old, new in subs:
            assert text.count(old) >= 1, (mid, old)
            text = text.replace(old, new)
        assert text != src, mid
        (OUTDIR / (mid + ".py")).write_text(text)
        manifest[mid] = [rule, ref]
    (OUTDIR / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(len(manifest), "mutants")


if __name__ == "__main__":
    main()
