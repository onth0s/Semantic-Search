"""Regression tests ensuring 'sempath get N', bare 'sempath N', and 'sempath list'
are 100% synchronized with the visual order displayed by 'sempath find'.
"""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from sempath.cli import cli
from sempath.utils.history import get_history_path


@pytest.fixture(autouse=True)
def _clean_history():
    """Ensure each test starts with an isolated/clean history file."""
    history_path = get_history_path()
    if history_path.exists():
        history_path.unlink()
    yield
    if history_path.exists():
        history_path.unlink()


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(env={"COLUMNS": "500"})


def _extract_find_numbered_paths(output: str) -> dict[int, str]:
    """Parse printed lines from 'sempath find' output into {rank: normalized_path_str}."""
    numbered: dict[int, str] = {}
    primary_match = re.search(r"Found match(?:\s*\([^)]*\))?:\s*([^\s\(\[\r\n]+)", output)
    if primary_match:
        numbered[1] = str(Path(primary_match.group(1).strip()).resolve())

    for m in re.finditer(r"(?:^|\s)(\d+)\.\s*(?:\[[^\]]*\])?\s*([^\s\(\[\r\n]+)", output):
        rank = int(m.group(1))
        val = m.group(2).strip()
        if val.startswith(("C:", "/", "\\")) or Path(val).exists():
            numbered[rank] = str(Path(val).resolve())
    return numbered


class TestHistoryIndexSync:
    """Tests verifying display-order to history-rank 1-to-1 parity."""

    def test_multi_folder_grouped_order_sync(self, runner: CliRunner, tmp_path: Path):
        """Verify multi-folder grouping reorders candidates but get N matches display N."""
        dir_a = tmp_path / "AlphaFolder"
        dir_a.mkdir()
        dir_b = tmp_path / "BetaFolder"
        dir_b.mkdir()
        dir_gen = tmp_path / "GenericFolder"
        dir_gen.mkdir()

        f_primary = tmp_path / "alpha_item_top.txt"
        f_primary.write_text("top match", encoding="utf-8")

        f_a1 = dir_a / "alpha_item_one.txt"
        f_a1.write_text("a1", encoding="utf-8")

        f_a2 = dir_a / "alpha_item_two.txt"
        f_a2.write_text("a2", encoding="utf-8")

        f_b1 = dir_b / "alpha_item_beta_one.txt"
        f_b1.write_text("b1", encoding="utf-8")

        f_b2 = dir_b / "alpha_item_beta_two.txt"
        f_b2.write_text("b2", encoding="utf-8")

        f_gen = dir_gen / "test.txt"
        f_gen.write_text("generic test", encoding="utf-8")

        res = runner.invoke(
            cli,
            [
                "find",
                "alpha_item",
                str(tmp_path),
                "--top-n",
                "6",
                "--no-index",
                "--non-interactive",
            ],
        )
        assert res.exit_code == 0, f"find failed: {res.output}"

        displayed_paths = _extract_find_numbered_paths(res.output)
        assert len(displayed_paths) >= 4, f"Expected multiple matches: {res.output}"

        # Verify sempath list shows the exact same numbered paths
        res_list = runner.invoke(cli, ["list"])
        assert res_list.exit_code == 0
        list_paths = _extract_find_numbered_paths(res_list.output)
        for rank, path_str in displayed_paths.items():
            assert rank in list_paths, f"Rank {rank} missing from list: {res_list.output}"
            assert list_paths[rank] == path_str, (
                f"Rank {rank} mismatch: find={path_str} vs list={list_paths[rank]}"
            )

        # Verify sempath get N and bare sempath N for EVERY rank
        for rank, expected_path in displayed_paths.items():
            # sempath get N
            res_get = runner.invoke(cli, ["get", str(rank)])
            assert res_get.exit_code == 0, f"get {rank} failed: {res_get.output}"
            assert expected_path in res_get.output, (
                f"'sempath get {rank}' did not return expected path {expected_path}. "
                f"Output: {res_get.output}"
            )

            # bare sempath N
            res_bare = runner.invoke(cli, [str(rank)])
            assert res_bare.exit_code == 0, f"bare '{rank}' failed: {res_bare.output}"
            assert str(Path(res_bare.output.strip()).resolve()) == expected_path, (
                f"bare 'sempath {rank}' output {res_bare.output.strip()} != {expected_path}"
            )

    def test_generic_stem_demotion_sync(self, runner: CliRunner, tmp_path: Path):
        """Verify that when generic stems are demoted, get N matches the updated display order."""
        f_generic = tmp_path / "temp.txt"
        f_generic.write_text("temp", encoding="utf-8")

        sub = tmp_path / "MyProject"
        sub.mkdir()
        f_real = sub / "temp_report.txt"
        f_real.write_text("report", encoding="utf-8")

        res = runner.invoke(
            cli,
            ["find", "temp", str(tmp_path), "--top-n", "3", "--no-index", "--non-interactive"],
        )
        assert res.exit_code == 0

        displayed_paths = _extract_find_numbered_paths(res.output)
        assert 1 in displayed_paths
        assert 2 in displayed_paths

        # Item 1 should be the non-generic file (promoted)
        assert displayed_paths[1] == str(f_real.resolve())
        # Item 2 should be the generic file (demoted)
        assert displayed_paths[2] == str(f_generic.resolve())

        # Verify get 1 returns non-generic
        res_get1 = runner.invoke(cli, ["get", "1"])
        assert res_get1.exit_code == 0
        assert str(f_real.resolve()) in res_get1.output

        # Verify get 2 returns generic
        res_get2 = runner.invoke(cli, ["get", "2"])
        assert res_get2.exit_code == 0
        assert str(f_generic.resolve()) in res_get2.output

        # Verify bare 1 and 2
        res_bare1 = runner.invoke(cli, ["1"])
        assert str(Path(res_bare1.output.strip()).resolve()) == str(f_real.resolve())
        res_bare2 = runner.invoke(cli, ["2"])
        assert str(Path(res_bare2.output.strip()).resolve()) == str(f_generic.resolve())

    def test_content_and_path_partition_sync(self, runner: CliRunner, tmp_path: Path):
        """Verify multiple content matches across folders are indexed identically in get."""
        docs = tmp_path / "docs"
        docs.mkdir()
        src = tmp_path / "src"
        src.mkdir()

        f_content1 = docs / "guide.txt"
        f_content1.write_text("This contains SPECIAL_KEYWORD inside text.", encoding="utf-8")

        f_content2 = src / "special_reference.py"
        f_content2.write_text("# SPECIAL_KEYWORD implementation", encoding="utf-8")

        res = runner.invoke(
            cli,
            [
                "find",
                "SPECIAL_KEYWORD",
                str(tmp_path),
                "--read-content",
                "--top-n",
                "5",
                "--no-index",
                "--non-interactive",
            ],
        )
        assert res.exit_code == 0

        displayed_paths = _extract_find_numbered_paths(res.output)
        assert len(displayed_paths) >= 2

        for rank, expected_path in displayed_paths.items():
            res_get = runner.invoke(cli, ["get", str(rank)])
            assert res_get.exit_code == 0
            assert expected_path in res_get.output
