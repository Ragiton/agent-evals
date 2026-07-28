# syntax=docker/dockerfile:1
# Agent Evals — reproducible engineering-evaluation environment.
#
# The manifest-list digest is pinned so the floating `9.0` tag cannot silently
# change the KiCad toolchain. The image currently publishes an amd64 platform.
# Build from the project root with:
#   docker build --pull -t agent-evals:9.0.8 harness/
# Run the toolchain smoke test with:
#   docker run --rm agent-evals:9.0.8 verify
FROM kicad/kicad:9.0.8@sha256:cd1c0b6f3b35a1ad61ccfab1a5243ef0f7db554a7b6908dc942fca779598f865

ARG DEBIAN_FRONTEND=noninteractive
ARG FREECAD_VERSION=0.20.2+dfsg1-4
ARG NGSPICE_VERSION=39.3+ds-1

LABEL org.opencontainers.image.title="Agent Evals engineering toolchain"
LABEL org.opencontainers.image.description="KiCad CLI, ngspice, FreeCAD CLI, and the Agent Evals harness"

# The official KiCad image runs as the unprivileged `kicad` user. Become root
# only for the deterministic package installation, then drop privileges again.
USER root
ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    QT_QPA_PLATFORM=offscreen

# Debian Bookworm is the pinned base distribution. KiCad's image already
# supplies kicad-cli; these packages add the remaining grading toolchain and
# Python modules imported by runner.py, grader.py, and aggregate.py. FreeCAD
# and ngspice versions are explicit build arguments so an integration build
# can override them only deliberately; the base image digest above is the
# immutable anchor for the KiCad side of the environment.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        bash \
        ca-certificates \
        freecad=${FREECAD_VERSION} \
        freecad-python3=${FREECAD_VERSION} \
        git \
        jq \
        ngspice=${NGSPICE_VERSION} \
        python3 \
        python3-jinja2 \
        python3-pip \
        python3-yaml \
    && test -x /usr/lib/freecad/bin/freecadcmd-python3 \
    && ln -s /usr/lib/freecad/bin/freecadcmd-python3 /usr/local/bin/freecad-cli \
    && rm -rf /var/lib/apt/lists/*

# Build context is harness/, so the complete harness is copied into a stable
# path. The entrypoint gives short, documented aliases for runner.py,
# grader.py, cross_grade.py, and the toolchain smoke test.
COPY . /opt/agent-evals/harness/
RUN install --mode=0755 /opt/agent-evals/harness/container-entrypoint.sh /usr/local/bin/agent-evals \
    && mkdir --parents /workspace /tmp/agent-evals \
    && chown --recursive kicad:kicad /workspace /tmp/agent-evals

ENV HARNESS_DIR=/opt/agent-evals/harness \
    HOME=/tmp/agent-evals
WORKDIR /workspace
USER kicad

ENTRYPOINT ["/usr/local/bin/agent-evals"]
CMD ["help"]
