"""Build the spoken edition of one stored report.

The report text is flattened into reading blocks tagged with the story they
belong to, split into sentence-sized segments, synthesized one segment at a
time, and framed into one WAV file. Every segment keeps its playback window, so
the caller can follow the transcript, and a failed segment is retried on its own
instead of discarding the whole edition. An edition keeps its asset until the
caller explicitly asks for a regeneration, so the artifact stays immutable
between requests.
"""

import asyncio
import hashlib
import io
import re
import wave
from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import TTSError
from app.core.ports.storage import AudioStorage
from app.core.ports.tts import TTSProvider
from app.models import AudioAsset, Digest
from app.schemas.audio import AudioAssetMetadata, AudioSegment, TTSConfig

PROVIDER = "kokoro-onnx"
AUDIO_FORMAT = "wav"
ASSET_VERSION = "1.0"
SAMPLE_RATE = 24_000
MAX_SEGMENT_CHARS = 400
SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class ScriptBlock:
    """One part of the reading script and the story it belongs to."""

    text: str
    story_index: int | None


@dataclass(frozen=True)
class SegmentTiming:
    """Playback window and provenance of one synthesized segment."""

    index: int
    story_index: int | None
    start_seconds: float
    end_seconds: float
    text: str

    def as_record(self) -> dict[str, object]:
        """Project the timing as the JSON record the asset column stores."""
        return {
            "index": self.index,
            "story_index": self.story_index,
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "text": self.text,
        }


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

        script = split_blocks(build_blocks(digest))
        if not script:
            raise TTSError("the report has no text to synthesize")
        config = TTSConfig(
            provider=PROVIDER,
            voice=self.settings.tts_voice or None,
            speed=self.settings.tts_speed,
            language=self.settings.tts_language,
        )
        voiced, timings = await self._synthesize(script, config)
        pcm = b"".join(segment.audio_bytes for segment in voiced)
        duration = len(pcm) / (2 * SAMPLE_RATE)
        wav = _wav_bytes(pcm, SAMPLE_RATE)
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
            segments=[timing.as_record() for timing in timings],
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

    async def _synthesize(
        self, script: list[ScriptBlock], config: TTSConfig
    ) -> tuple[list[AudioSegment], list[SegmentTiming]]:
        """Synthesize each segment in order and time it on the concatenated track."""
        voiced: list[AudioSegment] = []
        timings: list[SegmentTiming] = []
        samples = 0
        for index, block in enumerate(script):
            segment = await self._synthesize_with_retry(block.text, index, config)
            if segment.sample_rate != SAMPLE_RATE:
                raise TTSError(f"segment {index} was synthesized at an unsupported sample rate")
            start = samples / SAMPLE_RATE
            samples += len(segment.audio_bytes) // 2
            timings.append(
                SegmentTiming(
                    index=index,
                    story_index=block.story_index,
                    start_seconds=round(start, 6),
                    end_seconds=round(samples / SAMPLE_RATE, 6),
                    text=block.text,
                )
            )
            voiced.append(segment)
        return voiced, timings

    async def _synthesize_with_retry(self, text: str, index: int, config: TTSConfig) -> AudioSegment:
        """Synthesize one segment, retrying only that segment when it fails."""
        attempts = self.settings.tts_segment_retries + 1
        last_error: TTSError | None = None
        for attempt in range(attempts):
            try:
                return await self.tts.synthesize_segment(text, config)
            except TTSError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(self.settings.tts_segment_retry_delay)
        raise TTSError(f"segment {index} could not be synthesized after {attempts} attempts") from last_error


def build_blocks(digest: Digest) -> list[ScriptBlock]:
    """Flatten the edition into reading blocks tagged with the story they voice.

    The report title and summary come first and belong to no single story, so
    their ``story_index`` is empty; every story then contributes its title, its
    summary, and its claims in that order.
    """
    blocks: list[ScriptBlock] = []
    title = cast(str, digest.title)
    summary = cast(str | None, digest.summary)
    for header in (title, summary):
        if header and header.strip():
            blocks.append(ScriptBlock(text=header.strip(), story_index=None))
    for story_index, story in enumerate(sorted(digest.stories, key=lambda row: row.order_index or 0)):
        blocks.append(ScriptBlock(text=cast(str, story.title).strip(), story_index=story_index))
        if story.summary:
            blocks.append(ScriptBlock(text=story.summary.strip(), story_index=story_index))
        claims = [str(claim).strip() for claim in (story.claims or []) if str(claim).strip()]
        if claims:
            blocks.append(ScriptBlock(text=" ".join(claims), story_index=story_index))
    return [block for block in blocks if block.text]


def build_script(digest: Digest) -> str:
    """Flatten the edition into the Spanish reading script one voice reads."""
    return "\n\n".join(block.text for block in build_blocks(digest))


def split_blocks(blocks: list[ScriptBlock], limit: int = MAX_SEGMENT_CHARS) -> list[ScriptBlock]:
    """Split every block into bounded segments, keeping its story index."""
    segments: list[ScriptBlock] = []
    for block in blocks:
        segments.extend(
            ScriptBlock(text=text, story_index=block.story_index) for text in split_script(block.text, limit)
        )
    return segments


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
