"""
Git 集成

自动审计 git diff，生成 commit message。
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import GitConfig


@dataclass
class GitDiff:
    """Git diff 结果"""
    files: list[str]
    additions: int
    deletions: int
    diff_content: str
    summary: str


@dataclass
class CommitSuggestion:
    """Commit message 建议"""
    message: str
    type: str  # feat, fix, refactor, docs, test, chore
    scope: str
    description: str
    body: str = ""
    breaking_changes: str = ""


class GitIntegration:
    """Git 集成"""

    def __init__(self, project_dir: str | Path = ".", config: GitConfig | None = None):
        self.project_dir = Path(project_dir).resolve()
        self.config = config or GitConfig()

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """执行 git 命令"""
        return subprocess.run(
            ["git"] + list(args),
            cwd=self.project_dir,
            capture_output=True,
            text=True,
            timeout=30,  # 添加超时限制
        )

    def is_git_repo(self) -> bool:
        """检查是否是 git 仓库"""
        result = self._run_git("rev-parse", "--git-dir")
        return result.returncode == 0

    def get_current_branch(self) -> str:
        """获取当前分支"""
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip() if result.returncode == 0 else ""

    def get_diff(self, staged: bool = True) -> GitDiff | None:
        """获取 git diff"""
        # 构建命令参数
        diff_args = ["diff"]
        stat_args = ["diff", "--stat"]
        files_args = ["diff", "--name-only"]
        numstat_args = ["diff", "--numstat"]

        if staged:
            diff_args.insert(1, "--cached")
            stat_args.insert(1, "--cached")
            files_args.insert(1, "--cached")
            numstat_args.insert(1, "--cached")

        # 获取 diff 内容
        result = self._run_git(*diff_args)
        if result.returncode != 0 or not result.stdout:
            return None

        diff_content = result.stdout

        # 获取统计信息
        stat_result = self._run_git(*stat_args)
        stat_output = stat_result.stdout if stat_result.returncode == 0 else ""

        # 获取文件列表
        files_result = self._run_git(*files_args)
        files = files_result.stdout.strip().split("\n") if files_result.returncode == 0 and files_result.stdout.strip() else []

        # 使用 numstat 获取精确的增删行数
        additions = 0
        deletions = 0
        numstat_result = self._run_git(*numstat_args)
        if numstat_result.returncode == 0 and numstat_result.stdout.strip():
            for line in numstat_result.stdout.strip().split("\n"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    try:
                        additions += int(parts[0]) if parts[0] != "-" else 0
                        deletions += int(parts[1]) if parts[1] != "-" else 0
                    except ValueError:
                        pass

        return GitDiff(
            files=files,
            additions=additions,
            deletions=deletions,
            diff_content=diff_content,
            summary=stat_output,
        )

    def get_staged_files(self) -> list[str]:
        """获取已暂存的文件"""
        result = self._run_git("diff", "--cached", "--name-only")
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []

    def get_unstaged_files(self) -> list[str]:
        """获取未暂存的文件"""
        result = self._run_git("diff", "--name-only")
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []

    def get_untracked_files(self) -> list[str]:
        """获取未跟踪的文件"""
        result = self._run_git("ls-files", "--others", "--exclude-standard")
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []

    def stage_file(self, file_path: str) -> bool:
        """暂存文件"""
        result = self._run_git("add", file_path)
        return result.returncode == 0

    def stage_all(self) -> bool:
        """暂存所有更改"""
        result = self._run_git("add", "-A")
        return result.returncode == 0

    def commit(self, message: str) -> bool:
        """提交更改"""
        result = self._run_git("commit", "-m", message)
        return result.returncode == 0

    def generate_commit_prompt(self, diff: GitDiff) -> str:
        """生成 commit message 的提示"""
        return f"""请根据以下 git diff 生成一个规范的 commit message。

要求：
1. 使用约定式提交格式（Conventional Commits）
2. 类型包括：feat, fix, refactor, docs, test, chore, perf, ci
3. 简洁明了，不超过 72 个字符
4. 用中文描述

Git Diff:
{diff.diff_content}

已修改文件：
{', '.join(diff.files)}

统计信息：
+{diff.additions} additions, -{diff.deletions} deletions

请直接返回 commit message，不要其他内容。"""

    def parse_commit_message(self, message: str) -> CommitSuggestion:
        """解析 commit message"""
        lines = message.strip().split("\n")
        first_line = lines[0] if lines else ""

        # 解析类型和范围
        commit_type = "feat"
        scope = ""
        description = first_line

        if "(" in first_line and ")" in first_line:
            type_part, rest = first_line.split("(", 1)
            commit_type = type_part.strip()
            scope, description = rest.split(")", 1)
            description = description.strip().lstrip(":").strip()
        elif ":" in first_line:
            commit_type, description = first_line.split(":", 1)
            description = description.strip()

        # 解析正文
        body = ""
        breaking_changes = ""
        if len(lines) > 1:
            body_lines = []
            for line in lines[1:]:
                if line.startswith("BREAKING CHANGE:"):
                    breaking_changes = line.replace("BREAKING CHANGE:", "").strip()
                elif line.strip():
                    body_lines.append(line)
            body = "\n".join(body_lines)

        return CommitSuggestion(
            message=message.strip(),
            type=commit_type,
            scope=scope,
            description=description,
            body=body,
            breaking_changes=breaking_changes,
        )

    def get_log(self, count: int = 10) -> list[dict[str, str]]:
        """获取提交历史"""
        result = self._run_git(
            "log",
            f"-{count}",
            "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=short",
        )

        if result.returncode != 0:
            return []

        logs = []
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                parts = line.split("|", 4)
                if len(parts) == 5:
                    logs.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    })
        return logs
