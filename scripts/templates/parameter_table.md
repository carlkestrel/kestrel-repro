# Parameter Table

> Single source of truth for every parameter of the reproduction.

## §1  Model (模型)

| Parameter | Value | Default? | Source |
|---|---|---|---|
| Backbone |  |  | `configs/<run>/model.yaml` |
| Depth |  |  |  |
| Width |  |  |  |
| Dropout |  |  |  |
| Activation |  |  |  |
| Number of params (M) |  |  |  |
| Init seed |  |  |  |
- **source:** `experiments/<run_id>/configs/model.yaml`

## §2  Training (训练)

| Parameter | Value | Default? | Source |
|---|---|---|---|
| Optimizer |  |  | `configs/<run>/train.yaml` |
| LR |  |  |  |
| LR schedule |  |  |  |
| Batch size |  |  |  |
| Epochs |  |  |  |
| Weight decay |  |  |  |
| Gradient clip |  |  |  |
| EMA |  |  |  |
| AMP (fp16/bf16) |  |  |  |
| Loss |  |  |  |
| Warmup |  |  |  |
- **source:** `experiments/<run_id>/configs/train.yaml`

## §3  Data (数据)

| Parameter | Value | Default? | Source |
|---|---|---|---|
| Train split |  |  | `configs/<run>/data.yaml` |
| Val split |  |  |  |
| Test split |  |  |  |
| Number of workers |  |  |  |
| Pin memory |  |  |  |
| Drop last |  |  |  |
| Augmentation |  |  |  |
| Voxel size |  |  |  |
| Sample count per scene |  |  |  |
- **source:** `experiments/<run_id>/configs/data.yaml`

## §4  Evaluation (评估)

| Parameter | Value | Default? | Source |
|---|---|---|---|
| Metric |  |  | `configs/<run>/eval.yaml` |
| Ignore label |  |  |  |
| Voting (single / multi) |  |  |  |
| Sliding window (test only) |  |  |  |
| Test time augmentation |  |  |  |
| Checkpoint selection |  |  |  |
- **source:** `experiments/<run_id>/configs/eval.yaml`

## §5  Hardware (硬件)

| Parameter | Value | Source |
|---|---|---|
| GPU |  |  |
| GPU count |  |  |
| Distributed backend |  |  |
| cuDNN deterministic |  |  |
| Precision |  |  |
- **source:** `experiments/<run_id>/env.json`

## §6  Command-line equivalent (命令行等价)

```bash
# Verbatim command that reproduces these parameters.
python train.py --config <run>/configs/all.yaml --seed <seed>
```
- **source:** `experiments/<run_id>/run_manifest.json`

## §7  Next-stage recommendations (下阶段推荐)

- (e.g., "Increase batch size to 16 if VRAM allows; monitor stability.")
- (e.g., "Switch to AdamW with cosine schedule for next ablate.")
- **source:** `agents/repro-lead.md` recommendations + `/repro-review` open actions

---

## Appendix A — Cross-reference index

- → `templates/research_contract.md` §1
- → `templates/data_card.md` §4
- → `templates/environment_card.md` §2

## Appendix B — Default-vs-overridden flags

| Flag | Default | This run | Source |
|---|---|---|---|
| `HUMAN_CHECKPOINT` | True |  | `templates/control_flags.md` |
| `AUTO_RETRY` | False |  | `templates/control_flags.md` |
| `TOLERANCE_MIOU` | 0.5 |  | `templates/control_flags.md` |

## Appendix C — Configuration diff history

- `<run_id>` config hash: `sha256:...`
- last modified: `<ISO 8601>`
- modified by: `<agent or human>`

## Appendix D — Related runs

- L0 smoke: `<run_id>`
- L1 overfit: `<run_id>`
- L2 mini: `<run_id>`
- L3 resume: `<run_id>`

## Appendix E — Next-stage checklist

- [ ] (e.g., "Verify LR schedule matches paper before scaling to full data")
- [ ] (e.g., "Add gradient accumulation if batch size limited by VRAM")