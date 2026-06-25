"""Unit tests for multiple match retrieval, substring matching, and token-subset matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from sempath.engine import SearchEngine
from sempath.handlers.h2_case_insensitive import CaseInsensitiveHandler
from sempath.handlers.h3_token_normalized import TokenNormalizedHandler


@pytest.fixture
def feet_candidates() -> list[Path]:
    return [
        Path("C:/ar-T/zzz - DONE/About Feet"),
        Path("C:/ar-T/zzz - DONE/About Feet/B&W Stylized Shape/foot_study_003.png"),
        Path("C:/ar-T/zzz - DONE/About Feet/Best Looking Sole/best_looking_foot_sole__feet.png"),
        Path("C:/ar-T/zzz - DONE/3D-to-reGEN-to-VID/var_01/var/unnamed2d_FOOT_FIX.png"),
        Path("C:/ar-T/zzz - DONE/Last Tracing, Foot Switch"),
        Path("C:/ar-T/zzz - DONE/Simple Foot Render"),
        Path("C:/ar-T/zzz - DONE/DVa Raised Sole"),
        Path("C:/ar-T/zzz - DONE/Sitting on a Bench, Soles Peaking"),
        Path("C:/ar-T/zzz - DONE/Sitting on a Bench, Soles Peaking/soles_peeking.png"),
    ]


def test_h2_substring_matching_feet(sample_config: dict, feet_candidates: list[Path]):
    """h2_case_insensitive matches 'feet' in all paths containing it as substring."""
    handler = CaseInsensitiveHandler(sample_config)
    results = handler.match_all("feet", feet_candidates)

    matched_paths = [r.path for r in results]
    assert len(matched_paths) == 2
    assert Path("C:/ar-T/zzz - DONE/About Feet") in matched_paths
    assert (
        Path("C:/ar-T/zzz - DONE/About Feet/Best Looking Sole/best_looking_foot_sole__feet.png")
        in matched_paths
    )
    assert all(r.confidence == 0.85 for r in results)


def test_h2_substring_matching_foot(sample_config: dict, feet_candidates: list[Path]):
    """h2_case_insensitive matches 'foot' in all paths containing it as substring."""
    handler = CaseInsensitiveHandler(sample_config)
    results = handler.match_all("foot", feet_candidates)

    matched_paths = [r.path for r in results]
    # 'foot' matches:
    # - About Feet/B&W Stylized Shape/foot_study_003.png
    # - About Feet/Best Looking Sole/best_looking_foot_sole__feet.png
    # - 3D-to-reGEN-to-VID/var_01/var/unnamed2d_FOOT_FIX.png (case-insensitive)
    # - Last Tracing, Foot Switch
    # - Simple Foot Render
    assert len(matched_paths) == 5
    assert (
        Path("C:/ar-T/zzz - DONE/About Feet/B&W Stylized Shape/foot_study_003.png") in matched_paths
    )
    assert Path("C:/ar-T/zzz - DONE/Last Tracing, Foot Switch") in matched_paths


def test_h2_substring_matching_sole(sample_config: dict, feet_candidates: list[Path]):
    """h2_case_insensitive matches 'sole' in all paths containing 'sole' or 'soles' as substring."""
    handler = CaseInsensitiveHandler(sample_config)
    results = handler.match_all("sole", feet_candidates)

    matched_paths = [r.path for r in results]
    # 'sole' matches:
    # - About Feet/Best Looking Sole/best_looking_foot_sole__feet.png
    # - DVa Raised Sole
    # - Sitting on a Bench, Soles Peaking
    # - Sitting on a Bench, Soles Peaking/soles_peeking.png
    assert len(matched_paths) == 4
    assert Path("C:/ar-T/zzz - DONE/DVa Raised Sole") in matched_paths
    assert (
        Path("C:/ar-T/zzz - DONE/Sitting on a Bench, Soles Peaking/soles_peeking.png")
        in matched_paths
    )


def test_h3_subset_matching_feet(sample_config: dict, feet_candidates: list[Path]):
    """h3_token_normalized matches 'feet' when 'feet' is a subset of candidate tokens."""
    handler = TokenNormalizedHandler(sample_config)
    results = handler.match_all("feet", feet_candidates)

    matched_paths = [r.path for r in results]
    # 'feet' token subset matches:
    # - About Feet (tokens: about, feet)
    # - About Feet/Best Looking Sole/best_looking_foot_sole__feet.png
    #   (tokens: best, looking, foot, sole, feet, png)
    assert len(matched_paths) == 2
    assert Path("C:/ar-T/zzz - DONE/About Feet") in matched_paths
    assert (
        Path("C:/ar-T/zzz - DONE/About Feet/Best Looking Sole/best_looking_foot_sole__feet.png")
        in matched_paths
    )
    assert all(r.confidence == 0.90 for r in results)


def test_engine_success_multi_match(tmp_path: Path, sample_config: dict):
    """SearchEngine correctly groups and ranks multiple matches under success near_misses."""
    # Write config
    sample_config["handlers"]["enabled"] = ["h1", "h2", "h3"]
    engine = SearchEngine(sample_config)

    # Create temp files
    f1 = tmp_path / "About Feet"
    f1.mkdir()
    f2 = tmp_path / "Best Looking Sole"
    f2.mkdir()
    f3 = f2 / "best_looking_foot_sole__feet.png"
    f3.write_text("", encoding="utf-8")

    res = engine.find_path("feet", tmp_path, no_index=True, min_confidence=0.3, top_n=5)

    assert res.status == "success"
    # The top match should be 'About Feet' (depth 1) over the file (depth 2)
    assert res.match.path == f1.resolve()
    # The secondary match should be in near_misses
    assert len(res.near_misses) == 1
    assert res.near_misses[0].path == f3.resolve()


def test_exhaustive_feet_foot_sole(tmp_path: Path, sample_config: dict):
    """Test that SearchEngine finds exactly 2 feet, 5 foot, and 12 sole matches."""
    sample_config["handlers"]["enabled"] = ["h1", "h2", "h3"]
    # Force exhaustive mode on config
    sample_config["exhaustive"] = True
    engine = SearchEngine(sample_config)

    # Helper to create files
    def make_file(rel_path: str):
        p = tmp_path / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")

    # Helper to create dirs
    def make_dir(rel_path: str):
        p = tmp_path / rel_path
        p.mkdir(parents=True, exist_ok=True)

    # 12 paths matching 'sole' (which also contain 'foot' / 'feet' matches):
    make_dir("About Feet")  # matches: feet (1), foot (phonetic)
    make_dir("About Feet/Best Looking Sole")  # matches: sole (1)
    make_file(
        "About Feet/Best Looking Sole/best_looking_foot_sole__feet.png"
    )  # matches: feet (2), foot (1), sole (2)
    make_file("About Feet/B&W Stylized Shape/foot_study_003.png")  # matches: foot (2)
    make_file("3D-to-reGEN-to-VID/var_01/var/unname2d_FOOT_FIX.png")  # matches: foot (3)
    make_dir("Last Tracing, Foot Switch")  # matches: foot (4)
    make_dir("Simple Foot Render")  # matches: foot (5)
    make_dir("About Feet/Impecable Soles")  # matches: sole (3)
    make_dir("DVa Raised Sole")  # matches: sole (4)
    make_file("Simple Foot Render/sole_01.kra")  # matches: sole (5)
    make_file("Simple Foot Render/sole_02.kra")  # matches: sole (6)
    make_file("Simple Foot Render/sole_03.kra")  # matches: sole (7)
    make_file("Simple Foot Render/sole_04.kra")  # matches: sole (8)
    make_file("Simple Foot Render/sole_05.kra")  # matches: sole (9)
    make_dir("Sitting on a Bench, Soles Peaking")  # matches: sole (10)
    make_file("Sitting on a Bench, Soles Peaking/Soles Peeking.glb")  # matches: sole (11)
    make_file("Sitting on a Bench, Soles Peaking/soles_peeking.png")  # matches: sole (12)

    # Verify query "feet" finds exactly 2 matches
    res_feet = engine.find_path("feet", tmp_path, no_index=True, min_confidence=0.3)
    assert res_feet.status == "success"
    # 1 main match + 1 near miss (total 2)
    all_feet_matches = [res_feet.match.path] + [nm.path for nm in res_feet.near_misses]
    assert len(all_feet_matches) == 2

    # Verify query "foot" finds exactly 5 matches (via H2 substring matching)
    res_foot = engine.find_path("foot", tmp_path, no_index=True, min_confidence=0.3)
    assert res_foot.status == "success"
    all_foot_matches = [res_foot.match.path] + [nm.path for nm in res_foot.near_misses]
    assert len(all_foot_matches) == 5

    # Verify query "sole" finds exactly 12 matches (via H2 substring matching)
    res_sole = engine.find_path("sole", tmp_path, no_index=True, min_confidence=0.3)
    assert res_sole.status == "success"
    all_sole_matches = [res_sole.match.path] + [nm.path for nm in res_sole.near_misses]
    assert len(all_sole_matches) == 12


def test_category_query_multi_match(tmp_path: Path, sample_config: dict):
    """Test that category queries like 'vids' return all matching candidates in near_misses."""
    sample_config["handlers"]["enabled"] = ["h1", "h2", "h3"]
    engine = SearchEngine(sample_config)

    # Create multiple video files
    (tmp_path / "v1.mp4").write_text("", encoding="utf-8")
    (tmp_path / "v2.mov").write_text("", encoding="utf-8")
    (tmp_path / "image.png").write_text("", encoding="utf-8")  # should not match vids

    res = engine.find_path("vids", tmp_path, no_index=True, min_confidence=0.3, top_n=5)
    assert res.status == "success"
    assert res.match is not None
    # We should have 1 main match + 1 near_miss = 2 video matches in total
    assert len(res.near_misses) == 1
    all_matched = [res.match.path] + [nm.path for nm in res.near_misses]
    assert tmp_path / "v1.mp4" in all_matched
    assert tmp_path / "v2.mov" in all_matched
    assert tmp_path / "image.png" not in all_matched


def test_exhaustive_accumulation(tmp_path: Path, sample_config: dict):
    """Test that the handler chain keeps executing until top_n is satisfied."""
    sample_config["handlers"]["enabled"] = ["h1", "h2", "h3"]
    engine = SearchEngine(sample_config)

    # Create files
    f1 = tmp_path / "SCRIPT.md"
    f1.write_text("", encoding="utf-8")
    f2 = tmp_path / "script_extra.md"
    f2.write_text("", encoding="utf-8")
    f3 = tmp_path / "extra_script.md"
    f3.write_text("", encoding="utf-8")

    # If top_n = 1, it should stop at H1
    res_1 = engine.find_path("SCRIPT.md", tmp_path, no_index=True, top_n=1)
    assert res_1.status == "success"
    all_matched_1 = [res_1.match.path] + [nm.path for nm in res_1.near_misses]
    assert len(all_matched_1) == 1
    assert f1 in all_matched_1

    # If top_n = 3, it should fall through H1, H2, and H3 to collect all 3 matches
    res_3 = engine.find_path("SCRIPT.md", tmp_path, no_index=True, top_n=3)
    assert res_3.status == "success"
    all_matched_3 = [res_3.match.path] + [nm.path for nm in res_3.near_misses]
    assert len(all_matched_3) == 3
    assert f1 in all_matched_3
    assert f2 in all_matched_3
    assert f3 in all_matched_3
