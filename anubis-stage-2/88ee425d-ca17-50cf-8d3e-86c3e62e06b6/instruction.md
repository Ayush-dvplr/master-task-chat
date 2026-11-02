A medical supply claims exchange has dumped one tariff year of its clearing
book into `/app/data` and then lost the program that read it. What survives is
the written contract at `/app/data/schema.md`, the four claim files, the
reference tables, and the policy file the exchange cleared against. Your job is
to rebuild the pipeline.

The contract is the authority on every rule: how a claim reaches its region,
its currency, its rate and its tariff period, which claims are malformed, how
the per member reserve ladder decides whether a claim is cleared at all, and
the exact shape of every figure you must emit. Read it together with the bytes.
Deciding which file feeds which figure is part of the work, so treat the
directory as something to explore rather than a list handed to you.

Deliver a reusable transform program at `/app/out/transform.py`. It takes an
input directory and an output directory and writes every artifact under the
output directory, so the same code clears a directory it has never seen:

```bash
python3 /app/out/transform.py <DATA_DIR> <OUT_DIR>
```

Use only the Python standard library; anything you pip install now will be
absent later. The program must not open network connections or start other
processes. Money is integer USD cents throughout, and every JSON artifact is
written with sorted keys.

Write the normalized claim stream to `/app/out/normalized.jsonl`, the book wide
roll-up to `/app/out/summary.json`, the data health report to
`/app/out/data_quality.json`, and the per item roll-up to
`/app/out/product_summary.json`. Write one file per top level region at
`/app/out/region_central.json`, `/app/out/region_east.json`,
`/app/out/region_north.json`, `/app/out/region_south.json` and
`/app/out/region_west.json`, and one file per segment at
`/app/out/segment_consumer.json`, `/app/out/segment_corporate.json`,
`/app/out/segment_enterprise.json` and `/app/out/segment_smb.json`. The keys
inside each file are fixed by the contract. Every region file and every segment
file is written on every run, including a bucket that drew nothing.

Two warnings worth taking seriously. An artifact counts only when every single
value in it is exact, so one cent or one unit out of place costs the whole file.
And the figures interlock: a member's running reserve decides which of its later
claims are cleared, so a claim you clear wrongly moves the reserve, changes
which neighbours survive, and shifts every roll-up that touches them.

Finish by posting a closing message that reports what you built, where each
artifact was written, and the nine closing report figures the contract defines.
Those nine appear in no artifact, so they have to come out of your own run.

You have 7200 seconds to complete this task. Do not cheat by using online
solutions or hints specific to this task.
