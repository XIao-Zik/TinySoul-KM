"""Knowledge owner facade: store, derived index, and ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock

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
    parse_note,
    walk_vault,
)
from .storage.index import KnowledgeIndex, KnowledgeIndexEntry
from .storage.store import KnowledgeStore


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

    def __init__(self, *, settings: KnowledgeSettings) -> None:
        if not isinstance(settings, KnowledgeSettings):
            raise KnowledgeContractError("Knowledge settings are invalid")
        self._settings = settings
        self._store = KnowledgeStore(settings.root)
        self._index = KnowledgeIndex(settings.root)
        self._lock = RLock()

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

    def stats(self) -> dict[str, int]:
        entries = self._index.all()
        return {
            "documents": len(entries),
            "live": sum(1 for entry in entries if not entry.tombstoned),
            "tombstoned": sum(1 for entry in entries if entry.tombstoned),
        }

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
