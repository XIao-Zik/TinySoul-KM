"""Knowledge owner facade: store, derived index, and ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import os
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
    parse_frontmatter,
    parse_note,
    split_frontmatter,
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


@dataclass(frozen=True)
class CardWriteReport:
    """Outcome of one daily card write: reflection cycles re-call the action,
    so already-present (question, source_refs) pairs are skipped, not appended."""

    ref: str
    written: int
    duplicates: int


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

    @property
    def archive_root(self) -> Path:
        """Daily archive root; a relative setting hangs off the project root."""

        configured = self._settings.archive.archive_root
        if configured.is_absolute():
            return configured
        return self._settings.root.parent / configured

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

    def ingest_workspace_archive(self) -> IngestReport:
        """Ingest archived workspace Markdown into the knowledge store.

        Scans ``<archive_root>/<archive>/workspace/**/*.md``. The archive day
        is the archived BUSINESS day — ``transition.json``'s ``from_day``
        when present, else the leading 8 digits of the directory name; when
        neither is parsable the run falls back to today with a warning. Store
        path: ``workspace/<archive day>/<original relative path>`` with
        ``km_source=workspace`` and ``imported_on=<archive day>`` so the
        target day's reflection treats archived files as same-day candidates.
        Idempotent: a store entry whose checksum still matches the archive
        content is skipped without writing.
        """

        archive_root = self.archive_root
        added: list[str] = []
        updated: list[str] = []
        unchanged = 0
        failures: list[tuple[str, str]] = []
        changed = False
        if archive_root.is_dir():
            now = datetime.now(timezone.utc)
            for archive_dir in sorted(archive_root.iterdir()):
                if not archive_dir.is_dir() or archive_dir.name.startswith("."):
                    continue
                day = self._archive_day(archive_dir)
                if day is None:
                    day = now.date()
                    failures.append(
                        (
                            archive_dir.name,
                            "warning: archive day is unparsable; "
                            "ingesting under today",
                        )
                    )
                workspace_dir = archive_dir / "workspace"
                if not workspace_dir.is_dir():
                    continue
                try:
                    files = walk_vault(workspace_dir)
                except KnowledgeContractError as exc:
                    failures.append((archive_dir.name, f"warning: {exc}"))
                    continue
                for item in files:
                    store_relative = f"{day.isoformat()}/{item.relative_path}"
                    try:
                        raw = (workspace_dir / item.relative_path).read_text(
                            encoding="utf-8"
                        )
                    except (OSError, UnicodeDecodeError) as exc:
                        failures.append((store_relative, f"read failed: {exc}"))
                        continue
                    normalized = normalize_text(raw)
                    checksum = content_checksum(normalized)
                    existing = self._index.get(store_relative)
                    if (
                        existing is not None
                        and not existing.tombstoned
                        and existing.checksum == checksum
                    ):
                        unchanged += 1
                        continue
                    try:
                        parsed = parse_note(normalized)
                    except KnowledgeContractError as exc:
                        failures.append((store_relative, f"parse failed: {exc}"))
                        continue
                    for warning in parsed.warnings:
                        failures.append((store_relative, f"warning: {warning}"))
                    km_id = self._resolve_km_id(store_relative, parsed, checksum)
                    document = StoreDocument(
                        relative_path=store_relative,
                        km_id=km_id,
                        checksum=checksum,
                        title=note_title(parsed, item.relative_path),
                        links=tuple(link.target for link in parsed.links),
                        tags=parsed.tags,
                        text=compose_note_document(
                            parsed,
                            km_id=km_id,
                            checksum=checksum,
                            source_path=(
                                workspace_dir / item.relative_path
                            ).resolve().as_posix(),
                            imported_at=now,
                            km_source="workspace",
                        ),
                    )
                    try:
                        self._store.write_workspace(store_relative, document.text)
                    except (KnowledgeContractError, KnowledgeIOError) as exc:
                        failures.append(
                            (store_relative, f"store write failed: {exc}")
                        )
                        continue
                    self._index.put(
                        index_entry_for(
                            document,
                            source="workspace",
                            mtime=item.mtime,
                            size=item.size,
                            imported_on=day.isoformat(),
                        )
                    )
                    changed = True
                    if existing is not None and not existing.tombstoned:
                        updated.append(store_relative)
                    else:
                        added.append(store_relative)
        if changed:
            self._index.save()
        return IngestReport(
            source="workspace",
            added=tuple(sorted(added)),
            updated=tuple(sorted(updated)),
            tombstoned=(),
            unchanged=unchanged,
            failures=tuple(failures),
            dry_run=False,
        )

    def cleanup_expired_archives(self) -> dict[str, int]:
        """Delete expired, already-ingested workspace files from daily archives.

        Only the ``workspace/`` subtree of expired archive days is touched:
        session and memory snapshots are never modified. A file whose checksum
        is not live in the knowledge store was never ingested and is kept.
        ``retention_days <= 0`` disables cleanup entirely. Empty directories
        left behind inside ``workspace/`` are pruned; the archive directory
        itself is removed only when nothing else remains in it.
        """

        counts = {"deleted": 0, "kept_uningested": 0}
        retention = self._settings.archive.retention_days
        if retention <= 0:
            counts["disabled"] = 1
            return counts
        archive_root = self.archive_root
        if not archive_root.is_dir():
            return counts
        today = datetime.now().date()
        live_checksums = {entry.checksum for entry in self._index.live()}
        for archive_dir in sorted(archive_root.iterdir()):
            if not archive_dir.is_dir() or archive_dir.name.startswith("."):
                continue
            day = self._archive_day(archive_dir)
            if day is None or (today - day).days <= retention:
                continue
            workspace_dir = archive_dir / "workspace"
            if not workspace_dir.is_dir():
                continue
            try:
                files = walk_vault(workspace_dir)
            except KnowledgeContractError:
                continue
            removed_any = False
            for item in files:
                path = workspace_dir / item.relative_path
                try:
                    raw = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    counts["kept_uningested"] += 1
                    continue
                if content_checksum(normalize_text(raw)) not in live_checksums:
                    counts["kept_uningested"] += 1
                    continue
                try:
                    path.unlink()
                except OSError:
                    continue
                counts["deleted"] += 1
                removed_any = True
            if removed_any:
                self._prune_empty_dirs(workspace_dir)
                try:
                    workspace_dir.rmdir()
                except OSError:
                    pass
                # Succeeds only when session/memory snapshots are gone too;
                # their presence keeps the archive directory alive.
                try:
                    archive_dir.rmdir()
                except OSError:
                    pass
        return counts

    @staticmethod
    def _prune_empty_dirs(root: Path) -> None:
        for current, _dirnames, _filenames in os.walk(root, topdown=False):
            path = Path(current)
            if path == root:
                continue
            try:
                path.rmdir()
            except OSError:
                pass

    def _archive_day(self, archive_dir: Path) -> date | None:
        """Business day whose workspace the archive directory holds.

        ``transition.json``'s ``from_day`` is authoritative: the directory
        name carries the transition-execution timestamp, which is the day
        AFTER the archived business day for the 00:15 flow. The leading 8
        digits of the directory name are the fallback for archives without a
        parsable transition record.
        """

        import json

        try:
            raw = json.loads(
                (archive_dir / "transition.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            raw = None
        if isinstance(raw, dict):
            from_day = raw.get("from_day")
            if isinstance(from_day, str) and from_day:
                try:
                    return date.fromisoformat(from_day)
                except ValueError:
                    pass
        head = archive_dir.name[:8]
        if head.isdigit():
            try:
                return datetime.strptime(head, "%Y%m%d").date()
            except ValueError:
                return None
        return None

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

    def annotate_document(
        self,
        km_id: str,
        *,
        km_type: str,
        km_topics: tuple[str, ...],
        km_summary: str,
    ) -> bool:
        """Write reflection-time LLM annotations into a live document's frontmatter.

        The store text changes but the index checksum does not: annotations are
        derived metadata, so a later re-ingest of the unchanged source stays
        idempotent and never drops them. Returns False for unknown references
        and unreadable store documents; annotation is best effort (D-1).
        """

        entry = self._index.get_by_km_id(km_id)
        if entry is None:
            return False
        try:
            text = self._store.read_document(entry.path, source=entry.source)
            raw, body = split_frontmatter(text)
            frontmatter = parse_frontmatter(raw) if raw is not None else {}
            frontmatter["km_type"] = km_type
            frontmatter["km_topics"] = list(km_topics)
            frontmatter["km_summary"] = km_summary
            rendered = yaml.safe_dump(
                frontmatter,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
                width=10_000,
            )
            self._store.write_document(
                entry.path, f"---\n{rendered}---\n{body}", source=entry.source
            )
        except (KnowledgeContractError, KnowledgeIOError):
            return False
        # Re-put the unchanged entry to bump the index version so cached
        # corpus text (read from the store) refreshes.
        self._index.put(entry)
        self._index.save()
        return True

    def write_cards(
        self,
        day: str,
        cards: tuple[dict[str, object], ...],
        *,
        source_titles: dict[str, str] | None = None,
    ) -> CardWriteReport:
        """Append validated knowledge cards to ``cards/<day>.md``.

        The reflection turn may invoke card generation several times per turn
        and re-runs across restarts; a card whose (question, source_refs) pair
        is already present in the day's document is skipped instead of being
        appended again. Returns the stable card ref plus write counts.
        """

        if not cards:
            raise KnowledgeContractError("Card write requires at least one card")
        relative = f"{day}.md"
        titles = source_titles or {}
        card_km_id = "card-" + sha256(relative.encode("utf-8")).hexdigest()[:12]
        existing_path = self.store.cards_root.joinpath(relative)
        existing_text: str | None = None
        if existing_path.is_file():
            existing_text = self._store.read_document(relative, source="card")
        seen = self._existing_card_keys(existing_text) if existing_text else set()
        fresh: list[dict[str, object]] = []
        duplicates = 0
        for card in cards:
            key = self._card_key(card)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            fresh.append(card)
        existing_entry = self._index.get(relative)
        if existing_entry is not None and existing_entry.km_id:
            card_km_id = existing_entry.km_id
        ref = self.ref_for(card_km_id)
        if not fresh:
            return CardWriteReport(ref=ref, written=0, duplicates=duplicates)
        sections: list[str] = []
        for card in fresh:
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
                for card in fresh
                for ref in card.get("source_refs", ())
                for title in (titles.get(str(ref).partition(":")[2], ""),)
                if title
            )
        )
        if existing_text is not None:
            text = existing_text.rstrip("\n") + "\n\n" + body
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
        return CardWriteReport(ref=ref, written=len(fresh), duplicates=duplicates)

    @staticmethod
    def _card_key(card: dict[str, object]) -> tuple[str, tuple[str, ...]]:
        question = str(card.get("question", "")).strip()
        refs = tuple(sorted(str(ref) for ref in card.get("source_refs", ())))
        return question, refs

    @staticmethod
    def _existing_card_keys(text: str) -> set[tuple[str, tuple[str, ...]]]:
        """(question, source_refs) pairs already stored in a card document."""

        keys: set[tuple[str, tuple[str, ...]]] = set()
        for section in text.split("## 卡片")[1:]:
            question = ""
            refs: list[str] = []
            for line in section.splitlines():
                stripped = line.strip()
                if question == "" and stripped.startswith("**Q:") and stripped.endswith("**"):
                    question = stripped[4:-2].strip()
                elif stripped.startswith("- 来源:"):
                    value = stripped.split(":", 1)[1]
                    refs.extend(item.strip() for item in value.split(",") if item.strip())
            if question:
                keys.add((question, tuple(sorted(refs))))
        return keys

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
