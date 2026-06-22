# semantic-search — PLAN

## Vision

A Python CLI tool that lets LLMs (and humans) find filesystem paths by vague, colloquial, or semantically fuzzy descriptions — without needing to know the exact name, casing, or spelling.

**Examples:**
- `"desktop/main"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"the main dir on dsktp"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"Principal"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"important folder"` → `C:\Users\Leonardo\Desktop\__MAIN`
- `"dl"` → `C:\Users\Leonardo\Downloads`

**Platform Target:**
- Cross-platform support is deferred for now. The MVP is built specifically for the host machine (Windows OS).

**File/Directory Size Output:**
- If outputting file or directory sizes, always format them in a human-readable format (e.g. KB, MB, GB) with exactly 2 decimal places.

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
- Sends query + candidate list to a local or external LLM (Ollama, OpenAI, etc.).
- LLM decides which path best fits the semantic intent.
- Configurable provider (e.g., `ollama` or `openai`), endpoint URL, model, and API key.
- Confidence: `LLM-provided score or 0.6`

### H9 – Interactive Fallback
- Presents top N ambiguous candidates to user.
- Accepts keyboard selection or typed response.
- **Stateful Memory Loop:** Once the user confirms a path, the query-to-path association is learned and written to `learned_aliases.yaml` in the user's config directory (e.g. `~/.config/semantic-search/` or `.semantic-search/`).
- Subsequent matching of the same or similar query is instantly resolved by the Alias handler (H6).
- Can be suppressed (flag `--non-interactive`) for automated LLM use.
- Confidence: `1.0` (user confirmed)

---

## Indexing

### On-the-Fly (default)
- Recursively scans directory (from root or `cwd`) on every invocation.
- **Sensible Directory Traversal Ignores:** Automatically bypasses potential blackholes to prevent hangs:
  - Dot directories (e.g., `.git`, `.venv`, `.idea`, `.vscode`).
  - Common build, dependency, and cache artifacts (e.g., `node_modules`, `__pycache__`, `build`, `dist`, `.mypy_cache`, `.pytest_cache`).
- **`.gitignore` Integration:** Parse and respect actual `.gitignore` files found in the traversed directories to prevent matching developer-ignored files.
- Accepts `--depth` limit (default: 5) to constrain search radius.

### Persistent Index
- Pre-built index stored as JSON + optional embedding cache (`faiss` or numpy).
- Commands:
  - `semantic-search index create [path]` — build index
  - `semantic-search index update [path]` — incremental update
  - `semantic-search index list`
  - `semantic-search index remove`
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
semantic-search find [OPTIONS] <query> [path]
semantic-search index (create|update|list|remove) [path]
semantic-search alias (add|list|remove|clear)
semantic-search export-memory <path>
semantic-search import-memory <path>
```

### Options (for `find`)

| Flag | Default | Description |
|------|---------|-------------|
| `--root` | `cwd` | Root directory to search |
| `--depth` | `5` | Max directory depth |
| `--min-confidence` | `0.3` | Minimum score to consider |
| `--top-n` | `1` | Number of results to return |
| `--non-interactive` | false | Skip interactive fallback |
| `--no-index` | false | Force on-the-fly even if index exists |
| `--json` | false | JSON output (for LLM consumption) |
| `--verbose` | false | Show handler-by-handler trace |

---

## Robust Fallback System

When no handler produces a match above `--min-confidence`:

1. Collect **near-misses** from all handlers (configurable threshold, e.g. `0.2`).
2. Rank by confidence.
3. If interactive: present top 3 and ask `"Did you mean X, Y, or Z?"`.
4. If non-interactive / LLM mode: return JSON with `near_misses` array and `status: "ambiguous"`.
5. The LLM can then re-query with a refined query or ask the user.

---

## Config File (`~/.config/semantic-search/config.yaml`)

```yaml
handlers:
  enabled: [h1, h2, h3, h4, h5, h6, h7, h8, h9]
  h4_threshold: 75        # fuzzy match min similarity
  h7_model: all-MiniLM-L6-v2
  h8_provider: ollama
  h8_model: llama3
  h8_url: http://localhost:11434/v1
  h8_api_key: ""
  h9_timeout: 30          # seconds to wait for user input

index:
  auto: true              # auto-create index if none exists
  store: ~/.cache/semantic-search/
  exclude_patterns:
    - "node_modules"
    - ".git"
    - "venv"
    - "__pycache__"

aliases:
  main: [__MAIN, principal, important, primary, master]
  dl: [Downloads, download]
  docs: [Documents, documentation, docs]
```

---

## Implementation Order

1. **Phase 1: Scaffolding, Models & Config** — `pyproject.toml`, directory structure, configuration loader.
2. **Phase 2: Scanner & Core Handlers (H1 - H4)** — Ignore list, exact, case-insensitive, token-normalized, and fuzzy (`rapidfuzz`).
3. **Phase 3: Phonetic, Config Aliases & Memory (H5 - H6)** — `jellyfish` Soundex/Metaphone, alias YAML matching, memory updates, export/import CLI commands.
4. **Phase 4: Persistent Indexing** — Pre-tokenized indices, CLI `index` subcommands.
5. **Phase 5: Heavy Matchers (H7 - H8)** — Lazy sentence-transformers, Ollama/OpenAI API LLM matching.
6. **Phase 6: Interactive Fallback, Verification & Smoke Tests** — H9 interactive prompts, feedback loop test suite.

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
