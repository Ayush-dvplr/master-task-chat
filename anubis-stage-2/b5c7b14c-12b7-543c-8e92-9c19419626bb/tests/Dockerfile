# Verifier image for b5c7b14c-12b7-543c-8e92-9c19419626bb.
# The suite imports only the standard library and the rewardkit runner pinned
# below. The verifier owns its own
# extract generator and its own engine, so it never reads the agent corpus.
FROM 426628337772.dkr.ecr.ap-south-1.amazonaws.com/anubis:python-3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends util-linux && rm -rf /var/lib/apt/lists/* && getent passwd nobody && getent group nogroup


RUN pip install --no-cache-dir harbor-rewardkit==0.2.1 litellm==1.105.0
ENV LITELLM_LOCAL_MODEL_COST_MAP=True
COPY . /tests/

RUN chmod -R go-rwx /tests
RUN mkdir -p /app/out
WORKDIR /app
