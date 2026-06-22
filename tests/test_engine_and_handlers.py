"""Unit tests for SearchEngine and the H7, H8, H9 handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.engine import SearchEngine
from src.handlers.h7_embedding import EmbeddingHandler
from src.handlers.h8_llm import LLMHandler
from src.handlers.h9_interactive import InteractiveHandler


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


class TestEmbeddingHandler:
    """Tests for H7 EmbeddingHandler."""

    def test_missing_library_fallback(self, sample_config: dict):
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            handler = EmbeddingHandler(sample_config)
            ctx = MagicMock()
            ctx.obj = {"non_interactive": True}
            with patch("click.get_current_context", return_value=ctx):
                res = handler.match("test query", [Path("some_file.txt")])
                assert res is None

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
    """Tests for H8 LLMHandler query rewriter."""

    @patch("urllib.request.urlopen")
    def test_llm_rewrite_and_second_cycle(self, mock_urlopen, sample_config: dict):
        # Mock LLM API JSON response translating to "Desktop/__MAIN"
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Desktop/__MAIN"}}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        handler = LLMHandler(sample_config)
        ctx = MagicMock()
        ctx.obj = {"verbose": True}

        candidates = [Path("C:/User/Desktop/__MAIN"), Path("C:/User/Downloads")]

        with patch("click.get_current_context", return_value=ctx):
            res = handler.match("give me the main directory on desktop", candidates)
            assert res is not None
            assert res.path == Path("C:/User/Desktop/__MAIN")
            assert res.handler == "h8_llm(h1_exact)"


class TestInteractiveHandler:
    """Tests for H9 InteractiveHandler."""

    @patch("click.prompt")
    def test_interactive_selection_and_learning(
        self, mock_prompt, sample_config: dict, tmp_path: Path
    ):
        # User selects option 1 (first near-miss candidate)
        mock_prompt.return_value = 1

        memory_file = tmp_path / "learned_aliases.yaml"

        with patch("src.utils.memory.get_memory_file_path", return_value=memory_file):
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
                from src.utils.memory import load_memory

                memory = load_memory(memory_file)
                assert len(memory) == 1
                assert memory[0]["query"] == "desktop main"
                assert memory[0]["path"] == "C:\\User\\Desktop\\__MAIN"
