"""
CLI 入口 - 简洁版

简化命令，减少参数，提供默认值。
"""

import asyncio
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from .cli_engine import CLIEngine
from .config import AppConfig, get_config, CONFIG_FILE
from .persistence import SessionStorage
from .git_integration import GitIntegration
from .formatter import OutputFormatter

console = Console()
fmt = OutputFormatter()


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx):
    """Claude + Codex 协作工具"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# 简化命令：用 2-3 个字母的别名
@cli.command()
@click.argument("target", default=".")
@click.option("--git", "-g", is_flag=True, help="审计 git diff")
def r(target, git):
    """审计代码"""
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
    """技术讨论"""
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
    """协作编码"""
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
    """查看状态"""
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


def _show_result(session, mode):
    """显示结果"""
    fmt.print_success(f"{mode}完成！")
    if session.messages:
        last = session.messages[-1]
        if isinstance(last.content, dict) and "raw" in last.content:
            console.print(Panel(Markdown(last.content["raw"]), title="📋 结果"))


def _check_tool(name, cmd):
    """检查工具状态"""
    import subprocess
    try:
        # Windows 上需要 shell=True 才能找到 npm 全局安装的命令
        r = subprocess.run(
            f"{cmd} --version",
            capture_output=True,
            text=True,
            timeout=10,
            shell=True,
        )
        if r.returncode == 0:
            version = r.stdout.strip().split('\n')[0]  # 只取第一行
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
