# wtftools — diagnostic CLI + wtfd daemon image
#
# Two use cases:
#   1) one-shot CLI in CI/agent jobs:
#        docker run --rm --pid=host --net=host -v /:/host:ro -v /var/run/dbus:/var/run/dbus \
#                   ghcr.io/wachawo/wtftools wtf audit --only problem
#   2) wtfd HTTP API for a fleet:
#        docker run -d --name wtfd --pid=host --net=host \
#                   -v /var/lib/wtftools:/var/lib/wtftools \
#                   ghcr.io/wachawo/wtftools wtfd --listen 0.0.0.0:8765 --save
#
# NB: most checks need broad visibility — `--pid=host` so we see all
# processes, `--net=host` so listening-port + DNS probes work, a read-only
# bind of `/` for disk/cron/journal-file inspection. The check coverage on
# an isolated container is otherwise limited.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="wtftools"
LABEL org.opencontainers.image.description="One command to see what is going on with your Linux server right now."
LABEL org.opencontainers.image.source="https://github.com/wachawo/wtftools"
LABEL org.opencontainers.image.licenses="MIT"

# Tools wtftools probes for. Install the lot so checks degrade as little as
# possible on the host. Most cost <2MB.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        procps iproute2 iputils-ping \
        systemd-sysv \
        cron \
        smartmontools \
        openssl ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/wtftools
COPY pyproject.toml README.md LICENSE MANIFEST.in wtf.1 ./
COPY wtftools/ ./wtftools/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir .[full]

# Sensible defaults for wtfd. Snapshots persist in /var/lib/wtftools which the
# operator typically volume-mounts.
ENV WTFTOOLS_SNAPSHOT_DIR=/var/lib/wtftools/snapshots
VOLUME ["/var/lib/wtftools"]

EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8765/healthz || exit 1

# Default to the CLI; override with `docker run … wtfd …` for daemon mode.
ENTRYPOINT ["wtf"]
CMD ["--version"]
