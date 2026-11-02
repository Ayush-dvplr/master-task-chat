FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux xxd file bash procps nodejs npm \
 && rm -rf /var/lib/apt/lists/* \
 && getent passwd nobody && getent group nogroup
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0
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
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/
RUN mkdir -p /app
WORKDIR /app
