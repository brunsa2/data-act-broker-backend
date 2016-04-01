"""addHeadersDuplicated

Revision ID: 608afa719fb8
Revises: cdb714f6f374
Create Date: 2016-03-23 10:13:52.614000

"""

# revision identifiers, used by Alembic.
revision = '608afa719fb8'
down_revision = 'cdb714f6f374'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade(engine_name):
    globals()["upgrade_%s" % engine_name]()


def downgrade(engine_name):
    globals()["downgrade_%s" % engine_name]()





def upgrade_error_data():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('file_status', sa.Column('headers_duplicated', sa.Text(), nullable=True))
    ### end Alembic commands ###


def downgrade_error_data():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('file_status', 'headers_duplicated')
    ### end Alembic commands ###


def upgrade_job_tracker():
    ### commands auto generated by Alembic - please adjust! ###
    pass
    ### end Alembic commands ###


def downgrade_job_tracker():
    ### commands auto generated by Alembic - please adjust! ###
    pass
    ### end Alembic commands ###


# def upgrade_user_manager():
    ### commands auto generated by Alembic - please adjust! ###
    # op.drop_table('email_template')
    # op.drop_table('email_template_type')
    # op.drop_table('email_token')
    ### end Alembic commands ###


# def downgrade_user_manager():
#     ### commands auto generated by Alembic - please adjust! ###
#     op.create_table('email_token',
#     sa.Column('email_token_id', sa.INTEGER(), server_default=sa.text(u"nextval('emailtokenserial'::regclass)"), nullable=False),
#     sa.Column('token', sa.TEXT(), autoincrement=False, nullable=True),
#     sa.Column('salt', sa.TEXT(), autoincrement=False, nullable=True),
#     sa.PrimaryKeyConstraint('email_token_id', name=u'email_token_pkey')
#     )
#     op.create_table('email_template_type',
#     sa.Column('email_template_type_id', sa.INTEGER(), autoincrement=False, nullable=False),
#     sa.Column('name', sa.TEXT(), autoincrement=False, nullable=True),
#     sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
#     sa.PrimaryKeyConstraint('email_template_type_id', name=u'email_template_type_pkey')
#     )
#     op.create_table('email_template',
#     sa.Column('email_template_id', sa.INTEGER(), server_default=sa.text(u"nextval('emailtemplateserial'::regclass)"), nullable=False),
#     sa.Column('subject', sa.TEXT(), autoincrement=False, nullable=True),
#     sa.Column('content', sa.TEXT(), autoincrement=False, nullable=True),
#     sa.Column('template_type_id', sa.INTEGER(), autoincrement=False, nullable=False),
#     sa.PrimaryKeyConstraint('email_template_id', name=u'email_template_pkey')
#     )
    ### end Alembic commands ###

