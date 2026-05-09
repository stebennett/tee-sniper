# syntax=docker/dockerfile:1.7

# Build context: repository root.
# Build with: docker build -f mcp/Dockerfile --build-arg VERSION=<x.y.z> .
#
# VERSION is forwarded to hatch-vcs via SETUPTOOLS_SCM_PRETEND_VERSION so the
# image does not need .git/ available at build time.

FROM python:3.14-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

ARG VERSION=0.0.0+unknown
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

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
