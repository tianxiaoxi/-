"""cli — 道一引擎命令行入口

用法: python cli.py <init|tick|status|recall|modify|auto-tick|load-context|append-diary> ...

依赖: pip install pyyaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from nuwa import Character, _migrate_memories, cosine_sim
from fileio import (
    load_heart, save_heart, save_config,
    append_context_memory, load_context_memory, context_memory_path,
    DEFAULT_HEARTBEAT_INTERVAL, DEFAULT_CONTEXT_KEEP_TURNS,
)


# ── 命令实现 ──────────────────────────────────────────────────────

def cmd_init(args):
    import yaml

    dir_path = os.path.dirname(args.heart_path) or "."
    heart_path = os.path.join(dir_path, "heart.yaml")
    config_path = os.path.join(dir_path, "config.yaml")

    name = args.name or "未命名"
    pool = args.pool or 0.5
    memories: list[dict] = []

    if args.story:
        story_path = args.story
        with open(story_path, "r", encoding="utf-8") as f:
            story = yaml.safe_load(f) if story_path.endswith((".yaml", ".yml")) else json.load(f)
        raw_memories = story.get("memories", [])
        for m in raw_memories:
            memories.append({
                "emb": m["emb"],
                "intensity": m["intensity"],
                "turn": 0,
                "description": m.get("description", ""),
            })
        if memories:
            high = sum(1 for m in memories if m.get("intensity", 0) > 0.7)
            pool = round(max(0.2, 0.7 - (high / len(memories)) * 0.5), 2)

    heart = {
        "pool": pool,
        "turn_count": 0,
        "memories": memories,
        "last_heartbeat_turn": 0,
    }
    config = {
        "character": {"name": name, "created_from": "story" if memories else "blank"},
        "heartbeat_interval": DEFAULT_HEARTBEAT_INTERVAL,
        "context_keep_turns": DEFAULT_CONTEXT_KEEP_TURNS,
    }
    save_heart(heart_path, heart)
    save_config(config_path, config)

    n_trauma = sum(1 for m in memories if m["intensity"] > 0.7)
    n_high = sum(1 for m in memories if 0.5 < m["intensity"] <= 0.7)
    print(json.dumps({
        "status": "created",
        "name": name,
        "pool": pool,
        "memory_count": len(memories),
        "trauma_count": n_trauma,
        "high_count": n_high,
        "mode": "story" if memories else "blank",
    }, ensure_ascii=False))


def cmd_tick(args):
    emb = json.loads(args.emb_json)
    if len(emb) != 5:
        print(json.dumps({"error": "emb 必须是 5 维向量"}, ensure_ascii=False))
        sys.exit(1)

    state = load_heart(args.heart_path)
    char = Character(pool=state.get("pool", 0.5), memories=state.get("memories", []))

    pool_new, matched, recorded, drain = char.tick(
        emb, args.intensity,
        description=args.description or "",
        turn_count=state.get("turn_count", 0) + 1,
    )

    state["pool"] = round(pool_new, 4)
    state["memories"] = char.memories
    state["turn_count"] = state.get("turn_count", 0) + 1
    save_heart(args.heart_path, state)

    if args.message:
        append_context_memory(
            args.heart_path, args.message,
            state.get("context_keep_turns", DEFAULT_CONTEXT_KEEP_TURNS),
        )

    print(json.dumps({
        "pool": round(pool_new, 4),
        "matched_count": len(matched),
        "matched": [m.get("description", "") for m in matched],
        "recorded": recorded,
        "drain": round(drain, 4),
        "turn": state["turn_count"],
        "memory_total": len(char.memories),
    }, ensure_ascii=False))


def cmd_status(args):
    state = load_heart(args.heart_path)
    memories = _migrate_memories(state.get("memories", []))

    direction = ""
    if memories:
        high = [m for m in memories if m["intensity"] > 0.5]
        if high:
            dims = ["效价", "唤醒度", "社会权重", "自主威胁", "新颖度"]
            avgs = [sum(m["emb"][d] for m in high) / len(high) for d in range(5)]
            top = max(range(5), key=lambda d: avgs[d])
            direction = f"敏感方向: {dims[top]} (均值 {avgs[top]:.2f})"

    print(json.dumps({
        "pool": state.get("pool", 0.5),
        "turn_count": state.get("turn_count", 0),
        "memory_count": len(memories),
        "trauma_count": sum(1 for m in memories if m["intensity"] > 0.7),
        "direction": direction,
        "memories": memories,
    }, ensure_ascii=False, indent=2))


def cmd_recall(args):
    query_emb = json.loads(args.query_emb_json)
    if len(query_emb) != 5:
        print(json.dumps({"error": "query_emb 必须是 5 维向量"}, ensure_ascii=False))
        sys.exit(1)

    state = load_heart(args.heart_path)
    memories = _migrate_memories(state.get("memories", []))

    scored: list[dict] = []
    for idx, m in enumerate(memories):
        sim = cosine_sim(query_emb, m["emb"])
        scored.append({
            "index": idx,
            "description": m.get("description", ""),
            "intensity": m["intensity"],
            "similarity": round(sim, 4),
            "turn": m.get("turn", 0),
        })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    top = scored[:args.k]

    print(json.dumps({
        "query_k": args.k,
        "total_memories": len(memories),
        "results": top,
    }, ensure_ascii=False, indent=2))


def cmd_modify(args):
    idx = args.index

    state = load_heart(args.heart_path)
    memories = _migrate_memories(state.get("memories", []))

    if idx < 0 or idx >= len(memories):
        print(json.dumps({"error": f"索引 {idx} 超出范围 (0~{len(memories)-1})"}, ensure_ascii=False))
        sys.exit(1)

    old = memories[idx]
    changes: list[str] = []

    if args.intensity is not None:
        changes.append(f"intensity: {old['intensity']} → {args.intensity}")
        old["intensity"] = args.intensity
    if args.emb:
        new_emb = json.loads(args.emb)
        if len(new_emb) != 5:
            print(json.dumps({"error": "emb 必须是 5 维向量"}, ensure_ascii=False))
            sys.exit(1)
        changes.append(f"emb: {old['emb']} → {new_emb}")
        old["emb"] = new_emb
    if args.description is not None:
        old["description"] = args.description
        changes.append("description 已更新")

    save_heart(args.heart_path, state)

    print(json.dumps({
        "status": "modified",
        "index": idx,
        "changes": changes,
        "memory": {
            "description": old.get("description", ""),
            "intensity": old["intensity"],
            "emb": old["emb"],
            "turn": old.get("turn", 0),
        },
    }, ensure_ascii=False, indent=2))


def cmd_auto_tick(args):
    state = load_heart(args.heart_path)
    memories = _migrate_memories(state.get("memories", []))

    if not memories:
        auto_emb = [0.5, 0.3, 0.5, 0.5, 0.3]
    else:
        total_intensity = sum(m["intensity"] for m in memories) or 1.0
        weighted = [0.0] * 5
        for m in memories:
            w = m["intensity"] / total_intensity
            for d in range(5):
                weighted[d] += m["emb"][d] * w
        auto_emb = [min(1.0, round(v, 4)) for v in weighted]

    char = Character(pool=state.get("pool", 0.5), memories=memories)
    auto_intensity = auto_emb[1] * 0.5

    pool_new, matched, recorded, drain = char.tick(
        auto_emb, auto_intensity,
        description="auto-tick (heartbeat)",
        turn_count=state.get("turn_count", 0) + 1,
    )

    state["pool"] = round(pool_new, 4)
    state["memories"] = char.memories
    state["turn_count"] = state.get("turn_count", 0) + 1
    state["last_heartbeat_turn"] = state["turn_count"]
    save_heart(args.heart_path, state)

    suggest_speak = False
    if pool_new < 0.3 and len(matched) > 0:
        suggest_speak = True
    elif pool_new > 0.6:
        suggest_speak = True

    print(json.dumps({
        "pool": round(pool_new, 4),
        "matched_count": len(matched),
        "matched": [m.get("description", "") for m in matched],
        "recorded": recorded,
        "drain": round(drain, 4),
        "turn": state["turn_count"],
        "auto_emb": auto_emb,
        "suggest_speak": suggest_speak,
    }, ensure_ascii=False, indent=2))


def cmd_load_context(args):
    content = load_context_memory(args.heart_path)
    print(json.dumps({
        "context_file": context_memory_path(args.heart_path),
        "content": content,
        "line_count": len([l for l in content.split("\n") if l.strip()]) if content else 0,
    }, ensure_ascii=False, indent=2))


def cmd_append_diary(args):
    state = load_heart(args.heart_path)
    append_context_memory(
        args.heart_path,
        f"[道一内心]: {args.diary}",
        state.get("context_keep_turns", DEFAULT_CONTEXT_KEEP_TURNS),
    )
    print(json.dumps({"status": "appended", "line": args.diary}, ensure_ascii=False))


# ── main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="道一引擎 CLI")
    sub = parser.add_subparsers(dest="command")

    # init
    p = sub.add_parser("init", help="创建角色")
    p.add_argument("heart_path", help="heart.yaml 路径")
    p.add_argument("--name", help="角色名")
    p.add_argument("--pool", type=float, help="初始 pool")
    p.add_argument("--story", help="story.json 路径")
    p.set_defaults(func=cmd_init)

    # tick
    p = sub.add_parser("tick", help="处理一轮对话")
    p.add_argument("heart_path")
    p.add_argument("emb_json", help='5维向量 JSON: "[效价,唤醒度,社会权重,自主威胁,新颖度]"')
    p.add_argument("intensity", type=float, help="事件冲击强度 0-1")
    p.add_argument("--description", help="事件简述")
    p.add_argument("--message", help="本轮对话原文")
    p.set_defaults(func=cmd_tick)

    # status
    p = sub.add_parser("status", help="查看角色状态")
    p.add_argument("heart_path")
    p.set_defaults(func=cmd_status)

    # recall
    p = sub.add_parser("recall", help="主动检索相似记忆")
    p.add_argument("heart_path")
    p.add_argument("query_emb_json", help='查询 emb JSON')
    p.add_argument("--k", type=int, default=3, help="返回前 k 条 (默认 3)")
    p.set_defaults(func=cmd_recall)

    # modify
    p = sub.add_parser("modify", help="微调记忆")
    p.add_argument("heart_path")
    p.add_argument("index", type=int, help="记忆索引")
    p.add_argument("--intensity", type=float, help="新 intensity")
    p.add_argument("--emb", help="新 emb JSON")
    p.add_argument("--description", help="新描述")
    p.set_defaults(func=cmd_modify)

    # auto-tick
    p = sub.add_parser("auto-tick", help="心跳时钟驱动 tick")
    p.add_argument("heart_path")
    p.set_defaults(func=cmd_auto_tick)

    # load-context
    p = sub.add_parser("load-context", help="读取上下文记忆")
    p.add_argument("heart_path")
    p.set_defaults(func=cmd_load_context)

    # append-diary
    p = sub.add_parser("append-diary", help="追加内心日记")
    p.add_argument("heart_path")
    p.add_argument("diary", help="日记内容")
    p.set_defaults(func=cmd_append_diary)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
