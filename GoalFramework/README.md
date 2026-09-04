# Goal Framework

跨 Agent 复用的轻量项目目标框架。Python 负责核心逻辑；PowerShell 与 POSIX shell 提供简单的交互式入口。

## 初始化

进入项目根目录后运行对应系统的 `goal-init`。菜单只需选择 Agent；推荐 OpenCode。框架会先确保 `AGENTS.md` 存在，再创建目标目录、模板、项目级 operator skill 和项目版本清单 `.goal-framework.json`。

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
- `.agents/skills/goal-framework-operator/` 中的受管运行时文件；
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
.agents/skills/                # 项目级 Goal Framework Operator skill
AGENTS.md                      # 原有上下文 + Goal Framework 受管区块
docs/PROJECT.md                # 长期愿景、边界、原则与阶段方向
docs/CURRENT.md                # 唯一全局当前状态
docs/technical-plans/          # 用户明确要求时保存的自由格式技术方案（按需创建）
goals/GOAL-TEMPLATE.md         # 交付型 / 探索型目标模板
goals/active/
goals/archive/
```

完整版本历史见 `CHANGELOG.md`；机器可读取的跨版本迁移说明见 `MIGRATIONS.json`。

## 版本号规则

版本号使用 `主版本号.次版本号.修订号`：

- 小功能、兼容性增强、缺陷修复、文档或模板调整等小迭代，只递增最后一位修订号。
- 只有包含一组显著能力变化、代表阶段性大迭代时，才递增次版本号并将修订号归零。
- 只有架构、兼容边界或产品代际发生重大变化时，才递增主版本号，并将其余位归零。
- 难以判断时按小迭代处理，只递增修订号。

## Goal Framework Operator skill

`goal-init` 会自动将 `skills/goal-framework-operator/` 安装到项目的
`.agents/skills/goal-framework-operator/`；`goal-update` 会同步其受管文件。测试、
Python 缓存和其他开发文件不会复制到项目，用户在目标 skill 目录中自行添加的文件会保留。
初始化还会检查项目根目录 `.gitignore`，补充缺失的 Python 字节码缓存忽略规则且不改写既有规则。

安装后的 skill 通过 Python `goal-framework` 命令执行确定性的目标操作：

```sh
python .agents/skills/goal-framework-operator/scripts/goal-framework --project . doctor
python .agents/skills/goal-framework-operator/scripts/goal-framework --project . status
```

命令支持 `status`、`doctor`、`new`、`plan attach/detach`、`checkpoint` 与 `complete`。它不会使用 `goal`
作为命令名，避免与 Codex 原生 `/goal` 混淆。项目的 `.goal-framework.json` 会记录
skill 版本及受管文件；即使框架版本没有变化，再运行 `goal-update` 也会修复缺失或被修改的
受管 skill 文件。

复杂目标的完成条件支持嵌套复选框。每层使用两个空格缩进，状态按叶子条件统计；父条件只做汇总，
会在所有直属子条件满足时自动勾选。`checkpoint --satisfy` 使用 `1.2.1` 形式的层级索引且只接受
叶子条件。`new --condition` 可用 `> `、`>> ` 前缀依次建立子条件和孙条件。

## 技术方案关联

技术方案与目标分离：当用户明确要求留档，或在同步确认中授权新建方案时，由 Agent 将自由格式 Markdown 保存到
`docs/technical-plans/`。Goal Framework 不创建或解析技术方案正文，只通过目标文件中的普通
Markdown 链接维护关联：

普通的方案讨论不会自动写文件。用户明确要求保存、留档、落盘或归档，或确认新建方案后，Agent 会把已确认方案
整理为 `docs/technical-plans/<name>.md`；若能唯一确定活跃目标，则继续执行 `plan attach` 和
`doctor`，最后报告文档路径、关联目标与检查结果。目标不明确时只保存文档，不猜测关联对象。

```sh
python .agents/skills/goal-framework-operator/scripts/goal-framework --project . plan attach \
  2026-08-21-export-data.md docs/technical-plans/export-data.md
python .agents/skills/goal-framework-operator/scripts/goal-framework --project . plan detach \
  2026-08-21-export-data.md docs/technical-plans/export-data.md
```

一个目标可关联多份方案，也可以不关联。`doctor` 会检查已有链接是否位于规定目录、是否重复及
技术方案文件是否存在；解除关联不会删除技术文档。目标归档后链接保持不变。

## 对话变更与确认同步

推进活跃目标时，Agent 会对照用户反馈与已记录目标、全部关联方案，主动提醒实质冲突和新增要求。
规则由 `AGENTS.md` 的受管区块持续提供，operator skill 负责确认后的更新流程；旧项目运行
`goal-update` 即可获得，无需迁移文档结构。升级本身不会改写已有目标或方案。

形成具体调整后，Agent 最迟在依赖该调整的实施开始前或本轮讨论结束时，合并列出
“原记录 → 新约定”、受影响文件及需要重新验证的完成条件，并让用户选择：

- **采用新约定并同步**：完成相关文档更新后按新约定推进，无需再说一次“写入文档”。
- **保留原约定**：不采纳本次调整，按旧记录推进。
- **继续讨论**：暂不改写约定，暂停依赖分歧的实施，其他工作可继续。

即使用户说“就改成 B，按这个做”，未明确授权同步记录时仍会确认一次。已授权的同一变更不重复
询问；探索性提问、备选方案和措辞调整不直接触发同步。目标不明确时先确认对象，没有活跃目标时
不自动创建；确需新建技术方案时，先将创建路径列入确认。

同步只更新受影响内容，保留有效证据；验收标准改变后重新核验已完成条件，证据不足时取消勾选，
并重新汇总父条件。只有长期边界或原则变化时才涉及项目总纲。完成后报告文件、变化和检查结果；
部分失败会说明未同步部分，并暂停依赖一致性的实施。语义判断由 Agent 完成，`doctor` 只验证
结构和链接，因此自动化测试无法证明 Agent 在所有对话中都能识别偏差。
