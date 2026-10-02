"""abonnement stripe

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('stripe_events',
    sa.Column('id', sa.String(length=255), nullable=False),
    sa.Column('recu_le', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # batch : SQLite ne sait pas ajouter une contrainte d'unicité par ALTER TABLE
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('abonnement_statut', sa.String(length=40), nullable=True))
        batch.add_column(sa.Column('abonnement_fin', sa.DateTime(), nullable=True))
        # server_default : comptes déjà présents ; retiré ensuite pour coller au modèle
        batch.add_column(sa.Column('abonnement_resilie', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_unique_constraint('uq_users_stripe_customer_id', ['stripe_customer_id'])
    with op.batch_alter_table('users') as batch:
        batch.alter_column('abonnement_resilie', server_default=None)


def downgrade():
    with op.batch_alter_table('users') as batch:
        batch.drop_constraint('uq_users_stripe_customer_id', type_='unique')
        batch.drop_column('abonnement_resilie')
        batch.drop_column('abonnement_fin')
        batch.drop_column('abonnement_statut')
        batch.drop_column('stripe_subscription_id')
        batch.drop_column('stripe_customer_id')
    op.drop_table('stripe_events')
