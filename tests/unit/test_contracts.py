from app.contracts import (
    Classification,
    DigestStory,
    Citation,
    TTSConfig,
)


def test_classification_model():
    c = Classification()
    assert c.confidence == 0.0
    assert c.uncertainty is False
    assert c.review_needed is False
    assert c.categories == []


def test_citation_model():
    cit = Citation(
        entry_id="123",
        entry_url="https://example.com",
        title="Test",
    )
    assert cit.entry_id == "123"
    assert cit.relevance == 1.0


def test_digest_story_model():
    cit = Citation(entry_id="1", entry_url="u", title="t")
    story = DigestStory(title="s", summary="sum", claims=["c1"], citations=[cit])
    assert story.title == "s"
    assert len(story.claims) == 1


def test_tts_config():
    cfg = TTSConfig()
    assert cfg.provider == "podcastfy"
    assert cfg.language == "es-ES"
    assert cfg.speed == 1.0
