"""Unit tests for SearchEngine and the H7, H8, H9 handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sempath.engine import SearchEngine
from sempath.handlers.h7_embedding import EmbeddingHandler
from sempath.handlers.h8_llm import LLMHandler
from sempath.handlers.h9_interactive import InteractiveHandler


class TestSearchEngineHeuristics:
    """Tests that SearchEngine extracts and applies query heuristics correctly."""

    def test_find_path_with_latest_heuristic(self, tmp_path: Path, sample_config: dict):
        # Create temp files with different mtimes
        import time

        f1 = tmp_path / "doc_old.txt"
        f2 = tmp_path / "doc_new.txt"
        f1.write_text("old", encoding="utf-8")
        time.sleep(0.1)  # Ensure distinct mtime
        f2.write_text("new", encoding="utf-8")

        engine = SearchEngine(sample_config)

        # Force bypass auto-indexing to test scan_directory path
        # Query with "latest" keyword
        res = engine.find_path(
            query="latest doc", root_dir=tmp_path, no_index=True, min_confidence=0.1
        )
        assert res.status == "success"
        # "latest" heuristic triggers sorting by mtime desc, so f2 should be first
        assert res.match is not None
        assert res.match.path == f2


class TestSearchEngineTypeFiltering:
    """Tests that SearchEngine filters candidates correctly based on path type intent."""

    def test_find_path_directory_intent(self, tmp_path: Path, sample_config: dict):
        d1 = tmp_path / "some_dir"
        d1.mkdir()
        f1 = tmp_path / "some_file.txt"
        f1.write_text("content", encoding="utf-8")

        engine = SearchEngine(sample_config)

        # Query specifying "folder"
        ctx = MagicMock()
        ctx.obj = {"non_interactive": True}
        with patch("click.get_current_context", return_value=ctx):
            res = engine.find_path(
                query="some folder",
                root_dir=tmp_path,
                no_index=True,
                min_confidence=0.1,
                non_interactive=True,
            )
        assert res.status == "success"
        # It should ignore the file and match the directory
        assert res.match is not None
        assert res.match.path == d1

    def test_find_path_file_intent(self, tmp_path: Path, sample_config: dict):
        d1 = tmp_path / "some_dir"
        d1.mkdir()
        f1 = tmp_path / "some"
        f1.write_text("content", encoding="utf-8")

        engine = SearchEngine(sample_config)

        # Query specifying "file"
        ctx = MagicMock()
        ctx.obj = {"non_interactive": True}
        with patch("click.get_current_context", return_value=ctx):
            res = engine.find_path(
                query="some file",
                root_dir=tmp_path,
                no_index=True,
                min_confidence=0.1,
                non_interactive=True,
            )
        assert res.status == "success"
        # It should ignore the directory and match the file
        assert res.match is not None
        assert res.match.path == f1


class TestEmbeddingHandler:
    """Tests for H7 EmbeddingHandler."""

    def test_missing_library_fallback(self, sample_config: dict):
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            handler = EmbeddingHandler(sample_config)
            ctx = MagicMock()
            ctx.obj = {"non_interactive": True}
            with (
                patch("click.get_current_context", return_value=ctx),
                patch("sempath.handlers.h7_embedding.err_console.print") as mock_print,
            ):
                res = handler.match("test query", [Path("some_file.txt")])
                assert res is None
                output = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
                assert "pip install -e .[semantic]" in output
                assert "pip install sempath[semantic]" in output

    def test_embedding_match_success(self, sample_config: dict):
        # Mock sentence_transformers library
        mock_st = MagicMock()
        mock_model = MagicMock()
        mock_st.SentenceTransformer.return_value = mock_model

        # Mock cosine similarity return (highest score for second candidate)
        mock_scores = MagicMock()
        mock_scores.argmax.return_value = 1
        mock_scores.__getitem__.side_effect = lambda idx: [0.1, 0.95][idx]

        mock_cos_sim = MagicMock()
        mock_cos_sim.__getitem__.return_value = mock_scores
        mock_st.util.cos_sim.return_value = mock_cos_sim

        with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
            handler = EmbeddingHandler(sample_config)
            ctx = MagicMock()
            ctx.obj = {"non_interactive": True, "verbose": True}
            with patch("click.get_current_context", return_value=ctx):
                candidates = [Path("C:/User/Desktop/old"), Path("C:/User/Desktop/important")]
                res = handler.match("important folder", candidates)
                assert res is not None
                assert res.path == Path("C:/User/Desktop/important")
                assert res.confidence == 0.95
                assert res.handler == "h7_embedding"


class TestLLMHandler:
    """Tests for H8 LLMHandler direct semantic path matcher."""

    @patch("sempath.handlers.h8_llm._check_model_available")
    @patch("urllib.request.urlopen")
    def test_llm_direct_path_match(self, mock_urlopen, mock_check, sample_config: dict):
        """H8 asks the LLM to pick paths and returns matched MatchResults."""
        # LLM returns two relative paths, one per line
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "__MAIN\nDownloads"}}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        handler = LLMHandler(sample_config)
        ctx = MagicMock()
        # root must match so relative_to() works
        ctx.obj = {"verbose": True, "root": Path("C:/User")}

        candidates = [Path("C:/User/__MAIN"), Path("C:/User/Downloads"), Path("C:/User/Videos")]

        with patch("click.get_current_context", return_value=ctx):
            results = handler.match_all("give me the main directory", candidates)

        assert len(results) == 2
        assert results[0].path == Path("C:/User/__MAIN")
        assert results[0].handler == "h8_llm"
        assert results[0].confidence == 0.80
        assert results[1].path == Path("C:/User/Downloads")

    @patch("sempath.handlers.h8_llm._check_model_available")
    @patch("urllib.request.urlopen")
    def test_llm_match_returns_single_best(self, mock_urlopen, mock_check, sample_config: dict):
        """match() returns the first result from match_all."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Videos"}}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        handler = LLMHandler(sample_config)
        ctx = MagicMock()
        ctx.obj = {"verbose": True, "root": Path("C:/User")}

        candidates = [Path("C:/User/Videos"), Path("C:/User/Downloads")]

        with patch("click.get_current_context", return_value=ctx):
            res = handler.match("show me my videos", candidates)

        assert res is not None
        assert res.path == Path("C:/User/Videos")

    @patch(
        "sempath.handlers.h8_llm._check_model_available",
        side_effect=ValueError("Model 'xyz' not available"),
    )  # noqa: E501
    def test_llm_raises_on_missing_model(self, mock_check, sample_config: dict):
        """H8 propagates ValueError when model is not available — no fallback."""
        handler = LLMHandler(sample_config)
        ctx = MagicMock()
        ctx.obj = {"verbose": True, "root": Path("C:/User")}

        candidates = [Path("C:/User/__MAIN")]

        with (
            patch("click.get_current_context", return_value=ctx),
            pytest.raises(ValueError, match="not available"),
        ):
            handler.match_all("main dir", candidates)


