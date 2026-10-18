# Evaluación TTS para español (Fase 0 / Issue #8)

**Fecha:** 2026-10-18  
**Estado:** Preliminar - requiere pruebas con muestras reales

## 1. Objetivo

Evaluar providers TTS para español con foco en terminología técnica (nombres de
modelos IA), naturalidad conversacional, segmentación, privacidad y coste.
Decidir entre Podcastfy (adaptador conversacional) vs TTS directo.

## 2. Criterios de evaluación

| Criterio                          | Peso  | Descripción                                                                             |
| --------------------------------- | ----- | --------------------------------------------------------------------------------------- |
| **Pronunciación español técnico** | Alto  | Nombres: Qwen, DeepSeek, LLaMA, Mistral, Claude, GPT, etc. Siglas, números, anglicismos |
| **Naturalidad conversacional**    | Alto  | Fluidez, pausas, entonación para estilo podcast/conversación                            |
| **Segmentación**                  | Alto  | Generación por segmentos, retry independiente (resiliencia)                             |
| **Español (es-ES)**               | Alto  | Calidad voz castellana                                                                  |
| **Privacidad**                    | Alto  | Local vs remoto, qué datos envía                                                        |
| **Latencia**                      | Medio | Tiempo generación por segmento/informe                                                  |
| **Coste**                         | Medio | Por caracteres/segundos, coste por informe                                              |
| **Licenciamiento/condiciones**    | Alto  | Cumplimiento, sin voice cloning (MVP)                                                   |

## 3. Podcastfy (evaluación estructural)

### Fortalezas (confirmadas por código)

- Arquitectura modular: content parser → content generator (guión) → TTS
- Soporta generación conversacional (multi-voz) - ideal para Audio Overview
- Segmentación nativa
- Apache-2.0
- Configurable (conversation_config.yaml, config.yaml)

### Aspectos a probar con corpus español

- Guión conversacional con términos técnicos IA
- Pronunciación de nombres de modelos
- Manejo de citas/fuentes en diálogo (mantener atribución)

### Corpus de prueba propuesto

```text
Lanzamiento de DeepSeek V3.1: presenta mejoras en razonamiento.
Qwen 2.5 y LLaMA 4 compiten en benchmarks abiertos.
Mistral AI anunció nuevos modelos con pesos abiertos.
Claude 4 y GPT-4o evolucionan con capacidades de agentes.
OpenAI presentó actualizaciones; Anthropic y Google DeepMind avanzan en investigación.
```

### Estado prueba

- Estructura API revisada (client.py, tts/, content_generator.py)
- Dependencias instalables. **Nota:** pydub tiene incompatibilidad menor con
  Python 3.13 (pyaudioop) en algunos entornos - no bloqueante para evaluación
  conceptual.
- **Prueba de generación de audio:** Pendiente (requiriría descarga de
  modelos/voices según provider TTS configurado). Documentar sin generar
  archivos pesados ahora.

## 4. TTS directo (alternativa)

### Consideraciones

- Más simple, menor overhead
- Menos conversacional por defecto
- Segmentación manual pero controlable
- Providers: Coqui, Piper (local), OpenAI, Google, etc. Evaluar por caso.

### Comparación vs Podcastfy

| Aspecto               | Podcastfy             | TTS Directo      |
| --------------------- | --------------------- | ---------------- |
| Estilo conversacional | Excelente (multi-voz) | Manual/limitado  |
| Segmentación          | Nativa                | Manual           |
| Español técnico       | A probar              | Depende provider |
| Overhead              | Mayor (deps)          | Menor            |
| Flexibilidad          | Buena                 | Muy buena        |

## 5. Recomendación preliminar

- **Podcastfy:** Candidato fuerte para experiencia tipo Audio Overview
  (conversacional). Ideal para informes narrados. Requiere validación de
  pronunciación español técnico.
- **TTS directo:** Fallback robusto si Podcastfy no cumple calidad. Más liviano.

**Recomendación:** Empezar evaluando **Podcastfy** como adaptador principal
(Apache-2.0, alineado con plan). Mantener **TTS directo como fallback**.
Decisión definitiva tras generar muestras con corpus técnico.

## 6. Próximos pasos (para completar Fase 5)

1. Crear corpus de prueba ampliado (5-10 fragmentos con nombres técnicos)
2. Generar muestras con Podcastfy + provider TTS español disponible
3. Evaluación subjetiva (pronunciación, naturalidad, pausas)
4. Documentar resultados con muestras (o enlaces)
5. Decisión justificada y registrada

**Estado actual:** Evaluación estructural/comparativa completada. Pruebas de
audio reales pendientes (se realizarán en desarrollo de Fase 5, con aprobación
previa).
