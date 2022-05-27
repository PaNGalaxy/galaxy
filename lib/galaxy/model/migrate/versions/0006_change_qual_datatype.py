"""
This migration script changes certain values in the history_dataset_association.extension
column, specifically 'qual' is changed to be 'qual454'.
"""

import logging

from sqlalchemy import MetaData

log = logging.getLogger(__name__)
metadata = MetaData()


def upgrade(migrate_engine):
    print(__doc__)
    metadata.bind = migrate_engine
    metadata.reflect()

    # Set the default data in the galaxy_user table, but only for null values
    cmd = "UPDATE history_dataset_association SET extension = 'qual454' WHERE extension = 'qual' and peek like \'>%%\'"
    try:
        migrate_engine.execute(cmd)
    except Exception:
        log.exception("Resetting extension qual to qual454 in history_dataset_association failed.")
    cmd = "UPDATE history_dataset_association SET extension = 'qualsolexa' WHERE extension = 'qual' and peek not like \'>%%\'"
    try:
        migrate_engine.execute(cmd)
    except Exception:
        log.exception("Resetting extension qual to qualsolexa in history_dataset_association failed.")


def downgrade(migrate_engine):
    pass
