# Plan: agregador categorizado de feeds con informes de audio

**Estado:** propuesta funcional y técnica para entregar a un agente de
desarrollo  
**Fecha:** 2026-10-18  
**Idioma de producto:** español  
**Licencia objetivo:** open source con licencia aprobada por OSI; recomendación
inicial: Apache-2.0 (pendiente de confirmación del dueño)  
**Objetivo:** crear un lector categorizado de feeds de alcance general que
recopile las entradas de las fuentes integradas y permita generar informes en
español, texto y audio cuando el usuario los solicite.

## 1. Resumen ejecutivo

Construir un lector de feeds de propósito general inspirado en Feedly, con
categorías y colecciones del usuario, más informes de audio tipo Audio Overview
de NotebookLM. Todas las entradas disponibles de las fuentes integradas se
conservan como elementos navegables y buscables; el usuario decide qué fuentes,
periodo, categorías o temas incluir en cada informe. La ingesta periódica es
independiente de la generación: informes y audios se generan a pedido, salvo
que en el futuro se habilite una programación explícita.

El seguimiento verificable de lanzamientos de modelos de IA es un caso
especializado y una categoría de alto valor, no el límite del producto. En esa
categoría se identifica creador, anuncio, fecha, tipo de cambio y fuente
primaria; el resto de categorías usa el flujo general de lectura y resumen.

La revisión confirma que no conviene empezar desde cero: lectores OSS ya
resuelven buena parte de ingesta, categorías y lectura; proyectos de audio ya
automatizan síntesis y TTS. La aplicación debe reutilizar esas piezas y añadir
informes selectivos con procedencia. El seguimiento de anuncios de modelos es
un enriquecedor especializado dentro del catálogo general, no un producto
aislado.

## 2. Problema y usuarios

### Problema

La información de interés aparece dispersa en feeds de múltiples temas. El
usuario necesita seguir suscripciones heterogéneas por categorías, revisar lo
nuevo en un solo lugar y pedir un resumen hablado sin perder el acceso al
contenido original. Para IA, además, necesita distinguir anuncios oficiales
de comentarios y actualizaciones de nuevos lanzamientos.

### Usuario inicial

Una persona que integra feeds sobre varios temas, los organiza y quiere leerlos
en un solo lugar o pedir un informe en español para escucharlo y abrir las
fuentes. IA/modelos es un caso de uso inicial, no exclusivo. Diseñar primero
para un usuario individual; no asumir cuentas multiusuario ni publicación
pública.

### Tareas principales

1. Añadir feeds individualmente o importar suscripciones; organizarlos en
   categorías/colecciones y consultar todas sus entradas.
2. Explorar por fecha, fuente, categoría, búsqueda y estado de lectura.
3. Pedir informes como “lo importante de tecnología esta semana” o
   “novedades de IA/modelos desde mi último informe”.
4. Leer/escuchar el resultado y abrir fuentes; ajustar categorías, fuentes y
   duración/estilo del informe.

### 2.1 Productos y proyectos similares revisados

Revisión documental de repositorios y documentación pública al 2026-10-18; no
equivale a una instalación, auditoría de código ni prueba funcional. Las
capacidades y licencias deben volver a verificarse antes de adoptar una
dependencia.

