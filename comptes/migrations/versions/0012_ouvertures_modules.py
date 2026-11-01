"""Ouvertures des modules (cours et lab), pour le suivi des formateurs

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-01
"""

from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('module_openings',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(length=64), nullable=False),
    sa.Column('quoi', sa.String(length=10), nullable=False),
    sa.Column('premiere', sa.DateTime(), nullable=False),
    sa.Column('derniere', sa.DateTime(), nullable=False),
    sa.Column('nombre', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'module', 'quoi')
    )


def downgrade():
    op.drop_table('module_openings')
