# syntax=docker/dockerfile:1.7

# Build context: repository root (so `.git/` is available for hatch-vcs).
# Build with: docker build -f mcp/Dockerfile .

FROM python:3.14-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# git is needed by hatch-vcs to derive the version from tags at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY .git ./.git
COPY mcp/pyproject.toml mcp/README.md ./
COPY mcp/src ./src

RUN pip install build \
    && python -m build --wheel --outdir /wheels .

FROM python:3.14-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=builder /wheels /wheels

RUN pip install /wheels/*.whl && rm -rf /wheels

USER 65532:65532

ENTRYPOINT ["tee-sniper-mcp"]
