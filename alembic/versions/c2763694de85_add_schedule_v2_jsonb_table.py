"""add schedule_v2 jsonb table

Revision ID: c2763694de85
Revises: 4ee00300bc9f
Create Date: 2026-04-18 23:24:16.440732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2763694de85'
down_revision: Union[str, Sequence[str], None] = '4ee00300bc9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename legacy table instead of dropping
    op.rename_table('schedule', 'schedule_legacy')
    
    # Create new JSONB table
    op.create_table('schedule_v2',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('group_name', sa.Text(), nullable=False),
    sa.Column('day', sa.Text(), nullable=False),
    sa.Column('lessons', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schedule_v2_day'), 'schedule_v2', ['day'], unique=False)
    op.create_index(op.f('ix_schedule_v2_group_name'), 'schedule_v2', ['group_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_schedule_v2_group_name'), table_name='schedule_v2')
    op.drop_index(op.f('ix_schedule_v2_day'), table_name='schedule_v2')
    op.drop_table('schedule_v2')
    
    # Restore legacy table name
    op.rename_table('schedule_legacy', 'schedule')
