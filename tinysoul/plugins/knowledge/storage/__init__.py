"""Knowledge storage: Markdown documents, tombstone ledger, and derived index."""

from .index import KnowledgeIndex
from .store import KnowledgeStore

__all__ = ("KnowledgeIndex", "KnowledgeStore")
