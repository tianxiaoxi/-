"""nuwa (女娲) — 道一引擎核心

捏土造人。Character + 余弦相似度 + 记忆迁移。
零依赖。零文件系统。可被任何 Python 程序 import。
"""

from __future__ import annotations


# ── 余弦相似度（纯Python，零依赖）─────────────────────────────────

def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = (sum(x * x for x in a)) ** 0.5
    nb = (sum(x * x for x in b)) ** 0.5
    return dot / (na * nb + 1e-8)


# ── 记忆迁移（旧格式→新格式）─────────────────────────────────────

def _migrate_memories(memories: list[dict]) -> list[dict]:
    """给旧格式的记忆补上 turn 和 description 默认值。"""
    for m in memories:
        if "turn" not in m:
            m["turn"] = 0
        if "description" not in m:
            m["description"] = ""
    return memories


# ── 34行引擎核心 ─────────────────────────────────────────────────

class Character:
    def __init__(self, pool: float = 0.5, memories: list[dict] | None = None):
        self.pool = pool
        self.memories = _migrate_memories(memories or [])

    def tick(self, event_emb: list[float], intensity: float,
             base_drain: float = 0.05, base_recovery: float = 0.02,
             description: str = "", turn_count: int = 0):
        drain = base_drain
        matched: list[dict] = []

        for m in self.memories:
            sim = cosine_sim(event_emb, m["emb"])
            threshold = 0.6 - m["intensity"] * 0.4
            if sim > threshold:
                drain += m["intensity"] * sim * 0.4
                matched.append(m)

        for i in range(len(matched)):
            for j in range(i + 1, len(matched)):
                drain += cosine_sim(matched[i]["emb"], matched[j]["emb"]) * 0.1

        self.pool = max(0.0, min(1.0, self.pool - drain + base_recovery))

        recorded = False
        if intensity > 0.5:
            self.memories.append({
                "emb": event_emb,
                "intensity": intensity,
                "turn": turn_count,
                "description": description,
            })
            recorded = True

        return self.pool, matched, recorded, drain
