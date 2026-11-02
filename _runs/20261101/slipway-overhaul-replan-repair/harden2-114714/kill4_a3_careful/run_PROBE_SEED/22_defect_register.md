# Defect register

| stage | reason code | label |
| --- | --- | --- |
| p01 | JOB-DRAFTONLY | job set aside |
| p01 | JOB-NOPRECINCT | job set aside |
| p01 | JOB-WITHDRAWN | job set aside |
| p02 | EDG-ADVISORY | edge rejected |
| p02 | EDG-CROSSPRECINCT | edge rejected |
| p02 | EDG-CYCLE | edge rejected |
| p02 | EDG-DUPLICATE | edge rejected |
| p02 | EDG-SELF | edge rejected |
| p02 | EDG-UNKNOWNJOB | edge rejected |
| p02 | EDG-WITHDRAWN | edge rejected |
| p02 | JOB-CYCLE | job set aside |
| p04 | JOB-LICENCE | job set aside |
| p04 | JOB-OUTOFROUND | job set aside |
| p05 | JOB-CLOSUREBLOCKED | job set aside |
| p08 | GRP-DOUBLEBOOKED | group membership rejected |
| p08 | GRP-SINGLE | group carries no constraint |
| p13 | AMD-NOTARGET | amendment rejected |
| p13 | CMT-UNKNOWN | amendment rejected |

Modules in force: __init__, __main__, cache, cells, charge, closure, graph, mutate, normalise, objective, publish, reading, search
