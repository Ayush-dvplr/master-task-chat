# ECR: 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:98ed74c1-19ac-5ec8-adaf-392a172d4600-env
# Bundle: 98ed74c1-19ac-5ec8-adaf-392a172d4600
FROM python:3.12-slim
RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent

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
