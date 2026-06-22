"""Shared pytest fixtures for the sempath test suite."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_config() -> dict:
    """Return a valid config dict matching the default config structure."""
    return {
        "handlers": {
            "enabled": ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8", "h9"],
            "h4_threshold": 75,
            "h7_model": "all-MiniLM-L6-v2",
            "h8_provider": "ollama",
            "h8_model": "llama3",
            "h8_url": "http://localhost:11434/v1",
            "h8_api_key": "",
        },
        "index": {
            "auto": True,
            "store": "%APPDATA%\\sempath\\cache",
            "exclude_patterns": [
                "node_modules",
                ".git",
                "venv",
                "__pycache__",
            ],
        },
        "aliases": {
            "main": ["__MAIN", "principal", "important", "primary", "master"],
            "dl": ["Downloads", "download"],
            "docs": ["Documents", "documentation", "docs"],
        },
    }


@pytest.fixture
def mock_fs_path(tmp_path: Path) -> Path:
    """Create a temporary directory tree mimicking a typical user filesystem.

    Structure::

        root/
        ├── Desktop/
        │   ├── __MAIN/
        │   └── docs/
        ├── Downloads/
        └── Documents/
            └── notes.txt
    """
    desktop = tmp_path / "Desktop"
    desktop.mkdir()

    main_dir = desktop / "__MAIN"
    main_dir.mkdir()

    docs_dir = desktop / "docs"
    docs_dir.mkdir()

    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    documents = tmp_path / "Documents"
    documents.mkdir()

    notes = documents / "notes.txt"
    notes.write_text("sample notes content", encoding="utf-8")

    return tmp_path


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_config: dict) -> Path:
    """Write sample_config to a temporary YAML file and return its Path."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(sample_config, default_flow_style=False), encoding="utf-8")
    return config_path
