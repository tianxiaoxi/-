"""io — 文件读写层

heart.yaml / config.yaml / context_memory.txt 的读写。
不依赖 cli.py 或 nuwa.py。
"""

from __future__ import annotations

import os
import sys


DEFAULT_HEARTBEAT_INTERVAL = 300
DEFAULT_CONTEXT_KEEP_TURNS = 10000


def _ensure_yaml():
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("需要安装 pyyaml: pip install pyyaml", file=sys.stderr)
        sys.exit(1)


def load_heart(path: str) -> dict:
    _ensure_yaml()
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _ensure_defaults(data)


def save_heart(path: str, data: dict):
    _ensure_yaml()
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def save_config(path: str, data: dict):
    _ensure_yaml()
    import yaml
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def context_memory_path(heart_path: str) -> str:
    """返回 heart.yaml 同目录下的 context_memory.txt 路径。"""
    return os.path.join(os.path.dirname(heart_path) or ".", "context_memory.txt")


def heart_path(dir_path: str) -> str:
    """返回角色目录下的 heart.yaml 路径。"""
    return os.path.join(os.path.dirname(dir_path) or ".", "heart.yaml")


def append_context_memory(heart_path: str, message: str, keep_turns: int):
    """追加一条消息到上下文记忆文件，从尾部保留最近 keep_turns 条。"""
    ctx_path = context_memory_path(heart_path)
    lines: list[str] = []
    try:
        with open(ctx_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f if line.strip()]
    except FileNotFoundError:
        pass

    lines.append(message.strip())
    if len(lines) > keep_turns:
        lines = lines[-keep_turns:]

    with open(ctx_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def load_context_memory(heart_path: str) -> str:
    """读取 context_memory.txt 全文。"""
    ctx_path = context_memory_path(heart_path)
    try:
        with open(ctx_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _ensure_defaults(state: dict) -> dict:
    """向后兼容：旧 heart.yaml 自动补全字段。"""
    if "heartbeat_interval" not in state:
        state["heartbeat_interval"] = DEFAULT_HEARTBEAT_INTERVAL
    if "context_keep_turns" not in state:
        state["context_keep_turns"] = DEFAULT_CONTEXT_KEEP_TURNS
    if "last_heartbeat_turn" not in state:
        state["last_heartbeat_turn"] = 0
    return state
