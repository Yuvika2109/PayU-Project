"""
apply_randint_fix_patch.py
Run from your fraud_generator/ directory:

    python apply_randint_fix_patch.py

Fixes "empty range for randrange()" crash in DatasetEngine.
The LLM sometimes generates burst_min_txns > burst_max_txns.
Three targeted fixes to core/dataset_engine.py:

  Fix 1 — _burst(): clamp so randint(mn, mx) never has mn > mx
  Fix 2 — _chain(): same clamp
  Fix 3 — _network(): per_account calculation guarded against zero

Safe to run multiple times — each fix checks before applying.
"""

import re
import sys
from pathlib import Path

TARGET = Path("core/dataset_engine.py")

if not TARGET.exists():
    sys.exit(f"ERROR: {TARGET} not found. Run from fraud_generator/ directory.")

src = TARGET.read_text(encoding="utf-8")
original = src

# ── Fix 1: _burst() — clamp burst_min_txns / burst_max_txns ─────────────────
# Original:
#   n = random.randint(
#       params.get("burst_min_txns", 5),
#       min(params.get("burst_max_txns", 20), max_txns),
#   )
# Fixed:
#   _bmn = params.get("burst_min_txns", 5)
#   _bmx = max(_bmn, min(params.get("burst_max_txns", 20), max_txns))
#   n = random.randint(_bmn, _bmx)

BURST_OLD = re.compile(
    r'([ \t]+)n = random\.randint\(\s*\n'
    r'\s+params\.get\("burst_min_txns",\s*(\d+)\),\s*\n'
    r'\s+min\(params\.get\("burst_max_txns",\s*(\d+)\),\s*max_txns\),\s*\n'
    r'\s+\)'
)

def burst_replacement(m):
    indent = m.group(1)
    default_min = m.group(2)
    default_max = m.group(3)
    return (
        f'{indent}_bmn = params.get("burst_min_txns", {default_min})\n'
        f'{indent}_bmx = max(_bmn, min(params.get("burst_max_txns", {default_max}), max_txns))\n'
        f'{indent}n = random.randint(_bmn, _bmx)'
    )

if "_bmn = params.get" in src:
    print("Fix 1 (_burst): already applied — skipping.")
else:
    new_src, count = BURST_OLD.subn(burst_replacement, src)
    if count == 0:
        print("WARNING Fix 1: pattern not found — printing _burst context:")
        for i, line in enumerate(src.splitlines()):
            if "burst_min_txns" in line or "burst_max_txns" in line:
                print(f"  {i+1}: {line!r}")
    else:
        src = new_src
        print(f"Fix 1 applied: _burst() randint clamped ({count} occurrence).")

# ── Fix 2: _chain() — same clamp ─────────────────────────────────────────────
CHAIN_OLD = re.compile(
    r'([ \t]+)n = random\.randint\(\s*\n'
    r'\s+params\.get\("burst_min_txns",\s*(\d+)\),\s*\n'
    r'\s+min\(params\.get\("burst_max_txns",\s*(\d+)\),\s*max_txns\),\s*\n'
    r'\s+\)'
)

if "_cmn = params.get" in src:
    print("Fix 2 (_chain): already applied — skipping.")
else:
    # After Fix 1, the _burst occurrence is replaced.
    # If a second occurrence exists it belongs to _chain.
    def chain_replacement(m):
        indent = m.group(1)
        default_min = m.group(2)
        default_max = m.group(3)
        return (
            f'{indent}_cmn = params.get("burst_min_txns", {default_min})\n'
            f'{indent}_cmx = max(_cmn, min(params.get("burst_max_txns", {default_max}), max_txns))\n'
            f'{indent}n = random.randint(_cmn, _cmx)'
        )

    new_src, count = CHAIN_OLD.subn(chain_replacement, src, count=1)
    if count == 0:
        print("Fix 2 (_chain): no additional randint pattern found (may already be fixed).")
    else:
        src = new_src
        print(f"Fix 2 applied: _chain() randint clamped.")

# ── Fix 3: _network() — guard per_account against zero ───────────────────────
# Original:
#   per_account = max(1, max_txns // n_accounts)
# This is already safe, but let's also guard n_accounts itself:
# If LLM sets num_accounts=0, n_accounts becomes 0 → ZeroDivisionError

NET_OLD = 'n_accounts  = params.get("num_accounts", 5)'
NET_NEW = 'n_accounts  = max(1, params.get("num_accounts", 5))'

if NET_NEW in src:
    print("Fix 3 (_network): already applied — skipping.")
elif NET_OLD in src:
    src = src.replace(NET_OLD, NET_NEW, 1)
    print("Fix 3 applied: _network() n_accounts guarded against zero.")
else:
    print("WARNING Fix 3: 'num_accounts' line not found — skipping.")

# ── Fix 4: inter_txn_gap_seconds min/max swap guard ──────────────────────────
# In _chain(), gap_min and gap_max come from Sequence_Rules.
# If LLM sets min > max, random.uniform(gap_min, gap_max) crashes.
GAP_OLD = re.compile(
    r'([ \t]+gap_min = self\.seq_rules\.get\("inter_txn_gap_seconds", \{\}\)\.get\("min", (\d+)\))\s*\n'
    r'([ \t]+gap_max = self\.seq_rules\.get\("inter_txn_gap_seconds", \{\}\)\.get\("max", (\d+)\))'
)

def gap_replacement(m):
    indent1, def_min, indent2, def_max = m.group(1), m.group(2), m.group(3), m.group(4)
    return (
        f'{indent1}\n'
        f'{indent2}gap_max = self.seq_rules.get("inter_txn_gap_seconds", {{}}).get("max", {def_max})\n'
        f'{indent2}gap_min = min(self.seq_rules.get("inter_txn_gap_seconds", {{}}).get("min", {def_min}), gap_max)'
    )

if "gap_min = min(" in src:
    print("Fix 4 (gap_seconds): already applied — skipping.")
else:
    new_src, count = GAP_OLD.subn(gap_replacement, src)
    if count > 0:
        src = new_src
        print(f"Fix 4 applied: inter_txn_gap_seconds min/max swap guard added.")
    else:
        print("Fix 4: gap_seconds pattern not found — skipping (may have different spacing).")

# ── Write back ────────────────────────────────────────────────────────────────
if src != original:
    TARGET.write_text(src, encoding="utf-8")
    print(f"\nPatched: {TARGET}")
else:
    print("\nNo changes made — file already fully patched.")

print('Verify: python -c "from core.dataset_engine import DatasetEngine; print(\'OK\')"')