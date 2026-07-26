"""Shared fixtures for specbridge tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project with docs/ and src/ directories.

    Structure:
      tmp_project/
        docs/
          auth.md
          api.md
        src/
          auth/
            login.py
            logout.py
          api/
            handler.ts
    """
    project = tmp_path / "myproject"
    project.mkdir()

    docs = project / "docs"
    docs.mkdir()
    src = project / "src"
    src.mkdir()

    cwd = os.getcwd()
    os.chdir(str(project))
    yield project
    os.chdir(cwd)


@pytest.fixture
def tmp_project_spectra(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project with spectra-style structure.

    Includes .spectra/trace-mapping.yaml + @impl / <!-- @spec --> tags.
    """
    project = tmp_path / "spectra-project"
    project.mkdir()

    # .spectra/
    dot_spectra = project / ".spectra"
    dot_spectra.mkdir()
    (dot_spectra / ".gitkeep").touch()

    # trace-mapping.yaml
    (dot_spectra / "trace-mapping.yaml").write_text("""\
mappings:
  - id: "1.1"
    description: "User authentication"
    spec: "docs/auth.md"
    tags: ["@spec"]
    code:
      files:
        - "src/auth/login.py"
        - "src/auth/token.py"
      symbols:
        - "authenticate"
        - "verify_token"

  - id: "1.2"
    description: "User logout"
    spec: "docs/auth.md"
    code:
      files:
        - "src/auth/logout.py"
      symbols:
        - "logout"
""")

    # docs/
    docs = project / "docs"
    docs.mkdir()
    (docs / "auth.md").write_text("""\
<!-- @spec 1.1 -->
<!-- @satisfies 1.1 -->
# User Authentication

Users must log in with email and password.

## Login
<!-- @spec 1.1.1 -->
The login form submits to /auth/login.

## Logout
<!-- @spec 1.2 -->
<!-- @satisfies 1.2 -->
Users can end their session.
""")

    # src/
    src = project / "src"
    src.mkdir()
    auth_src = src / "auth"
    auth_src.mkdir()

    (auth_src / "login.py").write_text("""\
# @impl 1.1
# @module auth
# @feature login
def authenticate(email: str, password: str) -> bool:
    return True
""")

    (auth_src / "logout.py").write_text("""\
# @impl 1.2
def logout(session_id: str) -> None:
    pass
""")

    (auth_src / "token.py").write_text("""\
# @impl 1.1
def verify_token(token: str) -> dict:
    return {"user": "test"}
""")

    # tests/
    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text("""\
# @verifies 1.1
from src.auth.login import authenticate

def test_authenticate():
    assert authenticate("a@b.com", "pass") is not None
""")

    cwd = os.getcwd()
    os.chdir(str(project))
    yield project
    os.chdir(cwd)


@pytest.fixture
def tmp_project_heuristic(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a project with no tags — pure structural heuristics.

    Structure:
      project/
        docs/
          auth.md        (heading "# User Login", "## Password Reset")
          reporting.md   (heading "# Reports")
        src/
          auth/
            login.py     (def login(), class Session)
          reports/
            charts.py    (def generate_chart())
    """
    project = tmp_path / "heuristic-project"
    project.mkdir()

    docs = project / "docs"
    docs.mkdir()
    src = project / "src"
    src.mkdir()

    (docs / "auth.md").write_text("""\
# User Login

Users authenticate with email and password.

## Password Reset

Users can reset via email link.
""")

    (docs / "reporting.md").write_text("""\
# Reports

Generate and export reports.
""")

    auth_src = src / "auth"
    auth_src.mkdir()
    (auth_src / "login.py").write_text("""\
def login(email: str) -> bool:
    return True

class Session:
    def __init__(self, user_id: int):
        self.user_id = user_id
""")

    reports_src = src / "reports"
    reports_src.mkdir()
    (reports_src / "charts.py").write_text("""\
def generate_chart(data: list) -> str:
    return "chart.png"
""")

    cwd = os.getcwd()
    os.chdir(str(project))
    yield project
    os.chdir(cwd)
