"""questions et réponses sur les modules

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('exercises', sa.Column('dernier_journal', sa.Text(), server_default='', nullable=False))
    op.create_table('questions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(length=64), nullable=False),
    sa.Column('titre', sa.String(length=150), nullable=False),
    sa.Column('texte', sa.Text(), nullable=False),
    sa.Column('prive', sa.Boolean(), nullable=False),
    sa.Column('solution', sa.Boolean(), nullable=False),
    sa.Column('journal', sa.Text(), nullable=False),
    sa.Column('resolue_le', sa.DateTime(), nullable=True),
    sa.Column('masquee_le', sa.DateTime(), nullable=True),
    sa.Column('signalements', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.Column('activite_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_questions_user_id'), 'questions', ['user_id'], unique=False)
    op.create_index(op.f('ix_questions_module'), 'questions', ['module'], unique=False)
    op.create_index(op.f('ix_questions_cree_le'), 'questions', ['cree_le'], unique=False)
    op.create_table('answers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('texte', sa.Text(), nullable=False),
    sa.Column('solution', sa.Boolean(), nullable=False),
    sa.Column('equipe', sa.Boolean(), nullable=False),
    sa.Column('validee', sa.Boolean(), nullable=False),
    sa.Column('masquee_le', sa.DateTime(), nullable=True),
    sa.Column('signalements', sa.Integer(), nullable=False),
    sa.Column('cree_le', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_answers_question_id'), 'answers', ['question_id'], unique=False)
    op.create_index(op.f('ix_answers_user_id'), 'answers', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_answers_user_id'), table_name='answers')
    op.drop_index(op.f('ix_answers_question_id'), table_name='answers')
    op.drop_table('answers')
    op.drop_index(op.f('ix_questions_cree_le'), table_name='questions')
    op.drop_index(op.f('ix_questions_module'), table_name='questions')
    op.drop_index(op.f('ix_questions_user_id'), table_name='questions')
    op.drop_table('questions')
    with op.batch_alter_table('exercises') as batch:
        batch.drop_column('dernier_journal')
