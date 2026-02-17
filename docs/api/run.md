# Run class

The `Run` class is Aspara's central abstraction and is used to track an experiment.

In most cases you create a run with `aspara.init()`, but you can also instantiate `Run` directly.

```python
import aspara

# Recommended: use aspara.init()
run = aspara.init(project="my_project", config={"lr": 0.01})
aspara.log({"loss": 0.5})
aspara.finish()

# You can also instantiate Run directly
from aspara import Run
run = Run(project="my_project", config={"lr": 0.01})
run.log({"loss": 0.5})
run.finish()
```

## Context Manager Usage

The `Run` class supports the context manager protocol (`with` statement), which automatically calls `finish()` when exiting the context. This is convenient for ensuring proper cleanup, especially when exceptions may occur.

```python
import aspara

# Using context manager - finish() is called automatically
with aspara.init(project="my_project", config={"lr": 0.01}) as run:
    aspara.log({"loss": 0.5})
# finish() called automatically here
```

When using the context manager:

- `finish()` is called automatically when exiting the `with` block
- If an exception occurs, `exit_code=1` is set; otherwise `exit_code=0`
- The exception is re-raised after calling `finish()`

**When to use each pattern:**

| Pattern | Use Case |
|---------|----------|
| **Context manager** | Simple scripts where automatic cleanup on exit/exception is convenient |
| **Manual `finish()`** | Integration with frameworks like PyTorch Lightning, or when explicit control over `finish()` timing is needed |

## API (auto-generated)

::: aspara.run
    options:
      members:
        - Run
        - Config
        - Summary
        - init
        - log
        - finish
      show_root_heading: false
      heading_level: 3
      show_signature_annotations: true
      separate_signature: true
      show_source: false
      docstring_section_style: spacy
      merge_init_into_class: false
