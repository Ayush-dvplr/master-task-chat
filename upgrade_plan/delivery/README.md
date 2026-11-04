MC2 DELIVERY (STAGE A). The new system is built as git branches mc2-v2 and mc2-stable with tags mc2-v2.N. This session may push only to its own branch, so the branches travel inside one git bundle file: delivery/mc2.bundle.

On the Mac (Ayush runs every command):
1. Get this branch: git -C <this repo clone> fetch origin claude/youthful-feynman-zug0uq, then check out upgrade_plan/delivery/mc2.bundle from it.
2. Create ROOT from the bundle (ROOT name from settings, default mc2_root):
   git clone -b mc2-stable /path/to/mc2.bundle "/Users/mac/Desktop/mc2_root"
3. Optional, to keep the versions on GitHub too (Q152): inside ROOT run
   git remote add github <this repo url>
   git push github mc2-v2 mc2-stable --tags
4. Then follow upgrade_plan/tmp/W1-043/STEP0_REPORT.md for the data copy, backup, preflight and carry over.
Each later step replaces mc2.bundle with a newer one; inside ROOT: git fetch /path/to/mc2.bundle "refs/heads/*:refs/remotes/bundle/*" --tags, then the upgrade tool prints the switch commands.

STATUS 4 Nov: STAGE A complete in the bundle: tags mc2-v2.0 to mc2-v2.5 on mc2-v2; mc2-stable points at mc2-v2.0.
Upgrade path on the Mac, one tag at a time (each step: backup, preflight, the printed git commands, recheck):
1. In ROOT: python3 master_chat_tasks/tools/upgrade.py backup
2. python3 master_chat_tasks/tools/upgrade.py preflight
3. Run the git commands it prints (checkout of the next tag).
4. python3 master_chat_tasks/tools/upgrade.py recheck --from <old tag> --to <new tag>; on a FAIL it prints the rollback commands.
After mc2-v2.3, issue one real prompt and read it (sample: delivery/s3_sample_issued_P11.md). For mc2-v2.5 the master saves a new kit snapshot only on your word.
Details and every check result: upgrade_plan/tmp/W1-043/STEP0_REPORT.md, tmp/W1-044/STEPS12_REPORT.md, tmp/W1-045/STEPS345_REPORT.md.
