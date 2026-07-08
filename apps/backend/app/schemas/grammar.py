"""Grammar-check contract — one issue = one span with suggested replacements."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class GrammarIssue(BaseModel):
    offset: int = Field(..., ge=0, description="Character offset into the text.")
    length: int = Field(..., ge=0, description="Length of the flagged span.")
    message: str
    short: str = ""
    replacements: List[str] = Field(default_factory=list)
    rule: str = ""
    category: str = ""
    # spelling | grammar | punctuation | style
    severity: str = "style"
    context: str = ""


class CheckRequest(BaseModel):
    text: str = Field(..., description="The text of the editable field being checked.")
    language: str = "en-US"


class CheckResponse(BaseModel):
    issues: List[GrammarIssue] = Field(default_factory=list)
    engine: str = "heuristic"        # heuristic | languagetool
    language: str = "en-US"


class RewriteRequest(BaseModel):
    text: str = Field(..., min_length=1, description="The sentence/snippet to rewrite.")
    # clarity | conciseness | tone | grammar
    goal: str = "clarity"
    context: str = Field("", description="Surrounding text for reference only — never merged in.")


class RewriteResponse(BaseModel):
    options: List[str] = Field(default_factory=list)
    engine: str = ""
