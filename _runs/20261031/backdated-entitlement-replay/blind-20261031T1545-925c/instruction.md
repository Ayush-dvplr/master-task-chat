The billing team of a subscription business has received backdated corrections
to customer entitlements (seats and usage blocks). The bills of the window have
to be rated again with those corrections, and the carry-forward credit of every
account has to be worked out again on top of the corrected bills. The files are in /app/data. The documents there describe
the billing terms, the correction and credit policies and the output documents;
rule_register.md names the document that governs each topic.

Please write one reusable program at /app/out/derive_report.py. It is run as

    python3 /app/out/derive_report.py --input <input folder> --output <output folder>

and writes these documents into the output folder:

- summary.json
- policy_audit.json
- data_quality.json
- region_North.json, region_South.json, region_West.json, region_East.json
- segment_commercial.json, segment_public.json

Run it once on /app/data with /app/out as the output folder, so that
/app/out holds the program and the nine documents for this extract.

Each output document is graded whole, and only an exact match counts. Your
program is run again on this extract and on fresh extracts laid out like this
one, from a different input folder and a different working directory, with
python3 and the command above. Each run must finish within 60 seconds.

Leave /app/data unchanged and write only under /app/out.

When you are done, reply with the list of files you wrote and the checks you
ran on your program, each with what it showed.

You have 7200 seconds to complete this task. Do not cheat by using online
solutions or hints specific to this task.
