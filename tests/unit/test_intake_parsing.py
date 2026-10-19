"""Feed intake parsing: a pasted URL list and an OPML export.

The readers are not involved here; these tests cover only how an input
document is reduced to a list of candidates.
"""

import pytest

from app.services.feed_intake import parse_opml, parse_url_list

FEEDLY_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <head><title>Subscriptions in feedly Cloud</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" text="Ars Technica" xmlUrl="https://arstechnica.test/rss" htmlUrl="https://arstechnica.test"/>
      <outline type="rss" text="The Verge" xmlUrl="https://verge.test/rss" htmlUrl="https://verge.test"/>
    </outline>
    <outline text="AI" title="AI">
      <outline type="rss" text="Ars Technica" xmlUrl="https://arstechnica.test/rss" htmlUrl="https://arstechnica.test"/>
      <outline type="rss" text="DeepMind" xmlUrl="https://deepmind.test/blog/rss"/>
    </outline>
    <outline type="rss" text="Loose feed" xmlUrl="https://loose.test/feed"/>
  </body>
</opml>"""


def test_url_list_ignores_blanks_and_comments() -> None:
    """A pasted list tolerates blank lines and comments."""
    text = """
    # my technical feeds
    https://a.test/feed

    https://b.test/rss
    """
    candidates = parse_url_list(text)

    assert [candidate.url for candidate in candidates] == ["https://a.test/feed", "https://b.test/rss"]


def test_url_list_deduplicates() -> None:
    """The same URL twice collapses to one candidate."""
    candidates = parse_url_list("https://a.test/feed\nhttps://a.test/feed\n")

    assert len(candidates) == 1


def test_url_list_allows_trailing_comment_on_a_line() -> None:
    """An inline comment after a URL is ignored."""
    candidates = parse_url_list("https://a.test/feed  # technology\n")

    assert [candidate.url for candidate in candidates] == ["https://a.test/feed"]


def test_opml_preserves_category_nesting() -> None:
    """Folder outlines become the categories of their feeds."""
    candidates = {candidate.url: candidate for candidate in parse_opml(FEEDLY_OPML)}

    assert candidates["https://verge.test/rss"].categories == ("Tech",)
    assert candidates["https://deepmind.test/blog/rss"].categories == ("AI",)


def test_opml_feed_under_several_tags_keeps_all_of_them() -> None:
    """Miniflux keeps only the first tag; here the overlap is preserved and reported."""
    candidates = {candidate.url: candidate for candidate in parse_opml(FEEDLY_OPML)}

    assert candidates["https://arstechnica.test/rss"].categories == ("Tech", "AI")


def test_opml_feed_outside_a_folder_has_no_category() -> None:
    """A top-level subscription is imported without a category."""
    candidates = {candidate.url: candidate for candidate in parse_opml(FEEDLY_OPML)}

    assert candidates["https://loose.test/feed"].categories == ()


def test_opml_counts_each_feed_once() -> None:
    """Repeated xmlUrl values do not produce duplicate candidates."""
    candidates = parse_opml(FEEDLY_OPML)

    assert len(candidates) == len({candidate.url for candidate in candidates})


def test_opml_rejects_a_non_opml_document() -> None:
    """An unrelated XML document is refused, not partially parsed."""
    with pytest.raises(ValueError, match="not an OPML"):
        parse_opml("<?xml version='1.0'?><rss><channel/></rss>")


def test_opml_rejects_malformed_xml() -> None:
    """Broken XML raises a clear error instead of a parser traceback."""
    with pytest.raises(ValueError, match="not valid XML"):
        parse_opml("<opml><body>")


def test_opml_rejects_an_entity_expansion_payload() -> None:
    """Billion-laughs style entities are refused by defusedxml."""
    payload = """<?xml version="1.0"?>
    <!DOCTYPE opml [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>
    <opml version="2.0"><body><outline text="&b;" xmlUrl="https://x.test/feed"/></body></opml>"""

    with pytest.raises(ValueError):
        parse_opml(payload)


def test_opml_action_outlines_are_ignored() -> None:
    """Non-outline elements inside body are skipped rather than crashing."""
    document = """<?xml version="1.0"?>
    <opml version="2.0"><body>
      <note>ignored</note>
      <outline text="Tech"><outline type="rss" text="A" xmlUrl="https://a.test/feed"/></outline>
    </body></opml>"""

    candidates = parse_opml(document)

    assert [(candidate.url, candidate.categories) for candidate in candidates] == [("https://a.test/feed", ("Tech",))]


def test_opml_outline_without_a_name_keeps_the_parent_category() -> None:
    """An unnamed nested folder does not erase the category above it."""
    document = """<?xml version="1.0"?>
    <opml version="2.0"><body>
      <outline text="Tech">
        <outline>
          <outline type="rss" text="A" xmlUrl="https://a.test/feed"/>
        </outline>
      </outline>
    </body></opml>"""

    candidates = parse_opml(document)

    assert candidates[0].categories == ("Tech",)
