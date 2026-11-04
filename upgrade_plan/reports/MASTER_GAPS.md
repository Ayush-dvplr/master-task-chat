NEW MASTER GAPS (asked Ayush 5 Nov 2026 01:51 IST; WAITING). What the new master in ROOT does on its own, checked against STATE_CARD.md, README.md, RULES_IN_FORCE.md and the three cold test replies (4 Nov 23:55, 5 Nov 00:01, 5 Nov 00:31).

1. Today's goal: raised by itself (card line "not today: ask Ayush for today's goal"; all three cold masters asked).
2. QC kit classify: partly. The card QC KIT line always shows the change; the first cold master proposed it, the third did not. It does not know the workaround (snapshot has no text copy, so the evidence is git -C ROOT/Terminal_2.0_Harbor_Harness diff 5574d77e 48726eb7 -- Input_Bundle_QC); that is only in the prompt the session gave Ayush.
3. Where task sessions start: NOT raised. No record says start task sessions with opencode in ROOT (DCP off, ROOT/.opencode/dcp.jsonc), not in master_chat_tasks.
4. Compression: NOT raised. DCP is manual; nothing tells the master to remind Ayush or to ask for part E first.
5. JD-16 keep (ENTRY 109): the master does not know it; it will ask keep or fix again until minor_decisions.py record runs (command given to Ayush) or Ayush answers keep in the master.
6. Data-product: the cold master raised JD-16, the missing QL QC and the predicted final over the gate by itself; it did NOT raise TS-26 and JD-14 (treats them as kept, from the old QC v2 report).

Question put to Ayush: add 3, 4 and the TS-26 and JD-14 point (and the kit evidence workaround) to the master's rules or state card in the next release mc2-v2.5.4 (with 9718df83)? Options to offer when he answers: yes in mc2-v2.5.4 (Recommended); or he tells the master himself each time.
Also open: whether the remaining data-product decisions move to the new master (then mark them handed over in RESUME, NEXT and DATA_PRODUCT_TRIAGE.md).
