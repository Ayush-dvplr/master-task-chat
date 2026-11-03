RESEARCH INTAKE (W1-034, 3 Nov 2026; draft, not applied)

Purpose: a deep research answer pasted back from ChatGPT or Gemini is stored once, split into items a script can read, and fed into the next prompt, so nothing is lost at compaction and nothing is asked twice. research_prompt.py builds the prompt; this file says what happens to the answer.

1. BEFORE THE PASTE
1. The master runs research_prompt.py with a kind (verify, discover, explore, teammate_study) and saves the prompt as master_chat_work/research/<YYYYMMDD>/<prompt_id>.prompt.txt. The prompt id carries the kind, the IST time and a digest of the knowledge files it was built from.
2. Following the reply file rule (decisions.jsonl:37), the master creates an empty answer file and gives Ayush that exact path: master_chat_work/research/<YYYYMMDD>/<prompt_id>__<tool>.md (tool is chatgpt or gemini). One file per answer; a second tool on the same prompt gets its own file.

2. STORING THE ANSWER
1. Ayush pastes the whole reply into the answer file. The file is never edited after that; it is the raw record.
2. An intake script (to be built; standard library) reads only the text between BEGIN RESEARCH ANSWER and END RESEARCH ANSWER and writes one line per ITEM to master_chat_work/research/INTAKE.jsonl with: id (R plus a running number), prompt_id, tool, answer_file, item number, type, family, relation, title, statement, evidence, confidence, check, the idea fields, status "new", received_ist.
3. Every item of type idea is also appended to master_chat_tasks/registry/ideas.jsonl (the master's idea gate log) with: ist, batch (the prompt id), idea number, title, family, domain, source ("research <prompt_id> <tool> <answer_file> item <n>"), status "new", verdict null. master_chat_work/gen_memory/ideas.jsonl belongs to the generator and is not written.
4. Checks at intake: an item whose title and family match an existing INTAKE or ideas.jsonl row gets status "duplicate" with the id it repeats; an item that cites no source gets confidence lowered to low; a reply without the BEGIN and END lines is stored as status "unparsed" and the master asks Ayush once to ask the tool to reformat it to the answer format.
5. Teammate patterns (teammate_study) store task ids only; names in a reply are removed at intake.

3. STATUS LIFE OF AN ITEM
Claims: new, then checked (the master or a read only session ran the item's check line on our records), then verified or refuted.
Ideas: new, then carded (a DESIGN_CARD_TEMPLATE.md card exists), then built, kept part (the card failed and parts were kept, DESIGN_FLOW.md step D) or rejected (with the reason: copy, unsolvable, family not allowed, leak shape).
Angles: new, then run (a research or study session ran it), then S, M, W or N strength as in ANGLES.md.
Each change is one appended line (id, new status, reason, IST); lines are never rewritten.

4. NOTHING BECOMES A RULE WITHOUT AYUSH
1. A verified claim, a held angle or a working idea is evidence, not a rule. It changes BUILD_RULES.md, PATTERNS.md, CONFIRM.md, LEVER_RULES, templates or settings only after Ayush says so; the master lists such items under "for Ayush" in its next report with the item id and the evidence.
2. Ideas may enter the design queue (DESIGN_FLOW.md step A3) without a rule change, because a card still passes the design checks before any build.
3. An angle enters ANGLES.md's untried list only through the master's merge, as today.

5. HOW THE NEXT PROMPT USES IT
research_prompt.py reads INTAKE.jsonl on every run:
1. Every received title is listed under "what to avoid repeating", so the same idea or claim is not asked for again.
2. verify lists claims with status new as I ids and asks for outside evidence on them first.
3. discover lists all received ideas (and their verdicts) as already received, and the rotation reads design_cards.jsonl, so a family or domain used by the last cards is excluded.
4. Refuted claims and rejected ideas stay listed with their status, so a tool does not propose them again.
5. Because each prompt header carries the digests of the files it was built from, an answer can be matched to the knowledge state it saw; an answer built on an older digest is still stored, and its items are checked against the current files at intake.
