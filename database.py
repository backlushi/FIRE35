"""
FIRE35 — SQLite models via SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Float,
    DateTime, ForeignKey, UniqueConstraint, text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:////root/fire35/fire35.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True, nullable=True)
    pid = Column(String, unique=True, index=True)          # P-001 … P-051
    password_hash = Column(String, nullable=True)
    telegram_username = Column(String, nullable=True)      # @username для связи
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    profession = Column(String, nullable=True)
    skills = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    reports = relationship("Report", back_populates="user")
    sent_requests = relationship(
        "ContactRequest", foreign_keys="ContactRequest.from_user_id",
        back_populates="from_user")
    received_requests = relationship(
        "ContactRequest", foreign_keys="ContactRequest.to_user_id",
        back_populates="to_user")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(String, nullable=False)                 # "2026-02"
    budget_yes = Column(Boolean, nullable=False, default=False)
    income_gt_expense = Column(Boolean, nullable=False, default=False)
    savings_pct = Column(Float, nullable=False, default=0.0)
    invest_pct = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_user_month"),)

    user = relationship("User", back_populates="reports")


class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")   # pending / accepted / declined
    created_at = Column(DateTime, default=datetime.utcnow)

    from_user = relationship("User", foreign_keys=[from_user_id],
                             back_populates="sent_requests")
    to_user = relationship("User", foreign_keys=[to_user_id],
                           back_populates="received_requests")


class FcmToken(Base):
    __tablename__ = "fcm_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    token = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Миграции: добавляем новые колонки если их нет
    with engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        for col, definition in [
            ("password_hash", "TEXT"),
            ("telegram_username", "TEXT"),
        ]:
            if col not in cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
        conn.commit()
