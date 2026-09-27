import asyncio
from importlib import import_module
from logging.config import fileConfig
from typing import Any, cast

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context as alembic_context

migration_context = cast(Any, alembic_context)
database_module = import_module("app.core.database")
import_module("app.domain.models")
settings = database_module.settings
target_metadata = database_module.Base.metadata


def dynamic_context_member(name: str) -> Any:
    return getattr(migration_context, name)


config = dynamic_context_member("config")
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    dynamic_context_member("configure")(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with dynamic_context_member("begin_transaction")():
        dynamic_context_member("run_migrations")()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection: Connection) -> None:
    dynamic_context_member("configure")(connection=connection, target_metadata=target_metadata)
    with dynamic_context_member("begin_transaction")():
        dynamic_context_member("run_migrations")()


if dynamic_context_member("is_offline_mode")():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
