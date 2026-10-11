"""Chat platform export adapters → unified session structure (02 文档 §4).

Every adapter returns ``ChatSession`` records; conversion to knowledge store
Markdown is shared. Supported inputs: platform JSON exports (DeepSeek /
ChatGLM style), Markdown conversation exports, and HTML share pages as a
best-effort fallback (trafilatura).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import json
import re

from ..failures import KnowledgeContractError


@dataclass(frozen=True)
class ChatTurn:
    role: str  # "user" | "assistant"
    text: str


@dataclass(frozen=True)
class ChatSession:
    title: str
    turns: tuple[ChatTurn, ...]
    platform: str
    day: date | None = None
    url: str | None = None


@dataclass(frozen=True)
class ParsedChatFile:
    sessions: tuple[ChatSession, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def parse_chat_file(path: Path, *, platform: str) -> ParsedChatFile:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        return _parse_json(path, platform=platform)
    if suffix in (".md", ".markdown"):
        return _parse_markdown(path, platform=platform)
    if suffix in (".html", ".htm"):
        return _parse_html(path, platform=platform)
    raise KnowledgeContractError(
        f"Unsupported chat export format: {path.name} (json/md/html)"
    )


def _clean(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _norm_role(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    role = value.strip().casefold()
    if role in ("user", "human", "用户", "human/user"):
        return "user"
    if role in ("assistant", "ai", "bot", "模型", "助手"):
        return "assistant"
    return None


def _session_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match is None:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def _parse_json(path: Path, *, platform: str) -> ParsedChatFile:
    """DeepSeek/ChatGLM style exports: list of conversations or a wrapped map."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise KnowledgeContractError(f"Chat JSON export is invalid: {exc}") from exc
    conversations = payload
    if isinstance(payload, dict):
        for key in ("conversations", "sessions", "chats", "data", "items"):
            if isinstance(payload.get(key), list):
                conversations = payload[key]
                break
    if not isinstance(conversations, list):
        raise KnowledgeContractError(
            "Chat JSON export must contain a conversation list"
        )
    sessions: list[ChatSession] = []
    warnings: list[str] = []
    for index, raw in enumerate(conversations):
        if not isinstance(raw, dict):
            warnings.append(f"conversation #{index} is not an object; skipped")
            continue
        title = str(
            raw.get("title") or raw.get("name") or raw.get("topic") or f"chat-{index}"
        ).strip()
        url = raw.get("url") or raw.get("share_url") or raw.get("link")
        day = _session_date(
            raw.get("date") or raw.get("create_time") or raw.get("created_at")
        )
        turns: list[ChatTurn] = []
        messages = raw.get("messages")
        if not isinstance(messages, list):
            messages = raw.get("turns") or raw.get("history") or []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = _norm_role(message.get("role") or message.get("sender"))
            text = message.get("content") or message.get("text") or ""
            if role is None or not str(text).strip():
                continue
            turns.append(ChatTurn(role, _clean(str(text))))
        if not turns:
            warnings.append(f"conversation #{index} has no usable turns; skipped")
            continue
        sessions.append(
            ChatSession(
                title=title,
                turns=tuple(turns),
                platform=str(raw.get("platform") or platform),
                day=day,
                url=str(url) if isinstance(url, str) and url.strip() else None,
            )
        )
    return ParsedChatFile(sessions=tuple(sessions), warnings=tuple(warnings))


_MD_SESSION = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_ROLE_LINE = re.compile(
    r"^(?:##\s*)?(用户|助手|User|user|Assistant|assistant)\s*[:：]\s*(.*)$"
)


def _parse_markdown(path: Path, *, platform: str) -> ParsedChatFile:
    """Markdown export: one ``# Title`` section per conversation; turns as
    ``用户:`` / ``助手:`` (or User/Assistant) blocks separated by blank lines."""

    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise KnowledgeContractError(f"Chat Markdown export is unreadable: {exc}") from exc
    text = _clean(text)
    headings = list(_MD_SESSION.finditer(text))
    if not headings:
        session = _one_markdown_session(path.stem, text, platform=platform)
        if session is None:
            return ParsedChatFile(sessions=(), warnings=("no usable turns found",))
        return ParsedChatFile(sessions=(session,))
    sessions: list[ChatSession] = []
    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        title = match.group(1).strip()
        session = _one_markdown_session(title, text[start:end], platform=platform)
        if session is not None:
            sessions.append(session)
    return ParsedChatFile(sessions=tuple(sessions))


