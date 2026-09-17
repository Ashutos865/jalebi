"""Admin panel API — users, rubric configuration, prompts, audit logs, AI usage."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_role
from app.db.base import get_session
from app.db.models import (
    ROLE_ADMIN,
    ROLE_RANK,
    AuditLog,
    Evaluation,
    RubricOverride,
    User,
)
from app.scoring import ai_prompt
from app.scoring import constitution as C
from app.schemas.evaluation import ContentType
from app.services.audit import log_action

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_role(ROLE_ADMIN)


# --- Users ------------------------------------------------------------------

@router.get("/users")
async def list_users(_: User = Depends(admin_only),
                     session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(User))).scalars().all()
    return [
        {"id": u.id, "email": u.email, "name": u.name, "role": u.role,
         "department": u.department,
         "last_login": u.last_login.isoformat() if u.last_login else None}
        for u in rows
    ]


class UserPatch(BaseModel):
    role: Optional[str] = None
    department: Optional[str] = None


@router.patch("/users/{user_id}")
async def patch_user(user_id: int, body: UserPatch,
                     admin: User = Depends(admin_only),
                     session: AsyncSession = Depends(get_session)) -> dict:
    u = await session.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found.")
    if body.role is not None:
        if body.role not in ROLE_RANK:
            raise HTTPException(422, f"role must be one of {list(ROLE_RANK)}")
        u.role = body.role
    if body.department is not None:
        u.department = body.department
    await session.commit()
    await log_action(session, actor=admin, action="user.update", target=u.email,
                     meta={"role": u.role, "department": u.department})
    return {"id": u.id, "role": u.role, "department": u.department}


# --- Rubrics ----------------------------------------------------------------

@router.get("/rubrics")
async def list_rubrics(_: User = Depends(admin_only)) -> list[dict]:
    """The weights the scoring engine actually uses, per content type."""
    out = []
    for ct in ContentType:
        effective = C.weights_for(ct.value)
        override = C.get_override(ct.value)
        out.append({
            "content_type": ct.value,
            "label": ct.value.replace("_", " ").title(),
            "overridden": override is not None,
            "dimensions": [
                {"key": d.key, "name": d.name, "weight": effective[d.key]}
                for d in C.DIMENSIONS
            ],
        })
    return out


@router.delete("/rubrics/{content_type}")
async def reset_rubric(content_type: str,
                       admin: User = Depends(admin_only),
                       session: AsyncSession = Depends(get_session)) -> dict:
    """Drop an override and go back to the content type's base weights."""
    try:
        ct = ContentType(content_type)
    except ValueError:
        raise HTTPException(422, "Unknown content type.")
    row = (await session.execute(
        select(RubricOverride).where(RubricOverride.content_type == ct.value)
    )).scalar_one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    C.clear_override(ct.value)
    await log_action(session, actor=admin, action="rubric.reset", target=ct.value)
    return {
        "content_type": ct.value,
        "dimensions": [
            {"key": d.key, "name": d.name, "weight": C.weights_for(ct.value)[d.key]}
            for d in C.DIMENSIONS
        ],
    }


class RubricPatch(BaseModel):
    weights: dict  # {dimension_key: weight}


@router.put("/rubrics/{content_type}")
async def update_rubric(content_type: str, body: RubricPatch,
                        admin: User = Depends(admin_only),
                        session: AsyncSession = Depends(get_session)) -> dict:
    try:
        ct = ContentType(content_type)
    except ValueError:
        raise HTTPException(422, "Unknown content type.")

    # Validate against the dimensions the scoring engine actually uses. This
    # endpoint previously wrote to app/rubrics, which no score ever read — an
    # admin could tune weights, see them saved, and change nothing.
    try:
        C.validate_weights(body.weights)
    except C.WeightError as exc:
        raise HTTPException(422, str(exc)) from exc

    row = (await session.execute(
        select(RubricOverride).where(RubricOverride.content_type == ct.value)
    )).scalar_one_or_none()
    if row is None:
        row = RubricOverride(content_type=ct.value, weights=body.weights,
                             updated_by=admin.id)
        session.add(row)
    else:
        row.weights = body.weights
        row.version += 1
        row.updated_by = admin.id
    await session.commit()

    effective = C.set_override(ct.value, body.weights)
    await log_action(session, actor=admin, action="rubric.update", target=ct.value)
    # `requested` vs `effective`: weights are normalised to sum to 1.0, so asking
    # for accuracy=0.50 alongside the other defaults yields 0.40. Reporting both
    # means the admin is never shown a number they did not enter without
    # explanation.
    return {
        "content_type": ct.value,
        "requested": body.weights,
        "dimensions": [
            {"key": key, "name": name, "weight": effective[key]}
            for key, name in [(d.key, d.name) for d in C.DIMENSIONS]
        ],
        "normalised": any(
            abs(effective[k] - v) > 1e-6 for k, v in body.weights.items()
        ),
    }


# --- Prompts (view the exact prompt the model receives) ---------------------

@router.get("/prompts/{content_type}")
async def view_prompt(content_type: str, _: User = Depends(admin_only)) -> dict:
    try:
        ct = ContentType(content_type)
    except ValueError:
        raise HTTPException(422, "Unknown content type.")
    # ai_prompt is what HybridEvaluator actually sends. This previously rendered
    # app/pipeline/prompt.py, which no live evaluation used — so the panel showed
    # an admin a prompt the model never received.
    return {"content_type": ct.value,
            "system_prompt": ai_prompt.build_system(ct.value)}


# --- Audit log + usage ------------------------------------------------------

@router.get("/logs")
async def logs(limit: int = 100, _: User = Depends(admin_only),
               session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    )).scalars().all()
    return [
        {"id": r.id, "actor": r.actor_email, "action": r.action, "target": r.target,
         "meta": r.meta, "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@router.get("/usage")
async def usage(_: User = Depends(admin_only),
                session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(
        select(Evaluation.provider, Evaluation.model, func.count(Evaluation.id))
        .group_by(Evaluation.provider, Evaluation.model)
    )).all()
    return {"by_model": [{"provider": p, "model": m, "count": c} for p, m, c in rows]}
