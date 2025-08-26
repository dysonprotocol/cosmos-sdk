# syntax=docker/dockerfile:1.6

#
# Multi-stage build for dysonprotocol2
# - builder: installs deps and runs `make build` to produce dysond
# - runtime: minimal image with the dysond binary
#

FROM golang:1.24-bullseye AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    git \
    make \
    patch \
    python3 python3-venv python3-pip \
    zstd \
    curl \
    jq \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy the full repository
COPY . .

# Build dysond binary into build/dysond
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    GOFLAGS='-buildvcs=false' make build


FROM debian:bookworm-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    bash \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /root

# Copy dysond binary
COPY --from=builder /workspace/build/dysond /usr/local/bin/dysond

# Default to printing version; override with `docker run ... dysond start` as needed
CMD ["dysond", "version", "--long"]


