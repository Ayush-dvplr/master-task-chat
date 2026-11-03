STATUS (3 Nov 10:07): QUEUE batches B11 to B24 stay PAUSED. Sample batches S01 to S04 (15 tasks, ENTRY 33) are approved and running; same procedure, batch ids S01 to S04.
EARLIER: PAUSED by Ayush 3 Nov 09:55 (ENTRY 31): credits used up. Start NO new batch until Ayush agrees a tighter plan (Q102).

CARD RUN PROCEDURE (Layer D light cards; read this to continue the run after a compaction)

Counts: 114 teammate tasks have an Opus score; minus Ayush's own 5 = 109; minus 1 with no reward details = 108; minus 10 carded on 2 Nov and 3 pilot cards = 95 in QUEUE.txt (B01 to B23 have 4 tasks, B24 has 3).

1. Which batches are done: for each batch id in QUEUE.txt, a batch is DONE when every one of its tasks has a card file tmp/S2-CARDS/<first 8 characters of the task id>.md. Check with:
   cd /home/user/master-task-chat/upgrade_plan && python3 -c "import os;q=[l.split() for l in open('tmp/S2-CARDS/QUEUE.txt')];b={};[b.setdefault(x[0],[]).append(os.path.exists('tmp/S2-CARDS/'+x[1][:8]+'.md')) for x in q];print({k:sum(v) for k,v in b.items()})"
   (prints cards present per batch).
2. Which batches are running: rows in WORKER_LOG.md with status running. After a compaction the helper notices are lost: a running batch whose 4 cards all exist counts as done; one with missing cards, no notice and no new card file for 60 minutes (compare file times with ls -l) is restarted with a NEW helper id for the missing tasks only.
3. Next batch: the lowest batch id that has no row in WORKER_LOG.md (every batch row contains the text "batch Bnn").
4. Next helper id: one more than the highest W1-nnn in WORKER_LOG.md (ids are not tied to batch numbers).
5. Start: the Agent tool, background, prompt: "Read the file /home/user/master-task-chat/upgrade_plan/prompts/LIGHT_CARD_BRIEF.md and follow it exactly, with <HELPER> = W1-nnn and <BATCH> = Bnn." Then add a running row to WORKER_LOG.md and commit.
6. At most 3 batch helpers at a time.
7. When a batch is done: the master opens one card of the batch and checks one cited line; sets the row to verified (or rejected); commits tmp/S2-CARDS and WORKER_LOG.md; pushes.
8. After every 3 batches: a short update to Ayush.
9. Cards are committed in their own commit ("store cards Bnn"), not inside unrelated commits.
10. Helpers keep any scratch files in a subfolder named after their own helper id (the scratchpad is shared).
