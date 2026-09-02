"""Typed configuration schema and dataclasses for sempath."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sempath.constants import DEFAULT_DEPTH


@dataclass
class HandlersConfig:
    enabled: list[str] = field(
        default_factory=lambda: ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8"]
    )
    h4_threshold: int = 75
    h7_model: str = "BAAI/bge-small-en-v1.5"
    h8_provider: str = "ollama"
    h8_model: str = "minimax-m3:cloud"
    h8_url: str = "http://localhost:11434/v1"
    h8_api_key: str = ""
    h8_top_k: int = 6


@dataclass
class IndexConfig:
    auto: bool = True
    store: str = "%APPDATA%\\sempath\\cache"
    respect_gitignore: bool = False
    exclude_patterns: list[str] = field(
        default_factory=lambda: [
            "node_modules",
            ".git",
            "venv",
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            "build",
            "dist",
        ]
    )


@dataclass
class CategoryConfig:
    keywords: list[str] = field(default_factory=list)
    extensions: list[str] = field(default_factory=list)


def get_default_categories() -> dict[str, CategoryConfig]:
    """Return the default heuristic categories and their keywords/extensions."""
    return {
        "image": CategoryConfig(
            keywords=[
                "pic",
                "pics",
                "picture",
                "pictures",
                "photo",
                "photos",
                "image",
                "images",
                "img",
                "imgs",
                "png",
                "pngs",
                "jpg",
                "jpgs",
                "jpeg",
                "jpegs",
                "webp",
                "gif",
                "gifs",
                "bmp",
                "bmps",
            ],
            extensions=["png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff", "ico", "svg"],
        ),
        "document": CategoryConfig(
            keywords=[
                "doc",
                "docs",
                "document",
                "documents",
                "pdf",
                "pdfs",
                "text",
                "txt",
                "txts",
                "csv",
                "csvs",
                "md",
                "markdown",
                "markdowns",
                "vcf",
                "vcfs",
            ],
            extensions=[
                "pdf",
                "docx",
                "doc",
                "txt",
                "rtf",
                "odt",
                "xls",
                "xlsx",
                "ppt",
                "pptx",
                "csv",
                "md",
                "markdown",
                "vcf",
            ],
        ),
        "code": CategoryConfig(
            keywords=[
                "code",
                "script",
                "scripts",
                "source",
                "py",
                "python",
                "js",
                "javascript",
                "ts",
                "typescript",
                "html",
                "css",
                "json",
                "yaml",
                "yml",
                "toml",
            ],
            extensions=[
                "py",
                "js",
                "ts",
                "html",
                "css",
                "json",
                "yaml",
                "yml",
                "toml",
                "sh",
                "bat",
                "ps1",
                "rs",
                "go",
                "cpp",
                "c",
                "h",
            ],
        ),
        "audio": CategoryConfig(
            keywords=[
                "audio",
                "audios",
                "sound",
                "sounds",
                "music",
                "mp3",
                "mp3s",
                "wav",
                "wavs",
                "flac",
                "flacs",
                "song",
                "songs",
                "tune",
                "tunes",
            ],
            extensions=["mp3", "wav", "flac", "m4a", "ogg", "aac"],
        ),
        "video": CategoryConfig(
            keywords=[
                "video",
                "videos",
                "vid",
                "vids",
                "movie",
                "movies",
                "film",
                "films",
                "mp4",
                "mp4s",
                "mkv",
                "mkvs",
                "avi",
                "avis",
                "mov",
                "movs",
            ],
            extensions=["mp4", "mkv", "avi", "mov", "wmv", "flv", "webm"],
        ),
        "archive": CategoryConfig(
            keywords=[
                "archive",
                "archives",
                "compressed",
                "compression",
                "zip",
                "zips",
                "rar",
                "rars",
                "7z",
                "7zs",
                "tar",
                "tars",
            ],
            extensions=["zip", "rar", "tar", "gz", "7z", "tgz"],
        ),
        "executable": CategoryConfig(
            keywords=[
                "exe",
                "exes",
                "executable",
                "executables",
                "binary",
                "binaries",
            ],
            extensions=["exe", "msi", "bat", "cmd", "ps1", "sh"],
        ),
        "backup_blend": CategoryConfig(
            keywords=["blend1", "blend1s", "backup", "backups"],
            extensions=["blend*"],
        ),
    }


@dataclass
class HeuristicsConfig:
    categories: dict[str, CategoryConfig] = field(default_factory=get_default_categories)


@dataclass
class AppConfig:
    depth: int = DEFAULT_DEPTH
    verbose: bool = True
    exhaustive: bool = True
    handlers: HandlersConfig = field(default_factory=HandlersConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    aliases: dict[str, list[str]] = field(
        default_factory=lambda: {
            "main": ["__MAIN", "principal", "important", "primary", "master"],
            "dl": ["Downloads", "download"],
            "docs": ["Documents", "documentation", "docs"],
        }
    )
    presets: dict[str, str] = field(
        default_factory=lambda: {
            "0": "h1-6",
            "fast": "h1-6",
            "llm": "h8",
            "all": "h1-8",
        }
    )
    heuristics: HeuristicsConfig = field(default_factory=HeuristicsConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert AppConfig to a standard nested dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Create an AppConfig instance from a nested dictionary."""
        handlers_data = data.get("handlers", {})
        handlers = HandlersConfig(
            enabled=list(
                handlers_data.get("enabled", ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8"])
            ),
            h4_threshold=int(handlers_data.get("h4_threshold", 75)),
            h7_model=str(handlers_data.get("h7_model", "BAAI/bge-small-en-v1.5")),
            h8_provider=str(handlers_data.get("h8_provider", "ollama")),
            h8_model=str(handlers_data.get("h8_model", "minimax-m3:cloud")),
            h8_url=str(handlers_data.get("h8_url", "http://localhost:11434/v1")),
            h8_api_key=str(handlers_data.get("h8_api_key", "")),
            h8_top_k=int(handlers_data.get("h8_top_k", 6)),
        )

        index_data = data.get("index", {})
        index = IndexConfig(
            auto=bool(index_data.get("auto", True)),
            store=str(index_data.get("store", "%APPDATA%\\sempath\\cache")),
            respect_gitignore=bool(index_data.get("respect_gitignore", False)),
            exclude_patterns=list(
                index_data.get(
                    "exclude_patterns",
                    [
                        "node_modules",
                        ".git",
                        "venv",
                        "__pycache__",
                        ".mypy_cache",
                        ".pytest_cache",
                        "build",
                        "dist",
                    ],
                )
            ),
        )

        heuristics_data = data.get("heuristics", {})
        raw_categories = heuristics_data.get("categories", {})
        categories = {}
        for cat_name, cat_val in raw_categories.items():
            if isinstance(cat_val, dict):
                categories[cat_name] = CategoryConfig(
                    keywords=list(cat_val.get("keywords", [])),
                    extensions=list(cat_val.get("extensions", [])),
                )
            elif isinstance(cat_val, CategoryConfig):
                categories[cat_name] = cat_val
        heuristics = HeuristicsConfig(
            categories=categories if categories else get_default_categories()
        )

        return cls(
            depth=int(data.get("depth", DEFAULT_DEPTH)),
            verbose=bool(data.get("verbose", True)),
            exhaustive=bool(data.get("exhaustive", True)),
            handlers=handlers,
            index=index,
            aliases={
                k: list(v) if isinstance(v, list) else [str(v)]
                for k, v in data.get("aliases", {}).items()
            },
            presets={str(k): str(v) for k, v in data.get("presets", {}).items()},
            heuristics=heuristics,
        )
