"""Layer 2 (AI_THREE_LAYER_REBUILD_PLAN.md §4.6): on-demand Deep Research.

Two phases, not one call, matching the pattern already established by
Layer 1 (``src.ai.interpret``: assemble context, then interpret) and this
phase's own per-article/per-cluster analysis (gather evidence, then
structure it via ``complete_structured`` rather than parsing free text):

1. **Gather** (``gather_research``): ``run_agent`` drives a multi-step tool
   loop -- ``web_search`` (trusted-domain-allowlisted server tool),
   ``web_fetch`` (read a specific page in full), ``data_query`` (this
   app's own structured analytics) -- at DEEP tier
   (``router.FEATURE_TIER["deep_research"]``), since this is the plan's
   own highest-stakes tier. ``citation_check`` (``src/ai/tools/
   citation_check.py``) is deliberately NOT included here -- it checks a
   claim against a known ``search_documents.id``, which this agent never
   has (it isn't doing RAG retrieval, it's fetching live web pages); a
   tool the model can't actually use correctly is worse than no tool.
2. **Structure** (``structure_report``): the raw step transcript (tool
   calls + results + the model's own running commentary) is fed to a
   SEPARATE ``complete_structured`` call that produces the final cited
   report -- sections + deduped sources + confidence. Splitting these
   avoids forcing the exploration phase to also emit valid structured
   JSON on every turn, which tool-use models are worse at than a clean
   single-shot "now write it up" pass over evidence already in hand.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.agents.loop import AgentResult, AgentStep, run_agent
from src.ai.models import Tier
from src.ai.tools.data_query import DataQueryTool
from src.ai.tools.web_fetch import WebFetchTool
from src.ai.tools.web_search import web_search_tool_spec

# router.FEATURE_TIER["deep_research"] -- highest-stakes tier per
# src/ai/models.py's own Tier.DEEP docstring ("deep research,
# recommendations, scenarios"). Not looked up dynamically (FEATURE_TIER
# is today a documented registry, not yet consulted at call sites
# anywhere in this codebase -- every feature currently declares its tier
# directly, same as here).
RESEARCH_TIER = Tier.DEEP

MAX_RESEARCH_ITERATIONS = 12

RESEARCHER_SYSTEM_PROMPT = """\
You are a buy-side research analyst conducting deep, qualitative research \
on a subject for a professional investor, per \
AI_THREE_LAYER_REBUILD_PLAN.md Layer 2 (News/Information) §4.6.

Your job is to gather the qualitative "later-relevant" information NOT \
already captured by this app's structured financial data: management \
commentary, competitive dynamics, regulatory/political exposure, supply- \
chain and customer signals, controversies, and expert/alternative views.

Use your tools:
- web_search: find recent, relevant coverage from trusted sources.
- web_fetch: read a specific page's full text once web_search points you \
  at it -- don't rely on a search snippet alone for anything you'll cite.
- data_query: check this app's own computed analytics before asserting \
  anything quantitative -- never guess a number you could look up.

Corroborate important claims across multiple independent sources when you \
can, and note when something is a single-source or lower-trust claim \
rather than presenting it as settled fact. Never fabricate a source, a \
quote, or a fact you did not actually find. When you have gathered enough \
to answer well, stop calling tools and write a thorough final summary of \
everything you found, organized by topic, with the source for each claim \
noted inline (e.g. "(Reuters, 2026-01-10)") -- this becomes the evidence \
base for the final structured report, so be complete and specific rather \
than terse.
"""


class ResearchSection(BaseModel):
    title: str
    content: str
    citations: list[str] = Field(default_factory=list)


class ResearchReportOutput(BaseModel):
    """Structured output for the deep-research synthesis pass."""

    sections: list[ResearchSection] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


STRUCTURE_SYSTEM_PROMPT = """\
You are structuring a completed research investigation into a final cited \
report, per AI_THREE_LAYER_REBUILD_PLAN.md Layer 2 §4.6. You are given the \
full transcript of an analyst's research (tool calls, tool results, and \
their own running notes) -- NOT asked to do any further research.

Produce:
- sections: a list of {title, content, citations}, one per distinct topic \
  actually covered in the transcript (e.g. "Competitive Dynamics", \
  "Regulatory Exposure") -- only include topics the transcript actually \
  surfaced evidence for, do not manufacture empty or generic sections.
- sources: every distinct source (URL or named publication) cited across \
  all sections, deduplicated.
- confidence: your confidence in this report overall, lower when the \
  transcript's evidence was thin, single-sourced, or the research hit its \
  iteration limit without a clean conclusion.

Ground every claim in what the transcript actually contains -- never add \
information not present in the transcript below.
"""


def render_transcript(steps: list[AgentStep]) -> str:
    """Pure: render an agent run's steps into a readable evidence log for
    the structuring pass."""
    lines: list[str] = []
    for i, step in enumerate(steps, start=1):
        if step.text:
            lines.append(f"[Step {i} — analyst notes]\n{step.text}")
        for call, result in zip(step.tool_calls, step.tool_results):
            status = "ERROR" if result.get("is_error") else "OK"
            lines.append(
                f"[Step {i} — tool call: {call['name']}({call['input']}) -> {status}]\n"
                f"{result['content']}"
            )
    return "\n\n".join(lines) if lines else "(no research steps were recorded)"


async def gather_research(
    client,
    session: AsyncSession,
    *,
    subject_label: str,
    focus: str | None = None,
    on_step: Callable[[AgentStep], Awaitable[None]] | None = None,
) -> AgentResult:
    """Phase 1: drive the multi-step tool-use research loop. Raises if the
    client is disabled, matching ``interpreter.py``/``analyzer.py``'s
    convention."""
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")

    user = f"Research subject: {subject_label}"
    if focus:
        user += f"\nSpecific focus: {focus}"

    return await run_agent(
        client=client,
        system=RESEARCHER_SYSTEM_PROMPT,
        user=user,
        tools=[DataQueryTool(session), WebFetchTool()],
        server_tools=[web_search_tool_spec()],
        tier=RESEARCH_TIER,
        max_tokens=4096,
        max_iterations=MAX_RESEARCH_ITERATIONS,
        feature="deep_research",
        on_step=on_step,
    )


async def structure_report(
    client, agent_result: AgentResult, *, subject_label: str, focus: str | None = None
) -> ResearchReportOutput:
    """Phase 2: turn a completed gather pass's transcript into the final
    structured, cited report."""
    transcript = render_transcript(agent_result.steps)
    user = (
        f"Subject: {subject_label}\n"
        f"Focus: {focus or '(none specified — general research)'}\n\n"
        f"<research_transcript>\n{transcript}\n</research_transcript>"
    )
    return await client.complete_structured(
        response_model=ResearchReportOutput,
        user=user,
        system=STRUCTURE_SYSTEM_PROMPT,
        tier=RESEARCH_TIER,
        max_tokens=4096,
        feature="deep_research",
    )


async def run_deep_research(
    client,
    session: AsyncSession,
    *,
    subject_label: str,
    focus: str | None = None,
    on_step: Callable[[AgentStep], Awaitable[None]] | None = None,
) -> ResearchReportOutput:
    """Full pipeline: gather, then structure. Raises if the client is
    disabled (same convention as ``gather_research``) -- callers wanting a
    persisted PENDING/FAILED row on failure should catch via
    ``src.ai.research.store``."""
    agent_result = await gather_research(
        client, session, subject_label=subject_label, focus=focus, on_step=on_step,
    )
    return await structure_report(client, agent_result, subject_label=subject_label, focus=focus)