def _one_markdown_session(title: str, block: str, *, platform: str) -> ChatSession | None:
    turns: list[ChatTurn] = []
    role: str | None = None
    buffer: list[str] = []
    for line in block.splitlines():
        match = _ROLE_LINE.match(line.strip())
        if match is None:
            if role is not None:
                buffer.append(line)
            continue
        if role is not None and buffer:
            turns.append(ChatTurn(role, "\n".join(buffer).strip()))
        role = "user" if match.group(1).casefold() in ("用户", "user") else "assistant"
        inline = match.group(2).strip()
        buffer = [inline] if inline else []
    if role is not None and buffer:
        turns.append(ChatTurn(role, "\n".join(buffer).strip()))
    if not turns:
        return None
    return ChatSession(title=title or "chat", turns=tuple(turns), platform=platform)


def _parse_html(path: Path, *, platform: str) -> ParsedChatFile:
    """Best-effort HTML share page extraction (trafilatura), single session."""

    try:
        import trafilatura

        downloaded = path.read_text(encoding="utf-8-sig", errors="replace")
        text = trafilatura.extract(downloaded, include_comments=False) or ""
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise KnowledgeContractError(
            f"HTML chat export extraction failed: {exc}"
        ) from exc
    text = _clean(text)
    if not text:
        return ParsedChatFile(sessions=(), warnings=("html extraction produced no text",))
    # Heuristic split: treat alternating paragraphs as turns when roles are absent.
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    turns: list[ChatTurn] = []
    role = "user"
    for paragraph in paragraphs:
        normalized = _norm_role(paragraph.rstrip(":："))
        if normalized is not None:
            role = normalized
            continue
        turns.append(ChatTurn(role, paragraph))
        role = "assistant" if role == "user" else "user"
    if not turns:
        return ParsedChatFile(sessions=(), warnings=("html extraction produced no turns",))
    title = path.stem
    return ParsedChatFile(
        sessions=(ChatSession(title=title, turns=tuple(turns), platform=platform),)
    )


def chat_slug(title: str) -> str:
    """Filesystem-safe slug keeping CJK characters."""

    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title.strip(), flags=re.UNICODE)
    slug = slug.strip("-").strip(".")
    return (slug or "chat")[:80]


CHAT_SPLIT_TURNS = 20


def split_session(session: ChatSession) -> tuple[ChatSession, ...]:
    """Split long conversations every ``CHAT_SPLIT_TURNS`` turns (02 文档 §4.2)."""

    if len(session.turns) <= CHAT_SPLIT_TURNS:
        return (session,)
    chunks = []
    for start in range(0, len(session.turns), CHAT_SPLIT_TURNS):
        part = session.turns[start : start + CHAT_SPLIT_TURNS]
        number = start // CHAT_SPLIT_TURNS + 1
        chunks.append(
            ChatSession(
                title=f"{session.title} (part {number})",
                turns=part,
                platform=session.platform,
                day=session.day,
                url=session.url if number == 1 else None,
            )
        )
    return tuple(chunks)


def render_chat_markdown(session: ChatSession, *, km_id: str, imported_at: datetime) -> str:
    """Store form: km_source: chat frontmatter + ``## 问题`` / ``## 回答`` body."""

    header = [
        "---",
        "km_source: chat",
        f"km_id: {km_id}",
        f"km_platform: {session.platform}",
        f"km_chat_title: {session.title}",
    ]
    if session.day is not None:
        header.append(f"km_chat_date: {session.day.isoformat()}")
    if session.url:
        header.append(f"km_chat_url: {session.url}")
    header.append(f"km_imported: {imported_at.isoformat(timespec='seconds')}")
    header.append("---")
    body: list[str] = [f"# {session.title}", ""]
    for turn in session.turns:
        heading = "## 问题" if turn.role == "user" else "## 回答"
        body.extend([heading, "", turn.text, ""])
    return "\n".join(header) + "\n" + "\n".join(body).rstrip() + "\n"
