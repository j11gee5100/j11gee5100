from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Asset(BaseModel):
    id: str = Field(default="")
    hostname: str = Field(default="")
    ip: str = Field(default="")
    address: str = Field(default="")
    updated_at: str = Field(default="")


class SystemUser(BaseModel):
    id: str = Field(default="")
    name: str = Field(default="")
    username: str = Field(default="")


class CommandExecutionRequest(BaseModel):
    command: str
    run_as: str
    hosts: list[str]


class CommandExecutionResponse(BaseModel):
    id: str = Field(default="")
    is_finished: bool = Field(default=False)
    result: Any | None = Field(default=None)
    log_url: str | None = Field(default=None)
