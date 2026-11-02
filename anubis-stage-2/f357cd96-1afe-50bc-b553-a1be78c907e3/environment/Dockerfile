FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent
RUN printf 'boto3==1.43.118\ns3transfer==0.19.3\n' > /tmp/openhands-constraints.txt
ENV PIP_CONSTRAINT=/tmp/openhands-constraints.txt \
    UV_CONSTRAINT=/tmp/openhands-constraints.txt \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=10 \
    UV_HTTP_TIMEOUT=300

RUN apt-get update && apt-get install -y --no-install-recommends \
        xxd file bash procps ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# anubis: pre-baked agent so a sealed (no-network) run can start the agent.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates tmux \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && . "$HOME/.local/bin/env" \
    && uv venv /opt/openhands-sdk-venv --python /usr/local/bin/python3.12 --clear \
    && . /opt/openhands-sdk-venv/bin/activate \
    && uv pip install openhands-sdk==1.55.1 openhands-tools==1.55.1 fastapi litellm==1.105.0 \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk" \
    && chmod -R a+rX /opt/openhands-sdk-venv

WORKDIR /app

# task.toml runs the agent as uid 1000, so it must own /app to write the
# declared artifacts into /app/out; chown changes ownership, not contents.
# COPY data below stays root-owned (read-only for the agent) as intended.
RUN mkdir -p /app /app/out && chown -R 1000:1000 /app

COPY data /app/data
