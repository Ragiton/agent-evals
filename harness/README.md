# Agent Evals container

`Dockerfile` builds an immutable KiCad 9.0.8 evaluation image with the
additional command-line tools used by the deterministic graders:

- `kicad-cli` from the pinned `kicad/kicad:9.0.8` image
- `ngspice`
- `freecad-cli` (a headless wrapper around Debian's `freecadcmd-python3`)
- Python 3, Bash, Git, jq, PyYAML, and Jinja2
- `runner.py`, `grader.py`, `cross_grade.py`, and `aggregate.py`

The base image is pinned by digest in `Dockerfile`; the image currently
publishes an amd64 Linux platform.

## Build and verify

From the project root:

```bash
./harness/verify-container.sh agent-evals:9.0.8
```

The script builds with `harness/` as the Docker build context, runs the
container's `verify` command, and prints the resulting immutable Docker image
identifier. The smoke test prints versions for KiCad, ngspice, FreeCAD, Python,
and Bash, imports the harness's Python dependencies, and invokes `--help` on
each harness entry point.

Equivalent manual commands:

```bash
docker build --pull -t agent-evals:9.0.8 harness/
docker run --rm agent-evals:9.0.8 verify
docker image inspect --format '{{.Id}}' agent-evals:9.0.8
```

## Running harness commands

Mount the project when an eval spec or run directory is on the host:

```bash
docker run --rm -v "$PWD:/workspace" agent-evals:9.0.8 \
  runner.py --spec /workspace/evals/01-led-blinky-minimal.yaml \
  --agent claude-code --dry-run
```

The entrypoint also accepts `grader.py`, `cross_grade.py`, `aggregate.py`, or
an arbitrary executable such as `kicad-cli`.
