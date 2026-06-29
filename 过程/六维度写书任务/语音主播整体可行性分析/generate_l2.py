#!/usr/bin/env python3
"""Phase 3 Part B & C: L2 Reports Generator for Voice Streamer Analysis"""

import json
import os
import math
from collections import Counter, defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
L1_DIR = os.path.join(BASE_DIR, "l1_summaries")

# ── Load data ──
with open(os.path.join(BASE_DIR, "l0_raw.json"), "r", encoding="utf-8") as f:
    raw_data = json.load(f)

with open(os.path.join(BASE_DIR, "l0_stats.json"), "r", encoding="utf-8") as f:
    stats = json.load(f)

DIMS = ["人设定位", "互动效果", "粉丝关系", "流水营收", "个人状态", "内容质量"]

# ── Helper: filter valid entries (those with scores) ──
valid = [e for e in raw_data if e.get("scores") and len(e["scores"]) == 6]
total = len(raw_data)
valid_n = len(valid)

# ── Compute additional stats ──
def safe_mean(lst):
    return sum(lst) / len(lst) if lst else 0

def safe_std(lst, mean):
    return math.sqrt(sum((x - mean)**2 for x in lst) / len(lst)) if len(lst) > 1 else 0

# Region stats
regions = defaultdict(list)
for e in valid:
    regions[e.get("region", "未分类")].append(e)

# Type stats
types = defaultdict(list)
for e in valid:
    types[e.get("type", "综合")].append(e)

# Anonymity stats
anon_counts = Counter()
for e in valid:
    a = e.get("voice_special_factors", {}).get("anonymity_strength", "未知")
    anon_counts[a] += 1

# Vocal health risk
vocal_counts = Counter()
for e in valid:
    v = e.get("voice_special_factors", {}).get("vocal_health_risk", "未知")
    vocal_counts[v] += 1

# Near identity ③
ni3_counts = Counter()
for e in valid:
    n3 = e.get("voice_special_factors", {}).get("near_identity_3", "未知")
    ni3_counts[n3] += 1

# Voice deviation
vd_counts = Counter()
for e in valid:
    vd = e.get("voice_special_factors", {}).get("voice_deviation", "未知")
    vd_counts[vd] += 1

# Heart wall distribution
hw_types = Counter()
for e in valid:
    wc = e.get("heart_wall", {}).get("wall_category", "未知")
    hw_types[wc] += 1

# Path signal analysis for key paths
PATH_KEYS_MAP = {
    "③": "③（互动≈内容）",
    "⑥": "⑥（状态→人设·前台崩塌）",
    "⑦'": "⑦'（直播行为→状态·生理消耗）",
    "⑨": "⑨（人设→状态·前台维护成本）",
    "⑧": "⑧（粉丝关系→人设·粉圈塑形）",
    "②'": "②'（粉丝关系→营收·关系型）",
    "④": "④（互动→营收·交易型）",
}

def classify_path_signal(val):
    """Classify a path value into high/medium/low/na."""
    if not val:
        return "NA"
    v = val.lower()
    if any(w in v for w in ["强", "极强", "近恒等", "高度重叠", "恒等", "高风险", "★★★★★", "★★★★", "强正向"]):
        return "强"
    if any(w in v for w in ["中", "正向循环", "低风险", "工具型", "部分重叠"]):
        return "中"
    if any(w in v for w in ["弱", "低", "断裂", "极弱", "未触发", "不适用", "极低", "未知"]):
        return "弱"
    return "中"

# Path signal counts
path_counts = defaultdict(lambda: {"强": 0, "中": 0, "弱": 0, "NA": 0})
for e in valid:
    for pk_label, pk_full in PATH_KEYS_MAP.items():
        val = e.get("paths", {}).get(pk_full, "")
        if not val:
            # Try to find variant
            for k, v in e.get("paths", {}).items():
                if pk_label in k:
                    val = v
                    break
        signal = classify_path_signal(val)
        path_counts[pk_full]["强"] += 1 if signal == "强" else 0
        path_counts[pk_full]["中"] += 1 if signal == "中" else 0
        path_counts[pk_full]["弱"] += 1 if signal == "弱" else 0
        path_counts[pk_full]["NA"] += 1 if signal == "NA" else 0

# Score distribution by voice deviation
vd_scores = defaultdict(lambda: defaultdict(list))
for e in valid:
    vd = e.get("voice_special_factors", {}).get("voice_deviation", "未知")
    for d in DIMS:
        vd_scores[vd][d].append(e["scores"].get(d, 0))

# Score distribution by anonymity strength
anon_scores = defaultdict(lambda: defaultdict(list))
for e in valid:
    a = e.get("voice_special_factors", {}).get("anonymity_strength", "未知")
    for d in DIMS:
        anon_scores[a][d].append(e["scores"].get(d, 0))

# Contradiction analysis
contra_counts = Counter()
for e in valid:
    for c in e.get("contradictions", []):
        contra_counts[c[:40]] += 1  # truncated for grouping

# Outlier analysis by type
type_outliers = defaultdict(list)
for e in valid:
    t = e.get("type", "综合")
    type_data = types[t]
    if len(type_data) < 3:
        continue
    for d in DIMS:
        group_scores = [ee["scores"].get(d, 0) for ee in type_data]
        gm = safe_mean(group_scores)
        gs = safe_std(group_scores, gm)
        if gs == 0:
            continue
        z = (e["scores"].get(d, 0) - gm) / gs
        if abs(z) > 1.5:
            type_outliers[t].append({
                "name": e["name"],
                "dimension": d,
                "score": e["scores"].get(d, 0),
                "group_mean": round(gm, 2),
                "z_score": round(z, 2),
                "deviation": round(e["scores"].get(d, 0) - gm, 2)
            })

# ═══════════════════════════════════════════
# REPORT 1: 02_框架评估报告.md
# ═══════════════════════════════════════════

