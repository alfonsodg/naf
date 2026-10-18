"""Schema contracts: validation rules that the rest of the system relies on."""

from app.schemas import Citation, Classification, Digest, DigestStory, TTSConfig


def test_classification_defaults_are_explicit() -> None:
    """An unclassified item reports uncertainty instead of guessing."""
    result = Classification()

    assert result.category is None
    assert result.uncertainty is False
    assert result.review_needed is False
    assert result.rationale == ""


def test_citation_requires_source_identity() -> None:
    """A citation must carry the entry id and URL it references."""
    citation = Citation(entry_id="10", entry_url="https://example.test/post-10", title="Post")

    assert citation.entry_id == "10"
    assert citation.entry_url == "https://example.test/post-10"
    assert citation.author is None


def test_digest_requires_stories_collection() -> None:
    """A digest always carries an explicit story list and version."""
    digest = Digest(
        title="Informe",
        summary="Resumen del periodo",
        period_start="2026-10-18T00:00:00Z",
        period_end="2026-10-18T23:59:59Z",
        stories=[],
    )

    assert digest.stories == []
    assert digest.filters == {}
    assert digest.version == "1.0"


def test_digest_story_keeps_citations() -> None:
    """Stories preserve their citations and claims together."""
    story = DigestStory(
        title="Modelo publicado",
        summary="Un modelo nuevo",
        claims=["El modelo se publicó"],
        citations=[Citation(entry_id="1", entry_url="https://example.test/1", title="Fuente")],
    )

    assert len(story.citations) == 1
    assert story.entities == []


def test_tts_config_requires_language_and_provider() -> None:
    """Speech configuration has no implicit defaults for provider or language."""
    config = TTSConfig(provider="podcastfy", language="es-ES")

    assert config.speed == 1.0
    assert config.segment_pause_ms == 500
    assert config.voice is None
