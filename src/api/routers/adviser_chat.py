"""Layer 3 — Financial Adviser chat API (AI_THREE_LAYER_REBUILD_PLAN.md §5.3).

``POST /v5/adviser/conversations`` creates a thread. ``POST .../messages``
appends the user's message, then streams the adviser's reasoning over SSE
as it runs, per the plan's SSE requirement (mirrors
``src/api/routers/research_deep.py``'s streaming shape). ``GET
.../messages`` and ``GET .../recommendations`` serve history without
re-running anything.

Same session-lifetime caveat as ``research_deep.py`` (see that module's
docstring): the streaming generator opens its own session via
``get_session_factory()`` rather than reusing the request-scoped
``Depends(get_session)`` one, since FastAPI tears the latter down before
a ``StreamingResponse`` body actually runs. Unlike the version of that
pattern this router's own history had a latent bug in (``src/ai/research/
store.py``'s ``run_and_persist_research`` originally only ``flush()``ed,
never ``commit()``ed, inside that per-stream session -- caught and fixed
alongside this router), every state-changing step here explicitly commits.
"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.adviser.adviser import DISCLAIMER, AdviserTurnResult, run_adviser_turn
from src.ai.adviser.conversation import (
    append_message,
    create_conversation,
    get_conversation,
    load_history,
    render_history_for_prompt,
)
from src.ai.adviser.store import save_recommendations
from src.ai.agents.loop import AgentStep
from src.ai.client import get_ai_client
from src.ai.guardrails.budget import BudgetExceededError, check_budget
from src.ai.streaming import SSEEvent, format_sse, sse_response
from src.api.deps import get_session
from src.database import get_session_factory
from src.models.advice_recommendation import AdviceRecommendation
from src.models.conversation import Conversation, ConversationMessage
from src.schemas.adviser import (
    ConversationMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
    RecommendationResponse,
    SendMessageRequest,
)

router = APIRouter(tags=["AI - Adviser Chat"])

_SENTINEL = object()


@router.post("/adviser/conversations", response_model=ConversationResponse)
async def start_conversation(
    req: CreateConversationRequest,
    session: AsyncSession = Depends(get_session),
):
    convo = await create_conversation(
        session, user_id=req.user_id, portfolio_id=req.portfolio_id, title=req.title,
    )
    await session.commit()
    return ConversationResponse.model_validate(convo)


async def _stream_turn(
    conversation_id: uuid.UUID, portfolio_id: uuid.UUID, user_id: str, prompt: str,
) -> "asyncio.AsyncIterator[str]":
    queue: asyncio.Queue = asyncio.Queue()

    async def on_step(step: AgentStep) -> None:
        await queue.put({
            "tool_calls": [c["name"] for c in step.tool_calls],
            "note": (step.text or "")[:280] or None,
        })

    async def run_and_signal(session: AsyncSession, client) -> AdviserTurnResult | Exception:
        try:
            return await run_adviser_turn(
                client, session, portfolio_id=portfolio_id, message=prompt, on_step=on_step,
            )
        except Exception as e:  # noqa: BLE001
            return e
        finally:
            await queue.put(_SENTINEL)

    async with get_session_factory()() as run_session:
        client = get_ai_client()
        task = asyncio.create_task(run_and_signal(run_session, client))

        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            yield format_sse(SSEEvent(event="step", data=item))

        result = await task
        if isinstance(result, Exception):
            yield format_sse(SSEEvent(event="error", data={"message": str(result)}))
            return

        await append_message(run_session, conversation_id, role="assistant", content=result.reply_text)
        saved = await save_recommendations(
            run_session, user_id=user_id, portfolio_id=portfolio_id, verified=result.recommendations,
        )
        await run_session.commit()

        payload = {
            "reply": result.reply_text,
            "disclaimer": DISCLAIMER,
            "recommendations": [RecommendationResponse.from_row(r).model_dump(mode="json") for r in saved],
        }
        yield format_sse(SSEEvent(event="done", data=payload))


@router.post("/adviser/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    req: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
):
    """Send a message and stream the adviser's response over SSE.

    Event types: ``step`` ({tool_calls, note}) per agent turn, then a
    terminal ``done`` ({reply, disclaimer, recommendations}) or ``error``
    ({message}).
    """
    convo = await get_conversation(session, conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    if convo.portfolio_id is None:
        raise HTTPException(status_code=400, detail="Conversation has no associated portfolio")

    client = get_ai_client()
    if not client.enabled:
        raise HTTPException(status_code=503, detail="AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")

    try:
        await check_budget(convo.user_id, session_factory=get_session_factory)
    except BudgetExceededError as e:
        raise HTTPException(status_code=429, detail=str(e), headers={"Retry-After": "86400"})

    history = await load_history(session, conversation_id)
    await append_message(session, conversation_id, role="user", content=req.message)
    await session.commit()

    prompt = render_history_for_prompt(history) + req.message
    return sse_response(_stream_turn(conversation_id, convo.portfolio_id, convo.user_id, prompt))


@router.get("/adviser/conversations/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    convo = await get_conversation(session, conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    rows = (
        await session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        )
    ).scalars().all()
    return [ConversationMessageResponse.model_validate(r) for r in rows]


@router.get("/adviser/conversations/{conversation_id}/recommendations", response_model=list[RecommendationResponse])
async def get_recommendations(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    convo = await get_conversation(session, conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    rows = (
        await session.execute(
            select(AdviceRecommendation)
            .where(AdviceRecommendation.portfolio_id == convo.portfolio_id, AdviceRecommendation.user_id == convo.user_id)
            .order_by(AdviceRecommendation.created_at.desc())
        )
    ).scalars().all()
    return [RecommendationResponse.from_row(r) for r in rows]
