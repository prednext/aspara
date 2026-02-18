# Aspara

The loss must go on. Aspara tracks every step of the descent, all the way to convergence.


![Dashboard Screenshot](https://raw.githubusercontent.com/prednext/aspara/main/docs/images/dashboard-screenshot.png)

## Why Aspara?

- Fast by design: LTTB-based metric downsampling keeps dashboards responsive
- Built for scale: manage hundreds runs without friction
- Flexible UI: Web dashboard and TUI dashboard from the same data

## Try the Demo

Want to see Aspara in action without installing? Try the live demo.

**[https://prednext-aspara.hf.space/](https://prednext-aspara.hf.space/)**

The demo lets you explore the experiment results dashboard with sample data.

## Requirements

- Python 3.10+

## Installation

```bash
# Install with all features
pip install "aspara[all]"

# Or install components separately
pip install aspara                  # Client only
pip install "aspara[dashboard]"     # Dashboard only
pip install "aspara[tracker]"       # Tracker only
```

## Quick Start

**1. Log your experiments (just 3 lines!)**

```python
import aspara

aspara.init(project="my_project", config={"lr": 0.01, "batch_size": 32})

for epoch in range(100):
    loss, accuracy = train_one_epoch()
    aspara.log({"train/loss": loss, "train/accuracy": accuracy}, step=epoch)

aspara.finish()
```

**2. Visualize results**

```bash
aspara dashboard
```

Open http://localhost:3141 to compare runs, explore metrics, and share insights.

**3. Or use the Terminal UI**

```bash
pip install "aspara[tui]"
aspara tui
```

![TUI Screenshot](https://raw.githubusercontent.com/prednext/aspara/main/docs/images/terminal-screenshot.png)

Navigate projects, runs, and metrics with Vim-style keybindings. Perfect for SSH sessions and terminal workflows.

## Documentation

- [Getting Started](docs/getting-started.md)
- [Dashboard Guide](docs/advanced/dashboard.md)
- [User Guide](docs/user-guide/basics.md)
- [API Reference](docs/api/index.md)

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and guidelines.

**Quick setup:**
```bash
pnpm install && pnpm build  # Build frontend assets
uv sync --dev               # Install Python dependencies
```
