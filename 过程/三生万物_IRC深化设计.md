# 三生万物 · IRC 深化设计

> 本文档描述如何在现有 Collins 互动仪式链实现基础上，通过三个机制的深化，使引擎自然涌现命理学所观察到的结构性行为模式（生克、刑、十二长生、大运），而不引入任何命理术语或固定参数表。

---

## 一、现状诊断

### 当前 IRC 的实现层次

```
┌─────────────────────────────────────────────┐
│              当前 IRC 数据流                  │
├─────────────────────────────────────────────┤
│  turn 输入                                   │
│    ├─ surface_acting (sa)                    │
│    ├─ feedback (fb)                         │
│    ├─ conversation_quality (cq)              │
│    ├─ topic_switches (ts)                   │
│    └─ event_domain                          │
│                                             │
│  上一轮 EE  →  ritual_demand_mod (0.9/1.0/1.1)  ← 只看 1 轮！```
│  consecutive_failure >= 3 →  anticipatory_drain = 0.005 │
│                                             │
│  classify_ritual()  →  success/failure/partial │
│                         ↓                   │
│  ritual_chain.last_output  ← 覆写，不累积    │
│  ritual_memory.compressed_memories  ← 追加 │
│                                             │
│  能量变化 = total_support - total_demand      │
│  energy_pool += net_delta                    │
└─────────────────────────────────────────────┘
```

### 两个核心缺陷

| 缺陷 | 表现 | 后果 |
|------|------|------|
| **EE 无累积** | `ritual_chain.last_output.ee` 每轮覆写，只看上一轮 | 无法形成"最近 5 轮社交都很好所以现在社交域超稳"的惯性 |
| **EE 无自然衰减** | failure 的 EE 是 -0.3，但没有"时间疗愈"机制 | 角色一旦进入低 EE 就永远低，没有回升路径 |

---

## 二、三大深化机制

### 机制 A：EE 多轮累积池 (EE Reservoir)

**学术支撑**：Cayla & Auriacombe (2025) 民族志研究证实成功的仪式产生 ascending EE spirals，失败的仪式累积导致耗竭。Boyns & Luery (2015) 提出 negative EE 有自然半衰期。

#### 数据结构变更

```yaml
# state.yaml 新增字段
ritual_chain:
  # ... 保留现有字段 ...

  # 新增
  ee_reservoir: 0.0           # [-1.0, 1.0] 累积情感能量
  ee_half_life: 5             # 半衰期（轮数），从大五推导
  ee_domain_profile:          # 每个域的历史 EE 累积
    autonomy: 0.0
    social: 0.0
    financial: 0.0
    cognitive: 0.0
    peer: 0.0
```

#### 每轮 tick 的 EE 更新逻辑

```python
# ── 1. 仪式产出 EE（和现在一样）──
ritual_ee = {"success": 0.3, "failure": -0.3, "partial": 0.0}[ritual_outcome]

# ── 2. 注入累积池 ──
ee_reservoir = clamp(ee_reservoir + ritual_ee, -1.0, 1.0)

# ── 3. 自然衰减 (Negative EE Half-life) ──
decay_rate = 0.5 ** (1 / ee_half_life)  # half_life=5 → ~0.8706/轮
ee_reservoir *= decay_rate

# ── 4. 域特异性累积 ──
if event_domain:
    domain_profile[event_domain] = clamp(domain_profile[event_domain] + ritual_ee, -1.0, 1.0)
    domain_profile[event_domain] *= decay_rate

# ── 5. 用 ee_reservoir 替代 prev_ee 的 ritual_demand_mod ──
if ee_reservoir > 0.5:
    ritual_demand_mod = 0.7   # 高 EE，所有域消耗降低
elif ee_reservoir > 0.2:
    ritual_demand_mod = 0.85
elif ee_reservoir > -0.2:
    ritual_demand_mod = 1.0
elif ee_reservoir > -0.5:
    ritual_demand_mod = 1.15
else:
    ritual_demand_mod = 1.3   # 严重耗竭
