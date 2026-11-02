# Bundle: a7e17524-bb15-58d4-aff0-9bfb65a0846d
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
        xxd \
        file \
        bash \
        curl \
        nodejs \
        npm \
        procps \
        ca-certificates tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Pre-baked agent runtime so a sealed (no-network) run can start the agent.
RUN python3.12 -m venv /opt/openhands-sdk-venv \
    && /opt/openhands-sdk-venv/bin/pip install --no-cache-dir openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk, openhands.tools" \
    && chmod -R a+rX /opt/openhands-sdk-venv
RUN mkdir -p /app && chown 1000:1000 /app
RUN mkdir -p /app/out && chown 1000:1000 /app/out
COPY service /app/service
COPY data /app/data
