# AI Duet

Claude + Codex 双 AI 协作工具

让 Claude Code 和 Codex 在任何项目中互相协作，提高代码质量。

## ✨ 功能

- 🔍 **代码审计** - 两个 AI 互相审查代码
- 💬 **技术讨论** - 多轮对话，达成共识
- 👥 **协作编码** - 智能分工，各自编写
- ⚡ **并行执行** - 性能提升 2x
- 🔧 **Git 集成** - 自动生成 commit message
- 💾 **会话持久化** - 结果可复用

## 📦 安装

```bash
git clone https://github.com/yourusername/ai-duet.git
cd ai-duet
pip install -e .
```

### 前置要求

```bash
npm install -g @anthropic-ai/claude-code
npm install -g @openai/codex
```

## 🚀 使用

### 命令速查

```bash
duet r [目标]     # 审计代码
duet r -g         # 审计 git diff
duet d "话题"     # 技术讨论
duet p "任务"     # 协作编码
duet c            # 生成 commit message
duet s            # 查看状态
duet h            # 查看历史
```

### 示例

```bash
# 审计当前目录
duet r .

# 审计特定文件
duet r src/main.py

# 审计 git staged changes
duet r -g

# 讨论架构选择
duet d "微服务还是单体？"

# 协作编写功能
duet p "实现用户认证"

# 自动生成 commit message
duet c

# 查看状态
duet s

# 查看历史
duet h
```

## 📋 命令说明

| 命令 | 说明 | 参数 |
|------|------|------|
| `r` | 审计代码 | `[目标]` 文件/目录，默认当前目录 |
| `d` | 技术讨论 | `"话题"` 必填 |
| `p` | 协作编码 | `"任务"` 必填 |
| `c` | 生成 commit | 无参数 |
| `s` | 查看状态 | 无参数 |
| `h` | 查看历史 | 无参数 |

## ⚙️ 配置

### 环境变量

```bash
# 并行执行
export DUET_PARALLEL=true

# 超时时间
export DUET_TIMEOUT=120

# 保存结果
export DUET_SAVE=true

# 输出目录
export DUET_OUTPUT_DIR=./output
```

### 配置文件

`~/.ai-duet/config.json`

```json
{
  "output": {
    "format": "rich",
    "save_results": true
  },
  "execution": {
    "parallel": true,
    "timeout": 120
  },
  "git": {
    "commit_style": "conventional"
  }
}
```

## 🎯 工作流程

### 审计模式

```
Claude 审查 ──┐
              ├→ 比较 → 最终建议
Codex 审查 ──┘
```

### 讨论模式

```
Claude 观点 ──┐
              ├→ 多轮讨论 → 总结
Codex 观点 ──┘
```

### 协作模式

```
分工方案 → Claude 编写 ──┐
                         ├→ 审查 → 合并
           Codex 编写 ──┘
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
