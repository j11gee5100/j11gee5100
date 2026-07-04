from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class McpToolCallAudit(Base):
    __tablename__ = "mcp_tool_call_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    mcp_call_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    client_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    operator_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    operator_role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    toolset: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    arguments_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    object_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="started")
    error_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
