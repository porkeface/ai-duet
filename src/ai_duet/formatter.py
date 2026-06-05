"""
输出格式化器

使用 Rich 库美化输出。
"""

from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import OutputConfig


class OutputFormatter:
    """输出格式化器"""

    def __init__(self, config: OutputConfig | None = None):
        self.config = config or OutputConfig()
        self.console = Console(
            force_terminal=self.config.color,
            width=100,
        )

    def print_banner(self, mode: str, target: str):
        """打印模式横幅"""
        icons = {
            "review": "🔍",
            "discuss": "💬",
            "pair": "👥",
            "status": "📊",
            "commit": "📝",
        }
        icon = icons.get(mode, "🚀")

        self.console.print(Panel(
            f"[bold blue]{icon} {mode.upper()} Mode[/bold blue]\n"
            f"[dim]Target: {target}[/dim]",
            border_style="blue",
            expand=False,
        ))

    def print_success(self, message: str):
        """打印成功消息"""
        self.console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str):
        """打印错误消息"""
        self.console.print(f"[red]✗[/red] {message}")

    def print_warning(self, message: str):
        """打印警告消息"""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_info(self, message: str):
        """打印信息消息"""
        self.console.print(f"[blue]ℹ[/blue] {message}")

    def format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def print_summary(self, stats: dict[str, Any]):
        """打印执行摘要"""
        table = Table(
            title="📊 执行摘要",
            show_header=True,
            header_style="bold",
        )

        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")

        for key, value in stats.items():
            if isinstance(value, float):
                value = self.format_duration(value)
            table.add_row(key, str(value))

        self.console.print(table)
