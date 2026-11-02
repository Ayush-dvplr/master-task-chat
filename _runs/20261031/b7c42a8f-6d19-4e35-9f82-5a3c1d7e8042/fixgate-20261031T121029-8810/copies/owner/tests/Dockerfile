FROM python:3.12-slim
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
RUN apt-get update && apt-get install -y --no-install-recommends util-linux \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0
RUN groupadd -g 1001 verifier && useradd -u 1001 -g 1001 -m -d /home/verifier -s /bin/bash verifier
RUN groupadd -g 1002 solver   && useradd -u 1002 -g 1002 -m -d /home/solver   -s /bin/bash solver
RUN mkdir -p /app && chown -R 1002:1002 /app
RUN mkdir -p /logs/verifier && chown root:root /logs/verifier && chmod 755 /logs/verifier
COPY . /tests/
RUN chmod -R go-rwx /tests
WORKDIR /app
USER root
