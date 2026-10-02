"""Migrations du service Comptes : `alembic upgrade head` (DATABASE_URL)."""

import os
from logging.config import fileConfig

from alembic import context

from academy_comptes.db import Base, make_engine

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def database_url():
    return config.attributes.get("url") or os.environ["DATABASE_URL"]


def run_migrations_offline():
    context.configure(url=database_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = make_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
