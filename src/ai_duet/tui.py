"""AI Duet - Terminal UI for real-time Claude + Codex collaboration."""

import asyncio
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text
from rich.panel import Panel
from rich.console import Console

from .parallel_engine import ParallelEngine
from .config import get_config


class AgentPanel(Static):
    """Panel for displaying agent output."""

    agent_name: reactive[str] = reactive("")
    status: reactive[str] = reactive("idle")
    content: reactive[str] = reactive("")

    def __init__(self, agent_name: str, **kwargs):
        super().__init__(**kwargs)
        self.agent_name = agent_name
        self.content = f"[dim]等待 {agent_name} 开始工作...[/dim]"

    def render(self) -> Panel:
        status_icon = "🟢" if self.status == "working" else "⚪"
        title = f"{status_icon} {self.agent_name}"
        return Panel(
            self.content,
            title=title,
            border_style="blue" if self.status == "working" else "dim",
            padding=(1, 2),
        )

    def update_content(self, content: str, status: str = "working"):
        """Update panel content and status."""
        self.content = content
        self.status = status
        self.refresh()


class ChatLog(RichLog):
    """Chat log for conversation history."""

    def add_message(self, sender: str, content: str, style: str = ""):
        """Add a message to the chat log."""
        text = Text()
        text.append(f"{sender}: ", style="bold")
        text.append(content, style=style)
        self.write(text)


class DuetApp(App):
    """AI Duet Terminal UI Application."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
    }

    #agents-container {
        height: 70%;
        margin-bottom: 1;
    }

    #claude-panel {
        width: 50%;
        margin-right: 1;
    }

    #codex-panel {
        width: 50%;
    }

    #chat-container {
        height: 25%;
        margin-bottom: 1;
    }

    #chat-log {
        height: 100%;
    }

    #input-container {
        height: 5%;
        margin-bottom: 1;
    }

    #command-input {
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = get_config()
        self.engine = ParallelEngine(self.config.execution)
        self.claude_output = ""
        self.codex_output = ""

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Vertical(id="main-container"):
            # Agent panels
            with Horizontal(id="agents-container"):
                yield AgentPanel("Claude", id="claude-panel")
                yield AgentPanel("Codex", id="codex-panel")

            # Chat log
            with Vertical(id="chat-container"):
                yield ChatLog(id="chat-log", highlight=True, markup=True)

            # Input
            with Horizontal(id="input-container"):
                yield Input(
                    placeholder="输入问题或代码（输入 'quit' 退出）...",
                    id="command-input",
                )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app."""
        self.query_one("#chat-log").add_message(
            "System", "欢迎使用 AI Duet！输入问题开始协作。", "green"
        )
        self.query_one("#command-input").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input."""
        query = event.value.strip()
        if not query:
            return

        if query.lower() in ("quit", "exit", "q"):
            self.exit()
            return

        if query.lower() == "clear":
            self.action_clear()
            return

        # Clear input
        event.input.value = ""

        # Add to chat log
        self.query_one("#chat-log").add_message("You", query, "yellow")

        # Run agent collaboration
        self.run_worker(self.run_agents(query))

    async def run_agents(self, query: str) -> None:
        """Run Claude and Codex in parallel."""
        claude_panel = self.query_one("#claude-panel")
        codex_panel = self.query_one("#codex-panel")
        chat_log = self.query_one("#chat-log")

        # Update status
        claude_panel.update_content("[yellow]正在思考...[/yellow]", "working")
        codex_panel.update_content("[yellow]正在思考...[/yellow]", "working")

        # Run in parallel
        claude_task = asyncio.create_task(
            self.engine.run_tool("claude", query)
        )
        codex_task = asyncio.create_task(
            self.engine.run_tool("codex", query)
        )

        try:
            # Wait for Claude
            try:
                claude_result = await asyncio.wait_for(claude_task, timeout=120)
                claude_panel.update_content(claude_result, "idle")
                chat_log.add_message("Claude", claude_result[:200] + "..." if len(claude_result) > 200 else claude_result, "cyan")
            except asyncio.TimeoutError:
                claude_panel.update_content("[red]超时[/red]", "idle")
                chat_log.add_message("Claude", "响应超时", "red")
            except Exception as e:
                claude_panel.update_content(f"[red]错误: {e}[/red]", "idle")
                chat_log.add_message("Claude", f"错误: {e}", "red")

            # Wait for Codex
            try:
                codex_result = await asyncio.wait_for(codex_task, timeout=120)
                codex_panel.update_content(codex_result, "idle")
                chat_log.add_message("Codex", codex_result[:200] + "..." if len(codex_result) > 200 else codex_result, "green")
            except asyncio.TimeoutError:
                codex_panel.update_content("[red]超时[/red]", "idle")
                chat_log.add_message("Codex", "响应超时", "red")
            except Exception as e:
                codex_panel.update_content(f"[red]错误: {e}[/red]", "idle")
                chat_log.add_message("Codex", f"错误: {e}", "red")

            # Show comparison
            chat_log.add_message(
                "System",
                "两个 AI 已完成回答，请查看上方面板获取完整内容。",
                "yellow",
            )

        except Exception as e:
            chat_log.add_message("System", f"错误: {e}", "red")
            # 取消未完成的任务
            claude_task.cancel()
            codex_task.cancel()

    def action_clear(self) -> None:
        """Clear the chat log."""
        self.query_one("#chat-log").clear()
        self.query_one("#claude-panel").update_content(
            "[dim]等待 Claude 开始工作...[/dim]", "idle"
        )
        self.query_one("#codex-panel").update_content(
            "[dim]等待 Codex 开始工作...[/dim]", "idle"
        )


def run_tui():
    """Run the TUI application."""
    app = DuetApp()
    app.run()


if __name__ == "__main__":
    run_tui()
