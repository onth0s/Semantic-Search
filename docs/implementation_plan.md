# Fix: `--verbose` Phase Instrumentation

## Problem

The engine executes up to 5 distinct work phases when searching. `--verbose` shows handler-level detail *within* each phase, but **never announces which phase is running**. The result is a wall of identical `Evaluating handler hN on X candidates...` blocks with zero context — indistinguishable whether you're watching the main chain, a name_query retry, an early directory fallback, a post-failure directory fallback, or near-miss collection.

This makes the output look like error looping. It is not. The phases are intentional programmatic fallbacks.

---

## Full Phase Audit

| # | Phase | Trigger | Verbose today |
|---|---|---|---|
| 3b | **Early directory content match** | `exts_final` or `file_only` is set | ❌ No label — `_match_dir_name()` internal `chain.handle()` calls leak unlabeled handler output |
| 6 | **Main chain** | Always | ✅ Per-handler lines shown, but no phase banner |
| 7 | **name_query secondary chain** | `name_query != clean_query` | ❌ No label — output identical to main chain |
| fallback | **Fallback directory content match** | After main chain finds nothing | ❌ No label — same handler output, no indication it's a fallback |
| near-miss | **Near-miss collection** (`collect_all_matches`) | After fallback dir match fails | ❌ Completely invisible — `match_all()` has no logging at all |

---

## Proposed Changes

---

### `sempath/utils/logging.py`

#### [MODIFY] [logging.py](file:///C:/Users/Leonardo/001/00__DEV/Semantic%20Search/sempath/utils/logging.py)

Add a `suppress_verbose()` context manager using `contextvars.ContextVar`:

```python
from contextlib import contextmanager
from contextvars import ContextVar

_verbose_suppressed: ContextVar[bool] = ContextVar("_verbose_suppressed", default=False)

@contextmanager
def suppress_verbose():
    token = _verbose_suppressed.set(True)
    try:
        yield
    finally:
        _verbose_suppressed.reset(token)

def verbose_log(msg: str) -> None:
    if _verbose_suppressed.get():
        return
    # ... existing implementation unchanged ...
```

---

### `sempath/handlers/base.py`

#### [MODIFY] [base.py](file:///C:/Users/Leonardo/001/00__DEV/Semantic%20Search/sempath/handlers/base.py)

Add verbose logging to `collect_all_matches()` so the near-miss scan is no longer invisible:

```python
def collect_all_matches(self, query, candidates, context=None):
    from sempath.utils.logging import verbose_log
    verbose_log(
        f"[dim]  [near-miss scan] Evaluating handler [bold cyan]{self.name}[/] "
        f"on {len(candidates)} candidates...[/]"
    )
    results = self.match_all(query, candidates, context=context)
    if self.next_handler is not None:
        sub_results = self.next_handler.collect_all_matches(query, candidates, context=context)
        results = merge_matches(results, sub_results)
    return results
```

---

### `sempath/directory_matcher.py`

#### [MODIFY] [directory_matcher.py](file:///C:/Users/Leonardo/001/00__DEV/Semantic%20Search/sempath/directory_matcher.py)

Wrap the internal `chain.handle()` call in `suppress_verbose()` so `_match_dir_name()` token evaluations don't leak unlabeled handler output:

```python
from sempath.utils.logging import suppress_verbose

for q_tok in q_tokens:
    with suppress_verbose():
        matches = chain.handle(q_tok, synthetic_candidates)
    if not any(m.confidence >= 0.5 for m in matches):
        return False
```

---

### `sempath/engine.py`

#### [MODIFY] [engine.py](file:///C:/Users/Leonardo/001/00__DEV/Semantic%20Search/sempath/engine.py)

Add a phase-entry `verbose_log` banner before every distinct work phase. No logic changes — instrumentation only.

**Step 3b — Early directory content match:**
```python
# Before _try_directory_content_match() call
verbose_log("[dim]Phase: early directory content match (query has extension/file-only intent)...[/]")
```

**Step 6 — Main chain:**
```python
# Before _execute_chain() call
verbose_log(f"[dim]Phase: main handler chain on {len(filtered_candidates)} candidates...[/]")
```

**Step 7 — name_query secondary chain:**
```python
# Before name_chain.handle() call
verbose_log(f"[dim]Phase: name_query secondary chain (name_query='{heuristics.name_query}')...[/]")
```

**Fallback directory content match:**
```python
# Before fallback _try_directory_content_match() call
verbose_log("[dim]Phase: fallback directory content match...[/]")
```

**Near-miss collection:**
```python
# Before collect_all_matches() call
verbose_log(f"[dim]Phase: near-miss collection (re-scanning all handlers)...[/]")
```

---

## What the output will look like after the fix

```
Heuristics extracted: clean_query='ogp_dffdf1ee.png', extensions=[], age_limit=None
Gathered 251 candidates from scan/index...
Remaining candidates after applying filters: 251
Phase: main handler chain on 251 candidates...
  Evaluating handler h1_exact on 251 candidates...
  ✗ Handler h1_exact returned no match.
  ...
  ✗ Handler h6_alias returned no match.
Phase: fallback directory content match...
Phase: near-miss collection (re-scanning all handlers)...
  [near-miss scan] Evaluating handler h1_exact on 251 candidates...
  ...
❌ Failed: No image files found!
```

Every block of handler output is now preceded by a label explaining exactly what phase triggered it and why.

---

## Verification Plan

### Automated Tests
```
py -3.13 -m pytest tests/ -v
```

### Manual Verification

1. `sf ogp_dffdf1ee.png . --h1-6 --verbose` → each group of handler evaluations preceded by a phase label, no unlabeled repeating blocks.
2. `sf ogp_dffdf1ee.png . --h1-6 --verbose --read-content` → same phase labels, still finds `manifest.yaml` correctly.
3. `sf somequery . --verbose` on a query that triggers early dir match → phase 3b label appears, followed by main chain label — clearly distinct.
