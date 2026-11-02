# Bundle: 6defadfe-9c50-5aa1-b854-8d5c1718d794
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
        curl \
        bash \
        nodejs \
        npm \
        procps \
        tzdata \
        unzip \
        sqlite3 \
        ca-certificates tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pre-baked agent runtime so a sealed (no-network) run can start the agent.
RUN python3.12 -m venv /opt/openhands-sdk-venv \
    && /opt/openhands-sdk-venv/bin/pip install --no-cache-dir openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk, openhands.tools" \
    && chmod -R a+rX /opt/openhands-sdk-venv
# Offline parsers for every feed format, pinned.
RUN pip install --no-cache-dir PyYAML==6.0.2 pyarrow==18.1.0 pypdf==5.1.0 pdfplumber==0.11.4 openpyxl==3.1.5 \
        python-docx==1.1.2 lxml==5.3.0 icalendar==6.1.0 tzdata==2025.2 setuptools==75.6.0
RUN mkdir -p /app && chown 1000:1000 /app
RUN mkdir -p /app/out /app/project && chown 1000:1000 /app/out /app/project

COPY data /app/data
