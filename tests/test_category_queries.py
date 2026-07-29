"""Regression tests for category queries (songs, pics, videos, docs) without sort flags."""

from __future__ import annotations

from pathlib import Path

from sempath.engine import SearchEngine


def test_category_query_songs_without_flags(sample_config: dict, tmp_path: Path):
    """Query 'songs' matches audio files directly without triggering H7 confirmation or aborting."""
    engine = SearchEngine(sample_config)

    audio_dir = tmp_path / "scratch" / "audio"
    audio_dir.mkdir(parents=True)
    song1 = audio_dir / "track1.wav"
    song2 = audio_dir / "track2.mp3"
    song1.write_text("audio content 1")
    song2.write_text("audio content 2")

    res = engine.find_path("songs", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path in (song1, song2)
    assert res.match.handler == "category_match"
    assert len(res.near_misses) == 1


def test_category_query_pics_without_flags(sample_config: dict, tmp_path: Path):
    """Query 'pics' matches image files directly without triggering H7 confirmation or aborting."""
    engine = SearchEngine(sample_config)

    img_dir = tmp_path / "photos"
    img_dir.mkdir(parents=True)
    pic1 = img_dir / "photo1.png"
    pic1.write_text("image content")

    res = engine.find_path("pics", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == pic1
    assert res.match.handler == "category_match"


def test_category_query_docs_without_flags(sample_config: dict, tmp_path: Path):
    """Query 'doc file' matches document files directly without triggering H7 confirmation."""
    engine = SearchEngine(sample_config)

    docs_dir = tmp_path / "files"
    docs_dir.mkdir(parents=True)
    doc1 = docs_dir / "notes.pdf"
    doc1.write_text("pdf content")

    res = engine.find_path("doc file", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match is not None
    assert res.match.path == doc1
    assert res.match.handler == "category_match"
