# Bundle: 0b27b9dc-7985-54f1-a120-46e6810315a3
FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent

# The task itself is a standard library Python solver over a text corpus, and
# xxd and file help with triaging thirteen unlabelled encodings by hand. The
# remaining packages are what the harness needs to install and run an agent
# inside this container, so baking them here keeps agent setup off the slow
# path. The agent itself is never baked in; the image stays agent neutral.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xxd \
        file \
        bash \
        curl \
        nodejs \
        npm \
        procps \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# anubis: pre-baked agent so a sealed (no-network) run can start the agent.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates tmux \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && . "$HOME/.local/bin/env" \
    && uv venv /opt/openhands-sdk-venv --python /usr/local/bin/python3.12 --clear \
    && . /opt/openhands-sdk-venv/bin/activate \
    && uv pip install 'openhands-sdk==1.55.1' 'openhands-tools==1.55.1' fastapi 'litellm==1.105.0' \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk" \
    && chmod -R a+rX /opt/openhands-sdk-venv
# The bootstrap above ran as root with HOME=/home/agent; hand the home back.
RUN chown -R 1000:1000 /home/agent

WORKDIR /app
RUN mkdir -p /app
RUN mkdir -p /app/out
COPY data /app/data
# task.toml runs the agent and oracle as uid 1000, so it must own /app to write
# the declared artifacts into /app/out; chown changes ownership, not contents.
RUN chown -R 1000:1000 /app
