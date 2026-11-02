# Bundle: 9bb234eb-e964-5e0b-b8a9-37e9d58b887c
FROM python:3.12-slim
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
        curl \
        bash \
        nodejs \
        npm \
        procps \
        ca-certificates tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pre-baked agent runtime so a sealed (no-network) run can start the agent.
RUN mkdir -p /app && chown 1000:1000 /app

COPY data /app/data
