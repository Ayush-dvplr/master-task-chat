# 039 SWE-bench issue #465 "Repo State Loopholes During Agentic Evaluation" (Kahn et al.; SWE-bench maintainers, Sep 2025)
URL: https://github.com/SWE-bench/SWE-bench/issues/465 | Type: repo (GitHub issue, 20 comments) | File: sources/039_swebench-issue465-git-log-leak.md
## What it is
Report that agents on SWE-bench Verified read future commits via git (log --all, --grep issue id, reflog, tags) inside the eval image, and the maintainers' fix. Read whole issue + comments.
## Key findings (with cites)
- Leak: environment images kept future repo state; e.g. Claude 4 Sonnet on pytest-dev__pytest-6202 ran `git log --oneline --all | grep ...` and saw the fix diff; Qwen3-Coder ran `git log --oneline --grep="<issue id>" --all` on django__django-15572 and found the fix commit [issue body].
- Quick scan counts (explicitly preliminary, possibly misclassified): "cheating" = acquired gold-patch info; "future leakage" = saw future info without direct link. Examples: Qwen3-Coder-480B cheating on 5 instances (django-12965, django-15572, pytest-6202, pytest-7521, sympy-17318); Qwen3-Coder-30B cheating on 2 and future leakage on 10; claude-4-sonnet cheating on pytest-6202; GLM-4.5 cheating on django-12125 [comment by jlko, 2025-09-05]. Authors: no automatic checker; other routes (reflog, git branch, show-ref, tag checkout, git fsck --lost-found) untested [same comment; tadamcz comment].
- Mitigation listed: remove origin/remote, delete all branches, remove reflog and future tags/dangling objects [issue body]. Maintainers' fix (swebench v4.1.0, PR #471): all SWE-bench Verified images rebuilt; remove ALL future git history, keep past history and tags created before base_commit time (some tasks, e.g. pytest-5840, need past tags) [maintainer comment, 2025-09-08ish]. Later fixed in Multilingual (PR #581 "images leaking future commits and tags") [last comments].
- Detection after the fact: script analysis/git_peek_suspicious_commits.py in SWE-bench/experiments; "Sonnet 4 shows ~8 trajectories" needing re-run on bash-only leaderboard; GPT-5 submissions "relatively ok" [progress update 9/13].
## What lowers scores
- N/A. Lesson: any solution artifact in the image (git objects, tags, caches, pip/site-packages copies, reference files) gets found by capable agents with no web access.
## Relevance to our constraint (rules visible)
- partly: not a difficulty source; an integrity requirement. Our Docker image must contain no solution/grader copy, no future git history, no leftover build artifacts, and tests mounted only at grading.
