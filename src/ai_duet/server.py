"""
WebSocket 服务器

实现 Claude 和 Codex 之间的实时通信。
"""

import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from .protocol import CollabMessage, CollabMode

logger = logging.getLogger(__name__)


class Message:
    """消息定义"""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        msg_type: str,
        content: Any,
        request_id: str | None = None,
    ):
        self.id = str(uuid.uuid4())[:8]
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.msg_type = msg_type  # ask, response, review, error
        self.content = content
        self.request_id = request_id
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from": self.from_agent,
            "to": self.to_agent,
            "type": self.msg_type,
            "content": self.content,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "Message":
        d = json.loads(data)
        msg = cls(
            from_agent=d["from"],
            to_agent=d["to"],
            msg_type=d["type"],
            content=d["content"],
            request_id=d.get("request_id"),
        )
        msg.id = d.get("id", msg.id)
        msg.timestamp = d.get("timestamp", msg.timestamp)
        return msg


class DuetServer:
    """AI Duet WebSocket 服务器"""

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: dict[str, ServerConnection] = {}  # agent_id -> websocket
        self.message_history: deque[Message] = deque(maxlen=10000)  # 限制最大长度

    async def handler(self, websocket: ServerConnection):
        """处理 WebSocket 连接"""
        agent_id = None
        try:
            # 等待注册消息
            async for message in websocket:
                try:
                    msg = Message.from_json(message)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Invalid message: {e}")
                    continue

                # 注册消息
                if msg.msg_type == "register":
                    agent_id = msg.from_agent
                    self.clients[agent_id] = websocket
                    logger.info(f"Agent registered: {agent_id}")

                    # 发送确认
                    ack = Message(
                        from_agent="server",
                        to_agent=agent_id,
                        msg_type="register_ack",
                        content={"status": "ok", "agent_id": agent_id},
                    )
                    await websocket.send(ack.to_json())
                    continue

                # 服务器状态查询（支持 "status" 和 "ask" 两种消息类型）
                if msg.to_agent == "server" and msg.msg_type in ("status", "ask"):
                    status_msg = Message(
                        from_agent="server",
                        to_agent=msg.from_agent,
                        msg_type="response",
                        content=self.get_status(),
                        request_id=msg.id,
                    )
                    await websocket.send(status_msg.to_json())
                    continue

                # 普通消息
                logger.info(f"Message: {msg.from_agent} -> {msg.to_agent} ({msg.msg_type})")
                self.message_history.append(msg)

                # 转发消息
                if msg.to_agent in self.clients:
                    target_ws = self.clients[msg.to_agent]
                    try:
                        await target_ws.send(msg.to_json())
                        logger.info(f"Forwarded to {msg.to_agent}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.error(f"Agent {msg.to_agent} disconnected")
                        # 发送错误回复
                        error_msg = Message(
                            from_agent="server",
                            to_agent=msg.from_agent,
                            msg_type="error",
                            content={"error": f"Agent {msg.to_agent} is offline"},
                            request_id=msg.id,
                        )
                        await websocket.send(error_msg.to_json())
                else:
                    # 目标不在线
                    error_msg = Message(
                        from_agent="server",
                        to_agent=msg.from_agent,
                        msg_type="error",
                        content={"error": f"Agent {msg.to_agent} not found"},
                        request_id=msg.id,
                    )
                    await websocket.send(error_msg.to_json())

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed: {agent_id}")
        finally:
            # 清理
            if agent_id and agent_id in self.clients:
                del self.clients[agent_id]
                logger.info(f"Agent unregistered: {agent_id}")

    async def start(self):
        """启动服务器"""
        logger.info(f"Starting WebSocket server on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port) as server:
            await server.serve_forever()

    def get_status(self) -> dict:
        """获取服务器状态"""
        return {
            "host": self.host,
            "port": self.port,
            "clients": list(self.clients.keys()),
            "message_count": len(self.message_history),
        }


class DuetClient:
    """AI Duet 客户端"""

    def __init__(self, agent_id: str, server_url: str = "ws://localhost:8765"):
        self.agent_id = agent_id
        self.server_url = server_url
        self.websocket: ServerConnection | None = None
        self.pending_requests: dict[str, asyncio.Future] = {}
        self._receive_task: asyncio.Task | None = None

    async def connect(self):
        """连接到服务器"""
        self.websocket = await websockets.connect(self.server_url)

        # 发送注册消息
        register_msg = Message(
            from_agent=self.agent_id,
            to_agent="server",
            msg_type="register",
            content={"agent_id": self.agent_id},
        )
        await self.websocket.send(register_msg.to_json())

        # 等待确认
        response = await self.websocket.recv()
        ack = Message.from_json(response)
        if ack.msg_type != "register_ack":
            raise ConnectionError(f"Registration failed: {ack.content}")

        logger.info(f"Connected as {self.agent_id}")

        # 启动接收任务
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def disconnect(self):
        """断开连接"""
        if self._receive_task:
            self._receive_task.cancel()
        if self.websocket:
            await self.websocket.close()

    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message in self.websocket:
                try:
                    msg = Message.from_json(message)
                    logger.info(f"Received: {msg.from_agent} -> {msg.to_agent} ({msg.msg_type})")

                    # 如果是响应，完成等待
                    if msg.msg_type == "response" and msg.request_id:
                        if msg.request_id in self.pending_requests:
                            self.pending_requests[msg.request_id].set_result(msg)
                            del self.pending_requests[msg.request_id]

                    # 调用回调
                    if hasattr(self, '_on_message'):
                        await self._on_message(msg)

                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Invalid message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")

    async def send(self, to_agent: str, msg_type: str, content: Any) -> str:
        """发送消息"""
        if not self.websocket:
            raise ConnectionError("Not connected")

        msg = Message(
            from_agent=self.agent_id,
            to_agent=to_agent,
            msg_type=msg_type,
            content=content,
        )
        await self.websocket.send(msg.to_json())
        return msg.id

    async def ask(self, to_agent: str, question: str, timeout: float = 60.0) -> str:
        """发送问题并等待响应"""
        if not self.websocket:
            raise ConnectionError("Not connected")

        msg = Message(
            from_agent=self.agent_id,
            to_agent=to_agent,
            msg_type="ask",
            content={"question": question},
        )

        # 创建 Future
        future = asyncio.get_running_loop().create_future()
        self.pending_requests[msg.id] = future

        # 发送消息
        await self.websocket.send(msg.to_json())
        logger.info(f"Asked {to_agent}: {question[:50]}...")

        # 等待响应
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response.content.get("answer", str(response.content))
        except asyncio.TimeoutError:
            del self.pending_requests[msg.id]
            raise TimeoutError(f"No response from {to_agent} within {timeout}s")

    def on_message(self, callback):
        """设置消息回调"""
        self._on_message = callback
