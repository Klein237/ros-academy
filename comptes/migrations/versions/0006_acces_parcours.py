"""accès aux parcours (achat ou offert)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('access',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('parcours_id', sa.String(length=64), nullable=False),
    sa.Column('origine', sa.String(length=20), nullable=False),
    sa.Column('debut', sa.DateTime(), nullable=False),
    sa.Column('fin', sa.DateTime(), nullable=True),
    sa.Column('retire_le', sa.DateTime(), nullable=True),
    sa.Column('motif', sa.String(length=200), nullable=False),
    sa.Column('montant_centimes', sa.Integer(), nullable=True),
    sa.Column('stripe_session_id', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('stripe_session_id')
    )
    op.create_index(op.f('ix_access_user_id'), 'access', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_access_user_id'), table_name='access')
    op.drop_table('access')
