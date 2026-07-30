# SEMPATH_REPORT.md

## Tool: `sempath find` (aliased as `sf`)

Semantic filesystem search — finds paths by fuzzy/colloquial queries, file content, or wildcards.

---

## Key Flags

| Flag | Purpose |
|---|---|
| `--root PATH` | **Critical.** Scope search to a subtree. Without it, searches from CWD (entire repo including v9 archive). |
| `--read-content` | Search within file text content (not just paths). Required for code-level queries. |
| `--ext cs` | Filter to C# files only. Avoids noise from `.resx`, `.axaml`, etc. |
| `--top-n N` | Limit result count. Default 5 is usually enough for focused queries. |
| `--h1-6` | Restrict handler layers. Useful for precision but not a substitute for `--root`. |

---

## Usage Patterns for This Codebase

### Pattern 1: Code search (finding where a concept lives)
```powershell
sf "SZ" --root "ImageGlass\source" --read-content --ext cs --top-n 10
```
Returns: `Config_Static.cs`, `ToolbarControl.axaml.cs`, `ToolbarItemModel.cs`, `ViewerControl_ZoomAndPan.cs` — exactly the relevant files, zero v9 noise.

### Pattern 2: Architecture exploration (finding related files)
```powershell
sf "ToolbarIcons" --root "ImageGlass\source" --read-content --ext cs --top-n 10
```
Returns: `IgTheme.cs`, `IgThemeIcons.cs`, `ToolbarItemModel.cs` — the icon resolution chain.

### Pattern 3: File-path fuzzy matching (without content search)
```powershell
sf "ToolbarButton" --root "ImageGlass\source" --ext axaml
```
Returns files whose paths match "ToolbarButton" — useful for finding `.axaml` templates.

---

## Anti-Patterns (What NOT To Do)

### Bad: No `--root` scoping
```powershell
sf SZ --h1-6 --read-content          # searches entire repo including v9/
```
Returns ~15 results, 10+ from `ImageGlass/v9/` (legacy WinForms code). Waste of context.

### Bad: No `--ext` filter
```powershell
sf SZ --root "ImageGlass\source" --read-content
```
Returns `.resx`, `.axaml.cs`, and other noise alongside the C# files you actually want.

### Bad: Too broad a query
```powershell
sf "toggle" --root "ImageGlass\source" --read-content --ext cs
```
Returns 50+ files because "toggle" appears everywhere. Use specific identifiers instead (`SharedZoom`, `EnableSharedZoom`, `IG_ToggleSharedZoom`).

---

## Recommended Default for This Repo

```powershell
sf <QUERY> --root "ImageGlass\source" --read-content --ext cs --top-n 10
```

This consistently returns the v10 source files that matter, scoped and filtered.
