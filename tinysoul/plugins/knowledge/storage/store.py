"""Markdown-native filesystem store for external knowledge documents.

Layout under the configured knowledge root::

    notes/<relative path>.md    imported vault notes (structure mirrored)
    chats/<YYYY-MM>/<...>.md    chat exports (M3)
    cards/<YYYY-MM-DD>.md       daily knowledge cards (M4)
    tombstones.jsonl            append-only delete/rename audit trail
    .tinysoul_knowledge/        derived index and embedding cache

Tombstones never hard-delete store files; the audit line records why a source
path disappeared. Everything under ``.tinysoul_knowledge`` is derived state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tinysoul.infra.filesystem import atomic_write_text

from ..failures import KnowledgeContractError, KnowledgeIOError, KnowledgeInvariantError

_TOMBSTONE_SCHEMA = 1


class KnowledgeStore:
    """Read and atomically replace owner-owned knowledge Markdown files."""

    def __init__(self, root: Path) -> None:
        if not isinstance(root, Path):
            raise KnowledgeContractError("Knowledge store root must be a path")
        self._root = root
        self._validate_root()

    @property
    def root(self) -> Path:
        return self._root

    @property
    def notes_root(self) -> Path:
        return self._root / "notes"

    @property
    def chats_root(self) -> Path:
        return self._root / "chats"

    @property
    def cards_root(self) -> Path:
        return self._root / "cards"

    @property
    def internal_root(self) -> Path:
        return self._root / ".tinysoul_knowledge"

    def note_path(self, relative_path: str) -> Path:
        """Map a forward-slash store-relative note path to a safe target."""

        if not relative_path or relative_path.startswith("/"):
            raise KnowledgeContractError(
                f"Knowledge note path is invalid: {relative_path!r}"
            )
        parts = relative_path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise KnowledgeContractError(
                f"Knowledge note path is invalid: {relative_path!r}"
            )
        if not relative_path.lower().endswith(".md"):
            raise KnowledgeContractError(
                f"Knowledge notes must be Markdown: {relative_path!r}"
            )
        path = self.notes_root.joinpath(*parts)
        resolved = path.absolute()
        notes_root = self.notes_root.absolute()
        if notes_root not in resolved.parents:
            raise KnowledgeInvariantError(
                f"Knowledge note path escapes the store: {relative_path!r}"
            )
        return path

    def read_note(self, relative_path: str) -> str:
        path = self.note_path(relative_path)
        if not path.is_file():
            raise KnowledgeIOError(f"Knowledge note does not exist: {relative_path}")
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise KnowledgeIOError(
                f"Failed to read knowledge note {relative_path}: {exc}"
            ) from exc

    def write_note(self, relative_path: str, text: str) -> Path:
        path = self.note_path(relative_path)
        try:
            atomic_write_text(path, text)
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to write knowledge note {relative_path}: {exc}"
            ) from exc
        return path

    def delete_note(self, relative_path: str) -> None:
        """Remove a store note file; only callers that hard-delete may use this."""

        path = self.note_path(relative_path)
        try:
            path.unlink()
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to delete knowledge note {relative_path}: {exc}"
            ) from exc

    def record_tombstone(
        self, *, path: str, km_id: str, checksum: str, reason: str
    ) -> None:
        import json

        record = {
            "schema": _TOMBSTONE_SCHEMA,
            "path": path,
            "km_id": km_id,
            "checksum": checksum,
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        target = self._root / "tombstones.jsonl"
        try:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to append knowledge tombstone: {exc}"
            ) from exc

    def _validate_root(self) -> None:
        if self._root.is_symlink():
            raise KnowledgeInvariantError("Knowledge root cannot be a symlink")
        if self._root.exists() and not self._root.is_dir():
            raise KnowledgeInvariantError("Knowledge root must be a directory")
