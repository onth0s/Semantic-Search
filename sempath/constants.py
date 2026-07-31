"""Central constants and default configuration values for sempath."""

from __future__ import annotations

from typing import Any

SempathConfig = dict[str, Any]

# File & I/O Thresholds
TEXT_FILE_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB

# Matching Thresholds & Magic Numbers
FUZZY_THRESHOLD_DEFAULT: int = 75
DIR_FUZZY_THRESHOLD: int = 80
DIR_PHONETIC_FUZZY_THRESHOLD: int = 50
DIR_MIN_TOKEN_LENGTH: int = 4

CONTENT_SEARCH_EXACT_CONFIDENCE: float = 0.95
CONTENT_SEARCH_CASE_CONFIDENCE: float = 0.80
NEAR_MISS_MIN_CONFIDENCE: float = 0.2

# Learned Memory Defaults
DECAY_HALF_LIFE_DAYS: int = 7

# Search Defaults
DEFAULT_DEPTH: int = 5
DEFAULT_MIN_CONFIDENCE: float = 0.3
DEFAULT_TOP_N: int = 5

# Database Defaults
INDEX_DB_TIMEOUT: float = 30.0
INDEX_BUSY_TIMEOUT_MS: int = 30000
