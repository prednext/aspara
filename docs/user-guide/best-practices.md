# Best Practices

This page introduces best practices for using Aspara effectively and useful patterns for daily use.

## Organizing Runs

We recommend using clear naming conventions to organize runs:

```python
import aspara

# Good
run = aspara.init(
    project="image-classification",
    name=f"resnet18-adam-lr0.01-{timestamp}",
    config={
        "model": "resnet18",
        "optimizer": "adam",
        "lr": 0.01
    }
)

# Avoid
run = aspara.init(project="proj", name="test")
```

## Metric Naming

Use hierarchical naming to organize metrics:

```python
# Training metrics
aspara.log({
    "train/loss": train_loss,
    "train/accuracy": train_acc,
    "train/lr": current_lr
})

# Validation metrics
aspara.log({
    "val/loss": val_loss,
    "val/accuracy": val_acc
})

# Test metrics
aspara.log({
    "test/accuracy": test_acc,
    "test/f1_score": f1_score
})
```

## Organizing Parameters (Config)

We recommend putting information you want to reproduce or compare later into `config`.

```python
import aspara

aspara.init(
    project="my_project",
    name="my_run",
    config={
        # Model settings
        "model_type": "resnet18",
        "num_layers": 18,

        # Training settings
        "learning_rate": 0.01,
        "batch_size": 32,
        "optimizer": "adam",

        # Data settings
        "dataset": "cifar10",
        "image_size": 224,
    },
)
```

- Organizing keys into three categories (model, training, data) makes it easier to review later.
- In production, including model versions and dataset preprocessing conditions also makes comparisons easier.

## Regular Logging

We recommend logging metrics at regular intervals for consistency:

```python
import aspara

run = aspara.init(project="my_project", config={"lr": 0.01})
log_interval = 100  # Every 100 steps

for step in range(total_steps):
    # Training code...

    if step % log_interval == 0:
        aspara.log({
            "loss": current_loss,
            "lr": scheduler.get_last_lr()[0]
        }, step=step)

aspara.finish()
```

## Logging Multiple Metrics at Once

Sending multiple metrics in a single `aspara.log()` call helps maintain consistent log structure.

```python
# Log multiple metrics simultaneously
metrics = {
    "train/loss": train_loss,
    "train/accuracy": train_acc,
    "val/loss": val_loss,
    "val/accuracy": val_acc,
    "learning_rate": current_lr,
    "batch_time": batch_time,
}
aspara.log(metrics, step=epoch)
```

## Conditional Logging

If logging every step produces too many logs, conditional logging is effective.

```python
# Log only under specific conditions
if epoch % save_every_n_epochs == 0 or epoch == total_epochs - 1:
    aspara.log({
        "checkpoint_saved": True,
        "model_size_mb": model_size,
    }, step=epoch)
```

- Logging only at checkpoint saves or important events helps narrow down what to review later.

## Using Context Manager for Automatic Cleanup

Aspara supports the context manager pattern (`with` statement), which ensures `finish()` is called automatically when exiting the block. This is especially useful when exceptions may occur during training:

```python
import aspara

with aspara.init(project="my_project", config={"lr": 0.01}) as run:
    for step in range(total_steps):
        # Training code...
        aspara.log({"loss": current_loss}, step=step)
# finish() is called automatically, even if an exception occurs
```

**When to use context manager:**

- Simple training scripts where you want guaranteed cleanup
- Scripts where exceptions might occur and you want `finish()` to be called regardless

**When to use manual `finish()`:**

- Integration with frameworks like PyTorch Lightning that have their own lifecycle management
- When you need explicit control over when the run finishes
- When `finish()` needs to be called from a different scope than `init()`

## FAQ

### Q: What happens if a run crashes midway?

A: Logs are saved in real-time, so recorded data is preserved even after a crash.

### Q: What happens if I run with the same run name multiple times?

A: New data is appended to the existing file. We recommend using different names for different runs.

### Q: What if log files become too large?

A: Since each run has its own file, they are naturally split. Manually delete old logs if they are no longer needed.

For more details, see [Troubleshooting](troubleshooting.md).

For framework-specific examples, see [Examples](../examples/pytorch_example.md).
