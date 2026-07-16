# Deep Learning Runtime Optimization Skill

Use this skill when the task involves optimizing DataLoader, GPU memory, mixed precision training, distributed training, or hardware profiling for deep learning paper reproduction.

## When to Use This Skill

Apply this skill whenever:
- Optimizing DataLoader throughput (num_workers, pin_memory, prefetch_factor)
- Configuring AMP, BF16, TF32, or FP32 precision
- Setting up DDP (DistributedDataParallel) for multi-GPU training
- Profiling GPU memory usage and identifying bottlenecks
- Benchmarking training throughput (samples/sec, steps/sec)
- Planning gradient accumulation to simulate larger batch sizes
- Evaluating torch.compile or other graph compilation options

## Core Principles

### Parity Before Optimization

**Every optimization must be validated for numerical parity with the strict baseline before it can be used for paper results.**

The optimization hierarchy:

1. **strict_repro** (baseline): FP32, single GPU, paper-specified batch size. This is the reference.
2. **optimized_repro_safe**: AMP/BF16, DDP, adjusted batch size — ONLY after parity is verified.
3. **experimental_fast**: torch.compile, aggressive batch sizes, custom optimizations — NOT for paper results.

### Numerical Parity Testing

Before claiming two configurations are equivalent, verify:

```
| metric_strict - metric_optimized | <= tolerance
```

Typical tolerances:
- mIoU: ±0.5% absolute
- Accuracy/F1: ±0.5% absolute
- Loss: No fixed tolerance (watch for NaN/divergence)

Check both **final metrics** and **loss curve trajectories**. A configuration that matches final mIoU but has different training dynamics is NOT equivalent.

### Optimize for Throughput, Not Utilization

Do NOT maximize GPU utilization or VRAM usage as an end goal. Optimize:

- **Samples per second** (throughput)
- **Time to convergence** (wall-clock)
- **Memory stability** (no OOM, no memory leaks)
- **Numerical stability** (no NaN, no divergence)

A configuration that achieves 95% GPU utilization but produces different results than strict_repro is worse than one with 70% utilization that is numerically equivalent.

## DataLoader Optimization

### Worker Count Selection

```
num_workers = min(CPU_cores, 8)  # rule of thumb
num_workers = 0  # if data loading is already faster than GPU
```

Test with:
```python
import time
start = time.time()
for _ in range(100):
    batch = next(data_loader)
elapsed = time.time() - start
throughput = 100 * batch_size / elapsed
```

### Memory Pinning

- `pin_memory=True` accelerates CPU→GPU transfer for CUDA
- Has a small CPU memory overhead (~4x batch size)
- Does not help and may hurt on CPU-only or Apple Silicon

### Prefetch Factor

```python
DataLoader(..., num_workers=4, prefetch_factor=2)
```

- Prefetching helps when DataLoader is a bottleneck
- Does not help and wastes memory when GPU is the bottleneck
- Test empirically before committing

## Mixed Precision Training

### AMP (Automatic Mixed Precision)

```python
scaler = torch.cuda.amp.GradScaler()
with torch.cuda.amp.autocast():
    outputs = model(inputs)
loss = criterion(outputs, targets)
scaler.scale(loss).backward()
scaler.step(optimizer)
scaler.update()
```

- Use AMP first — it is the most broadly compatible optimization
- Loss scaling prevents gradient underflow in FP16
- Works with most models without architecture changes

### BF16 (BFloat16)

```python
with torch.cuda.amp.autocast(dtype=torch.bfloat16):
    outputs = model(inputs)
```

- BF16 has wider dynamic range than FP16 — more stable for training
- Requires Ampere+ GPU (compute capability >= 8.0)
- Check `torch.cuda.is_bf16_supported()`

### TF32 (TensorFloat-32)

```python
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
```

- TF32 is a 19-bit format that accelerates matrix multiplications on Ampere+
- Does not change the precision of weights or gradients
- Usually safe to enable alongside AMP
- Verify that TF32 does not change results (within numerical tolerance)

### Parity Checklist for Mixed Precision

- [ ] Loss curves match between FP32 and mixed precision
- [ ] Final metrics are within tolerance
- [ ] No NaN or Inf values appear during training
- [ ] Gradient norms are similar between FP32 and mixed precision
- [ ] Checkpoint reloading produces identical results

## Distributed Data Parallel (DDP)

### Basic Setup

```python
import torch.distributed as dist
dist.init_process_group(backend="nccl")
model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[local_rank])
```

### Multi-GPU Parity

Single GPU and multi-GPU must produce numerically equivalent results:

- Verify that `find_unused_parameters=False` (or all parameters are used)
- Verify that batch normalization stats are synchronized across GPUs
- Verify that dropout uses the same random seed across runs
- Run a short training and compare metrics between single-GPU and multi-GPU

### Batch Size Scaling

When changing batch size, scale learning rate:

```
lr_new = lr_original * (batch_size_new / batch_size_original)^0.5  # linear scaling rule
```

Or use the square root rule for large changes. Always validate with a short training.

## Gradient Accumulation

Use gradient accumulation to simulate larger batch sizes:

```python
accumulation_steps = effective_batch_size // physical_batch_size
optimizer.zero_grad()
for i, (inputs, targets) in enumerate(data_loader):
    outputs = model(inputs)
    loss = criterion(outputs, targets) / accumulation_steps
    loss.backward()
    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()
```

- Verify numerical parity with the equivalent physical batch size
- Gradient accumulation is generally safe for most architectures
- May affect BatchNorm statistics — test carefully

## torch.compile

```python
model = torch.compile(model, mode="reduce-overhead")
```

- `mode="default"`: Best optimization, longer compile time
- `mode="reduce-overhead"`: Lower Python overhead, good for small batches
- `mode="max-autotune"`: Maximum performance, very long compile time

**Do NOT use torch.compile for paper results without extensive parity testing.**

torch.compile can change numerical behavior through graph rewriting.

## Hardware Profiling

### Memory Profiling

```python
print(torch.cuda.memory_summary(device=0))
print(f"Allocated: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
print(f"Reserved: {torch.cuda.memory_reserved() / 1e9:.2f} GB")
```

### Throughput Profiling

```python
import time
model.train()
for i, (inputs, targets) in enumerate(data_loader):
    if i >= warmup_steps:
        t_start = time.time()
    with torch.cuda.amp.autocast():
        outputs = model(inputs)
        loss = criterion(outputs, targets)
    loss.backward()
    optimizer.step()
    if i >= warmup_steps:
        elapsed += time.time() - t_start
        steps += 1
throughput = batch_size * steps / elapsed
```

## Common Pitfalls

| Pitfall | Symptom | Resolution |
|---|---|---|
| AMP causes NaN | Loss becomes NaN after a few steps | Increase loss scale, check for inf/nan in inputs |
| DDP batch norm mismatch | Different results on different GPUs | Set `sync_batchnorm=True` or use `DistributedDataParallel` with `broadcast_buffers=True` |
| DataLoader is bottleneck | GPU utilization < 80% | Increase num_workers, enable pin_memory, prefetch more |
| OOM on large batch | CUDA out of memory | Reduce batch size, use gradient accumulation, enable activation checkpointing |
| torch.compile changes results | Metrics differ from non-compiled | Do NOT use torch.compile for paper results |
| LR not scaled for batch | Training unstable at large batch | Apply linear learning rate scaling |

## Integration with Other Skills

- `paper-reproduction` skill defines the baseline configuration to optimize against
- `point-cloud-reproduction` skill has specific considerations for full-PC voting memory
- `reproduction-gates.mdc` rule enforces parity testing before using optimizations for paper results
