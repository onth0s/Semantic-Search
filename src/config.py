"""Configuration loading and validation for sempath.

Loads YAML configuration from the user's config directory
(``%APPDATA%\\sempath\\config.yaml`` on Windows), falling back to
the bundled ``config.yaml`` in the project root.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Default configuration — mirrors config.yaml
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
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
            ".mypy_cache",
            ".pytest_cache",
            "build",
            "dist",
        ],
    },
    "aliases": {
        "main": ["__MAIN", "principal", "important", "primary", "master"],
        "dl": ["Downloads", "download"],
        "docs": ["Documents", "documentation", "docs"],
    },
    "heuristics": {
        "categories": {
            "image": {
                "keywords": ["pic", "pics", "picture", "pictures", "photo", "photos", "image", "images", "img", "imgs", "png", "pngs", "jpg", "jpgs", "jpeg", "jpegs", "webp", "gif", "gifs", "bmp", "bmps"],
                "extensions": ["png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff", "ico", "svg"]
            },
            "document": {
                "keywords": ["doc", "docs", "document", "documents", "pdf", "pdfs", "text", "txt", "txts", "csv", "csvs", "md", "markdown", "markdowns"],
                "extensions": ["pdf", "docx", "doc", "txt", "rtf", "odt", "xls", "xlsx", "ppt", "pptx", "csv", "md", "markdown"]
            },
            "code": {
                "keywords": ["code", "script", "scripts", "source", "py", "python", "js", "javascript", "ts", "typescript", "html", "css", "json", "yaml", "yml", "toml"],
                "extensions": ["py", "js", "ts", "html", "css", "json", "yaml", "yml", "toml", "sh", "bat", "ps1", "rs", "go", "cpp", "c", "h"]
            },
            "audio": {
                "keywords": ["audio", "audios", "sound", "sounds", "music", "mp3", "mp3s", "wav", "wavs", "flac", "flacs"],
                "extensions": ["mp3", "wav", "flac", "m4a", "ogg", "aac"]
            },
            "video": {
                "keywords": ["video", "videos", "vid", "vids", "movie", "movies", "film", "films", "mp4", "mp4s", "mkv", "mkvs", "avi", "avis", "mov", "movs"],
                "extensions": ["mp4", "mkv", "avi", "mov", "wmv", "flv", "webm"]
            },
            "archive": {
                "keywords": ["archive", "archives", "compressed", "compression", "zip", "zips", "rar", "rars", "7z", "7zs", "tar", "tars"],
                "extensions": ["zip", "rar", "tar", "gz", "7z", "tgz"]
            },
            "backup_blend": {
                "keywords": ["blend1", "blend1s", "backup", "backups"],
                "extensions": ["blend*"]
            }
        }
    },
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BUNDLED_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
_APPDATA_CONFIG = Path(os.environ.get("APPDATA", "")) / "sempath" / "config.yaml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"%([^%]+)%")


def expand_env_vars(path_str: str) -> Path:
    """Expand Windows-style ``%VAR%`` environment variables in a path string.

    Returns:
        A resolved :class:`~pathlib.Path` with variables expanded.
    """

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))

    return Path(_ENV_VAR_RE.sub(_replace, path_str))


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a new dict.

    - Dict values are merged recursively.
    - All other types in *override* replace the corresponding *base* value.
    """
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate_config(config: dict) -> None:
    """Run basic sanity checks on a loaded config dict.

    Raises:
        ValueError: If the config contains invalid values.
    """
    handlers = config.get("handlers", {})

    # Validate enabled handlers list
    enabled = handlers.get("enabled", [])
    valid_handler_names = {f"h{i}" for i in range(1, 10)}
    for name in enabled:
        if name not in valid_handler_names:
            raise ValueError(
                f"Invalid handler name '{name}' in handlers.enabled. "
                f"Valid names: {sorted(valid_handler_names)}"
            )

    # Validate h4_threshold range
    threshold = handlers.get("h4_threshold", 75)
    if not (0 <= threshold <= 100):
        raise ValueError(f"handlers.h4_threshold must be between 0 and 100, got {threshold}")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: Path | None = None) -> dict:
    """Load and return the merged sempath configuration.

    Resolution order:

    1. If *path* is given explicitly, load that file.
    2. Otherwise try the user-level config at ``%APPDATA%\\sempath\\config.yaml``.
    3. Fall back to the bundled ``config.yaml`` next to the package root.
    4. If nothing is found on disk, use :data:`DEFAULT_CONFIG`.

    The loaded file is deep-merged on top of :data:`DEFAULT_CONFIG` so that
    any missing keys are filled with sensible defaults.

    Args:
        path: Optional explicit path to a YAML config file.

    Returns:
        A fully-merged configuration dictionary.

    Raises:
        FileNotFoundError: If an explicit *path* is given but does not exist.
        ValueError: If the resulting config fails validation.
    """
    user_config: dict = {}

    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    elif _APPDATA_CONFIG.exists():
        with open(_APPDATA_CONFIG, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    elif _BUNDLED_CONFIG.exists():
        with open(_BUNDLED_CONFIG, encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

    merged = _deep_merge(DEFAULT_CONFIG, user_config)

    # Expand environment variables in path-like config values
    index_store = merged.get("index", {}).get("store", "")
    if index_store:
        merged["index"]["store"] = str(expand_env_vars(index_store))

    _validate_config(merged)

    return merged
