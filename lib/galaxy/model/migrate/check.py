import logging
import os.path
import sys

from migrate.versioning import repository, schema
from sqlalchemy import (
    create_engine,
    MetaData,
    Table
)
from sqlalchemy.exc import NoSuchTableError

from galaxy.model import mapping
from galaxy.model.database_utils import create_database, database_exists

log = logging.getLogger(__name__)

# path relative to galaxy
migrate_repository_directory = os.path.abspath(os.path.dirname(__file__)).replace(os.getcwd() + os.path.sep, '', 1)
migrate_repository = repository.Repository(migrate_repository_directory)


def create_or_verify_database(url, galaxy_config_file, engine_options=None, app=None, map_install_models=False):
    """
    Check that the database is use-able, possibly creating it if empty (this is
    the only time we automatically create tables, otherwise we force the
    user to do it using the management script so they can create backups).

    1) Empty database --> initialize with latest version and return
    2) Database older than migration support --> fail and require manual update
    3) Database at state where migrate support introduced --> add version control information but make no changes (might still require manual update)
    4) Database versioned but out of date --> fail with informative message, user must run "sh manage_db.sh upgrade"
    """
    # Create the base database if it doesn't yet exist.
    engine_options = engine_options or {}
    new_database = not database_exists(url)
    if new_database:
        template = app and getattr(app.config, "database_template", None)
        encoding = app and getattr(app.config, "database_encoding", None)
        create_kwds = {}

        message = f"Creating database for URI [{url}]"
        if template:
            message += f" from template [{template}]"
            create_kwds["template"] = template
        if encoding:
            message += f" with encoding [{encoding}]"
            create_kwds["encoding"] = encoding
        log.info(message)
        create_database(url, **create_kwds)

    # Create engine and metadata
    engine = create_engine(url, **engine_options)

    def migrate():
        try:
            # Declare the database to be under a repository's version control
            db_schema = schema.ControlledSchema.create(engine, migrate_repository)
        except Exception:
            # The database is already under version control
            db_schema = schema.ControlledSchema(engine, migrate_repository)
        # Apply all scripts to get to current version
        migrate_to_current_version(engine, db_schema)

    def migrate_from_scratch():
        if not os.environ.get("GALAXY_TEST_FORCE_DATABASE_MIGRATION"):
            log.info("Creating new database from scratch, skipping migrations")
            current_version = migrate_repository.version().version
            mapping.init(file_path='/tmp', url=url, map_install_models=map_install_models, create_tables=True)
            schema.ControlledSchema.create(engine, migrate_repository, version=current_version)
            db_schema = schema.ControlledSchema(engine, migrate_repository)
            assert db_schema.version == current_version
        migrate()
        if app:
            # skips the tool migration process.
            app.new_installation = True

    meta = MetaData(bind=engine)
    if new_database:
        migrate_from_scratch()
        return
    elif app and getattr(app.config, 'database_auto_migrate', False):
        migrate()
        return

    # Try to load dataset table
    try:
        Table("dataset", meta, autoload=True)
    except NoSuchTableError:
        # No 'dataset' table means a completely uninitialized database.
        log.info("No database, initializing")
        migrate_from_scratch()
        return
    try:
        hda_table = Table("history_dataset_association", meta, autoload=True)
    except NoSuchTableError:
        raise Exception("Your database is older than hg revision 1464:c7acaa1bb88f and will need to be updated manually")
    # There is a 'history_dataset_association' table, so we (hopefully) have
    # version 1 of the database, but without the migrate_version table. This
    # happens if the user has a build from right before migration was added.
    # Verify that this is true, if it is any older they'll have to update
    # manually
    if 'copied_from_history_dataset_association_id' not in hda_table.c:
        # The 'copied_from_history_dataset_association_id' column was added in
        # rev 1464:c7acaa1bb88f.  This is the oldest revision we currently do
        # automated versioning for, so stop here
        raise Exception("Your database is older than hg revision 1464:c7acaa1bb88f and will need to be updated manually")
    # At revision 1464:c7acaa1bb88f or greater (database version 1), make sure
    # that the db has version information. This is the trickiest case -- we
    # have a database but no version control, and are assuming it is a certain
    # version. If the user has postion version 1 changes this could cause
    # problems
    try:
        Table("migrate_version", meta, autoload=True)
    except NoSuchTableError:
        # The database exists but is not yet under migrate version control, so init with version 1
        log.info("Adding version control to existing database")
        try:
            Table("metadata_file", meta, autoload=True)
            schema.ControlledSchema.create(engine, migrate_repository, version=2)
        except NoSuchTableError:
            schema.ControlledSchema.create(engine, migrate_repository, version=1)
    # Verify that the code and the DB are in sync
    db_schema = schema.ControlledSchema(engine, migrate_repository)
    if migrate_repository.versions.latest != db_schema.version:
        config_arg = ''
        if galaxy_config_file and os.path.abspath(os.path.join(os.getcwd(), 'config', 'galaxy.ini')) != galaxy_config_file:
            config_arg = f" -c {galaxy_config_file.replace(os.path.abspath(os.getcwd()), '.')}"
        expect_msg = "Your database has version '%d' but this code expects version '%d'" % (db_schema.version, migrate_repository.versions.latest)
        instructions = ""
        if db_schema.version > migrate_repository.versions.latest:
            instructions = "To downgrade the database schema you have to checkout the Galaxy version that you were running previously. "
            cmd_msg = "sh manage_db.sh%s downgrade %d" % (config_arg, migrate_repository.versions.latest)
        else:
            cmd_msg = f"sh manage_db.sh{config_arg} upgrade"
        backup_msg = f"Please backup your database and then migrate the database schema by running '{cmd_msg}'."
        allow_future_database = os.environ.get("GALAXY_ALLOW_FUTURE_DATABASE", False)
        if db_schema.version > migrate_repository.versions.latest and allow_future_database:
            log.warning("WARNING: Database is from the future, but GALAXY_ALLOW_FUTURE_DATABASE is set, so Galaxy will continue to start.")
        else:
            raise Exception(f"{expect_msg}. {instructions}{backup_msg}")
    else:
        log.info("At database version %d" % db_schema.version)


def migrate_to_current_version(engine, schema):
    # Changes to get to current version
    try:
        changeset = schema.changeset(None)
    except Exception as e:
        log.error(f"Problem determining migration changeset for engine [{engine}]")
        raise e
    for ver, change in changeset:
        nextver = ver + changeset.step
        log.info(f'Migrating {ver} -> {nextver}... ')
        old_stdout = sys.stdout

        class FakeStdout:
            def __init__(self):
                self.buffer = []

            def write(self, s):
                self.buffer.append(s)

            def flush(self):
                pass
        sys.stdout = FakeStdout()
        try:
            schema.runchange(ver, change, changeset.step)
        finally:
            for message in "".join(sys.stdout.buffer).split("\n"):
                log.info(message)
            sys.stdout = old_stdout