```

#### 行为表现：EE 不再只看上一轮

- 连续 3 轮成功 → ee_reservoir 逐渐爬升 → demand 持续降低
- 连续 3 轮失败 → ee_reservoir 跌入负值 → demand 持续抬高
- 一轮成功不能抵消累积的负面 EE——需要多轮正面互动才能恢复

**对应命理效果**：「通用 spillover」——一个域的连续成功/失败通过 EE 池影响所有域，不需要方向性系数。


### 机制 B：Surface Acting 慢性消耗路径 (Chronic Pathway)

**学术支撑**：Deng et al. (2017) 在 *Personnel Psychology* 实证——surface acting → ego depletion → 跨域滞后伤害同事关系。这是「刑」和「害」延迟效应的现代心理学术语等价物。

#### 数据结构变更

```yaml
# state.yaml 新增字段
heart_wall:
  # ... 保留现有字段 ...

  # 新增
  cumulative_sa_load: 0.0     # [0, ∞) 累积表面表演负荷
  sa_recovery_rate: 0.02      # 每轮自然恢复量（大五推导）
```

#### 每轮 tick 的 SA 累积逻辑

```python
# ── 1. 本轮 SA 负荷 ──
sa_load_map = {"natural": -0.5, "normal": 0.0, "forced": 0.5, "challenged": 1.0}
sa_load = sa_load_map.get(sa, 0.0)

# ── 2. 累积池更新（大于 0 才累积，natural 会恢复）──
cumulative_sa_load = max(0, cumulative_sa_load + sa_load - sa_recovery_rate)

# ── 3. 慢性效应：侵蚀心之壁 ──
if cumulative_sa_load > 5.0:
    wall_integrity -= 0.01   # 加速磨损
elif cumulative_sa_load > 2.0:
    wall_integrity -= 0.005   # 缓慢磨损

# ── 4. 域特异性退化 ──
# 在某域反复 forced SA → 该域 resistance 缓慢下降
if sa in ("forced", "challenged") and event_domain:
    domain_resistance[event_domain] -= 0.001
    # "这个域的角色已经演不动了"
```

#### 行为表现

| cumulative_sa_load | 表现 |
|-------------------|------|
| < 1.0 | 健康，心之壁自然恢复 |
| 1.0 ~ 3.0 | 开始需要更多休息，偶尔出现 crack |
| 3.0 ~ 5.0 | integrity 持续下降，wall 变薄，后台信息泄露 |
| > 5.0 | 强制崩塌临近，角色无法在任何域维持 frontstage |

**对应命理效果**：
- **「刑」**——长期 forced surface acting 的慢性磨损，不是急性伤
- **「害」的延迟效应**——表面正常（warmth 不变），但 cumulative_sa_load 在后台累积。3-5 轮后才 crack，当时看不出来
- **「破」**——warmth 不变但 trust 下降，warmth/trust 分离已经是现有机制


### 机制 C：EE Tropism — 域吸引力动态 (Domain Attraction)

**学术支撑**：Collins (2004) 核心论断——"Human behaviour may be characterized as emotional energy tropism. The strongest energizing situation exerts the strongest pull." 人格不是先天给定的，是仪式链的累积产物。

#### 数据结构

已在机制 A 的 `ee_domain_profile` 中，无需新增字段。

#### 吸引力计算

```python
def compute_domain_attraction(state: dict) -> dict:
    profile = state["ritual_chain"]["ee_domain_profile"]
    memories = state["ritual_memory"]["compressed_memories"]

    attraction = {}
    for domain in ["autonomy", "social", "financial", "cognitive", "peer"]:
        # 基础分：该域的历史 EE 累积
        base = profile.get(domain, 0.0)

        # 近期加分：最近 3 轮该域有成功仪式
        recent = [m for m in memories[-3:]
                  if m.get("domain") == domain and m.get("outcome") == "success"]
        recency_bonus = 0.1 if recent else 0.0

        # 遗忘扣分：最近 3 轮该域无任何互动
        recent_any = [m for m in memories[-3:] if m.get("domain") == domain]
        neglect_penalty = -0.1 if not recent_any else 0.0

        attraction[domain] = base + recency_bonus + neglect_penalty

    return attraction
