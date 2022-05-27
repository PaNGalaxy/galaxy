"""
Migration script to add the cleanup_event_user_association table.
"""

import datetime
import logging

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table
)

from galaxy.model.migrate.versions.util import (
    create_table,
    drop_table
)

now = datetime.datetime.utcnow
log = logging.getLogger(__name__)
metadata = MetaData()

# New table to log cleanup events
CleanupEventUserAssociation_table = Table(
    "cleanup_event_user_association", metadata,
    Column("id", Integer, primary_key=True),
    Column("create_time", DateTime, default=now),
    Column("cleanup_event_id", Integer, ForeignKey("cleanup_event.id"), index=True, nullable=True),
    Column("user_id", Integer, ForeignKey("galaxy_user.id"), index=True))


def upgrade(migrate_engine):
    print(__doc__)
    metadata.bind = migrate_engine
    metadata.reflect()

    create_table(CleanupEventUserAssociation_table)


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()

    drop_table(CleanupEventUserAssociation_table)
