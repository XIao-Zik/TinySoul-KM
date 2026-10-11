"""Obsidian vault adapter: frontmatter, wiki links, tags — best effort.

Parsing never fails fatally: unrecognized syntax stays in the body verbatim,
a malformed frontmatter downgrades the note to "no frontmatter" with a
warning. Only routine frontmatter/links/tags extraction is in scope (M1
acceptance); Dataview or plugin query blocks are preserved untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml

from ..failures import KnowledgeContractError
from ..storage.index import KnowledgeIndexEntry

_FM_PATTERN = re.compile(r"\A---[ \t]*\r?\n(.*?)\n---[ \t]*\r?\n?", re.DOTALL)
_WIKI_LINK = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
_INLINE_TAG = re.compile(r"(?<![\w/])#([A-Za-z\u4e00-\u9fff][\w/\u4e00-\u9fff-]*)")
_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_VAULT_SKIP_DIRS = frozenset({".obsidian", ".trash", ".git", ".tinysoul_knowledge"})


@dataclass(frozen=True)
class WikiLink:
    target: str
    embed: bool = False


@dataclass(frozen=True)
class ParsedNote:
    """Vault note split into user frontmatter (verbatim) and derived facts."""

    frontmatter_raw: str | None
    frontmatter: dict[str, object]
    body: str
    links: tuple[WikiLink, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def normalize_text(text: str) -> str:
    """Canonical import form: strip BOM, unify line endings, drop trailing spaces."""

    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split the leading YAML frontmatter block; returns (raw|None, body)."""

    match = _FM_PATTERN.match(text)
    if match is None:
        return None, text
    return match.group(1), text[match.end() :]


def parse_frontmatter(raw: str) -> dict[str, object]:
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise KnowledgeContractError(f"Frontmatter is not valid YAML: {exc}") from exc
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise KnowledgeContractError("Frontmatter must be a YAML mapping")
    return value


def parse_note(text: str) -> ParsedNote:
    normalized = normalize_text(text)
    raw, body = split_frontmatter(normalized)
    warnings: list[str] = []
    frontmatter: dict[str, object] = {}
    if raw is not None:
        try:
            frontmatter = parse_frontmatter(raw)
        except KnowledgeContractError as exc:
            warnings.append(str(exc))
            body = normalized
            raw = None
    return ParsedNote(
        frontmatter_raw=raw,
        frontmatter=frontmatter,
        body=body,
        links=extract_links(body),
        tags=extract_tags(frontmatter, body),
        warnings=tuple(warnings),
    )


def extract_links(body: str) -> tuple[WikiLink, ...]:
    """Extract ``[[link]]``/``[[path|alias]]``/``![[embed]]`` targets in order."""

    links: list[WikiLink] = []
    seen: set[tuple[str, bool]] = set()
    for embed_marker, target in _WIKI_LINK.findall(body):
        # Strip alias and any #heading anchor: identity is the note target.
        head = target.split("|", 1)[0].split("#", 1)[0].strip()
        if not head:
            continue
        # Backslashes are common in Windows-flavored paths inside wikilinks.
        normalized = PurePosixPath(head.replace("\\", "/")).as_posix()
        embed = embed_marker == "!"
        key = (normalized, embed)
        if key not in seen:
            seen.add(key)
            links.append(WikiLink(target=normalized, embed=embed))
    return tuple(links)


def extract_tags(frontmatter: dict[str, object], body: str) -> tuple[str, ...]:
    """Merge frontmatter ``tags`` and inline ``#tag`` occurrences, deduplicated."""

    tags: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        tag = value.strip().strip("#").casefold()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)

    raw_tags = frontmatter.get("tags")
    if isinstance(raw_tags, str):
        for item in raw_tags.replace("，", ",").split(","):
            add(item)
    elif isinstance(raw_tags, (list, tuple)):
        for item in raw_tags:
            if isinstance(item, str):
                add(item)
    elif isinstance(raw_tags, (int, float)):
        add(str(raw_tags))

    in_fence: str | None = None
    for line in body.splitlines():
        fence = _FENCE.match(line)
        if fence is not None:
            marker = fence.group(1)
            if in_fence is None:
                in_fence = marker[:3]
            elif marker.startswith(in_fence):
                in_fence = None
            continue
        if in_fence is not None:
            continue
        if _HEADING.match(line) is not None:
            # ATX heading lines (hash + space) are not tag sources.
            continue
        for match in _INLINE_TAG.finditer(line):
            add(match.group(1))
    return tuple(tags)


@dataclass(frozen=True)
class VaultFile:
    relative_path: str
    mtime: float
    size: int


def walk_vault(vault: Path) -> list[VaultFile]:
    """All Markdown files under the vault, hidden/plugin directories excluded."""

    files: list[VaultFile] = []
    stack = [vault]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise KnowledgeContractError(
                f"Cannot read vault directory {current}: {exc}"
            ) from exc
        for child in children:
            if child.is_symlink():
                continue
            if child.is_dir():
                if child.name not in _VAULT_SKIP_DIRS and not child.name.startswith(
                    "."
                ):
                    stack.append(child)
                continue
            if child.is_file() and child.suffix.casefold() == ".md":
                stat = child.stat()
                files.append(
                    VaultFile(
                        relative_path=child.relative_to(vault).as_posix(),
                        mtime=stat.st_mtime,
                        size=stat.st_size,
                    )
                )
    return files


def content_checksum(normalized_text: str) -> str:
    """Checksum the canonical form so line-ending or BOM drift is not a change."""

    return "sha256:" + sha256(
        normalize_text(normalized_text).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class StoreDocument:
    """One note ready to be written into the knowledge store."""

    relative_path: str
    km_id: str
    checksum: str
    title: str
    links: tuple[str, ...]
    tags: tuple[str, ...]
    text: str


def note_title(parsed: ParsedNote, relative_path: str) -> str:
    """Display title: frontmatter ``title`` first, else the file stem."""

    value = parsed.frontmatter.get("title")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return relative_path.removesuffix(".md").rsplit("/", 1)[-1]


def compose_note_document(
    parsed: ParsedNote,
    *,
    km_id: str,
    checksum: str,
    source_path: str,
    imported_at: datetime | None = None,
    km_source: str = "obsidian",
) -> str:
    """Merge ``km_*`` metadata into the note's frontmatter; body stays verbatim."""

    moment = (imported_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    metadata: dict[str, Any] = dict(parsed.frontmatter)
    metadata.update(
        {
            "km_id": km_id,
            "km_source": km_source,
            "km_source_path": source_path,
            "km_imported": moment,
            "km_checksum": checksum,
        }
    )
    if parsed.tags:
        metadata["km_tags"] = list(parsed.tags)
    if parsed.links:
        metadata["km_links"] = [link.target for link in parsed.links]
    rendered = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=10_000,
    )
    return f"---\n{rendered}---\n{parsed.body}"


def index_entry_for(
    document: StoreDocument,
    *,
    source: str,
    mtime: float,
    size: int,
    existing: KnowledgeIndexEntry | None = None,
) -> KnowledgeIndexEntry:
    return KnowledgeIndexEntry(
        path=document.relative_path,
        km_id=document.km_id,
        checksum=document.checksum,
        source=source,
        title=document.title,
        mtime=mtime,
        size=size,
        links=document.links,
        tags=document.tags,
        tombstoned=False,
    )
