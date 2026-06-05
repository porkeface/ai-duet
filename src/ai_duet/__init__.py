"""
AI Duet: Claude + Codex Real-time Collaboration Tool

让 Claude Code 和 Codex 能够实时交流、互相审查、协作编写代码。
"""

__version__ = "0.4.1"
__author__ = "AI Duet Contributors"

from .protocol import (
    CollabMode,
    CollabSession,
    CollabMessage,
    ReviewFeedback,
    DiscussionPoint,
    CodeChange,
    Severity,
    Category,
)
from .config import AppConfig, get_config
from .cli_engine import CLIEngine
from .parallel_engine import ParallelEngine
from .persistence import SessionStorage, ResultExporter
from .git_integration import GitIntegration
from .formatter import OutputFormatter

__all__ = [
    "CollabMode",
    "CollabSession",
    "CollabMessage",
    "ReviewFeedback",
    "DiscussionPoint",
    "CodeChange",
    "Severity",
    "Category",
    "AppConfig",
    "get_config",
    "CLIEngine",
    "ParallelEngine",
    "SessionStorage",
    "ResultExporter",
    "GitIntegration",
    "OutputFormatter",
]
