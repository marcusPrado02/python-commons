"""Unit tests for Alembic env boilerplate generator (§27.6)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mp_commons.adapters.sqlalchemy.migrations import (
    ALEMBIC_ENV_TEMPLATE,
    ALEMBIC_INI_TEMPLATE,
    ALEMBIC_SCRIPT_MAKO,
    generate_alembic_files,
)


# ---------------------------------------------------------------------------
# Template content sanity checks
# ---------------------------------------------------------------------------


class TestTemplateConstants:
    def test_alembic_ini_is_nonempty_string(self) -> None:
        assert isinstance(ALEMBIC_INI_TEMPLATE, str)
        assert len(ALEMBIC_INI_TEMPLATE) > 100

    def test_alembic_ini_contains_script_location(self) -> None:
        assert "script_location = migrations" in ALEMBIC_INI_TEMPLATE

    def test_alembic_ini_contains_sqlalchemy_url(self) -> None:
        assert "sqlalchemy.url" in ALEMBIC_INI_TEMPLATE

    def test_alembic_ini_contains_loggers_section(self) -> None:
        assert "[loggers]" in ALEMBIC_INI_TEMPLATE

    def test_env_template_is_nonempty_string(self) -> None:
        assert isinstance(ALEMBIC_ENV_TEMPLATE, str)
        assert len(ALEMBIC_ENV_TEMPLATE) > 200

    def test_env_template_contains_asyncio_run(self) -> None:
        assert "asyncio.run" in ALEMBIC_ENV_TEMPLATE

    def test_env_template_contains_async_engine(self) -> None:
        assert "async_engine_from_config" in ALEMBIC_ENV_TEMPLATE

    def test_env_template_contains_offline_migration(self) -> None:
        assert "run_migrations_offline" in ALEMBIC_ENV_TEMPLATE

    def test_env_template_contains_online_migration(self) -> None:
        assert "run_migrations_online" in ALEMBIC_ENV_TEMPLATE

    def test_env_template_references_mp_commons_base(self) -> None:
        assert "mp_commons.adapters.sqlalchemy" in ALEMBIC_ENV_TEMPLATE

    def test_env_template_supports_database_url_env_override(self) -> None:
        assert "DATABASE_URL" in ALEMBIC_ENV_TEMPLATE

    def test_script_mako_is_nonempty_string(self) -> None:
        assert isinstance(ALEMBIC_SCRIPT_MAKO, str)
        assert len(ALEMBIC_SCRIPT_MAKO) > 50

    def test_script_mako_contains_upgrade_function(self) -> None:
        assert "def upgrade" in ALEMBIC_SCRIPT_MAKO

    def test_script_mako_contains_downgrade_function(self) -> None:
        assert "def downgrade" in ALEMBIC_SCRIPT_MAKO


# ---------------------------------------------------------------------------
# §27.6 — generate_alembic_files()
# ---------------------------------------------------------------------------


class TestGenerateAlembicFiles:
    def test_creates_alembic_ini(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        assert (tmp_path / "alembic.ini").exists()

    def test_creates_migrations_env_py(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        assert (tmp_path / "migrations" / "env.py").exists()

    def test_creates_migrations_script_mako(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        assert (tmp_path / "migrations" / "script.py.mako").exists()

    def test_creates_versions_directory(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        assert (tmp_path / "migrations" / "versions").is_dir()

    def test_creates_versions_gitkeep(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        assert (tmp_path / "migrations" / "versions" / ".gitkeep").exists()

    def test_returns_list_of_paths(self, tmp_path: Path) -> None:
        result = generate_alembic_files(tmp_path)
        assert isinstance(result, list)
        assert len(result) >= 4  # ini + env.py + mako + .gitkeep

    def test_returned_paths_all_exist(self, tmp_path: Path) -> None:
        for p in generate_alembic_files(tmp_path):
            assert p.exists(), f"{p} should exist"

    def test_alembic_ini_content(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        content = (tmp_path / "alembic.ini").read_text()
        assert "script_location = migrations" in content
        assert "sqlalchemy.url" in content

    def test_env_py_content_has_async_run(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        content = (tmp_path / "migrations" / "env.py").read_text()
        assert "asyncio.run" in content
        assert "run_migrations_online" in content

    def test_script_mako_content(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        content = (tmp_path / "migrations" / "script.py.mako").read_text()
        assert "def upgrade" in content
        assert "def downgrade" in content

    def test_raises_file_exists_error_without_overwrite(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        with pytest.raises(FileExistsError):
            generate_alembic_files(tmp_path)

    def test_overwrite_true_replaces_files(self, tmp_path: Path) -> None:
        generate_alembic_files(tmp_path)
        # Should not raise
        generate_alembic_files(tmp_path, overwrite=True)
        assert (tmp_path / "alembic.ini").exists()

    def test_accepts_string_dest_dir(self, tmp_path: Path) -> None:
        generate_alembic_files(str(tmp_path / "proj"))
        assert (tmp_path / "proj" / "alembic.ini").exists()

    def test_creates_nested_dest_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        generate_alembic_files(nested)
        assert (nested / "alembic.ini").exists()

    def test_returns_path_objects(self, tmp_path: Path) -> None:
        result = generate_alembic_files(tmp_path)
        assert all(isinstance(p, Path) for p in result)
