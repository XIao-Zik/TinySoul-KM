"""Knowledge owner facade: store, derived index, and ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import time

import yaml

from pathlib import Path
from threading import RLock

from tinysoul.infra.references import ResourceTarget
from tinysoul.kernel.retrieval.contracts import (
    AttributeField,
    AttributeFilters,
    AttributeKind,
)

from .config import KnowledgeSettings
from .failures import KnowledgeContractError, KnowledgeIOError
from .ingest.obsidian import (
    ParsedNote,
    StoreDocument,
    VaultFile,
    compose_note_document,
    content_checksum,
    index_entry_for,
    normalize_text,
    note_title,
    parse_note,
    walk_vault,
)
from .storage.index import KnowledgeIndex, KnowledgeIndexEntry
from .storage.store import KnowledgeStore

KNOWLEDGE_SEARCH_FILTERS = AttributeFilters(
    (
        AttributeField("source"),
        AttributeField("tag", AttributeKind.TEXT_SET),
        AttributeField("updated_on", AttributeKind.DATE),
    )
)


@dataclass(frozen=True)
class IngestReport:
    """Outcome of one incremental import pass."""

    source: str
    added: tuple[str, ...]
    updated: tuple[str, ...]
    tombstoned: tuple[str, ...]
    unchanged: int
    failures: tuple[tuple[str, str], ...]
    dry_run: bool

    def summary(self) -> str:
        scope = " (dry run)" if self.dry_run else ""
        return (
            f"{self.source} import{scope}: "
            f"added={len(self.added)} updated={len(self.updated)} "
            f"tombstoned={len(self.tombstoned)} unchanged={self.unchanged} "
            f"failed={len(self.failures)}"
        )


class KnowledgeEngine:
    """Single assembly facade for Knowledge reads, writes, and retrieval (M2+)."""

    def __init__(
        self,
        *,
        settings: KnowledgeSettings,
        embedding: object | None = None,
    ) -> None:
        if not isinstance(settings, KnowledgeSettings):
            raise KnowledgeContractError("Knowledge settings are invalid")
        self._settings = settings
        self._store = KnowledgeStore(settings.root)
        self._index = KnowledgeIndex(settings.root)
        self.embedding = embedding
        self._lock = RLock()
        self._corpus_cache: dict[str, tuple[KnowledgeIndexEntry, str, tuple]] = {}
        self._corpus_cache_version = self._index.version
        self._backfill_imported_on()

    def _backfill_imported_on(self) -> None:
        """Entries predating the imported_on field derive it from their mtime."""

        stale = [
            entry
            for entry in self._index.all()
            if not entry.imported_on
        ]
        if not stale:
            return
        for entry in stale:
            from dataclasses import replace

            self._index.put(
                replace(
                    entry,
                    imported_on=datetime.fromtimestamp(
                        entry.mtime or 0
                    ).date().isoformat()
                    if entry.mtime
                    else datetime.now().date().isoformat(),
                )
            )
        self._index.save()

    @property
    def root(self) -> Path:
        return self._store.root

    @property
    def settings(self) -> KnowledgeSettings:
        return self._settings

    @property
    def store(self) -> KnowledgeStore:
        return self._store

    @property
    def index(self) -> KnowledgeIndex:
        return self._index

    def ingest_obsidian(
        self,
        vault: Path,
        *,
        dry_run: bool = False,
        full: bool = False,
    ) -> IngestReport:
        """Incrementally import a vault: add/update changed notes, tombstone vanished."""

        if not isinstance(vault, Path):
            raise KnowledgeContractError("Obsidian vault must be a path")
        if not vault.is_dir():
            raise KnowledgeContractError(f"Obsidian vault does not exist: {vault}")
        now = datetime.now(timezone.utc)
        added: list[str] = []
        updated: list[str] = []
        unchanged_paths: set[str] = set()
        failures: list[tuple[str, str]] = []
        pending: list[tuple[StoreDocument, VaultFile]] = []
        planned: list[tuple[StoreDocument, VaultFile]] = []

        try:
            files = walk_vault(vault)
        except KnowledgeContractError as exc:
            raise KnowledgeIOError(str(exc)) from exc

        for item in files:
            entry = self._index.get(item.relative_path)
            if (
                not full
                and entry is not None
                and not entry.tombstoned
                and entry.mtime == item.mtime
                and entry.size == item.size
            ):
                unchanged_paths.add(item.relative_path)
                continue
            try:
                raw = (vault / item.relative_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failures.append((item.relative_path, f"read failed: {exc}"))
                continue
            normalized = normalize_text(raw)
            checksum = content_checksum(normalized)
            if entry is not None and entry.checksum == checksum:
                unchanged_paths.add(item.relative_path)
                if not dry_run:
                    self._index.put(
                        KnowledgeIndexEntry(
                            path=entry.path,
                            km_id=entry.km_id,
                            checksum=entry.checksum,
                            source=entry.source,
                            title=entry.title,
                            imported_on=entry.imported_on,
                            mtime=item.mtime,
                            size=item.size,
                            links=entry.links,
                            tags=entry.tags,
                            tombstoned=False,
                        )
                    )
                continue
            document = self._compose_document(
                item, normalized, checksum, vault, now, failures
            )
            if document is None:
                continue
            if dry_run:
                planned.append((document, item))
            else:
                pending.append((document, item))

        tombstoned: list[str] = []
        for entry in self._index.live(source="obsidian"):
            if entry.path in unchanged_paths or any(
                document.relative_path == entry.path
                for document, _ in (*pending, *planned)
            ):
                continue
            tombstoned.append(entry.path)

        if dry_run:
            return IngestReport(
                source="obsidian",
                added=tuple(
                    sorted(
                        document.relative_path
                        for document, _ in planned
                        if self._is_new(document.relative_path)
                    )
                ),
                updated=tuple(
                    sorted(
                        document.relative_path
                        for document, _ in planned
                        if not self._is_new(document.relative_path)
                        and not self._was_tombstoned(document.relative_path)
                    )
                ),
                tombstoned=tuple(sorted(tombstoned)),
                unchanged=len(unchanged_paths),
                failures=tuple(failures),
                dry_run=True,
            )

        for document, item in pending:
            try:
                self._store.write_note(document.relative_path, document.text)
            except (KnowledgeContractError, KnowledgeIOError) as exc:
                failures.append((document.relative_path, f"store write failed: {exc}"))
                continue
            existing = self._index.get(document.relative_path)
            is_update = existing is not None and not existing.tombstoned
            if existing is not None and existing.tombstoned:
                self._index.revive(
                    document.relative_path,
                    checksum=document.checksum,
                    mtime=item.mtime,
                    size=item.size,
                )
            self._index.put(
                index_entry_for(
                    document,
                    source="obsidian",
                    mtime=item.mtime,
                    size=item.size,
                    imported_on=datetime.now().date().isoformat(),
                    existing=existing,
                )
            )
            if is_update:
                updated.append(document.relative_path)
            elif existing is not None:
                added.append(document.relative_path)
            else:
                added.append(document.relative_path)

        for path in tombstoned:
            entry = self._index.get(path)
            if entry is None:
                continue
            self._store.record_tombstone(
                path=path, km_id=entry.km_id, checksum=entry.checksum, reason="vanished"
            )
            self._index.mark_tombstoned(path)

        self._index.save()
        return IngestReport(
            source="obsidian",
            added=tuple(sorted(added)),
            updated=tuple(sorted(updated)),
            tombstoned=tuple(sorted(tombstoned)),
            unchanged=len(unchanged_paths),
            failures=tuple(failures),
            dry_run=False,
        )

    def ingest_chat(
        self,
        source: Path,
        *,
        platform: str = "deepseek",
        dry_run: bool = False,
    ) -> IngestReport:
        """Import a chat export file (JSON/Markdown/HTML) as knowledge entries."""

        from .ingest.chat_export import parse_chat_file, render_chat_markdown, split_session

        if not isinstance(source, Path):
            raise KnowledgeContractError("Chat export source must be a path")
        if not source.is_file():
            raise KnowledgeContractError(
                f"Chat export file does not exist: {source}"
            )
        now = datetime.now(timezone.utc)
        parsed = parse_chat_file(source, platform=platform)
        added: list[str] = []
        unchanged = 0
        failures: list[tuple[str, str]] = [
            (source.name, warning) for warning in parsed.warnings
        ]
        planned: list[tuple[str, StoreDocument]] = []
        for session in parsed.sessions:
            for chunk in split_session(session):
                relative = self._chat_store_path(chunk)
                # Checksum the canonical session content, not the store form:
                # km_imported changes every run and must not force re-imports.
                epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
                canonical = normalize_text(
                    render_chat_markdown(chunk, km_id="", imported_at=epoch)
                )
                checksum = content_checksum(canonical)
                entry = self._index.get(relative)
                if entry is not None and entry.checksum == checksum:
                    unchanged += 1
                    continue
                km_id = (
                    entry.km_id
                    if entry is not None and entry.km_id
                    else "c-" + sha256(relative.encode("utf-8")).hexdigest()[:12]
                )
                text = normalize_text(
                    render_chat_markdown(chunk, km_id=km_id, imported_at=now)
                )
                planned.append(
                    (
                        relative,
                        StoreDocument(
                            relative_path=relative,
                            km_id=km_id,
                            checksum=checksum,
                            title=chunk.title,
                            links=(),
                            tags=(f"platform/{chunk.platform}",),
                            text=text,
                        ),
                    )
                )
        if dry_run:
            return IngestReport(
                source=f"chat/{platform}",
                added=tuple(sorted(path for path, _ in planned)),
                updated=(),
                tombstoned=(),
                unchanged=unchanged,
                failures=tuple(failures),
                dry_run=True,
            )
        for relative, document in planned:
            try:
                self._store.write_chat(relative, document.text)
            except (KnowledgeContractError, KnowledgeIOError) as exc:
                failures.append((relative, f"store write failed: {exc}"))
                continue
            self._index.put(
                index_entry_for(
                    document,
                    source="chat",
                    mtime=now.timestamp(),
                    size=len(document.text),
                    imported_on=datetime.now().date().isoformat(),
                )
            )
            added.append(relative)
        self._index.save()
        return IngestReport(
            source=f"chat/{platform}",
            added=tuple(sorted(added)),
            updated=(),
            tombstoned=(),
            unchanged=unchanged,
            failures=tuple(failures),
            dry_run=False,
        )

    def _chat_store_path(self, session) -> str:
        from .ingest.chat_export import chat_slug

        day = session.day or datetime.now(timezone.utc).date()
        slug = chat_slug(session.title)
        return f"{day:%Y-%m}/{session.platform}/{slug}.md"

    def stats(self) -> dict[str, int]:
        entries = self._index.all()
        return {
            "documents": len(entries),
            "live": sum(1 for entry in entries if not entry.tombstoned),
            "tombstoned": sum(1 for entry in entries if entry.tombstoned),
        }

    # -- reference identity (M2 retrieval) ---------------------------------

    @staticmethod
    def ref_for(km_id: str) -> str:
        return f"km:{km_id}"

    def canonical_reference(
        self, resource: str, fragment: str = "", source_day: date | None = None
    ) -> ResourceTarget:
        """Resolve one ``km:`` reference to its live store identity.

        Accepts the stable identity form ``km:<km_id>`` and, for convenience,
        a store-relative or vault-relative Markdown path.
        """

        _, _, value = resource.partition(":")
        value = value.strip()
        if not value:
            raise KnowledgeContractError(
                f"Knowledge reference is empty: {resource!r}"
            )
        entry = self._find_by_km_id(value) or self._find_by_path(value)
        if entry is None or entry.tombstoned:
            raise KnowledgeContractError(
                f"Knowledge reference does not resolve to a live document: {resource!r}"
            )
        return ResourceTarget(self.ref_for(entry.km_id), fragment)

    def resolve_link_target(self, target: str) -> tuple[str, ...]:
        """Resolve one ``km_links`` target to zero or more live document ids."""

        key = target.strip().casefold()
        if not key:
            return ()
        stem = key.removesuffix(".md").rsplit("/", 1)[-1]
        matches: list[str] = []
        for entry in self._index.live():
            if entry.checksum and self._matches_target(entry, key, stem):
                matches.append(entry.km_id)
        return tuple(matches)

    def corpus_candidates(self):
        """Materialized (entry, text, content_units) per live document.

        Built once per index version and reused across queries so that
        per-query work stays proportional to the result set, not the store.
        """

        if self._corpus_cache_version != self._index.version:
            self._corpus_cache.clear()
            self._corpus_cache_version = self._index.version
        for entry in self._index.live():
            cached = self._corpus_cache.get(entry.path)
            if cached is not None and cached[0] == entry:
                yield cached
                continue
            from tinysoul.kernel.retrieval.disclosure import content_units
            from .failures import KnowledgeIOError

            try:
                text = self._store.read_document(entry.path, source=entry.source)
            except KnowledgeIOError:
                # Stale index entry whose file is gone; the next ingest
                # reconciles it. Skip instead of failing the whole query.
                continue
            units = content_units(self.ref_for(entry.km_id), text)
            value = (entry, text, units)
            self._corpus_cache[entry.path] = value
            yield value

    # -- daily reflection support (M4) -------------------------------------

    def documents_imported_on(self, day: str) -> tuple[KnowledgeIndexEntry, ...]:
        """Live entries first imported on the given YYYY-MM-DD."""

        return tuple(
            entry for entry in self._index.live() if entry.imported_on == day
        )

    def document_excerpt(self, entry: KnowledgeIndexEntry, max_chars: int = 1200) -> str:
        text = self._store.read_document(entry.path, source=entry.source)
        if len(text) > max_chars:
            return text[:max_chars] + "…"
        return text

    def write_cards(
        self,
        day: str,
        cards: tuple[dict[str, object], ...],
        *,
        source_titles: dict[str, str] | None = None,
    ) -> str:
        """Append validated knowledge cards to ``cards/<day>.md``; returns ref."""

        if not cards:
            raise KnowledgeContractError("Card write requires at least one card")
        relative = f"{day}.md"
        titles = source_titles or {}
        card_km_id = "card-" + sha256(relative.encode("utf-8")).hexdigest()[:12]
        sections: list[str] = []
        for card in cards:
            refs = tuple(str(ref) for ref in card.get("source_refs", ()))
            lines = [
                "## 卡片",
                "",
                f"**Q: {card.get('question', '')}**",
                "",
                str(card.get("answer", "")),
                "",
                f"- 标签: {', '.join(str(t) for t in card.get('concept_tags', ()))}",
                f"- 来源: {', '.join(refs)}",
                f"- 置信度: {card.get('confidence', 'medium')}",
                "",
            ]
            sections.append("\n".join(lines))
        body = "\n".join(sections)
        links = tuple(
            dict.fromkeys(
                title
                for card in cards
                for ref in card.get("source_refs", ())
                for title in (titles.get(str(ref).partition(":")[2], ""),)
                if title
            )
        )
        existing_path = self.store.cards_root.joinpath(relative)
        if existing_path.is_file():
            existing = self._store.read_document(relative, source="card")
            text = existing.rstrip("\n") + "\n\n" + body
        else:
            frontmatter: dict[str, object] = {
                "km_source": "card",
                "km_id": card_km_id,
                "km_card_date": day,
                "km_imported": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            if links:
                frontmatter["km_links"] = list(links)
            text = (
                "---\n"
                + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
                + "---\n\n"
                + body
            )
        self._store.write_card(relative, text)
        existing_entry = self._index.get(relative)
        if existing_entry is not None:
            card_km_id = existing_entry.km_id or card_km_id
        self._index.put(
            KnowledgeIndexEntry(
                path=relative,
                km_id=card_km_id,
                checksum=content_checksum(text),
                source="card",
                title=f"知识卡片 {day}",
                imported_on=datetime.now().date().isoformat(),
                mtime=datetime.now(timezone.utc).timestamp(),
                size=len(text),
                links=links,
                tags=("card",),
                tombstoned=False,
            )
        )
        self._index.save()
        return self.ref_for(card_km_id)

    def _matches_target(self, entry: KnowledgeIndexEntry, key: str, stem: str) -> bool:
        if entry.path.casefold() == key or entry.path.removesuffix(".md").casefold() == key:
            return True
        if entry.path.removesuffix(".md").rsplit("/", 1)[-1].casefold() == stem:
            return True
        if entry.title and entry.title.casefold() == key:
            return True
        return False

    def _find_by_km_id(self, km_id: str) -> KnowledgeIndexEntry | None:
        for entry in self._index.all():
            if entry.km_id == km_id:
                return entry
        return None

    def _find_by_path(self, value: str) -> KnowledgeIndexEntry | None:
        candidates = {
            value,
            value.removesuffix(".md") + ".md",
            f"notes/{value}",
            f"notes/{value.removesuffix('.md')}.md",
        }
        for entry in self._index.all():
            if entry.path in candidates:
                return entry
        return None

    def _compose_document(
        self,
        item: VaultFile,
        normalized: str,
        checksum: str,
        vault: Path,
        now: datetime,
        failures: list[tuple[str, str]],
    ) -> StoreDocument | None:
        try:
            parsed = parse_note(normalized)
        except KnowledgeContractError as exc:
            failures.append((item.relative_path, f"parse failed: {exc}"))
            return None
        for warning in parsed.warnings:
            failures.append((item.relative_path, f"warning: {warning}"))
        km_id = self._resolve_km_id(item.relative_path, parsed, checksum)
        source_path = (vault / item.relative_path).resolve().as_posix()
        text = compose_note_document(
            parsed,
            km_id=km_id,
            checksum=checksum,
            source_path=source_path,
            imported_at=now,
        )
        return StoreDocument(
            relative_path=item.relative_path,
            km_id=km_id,
            checksum=checksum,
            title=note_title(parsed, item.relative_path),
            links=tuple(link.target for link in parsed.links),
            tags=parsed.tags,
            text=text,
        )

    def _resolve_km_id(
        self, relative_path: str, parsed: ParsedNote, checksum: str
    ) -> str:
        entry = self._index.get(relative_path)
        if entry is not None and entry.km_id:
            return entry.km_id
        explicit = parsed.frontmatter.get("km_id")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        revived = self._index.km_id_by_checksum(checksum)
        if revived:
            return revived
        return "k-" + sha256(relative_path.encode("utf-8")).hexdigest()[:12]

    def _is_new(self, path: str) -> bool:
        entry = self._index.get(path)
        return entry is None or entry.tombstoned

    def _was_tombstoned(self, path: str) -> bool:
        entry = self._index.get(path)
        return entry is not None and entry.tombstoned
