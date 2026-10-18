"""avis des étudiants sur les modules

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('module_feedback',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(length=64), nullable=False),
    sa.Column('note', sa.Integer(), nullable=False),
    sa.Column('difficulte', sa.String(length=20), nullable=False),
    sa.Column('commentaire', sa.Text(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('modifie_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'module')
    )


def downgrade():
    op.drop_table('module_feedback')
