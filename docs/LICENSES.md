# Inventario de licencias de dependencias (Fase 0)

**Estado:** Inicial - se irá completando conforme se añadan dependencias

## Licencia del proyecto

- **Proyecto naf:** Apache-2.0 (ver `LICENSE` en raíz)
- **Confirmado:** Sí (archivo LICENSE presente)

## Dependencias clave identificadas

| Dependencia                                                 | Tipo                              | Licencia                      | Fuente                                                                | Notas                                         |
| ----------------------------------------------------------- | --------------------------------- | ----------------------------- | --------------------------------------------------------------------- | --------------------------------------------- |
| **[Miniflux](https://github.com/miniflux/v2)**              | Reader base (integración vía API) | Apache-2.0                    | [GitHub](https://github.com/miniflux/v2/blob/main/LICENSE)            | Reutilización prioritaria. Solo API, no fork. |
| **[Podcastfy](https://github.com/souzatharsis/podcastfy)**  | Generador audio conversacional    | Apache-2.0                    | [GitHub](https://github.com/souzatharsis/podcastfy/blob/main/LICENSE) | Candidato para audio. Validar en Fase 5/8.    |
| **[FastAPI](https://github.com/tiangolo/fastapi)**          | Backend API                       | Apache-2.0                    | PyPI/GitHub                                                           | Stack propuesto                               |
| **[Uvicorn](https://github.com/encode/uvicorn)**            | ASGI server                       | BSD-3-Clause                  | PyPI                                                                  | Típico con FastAPI                            |
| **[Pydantic](https://github.com/pydantic/pydantic)**        | Validación datos                  | MIT                           | PyPI                                                                  | Típico                                        |
| **[SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy)**  | ORM                               | MIT                           | PyPI                                                                  | Complement DB                                 |
| **[psycopg2/psycopg3](https://github.com/psycopg/psycopg)** | PostgreSQL driver                 | LGPL v3 / BSD-like (psycopg3) | PyPI                                                                  | Revisar según versión elegida                 |

## Exclusiones (por plan)

| Proyecto                                                                  | Licencia                       | Razón de exclusión                                                                              |
| ------------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------------------- |
| **[AI Summary Podcast](https://github.com/applab-nl/ai-summary-podcast)** | CC BY-NC 4.0                   | No compatible con licencia OSS objetivo (restricción uso comercial). Solo referencia funcional. |
| **[Daily Digest](https://github.com/MarcelloMorettoni/daily-digest)**     | Sin licencia clara (observado) | No copiar sin licencia clara. Solo referencia UI/flujo.                                         |

## Inventario de modelos/recursos (futuro)

- **Voces TTS**: revisar términos de uso según proveedor elegido
- **Modelos LLM**: si se usan APIs externas, revisar ToS
- **Prompts/assets**: marcar licencia cuando se creen

## Checklist

- [ ] Verificar licencias exactas al fijar versiones
- [ ] Comprobar compatibilidad entre licencias (Apache-2.0 es permisiva)
- [ ] Documentar excepciones/advertencias
- [ ] Actualizar con nuevas deps al añadirlas
- [ ] Revisar TTS provider elegido en Fase 5
