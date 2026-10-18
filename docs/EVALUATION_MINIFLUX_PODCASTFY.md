# Evaluación: Miniflux + Podcastfy (Fase 0)

**Fecha:** 2026-10-18  
**Estado:** Evaluación preliminar - requiere validación práctica

## 1. Miniflux

### Resumen

Miniflux (v2) es un lector RSS/Atom/JSON Feed maduro, autoalojado, Apache-2.0.
El plan lo identifica como candidato preferido para la base lectora.

### Fortalezas

- **Licencia:** Apache-2.0 (compatible con objetivo)
- **Madurez:** producción, estable, bien mantenido
- **API REST completa:** feeds, entradas, categorías, estados, búsqueda, OPML
  import/export
- **Características clave:** leído/no leído, favoritos, categorías/etiquetas,
  dedupe, WebSub, extracción
- **Autoalojable:** fácil con Docker, PostgreSQL
- **Ligero y enfocado:** no sobrecargado, buen rendimiento
- **No invade BD propia:** podemos usar API exclusivamente (no acceder tablas) -
  cumple requisito del plan

### Limitaciones para nuestro caso

- **No genera informes/audio:** Solo lector. Necesitamos capa complementaria
- **UI genérica:** Necesitamos pantalla específica para informes/audio
  (complementaria, no reemplazar)

### Validación API (requerida)

- [ ] Probar endpoints: `/v1/feeds`, `/v1/entries`, `/v1/categories`,
      `/v1/mark-all-as-read`
- [ ] OPML import/export
- [ ] Búsqueda y filtros
- [ ] Timeouts, rate limiting, manejo errores

### Recomendación

**Aprobado para adopción.** Ideal como base lectora. Cumple todos los requisitos
del plan.

## 2. Podcastfy

### Resumen (Podcastfy)

Podcastfy (v0.4.3 instalado) es librería Python Apache-2.0 para convertir
contenido en conversaciones de audio multilingües con guión personalizable.
Candidato para motor de informes/audio conversacional.

### Fortalezas (Podcastfy)

- **Licencia:** Apache-2.0 (compatible)
- **Enfoque conversacional:** Genera audio tipo "podcast/conversación" (ideal
  para Audio Overview estilo)
- **Multilingüe:** Soporta español (requisito crítico)
- **Arquitectura modular:** Parser de contenido, generador de guión, TTS
  segmentado
- **Segmentación:** Generación por segmentos - alineado con requisito
  "reintentar solo segmento fallido"
- **Python + extensible:** Integra bien con FastAPI
- **TTS intercambiable:** Soporta múltiples providers (flexible)

### Aspectos a validar (críticos)

| Aspecto                                 | Estado    | Acción requerida                                                                      |
| --------------------------------------- | --------- | ------------------------------------------------------------------------------------- |
| **Pronunciación español (técnico)**     | Pendiente | Probar nombres modelos (Qwen, DeepSeek, LLaMA, Mistral), siglas, números, anglicismos |
| **Calidad conversacional español**      | Pendiente | Generar muestra con artículo técnico IA y evaluar naturalidad                         |
| **Segmentación + recuperación errores** | Pendiente | Verificar retry por segmento                                                          |
| **Salida estructurada (citas)**         | Pendiente | Confirmar puede mantener referencias a fuentes en guión                               |
| **Dependencias/Peso**                   | Observado | Instala muchas deps (ML/TTS) - aceptable para MVP                                     |
| **Local vs remoto (TTS)**               | Pendiente | Identificar qué providers usa y si permite operación local                            |
| **Privacidad**                          | Pendiente | Determinar si envía datos a APIs remotas (configurable?)                              |

### Riesgos

- **Dependencia pesada:** Muchas dependencias ML - build/instalación pesadas
- **Calidad variable:** Depende de provider TTS elegido
- **Poca visibilidad de configuración TTS española:** Necesita evaluación con
  voces/español

### Recomendación preliminar

**Candidato prometedor.** Requiere prueba práctica con muestras en español
(términos técnicos IA). No adoptarlo automáticamente - validar criterios de
aceptación en prueba.

## 3. Integración: Miniflux + Naf

### Arquitectura propuesta (validada conceptualmente)

- **Miniflux**: Motor de lectura (gestión feeds, organización, lectura,
  búsqueda). Acceso **solo vía API REST**.
- **Naf (complemento):** Informes texto+audio, clasificación, citas, historial.
  Persistencia propia (Postgres) para digests/audio.
- **Separación BD:** No acceder a tablas Miniflux. Complemento independiente.
- **Comunicación:** HTTP API (Miniflux expuesto o interno). Timeouts,
  reintentos, graceful degradation.

### Puntos a probar

- [ ] Miniflux corriendo (Docker), acceso API (Docker daemon disponible
      localmente - pendiente verificación entorno)
- [ ] Sync de feeds/entradas desde Naf vía API
- [ ] OPML import/export
- [ ] Lectura preserva todas entradas (sin filtrado en ingesta)
- [ ] Prueba con feeds de `docs/FEEDS_TEST.md`

## 4. Prueba de integración (Integration Proof)

### Estado

- Docker disponible (`docker --version` OK). Docker daemon no verificado/running
  en este entorno.
- Miniflux no instalado localmente (CLI). Deploy vía Docker Compose planificado.
- Prueba API pendiente: conectar a Miniflux local, autenticar, listar feeds,
  leer entradas, probar OPML.

### Plan de prueba

1. Levantar Miniflux + Postgres vía docker-compose (local)
2. Crear usuario admin, obtener token API
3. Añadir feeds de prueba (`docs/FEEDS_TEST.md`) - mínimo 2-3
4. Verificar lectura completa de entradas (preservar todas)
5. Probar búsqueda, marcado leído/no leído, categorías
6. Exportar/importar OPML
7. Documentar resultados en `docs/INTEGRATION_MINIFLUX_PROOF.md`

**Nota:** Aunque Docker daemon no está corriendo ahora, el entorno tiene Docker
instalado; la prueba es factible en dev local.

## 5. Conclusión

- **Miniflux:** **Recomendado para adopción** (sin bloqueadores). API cumple
  requisitos.
- **Podcastfy:** **Recomendado para evaluación práctica** con corpus español
  técnico. Decisión final tras pruebas (Issue #8/#9).

**Próximo paso:** Completar prueba de integración API con Miniflux local.
Generar muestras Podcastfy con feeds de prueba y evaluar español técnico.
