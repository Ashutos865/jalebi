"""document optimistic-locking version column

Two editors acting on the same submitted article -- one approving, one
scrapping -- both validated against the status they had read, both wrote, and
both received "ok". The scrap silently vanished and the piece went on to
publication. Every UPDATE now carries the version it read.

Revision ID: c4f7a1e82b93
Revises: b7e2d9c41a58
Create Date: 2026-09-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f7a1e82b93'
down_revision: Union[str, None] = 'b7e2d9c41a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default: the model declares a Python-side default, which is applied
    # on INSERT only and never emitted as DDL, so a plain NOT NULL add fails on
    # Postgres against a table that already has rows.
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('version_id', sa.Integer(),
                                      nullable=False, server_default='1'))


def downgrade() -> None:
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_column('version_id')
