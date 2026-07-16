# Claim × Evidence Matrix

> **Why this file exists**: every claim in the paper must map to a *specific
> experiment*, a *specific run*, a *specific recomputed artifact*, and an
> honest status. If a cell is empty, the claim is not yet reproducible.
>
> **Schema (11 columns, exact order — automated parser depends on it)**:
>
> 1. Claim
> 2. Source
> 3. Required evidence
> 4. Dataset
> 5. Protocol
> 6. Run
> 7. Artifact
> 8. Recomputed
> 9. Status
> 10. Gap
> 11. Explanation

---

## Header (do not delete)

| Claim | Source | Required evidence | Dataset | Protocol | Run | Artifact | Recomputed | Status | Gap | Explanation |
|---|---|---|---|---|---|---|---|---|---|---|
| (one row per paper claim, see plan §Claims Inventory) |

---

## Row format

```
| <short claim id>: <claim text> | §<table/figure/equation> | <file:line or section> | <dataset name + split> | <eval protocol> | <run_id> | <path to log/ckpt/metric> | <recomputed value or "—"> | PASS \| PARTIAL \| FAIL \| PENDING | <delta vs paper, signed> | <one-sentence reason> |
```

`Status ∈ {PASS, PARTIAL, FAIL, PENDING}`:
- **PASS** — recomputed value is within tolerance of paper value.
- **PARTIAL** — within 2× tolerance, or only a subset of claims reproduced.
- **FAIL** — outside tolerance, or recomputation not yet possible.
- **PENDING** — claim not yet attempted (no run assigned).

`Gap` is signed (e.g., `-0.4 pp`, `+0.7 pp`) and **must** be filled whenever
`Status ∈ {PASS, PARTIAL, FAIL}`. Empty `Gap` is only valid when `Status=PENDING`.

`Explanation` is mandatory for `PARTIAL` and `FAIL` rows.

---

## Example row

```
| C1: S3DIS Area-6 mIoU | Table 3, row "Ours (KPConv)" | training log + per-class IoU | S3DIS / Area-6 | sub-points, vote-3, ignore-0 | r-s3dis-001 | metrics/r-s3dis-001/miou.json | 73.5 | PASS | -0.4 pp | within 0.5 pp tolerance (paper 73.9) |
```

---

## Parser contract

`scripts/reproctl.py` parses this file with the regex
`r"^\|\s*(C\d+):"`. Adding a row without the `C\d+:` prefix will make it
invisible to automation. **Do not** reorder columns.

## Updating

- Append-only. To correct a row, add a new row referencing the old one in
  `Explanation` and bump `Status` accordingly.
- A run that closes a claim must reference an existing `experiment_id` from
  `experiment_tracker.csv` (see P2_T03).