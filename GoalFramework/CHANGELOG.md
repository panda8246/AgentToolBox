# Changelog

## 1.3.0 — 2026-08-17

- `goal-init` 现在自动将 operator skill 安装到项目 `.agents/skills/`。
- `goal-update` 现在同步项目级 skill；项目已是最新版本时也会检查并修复 skill。
- 项目状态文件记录 skill 的受管文件清单，以便删除旧版遗留文件并保留用户额外文件。
- Git 与项目级 skill 同步都会忽略 Python 字节码缓存。

## 1.2.0 — 2026-08-17

- 新增 `goal-framework-operator` skill，通过 Python `goal-framework` 命令管理目标生命周期。
- 新增 `status`、`doctor`、`new`、`checkpoint` 与 `complete` 操作。
- 目标模板改用可验证的完成条件复选框与结构化进度区块。
- 写入操作新增项目锁、原子替换与失败回滚保护。

## 1.1.0 — 2026-08-12

- 新增 `.goal-framework.json`，记录每个项目已应用的框架版本。
- 新增 `goal-update`：展示并应用跨版本迁移说明，更新受管规则与目标模板。
- 初始化后不再保留 `GOAL-FRAMEWORK-PROMPT.md`；初始化提示只在 Agent 调用时临时使用。
- 明确归档目标使用归档日期重命名。

## 1.0.0 — 2026-08-12

- 首次发布三层目标框架：项目总纲、活跃目标与归档目标。
