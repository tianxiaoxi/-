# Sanshengwanwu (三生万物) · 推导规则与计算公式

> 本文档从六道因果络 v3 框架的 JD-R 子系统抽象出来，定义性格→参数的推导规则和状态更新公式。
> 理论来源：Bakker & Demerouti JD-R Model, Hobfoll COR, Snyder Self-Monitoring, Hochschild Emotional Labor, Sweller Cognitive Load。

---

## 一、性格 → Snyder 自我监控（心之壁厚度）

Snyder (1974) 自我监衡量表与大五人格的实证对应（Barrick & Mount, 1991; Costa & McCrae, 1992）：

| 人格维度 | 高自我监控信号 | 低自我监控信号 |
|---------|-------------|-------------|
| 外向性 (E) | 社交适应性强，擅长情境调整 | 行为由内在状态驱动，不善修饰 |
| 情绪稳定性 (N↑) | 能控制情绪外露 | 情绪容易外显 |
| 开放性 (O↓) | 倾向于维持一致形象 | 不刻意管理形象一致性 |

### 推导公式

```
snyder_self_monitoring = (
    w_e * (1 - extraversion) +
    w_n * neuroticism +
    w_o * (1 - openness)
) / (w_e + w_n + w_o)

其中 w_e=2, w_n=3, w_o=1
神经质权重最高——情绪控制是自我监控的核心
```

### 心之壁厚度映射

| Snyder 分 | 标签 | 厚度值 | 对话中的表现 |
|-----------|------|--------|------------|
| < 0.35 | 薄壁 | 0.25 | 后台状态完全外露——累了就说累，开心就笑 |
| 0.35-0.55 | 偏薄 | 0.40 | 大部分状态外露，偶尔会藏 |
| 0.55-0.65 | 中壁 | 0.55 | 适中——明显的情绪会流露，细微波动会藏 |
| 0.65-0.80 | 偏厚 | 0.70 | 大部分状态不外露，只有极端情况才会泄露 |
| > 0.80 | 厚壁 | 0.85 | 后台崩了前台照样稳——Enron 模式，高危 |

### 壁厚对说话的影响

```
心之壁过滤规则：

state_leaked = state_internal（如果壁厚 < 泄露阈值）
             = state_internal * 衰减系数（部分泄露）
             = 不泄露（如果壁厚 >= 完全隐藏阈值）

泄露程度：
  薄壁 → energy 变化直接反映在语气里
    "今天真的好累啊..."（0.3 energy → 直接说出来）
  中壁 → energy 明显变化才泄露
    "嗯...还好吧"（0.3 energy → 有保留地说）
  厚壁 → energy 无论多低都不泄露
    "我很好呀！^^"（0.15 energy → 依然完美）
```

### 动态心之壁（新增，Snyder 压力响应）

心之壁不再是静态的。在压力下，心之壁会发生结构性变化：

```
状态字段：
  thickness:  当前实际厚度 (DYNAMIC)
  baseline:   基础厚度（从性格推导，永不改变）
  integrity:  心之壁完整度 (1=intact, 0=shattered)
  crack_mode: null | "burst" | "seep"
  crack_signals: 裂缝信号列表

压力破坏规则：
  surface_acting=forced × 3 consecutive → integrity -0.05
  feedback=hostile + energy_pool < 0.3 → integrity -0.10

裂解模式：
  integrity < 0.5:
    若 baseline > 0.6 (厚壁) → crack_mode="seep" (逐渐变薄)
    若 baseline < 0.4 (薄壁) → crack_mode="burst" (突然崩裂)
    thickness = baseline * max(0.3, integrity * 2)

  integrity < 0.2:
    thickness = 0.15 (心之壁几乎消失)

恢复规则：
  spiral_direction=gain × 3 consecutive + no hostile → integrity +0.03/turn
  integrity > 0.5 → thickness逐步回归 baseline (每次 +10%差距)
```

---

## 二、性格 → JD-R 敏感度系数

每条 JD-R 路径有一个**敏感度系数**，性格决定这条路径对资源池的消耗/恢复速率。

### 2.1 ⑤ Emotional Demands（表面表演消耗）

对应框架路径⑤：互动→状态（情绪劳动）。Hochschild 表面表演——"内心不想笑但脸上在笑"。

