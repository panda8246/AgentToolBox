# Goal Framework

一个适用于长期项目的轻量目标管理模板。它只保留三层信息：项目长期方向、当前活跃目标、已完成目标的归档。

## 目录

```text
AGENTS.md
PROMPT.md
docs/
  PROJECT.md
  CURRENT.md
goals/
  active/
  archive/
```

## 使用方式

1. 将本目录复制到新项目根目录。
2. 用 `PROMPT.md` 中的初始化提示词，让 Agent 根据你的项目填写 `docs/PROJECT.md` 与 `docs/CURRENT.md`。
3. 只有需要独立推进、探索或验收时，才从 `goals/GOAL-TEMPLATE.md` 新建一个目标文件。
4. 目标完成后补充结论与验证信息，移动至 `goals/archive/`。

## 三层职责

- `docs/PROJECT.md`：长期愿景、目的、边界、原则、阶段方向；不记录日常进度。
- `docs/CURRENT.md`：唯一全局当前状态；只列活跃目标、阻塞或待确认事项。
- `goals/active/`：每个目标自己的目的、完成条件、进度与下一步。支持“交付型”和“探索型”。

不要为简单的一次性修改建立目标文件；不要为没有实际内容的架构、历史、路线图或决策建立空模板。
