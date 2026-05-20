# wtftools — one-shot diagnostic CLI in a container.
#
# Typical use: run from CI/agent jobs against the host:
#   docker run --rm --pid=host --net=host -v /:/host:ro \
#              ghcr.io/wachawo/wtftools wtf problems
#
# NB: most checks need broad visibility — `--pid=host` so we see all
# processes, `--net=host` so listening-port + DNS probes work, a read-only
# bind of `/` for disk/cron/journal-file inspection. Check coverage on an
# isolated container is otherwise limited.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="wtftools"
LABEL org.opencontainers.image.description="One command to see what is going on with your Linux server right now."
LABEL org.opencontainers.image.source="https://github.com/wachawo/wtftools"
LABEL org.opencontainers.image.licenses="MIT"

# Tools wtftools probes for. Install the lot so checks degrade as little as
# possible on the host. Most cost <2MB.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        procps iproute2 \
        systemd-sysv \
        cron \
        smartmontools \
        openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/wtftools
COPY pyproject.toml README.md LICENSE MANIFEST.in ./
COPY wtftools/ ./wtftools/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir .[full]

ENTRYPOINT ["wtf"]
CMD ["--version"]
