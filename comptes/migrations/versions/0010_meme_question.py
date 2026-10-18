"""« J'ai la même question »

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('question_votes',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'question_id')
    )
    op.create_index(op.f('ix_question_votes_question_id'), 'question_votes', ['question_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_question_votes_question_id'), table_name='question_votes')
    op.drop_table('question_votes')
