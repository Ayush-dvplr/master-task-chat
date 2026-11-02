FROM python:3.12-slim
ENV HOME=/home/agent

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tmux \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent


RUN mkdir -p /app/data /app/out && chown -R 1000:1000 /app

COPY --chown=1000:1000 data /app/data
WORKDIR /app
USER 1000:1000