<!-- markdownlint-disable MD013 -->
| Proyecto | Qué resuelve hoy | Coincidencia y brecha para este producto | Evaluación inicial |
| --- | --- | --- | --- |
| [AI Summary Podcast](https://github.com/applab-nl/ai-summary-podcast) | Pipeline integrado: RSS/web, resumen LLM, deduplicación, composición, TTS, panel, historial y feed RSS de episodios con enlaces. | Antecedente cercano al boletín hablado, no al lector general ni a la verificación de anuncios oficiales. No acredita calidad en español. | Referencia funcional; CC BY-NC 4.0 no es compatible con la licencia open source objetivo. |
| [Daily Digest](https://github.com/MarcelloMorettoni/daily-digest) | Boletín configurable por categorías y fuentes RSS/YouTube, Ollama local, Piper local, interfaz, historial y programación. | Muy cercano en experiencia y útil como referencia de ejecución local; su README lo presenta como boletín diario, no como registro auditable de anuncios oficiales ni como lector Feedly completo. | Referencia de diseño/prototipo, no base de producción sin revisión: la página observada muestra un solo commit y no expone una licencia en la ficha del repositorio. No asumir derechos de reutilización. |
| [Podcastfy](https://github.com/souzatharsis/podcastfy) | Librería/API Python que convierte conjuntos de fuentes en conversaciones de audio multilingües y permite personalizar guion/estilo. Declara Apache 2.0. | Cubre generación conversacional; no es un lector permanente, gestor de categorías/lectura ni historial de todas las entradas. | Candidato como motor de informes de audio, no como aplicación completa; validar español técnico. |
| [Miniflux](https://github.com/miniflux/v2) | Lector RSS/Atom/JSON Feed maduro, categorías, búsqueda, estado de lectura, API REST y PostgreSQL; Apache 2.0. | Cubre la base de un lector categorizado y puede evitar construir polling, lectura, organización y búsqueda desde cero. No aporta informes de audio ni la categoría especializada de modelos. | Candidato preferido para la base lectora; validar API y si se reutiliza su UI o se crea una interfaz complementaria. |
| [FreshRSS](https://github.com/FreshRSS/FreshRSS) | Agregador autohospedado, multiusuario, API, WebSub y extracción XPath básica para webs sin feed; AGPL-3.0. | Alternativa de lector general, pero no resuelve informes de audio ni el análisis editorial. | Opción si WebSub/extracción son determinantes; revisar AGPL antes de distribuir integración o modificaciones. |
| [RSSHub](https://github.com/DIYgod/RSSHub) | Genera feeds RSS a partir de rutas mantenidas para diversos sitios y servicios. | Puede cubrir fuentes sin RSS nativo; es infraestructura de descubrimiento/normalización, no lector, clasificador ni generador de audio. La cobertura depende de la ruta concreta y puede romperse si el sitio cambia. | Usar solo como adaptador opcional autoalojado y tras revisar/medir cada ruta. Priorizar fuentes oficiales nativas y APIs; nunca interpretar el resultado de una ruta comunitaria como confirmación del creador. |
| [Feedly](https://feedly.com/) | Producto comercial de lectura, organización y análisis de fuentes. | Referencia funcional para el agregador general; API/plan comercial no es requisito si se reutiliza Miniflux. | Benchmark de experiencia, no dependencia del núcleo open source. |
| [NotebookLM / Gemini Notebook](https://support.google.com/gemininotebook/answer/16212820?hl=en) | Genera Audio Overviews conversacionales a partir de fuentes, con reproducción, citas y descarga desde la aplicación. | Referencia de experiencia de escucha y presentación de fuentes, no colector continuo de feeds ni API backend asumida para automatización. | Inspiración de UX; generar el contenido por una canalización propia o con librería TTS/Python probada. |
<!-- markdownlint-enable MD013 -->

### Conclusión de reutilización

- **Reutilización prioritaria para el producto open source:** integrar Miniflux
  (Apache-2.0) como motor de feeds RSS/Atom y evaluar Podcastfy (Apache-2.0)
  como componente de guion/audio conversacional. Revisar dependencias, avisos de
  atribución, seguridad y compatibilidad antes de fijar versiones o distribuir.
- **Código propio limitado al diferencial:** orquestación de informes por
  categorías, cursor incremental, procedencia unificada y, como enriquecedor
  optativo, catálogo de creadores/modelos y distinción anuncio oficial/terceros.
  No construir un lector RSS ni un generador conversacional genérico si los
  componentes OSS existentes satisfacen los criterios.
- **AI Summary Podcast:** no incorporarlo ni hacer fork como base. Su licencia
  publicada es CC BY-NC 4.0; OSI exige que la licencia no restrinja campos de
  actividad, incluido el uso comercial. Puede servir como referencia funcional,
  pero su código no entra en una distribución open source que permita uso
  comercial sin permiso o cambio de licencia otorgado por los titulares.
- **Daily Digest:** referencia de interfaz/flujo hasta que el repositorio tenga
  licencia clara y mantenimiento suficiente; no copiar código sin licencia.
- **FreshRSS:** alternativa de agregación, pero Miniflux es preferible para el
  diseño inicial; FreshRSS usa AGPL-3.0 y requiere revisar sus obligaciones
  antes de distribuir una integración o modificación.
- **RSSHub:** fallback solo para fuentes sin feed/API nativos, tras verificar
  cada ruta; no prueba autoría del anuncio.
- Feedly y NotebookLM son referencias de producto o integraciones externas, no
  dependencias del núcleo open source.
- **Criterios de descarte inmediata:** licencia incompatible con el uso previsto;
  imposibilidad de ejecutar local/aislado como se requiere; falta de trazabilidad
  de fuentes; español técnico no aceptable; integración que obligue a exponer
  datos/credenciales sin aprobación.

## 3. Alcance del MVP

### Incluido

- Lector categorizado general: altas individuales e importación OPML, categorías
  y colecciones, leído/no leído, guardar/favoritos, búsqueda y feed cronológico.
- Ingesta periódica de todas las entradas y metadatos que entregue cada fuente
  integrada, sin restringir temas a IA. Si el feed solo ofrece título/extracto,
  conservar ese nivel; la extracción del cuerpo completo depende de la fuente.
- Fuentes iniciales de varias áreas como ejemplos configurables, no como una
  lista cerrada de fuentes admitidas.
- Categorías/colecciones definidas por usuario, asignación manual y sugerencias
  automáticas corregibles; filtros combinables por fuente, fecha, categoría,
  etiquetas, búsqueda y estado de lectura.
- Solicitud de informes sobre todas las entradas que coincidan con periodo,
  fuente, categoría, etiquetas o búsqueda; no filtrar por IA por defecto.
- Registro de entradas con URL, fechas, contenido disponible, categoría,
  estado y referencia al feed de origen.
- Agrupación de duplicados como ayuda de lectura, sin retirar entradas
  originales ni ocultar que hay varias publicaciones.
- Enriquecedor optativo para IA/modelos: detectar lanzamientos, actualizaciones,
  creadores y evidencia primaria.
- Reutilizar interfaz/servicios de lector para tareas RSS; añadir una pantalla
  propia ligera para pedir informes, escuchar, revisar fuentes e historial.
- Guion en español con enlaces y atribución a las fuentes. En IA se distingue
  anuncio oficial, investigación y análisis de terceros.
- Síntesis de audio española por bloques, reproductor y descarga del archivo;
  transcripción sincronizada o asociada al audio.
- Historial de informes y posibilidad de reproducirlos sin regenerar el audio.
- Registro de errores de ingesta y reintentos acotados.

### Fuera del MVP

- Envío automático por correo, Telegram, RSS personalizado o notificaciones
  push. Primero se valida el informe bajo demanda.
- Scraping de redes sociales con autenticación o automatización de cuentas.
- Reproducción íntegra de artículos, traducción íntegra o almacenamiento de
  copias completas sin una base jurídica/licencia revisada.
- Comentarios, colaboración multiusuario, recomendaciones sociales o ranking
  basado en popularidad.
- Entrenamiento/fine-tuning de modelos propios.
- Replicar la interfaz, marca o contenido propietario de Feedly o NotebookLM.

## 4. Reglas editoriales y de evidencia

1. Conservar autor, fuente original y enlace en toda categoría; no presentar
   resumen o clasificación generada como contenido textual original del autor.
   Para la categoría IA, priorizar anuncio/documentación del creador y después
   distinguir paper, cobertura de terceros y análisis.
2. Toda afirmación concreta del informe debe apuntar a una o más fuentes
   guardadas. El reproductor debe ofrecer acceso a la lista de fuentes y el
   informe de texto debe enlazarlas junto a los puntos relevantes.
3. Para la categoría IA, no afirmar que un modelo es “nuevo” solo porque se
   actualizó el repositorio. Diferenciar `new_model`, `model_update`,
   `weights_release`, `API_release`,
   `research_paper`, `product_update`, `analysis` y `other`.
4. Guardar por separado la fecha declarada por el editor, la fecha de primera
   captura y la fecha de última modificación conocida. Mostrar zona horaria o
   fecha sin hora si la fuente no permite resolverla.
5. La extracción automática propone clasificación y entidades; una puntuación
   baja o conflicto de fechas debe aparecer como “por verificar”, nunca
   resolverse inventando un dato.
6. En el texto/audio, distinguir “el creador afirma” de resultados
   independientes. No inferir benchmarks, licencia, idiomas, tamaño,
   disponibilidad o pesos que la fuente no confirme.
7. No sintetizar una lista de títulos sin contexto: incluir qué cambió, para
   quién importa y limitaciones conocidas, sin añadir opinión no atribuida.
8. Guardar metadatos, enlaces y extractos breves necesarios; evitar copiar el
   cuerpo completo de artículos por defecto. Revisar términos/licencias antes
   de habilitar extracción extensa o redistribución.

## 5. Taxonomía inicial

Las categorías deben ser editables, no codificadas como una lista cerrada. Las
áreas de IA son una taxonomía sugerida, no el alcance temático total.

### Categorías generales iniciales sugeridas

- Tecnología y software.
- Ciencia e investigación.
- Negocios y economía.
- Política, regulación y seguridad.
- Salud, educación, cultura y medios.
- Categorías personalizadas por el usuario.

### Tipos de publicación

- Noticia/artículo.
- Anuncio o comunicado.
- Investigación/paper/preprint.
- Lanzamiento o actualización de producto/servicio.
- Análisis, opinión o comentario.
- Podcast, video u otro adjunto de audio/video.
- Tipo personalizado por el usuario.

### Clasificación especializada para IA/modelos

- Lanzamiento de modelo/familia; actualización; publicación de pesos/API.
- Investigación/paper, evaluación/benchmark o informe técnico.
- Herramienta/plataforma basada en IA.
- Política, seguridad o regulación de IA.
- Análisis de terceros, separado de la fuente creadora.

### Áreas/modelos

- LLM y razonamiento.
- Modelos abiertos/pesos disponibles.
- Visión, VLM y documentos/OCR.
- Audio: voz, STT, TTS y música.
- Video e imagen generativa.
- Agentes y uso de herramientas.
- Embeddings y búsqueda.
- Robótica/mundo físico.
- Ciencia y modelos especializados.

Cada elemento puede tener varias etiquetas. Mantener separada la categoría
editorial del tipo de modelo; p. ej., un anuncio de pesos de un modelo de audio
lleva ambas dimensiones.

## 6. Fuentes iniciales y estrategia de descubrimiento

No limitar la aplicación a una lista de laboratorios. El usuario puede añadir
feeds de cualquier tema compatible. El paquete inicial de ejemplo/prueba debe
mezclar varias categorías generales con una colección de IA/modelos; puede
incluir noticias, blogs, investigación, lanzamientos oficiales y releases de
repositorios. Candidatos de la colección IA: OpenAI News, Anthropic News,
Google DeepMind News, Meta AI, Mistral AI, Microsoft Research/AI, NVIDIA
Research, repositorios oficiales de Qwen y DeepSeek, Hugging Face de las
organizaciones creadoras y arXiv. Esta lista es editable y no limita admisión.
Verificar URL, tipo de fuente y método antes de incorporarlos.

### Orden de preferencia de captura

1. RSS/Atom oficial.
2. API pública/documentada del propietario.
3. Feed de actividad/release del repositorio oficial (por ejemplo, Atom de
   GitHub cuando aplique).
4. Adaptador de página oficial con extracción acotada, términos revisados,
   respeto de las reglas de rastreo publicadas, límites de frecuencia, caché y
   `ETag`/`Last-Modified` cuando el servidor los proporcione.
5. Entrada manual aprobada por el usuario cuando la fuente no sea automatizable.

El producto debe importar/exportar OPML para portabilidad del catálogo de feeds.
La configuración de categorías y el estado de lectura son datos del producto y
deben persistir aunque una fuente deje de estar disponible.

Hugging Face puede detectar nuevos/actualizados repositorios de modelos por
organización mediante Hub API/webhooks, pero esto es señal de descubrimiento,
no prueba suficiente de que se trate de un anuncio público del creador. El
artículo o card oficial debe verificarse antes de etiquetar un lanzamiento.

Feedly queda como integración opcional. No es dependencia de MVP: su API requiere
acceso/plan habilitado y funciones adicionales pueden tener requisitos propios.
No basar el diseño en API privada ni reutilizar contenido sin confirmar las
condiciones vigentes.

## 7. Flujo funcional

```text
Fuentes registradas
  → sondeo programado y adaptadores
  → conservar todas las entradas disponibles en cada feed
  → normalizar + organizar en categorías/estado de lectura
  → búsqueda y lectura del catálogo completo
  → petición del usuario (feed completo o periodo + categorías + preferencias)
  → selección de entradas por filtros/cursor
  → guion español con enlaces a las fuentes
  → enriquecimiento especializado opcional para IA/modelos
  → validaciones de citas/afirmaciones
  → síntesis TTS por segmentos
  → edición reproducible: texto + audio + fuentes
```

La vigilancia periódica es independiente de la entrega. No filtrar entradas
durante la ingesta por relevancia, categoría o valoración del LLM; todos los
elementos se mantienen en el lector, y solo el informe aplica la selección del
usuario. Si la selección no contiene novedades, informar “sin novedades” sin
reciclar contenido. Guardar el cursor del informe para que “desde el último”
sea determinista; permitir reejecución y conservar versiones del guion.

## 8. Diseño técnico recomendado

La arquitectura debe iniciar como **monolito modular** para reducir coste y
complejidad. Separar interfaces internas para poder extraer workers más tarde.

### Componentes

1. **Experiencia de usuario:** reutilizar inicialmente la UI/API de Miniflux
   para gestionar feeds, leer, buscar y organizar; añadir una aplicación
   complementaria pequeña para lanzar informes, mostrar citas y reproducir
   audio. No construir un segundo lector completo en el MVP.
2. **Catálogo de fuentes/adaptadores:** contrato común para ejecutar una
   consulta, devolver entradas normalizadas y reportar errores/reintentos.
3. **Planificador/worker:** ingestión periódica y tareas de informe/audio
   asíncronas. No ejecutar crawls largos dentro de la petición HTTP.
4. **Persistencia relacional:** conexiones/feeds, entradas, categorías,
   etiquetas, estado de lectura, ejecuciones y ediciones de informe; entidades
   de creador/modelo son una extensión opcional del dominio general.
5. **Almacenamiento de audio:** interfaz abstracta para almacenamiento local
   durante desarrollo y almacenamiento persistente aprobado en despliegue.
6. **Capa LLM:** adaptador intercambiable para extracción/clasificación y
   síntesis con salida estructurada y validación de esquema. El modelo no es
   fuente de verdad.
7. **Capa TTS:** adaptador intercambiable, segmentación, unión de audio,
   metadatos y duración. No fijar proveedor/voz antes de una comparación
   española reproducible.
8. **Observabilidad:** logs estructurados, métricas de fallos/duración y
   trazabilidad por `source_id`, `ingestion_run_id`, `digest_id`; nunca registrar
   claves ni cuerpos completos innecesarios.

### Stack de referencia con reutilización OSS prioritaria

- **Dominio propio:** backend Python/FastAPI con `uv` es la opción inicial
  recomendada para integrar el lector, generar informes, mantener la
  procedencia y añadir extensiones de dominio (como seguimiento de modelos).
  No debe volver a implementar el catálogo general si el lector OSS elegido ya
  lo proporciona. La UI consume el lector y el componente de informes.
- **RSS/UI:** reutilizar Miniflux como lector principal (interfaz y servicio)
  para gestionar, leer, buscar, marcar y organizar feeds; la aplicación propia
  será complementaria y enfocada en informes/audio. Integrar vía API documentada,
  nunca accediendo a sus tablas. Si faltan categorías a nivel de artículo o
  colecciones, añadir solo esa capa delgada en el complemento. Fuentes sin
  feed/API nativos usan adaptadores pequeños; RSSHub queda como fallback.
- **Persistencia:** PostgreSQL para los datos de dominio. Si se adopta Miniflux,
  su base interna es propiedad de Miniflux; no acceder directamente a sus
  tablas. Documentar ambas bases y backups antes de integración.
- **Audio:** integrar Podcastfy como adaptador Python para guion conversacional
  en español, sujeto a prueba de calidad técnica, privacidad, API y dependencias.
  No reimplementar esa etapa si cumple. Mantener TTS directo por segmentos solo
  como fallback ante una carencia demostrada. Podcastfy no sustituye ingesta,
  verificación ni el historial del producto.
- Worker/scheduler en el mismo proyecto en el MVP; frontend web responsive;
  almacenamiento persistente de objetos para audio y arquitectura modular, no
  microservicios por anticipado.
- Evaluar opciones del estudio existente
  `docs/EVALUACION_STT_TTS_CLONACION_VOZ.md`; no fijar voz/proveedor hasta medir
  pronunciación de nombres de modelos, siglas, cifras y anglicismos en español.

Este stack es una recomendación para estimación, no una autorización para
desplegar ni para instalar servicios localmente. El nuevo proyecto debe decidir
su entorno y documentarlo antes de cualquier prueba integrada.

El repositorio del producto debe declarar una licencia aprobada por OSI. Se
propone Apache-2.0; confirmar antes de crear el archivo `LICENSE`. Mantener un
inventario de licencias de dependencias, modelos, voces, prompts, datasets y
assets: que el código sea OSS no convierte automáticamente esos materiales en
open source.

## 9. Modelo de datos mínimo

- `feed_connection`: URL/identificador, título, sitio, formato, credenciales
  referenciadas de forma segura, estado de sincronización, cursor y metadatos de
  polling. Miniflux puede ser dueño de esta entidad si se elige como lector.
- `item`: feed de origen, GUID/URL canónica, título, autor, fechas, idioma,
  contenido exactamente al nivel disponible, adjuntos, huella y estado.
- `category`, `collection`, `tag` y relaciones: taxonomía/carpeta del usuario y
  asignaciones múltiples; importación/exportación OPML mantiene feeds, no obliga
  a fusionar preferencias privadas del motor.
- `reading_state`: leído/no leído, guardado/favorito y fecha del cambio.
- `item_relation`: duplicado o cobertura relacionada; relaciones no eliminan
  entradas individuales ni reemplazan el acceso al original.
- `creator` y `model_entity`: extensión opcional para la categoría IA; atributos
  solo con evidencia (modalidad, pesos, licencia, idiomas, parámetros, contexto).
- `ingestion_run`: inicio/fin, conteos, errores resumidos, estado y versión del
  adaptador.
- `digest`: rango temporal, filtros, cursor, formato, idioma, duración objetivo,
  estado y versión de prompt/modelo.
- `digest_story`: orden, motivo de inclusión, resumen, afirmaciones y fuentes.
- `audio_asset`: formato, duración, tamaño, checksum, voz/proveedor/modelo,
  estado y URI del almacenamiento.

Las eliminaciones y retención deben ser explícitas y configurables. Los cambios
de clasificación conservan historial suficiente para auditar informes ya
generados.

## 10. Generación del informe y del audio

1. Resolver el periodo con fechas UTC y mostrarlo en la zona local del usuario.
2. Seleccionar novedades inéditas para ese cursor; permitir incluir leídas o
   anteriores mediante una opción expresa.
3. Agrupar cobertura repetida por entidad/lanzamiento y mostrar varias fuentes
   sin repetir la misma historia.
4. Crear un esquema intermedio validado: título, resumen, relevancia, tipo,
   creador, fecha, afirmaciones, incertidumbres y referencias.
5. Generar un guion de duración objetivo configurable (valor inicial sugerido:
   5–8 minutos), dando prioridad a calidad/procedencia sobre completar una
   duración artificial.
6. Comprobar que cada afirmación factual del guion referencia una entrada
   seleccionada; rechazar o marcar segmentos no fundamentados.
7. Sintetizar por segmentos (introducción, historia, transición, cierre) para
   reintentar solo el segmento fallido. Añadir pausas y pronunciación de nombres
   técnicos mediante diccionario editable.
8. Guardar texto, referencias y audio como una edición inmutable; regenerar
   solo mediante acción explícita y guardar la nueva versión.
9. Si el texto excede límites del proveedor TTS, segmentar sin truncar ni
   alterar el contenido silenciosamente.

Audio Overview de NotebookLM es referencia de UX, no dependencia del backend:
   su documentación describe generación a partir de fuentes, reproducción,
   citas y descarga dentro de Gemini Notebook. No asumir API pública de
   automatización. El producto debe poder operar con su propia canalización.

## 11. Requisitos funcionales verificables

- **RF-01 Feeds:** el usuario puede añadir, probar, pausar y eliminar una
  suscripción; ver salud, última sincronización y errores.
- **RF-02 Portabilidad:** importar/exportar OPML conserva la lista de feeds;
  fallos en una fuente no bloquean la importación o sincronización de las demás.
- **RF-03 Captura completa:** se muestran y conservan todas las entradas
  entregadas por los feeds integrados, con origen, URL y fechas, sin filtrado
  temático implícito. Límites del contenido publicado por el feed son visibles.
- **RF-04 Organización:** categorías/colecciones y etiquetas personalizadas
  permiten asignación múltiple y filtros combinables. Se puede marcar leído/no
  leído y guardar/favorito.
- **RF-05 Búsqueda:** buscar texto en los metadatos y contenido disponible de
  las entradas, respetando el nivel de contenido provisto por cada fuente.
- **RF-06 Dedupe:** la misma URL/GUID no duplica registros; historias similares
  se agrupan como relacionadas sin eliminar ninguna entrada.
- **RF-07 Clasificación:** clasificación automática opcional puede sugerir tema
  y etiqueta; el usuario corrige y conserva sus cambios.
- **RF-08 Evidencia IA:** los atributos de modelos enlazan a una evidencia o
  quedan expresamente como no verificados.
- **RF-09 Informe bajo pedido:** generar un informe sobre el feed completo o
  selección por periodo, feeds, categorías, etiquetas y búsqueda; no imponer
  categoría IA por defecto.
- **RF-10 Incrementalidad:** “desde el último” usa el cursor guardado y no
  repite elementos salvo que el usuario lo solicite.
- **RF-11 Texto y citas:** cada historia ofrece enlaces al feed/entrada original
  y conserva autoría; la categoría IA distingue fuente oficial de terceros.
- **RF-12 Audio:** una edición lista puede reproducirse/descargarse y mantiene
  correspondencia con la versión de transcripción y referencias.
- **RF-13 Sin novedades:** devolver mensaje explícito sin generar relleno ni
  repetir contenido antiguo.
- **RF-14 Fallos:** timeout, respuesta inválida de una fuente, error de LLM o
  fallo parcial de TTS se muestran con estado recuperable y sin duplicar tareas.
- **RF-15 Reproducibilidad:** cada informe registra filtros, entradas incluidas,
  versión del generador y estado del audio.

## 12. Requisitos no funcionales y riesgos

- Ingesta idempotente, con timeouts, límites por dominio, backoff y respeto de
  políticas de acceso publicadas por cada fuente.
- Toda operación externa debe poder desactivarse por fuente/configuración.
- No guardar credenciales en el repositorio; secretos solo por mecanismo
  documentado del entorno.
- Protección contra SSRF: permitir solo esquemas/hosts autorizados, bloquear
  redes privadas y revalidar redirecciones DNS/HTTP antes de descargar.
- Limitar tamaño, MIME, redirecciones y tiempo de descarga; no ejecutar
  contenido de fuentes.
- Tratar texto de artículos como entrada no confiable; bloquear instrucciones
  embebidas en fuentes que intenten cambiar comportamiento del agente.
- Citas y enlaces deben sobrevivir a errores del modelo; la salida no se publica
  fuera del usuario autenticado en MVP.
- Retención limitada a metadatos, extractos proporcionados por la fuente y
  audio generado necesario. Revisar copyright, términos y privacidad antes de
  extracción extensa o entrega externa.
- Medir por informe: coste estimado/real de LLM y TTS, duración de generación,
  tasa de citas válidas, fallos por fuente, tamaño del audio y calidad española.
- Riesgo principal: anuncios sin RSS o con contenido dinámico; mitigación:
  adaptadores controlados, detección de cambios, fallback manual y monitor de
  salud de fuentes.
- Riesgo editorial: confundir actualización de pesos con nuevo modelo o tomar
  una afirmación promocional como evaluación independiente; mitigación:
  taxonomía y procedencia visibles.
- Riesgo de coste/latencia de audio: sintetizar por demanda, cachear ediciones
  inmutables y permitir texto sin audio cuando el usuario lo elija.

## 13. Interfaz prevista

1. **Inicio/Feed:** lector general con listas por fuente/categoría/colección,
   búsqueda, rango de fechas, leído/no leído, guardados y acciones de lectura.
2. **Detalle de entrada:** contenido disponible del feed, adjuntos, autor,
   fecha, enlace original, etiquetas y fuentes relacionadas. En IA, añadir
   evidencia del modelo y estado oficial/terceros cuando aplique.
3. **Crear informe:** feed completo o filtros por periodo (incluido “desde el
   último”), categoría, fuente, etiqueta o búsqueda; duración orientativa,
   estilo y selector de audio.
4. **Informe:** reproductor, transcripción por segmentos, citas por historia,
   descarga, filtros usados y hora de generación.
5. **Fuentes:** nombre, URL, método, categorías, última consulta, errores y
   controles para pausar/probar; importación/exportación OPML.

No se requieren screenshots de UI en este documento; la validación visual
posterior deberá cubrir móvil, tablet y escritorio según los estándares del
proyecto que implemente la aplicación.

## 14. Plan de entrega por fases

### Fase 0 — Confirmación y proyecto

- Confirmar nombre del proyecto, repositorio y rama designada.
- Confirmar Miniflux como lector base preferido; probar API, import/export OPML,
  leído/no leído, guardados, categorías, búsqueda, adjuntos y límites de captura.
- Definir categorías generales iniciales y seleccionar fuentes de prueba de
  varios temas; incluir la colección IA/modelos sin convertirla en único tema.
- Acordar canal de uso inicial (web solamente recomendado) y entorno de
  desarrollo/pruebas.
- **Prueba de integración previa al producto:** integrar 5–10 feeds reales
  autorizados de categorías distintas con Miniflux y validar que el usuario
  conserva acceso a todas las entradas, orden, contenido disponible, búsqueda,
  lectura/favoritos y categorías. Probar informes con selección multi-categoría
  y un informe específico de IA/modelos. Evaluar Podcastfy con muestras de
  distintas categorías y español técnico. Usar RSSHub solo para feeds oficiales
  no disponibles por vía nativa. Hacer pruebas en el repositorio/rama aprobados,
  no crear una copia de proyecto.
- Revisar licencias, avisos de atribución, dependencias, seguridad, privacidad,
  calidad española y operación. Excluir código CC BY-NC de AI Summary Podcast y
  código sin licencia clara de Daily Digest; mantenerlos como referencias.
- Registrar evidencia reproducible. Por defecto reutilizar Miniflux + Podcastfy;
  sustituir alguno solo si una prueba demuestra que no cumple un requisito.
- Revisar el stack disponible y el documento actual de TTS español.
- Crear issue aprobado con alcance y criterios antes de modificar código.

**Salida:** matriz de compatibilidad OSS, evidencia de integración, decisión de
licencia del producto y dependencias, issue autorizado y repositorio objetivo.
No iniciar Fase 1 hasta aprobar esta salida.

### Fase 1 — Esqueleto y contratos

- Crear estructura del servicio y documentación bootstrap exigida por el
  repositorio de destino.
- Integrar el lector elegido con autenticación/configuración aprobada; definir
  únicamente contratos de extensión para informes, clasificación y audio.
- Definir estados de sincronización/informe/audio y el modelo complementario que
  el lector existente no cubra (no duplicar entradas, etiquetas o read-state).
- Crear fixtures de fuentes verificadas y ejemplos sintéticos únicamente para
  límites/fallos; las entradas reales vendrán de fuentes públicas autorizadas.
- Validar contratos y modelo de datos antes de activar recolección remota.

**Salida:** aplicación arranca, migraciones reproducibles, contratos y pruebas
unitarias/contrato.

### Fase 2 — Colector y feed

- Configurar el lector integrado con 5–10 feeds de varias áreas; evitar reescribir
  su parser, scheduler o lector salvo que la prueba identifique una brecha
  esencial.
- Implementar adaptadores propios solo para fuentes importantes que carezcan de
  feed/API; añadir idempotencia, errores visibles y controles de URL.
- Añadir el paquete curado de categorías/fuentes de ejemplo y verificar OPML,
  búsqueda, estado de lectura y acceso a todas las entradas.
- Ejecutar pruebas integradas respetando las políticas de cada fuente y
  registrar qué campos/contenido no entrega cada feed.

**Salida:** todas las entradas de feeds integrados pueden consultarse y
organizarse en el lector reutilizado; cada entrada conserva la fuente original.

### Fase 3 — Clasificación y entidades

- Implementar etiquetas/categorías generales configurables y sugerencias
  automáticas que nunca oculten ni excluyan entradas del lector.
- Crear conjunto de evaluación con entradas de varias áreas y ejemplos de
  etiquetas ambiguas; añadir un subconjunto de anuncios, actualizaciones,
  papers y análisis de IA.
- Medir precisión/recall por categoría y preferir “por revisar” cuando exista
  incertidumbre; aplicar controles específicos de anuncio oficial solo a IA.

**Salida:** organización general evaluada y, de forma separada, enriquecimiento
de IA evaluado; las entradas originales siguen disponibles aunque falle el LLM.

### Fase 4 — Informe textual

- Selector de periodo y filtros; cursor incremental.
- Guion basado únicamente en entradas seleccionadas, con citas por afirmación.
- Validación de citas, ausencia de novedades y vista de informe/historial.
- Pruebas de no repetición, conflictos, fechas y atribución.

**Salida:** resumen español auditable en texto.

### Fase 5 — Audio

- Comparar TTS de español con un guion común: inteligibilidad de nombres
  técnicos, acentos, números, siglas, latencia, coste, licencia/condiciones y
  posibilidad de operación local.
- Elegir proveedor/voz después de una prueba documentada; no incluir clonación
  de voz en MVP.
- Implementar generación segmentada, almacenamiento, reproductor y descarga.
- Probar audio parcial fallido, regeneración y correspondencia texto/audio.

**Salida:** informe de texto y audio reproducible, con decisión TTS justificada.

### Fase 6 — Piloto y endurecimiento

- Ejecutar piloto con 8–15 feeds de varias categorías, incluyendo feeds
  oficiales de IA/modelos, por un periodo acordado.
- Revisar muestras de cobertura de ingesta, organización, duplicados, informes,
  citas y errores con el usuario.
- Validar seguridad SSRF, límites, retención, accesibilidad, dispositivos y
  costes reales.
- Corregir issues aprobados; no habilitar envío automático ni despliegue
  público sin autorización independiente.

**Salida:** evidencia piloto, pendientes explícitos y recomendación go/no-go.

## 15. Estrategia de pruebas y puertas de calidad

- **Unitarias:** normalización URL/fechas, canonicalización, dedupe, reglas de
  categorías, cursores, segmentación TTS, validación de esquema y permisos.
- **Contrato:** cada adaptador transforma respuestas reales grabadas/autorizadas
  al esquema común; endpoints API mantienen contrato documentado.
- **Integración:** persistencia, scheduler, reintentos, idempotencia,
  almacenamiento de audio y recuperación de tareas parciales.
- **E2E:** configurar fuente → importar → filtrar → solicitar informe → abrir
  cita → reproducir/descargar audio → consultar historial.
- **Calidad editorial:** conjunto etiquetado para detectar anuncio oficial,
  update vs modelo nuevo dentro de IA; evaluar sugerencias de categoría general
  por separado. Informe evaluado por cobertura de entradas seleccionadas,
  precisión factual, atribución y repetición.
- **Seguridad:** SSRF, redirecciones, DNS rebinding, HTML malicioso, prompt
  injection de fuentes, archivos de gran tamaño, secretos y control de acceso.
- **Operación:** una fuente caída, API rate-limit, LLM/TTS no disponible,
  reintento, cancelación y recuperación después de reinicio.
- Ejecutar lint, type checks, migraciones y suites existentes antes de marcar
  criterios cumplidos. Pruebas con servicios persistentes deben usar únicamente
  el entorno remoto aprobado que conste en `REMOTE.md` del repositorio destino.

## 16. Métricas de éxito del piloto

No fijar valores inventados antes de la línea base. Registrar y acordar umbrales
tras una semana de observación. Métricas mínimas:

- porcentaje de ejecuciones de fuente exitosas y frescura de cada fuente;
- porcentaje de entradas recibidas que quedan disponibles en el lector, sin
  filtrado por clasificación;
- precisión de sugerencias de categorías generales y tasa de correcciones;
- para IA, anuncios oficiales detectados y falsos positivos frente al conjunto
  revisado;
- porcentaje de afirmaciones factuales con fuente válida;
- tasa de historias duplicadas/repetidas entre informes;
- tasa de informes y audios generados sin fallo;
- latencia p50/p95 y coste por informe en texto y audio;
- valoración humana del contenido español, pronunciación y utilidad;
- duración real frente a la duración elegida por el usuario.

### Condiciones de aceptación del piloto

- Para cada historia factual del informe, el usuario puede abrir una fuente
  primaria o se indica explícitamente que solo existe cobertura secundaria.
- El sistema no clasifica como lanzamiento oficial una fuente de terceros sin
  confirmación del creador.
- “Desde el último informe” no repite historias ya incluidas sin acción expresa.
- Fallo de una fuente no bloquea el resto de la ingesta y queda visible.
- Si el audio falla, el informe textual permanece disponible y el audio puede
  reintentarse sin regenerar/repetir historias.
- El usuario entiende periodo, filtros, hora y versión del informe.

## 17. Decisiones que debe confirmar el dueño antes del desarrollo

El agente que reciba este plan debe presentar estas decisiones en el issue o
documento de arranque; no inventar valores operativos:

1. Nombre del producto y repositorio/grupo destino.
2. Uso individual privado (recomendado) o multiusuario.
3. Interfaz inicial: web solamente (recomendado) u otro canal.
4. Categorías generales iniciales, feeds de ejemplo y frecuencia máxima
   aceptable por fuente; feeds de IA/modelos serán una colección, no el único
   contenido del producto.
5. Duración/estilo predeterminado del informe y zona horaria de presentación.
6. TTS remoto, local o ambos; límites de coste/privacidad y voz española.
7. Entorno de desarrollo y servidor de prueba; ubicación persistente del audio.
8. Retención de entradas, transcripciones y audios.
9. Si se autoriza uso de una cuenta/API de Feedly; por defecto, no depender de
   ella.
10. Política de envío automático futuro; por defecto, solo petición explícita.

Recomendaciones iniciales, sujetas a aprobación: lector de propósito general,
Miniflux como lector principal y UI de feeds, Podcastfy para audio si supera las
pruebas, aplicación complementaria solo para informes/audio, un usuario,
informes bajo demanda en español, feeds de ejemplo de varias categorías,
colección inicial de IA/modelos, cinco a ocho minutos como objetivo flexible,
TTS seleccionable y sin clonación de voz.

## 18. Instrucciones para el agente implementador

- Este documento es la especificación inicial, no permiso para desplegar,
  publicar audio externamente, crear recursos pagos o activar fuentes que
  requieran credenciales.
- Antes de programar: verificar el repositorio y `REMOTE.md`, revisar issues
  abiertos y cerrados, buscar duplicados, acordar el issue y sus criterios,
  confirmar rama y entorno. Respetar las instrucciones del repositorio de
  destino, especialmente límites de workspace y despliegue.
- Implementar por fases; no crear microservicios por adelantado.
- Mantener las fuentes, prompts, modelos, voces, rutas y frecuencias como
  configuración tipada, no como literales dispersos.
- No publicar una historia si no conserva su procedencia; no resolver
  incertidumbre mediante una afirmación generada por el LLM.
- Mantener separadas las fases de commit/push, publicación de imágenes,
  despliegue y difusión del audio; cada una exige la autorización aplicable.
- Registrar métricas y evidencia del piloto antes de recomendar producción.

## 19. Referencias consultadas

- Feedly API: [introducción](https://developers.feedly.com/reference/introduction),
  [autorización y requisitos de acceso](https://developers.feedly.com/reference/authorization),
  [Ask AI API](https://developers.feedly.com/reference/ai-actions-experimental).
- Hugging Face Hub: [API de modelos y webhooks](https://huggingface.co/docs/hub/en/api),
  [filtros/listado por organización](https://huggingface.co/docs/huggingface_hub/main/package_reference/hf_api).
- GitHub: [REST API de feeds y formato Atom](https://docs.github.com/en/rest/activity/feeds?apiVersion=2022-11-28).
- Comparación de proyectos:
  [AI Summary Podcast](https://github.com/applab-nl/ai-summary-podcast),
  [su licencia CC BY-NC 4.0](https://github.com/applab-nl/ai-summary-podcast/blob/main/LICENSE),
  [Daily Digest](https://github.com/MarcelloMorettoni/daily-digest),
  [Podcastfy](https://github.com/souzatharsis/podcastfy),
  [licencia Apache-2.0 de Podcastfy](https://github.com/souzatharsis/podcastfy/blob/main/LICENSE),
  [Miniflux](https://github.com/miniflux/v2),
  [FreshRSS](https://github.com/FreshRSS/FreshRSS),
  [RSSHub](https://github.com/DIYgod/RSSHub).
- Licencias: [Open Source Definition de OSI](https://opensource.org/osd),
  [licencia Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0.html).
- NotebookLM/Gemini Notebook: [generar Audio Overview, consultar fuentes,
  reproducir y descargar](https://support.google.com/gemininotebook/answer/16212820?hl=en).
- OpenAI: [API de generación de audio](https://platform.openai.com/docs/api-reference/audio/json-object?lang=csharp).
- Fuentes de ejemplo a verificar durante Fase 0: [OpenAI News](https://openai.com/news),
  [Anthropic News](https://www.anthropic.com/news),
  [Google DeepMind News](https://deepmind.google/blog/).
- Investigación TTS local ya documentada en este repositorio:
  [`docs/EVALUACION_STT_TTS_CLONACION_VOZ.md`](EVALUACION_STT_TTS_CLONACION_VOZ.md).

---

**Uso previsto:** entregar este documento al agente que diseñará y construirá el
proyecto. Debe tratar las decisiones de la sección 17 como pendientes de
confirmación y no presentar el plan como producto ya implementado.