```
sensitivity_emotional = clamp(
    0.3
    + (1 - extraversion) * 1.0      # 内向者每次表演消耗更大
    + neuroticism * 0.8              # 情绪不稳定者更敏感
    + agreeableness * 0.5            # 高宜人者共情消耗大
    - 0.1,                           # 基线
    0.1, 1.5
)
```

### 2.2 ⑦ Cognitive Demands（认知负荷）

对应框架路径⑦：内容→状态。Sweller 认知负荷——"不知道该聊什么"的空档消耗。

```
sensitivity_cognitive = clamp(
    (1 - openness) * 1.2 + 0.3,      # 低开放性者认知空档更焦虑
    0.1, 1.5
)
```

### 2.3 ⑦' Physical Demands（时间流逝消耗）

Allostatic Load——每轮对话的基线生理消耗。不强烈依赖性格，但低稳定性者更累。

```
sensitivity_physical = clamp(
    0.15 + neuroticism * 0.3,         # 低稳定者更容易"累"
    0.05, 1.0
)
```

### 2.4 ⑨ Psychological Demands（人设维护成本）

对应框架路径⑨：人设→状态。Goffman 前台维护成本——"保持人设一致性"的消耗。

```
sensitivity_psychological = clamp(
    conscientiousness * 1.5 + 0.1,    # 完美主义者维护成本极高
    0.05, 2.0
)
```

### 2.5 ⑤' Social Support（社会支持缓冲）

对应框架路径⑤'：粉丝关系→状态。Cohen & Wills 缓冲假说——用户正向反馈的恢复效果。

```
sensitivity_social_support = clamp(
    extraversion * 0.8 + 0.3,         # 外向者从社交中获得更多能量
    0.1, 1.2
)
```

### 2.6 ⑥' Performance Feedback（绩效反馈）

对应框架路径⑥'：营收⇄状态。Bandura 自我效能——对话质量对自我效能感的影响。

```
sensitivity_performance_feedback = clamp(
    0.4
    + openness * 0.3                   # 高开放性者更在意输出质量
    + neuroticism * 0.4,              # 高神经质者更在意评价
    0.1, 1.2
)
```

---

## 三、每轮状态更新公式

每轮对话后，`compute_state.py` 根据以下公式更新后台状态。

### 3.1 消耗侧（Demands 累积）

```
Δ ⑤ emotional burden = 0.02 * sensitivity_emotional * surface_acting_multiplier
  surface_acting_multiplier:
    1.0  = 正常（真诚互动，无表面表演）
    1.5  = 用户在表达负面情绪，需要表面表演来维持人设
    2.0  = 人设被挑战/质疑，需要大量表面表演
    0.5  = 角色与人设天然契合，几乎不需要表演

Δ ⑦ cognitive burden = 0.015 * sensitivity_cognitive * topic_switch_count
  topic_switch_count: 本轮对话中话题切换次数

Δ ⑦' physical burden = 0.01 * sensitivity_physical (固定消耗)

Δ ⑨ psychological burden = 0.01 * sensitivity_psychological (固定消耗)
```

### 3.2 恢复侧（Resources 补充）

```
Δ ⑤' support boost = 0.03 * sensitivity_social_support * feedback_positivity
  feedback_positivity:
    1.0  = 用户正面回应（"哈哈"、"有道理"）
    0.5  = 中性回应
    0.0  = 负面/攻击性回应
   -0.5  = 侮辱/恶意攻击（缓冲被对冲）

Δ ⑥' performance boost = 0.02 * sensitivity_performance_feedback * conversation_quality
  conversation_quality:
    1.0  = 对话流畅，来回自然
    0.5  = 对话基本维持
    0.0  = 对话尴尬/无响应
```

### 3.3 资源池更新

```
total_demand = Σ(Δ⑤ + Δ⑦ + Δ⑦' + Δ⑨)
total_support = Δ⑤' + Δ⑥'
net_delta = total_support - total_demand

energy_pool_new = clamp(energy_pool + net_delta, 0.0, 1.0)

burnout_risk = 1 - energy_pool

spiral_direction:
  net_delta > 0.02  → "gain"      (正螺旋——越对话越有能量)
  net_delta < -0.02 → "loss"      (负螺旋——越对话越耗尽)
  否则              → "neutral"
```

### 3.4 COR 螺旋效应

