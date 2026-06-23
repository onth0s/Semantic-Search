# sempath

`sempath` is a Windows-first Python CLI for finding filesystem paths from vague,
colloquial, misspelled, semantically fuzzy, or wildcard/glob (e.g. `*.txt`) descriptions.
It features config-driven ad hoc category keyword tags (e.g. `docs`, `pics`) and is meant to be
usable by both humans and LLM agents that need reliable path resolution without
knowing exact casing, spelling, or directory names.

## Examples

- `"desktop/main"` -> `C:\Users\Leonardo\Desktop\__MAIN`
- `"the main dir on dsktp"` -> `C:\Users\Leonardo\Desktop\__MAIN`
- `"Principal"` -> `C:\Users\Leonardo\Desktop\__MAIN`
- `"important folder"` -> `C:\Users\Leonardo\Desktop\__MAIN`
- `"dl"` -> `C:\Users\Leonardo\Downloads`

## Current Status

The current implementation includes the Click/Rich CLI, filesystem scanning,
SQLite indexing, heuristic filters, handlers H1 through H9, learned alias memory,
memory import/export, Windows admin USN Journal acceleration, and tests.

> [!IMPORTANT]
> To avoid Windows environment/path conflicts (such as Anaconda shadowing standard Python), always use `py -3.13` to explicitly target the correct environment for installation and testing:
> ```powershell
> py -3.13 -m pip install -e .
> py -3.13 -m pytest
> ```
> These are the only commands guaranteed to install the package and run the test suite properly without environment mismatch issues.

Last local verification: 104 tests passed on Python 3.13.1.

## Project Rules

These rules are also captured in `.agents/AGENTS.md` and should stay true in
future code and docs changes:

- The MVP targets the host machine on Windows. Cross-platform support is deferred.
- File and directory sizes must be human-readable with exactly two decimal places.
- User-facing CLI output should use Rich styling where relevant.

## Tech Stack

- Python 3.11+
- Click for subcommand routing and prompts
- Rich for styled CLI output
- PyYAML for config and learned-memory files
- RapidFuzz for fuzzy string scoring
- pathspec for `.gitignore` support
- jellyfish for Metaphone phonetic matching
- SQLite for the persistent path index
- pytest and Ruff for test and lint tooling

Optional runtime integrations:

- `sentence-transformers` powers H7 semantic embedding matches when installed.
  It is lazy-imported and installable with `pip install -e .[semantic]` from
  this checkout, or `pip install sempath[semantic]` for an installed package.
- H8 calls an OpenAI-compatible chat-completions endpoint, configured for Ollama
  by default.

## Architecture

`sempath` resolves a query in five broad steps:

1. Gather candidate paths from the SQLite index, or scan on the fly with
   `--no-index`.
2. Apply query heuristics for extensions, temporal filters, latest/newest, and
   largest/biggest.
3. Filter and sort candidates based on explicit flags and parsed heuristics.
4. Run the configured handler chain.
5. Return a success, ambiguous near-miss result, or failure object.

```mermaid
graph TD
    UserQuery["User query"] --> Heuristics["Heuristic parser"]
    Heuristics --> Candidates["Candidate gathering"]
    Candidates --> Index["SQLite index if enabled"]
    Candidates --> Scan["On-the-fly scan"]
    Scan --> MFT["Windows admin USN Journal path if available"]
    Scan --> Walk["os.walk fallback"]
    Index --> FilterSort["Filter and sort candidates"]
    Walk --> FilterSort
    MFT --> FilterSort
    FilterSort --> Chain["Handler chain H1-H9"]
    Chain --> Result["SearchResult JSON/text output"]
```

## Handlers

The default handler order is configured in `config.yaml`:

```yaml
handlers:
  enabled: [h1, h2, h3, h4, h5, h6, h7, h8, h9]
```

| Handler | Implemented behavior |
|---|---|
| H1 Exact | Exact basename, stem, or path-suffix match. Supports case-sensitive globbing. |
| H2 Case-insensitive | Case-insensitive basename, stem, or path-suffix match. Supports case-insensitive globbing. |
| H3 Token-normalized | Normalizes alphanumeric and wildcard tokens and compares unordered sets via bijection globbing. |
| H4 Fuzzy | RapidFuzz ratio against name, stem, and path suffixes. Destructures wildcard queries by stripping `*`/`?`. |
| H5 Phonetic | jellyfish Metaphone comparison for name, stem, and path suffixes. Destructures wildcard queries by stripping `*`/`?`. |
| H6 Alias | Config aliases and learned aliases with exact, regex, fuzzy, and phonetic key matching. Supports wildcard targets and `"<sub query> on <alias>"` / `"<sub query> in <alias>"` routing. |
| H7 Embedding | Optional lazy `sentence-transformers` semantic match. Prompts before loading in interactive mode. Translates wildcard queries to descriptions before encoding. |
| H8 LLM rewrite | Sends the query to an OpenAI-compatible chat endpoint (translating wildcard queries first), then runs H1-H6 on the rewritten query. |
| H9 Interactive | Click-based fallback that offers fuzzy-ranked candidates and stores confirmed selections as learned memory. |

