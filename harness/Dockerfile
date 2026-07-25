# Agent Evals — reproducible eval environment
# Provides kicad-cli, ngspice, and freecad-cli for engineering eval runs.
#
# Build:    docker build -t agent-evals:0.1 harness/
# Run:      docker run --rm -v $(pwd):/work -w /work agent-evals:0.1 kicad-cli pcb drc foo.kicad_pcb
FROM kicad/kicad:9.0

LABEL maintainer="jp@agent-evals.local"
LABEL description="Reproducible eval environment for AI coding agents on KiCad / FreeCAD / ngspice"

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Install additional engineering tools not in the image by default
RUN apt-get update && apt-get install -y --no-install-recommends \
        ngspice \
        python3-pip \
        python3-yaml \
        python3-jinja2 \
        openscad \
        git \
        jq \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# FreeCAD is intentionally not in the base KiCad image — it would bloat ~1.5GB.
# When FreeCAD evals are needed, build a separate image:
#   FROM agent-evals:0.1; RUN apt-get install -y freecad
# Documented in research/freecad-install.md.

# Verify CLI versions (best-effort: tools may not be installed in CI)
RUN kicad-cli version || echo "kicad-cli not found"; \
    ngspice --version 2>&1 | head -1 || echo "ngspice not found"; \
    python3 --version || echo "python3 not found"

WORKDIR /work
