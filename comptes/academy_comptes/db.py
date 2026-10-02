"""Modèle de données du service Comptes."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    nom: Mapped[str] = mapped_column(String(120), default="")
    formule: Mapped[str] = mapped_column(String(20), default="free")
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def hub_name(self):
        """Nom d'utilisateur du Hub : stable et conforme au format accepté par le Hub."""
        return f"u{self.id}"


class Identity(Base):
    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("fournisseur", "sujet"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    fournisseur: Mapped[str] = mapped_column(String(20))
    sujet: Mapped[str] = mapped_column(String(255))


class SessionRow(Base):
    __tablename__ = "sessions"
    id_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expire_le: Mapped[datetime] = mapped_column(DateTime)
    revoquee: Mapped[bool] = mapped_column(Boolean, default=False)


class LoginToken(Base):
    __tablename__ = "login_tokens"
    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    suite: Mapped[str] = mapped_column(String(500), default="/")
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expire_le: Mapped[datetime] = mapped_column(DateTime)
    utilise_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UsageTick(Base):
    """Une minute de lab comptée (clé unique : relevé idempotent)."""

    __tablename__ = "usage_ticks"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    minute: Mapped[datetime] = mapped_column(DateTime, primary_key=True)


class QcmAttempt(Base):
    __tablename__ = "qcm_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    module: Mapped[str] = mapped_column(String(64))
    note: Mapped[float] = mapped_column(Float)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Exercise(Base):
    __tablename__ = "exercises"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    module: Mapped[str] = mapped_column(String(64), primary_key=True)
    indices: Mapped[int] = mapped_column(Integer, default=0)
    reussi_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QueueTicket(Base):
    __tablename__ = "queue"
    ticket: Mapped[str] = mapped_column(String(43), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    vu_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


def make_engine(url):
    engine = create_engine(url, pool_pre_ping=True, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    return engine


def make_sessionmaker(engine):
    return sessionmaker(engine, expire_on_commit=False)
