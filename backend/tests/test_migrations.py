from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from app.models import Base
from tests.conftest import TEST_DATABASE_URL, alembic_config, recreate_database

MIGRATIONS_DB_URL = (
    make_url(TEST_DATABASE_URL)
    .set(database=f"{make_url(TEST_DATABASE_URL).database}_migrations")
    .render_as_string(hide_password=False)
)


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_migrations_run_up_down_and_up_again_on_a_fresh_database():
    recreate_database(MIGRATIONS_DB_URL)
    config = alembic_config(MIGRATIONS_DB_URL)
    engine = create_engine(MIGRATIONS_DB_URL)
    try:
        command.upgrade(config, "head")
        assert _tables(engine) == set(Base.metadata.tables)

        command.downgrade(config, "base")
        assert _tables(engine) == set()

        command.upgrade(config, "head")
        assert _tables(engine) == set(Base.metadata.tables)
    finally:
        engine.dispose()


def test_models_match_migrations(engine):
    """Fails if a model was changed without generating a migration for it."""
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []
