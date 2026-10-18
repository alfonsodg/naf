# Contratos (Ports/Interfaces) - Fase 1

**Fecha:** 2026-10-18  
**Issue:** [#3](https://github.com/alfonsodg/naf/issues/3)

## Principio

Los contratos (interfaces) viven en `app/contracts/` y definen el comportamiento
sin detalles de infraestructura. Las implementaciones (adaptadores) en
`app/adapters/` dependen de los contratos, no al revés (Dependency Inversion).

## 1. FeedReader (Miniflux API)

Contrato para leer desde Miniflux **solo vía API**. Nunca acceso a BD.

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class FeedReader(ABC):
    @abstractmethod
    async def health(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def list_feeds(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def get_entries(self, feed_id: Optional[int] = None,
                          limit: int = 100,
                          offset: int = 0,
                          category_id: Optional[int] = None,
                          starred: Optional[bool] = None,
                          read: Optional[bool] = None,
                          search: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def get_entry(self, entry_id: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def mark_entry_read(self, entry_id: int) -> bool: ...

    @abstractmethod
    async def export_opml(self) -> str: ...

    @abstractmethod
    async def import_opml(self, opml_content: str) -> Dict[str, Any]: ...
```

**Invariantes:**

- Solo lectura para operaciones de consulta (no modificar estado salvo marcado
  lectura si necesario)
- Debe preservar todos los campos originales (provenance)
- Timeouts configurables, reintentos con backoff
- Manejo errores: graceful degradation, no bloquear otros feeds

## 2. Classifier

Clasificación general + IA enrichment. Nunca filtra entradas del lector.

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel

class Classification(BaseModel):
    category: Optional[str] = None
    categories: List[str] = []
    tags: List[str] = []
    pub_type: Optional[str] = None  # news, article, announcement, paper, analysis...
    is_official: Optional[bool] = None  # for AI: official vs third-party
    confidence: float = 0.0
    uncertainty: bool = False
    review_needed: bool = False  # "por verificar"
    ai_enrichment: Optional[dict] = None
    rationale: str = ""

class Classifier(ABC):
    @abstractmethod
    async def classify(self, item: dict) -> Classification: ...

    @abstractmethod
    async def classify_batch(self, items: List[dict]) -> List[Classification]: ...
```

**Invariantes:**

- Si incertidumbre > umbral → `uncertainty=True`, `review_needed=True` ("por
  verificar")
- Nunca elimina/oculta entradas
- Sugerencias corregibles (usuario puede sobreescribir)
- IA enrichment separado de clasificación general
- Para AI: distinguir oficial/terceros; requerir evidencia para atributos
  model_entity

## 3. ReportGenerator

Generación de informe textual con citas obligatorias.

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from pydantic import BaseModel

class Citation(BaseModel):
    entry_id: str
    entry_url: str
    title: str
    author: Optional[str] = None
    quote: Optional[str] = None
    relevance: float = 1.0

class DigestStory(BaseModel):
    title: str
    summary: str
    claims: List[str]
    citations: List[Citation]
    pub_type: Optional[str] = None
    entities: List[Dict] = []

class Digest(BaseModel):
    title: str
    summary: str
    period_start: str
    period_end: str
    filters: Dict = {}
    cursor: Optional[str] = None
    stories: List[DigestStory]
    version: str = "1.0"

class ReportGenerator(ABC):
    @abstractmethod
    async def generate(self, entries: List[dict],
                       filters: dict,
                       since_last: Optional[str] = None) -> Digest: ...

    @abstractmethod
    def validate_citations(self, digest: Digest, entries: List[dict]) -> bool: ...
```

**Invariantes:**

- Toda afirmación factual debe tener ≥1 cita (validación obligatoria)
- `validate_citations()` debe rechazar digest con afirmaciones no referenciadas
- Soporta "sin novedades" → devolver digest vacío con mensaje explícito
- Cursor incremental determinista
- Cada digest versionado (inmutable)

## 4. TTSProvider

Proveedor TTS intercambiable, segmentado.

```python
from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel

class AudioSegment(BaseModel):
    text: str
    audio_bytes: bytes
    duration_seconds: float
    index: int

class TTSConfig(BaseModel):
    provider: str = "podcastfy"
    voice: Optional[str] = None
    speed: float = 1.0
    language: str = "es-ES"
    segment_pause_ms: int = 500

class TTSProvider(ABC):
    @abstractmethod
    async def synthesize_segment(self, text: str, config: TTSConfig) -> AudioSegment: ...

    @abstractmethod
    async def synthesize_batch(self, texts: List[str], config: TTSConfig) -> List[AudioSegment]: ...

    @abstractmethod
    def supports_segmentation(self) -> bool: ...
```

**Invariantes:**

- Síntesis por segmentos (retry solo segmento fallido)
- Configurable por provider (Podcastfy vs directo)
- No voice cloning (MVP)
- Español es-ES prioritario

## 5. AudioStorage

Almacenamiento abstracto de assets de audio.

```python
from abc import ABC, abstractmethod
from typing import Optional, BinaryIO

class AudioAssetMetadata(BaseModel):
    digest_id: str
    filename: str
    format: str = "mp3"
    duration_seconds: float
    size_bytes: int
    checksum: str
    provider: str
    voice: Optional[str] = None
    version: str = "1.0"

class AudioStorage(ABC):
    @abstractmethod
    async def store(self, audio_bytes: bytes, metadata: AudioAssetMetadata) -> str: ...

    @abstractmethod
    async def retrieve(self, asset_id: str) -> bytes: ...

    @abstractmethod
    async def get_url(self, asset_id: str) -> Optional[str]: ...

    @abstractmethod
    async def delete(self, asset_id: str) -> bool: ...
```

**Invariantes:**

- Assets inmutables (cambiar versión en nueva generación)
- Metadata completa (checksum, provider, duración)
- Interfaz abstracta (local → S3/compatible futuro)
- Retención configurable
