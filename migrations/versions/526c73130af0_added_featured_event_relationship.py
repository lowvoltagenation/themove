"""added featured event relationship

Revision ID: 526c73130af0
Revises: 819a44d43cf0
Create Date: 2023-12-29 17:24:18.315311

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '526c73130af0'
down_revision = '819a44d43cf0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('featured_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('newsletter_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'newsletters', ['newsletter_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('featured_events', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('newsletter_id')

    # ### end Alembic commands ###
