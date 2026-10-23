"""Markdown-native filesystem store for external knowledge documents.

Layout under the configured knowledge root::

    notes/<relative path>.md    imported vault notes (structure mirrored)
    chats/<YYYY-MM>/<...>.md    chat exports (M3)
    cards/<YYYY-MM-DD>.md       daily knowledge cards (M4)
    workspace/<YYYY-MM-DD>/...  archived workspace documents (archive ingest)
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
    def workspace_root(self) -> Path:
        return self._root / "workspace"

    @property
    def internal_root(self) -> Path:
        return self._root / ".tinysoul_knowledge"

    def note_path(self, relative_path: str) -> Path:
        """Map a forward-slash store-relative note path to a safe target."""

        return self._safe_path(self.notes_root, relative_path)

    def _safe_path(self, base: Path, relative_path: str) -> Path:
        if not relative_path or relative_path.startswith("/"):
            raise KnowledgeContractError(
                f"Knowledge document path is invalid: {relative_path!r}"
            )
        parts = relative_path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise KnowledgeContractError(
                f"Knowledge document path is invalid: {relative_path!r}"
            )
        if not relative_path.lower().endswith(".md"):
            raise KnowledgeContractError(
                f"Knowledge documents must be Markdown: {relative_path!r}"
            )
        path = base.joinpath(*parts)
        resolved = path.absolute()
        base_abs = base.absolute()
        if base_abs not in resolved.parents and resolved != base_abs:
            raise KnowledgeInvariantError(
                f"Knowledge document path escapes the store: {relative_path!r}"
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

    def _root_for(self, source: str) -> Path:
        return {
            "obsidian": self.notes_root,
            "chat": self.chats_root,
            "card": self.cards_root,
            "workspace": self.workspace_root,
        }.get(source, self.notes_root)

    def read_document(self, relative_path: str, *, source: str) -> str:
        """Read a store document from the root matching its km_source."""

        path = self._safe_path(self._root_for(source), relative_path)
        if not path.is_file():
            raise KnowledgeIOError(
                f"Knowledge document does not exist: {relative_path}"
            )
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise KnowledgeIOError(
                f"Failed to read knowledge document {relative_path}: {exc}"
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

    def write_chat(self, relative_path: str, text: str) -> Path:
        """Write under ``chats/`` (relative paths like ``2026-10/deepseek/x.md``)."""

        path = self._safe_path(self.chats_root, relative_path)
        try:
            atomic_write_text(path, text)
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to write chat document {relative_path}: {exc}"
            ) from exc
        return path

    def write_card(self, relative_path: str, text: str) -> Path:
        """Write under ``cards/`` (M4 daily knowledge cards)."""

        path = self._safe_path(self.cards_root, relative_path)
        try:
            atomic_write_text(path, text)
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to write card document {relative_path}: {exc}"
            ) from exc
        return path

    def write_workspace(self, relative_path: str, text: str) -> Path:
        """Write under ``workspace/`` (paths like ``2026-10-13/note.md``)."""

        path = self._safe_path(self.workspace_root, relative_path)
        try:
            atomic_write_text(path, text)
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to write workspace document {relative_path}: {exc}"
            ) from exc
        return path

    def write_document(self, relative_path: str, text: str, *, source: str) -> Path:
        """Rewrite a store document in the root matching its km_source."""

        path = self._safe_path(self._root_for(source), relative_path)
        try:
            atomic_write_text(path, text)
        except OSError as exc:
            raise KnowledgeIOError(
                f"Failed to write knowledge document {relative_path}: {exc}"
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
