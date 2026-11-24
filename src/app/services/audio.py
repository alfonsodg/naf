"""Build the spoken edition of one stored report.

The report text is flattened into a reading script, split into sentence-sized
segments, synthesized in order, and framed into one WAV file. An edition keeps
its asset until the caller explicitly asks for a regeneration, so the artifact
stays immutable between requests.
"""

import hashlib
import io
import re
import wave
from collections.abc import Iterator
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import TTSError
from app.core.ports.storage import AudioStorage
from app.core.ports.tts import TTSProvider
from app.models import AudioAsset, Digest
from app.schemas.audio import AudioAssetMetadata, TTSConfig

PROVIDER = "kokoro-onnx"
AUDIO_FORMAT = "wav"
ASSET_VERSION = "1.0"
MAX_SEGMENT_CHARS = 400
SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+")


class AudioService:
    """Turn one ready report into a stored WAV asset."""

    def __init__(self, session: Session, tts: TTSProvider, storage: AudioStorage, settings: Settings) -> None:
        """Bind the service to storage, the speech port, and the settings."""
        self.session = session
        self.tts = tts
        self.storage = storage
        self.settings = settings

    async def generate(self, digest: Digest, force: bool = False) -> AudioAsset:
        """Return the existing asset or synthesize, store, and record a new one.

        A synthesis failure leaves the edition untouched: ``has_audio`` only
        flips after the audio was stored and the row was committed, so the text
        report stays available and the request can be retried.
        """
        identifier = cast(int, digest.id)
        existing = AudioService.latest_asset(self.session, identifier)
        if existing is not None and not force:
            return existing

        texts = split_script(build_script(digest))
        if not texts:
            raise TTSError("the report has no text to synthesize")
        config = TTSConfig(
            provider=PROVIDER,
            voice=self.settings.tts_voice or None,
            speed=self.settings.tts_speed,
            language=self.settings.tts_language,
        )
        segments = await self.tts.synthesize_batch(texts, config)
        if not segments:
            raise TTSError("the speech engine returned no segments")

        sample_rate = segments[0].sample_rate
        pcm = b"".join(segment.audio_bytes for segment in segments)
        duration = len(pcm) / (2 * sample_rate)
        wav = _wav_bytes(pcm, sample_rate)
        checksum = hashlib.sha256(wav).hexdigest()
        metadata = AudioAssetMetadata(
            digest_id=str(identifier),
            filename=f"report-{identifier}-{checksum[:16]}.{AUDIO_FORMAT}",
            format=AUDIO_FORMAT,
            duration_seconds=round(duration, 3),
            size_bytes=len(wav),
            checksum=checksum,
            provider=PROVIDER,
            voice=self.settings.tts_voice or None,
            version=ASSET_VERSION,
        )
        file_path = await self.storage.store(wav, metadata)

        row = AudioAsset(
            digest_id=identifier,
            filename=metadata.filename,
            file_path=file_path,
            format=AUDIO_FORMAT,
            duration_seconds=metadata.duration_seconds,
            size_bytes=metadata.size_bytes,
            checksum=checksum,
            provider=PROVIDER,
            voice=metadata.voice,
            version=ASSET_VERSION,
        )
        # The model declares columns without Mapped annotations, so mypy reads
        # the instance attribute as its descriptor; the runtime value is a bool.
        digest.has_audio = True  # type: ignore[assignment]
        digest.audio_assets.append(row)
        self.session.add(row)
        self.session.commit()
        return row

    @classmethod
    def latest_asset(cls, session: Session, digest_id: int) -> AudioAsset | None:
        """Return the newest asset stored for one edition, if any."""
        statement = select(AudioAsset).where(AudioAsset.digest_id == digest_id).order_by(AudioAsset.id.desc()).limit(1)
        return session.execute(statement).scalars().first()


def build_script(digest: Digest) -> str:
    """Flatten the edition into the Spanish reading script one voice reads."""
    title = cast(str, digest.title)
    summary = cast(str | None, digest.summary)
    blocks: list[str] = [title, summary or ""]
    for story in sorted(digest.stories, key=lambda row: row.order_index or 0):
        blocks.append(story.title)
        if story.summary:
            blocks.append(story.summary)
        claims = [str(claim).strip() for claim in (story.claims or []) if str(claim).strip()]
        if claims:
            blocks.append(" ".join(claims))
    return "\n\n".join(block.strip() for block in blocks if block.strip())


def split_script(script: str, limit: int = MAX_SEGMENT_CHARS) -> list[str]:
    """Split the script into ordered segments of at most ``limit`` characters.

    Sentences are packed together while they fit; a sentence longer than the
    limit is split on word boundaries, so no segment ever starts or ends in the
    middle of a word.
    """
    segments: list[str] = []
    current = ""
    for sentence in _sentences(script):
        if len(sentence) > limit:
            if current:
                segments.append(current)
                current = ""
            segments.extend(_split_words(sentence, limit))
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            segments.append(current)
            current = sentence
    if current:
        segments.append(current)
    return segments


def _sentences(script: str) -> Iterator[str]:
    """Yield normalized sentences, keeping paragraph breaks as pauses."""
    for paragraph in script.split("\n\n"):
        normalized = " ".join(paragraph.split())
        if not normalized:
            continue
        for sentence in SENTENCE_BREAK.split(normalized):
            if sentence:
                yield sentence


def _split_words(sentence: str, limit: int) -> list[str]:
    """Split one oversized sentence on spaces, never inside a word."""
    segments: list[str] = []
    current = ""
    for word in sentence.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            segments.append(current)
            current = word
    if current:
        segments.append(current)
    return segments


def _wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    """Frame mono 16-bit PCM into one WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()
