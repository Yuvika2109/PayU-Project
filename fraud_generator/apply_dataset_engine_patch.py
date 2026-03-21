"""
apply_dataset_engine_patch.py  (v3 — handles partial patches)
Run from your fraud_generator/ directory:

    python apply_dataset_engine_patch.py

Applies three targeted changes to core/dataset_engine.py:
  1. Adds _sanitise_weights() helper (skips if already present)
  2. Makes NormalGenerator.cur_w use it (flexible spacing + quote match)
  3. Makes FraudInjector.cur_w use it (flexible spacing + quote match)

Safe to run multiple times — each patch checks before applying.
"""

import re
import sys
from pathlib import Path

TARGET = Path("core/dataset_engine.py")

if not TARGET.exists():
    sys.exit(f"ERROR: {TARGET} not found. Run from fraud_generator/ directory.")

src = TARGET.read_text(encoding="utf-8")
original = src  # keep for comparison at end

# ── Patch 1: add _sanitise_weights() helper ───────────────────────────────────
if "_sanitise_weights" in src:
    print("Patch 1: _sanitise_weights already present — skipping.")
else:
    HELPER = '''\ndef _sanitise_weights(weights_dict, fallback: dict) -> dict:
    """
    Ensure a weights dict has at least one numeric value.
    Returns fallback if the dict is missing, empty, or has no numeric values.
    Strips non-numeric entries so _weighted_choice never crashes.
    """
    if not isinstance(weights_dict, dict) or not weights_dict:
        return fallback
    clean = {k: v for k, v in weights_dict.items() if isinstance(v, (int, float))}
    return clean if clean else fallback

'''
    for anchor in ["def _sample_amount(", "def _sample_amount ("]:
        if anchor in src:
            src = src.replace(anchor, HELPER + anchor, 1)
            print("Patch 1 applied: _sanitise_weights() helper added.")
            break
    else:
        sys.exit("ERROR: could not find 'def _sample_amount' anchor. Check dataset_engine.py.")

# ── Patch 2: NormalGenerator cur_w ───────────────────────────────────────────
if '_sanitise_weights(prof.get("currency_weights")' in src or \
   "_sanitise_weights(prof.get('currency_weights')" in src:
    print("Patch 2: NormalGenerator.cur_w already patched — skipping.")
else:
    # Match any spacing/quoting variant of:
    #   self.cur_w ... = prof["currency_weights"]
    #   self.cur_w ... = prof['currency_weights']
    pat2 = re.compile(
        r'([ \t]+self\.cur_w[ \t]*=[ \t]*prof\[["\']currency_weights["\']\])'
    )
    m2 = pat2.search(src)
    if not m2:
        # Show all cur_w lines to help diagnose
        lines = [(i+1, l) for i, l in enumerate(src.splitlines()) if "cur_w" in l]
        print("ERROR: could not find NormalGenerator cur_w line.")
        print("All lines with 'cur_w':")
        for no, l in lines:
            print(f"  {no}: {l!r}")
        sys.exit(1)
    indent = re.match(r'([ \t]+)', m2.group(1)).group(1)
    replacement = f'{indent}self.cur_w = _sanitise_weights(prof.get("currency_weights"), {{"USD": 1.0}})'
    src = src[:m2.start()] + replacement + src[m2.end():]
    print("Patch 2 applied: NormalGenerator.cur_w uses _sanitise_weights().")

# ── Patch 3: FraudInjector cur_w ─────────────────────────────────────────────
if '_sanitise_weights(\n' in src and 'Normal_User_Profile' in src and \
   'get("currency_weights")' in src:
    print("Patch 3: FraudInjector.cur_w already patched — skipping.")
else:
    # Match any spacing/quoting variant of:
    #   self.cur_w ... = blueprint["Normal_User_Profile"]["currency_weights"]
    pat3 = re.compile(
        r'([ \t]+self\.cur_w[ \t]*=[ \t]*blueprint\[["\']Normal_User_Profile["\']\]\[["\']currency_weights["\']\])'
    )
    m3 = pat3.search(src)
    if not m3:
        lines = [(i+1, l) for i, l in enumerate(src.splitlines()) if "cur_w" in l]
        print("ERROR: could not find FraudInjector cur_w line.")
        print("All lines with 'cur_w':")
        for no, l in lines:
            print(f"  {no}: {l!r}")
        sys.exit(1)
    indent3 = re.match(r'([ \t]+)', m3.group(1)).group(1)
    replacement3 = (
        f'{indent3}self.cur_w = _sanitise_weights(\n'
        f'{indent3}    blueprint["Normal_User_Profile"].get("currency_weights"),\n'
        f'{indent3}    {{"USD": 1.0}},\n'
        f'{indent3})'
    )
    src = src[:m3.start()] + replacement3 + src[m3.end():]
    print("Patch 3 applied: FraudInjector.cur_w uses _sanitise_weights().")

# ── Write back only if changed ────────────────────────────────────────────────
if src != original:
    TARGET.write_text(src, encoding="utf-8")
    print(f"\nWrote patched file: {TARGET}")
else:
    print("\nNo changes needed — file already fully patched.")

print('Done. Verify: python -c "from core.dataset_engine import DatasetEngine; print(\'OK\')"')