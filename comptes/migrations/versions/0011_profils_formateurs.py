"""Profil public des formateurs (page « Qui sommes-nous »)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-31
"""

from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('trainer_profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=80), nullable=False),
    sa.Column('titre', sa.String(length=120), nullable=False),
    sa.Column('linkedin', sa.String(length=300), nullable=False),
    sa.Column('visible', sa.Boolean(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('modifie_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade():
    op.drop_table('trainer_profiles')
