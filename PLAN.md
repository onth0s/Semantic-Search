# semantic-search — PLAN

## Vision

A Python CLI tool that lets LLMs (and humans) find filesystem paths by vague, colloquial, or semantically fuzzy descriptions — without needing to know the exact name, casing, or spelling.

**Examples:**
- `"desktop/main"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"the main dir on dsktp"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"Principal"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"important folder"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"dl"` → `C:\Users\Leonardo\Downloads`

---

## Architecture: Handler Pattern (Chain of Responsibility)

Each matching strategy is an independent **Handler** with a uniform interface. Handlers are composed into an ordered chain. An LLM (or CLI user) invokes the chain: each handler either returns a match with confidence, or passes to the next.

```
User Query
   │
   ▼
┌─────────────────┐
│  Router         │  ← parses query, extracts path segments & keywords
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Handler 1       │  Exact Match
│ (fast, cheap)   │  ──→ match? → return
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 2       │  Case-Insensitive Match
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 3       │  Token-Normalized Match (split, sort, compare)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 4       │  Fuzzy String / Edit Distance
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 5       │  Phonetic Match (Soundex, Metaphone)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 6       │  Alias / Synonym Expansion
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 7       │  Embedding Semantic Match
│ (slow, heavy)   │  (sentence-transformers, cosine similarity)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 8       │  LLM Match (ask external LLM to interpret)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 9       │  Interactive Fallback (ask user)
│                  │  "Did you mean __MAIN?"
└─────────────────┘
```

---

## Handler Interface

```python
class MatchResult(NamedTuple):
    path: Path
    confidence: float   # 0.0–1.0
    handler: str        # name of handler that matched

class BaseHandler(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.next_handler: BaseHandler | None = None

    def set_next(self, handler: BaseHandler) -> BaseHandler:
        self.next_handler = handler
        return handler

    @abstractmethod
    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        ...

    def handle(self, query: str, candidates: list[Path]) -> MatchResult | None:
        result = self.match(query, candidates)
        if result is not None:
            return result
        if self.next_handler is not None:
            return self.next_handler.handle(query, candidates)
        return None
```

---

## Handlers (in priority order)

### H1 – Exact Match
- Direct `==` comparison of query token → candidate basename.
- Confidence: `1.0`

### H2 – Case-Insensitive Match
- `lower()` comparison.
- Confidence: `0.95`

### H3 – Token-Normalized Match
- Strip non-alphanumeric chars, split into tokens, sort, compare unordered sets.
- `"desktop/main"` → tokens `{desktop, main}` → matches dir named `__MAIN` inside `Desktop`.
- Confidence: `0.9` (penalised slightly for normalization)

### H4 – Fuzzy String / Edit Distance
- Levenshtein / Damerau-Levenshtein ratio (via `rapidfuzz` or `thefuzz`).
- Accept matches above configurable threshold (e.g. `≥75`).
- `"dsktp"` → `Desktop` (similarity ~80%).
- `"principl"` → `Principal` (but ideally catches `__MAIN` too via synonym expansion).
- Confidence: `ratio * 1.0`

### H5 – Phonetic Match
- Encode tokens with Soundex/Metaphone (via `phonetics` or custom).
- Compare phonetic codes of query vs candidate.
- Catches homophones: `"main"` vs `"mane"`, `"there"` vs `"their"`.
- Confidence: `0.75`

### H6 – Alias / Synonym Expansion
- Configurable dictionary + automated synonym generation.
- Built-in defaults: `"main" → ["__MAIN", "principal", "important", "primary", "master"]`
- User-customisable via config file.
- Confidence: `0.7` (broadening reduces precision)

### H7 – Embedding Semantic Match
- Uses `sentence-transformers` (lightweight model like `all-MiniLM-L6-v2`) to embed query and each candidate basename.
- Cosine similarity scoring.
- Matches `"important folder"` → `__MAIN`.
- First invocation loads model; subsequent use is cached.
- Confidence: `cosine_sim * 1.0`
- Can be disabled for resource-constrained environments.

### H8 – LLM Match
- Sends query + candidate list (or directory structure) to an external LLM (OpenAI, Claude, etc.).
- LLM decides which path best fits the semantic intent.
- Useful for complex relational queries: `"the folder where I keep my downloads from work"`.
- Requires API key configuration.
- Confidence: `LLM-provided score or 0.6` (depends on model quality)

### H9 – Interactive Fallback
- Presents top N ambiguous candidates to user.
- `"Did you mean '__MAIN' (score 0.85) or 'Main' (score 0.80)?"`
- Accepts keyboard selection or typed response.
- Confidence: `1.0` (user confirmed)
- Can be suppressed (flag `--non-interactive`) for automated LLM use.

---

## Indexing

### On-the-Fly (default)
- Recursively scans directory (from root or `cwd`) on every invocation.
- Respects `.gitignore`, hidden dirs (configurable).
- Good for one-off queries or small directory trees.
- Accepts `--depth` limit.

### Persistent Index
- Pre-built index stored as JSON + optional embedding cache (`faiss` or numpy).
- Commands:
  - `semantic-search index create <path>` — build index
  - `semantic-search index update <path>` — incremental update
  - `semantic-search index list`
- Index stores for each path:
  - Full path, basename, parent dirs
  - Tokens (normalized)
  - Soundex/Metaphone codes
  - Embedding vector (if H7 enabled)
  - Custom aliases
