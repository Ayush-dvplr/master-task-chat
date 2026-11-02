FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
# util-linux carries setpriv, which grading uses to drop root before it runs
# the delivered program; the sandbox account owns nothing the grader trusts.
RUN apt-get update && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 4001 sandbox && useradd --uid 4001 --gid 4001 --no-create-home sandbox
RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/
RUN mkdir -p /app
WORKDIR /app