```

#### 域惯性 (Domain Inertia)

角色不会因某域 EE 突然上升 0.01 就切过去。切换有摩擦：

```python
current_dominant = state["ritual_chain"].get("dominant_domain")
switch_threshold = 0.1  # 基础阈值

# 粘性：保持越久，越难切换
unchanged_rounds = state["ritual_chain"].get("dominant_domain_unchanged", 0)
switch_threshold *= 1.2 ** min(unchanged_rounds, 5)  # 最多增长到 0.25

leader = max(attraction, key=attraction.get)
if attraction[leader] > attraction.get(current_dominant, -99) + switch_threshold:
    dominant_domain = leader
    unchanged_rounds = 0
else:
    dominant_domain = current_dominant
    unchanged_rounds += 1
```

**效果**：防止反复横跳，主导域变动是结构性的。

#### 自然涌现「大运」——不需要 10 轮固定周期

```
Phase 1: social 域连续成功 (T01-T08)
  → social profile=+0.52, dominant_domain=social
  → financial/cognitive 域长期不练，resistance 退化
  → 相当于「印星大运」

Phase 2: 脆弱累积 + 触发 (T09-T10)
  → financial 域 resistance 退化到很低
  → 偶然 financial 事件 → 大概率失败
  → ee_reservoir ↓，所有域 demand ↑

Phase 3: 连锁崩塌 (T11-T13)
  → social 域也开始吃力，连续失败
  → social profile ↓↓
  → dominant_domain 准备切换

Phase 4: 回避期 (T14-T18)
  → 角色 avoid 高消耗域
  → ee_reservoir 自然衰减回升
  → 相当于「墓/绝」

Phase 5: 新主导域 (T19-T30)
  → cognitive profile 此时最高（上一轮没被伤）
  → dominant_domain=cognitive
  → 相当于「食伤大运」
```

**周期长度完全由角色历史决定**——可能 8 轮，可能 30 轮。命理说"十年一换"是粗粒度观察的近似。


## 三、参数清单

相比命理属性整合的 14,400+ 组合空间，深化 IRC 只新增以下参数：

| 参数 | 来源 | 初始值 | 是否可调 |
|------|------|--------|---------|
| `ee_reservoir` 初始值 | 大五推导（高外向性→高初始值） | 0.0 | ✅ |
| `ee_half_life` | 大五推导（低神经质→长半衰期） | 5 轮 | ✅ |
| `ee_decay_rate` | 计算 = 0.5^(1/half_life) | ~0.87/轮 | — |
| `sa_recovery_rate` | 大五推导（低神经质→高恢复） | 0.02/轮 | ✅ |
| `chronic_sa_threshold` | 固定 | cum_sa_load > 2.0 | ✅ |
| `chronic_integrity_decay` | 固定 | 0.005/轮 | ✅ |
| `switch_threshold_base` | 固定 | 0.1 | ✅ |

**共 7 个新参数，3 个从大五推导，4 个有默认值。没有矩阵，没有 lookup table。**


## 四、不需要实现的命理属性

| 命理属性 | 理由 |
|---------|------|
| 五行生克矩阵 | EE 池提供通用跨域 spillover。方向性从各域自身 sensitivity 自动产生 |
| 十二长生阶段 | Negative EE 半衰期 + 回避机制 = 更精细的回升路径，不需要硬编码 12 阶段 |
| 格局判定 | EE tropism = 格局的行为等价物。规则推导的是因果链，不是分类标签 |
| 刑冲合害破会 | SA 慢性累积 = 刑，延迟崩塌 = 害，warmth/trust 分离 = 破 |
| 大运周期 | EE tropism + 域惯性 + 脆弱累积 → 自然涌现 |
| 命理具体系数 | **全部砍掉**——代码是机制，不是参数表 |


## 五、预期表现

50 轮后的状态日志示例：

```
T01-T08:  dominant_domain=social
  social EE profile=+0.52  [██░░░░]
  cognitive EE profile=+0.08  [░░░░░░]

