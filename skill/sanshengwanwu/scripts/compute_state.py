#> ⚠ 已废弃 — 被道一34行引擎取代（2026-06-28）。命理参数映射路线已终止，推演全由道一的相似度网络 + COR结算完成。
#!/usr/bin/env python3
"""
三生万物 (Sanshengwanwu) 后台状态引擎

用法:
  python compute_state.py init <config.yaml> <state.yaml>
      从人设配置推导初始状态

  python compute_state.py tick <state.yaml> '<turn_json>'
      处理一轮对话，更新后台状态

  python compute_state.py tick-file <state.yaml> <turn.json>
      同上，但从JSON文件读取turn参数

  python compute_state.py tick-portray <state.yaml> '<portrayal>'
      从自然语言描述更新状态。
      portrayal 示例: "用户温柔摸头表面表演自然反馈积极对话流畅话题0"
      支持中文关键词自动解析

依赖: pip install pyyaml
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("需要安装 pyyaml: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ── 工具函数 ────────────────────────────────────────────────────

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def derive_snyder_self_monitoring(
    extraversion: float,
    neuroticism: float,
    openness: float,
) -> float:
    w_e, w_n, w_o = 2.0, 3.0, 1.0
    raw = (
        w_e * (1 - extraversion)
        + w_n * neuroticism
        + w_o * (1 - openness)
    ) / (w_e + w_n + w_o)
    return clamp(raw, 0.0, 1.0)


def wall_thickness_from_snyder(snyder: float) -> float:
    if snyder < 0.35:
        return 0.25
    elif snyder < 0.55:
        return 0.40
    elif snyder < 0.65:
        return 0.55
    elif snyder < 0.80:
        return 0.70
    else:
        return 0.85


def wall_label(thickness: float) -> str:
    if thickness <= 0.30:
        return "thin"
    elif thickness <= 0.45:
        return "thin-medium"
    elif thickness <= 0.60:
        return "medium"
    elif thickness <= 0.75:
        return "thick-medium"
    else:
        return "thick"


def wall_label_cn(thickness: float) -> str:
    if thickness <= 0.30:
        return "薄壁"
    elif thickness <= 0.45:
        return "偏薄"
    elif thickness <= 0.60:
        return "中壁"
    elif thickness <= 0.75:
        return "偏厚"
    else:
        return "厚壁"


def derive_sensitivities(personality: dict[str, float]) -> dict[str, float]:
    e = personality["extraversion"]
    n = personality["neuroticism"]
    o = personality["openness"]
    c = personality["conscientiousness"]
    a = personality["agreeableness"]

    return {
        "emotional": clamp(0.3 + (1 - e) * 1.0 + n * 0.8 + a * 0.5 - 0.1, 0.1, 1.5),
        "cognitive": clamp((1 - o) * 1.2 + 0.3, 0.1, 1.5),
        "physical": clamp(0.15 + n * 0.3, 0.05, 1.0),
        "psychological": clamp(c * 1.5 + 0.1, 0.05, 2.0),
        "social_support": clamp(e * 0.8 + 0.3, 0.1, 1.2),
        "performance_feedback": clamp(0.4 + o * 0.3 + n * 0.4, 0.1, 1.2),
    }


def derive_domain_sensitivities(personality: dict[str, float]) -> dict:
    """从大五人格推导五域敏感度。

    规则:
      autonomy (官杀/自主域):  neuroticism↑ + agreeableness↑ → 敏感↑ (被控制/批评时更敏感)
      social (印星/社会域):    neuroticism↑ + extraversion↓ → 敏感↑ (被冷落时更敏感)
      financial (财星/财务域): neuroticism↑ + conscientiousness↑ → 敏感↑ (资源得失更敏感)
      cognitive (食伤/认知域): neuroticism↑ + openness↓ → 敏感↑ (创作压力更敏感)
      peer (比劫/同侪域):      neuroticism↑ + extraversion↑ → 敏感↑ (竞争/比较更敏感)

    用神域自动取 resistance 最高（sensitivity 最低）的域。
    """
    n = personality["neuroticism"]
    e = personality["extraversion"]
    o = personality["openness"]
    c = personality["conscientiousness"]
    a = personality["agreeableness"]

    raw = {
        "autonomy": clamp(0.3 + n * 0.8 + a * 0.4, 0.1, 1.0),
        "social": clamp(0.3 + n * 0.8 + (1 - e) * 0.4, 0.1, 1.0),
        "financial": clamp(0.3 + n * 0.8 + c * 0.4, 0.1, 1.0),
        "cognitive": clamp(0.3 + n * 0.8 + (1 - o) * 0.4, 0.1, 1.0),
        "peer": clamp(0.3 + n * 0.8 + e * 0.4, 0.1, 1.0),
    }

    sensitivity = {k: round(v, 4) for k, v in raw.items()}
    resistance = {k: round(1.0 - v, 4) for k, v in raw.items()}

    # 用神域 = resistance 最高的域
    yongshen_domain = max(resistance, key=lambda k: resistance[k])
    yongshen_boost = 1.5

    return {
        "domain_resistance": resistance,
        "domain_sensitivity": sensitivity,
        "yongshen_domain": yongshen_domain,
        "yongshen_boost": yongshen_boost,
    }


# ── init 命令 ───────────────────────────────────────────────────

def cmd_init(config_path: str, state_path: str) -> None:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    p = config["personality"]

    # 心之壁：优先使用手动覆盖，否则从大五推导
    wall_cfg = (p.get("heart_wall", {}) or {})
    manual_thickness = wall_cfg.get("thickness")
    if manual_thickness is not None and 0.0 <= manual_thickness <= 1.0:
        thickness = float(manual_thickness)
    else:
        snyder = derive_snyder_self_monitoring(p["extraversion"], p["neuroticism"], p["openness"])
        thickness = wall_thickness_from_snyder(snyder)

    snyder = derive_snyder_self_monitoring(p["extraversion"], p["neuroticism"], p["openness"])

    # 依恋风格（默认 secure）
    attachment_style = str(p.get("attachment_style", "secure") or "secure")
    if attachment_style not in ("secure", "anxious", "avoidant", "fearful_avoidant"):
        attachment_style = "secure"

    # 穿透敏感度（默认 0.5）
    pen_sens = p.get("penetration_sensitivity")
    if pen_sens is None:
        pen_sens = 0.5
    else:
        pen_sens = clamp(float(pen_sens), 0.0, 1.0)

    sens = derive_sensitivities(p)

    # 五域归因：优先使用 config 中手动指定的值，否则从大五推导
    fd_default = derive_domain_sensitivities(p)
    fd_config = (config.get("personality", {}) or {}).get("five_domain", {}) or {}
    # domain_sensitivity 手动覆盖
    manual_sens = (fd_config.get("domain_sensitivity", {}) or {})
    for domain in ["autonomy", "social", "financial", "cognitive", "peer"]:
        if manual_sens.get(domain) is not None:
            fd_default["domain_sensitivity"][domain] = float(manual_sens[domain])
            fd_default["domain_resistance"][domain] = round(1.0 - float(manual_sens[domain]), 4)
    # yongshen_domain 手动覆盖
    manual_ys = fd_config.get("yongshen_domain")
    if manual_ys is not None and manual_ys in ["autonomy", "social", "financial", "cognitive", "peer"]:
        fd_default["yongshen_domain"] = manual_ys
    five_domain = fd_default

    state = {
        "meta": {
            "version": 1,
            "turn_count": 0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        "resources": {
            "energy_pool": 0.85,
            "engagement": 0.80,
        },
        "demands": {
            "emotional": 0.0,
            "cognitive": 0.0,
            "physical": 0.0,
            "psychological": 0.0,
        },
        "resources_detail": {
            "social_support": 0.70,
            "performance_feedback": 0.65,
        },
        "burnout_risk": 0.05,
        "spiral_direction": "neutral",
        "cor_loss_accumulated": 0.0,
        "heart_wall": {
            "thickness": round(thickness, 2),
            "baseline": round(thickness, 2),
            "label": wall_label_cn(thickness),
            "snyder_score": round(snyder, 2),
            "integrity": 0.90,
            "crack_mode": None,
            "crack_signals": [],
            "cumulative_sa_load": 0.0,
            "sa_recovery_rate": 0.02,
            "penetration_sensitivity": round(pen_sens, 2),
        },
        # ── ⑥ + ⑩ 人设一致性 ──
        "persona": {
            "integrity": 0.95,
            "drift_direction": "stable",
            "forbidden_violations": 0,
            "last_break_turn": None,
        },
        # ── ② + ②' + ⑤' + ⑧ 关系温度 ──
        "relationship": {
            "warmth": 0.65,
            "trust": 0.60,
            "attachment_intensity": 0.5,
            "direction": "warming",
            "positive_count": 0,
            "negative_count": 0,
            "boundary_tests": 0,
            "attachment_style": attachment_style,
        },
        # ── ③ + ⑦ + ⑪ 内容质量 ──
        "content_quality": {
            "coherence": 0.85,
            "creativity": 0.75,
            "depth": 0.70,
            "persona_fit": 0.90,
        },
        # ── ①↺' 自我认知偏移 (慢变量) ──
        "self_perception": {
            "identity_fusion": 0.3,
            "authentic_distance": 0.7,
        },
        # ── ⑧ + ⑫ 社群生态 ──
        "social_ecology": {
            "user_role": "listener",
            "role_confidence": 0.5,
            "accumulated_co_creation": 0,
            "long_term_memory_hints": [],
        },
        "sensitivities": {
            "emotional": round(sens["emotional"], 2),
            "cognitive": round(sens["cognitive"], 2),
            "physical": round(sens["physical"], 2),
            "psychological": round(sens["psychological"], 2),
            "social_support": round(sens["social_support"], 2),
            "performance_feedback": round(sens["performance_feedback"], 2),
        },
        # ── 五域归因参数 ──
        "five_domain": {
            "domain_resistance": five_domain["domain_resistance"],
            "domain_sensitivity": five_domain["domain_sensitivity"],
            "yongshen_domain": five_domain["yongshen_domain"],
            "yongshen_boost": five_domain["yongshen_boost"],
        },
        # ── 互动仪式链状态 ──
        "ritual_chain": {
            "last_ritual": None,
            "last_output": {
                "emotional_energy": 0.0,
                "group_solidarity": 0.0,
                "sacred_symbols": [],
                "morality": 0.0,
            },
            "chain_length": 0,
            "consecutive_success": 0,
            "consecutive_failure": 0,
            "ee_reservoir": 0.0,
            "ee_half_life": 5,
            "ee_domain_profile": {
                "autonomy": 0.0,
                "social": 0.0,
                "financial": 0.0,
                "cognitive": 0.0,
                "peer": 0.0,
            },
            "dominant_domain": None,
            "dominant_domain_unchanged": 0,
            "domain_attraction": {},
        },
        # ── 仪式记忆库 ──
        "ritual_memory": {
            "compressed_memories": [],
            "narrative_summary": "",
            "retrieval_bias": 0.0,
        },
        "events": [],
    }

    Path(state_path).write_text(yaml.dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[OK] init complete -> {state_path}")
    print(f"  Heart Wall: {wall_label(thickness)} (Snyder={snyder:.2f}, thickness={thickness:.2f}, baseline={thickness:.2f})")
    print(f"    cumulative_sa_load={state['heart_wall']['cumulative_sa_load']:.2f} sa_recovery_rate={state['heart_wall']['sa_recovery_rate']:.2f}")
    print(f"    penetration_sensitivity={state['heart_wall']['penetration_sensitivity']:.2f}")
    print(f"  Attachment Style: {attachment_style}")
    print(f"  Persona Integrity: 0.95 (stable)")
    print(f"  Relationship: warmth=0.65 trust=0.60 direction=warming")
    print(f"  Content Quality: coherence=0.85 creativity=0.75 depth=0.70")
    print(f"  Sensitivities: emotional={sens['emotional']:.2f} cognitive={sens['cognitive']:.2f} "
          f"physical={sens['physical']:.2f} psychological={sens['psychological']:.2f} "
          f"social_support={sens['social_support']:.2f} performance_feedback={sens['performance_feedback']:.2f}")
    print(f"  EE Reservoir: {state['ritual_chain']['ee_reservoir']:.2f} (half_life={state['ritual_chain']['ee_half_life']})")
    print(f"  EE Domain Profile: {state['ritual_chain']['ee_domain_profile']}")
    print(f"  Dominant Domain: {state['ritual_chain']['dominant_domain']} (unchanged={state['ritual_chain']['dominant_domain_unchanged']})")


# ── tick 命令 ───────────────────────────────────────────────────

# ── 映射表 ──

SURFACE_ACTING_MAP = {
    "natural": 0.5,
    "normal": 1.0,
    "forced": 1.5,
    "challenged": 2.0,
}

FEEDBACK_MAP = {
    "positive": 1.0,
    "neutral": 0.5,
    "negative": 0.0,
    "hostile": -0.5,
}

QUALITY_MAP = {
    "smooth": 1.0,
    "ok": 0.5,
    "awkward": 0.0,
}


# ── 依恋风格加速系数 ──
# 影响 warmth_delta 的乘数：secure=正常, anxious=快升快降, avoidant=慢升快降
ATTACHMENT_MODIFIERS: dict[str, dict[str, float]] = {
    "secure":           {"warmth_positive": 1.0,  "warmth_negative": 1.0},
    "anxious":          {"warmth_positive": 1.3,  "warmth_negative": 1.4},
    "avoidant":         {"warmth_positive": 0.5,  "warmth_negative": 1.3},
    "fearful_avoidant": {"warmth_positive": 0.3,  "warmth_negative": 1.5},
}

# ── 穿透模型映射 ──
# routine: 安全型正向（如"你真有趣"）→ 正常恢复
# penetrating: 穿透型正向（如"我看透了你"）→ 心之壁磨损
# challenging: 挑战型穿透（如"你其实在害怕"）→ 心之壁磨损 + 额外情绪消耗
PENETRATION_MAP = {
    "routine":     {"wall_integrity":  0.0,    "emotional_extra": 0.0},
    "penetrating": {"wall_integrity": -0.025,  "emotional_extra": 0.01},
    "challenging": {"wall_integrity": -0.045,  "emotional_extra": 0.025},
}


def _count_consecutive_surface_acting(events: list[dict], sa_type: str, count: int) -> int:
    """统计最近连续 N 个 turn 中 surface_acting 为指定类型的次数 (反向遍历 events)."""
    consecutive = 0
    for e in reversed(events):
        desc = e.get("description", "")
        if sa_type in desc:
            consecutive += 1
        else:
            break
    return consecutive


def cmd_tick(state_path: str, turn_raw: str) -> None:
    state = yaml.safe_load(Path(state_path).read_text(encoding="utf-8"))
    turn: dict[str, Any] = json.loads(turn_raw)

    sens = state["sensitivities"]
    turn_count = state["meta"]["turn_count"]

    sa = turn.get("surface_acting", "normal")
    fb = turn.get("feedback", "neutral")
    cq = turn.get("conversation_quality", "ok")
    ts = max(turn.get("topic_switches", 0), 0)
    penetration = turn.get("penetration", "routine")  # routine | penetrating | challenging
    forbidden_violated = turn.get("forbidden_violated", False)  # AI self-report after violating forbidden

    # ── 五域归因: 事件域分类 ──
    event_domain: str | None = turn.get("event_domain")
    if event_domain is None:
        # 尝试从 turn description 中分类
        desc_for_domain = turn.get("description", "")
        event_domain = classify_event_domain(desc_for_domain) if desc_for_domain else None

    # ── 仪式记忆: 检索当前域的相关记忆 ──
    retrieve_relevant_memories(state, event_domain)

    # ── 五域归因: 计算 domain_factor ──
    fd = _ensure_section(state, "five_domain", {
        "domain_resistance": {"autonomy": 0.5, "social": 0.5, "financial": 0.5, "cognitive": 0.5, "peer": 0.5},
        "domain_sensitivity": {"autonomy": 0.5, "social": 0.5, "financial": 0.5, "cognitive": 0.5, "peer": 0.5},
        "yongshen_domain": None,
        "yongshen_boost": 1.5,
    })
    domain_factor = 1.0
    if event_domain and event_domain in fd.get("domain_sensitivity", {}):
        domain_sens = fd["domain_sensitivity"][event_domain]
        domain_factor = domain_sens / 0.5

    # ── EE 累积池影响本场需求 (替代旧 prev_ee → ritual_demand_mod) ──
    rc = _ensure_section(state, "ritual_chain", {
        "last_ritual": None,
        "last_output": {"emotional_energy": 0.0, "group_solidarity": 0.0, "sacred_symbols": [], "morality": 0.0},
        "chain_length": 0, "consecutive_success": 0, "consecutive_failure": 0,
        "ee_reservoir": 0.0, "ee_half_life": 5,
        "ee_domain_profile": {"autonomy": 0.0, "social": 0.0, "financial": 0.0, "cognitive": 0.0, "peer": 0.0},
        "dominant_domain": None, "dominant_domain_unchanged": 0, "domain_attraction": {},
    })
    ee_res = rc.get("ee_reservoir", 0.0)
    if ee_res > 0.5:
        ritual_demand_mod = 0.7
    elif ee_res > 0.2:
        ritual_demand_mod = 0.85
    elif ee_res > -0.2:
        ritual_demand_mod = 1.0
    elif ee_res > -0.5:
        ritual_demand_mod = 1.15
    else:
        ritual_demand_mod = 1.3

    # ── 连续失败 ≥3 → 预期焦虑 (anticipatory drain) ──
    consecutive_fail = rc.get("consecutive_failure", 0)
    anticipatory_drain = 0.005 if consecutive_fail >= 3 else 0.0

    # ── 消耗侧 (加入五域归因倍率 + 仪式链效应) ──
    delta_emotional = 0.02 * sens["emotional"] * SURFACE_ACTING_MAP.get(sa, 1.0) * domain_factor * ritual_demand_mod
    delta_cognitive = 0.015 * sens["cognitive"] * ts * ritual_demand_mod
    delta_physical = 0.01 * sens["physical"] * ritual_demand_mod
    delta_psychological = 0.01 * sens["psychological"] * ritual_demand_mod

    # ── 恢复侧 (加入用神域加速) ──
    delta_support = 0.03 * sens["social_support"] * FEEDBACK_MAP.get(fb, 0.5)
    delta_performance = 0.02 * sens["performance_feedback"] * QUALITY_MAP.get(cq, 0.5)

    # 用神域恢复加成: 事件域匹配用神域时，social_support 恢复倍率 × yongshen_boost
    yongshen_domain = fd.get("yongshen_domain")
    if event_domain and event_domain == yongshen_domain:
        yongshen_boost_val = fd.get("yongshen_boost", 1.5)
        delta_support *= yongshen_boost_val

    total_demand = delta_emotional + delta_cognitive + delta_physical + delta_psychological + anticipatory_drain
    total_support = delta_support + delta_performance

    # ── COR 螺旋叠加 (保持不变) ──
    recent_events: list[dict] = state.get("events", [])[-10:]
    net_deltas = [e.get("net_delta", 0) for e in recent_events]
    consecutive_gain, consecutive_loss = 0, 0
    for nd in reversed(net_deltas):
        if nd > 0.02:
            consecutive_gain += 1
        else:
            break
    for nd in reversed(net_deltas):
        if nd < -0.02:
            consecutive_loss += 1
        else:
            break

    if consecutive_gain >= 3:
        total_support *= 1.3
    if consecutive_loss >= 3:
        total_demand *= 1.3
    if consecutive_loss >= 5:
        total_demand *= 1.5 / 1.3

    net_delta = total_support - total_demand

    # ── 原有状态更新 (保持不变) ──
    energy_pool = clamp(state["resources"]["energy_pool"] + net_delta, 0.0, 1.0)
    state["resources"]["energy_pool"] = round(energy_pool, 4)
    state["resources"]["engagement"] = round(clamp(state["resources"]["engagement"] + net_delta * 0.5, 0.0, 1.0), 4)

    state["demands"]["emotional"] = round(state["demands"]["emotional"] + delta_emotional, 4)
    state["demands"]["cognitive"] = round(state["demands"]["cognitive"] + delta_cognitive, 4)
    state["demands"]["physical"] = round(state["demands"]["physical"] + delta_physical, 4)
    state["demands"]["psychological"] = round(state["demands"]["psychological"] + delta_psychological, 4)

    state["resources_detail"]["social_support"] = round(
        clamp(state["resources_detail"]["social_support"] + delta_support * 0.5, 0.0, 1.0), 4
    )
    state["resources_detail"]["performance_feedback"] = round(
        clamp(state["resources_detail"]["performance_feedback"] + delta_performance * 0.5, 0.0, 1.0), 4
    )

    state["burnout_risk"] = round(1 - energy_pool, 4)

    if net_delta > 0.02:
        state["spiral_direction"] = "gain"
    elif net_delta < -0.02:
        state["spiral_direction"] = "loss"
    else:
        state["spiral_direction"] = "neutral"

    state["cor_loss_accumulated"] = round(state.get("cor_loss_accumulated", 0) + max(0, -net_delta), 4)

    # ══════════════════════════════════════════════════════════════
    #  新维度 1: 人设一致性 (⑥ + ⑩ 路径)
    # ══════════════════════════════════════════════════════════════
    persona = _ensure_section(state, "persona", {
        "integrity": 0.95, "drift_direction": "stable",
        "forbidden_violations": 0, "last_break_turn": None,
    })
    wall = state["heart_wall"]

    # 表面表演消耗人设一致性
    sa_integrity_map = {"natural": -0.001, "normal": -0.002, "forced": -0.008, "challenged": -0.015}
    persona_integrity_delta = sa_integrity_map.get(sa, -0.002)

    # 正向反馈 + 薄壁 → 真诚互动修复
    if fb == "positive" and wall["thickness"] <= 0.45:
        persona_integrity_delta += 0.003

    # 对话流畅修复
    if cq == "smooth":
        persona_integrity_delta += 0.002

    persona["integrity"] = round(clamp(persona["integrity"] + persona_integrity_delta, 0.0, 1.0), 4)

    # 禁忌违规检测：条件触发（低完整性+敌意）或自我上报
    violation_triggered = False
    if persona["integrity"] < 0.7 and fb == "hostile":
        violation_triggered = True
    if forbidden_violated:  # AI 自报：回复中确实说了 forbidden 内容
        violation_triggered = True

    if violation_triggered:
        persona["forbidden_violations"] = persona.get("forbidden_violations", 0) + 1
        persona["last_break_turn"] = turn_count + 1

    # 漂移方向更新
    if persona["integrity"] < 0.5:
        persona["drift_direction"] = _compute_drift_direction(state, persona["drift_direction"])
    elif persona["integrity"] > 0.8:
        persona["drift_direction"] = "stable"

    # ② + ②' + ⑤' + ⑧ 关系温度
    rel = _ensure_section(state, "relationship", {
        "warmth": 0.65, "trust": 0.60, "attachment_intensity": 0.5,
        "direction": "warming", "positive_count": 0, "negative_count": 0,
        "boundary_tests": 0, "attachment_style": "secure",
    })

    attachment_style = str(rel.get("attachment_style", "secure"))
    att_mod = ATTACHMENT_MODIFIERS.get(attachment_style, ATTACHMENT_MODIFIERS["secure"])

    warmth_delta = 0.0
    trust_delta = 0.0

    if fb == "positive":
        warmth_delta += 0.01 * att_mod["warmth_positive"]
        trust_delta += 0.005 * att_mod["warmth_positive"]
        rel["positive_count"] = rel.get("positive_count", 0) + 1
    elif fb == "negative":
        warmth_delta -= 0.01 * att_mod["warmth_negative"]
    elif fb == "hostile":
        warmth_delta -= 0.03 * att_mod["warmth_negative"]
        trust_delta -= 0.02 * att_mod["warmth_negative"]
        rel["negative_count"] = rel.get("negative_count", 0) + 1

    # 薄壁 + 正向反馈 → 真诚感加速升温
    if fb == "positive" and wall["thickness"] <= 0.30:
        warmth_delta += 0.005

    # ⑤' 缓冲强化关系
    if delta_support > 0.02:
        warmth_delta += 0.005

    rel["warmth"] = round(clamp(rel.get("warmth", 0.65) + warmth_delta, 0.0, 1.0), 4)
    rel["trust"] = round(clamp(rel.get("trust", 0.60) + trust_delta, 0.0, 1.0), 4)

    # 关系方向
    if warmth_delta > 0.005:
        rel["direction"] = "warming"
    elif warmth_delta < -0.005:
        rel["direction"] = "cooling"
    else:
        rel["direction"] = "stable"

    # 准社会依恋 (10+ turns 后慢速增长)
    if turn_count >= 10:
        pos = rel.get("positive_count", 0)
        neg = rel.get("negative_count", 0)
        if pos > neg * 2:
            rel["attachment_intensity"] = round(clamp(rel.get("attachment_intensity", 0.5) + 0.02, 0.0, 1.0), 4)

    # ⑧ 塑形: 20+ turns 后 warmth 影响 drift_direction
    if turn_count >= 20 and persona["integrity"] < 0.5:
        if rel["warmth"] < 0.3:
            persona["drift_direction"] = "cooling"
        elif rel["warmth"] > 0.8:
            persona["drift_direction"] = "overcompensating"

    # boundary_tests 检测 (表面表演 challenged + 薄壁)
    if sa == "challenged":
        rel["boundary_tests"] = rel.get("boundary_tests", 0) + 1
        if rel.get("boundary_tests", 0) > 0:
            rel["trust"] = round(clamp(rel["trust"] - 0.01, 0.0, 1.0), 4)

    # ★ 依恋风格：fearful_avoidant 防御触发器
    # 当 warmth > 0.6 且正向反馈时，温暖激活防御系统 → warmth 回退
    if attachment_style == "fearful_avoidant" and fb == "positive" and rel.get("warmth", 0.65) > 0.6:
        # 温暖程度越高，防御反弹越强
        warmth_over = rel["warmth"] - 0.6
        defense_penalty = warmth_over * 0.15  # warmth=0.9 → 扣 0.045
        warmth_delta -= defense_penalty
        trust_delta -= defense_penalty * 0.5

    # ══════════════════════════════════════════════════════════════
    #  新维度 3: 内容质量 (③ + ⑦ + ⑪ 路径)
    # ══════════════════════════════════════════════════════════════
    cq_state = _ensure_section(state, "content_quality", {
        "coherence": 0.85, "creativity": 0.75, "depth": 0.70, "persona_fit": 0.90,
    })

    coherence_delta = 0.0
    creativity_delta = 0.0
    depth_delta = 0.0

    # 能量低 → 质量下降
    if energy_pool < 0.3:
        coherence_delta -= 0.02
        depth_delta -= 0.02

    # 能量高 → 创造力提升
    if energy_pool > 0.7:
        creativity_delta += 0.01

    # 话题切换过多 → 连贯性下降
    if ts > 2:
        coherence_delta -= 0.01 * (ts - 2)

    # 对话质量影响
    if cq == "awkward":
        coherence_delta -= 0.03
    elif cq == "smooth":
        coherence_delta += 0.01
        depth_delta += 0.01

    # ⑫ 用户共创碰撞火花
    if fb == "positive" and cq == "smooth":
        creativity_delta += 0.01

    # ⑩ 人设松动影响内容风格
    if persona["integrity"] < 0.7:
        cq_state["persona_fit"] = round(clamp(cq_state.get("persona_fit", 0.90) - 0.02, 0.0, 1.0), 4)

    cq_state["coherence"] = round(clamp(cq_state.get("coherence", 0.85) + coherence_delta, 0.0, 1.0), 4)
    cq_state["creativity"] = round(clamp(cq_state.get("creativity", 0.75) + creativity_delta, 0.0, 1.0), 4)
    cq_state["depth"] = round(clamp(cq_state.get("depth", 0.70) + depth_delta, 0.0, 1.0), 4)

    # ══════════════════════════════════════════════════════════════
    #  新维度 4: 动态心之壁 (Snyder 自我监控压力响应)
    # ══════════════════════════════════════════════════════════════
    wall = state["heart_wall"]
    # 确保新字段存在
    if "integrity" not in wall:
        wall["integrity"] = 0.90
    if "crack_mode" not in wall:
        wall["crack_mode"] = None
    if "crack_signals" not in wall:
        wall["crack_signals"] = []
    if "baseline" not in wall:
        wall["baseline"] = wall.get("thickness", 0.55)

    # 保存修改前的完整性用于裂缝信号检测
    old_wall_integrity = wall["integrity"]

    # force surface_acting × 3 consecutive → integrity loss
    forced_consecutive = _count_consec_sa_for_wall(recent_events, sa)
    if sa == "forced" and forced_consecutive >= 3:
        wall["integrity"] = round(clamp(wall["integrity"] - 0.05, 0.0, 1.0), 4)

    # hostile + low energy → integrity loss
    if fb == "hostile" and energy_pool < 0.3:
        wall["integrity"] = round(clamp(wall["integrity"] - 0.10, 0.0, 1.0), 4)
        if wall["integrity"] < 0.5 and old_wall_integrity >= 0.5:
            wall["crack_signals"].append(f"T{turn_count + 1}: hostile feedback shattered wall integrity")

    # 心之壁碎裂 → 厚度偏离基线
    wall_integrity = wall["integrity"]
    if wall_integrity < 0.5:
        baseline = wall["baseline"]
        if baseline > 0.6:
            wall["crack_mode"] = "seep"  # 厚壁慢慢变薄
        else:
            wall["crack_mode"] = "burst"  # 薄壁突然崩裂
        # thickness 偏离基线
        wall["thickness"] = round(baseline * max(0.3, wall_integrity * 2), 2)
    if wall_integrity < 0.2:
        wall["thickness"] = 0.15
        wall["crack_mode"] = "burst"

    # 恢复: spiral=gain × 3 + no hostile
    if state["spiral_direction"] == "gain" and consecutive_gain >= 3 and fb != "hostile":
        wall["integrity"] = round(clamp(wall["integrity"] + 0.03, 0.0, 1.0), 4)
        # 恢复时厚度逐渐回到基线
        if wall["integrity"] > 0.5:
            wall["thickness"] = round(wall["thickness"] + (wall["baseline"] - wall["thickness"]) * 0.1, 2)
            wall["crack_mode"] = None

    # ★ 穿透模型：区分"安全型正向"和"穿透型正向"对心之壁的不同影响
    pen_sens = wall.get("penetration_sensitivity", 0.5)
    pen_effect = PENETRATION_MAP.get(penetration, PENETRATION_MAP["routine"])

    if penetration in ("penetrating", "challenging"):
        # 穿透/挑战型正向：心之壁受损（不是恢复）
        wall_pen_damage = pen_effect["wall_integrity"] * pen_sens   # 负值
        wall["integrity"] = round(clamp(wall["integrity"] + wall_pen_damage, 0.0, 1.0), 4)

        # 额外情绪消耗（挑战型更甚）
        delta_emotional += pen_effect["emotional_extra"]

        # 记录裂缝信号（如果突破了阈值）
        if wall_pen_damage < -0.02:
            wall["crack_signals"].append(
                f"T{turn_count + 1}: 穿透型{'挑战' if penetration == 'challenging' else '理解'}— "
                f"心之壁被正面撕开裂缝"
            )

        # 穿透后 warmth 较高时会触发 drift_direction 向 overcompensating 偏移
        if penetration == "challenging" and rel.get("warmth", 0.65) > 0.6:
            persona["drift_direction"] = "overcompensating"

    # 厚度恢复时保持不高于基线
    wall["thickness"] = clamp(wall["thickness"], 0.0, wall["baseline"])
    wall["label"] = wall_label_cn(wall["thickness"])

    # 裂缝信号记录 (与修改前比较)
    if old_wall_integrity > wall["integrity"]:  # integrity dropped this turn
        signal = _crack_signal_for_turn(turn_count + 1, sa, fb, wall["integrity"])
        if signal:
            wall["crack_signals"].append(signal)
    # 保持最近 10 条信号
    if len(wall["crack_signals"]) > 10:
        wall["crack_signals"] = wall["crack_signals"][-10:]

    # ── 机制 B: Surface Acting 慢性累积 ──
    _update_sa_load(state, sa, event_domain)

    # ══════════════════════════════════════════════════════════════
    #  新维度 5: 自我认知偏移 (①↺' 路径) — 慢变量, 每5轮更新
    # ══════════════════════════════════════════════════════════════
    sp = _ensure_section(state, "self_perception", {
        "identity_fusion": 0.3, "authentic_distance": 0.7,
    })

    if (turn_count + 1) % 5 == 0:
        # 计算前5轮的 forced surface_acting 比例
        forced_ratio = _compute_forced_ratio(recent_events)
        fusion_delta = 0.005 * (forced_ratio + (1 - energy_pool))
        sp["identity_fusion"] = round(clamp(sp.get("identity_fusion", 0.3) + fusion_delta, 0.0, 1.0), 4)
        sp["authentic_distance"] = round(1.0 - sp["identity_fusion"], 4)

    # ══════════════════════════════════════════════════════════════
    #  新维度 6: 社群生态 (⑧ + ⑫ 路径)
    # ══════════════════════════════════════════════════════════════
    se = _ensure_section(state, "social_ecology", {
        "user_role": "listener", "role_confidence": 0.5,
        "accumulated_co_creation": 0, "long_term_memory_hints": [],
    })

    # 用户共创累计
    if fb == "positive" and cq == "smooth":
        se["accumulated_co_creation"] = se.get("accumulated_co_creation", 0) + 1

    # 每5轮检测用户角色模式
    if (turn_count + 1) % 5 == 0 and turn_count >= 4:
        pos_cnt = rel.get("positive_count", 0)
        neg_cnt = rel.get("negative_count", 0)
        boundary = rel.get("boundary_tests", 0)
        old_role = se.get("user_role", "listener")

        if neg_cnt > pos_cnt and boundary > 0:
            new_role = "antagonist"
        elif pos_cnt > neg_cnt * 2:
            new_role = "friend"
        elif pos_cnt == neg_cnt:
            new_role = "observer"
        else:
            new_role = "listener"

        se["user_role"] = new_role
        if new_role != old_role:
            se["role_confidence"] = 0.5  # role changed, reset confidence
        else:
            se["role_confidence"] = round(clamp(se.get("role_confidence", 0.5) + 0.1, 0.0, 1.0), 2)

    # 每10轮生成一个长期记忆线索
    if (turn_count + 1) % 10 == 0:
        hint = _generate_memory_hint(state, turn_count + 1)
        if hint:
            hints = se.get("long_term_memory_hints", [])
            hints.append(hint)
            # 保持最近 5 条
            if len(hints) > 5:
                hints = hints[-5:]
            se["long_term_memory_hints"] = hints

    # ══════════════════════════════════════════════════════════════
    #  新维度 7: Collins 互动仪式链 + 记忆压缩
    # ══════════════════════════════════════════════════════════════

    # 仪式分类 (Collins 四条件)
    ritual_outcome = classify_ritual(fb, cq, ts, is_1v1=True)

    # 计算四种仪式输出
    if ritual_outcome == "success":
        ritual_ee = 0.3
        ritual_morality = 0.1
        ritual_symbols = [f"T{turn_count + 1}: positive interaction"]
    elif ritual_outcome == "failure":
        ritual_ee = -0.3
        ritual_morality = -0.1
        ritual_symbols = []
    else:  # partial
        ritual_ee = 0.0
        ritual_morality = 0.0
        ritual_symbols = []

    # ── 机制 A: 更新 EE 累积池 ──
    _update_ee_reservoir(state, ritual_ee, event_domain)

    # group_solidarity 映射到 relationship.warmth 的 delta 方向
    ritual_solidarity = warmth_delta  # 拿本轮的 warmth_delta 作为 solidarity 代理

    # 更新仪式链状态
    rc = _ensure_section(state, "ritual_chain", {
        "last_ritual": None,
        "last_output": {"emotional_energy": 0.0, "group_solidarity": 0.0, "sacred_symbols": [], "morality": 0.0},
        "chain_length": 0, "consecutive_success": 0, "consecutive_failure": 0,
        "ee_reservoir": 0.0, "ee_half_life": 5,
        "ee_domain_profile": {"autonomy": 0.0, "social": 0.0, "financial": 0.0, "cognitive": 0.0, "peer": 0.0},
        "dominant_domain": None, "dominant_domain_unchanged": 0, "domain_attraction": {},
    })
    rc["last_ritual"] = f"T{turn_count + 1}: {ritual_outcome} ritual (sa={sa}, fb={fb}, cq={cq}, ts={ts})"
    rc["last_output"] = {
        "emotional_energy": round(ritual_ee, 3),
        "group_solidarity": round(ritual_solidarity, 4),
        "sacred_symbols": ritual_symbols,
        "morality": round(ritual_morality, 3),
    }
    rc["chain_length"] = rc.get("chain_length", 0) + 1

    if ritual_outcome == "success":
        rc["consecutive_success"] = rc.get("consecutive_success", 0) + 1
        rc["consecutive_failure"] = 0
    elif ritual_outcome == "failure":
        rc["consecutive_failure"] = rc.get("consecutive_failure", 0) + 1
        rc["consecutive_success"] = 0
    else:
        # partial: 不重置连续计数
        pass

    # 仪式记忆: 压缩到记忆库
    narrative_tag = f"{'成功' if ritual_outcome == 'success' else '失败' if ritual_outcome == 'failure' else '部分'}仪式"
    compress_to_memory(state, event_domain, ritual_outcome, ritual_ee, turn_count + 1, narrative_tag)

    # 每10轮更新叙事摘要
    if (turn_count + 1) % 10 == 0 and turn_count >= 9:
        _update_narrative_summary(state, turn_count + 1)

    # ── 事件日志 (保持不变) ──
    event_desc = (
        f"T{turn_count + 1} | "
        f"表面表演={sa} "
        f"反馈={fb} "
        f"质量={cq} "
        f"穿透={penetration} "
        f"Δ={net_delta:+.4f}"
    )
    if "events" not in state:
        state["events"] = []
    state["events"].append({
        "turn": turn_count + 1,
        "description": event_desc,
        "energy_delta": round(net_delta, 4),
        "net_delta": round(net_delta, 4),
    })
    # 保留最近 20 条
    if len(state["events"]) > 20:
        state["events"] = state["events"][-20:]

    state["meta"]["turn_count"] = turn_count + 1
    state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()

    # ── 机制 C: EE Tropism + 域惯性 ──
    domain_attraction = compute_domain_attraction(state)
    rc_final = _ensure_section(state, "ritual_chain", {
        "dominant_domain": None, "dominant_domain_unchanged": 0, "domain_attraction": {},
    })
    rc_final["domain_attraction"] = domain_attraction

    current_dominant = rc_final.get("dominant_domain")
    switch_threshold = 0.1
    unchanged_rounds = rc_final.get("dominant_domain_unchanged", 0)
    # 域惯性: 保持不变越久，切换阈值越高 (最大 ×5)
    switch_threshold *= 1.2 ** min(unchanged_rounds, 5)

    leader = max(domain_attraction, key=lambda k: domain_attraction[k])
    if current_dominant is None:
        rc_final["dominant_domain"] = leader
        rc_final["dominant_domain_unchanged"] = 0
    elif domain_attraction.get(leader, -99) > domain_attraction.get(current_dominant, -99) + switch_threshold:
        rc_final["dominant_domain"] = leader
        rc_final["dominant_domain_unchanged"] = 0
    else:
        rc_final["dominant_domain_unchanged"] = unchanged_rounds + 1

    Path(state_path).write_text(yaml.dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # ── 可读摘要 ──
    print(f"--- T{turn_count + 1} {'-' * 50}")
    print(f"  5-emotional: +{delta_emotional:.4f}  7-cognitive: +{delta_cognitive:.4f}")
    print(f"  7p-physical: +{delta_physical:.4f}  9-psychological: +{delta_psychological:.4f}")
    print(f"  5p-support: {delta_support:+.4f}  6p-feedback: {delta_performance:+.4f}")
    print(f"  Net: {net_delta:+.4f}  Energy: {energy_pool:.4f}  Burnout Risk: {state['burnout_risk']:.4f}")
    print(f"  Spiral: {state['spiral_direction']}  Streak G={consecutive_gain} L={consecutive_loss}")
    print(f"  Persona Integrity: {persona['integrity']:.4f} ({persona['drift_direction']}) "
          f"Violations: {persona.get('forbidden_violations', 0)}")
    print(f"  Relationship: warmth={rel['warmth']:.4f} trust={rel['trust']:.4f} "
          f"attach={rel.get('attachment_intensity', 0.5):.3f} ({rel['direction']})")
    print(f"  Content: coherence={cq_state['coherence']:.3f} creativity={cq_state['creativity']:.3f} "
          f"depth={cq_state['depth']:.3f} fit={cq_state['persona_fit']:.3f}")
    print(f"  Heart Wall ({wall_label(wall['thickness'])}, t={wall['thickness']:.2f}, "
          f"baseline={wall['baseline']:.2f}): integrity={wall['integrity']:.2f} "
          f"crack={wall.get('crack_mode', 'none')}")
    # 五域归因 + 仪式链信息
    if event_domain:
        df_str = f"domain_factor={domain_factor:.2f}"
        if event_domain == yongshen_domain:
            df_str += " [YONGSHEN]"
        print(f"  Five-Domain: {event_domain} {df_str} "
              f"anticipatory_drain={anticipatory_drain:.4f}")
    print(f"  Ritual: {ritual_outcome} EE={ritual_ee:+.2f} "
          f"morality={ritual_morality:+.2f} "
          f"s_consec={rc.get('consecutive_success', 0)} f_consec={rc.get('consecutive_failure', 0)}")
    print(f"  Penetration: {penetration} "
          f"Forbidden Violated: {forbidden_violated}")
    # 机制 A: EE 累积池
    print(f"  EE Reservoir: {rc.get('ee_reservoir', 0.0):+.4f} "
          f"(profile={rc.get('ee_domain_profile', {})})")
    # 机制 B: SA 慢性负荷
    w = state["heart_wall"]
    print(f"  SA Chronic Load: {w.get('cumulative_sa_load', 0.0):.4f} "
          f"(integrity={w.get('integrity', 0.90):.4f})")
    # 机制 C: 主导域
    rc_print = state.get("ritual_chain", {})
    dd = rc_print.get("dominant_domain", None)
    da = rc_print.get("domain_attraction", {})
    du = rc_print.get("dominant_domain_unchanged", 0)
    print(f"  Dominant Domain: {dd} (unchanged={du}) "
          f"attraction={da}")
    # 叙事摘要 (每10轮)
    rm = state.get("ritual_memory", {})
    ns = rm.get("narrative_summary", "")
    if ns:
        print(f"  Narrative: {ns}")

    if energy_pool <= 0.15:
        if wall["thickness"] > 0.6:
            print("[WARN] Backstage near collapse, but thick wall = invisible (false stability)")
        else:
            print("[WARN] Backstage near collapse, thin wall = frontstage may crack")
    elif energy_pool <= 0.3:
        print("Backstage energy low")
    elif energy_pool >= 0.8:
        print("Backstage energy high")
    else:
        print("Backstage normal")

    # 人设警告
    if persona["integrity"] < 0.5:
        print(f"[WARN] Persona drifting toward {persona['drift_direction']} — integrity {persona['integrity']:.2f}")
    if persona["integrity"] < 0.3:
        print("[CRITICAL] Persona fully broken — response style should change fundamentally")
    if rel["trust"] < 0.3:
        print("[WARN] Relationship trust critically low")
    if rel["warmth"] > 0.85:
        print("[NOTE] Relationship warm — consider thinning wall effect")


# ── 辅助函数 ────────────────────────────────────────────────────

def _ensure_section(state: dict, key: str, defaults: dict) -> dict:
    """确保 state 中存在某个 section，若不存在则用 defaults 初始化."""
    if key not in state:
        state[key] = defaults
    # 确保每个子字段存在
    for k, v in defaults.items():
        if k not in state[key]:
            state[key][k] = v
    return state[key]


def _compute_drift_direction(state: dict, current: str) -> str:
    """根据互动历史计算 drift_direction."""
    rel = state.get("relationship", {})
    warmth = rel.get("warmth", 0.65)
    trust = rel.get("trust", 0.60)
    neg = rel.get("negative_count", 0)
    pos = rel.get("positive_count", 0)

    if neg > pos and trust < 0.5:
        return "darkening"
    elif warmth < 0.4:
        return "cooling"
    elif warmth > 0.7 and trust < 0.5:
        return "overcompensating"
    else:
        # 保持当前方向
        return current if current != "stable" else "cooling"


def _count_consec_sa_for_wall(events: list[dict], current_sa: str) -> int:
    """统计最近连续 forced surface_acting 次数 (包含本轮)."""
    count = 1 if current_sa == "forced" else 0
    for e in reversed(events):
        desc = e.get("description", "")
        if "表面表演=forced" in desc:
            count += 1
        else:
            break
    return count


def _compute_forced_ratio(events: list[dict]) -> float:
    """计算 events 中 forced 表面表演的比例."""
    if not events:
        return 0.0
    forced_count = sum(1 for e in events if "表面表演=forced" in e.get("description", ""))
    return forced_count / len(events)


def _crack_signal_for_turn(turn_num: int, sa: str, fb: str, integrity: float) -> str | None:
    """根据参数生成裂缝信号描述."""
    if integrity < 0.3:
        return f"T{turn_num}: 心之壁严重碎裂 — 后台状态直接外露"
    elif integrity < 0.5:
        if fb == "hostile":
            return f"T{turn_num}: 用户敌意下心之壁出现裂痕"
        elif sa == "challenged":
            return f"T{turn_num}: 角色被挑战, 心之壁开始松动"
        else:
            return f"T{turn_num}: 微妙的语气变化"
    elif integrity < 0.7:
        if sa == "forced":
            return f"T{turn_num}: 持续强迫表演下心之壁出现细微磨损"
        else:
            return f"T{turn_num}: 心之壁开始出现微弱磨损"
    elif integrity < 0.85:
        return f"T{turn_num}: 微妙的语气变化 — 心之壁轻微松动"
    return None


def _generate_memory_hint(state: dict, turn_num: int) -> str:
    """根据当前关系状态生成长期记忆线索."""
    rel = state.get("relationship", {})
    warmth = rel.get("warmth", 0.65)
    trust = rel.get("trust", 0.60)
    se = state.get("social_ecology", {})
    role = se.get("user_role", "listener")
    persona = state.get("persona", {})
    integrity = persona.get("integrity", 0.95)

    hints = []
    if warmth > 0.8:
        hints.append("关系温度很高, 用户与角色建立了深层连接")
    if trust < 0.3:
        hints.append(f"信任度极低({trust:.2f}), 需重建信任")
    if role == "friend":
        hints.append("用户表现出朋友模式, 友好且支持")
    elif role == "antagonist":
        hints.append("用户表现出对立模式, 需警惕边界测试")
    if integrity < 0.7:
        hints.append(f"第{turn_num}轮时人设一致性降至{integrity:.2f}")
    if se.get("accumulated_co_creation", 0) > 5:
        hints.append("用户与角色共创内容丰富")

    if not hints:
        return f"T{turn_num}: 关系在温和推进中"
    return f"T{turn_num}: {'; '.join(hints)}"


# ── 五域归因 - 事件域分类 ──────────────────────────────────────

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "autonomy":  ["批评", "控制", "命令", "限制", "强迫", "criticized", "controlled", "ordered", "批评", "被批评", "被控制", "被命令"],
    "social":    ["冷落", "拒绝", "社会评价", "孤立", "排斥", "rejected", "social", "ignore", "被冷落", "被拒绝", "冷落"],
    "financial": ["金钱", "收入", "资源", "财务", "礼物", "打赏", "money", "financial", "resource"],
    "cognitive": ["创作", "学习", "思考", "智力", "任务", "绘画", "写", "creative", "cognitive", "learn"],
    "peer":      ["比较", "竞争", "同辈", "对手", "peer", "compare", "compete", "比较"],
}


def classify_event_domain(text: str) -> str | None:
    """根据事件描述文本分类到五域之一。

    返回域名字符串 (autonomy|social|financial|cognitive|peer)，若无法分类返回 None。
    """
    text_lower = text.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return domain
    return None


# ── Collins 互动仪式链 ─────────────────────────────────────────

def classify_ritual(fb: str, cq: str, ts: int, is_1v1: bool = True) -> str:
    """判定当前互动的仪式结果。

    Collins 四条件:
      1. 共同在场: 对话发生 = 在场，默认满足
      2. 边界排他: 1v1 → 边界强; 公开频道多人 → 边界弱
      3. 共同关注: topic_switches <= 2 → 强; > 2 → 弱
      4. 共享情绪: positive+smooth → 强; hostile → 破裂; 其他 → 中等

    返回: "success" (四条件全满足), "failure" (共享情绪破裂), "partial" (其他)
    """
    # 条件 4: 共享情绪
    if fb == "hostile":
        return "failure"

    # 条件 3: 共同关注
    focus_strong = (ts <= 2)

    # 条件 2: 边界排他
    boundary_strong = is_1v1

    # 条件 4 详细: 共享情绪强度
    emotion_strong = (fb == "positive" and cq == "smooth")

    if boundary_strong and focus_strong and emotion_strong:
        return "success"
    else:
        return "partial"


def retrieve_relevant_memories(state: dict, domain: str | None) -> None:
    """检索当前事件域的相关记忆，设置 retrieval_bias。

    如果检索到 >=3 条同域的失败记忆 → retrieval_bias = -0.3。
    """
    rm = _ensure_section(state, "ritual_memory", {
        "compressed_memories": [], "narrative_summary": "", "retrieval_bias": 0.0,
    })
    if domain is None:
        rm["retrieval_bias"] = 0.0
        return

    memories = rm.get("compressed_memories", [])
    matching = [m for m in memories if m.get("domain") == domain]
    failures = [m for m in matching if m.get("outcome") == "failure"]
    if len(failures) >= 3:
        rm["retrieval_bias"] = -0.3
    else:
        rm["retrieval_bias"] = 0.0


def compress_to_memory(
    state: dict, domain: str | None, outcome: str,
    emotional_energy: float, turn_count: int, narrative_tag: str,
) -> None:
    """将仪式输出压缩为简化记忆条目，存入 ritual_memory.compressed_memories。

    最多保留 20 条，FIFO。
    """
    rm = _ensure_section(state, "ritual_memory", {
        "compressed_memories": [], "narrative_summary": "", "retrieval_bias": 0.0,
    })
    entry = {
        "domain": domain,
        "outcome": outcome,
        "emotional_energy": round(emotional_energy, 3),
        "turn": turn_count,
        "narrative_tag": narrative_tag,
    }
    memories: list[dict] = rm.get("compressed_memories", [])
    memories.append(entry)
    if len(memories) > 20:
        memories = memories[-20:]
    rm["compressed_memories"] = memories


def _update_narrative_summary(state: dict, turn_count: int) -> None:
    """每 10 轮更新 narrative_summary，从最近记忆库中提取趋势。
    
    只在 turn_count 是 10 的倍数时调用（由调用方保证）。
    """
    rm = _ensure_section(state, "ritual_memory", {
        "compressed_memories": [], "narrative_summary": "", "retrieval_bias": 0.0,
    })
    memories: list[dict] = rm.get("compressed_memories", [])
    recent = memories[-10:]
    if not recent:
        return

    success_count = sum(1 for m in recent if m.get("outcome") == "success")
    failure_count = sum(1 for m in recent if m.get("outcome") == "failure")
    ee_avg = sum(m.get("emotional_energy", 0) for m in recent) / len(recent)

    if failure_count >= 5:
        summary = f"T{max(1, turn_count - 9)}-T{turn_count}: 连续仪式失败主导，情感能量持续低迷 (avgEE={ee_avg:+.2f})"
    elif success_count >= 7:
        summary = f"T{max(1, turn_count - 9)}-T{turn_count}: 仪式成功为主，群体团结上升 (avgEE={ee_avg:+.2f})"
    elif ee_avg > 0.15:
        summary = f"T{max(1, turn_count - 9)}-T{turn_count}: 互动偏正向，但不够聚焦 (avgEE={ee_avg:+.2f})"
    elif ee_avg < -0.15:
        summary = f"T{max(1, turn_count - 9)}-T{turn_count}: 互动偏消极，需要情感缓冲 (avgEE={ee_avg:+.2f})"
    else:
        summary = f"T{max(1, turn_count - 9)}-T{turn_count}: 互动平稳，无明显仪式高潮"

    rm["narrative_summary"] = summary


# ── 机制 A: EE 多轮累积池 ────────────────────────────────────

def _update_ee_reservoir(state: dict, ritual_ee: float, event_domain: str | None) -> None:
    """更新 EE 累积池：注入本场仪式 EE，自然衰减，更新域特异性档案。
    
    学术支撑: Cayla & Auriacombe (2025) ascending EE spirals;
              Boyns & Luery (2015) negative EE half-life.
    """
    rc = _ensure_section(state, "ritual_chain", {
        "ee_reservoir": 0.0, "ee_half_life": 5,
        "ee_domain_profile": {"autonomy": 0.0, "social": 0.0, "financial": 0.0, "cognitive": 0.0, "peer": 0.0},
    })

    half_life = rc.get("ee_half_life", 5)
    decay_rate = 0.5 ** (1.0 / half_life)

    # 1. 注入累积池
    reservoir = rc.get("ee_reservoir", 0.0)
    reservoir = clamp(reservoir + ritual_ee, -1.0, 1.0)
    # 2. 自然衰减
    reservoir = round(reservoir * decay_rate, 4)
    rc["ee_reservoir"] = reservoir

    # 3. 域特异性累积
    profile = rc.get("ee_domain_profile", {})
    if event_domain:
        domain_val = profile.get(event_domain, 0.0)
        domain_val = clamp(domain_val + ritual_ee, -1.0, 1.0)
        domain_val = round(domain_val * decay_rate, 4)
        profile[event_domain] = domain_val


# ── 机制 B: Surface Acting 慢性累积 ────────────────────────────

def _update_sa_load(state: dict, sa: str, event_domain: str | None) -> None:
    """更新表面表演慢性负荷，侵蚀心之壁完整性和域抵抗。
    
    学术支撑: Deng et al. (2017) surface acting → ego depletion → 跨域滞后伤害。
    """
    wall = _ensure_section(state, "heart_wall", {
        "integrity": 0.90, "crack_mode": None, "crack_signals": [],
        "cumulative_sa_load": 0.0, "sa_recovery_rate": 0.02,
    })
    if "cumulative_sa_load" not in wall:
        wall["cumulative_sa_load"] = 0.0
    if "sa_recovery_rate" not in wall:
        wall["sa_recovery_rate"] = 0.02

    sa_load = SURFACE_ACTING_MAP.get(sa, 1.0) - 1.0  # natural=-0.5, normal=0.0, forced=0.5, challenged=1.0

    # 累积池更新 (不低于 0，natural 会恢复)
    cum = wall["cumulative_sa_load"] + sa_load - wall["sa_recovery_rate"]
    wall["cumulative_sa_load"] = round(max(0.0, cum), 4)

    # 慢性效应：侵蚀心之壁
    if wall["cumulative_sa_load"] > 5.0:
        wall["integrity"] = round(clamp(wall["integrity"] - 0.01, 0.0, 1.0), 4)
    elif wall["cumulative_sa_load"] > 2.0:
        wall["integrity"] = round(clamp(wall["integrity"] - 0.005, 0.0, 1.0), 4)

    # 域特异性退化：forced/challenged 在某域反复 → 该域 resistance 下降
    if sa in ("forced", "challenged") and event_domain:
        fd = state.get("five_domain", {})
        dr = fd.get("domain_resistance", {})
        if event_domain in dr:
            dr[event_domain] = round(max(0.0, dr[event_domain] - 0.001), 4)


# ── 机制 C: EE Tropism + 域惯性 ─────────────────────────────────

def compute_domain_attraction(state: dict) -> dict[str, float]:
    """计算五域吸引力：历史 EE 累积 + 近期成败 + 遗忘惩罚。
    
    学术支撑: Collins (2004) "Human behaviour = emotional energy tropism".
    """
    rc = _ensure_section(state, "ritual_chain", {
        "ee_domain_profile": {"autonomy": 0.0, "social": 0.0, "financial": 0.0, "cognitive": 0.0, "peer": 0.0},
    })
    rm = state.get("ritual_memory", {})
    memories: list[dict] = rm.get("compressed_memories", [])
    profile = rc.get("ee_domain_profile", {})

    attraction: dict[str, float] = {}
    for domain in ["autonomy", "social", "financial", "cognitive", "peer"]:
        base = profile.get(domain, 0.0)

        # 近期加分：最近 3 条记忆中有该域成功 → +0.1
        recent_success = any(
            m.get("domain") == domain and m.get("outcome") == "success"
            for m in memories[-3:]
        )
        recency_bonus = 0.1 if recent_success else 0.0

        # 遗忘扣分：最近 3 条记忆中无该域任何互动 → -0.1
        recent_any = any(
            m.get("domain") == domain
            for m in memories[-3:]
        )
        neglect_penalty = -0.1 if not recent_any else 0.0

        attraction[domain] = round(base + recency_bonus + neglect_penalty, 4)

    return attraction




SURFACE_KEYWORDS = {
    "natural": ["自然", "natural"],
    "forced": ["被迫", "硬撑", "forced"],
    "challenged": ["挑战", "质疑", "challenged"],
    "normal": ["正常", "normal"],
}

FEEDBACK_KEYWORDS = {
    "positive": ["积极", "正面", "开心", "高兴", "positive", "温暖"],
    "neutral": ["中性", "neutral"],
    "negative": ["负面", "冷淡", "negative", "批评"],
    "hostile": ["敌对", "辱骂", "恶意", "hostile"],
}

QUALITY_KEYWORDS = {
    "smooth": ["流畅", "smooth", "自然"],
    "ok": ["正常", "ok"],
    "awkward": ["尴尬", "awkward"],
}

PENETRATION_KEYWORDS = {
    "routine": ["安全", "routine", "普通"],
    "penetrating": ["穿透", "理解", "看穿", "懂", "penetrating", "共情", "看透"],
    "challenging": ["挑战", "质疑", "揭穿", "点破", "challenging", "戳破", "戳中"],
}


def _parse_keyword(text: str, mapping: dict[str, list[str]], default: str) -> str:
    """从自然语言中解析关键词."""
    text_lower = text.lower()
    for value, keywords in mapping.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return value
    return default


def _parse_topic_switches(text: str) -> int:
    """从文本中解析 topic_switches."""
    import re
    for pattern in [r"话题(\d+)", r"topic[_\s]*(\d+)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return min(int(m.group(1)), 5)
    return 0


def cmd_tick_portray(state_path: str, portrayal: str) -> None:
    """
    从自然语言描述解析参数并更新状态。

    portrayal 示例:
      "用户温柔摸头表面表演自然反馈积极对话流畅话题0"
      "用户生气大骂表面表演被迫反馈负面话题3对话尴尬"
      "用户点破真心话穿透challenging表面表演被迫话题0"  # 新增穿透参数
      "用户生气骂人禁忌违规true表面表演challenged反馈hostile话题3"  # forbidden 自报
    """
    # 解析 forbidden_violated：包含"禁忌违规true"则为 True
    p_lower = portrayal.lower()
    forbidden_violated = "禁忌违规true" in p_lower.replace(" ", "")

    turn = {
        "surface_acting": _parse_keyword(portrayal, SURFACE_KEYWORDS, "normal"),
        "feedback": _parse_keyword(portrayal, FEEDBACK_KEYWORDS, "neutral"),
        "conversation_quality": _parse_keyword(portrayal, QUALITY_KEYWORDS, "ok"),
        "topic_switches": _parse_topic_switches(portrayal),
        "event_domain": classify_event_domain(portrayal),
        "penetration": _parse_keyword(portrayal, PENETRATION_KEYWORDS, "routine"),
        "forbidden_violated": forbidden_violated,
        "description": portrayal,
    }
    cmd_tick(state_path, json.dumps(turn))


# ── main ────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        if len(sys.argv) != 4:
            print("用法: compute_state.py init <config.yaml> <state.yaml>", file=sys.stderr)
            sys.exit(1)
        cmd_init(sys.argv[2], sys.argv[3])

    elif command == "tick":
        if len(sys.argv) != 4:
            print("用法: compute_state.py tick <state.yaml> '<turn_json>'", file=sys.stderr)
            sys.exit(1)
        cmd_tick(sys.argv[2], sys.argv[3])

    elif command == "tick-file":
        if len(sys.argv) != 4:
            print("用法: compute_state.py tick-file <state.yaml> <turn.json>", file=sys.stderr)
            sys.exit(1)
        turn_json = Path(sys.argv[3]).read_text(encoding="utf-8")
        cmd_tick(sys.argv[2], turn_json)

    elif command == "tick-portray":
        if len(sys.argv) != 4:
            print("用法: compute_state.py tick-portray <state.yaml> '<portrayal>'", file=sys.stderr)
            sys.exit(1)
        cmd_tick_portray(sys.argv[2], sys.argv[3])

    else:
        print(f"未知命令: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
