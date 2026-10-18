# Arquitectura - Monolito Modular (Fase 1)

**Fecha:** 2026-10-18  
**Issue:** [#3](https://github.com/alfonsodg/naf/issues/3)  
**Relacionado:** [Meta #1](https://github.com/alfonsodg/naf/issues/1),
[#2](https://github.com/alfonsodg/naf/issues/2)

## Principios

- **Monolito modular:** Un solo deploy, pero módulos bien separados por
  responsabilidades
- **Separación de dominios:** Lector (Miniflux) vs Complemento
  (informes/audio/clasificación)
- **Nunca acceder a BD Miniflux:** Solo vía API REST documentada
- **Puertos y adaptadores:** Interfaces definidas en `app/contracts/`,
  implementaciones en `app/adapters/`
- **Fácil de extraer workers:** Interfaces permiten mover tareas asíncronas a
  workers futuros sin reescribir dominio
- **Configuración tipada:** Sin secretos en repo

## Arquitectura general

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          Naf (Complemento)                            │
├─────────────────────────────────────────────────────────────────────┤
│  API (FastAPI) ── app/api/                                             │
│    ├── /health, /feeds, /entries, /reports, /audio                    │
│    └── Complement UI endpoints (ligero, enfocado a informes)           │
├─────────────────────────────────────────────────────────────────────┤
│  Services ── app/services/                                             │
│    ├── collector (sync con Miniflux vía API)                           │
│    ├── classifier (LLM con output estructurado)                        │
│    ├── report_generator (texto + citas)                                │
│    └── audio_generator (segmentado + TTS)                              │
├─────────────────────────────────────────────────────────────────────┤
│  Adapters (implementan contratos) ── app/adapters/                    │
│    ├── miniflux (HTTP client API)                                     │
│    ├── llm (provider intercambiable)                                  │
│    ├── tts/ (Podcastfy + fallback)                                     │
│    └── storage (audio artifacts)                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Core (dominio puro) ── app/core/                                     │
│    ├── models, schemas, taxonomy, citation, audio, config              │
│    └── reglas de evidencia (citas obligatorias, "por verificar")       │
├─────────────────────────────────────────────────────────────────────┤
│  Contracts (interfaces/ports) ── app/contracts/                       │
└─────────────────────────────────────────────────────────────────────┘
           │                           │
           │ HTTP API (solo lectura)   │ PostgreSQL (complemento)
           ▼                           ▼
      ┌─────────────┐           ┌─────────────────────────┐
      │  Miniflux    │           │ Naf DB (complemento)     │
      │  (lector)    │           │ - digests, digest_story  │
      │  BD propia   │           │ - audio_asset            │
      │  NO accedido │           │ - creator/model_entity   │
      └─────────────┘           │ - ingestion_run          │
                                └─────────────────────────┘
```

## Propiedad de datos

| Entidad                                    | Propietario  | Notas                                                  |
| ------------------------------------------ | ------------ | ------------------------------------------------------ |
| Feeds/entradas/lectura/categorías Miniflux | **Miniflux** | Solo consultados vía API. Nunca modificados desde naf. |
| Digests (informes), DigestStory, citas     | **Naf**      | Estado de informes generados                           |
| AudioAsset                                 | **Naf**      | Archivos/audio metadata, versiones inmutables          |
| Creator/ModelEntity                        | **Naf**      | Enriquecimiento IA con evidencia                       |
| IngestionRun                               | **Naf**      | Tracking syncs naf→Miniflux API                        |

**Regla fundamental:** Si pertenece al dominio lector
(feeds/entries/read-state), consultar vía Miniflux API. Si es específico de
informes/audio/clasificación/evidencia, guardar en BD naf.

## Módulos

### `app/contracts/`

Puertos (interfaces) que definen qué necesita el dominio. Ejemplos:

- `FeedReader` (interfaz Miniflux adapter)
- `Classifier`
- `ReportGenerator`
- `TTSProvider`
- `AudioStorage`

### `app/adapters/`

Implementaciones concretas de contratos. Desacoplan infraestructura.

- `miniflux/client.py` - HTTP client (requests/httpx), auth, timeouts
- `llm/` - provider LLM
- `tts/` - Podcastfy adapter + fallback
- `storage/local.py` - almacenamiento audio

### `app/core/`

Lógica pura, sin dependencias infraestructura.

- `config.py` - settings tipados (Pydantic Settings)
- `models/` - entidades dominio
- `schemas/` - Pydantic schemas API
- `taxonomy.py` - taxonomías generales + IA
- `citation.py` - validación citas/evidencia
- `audio.py` - segmentación/merging
- `exceptions.py`

### `app/services/`

Orquestación. Usan contratos (no adapters directos).

- `collector.py` - sync con Miniflux
- `classifier.py` - clasificación con validación
- `report_generator.py` - generación texto con citas
- `audio_generator.py` - generación audio segmentada

### `app/api/`

Endpoints FastAPI. Validación, auth ligero (MVP individual), respuestas.

- `routes/health.py`, `feeds.py`, `entries.py`, `reports.py`, `audio.py`

### `app/db/`

Migrations, session, base model.

## Tecnologías

- **Runtime:** Python 3.12+ (compatible con uv)
- **Framework:** FastAPI + Uvicorn
- **Deps:** `uv` (gestión)
- **DB:** PostgreSQL + SQLAlchemy (Alembic para migraciones)
- **Config:** Pydantic Settings (env vars)
- **HTTP:** httpx (async) o requests (sync) para Miniflux API
- **Validación:** Pydantic v2
- **Tests:** pytest + pytest-asyncio

## Seguridad (básicos)

- SSRF: permitir solo hosts/domains configurados para Miniflux/API externos;
  bloquear redes privadas (future hardening)
- Timeouts, retries con backoff
- Secrets via env (no .env en repo)
- Validación entrada/salida
- No logging de secretos

## Flujo ejemplo: generar informe

1. Usuario solicita informe (filtros + "desde último")
2. `reports` API → `ReportService`
3. `collector` obtiene entradas relevantes desde Miniflux API
4. `classifier` sugiere categorías (corrigible) - no bloquea
5. `report_generator` genera texto con citas validadas
6. Si pide audio: `audio_generator` segmenta → TTS → merge → guarda asset
7. Retorna informe + referencias + audio si existe
