"""verifications par exercice

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('exercises') as batch:
        # server_default : lignes déjà présentes ; retiré ensuite pour coller au modèle
        batch.add_column(sa.Column('verifications', sa.Integer(), nullable=False, server_default='0'))
    with op.batch_alter_table('exercises') as batch:
        batch.alter_column('verifications', server_default=None)


def downgrade():
    with op.batch_alter_table('exercises') as batch:
        batch.drop_column('verifications')
