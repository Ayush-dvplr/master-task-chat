FROM lever-b2-python:3.12
RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent
RUN apt-get update && apt-get install -y --no-install-recommends xxd file curl bash nodejs npm procps ca-certificates tmux && rm -rf /var/lib/apt/lists/*
# Pre-baked agent runtime so a sealed (no-network) run can start the agent.
RUN mkdir -p /app && chown 1000:1000 /app
WORKDIR /app
COPY data /app/data