- Auto-detects staleness via mtime checks.

---

## CLI Interface

```
semantic search [OPTIONS] <query> [path]
semantic index  (create|update|list|remove) [path]
semantic alias  (add|list|remove) <alias> <target>
```

### Options (for `search`)

| Flag | Default | Description |
|------|---------|-------------|
| `--root` | `cwd` | Root directory to search |
| `--depth` | `5` | Max directory depth |
| `--min-confidence` | `0.3` | Minimum score to consider |
| `--top-n` | `1` | Number of results to return |
| `--handler` | all | Run only specific handler(s) |
| `--non-interactive` | false | Skip interactive fallback |
| `--no-index` | false | Force on-the-fly even if index exists |
| `--json` | false | JSON output (for LLM consumption) |
| `--verbose` | false | Show handler-by-handler trace |

### Output (JSON mode)

```json
{
  "query": "desktop/main",
  "results": [
    {
      "path": "C:\\Users\\Leonardo\\Desktop\\__MAIN",
      "confidence": 1.0,
      "handler": "exact_match",
      "matched_on": "desktop → Desktop, main → __MAIN"
    }
  ],
  "total_candidates": 340,
  "handlers_tried": ["exact", "case_insensitive", "token_normalized"]
}
```

---

## Robust Fallback System

When no handler produces a match above `--min-confidence`:

1. Collect **near-misses** from all handlers (configurable threshold, e.g. `0.2`).
2. Rank by confidence.
3. If interactive: present top 3 and ask `"Did you mean X, Y, or Z?"`.
4. If non-interactive / LLM mode: return JSON with `near_misses` array and `status: "ambiguous"`.
5. The LLM can then re-query with a refined query or ask the user.

```
Status: ambiguous
Near misses:
  - C:\Users\Leonardo\Desktop\__MAIN  (0.45 — fuzzy matched "main")
  - C:\Users\Leonardo\Documents\main.py (0.4 — exact file match)
  - C:\Users\Leonardo\Desktop\Principal (0.35 — synonym "principal" → "main")
Suggestion: try "desktop/__MAIN" or "the __MAIN folder on desktop"
```

---

## Config File (`~/.config/semantic-search/config.yaml`)

```yaml
handlers:
  enabled: [h1, h2, h3, h4, h5, h6, h7, h8, h9]
  h4_threshold: 75        # fuzzy match min similarity
  h7_model: all-MiniLM-L6-v2
  h8_api_key: <env:LLM_API_KEY>
  h8_model: gpt-4o-mini
  h9_timeout: 30          # seconds to wait for user input

index:
  auto: true              # auto-create index if none exists
  store: ~/.cache/semantic-search/
  embedding_dim: 384

aliases:
  main: [__MAIN, principal, important, primary, master]
  dl: [Downloads, download]
  docs: [Documents, documentation, docs]
  tmp: [Temp, temporary, tempfiles]
  pic: [Pictures, Photos, Images, img]
```

Aliases are user-extensible. The `alias` subcommand manages them.

---

## Implementation Order

1. **CLI scaffolding** — `click` or `argparse`, project structure, `pyproject.toml`.
2. **Scanner** — on-the-fly directory walker with depth control, gitignore support.
3. **Handler base class + chain builder** — the core pattern.
4. **H1–H4** (exact, case, token-normalized, fuzzy) — fast matchers, no deps beyond stdlib + `rapidfuzz`.
5. **H5** (phonetic) — `phonetics` package.
6. **H6** (alias/synonym) — YAML config, alias subcommand.
7. **Persistent index** — JSON store, incremental updates, embedding cache.
8. **H7** (embeddings) — `sentence-transformers`, `numpy`, optional `faiss`.
9. **H8** (LLM) — `httpx` or `openai` SDK, prompt crafting.
10. **H9** (interactive fallback) — `inquirer` or `questionary`.
11. **JSON output + LLM-friendly mode** — `--json`, structured error/near-miss responses.
12. **Integration tests** — fixture directory with tricky names, query fuzzing.

---

## Directory Structure

```
semantic-search/
├── pyproject.toml
├── README.md
├── PLAN.md
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # CLI entry point
│   ├── config.py               # Config loading (YAML)
│   ├── scanner.py              # Directory walker
│   ├── index.py                # Persistent index logic
│   ├── models.py               # MatchResult, HandlerConfig, etc.
│   ├── chain.py                # Handler chain builder
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseHandler ABC
│   │   ├── h1_exact.py
│   │   ├── h2_case_insensitive.py
│   │   ├── h3_token_normalized.py
│   │   ├── h4_fuzzy.py
│   │   ├── h5_phonetic.py
│   │   ├── h6_alias.py
│   │   ├── h7_embedding.py
│   │   ├── h8_llm.py
│   │   └── h9_interactive.py
│   └── utils/
│       ├── __init__.py
│       ├── tokenize.py         # Token splitting/normalisation
│       └── scoring.py          # Confidence normalisation
├── tests/
│   ├── conftest.py
│   ├── test_scanner.py
│   ├── test_handlers.py
│   ├── test_chain.py
│   ├── test_cli.py
│   └── fixtures/
│       └── mock_fs/            # Fake directory tree for tests
└── config.yaml                 # Default config
```
