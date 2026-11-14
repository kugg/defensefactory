# syntax=docker/dockerfile:1.7
FROM node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS node-runtime
FROM golang:1.23-bookworm@sha256:167053a2bb901972bf2c1611f8f52c44d5fe7e762e5cab213708d82c421614db AS go-runtime
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ARG OPENCODE_VERSION=1.19.5
ARG FACTORY_RELEASE_COMMIT=0000000000000000000000000000000000000000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/* \
    && true

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=go-runtime /usr/local/go /usr/local/go

RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && npm install --global "opencode-ai@${OPENCODE_VERSION}" \
    && npm cache clean --force

WORKDIR /opt/defensefactory
COPY . /opt/defensefactory

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/usr/local/go/bin:$PATH \
    FACTORY_RELEASE_COMMIT=${FACTORY_RELEASE_COMMIT}

LABEL org.opencontainers.image.title="Defense Factory alpha" \
      org.opencontainers.image.description="Manually operated ticket-driven security remediation workflow" \
      org.opencontainers.image.source="https://github.com/kugg/defensefactory" \
      org.opencontainers.image.revision=${FACTORY_RELEASE_COMMIT} \
      org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["python3", "-m", "release.alpha.entrypoint"]
CMD ["validate"]
