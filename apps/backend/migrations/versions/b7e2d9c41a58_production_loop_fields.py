"""production loop fields (SOP §3)

Assignment brief, phase clocks, sign-off and escalation records.

Revision ID: b7e2d9c41a58
Revises: 9a1c4f2b7e30
Create Date: 2026-09-17 19:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2d9c41a58'
down_revision: Union[str, None] = '9a1c4f2b7e30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# server_default on every non-nullable column: the models declare Python-side
# defaults, which are applied on INSERT only and never emitted as DDL, so a
# plain NOT NULL add fails on Postgres against a table that already has rows.
_TEXT_COLUMNS = [
    ('assigned_to', 200),
    ('assigned_by', 200),
    ('approved_by', 200),
]


def upgrade() -> None:
    with op.batch_alter_table('documents', schema=None) as batch_op:
        for name, length in _TEXT_COLUMNS:
            batch_op.add_column(sa.Column(name, sa.String(length=length),
                                          nullable=False, server_default=''))
        batch_op.add_column(sa.Column('override_reason', sa.Text(),
                                      nullable=False, server_default=''))
        batch_op.add_column(sa.Column('escalation_reason', sa.Text(),
                                      nullable=False, server_default=''))
        batch_op.add_column(sa.Column('word_min', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('word_max', sa.Integer(), nullable=True))
        for name in ('assigned_at', 'submitted_at', 'phase_started_at',
                     'approved_at'):
            batch_op.add_column(sa.Column(name, sa.DateTime(timezone=True),
                                          nullable=True))
        # The tracker filters and sorts on status constantly.
        batch_op.create_index('ix_documents_status', ['status'])


def downgrade() -> None:
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index('ix_documents_status')
        for name in ('approved_at', 'phase_started_at', 'submitted_at',
                     'assigned_at', 'word_max', 'word_min',
                     'escalation_reason', 'override_reason'):
            batch_op.drop_column(name)
        for name, _ in reversed(_TEXT_COLUMNS):
            batch_op.drop_column(name)