class TestInteractiveHandler:
    """Tests for H9 InteractiveHandler."""

    @patch("click.prompt")
    def test_non_interactive_skips_prompt(self, mock_prompt, sample_config: dict):
        handler = InteractiveHandler(sample_config)
        ctx = MagicMock()
        ctx.obj = {"non_interactive": True}

        with patch("click.get_current_context", return_value=ctx):
            res = handler.match("desktop main", [Path("C:/User/Desktop/__MAIN")])

        assert res is None
        mock_prompt.assert_not_called()

    @patch("click.prompt")
    def test_interactive_selection_and_learning(
        self, mock_prompt, sample_config: dict, tmp_path: Path
    ):
        # User selects option 1 (first near-miss candidate)
        mock_prompt.return_value = 1

        memory_file = tmp_path / "learned_aliases.yaml"

        with patch("sempath.utils.memory.get_memory_file_path", return_value=memory_file):
            handler = InteractiveHandler(sample_config)
            ctx = MagicMock()
            ctx.obj = {"non_interactive": False, "verbose": True}

            candidates = [Path("C:/User/Desktop/__MAIN"), Path("C:/User/Downloads")]

            with patch("click.get_current_context", return_value=ctx):
                res = handler.match("desktop main", candidates)
                assert res is not None
                assert res.path == Path("C:/User/Desktop/__MAIN")
                assert res.handler == "h9_interactive"
                assert res.confidence == 1.0

                # Verify that confirmation was stored to memory
                from sempath.utils.memory import load_memory

                memory = load_memory(memory_file)
                assert len(memory) == 1
                assert memory[0]["query"] == "desktop main"
                assert memory[0]["path"] == "C:\\User\\Desktop\\__MAIN"


