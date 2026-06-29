#!/usr/bin/env python3
"""
世界引擎 (World Engine) — 多实体传播仿真

基于道一34行引擎的 World 类。
复杂的是每个 entity 的 memories，不是 World 类。

用法:
  python world_engine.py <config.json>
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from typing import Any


# ── 余弦相似度 ──────────────────────────────────────────────────

def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = (sum(x * x for x in a)) ** 0.5
    nb = (sum(x * x for x in b)) ** 0.5
    return dot / (na * nb + 1e-8)


# ── 34行引擎核心（道一 Character 类）─────────────────────────────

class Character:
    def __init__(self, pool: float = 0.5, memories: list[dict] | None = None):
        self.pool = pool
        self.memories = memories or []

    def tick(self, event_emb: list[float], intensity: float,
             base_drain: float = 0.05, base_recovery: float = 0.02):
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
            self.memories.append({"emb": event_emb, "intensity": intensity})
            recorded = True

        return self.pool, matched, recorded, drain


# ── WorldCharacter: 多实体世界校准版 ─────────────────────────────

class WorldCharacter(Character):
    """世界仿真级的 Character，使用效价方向判定。

    34 行引擎是为 1v1 对话设计的——每轮匹配 0-2 条记忆。
    世界仿真中，一个宏观事件可能同时触动多条记忆。

    核心修正：事件效价 vs 记忆效价。
    - 同向（都是正面或都是负面）：共鸣 → recovery（不是消耗）
    - 反向（事件正面但记忆负面，或反之）：冲突 → drain（比纯消耗更强）
    """

    def tick(self, event_emb: list[float], intensity: float,
             base_drain: float = 0.03, base_recovery: float = 0.01):
        event_valence = event_emb[0]
        drain = base_drain
        recovery = base_recovery
        matched_drain: list[dict] = []   # 反向冲突 → 消耗
        matched_recovery: list[dict] = []  # 同向共鸣 → 恢复

        for m in self.memories:
            sim = cosine_sim(event_emb, m["emb"])
            threshold = 0.7 - m["intensity"] * 0.3
            if sim > threshold:
                memory_valence = m["emb"][0]
                valence_agreement = 1.0 - abs(event_valence - memory_valence)
                # valence_agreement: 0=完全相反, 1=完全相同

                if valence_agreement >= 0.70:
                    # 同向共鸣 → 恢复
                    # 事件方向与记忆方向一致：论文证实了你的路线，你的敌人被打脸了
                    recovery += m["intensity"] * sim * valence_agreement * 0.06
                    m_copy = dict(m)
                    m_copy["_valence_effect"] = "resonance"
                    matched_recovery.append(m_copy)
                else:
                    # 反向冲突 → 消耗
                    # 事件方向与记忆相反：论文否定了你押注的方向
                    drain += m["intensity"] * sim * (1.0 - valence_agreement) * 0.12
                    m_copy = dict(m)
                    m_copy["_valence_effect"] = "conflict"
                    matched_drain.append(m_copy)

        # 交叉匹配：只有同方向的记忆对才产生共振
        for i in range(len(matched_recovery)):
            for j in range(i + 1, len(matched_recovery)):
                recovery += cosine_sim(matched_recovery[i]["emb"],
                                       matched_recovery[j]["emb"]) * 0.02
        for i in range(len(matched_drain)):
            for j in range(i + 1, len(matched_drain)):
                drain += cosine_sim(matched_drain[i]["emb"],
                                    matched_drain[j]["emb"]) * 0.03

        self.pool = max(0.0, min(1.0, self.pool - drain + recovery))

        recorded = False
        if intensity > 0.5:
            self.memories.append({"emb": event_emb, "intensity": intensity})
            recorded = True

        all_matched = matched_drain + matched_recovery
        return self.pool, all_matched, recorded, drain, recovery


# ── World 类 ────────────────────────────────────────────────────

class World:
    """多实体世界。

    核心认知:
    - 复杂的是每个 entity 的 memories，不是 World 类
    - 事件打进所有 entities，各 entity 自己决定受不受影响
    - 状态变化本身成为下一轮次生事件
    """

    def __init__(self):
        self.entities: dict[str, Character] = {}
        self.history: list[dict] = []
        self.turn = 0

    def add_entity(self, name: str, pool: float, memories: list[dict]):
        self.entities[name] = WorldCharacter(pool=pool, memories=memories)

    def propagate(self, event_emb: list[float], intensity: float,
                  event_desc: str = "") -> dict[str, dict]:
        """一个事件打进所有 entities。"""
        self.turn += 1
        results = {}

        for name, entity in self.entities.items():
            pool_before = entity.pool
            pool_after, matched, recorded, drain, recovery = entity.tick(event_emb, intensity)
            # 分类匹配：共振 vs 冲突
            resonance = [m.get("description", "") for m in matched
                         if m.get("_valence_effect") == "resonance"]
            conflict = [m.get("description", "") for m in matched
                        if m.get("_valence_effect") == "conflict"]
            raw = [m.get("description", "") for m in matched
                   if "_valence_effect" not in m]
            results[name] = {
                "pool_before": round(pool_before, 4),
                "pool_after": round(pool_after, 4),
                "delta": round(pool_after - pool_before, 4),
                "matched_count": len(matched),
                "matched": raw + resonance + conflict,
                "resonance": resonance,
                "conflict": conflict,
                "recorded": recorded,
                "drain": round(drain, 4),
                "recovery": round(recovery, 4),
            }

        entry = {
            "turn": self.turn,
            "event": event_desc,
            "event_emb": event_emb,
            "intensity": intensity,
            "results": results,
        }
        self.history.append(entry)
        return results

    def get_state_snapshot(self) -> dict:
        return {
            name: {"pool": round(e.pool, 4), "memory_count": len(e.memories)}
            for name, e in self.entities.items()
        }

    def get_significant_changes(self, threshold: float = 0.03) -> list[dict]:
        """找出本轮 delta 超过阈值的 entity。"""
        if not self.history:
            return []
        last = self.history[-1]
        sig = []
        for name, r in last["results"].items():
            if abs(r["delta"]) >= threshold:
                sig.append({
                    "entity": name,
                    "delta": r["delta"],
                    "pool": r["pool_after"],
                    "matched": r["matched"],
                    "drain": r["drain"],
                    "recovery": r["recovery"],
                    "resonance_count": len(r.get("resonance", [])),
                    "conflict_count": len(r.get("conflict", [])),
                })
        return sorted(sig, key=lambda x: abs(x["delta"]), reverse=True)

    def to_report(self) -> str:
        """生成仿真报告。"""
        lines = []
        lines.append("# 世界引擎 — 多实体传播仿真报告")
        lines.append(f"## 总轮数: {self.turn}")
        lines.append("")

        # Pool 轨迹表
        lines.append("## Pool 轨迹")
        lines.append("")
        header = "| Turn | Event |" + " | ".join(self.entities.keys()) + " |"
        lines.append(header)
        sep = "|------|-------|" + " | ".join("------" for _ in self.entities) + " |"
        lines.append(sep)

        for h in self.history:
            event_short = h["event"][:30] + ("..." if len(h["event"]) > 30 else "")
            pools = " | ".join(
                f"{r['pool_after']:.4f} ({r['delta']:+.4f})"
                for r in h["results"].values()
            )
            lines.append(f"| T{h['turn']} | {event_short} | {pools} |")

        lines.append("")

        # 每轮详情
        lines.append("## 每轮详情")
        lines.append("")
        for h in self.history:
            lines.append(f"### T{h['turn']}: {h['event']}")
            lines.append(f"- **Intensity**: {h['intensity']}")
            lines.append(f"- **EMB**: [{', '.join(f'{v:.2f}' for v in h['event_emb'])}]")
            lines.append("")
            for name, r in h["results"].items():
                net = "↑" if r["delta"] > 0 else "↓"
                lines.append(f"**{name}**: pool {r['pool_before']:.4f} → {r['pool_after']:.4f} "
                           f"({net} Δ={r['delta']:+.4f}) drain={r['drain']:.4f} recovery={r['recovery']:.4f}")
                if r.get("resonance"):
                    lines.append(f"  - Resonance ({len(r['resonance'])}): {r['resonance'][:2]}")
                if r.get("conflict"):
                    lines.append(f"  - Conflict ({len(r['conflict'])}): {r['conflict'][:2]}")
                if not r["matched"]:
                    lines.append(f"  - No memories matched")
            lines.append("")

        # 终态对比
        lines.append("## 终态快照")
        lines.append("")
        for name, e in self.entities.items():
            status = "GREEN" if e.pool > 0.7 else \
                     "YELLOW" if e.pool > 0.4 else \
                     "ORANGE" if e.pool > 0.2 else \
                     "RED" if e.pool > 0.08 else \
                     "CRITICAL"
            lines.append(f"- **{name}**: pool={e.pool:.4f} {status}, memories={len(e.memories)}")

        return "\n".join(lines)


# ── 事件编码器（LLM 替身：将自然语言事件编码为 5维 emb）─────────

def encode_event(description: str, category: str = "general") -> tuple[list[float], float]:
    """将事件描述编码为 (emb, intensity)。

    这是 LLM 替身层。真实场景中 LLM 做这件事。
    这里用启发式规则。
    """
    desc_lower = description.lower()
    keywords = set(desc_lower.replace(",", " ").replace("，", " ").split())

    # 默认值
    valence = 0.5      # 效价
    arousal = 0.5      # 唤醒度
    social_weight = 0.5  # 社会权重
    autonomy_threat = 0.5  # 自主威胁
    novelty = 0.5      # 新颖度
    intensity = 0.6    # 事件强度

    # 效价判定
    positive_words = {"突破", "发布", "创新", "增长", "领先", "合作", "成功", "利好",
                      "breakthrough", "success", "growth", "innovation", "leading"}
    negative_words = {"危机", "崩溃", "下跌", "衰退", "制裁", "威胁", "失败", "风险",
                      "crash", "decline", "sanction", "threat", "failure", "risk"}

    pos_count = sum(1 for w in keywords if w in positive_words)
    neg_count = sum(1 for w in keywords if w in negative_words)

    if pos_count > neg_count:
        valence = 0.75
    elif neg_count > pos_count:
        valence = 0.25

    # 唤醒度
    high_arousal = {"突破", "崩溃", "危机", "革命", "震惊", "颠覆",
                    "breakthrough", "crash", "crisis", "revolution", "shock"}
    ar_count = sum(1 for w in keywords if w in high_arousal)
    arousal = min(1.0, 0.5 + ar_count * 0.15)

    # 社会权重
    high_social = {"全球", "国际", "世界", "国家", "政府", "公众",
                   "global", "international", "world", "government", "public"}
    sc_count = sum(1 for w in keywords if w in high_social)
    social_weight = min(1.0, 0.5 + sc_count * 0.12)

    # 自主威胁
    autonomy_words = {"制裁", "限制", "控制", "监管", "禁止", "封锁",
                      "sanction", "restrict", "control", "regulate", "ban", "block"}
    at_count = sum(1 for w in keywords if w in autonomy_words)
    autonomy_threat = min(1.0, 0.2 + at_count * 0.2)

    # 新颖度
    novel_words = {"新", "首次", "突破", "从未", "颠覆", "革命",
                   "new", "first", "breakthrough", "never", "revolutionary"}
    nv_count = sum(1 for w in keywords if w in novel_words)
    novelty = min(1.0, 0.4 + nv_count * 0.15)

    # Intensity 判定
    if "突破" in keywords or "breakthrough" in keywords:
        intensity = 0.85
    elif "危机" in keywords or "crash" in keywords:
        intensity = 0.8
    elif "发布" in keywords or "publish" in keywords or "release" in keywords:
        intensity = 0.7
    elif "论文" in keywords or "paper" in keywords:
        intensity = 0.65

    return ([round(valence, 2), round(arousal, 2), round(social_weight, 2),
             round(autonomy_threat, 2), round(novelty, 2)],
            round(intensity, 2))


# ── 次生事件生成器 ──────────────────────────────────────────────

def generate_secondary_event(entity_name: str, delta: float, pool: float,
                             matched_descs: list[str]) -> tuple[str, list[float], float]:
    """生成次生事件: entity pool 显变 → 其他 entity 感知到的事件。"""
    if delta < -0.05:
        desc = f"Market signal: {entity_name} shows significant resource drain (delta={delta:+.3f}, pool={pool:.3f})"
        # 危机信号: 负效价, 中唤醒, 高社会权重 (关乎整个生态)
        emb = [0.25, 0.55, 0.65, 0.20, 0.50]
        intensity = 0.55
    elif delta < -0.02:
        desc = f"Market signal: {entity_name} mild resource decline (delta={delta:+.3f})"
        emb = [0.35, 0.45, 0.50, 0.15, 0.30]
        intensity = 0.40
    elif delta > 0.02:
        desc = f"Market signal: {entity_name} resource increase (delta={delta:+.3f}, pool={pool:.3f})"
        emb = [0.70, 0.50, 0.50, 0.10, 0.30]
        intensity = 0.40
    else:
        desc = ""
        emb = [0.5, 0.5, 0.5, 0.5, 0.5]
        intensity = 0.0

    return desc, emb, intensity


# ── main ───────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = None

    # ═══════════════════════════════════════════════════════════════
    # 复合事件：8 关键点 — 道一·六道·三生 三位一体发布
    # ═══════════════════════════════════════════════════════════════
    event_desc = (
        "Paradigm event: One Chinese researcher releases three interconnected papers "
        "in 3 months with $500 total — 1) Daoyi: 34-line minimal consciousness model "
        "inspired by Dao De Jing; 2) Liudao Yinguo Luo: six-path causal network framework "
        "aligned with Chinese mingli as forgotten sociological meta-theory; "
        "3) Sanshengwanwu: branch simulation engine predicting any individual/organization's future. "
        "All three form a unified system proving that entire AI+causality stack needs neither "
        "billion-dollar GPU clusters nor Western institutional frameworks."
    )
    # EMB: [valence, arousal, social_weight, autonomy_threat, novelty]
    # Breakthrough with disruptive weight: high arousal, extreme novelty, neutral-positive valence
    # Valence 0.65: objectively a breakthrough, but carries disruptive power for incumbents
    event_emb = [0.65, 0.95, 0.90, 0.20, 0.98]
    event_intensity = 0.90

    print(f"Event: {event_desc}")
    print(f"EMB: valence={event_emb[0]:.2f} arousal={event_emb[1]:.2f} "
          f"social_weight={event_emb[2]:.2f} autonomy_threat={event_emb[3]:.2f} "
          f"novelty={event_emb[4]:.2f}")
    print(f"Intensity: {event_intensity:.2f}")
    print()

    if config_path:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        world = World()
        for entity_cfg in config["entities"]:
            world.add_entity(
                entity_cfg["name"],
                entity_cfg["pool"],
                entity_cfg["memories"],
            )
            print(f"Loaded: {entity_cfg['name']} (pool={entity_cfg['pool']:.2f}, "
                  f"memories={len(entity_cfg['memories'])})")
    else:
        print("Usage: python world_engine.py <config.json>")
        sys.exit(1)

    print(f"\n{'='*60}")
    snapshot = world.get_state_snapshot()
    print(f"Initial state:")
    for name, s in snapshot.items():
        print(f"  {name}: pool={s['pool']:.4f}, memories={s['memory_count']}")
    print(f"{'='*60}\n")

    # T1: Paper published event
    print("=== T1: Three-Paper Paradigm Event ===")
    print(f"  One Chinese researcher, 3 months, $500 — DaoYi + Liudao + Sansheng")
    print(f"  Event valence=0.65 (breakthrough: objectively positive, disruption for scale-heavy incumbents)")
    world.propagate(event_emb, event_intensity, event_desc)

    results_t1 = list(world.history[-1]["results"].items())
    # Sort by delta descending (winners first)
    results_t1.sort(key=lambda x: x[1]["delta"], reverse=True)

    print(f"\n  {'Entity':<20} {'Pool':>8} {'Delta':>8} {'Drain':>8} {'Recovery':>8} {'Resonance':>6} {'Conflict':>6}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*6} {'-'*6}")
    for name, r in results_t1:
        net = "+" if r["delta"] >= 0 else ""
        print(f"  {name:<20} {r['pool_before']:.4f}→{r['pool_after']:.4f} "
              f"{net}{r['delta']:+.4f}  {r['drain']:.4f}  {r['recovery']:.4f}  "
              f"{len(r.get('resonance',[])):>6}  {len(r.get('conflict',[])):>6}")

    print(f"\n  Breakdown:")
    for name, r in results_t1:
        resonance = r.get("resonance", [])
        conflict = r.get("conflict", [])
        if resonance or conflict:
            parts = []
            if resonance:
                parts.append(f"+{len(resonance)} resonance: {resonance[0][:50]}")
            if conflict:
                parts.append(f"-{len(conflict)} conflict: {conflict[0][:50]}")
            print(f"    {name}: {' | '.join(parts)}")

    # Detect secondary events (only propagate top 2 to avoid cascade)
    sig_changes = world.get_significant_changes(threshold=0.02)
    top_impacts = sig_changes[:2]

    print(f"\nSecondary event candidates ({len(sig_changes)} total, propagating top {len(top_impacts)}):")
    for sc in sig_changes:
        marker = " [PROPAGATED]" if sc in top_impacts else ""
        print(f"  {sc['entity']}: delta={sc['delta']:+.4f}, pool={sc['pool']:.4f}{marker}")

    # T2-T3: Only propagate top 2 most significant changes
    print(f"\n{'='*60}")
    for i, sc in enumerate(top_impacts):
        desc, emb, intensity = generate_secondary_event(
            sc["entity"], sc["delta"], sc["pool"], sc["matched"]
        )
        if intensity > 0:
            print(f"=== T{world.turn + 1}: Secondary Event {i+1} — {desc} ===")
            world.propagate(emb, intensity, desc)

            for name, r in world.history[-1]["results"].items():
                net = "+" if r["delta"] >= 0 else ""
                r_info = ""
                if r.get("resonance"):
                    r_info += f" [+{len(r['resonance'])}R]"
                if r.get("conflict"):
                    r_info += f" [-{len(r['conflict'])}C]"
                print(f"  {name}: {r['pool_before']:.4f} -> {r['pool_after']:.4f} "
                      f"({net}{r['delta']:+.4f}) d={r['drain']:.3f} r={r['recovery']:.3f}{r_info}")

    # Save report
    print(f"\n{'='*60}")
    report = world.to_report()
    print(report)

    report_path = "simulation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
