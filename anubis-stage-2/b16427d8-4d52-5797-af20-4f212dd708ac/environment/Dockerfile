# ECR: 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:b16427d8-4d52-5797-af20-4f212dd708ac-env
FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN id agent >/dev/null 2>&1 || (groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent)
ENV HOME=/home/agent
RUN apt-get update && apt-get install -y --no-install-recommends xxd file curl bash procps ca-certificates tmux && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pyarrow==17.0.0 PyYAML==6.0.3 openpyxl==3.1.5 python-docx==1.1.2 pypdf==5.0.1 lxml==5.3.0
# Pre-baked agent runtime so a sealed (no-network) run can start the agent.
RUN python3.12 -m venv /opt/openhands-sdk-venv \
    && /opt/openhands-sdk-venv/bin/pip install --no-cache-dir openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk, openhands.tools" \
    && chmod -R a+rX /opt/openhands-sdk-venv
RUN mkdir -p /app && chown 1000:1000 /app
WORKDIR /app
COPY data /app/data
