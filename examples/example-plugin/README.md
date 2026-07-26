# Example specbridge Plugin

A minimal example showing how to write a specbridge adapter plugin.

## Structure

```
example-specbridge-plugin/
├── pyproject.toml        # entry point declaration
└── example_adapter.py    # ProjectAdapter subclass
```

## How it works

1. Subclass `ProjectAdapter` from `specbridge.adapters._base`
2. Implement `detect()` and `analyze()`
3. Declare the entry point in `pyproject.toml`:

```toml
[project.entry-points."specbridge.adapters"]
example = "example_adapter:ExampleAdapter"
```

4. Install the plugin package in the same environment as specbridge
5. Run `specbridge plugins` to verify it's loaded

## Try it

```bash
cd examples/example-plugin
pip install -e .
specbridge plugins --refresh
```
