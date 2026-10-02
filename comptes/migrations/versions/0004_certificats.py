"""certificats

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('certificates',
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('parcours_id', sa.String(length=64), nullable=False),
    sa.Column('parcours_titre', sa.String(length=200), nullable=False),
    sa.Column('nom', sa.String(length=80), nullable=False),
    sa.Column('note', sa.Float(), nullable=False),
    sa.Column('mention', sa.String(length=20), nullable=False),
    sa.Column('modules_json', sa.Text(), nullable=False),
    sa.Column('emis_le', sa.DateTime(), nullable=False),
    sa.Column('revoque_le', sa.DateTime(), nullable=True),
    sa.Column('revoque_motif', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('code'),
    sa.UniqueConstraint('user_id', 'parcours_id')
    )
    op.create_index(op.f('ix_certificates_user_id'), 'certificates', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_certificates_user_id'), table_name='certificates')
    op.drop_table('certificates')
