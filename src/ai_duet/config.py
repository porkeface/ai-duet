"""
配置系统

支持配置文件和环境变量。
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# 默认配置目录
CONFIG_DIR = Path.home() / ".ai-duet"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"


@dataclass
class OutputConfig:
    """输出配置"""
    format: str = "rich"  # rich, plain, json, markdown
    color: bool = True
    verbose: bool = False
    save_results: bool = True
    output_dir: str = "./ai-duet-output"


@dataclass
class ExecutionConfig:
    """执行配置"""
    parallel: bool = True
    timeout: int = 120
    max_retries: int = 3
    interactive: bool = False


@dataclass
class GitConfig:
    """Git 集成配置"""
    auto_diff: bool = True
    generate_commit: bool = True
    commit_style: str = "conventional"  # conventional, simple, detailed


@dataclass
class AppConfig:
    """应用配置"""
    output: OutputConfig = field(default_factory=OutputConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    git: GitConfig = field(default_factory=GitConfig)
    default_project: str = "."

    def save(self, path: Path | None = None):
        """保存配置到文件"""
        config_path = path or CONFIG_FILE
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        """从文件加载配置"""
        config_path = path or CONFIG_FILE
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                output=OutputConfig(**data.get("output", {})),
                execution=ExecutionConfig(**data.get("execution", {})),
                git=GitConfig(**data.get("git", {})),
                default_project=data.get("default_project", "."),
            )
        return cls()

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量加载配置"""
        load_dotenv()
        config = cls()

        # 输出配置
        config.output.format = os.getenv("COLLAB_OUTPUT_FORMAT", config.output.format)
        config.output.color = os.getenv("COLLAB_COLOR", "true").lower() == "true"
        config.output.verbose = os.getenv("COLLAB_VERBOSE", "false").lower() == "true"
        config.output.save_results = os.getenv("COLLAB_SAVE", "true").lower() == "true"
        config.output.output_dir = os.getenv("COLLAB_OUTPUT_DIR", config.output.output_dir)

        # 执行配置
        config.execution.parallel = os.getenv("COLLAB_PARALLEL", "true").lower() == "true"
        config.execution.timeout = int(os.getenv("COLLAB_TIMEOUT", str(config.execution.timeout)))
        config.execution.interactive = os.getenv("COLLAB_INTERACTIVE", "false").lower() == "true"

        # Git 配置
        config.git.auto_diff = os.getenv("COLLAB_GIT_DIFF", "true").lower() == "true"
        config.git.generate_commit = os.getenv("COLLAB_GIT_COMMIT", "true").lower() == "true"
        config.git.commit_style = os.getenv("COLLAB_COMMIT_STYLE", config.git.commit_style)

        # 项目配置
        config.default_project = os.getenv("COLLAB_PROJECT", config.default_project)

        return config


def get_config() -> AppConfig:
    """获取配置（优先环境变量，其次配置文件）"""
    # 先从环境变量加载
    env_config = AppConfig.from_env()

    # 如果配置文件存在，合并配置（环境变量优先）
    if CONFIG_FILE.exists():
        file_config = AppConfig.load()

        # 对于每个配置项，如果环境变量有值则使用环境变量，否则使用文件配置
        # 输出配置
        output = OutputConfig(
            format=os.getenv("COLLAB_OUTPUT_FORMAT", file_config.output.format),
            color=os.getenv("COLLAB_COLOR", str(file_config.output.color)).lower() == "true",
            verbose=os.getenv("COLLAB_VERBOSE", str(file_config.output.verbose)).lower() == "true",
            save_results=os.getenv("COLLAB_SAVE", str(file_config.output.save_results)).lower() == "true",
            output_dir=os.getenv("COLLAB_OUTPUT_DIR", file_config.output.output_dir),
        )

        # 执行配置
        execution = ExecutionConfig(
            parallel=os.getenv("COLLAB_PARALLEL", str(file_config.execution.parallel)).lower() == "true",
            timeout=int(os.getenv("COLLAB_TIMEOUT", str(file_config.execution.timeout))),
            max_retries=int(os.getenv("COLLAB_MAX_RETRIES", str(file_config.execution.max_retries))),
            interactive=os.getenv("COLLAB_INTERACTIVE", str(file_config.execution.interactive)).lower() == "true",
        )

        # Git 配置
        git = GitConfig(
            auto_diff=os.getenv("COLLAB_GIT_DIFF", str(file_config.git.auto_diff)).lower() == "true",
            generate_commit=os.getenv("COLLAB_GIT_COMMIT", str(file_config.git.generate_commit)).lower() == "true",
            commit_style=os.getenv("COLLAB_COMMIT_STYLE", file_config.git.commit_style),
        )

        return AppConfig(
            output=output,
            execution=execution,
            git=git,
            default_project=os.getenv("COLLAB_PROJECT", file_config.default_project),
        )

    return env_config
