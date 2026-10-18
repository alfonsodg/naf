# Integración Miniflux - evidencia real (Fase 2)

**Fecha:** 2026-10-18  
**Issue:** [#4](https://github.com/alfonsodg/naf/issues/4)  
**Entorno:** Podman local, `miniflux/miniflux:latest` (schema v132) +
`postgres:17-alpine`

## Setup reproducible

```bash
podman network create naf-test
podman run -d --name naf-pg --network naf-test \
  -e POSTGRES_USER=miniflux -e POSTGRES_PASSWORD=miniflux \
  -e POSTGRES_DB=miniflux docker.io/library/postgres:17-alpine
podman run -d --name naf-miniflux --network naf-test -p 8080:8080 \
  -e "DATABASE_URL=postgres://miniflux:miniflux@naf-pg/miniflux?sslmode=disable" \
  -e RUN_MIGRATIONS=1 -e CREATE_ADMIN=1 \
  -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=test123 \
  -e BASE_URL=http://localhost:8080 docker.io/miniflux/miniflux:latest
```

API key de prueba (solo entorno local): insertada en `api_keys` de la BD de
Miniflux para poder autenticar con `X-Auth-Token`.

## Resultados verificados

| Operación              | Método API                     | Resultado                                       |
| ---------------------- | ------------------------------ | ----------------------------------------------- |
| Health                 | `GET /healthcheck`             | `OK`                                            |
| Listar feeds           | `GET /v1/feeds`                | 10 feeds                                        |
| Entradas               | `GET /v1/entries`              | 2550 totales                                    |
| Búsqueda               | `GET /v1/entries?search=model` | hits correctos                                  |
| Marcar leído           | `PUT /v1/entries`              | `204` / `True`                                  |
| Export OPML            | `GET /v1/export`               | 3036 bytes, 13 outlines                         |
| Categorías             | `POST /v1/categories`          | creadas `IA y Modelos`, `Tecnología`, `Ciencia` |
| Mover feed a categoría | `PUT /v1/feeds/{id}`           | `201`                                           |
| Colector NAF           | `POST /api/v1/collect`         | 371 entradas, 0 errores                         |

## Endpoints NAF expuestos

- `GET /api/v1/feeds`
- `GET /api/v1/feeds/health`
- `GET /api/v1/entries` (`feed_id`, `category_id`, `search`, `read`, `starred`,
  `limit`, `offset`)
- `POST /api/v1/entries/{id}/read`
- `GET /api/v1/opml/export`
- `POST /api/v1/opml/import`
- `POST /api/v1/collect?limit=N`

## Invariantes comprobadas

1. **Provenance:** cada entrada normalizada conserva `entry_id`, `url`, `title`,
   `author`, `published_at`, `feed_id`, `feed_title`, `feed_url`, `site_url`.
2. **Sin acceso a tablas de Miniflux:** todo pasa por HTTP API.
3. **Aislamiento de fallos:** un feed con error no detiene el resto (test
   `test_one_failing_feed_does_not_block_others`).
4. **Sin filtrado en ingesta:** se conservan todas las entradas; el filtrado es
   de presentación/informe.
5. **Health visible:** `parsing_error_count`, `checked_at`, `disabled` por feed.

## Correcciones derivadas de la prueba

- `health()` apuntaba a `/v1/healthcheck` → corregido a `/healthcheck`.
- `env_prefix` no estaba configurado: `NAF_*` del `.env` se ignoraban →
  corregido en `app/core/config.py`.
- `docs/FEEDS_TEST.md`: 4 URLs erróneas (Anthropic, Meta, Mistral, arXiv) y
  Reuters retirado, corregidas con estado verificado.
