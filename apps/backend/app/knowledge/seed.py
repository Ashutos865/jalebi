"""Seed the TIES Content SOP into the knowledge base.

Idempotent — runs on startup and ingests the SOP as a handbook document if it isn't
already present, so every AI evaluation retrieves TIES' actual editorial standards.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeDoc
from app.knowledge.service import create_knowledge_doc

SOP_TITLE = "TIES Content SOP"
CONSTITUTION_TITLE = "TIES Editorial Standards (AI Editor Specification)"
_CONSTITUTION_PATH = Path(__file__).with_name("ties_constitution.md")

SOP_TEXT = """\
Standard Operating Procedure (SOP) for Content — TIES

Purpose: Standardise content creation, editing, and publication — ensuring high-quality,
accurate, engaging outputs with accountability and collaboration between writers and editors.

1. Data Management & Documentation
- Maintain a record of all content pieces. Each entry includes: Title, Publication date,
  Published for, Co-authors (if any), Editor's name, Status (draft, under review,
  finalized, published). Writers and editors verify content readiness with each other.

2. Editorial Guidelines
- Editors ensure content is grammatically correct, well-structured, free of spelling errors.
- Run content through grammar and plagiarism checkers.
- Suggest improvements, refine phrasing, and condense WITHOUT altering the writer's voice.
- Paraphrase to meet word limits or improve clarity.
- Provide or suggest credible sources if the writer hasn't included them.
- Guide writers while retaining their original style. Editors do NOT take ownership.
- Maintain consistency in style and formatting. Highlight factual discrepancies or areas
  needing further research. Align with the publication's tone and audience.

3. AI Usage Policy
- AI tools may be used ONLY for research and idea generation.
- Humanise all AI outputs; content must remain written and reviewed by humans.
- Do NOT rely on AI to write full articles or opinion pieces.

4. Nature & Types of Content
- Matter Coverage / Breaking News: straightforward reporting of events/facts/developments;
  accuracy and clarity are priorities.
- Opinion Pieces: informed viewpoints supported by credible data, research, or statistics.
- Insight / Analytical Pieces: deep-dive evaluations connecting multiple data points;
  explain trends, patterns, and implications.
- Observatory / Investigative Content: observational + analytical work combining facts and
  reasoned conclusions; interpret data, highlight insights, provide actionable perspectives.

5. Quality Assurance & Review — checklist before publication:
- Grammar and spelling
- Word limit and conciseness
- Credible sourcing and citations
- Coherence and logical flow
- Readiness for publication (aligned with the writer's voice and the publication's tone)

6. Continuous Improvement: feedback loops between writers and editors; improve depth of
analysis, clarity of presentation, relevance, and originality.
"""


async def _seed_one(session: AsyncSession, title: str, content: str) -> bool:
    existing = (
        await session.execute(select(KnowledgeDoc).where(KnowledgeDoc.title == title))
    ).scalar_one_or_none()
    if existing is not None:
        return False
    await create_knowledge_doc(
        session, kind="handbook", title=title, content=content, content_type=None
    )
    return True


async def seed_default_knowledge(session: AsyncSession) -> bool:
    """Ingest the SOP and the Editorial Constitution if not already present.

    Returns True if anything was created. The Constitution is the primary editorial
    standard; the SOP remains as supporting process guidance.
    """
    created = await _seed_one(session, SOP_TITLE, SOP_TEXT)
    try:
        constitution = _CONSTITUTION_PATH.read_text(encoding="utf-8")
        created = await _seed_one(session, CONSTITUTION_TITLE, constitution) or created
    except OSError:
        pass
    return created
