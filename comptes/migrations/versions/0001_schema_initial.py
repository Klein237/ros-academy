"""schema initial

Revision ID: 0001
Revises: 
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('login_tokens',
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('suite', sa.String(length=500), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('expire_le', sa.DateTime(), nullable=False),
    sa.Column('utilise_le', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('hash')
    )
    op.create_index(op.f('ix_login_tokens_email'), 'login_tokens', ['email'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('nom', sa.String(length=120), nullable=False),
    sa.Column('formule', sa.String(length=20), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('exercises',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(length=64), nullable=False),
    sa.Column('indices', sa.Integer(), nullable=False),
    sa.Column('reussi_le', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'module')
    )
    op.create_table('identities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('fournisseur', sa.String(length=20), nullable=False),
    sa.Column('sujet', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fournisseur', 'sujet')
    )
    op.create_index(op.f('ix_identities_user_id'), 'identities', ['user_id'], unique=False)
    op.create_table('qcm_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(length=64), nullable=False),
    sa.Column('note', sa.Float(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_qcm_attempts_user_id'), 'qcm_attempts', ['user_id'], unique=False)
    op.create_table('queue',
    sa.Column('ticket', sa.String(length=43), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('vu_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('ticket'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('sessions',
    sa.Column('id_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('expire_le', sa.DateTime(), nullable=False),
    sa.Column('revoquee', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id_hash')
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('usage_ticks',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('minute', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'minute')
    )


def downgrade():
    op.drop_table('usage_ticks')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_table('queue')
    op.drop_index(op.f('ix_qcm_attempts_user_id'), table_name='qcm_attempts')
    op.drop_table('qcm_attempts')
    op.drop_index(op.f('ix_identities_user_id'), table_name='identities')
    op.drop_table('identities')
    op.drop_table('exercises')
    op.drop_table('users')
    op.drop_index(op.f('ix_login_tokens_email'), table_name='login_tokens')
    op.drop_table('login_tokens')
