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
