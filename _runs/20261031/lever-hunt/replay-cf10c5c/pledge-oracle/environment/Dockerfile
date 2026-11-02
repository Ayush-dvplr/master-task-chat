# Bundle: df8f123b-6d6c-5e28-bb60-fb4f45111e6c
FROM lever-b2-python:3.12
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
RUN mkdir -p /app && chown 1000:1000 /app
RUN mkdir -p /app/out && chown 1000:1000 /app/out && chmod 775 /app/out
COPY service /app/service
COPY data /app/data
