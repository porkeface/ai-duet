"""
CLI 入口 - 简洁版

简化命令，减少参数，提供默认值。
"""

import asyncio
import sys

import click

from . import __version__
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from .cli_engine import CLIEngine
from .config import AppConfig, get_config, CONFIG_FILE
from .persistence import SessionStorage
from .git_integration import GitIntegration
from .formatter import OutputFormatter
from .server import DuetServer, DuetClient, Message
from .tui import run_tui

console = Console()
fmt = OutputFormatter()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx):
    """Claude + Codex 实时协作工具"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ==================== 服务器命令 ====================

@cli.command()
@click.option("--port", "-p", default=8765, help="服务器端口")
def daemon(port):
    """启动 WebSocket 服务器"""
    import logging
    logging.basicConfig(level=logging.INFO)

    server = DuetServer(port=port)
    fmt.print_success(f"启动服务器 ws://localhost:{port}")
    fmt.print_info("按 Ctrl+C 停止")

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        fmt.print_info("服务器已停止")


@cli.command()
@click.argument("agent")
@click.argument("question")
@click.option("--timeout", "-t", default=60, help="超时时间（秒）")
def ask(agent, question, timeout):
    """向 Agent 发送问题

    AGENT: 目标 agent (claude/codex)
    QUESTION: 问题内容
    """
    async def _ask():
        client = DuetClient("user")
        try:
            await client.connect()
            fmt.print_info(f"已连接到服务器")

            fmt.print_info(f"向 {agent} 发送问题...")
            answer = await client.ask(agent, question, timeout=timeout)

            console.print(Panel(
                Markdown(answer),
                title=f"💬 {agent} 的回答",
            ))
        except TimeoutError:
            fmt.print_error(f"{agent} 超时未响应")
            sys.exit(1)
        except ConnectionError as e:
            fmt.print_error(f"连接失败: {e}")
            fmt.print_info("请先启动服务器: duet daemon")
            sys.exit(1)
        finally:
            await client.disconnect()

    asyncio.run(_ask())


@cli.command()
@click.argument("agent")
@click.argument("file_path")
def review(agent, file_path):
    """请求 Agent 审查代码

    AGENT: 目标 agent (claude/codex)
    FILE_PATH: 文件路径
    """
    async def _review():
        client = DuetClient("user")
        try:
            await client.connect()
            fmt.print_info(f"已连接到服务器")

            # 读取文件内容
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
            except FileNotFoundError:
                fmt.print_error(f"文件不存在: {file_path}")
                sys.exit(1)

            question = f"请审查以下代码（{file_path}）：\n\n```\n{code}\n```"
            fmt.print_info(f"向 {agent} 发送审查请求...")

            answer = await client.ask(agent, question, timeout=120)

            console.print(Panel(
                Markdown(answer),
                title=f"🔍 {agent} 的审查结果",
            ))
        except TimeoutError:
            fmt.print_error(f"{agent} 超时未响应")
            sys.exit(1)
        except ConnectionError as e:
            fmt.print_error(f"连接失败: {e}")
            fmt.print_info("请先启动服务器: duet daemon")
            sys.exit(1)
        finally:
            await client.disconnect()

    asyncio.run(_review())


@cli.command()
def status():
    """查看服务器状态"""
    async def _status():
        client = DuetClient("status-check")
        try:
            await client.connect()
            fmt.print_success("服务器运行中")

            # 获取状态
            response = await client.ask("server", "status", timeout=5.0)

            # 显示状态
            if isinstance(response, dict):
                table = Table(title="📊 服务器状态")
                table.add_column("指标", style="cyan")
                table.add_column("值", style="green")

                for key, value in response.items():
                    table.add_row(key, str(value))
                console.print(table)
            else:
                console.print(Panel(str(response), title="📊 服务器状态"))

        except TimeoutError:
            fmt.print_error("服务器响应超时")
        except ConnectionError:
            fmt.print_error("服务器未运行")
            fmt.print_info("启动服务器: duet daemon")
        except Exception as e:
            fmt.print_error(f"错误: {e}")
        finally:
            await client.disconnect()

    asyncio.run(_status())


# ==================== 原有命令 ====================

@cli.command()
@click.argument("target", default=".")
@click.option("--git", "-g", is_flag=True, help="审计 git diff")
def r(target, git):
    """审计代码（本地模式）"""
    engine = CLIEngine(".")
    try:
        if git:
            session = asyncio.run(engine.run_git_review())
        else:
            session = asyncio.run(engine.run_review(target))
        _show_result(session, "审计")
    except Exception as e:
        fmt.print_error(str(e))
        sys.exit(1)


@cli.command()
@click.argument("topic")
@click.option("--n", "-n", default=3, help="讨论轮数")
def d(topic, n):
    """技术讨论（本地模式）"""
    engine = CLIEngine(".")
    try:
        session = asyncio.run(engine.run_discuss(topic, rounds=n))
        _show_result(session, "讨论")
    except Exception as e:
        fmt.print_error(str(e))
        sys.exit(1)


@cli.command()
@click.argument("task")
def p(task):
    """协作编码（本地模式）"""
    engine = CLIEngine(".")
    try:
        session = asyncio.run(engine.run_pair(task))
        _show_result(session, "协作")
    except Exception as e:
        fmt.print_error(str(e))
        sys.exit(1)


@cli.command()
def c():
    """生成 commit message"""
    engine = CLIEngine(".")
    try:
        msg = asyncio.run(engine.run_git_commit())
        console.print(Panel(Markdown(msg), title="📝 Commit Message"))
        if click.confirm("提交？"):
            git = GitIntegration(".")
            git.commit(msg)
            fmt.print_success("已提交")
    except Exception as e:
        fmt.print_error(str(e))
        sys.exit(1)


@cli.command()
def s():
    """查看工具状态"""
    _check_tool("Claude", "claude")
    _check_tool("Codex", "codex")
    _check_tool("Git", "git")


@cli.command()
def h():
    """查看历史"""
    storage = SessionStorage()
    sessions = storage.list_sessions(10)
    if not sessions:
        fmt.print_info("无历史记录")
        return

    table = Table(title="📚 历史记录")
    table.add_column("ID", style="cyan")
    table.add_column("模式", style="green")
    table.add_column("状态", style="yellow")
    table.add_column("时间", style="dim")

    for s in sessions:
        table.add_row(s["id"], s["mode"], s["status"], s["started_at"])
    console.print(table)


@cli.command()
def tui():
    """启动终端 UI 实时协作"""
    fmt.print_info("启动 AI Duet TUI...")
    fmt.print_info("按 Ctrl+C 或输入 'quit' 退出")
    try:
        run_tui()
    except KeyboardInterrupt:
        fmt.print_info("已退出")
    except Exception as e:
        fmt.print_error(f"TUI 错误: {e}")
        sys.exit(1)


def _show_result(session, mode):
    """显示结果"""
    fmt.print_success(f"{mode}完成！")

    if not session.messages:
        return

    # 显示所有消息
    for i, msg in enumerate(session.messages):
        if not isinstance(msg.content, dict):
            continue

        # 确定标题
        sender = msg.sender
        if sender == "claude":
            title = "🔵 Claude"
            color = "blue"
        elif sender == "codex":
            title = "🔴 Codex"
            color = "red"
        else:
            title = "📋 总结"
            color = "green"

        # 显示内容
        if "raw" in msg.content:
            console.print(Panel(
                Markdown(msg.content["raw"]),
                title=f"{title} ({msg.id})",
                border_style=color,
            ))


def _check_tool(name, cmd):
    """检查工具状态"""
    import subprocess
    try:
        r = subprocess.run(
            f"{cmd} --version",
            capture_output=True,
            text=True,
            timeout=10,
            shell=True,
        )
        if r.returncode == 0:
            version = r.stdout.strip().split('\n')[0]
            console.print(f"[green]✓[/green] {name}: {version}")
        else:
            console.print(f"[red]✗[/red] {name}: 错误")
    except FileNotFoundError:
        console.print(f"[red]✗[/red] {name}: 未安装")
    except subprocess.TimeoutExpired:
        console.print(f"[yellow]?[/yellow] {name}: 超时")
    except Exception as e:
        console.print(f"[red]✗[/red] {name}: {e}")


def main():
    """主入口"""
    cli()


if __name__ == "__main__":
    main()
