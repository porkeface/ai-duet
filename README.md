# AI Duet

Claude + Codex 实时协作工具

让 Claude Code 和 Codex CLI 能够实时交流、互相审查、协作编写代码。

## ✨ 功能

- 🖥️ **终端 UI** - 分屏显示 Claude 和 Codex 的实时回答
- 🔍 **代码审计** - 两个 AI 同时审查代码，交叉验证
- 💬 **技术讨论** - 从不同角度分析技术问题
- 👥 **协作编码** - 智能分工，各自编写后合并
- 🔧 **Git 集成** - 自动生成 commit message
- 💾 **会话持久化** - 结果可导出为 JSON/Markdown/HTML

## 📦 安装

### 前置要求

```bash
# 安装 Claude Code CLI
npm install -g @anthropic-ai/claude-code

# 安装 Codex CLI
npm install -g @openai/codex
```

### 安装 AI Duet

```bash
git clone https://github.com/porkeface/ai-duet.git
cd ai-duet

# 开发模式安装
uv pip install -e .

# 或全局安装
pip install -e .
```

## 🚀 使用

### 终端 UI（推荐）

```bash
# 启动终端 UI
duet tui

# 在 UI 中输入问题
# → Claude 和 Codex 同时回答
# → 分屏显示，实时查看
# → 快捷键：Ctrl+L 清屏，Ctrl+P 命令面板
```

### 代码审计

```bash
# 审计单个文件
duet r src/main.py

# 审计整个目录
duet r src/

# 审计 Git diff
duet r --git
```

### 技术讨论

```bash
# 从不同角度讨论技术问题
duet d "微服务还是单体架构？"

# 指定讨论轮数
duet d "如何优化数据库查询？" --n 5
```

### 协作编码

```bash
# 两个 AI 协作完成功能
duet p "实现用户认证"

# 查看两个 AI 的代码差异和合并结果
```

### Git 集成

```bash
# 自动生成 commit message
duet c
```

### 工具状态

```bash
# 检查 Claude、Codex、Git 是否可用
duet s
```

### 历史记录

```bash
# 查看历史会话
duet h
```

## 📋 命令一览

| 命令 | 说明 | 示例 |
|------|------|------|
| `tui` | 启动终端 UI | `duet tui` |
| `r` | 审计代码 | `duet r src/main.py` |
| `d` | 技术讨论 | `duet d "话题"` |
| `p` | 协作编码 | `duet p "任务"` |
| `c` | 生成 commit | `duet c` |
| `s` | 查看工具状态 | `duet s` |
| `h` | 查看历史 | `duet h` |

## 🎯 工作流程

### 代码审计流程

```
1. 写完代码后运行 duet r src/
2. Claude 和 Codex 同时审查
3. 查看两个 AI 的审查结果
4. 根据建议修改代码
5. duet c 生成 commit message
```

### 技术讨论流程

```
1. duet d "技术问题"
2. Claude 和 Codex 从不同角度分析
3. 查看双方的共识和分歧
4. 获取最终建议
```

### 协作编码流程

```
1. duet p "实现功能描述"
2. Claude 和 Codex 各自实现
3. 查看两个实现的差异
4. 获取合并后的最终代码
```

## ⚙️ 配置

### 环境变量

```bash
# 执行超时时间（秒）
export COLLAB_TIMEOUT=120

# 最大重试次数
export COLLAB_MAX_RETRIES=3

# 输出格式
export COLLAB_OUTPUT_FORMAT=markdown

# 是否保存结果
export COLLAB_SAVE=true
```

### 配置文件

`~/.ai-duet/config.json`

```json
{
  "output": {
    "format": "markdown",
    "color": true,
    "verbose": false,
    "save_results": true
  },
  "execution": {
    "parallel": true,
    "timeout": 120,
    "max_retries": 3
  },
  "git": {
    "auto_diff": true,
    "generate_commit": true
  }
}
```

## 🧪 开发

```bash
# 运行测试
uv run pytest tests/ -v

# 格式化代码
ruff format src/ tests/

# 代码检查
ruff check src/ tests/
```

## 📁 项目结构

```
ai-duet/
├── src/ai_duet/
│   ├── cli.py               # CLI 命令入口
│   ├── cli_engine.py        # 核心执行引擎
│   ├── tui.py               # 终端 UI（Textual）
│   ├── server.py            # WebSocket 服务器
│   ├── protocol.py          # 消息协议定义
│   ├── config.py            # 配置管理
│   ├── parallel_engine.py   # 并行执行引擎
│   ├── persistence.py       # 会话持久化
│   ├── git_integration.py   # Git 集成
│   └── formatter.py         # 输出格式化
├── tests/
│   └── test_all.py          # 测试文件
├── pyproject.toml           # 项目配置
└── README.md
```

## 🔧 技术栈

- **Python 3.10+**
- **Click** - CLI 框架
- **Rich** - 终端美化输出
- **Textual** - 终端 UI 框架
- **Pydantic** - 数据验证
- **asyncio** - 异步并发
- **websockets** - WebSocket 通信

## 📄 许可证

MIT License

## 🔗 链接

- [GitHub](https://github.com/porkeface/ai-duet)
- [Issues](https://github.com/porkeface/ai-duet/issues)
