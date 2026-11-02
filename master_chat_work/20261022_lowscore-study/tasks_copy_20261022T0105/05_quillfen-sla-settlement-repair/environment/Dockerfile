FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN apt-get update && apt-get install -y --no-install-recommends xxd file curl bash nodejs npm procps ca-certificates unzip zip && rm -rf /var/lib/apt/lists/*
# anubis: pre-baked agent so a sealed (no-network) run can start the agent.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates tmux \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && . "$HOME/.local/bin/env" \
    && uv venv /opt/openhands-sdk-venv --python /usr/local/bin/python3.12 --clear \
    && . /opt/openhands-sdk-venv/bin/activate \
    && uv pip install openhands-sdk openhands-tools fastapi \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk" \
    && chmod -R a+rX /opt/openhands-sdk-venv
RUN mkdir -p /app
RUN mkdir -p /app/out && chown 1000:1000 /app/out
WORKDIR /app
COPY data /app/data