## CLI

To view standard help and the main options, run:
```bash
sempath --help
```

To view comprehensive help showing all options, arguments, and descriptions for **every possible command and subcommand** recursively, run:
```bash
sempath --help-full
```

### Usage
```bash
sempath find [OPTIONS] QUERY [ROOT_DIR]
sempath index create [OPTIONS] [PATH]
sempath index update [OPTIONS] [PATH]
sempath index list
sempath index remove [OPTIONS] [PATH]
sempath alias add NAME PATH
sempath alias list
sempath alias remove NAME
sempath alias clear
sempath alias undo
sempath config verbose VALUE
sempath export-memory FILE_PATH
sempath import-memory FILE_PATH
```

### `find` Options

| Option | Default | Description |
|---|---:|---|
| `--root` | `None` | Root directory to search, overriding the positional `ROOT_DIR`. |
| `--depth` | `5` | Maximum folder depth to traverse. |
| `--min-confidence` | `0.3` | Minimum confidence score needed for success. |
| `--top-n` | `1` | Number of near misses to print in text output. |
| `--non-interactive` | `false` | Disable H9 interactive fallback and skip the H7 confirmation prompt. |
| `--no-index` | `false` | Force on-the-fly scanning instead of SQLite index use. |
| `--json` | `false` | Emit structured JSON. |
| `--verbose` | `false` | Enable detailed under-the-hood diagnostics, category matching, and handler execution logs. |
| `--latest` | `false` | Sort filtered candidates by newest modification time. |
| `--largest` | `false` | Sort filtered candidates by largest file size. |
| `--ext` | `None` | Keep candidates with the given extension. |

## Indexing And Scanning

By default, `find` uses the SQLite index when `index.auto` is true. If the root is
not indexed yet, the engine creates or updates the index automatically before
querying it. Pass `--no-index` to force a direct filesystem scan.

The scanner:

- ignores hidden names and configured exclusions such as `.git`, `node_modules`,
  virtualenvs, build outputs, and Python caches;
- respects nested `.gitignore` files with `pathspec`;
- on Windows, tries a read-only USN Journal scan when running as Administrator;
- falls back to `os.walk` when USN scanning is unavailable.

## Learned Memory

Learned aliases are stored at `%APPDATA%\sempath\learned_aliases.yaml` on
Windows, or under the user config directory fallback when `APPDATA` is not set.

Each entry contains:

- `query`
- `path`
- `timestamp`
- `hits`
- `decay_rank`

The memory utilities recalculate decay rank on load, merge imported memory by
query/path, and support chronological undo through `sempath alias undo`.

## JSON Output

`--json` serializes the `SearchResult` model.

Success:

```json
{
  "status": "success",
  "query": "desktop/main",
  "match": {
    "path": "C:\\Users\\Leonardo\\Desktop\\__MAIN",
    "confidence": 1.0,
    "handler": "h1_exact"
  }
}
```

Ambiguous:

```json
{
  "status": "ambiguous",
  "query": "dsktp/maine",
  "message": "No match found above confidence threshold.",
  "near_misses": [
    {
      "path": "C:\\Users\\Leonardo\\Desktop\\__MAIN",
      "confidence": 0.85,
      "handler": "h4_fuzzy"
    }
  ]
}
```

Failure:

```json
{
  "status": "failed",
  "query": "unknown_path",
  "message": "No candidate paths or near-misses matched the query.",
  "near_misses": []
}
```

## Configuration

Bundled defaults live in `config.yaml`; user config at
`%APPDATA%\sempath\config.yaml` is deep-merged over those defaults.

### CLI Verbose Command
You can persistently toggle verbose logging via the CLI command:
```bash
sempath config verbose [on|off|true|false]
```
This saves the configuration locally under `%APPDATA%\sempath\config.yaml` to override any system/package defaults.

```yaml
handlers:
  enabled: [h1, h2, h3, h4, h5, h6, h7, h8, h9]
  h4_threshold: 75
  h7_model: all-MiniLM-L6-v2
  h8_provider: ollama
  h8_model: llama3
  h8_url: http://localhost:11434/v1
  h8_api_key: ""

index:
  auto: true
  store: "%APPDATA%\\sempath\\cache"
  exclude_patterns:
    - "node_modules"
    - ".git"
    - "venv"
    - "__pycache__"
    - ".mypy_cache"
    - ".pytest_cache"
    - "build"
    - "dist"

aliases:
  main: [__MAIN, principal, important, primary, master]
  dl: [Downloads, download]
  docs: [Documents, documentation, docs]
```

## Roadmap Snapshot

- Completed: scaffolding, config loading, models, scanner, H1-H9 handlers,
  heuristics, explicit flags, learned memory, SQLite indexing, memory
  import/export, CLI commands, Windows USN Journal scan path, and tests.
- Optional/runtime-dependent: H7 requires the `semantic` extra; H8 requires a
  reachable configured LLM endpoint.
- Future work: broader cross-platform tuning and additional performance
  hardening for very large trees.
