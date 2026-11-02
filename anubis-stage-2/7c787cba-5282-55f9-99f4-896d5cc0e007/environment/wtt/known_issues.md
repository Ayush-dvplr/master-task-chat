# Known issues

Operator notes kept with the extract. None of this changes the contract; it
records what the compile desk has already found.

1. The compiler in the repository is the 4.2 build and its last run stopped
   before the digest stage. Its partial output was kept as
   `legacy_compiled_output.json`. The figures in that file disagree with the
   rulebook in several places and it is kept only so the two can be compared.
2. The 4.2 build is known to disagree with the rulebook. The compile desk has
   not written down where, and reading the rulebook against the code is the way
   to find out. Treat the code as the thing under repair and the rulebook as
   the authority, never the other way round.
3. Several faults in the 4.2 build leave this extract's output unchanged and
   only show on other periods, because this period happens to miss the cases
   they govern. Reproducing this extract is therefore not proof that the compile
   is right.
4. The previous issue of the path register, the unapproved rule draft and the
   proposed transition table were all left in the extract by the archiver.
   `file_role_index.md` is the only place that says which copy decides.
5. The mailbox carries more than one headway message. Only the approved prefix
   changes a value.
6. The debug log of the aborted run is kept for operators. It names a warning
   for an alias walk and a warning for a local departure with no instant; both
   are ordinary and the rulebook says what to do with each.
