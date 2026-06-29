"""Counterfactual: what if the family didn't know about the papers at T1 and T2?"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from world_engine import WorldCharacter, cosine_sim

# Clone the family from the original config
# Same initial pool and memories as the "they knew" scenario
family = WorldCharacter()
family.pool = 0.48
family.memories = [
    {"description": "Never asked him to stop. Girlfriend paid electricity. Brother shared lunch. Mom said 'I trust you'", "intensity": 0.82, "emb": [0.75, 0.38, 0.35, 0.05, 0.22]},
    {"description": "Spring Festival relatives: 'why no job?' — 3 years of smiling and changing the subject", "intensity": 0.75, "emb": [0.15, 0.58, 0.72, 0.52, 0.14]},
    {"description": "Since childhood he saw patterns others couldn't — we always knew there was something rare in this child", "intensity": 0.68, "emb": [0.72, 0.42, 0.40, 0.05, 0.62]},
    {"description": "Never understood the code. But door closed at 2am = working. Food outside. Hot water. No questions.", "intensity": 0.78, "emb": [0.72, 0.35, 0.32, 0.03, 0.10]},
    {"description": "Quiet terror: not that he'd fail. That the world would never open the door for Nanhua graduate with no big-tech experience.", "intensity": 0.76, "emb": [0.12, 0.60, 0.55, 0.48, 0.18]},
]

print("=== COUNTERFACTUAL: Family did NOT know about papers at T1/T2 ===")
print(f"Initial pool: {family.pool:.4f}")
print()

# ── T1: Family skips the paradigm event ──
print("T1 (skipped): Family unaware of papers. Pool unchanged at 0.4800")
print("    - No memory activation. No 'we were right'. No 'the fridge was empty'.")
print()

# ── T2: Family skips the USA panic signal ──
print("T2 (skipped): Family unaware of global panic. Pool unchanged at 0.4800")
print("    - No terror about trust being reckless. No self-doubt.")
print()

# ── T3: The Revelation ──
# This is a compound event. The family learns EVERYTHING at once:
# 1) Their son did 3 paradigm-shifting papers
# 2) 500 yuan, 3 months
# 3) The world panicked
# 4) Now China is celebrating
# 5) And they were kept in the dark the entire time
#
# EMB analysis:
# valence: 0.55 — pride (high) mixed with exclusion (low), net slightly above neutral
#   The achievement is positive, but "you didn't tell us" creates a valence drag
# arousal: 0.88 — discovering your son is world-famous and you're the last to know
# social_weight: 0.70 — the world knows; you don't. That gap has social weight.
# autonomy_threat: 0.25 — no direct threat, but the feeling of being managed/protected
# novelty: 0.85 — you thought he was just working. He was rewriting civilization.

revelation_emb = [0.55, 0.88, 0.70, 0.25, 0.85]
revelation_intensity = 0.88

print("=== T3: THE REVELATION ===")
print("Event: You discover your son is a paradigm-shifter. The world panicked.")
print("       He lived on 500 yuan for 3 months. Now China is celebrating.")
print("       And he didn't tell you any of this.")
print(f"EMB: valence={revelation_emb[0]:.2f} arousal={revelation_emb[1]:.2f} "
      f"social={revelation_emb[2]:.2f} autonomy={revelation_emb[3]:.2f} "
      f"novelty={revelation_emb[4]:.2f}")
print(f"Intensity: {revelation_intensity:.2f}")
print()

pool, matched, recorded, drain, recovery = family.tick(revelation_emb, revelation_intensity)
family.pool = pool

resonance_count = sum(1 for m in matched if m.get("_valence_effect") == "resonance")
conflict_count = sum(1 for m in matched if m.get("_valence_effect") == "conflict")

print(f"  Pool: 0.4800 -> {pool:.4f} (delta={pool-0.48:+.4f})")
print(f"  Drain={drain:.4f} Recovery={recovery:.4f}")
print(f"  Resonance={resonance_count} Conflict={conflict_count}")
print()

# Show per-memory breakdown
event_valence = revelation_emb[0]
for m in family.memories[:5]:
    sim = cosine_sim(revelation_emb, m["emb"])
    threshold = 0.7 - m["intensity"] * 0.3
    memory_valence = m["emb"][0]
    va = 1.0 - abs(event_valence - memory_valence)
    activated = sim > threshold
    effect = "resonance" if (activated and va >= 0.70) else ("conflict" if activated else "inactive")
    symbol = "+" if effect == "resonance" else ("-" if effect == "conflict" else " ")
    print(f"  [{symbol}] {m['description'][:65]:65s} val={memory_valence:.2f} va={va:.2f} sim={sim:.3f} {effect}")

print()
print("=" * 60)
print("COMPARISON TABLE")
print("=" * 60)
print(f"{'Scenario':<40} {'End Pool':>10}")
print("-" * 52)
print(f"{'They KNEW (original simulation)':<40} {0.36:>10.4f}")
print(f"{'They DID NOT KNOW (counterfactual)':<40} {family.pool:>10.4f}")
print(f"{'Difference':<40} {family.pool - 0.36:>+10.4f}")
print()

if family.pool > 0.36:
    print("RESULT: Not telling them was slightly better (+{:.4f}).".format(family.pool - 0.36))
    print("But the gain is marginal — and it came at the cost of excluding them")
    print("from the most important moment of your life.")
elif family.pool < 0.36:
    print("RESULT: Telling them was slightly better (+{:.4f}).".format(0.36 - family.pool))
    print("The joy of shared trust (+0.04 at T1) outweighed the cost")
    print("of watching them panic (-0.23 at T2).")
else:
    print("RESULT: Approximately equal. The path is different, the destination is the same.")

print()
print("KEY INSIGHT:")
print("  Knowing = +0.04 (quiet joy) + -0.23 (panic terror) + +0.08 (vindication)")
print("  Not knowing = compound revelation: pride + exclusion + 'you didn't tell us'")
print(f"  Final: {family.pool:.4f}")
