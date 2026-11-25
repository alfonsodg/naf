# Container image

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Image** | `ghcr.io/alfonsodg/naf:<tag>` |
| **Location** | `Dockerfile`, `.dockerignore`, `.github/workflows/container.yml` |

## Build

A plain branch push never builds. Pushing a tag runs
`.github/workflows/container.yml`, which builds with Buildx and publishes the
image plus a `sha-<short>` tag:

```bash
git tag -a feat-50-1 -m "Container build: <what changed>"
git push origin feat-50-1
```

Issue builds use `<type>-<issue>-<n>`; releases use `vMAJOR.MINOR.PATCH`. The
image is never built by hand: the pipeline is the only producer.

## Shape

- Two stages: a builder that resolves `uv.lock` into a virtual environment and a
  runtime that copies it.
- The environment is created at `/app/.venv`, the path it keeps at runtime, so
  the console scripts work after the copy. The project is installed
  non-editable.
- Runtime runs as `nobody`, exposes port 8000, carries `alembic.ini`, and answers
  `GET /health` in its healthcheck.
- The `tts` extra installs Kokoro ONNX; the model and the voice bank are not
  baked in. They are mounted read-only from `NAF_MODELS_DIR` at `/models`.
- `README.md` is copied because `pyproject.toml` names it as the package readme.

## Context exclusions

`.dockerignore` keeps `.git/`, the virtual environments, `docs/`, `tests/`,
caches, `worktrees/`, and the local-only operational files out of the build
context. Secrets never enter the image: the provider key, the reader token, and
the proxy password are runtime environment values.

## Verification

The pipeline runs lint, format, types, bandit, the dependency audit, and the unit
and contract suite before the image is pushed; a red job publishes nothing. The
`Dependency audit` step fails on an advisory reachable from the runtime set, so a
tag cannot ship a known vulnerable pin.
