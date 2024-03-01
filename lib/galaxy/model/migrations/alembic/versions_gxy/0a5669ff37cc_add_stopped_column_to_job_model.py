"""add stopped column to job model

Revision ID: 0a5669ff37cc
Revises: e0561d5fc8c7
Create Date: 2023-12-04 15:56:26.362315

"""
from alembic import op
import sqlalchemy as sa

from sqlalchemy import (
    Boolean,
    Column,
)

from galaxy.model.database_object_names import build_index_name
from galaxy.model.migrations.util import (
    add_column,
    drop_column,
    drop_index,
    transaction,
)


# revision identifiers, used by Alembic.
revision = '0a5669ff37cc'
down_revision = 'e0561d5fc8c7'
branch_labels = None
depends_on = None

#database object names used in this revision
table_name = "job"
column_name = "stopped"
index_name = build_index_name(table_name, column_name)


def upgrade():
    add_column(table_name, Column(column_name, Boolean(), default=False, index=True))


def downgrade():
    with transaction():
        drop_index(index_name, table_name)
        drop_column(table_name, column_name)
