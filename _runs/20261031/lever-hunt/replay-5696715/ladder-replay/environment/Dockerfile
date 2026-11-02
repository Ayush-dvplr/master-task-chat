FROM qcwarm-b7c42a8f-env:latest
USER root
RUN rm -rf /app/data /app/out && mkdir -p /app && chown 1000:1000 /app
COPY data /app/data
WORKDIR /app
