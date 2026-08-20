"""add consultation_consent to client_profiles

Revision ID: b1f3c9a02e11
Revises: 9d5a4e3bf954
Create Date: 2026-08-20 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1f3c9a02e11'
down_revision: Union[str, None] = '9d5a4e3bf954'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('client_profiles', sa.Column('consultation_consent', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('client_profiles', 'consultation_consent')
