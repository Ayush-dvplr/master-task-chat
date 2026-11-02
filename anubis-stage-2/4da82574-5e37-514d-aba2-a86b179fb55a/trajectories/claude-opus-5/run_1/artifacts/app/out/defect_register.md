# Defect register

| stage | reason code | meaning |
| --- | --- | --- |
| r09 | CMP-NOTARGET | the named target sits outside the canonical history |
| r09 | CMP-WITHDRAWN | the compensation link is absent or withdrawn |
| r07 | DEP-CYCLE | the record sits on a dependency cycle |
| r07 | DEP-MISSING | a dependency is neither in the checkpoint nor earlier in the window |
| r07 | DEP-SELF | the record names itself as a dependency |
| r01 | EVT-DRAFTREVISION | the record lodges above the frozen register revision |
| r01 | EVT-IMPLAUSIBLE | the normalised quantity passes the memo ceiling |
| r01 | EVT-NONPOSITIVE | the normalised quantity is zero or below |
| r02 | EVT-UNKNOWNPROGRAMME | the programme is absent from the register |
| r02 | EVT-UNKNOWNSTATION | the station is absent from the frozen register |
| r01 | EVT-WITHDRAWN | the identifier sits in the withdrawn journal |

Stages in force: r01, r02, r03, r04, r05, r06, r07, r08, r09, r10, r11, r12, r13, r14
