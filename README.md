# semantic-search

A Python CLI tool designed to help humans and LLM agents find filesystem paths using vague, colloquial, misspelled, or semantically fuzzy descriptions. It eliminates the need to remember exact casings, paths, or naming conventions.

---

## 🌟 Vision

- `"desktop/main"` ➔ `C:\Users\Leonardo\Desktop\__MAIN`
- `"the main dir on dsktp"` ➔ `C:\Users\Leonardo\Desktop\__MAIN`
- `"Principal"` ➔ `C:\Users\Leonardo\Desktop\__MAIN` (Synonym)
- `"important folder"` ➔ `C:\Users\Leonardo\Desktop\__MAIN` (Semantic)
- `"dl"` ➔ `C:\Users\Leonardo\Downloads` (Alias)

> [!NOTE]
> **Platform Target:** Cross-platform support is deferred for now. The MVP is built specifically for the host machine (Windows OS).
>
> **File/Directory Size Output:** If outputting file or directory sizes, always format them in a human-readable format (e.g. KB, MB, GB) with exactly 2 decimal places.

---

## 🏗️ Architecture: Handler Pattern (Chain of Responsibility)

Matching strategies are decoupled into individual **Handlers** with a uniform interface. Handlers are structured as a prioritized chain, executing from fastest/cheapest to slowest/deepest.

```
User Query
   │
   ▼
┌─────────────────┐
│  Router         │  ← Parses query & extracts candidate paths
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│ Handler 1       │  Exact Match
│ (fast, cheap)   │  ──→ Match found ➔ Return result
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 2       │  Case-Insensitive Match
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 3       │  Token-Normalized Match
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 4       │  Fuzzy String / Edit Distance (rapidfuzz)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 5       │  Phonetic Match (Soundex/Metaphone via jellyfish)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 6       │  Alias & Synonym Expansion (config + learned)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 7       │  Embedding Semantic Match (sentence-transformers)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 8       │  LLM Match (Ollama, OpenAI, or local APIs)
└──────┬──────────┘
       │ no match
       ▼
┌─────────────────┐
│ Handler 9       │  Interactive Fallback (Ask user & learn choice)
└─────────────────┘
```

---

## 🧠 Stateful Memory & Robust User Ratified Aliases

Unlike purely stateless CLI search engines, `semantic-search` remembers confirmations to build an intuitive, personalized interaction model, and treats alias matching as a robust semantic system:

1. **Learning confirmations:** When a query resolves to an interactive selection (H9) and the user confirms, that query-to-path association is saved to a persistent storage (`%APPDATA%\semantic-search\learned_aliases.yaml`).
2. **Robust User Ratified Aliases (H6):** The Alias handler doesn't just check for exact string matches:
   - **Fuzzy / Phonetic Keys:** Alias keys (e.g., `DWL` -> `Downloads`) are checked via fuzzy matching, so `dwll` resolves directly with high confidence.
   - **Regex / Wildcard Mappings:** Confirmed/configured aliases can contain regex patterns.
   - **Context / Query Splitting:** If the query includes an alias and a sub-query (e.g., `"latest pic on MAIN"`), the system extracts the alias `MAIN`, resolves it to its directory (`C:\Users\Leonardo\Desktop\__MAIN`), and searches recursively within that directory for the remaining query (`"latest pic"`), resolving files matching image extensions sorted by creation/modification time.
3. **Chronological Undo Stack:** Aliases are logged chronologically. If you make a mistake, run `semantic-search alias undo` to revert the last learned alias.
4. **Deterministic execution & Feedback Loop:** Next time a query is matched via a learned alias, it resolves instantly and displays a feedback hint:
   `[i] Matched via learned alias: 'query' -> 'path' (run 'semantic-search alias undo' to revert)`
5. **Sharing/Attaching context:** LLM agents or remote deployment bots can export and import this state.
   - `semantic-search export-memory <export_path.yaml>`
   - `semantic-search import-memory <import_path.yaml>`

---

## 💻 CLI Interface

```bash
# Search for paths
semantic-search find [OPTIONS] <QUERY> [ROOT_DIR]

# Persistent Indexing
semantic-search index (create | update | list | remove) [ROOT_DIR]

# Managed Aliases / Custom Mappings
semantic-search alias (add | list | remove | clear | undo)

# Memory Import & Export
semantic-search export-memory <FILE_PATH>
semantic-search import-memory <FILE_PATH>
```

### Search Options

| Option | Default | Description |
|---|---|---|
| `--root` | `cwd` | Root directory to begin matching/traversal. |
| `--depth` | `5` | Maximum folder depth to traverse. |
| `--min-confidence` | `0.3` | Minimum confidence score (0.0 to 1.0) to return a match. |
| `--top-n` | `1` | Number of results to return. |
| `--non-interactive` | `false` | Disable interactive fallback (H9), return JSON near-misses instead. |
| `--no-index` | `false` | Force an on-the-fly traversal scan. |
| `--json` | `false` | Output structured JSON instead of stdout (for LLM agents). |
| `--verbose` | `false` | Enable handler-by-handler execution logs. |

---

## 🛠️ Configuration (`config.yaml`)

```yaml
handlers:
  enabled: [h1, h2, h3, h4, h5, h6, h7, h8, h9]
  h4_threshold: 75
  h7_model: all-MiniLM-L6-v2
  h8_provider: ollama      # or openai, etc.
  h8_model: llama3
  h8_url: http://localhost:11434/v1
  h8_api_key: ""
  h9_timeout: 30

index:
  auto: true
  store: "%APPDATA%\\semantic-search\\cache"
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

## 🗺️ Sequentially Phased Implementation Roadmap

### Phase 1: Scaffolding, Models & Config
- Set up directory structure, `pyproject.toml`, and config parser.
- Define shared interfaces (`BaseHandler`, `MatchResult`) and the pipeline builder (`Chain`).

### Phase 2: Scanner & Core Handlers (H1 - H4)
- Implement `scanner.py` with ignore-list filters for `node_modules`, dotfiles, and virtual environments.
- Implement H1 (Exact), H2 (Case-Insensitive), H3 (Token-Normalized), and H4 (Fuzzy String with `rapidfuzz`).

### Phase 3: Phonetic, Config Aliases & Memory (H5 - H6)
- Implement H5 (Phonetic matching using `jellyfish`'s Metaphone/Soundex algorithm).
- Implement H6 (Alias parsing from `config.yaml` and dynamic memory from `learned_aliases.yaml`).
- Implement `export-memory` and `import-memory` commands.

### Phase 4: Persistent Indexing
- Create persistent index store (`index.json`) containing pre-tokenized directory contents and modification checks (`mtime`).
- Implement CLI `index` subcommands.

### Phase 5: Heavy Matchers (H7 - H8)
- Implement H7 (Lazy-loaded `sentence-transformers` for semantic similarity scoring).
- Implement H8 (LLM inference via Ollama / OpenAI API compatible endpoints).

### Phase 6: Interactive Fallback, Verification & Smoke Tests
- Implement H9 (Interactive prompt utilizing `questionary` or `inquirer` to confirm options).
- Add confirmation log appender to update the memory.
- Add mock filesystem tests under `tests/` checking the exact execution path of the chain.
