"""Timing optimization: when should the family find out?
Searches all possible revelation timings to find the optimal moment."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from world_engine import WorldCharacter, cosine_sim
from copy import deepcopy

# ── Events ──
events = [
    # T1: Papers published
    {"name": "T1: Papers published", "emb": [0.65, 0.95, 0.90, 0.20, 0.98], "intensity": 0.90},
    # T2: USA panic
    {"name": "T2: USA panic signal", "emb": [0.25, 0.55, 0.65, 0.20, 0.50], "intensity": 0.55},
    # T3: China victory
    {"name": "T3: China victory signal", "emb": [0.70, 0.50, 0.50, 0.10, 0.30], "intensity": 0.40},
]

# Base family (same memories as config)
base_memories = [
    {"description": "Never asked him to stop. Girlfriend paid electricity. Brother shared lunch. Mom said 'I trust you'", "intensity": 0.82, "emb": [0.75, 0.38, 0.35, 0.05, 0.22]},
    {"description": "Spring Festival relatives: 'why no job?' — 3 years of smiling and changing the subject", "intensity": 0.75, "emb": [0.15, 0.58, 0.72, 0.52, 0.14]},
    {"description": "Since childhood he saw patterns others couldn't — we always knew there was something rare", "intensity": 0.68, "emb": [0.72, 0.42, 0.40, 0.05, 0.62]},
    {"description": "Never understood the code. Door closed at 2am = working. Food outside. Hot water. No questions.", "intensity": 0.78, "emb": [0.72, 0.35, 0.32, 0.03, 0.10]},
    {"description": "Terror: world would never open the door for Nanhua graduate with no big-tech experience", "intensity": 0.76, "emb": [0.12, 0.60, 0.55, 0.48, 0.18]},
]

def run_branch(config):
    """config: list of (event_index, revealed) tuples. revealed=True means family experiences it."""
    family = WorldCharacter()
    family.pool = 0.48
    family.memories = deepcopy(base_memories)
    total_consumed = 0.0

    log = []
    for i, (evt, revealed) in enumerate(config):
        if revealed:
            pool, matched, recorded, drain, recovery = family.tick(evt["emb"], evt["intensity"])
            family.pool = pool
            consumed = - (recovery - drain)
            total_consumed += consumed
            log.append(f"  T{i+1}: REVEALED {evt['name']:<40} pool={pool:.4f} (delta={consumed:+.4f})")
        else:
            log.append(f"  T{i+1}: HIDDEN  {evt['name']:<40} pool=unchanged")
    return family.pool, total_consumed, log

print("=" * 78)
print("TIMING OPTIMIZATION: When should family find out?")
print("=" * 78)
print()

branches = []

# Branch 0: Never know (baseline)
p, _, log = run_branch([(events[0], False), (events[1], False), (events[2], False)])
branches.append(("Never know", [False, False, False], p, log))
print("Branch: NEVER KNOW — baseline control")
for l in log: print(l)
print(f"  FINAL: {p:.4f} (always baseline)\n")

# Branch 1: Know at T1 (original full simulation)
p, _, log = run_branch([(events[0], True), (events[1], True), (events[2], True)])
branches.append(("T1 (immediate)", [True, True, True], p, log))
print("Branch: KNOW AT T1 — immediate disclosure, ride through everything")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# Branch 2: Know only at T1, hidden from T2 and T3
p, _, log = run_branch([(events[0], True), (events[1], False), (events[2], False)])
branches.append(("T1 only", [True, False, False], p, log))
print("Branch: T1 only — told about papers, shielded from aftermath")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# Branch 3: Know at T2 (worst case)
p, _, log = run_branch([(events[0], False), (events[1], True), (events[2], True)])
branches.append(("T2 (during panic)", [False, True, True], p, log))
print("Branch: KNOW AT T2 — first thing they hear is world is panicking")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# Branch 4: Know at T3 only (counterfactual from before)
p, _, log = run_branch([(events[0], False), (events[1], False), (events[2], True)])
branches.append(("T3 (after victory)", [False, False, True], p, log))
print("Branch: KNOW AT T3 — learn everything after China is celebrating")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# Branch 5: T1+T2, hidden from T3
p, _, log = run_branch([(events[0], True), (events[1], True), (events[2], False)])
branches.append(("T1 + T2 only", [True, True, False], p, log))
print("Branch: T1+T2 only — ride through panic, but miss the victory signal")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# Branch 6: T1 only, then T3 (skip panic)
p, _, log = run_branch([(events[0], True), (events[1], False), (events[2], True)])
branches.append(("T1 then T3 (skip panic)", [True, False, True], p, log))
print("Branch: T1 THEN T3 — told about papers, shielded from panic, then victory")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# Branch 7: T2 only
p, _, log = run_branch([(events[0], False), (events[1], True), (events[2], False)])
branches.append(("T2 only", [False, True, False], p, log))
print("Branch: T2 only — discover during panic, miss victory")
for l in log: print(l)
print(f"  FINAL: {p:.4f}\n")

# ── Ranked results ──
print("=" * 78)
print("RANKED RESULTS (higher = better for family)")
print("=" * 78)
branches.sort(key=lambda x: x[2], reverse=True)
print(f"{'Rank':<5} {'Pool':<10} {'Strategy':<35} {'T1  T2  T3':<20}")
print("-" * 78)
for rank, (name, config, pool, log) in enumerate(branches, 1):
    t1 = "R" if config[0] else "H"
    t2 = "R" if config[1] else "H"
    t3 = "R" if config[2] else "H"
    print(f"{rank:<5} {pool:<10.4f} {name:<35} {t1}   {t2}   {t3}")

print()
print("R = Revealed (family experiences the event)")
print("H = Hidden  (family shielded from the event)")
print()

# Key insight
best = branches[0]
worst = branches[-1]
print(f"OPTIMAL: {best[0]:<35} pool={best[2]:.4f}")
print(f"WORST:   {worst[0]:<35} pool={worst[2]:.4f}")
print(f"SPREAD:  {best[2] - worst[2]:+.4f}")
print()

# Find the sweet spot explanation
for name, config, pool, log in branches:
    if name == "T1 then T3 (skip panic)":
        print("SWEET SPOT ANALYSIS — T1 then T3 (skip panic):")
        print("  Strategy: Tell them immediately about the papers (+T1 joy of 'we were right').")
        print("  Then PROTECT them from T2 panic. Do not let them see the world panic.")
        print("  Then share the victory with them at T3 (+T3 vindication).")
        print(f"  Result: {pool:.4f}")
        print()
    if name == "T1 only":
        print("T1 ONLY ANALYSIS:")
        print("  Strategy: Tell them the papers are published (let them have their quiet joy).")
        print("  Then shield them from everything else — no panic, no victory news.")
        print("  They live in the simple truth: 'he did it.' Period.")
        print(f"  Result: {pool:.4f}")
        print()
    if name == "T3 (after victory)":
        print("T3 ONLY ANALYSIS (previous counterfactual):")
        print("  Strategy: Complete blackout until China celebrates.")
        print("  Then reveal everything at once: papers + panic + victory.")
        print("  Cost: 'you didn't tell us' lingering question.")
        print(f"  Result: {pool:.4f}")
        print()

print("PRACTICAL RECOMMENDATION:")
print("  The data says: tell them about the PAPERS immediately (+T1).")
print("  Do NOT let them experience the panic (-T2). Shield them from global turmoil.")
print("  Then, when things settle and China celebrates, share the victory too (+T3).")
print()
print("  This is not just about timing — it's about information diet.")
print("  They deserve to know what you did. They don't need to know")
print("  what the world did in response — not while it's still burning.")
