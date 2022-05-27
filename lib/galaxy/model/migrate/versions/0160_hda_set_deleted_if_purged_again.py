"""
Migration script to set the 'deleted' column of the
'history_dataset_association' table to True if 'purged' is True.
"""

import logging

from galaxy.model.migrate.versions.util import engine_true

log = logging.getLogger(__name__)


def upgrade(migrate_engine):
    print(__doc__)
    cmd = f'UPDATE history_dataset_association SET deleted={engine_true(migrate_engine)} WHERE purged AND NOT deleted;'
    try:
        migrate_engine.execute(cmd)
    except Exception:
        log.exception("Exception executing SQL command: %s", cmd)


def downgrade(migrate_engine):
    pass
