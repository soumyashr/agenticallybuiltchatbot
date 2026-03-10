from pydantic import BaseModel
from enum import Enum
from typing import Optional


class Role(str, Enum):
    admin = "admin"
    faculty = "faculty"
    student = "student"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ChatRequest(BaseModel):
    message: str
    session_id: str


class SourceDoc(BaseModel):
    source: str
    page: Optional[int] = None
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    role: str
    sources: list[SourceDoc]
    reasoning_steps: int


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    chunk_count: int
    error_msg: Optional[str] = None
