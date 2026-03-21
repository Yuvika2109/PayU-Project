"""
fix_dataset_engine_gap.py
Run from your fraud_generator/ directory:

    python fix_dataset_engine_gap.py

Repairs the corrupted gap_seconds lines in core/dataset_engine.py.
The previous patch script concatenated two statements on one line,
causing a SyntaxError at line ~402.

Replaces the corrupted block with three correct lines:
    gap_min = self.seq_rules.get("inter_txn_gap_seconds", {}).get("min", 30)
    gap_max = self.seq_rules.get("inter_txn_gap_seconds", {}).get("max", 300)
    gap_min = min(gap_min, gap_max)   ← swap guard so min never > max

Safe to run multiple times — syntax-checks before writing.
"""

import ast
import re
import sys
from pathlib import Path

TARGET = Path("core/dataset_engine.py")

if not TARGET.exists():
    sys.exit(f"ERROR: {TARGET} not found. Run from fraud_generator/ directory.")

src = TARGET.read_text(encoding="utf-8")

# ── Find the corrupted/existing gap block ─────────────────────────────────────
# The block is in _chain(). It may be:
#   (a) original clean 2 lines  (gap_min=...\ngap_max=...)
#   (b) partially patched       (includes gap_min = min(...) but on wrong line)
#   (c) corrupted concatenation (two statements on same line)
#
# Strategy: find all lines in the file containing "gap_min" or "gap_max"
# that reference seq_rules OR are the min() guard, delete them all,
# and insert the correct 3 lines at the position of the first one.

lines_in  = src.split('\n')
lines_out = []
insert_pos = None
indent_str = '        '  # default 8 spaces — will be detected from first match

for i, line in enumerate(lines_in):
    stripped = line.lstrip()
    is_gap_line = (
        stripped.startswith('gap_min') or
        stripped.startswith('gap_max')
    ) and (
        'seq_rules' in line or
        'gap_min = min(' in line or
        # corrupted: contains two statements (no newline between them)
        line.count('gap_') > 1
    )
    if is_gap_line:
        if insert_pos is None:
            insert_pos = len(lines_out)  # remember where to insert
            indent_str = line[:len(line) - len(line.lstrip())]
        # Drop this line (we'll insert clean replacement at insert_pos)
    else:
        lines_out.append(line)

if insert_pos is None:
    print("No gap_min/gap_max lines found — nothing to fix.")
    sys.exit(0)

# Insert the 3 correct lines at the saved position
correct = [
    f'{indent_str}gap_min = self.seq_rules.get("inter_txn_gap_seconds", {{}}).get("min", 30)',
    f'{indent_str}gap_max = self.seq_rules.get("inter_txn_gap_seconds", {{}}).get("max", 300)',
    f'{indent_str}gap_min = min(gap_min, gap_max)',
]
lines_out[insert_pos:insert_pos] = correct

new_src = '\n'.join(lines_out)

# ── Syntax check before writing ───────────────────────────────────────────────
print("Replaced gap block with:")
for line in correct:
    print(f"  {line!r}")

try:
    ast.parse(new_src)
    print("\nSyntax check: PASSED")
except SyntaxError as e:
    print(f"\nSyntax check: FAILED — {e}")
    # Show context around the error line
    err_lines = new_src.split('\n')
    start = max(0, e.lineno - 3)
    end   = min(len(err_lines), e.lineno + 2)
    print("Context:")
    for j, l in enumerate(err_lines[start:end], start + 1):
        marker = " <-- HERE" if j == e.lineno else ""
        print(f"  {j}: {l!r}{marker}")
    print("\nFile NOT written.")
    sys.exit(1)

TARGET.write_text(new_src, encoding="utf-8")
print(f"\nFixed: {TARGET}")
print('Verify: python -c "from core.dataset_engine import DatasetEngine; print(\'OK\')"')