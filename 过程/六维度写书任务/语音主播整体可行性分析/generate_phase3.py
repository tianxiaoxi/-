#!/usr/bin/env python3
"""Phase 3: L1 Summaries + L2 Reports Generator for Voice Streamer Analysis"""

import json
import os
import math
from collections import Counter, defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
L1_DIR = os.path.join(BASE_DIR, "l1_summaries")
os.makedirs(L1_DIR, exist_ok=True)

# ── Load data ──
with open(os.path.join(BASE_DIR, "l0_raw.json"), "r", encoding="utf-8") as f:
    raw_data = json.load(f)

with open(os.path.join(BASE_DIR, "l0_stats.json"), "r", encoding="utf-8") as f:
    stats = json.load(f)

DIMS = ["人设定位", "互动效果", "粉丝关系", "流水营收", "个人状态", "内容质量"]

# ═══════════════════════════════════════════
# PART A: L1 Summaries
# ═══════════════════════════════════════════

# Knowledge base of key findings for special cases (extracted from reports)
SPECIAL_KEY_FINDINGS = {
    "Studio_VOXYZ": [
        "语音合成创作者——声音经过UTAU引擎中介层传递，框架关键边界案例",
        "2025年甲状腺全切除手术构成了⑥-physical（物理性前台崩塌）的全新子类别",
        "甲状腺手术构成⑦'-surgical（外科性生理消耗）——非行为性、不可逆的生理风险",
        "产品中介层使③（互动≈内容）被拆散——内容以产品形式存在，互动以社交媒体形式存在",
        "从衣柜录音到Whisper Room的16年专业进化，但Bus Factor=1是根本结构脆弱性"
    ],
    "不合时宜": [
        "⑥（状态→人设）的教科书级价值观崩塌案例——'在麦克风前批判跨国资本时，录音室外正是被拖欠薪资的实习生'",
        "⑧路径的悖论发现：在价值观崩塌中，核心粉丝的'忠诚'反而加速人设公信力崩塌",
        "发现全新的⑨子类型——'价值观一致性成本'：声线维护成本被言行一致性成本取代",
        "后台崩塌在声音匿名环境中的传播100%依赖文字社交媒体的外部信息注入",
        "⑬→⑥'→⑥的三角恶性循环：营收不足→廉价劳动力→后台暴露→信任崩塌→营收进一步缩水"
    ],
    "姜峰真的苟": [
        "多声线复合型创作者——至少6种声线同时维护，⑨（声线维护成本）处于框架极限值",
        "8年持续伪声，22岁声带的代偿性掩盖了潜在风险——⑦'（生理消耗）处于理论最高档",
        "用营收开设线下密室（梦境旅人）建立了罕见的'线上崩了线下兜底'主动风险对冲",
        "心之壁'自发打破型'——主动放弃声音匿名性换取商业价值和跨平台可迁移性",
        "③（互动≈内容）从'实时恒等'演变为'精选恒等'——视频剪辑降低了实时性但提高了传播性"
    ],
    "MIYU_ASMR": [
        "非语言型声音主播——声音产品为咀嚼音而非人声语言，核心消耗从声带迁移至下颌系统",
        "③（互动≈内容）达到极端值——吃音=内容=互动，三者完全重合",
        "心之壁属于新型'声音沉默型'——不说话而非伪装声音来保护后台",
        "大食量+屏息吃音技术对颞下颌关节和消化系统造成长期生理磨损",
        "322万订阅全球顶尖ASMR创作者，但'体質的に太りにくい'体质争议持续"
    ],
    "Coromo_Sara": [
        "No Talking ASMR的全球标杆——③（互动≈内容）在此发生质变：内容≠互动，属于框架边界案例",
        "301万订阅世界第8位ASMR创作者，但商业化严重不足——仅3个赞助商",
        "No Talking格式带来极低声带消耗的结构性红利——声带消耗约为传统语音主播的3-5%",
        "心之壁属于极厚'声音匿名型'——9年无后台泄露，但存在⑥沉默风险",
        "从$1麦克风到$6000 SAMREC 2700Pro仿真头的设备进化轨迹是⑬路径的教科书级案例"
    ],
    "maimy": [
        "声誉崩塌的系统性路径断裂案例——几乎所有18条路径同时断裂或反转",
        "ASMR特有的亲密感在信任崩塌后从资产翻转为毒药——声音从'治愈'变为'触发厌恶'",
        "Roleplay型ASMR的结构与grooming行为存在危险的形式相似性——所有该类型创作者的警示",
        "心之壁经历了'外力打破→自发加厚→不可穿透'的三阶段演变",
        "⑨（维护成本）从声线维护突变为法律/公关防御成本——框架未预见的极端形态"
    ],
    "DrV_ASMR": [
        "NSFW音频创作者的匿名性困境——职业声优本音可能被同行认出",
        "全维度低于均值的系统性能量不足案例——互动效果5分、粉丝关系4分、流水营收3分",
        "声音匿名型心之壁面临'已被打破'的边界状态"
    ],
    "Sophie_Michelle": [
        "个人状态极端低分（1分）——严重burnout/健康危机的信号",
        "全维度显著低于均值——人设6分、互动5分、内容6分"
    ],
    "WhispersRed": [
        "ASMR领域最资深的创作者之一——正面案例，个人状态9分",
        "长期稳定运营的典范——所有路径信号中等到强"
    ],
    "Gibi_ASMR": [
        "全球最知名ASMR创作者之一——商业化和内容质量的标杆",
        "真人主播向新领域（动漫配音）跨界拓展的代表"
    ],
    "GentleWhispering": [
        "ASMR元老级创作者——13年+持续运营的稳定性典范",
        "声音人设的高度一致性是长周期运营的核心资产"
    ],
}