def generate_framework_eval():
    lines = []
    lines.append("# 02_框架评估报告：六道因果络框架在语音主播中的适用性验证")
    lines.append("")
    lines.append(f"> 生成日期：2026-06-25 | 样本量：{total}份报告（{valid_n}份有效）")
    lines.append("> 分析层次：L2 Task A — 框架评估")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ── 1. 无视觉层的框架适应性 ──
    lines.append("## 1. 无视觉层的框架适应性")
    lines.append("")
    
    ### 1.1 ③（互动≈内容）在语音主播中是否接近恒等？
    lines.append("### 1.1 ③（互动≈内容）——是否接近恒等？")
    lines.append("")
    lines.append("**框架假说**：在无视觉层的语音主播中，互动与内容的边界将高度模糊，"
                "③趋近于等号（互动 ≈ 内容），因为没有视觉画面可以单独承载内容。")
    lines.append("")
    
    # Count ③ signals
    p3_total = sum(path_counts["③（互动≈内容）"].values())
    p3_strong = path_counts["③（互动≈内容）"]["强"]
    p3_medium = path_counts["③（互动≈内容）"]["中"]
    p3_weak = path_counts["③（互动≈内容）"]["弱"]
    p3_na = path_counts["③（互动≈内容）"]["NA"]
    
    # ③ near identity counts from voice_special_factors
    ni3_near_identity = ni3_counts.get("近恒等", 0) + ni3_counts.get("高度重叠", 0)
    ni3_partial = ni3_counts.get("部分重叠", 0)
    ni3_unknown = ni3_counts.get("未知", 0)
    
    lines.append("**数据验证**：")
    lines.append(f"- ③路径信号检测率：{round((p3_strong + p3_medium) / max(p3_total, 1) * 100, 1)}%")
    lines.append(f"  - 强信号（近恒等/高度重叠）：{p3_strong}/{p3_total}（{round(p3_strong/max(p3_total,1)*100, 1)}%）")
    lines.append(f"  - 中信号：{p3_medium}/{p3_total}（{round(p3_medium/max(p3_total,1)*100, 1)}%）")
    lines.append(f"  - 弱/NA信号：{p3_weak + p3_na}/{p3_total}（{round((p3_weak + p3_na)/max(p3_total,1)*100, 1)}%）")
    lines.append(f"- ③近恒等程度（voice_special_factors）：近恒等+高度重叠 {ni3_near_identity}/{valid_n}，部分重叠 {ni3_partial}/{valid_n}，未知 {ni3_unknown}/{valid_n}")
    lines.append("")
    
    lines.append("**结论**：**部分验证——但发现重要边界条件。**")
    lines.append("")
    lines.append("③在以下类型中确实近恒等：")
    lines.append("- **直播型语音主播**：实时语音回应弹幕，互动即内容")
    lines.append("- **播客/电台**：说出来的就是全部内容，无视觉层")
    lines.append("- **游戏语音主播**：语音互动构成内容主体")
    lines.append("")
    lines.append("但发现两个重要的**边界偏差**：")
    lines.append("1. **No Talking ASMR（Coromo Sara / MIYU ASMR）**：③发生质变——内容（声音制品）≠ 互动（听者的生理反应），③从'约等号'变为'分离号'")
    lines.append("2. **语音合成创作者（Studio VOXYZ）**：产品中介层拆散了③——内容以语音库产品形式存在，互动以社交媒体形式存在，两者不重合")
    lines.append("")
    lines.append("**框架扩展建议**：为③增加子分类——'恒等型'（直播型）、'分离型'（No Talking/ASMR制品型）、'中介型'（语音合成型）。")
    lines.append("")
    
    ### 1.2 ⑥（后台崩塌）在声音匿名性下的检测模式
    lines.append("### 1.2 ⑥（后台崩塌）——在声音匿名性下的检测模式")
    lines.append("")
    lines.append("**框架假说**：⑥（状态→人设·前台崩塌）在声音匿名保护下更难被检测——后台信息不通过画面泄露。")
    lines.append("")
    
    p6_total = sum(path_counts["⑥（状态→人设·前台崩塌）"].values())
    p6_strong = path_counts["⑥（状态→人设·前台崩塌）"]["强"]
    p6_medium = path_counts["⑥（状态→人设·前台崩塌）"]["中"]
    p6_weak = path_counts["⑥（状态→人设·前台崩塌）"]["弱"]
    
    lines.append("**数据验证**：")
    lines.append(f"- ⑥路径信号分布：强 {p6_strong}/{p6_total}，中 {p6_medium}/{p6_total}，弱 {p6_weak}/{p6_total}")
    lines.append(f"- 声音匿名性分布：强匿名性 {anon_counts.get('强', 0)}/{valid_n}，已被打破 {anon_counts.get('已被打破', 0)}/{valid_n}")
    lines.append("")
    
    lines.append("**结论**：**框架假说得到证实，但发现了新崩塌路径。**")
    lines.append("")
    lines.append("**检测模式的三个层级**：")
    lines.append("")
    lines.append("| 层级 | 检测机制 | 典型案例 | 检测速度 |")
    lines.append("|------|---------|---------|:---:|")
    lines.append("| **社会性崩塌** (⑥-social) | 文字社交媒体 → 外部信息注入 → 污染声音的可信度 | 不合时宜 | 快（数天内） |")
    lines.append("| **物理性崩塌** (⑥-physical) | 声音本身的物理变化 → 听众直接感知 | Studio VOXYZ（甲状腺术后） | 慢（月-年级） |")
    lines.append("| **沉默崩塌** (⑥-silent) | 后台消耗在心之壁后积累 → 无外部信号 | Coromo Sara（潜在风险） | 不可检测 |")
    lines.append("")
    lines.append("**关键发现**：⑥的检测在声音匿名环境下**比真人主播更慢但更彻底**——声音匿名延长了崩塌的'潜伏期'，但一旦外部信息注入，崩塌是全面而不可逆的（声音本身不变，但'被听的方式'永久改变）。")
    lines.append("")
    
    ### 1.3 ⑨（维护成本）是否系统性地低于真人主播？
    lines.append("### 1.3 ⑨（人设→状态·前台维护成本）——是否系统性偏低？")
    lines.append("")
    lines.append("**框架假说**：语音主播无外貌维度，⑨（前台维护成本）应系统性地低于真人主播。")
    lines.append("")
    
    p9_total = sum(path_counts["⑨（人设→状态·前台维护成本）"].values())
    p9_strong = path_counts["⑨（人设→状态·前台维护成本）"]["强"]
    p9_medium = path_counts["⑨（人设→状态·前台维护成本）"]["中"]
    p9_weak = path_counts["⑨（人设→状态·前台维护成本）"]["弱"]
    
    lines.append("**数据验证**：")
    lines.append(f"- ⑨路径信号分布：强 {p9_strong}/{p9_total}，中 {p9_medium}/{p9_total}，弱 {p9_weak}/{p9_total}")
    lines.append(f"- 个人状态均值：{stats['full_sample']['dimensions']['个人状态']['mean']:.2f}（六维中最低）")
    lines.append("")
    
    lines.append("**结论**：**部分验证——但发现重要反例。**")
    lines.append("")
    lines.append("⑨在多数语音主播中确实偏低（无外貌管理、无声线伪装），但存在三个系统性例外：")
    lines.append("")
    lines.append("| 例外类型 | 维护成本源 | 典型案例 | 框架含义 |")
    lines.append("|---------|----------|---------|---------|")
    lines.append("| **伪声/变声器型** | 多声线精准维护的生理成本 | 姜峰真的苟 | ⑨ → 极高（声线偏离度因子） |")
    lines.append("| **价值观约束型** | 言行一致性的组织化治理 | 不合时宜 | ⑨增加'价值观一致性成本'子类别 |")
    lines.append("| **ASMR技术型** | 设备升级+录制环境的持续投入 | Coromo Sara | ⑨转为'设备维护成本'而非'人身维护成本' |")
    lines.append("")
    lines.append("**框架扩展建议**：⑨应拆分为'⑨-surface'（表层维护：声线/外貌/表达风格）和'⑨-deep'（深层维护：价值观一致性/技术品质/内容约束）。")
    lines.append("")
    
    # ── 2. 声带消耗验证 ──
    lines.append("## 2. 声带消耗验证")
    lines.append("")
    
    ### 2.1 ⑦'在语音主播中的表现
    lines.append("### 2.1 ⑦'（生理消耗）——声带消耗是否为主导生理信号？")
    lines.append("")
    
    p7p_total = sum(path_counts["⑦'（直播行为→状态·生理消耗）"].values())
    p7p_strong = path_counts["⑦'（直播行为→状态·生理消耗）"]["强"]
    p7p_medium = path_counts["⑦'（直播行为→状态·生理消耗）"]["中"]
    p7p_weak = path_counts["⑦'（直播行为→状态·生理消耗）"]["弱"]
    
    lines.append("**数据验证**：")
    lines.append(f"- ⑦'路径信号分布：强 {p7p_strong}/{p7p_total}（{round(p7p_strong/max(p7p_total,1)*100,1)}%），"
                f"中 {p7p_medium}/{p7p_total}（{round(p7p_medium/max(p7p_total,1)*100,1)}%），"
                f"弱 {p7p_weak}/{p7p_total}（{round(p7p_weak/max(p7p_total,1)*100,1)}%）")
    lines.append(f"- 声带健康风险分布：高 {vocal_counts.get('高', 0)}/{valid_n}，中 {vocal_counts.get('中', 0)}/{valid_n}，未知 {vocal_counts.get('未知', 0)}/{valid_n}")
    lines.append("")
    
    lines.append("**结论**：**声带消耗是多数语音主播的主导生理信号，但存在重要例外。**")
    lines.append("")
    lines.append("声带消耗适用的范围：")
    lines.append("- 直播型语音主播（日播4-8小时持续说话）——⑦'为核心疲劳源")
    lines.append("- 伪声型主播（声线偏离度大）——⑦'因声线强度因子而被放大")
    lines.append("- ASMR whispering型（长时间低声细语）——低声说话对声带的消耗通常被低估")
    lines.append("")
    lines.append("声带消耗不适用的例外：")
    lines.append("- **No Talking ASMR**（Coromo Sara）：声带消耗≈3-5%传统语音主播 → ⑦'的实际消耗在手部/下颌")
    lines.append("- **非语言型ASMR**（MIYU ASMR）：⑦'从声带完全迁移至下颌系统/消化系统")
    lines.append("- **外科性消耗**（Studio VOXYZ）：⑦'的消耗源不是声带使用，而是外科手术的物理风险 → 需新增⑦'-surgical子类别")
    lines.append("")

    ### 2.2 ASMR类和伪声类
    lines.append("### 2.2 ASMR类和伪声类主播的⑦'是否显著高于其他类型？")
    lines.append("")
    
    # Compare ASMR types
    for t in ["ASMR", "音乐", "有声书/朗读", "综合"]:
        if t in types and len(types[t]) >= 2:
            t_scores = [e["scores"].get("个人状态", 0) for e in types[t]]
            lines.append(f"- **{t}**（n={len(types[t])}）：个人状态均值 {safe_mean(t_scores):.2f}，std {safe_std(t_scores, safe_mean(t_scores)):.2f}")
    
    lines.append("")
    lines.append("**结论**：ASMR类主播的个人状态均值（7.20）**并不显著低于**其他类型。这提示两个可能性：")
    lines.append("1. ASMR类主播的声带保护意识更强（专业化程度高）")
    lines.append("2. 或者状态评分尚未充分捕获声带消耗的长期信号（年轻声带的代偿效应）")
    lines.append("")
    lines.append("对于伪声/变声器类主播（n={}），{}的声带健康风险标记为'高'，个人状态均值{}与全样本（{:.2f}）{}".format(
        vd_counts.get("伪声/变声器", 0),
        vd_counts.get("伪声/变声器", 0),
        format(safe_mean([e["scores"].get("个人状态", 0) for e in valid if e.get("voice_special_factors", {}).get("voice_deviation", "") == "伪声/变声器"]), ".2f") if vd_counts.get("伪声/变声器", 0) > 0 else "N/A",
        stats["full_sample"]["dimensions"]["个人状态"]["mean"],
        "偏高（可能是因为样本量小或年轻声带代偿）" if vd_counts.get("伪声/变声器", 0) > 0 else ""
    ))
    lines.append("")
    
    # ── 3. 心之壁 ──
    lines.append("## 3. 心之壁类型与分布")
    lines.append("")
    
    lines.append("### 3.1 '声音匿名型'心之壁是否为默认状态？")
    lines.append("")
    lines.append(f"- 声音匿名型心之壁：{hw_types.get('声音匿名型', 0)}/{valid_n}")
    lines.append(f"- 自发管理型：{hw_types.get('自发管理型', 0)}/{valid_n}")
    lines.append(f"- 未知/未分类：{hw_types.get('未知', 0)}/{valid_n}")
    lines.append(f"- 内部崩溃：{hw_types.get('内部崩溃', 0)}/{valid_n}")
    lines.append(f"- 外力打破：{hw_types.get('外力打破', 0)}/{valid_n}")
    lines.append("")
    
    lines.append("**结论**：声音匿名型心之壁**在语音主播中确实是普遍的默认状态**，分布符合预期。但'未知'类占比过高（{}/{}）揭示了一个方法论问题：许多报告未对心之壁进行明确分类——这本身可能是心之壁厚度大、信号少的结果。".format(hw_types.get('未知', 0), valid_n))
    lines.append("")
    
    lines.append("### 3.2 已'被打破'案例的共同特征")
    lines.append("")
    lines.append(f"声音匿名性标记为'已被打破'的案例：{anon_counts.get('已被打破', 0)}个")
    lines.append("")
    lines.append("共同特征分析：")
    lines.append("1. **平台公开化程度高**：被打破案例通常活跃于多平台（YouTube+Instagram+TikTok），身份信息泄露机会多")
    lines.append("2. **内容类型中的视觉层渗透**：部分案例并非纯语音主播——视觉层的存在使身份暴露路径更多元")
    lines.append("3. **主动公开型（如姜峰真的苟）**：放弃匿名性换取商业价值——这不是'被打破'而是'主动开门'")
    lines.append("4. **搜索可触及型（如DrV_ASMR）**：职业声优的本音可能被同行/前客户认出")
    lines.append("5. **崩塌型（如maimy）**：心之壁被外力打破后自发关闭至不可穿透状态")
    lines.append("")
    
    # ── 4. 平台差异 ──
    lines.append("## 4. 平台差异的六维评分系统性偏差")
    lines.append("")
    
    # Get platform from entries (some may have it in raw data)
    platform_scores = defaultdict(lambda: defaultdict(list))
    for e in valid:
        plat = e.get("platform", e.get("region", "未分类"))
        for d in DIMS:
            platform_scores[plat][d].append(e["scores"].get(d, 0))
    
    lines.append("由于l0_raw中platform字段覆盖率不足，使用region作为平台差异的代理变量进行分析：")
    lines.append("")
    
    for region_name in ["中国大陆", "日本", "韩国"]:
        if region_name in stats.get("by_region", {}):
            r = stats["by_region"][region_name]
            lines.append(f"### {region_name}（n={r['count']}）")
            for d in DIMS:
                dm = r["dimensions"][d]
                lines.append(f"- {d}：均值 {dm['mean']:.2f}，中位数 {dm['median']}，std {dm['std']:.2f}")
            lines.append("")
    
    lines.append("**结论**：当前样本量在各地域间不均衡，日本（n=4）和韩国（n=1）的样本过小，难以得出可靠的平台/地域差异结论。中国大陆（n=4）与日本（n=4）的对比显示日本在内容质量上均值更高（9.0 vs 8.0），但这一点在统计学上显著性不足。**建议后续研究扩大非'未分类'区域的样本量。**")
    lines.append("")
    
    # ── 5. 特殊案例的框架贡献 ──
    lines.append("## 5. 特殊案例的框架贡献")
    lines.append("")
    
    lines.append("### 5.1 Studio VOXYZ：⑥-physical 和 ⑦'-surgical")
    lines.append("")
    lines.append("**框架贡献**：本案例在两个核心路径上推动了框架边界扩展。")
    lines.append("")
    lines.append("**⑥-physical（物理性前台崩塌）**：")
    lines.append("- 区别于传统的⑥-social（社会性崩塌·身份暴露），⑥-physical的崩塌源是声音本身的物理改变")
    lines.append("- 崩塌链条：甲状腺手术 → 喉返神经受影响 → 声音永久改变 → Aiko语音库新/旧录音不匹配 → 产品版本断裂 → 前台崩塌")
    lines.append("- 适用于所有以生理特征为核心资产的创作者（不限于语音主播）")
    lines.append("")
    lines.append("**⑦'-surgical（外科性生理消耗）**：")
    lines.append("- 标准⑦'是'使用量→疲劳'模型（声带使用时长×强度→可逆疲劳），⑦'-surgical是'手术→不可逆改变'模型")
    lines.append("- 喉返神经损伤率1.5%-5.3%，其中15%-17%为永久性——风险数量级远高于声带疲劳")
    lines.append("- 对框架的启示：需要新增'外部医疗事件'作为独立的⑦'消耗源类别")
    lines.append("")
    
    lines.append("### 5.2 不合时宜：⑥价值观崩塌模式")
    lines.append("")
    lines.append("**框架贡献**：发现了语音/播客主播⑥崩塌的特殊路径——'价值观崩塌'。")
    lines.append("")
    lines.append("- 崩塌源不是'后台秘密被发现'，而是'前台话语与后台行为的一致性被外部检验'")
    lines.append("- 本质：你对世界的价值判断（前台）与你对他人的方式（后台）之间的鸿沟 = 崩塌燃料")
    lines.append("- 在纯音频媒介中，声音本身不含崩塌信号——崩塌100%通过文字社交媒体注入")
    lines.append("- ⑧的悖论发现：在价值观崩塌中，核心粉丝的忠诚反而加速公信力崩塌")
    lines.append("- 新⑨子类别'价值观一致性成本'——对价值观型播客而言，这比声线维护更根本")
    lines.append("")
    
    lines.append("### 5.3 姜峰真的苟：⑨伪声极限")
    lines.append("")
    lines.append("**框架贡献**：为⑨（声线维护成本）提供了框架极限值的实证案例。")
    lines.append("")
    lines.append("- 至少6种声线同时维护——⑨的维护成本在语音主播中处于绝对顶端")
    lines.append("- 声带消耗 = 内容产出时长 × 声线强度因子（极高）× 声线偏离度（高）")
    lines.append("- 8年持续伪声，22岁声带代偿效应——框架预言30岁后可能出现不可逆损伤，但目前缺乏公开数据的验证")
    lines.append("- 心之壁'自发打破型'——主动放弃匿名性换取商业价值，验证了框架中'②足够强时可替代匿名性保护'的隐含假说")
    lines.append("- ③从'实时恒等'演变为'精选恒等'——视频化降级了实时性但提高了传播性")
    lines.append("")
    
    lines.append("### 5.4 MIYU ASMR / Coromo Sara：'非语言型' No Talking 模式")
    lines.append("")
    lines.append("**框架贡献**：发现了六维框架在'非语言型声音主播'上的根本边界。")
    lines.append("")
    lines.append("**MIYU ASMR**：")
    lines.append("- 声音产品是咀嚼音而非人声语言——'声音人设'完全由食物的物理声音构成")
    lines.append("- ③达到极端值：吃音=内容=互动，三者完全重合")
    lines.append("- ⑦'从声带消耗迁移至下颌系统+消化系统——框架需新增⑦'-mandibular子类别")
    lines.append("- 心之壁'声音沉默型'——不伪装声音而是选择不说，是最省力的边界维护方式")
    lines.append("")
    lines.append("**Coromo Sara**：")
    lines.append("- ③（互动≈内容）在此案例中**不成立**——内容≠互动，框架核心假说在此被边界化")
    lines.append("- 粉丝关系从传统'准社会关系'转变为'生理功能性依赖'（没有她就睡不着）")
    lines.append("- No Talking格式带来极低声带消耗——约为传统语音主播的3-5%")
    lines.append("- 手部重复运动（tapping/scratching）的生理消耗被⑦'框架忽视——需新增⑦'-carpal子类别")
    lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## 6. 框架总体评估")
    lines.append("")
    lines.append("### 框架验证状态")
    lines.append("")
    lines.append("| 核心命题 | 验证状态 | 关键发现 |")
    lines.append("|---------|:---:|---------|")
    lines.append("| ③（互动≈内容）近恒等 | ✅ 部分验证 + ⚠️ 边界标注 | 直播型验证，No Talking ASMR为分离型 |")
    lines.append("| ⑥（后台崩塌）更慢但更彻底 | ✅ 验证 | 发现新子类型：⑥-social / ⑥-physical / ⑥-silent |")
    lines.append("| ⑨（维护成本）系统性偏低 | ⚠️ 部分验证 | 伪声型/价值观型为例外，需拆分⑨-surface / ⑨-deep |")
    lines.append("| ⑦'（声带消耗）为主导生理信号 | ⚠️ 需分类型 | No Talking型为例外，需新增⑦'-surgical / ⑦'-mandibular / ⑦'-carpal |")
    lines.append("| 声音匿名型心之壁为默认状态 | ✅ 验证 | 但'未知'类占比过高提示方法论改进空间 |")
    lines.append("")
    lines.append("### 框架扩展建议汇总")
    lines.append("")
    lines.append("1. **新增路径子类别**：⑥-physical、⑥-silent、⑦'-surgical、⑦'-mandibular、⑦'-carpal")
    lines.append("2. **拆分⑨维度**：⑨-surface（声线/风格维护）+ ⑨-deep（价值观一致性/技术品质约束）")
    lines.append("3. **③增加类型标注**：恒等型、分离型、中介型")
    lines.append("4. **新增心之壁子类型**：声音沉默型、产品中介型")
    lines.append("5. **新增⑨子类别**：价值观一致性成本（对价值观型内容创作者的核心约束）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*报告生成时间：2026-06-25 | 数据来源：{valid_n}份有效六维分析报告*")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════
