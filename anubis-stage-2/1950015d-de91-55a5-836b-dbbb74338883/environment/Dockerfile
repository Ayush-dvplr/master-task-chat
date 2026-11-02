# Bundle: 1950015d-de91-55a5-836b-dbbb74338883
FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b

RUN groupadd -g 1000 agent && useradd -u 1000 -g 1000 -m -d /home/agent -s /bin/bash agent
ENV HOME=/home/agent

RUN apt-get update && apt-get install -y --no-install-recommends \
        xxd \
        file \
        bash \
        procps \
        nodejs \
        npm \
        curl \
        ca-certificates \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Offline readers for every container the settlement drop uses.
RUN pip install --no-cache-dir --default-timeout=180 --retries 10 \
        pyarrow==18.1.0 \
        openpyxl==3.1.5 \
        python-docx==1.1.2 \
        pdfplumber==0.11.4 \
        pypdf==5.1.0 \
        PyYAML==6.0.3 \
        lxml==5.3.0 \
        icalendar==6.1.0 \
    && python -c "import pyarrow, openpyxl, docx, pdfplumber, pypdf, yaml, lxml, icalendar"

# anubis: pre-baked agent so a sealed (no-network) run can start the agent.
RUN python3.12 -m venv /opt/openhands-sdk-venv \
    && /opt/openhands-sdk-venv/bin/pip install --no-cache-dir --default-timeout=120 --retries 10 openhands-sdk==1.55.1 openhands-tools==1.55.1 litellm==1.105.0 fastapi \
    && /opt/openhands-sdk-venv/bin/python -c "import openhands.sdk, openhands.tools" \
    && chmod -R a+rX /opt/openhands-sdk-venv

WORKDIR /app

RUN mkdir -p /app && chown 1000:1000 /app
RUN mkdir -p /app/out && chown 1000:1000 /app/out

COPY data /app/data
