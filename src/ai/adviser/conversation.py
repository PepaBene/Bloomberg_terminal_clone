"""Persistence for Layer 3 adviser chat conversations (§5.3): multi-turn
threads, and the "conversational memory/recall over prior messages" the
plan calls for. ``run_agent`` (and by extension ``gather_advice``) only
takes a single seed ``user`` string, not a message-list API -- recall is
implemented by rendering prior turns as a text transcript prepended to
the new message, the same technique ``render_transcript`` in this
package uses for tool-call history within a single turn.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationMessage

# How many prior turns to include as recall context. Unbounded history
# would make later turns' prompts grow without limit; recent turns matter
# far more than the full thread for a financial adviser conversation.
MAX_HISTORY_MESSAGES = 20


async def create_conversation(
    session: AsyncSession, *, user_id: str, portfolio_id: uuid.UUID | None = None, title: str | None = None,
) -> Conversation:
    convo = Conversation(id=uuid.uuid4(), user_id=user_id, portfolio_id=portfolio_id, title=title)
    session.add(convo)
    await session.flush()
    return convo


async def get_conversation(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


async def append_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    role: str,
    content: str,
    tool_calls: list | None = None,
    citations: list | None = None,
    tokens: int | None = None,
) -> ConversationMessage:
    msg = ConversationMessage(
        id=uuid.uuid4(), conversation_id=conversation_id, role=role, content=content,
        tool_calls=tool_calls, citations=citations, tokens=tokens,
    )
    session.add(msg)
    await session.flush()
    return msg


async def load_history(
    session: AsyncSession, conversation_id: uuid.UUID, *, limit: int = MAX_HISTORY_MESSAGES,
) -> list[ConversationMessage]:
    """Most recent ``limit`` messages, oldest first (chronological reading order)."""
    rows = (
        await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(reversed(rows))


def render_history_for_prompt(messages: list[ConversationMessage]) -> str:
    """Pure: prior turns -> a text transcript to prepend to a new user
    message, giving the adviser recall without a message-list API."""
    if not messages:
        return ""
    lines = ["Prior conversation:"]
    for m in messages:
        speaker = "User" if m.role == "user" else "Adviser"
        lines.append(f"{speaker}: {m.content}")
    return "\n".join(lines) + "\n\n---\n\n"
