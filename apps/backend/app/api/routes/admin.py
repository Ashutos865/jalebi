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
from app.pipeline import prompt as prompt_builder
from app.rubrics import RUBRICS, get_rubric, set_override
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
    out = []
    for ct in ContentType:
        r = get_rubric(ct)
        out.append({
            "content_type": ct.value, "label": r.label,
            "dimensions": [{"key": d.key, "name": d.name, "weight": d.weight}
                           for d in r.dimensions],
        })
    return out


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
    valid = {d.key for d in RUBRICS[ct].dimensions}
    bad = set(body.weights) - valid
    if bad:
        raise HTTPException(422, f"Unknown dimension keys: {sorted(bad)}")
    # Persist + apply in-memory.
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
    set_override(ct, body.weights)
    await log_action(session, actor=admin, action="rubric.update", target=ct.value)
    return {"content_type": ct.value,
            "dimensions": [{"key": d.key, "weight": d.weight}
                           for d in get_rubric(ct).dimensions]}


# --- Prompts (view the exact prompt the model receives) ---------------------

@router.get("/prompts/{content_type}")
async def view_prompt(content_type: str, _: User = Depends(admin_only)) -> dict:
    try:
        ct = ContentType(content_type)
    except ValueError:
        raise HTTPException(422, "Unknown content type.")
    return {"content_type": ct.value,
            "system_prompt": prompt_builder.build_system(get_rubric(ct))}


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
