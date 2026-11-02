# Questions for Ayush

1. The prompt says `anubis-stage-2` has 52 tasks, but the current checkout has 102 `task.toml` folders and 204 model summaries (`scripts/extract_tasks.py` output). Did you intend a particular 52-task cohort?
   - **Recommended: all 102 current tasks.** It uses the whole available evidence and keeps the inventory reproducible.
   - Alternative: a specific 52-task snapshot/list. Please provide its commit or IDs; then rerun the scripts for that cohort.