T09-T10:  dominant_domain=cognitive
  social EE profile=+0.31  [█░░░░░]
  cognitive EE profile=+0.34  [█░░░░░]

T11-T13:  financial 域被触及，连续失败
  ee_reservoir=-0.45  "情感储备耗尽"
  all domains demand = 1.2x

T14-T18:  dominant_domain=peer
  peer EE profile=+0.18  [░░░░░░]
  cumulative_sa_load=3.2  "慢性表演消耗累积"

T19:  wall.integrity=0.38 → crack 信号
T20:  角色 avoid 高消耗域，dominant_domain=None

T21-T23:  ee_reservoir 自然衰减回升
  -0.31 → -0.25 → -0.19

T24-T30:  新周期，dominant_domain=cognitive
```

命理观察者会说：「24 轮之前印星大运，24 轮之后食伤大运。」
IRC 引擎的答案：「不是大运。是 social 域资源过度集中→其他域脆弱→financial 触发连锁崩塌→角色回避→cognitive 自然成为新吸引中心。每一步都有因果链可追溯。」


## 六、实现阶段与工作量

| 阶段 | 内容 | 时间 | 风险 | 改动文件 |
|------|------|------|------|---------|
| Phase 1 | EE 累积池 | 2-3h | 低 | cmd_tick EE 段 (~366-397) |
| Phase 2 | SA 慢性累积 | 2-3h | 低-中 | cmd_tick SA 段 (~460-470) |
| Phase 3 | EE Tropism + 域惯性 | 2-3h | 低 | cmd_tick 末尾新增 |
| Phase 4 | 参数调优 | 1-2h | 极低 | 全文件 |
| **合计** | | **1-1.5 天** | | |

### 具体改动文件

| 文件 | 函数/段 | 变更类型 |
|------|---------|---------|
| `compute_state.py` | `cmd_init()` | 修改：初始化 ee_reservoir 等新字段 |
| `compute_state.py` | `cmd_tick()` ~L366-397 | 修改：替换 prev_ee → ritual_demand_mod 为 ee_reservoir → 多级倍率 |
| `compute_state.py` | `cmd_tick()` ~L460-470 | 修改：新增 cumulative_sa_load 更新 + chronic integrity decay |
| `compute_state.py` | `cmd_tick()` ~L766 后 | 新增：compute_domain_attraction() 调用 + dominant_domain 写入 |
| `compute_state.py` | 新增 | `_update_ee_reservoir(state, ritual_ee)` |
| `compute_state.py` | 新增 | `_update_sa_load(state, sa)` |
| `compute_state.py` | 新增 | `compute_domain_attraction(state)` |
| `state_template.yaml` | ritual_chain 段 | 修改：新增字段 |
| `reference.md` | IRC 说明段 | 修改：更新机制说明 |


## 七、与命理属性整合的关系

| | 命理属性整合（原方案） | IRC 深化（本方案） |
|------|---------------------|-------------------|
| 参数空间 | 14,400+ 组合 | 7 个参数 |
| 实现周期 | 每个 Phase 1-3 天，Phase 4 高 | 合计 1-1.5 天 |
| 理论支撑 | 命理古籍（无现代对应） | Collins IRC + 多项实证研究 |
| 生克 | 硬编码方向性矩阵 | EE spillover → 从各域 sensitivity 自然产生方向性 |
| 大运 | 固定 10 轮轮换 | EE tropism + 域惯性 → 内生涌现 |
| 验证方式 | 调参 → 看分布 → 再调参 | EE tropism 因果链可追溯 |
| 工程风险 | 参数地狱 | 简单机制，深度涌现 |

**核心区别**：命理属性整合是把古人总结的 pattern 作为 code 写进去。IRC 深化是把产生 pattern 的机制实现了，然后让 pattern 自己长出来。


---

*基于 Collins (2004) Interaction Ritual Chains、Cayla & Auriacombe (2025) Emotional Energy in Service Interactions (Journal of Marketing)、Deng et al. (2017) Spillover Effects of Emotional Labor (Personnel Psychology)、Boyns & Luery (2015) Negative Emotional Energy (Social Sciences) 等学术证据。*
