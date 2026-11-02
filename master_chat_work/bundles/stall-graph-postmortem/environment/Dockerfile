FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent
RUN apt-get update && apt-get install -y --no-install-recommends xxd file curl bash tmux nodejs npm procps ca-certificates && rm -rf /var/lib/apt/lists/*
# anubis: pre-baked agent so a sealed (no-network) run can start the agent.
RUN python3.12 -m venv /opt/openhands-sdk-venv \
 && /opt/openhands-sdk-venv/bin/pip install --no-cache-dir openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi \
 && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk, openhands.tools" \
 && chmod -R a+rX /opt/openhands-sdk-venv
RUN mkdir -p /app/out && chown -R 1000:1000 /app
WORKDIR /app
COPY --chown=1000:1000 data /app/data
