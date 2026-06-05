"""
并行执行引擎

使用 asyncio.gather 并行调用 Claude 和 Codex。
"""

import asyncio
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from .config import ExecutionConfig


@dataclass
class CLIResult:
    """CLI 执行结果"""
    tool: str  # claude or codex
    success: bool
    output: str
    error: str = ""
    duration: float = 0.0
    retries: int = 0


@dataclass
class ParallelResult:
    """并行执行结果"""
    claude: CLIResult
    codex: CLIResult
    total_duration: float = 0.0


class ParallelEngine:
    """并行执行引擎"""

    def __init__(self, config: ExecutionConfig | None = None):
        self.config = config or ExecutionConfig()

    async def _run_cli(
        self,
        tool: str,
        prompt: str,
        cwd: str = ".",
    ) -> CLIResult:
        """执行单个 CLI 命令"""
        start_time = time.time()
        last_error = ""

        for attempt in range(self.config.max_retries):
            try:
                if tool == "claude":
                    cmd = ["claude", "-p", prompt, "--output-format", "json"]
                else:
                    cmd = ["codex", "-q", prompt]

                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=self.config.timeout,
                )

                duration = time.time() - start_time

                if result.returncode == 0:
                    return CLIResult(
                        tool=tool,
                        success=True,
                        output=result.stdout,
                        duration=duration,
                        retries=attempt,
                    )
                else:
                    last_error = result.stderr
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避

            except subprocess.TimeoutExpired:
                last_error = f"Timeout after {self.config.timeout}s"
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except FileNotFoundError:
                return CLIResult(
                    tool=tool,
                    success=False,
                    output="",
                    error=f"{tool} CLI not found. Please install it first.",
                    duration=time.time() - start_time,
                )

        return CLIResult(
            tool=tool,
            success=False,
            output="",
            error=f"Max retries exceeded: {last_error}",
            duration=time.time() - start_time,
            retries=self.config.max_retries,
        )

    async def run_parallel(
        self,
        claude_prompt: str,
        codex_prompt: str,
        cwd: str = ".",
    ) -> ParallelResult:
        """并行执行 Claude 和 Codex"""
        start_time = time.time()

        if self.config.parallel:
            # 并行执行
            claude_task = self._run_cli("claude", claude_prompt, cwd)
            codex_task = self._run_cli("codex", codex_prompt, cwd)
            claude_result, codex_result = await asyncio.gather(
                claude_task, codex_task
            )
        else:
            # 串行执行
            claude_result = await self._run_cli("claude", claude_prompt, cwd)
            codex_result = await self._run_cli("codex", codex_prompt, cwd)

        total_duration = time.time() - start_time

        return ParallelResult(
            claude=claude_result,
            codex=codex_result,
            total_duration=total_duration,
        )
