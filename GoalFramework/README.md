# Goal Framework

跨 Agent 复用的轻量项目目标框架。Python 负责核心逻辑；PowerShell 与 POSIX shell 提供简单的交互式入口。

## 初始化

进入项目根目录后运行对应系统的 `goal-init`。菜单只需选择 Agent；推荐 OpenCode。框架会先确保 `AGENTS.md` 存在，再创建目标目录、模板和项目版本清单 `.goal-framework.json`。

```powershell
& 'E:\AgentToolBox\GoalFramework\bin\goal-init.ps1'
```

```sh
/path/to/GoalFramework/bin/goal-init
```

初始化时，Agent 使用内部提示填写 `docs/PROJECT.md` 和 `docs/CURRENT.md`；项目中不会保留 `GOAL-FRAMEWORK-PROMPT.md`。

## 更新已初始化项目

框架升级后，进入旧项目根目录运行 `goal-update`：

```powershell
& 'E:\AgentToolBox\GoalFramework\bin\goal-update.ps1'
```

```sh
/path/to/GoalFramework/bin/goal-update
```

它会读取 `.goal-framework.json`，显示从项目版本到当前框架版本之间的每一版变更与人工迁移提示，再等待确认。它自动更新：

- `AGENTS.md` 中的 `GOAL-FRAMEWORK` 受管区块；
- `goals/GOAL-TEMPLATE.md`；
- `.goal-framework.json` 的版本与更新时间。

它绝不自动覆盖项目已填写的 `docs/PROJECT.md`、`docs/CURRENT.md`、`goals/active/*` 或 `goals/archive/*`。如果未来模板结构有变化，迁移提示会告诉你应人工补充什么。

Python 高级入口支持自动化：

```sh
python3 /path/to/GoalFramework/bin/goal-update.py --dry-run
python3 /path/to/GoalFramework/bin/goal-update.py --yes
```

## 目标命名

活跃目标在 `goals/active/` 中使用 `YYYY-MM-DD-short-title.md`，日期为创建日期，例如 `2026-08-12-time-tracker-v01.md`。归档时先按归档日期重命名，例如 `2026-09-01-time-tracker-v01.md`，再移至 `goals/archive/`。

## 写入的项目结构

```text
.goal-framework.json           # 当前项目已应用的框架版本
AGENTS.md                      # 原有上下文 + Goal Framework 受管区块
docs/PROJECT.md                # 长期愿景、边界、原则与阶段方向
docs/CURRENT.md                # 唯一全局当前状态
goals/GOAL-TEMPLATE.md         # 交付型 / 探索型目标模板
goals/active/
goals/archive/
```

完整版本历史见 `CHANGELOG.md`；机器可读取的跨版本迁移说明见 `MIGRATIONS.json`。
