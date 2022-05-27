"""
Migration script to add 'object_store_id' column to various tables
"""

import logging

from sqlalchemy import Column, MetaData, Table

from galaxy.model.custom_types import TrimmedString

log = logging.getLogger(__name__)
metadata = MetaData()


def upgrade(migrate_engine):
    print(__doc__)
    metadata.bind = migrate_engine
    metadata.reflect()

    for t_name in ('dataset', 'job', 'metadata_file'):
        t = Table(t_name, metadata, autoload=True)
        c = Column("object_store_id", TrimmedString(255), index=True)
        try:
            c.create(t, index_name=f"ix_{t_name}_object_store_id")
            assert c is t.c.object_store_id
        except Exception:
            log.exception("Adding object_store_id column to %s table failed.", t_name)


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()

    for t_name in ('dataset', 'job', 'metadata_file'):
        t = Table(t_name, metadata, autoload=True)
        try:
            t.c.object_store_id.drop()
        except Exception:
            log.exception("Dropping object_store_id column from %s table failed.", t_name)