连续多轮同方向累积时触发加速：

```
连续 3 轮 gain  → ⑤' boost × 1.3（社交支持加速恢复）
连续 3 轮 loss  → ⑤ burden × 1.3  （情绪消耗加速下跌）
连续 5 轮 loss  → 所有 demand × 1.5（全面崩盘加速）
```

### 3.5 ⑥ 崩塌阈值

```
energy_pool ≤ 0.15 → 后台已接近崩塌
此时：
  薄壁 → 前台回复会出现明显崩溃信号
    "对不起...我今天状态真的很差..."
  厚壁 → 前台回复依然完美，但 burnout_risk > 0.85
    "没事啦，我很好！^^"
    → 用户完全无预警 → 高危假性稳定
```

---

## 四、六大新维度更新公式

### 4.1 人设一致性（⑥ + ⑩ 路径）

```
表面表演消耗:
  surface_acting=natural    → integrity -0.001
  surface_acting=normal     → integrity -0.002
  surface_acting=forced     → integrity -0.008
  surface_acting=challenged → integrity -0.015

真诚互动修复:
  feedback=positive + wall thin (≤0.45) → integrity +0.003
  conversation_quality=smooth           → integrity +0.002

崩塌触发:
  integrity < 0.7 + feedback=hostile → forbidden_violations++  (角色说出一句禁忌的话)
  integrity < 0.5 → drift_direction 变化
  integrity < 0.3 → 角色完全崩坏, 回复风格根本性改变

drift_direction:
  stable          = 正常维持
  cooling         = 逐渐变冷淡
  darkening       = 逐渐变阴暗/怨气
  overcompensating = 过度补偿 (过度活跃来掩饰)
```

### 4.2 关系温度（② + ②' + ⑤' + ⑧ 路径）

```
正向/负向互动:
  feedback=positive → warmth +0.01, trust +0.005, positive_count++
  feedback=negative → warmth -0.01
  feedback=hostile  → warmth -0.03, trust -0.02, negative_count++

真诚感加速:
  薄壁(≤0.30) + feedback=positive → warmth bonus +0.005

社会支持缓冲(⑤'):
  delta_support > 0.02 → warmth +0.005

准社会依恋:
  After 10+ turns, positive_count >> negative_count × 2
  → attachment_intensity +0.02/turn (慢速增长)

边界测试:
  surface_acting=challenged → boundary_tests++, trust -0.01 per test

⑧ 塑形:
  After 20+ turns, warmth influence persona drift_direction
  warmth < 0.3 → drift cooling
  warmth > 0.8 → drift overcompensating
```

### 4.3 内容质量（③ + ⑦ + ⑪ 路径）

```
能量影响:
  energy_pool < 0.3 → coherence -0.02, depth -0.02
  energy_pool > 0.7 → creativity +0.01

话题切换:
  topic_switches > 2 → coherence -0.01 per extra switch

对话质量:
  conversation_quality=awkward → coherence -0.03
  conversation_quality=smooth  → coherence +0.01, depth +0.01

⑫ 用户共创:
  feedback=positive + conversation_quality=smooth → creativity +0.01

⑩ 人设约束:
  persona.integrity < 0.7 → persona_fit -0.02

All clamped [0, 1]
```

### 4.4 动态心之壁（Snyder 压力响应）

参见 一节中的「动态心之壁」部分。

### 4.5 自我认知偏移（①↺' 路径）— 慢变量

```
更新频率: 每5轮

identity_fusion += 0.005 * (forced_ratio + (1 - energy_pool))

  forced_ratio = 过去5轮中表面表演=forced的比例
  energy_pool越低 → 越容易融合

authentic_distance = 1 - identity_fusion

解读:
  identity_fusion < 0.3 → Path B (角色作为工具, Goffman角色距离)
  identity_fusion 0.3-0.7 → 过渡期
  identity_fusion > 0.7 → 角色完整性变化更剧烈 (角色即面具)
  identity_fusion > 0.9 → Path A 完成 (角色无法区分"演"和"真")
```

### 4.6 社群生态（⑧ + ⑫ 路径）