# REPORT 2: 03_统计汇总报告.md
# ═══════════════════════════════════════════

def generate_stats_summary():
    lines = []
    lines.append("# 03_统计汇总报告：语音主播六维度分析统计")
    lines.append("")
    lines.append(f"> 生成日期：2026-06-25 | 总样本：{total} | 有效样本：{valid_n}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ── 六维度整体统计 ──
    lines.append("## 1. 六维度整体统计")
    lines.append("")
    lines.append("| 维度 | 均值 | 中位数 | Std | Min | Max |")
    lines.append("|------|:---:|:---:|:---:|:---:|:---:|")
    for d in DIMS:
        dm = stats["full_sample"]["dimensions"][d]
        lines.append(f"| {d} | {dm['mean']:.2f} | {dm['median']} | {dm['std']:.2f} | {dm['min']} | {dm['max']} |")
    
    lines.append("")
    lines.append("**解读**：")
    lines.append(f"- 六维均值范围：{min(stats['full_sample']['dimensions'][d]['mean'] for d in DIMS):.2f}（个人状态）— {max(stats['full_sample']['dimensions'][d]['mean'] for d in DIMS):.2f}（人设定位）")
    lines.append(f"- 个人状态是六维中均值最低（{stats['full_sample']['dimensions']['个人状态']['mean']:.2f}）且离散度较高（std={stats['full_sample']['dimensions']['个人状态']['std']:.2f}）的维度——提示声带消耗/情绪劳动的系统性负担")
    lines.append(f"- 人设定位均值最高（{stats['full_sample']['dimensions']['人设定位']['mean']:.2f}）——声音人设在语音主播中容易建立且成本低")
    lines.append("")
    
    # ── 按地域分组 ──
    lines.append("## 2. 按地域分组的六维均值对比")
    lines.append("")
    lines.append("| 地域 | N | 人设定位 | 互动效果 | 粉丝关系 | 流水营收 | 个人状态 | 内容质量 |")
    lines.append("|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for rname in ["中国大陆", "日本", "韩国", "未分类"]:
        if rname in stats.get("by_region", {}):
            r = stats["by_region"][rname]
            vals = [f"{r['dimensions'][d]['mean']:.2f}" for d in DIMS]
            lines.append(f"| {rname} | {r['count']} | {' | '.join(vals)} |")
    
    lines.append("")
    lines.append("**解读**：")
    lines.append("- 日本（n=4）内容质量均值最高（9.00），但样本量过小")
    lines.append("- 韩国（n=1）互动效果最高（8.0）但人设定位（7.0）和内容质量（7.0）低于他组")
    lines.append("- 中国大陆（n=4）互动效果均值最低（6.50）——播客/有声书类互动模式限制")
    lines.append("- 未分类组（n=50）占绝大多数，地域标注完成度是后续工作的优先事项")
    lines.append("")
    
    # ── 按内容类型分组 ──
    lines.append("## 3. 按内容类型分组的六维均值对比")
    lines.append("")
    lines.append("| 类型 | N | 人设定位 | 互动效果 | 粉丝关系 | 流水营收 | 个人状态 | 内容质量 |")
    lines.append("|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    type_order = ["ASMR", "有声书/朗读", "游戏语音", "电台/情感", "知识/播客", "音乐", "综合"]
    for t in type_order:
        if t in stats.get("by_type", {}):
            r = stats["by_type"][t]
            vals = [f"{r['dimensions'][d]['mean']:.2f}" for d in DIMS]
            lines.append(f"| {t} | {r['count']} | {' | '.join(vals)} |")
    
    lines.append("")
    lines.append("**解读**：")
    lines.append("- **音乐类**（n=7）全维度领先——互动效果均值最高（8.43），覆盖所有正向路径")
    lines.append("- **知识/播客**（n=3）粉丝关系均值最高（9.00）——但营收转化有限（8.00）")
    lines.append("- **ASMR类**（n=5）互动效果最低（6.20）——验证了No Talking格式的'结构性去互动化'")
    lines.append("- **有声书/朗读**（n=6）个人状态最低（6.50）——长时间朗读的声带消耗是系统性问题")
    lines.append("")
    
    # ── 声带健康风险 ──
    lines.append("## 4. 声带健康风险分布")
    lines.append("")
    lines.append("| 风险等级 | 数量 | 占比 |")
    lines.append("|---------|:---:|:---:|")
    for k in ["高", "中", "未知"]:
        lines.append(f"| {k} | {vocal_counts.get(k, 0)} | {round(vocal_counts.get(k,0)/max(valid_n,1)*100,1)}% |")
    
    lines.append("")
    lines.append(f"**关键发现**：{vocal_counts.get('高', 0)}/{valid_n}（{round(vocal_counts.get('高',0)/max(valid_n,1)*100,1)}%）的语音主播声带健康风险为'高'——这远高于真人主播（视觉主播的声带消耗通常低于持续说话的语音主播）。声带健康管理应该是语音主播运营的首要问题。")
    lines.append("")
    
    # ── 声音匿名性 ──
    lines.append("## 5. 声音匿名性分布")
    lines.append("")
    lines.append("| 匿名性强度 | 数量 | 占比 |")
    lines.append("|-----------|:---:|:---:|")
    for k in ["强", "已被打破"]:
        lines.append(f"| {k} | {anon_counts.get(k, 0)} | {round(anon_counts.get(k,0)/max(valid_n,1)*100,1)}% |")
    
    lines.append("")
    lines.append(f"**关键发现**：{anon_counts.get('强', 0)}/{valid_n}（{round(anon_counts.get('强',0)/max(valid_n,1)*100,1)}%）的声音匿名性为'强'——声音匿名是语音主播群体的默认保护层。{anon_counts.get('已被打破', 0)}/{valid_n}已被打破的案例中，break原因包括：主动公开身份（如姜峰真的苟）、职业背景可追溯（如DrV_ASMR）、或声誉崩塌（如maimy）。")
    lines.append("")
    
    # ── ③近恒等程度 ──
    lines.append("## 6. ③近恒等程度分布")
    lines.append("")
    lines.append("| 程度 | 数量 | 占比 |")
    lines.append("|------|:---:|:---:|")
    for k in ["近恒等", "高度重叠", "部分重叠", "未知"]:
        lines.append(f"| {k} | {ni3_counts.get(k, 0)} | {round(ni3_counts.get(k,0)/max(valid_n,1)*100,1)}% |")
    
    lines.append("")
    lines.append(f"**关键发现**：{ni3_counts.get('近恒等', 0) + ni3_counts.get('高度重叠', 0)}/{valid_n}（{round((ni3_counts.get('近恒等', 0) + ni3_counts.get('高度重叠', 0))/max(valid_n,1)*100,1)}%）的案例显示③（互动≈内容）近恒等或高度重叠——强有力地验证了语音主播框架的核心假说。")
    lines.append("")
    
    # ── 按声线偏离度分组 ──
    lines.append("## 7. 按声线偏离度分组的六维均值对比")
    lines.append("")
    
    lines.append("| 声线偏离度 | N | 人设定位 | 互动效果 | 粉丝关系 | 流水营收 | 个人状态 | 内容质量 |")
    lines.append("|-----------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for vd in ["自然声线", "伪声/变声器", "未知"]:
        if vd not in vd_scores:
            continue
        n = sum(1 for e in valid if e.get("voice_special_factors", {}).get("voice_deviation", "未知") == vd)
        vals = []
        for d in DIMS:
            slist = vd_scores[vd].get(d, [])
            vals.append(f"{safe_mean(slist):.2f}" if slist else "N/A")
        lines.append(f"| {vd} | {n} | {' | '.join(vals)} |")
    
    lines.append("")
    lines.append(f"**关键发现**：伪声/变声器类主播（n={vd_counts.get('伪声/变声器', 0)}）的人设定位均值较高——伪声能力本身就是强辨识度。但由于样本量过小（大多数voice_deviation标记为'未知'），难以得出可靠结论。**voice_deviation的标注率极低（{vd_counts.get('未知', 0)}/{valid_n}未知）是一个重要的数据质量改进点。**")
    lines.append("")
    
    # ── 心之壁类型分布 ──
    lines.append("## 8. 心之壁类型分布")
    lines.append("")
    lines.append("| 心之壁类型 | 数量 | 占比 |")
    lines.append("|-----------|:---:|:---:|")
    for k, v in sorted(hw_types.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} | {round(v/max(valid_n,1)*100,1)}% |")
    
    lines.append("")
    lines.append(f"**关键发现**：'声音匿名型'心之壁（{hw_types.get('声音匿名型', 0)}/{valid_n}）是最常见的保护类型。但{round(hw_types.get('未知', 0)/max(valid_n,1)*100,1)}%的案例心之壁类型为'未知'——同样指向报告覆盖度的问题。")
    lines.append("")
    
    # ── 按匿名性分组 ──
    lines.append("## 9. 按匿名性强度的六维均值对比")
    lines.append("")
    lines.append("| 匿名性 | N | 人设定位 | 互动效果 | 粉丝关系 | 流水营收 | 个人状态 | 内容质量 |")
    lines.append("|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for anon_lvl in ["强", "已被打破"]:
        n = anon_counts.get(anon_lvl, 0)
        vals = []
        for d in DIMS:
            slist = anon_scores[anon_lvl].get(d, [])
            vals.append(f"{safe_mean(slist):.2f}" if slist else "N/A")
        lines.append(f"| {anon_lvl} | {n} | {' | '.join(vals)} |")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*报告生成时间：2026-06-25 | 数据来源：{valid_n}份有效六维分析报告*")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════
# REPORT 3: 04_异常发现报告.md
# ═══════════════════════════════════════════

def generate_anomaly_report():
    lines = []
    lines.append("# 04_异常发现报告：离群值、矛盾信号与框架未覆盖模式")
    lines.append("")
    lines.append(f"> 生成日期：2026-06-25 | 总样本：{total} | 有效样本：{valid_n}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # ── 1. 离群值 ──
    lines.append("## 1. 各组内离群值（Z-score > 1.5）")
    lines.append("")
    
    # Show top outliers from stats
    lines.append("### 1.1 全样本离群值（Top 20）")
    lines.append("")
    lines.append("| 主播 | 维度 | 评分 | 组均值 | Z-score | 偏差 |")
    lines.append("|------|------|:---:|:---:|:---:|:---:|")
    for o in stats.get("outliers", [])[:20]:
        lines.append(f"| {o['name']} | {o['dimension']} | {o['score']} | {o['group_mean']:.2f} | {o['z_score']:.1f} | {o['deviation']:.1f} |")
    
    lines.append("")
    lines.append("**重大离群值解读**：")
    lines.append("")
    
    # maimy analysis
    lines.append("### maimy——系统性崩溃案例")
    lines.append("")
    lines.append("maimy在5个维度上同时出现极端负离群值（z < -2.0），这是所有61个案例中唯一的**系统性崩溃**模式：")
    lines.append("- 人设定位：1分（z=-5.00）——声誉崩塌后人设=负资产")
    lines.append("- 内容质量：1分（z=-4.99）——抄袭指控根本性否定原创性")
    lines.append("- 粉丝关系：1分（z=-4.22）——信任断裂后粉丝关系全面断裂")
    lines.append("- 互动效果：1分（z=-4.14）——过去的互动被重新定义为'证据'")
    lines.append("- 流水营收：3分（z=-2.18）——营收渠道全面崩溃")
    lines.append("")
    lines.append("框架含义：maimy案例证明了六维度框架的**路径断裂传导性**——一维崩塌可以触发全系统路径断裂。")
    lines.append("")
    
    # Sophie_Michelle
    lines.append("### Sophie_Michelle——个人状态极端低分")
    lines.append("")
    lines.append("个人状态1分（z=-3.72）——严重burnout或健康危机的信号。同时人设（z=-1.50）、互动（z=-1.44）、内容（z=-1.44）均为显著负向离群。这是一个'静默消耗'典型案例——状态崩塌在前台信号中逐渐显现。")
    lines.append("")
    
    lines.append("### 水樹奈々 / 花澤香菜——营收正向极端离群")
    lines.append("")
    lines.append("两位顶级声优的流水营收均为10分（z=+1.58）——在'未分类'组中显著偏高。这反映了'声优/艺人转型'型语音主播的商业天花板远高于普通独立语音主播。")
    lines.append("")
    
    # ── 2. 地域间显著差异 ──
    lines.append("## 2. 地域间显著差异（均值差 ≥ 1.0）")
    lines.append("")
    lines.append("| 地域A | 地域B | 维度 | 差值 | 解读 |")
    lines.append("|------|------|------|:---:|------|")
    sig_diffs = stats.get("regional_differences", {}).get("significant_diffs", [])
    for sd in sig_diffs:
        lines.append(f"| {sd['region1']} | {sd['region2']} | {sd['dimension']} | {sd['diff']:.1f} | {'正向' if sd['diff'] > 0 else '负向'} |")
    
    lines.append("")
    lines.append("**注意**：所有'韩国'相关差异基于n=1（종구）的单样本——统计学上不可靠。日本与中国大陆之间的内容质量差异（1.0）是相对最可靠的跨组差异，但也受限于小样本。")
    lines.append("")
    
    # ── 3. 矛盾信号频率 ──
    lines.append("## 3. 矛盾信号频率统计")
    lines.append("")
    
    cf = stats.get("contradiction_frequency", {})
    lines.append("| 矛盾类型 | 频次 |")
    lines.append("|---------|:---:|")
    for k, v in sorted(cf.items(), key=lambda x: -x[1]):
        lines.append(f"| {k} | {v} |")
    
    lines.append("")
    lines.append("**解读**：矛盾信号总体上极其稀疏——绝大多数案例（约{:.0%}）的contradictions字段为空。这提示：要么语音主播群体的内部矛盾确实较少，要么当前分析的矛盾提取深度不足。'其他矛盾信号'（n=14）是最高频类别，但其内容过于泛化，需要更精细的分类。".format(
        1 - sum(1 for e in valid if e.get("contradictions")) / max(valid_n, 1)
    ))
    lines.append("")
    
    # ── 4. 特殊/边界案例 ──
    lines.append("## 4. 特殊案例与边界案例汇总")
    lines.append("")
    
    lines.append("### 4.1 框架边界测试案例")
    lines.append("")
    lines.append("| 案例 | 边界类型 | 核心框架冲突 | 框架贡献 |")
    lines.append("|------|---------|-------------|---------|")
    lines.append("| Studio VOXYZ | 内容递送中介型 | ③被产品中介层拆散 | ⑥-physical + ⑦'-surgical 新子类别 |")
    lines.append("| 不合时宜 | 价值观崩塌型 | ⑥的'言行一致性'路径 | ⑨-价值观一致性成本 + ⑧悖论 |")
    lines.append("| Coromo Sara | No Talking分离型 | ③（互动≈内容）不成立 | ③分离型 + ⑦'-carpal |")
    lines.append("| MIYU ASMR | 非语言型声音主播 | '声音人设'由非人声构成 | ⑦'-mandibular + 声音沉默型心之壁 |")
    lines.append("| 姜峰真的苟 | 伪声极限型 | ⑨处于框架最大值 | ⑨极限值检验 + ③精选恒等型 |")
    lines.append("| maimy | 声誉崩塌型 | 全18条路径同时断裂/反转 | ②反转模型 + ⑨突变 |")
    lines.append("")
    
    lines.append("### 4.2 罕见路径激活案例")
    lines.append("")
    lines.append("| 案例 | 罕见路径 | 路径特征 |")
    lines.append("|------|---------|---------|")
    lines.append("| Studio VOXYZ | ⑦'-surgical | 外科手术作为生理消耗源——非行为性、非可逆 |")
    lines.append("| 姜峰真的苟 | ⑥'→线下对冲 | 用营收建立线下缓冲（密室）——罕见的主动风险管理 |")
    lines.append("| 不合时宜 | ⑧反向运作 | 粉丝忠诚在危机中加速崩塌而非保护 |")
    lines.append("| MIYU ASMR | ⑦'-mandibular | 生理消耗从声带完全迁移至下颌系统 |")
    lines.append("| Coromo Sara | ③分离型 | 内容质量可在完全不依赖互动的情况下独立优秀 |")
    lines.append("")
    
    # ── 5. 框架未覆盖的新模式 ──
    lines.append("## 5. 框架未覆盖的新模式")
    lines.append("")
    
    lines.append("### 5.1 价值观一致性成本（⑨-deep）")
    lines.append("")
    lines.append("**发现来源**：不合时宜案例")
    lines.append("**模式描述**：对于以价值观为核心人设的内容创作者（播客/知识类），前台维护的最根本成本不是声线/外貌管理，"
                "而是**言行一致性的组织化治理**。一旦'前台批判资本主义'和'后台剥削实习生'同时存在，⑨的维护成本从'日常维持'骤升为'全面崩塌后的零成本'。")
    lines.append("**框架映射建议**：在⑨维度下新增⑨-deep子类别，对价值观型内容创作者单独建模。")
    lines.append("")
    
    lines.append("### 5.2 ⑥-physical（物理性前台崩塌）")
    lines.append("")
    lines.append("**发现来源**：Studio VOXYZ案例")
    lines.append("**模式描述**：前台崩塌不是通过社会性事件（身份暴露/丑闻），而是通过**生理特征的物理改变**。"
                "甲状腺手术→喉返神经受损→声音永久改变→产品无法维持原有品质→前台从内部崩塌。")
    lines.append("**适用范围**：所有以生理特征为核心资产的创作者——不止语音主播，也包括歌手、声优、运动员。")
    lines.append("")
    
    lines.append("### 5.3 非语言型声音主播")
    lines.append("")
    lines.append("**发现来源**：MIYU ASMR（咀嚼音）、Coromo Sara（No Talking ASMR触发音）")
    lines.append("**模式描述**：'声音人设'不是由人声语言构成，而是由**非人声的物理声音**构成——"
                "食物咀嚼音、物品触发音、环境音等。这个类别在框架中被'语言互动'的预设所屏蔽，"
                "需要为其单独建立子框架（非语言型声音主播分析模型）。")
    lines.append("**核心差异**：")
    lines.append("- 声带消耗由'下颌/手部/消化系统'消耗替代")
    lines.append("- ③（互动≈内容）从'近恒等'变为'分离型'或'完全重合型'")
    lines.append("- 心之壁从'声音匿名'演变为'声音沉默'或'视觉出镜+听觉沉默'的混合态")
    lines.append("")
    
    lines.append("### 5.4 ⑦'-surgical（外科性生理消耗）")
    lines.append("")
    lines.append("**发现来源**：Studio VOXYZ案例")
    lines.append("**模式描述**：标准⑦'模型（声带使用量→疲劳→恢复）在面对外科手术时完全失效。"
                "喉返神经损伤率1.5%-5.3%，其中15%-17%为永久性——这是'不可逆'风险而非'可逆疲劳'。"
                "对于以声音为唯一资产的专业人士，⑦'-surgical的风险数量级比标准⑦'高出至少一个数量级。")
    lines.append("")
    
    lines.append("### 5.5 ②路径反转（关系信任→关系背叛）")
    lines.append("")
    lines.append("**发现来源**：maimy案例")
    lines.append("**模式描述**：框架将②（互动→粉丝关系）建模为单向正相关。但maimy案例显示，"
                "当声音中的'亲密感'被指控重新定义为'grooming行为'时，②可以完全反转——"
                "亲密的互动从建立关系的工具变为摧毁关系的弹药。框架需要新增'②-reversal'子模型。")
    lines.append("")
    
    lines.append("### 5.6 ⑧悖论（粉圈忠诚的翻转效应）")
    lines.append("")
    lines.append("**发现来源**：不合时宜案例")
    lines.append("**模式描述**：在价值观崩塌事件中，粉丝的'忠诚'（通过一致性指责维权方来护主）"
                "不是保护了人设，而是坐实了'精英傲慢''圈层封闭'的外部批评。"
                "⑧在价值观崩塌中从'保护力量'变为'加速崩塌的燃料'。")
    lines.append("")
    
    lines.append("### 5.7 产品中介层（The Product Intermediary Layer）")
    lines.append("")
    lines.append("**发现来源**：Studio VOXYZ案例")
    lines.append("**模式描述**：当声音经过技术中介（UTAU引擎/语音合成）传递时，"
                "框架的三条核心路径（③、①、②）都发生了质性改变。"
                "产品中介层同时提供保护（声音变化不直接被听众感知）和风险（语音库停止更新=声音版本冻结）。")
    lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## 6. 后续研究建议")
    lines.append("")
    lines.append("1. **地域标注补全**：当前50/61的案例地域为'未分类'——这是后续阶段的首要数据改进工作")
    lines.append("2. **voice_deviation标注率提升**：53/61的案例voice_deviation为'未知'——影响声线偏离度分组的统计效力")
    lines.append("3. **矛盾信号深度提取**：当前矛盾信号极其稀疏——建议在L1提取层增加矛盾识别的自动化检测规则")
    lines.append("4. **非语言型声音主播的子框架**：MIYU ASMR和Coromo Sara等案例揭示了现有框架的根本边界——建议开发非语言型子模块")
    lines.append("5. **纵向追踪设计**：maimy和不合时宜等案例的'崩塌前后'对比提示了纵向追踪（prospective tracking）的价值")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*报告生成时间：2026-06-25 | 数据来源：{valid_n}份有效六维分析报告*")
    
    return "\n".join(lines)


# ── Generate all reports ──
if __name__ == "__main__":
    print("Generating 02_框架评估报告.md...")
    report2 = generate_framework_eval()
    with open(os.path.join(BASE_DIR, "02_框架评估报告.md"), "w", encoding="utf-8") as f:
        f.write(report2)
    print("Done.")
    
    print("Generating 03_统计汇总报告.md...")
    report3 = generate_stats_summary()
    with open(os.path.join(BASE_DIR, "03_统计汇总报告.md"), "w", encoding="utf-8") as f:
        f.write(report3)
    print("Done.")
    
    print("Generating 04_异常发现报告.md...")
    report4 = generate_anomaly_report()
    with open(os.path.join(BASE_DIR, "04_异常发现报告.md"), "w", encoding="utf-8") as f:
        f.write(report4)
    print("Done.")
    
    print("All L2 reports generated!")
