# Decisions only Ayush can make

1. **May Upgrade 2 move the master into a separate non-admin macOS account?** Options: **A (recommended):** separate `tb-master` account, with Ayush owning protected files and the trust store; **B:** keep the current `mac` account and accept detection only. Reason: `ls -ldO` shows current master files and OpenCode config owned by `mac`, so a process with that same unrestricted identity can bypass a voluntary verifier.

2. **How should an unattended run plan be approved?** Options: **A (recommended):** Ayush reviews and signs each `auto/plans/*.md` before the run, and the copied run plan must match it; **B:** approve only a reusable plan template and let the master fill run fields. Reason: `AUTO_POLICY.md:3` gives the run plan precedence over policy; B leaves a route to change effective rules.

3. **Should plugin package code be in the signed byte scope?** Options: **A (recommended):** pin versions in the config/lockfile, install as Ayush, and include the actually loaded package artifacts or immutable package tree; **B:** sign config/lockfile only and accept that package bytes are outside this guard. Reason: `opencode.jsonc:4-9` and `tui.json:2-5` load external plugins; the draft covers config/local plugin files but excludes `node_modules`.
