# Feeds de prueba (Fase 0)

**Objetivo:** Seleccionar 8-15 feeds reales para validar ingesta completa,
organización, dedupe, informes y citas.

## Criterios de selección

- Mezclar **categorías generales** + **colección IA/modelos**
- Priorizar **RSS/Atom oficiales**
- Cubrir distintas fuentes: blogs, noticias, investigación, lanzamientos
  oficiales
- Verificables sin autenticación
- Representativos del uso previsto

## Lista propuesta

### Colección IA/Modelos (críticos para validar evidencia)

| Feed                  | URL                                                                                                                          | Tipo             | Notas                                       |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------- |
| OpenAI News           | `https://openai.com/news/rss.xml` | RSS oficial      | Lanzamientos/comunicados oficiales          |
| Anthropic News        | `https://www.anthropic.com/news/rss.xml` | RSS oficial      | Comunicados oficiales                       |
| Google DeepMind Blog  | `https://deepmind.google/blog/rss.xml` | RSS oficial      | Investigación/lanzamientos                  |
| Meta AI Blog          | `https://ai.meta.com/blog/rss/` | RSS oficial      | Blog Meta AI                                |
| Mistral AI News       | `https://mistral.ai/news/feed.xml` | RSS/Feed oficial | Comunicados (verificar formato actual)      |
| Hugging Face Blog     | `https://huggingface.co/blog/feed.xml` | RSS/Feed oficial | Ecosistema abierto, releases, investigación |
| arXiv CS.AI (últimas) | `https://export.arxiv.org/api/query?search_query=cat:cs.AI&start=0&max_results=25&sortBy=lastUpdatedDate&sortOrder=descending` | Atom API         | Papers recientes IA (usar como feed)        |

### Categorías generales (validar alcance multi-tema)

| Feed                | URL                                              | Tipo | Categoría                        |
| ------------------- | ------------------------------------------------ | ---- | -------------------------------- |
| Ars Technica        | `https://feeds.arstechnica.com/arstechnica/index` | RSS  | Tecnología y software            |
| The Verge           | `https://www.theverge.com/rss/index.xml` | RSS  | Tecnología y software            |
| ScienceDaily        | `https://www.sciencedaily.com/rss/top/science.xml` | RSS  | Ciencia e investigación          |
| MIT News            | `https://news.mit.edu/rss/research` | RSS  | Ciencia e investigación          |
| Reuters World News  | `https://feeds.reuters.com/reuters/worldnews` | RSS  | Política, regulación y seguridad |
| BBC News Technology | `https://feeds.bbci.co.uk/news/technology/rss.xml` | RSS  | Tecnología                       |
| TechCrunch          | `https://techcrunch.com/feed/` | RSS  | Negocios/tecnología              |

**Total:** 14 feeds (7 IA + 7 generales). Suficiente para Fase 0/6 (objetivo
8-15).

## Validación durante Fase 0

- [ ] Accesible sin auth
- [ ] Devuelve entradas recientes (últimos 7-30 días)
- [ ] Campos mínimos: título, enlace/URL, fecha, contenido/extracto
- [ ] Formato válido (RSS 2.0/Atom/JSON Feed)
- [ ] Sin bloqueos evidentes (robots, user-agent ok con fetch estándar)
- [ ] Verificar URLs exactas al momento de integración (pueden cambiar)

## Notas

- Algunos feeds pueden requerir ajuste de URL (p.ej. Mistral/HF pueden variar).
  Verificar en Fase 0.
- arXiv via API es válido como fuente; permite obtener papers recientes.
- Se prioriza **oficial** sobre agregadores cuando hay opción.
