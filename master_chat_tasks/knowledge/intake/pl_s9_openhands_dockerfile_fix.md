# PL procedure: pre-bake openhands-sdk in environment/Dockerfile (QC S9) - from Ayush 20 Oct 23:53 IST
Shared by PL as a "hardness check" but it is actually the S9 Dockerfile fix. Verbatim content kept in Ayush's message; key points:
- Edit only environment/Dockerfile. Final stage (after last FROM) must have all 5:
  1. apt: curl, ca-certificates, tmux  2. venv at exactly /opt/openhands-sdk-venv
  3. openhands-sdk openhands-tools fastapi in that venv  4. build-time /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk"
  5. chmod -R a+rX /opt/openhands-sdk-venv
- All present: change nothing ("already baked in"). None: insert PL block. Partial: add only missing pieces in same style.
- New lines after existing apt/RUN installs, before WORKDIR / COPY data. No version pins, no reorder/removal.
- PL block:
  RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates tmux && rm -rf /var/lib/apt/lists/*
  RUN curl -LsSf https://astral.sh/uv/install.sh | sh && . "$HOME/.local/bin/env" && uv venv /opt/openhands-sdk-venv --python /usr/local/bin/python3.12 --clear && . /opt/openhands-sdk-venv/bin/activate && uv pip install openhands-sdk openhands-tools fastapi && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk" && chmod -R a+rX /opt/openhands-sdk-venv
  (base not python:3.12 and no /usr/local/bin/python3.12 -> use --python 3.12)
- Verify: structure_qc.py <BUNDLE> shows "pass [S9]". PL path is /Users/apple/...; on this Mac use
  /Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/structure_qc.py
- Note: PL generator already emits this (commit 1096b244 'pre-baked openhands-sdk runtime'); needed for hand-built or older bundles.
