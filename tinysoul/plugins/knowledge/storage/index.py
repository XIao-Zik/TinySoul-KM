"""Incremental path index over the knowledge store (derived, rebuildable state).

The index maps store-relative note paths to import facts: stable identity,
normalized-content checksum, observed mtime/size, extracted links/tags, and a
tombstone flag. Deleted notes keep their store file; the flag is what later
retrieval stages must honor, so a tombstone is reversible by re-import.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Any

from tinysoul.infra.filesystem import atomic_write_text

from ..failures import KnowledgeIOError, KnowledgeInvariantError

_INDEX_SCHEMA = 1


@dataclass(frozen=True)
class KnowledgeIndexEntry:
    path: str
    km_id: str
    checksum: str
    source: str
    title: str = ""
    imported_on: str = ""
    mtime: float = 0.0
    size: int = 0
    links: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    tombstoned: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "km_id": self.km_id,
            "checksum": self.checksum,
            "source": self.source,
            "title": self.title,
            "imported_on": self.imported_on,
            "mtime": self.mtime,
            "size": self.size,
            "links": list(self.links),
            "tags": list(self.tags),
            "tombstoned": self.tombstoned,
        }


class KnowledgeIndex:
    """Owner-scoped path index persisted at ``<root>/.tinysoul_knowledge/index.json``."""

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise KnowledgeInvariantError("Knowledge index root must be a path")
        self._root = root
        self._path = root / ".tinysoul_knowledge" / "index.json"
        self._lock = RLock()
        self._entries: dict[str, KnowledgeIndexEntry] = {}
        self._version = 0
        self.load()

    @property
    def version(self) -> int:
        """Bumped on every persisted mutation; lets owners invalidate caches."""

        return self._version

    @property
    def path(self) -> Path:
        return self._path

    def get(self, path: str) -> KnowledgeIndexEntry | None:
        with self._lock:
            return self._entries.get(path)

    def all(self) -> tuple[KnowledgeIndexEntry, ...]:
        with self._lock:
            return tuple(self._entries.values())

    def live(self, *, source: str | None = None) -> tuple[KnowledgeIndexEntry, ...]:
        with self._lock:
            return tuple(
                entry
                for entry in self._entries.values()
                if not entry.tombstoned
                and (source is None or entry.source == source)
            )

    def put(self, entry: KnowledgeIndexEntry) -> None:
        with self._lock:
            self._entries[entry.path] = entry
            self._version += 1

    def mark_tombstoned(self, path: str) -> KnowledgeIndexEntry | None:
        with self._lock:
            entry = self._entries.get(path)
            if entry is None or entry.tombstoned:
                return entry
            updated = replace(entry, tombstoned=True)
            self._entries[path] = updated
            self._version += 1
            return updated

    def revive(self, path: str, *, checksum: str, mtime: float, size: int) -> bool:
        """Clear a tombstone on re-import; returns False when no entry exists."""

        with self._lock:
            entry = self._entries.get(path)
            if entry is None or not entry.tombstoned:
                return False
            self._entries[path] = replace(
                entry, tombstoned=False, checksum=checksum, mtime=mtime, size=size
            )
            return True

    def km_id_by_checksum(self, checksum: str) -> str | None:
        """Stable-identity revival: the newest entry with this content checksum."""

        with self._lock:
            matches = [
                entry
                for entry in self._entries.values()
                if entry.checksum == checksum and entry.km_id
            ]
            if not matches:
                return None
            return max(matches, key=lambda item: item.path).km_id

    def get_by_km_id(self, km_id: str) -> KnowledgeIndexEntry | None:
        with self._lock:
            for entry in self._entries.values():
                if entry.km_id == km_id and not entry.tombstoned:
                    return entry
            return None

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            import json

            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise KnowledgeIOError(
                f"Failed to read knowledge index {self._path}: {exc}"
            ) from exc
        if not isinstance(payload, dict) or payload.get("schema") != _INDEX_SCHEMA:
            raise KnowledgeInvariantError(
                "Knowledge index schema is unknown; rebuild the knowledge store"
            )
        entries = payload.get("entries")
        if not isinstance(entries, dict):
            raise KnowledgeInvariantError("Knowledge index entries are invalid")
        parsed: dict[str, KnowledgeIndexEntry] = {}
        for path, raw in entries.items():
            if not isinstance(path, str) or not isinstance(raw, dict):
                raise KnowledgeInvariantError("Knowledge index entry is invalid")
            parsed[path] = KnowledgeIndexEntry(
                path=path,
                km_id=str(raw.get("km_id", "")),
                checksum=str(raw.get("checksum", "")),
                source=str(raw.get("source", "obsidian")),
                title=str(raw.get("title", "")),
                imported_on=str(raw.get("imported_on", "")),
                mtime=float(raw.get("mtime", 0.0)),
                size=int(raw.get("size", 0)),
                links=tuple(str(item) for item in raw.get("links", ())),
                tags=tuple(str(item) for item in raw.get("tags", ())),
                tombstoned=bool(raw.get("tombstoned", False)),
            )
        with self._lock:
            self._entries = parsed

    def save(self) -> None:
        with self._lock:
            self._version += 1
            payload = {
                "schema": _INDEX_SCHEMA,
                "entries": {
                    path: entry.to_json() for path, entry in self._entries.items()
                },
            }
        import json

        try:
            atomic_write_text(
                self._path, json.dumps(payload, ensure_ascii=False, indent=1)
            )
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to write knowledge index {self._path}: {exc}"
            ) from exc
