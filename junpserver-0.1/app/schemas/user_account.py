from __future__ import annotations

from pydantic import BaseModel, Field


class CreateUserAccountRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=128)
    role: str = Field(default="user", max_length=32)
    password: str = Field(min_length=1, max_length=128)
    enabled: bool = True


class UpdateUserAccountRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    role: str | None = Field(default=None, max_length=32)
    password: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
