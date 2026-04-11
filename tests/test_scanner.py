"""
Tests for ProjectScanner - no LLM calls, uses real temp filesystem.
"""

import pytest
from pathlib import Path
from src.ingestion.scanner import ProjectScanner


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a minimal fake project directory."""
    (tmp_path / "main.py").write_text("def main(): pass\n")
    (tmp_path / "config.yaml").write_text("database:\n  host: localhost\n")
    (tmp_path / "schema.sql").write_text("CREATE TABLE users (id INT PRIMARY KEY);\n")
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
    (tmp_path / "README.md").write_text("# My Project\n")

    # Subdirectory
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "service.py").write_text("class UserService: pass\n")
    (sub / "model.py").write_text("class User: pass\n")

    # Should be ignored
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-312.pyc").write_bytes(b"\x00\x01\x02")

    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "lodash.js").write_text("// lodash\n")

    return tmp_path


class TestScanner:
    def test_scans_supported_files(self, sample_project):
        scanner = ProjectScanner(root_path=str(sample_project))
        files = scanner.scan()
        extensions = {Path(f.relative_path).suffix for f in files}
        assert ".py" in extensions
        assert ".yaml" in extensions
        assert ".sql" in extensions

    def test_ignores_pycache_and_node_modules(self, sample_project):
        scanner = ProjectScanner(root_path=str(sample_project))
        files = scanner.scan()
        paths = [f.relative_path for f in files]
        assert not any("__pycache__" in p for p in paths)
        assert not any("node_modules" in p for p in paths)

    def test_sql_comes_before_python(self, sample_project):
        scanner = ProjectScanner(root_path=str(sample_project))
        files = scanner.scan()
        languages = [f.language for f in files]
        sql_idx = next((i for i, l in enumerate(languages) if l == "SQL"), None)
        python_idx = next((i for i, l in enumerate(languages) if l == "Python"), None)
        assert sql_idx is not None
        assert python_idx is not None
        assert sql_idx < python_idx

    def test_main_py_scores_higher_than_readme(self, sample_project):
        scanner = ProjectScanner(root_path=str(sample_project))
        files = scanner.scan()
        paths = [f.relative_path for f in files]
        main_idx = next((i for i, p in enumerate(paths) if "main.py" in p), None)
        readme_idx = next((i for i, p in enumerate(paths) if "README" in p), None)
        assert main_idx is not None
        assert readme_idx is not None
        assert main_idx < readme_idx

    def test_respects_max_files(self, tmp_path):
        for i in range(20):
            (tmp_path / f"module_{i}.py").write_text(f"# module {i}\n" * 10)
        scanner = ProjectScanner(root_path=str(tmp_path), max_files=5)
        files = scanner.scan()
        assert len(files) <= 5

    def test_truncates_large_files(self, tmp_path):
        large = tmp_path / "big.py"
        large.write_text("x = 1\n" * 10000)  # ~60KB
        scanner = ProjectScanner(root_path=str(tmp_path))
        files = scanner.scan()
        match = next((f for f in files if "big.py" in f.relative_path), None)
        assert match is not None
        assert match.truncated is True

    def test_skips_tiny_files(self, tmp_path):
        (tmp_path / "stub.py").write_text("")  # empty
        (tmp_path / "real.py").write_text("def main(): pass\n" * 5)
        scanner = ProjectScanner(root_path=str(tmp_path))
        files = scanner.scan()
        paths = [f.relative_path for f in files]
        assert not any("stub.py" in p for p in paths)
        assert any("real.py" in p for p in paths)

    def test_directory_tree_excludes_ignored_dirs(self, sample_project):
        scanner = ProjectScanner(root_path=str(sample_project))
        tree = scanner.get_directory_tree()
        assert "__pycache__" not in tree
        assert "node_modules" not in tree
        assert "src" in tree


class TestContextSummary:
    def test_summary_counts_languages(self, sample_project):
        from src.ingestion.context import ProjectContext
        ctx = ProjectContext.from_path(str(sample_project))
        summary = ctx.summary()
        assert summary["total_files"] > 0
        assert "Python" in summary["languages"]
        assert "SQL" in summary["languages"]

    def test_summary_has_project_name(self, sample_project):
        from src.ingestion.context import ProjectContext
        ctx = ProjectContext.from_path(str(sample_project), project_name="MyApp")
        assert ctx.summary()["project_name"] == "MyApp"
