# Contributing to specbridge (limited release)

Thanks for trying specbridge! This is a private beta — your feedback directly shapes the tool.

## Quick feedback

The most helpful things you can send:

1. **`specbridge --version`** and **`specbridge config`** output
2. What you tried to do
3. What happened (or didn't happen)
4. What you expected instead

```bash
# Include this in your report:
echo "=== version ===" && specbridge --version
echo "=== config ===" && specbridge config
echo "=== tree ===" && find . -name '.specbridge.yaml' -o -name '*.md' -path '*/docs/*' | head -20
```

## Where to send it

- **GitHub Issues**: https://github.com/nekolife1984/specbridge/issues
- **Direct message**: nekolife@gmail.com

## Running the project locally

```bash
git clone https://github.com/nekolife1984/specbridge.git
cd specbridge
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run linter
ruff check specbridge/ tests/

# Type check
mypy specbridge/
```

## Before sending a PR

1. Tests pass: `python -m pytest tests/ -v`
2. Linter clean: `ruff check specbridge/ tests/`
3. Type check clean: `mypy specbridge/`
4. Branch from `main`, use naming convention: `feat/`, `fix/`, `chore/`, `docs/`
5. One logical change per commit
6. 📚 **Update docs (EN + JA)** — see [Branching Strategy](docs/en/12-branching-strategy.md)

> **📖 Full branching guide:** [docs/en/12-branching-strategy.md](docs/en/12-branching-strategy.md)

---

That's it. No CLA, no bureaucracy. Just ship it. 🚀
