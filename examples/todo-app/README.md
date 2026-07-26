# specbridge example: todo-app

A minimal task management app that demonstrates specbridge's full traceability pipeline.

```
examples/todo-app/
├── docs/
│   └── tasks.md         ← Spec document (Markdown + @spec tags)
├── src/
│   └── tasks/
│       └── service.py   ← Implementation (@impl tags)
├── tests/
│   └── test_tasks.py    ← Tests (@verifies tags)
└── .specbridge.yaml     ← specbridge config
```

## Try it

```bash
# Install specbridge (one time)
pip install git+https://github.com/nekolife1984/specbridge.git

# Analyze
cd examples/todo-app
specbridge analyze
```

Expected output:

```
🔍 Scanning ... (spectra adapter)

   Nodes: 9 | Edges: 16
   Coverage: 100.0% (3/3)
```

All 3 specs are linked to their code → 100% coverage.

## Commands to explore

```bash
# Full trace graph with heuristic fallback
specbridge analyze --merge

# What implements spec 1.1?
specbridge impact --spec-id 1.1

# Coverage stats
specbridge coverage

# JSON output (great for scripting)
specbridge analyze --format json | jq '.edges | length'

# Interactive HTML graph
specbridge analyze --format html
open .specbridge/trace.html

# Watch for changes
specbridge watch
```

## What this demonstrates

| Feature | How it's shown |
|---------|---------------|
| **spectra adapter** | `@impl 1.1`, `@spec 1.1` tags in code + docs |
| **Heuristic fallback** | `--merge` also finds filename-based links |
| **Boundary validation** | `_Boundary:_ src/tasks/*` in docs |
| **Impact analysis** | `specbridge impact --spec-id 1.1` → 2 files |
| **Drift detection** | `specbridge snapshot` → change a file → `specbridge drift` |
| **Test traceability** | `@verifies 1.1` links tests to specs |
