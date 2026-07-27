"""Tests for tree-sitter AST-based code analysis (discovery/ast.py)."""

from __future__ import annotations

from pathlib import Path

from specbridge.discovery.ast import (
    extract_functions,
    extract_functions_go,
    extract_functions_python,
    extract_functions_rust,
    extract_functions_typescript,
)


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


class TestExtractFunctionsTypeScript:
    """TypeScript/JavaScript function extraction."""

    def test_extract_function(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("function hello(name: string): void {\n  console.log(name);\n}\n")
        blocks = extract_functions_typescript(str(ts_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "hello"
        assert blocks[0].kind == "function"

    def test_extract_class(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("class Greeter {\n  greet() { return 'hi'; }\n}\n")
        blocks = extract_functions_typescript(str(ts_file))
        class_blocks = [b for b in blocks if b.kind == "class"]
        assert len(class_blocks) >= 1
        assert class_blocks[0].name == "Greeter"

    def test_extract_arrow_function(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "test.ts"
        ts_file.write_text("const arrow = (x: number) => x + 1;\n")
        blocks = extract_functions_typescript(str(ts_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "arrow"

    def test_extract_empty_file(self, tmp_path: Path) -> None:
        ts_file = tmp_path / "empty.ts"
        ts_file.write_text("")
        blocks = extract_functions_typescript(str(ts_file))
        assert blocks == []


class TestExtractFunctionsGo:
    """Go function/method extraction."""

    def test_extract_function(self, tmp_path: Path) -> None:
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\nfunc greet(name string) string {\n    return \"Hello\"\n}\n")
        blocks = extract_functions_go(str(go_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "greet"
        assert blocks[0].kind == "function"

    def test_extract_method(self, tmp_path: Path) -> None:
        go_file = tmp_path / "main.go"
        go_file.write_text("package main\nfunc (s *Service) Serve() error {\n    return nil\n}\n")
        blocks = extract_functions_go(str(go_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "Serve"

    def test_extract_empty(self, tmp_path: Path) -> None:
        go_file = tmp_path / "empty.go"
        go_file.write_text("")
        blocks = extract_functions_go(str(go_file))
        assert blocks == []


class TestExtractFunctionsRust:
    """Rust function/struct/enum extraction."""

    def test_extract_function(self, tmp_path: Path) -> None:
        rs_file = tmp_path / "lib.rs"
        rs_file.write_text("fn greet(name: &str) -> String {\n    format!(\"Hello\")\n}\n")
        blocks = extract_functions_rust(str(rs_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "greet"
        assert blocks[0].kind == "function"

    def test_extract_struct(self, tmp_path: Path) -> None:
        rs_file = tmp_path / "lib.rs"
        rs_file.write_text("struct User { name: String }\n")
        blocks = extract_functions_rust(str(rs_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "User"
        assert blocks[0].kind == "class"

    def test_extract_enum(self, tmp_path: Path) -> None:
        rs_file = tmp_path / "lib.rs"
        rs_file.write_text("enum Status { Active, Inactive }\n")
        blocks = extract_functions_rust(str(rs_file))
        assert len(blocks) >= 1
        assert blocks[0].name == "Status"


class TestExtractFunctionsAutoDispatch:
    """Auto-dispatch via extract_functions() based on extension."""

    def test_dispatch_ts(self, tmp_path: Path) -> None:
        f = tmp_path / "test.ts"
        f.write_text("function hello(): void {}\n")
        blocks = extract_functions(str(f))
        assert len(blocks) >= 1
        assert blocks[0].name == "hello"

    def test_dispatch_go(self, tmp_path: Path) -> None:
        f = tmp_path / "main.go"
        f.write_text("package main\nfunc hello() {}\n")
        blocks = extract_functions(str(f))
        assert len(blocks) >= 1
        assert blocks[0].name == "hello"

    def test_dispatch_rust(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text("fn hello() {}\n")
        blocks = extract_functions(str(f))
        assert len(blocks) >= 1
        assert blocks[0].name == "hello"

    def test_dispatch_py(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("def hello(): pass\n")
        blocks = extract_functions(str(f))
        assert len(blocks) >= 1
        assert blocks[0].name == "hello"

    def test_dispatch_unknown_ext(self, tmp_path: Path) -> None:
        f = tmp_path / "test.rb"
        f.write_text("def hello; end\n")
        blocks = extract_functions(str(f))
        assert isinstance(blocks, list)
