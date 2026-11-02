FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0 pyarrow==19.0.1 openpyxl==3.1.5 python-docx==1.1.2 pypdf==5.4.0 pdfplumber==0.11.6 lxml==5.3.1 PyYAML==6.0.3 icalendar==6.1.3 tomli==2.2.1
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/
RUN mkdir -p /app
WORKDIR /app
