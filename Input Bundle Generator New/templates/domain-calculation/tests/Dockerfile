FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends util-linux \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/
RUN mkdir -p /app
WORKDIR /app