def test_category_empty_candidates_custom_messages(sample_config: dict, tmp_path: Path):
    """SearchEngine returns targeted fail messages when category matching yields no candidates."""
    engine = SearchEngine(sample_config)

    # 1. Query "songs" -> No audio files found (specifically "No songs found!")
    res = engine.find_path("songs", tmp_path, no_index=True)
    assert res.status == "failed"
    assert res.message == "No songs found!"

    # 2. Query "tunes" -> No tunes found!
    res = engine.find_path("tunes", tmp_path, no_index=True)
    assert res.status == "failed"
    assert res.message == "No tunes found!"

    # 3. Query "music" -> No audio files found!
    res = engine.find_path("music", tmp_path, no_index=True)
    assert res.status == "failed"
    assert res.message == "No audio files found!"

    # 4. Query "pics" -> No image files found!
    res = engine.find_path("pics", tmp_path, no_index=True)
    assert res.status == "failed"
    assert res.message == "No image files found!"


def test_directory_content_matching(sample_config: dict, tmp_path: Path):
    """SearchEngine finds category-matching files inside directories that match the search term."""
    engine = SearchEngine(sample_config)

    # Setup directories and files
    akira_dir = tmp_path / "3D-to-reGEN-to-VID" / "Mado Akira"
    akira_dir.mkdir(parents=True)
    img_inside = akira_dir / "1 - Untitled.png"
    img_inside.write_text("", encoding="utf-8")
    txt_inside = akira_dir / "notes.txt"
    txt_inside.write_text("", encoding="utf-8")

    other_dir = tmp_path / "Other Folder"
    other_dir.mkdir(parents=True)
    img_outside = other_dir / "arweuyh.png"
    img_outside.write_text("", encoding="utf-8")

    # Search for "akira pics" -> should find the image inside Mado Akira
    res = engine.find_path("akira pics", tmp_path, no_index=True, top_n=5)
    assert res.status == "success"
    assert res.match.path.resolve() == img_inside.resolve()
    assert res.match.handler == "directory_content_match"
    assert "Matching files inside directory:" in res.message
    # Check that it tells us the directory name in the message
    assert "Mado Akira" in res.message


def test_directory_content_matching_fuzzy_and_phonetic(sample_config: dict, tmp_path: Path):
    """SearchEngine finds category files inside directories that match fuzzily or phonetically."""
    engine = SearchEngine(sample_config)

    # Setup Mado Akira directory
    akira_dir = tmp_path / "Mado Akira"
    akira_dir.mkdir(parents=True)
    img_inside = akira_dir / "akira.png"
    img_inside.write_text("", encoding="utf-8")

    # 1. Fuzzy match "akri pics" -> matches "Mado Akira"
    res = engine.find_path("akri pics", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match.path.resolve() == img_inside.resolve()

    # 2. Phonetic match "akera pics" -> matches "Mado Akira"
    res = engine.find_path("akera pics", tmp_path, no_index=True)
    assert res.status == "success"
    assert res.match.path.resolve() == img_inside.resolve()


def test_directory_content_matching_ancestor(sample_config: dict, tmp_path: Path):
    """SearchEngine finds files when the search term matches an ancestor/current folder."""
    engine = SearchEngine(sample_config)

    # Setup Desktop directory structure
    desktop = tmp_path / "Desktop"
    desktop.mkdir(parents=True)
    song = desktop / "Roi.mp3"
    song.write_text("", encoding="utf-8")

    # Search from within Desktop itself with query "dsktp song"
    res = engine.find_path("dsktp song", desktop, no_index=True)
    assert res.status == "success"
    assert res.match.path.resolve() == song.resolve()


def test_embedding_handler_similarity_threshold(sample_config: dict):
    """EmbeddingHandler returns None for best matches with cosine similarity below 0.5."""
    import sys
    from unittest.mock import MagicMock, patch

    mock_st = MagicMock()
    mock_scores = MagicMock()
    mock_scores.argmax.return_value = 0
    # Simulate a similarity of 0.45 (< 0.5)
    mock_scores.__getitem__.side_effect = lambda idx: [0.45][idx]

    mock_cos_sim = MagicMock()
    mock_cos_sim.__getitem__.return_value = mock_scores
    mock_st.util.cos_sim.return_value = mock_cos_sim

    with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
        handler = EmbeddingHandler(sample_config)
        ctx = MagicMock()
        ctx.obj = {"non_interactive": True, "verbose": True}
        with patch("click.get_current_context", return_value=ctx):
            candidates = [Path("C:/User/Desktop/old")]
            # Score is 0.45 (< 0.5), so it should return None
            res = handler.match("song", candidates)
            assert res is None

            # Test match_all should also return empty list
            res_all = handler.match_all("song", candidates)
            assert len(res_all) == 0
