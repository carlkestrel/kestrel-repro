# Rollback Instructions

## BUG-001

**File:** `scripts/reproctl.py`  
**Change:** Line 163: `control_flags` → `flags`

To rollback:
```python
# In get_default_state(), change:
"flags": {
# Back to:
"control_flags": {
```

**Impact of rollback:** State will again use inconsistent keys.  
`get_default_state()` will return `control_flags`, `load_state()` will read `flags`.

## BUG-002

**File:** `templates/narrative_report.md`  
**Change:** Lines 30-33: concrete example → placeholders

To rollback:
```markdown
metric: 73.5%
source: experiments/r-001/metrics/eval_results.json:line_42
paper:  Table 3, row "Ours (KPConv)"
gap:    -0.4 pp (within ±0.5 pp tolerance)
```

**Impact of rollback:** Narrative report template will again have a concrete number  
without a verifiable source in the illustration section.
