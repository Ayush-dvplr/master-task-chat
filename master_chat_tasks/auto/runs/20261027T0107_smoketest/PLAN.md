# Auto mode smoke test (Ayush 27 Oct 01:04: "small test ... shorter 1 min sessions")

Until: 01:30

## Ayush's words
"chat is opened in os master mode for a small test schedule auto mode ... give some small to some new chats and get response from there like normal way and give again some commands like normal ... shorter 1 min sessions"

## Do in order
1. Spawn test worker t1smoke with auto/smoketest/t1.md and t2smoke with auto/smoketest/t2.md (auto.py spawn).
2. When each reports done, read its reply and send one follow-up (auto.py send): t1smoke "Reply with exactly: T1 STEP2 OK"; t2smoke "Reply with exactly: T2 STEP2 OK".
3. When both step-2 replies are in, run auto.py stop and summarise for Ayush.

## Do not
No board.json/registry/pending changes, no harness runs, no real task work, no pushing, no deletes.

## Timed steps
at 01:07: begin step 1 of the plan.