def get_key_findings(entry):
    """Extract key findings from raw data by synthesizing scores and paths."""
    name = entry["name"]
    scores = entry["scores"]
    paths = entry["paths"]
    voice = entry.get("voice_special_factors", {})
    hw = entry.get("heart_wall", {})
    contradictions = entry.get("contradictions", [])
    
    findings = []
    
    # Check for special cases first
    if name in SPECIAL_KEY_FINDINGS:
        return SPECIAL_KEY_FINDINGS[name]
    
    # Score-based findings
    if not scores:
        return ["数据解析不完整——六维评分缺失，报告提取质量受限", "需人工补充评分"]
    score_vals = [scores.get(d, 0) for d in DIMS if d in scores]
    if not score_vals:
        return ["数据解析不完整——六维评分缺失"]
    high_dims = [d for d in DIMS if scores.get(d, 0) >= 9]
    low_dims = [d for d in DIMS if scores.get(d, 0) <= 4]
    score_range = max(score_vals) - min(score_vals)
    
    if high_dims:
        findings.append(f"高峰维度: {', '.join(high_dims)} 得分≥9")
    if low_dims:
        findings.append(f"低谷维度: {', '.join(low_dims)} 得分≤4——关键风险区")
    
    # ③ signal
    path3 = paths.get("③（互动≈内容）", "")
    if "恒等" in path3 or "高度重叠" in path3:
        findings.append("③（互动≈内容）近恒等——验证了语音主播框架的核心假说")
    elif "断裂" in path3:
        findings.append("③（互动≈内容）断裂——构成框架边界案例")
    
    # ⑦' signal
    path7prime = paths.get("⑦'（直播行为→状态·生理消耗）", "")
    if "强" in path7prime or "高" in path7prime:
        findings.append("⑦'声带消耗信号强——声带作为核心生理瓶颈")
    
    # Heart wall
    wall_cat = hw.get("wall_category", "")
    if "声音匿名" in wall_cat:
        findings.append("心之壁属'声音匿名型'——语音主播的默认保护层")
    elif "打破" in wall_cat:
        findings.append("心之壁已被打破——匿名性保护层失效")
    
    # Voice deviation
    voice_dev = voice.get("voice_deviation", "未知")
    if "伪声" in voice_dev:
        findings.append("使用伪声/变声器——⑨（声线维护成本）和⑦'（生理消耗）系统性偏高")
    
    # Anonymity
    anon = voice.get("anonymity_strength", "")
    if anon == "已被打破":
        findings.append("声音匿名性已被打破——身份暴露风险兑现")
    
    # Contradictions
    if contradictions:
        for c in contradictions[:2]:
            if isinstance(c, str):
                findings.append(f"核心矛盾: {c}")
    
    # Score dispersion
    if score_range >= 5:
        findings.append(f"六维评分极度离散（极差={score_range}）——系统性失衡")
    
    # If we have too few findings, add generic ones
    if len(findings) < 3 and score_vals:
        avg_score = sum(score_vals) / max(len(score_vals), 1)
        if avg_score >= 8:
            findings.append("全维度高分均衡——综合实力强")
        elif avg_score <= 5:
            findings.append("全维度偏低——系统性运营问题")
        else:
            findings.append("六维评分中等偏上——有明确增长空间")

    return findings[:5]


