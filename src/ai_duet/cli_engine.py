"""
CLI 执行引擎

调用 Claude Code CLI 和 Codex CLI 进行协作。
集成并行执行、会话持久化、Git 集成。
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig, get_config
from .parallel_engine import ParallelEngine, CLIResult, ParallelResult
from .persistence import SessionStorage, ResultExporter
from .git_integration import GitIntegration
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


class CLIEngine:
    """CLI 执行引擎"""

    def __init__(self, project_dir: str | Path = ".", config: AppConfig | None = None):
        self.project_dir = Path(project_dir).resolve()
        self.config = config or get_config()
        self.parallel_engine = ParallelEngine(self.config.execution)
        self.storage = SessionStorage()
        self.exporter = ResultExporter(self.config.output)
        self.git = GitIntegration(self.project_dir, self.config.git)

    def _generate_session_id(self, mode: str) -> str:
        """生成会话 ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:6]
        return f"{mode}_{timestamp}_{short_id}"

    async def run_review(
        self,
        target: str,
        use_git_diff: bool = False,
    ) -> CollabSession:
        """执行代码审计模式"""
        session_id = self._generate_session_id("review")
        session = CollabSession(
            id=session_id,
            mode=CollabMode.REVIEW,
            project_dir=str(self.project_dir),
        )

        # 获取代码内容
        code_content = ""
        if use_git_diff and self.git.is_git_repo():
            diff = self.git.get_diff(staged=True)
            if diff:
                code_content = diff.diff_content
                target = f"Git staged changes ({len(diff.files)} files)"

        if not code_content:
            # 读取目标文件
            target_path = self.project_dir / target
            if target_path.is_file():
                code_content = target_path.read_text(encoding="utf-8")
            elif target_path.is_dir():
                # 读取目录下的所有 Python 文件
                code_content = self._read_directory(target_path)

        # 并行执行审计
        claude_prompt = self._build_review_prompt(target, code_content, "claude")
        codex_prompt = self._build_review_prompt(target, code_content, "codex")

        result = await self.parallel_engine.run_parallel(
            claude_prompt, codex_prompt, str(self.project_dir)
        )

        # 记录结果
        session.messages.append(CollabMessage(
            id="claude-review-1",
            sender="claude",
            mode=CollabMode.REVIEW,
            content={"raw": result.claude.output, "success": result.claude.success},
            metadata={"duration": result.claude.duration},
        ))

        session.messages.append(CollabMessage(
            id="codex-review-1",
            sender="codex",
            mode=CollabMode.REVIEW,
            content={"raw": result.codex.output, "success": result.codex.success},
            metadata={"duration": result.codex.duration},
        ))

        # 比较结果
        if result.claude.success and result.codex.success:
            compare_prompt = self._build_compare_prompt(
                result.claude.output, result.codex.output
            )
            compare_result = await self.parallel_engine._run_cli(
                "claude", compare_prompt, str(self.project_dir)
            )

            session.messages.append(CollabMessage(
                id="compare-1",
                sender="user",
                mode=CollabMode.REVIEW,
                content={"raw": compare_result.output, "success": compare_result.success},
            ))

        session.status = "completed" if result.claude.success or result.codex.success else "failed"

        # 保存会话
        if self.config.output.save_results:
            self.storage.save_session(session)
            self.exporter.export_json(session)
            self.exporter.export_markdown(session)

        return session

    async def run_discuss(
        self,
        topic: str,
        rounds: int = 3,
    ) -> CollabSession:
        """执行技术讨论模式"""
        session_id = self._generate_session_id("discuss")
        session = CollabSession(
            id=session_id,
            mode=CollabMode.DISCUSS,
            project_dir=str(self.project_dir),
        )

        # 初始观点
        claude_prompt = f"""请就以下技术话题阐述你的观点：
话题：{topic}

请提供：
1. 你的立场
2. 支持论点
3. 证据或示例
4. 潜在的反驳"""

        codex_prompt = f"""Please provide your perspective on this technical topic:
Topic: {topic}

Please provide:
1. Your position
2. Supporting arguments
3. Evidence or examples
4. Potential counter-arguments"""

        # 并行获取初始观点
        result = await self.parallel_engine.run_parallel(
            claude_prompt, codex_prompt, str(self.project_dir)
        )

        session.messages.append(CollabMessage(
            id="claude-discuss-1",
            sender="claude",
            mode=CollabMode.DISCUSS,
            content={"raw": result.claude.output, "success": result.claude.success},
        ))

        session.messages.append(CollabMessage(
            id="codex-discuss-1",
            sender="codex",
            mode=CollabMode.DISCUSS,
            content={"raw": result.codex.output, "success": result.codex.success},
        ))

        # 多轮讨论
        claude_response = result.claude.output
        codex_response = result.codex.output

        for round_num in range(1, rounds):
            # Claude 回应
            claude_rebuttal_prompt = f"""Codex 的回应：
{codex_response}

请：
1. 评估 Codex 的观点
2. 指出你同意的部分
3. 提出反驳或补充
4. 尝试达成共识"""

            # Codex 回应
            codex_rebuttal_prompt = f"""Claude's response:
{claude_response}

Please:
1. Evaluate Claude's perspective
2. Points you agree with
3. Counter-arguments or additions
4. Try to reach consensus"""

            rebuttal_result = await self.parallel_engine.run_parallel(
                claude_rebuttal_prompt, codex_rebuttal_prompt, str(self.project_dir)
            )

            session.messages.append(CollabMessage(
                id=f"claude-discuss-{round_num + 1}",
                sender="claude",
                mode=CollabMode.DISCUSS,
                content={"raw": rebuttal_result.claude.output},
            ))

            session.messages.append(CollabMessage(
                id=f"codex-discuss-{round_num + 1}",
                sender="codex",
                mode=CollabMode.DISCUSS,
                content={"raw": rebuttal_result.codex.output},
            ))

            claude_response = rebuttal_result.claude.output
            codex_response = rebuttal_result.codex.output

        # 生成总结
        summary_prompt = f"""总结这场技术讨论：

话题：{topic}

Claude 的观点：{result.claude.output}
Codex 的观点：{result.codex.output}

请提供：
1. 双方的共识点
2. 仍然存在的分歧
3. 最终建议"""

        summary_result = await self.parallel_engine._run_cli(
            "claude", summary_prompt, str(self.project_dir)
        )

        session.messages.append(CollabMessage(
            id="summary-1",
            sender="user",
            mode=CollabMode.DISCUSS,
            content={"raw": summary_result.output},
        ))

        session.status = "completed"

        # 保存会话
        if self.config.output.save_results:
            self.storage.save_session(session)
            self.exporter.export_json(session)
            self.exporter.export_markdown(session)

        return session

    async def run_pair(
        self,
        task: str,
        strategy: str = "by_module",
    ) -> CollabSession:
        """执行协作编码模式"""
        session_id = self._generate_session_id("pair")
        session = CollabSession(
            id=session_id,
            mode=CollabMode.PAIR,
            project_dir=str(self.project_dir),
        )

        # 获取 Git 信息
        git_context = ""
        if self.git.is_git_repo():
            diff = self.git.get_diff(staged=True)
            if diff:
                git_context = f"\n\nCurrent git diff:\n{diff.diff_content}"

        # 分工
        division_prompt = f"""我们需要协作完成以下任务：
任务：{task}
项目目录：{self.project_dir}
分工策略：{strategy}
{git_context}

请设计分工方案，以 JSON 格式返回：
- claude_tasks: Claude 负责的部分（列表）
- codex_tasks: Codex 负责的部分（列表）
- interface_contract: 接口约定
- merge_strategy: 合并策略"""

        division_result = await self.parallel_engine._run_cli(
            "claude", division_prompt, str(self.project_dir)
        )

        session.messages.append(CollabMessage(
            id="division-1",
            sender="user",
            mode=CollabMode.PAIR,
            content={"raw": division_result.output},
        ))

        # 并行编写代码
        claude_code_prompt = f"""根据分工方案编写代码：
{division_result.output}

请直接编写代码，完成后以 JSON 格式返回：
- file_path: 文件路径
- content: 代码内容
- description: 说明"""

        codex_code_prompt = f"""Write code based on the division plan:
{division_result.output}

Write your part and return as JSON:
- file_path: file path
- content: code content
- description: explanation"""

        code_result = await self.parallel_engine.run_parallel(
            claude_code_prompt, codex_code_prompt, str(self.project_dir)
        )

        session.messages.append(CollabMessage(
            id="claude-code-1",
            sender="claude",
            mode=CollabMode.PAIR,
            content={"raw": code_result.claude.output, "success": code_result.claude.success},
        ))

        session.messages.append(CollabMessage(
            id="codex-code-1",
            sender="codex",
            mode=CollabMode.PAIR,
            content={"raw": code_result.codex.output, "success": code_result.codex.success},
        ))

        # 代码审查和合并
        review_prompt = f"""审查并合并双方的代码：

Claude 的代码：
{code_result.claude.output}

Codex 的代码：
{code_result.codex.output}

请：
1. 检查代码一致性
2. 发现潜在问题
3. 提供合并后的最终代码
4. 说明需要修改的地方"""

        review_result = await self.parallel_engine._run_cli(
            "claude", review_prompt, str(self.project_dir)
        )

        session.messages.append(CollabMessage(
            id="review-1",
            sender="user",
            mode=CollabMode.PAIR,
            content={"raw": review_result.output},
        ))

        session.status = "completed"

        # 保存会话
        if self.config.output.save_results:
            self.storage.save_session(session)
            self.exporter.export_json(session)
            self.exporter.export_markdown(session)

        return session

    async def run_git_review(self, staged: bool = True) -> CollabSession:
        """审计 Git diff"""
        if not self.git.is_git_repo():
            raise RuntimeError("Not a git repository")

        diff = self.git.get_diff(staged=staged)
        if not diff:
            raise RuntimeError("No changes to review")

        return await self.run_review(
            target=f"Git diff ({len(diff.files)} files)",
            use_git_diff=True,
        )

    async def run_git_commit(self, auto_stage: bool = False) -> str:
        """生成并执行 Git commit"""
        if not self.git.is_git_repo():
            raise RuntimeError("Not a git repository")

        if auto_stage:
            self.git.stage_all()

        diff = self.git.get_diff(staged=True)
        if not diff:
            raise RuntimeError("No staged changes to commit")

        # 生成 commit message
        prompt = self.git.generate_commit_prompt(diff)
        result = await self.parallel_engine._run_cli(
            "claude", prompt, str(self.project_dir)
        )

        if not result.success:
            raise RuntimeError(f"Failed to generate commit message: {result.error}")

        return result.output

    def _build_review_prompt(self, target: str, code: str, tool: str) -> str:
        """构建审计提示"""
        if tool == "claude":
            return f"""请审计以下代码，提供详细的审查意见：
目标：{target}
项目目录：{self.project_dir}

代码内容：
{code}

请以 JSON 格式返回审计结果，包含：
- severity: CRITICAL/HIGH/MEDIUM/LOW
- file_path: 文件路径
- line_start, line_end: 行号
- message: 问题描述
- suggestion: 修复建议
- category: security/performance/readability/logic/style/architecture
- confidence: 0.0-1.0"""
        else:
            return f"""Review the following code:
Target: {target}
Project directory: {self.project_dir}

Code:
{code}

Provide structured review feedback as JSON with:
- severity: CRITICAL/HIGH/MEDIUM/LOW
- file_path: file path
- line_start, line_end: line numbers
- message: issue description
- suggestion: fix suggestion
- category: security/performance/readability/logic/style/architecture
- confidence: 0.0-1.0"""

    def _build_compare_prompt(self, claude_review: str, codex_review: str) -> str:
        """构建比较提示"""
        return f"""比较以下两个代码审计结果，找出共同点和分歧：

Claude 的审计：
{claude_review}

Codex 的审计：
{codex_review}

请以 JSON 格式返回：
- common_issues: 双方都认为的问题
- claude_only: 只有 Claude 发现的问题
- codex_only: 只有 Codex 发现的问题
- conflicts: 双方有分歧的问题
- final_recommendations: 最终建议"""

    def _read_directory(self, dir_path: Path, extensions: list[str] = None, max_size_mb: float = 1.0) -> str:
        """读取目录下的文件

        Args:
            dir_path: 目录路径
            extensions: 文件扩展名列表
            max_size_mb: 最大总大小（MB），默认 1MB
        """
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs"]

        max_size_bytes = int(max_size_mb * 1024 * 1024)
        total_size = 0
        content_parts = []
        skipped_files = []

        # 排除的目录
        exclude_dirs = {".venv", "venv", "node_modules", "__pycache__", ".git", "dist", "build"}

        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                # 检查是否在排除目录中
                if any(excluded in file_path.parts for excluded in exclude_dirs):
                    continue

                try:
                    file_size = file_path.stat().st_size

                    # 检查单个文件大小（跳过大于 100KB 的文件）
                    if file_size > 100 * 1024:
                        skipped_files.append(f"{file_path.name} (too large: {file_size // 1024}KB)")
                        continue

                    # 检查总大小
                    if total_size + file_size > max_size_bytes:
                        skipped_files.append(f"remaining files (total size limit {max_size_mb}MB reached)")
                        break

                    file_content = file_path.read_text(encoding="utf-8")
                    relative_path = file_path.relative_to(dir_path)
                    content_parts.append(f"=== {relative_path} ===\n{file_content}")
                    total_size += file_size

                except (UnicodeDecodeError, PermissionError, OSError):
                    continue

        result = "\n\n".join(content_parts)

        # 如果有跳过的文件，添加提示
        if skipped_files:
            result += f"\n\n=== SKIPPED FILES ===\n" + "\n".join(skipped_files)

        return result

    def get_session_summary(self, session: CollabSession) -> dict[str, Any]:
        """获取会话摘要"""
        return {
            "id": session.id,
            "mode": session.mode.value,
            "status": session.status,
            "messages": len(session.messages),
            "project": session.project_dir,
            "started_at": session.started_at.isoformat(),
        }
