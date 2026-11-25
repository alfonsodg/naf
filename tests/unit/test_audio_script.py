"""The reading script and its segmentation, without an engine or a database."""

from app.models import Digest, DigestStory
from app.services.audio import MAX_SEGMENT_CHARS, build_script, split_script


def _digest() -> Digest:
    """Build an in-memory edition with two ordered stories."""
    return Digest(
        title="Radar semanal",
        summary="Resumen del periodo seleccionado.",
        stories=[
            DigestStory(
                title="Historia uno",
                summary="Explicación de la primera historia.",
                claims=["Primera afirmación.", "Segunda afirmación."],
                order_index=0,
            ),
            DigestStory(
                title="Historia dos",
                summary="Explicación de la segunda historia.",
                claims=["Tercera afirmación."],
                order_index=1,
            ),
        ],
    )


def test_the_script_keeps_every_story_field_in_order() -> None:
    """Title, summary, story titles, summaries, and claims all reach the voice."""
    script = build_script(_digest())

    assert script.startswith("Radar semanal\n\nResumen del periodo seleccionado.")
    assert "Historia uno" in script
    assert "Explicación de la primera historia." in script
    assert "Primera afirmación. Segunda afirmación." in script
    assert "Tercera afirmación." in script
    assert script.index("Historia uno") < script.index("Historia dos")


def test_the_script_is_packed_into_bounded_segments() -> None:
    """Sentences are packed while they fit and no segment exceeds the limit."""
    script = "Una frase corta. " * 80

    segments = split_script(script)

    assert len(segments) > 1
    assert all(len(segment) <= MAX_SEGMENT_CHARS for segment in segments)
    assert " ".join(segments).split() == script.split()


def test_an_oversized_sentence_is_split_between_words() -> None:
    """A sentence with no punctuation is split on spaces, never inside a word."""
    script = " ".join(["palabra"] * 200)

    segments = split_script(script)

    assert len(segments) > 1
    assert all(len(segment) <= MAX_SEGMENT_CHARS for segment in segments)
    assert " ".join(segments).split() == script.split()
    assert all(set(segment.split()) == {"palabra"} for segment in segments)