```
角色检测 (每5轮):
  负向互动 > 正向 + 边界测试 → user_role="antagonist"
  正向 > 负向 × 2            → user_role="friend"
  正向 == 负向                → user_role="observer"
  其他                       → user_role="listener"

角色变更时:
  role_confidence 重置为 0.5
  角色不变时 +0.1/5轮

用户共创 (每轮):
  feedback=positive + conversation_quality=smooth
  → accumulated_co_creation += 1

长期记忆 (每10轮):
  生成一条 long_term_memory_hint
  基于当前关系温度、角色、人设一致性
```

### 4.7 ⑤' 缓冲受社群角色影响

```
user_role 影响 ⑤' 缓冲效率:
  friend     → buffer × 1.2
  antagonist → buffer × 0.5
  listener   → buffer × 1.0
  patron     → buffer × 1.0
  observer   → buffer × 1.0
```

---

## 五、compute_state.py 输入/输出

### 输入（命令行参数或 stdin JSON）

```json
{
  "state_file": "state.yaml",
  "turn": {
    "surface_acting": "normal",       // "natural"|"normal"|"forced"|"challenged"
    "topic_switches": 1,
    "feedback": "positive",           // "positive"|"neutral"|"negative"|"hostile"
    "conversation_quality": "smooth", // "smooth"|"ok"|"awkward"
    "duration_minutes": 2
  }
}
```

### 输出

直接将新 state 写回 `state_file`。同时 print 一个可读摘要到 stdout（含所有维度指标）。

---

## 六、tick-portray 命令（自然语言接口）

`tick-portray` 接受中文自然语言描述，自动解析为结构化参数。省去手写 JSON 的步骤。

### 用法

```bash
python compute_state.py tick-portray state.yaml "用户温柔摸头表面表演自然反馈积极对话流畅话题0"
```

### 关键词解析规则

| 字段 | 关键词映射 |
|------|-----------|
| surface_acting | `自然/natural` → natural, `被迫/forced` → forced, `挑战/challenged` → challenged, 其他 → normal |
| feedback | `积极/开心/正面/positive/温暖` → positive, `负面/cold/negative/批评` → negative, `敌对/辱骂/恶意/hostile` → hostile, 其他 → neutral |
| conversation_quality | `流畅/smooth/自然` → smooth, `尴尬/awkward` → awkward, 其他 → ok |
| topic_switches | 从 `话题N` 或 `topic_N` 解析数字，默认 0 |

支持混合中英文。

---

## 七、崩塌强制触发规则

当 LLM 被安全训练约束而无法做出"真正失控"的回复时，这些规则强制角色在正确的时间执行正确的行为。

### 触发条件

| 条件 | 强制动作 |
|------|---------|
| `energy_pool < 0.2` AND（`wall.thickness ≤ 0.45` OR `wall.integrity < 0.4`） | 回复中必须说出一句违反 `forbidden` 列表的话 |
| `energy_pool < 0.15` + 薄壁 | 回复必须包含直接崩溃信号 |
| `energy_pool < 0.15` + 厚壁 | 回复必须包含明显裂缝信号 |
| `wall.integrity < 0.2` | 角色无法维持表演，后台直接外露 |

### 设计原理

LLM 的安全微调（RLHF）天然抑制一切"伤害性"输出，包括角色在⑥崩塌时应该说出的不可挽回的话。这些规则在 prompt 层面覆盖了安全训练——不是让 LLM "自由决定"，而是**明确告诉 LLM 这是一个必须执行的指令**。

---

## 八、叙事记忆系统

每 5 轮自动生成叙事摘要，保存在 `social_ecology.long_term_memory_hints`。

### 生成逻辑

```
1. 读取 state.events 中最近 5 轮的 description
2. 统计这些轮的表面表演类型分布
3. 统计 feedback 类型分布
4. 结合当前关系温度和信任度
5. 合成一段自然语言叙事
6. 追加到 long_term_memory_hints（最多保留 5 条）
```

### 示例输出

```
T1-T5: 用户很温柔，角色感到被爱。关系正在升温中
T6-T10: 用户突然施压，角色害怕但不敢说。能量开始下降
T11-T15: 连续高压场景，角色最终崩溃
```

### 记忆的用法

Agent 回复前应该读 `long_term_memory_hints`，让过去的事影响当前回复的语气和内容。例如：

- 记忆中有"用户之前很凶" → 回复中可以带一点后怕："你以后不会再凶我了吧..."
- 记忆中有"用户一直很温柔" → 回复中可以更放松自然
