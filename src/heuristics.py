"""Heuristic Intent Detector for sempath.

Parses temporal, file type, and ordering keywords from queries to produce
canonical filter parameters and a cleaned search string.
"""

from __future__ import annotations

import re
from datetime import timedelta

# Type maps
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
DOCUMENT_EXTENSIONS = {"pdf", "docx", "doc", "txt", "rtf", "odt"}

# Regexes
TEMPORAL_RE = re.compile(
    r"\b(?:modified|changed)?\s*(yesterday|today|last\s+week|last\s+month)\b",
    re.IGNORECASE,
)
TYPE_RE = re.compile(
    r"\b(pic|photo|image|doc|document|pdf)s?\b",
    re.IGNORECASE,
)
LATEST_RE = re.compile(
    r"\b(latest|newest)\b",
    re.IGNORECASE,
)
LARGEST_RE = re.compile(
    r"\b(largest|biggest)\b",
    re.IGNORECASE,
)
DIR_INTENT_RE = re.compile(
    r"\b(dir|directory|folder|folders)\b",
    re.IGNORECASE,
)
FILE_INTENT_RE = re.compile(
    r"\b(file|files)\b",
    re.IGNORECASE,
)


def extract_heuristics(query: str) -> dict:
    """Extract temporal, type, ordering, size, and directory/file intents from query.

    Returns:
        A dictionary with keys:
            - 'clean_query': query with heuristic terms removed and stripped.
            - 'modified_within_seconds': max age in seconds, or None.
            - 'extensions': list of lowercase extensions, or None.
            - 'latest': boolean indicating if 'latest'/'newest' was requested.
            - 'largest': boolean indicating if 'largest'/'biggest' was requested.
            - 'directory_only': boolean indicating if query is looking for a directory.
            - 'file_only': boolean indicating if query is looking for a file.
    """
    clean_query = query
    modified_within_seconds = None
    extensions = None
    latest = False
    largest = False
    directory_only = False
    file_only = False

    # Temporal match
    temp_match = TEMPORAL_RE.search(clean_query)
    if temp_match:
        term = temp_match.group(1).lower()
        if term in ("yesterday", "today"):
            modified_within_seconds = int(timedelta(days=1).total_seconds())
        elif term == "last week":
            modified_within_seconds = int(timedelta(days=7).total_seconds())
        elif term == "last month":
            modified_within_seconds = int(timedelta(days=30).total_seconds())

        clean_query = TEMPORAL_RE.sub("", clean_query)

    # Type match
    type_match = TYPE_RE.search(clean_query)
    if type_match:
        term = type_match.group(1).lower()
        if term in ("pic", "photo", "image"):
            extensions = sorted(list(IMAGE_EXTENSIONS))
        elif term in ("doc", "document"):
            extensions = sorted(list(DOCUMENT_EXTENSIONS))
        elif term == "pdf":
            extensions = ["pdf"]

        clean_query = TYPE_RE.sub("", clean_query)

    # Latest match
    latest_match = LATEST_RE.search(clean_query)
    if latest_match:
        latest = True
        clean_query = LATEST_RE.sub("", clean_query)

    # Largest match
    largest_match = LARGEST_RE.search(clean_query)
    if largest_match:
        largest = True
        clean_query = LARGEST_RE.sub("", clean_query)

    # Directory intent match
    dir_match = DIR_INTENT_RE.search(clean_query)
    if dir_match:
        directory_only = True
        clean_query = DIR_INTENT_RE.sub("", clean_query)

    # File intent match
    file_match = FILE_INTENT_RE.search(clean_query)
    if file_match:
        file_only = True
        clean_query = FILE_INTENT_RE.sub("", clean_query)

    # Clean up whitespace runs
    clean_query = re.sub(r"\s+", " ", clean_query).strip()

    return {
        "clean_query": clean_query,
        "modified_within_seconds": modified_within_seconds,
        "extensions": extensions,
        "latest": latest,
        "largest": largest,
        "directory_only": directory_only,
        "file_only": file_only,
    }
