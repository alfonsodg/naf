"""Per-segment timing, story attribution, and independent retry of one segment.

The fake engine in this suite's conftest records every call, so the tests can
prove that a segment is retried on its own, that the retry budget comes from the
settings, and that the stored asset carries a monotonic transcript that ends
where the WAV ends.
"""

from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import AudioAsset, Digest
from app.services.audio import build_blocks, split_blocks

client = TestClient(app)
SEGMENT_KEYS = {"index", "story_index", "start_seconds", "end_seconds", "text"}


def _post(report_id: int, **params: Any) -> Any:
    """Ask for the spoken edition of one report."""
    return client.post(f"/api/v1/reports/{report_id}/audio", params=params)


def _detail(report_id: int) -> Any:
    """Read the stored edition through the API projection."""
    response = client.get(f"/api/v1/reports/{report_id}")
    assert response.status_code == 200
    return response.json()["data"]


def test_the_detail_projects_every_timed_segment(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """Segments are monotonic, contiguous, attributed, and end at the WAV length."""
    digest = audio_digest()

    asset = _post(digest.id).json()["data"]
    detail = _detail(digest.id)
    segments = detail["audio"][0]["segments"]

    assert asset["segments"] == segments
    assert all(set(segment) == SEGMENT_KEYS for segment in segments)
    assert [segment["index"] for segment in segments] == list(range(len(segments)))
    assert segments[0]["start_seconds"] == 0
    assert segments[-1]["end_seconds"] == pytest.approx(asset["duration_seconds"], abs=0.001)
    assert [segment["start_seconds"] for segment in segments] == sorted(
        segment["start_seconds"] for segment in segments
    )
    for previous, current in pairwise(segments):
        assert current["start_seconds"] == pytest.approx(previous["end_seconds"])
        assert current["end_seconds"] > current["start_seconds"]
    assert segments[0]["story_index"] is None
    stories = set(range(len(detail["stories"])))
    voiced = {segment["story_index"] for segment in segments if segment["story_index"] is not None}
    assert voiced == stories
    assert [segment["story_index"] for segment in segments] == sorted(
        (segment["story_index"] for segment in segments), key=lambda value: -1 if value is None else value
    )
    row = audio_session.execute(select(AudioAsset).where(AudioAsset.digest_id == digest.id)).scalars().one()
    assert row.segments == segments


def test_the_script_tags_the_header_and_every_story(audio_digest: Callable[..., Digest]) -> None:
    """The report header carries no story index and each story keeps its own."""
    digest = audio_digest()

    blocks = build_blocks(digest)

    assert [block.story_index for block in blocks] == [None, None, 0, 0, 0, 1, 1, 1]
    assert blocks[0].text == "Radar semanal"
    assert blocks[2].text == "Historia uno"


def test_a_segment_that_fails_once_is_retried_and_the_asset_is_stored(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """Only the refused segment is synthesized again; the edition keeps its asset."""
    digest = audio_digest()
    target = split_blocks(build_blocks(digest))[1].text
    audio_wiring.tts.fail_once.add(target)

    response = _post(digest.id)

    assert response.status_code == 201
    asset = response.json()["data"]
    assert audio_wiring.tts.calls.count(target) == 2
    assert audio_wiring.tts.texts.count(target) == 1
    assert audio_wiring.storage.calls == 1
    assert [segment["text"] for segment in asset["segments"]] == audio_wiring.tts.texts
    audio_session.refresh(digest)
    assert digest.has_audio is True


def test_a_segment_that_always_fails_stores_nothing(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest]
) -> None:
    """The whole edition is refused and the text report stays available."""
    digest = audio_digest()
    target = split_blocks(build_blocks(digest))[1].text
    audio_wiring.tts.always_fail.add(target)

    response = _post(digest.id)

    assert response.status_code == 502
    assert response.json()["detail"]["error"]["code"] == "TTS_SYNTHESIS_FAILED"
    assert audio_wiring.tts.calls.count(target) == 3
    assert audio_wiring.storage.calls == 0
    assert audio_session.execute(select(AudioAsset)).scalars().all() == []
    audio_session.refresh(digest)
    assert digest.has_audio is False
    assert _detail(digest.id)["audio"] == []


@pytest.mark.parametrize("retries", [0, 3])
def test_the_retry_count_comes_from_settings(
    audio_session: Session, audio_wiring: Any, audio_digest: Callable[..., Digest], retries: int
) -> None:
    """The configured budget decides how many attempts one segment receives."""
    audio_wiring.configure(tts_segment_retries=retries)
    digest = audio_digest()
    target = split_blocks(build_blocks(digest))[2].text
    audio_wiring.tts.always_fail.add(target)

    response = _post(digest.id)

    assert response.status_code == 502
    assert audio_wiring.tts.calls.count(target) == retries + 1
