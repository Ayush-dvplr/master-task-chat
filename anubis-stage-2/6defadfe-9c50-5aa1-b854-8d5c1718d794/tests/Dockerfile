FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux tzdata \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0 setuptools==75.6.0
RUN pip install --no-cache-dir --target /opt/deps/pyyaml PyYAML==6.0.2 \
 && pip install --no-cache-dir --target /opt/deps/pyarrow pyarrow==18.1.0 \
 && pip install --no-cache-dir --target /opt/deps/pypdf pypdf==5.1.0 \
 && chmod -R a+rX /opt/deps
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/
RUN mkdir -p /app
WORKDIR /app
