from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from academy_comptes.db import Base, make_engine

ROOT = Path(__file__).resolve().parents[1]


def config(url):
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


def test_upgrade_keeps_existing_accounts(tmp_path):
    from sqlalchemy import text
    url = f"sqlite:///{tmp_path / 'm.db'}"
    command.upgrade(config(url), "0001")
    engine = make_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (email, nom, formule, cree_le) VALUES ('a@b.fr', '', 'free', '2026-01-01')"))
    command.upgrade(config(url), "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT abonnement_resilie, stripe_customer_id FROM users")).one() == (0, None)
    engine.dispose()


def test_migrations_match_the_models(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    command.upgrade(config(url), "head")
    engine = make_engine(url)
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    command.downgrade(config(url), "base")
    engine.dispose()
