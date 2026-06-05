"""
协作协议定义

定义 Claude 和 Codex 之间通信的标准格式。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CollabMode(str, Enum):
    """协作模式"""
    REVIEW = "review"
    DISCUSS = "discuss"
    PAIR = "pair"


class Severity(str, Enum):
    """问题严重级别"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Category(str, Enum):
    """问题类别"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    READABILITY = "readability"
    LOGIC = "logic"
    STYLE = "style"
    ARCHITECTURE = "architecture"


class ReviewFeedback(BaseModel):
    """审计反馈"""
    severity: Severity
    file_path: str
    line_start: int = 0
    line_end: int = 0
    message: str
    suggestion: str
    category: Category
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    code_snippet: str = ""


class DiscussionPoint(BaseModel):
    """讨论要点"""
    topic: str
    position: str
    arguments: list[str] = []
    evidence: list[str] = []


class CodeChange(BaseModel):
    """代码变更"""
    file_path: str
    operation: Literal["create", "modify", "delete"]
    old_content: str | None = None
    new_content: str
    description: str
    author: Literal["claude", "codex"]


class CollabMessage(BaseModel):
    """协作消息"""
    id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    sender: Literal["claude", "codex", "user"]
    mode: CollabMode
    content: ReviewFeedback | DiscussionPoint | CodeChange | dict[str, Any]
    metadata: dict[str, Any] = {}


class CollabSession(BaseModel):
    """协作会话"""
    id: str
    mode: CollabMode
    started_at: datetime = Field(default_factory=datetime.now)
    messages: list[CollabMessage] = []
    status: Literal["active", "completed", "failed"] = "active"
    project_dir: str = ""
