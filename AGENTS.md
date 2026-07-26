# Agent Guidelines for Codebase Search

## Efficient Search with `sempath`
When searching for files, architectural concepts, or code snippets across a repository, AI agents SHOULD use `sempath` (or alias `sf`) instead of slow, unindexed `grep`/`glob` scans. `sempath` executes multi-layer fuzzy, phonetic, wildcard, and content searches in seconds.

### Key Instructions for Agents:
1. **Self-Discovery**: Run `sempath --help` or `sempath find --help` (or `py -3.13 -m sempath find --help`) whenever needed to explore options.
2. **Recommended Command Pattern**:
   ```powershell
   sempath find "<QUERY>" --root "<TARGET_DIR>" --read-content --ext <EXT> --top-n 10 --non-interactive --json
   ```
3. **Best Practices**:
   - **Scope with `--root`**: Always scope to relevant subdirectories (e.g. `--root "src"`) to avoid noise from legacy folders or archives.
   - **Content Search**: Use `--read-content` when querying code concepts or text inside files.
   - **Extension Filter**: Use `--ext` (e.g. `--ext cs`, `--ext py`) to isolate target file types.
   - **Agent Options**: Use `--non-interactive` to prevent interactive prompts and `--json` for structured output parsing when needed.

---

# Project Rules

- **Platform Target**: Cross-platform support is deferred for now. The MVP is built specifically for the host machine (Windows OS).
- **File/Directory Size Output**: If outputting file or directory sizes, always format them in a human-readable format (e.g. KB, MB, GB) with exactly 2 decimal places.
- **Test Success Message**: When all tests pass, append a cute message at the end with an ASCII character saying "BANZAI~!".
- **Rich CLI Output**: Use [Rich](https://rich.readthedocs.io/) to color and style all relevant CLI output (status messages, match results, errors, warnings, tables, progress indicators). Plain uncolored output is not acceptable for user-facing messages.
- **Don't restore any files that have been deleted unless the user explicitly tells you to.**
- **Code Quality Check**: Always run Ruff (`py -3.13 -m ruff check --fix` and `py -3.13 -m ruff format`) to check and format the codebase after every major change.
- **Distribution/Packaging**: Package distribution is deferred for now as this is still in beta. The configuration file `config.yaml` remains at the project root as a user-editable example.

