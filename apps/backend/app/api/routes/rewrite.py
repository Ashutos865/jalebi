"""POST /api/rewrite — on-demand AI rewrite of one sentence/snippet.

Unlike /check (fast, rule-based, runs on every keystroke), this is an explicit,
user-triggered call: the writer clicks "Rewrite with AI" on a hover card. It uses
the active LLM provider to return a few alternative phrasings. It is a *line
editor*, not a fact generator — the prompt forbids adding, removing, or altering
any fact, name, number, or claim; it only rephrases for clarity/tone/conciseness.
"""
from __future__ import annotations

import json
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import maybe_require_auth
from app.config import settings
from app.llm.registry import get_spec, _build_client
from app.schemas.grammar import RewriteRequest, RewriteResponse

router = APIRouter(tags=["grammar"])

_GOALS = {
    "clarity": "clearer and easier to read",
    "conciseness": "more concise — cut every word that doesn't earn its place",
    "tone": "more polished and professional in tone",
    "grammar": "grammatically correct while keeping the meaning",
}

_SYSTEM = (
    "You are a meticulous line editor. You rewrite a single sentence to improve it "
    "WITHOUT changing its meaning. STRICT RULES, non-negotiable:\n"
    "- Never add, remove, or alter any fact, name, number, date, quote, or claim.\n"
    "- Never invent information or sources. Only rephrase what is already there.\n"
    "- Preserve the writer's voice; do not impose a generic 'AI voice'.\n"
    "- Return ONLY a JSON array of 2-3 distinct rewrites, e.g. [\"...\",\"...\"]. "
    "No commentary, no keys, no markdown."
)

_MAX_CHARS = 600


def _parse_options(raw: str, original: str) -> List[str]:
    """Pull a JSON array of strings out of the model output; fall back gracefully."""
    text = raw.strip()
    # Strip code fences if the model wrapped the array.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    candidates: List[str] = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            candidates = [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        # Last resort: split lines that look like list items.
        for line in text.splitlines():
            line = re.sub(r'^\s*(?:[-*\d.)\]"]+)\s*', "", line).strip().strip('"')
            if line:
                candidates.append(line)
    # De-dupe, drop anything identical to the original, cap at 3.
    seen = set()
    out: List[str] = []
    for c in candidates:
        key = c.lower()
        if key and key != original.strip().lower() and key not in seen:
            seen.add(key)
            out.append(c)
    return out[:3]


@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite(body: RewriteRequest, _=Depends(maybe_require_auth)) -> RewriteResponse:
    if len(body.text) > _MAX_CHARS:
        raise HTTPException(413, "Select a shorter passage to rewrite.")

    spec = get_spec(settings.provider)
    if spec.kind == "mock" or not spec.is_configured():
        # No live model available — nothing to fabricate a rewrite from.
        return RewriteResponse(options=[], engine="unavailable")

    goal = _GOALS.get(body.goal, _GOALS["clarity"])
    prompt = (
        f"Rewrite this sentence to be {goal}.\n\n"
        f"Sentence:\n\"\"\"{body.text.strip()}\"\"\"\n"
    )
    if body.context.strip():
        prompt += (
            f"\nSurrounding text (for reference only — do NOT merge it in):\n"
            f"\"\"\"{body.context.strip()[:400]}\"\"\"\n"
        )
    prompt += "\nReturn a JSON array of 2-3 rewrites."

    try:
        client = _build_client(spec)
        resp = await client.complete(system=_SYSTEM, prompt=prompt, max_tokens=600)
    except Exception as exc:  # provider/network error — surface a clean 502
        raise HTTPException(502, f"Rewrite provider error: {exc}") from exc

    options = _parse_options(resp.text, body.text)
    return RewriteResponse(options=options, engine=spec.id)
