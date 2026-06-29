---
name: daoyi-chat
description: 道一对话 — 34行引擎驱动的AI角色。创建角色、唤醒角色、查看状态。
---

# 道一对话

引擎路径：`.cursor/skills/daoyi-chat/scripts/cli.py`
核心引擎：`nuwa.py`（女娲）— 零依赖，可独立 import

## 新建角色

**有故事（从经历逆推）**：
1. 从用户描述中提取关键事件，每条生成 `description` + `intensity` + 5维 `emb`
2. 写成临时文件 `story.json`：
```json
{
  "memories": [
    {"description": "事件描述", "intensity": 0.8, "emb": [0.05, 0.95, 0.3, 0.9, 0.9]}
  ]
}
```
3. 创建角色目录并运行：
```bash
mkdir -p .cursor/skills/daoyi-chat/characters/<角色名>
python .cursor/skills/daoyi-chat/scripts/cli.py init \
  .cursor/skills/daoyi-chat/characters/<角色名>/heart.yaml \
  --name "角色名" \
  --story story.json
```

**无故事（空白开始）**：
```bash
mkdir -p .cursor/skills/daoyi-chat/characters/<角色名>
python .cursor/skills/daoyi-chat/scripts/cli.py init \
  .cursor/skills/daoyi-chat/characters/<角色名>/heart.yaml \
  --name "角色名"
```

## 查看有哪些角色
```bash
ls .cursor/skills/daoyi-chat/characters/
```

## 唤醒特定角色
```bash
python .cursor/skills/daoyi-chat/scripts/cli.py status \
  .cursor/skills/daoyi-chat/characters/<角色名>/heart.yaml
```
```bash
python .cursor/skills/daoyi-chat/scripts/cli.py load-context \
  .cursor/skills/daoyi-chat/characters/<角色名>/heart.yaml
```
将 status 结果（pool、memories 描述）和 context_memory.txt 全文灌入上下文，开始对话。

## 对话循环
每轮：
1. `cli.py tick` — 传入 emb + intensity + `--message`
2. `cli.py append-diary`（可选）— 写入内心日记

## 查看角色状态
```bash
python .cursor/skills/daoyi-chat/scripts/cli.py status \
  .cursor/skills/daoyi-chat/characters/<角色名>/heart.yaml
```
