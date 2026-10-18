# Feeds de prueba (Fase 0/2)

**Objetivo:** Seleccionar 8-15 feeds reales para validar ingesta completa,
organización, dedupe, informes y citas.

**Estado:** Verificado empíricamente contra Miniflux 132 el 2026-10-18 (10 feeds
aceptados, 2550 entradas ingestadas).

## Criterios de selección

- Mezclar **categorías generales** + **colección IA/modelos**
- Priorizar **RSS/Atom oficiales**
- Cubrir distintas fuentes: blogs, noticias, investigación, lanzamientos
  oficiales
- Verificables sin autenticación
- Representativos del uso previsto

## Colección IA/Modelos (críticos para validar evidencia)

| Feed                 | URL                                    | Tipo        | Estado                       |
| -------------------- | -------------------------------------- | ----------- | ---------------------------- |
| OpenAI News          | `https://openai.com/news/rss.xml`      | RSS oficial | OK (1299 entr.)              |
| Google DeepMind Blog | `https://deepmind.google/blog/rss.xml` | RSS oficial | OK                           |
| Hugging Face Blog    | `https://huggingface.co/blog/feed.xml` | RSS oficial | OK (880 entr.)               |
| Mistral AI Blog      | `https://mistral.ai/news/rss`          | RSS oficial | OK                           |
| Anthropic News       | N/A                                    | -           | 404 verificado               |
| Meta AI Blog         | N/A                                    | -           | 404 verificado               |
| arXiv CS.AI query    | N/A                                    | Atom API    | Rechazado por Miniflux (500) |

Los tres últimos quedan como **pendientes de adaptador propio** (Fase 2, sección
de adaptadores): requieren extracción acotada de página oficial o feed
alternativo verificado.

## Categorías generales (validar alcance multi-tema)

| Feed                | URL                                                | Tipo | Categoría               |
| ------------------- | -------------------------------------------------- | ---- | ----------------------- |
| Ars Technica        | `https://feeds.arstechnica.com/arstechnica/index`  | RSS  | Tecnología y software   |
| The Verge           | `https://www.theverge.com/rss/index.xml`           | RSS  | Tecnología y software   |
| BBC News Technology | `https://feeds.bbci.co.uk/news/technology/rss.xml` | RSS  | Tecnología              |
| TechCrunch          | `https://techcrunch.com/feed/`                     | RSS  | Negocios/tecnología     |
| ScienceDaily        | `https://www.sciencedaily.com/rss/top/science.xml` | RSS  | Ciencia e investigación |
| MIT News            | `https://news.mit.edu/rss/research`                | RSS  | Ciencia e investigación |
| Reuters World News  | `https://feeds.reuters.com/reuters/worldnews`      | RSS  | Política/regulación     |

Reuters quedó **no disponible** (500 en Miniflux, feed retirado). Sustituir por
una fuente de política/regulación verificada antes del piloto.

## Resultado de la verificación

```text
Feeds aceptados: 10
Entradas ingeridas: 2550
OpenAI News               1299
Hugging Face Blog          880
Google DeepMind News       100
Mistral Blog                90
ScienceDaily                60
MIT News                    50
BBC News                    21
Ars Technica                20
TechCrunch                  20
The Verge                   10
```

Categorización aplicada en Miniflux: `IA y Modelos` (OpenAI, DeepMind, HF,
Mistral), `Tecnología` (Ars, Verge, BBC, TechCrunch), `Ciencia` (ScienceDaily,
MIT).

## Criterios de aceptación verificados

- [x] Accesible sin auth
- [x] Devuelve entradas (ver conteos arriba)
- [x] Campos mínimos: título, URL, fecha, contenido
- [x] Formato válido (RSS 2.0 / Atom)
- [x] Sin bloqueos con fetch estándar de Miniflux
- [x] URLs exactas verificadas (corregidas las 4 erróneas)

## Notas

- Las URLs marcadas N/A deben resolverse con adaptador propio o feed alternativo
  verificado; nunca asumir que un agregador comunitario prueba autoría oficial.
- Se prioriza **oficial** sobre agregadores cuando hay opción.
- Reproducible con `scripts/integration_proof.py` y `POST /api/v1/collect`.
