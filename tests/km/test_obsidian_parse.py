"""Obsidian adapter parsing tests: frontmatter, links, tags, normalization."""

from __future__ import annotations

import pytest

from tinysoul.plugins.knowledge.ingest.obsidian import (
    extract_links,
    extract_tags,
    normalize_text,
    parse_note,
)
from tinysoul.plugins.knowledge.ingest.obsidian import (
    compose_note_document,
    content_checksum,
)


def test_normalize_text_strips_bom_and_unifies_newlines() -> None:
    assert normalize_text("\ufeffa\r\nb\rc") == "a\nb\nc"


def test_parse_note_with_frontmatter_and_links_and_tags() -> None:
    text = (
        "---\n"
        "title: Transformer notes\ntags: [ml, transformer]\n"
        "---\n"
        "See [[Attention]] and [[subdir/KV cache|kv]] and ![[diagram.png]].\n"
        "#ml #deep-learning\n"
    )
    parsed = parse_note(text)
    assert parsed.frontmatter["title"] == "Transformer notes"
    assert parsed.body.startswith("See [[Attention]]")
    assert [link.target for link in parsed.links] == [
        "Attention",
        "subdir/KV cache",
        "diagram.png",
    ]
    assert [link.embed for link in parsed.links] == [False, False, True]
    # tags and inline tags merged, casefolded, deduplicated
    assert parsed.tags == ("ml", "transformer", "deep-learning")
    assert parsed.warnings == ()


def test_parse_note_malformed_frontmatter_degrades_with_warning() -> None:
    text = "---\ntitle: [unclosed\n---\nbody stays verbatim\n"
    parsed = parse_note(text)
    assert parsed.frontmatter == {}
    assert parsed.frontmatter_raw is None
    assert parsed.body == text
    assert parsed.warnings and "YAML" in parsed.warnings[0]


def test_parse_note_without_frontmatter() -> None:
    parsed = parse_note("plain body with [[link]]\n")
    assert parsed.frontmatter == {}
    assert parsed.body == "plain body with [[link]]\n"
    assert [link.target for link in parsed.links] == ["link"]


def test_extract_links_handles_alias_heading_and_backslash() -> None:
    body = "[[Note#Section|alias]] [[a\\b]] [[#^block]] [[|empty]]"
    targets = [link.target for link in extract_links(body)]
    assert targets == ["Note", "a/b"]


def test_extract_tags_skips_headings_and_code_fences() -> None:
    body = "# Heading\ntext #realtag\n```\n#notag\n```\n~~~\n#alsonotag\n~~~"
    tags = extract_tags({}, body)
    assert tags == ("realtag",)


def test_extract_tags_frontmatter_string_and_chinese() -> None:
    assert extract_tags({"tags": "ml, nlp"}, "") == ("ml", "nlp")
    assert extract_tags({}, "中文 #机器学习 标签") == ("机器学习",)


def test_content_checksum_stable_across_line_endings() -> None:
    assert content_checksum("a\nb") == content_checksum("a\r\nb")
    assert content_checksum("a\nb") != content_checksum("a\nb ")


def test_compose_note_document_keeps_body_verbatim_and_merges_frontmatter() -> None:
    text = (
        "---\n"
        "title: My note\ntags: [a]\n"
        "---\n"
        "body line 1\n\n- item [[other]]\n"
    )
    parsed = parse_note(text)
    merged = compose_note_document(
        parsed,
        km_id="k-test",
        checksum=content_checksum("x"),
        source_path="D:/Vault/note.md",
    )
    assert merged.endswith("body line 1\n\n- item [[other]]\n")
    assert "km_id: k-test" in merged
    assert "km_source: obsidian" in merged
    assert "km_source_path: D:/Vault/note.md" in merged
    assert "title: My note" in merged
    # re-parsing the composed document round-trips the derived facts
    reparsed = parse_note(merged)
    assert reparsed.frontmatter["km_id"] == "k-test"
    assert reparsed.frontmatter["title"] == "My note"
    assert [link.target for link in reparsed.links] == ["other"]


@pytest.mark.parametrize(
    "frontmatter,tags",
    [
        ("tags: ml\n", ("ml",)),
        ("tags: [a, b]\n", ("a", "b")),
    ],
)
def test_frontmatter_tag_shapes(frontmatter: str, tags: tuple[str, ...]) -> None:
    parsed = parse_note(f"---\n{frontmatter}---\nbody")
    assert parsed.tags == tags
