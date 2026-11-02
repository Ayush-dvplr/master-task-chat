# Decision for Ayush

1. After an idle-window cleanup, how much BuildKit cache should Docker keep?
   - **Recommended: 15 GB.** Trims about 3.73 GB of cache accounting from the 18.73 GB snapshot while keeping more warm build layers (`inventory/buildx_du_verbose.txt:7914-7917`; `CLEANUP.md:39-51`).
   - **10 GB.** Trims up to 8.73 GB of cache accounting, with more risk that the next verifier/environment build downloads dependencies again (`CLEANUP.md:39-51`; `BUILD_LOGS.csv` two costly cold steps).

No Docker cleanup was run in this learning session.
