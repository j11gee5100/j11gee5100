from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    approval_action_audit,
    approval_request,
    audit_link,
    asset_projection,
    callback_delivery,
    callback_hook,
    callback_replay_audit,
    command_blacklist_rule,
    command_template,
    execution,
    governance_audit,
    sync_checkpoint,
    sync_snapshot,
    system_user_projection,
    task,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
