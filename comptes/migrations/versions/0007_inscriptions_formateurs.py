"""inscriptions par vagues et formateurs

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-17
"""

from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    # Les comptes existants restent actifs
    op.add_column('users', sa.Column('statut', sa.String(length=20), server_default='actif', nullable=False))
    op.add_column('users', sa.Column('attente_depuis', sa.DateTime(), nullable=True))
    op.create_table('trainers',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('ajoute_le', sa.DateTime(), nullable=False),
    sa.Column('ajoute_par', sa.String(length=320), nullable=False),
    sa.PrimaryKeyConstraint('email')
    )
    op.create_table('reglages',
    sa.Column('cle', sa.String(length=64), nullable=False),
    sa.Column('valeur', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('cle')
    )


def downgrade():
    op.drop_table('reglages')
    op.drop_table('trainers')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('attente_depuis')
        batch.drop_column('statut')
