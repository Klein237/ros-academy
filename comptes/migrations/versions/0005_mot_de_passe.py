"""mot de passe, adresse vérifiée, liens par but, échecs de connexion

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('mot_de_passe', sa.String(length=200), nullable=True))
    op.add_column('users', sa.Column('email_verifie_le', sa.DateTime(), nullable=True))
    # Comptes existants : ouverts par un lien reçu par e-mail ou par Google / GitHub, l'adresse est vérifiée
    op.execute("UPDATE users SET email_verifie_le = cree_le")
    op.add_column('login_tokens', sa.Column('but', sa.String(length=20), server_default='connexion', nullable=False))
    op.create_table('login_failures',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_failures_email'), 'login_failures', ['email'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_login_failures_email'), table_name='login_failures')
    op.drop_table('login_failures')
    op.drop_column('login_tokens', 'but')
    op.drop_column('users', 'email_verifie_le')
    op.drop_column('users', 'mot_de_passe')
