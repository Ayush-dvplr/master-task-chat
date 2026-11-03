STATE CARD (generated 03 Nov 2026 10:26 IST by tools/state_card.py; do not edit by hand)

RULES IN FORCE (one layer; the only rule text the master follows)
MISSING: RULES_IN_FORCE.md not found. Stop and tell Ayush.

TODAY
At least 4 push-ready tasks today, counting slipway (pushed 2 Nov 11:42). Sources allowed: flood and depot rebuilt with a new primary lever (R0 1a-c), parked bundles on disk; doc changes allowed; hangar go after the v3.8 upgrade, on Ayush's word. b7c42a8f is Nikhil's task: never counted, never issued without Ayush.

SESSIONS RUNNING OR ISSUED (3; Ayush decides when issued becomes running)
420bf9a | running | flood-repair-portfolio | flood fix QC v4 TS-16/TS-19/DS-27 (TS-26, AL-27 kept) | master_chat_tasks/prompts/issued/flood-repair-portfolio/20261102T2345_fix.md
ffd3a8e | running | sensor-network-lsq-correlated-adjustment | sensor full QC v3 on tree 380f417a8efd | master_chat_tasks/prompts/issued/sensor-network-lsq-correlated-adjustment/20261102T2330_qc.md
dabfeb4 | running | hangar-check-replan | hangar fix QC v4 F01-F07 | master_chat_tasks/prompts/issued/hangar-check-replan/20261102T2246_fix.md

ACTIVE TASKS (5)
sensor-network-lsq-correlated-adjustment | qc | next: full QC v3 ffd3a8e (issued 23:30) on tree 380f417a8efd, then freeze, 1 paid run
flood-repair-portfolio | fix | next: 420bf9a fix TS-16/TS-19/DS-27 (TS-26, AL-27 KEPT by Ayush 23:4x) then QC v5 recheck, freez
b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 | gate_runs | next: NIKHIL's task (not Ayush's): never count toward Ayush's pushes; never issue anything unles
hangar-check-replan | fix | next: dabfeb4 continue (Ayush 23:28 accepted pred mid 41.4): behaviour negative_hardcoded_sample
depot-charge-plan | gate_runs | next: a2 offline no lever (0/2312); off_route1/park HELD: Ayush flow review 2 Nov

OPEN ITEMS (top 10; full list: python3 tools/pending.py list)
Q52 | question | high | SECURITY: litellm 1.107.0 payload RAN 21 Oct 17:34 (uv cache env mGj267huY6AIjqVl). Ayush:
S429 | step | high | Today's goal 2 Nov: >=4 push-ready (slipway counts); hangar go after v3.8; pick 2 more fro
S393 | step | medium | Send district QL round-2 reply
Q46 | reminder | medium | Send PL notes: false positives + kept minors in master_chat_work/20261022_<slug>/p12_r*/PL
Q47 | question | medium | Ask PL: Anubis 07-10 verifiers fixed in 5d565653 but trajectories/rewards in repo are stil
Q20-22 | reminder | medium | Trial review ~23-24 Oct: pending lessons (Q22) and temp folder deletion (Q20)
Q48 | question | medium | Later: store a shasum manifest of every researched peer task (root-level files and folders
R08 | reminder | medium | Merge 6 Final_Delivery reads (9bd1ca1 d930be0 f272f70 36f01dd 9fc8d98 e841c43) into final_
R09 | reminder | medium | Later: let auto-mode QC sessions run oracle/nop/stub/forgery harbor runs (QC Step 10); kee
R11 | reminder | medium | Speed upgrade plan v1 (dockslot, 4 parallel gate lanes, recheck-only gate reuse, ~/tb_runs

HANDOFF FORMAT: a table with board sha, step, status and a clickable file link; never 'read and follow'.
