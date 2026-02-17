# Storage (Advanced)

In LocalRun, you can choose from two storage backends for saving metrics:

- **JSONL** (default)
- **Polars** (experimental)

## Backend Comparison

| Feature | JSONL (Default) | Polars (Experimental) |
|---------|-----------------|----------------------|
| **Write Speed** | Fast | Fast |
| **File Size** | Larger | Smaller (compressed + archived) |
| **Read Speed** | Normal | Fast |
| **Compatibility** | Best (text file) | Good |
| **Additional Dependencies** | None | polars >= 1.36.1 |

## What is the Polars Backend? (Experimental)

The Polars backend is a storage option for efficiently saving metrics. Features:

- **Auto-archiving**: Automatically compresses data to Parquet format when WAL threshold is exceeded
- **Small file size**: Efficiently uses storage through compression
- **Hybrid mode**: Metrics use Polars, others (init/config/finish) use JSONL

## Enabling the Polars Backend

### Method 1: Specify via Parameter (Recommended)

```python
import aspara

# Enable Polars backend
run = aspara.init(
    project="long_training",
    storage_backend="polars"
)

aspara.log({"loss": 0.5, "accuracy": 0.8})
aspara.finish()
```

### Method 2: Specify via Environment Variable

```bash
# Enable Polars via environment variable
export ASPARA_STORAGE_BACKEND=polars

# All runs from now on will use Polars
python train.py
```

**Priority order:** Parameter > Environment variable > Default (`jsonl`)

## Installing Polars

To use the Polars backend, you need the `polars` package:

```bash
# If using uv
uv pip install "aspara[polars]"
```
