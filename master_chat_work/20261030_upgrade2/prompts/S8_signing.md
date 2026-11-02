# S8: Self-upgrade guard (Ayush must sign changes to the master's rules)
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/S8_signing/`

Goal (Ayush U13): the master must not be able to change its own rules, prompts templates, policies or tools without Ayush. Use a key pair: Ayush holds the private key (or a password-protected script); the master can only verify.

Answer with evidence:
1. Protected set: list the files whose change alters the master's behaviour (rule files in knowledge/, prompts/templates/, AUTO_POLICY.md, GOALS.md, tools/*.py, auto/auto.py, opencode config ~/.config/opencode/*.jsonc + plugins, skills used). Today, which of these were changed by the master itself and when (APPLY_LOG.md, CHANGELOG.md, decisions.jsonl, file mtimes)?
2. Options compared (`OPTIONS.md`): (a) `ssh-keygen -Y sign/verify` over a manifest of sha256 sums, (b) git signed commits/tags in the private repo (S2) with branch protection, (c) macOS file flags/permissions (uchg, separate user) with a sudo/password step, (d) a manifest + Ayush-run `approve.sh` that asks for a passphrase. For each: what stops the master, what Ayush must do per change, tooling already on this Mac (check `ssh-keygen -Y` support, `gpg`, `git` version), failure modes, how the master detects an unsigned change at start and refuses to use it.
3. Recommend one; write a DRAFT `approve.sh` + `verify_manifest.py` design (not installed, no keys generated) and the exact steps Ayush runs once to set up and per change to approve.
4. Interaction with auto mode (unattended runs must still work) and with the git repo (S2).
