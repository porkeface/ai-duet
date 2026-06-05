"""
并行执行引擎

使用 asyncio.gather 并行调用 Claude 和 Codex。
"""

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

    def _get_tool_path(self, tool: str) -> str:
        """获取工具的完整路径"""
        # 先在 PATH 中查找
        tool_path = shutil.which(tool)
        if tool_path:
            return tool_path

        # 如果在 PATH 中找不到，尝试在 npm 全局目录中查找
        npm_global_dirs = [
            Path.home() / ".npm-global" / "bin",
            Path.home() / "AppData" / "Roaming" / "npm",
        ]

        # 从环境变量读取 npm 全局目录
        npm_prefix = os.environ.get("NPM_CONFIG_PREFIX") or os.environ.get("npm_config_prefix")
        if npm_prefix:
            npm_global_dirs.insert(0, Path(npm_prefix) / "bin")
            npm_global_dirs.insert(0, Path(npm_prefix))

        for npm_dir in npm_global_dirs:
            if npm_dir.exists():
                tool_path = npm_dir / tool
                if tool_path.exists():
                    return str(tool_path)
                # Windows 上也检查 .cmd 文件
                tool_path_cmd = npm_dir / f"{tool}.cmd"
                if tool_path_cmd.exists():
                    return str(tool_path_cmd)

        # 如果都找不到，返回原始命令名
        return tool

    def _parse_output(self, tool: str, raw_output: str) -> str:
        """解析 CLI 输出"""
        if tool == "claude":
            return self._parse_claude_output(raw_output)
        else:
            return self._parse_codex_output(raw_output)

    def _parse_claude_output(self, raw_output: str) -> str:
        """解析 Claude 的 JSON 输出"""
        try:
            data = json.loads(raw_output.strip())
            if isinstance(data, dict) and "result" in data:
                return data["result"]
            return raw_output
        except json.JSONDecodeError:
            return raw_output

    def _parse_codex_output(self, raw_output: str) -> str:
        """解析 Codex 的 JSONL 输出"""
        lines = raw_output.strip().split("\n")
        messages = []
        errors = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                event_type = data.get("type", "")

                # 提取消息内容
                if event_type == "item.completed":
                    item = data.get("item", {})
                    item_type = item.get("type", "")
                    if item_type == "agent_message":
                        text = item.get("text", "")
                        if text:
                            messages.append(text)
                elif event_type == "message":
                    content = data.get("content", "")
                    if content:
                        messages.append(content)
                elif event_type == "response":
                    text = data.get("text", "") or data.get("content", "")
                    if text:
                        messages.append(text)
                elif event_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    errors.append(error_msg)
            except json.JSONDecodeError:
                # 非 JSON 行直接作为输出
                if line and not line.startswith("{"):
                    messages.append(line)

        # 如果有错误，附加到输出中
        if errors:
            messages.append(f"[Errors: {'; '.join(errors)}]")

        result = "\n".join(messages).strip()
        return result if result else raw_output

    async def _run_cli(
        self,
        tool: str,
        prompt: str,
        cwd: str = ".",
    ) -> CLIResult:
        """执行单个 CLI 命令"""
        start_time = time.time()
        last_error = ""

        # Windows 命令行长度限制约 8192 字符
        # 长提示需要通过 stdin 传递
        USE_STDIN_THRESHOLD = 4000
        use_stdin = len(prompt) > USE_STDIN_THRESHOLD

        for attempt in range(self.config.max_retries):
            try:
                # 获取工具的完整路径
                tool_path = self._get_tool_path(tool)

                # 使用列表形式，安全且跨平台
                if tool == "claude":
                    if use_stdin:
                        # 长提示通过 stdin 传递
                        cmd = [tool_path, "-p", "-", "--output-format", "json"]
                    else:
                        cmd = [tool_path, "-p", prompt, "--output-format", "json"]
                else:
                    # 使用 codex exec 命令进行非交互式运行
                    if use_stdin:
                        cmd = [
                            tool_path, "exec", "-",
                            "--json",
                            "-s", "read-only",
                            "--dangerously-bypass-approvals-and-sandbox",
                            "--ephemeral",
                        ]
                    else:
                        cmd = [
                            tool_path, "exec", prompt,
                            "--json",
                            "-s", "read-only",
                            "--dangerously-bypass-approvals-and-sandbox",
                            "--ephemeral",
                        ]

                # 使用 asyncio.create_subprocess_exec 替代 subprocess.run
                # 避免阻塞事件循环
                stdin_data = prompt.encode("utf-8") if use_stdin else None
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=cwd,
                    stdin=asyncio.subprocess.PIPE if use_stdin else None,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(input=stdin_data),
                        timeout=self.config.timeout,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    raise

                duration = time.time() - start_time
                raw_output = stdout.decode("utf-8", errors="replace")
                raw_error = stderr.decode("utf-8", errors="replace")

                # 解析输出
                output = self._parse_output(tool, raw_output)

                if process.returncode == 0:
                    return CLIResult(
                        tool=tool,
                        success=True,
                        output=output,
                        duration=duration,
                        retries=attempt,
                    )
                else:
                    # 即使返回非零退出码，如果有输出也尝试使用
                    if output and output.strip():
                        return CLIResult(
                            tool=tool,
                            success=True,
                            output=output,
                            duration=duration,
                            retries=attempt,
                        )
                    last_error = raw_error or raw_output
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # 指数退避

            except asyncio.TimeoutError:
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

    async def run_tool(
        self,
        tool: str,
        prompt: str,
        cwd: str = ".",
    ) -> str:
        """执行单个工具并返回输出"""
        result = await self._run_cli(tool, prompt, cwd)
        if result.success:
            return result.output
        else:
            raise RuntimeError(f"{tool} error: {result.error}")

    async def run_single(
        self,
        tool: str,
        prompt: str,
        cwd: str = ".",
    ) -> CLIResult:
        """执行单个工具并返回完整结果"""
        return await self._run_cli(tool, prompt, cwd)

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
