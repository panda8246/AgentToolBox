# Goal Framework

跨 Agent 复用的轻量项目目标框架。核心逻辑由 Python 实现；PowerShell 与 POSIX shell 提供简单的交互式入口。

## 日常使用

进入目标项目根目录后运行。启动器会显示数字菜单，只需选择 Agent：自动检测、Codex、Cursor、OpenCode，或仅创建框架。

```powershell
# Windows PowerShell
& 'E:\AgentToolBox\GoalFramework\bin\goal-init.ps1'

# Windows 命令提示符
E:\AgentToolBox\GoalFramework\bin\goal-init.cmd
```

```sh
# macOS / Linux
/path/to/GoalFramework/bin/goal-init
```

启动器默认使用当前目录作为项目目录，且不要求记忆参数。

## 高级用法

Python 核心保留完整参数接口，适合自动化或明确指定项目目录：

```sh
python3 /path/to/GoalFramework/bin/goal-init.py --agent opencode
python3 /path/to/GoalFramework/bin/goal-init.py --project-path /path/to/project --dry-run
python3 /path/to/GoalFramework/bin/goal-init.py --skip-native-init --no-agent-prompt
```

需要 Python 3.10+。

## 行为

如果项目根目录没有 `AGENTS.md`，命令会先运行选定 Agent 的项目上下文初始化：OpenCode 优先尝试原生 `/init`；Codex 和 Cursor 使用等价的“分析项目并创建 `AGENTS.md`”提示，因为没有可由外部脚本稳定调用的通用 `/init`。

随后命令会加入 Goal Framework：创建框架目录与模板，并向 `AGENTS.md` 合并带 `GOAL-FRAMEWORK` 标记的受管区块。已有项目规则与已存在的框架文件默认保留；只有 Python 高级入口的 `--force` 才覆盖模板文件。

## 目标文件命名

活跃目标在 `goals/active/` 中使用 `YYYY-MM-DD-short-title.md`：创建日期 + 小写英文短标题 + 连字符，例如 `2026-08-12-time-tracker-v01.md`。归档时先将文件重命名为“归档日期 + 原短标题”，再移至 `goals/archive/`；例如 `2026-09-01-time-tracker-v01.md`。

## 写入的项目结构

```text
AGENTS.md                      # 原有上下文 + Goal Framework 受管区块
docs/PROJECT.md                # 长期愿景、边界、原则与阶段方向
docs/CURRENT.md                # 唯一全局当前状态
goals/GOAL-TEMPLATE.md         # 交付型 / 探索型目标模板
goals/active/
goals/archive/
GOAL-FRAMEWORK-PROMPT.md        # 初始化后供 Agent 执行的系统提示词
```


