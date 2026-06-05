"""
全面测试

测试所有模块的功能。
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from ai_duet.protocol import (
    CollabMode,
    CollabSession,
    CollabMessage,
    ReviewFeedback,
    DiscussionPoint,
    CodeChange,
    Severity,
    Category,
)
from ai_duet.config import AppConfig, OutputConfig, ExecutionConfig, GitConfig
from ai_duet.persistence import SessionStorage, ResultExporter
from ai_duet.git_integration import GitIntegration, GitDiff, CommitSuggestion
from ai_duet.formatter import OutputFormatter
from ai_duet.parallel_engine import ParallelEngine, CLIResult


# ========== Protocol Tests ==========

class TestProtocol:
    """测试协议模块"""

    def test_collab_mode_enum(self):
        """测试 CollabMode 枚举"""
        assert CollabMode.REVIEW == "review"
        assert CollabMode.DISCUSS == "discuss"
        assert CollabMode.PAIR == "pair"

    def test_severity_enum(self):
        """测试 Severity 枚举"""
        assert Severity.CRITICAL == "CRITICAL"
        assert Severity.HIGH == "HIGH"
        assert Severity.MEDIUM == "MEDIUM"
        assert Severity.LOW == "LOW"

    def test_category_enum(self):
        """测试 Category 枚举"""
        assert Category.SECURITY == "security"
        assert Category.PERFORMANCE == "performance"
        assert Category.READABILITY == "readability"
        assert Category.LOGIC == "logic"
        assert Category.STYLE == "style"
        assert Category.ARCHITECTURE == "architecture"

    def test_review_feedback(self):
        """测试 ReviewFeedback 模型"""
        feedback = ReviewFeedback(
            severity=Severity.HIGH,
            file_path="src/main.py",
            line_start=10,
            line_end=20,
            message="Potential security issue",
            suggestion="Use parameterized queries",
            category=Category.SECURITY,
            confidence=0.9,
        )
        assert feedback.severity == "HIGH"
        assert feedback.file_path == "src/main.py"
        assert feedback.confidence == 0.9

    def test_discussion_point(self):
        """测试 DiscussionPoint 模型"""
        point = DiscussionPoint(
            topic="Microservices vs Monolith",
            position="Microservices are better for large teams",
            arguments=["Better scalability", "Independent deployment"],
            evidence=["Netflix case study", "Amazon architecture"],
        )
        assert point.topic == "Microservices vs Monolith"
        assert len(point.arguments) == 2

    def test_code_change(self):
        """测试 CodeChange 模型"""
        change = CodeChange(
            file_path="src/auth.py",
            operation="create",
            new_content="def login(): pass",
            description="Add login function",
            author="claude",
        )
        assert change.operation == "create"
        assert change.author == "claude"

    def test_collab_session(self):
        """测试 CollabSession 模型"""
        session = CollabSession(
            id="test-001",
            mode=CollabMode.REVIEW,
            project_dir="/path/to/project",
        )
        assert session.id == "test-001"
        assert session.status == "active"
        assert len(session.messages) == 0

    def test_collab_message(self):
        """测试 CollabMessage 模型"""
        message = CollabMessage(
            id="msg-001",
            sender="claude",
            mode=CollabMode.REVIEW,
            content={"raw": "test content"},
        )
        assert message.sender == "claude"
        assert message.mode == "review"


# ========== Config Tests ==========

class TestConfig:
    """测试配置模块"""

    def test_default_config(self):
        """测试默认配置"""
        config = AppConfig()
        assert config.output.format == "rich"
        assert config.execution.parallel is True
        assert config.git.commit_style == "conventional"

    def test_output_config(self):
        """测试输出配置"""
        config = OutputConfig(
            format="json",
            color=False,
            verbose=True,
            save_results=False,
        )
        assert config.format == "json"
        assert config.color is False
        assert config.verbose is True

    def test_execution_config(self):
        """测试执行配置"""
        config = ExecutionConfig(
            parallel=False,
            timeout=60,
            max_retries=5,
        )
        assert config.parallel is False
        assert config.timeout == 60
        assert config.max_retries == 5

    def test_git_config(self):
        """测试 Git 配置"""
        config = GitConfig(
            auto_diff=False,
            generate_commit=False,
            commit_style="simple",
        )
        assert config.auto_diff is False
        assert config.commit_style == "simple"

    def test_config_save_load(self, tmp_path):
        """测试配置保存和加载"""
        config_file = tmp_path / "config.json"
        config = AppConfig(
            output=OutputConfig(format="json"),
            execution=ExecutionConfig(timeout=60),
        )
        config.save(config_file)

        loaded = AppConfig.load(config_file)
        assert loaded.output.format == "json"
        assert loaded.execution.timeout == 60


# ========== Persistence Tests ==========

class TestPersistence:
    """测试持久化模块"""

    def test_session_storage(self, tmp_path):
        """测试会话存储"""
        storage = SessionStorage(tmp_path)
        session = CollabSession(
            id="test-001",
            mode=CollabMode.REVIEW,
            project_dir="/test",
        )
        session.messages.append(CollabMessage(
            id="msg-001",
            sender="claude",
            mode=CollabMode.REVIEW,
            content={"raw": "test"},
        ))

        # 保存
        path = storage.save_session(session)
        assert path.exists()

        # 加载
        loaded = storage.load_session("test-001")
        assert loaded is not None
        assert loaded.id == "test-001"
        assert len(loaded.messages) == 1

    def test_list_sessions(self, tmp_path):
        """测试列出会话"""
        storage = SessionStorage(tmp_path)

        # 创建多个会话
        for i in range(3):
            session = CollabSession(
                id=f"test-{i:03d}",
                mode=CollabMode.REVIEW,
                project_dir="/test",
            )
            storage.save_session(session)

        sessions = storage.list_sessions()
        assert len(sessions) == 3

    def test_delete_session(self, tmp_path):
        """测试删除会话"""
        storage = SessionStorage(tmp_path)
        session = CollabSession(
            id="test-001",
            mode=CollabMode.REVIEW,
            project_dir="/test",
        )
        storage.save_session(session)

        assert storage.delete_session("test-001") is True
        assert storage.load_session("test-001") is None

    def test_export_json(self, tmp_path):
        """测试导出 JSON"""
        config = OutputConfig(output_dir=str(tmp_path))
        exporter = ResultExporter(config)

        session = CollabSession(
            id="test-001",
            mode=CollabMode.REVIEW,
            project_dir="/test",
        )

        path = exporter.export_json(session)
        assert path.exists()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["session"]["id"] == "test-001"

    def test_export_markdown(self, tmp_path):
        """测试导出 Markdown"""
        config = OutputConfig(output_dir=str(tmp_path))
        exporter = ResultExporter(config)

        session = CollabSession(
            id="test-001",
            mode=CollabMode.REVIEW,
            project_dir="/test",
        )

        path = exporter.export_markdown(session)
        assert path.exists()
        assert path.suffix == ".md"

    def test_export_html(self, tmp_path):
        """测试导出 HTML"""
        config = OutputConfig(output_dir=str(tmp_path))
        exporter = ResultExporter(config)

        session = CollabSession(
            id="test-001",
            mode=CollabMode.REVIEW,
            project_dir="/test",
        )

        path = exporter.export_html(session)
        assert path.exists()
        assert path.suffix == ".html"


# ========== Git Integration Tests ==========

class TestGitIntegration:
    """测试 Git 集成模块"""

    def test_is_git_repo(self):
        """测试检查是否是 git 仓库"""
        git = GitIntegration(".")
        # 当前目录应该是 git 仓库
        result = git.is_git_repo()
        assert isinstance(result, bool)

    def test_get_current_branch(self):
        """测试获取当前分支"""
        git = GitIntegration(".")
        branch = git.get_current_branch()
        assert isinstance(branch, str)

    def test_generate_commit_prompt(self):
        """测试生成 commit prompt"""
        git = GitIntegration(".")
        diff = GitDiff(
            files=["test.py"],
            additions=10,
            deletions=5,
            diff_content="+ new line\n- old line",
            summary="1 file changed",
        )

        prompt = git.generate_commit_prompt(diff)
        assert "test.py" in prompt
        assert "git diff" in prompt

    def test_parse_commit_message(self):
        """测试解析 commit message"""
        git = GitIntegration(".")
        message = "feat(auth): add login functionality\n\nImplement user login with JWT tokens."

        suggestion = git.parse_commit_message(message)
        assert suggestion.type == "feat"
        assert suggestion.scope == "auth"
        assert "login" in suggestion.description

    def test_parse_simple_commit(self):
        """测试解析简单 commit message"""
        git = GitIntegration(".")
        message = "fix: resolve null pointer exception"

        suggestion = git.parse_commit_message(message)
        assert suggestion.type == "fix"
        assert "null pointer" in suggestion.description


# ========== Formatter Tests ==========

class TestFormatter:
    """测试格式化器模块"""

    def test_formatter_init(self):
        """测试格式化器初始化"""
        formatter = OutputFormatter()
        assert formatter is not None

    def test_format_duration(self):
        """测试格式化时长"""
        formatter = OutputFormatter()

        assert formatter.format_duration(30) == "30.0s"
        assert formatter.format_duration(90) == "1.5m"
        assert formatter.format_duration(3600) == "1.0h"


# ========== Parallel Engine Tests ==========

class TestParallelEngine:
    """测试并行执行引擎"""

    def test_engine_init(self):
        """测试引擎初始化"""
        config = ExecutionConfig()
        engine = ParallelEngine(config)
        assert engine.config == config

    def test_cli_result(self):
        """测试 CLI 结果"""
        result = CLIResult(
            tool="claude",
            success=True,
            output="test output",
            duration=1.5,
        )
        assert result.tool == "claude"
        assert result.success is True
        assert result.duration == 1.5


# ========== CLI Tests ==========

class TestCLI:
    """测试 CLI 模块"""

    def test_cli_help(self):
        """测试 CLI 帮助"""
        from click.testing import CliRunner
        from ai_duet.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Claude + Codex" in result.output

    def test_review_help(self):
        """测试 r 命令帮助"""
        from click.testing import CliRunner
        from ai_duet.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["r", "--help"])
        assert result.exit_code == 0
        assert "审计代码" in result.output

    def test_discuss_help(self):
        """测试 d 命令帮助"""
        from click.testing import CliRunner
        from ai_duet.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["d", "--help"])
        assert result.exit_code == 0
        assert "技术讨论" in result.output

    def test_pair_help(self):
        """测试 p 命令帮助"""
        from click.testing import CliRunner
        from ai_duet.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["p", "--help"])
        assert result.exit_code == 0
        assert "协作编码" in result.output

    def test_status_command(self):
        """测试 s 命令"""
        from click.testing import CliRunner
        from ai_duet.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["s"])
        assert result.exit_code == 0

    def test_history_command(self):
        """测试 h 命令"""
        from click.testing import CliRunner
        from ai_duet.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["h"])
        assert result.exit_code == 0
