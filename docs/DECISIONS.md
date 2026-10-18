# Decisiones de diseño (Fase 0)

**Fecha:** 2026-10-18  
**Proyecto:** naf (News Aggregator + Audio Reports)  
**Estado:** Propuesto - pendiente de aprobación  
**Relacionado:** [Issue #2](https://github.com/alfonsodg/naf/issues/2),
[Meta #1](https://github.com/alfonsodg/naf/issues/1)  
**Basado en:** [Plan](PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md)

Estas decisiones resuelven los 10 puntos de la Sección 17 del plan
`PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md`.

## 1. Nombre del producto y repositorio

- **Producto:** `naf` (acrónimo/identificador del proyecto)
- **Repositorio:** `https://github.com/alfonsodg/naf`
- **Rama principal:** `main` (por confirmar)

## 2. Uso: individual privado vs multiusuario

- **Decisión:** **Individual privado (MVP)**
- **Justificación:** El plan recomienda empezar para un solo usuario. Evita
  complejidad de auth multiusuario, permisos, roles. Se puede escalar después si
  procede.

## 3. Interfaz inicial

- **Decisión:** **Web solamente (MVP)**
- **Justificación:** Más directo para acceder desde distintos dispositivos. API
  REST existente facilita extensión futura (móvil, CLI). Plan recomienda
  web-only.

## 4. Categorías generales iniciales, feeds de ejemplo y frecuencia

- **Categorías generales iniciales:**
  - Tecnología y software
  - Ciencia e investigación
  - Negocios y economía
  - Política, regulación y seguridad
  - Salud, educación, cultura y medios
  - Personalizadas (por usuario)

- **Colección IA/modelos (separada, no única):** LLMs, modelos abiertos,
  visión/VLM, audio (STT/TTS), video/imagen, agentes, embeddings/búsqueda,
  robótica, ciencia/especializados.

- **Feeds de ejemplo (mix general + IA):** Ver `docs/FEEDS_TEST.md` para lista
  detallada.

- **Frecuencia máxima aceptable por fuente:**
  - Feeds RSS/Atom: **cada 15-30 min** (configurable por fuente)
  - GitHub releases/actividad: **cada 30-60 min**
  - Fuentes con rate-limit: respetar `Cache-Control`/`ETag`/`Last-Modified`
  - **Respeto estricto** de robots.txt/políticas publicadas

## 5. Duración/estilo predeterminado del informe + zona horaria

- **Duración objetivo:** **5-8 minutos** (flexible según cantidad/contenido).
  Priorizar calidad/procedencia sobre alcanzar duración artificial.
- **Estilo:** Conversacional en **español**, con pausas naturales, citas claras,
  distinción entre anuncio oficial/terceros. Inspirado en Audio Overview
  (NotebookLM) pero con énfasis en citas/fuentes.
- **Zona horaria:** Mostrar fechas en **zona horaria local del usuario** (UTC
  para almacenamiento interno).

## 6. TTS: remoto/local o ambos; límites coste/privacidad; voz española

- **Modalidad:** **Ambos, con selección por configuración**. Empezar con local
  si viable para privacidad; permitir remoto si calidad/coste mejor.
- **Sin clonación de voz (MVP):** Explícitamente excluido.
- **Requisito español:** Pronunciación correcta de nombres técnicos de modelos
  (Qwen, DeepSeek, LLaMA, Mistral), siglas, números, anglicismos.
- **Privacidad:** Por defecto **local** si cumple criterios de calidad. Solo
  enviar texto necesario a proveedor remoto si usuario lo habilita.
- **Coste:** Límite configurable por informe; cachear audios inmutables; generar
  audio bajo demanda.
- **Decisión técnica:** Evaluar **Podcastfy** (Apache-2.0) como adaptador
  conversacional. Comparar con TTS directo. Ver `docs/TTS_EVALUATION.md`.

## 7. Entorno de desarrollo/pruebas + ubicación persistente del audio

- **Entorno dev:** Local con Docker (recomendado) o directo con `uv`. PostgreSQL
  local.
- **Miniflux:** Ejecutar local para desarrollo (Docker) o conectar a instancia
  existente para pruebas.
- **Audio persistente:**
  - **Dev:** `storage/audio/` (local filesystem)
  - **Prod/despliegue futuro:** interfaz abstracta para permitir S3/compatible,
    filesystem, etc. Configurable vía settings.
- **Separación:** Base complementaria (naf) independiente de schema interno de
  Miniflux.

## 8. Retención de entradas, transcripciones y audios

- **Entradas (metadatos + extractos):** Configurable. Default conservador -
  mantener referencias (URLs, GUIDs, metadatos). Evitar copiar cuerpo completo
  por defecto.
- **Transcripciones (texto del informe):** Conservar todas las versiones de
  informes generados (versionado inmutable).
- **Audios generados:** Conservar ediciones inmutables. Permitir limpieza por
  antigüedad (configurable). Por defecto: **30-90 días** (a decidir según
  almacenamiento/coste).
- **Política:** Explícita, configurable. Revisión periódica futura.

## 9. Uso de API Feedly

- **Decisión:** **No depender de Feedly API (MVP)**.
- **Justificación:** Añade dependencia externa con posibles requisitos de
  plan/acceso. Priorizar fuentes nativas RSS/Atom/APIs públicas. Feedly puede
  considerarse integración opcional futura solo si aporta valor claro. Plan
  recomienda no basar diseño en ello.

## 10. Envío automático futuro

- **Decisión:** **Solo petición explícita (MVP)**. Sin envío automático.
- **Justificación:** Plan dice explícitamente fuera de MVP (correo/Telegram/RSS
  personalizado/notificaciones push). Validar primero bajo demanda. Si se
  habilita en futuro, requerirá autorización explícita y configuración granular.
