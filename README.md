# AI Duet

Claude + Codex 实时协作工具

让 Claude Code 和 Codex 能够实时交流、互相审查、协作编写代码。

## ✨ 功能

- 🔍 **实时审查** - Claude 和 Codex 互相审查代码
- 💬 **实时交流** - 通过 WebSocket 实时通信
- 👥 **协作编码** - 智能分工，各自编写
- 🔧 **Git 集成** - 自动生成 commit message
- 💾 **会话持久化** - 结果可复用

## 📦 安装

```bash
git clone https://github.com/porkeface/ai-duet.git
cd ai-duet
uv pip install -e .
```

### 前置要求

```bash
npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex
```

## 🚀 使用

### 方式 1：实时协作模式（推荐）

```bash
# 1. 启动 WebSocket 服务器
duet daemon

# 2. 在另一个终端，向 Claude 发送问题
duet ask claude "如何优化这个函数？"

# 3. 向 Codex 发送审查请求
duet review codex src/main.py

# 4. 查看服务器状态
duet status
```

### 方式 2：本地模式

```bash
# 审计代码
duet r src/main.py

# 技术讨论
duet d "微服务还是单体？"

# 协作编码
duet p "实现用户认证"

# 生成 commit message
duet c
```

## 📋 命令说明

### 实时协作命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `daemon` | 启动 WebSocket 服务器 | `duet daemon` |
| `ask` | 向 Agent 发送问题 | `duet ask claude "问题"` |
| `review` | 请求 Agent 审查代码 | `duet review codex src/main.py` |
| `status` | 查看服务器状态 | `duet status` |

### 本地模式命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `r` | 审计代码 | `duet r src/main.py` |
| `d` | 技术讨论 | `duet d "话题"` |
| `p` | 协作编码 | `duet p "任务"` |
| `c` | 生成 commit | `duet c` |
| `s` | 查看工具状态 | `duet s` |
| `h` | 查看历史 | `duet h` |

## 🎯 工作流程

### 实时协作流程

```
1. 启动服务器
   duet daemon

2. 在 Claude Code 中写代码
   claude -p "实现用户登录功能"

3. 写完后，请求 Codex 审查
   duet ask codex "审查刚才的代码"

4. Codex 返回审查结果
   Claude 看到结果，继续修改

5. 重复直到满意
```

### 本地模式流程

```
1. duet d "讨论方案"     # 技术讨论
2. duet p "实现功能"     # 协作编码
3. duet r src/xxx.py     # 代码审查
4. duet c                # 生成 commit
5. git push              # 提交代码
```

## ⚙️ 配置

### 环境变量

```bash
# 服务器端口
export DUET_PORT=8765

# 超时时间
export DUET_TIMEOUT=60
```

### 配置文件

`~/.ai-duet/config.json`

```json
{
  "server": {
    "host": "localhost",
    "port": 8765
  },
  "timeout": 60
}
```

## 🧪 开发

```bash
# 运行测试
uv run pytest tests/ -v

# 格式化代码
ruff format src/ tests/
```

## 📁 项目结构

```
ai-duet/
├── src/ai_duet/
│   ├── cli.py               # CLI 命令
│   ├── cli_engine.py        # 执行引擎
│   ├── server.py            # WebSocket 服务器
│   ├── protocol.py          # 消息协议
│   ├── config.py            # 配置管理
│   ├── parallel_engine.py   # 并行执行
│   ├── persistence.py       # 会话持久化
│   ├── git_integration.py   # Git 集成
│   └── formatter.py         # 输出格式化
├── tests/
└── README.md
```

## 📄 许可证

MIT License
