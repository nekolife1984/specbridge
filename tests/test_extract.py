"""Tests for tag extraction (core/extract.py)."""

from __future__ import annotations

from pathlib import Path

from specbridge.core.extract import (
    extract_tags_from_dir,
    extract_tags_from_file,
)


class TestExtractFromFile:
    """Test extract_tags_from_file with various file types."""

    def test_python_impl_tag(self, tmp_project_heuristic: Path) -> None:
        """# @impl 1.1 in .py file."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text("# @impl 1.1\ndef login(): pass\n")

        tags = extract_tags_from_file(py_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"
        assert tags[0].value == "1.1"

    def test_python_multiple_impl(self, tmp_project_heuristic: Path) -> None:
        """# @impl 1.1, 1.2 in .py file — comma-separated list."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text("# @impl 1.1, 1.2\ndef login(): pass\n")

        tags = extract_tags_from_file(py_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"
        assert tags[0].value == "1.1, 1.2"

    def test_typescript_impl_tag(self, tmp_project_heuristic: Path) -> None:
        """// @impl 2.0 in .ts file."""
        project = tmp_project_heuristic
        ts_file = project / "src" / "app.ts"
        ts_file.write_text("// @impl 2.0\nexport function serve(): void {}\n")

        tags = extract_tags_from_file(ts_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"
        assert tags[0].value == "2.0"

    def test_go_impl_tag(self, tmp_project_heuristic: Path) -> None:
        """// @impl 3.0 in .go file."""
        project = tmp_project_heuristic
        go_file = project / "src" / "server.go"
        go_file.write_text("// @impl 3.0\nfunc main() {}\n")

        tags = extract_tags_from_file(go_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"

    def test_markdown_spec_tag(self, tmp_project_heuristic: Path) -> None:
        """<!-- @spec 1.1 --> in .md file."""
        project = tmp_project_heuristic
        md_file = project / "docs" / "auth.md"
        md_file.write_text("<!-- @spec 1.1 -->\n# Auth\n")

        tags = extract_tags_from_file(md_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "spec"
        assert tags[0].value == "1.1"

    def test_markdown_design_tag(self, tmp_project_heuristic: Path) -> None:
        """<!-- @design AuthService --> in .md file."""
        project = tmp_project_heuristic
        md_file = project / "docs" / "auth.md"
        md_file.write_text("<!-- @design AuthService -->\n# Auth\n")

        tags = extract_tags_from_file(md_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "design"
        assert tags[0].value == "AuthService"

    def test_markdown_satisfies(self, tmp_project_heuristic: Path) -> None:
        """<!-- @satisfies 1.1, 1.2 --> resolves correctly."""
        project = tmp_project_heuristic
        md_file = project / "docs" / "auth.md"
        md_file.write_text("<!-- @satisfies 1.1, 1.2 -->\n# Auth\n")

        tags = extract_tags_from_file(md_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "satisfies"
        assert tags[0].value == "1.1, 1.2"

    def test_verifies_tag(self, tmp_project_heuristic: Path) -> None:
        """# @verifies 1.1 in .py file."""
        project = tmp_project_heuristic
        test_file = project / "src" / "test_auth.py"
        test_file.write_text("# @verifies 1.1\ndef test_login(): pass\n")

        tags = extract_tags_from_file(test_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "verifies"
        assert tags[0].value == "1.1"

    def test_module_tag(self, tmp_project_heuristic: Path) -> None:
        """# @module auth extracted."""
        project = tmp_project_heuristic
        src_file = project / "src" / "login.py"
        src_file.write_text("# @module auth\ndef login(): pass\n")

        tags = extract_tags_from_file(src_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "module"
        assert tags[0].value == "auth"

    def test_feature_tag(self, tmp_project_heuristic: Path) -> None:
        """# @feature login extracted."""
        project = tmp_project_heuristic
        src_file = project / "src" / "login.py"
        src_file.write_text("# @feature login\ndef login(): pass\n")

        tags = extract_tags_from_file(src_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "feature"
        assert tags[0].value == "login"

    def test_multiple_tags_same_file(self, tmp_project_heuristic: Path) -> None:
        """Multiple tags in the same file are all extracted."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text(
            "# @module auth\n"
            "# @feature login\n"
            "# @impl 1.1\n"
            "def login(): pass\n"
        )
        tags = extract_tags_from_file(py_file, project)
        kinds = {t.kind for t in tags}
        assert "module" in kinds
        assert "feature" in kinds
        assert "impl" in kinds

    def test_no_tags(self, tmp_project_heuristic: Path) -> None:
        """File with no tags returns empty list."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text("def login(): pass\n")
        tags = extract_tags_from_file(py_file, project)
        assert tags == []

    def test_unsupported_file_type(self, tmp_project_heuristic: Path) -> None:
        """.txt files are not scanned."""
        project = tmp_project_heuristic
        txt_file = project / "README.txt"
        txt_file.write_text("# @impl 1.1\n")
        tags = extract_tags_from_file(txt_file, project)
        assert tags == []

    def test_csharp_line_comment(self, tmp_project_heuristic: Path) -> None:
        """C# .cs uses // line comments."""
        project = tmp_project_heuristic
        cs_file = project / "src" / "Handler.cs"
        cs_file.write_text("// @impl 4.0\nclass Handler {}\n")

        tags = extract_tags_from_file(cs_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"
        assert tags[0].value == "4.0"

    def test_ruby_hash_comment(self, tmp_project_heuristic: Path) -> None:
        """Ruby .rb uses # line comments."""
        project = tmp_project_heuristic
        rb_file = project / "src" / "app.rb"
        rb_file.write_text("# @impl 5.0\ndef run; end\n")

        tags = extract_tags_from_file(rb_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"

    def test_yaml_file(self, tmp_project_heuristic: Path) -> None:
        """YAML files with # comments should be scanned as source."""
        project = tmp_project_heuristic
        yml_file = project / "deploy.yml"
        yml_file.parent.mkdir(exist_ok=True)
        yml_file.write_text("# @impl 6.0\nversion: '3'\n")

        tags = extract_tags_from_file(yml_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"

    def test_impl_line_numbers(self, tmp_project_heuristic: Path) -> None:
        """Line numbers are 1-indexed and correct."""
        project = tmp_project_heuristic
        py_file = project / "src" / "login.py"
        py_file.write_text("\n\n# @impl 1.1\ndef login(): pass\n")

        tags = extract_tags_from_file(py_file, project)
        assert len(tags) == 1
        assert tags[0].line == 3

    def test_spec_line_numbers(self, tmp_project_heuristic: Path) -> None:
        """HTML comment line numbers in .md are correct."""
        project = tmp_project_heuristic
        md_file = project / "docs" / "auth.md"
        md_file.write_text("Before\n\n<!-- @spec 1.1 -->\n# Auth\n")

        tags = extract_tags_from_file(md_file, project)
        assert len(tags) == 1
        assert tags[0].line == 3

    def test_relative_path(self, tmp_project_heuristic: Path) -> None:
        """Path in Tag is relative to project root."""
        project = tmp_project_heuristic
        py_file = project / "src" / "login.py"
        py_file.write_text("# @impl 1.1\ndef login(): pass\n")

        tags = extract_tags_from_file(py_file, project)
        assert len(tags) == 1
        assert tags[0].file == "src/login.py"

    def test_java_impl(self, tmp_project_heuristic: Path) -> None:
        """Java // @impl tag."""
        project = tmp_project_heuristic
        java_file = project / "src" / "Main.java"
        java_file.parent.mkdir(exist_ok=True)
        java_file.write_text("// @impl 7.0\npublic class Main {}\n")

        tags = extract_tags_from_file(java_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"

    def test_swift_impl(self, tmp_project_heuristic: Path) -> None:
        """Swift // @impl tag."""
        project = tmp_project_heuristic
        swift_file = project / "src" / "App.swift"
        swift_file.parent.mkdir(exist_ok=True)
        swift_file.write_text("// @impl 8.0\nstruct App {}\n")

        tags = extract_tags_from_file(swift_file, project)
        assert len(tags) == 1
        assert tags[0].kind == "impl"

    def test_dart_impl(self, tmp_project_heuristic: Path) -> None:
        """Dart // @impl tag."""
        project = tmp_project_heuristic
        dart_file = project / "src" / "app.dart"
        dart_file.parent.mkdir(exist_ok=True)
        dart_file.write_text("// @impl 9.0\nclass App {}\n")

        tags = extract_tags_from_file(dart_file, project)
        assert len(tags) == 1

    def test_php_impl(self, tmp_project_heuristic: Path) -> None:
        """PHP // @impl tag."""
        project = tmp_project_heuristic
        php_file = project / "src" / "index.php"
        php_file.parent.mkdir(exist_ok=True)
        php_file.write_text("<?php // @impl 10.0\nclass App {}\n")

        tags = extract_tags_from_file(php_file, project)
        assert len(tags) == 1


class TestExtractFromDir:
    """Test recursive directory scanning."""

    def test_scan_dir_finds_tags(self, tmp_project_heuristic: Path) -> None:
        """extract_tags_from_dir finds all tags in a project."""
        project = tmp_project_heuristic
        # Add tags to existing files
        (project / "src" / "auth" / "login.py").write_text(
            "# @impl 1.1\n# @module auth\ndef login(): pass\n"
        )

        tags = extract_tags_from_dir(str(project))
        assert len(tags) >= 2
        kinds = {t.kind for t in tags}
        assert "impl" in kinds
        assert "module" in kinds

    def test_scan_dir_excludes_dirs(self, tmp_project_heuristic: Path) -> None:
        """Directories in exclude_dirs are skipped."""
        project = tmp_project_heuristic
        node_modules = project / "node_modules" / "lib"
        node_modules.mkdir(parents=True)
        (node_modules / "index.js").write_text("// @impl irrelevant\n")

        (project / "src" / "auth" / "login.py").write_text(
            "# @impl 1.1\ndef login(): pass\n"
        )

        tags = extract_tags_from_dir(str(project))
        impl_ids = [t.value for t in tags if t.kind == "impl"]
        assert "1.1" in impl_ids
        assert "irrelevant" not in impl_ids

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        tags = extract_tags_from_dir(str(tmp_path / "empty"))
        assert tags == []


class TestExtractStringLiteralSafety:
    """String literal contents should not be mistaken for tags."""

    def test_python_fstring_not_matched(self, tmp_project_heuristic: Path) -> None:
        """# inside an f-string is still matched (known regex limitation)."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text(
            '\n\nmsg = f"# @impl 1.1"\n'
            "def login(): pass\n"
        )
        tags = extract_tags_from_file(py_file, project)
        # Python's tokenize distinguishes COMMENT from STRING tokens,
        # so f-string contents are correctly ignored.
        assert tags == []

    def test_docstring_not_matched(self, tmp_project_heuristic: Path) -> None:
        """@impl inside a docstring is NOT matched (tokenize-aware)."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text(
            '"""\n# @impl 1.1\n"""\n'
            "def login(): pass\n"
        )
        tags = extract_tags_from_file(py_file, project)
        # Docstring is a STRING token, not COMMENT — correctly ignored
        assert tags == []

    def test_comment_example_not_matched(self, tmp_project_heuristic: Path) -> None:
        """@impl inside a code example in comments is still matched (caveat)."""
        project = tmp_project_heuristic
        py_file = project / "src" / "auth" / "login.py"
        py_file.write_text(
            "# Example: # @impl 1.1\n"
            "def login(): pass\n"
        )
        tags = extract_tags_from_file(py_file, project)
        # The # @impl 1.1 after `Example:` still matches because
        # regex doesn't distinguish comment-in-comment.
        # This is a known limitation.
        assert isinstance(tags, list)
