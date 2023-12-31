"""newsletter initial

Revision ID: 8d38054f3952
Revises: 452d0dffe1e1
Create Date: 2023-12-21 23:10:23.630464

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8d38054f3952'
down_revision = '452d0dffe1e1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('featured_images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('image_path', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('newsletters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('html_content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sponsors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('image_path', sa.String(length=255), nullable=False),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('featured_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('is_themove', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['event.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('apscheduler_jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_apscheduler_jobs_next_run_time')

    op.drop_table('apscheduler_jobs')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('apscheduler_jobs',
    sa.Column('id', sa.VARCHAR(length=191), autoincrement=False, nullable=False),
    sa.Column('next_run_time', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True),
    sa.Column('job_state', postgresql.BYTEA(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='apscheduler_jobs_pkey')
    )
    with op.batch_alter_table('apscheduler_jobs', schema=None) as batch_op:
        batch_op.create_index('ix_apscheduler_jobs_next_run_time', ['next_run_time'], unique=False)

    op.drop_table('featured_events')
    op.drop_table('sponsors')
    op.drop_table('newsletters')
    op.drop_table('featured_images')
    # ### end Alembic commands ###
