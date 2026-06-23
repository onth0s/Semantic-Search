# Codebase Audit & Sequential Refactoring Strategy

Full audit of the `sempath` codebase, identifying structural issues, code smells, duplication, and architectural debt — with a phased refactoring plan designed to execute sequentially while keeping tests green at every step.

---

## Audit Summary

### Codebase Metrics

| Area | Files | Total Lines | Largest File |
|---|---|---|---|
| Core (`src/`) | 12 | ~1,930 | [cli.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/cli.py) (555 lines) |
| Handlers (`src/handlers/`) | 11 | ~1,160 | [h6_alias.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h6_alias.py) (263 lines) |
| Utilities (`src/utils/`) | 6 | ~570 | [mft_reader.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/utils/mft_reader.py) (253 lines) |
| Tests (`tests/`) | 20 | ~3,800 | [test_engine_and_handlers.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/tests/test_engine_and_handlers.py) (13,046 bytes) |
| **Total** | **49** | **~7,460** | |

---

## Findings

### F1 — Triplicated Category Data (Critical DRY Violation)

The full category keyword/extension mapping is duplicated **three times** in almost identical form:

1. [config.yaml](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/config.yaml) (L28-50) — the bundled YAML file
2. [config.py `DEFAULT_CONFIG`](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/config.py#L52-L216) — inline Python dict (~165 lines)
3. [heuristics.py `DEFAULT_CATEGORIES`](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py#L13-L174) — inline Python dict (~162 lines)

This means any category addition (keyword, extension) must be replicated in three places or risk drift. The `heuristics.py` copy only exists as a fallback when `config` is unavailable, but that path is already handled by the function itself calling `load_config()`.

> [!CAUTION]
> This is the largest source of raw line bloat in the codebase (~330 lines of pure duplication). It makes category maintenance error-prone.

---

### F2 — Duplicated "Category Not Found" Message Builder in `engine.py`

The same category-to-message mapping block is copied verbatim **twice** inside [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py):

- Lines 164–189 (early empty-candidates path)
- Lines 284–308 (post-chain fallback path)

Both blocks do the exact same `if "audio" in matched_cats ... elif "image" ...` chain to produce a human-readable failure message.

---

### F3 — `match()` / `match_all()` Duplication in Handlers H1–H5

Each of H1, H2, H3, H4, and H5 implements both `match()` and `match_all()` with **near-identical loop bodies**. The only difference is:

- `match()` collects matches and returns a single best result.
- `match_all()` collects matches and returns the full list.

This pattern repeats across 5 handlers, with each pair sharing ~70-90% of their loop logic. Examples:

| Handler | `match()` lines | `match_all()` lines | Shared logic % |
|---|---|---|---|
| [h1_exact.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h1_exact.py) | 22–61 | 63–97 | ~85% |
| [h2_case_insensitive.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h2_case_insensitive.py) | 22–67 | 69–123 | ~75% |
| [h4_fuzzy.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h4_fuzzy.py) | 26–70 | 72–106 | ~80% |
| [h5_phonetic.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h5_phonetic.py) | 42–81 | 83–117 | ~80% |

---

### F4 — Scattered Verbose / Click Context Access Pattern

The pattern of grabbing `click.get_current_context(silent=True)` → checking `ctx.obj.get("verbose")` → conditionally importing `err_console` is repeated **~15+ times** across:

- [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py) (lines 67, 84, 113, 131, 157)
- [base.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/base.py) (lines 49-74)
- [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py) (lines 259-269, 312-315)
- [h6_alias.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h6_alias.py) (lines 164-167, 217-222)
- [h7_embedding.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h7_embedding.py) (lines 35-38)
- [h8_llm.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h8_llm.py) (lines 41-42)
- [h9_interactive.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h9_interactive.py) (lines 31-32)

---

### F5 — Redundant `import re as regex` in `heuristics.py`

[heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py#L373) imports `re` at the top (line 9) then does `import re as regex` inside `extract_heuristics()` (line 373). This is confusing — two different names for the same module within one file.

---

### F6 — Deferred/Inline Imports Sprinkled Throughout

Many modules use **deferred imports inside functions** where they could be top-level:

| File | Deferred import | Location |
|---|---|---|
| [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py) | `from src.pipeline import ...` | L141 (inside `find_path()`) |
| [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py) | `from src.directory_matcher import ...` | L194 |
| [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py) | `import re` | L52 |
| [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py) | `from src.handlers.h6_alias import AliasHandler` | L54 |
| [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py) | `import click` | L259, L312 |
| [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py) | `import jellyfish`, `from rapidfuzz import fuzz` | L380-381 |
| [h1_exact.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h1_exact.py) | `import fnmatch` | L31, L72 |
| Most handlers | `import fnmatch`, `import jellyfish`, `from rapidfuzz import fuzz` | various |

Some are intentional (H7's lazy `sentence-transformers`, H8's `urllib`), but many are just accidental — e.g., `fnmatch` and `re` are stdlib modules with no import cost and should be top-level.

---

### F7 — `engine.py` `find_path()` is a 285-line God Method

[SearchEngine.find_path()](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py#L31-L315) handles:

1. Alias fast-resolve routing (L50-88)
2. Candidate gathering (L91-110)
3. Heuristic extraction and merging (L118-138)
4. Pipeline filtering (L141-161)
5. Category empty-result message generation (L164-189)
6. Directory content matching (L193-215)
7. Sort + explicit flags bypass (L218-234)
8. Chain execution (L237-257)
9. Near-miss collection (L260-276)
10. Final category failure message generation (L284-314)

This violates Single Responsibility — it's the orchestrator but also contains inline logic for routing, message generation, and flag merging.

---

### F8 — `cli.py` Verbose Flag Resolution is Tangled

The `verbose` flag is determined in [cli.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/cli.py#L173) as `verbose or config.get("verbose", False)` and then passed both into `ctx.obj` and as an argument to `engine.find_path()`. The engine also receives it, but multiple handlers also independently read from `ctx.obj["verbose"]`. This dual source of truth for verbosity creates fragility.

---

### F9 — `heuristics.py` `extract_heuristics()` Returns a Raw Dict

The function returns a plain `dict` with string keys (`"clean_query"`, `"extensions"`, etc.), requiring callers to use magic string keys and `.get()` with defaults. This should be a proper dataclass or `NamedTuple` for type safety.

---

### F10 — `_normalize_tokens_with_wildcards` is a Private Function Imported Cross-Module

[`_normalize_tokens_with_wildcards`](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h3_token_normalized.py#L18) in `h3_token_normalized.py` is prefixed with `_` (conventionally private), but is imported by:
- [directory_matcher.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/directory_matcher.py#L24) (line 24)
- [directory_matcher.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/directory_matcher.py#L113) (line 113)

This cross-module import of a private function is an encapsulation leak. The function should either be made public or moved to a shared utility.

---

### F11 — `scoring.py` Utilities Are Unused in Production Code

[`clamp_confidence()`](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/utils/scoring.py#L6) and [`format_size()`](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/utils/scoring.py#L21) are defined but **never called** from any production module (only tested in `test_utils.py`). They represent dead utility code or code written in anticipation of future use.

---

### F12 — Package Name vs Directory Name Mismatch

The package is `src/` (as configured in `pyproject.toml`: `packages = ["src"]`), but the project name is `sempath`. This means all internal imports use `from src.xxx` rather than `from sempath.xxx`, which is unusual and will cause confusion if the project is ever installed alongside other packages that also use a generic `src` package name.

> [!IMPORTANT]
> This is an **architectural naming issue** — the source package should be named `sempath/` to match the project identity. However, this is a large rename that touches every import in the codebase (60+ import statements) and the build config, so it needs to be handled carefully and is the riskiest refactor.

---

### F13 — Stale/Orphan Files at Root

The root directory contains files that appear to be development artifacts and not part of the project:

- `findhelp.txt` (2.49 KB)
- `hf.txt` (22.37 KB)
- `hf_fixed.txt` (22.37 KB)
- `sempath.spec` (871 bytes — PyInstaller spec, likely stale)
- `misc/TREE_EXAMPLE.txt` (25.82 KB)
- `build/` and `dist/` directories (build artifacts)

---

### F14 — `conftest.py` Mutates Global `os.environ["APPDATA"]` at Import Time

[conftest.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/tests/conftest.py#L8-L9) sets `os.environ["APPDATA"]` at module scope (line 9), which affects every test and potentially leaks into the host environment for the process lifetime. This is fragile — it should use `monkeypatch` or a fixture-scoped pattern.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Package rename `src/` → `sempath/`?**
> This is the most impactful refactor (F12). It would change every internal import from `from src.xxx` to `from sempath.xxx` (60+ locations). This is the correct long-term move, but it's risky and touches everything. **Do you want this included in the plan, or deferred?**

> [!IMPORTANT]
> **Q2 — Stale root files cleanup?**
> Should `findhelp.txt`, `hf.txt`, `hf_fixed.txt`, `sempath.spec`, `misc/TREE_EXAMPLE.txt`, `build/`, and `dist/` be deleted or preserved? (Per project rules, I won't restore deleted files, so I want confirmation before cleaning.)

> [!IMPORTANT]
> **Q3 — `scoring.py` dead code?**
> `clamp_confidence()` and `format_size()` are defined but never called from production code. Should they be kept (anticipated future use) or removed?

---

## Proposed Changes (Sequential Phases)

Each phase is designed to be independently committable with all 130 tests passing at the end.

---

### Phase 1 — Eliminate Category Data Triplication (F1)

**Goal**: Single source of truth for category keywords/extensions.

#### [MODIFY] [config.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/config.py)
- Keep `DEFAULT_CONFIG` as the single Python-level source of truth (it already is the canonical fallback).
- No changes needed here — this is already the primary.

#### [MODIFY] [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py)
- **Delete** the 162-line `DEFAULT_CATEGORIES` constant (lines 13-174).
- Change `extract_heuristics()` to import and use `DEFAULT_CONFIG` from `config.py` as the fallback instead of its own copy.
- Net: **~160 lines removed**.

---

### Phase 2 — Extract Category Failure Message Builder (F2)

**Goal**: DRY the duplicated message-building logic in `engine.py`.

#### [MODIFY] [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py)
- Extract a helper `_build_category_failure_message(heuristics: dict) -> str` function.
- Replace both inline blocks (lines 164-189 and 284-308) with calls to this helper.
- Net: **~30 lines removed**.

---

### Phase 3 — DRY Handler `match()` / `match_all()` Duplication (F3)

**Goal**: Each handler's `match()` should delegate to `match_all()` + pick best, eliminating the duplicated loop.

#### [MODIFY] [h1_exact.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h1_exact.py)
- Rewrite `match()` to call `self.match_all(query, candidates)` and return the best result (shortest depth).
- Delete the duplicated loop body from `match()`.

#### [MODIFY] [h2_case_insensitive.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h2_case_insensitive.py)
- Same pattern: `match()` delegates to `match_all()` + picks best.

#### [MODIFY] [h4_fuzzy.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h4_fuzzy.py)
- Same pattern.

#### [MODIFY] [h5_phonetic.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h5_phonetic.py)
- Same pattern.

> [!NOTE]
> H3 (`TokenNormalizedHandler`) has extra token-subset logic in `match_all()` not present in `match()`, so it needs slightly different treatment — `match()` would call `match_all()` with an additional filter to only consider `confidence == 0.90` results (exact token set matches), excluding the 0.90 subset fallback that `match_all` adds.

#### [MODIFY] [h3_token_normalized.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h3_token_normalized.py)
- Rewrite `match()` to call `match_all()` and pick the best result among those that were exact token-set matches.

**Net across Phase 3: ~120 lines removed.**

---

### Phase 4 — Extract Verbose Logging Helper (F4)

**Goal**: Replace 15+ scattered `click.get_current_context → obj.get("verbose") → err_console.print` patterns with a single utility.

#### [NEW] [src/utils/logging.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/utils/logging.py)
- Create `verbose_log(message: str) -> None` that encapsulates the Click context check + Rich stderr print.
- Create `is_verbose() -> bool` for conditional blocks.

#### [MODIFY] Multiple files
- Replace scattered verbose patterns in `engine.py`, `base.py`, `heuristics.py`, `h6_alias.py`, `h7_embedding.py`, `h8_llm.py`, `h9_interactive.py` with calls to `verbose_log()` / `is_verbose()`.

---

### Phase 5 — Promote `_normalize_tokens_with_wildcards` to Shared Utility (F10)

**Goal**: Fix the cross-module private function import.

#### [MODIFY] [src/utils/tokenize.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/utils/tokenize.py)
- Move `_normalize_tokens_with_wildcards` here, renamed to `normalize_tokens_with_wildcards` (public).

#### [MODIFY] [h3_token_normalized.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/handlers/h3_token_normalized.py)
- Import from `src.utils.tokenize` instead of defining locally. Keep backward-compatible `_normalize_tokens_with_wildcards = normalize_tokens_with_wildcards` alias for any external consumers.

#### [MODIFY] [directory_matcher.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/directory_matcher.py)
- Import from `src.utils.tokenize` instead of `src.handlers.h3_token_normalized`.

---

### Phase 6 — Hoist Deferred Imports to Top-Level (F5, F6)

**Goal**: Clean up unnecessarily deferred imports for stdlib and always-available project modules.

#### [MODIFY] [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py)
- Move `import re`, `from src.pipeline import ...`, `from src.directory_matcher import ...` to top-level imports.
- Keep `from src.handlers.h6_alias import AliasHandler` deferred (it's conditionally used based on enabled handlers).

#### [MODIFY] [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py)
- Remove `import re as regex` (line 373) — use the already-imported `re` module.
- Move `import jellyfish`, `from rapidfuzz import fuzz`, `import click` to top-level.

#### [MODIFY] Handlers (h1-h5)
- Move `import fnmatch` to top-level in each handler file.
- Move `import jellyfish`, `from rapidfuzz import fuzz` to top-level where applicable.

---

### Phase 7 — Introduce `HeuristicsResult` Dataclass (F9)

**Goal**: Replace the raw `dict` return from `extract_heuristics()` with a typed dataclass.

#### [MODIFY] [models.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/models.py)
- Add `HeuristicsResult` dataclass with typed fields: `clean_query`, `modified_within_seconds`, `extensions`, `latest`, `largest`, `directory_only`, `file_only`, `matched_categories`, `matched_category_keywords`.

#### [MODIFY] [heuristics.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/heuristics.py)
- Return `HeuristicsResult(...)` instead of a raw dict.

#### [MODIFY] [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py)
- Update `find_path()` to use attribute access (`heuristics.clean_query`) instead of dict keys (`heuristics["clean_query"]`).

#### [MODIFY] Tests referencing heuristics dicts
- Update `test_heuristics.py` assertions to use attribute access.

---

### Phase 8 — Decompose `find_path()` God Method (F7)

**Goal**: Break the 285-line method into focused sub-methods.

#### [MODIFY] [engine.py](file:///c:/Users/Leonardo/001/00__DEV/Semantic%20Search/src/engine.py)
- Extract `_try_alias_routing(query, search_root, verbose) -> tuple[str, Path] | SearchResult | None`
- Extract `_gather_candidates(search_root, depth, exclude_patterns, no_index, use_index, verbose) -> list[Path]`
- Extract `_apply_filters(candidates, heuristics, ext, latest, largest) -> list[Path]`
- Extract `_collect_near_misses(chain, clean_query, candidates) -> list[MatchResult]`
- Reduce `find_path()` to a linear orchestrator calling these ~5 sub-methods.

---

## Verification Plan

### Automated Tests
After **each phase**, run:
```powershell
py -3.13 -m pytest
py -3.13 -m ruff check --fix
py -3.13 -m ruff format
```

All 130 tests must remain green throughout. No behavioral changes — only structural.

### Manual Verification
- `sempath find "desktop/main" .` → should still resolve correctly.
- `sempath find "dl" C:\Users\Leonardo` → should still resolve to Downloads.
- `sempath --help-full` → should still render the full help tree.
