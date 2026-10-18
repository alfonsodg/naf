# naf

News aggregator with categorized feeds and on-demand audio reports in Spanish.

Reads feeds via [Miniflux](https://github.com/miniflux/v2) API and adds
on-demand text/audio digests with mandatory citations, plus optional AI/model
announcement enrichment.

## Status

Phase 1 skeleton (see `docs/`). Spec: `docs/PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md`.

- **Decisions:** `docs/DECISIONS.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Contracts:** `docs/CONTRACTS.md`
- **Issues:** GitHub Issues (meta #1, phases #2-#8, TTS #9)

## Development

```bash
# Install
uv sync

# Configure
cp .env.example .env  # fill in values

# Run API
make dev  # http://localhost:8000 (docs at /docs)

# Tests / lint
make test
make lint
```

## Structure

```text
app/
  contracts/   # ports (interfaces)
  adapters/    # miniflux client, LLM, TTS, storage
  core/        # config, exceptions
  models/      # SQLAlchemy (complement DB)
  services/    # collector, classifier, report, audio
  api/routes/  # FastAPI endpoints
tests/
  unit/        # domain + API
  contract/    # adapter contracts (mocked responses)
```

**Rule:** reader state (feeds/entries/read state) lives in Miniflux, accessed
only via its REST API. NAF owns only digest/audio/classification data.

## License

Apache-2.0. See `LICENSE`.
