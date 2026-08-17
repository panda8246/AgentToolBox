# Goal Framework 项目规则

项目通过三层文件管理：项目总纲、活跃目标、已归档目标。

## 开始工作

1. 阅读 `docs/PROJECT.md` 和 `docs/CURRENT.md`。
2. 若工作属于活跃目标，阅读 `goals/active/` 中对应的文件。
3. 修改前简要说明要推进的目标及当前状态。

## 维护规则

- 若环境提供 `goal-framework-operator` skill，目标的新建、检查点、检查和归档优先使用其 Python `goal-framework` 命令；不要简写为 `goal`，以免与 Agent 自身的目标功能混淆。
- `docs/PROJECT.md` 只保存长期愿景、目的、边界、原则与阶段方向。
- `docs/CURRENT.md` 是唯一的全局当前状态；只列活跃目标、阻塞项和下一步。
- 需要独立推进、探索或验收时，创建一个目标文件。目标可为“交付型”或“探索型”。
- 活跃目标文件命名为 `YYYY-MM-DD-short-title.md`：使用创建日期、小写英文短标题和连字符，例如 `2026-08-12-time-tracker-v01.md`。
- 归档目标使用归档日期命名：完成后将文件重命名为 `YYYY-MM-DD-short-title.md`，其中日期为归档日期，再移至 `goals/archive/`；例如 `2026-09-01-time-tracker-v01.md`。
- 目标完成后，在目标文件写明结果、验证或结论，再移至 `goals/archive/`。
- 只记录可复用的事实和结论，不记录完整聊天过程或敏感数据。
- 文档与可验证的代码、配置冲突时，以代码和配置为准，并同步文档。




