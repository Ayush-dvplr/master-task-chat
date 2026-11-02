# Decision only Ayush can make

1. **Can a QC recheck use gate runs from its fix session to qualify for the next paid run?** The live QC kit asks for five oracle runs in Step 10 (`Terminal_2.0_Harbor_Harness/Input_Bundle_QC/Final_checklist.md:354-367,390`). P12 currently runs three; Ayush approved one oracle plus nop as the recheck spot check (`FAST_TRACK_PLAN_v1.md` section 4), while P11 calls a round with fewer than five “not kit-complete” (`P11_full_qc_v3.md:89-90`).
   - **Recommended: require a complete five-oracle QC round before the paid run.** Reuse still shortens exploratory rechecks, and paid-run readiness stays aligned with the kit. It reduces the expected time saving.
   - **Allow cross-session aggregation by exact tree SHA.** Count the fix session's three plus two recheck or follow-up oracle runs on identical bytes, with saved logs and a new explicit kit exception. This preserves more speed but changes how the kit's “this round” proof is interpreted.
