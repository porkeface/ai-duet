"""
会话持久化

保存审计结果、讨论记录、协作历史。
"""

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import SESSIONS_DIR, OutputConfig
from .protocol import CollabSession, CollabMessage


class SessionStorage:
    """会话存储"""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or SESSIONS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.base_dir / f"{session_id}.json"

    def save_session(self, session: CollabSession) -> Path:
        """保存会话"""
        path = self._get_session_path(session.id)
        data = {
            "id": session.id,
            "mode": session.mode.value,
            "status": session.status,
            "started_at": session.started_at.isoformat(),
            "project_dir": session.project_dir,
            "messages": [
                {
                    "id": msg.id,
                    "timestamp": msg.timestamp.isoformat(),
                    "sender": msg.sender,
                    "mode": msg.mode.value,
                    "content": msg.content,
                    "metadata": msg.metadata,
                }
                for msg in session.messages
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return path

    def load_session(self, session_id: str) -> CollabSession | None:
        """加载会话"""
        path = self._get_session_path(session_id)
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = [
            CollabMessage(
                id=msg["id"],
                timestamp=datetime.fromisoformat(msg["timestamp"]),
                sender=msg["sender"],
                mode=msg["mode"],
                content=msg["content"],
                metadata=msg.get("metadata", {}),
            )
            for msg in data.get("messages", [])
        ]

        return CollabSession(
            id=data["id"],
            mode=data["mode"],
            status=data["status"],
            started_at=datetime.fromisoformat(data["started_at"]),
            messages=messages,
            project_dir=data.get("project_dir", ""),
        )

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """列出所有会话"""
        sessions = []
        for path in sorted(self.base_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data["id"],
                    "mode": data["mode"],
                    "status": data["status"],
                    "started_at": data["started_at"],
                    "message_count": len(data.get("messages", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False


class ResultExporter:
    """结果导出器"""

    def __init__(self, output_config: OutputConfig):
        self.output_dir = Path(output_config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_json(self, session: CollabSession) -> Path:
        """导出为 JSON"""
        filename = f"{session.id}_{session.mode.value}.json"
        path = self.output_dir / filename

        data = {
            "session": {
                "id": session.id,
                "mode": session.mode.value,
                "status": session.status,
                "started_at": session.started_at.isoformat(),
                "project_dir": session.project_dir,
            },
            "messages": [
                {
                    "id": msg.id,
                    "timestamp": msg.timestamp.isoformat(),
                    "sender": msg.sender,
                    "content": msg.content,
                }
                for msg in session.messages
            ],
            "exported_at": datetime.now().isoformat(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return path

    def export_markdown(self, session: CollabSession) -> Path:
        """导出为 Markdown"""
        filename = f"{session.id}_{session.mode.value}.md"
        path = self.output_dir / filename

        lines = [
            f"# {session.mode.value.title()} Session",
            f"",
            f"**Session ID:** {session.id}",
            f"**Status:** {session.status}",
            f"**Started:** {session.started_at.isoformat()}",
            f"**Project:** {session.project_dir}",
            f"",
            f"## Messages",
            f"",
        ]

        for msg in session.messages:
            lines.append(f"### {msg.sender} ({msg.timestamp.isoformat()})")
            lines.append(f"")
            if isinstance(msg.content, dict):
                if "raw" in msg.content:
                    lines.append(f"```")
                    lines.append(msg.content["raw"])
                    lines.append(f"```")
                else:
                    lines.append(f"```json")
                    lines.append(json.dumps(msg.content, indent=2, ensure_ascii=False))
                    lines.append(f"```")
            else:
                lines.append(str(msg.content))
            lines.append(f"")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return path

    def export_html(self, session: CollabSession) -> Path:
        """导出为 HTML"""
        filename = f"{session.id}_{session.mode.value}.html"
        path = self.output_dir / filename

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{session.mode.value.title()} Session - {session.id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .message {{ border-left: 4px solid #007bff; padding: 15px; margin: 10px 0; background: #f9f9f9; }}
        .claude {{ border-color: #4CAF50; }}
        .codex {{ border-color: #FF9800; }}
        .user {{ border-color: #9C27B0; }}
        pre {{ background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 4px; overflow-x: auto; }}
        .meta {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{session.mode.value.title()} Session</h1>
        <p><strong>ID:</strong> {session.id}</p>
        <p><strong>Status:</strong> {session.status}</p>
        <p><strong>Started:</strong> {session.started_at.isoformat()}</p>
        <p><strong>Project:</strong> {session.project_dir}</p>
    </div>
    <h2>Messages</h2>
"""

        for msg in session.messages:
            content = ""
            if isinstance(msg.content, dict):
                if "raw" in msg.content:
                    content = f"<pre>{html.escape(str(msg.content['raw']))}</pre>"
                else:
                    content = f"<pre>{html.escape(json.dumps(msg.content, indent=2, ensure_ascii=False))}</pre>"
            else:
                content = f"<p>{html.escape(str(msg.content))}</p>"

            html_content += f"""
    <div class="message {msg.sender}">
        <div class="meta">{msg.sender} - {msg.timestamp.isoformat()}</div>
        {content}
    </div>
"""

        html_content += """
</body>
</html>
"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return path
