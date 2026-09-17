"""document AI/plagiarism integrity fields

Records the AI-content and plagiarism percentages the editor obtained from a
real checker (SOP §4), plus who ran them and when. Nullable throughout: an
unchecked document is a distinct state from one checked and found at 0%.

Revision ID: 9a1c4f2b7e30
Revises: 848eaac5682b
Create Date: 2026-09-17 18:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a1c4f2b7e30'
down_revision: Union[str, None] = '848eaac5682b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_percent', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('plagiarism_percent', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('integrity_checked_by', sa.String(length=200),
                                      nullable=False, server_default=''))
        batch_op.add_column(sa.Column('integrity_checked_at',
                                      sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_column('integrity_checked_at')
        batch_op.drop_column('integrity_checked_by')
        batch_op.drop_column('plagiarism_percent')
        batch_op.drop_column('ai_percent')
