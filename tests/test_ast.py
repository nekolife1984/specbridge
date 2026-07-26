"""Tests for tree-sitter AST-based code analysis (discovery/ast.py)."""

from __future__ import annotations

from pathlib import Path

from specbridge.discovery.ast import extract_functions_python


class TestExtractFunctionsPython:
    """Python function extraction via tree-sitter (or regex fallback)."""

    def test_extract_simple_function(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello(name):\n    return f'Hello {name}'\n")
        blocks = extract_functions_python(str(py_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "hello"
        assert blocks[0].kind == "function"

    def test_extract_class(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text("class MyClass:\n    def method(self):\n        pass\n")
        blocks = extract_functions_python(str(py_file))
        class_blocks = [b for b in blocks if b.kind == "class"]
        assert len(class_blocks) >= 1
        assert class_blocks[0].name == "MyClass"

    def test_extract_with_decorator(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text(
            "@app.route('/')\n"
            "def index():\n"
            "    return 'Hello'\n"
        )
        blocks = extract_functions_python(str(py_file))
        fn_blocks = [b for b in blocks if b.kind == "function"]
        assert len(fn_blocks) >= 1
        assert fn_blocks[0].name == "index"

    def test_extract_async(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text("async def fetch(url):\n    return await get(url)\n")
        blocks = extract_functions_python(str(py_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "fetch"

    def test_body_hash(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text("def foo():\n    return 1\n")
        blocks = extract_functions_python(str(py_file))
        assert len(blocks) >= 1
        assert len(blocks[0].body_hash) == 16
        assert blocks[0].body_lines >= 1
        assert blocks[0].body_preview

    def test_empty_file(self, tmp_path: Path) -> None:
        py_file = tmp_path / "empty.py"
        py_file.write_text("")
        blocks = extract_functions_python(str(py_file))
        assert blocks == []

    def test_no_functions(self, tmp_path: Path) -> None:
        py_file = tmp_path / "data.py"
        py_file.write_text("x = 1\ny = 2\n")
        blocks = extract_functions_python(str(py_file))
        assert blocks == []

    def test_nested_functions(self, tmp_path: Path) -> None:
        """Nested functions: both outer and inner are extracted."""
        py_file = tmp_path / "test.py"
        py_file.write_text(
            "def outer():\n"
            "    def inner():\n"
            "        pass\n"
            "    return inner\n"
        )
        blocks = extract_functions_python(str(py_file))
        names = {b.name for b in blocks}
        assert "outer" in names
        assert "inner" in names

    def test_multiple_functions(self, tmp_path: Path) -> None:
        py_file = tmp_path / "test.py"
        py_file.write_text(
            "def a(): pass\n"
            "def b(): pass\n"
            "def c(): pass\n"
        )
        blocks = extract_functions_python(str(py_file))
        assert len(blocks) >= 3
