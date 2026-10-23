"""In-memory chat sessions with inactivity timeout."""

from __future__ import annotations

import time
import uuid
from typing import Any

SESSION_TTL_SEC = 30 * 60  # 30 minutes
MAX_TURNS = 12  # user+bot pairs kept roughly as 24 messages

_sessions: dict[str, dict[str, Any]] = {}


def new_session_id() -> str:
    return uuid.uuid4().hex


def _purge_expired(now: float | None = None) -> None:
    now = time.time() if now is None else now
    dead = [sid for sid, s in _sessions.items() if now - s["updated"] > SESSION_TTL_SEC]
    for sid in dead:
        _sessions.pop(sid, None)


def load_session(session_id: str | None) -> tuple[str, list[dict[str, str]], bool]:
    """Return (session_id, history, expired).

    If the previous session timed out, ``expired`` is True and history is empty
    (caller should notify the user that context was cleared).
    """
    _purge_expired()
    now = time.time()
    sid = (session_id or "").strip()
    expired = False
    if sid and sid in _sessions:
        sess = _sessions[sid]
        if now - sess["updated"] > SESSION_TTL_SEC:
            _sessions.pop(sid, None)
            expired = True
            sid = new_session_id()
            _sessions[sid] = {"updated": now, "messages": []}
        else:
            sess["updated"] = now
            return sid, list(sess["messages"]), False
    elif sid:
        # Client sent an id we no longer have → treat as expired context.
        expired = True
        sid = new_session_id()
        _sessions[sid] = {"updated": now, "messages": []}
    else:
        sid = new_session_id()
        _sessions[sid] = {"updated": now, "messages": []}
    return sid, list(_sessions[sid]["messages"]), expired


def save_turn(
    session_id: str,
    user_text: str,
    assistant_text: str,
    *,
    matrix: str | None = None,
) -> None:
    _purge_expired()
    now = time.time()
    sess = _sessions.setdefault(session_id, {"updated": now, "messages": []})
    msgs: list[dict[str, str]] = sess["messages"]
    msgs.append({"role": "user", "content": user_text})
    note = assistant_text
    if matrix:
        note = f"[table {matrix}] {assistant_text}"
    msgs.append({"role": "assistant", "content": note[:1200]})
    # keep last MAX_TURNS exchanges
    if len(msgs) > MAX_TURNS * 2:
        sess["messages"] = msgs[-(MAX_TURNS * 2) :]
    sess["updated"] = now


def history_text(messages: list[dict[str, str]], limit: int = 8) -> str:
    if not messages:
        return ""
    lines = []
    for m in messages[-limit:]:
        role = m.get("role", "?")
        content = (m.get("content") or "").strip().replace("\n", " ")
        lines.append(f"{role}: {content[:400]}")
    return "\n".join(lines)