def generate_l1_summary(entry):
    """Generate a YAML/MD summary for a single streamer."""
    name = entry["name"]
    scores = entry["scores"]
    paths = entry["paths"]
    voice = entry.get("voice_special_factors", {})
    hw = entry.get("heart_wall", {})
    contradictions = entry.get("contradictions", [])
    key_findings = get_key_findings(entry)
    
    # Format paths as a clean dictionary
    paths_clean = {}
    for k, v in paths.items():
        paths_clean[k] = v
    
    # Format voice special factors
    vsf = {
        "vocal_health_risk": voice.get("vocal_health_risk", "未知"),
        "anonymity_strength": voice.get("anonymity_strength", "未知"),
        "near_identity_3": voice.get("near_identity_3", "未知"),
        "voice_deviation": voice.get("voice_deviation", "未知"),
    }
    
    # Format heart wall
    hw_clean = {
        "type": hw.get("wall_category", hw.get("type", "未知")),
        "risk_level": hw.get("risk_level", "未知"),
    }
    
    lines = [
        "---",
        f"name: \"{name}\"",
        f"region: \"{entry.get('region', '未分类')}\"",
        f"platform: \"{entry.get('platform', '未分类')}\"",
        f"state: \"{entry.get('state', '未分类')}\"",
        f"tenure: \"{entry.get('tenure', '未分类')}\"",
        f"type: \"{entry.get('type', '未分类')}\"",
        f"org: \"{entry.get('org', '未分类')}\"",
        "",
        "scores:",
    ]
    if scores:
        for d in DIMS:
            lines.append(f"  {d}: {scores.get(d, 'N/A')}")
    else:
        for d in DIMS:
            lines.append(f"  {d}: N/A")
    
    lines.append("")
    lines.append("heart_wall:")
    lines.append(f"  type: \"{hw_clean['type']}\"")
    lines.append(f"  risk_level: \"{hw_clean['risk_level']}\"")
    
    lines.append("")
    lines.append("contradictions:")
    if contradictions:
        for c in contradictions:
            lines.append(f"  - \"{c}\"")
    else:
        lines.append("  []")
    
    lines.append("")
    lines.append("voice_special_factors:")
    for k, v in vsf.items():
        lines.append(f"  {k}: \"{v}\"")
    
    lines.append("")
    lines.append("paths:")
    path_keys = [
        "①（人设⇄互动）",
        "①↺'（表演→自我认知内化/工具）",
        "②（互动→粉丝关系）",
        "③（互动≈内容）",
        "④（互动→营收·交易型）",
        "⑤（互动→状态·情绪消耗）",
        "②'（粉丝关系→营收·关系型）",
        "⑤'（粉丝关系→状态·社会支持缓冲）",
        "⑥（状态→人设·前台崩塌）",
        "⑥'（营收⇄状态·双向反馈）",
        "⑦（内容→状态·认知负荷）",
        "⑦'（直播行为→状态·生理消耗）",
        "⑧（粉丝关系→人设·粉圈塑形）",
        "⑨（人设→状态·前台维护成本）",
        "⑩（人设→内容·叙事约束）",
        "⑪（内容→粉丝关系）",
        "⑫（粉丝→内容·群体共创）",
        "⑬（营收→内容·资源投入）",
    ]
    for pk in path_keys:
        val = paths_clean.get(pk, "未知")
        lines.append(f"  {pk}: \"{val}\"")
    
    # Handle paths with variant keys
    other_paths = {k: v for k, v in paths_clean.items() if k not in path_keys}
    if other_paths:
        lines.append("  # Variant path keys (from report):")
        for k, v in other_paths.items():
            lines.append(f"  \"{k}\": \"{v}\"")
    
    lines.append("")
    lines.append("key_findings:")
    for kf in key_findings:
        lines.append(f"  - \"{kf}\"")
    
    lines.append("---")
    
    return "\n".join(lines)


# Generate all L1 summaries
print("Generating L1 summaries...")
for entry in raw_data:
    name = entry["name"]
    yaml_content = generate_l1_summary(entry)
    filepath = os.path.join(L1_DIR, f"{name}_l1.yaml")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(yaml_content)

print(f"Generated {len(raw_data)} L1 summary files in {L1_DIR}")

print("Phase 3 Part A complete!")
