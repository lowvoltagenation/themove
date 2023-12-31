"""instagram

Revision ID: a15cb08491df
Revises: 0b247c6906a3
Create Date: 2023-12-21 12:21:03.560207

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a15cb08491df'
down_revision = '0b247c6906a3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('instagram_post',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('venue_id', sa.Integer(), nullable=False),
    sa.Column('caption', sa.Text(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('image_path', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['venue_id'], ['venue.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('venue', schema=None) as batch_op:
        batch_op.add_column(sa.Column('instagram_handle', sa.String(length=255), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('venue', schema=None) as batch_op:
        batch_op.drop_column('instagram_handle')

    op.drop_table('instagram_post')
    # ### end Alembic commands ###
