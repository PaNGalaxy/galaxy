"""
This module no longer contains the mapping of data model classes to the
relational database.
The module will be revised during migration from SQLAlchemy Migrate to Alembic.
"""

import logging
from threading import local
from typing import Optional, Type

from galaxy import model
from galaxy.config import GalaxyAppConfiguration
from galaxy.model import mapper_registry
from galaxy.model.base import SharedModelMapping
from galaxy.model.migrate.triggers.update_audit_table import install as install_timestamp_triggers
from galaxy.model.orm.engine_factory import build_engine
from galaxy.model.security import GalaxyRBACAgent
from galaxy.model.view.utils import install_views

log = logging.getLogger(__name__)

metadata = mapper_registry.metadata


class GalaxyModelMapping(SharedModelMapping):
    security_agent: GalaxyRBACAgent
    thread_local_log: Optional[local]
    create_tables: bool
    User: Type
    GalaxySession: Type


def init(file_path, url, engine_options=None, create_tables=False, map_install_models=False,
        database_query_profiling_proxy=False, object_store=None, trace_logger=None, use_pbkdf2=True,
        slow_query_log_threshold=0, thread_local_log: Optional[local] = None, log_query_counts=False) -> GalaxyModelMapping:
    """Connect mappings to the database"""
    if engine_options is None:
        engine_options = {}
    # Connect dataset to the file path
    model.Dataset.file_path = file_path
    # Connect dataset to object store
    model.Dataset.object_store = object_store
    # Use PBKDF2 password hashing?
    model.User.use_pbkdf2 = use_pbkdf2
    # Load the appropriate db module
    engine = build_engine(url, engine_options, database_query_profiling_proxy, trace_logger, slow_query_log_threshold, thread_local_log=thread_local_log, log_query_counts=log_query_counts)

    model_modules = [model]
    if map_install_models:
        import galaxy.model.tool_shed_install.mapping  # noqa: F401
        from galaxy.model import tool_shed_install
        galaxy.model.tool_shed_install.mapping.init(url=url, engine_options=engine_options, create_tables=create_tables)
        model_modules.append(tool_shed_install)

    result = GalaxyModelMapping(model_modules, engine=engine)

    # Create tables if needed
    if create_tables:
        metadata.create_all(bind=engine)
        install_timestamp_triggers(engine)
        install_views(engine)

    result.create_tables = create_tables
    # load local galaxy security policy
    result.security_agent = GalaxyRBACAgent(result)
    result.thread_local_log = thread_local_log
    return result


def init_models_from_config(config: GalaxyAppConfiguration, map_install_models=False, object_store=None, trace_logger=None):
    model = init(
        config.file_path,
        config.database_connection,
        config.database_engine_options,
        map_install_models=map_install_models,
        database_query_profiling_proxy=config.database_query_profiling_proxy,
        object_store=object_store,
        trace_logger=trace_logger,
        use_pbkdf2=config.get_bool('use_pbkdf2', True),
        slow_query_log_threshold=config.slow_query_log_threshold,
        thread_local_log=config.thread_local_log,
        log_query_counts=config.database_log_query_counts,
    )
    return model
