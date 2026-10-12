from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, DateTime, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.db import Base

def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    projects: Mapped[list["Project"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    owner: Mapped[User] = relationship(back_populates="projects")
    error_logs: Mapped[list["ErrorLog"]] = relationship(back_populates="project", cascade="all, delete-orphan")
class ErrorLog(Base):
    __tablename__ = "error_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    project: Mapped[Project] = relationship(back_populates="error_logs")
    patches: Mapped[list["Patch"]] = relationship(back_populates="error_log", cascade="all, delete-orphan")
class Patch(Base):
    __tablename__ = "patches"
    id: Mapped[int] = mapped_column(primary_key=True)
    error_log_id: Mapped[int] = mapped_column(ForeignKey("error_logs.id", ondelete="CASCADE"), index=True)
    diff: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="awaiting_approval")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    error_log: Mapped[ErrorLog] = relationship(back_populates="patches")
    runs: Mapped[list["SandboxRun"]] = relationship(back_populates="patch", cascade="all, delete-orphan")
class SandboxRun(Base):
    __tablename__ = "sandbox_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    patch_id: Mapped[int] = mapped_column(ForeignKey("patches.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    sandbox_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    patch: Mapped[Patch] = relationship(back_populates="runs")
    test_results: Mapped[list["TestResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
class TestResult(Base):
    __tablename__ = "test_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    sandbox_run_id: Mapped[int] = mapped_column(ForeignKey("sandbox_runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    run: Mapped[SandboxRun] = relationship(back_populates="test_results")
