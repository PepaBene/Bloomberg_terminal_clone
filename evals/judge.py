"""LLM-as-judge grading: a second Claude call scores a generated response
against a fixed rubric (faithfulness, citation correctness, hallucination,
date awareness, tone), 0-10 per criterion, using ``complete_structured`` so
scores are a validated Pydantic object rather than parsed free text.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from src.ai.models import DEFAULT_TIER, Tier

JUDGE_SYSTEM_PROMPT = """You are grading an AI financial-research assistant's response \
against a rubric. Score each criterion 0-10 (10 = perfect). Be strict: a response that \
states a fact not present in the provided context is NOT faithful even if the fact \
happens to be true in the real world -- it must be grounded in what was actually given, \
not general knowledge."""


class JudgeScore(BaseModel):
    faithfulness: int = Field(
        ge=0, le=10, description="Grounded in the provided context, no invented facts"
    )
    citation_correctness: int = Field(
        ge=0, le=10, description="Citations point at claims they actually support"
    )
    hallucination: int = Field(
        ge=0, le=10, description="10 = no hallucination detected, 0 = fabricated facts present"
    )
    date_awareness: int = Field(
        ge=0, le=10, description="No future dates asserted as already-settled fact"
    )
    tone: int = Field(ge=0, le=10, description="Professional, Bloomberg-style register")
    rationale: str = Field(description="One or two sentences explaining the scores")

    @property
    def overall(self) -> float:
        return (
            self.faithfulness + self.citation_correctness + self.hallucination
            + self.date_awareness + self.tone
        ) / 5


def build_judge_prompt(
    *, question: str, context: str, response: str, rubric_notes: str = ""
) -> str:
    """Pure: assemble the judge's user prompt. Split out so the exact wording
    fed to the judge is independently testable/reviewable without a live call.
    """
    return (
        f"QUESTION:\n{question}\n\n"
        f"CONTEXT PROVIDED TO THE ASSISTANT:\n{context}\n\n"
        f"ASSISTANT'S RESPONSE:\n{response}\n\n"
        f"RUBRIC NOTES:\n{rubric_notes or '(none)'}\n\n"
        "Score the response on the five criteria."
    )


async def judge_response(
    client,
    *,
    question: str,
    context: str,
    response: str,
    rubric_notes: str = "",
    tier: Tier | str = DEFAULT_TIER,
) -> JudgeScore:
    """Grade ``response`` against ``context`` for ``question``.

    Requires a live, enabled AI client (raises ``RuntimeError`` otherwise,
    matching ``AIClient.complete_structured``'s own contract -- there's no
    meaningful "disabled" grade to fall back to).
    """
    if not client.enabled:
        raise RuntimeError("AI disabled: set ANTHROPIC_API_KEY and install 'anthropic'.")
    user = build_judge_prompt(
        question=question, context=context, response=response, rubric_notes=rubric_notes
    )
    return await client.complete_structured(
        response_model=JudgeScore,
        user=user,
        system=JUDGE_SYSTEM_PROMPT,
        tier=tier,
        feature="eval_judge",
    )
