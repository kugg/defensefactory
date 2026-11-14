# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim

ARG OPENCODE_VERSION=1.19.5
ARG FACTORY_RELEASE_COMMIT=0000000000000000000000000000000000000000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force

WORKDIR /opt/defensefactory
COPY . /opt/defensefactory

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FACTORY_RELEASE_COMMIT=${FACTORY_RELEASE_COMMIT}

LABEL org.opencontainers.image.title="Defense Factory alpha" \
      org.opencontainers.image.description="Manually operated ticket-driven security remediation workflow" \
      org.opencontainers.image.source="https://github.com/kugg/defensefactory" \
      org.opencontainers.image.revision=${FACTORY_RELEASE_COMMIT} \
      org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["python3", "-m", "release.alpha.entrypoint"]
CMD ["validate"]
