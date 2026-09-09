"""File operations and text inspection utilities for sempath."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sempath.constants import TEXT_FILE_MAX_BYTES


def is_text_file(path: Path) -> bool:
    """Return True if path points to a readable text file (non-binary and < 5MB)."""
    try:
        if not path.is_file():
            return False
        if path.stat().st_size > TEXT_FILE_MAX_BYTES:
            return False
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return False
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    chunk.decode("latin-1")
                except UnicodeDecodeError:
                    return False
        return True
    except (OSError, PermissionError):
        return False


def read_text_safely(path: Path) -> str | None:
    """Safely read text content of a file with utf-8 / latin-1 fallback."""
    if not is_text_file(path):
        return None
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return None


# Match tier constants (1 = highest confidence, 5 = lowest)
TIER_EXACT_TOKEN = 1
TIER_CI_TOKEN = 2
TIER_EXACT_SUBSTRING = 3
TIER_CI_SUBSTRING = 4
TIER_DELIMITED = 5


@dataclass(frozen=True)
class ContentMatchInfo:
    """Structured information regarding content search matches in a file."""

    snippets: list[tuple[int, str]]
    best_tier: int

    total_occurrences: int


def _is_token_boundary_match(line: str, query: str, ignore_case: bool = False) -> bool:
    """Return True if query occurs as a distinct token (word boundary or punctuation separated)."""
    flags = re.IGNORECASE if ignore_case else 0
    # Match query bounded by word boundaries or common identifier/punctuation boundaries
    # E.g. (PES), [PES], PES-STATE, PES_LOG, or standalone PES
    pattern = rf"(?<![A-Za-z0-9]){re.escape(query)}(?![A-Za-z0-9])"
    return bool(re.search(pattern, line, flags))


def extract_content_match_info(
    content: str, query: str, max_snippets: int = 10
) -> ContentMatchInfo | None:
    """Extract matching snippets and classify the quality tier and occurrence count.

    Match tiers:
    1: Exact token match (e.g. '(PES)', 'PES-STATE', or standalone 'PES')
    2: Case-insensitive token match (e.g. 'pes-validate', 'pes')
    3: Exact substring match within a larger token (e.g. 'FOOPESBAR')
    4: Case-insensitive substring within a token (e.g. 'foreign-types' matching 'pes')
    5: Multi-token delimiter match (e.g. 'Launching-Blender' matching 'Launching Blender')
    """

    if not query or not content:
        return None

    lines = content.splitlines()
    q_lower = query.lower()

    # Pre-check delimiter multi-token pattern
    tokens = [re.escape(t) for t in re.split(r"[\s\-_]+", query.strip()) if t]
    delim_pattern = (
        re.compile(r"[\s\-_.:/]+".join(tokens), re.IGNORECASE) if len(tokens) > 1 else None
    )

    # We collect snippets and track best_tier across all matching lines
    best_tier = float("inf")
    total_occurrences = 0
    tier_1_snippets: list[tuple[int, str]] = []
    tier_2_snippets: list[tuple[int, str]] = []
    tier_3_snippets: list[tuple[int, str]] = []
    tier_4_snippets: list[tuple[int, str]] = []
    tier_5_snippets: list[tuple[int, str]] = []

    token_pattern = rf"(?<![A-Za-z0-9]){re.escape(query)}(?![A-Za-z0-9])"

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # Check Tier 1: Exact token
        if _is_token_boundary_match(raw_line, query, ignore_case=False):
            tier_1_snippets.append((line_num, line))
            best_tier = min(best_tier, TIER_EXACT_TOKEN)
            total_occurrences += len(re.findall(token_pattern, raw_line))
        # Check Tier 2: Case-insensitive token
        elif _is_token_boundary_match(raw_line, query, ignore_case=True):
            tier_2_snippets.append((line_num, line))
            best_tier = min(best_tier, TIER_CI_TOKEN)
            total_occurrences += len(re.findall(token_pattern, raw_line, re.IGNORECASE))
        # Check Tier 3: Exact substring
        elif query in raw_line:
            tier_3_snippets.append((line_num, line))
            best_tier = min(best_tier, TIER_EXACT_SUBSTRING)
            total_occurrences += raw_line.count(query)
        # Check Tier 4: Case-insensitive substring
        elif q_lower in raw_line.lower():
            tier_4_snippets.append((line_num, line))
            best_tier = min(best_tier, TIER_CI_SUBSTRING)
            total_occurrences += raw_line.lower().count(q_lower)
        # Check Tier 5: Delimiter pattern
        elif delim_pattern and delim_pattern.search(raw_line):
            tier_5_snippets.append((line_num, line))
            best_tier = min(best_tier, TIER_DELIMITED)
            total_occurrences += len(delim_pattern.findall(raw_line))

    if best_tier == float("inf"):
        return None

    # Gather snippets in tier priority order up to max_snippets
    collected: list[tuple[int, str]] = []
    all_tier_snippets = (
        tier_1_snippets,
        tier_2_snippets,
        tier_3_snippets,
        tier_4_snippets,
        tier_5_snippets,
    )
    for tier_list in all_tier_snippets:
        for snip in tier_list:
            if len(collected) < max_snippets:
                collected.append(snip)
            else:
                break
        if len(collected) >= max_snippets:
            break

    # Sort collected snippets by line number for clean natural reading order
    collected.sort(key=lambda s: s[0])

    return ContentMatchInfo(
        snippets=collected,
        best_tier=int(best_tier),
        total_occurrences=total_occurrences,
    )


def extract_matching_snippets(
    content: str, query: str, max_snippets: int = 10
) -> list[tuple[int, str]]:
    """Extract line numbers and trimmed line texts matching query.

    Supports exact match, case-insensitive match, and delimiter-normalized matching.
    Preserves backward compatibility by returning list of (line_num, text).
    """
    info = extract_content_match_info(content, query, max_snippets=max_snippets)
    return info.snippets if info else []


def format_human_size(size_bytes: int | float) -> str:
    """Format bytes as human-readable string with exactly 2 decimal places."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_human_mtime(mtime: float) -> str:
    """Format a modification timestamp as a human-readable date-time string."""
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return "1970-01-01 00:00"


def get_path_file_meta(path: Path) -> str:
    """Return a compact '[size, date]' dimmed suffix for path."""
    try:
        st = path.stat()
        sz = format_human_size(st.st_size) if path.is_file() else "DIR"
        dt = format_human_mtime(st.st_mtime)
        return f" [dim][{sz}, {dt}][/]"
    except OSError:
        return ""
