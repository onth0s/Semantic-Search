"""LLM handler — direct semantic path matching.

Sends the candidate relative paths and the user query to the configured LLM
model and asks it to select the best matching paths.  The response is a plain
newline-separated list of relative paths; we resolve them back to absolute
Path objects and return them as MatchResult entries.

Configuration keys (under ``handlers`` in config):
    h8_model   - Ollama model tag to use (default: minimax-m3:cloud).
    h8_url     - Base URL of the Ollama server (default: http://localhost:11434/v1).
    h8_api_key - Bearer token if required (default: "").
    h8_top_k   - Maximum number of paths to return (default: 6).

If the configured model is not available the handler raises ValueError
immediately.  It does **not** fall back to any other model.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from sempath.handlers.base import BaseHandler
from sempath.models import MatchResult
from sempath.utils.console import err_console

if TYPE_CHECKING:
    from sempath.search_context import SearchContext

_CONFIDENCE = 0.80

_SYSTEM_PROMPT = (
    "You are a filesystem path matching assistant.\n"
    "You are given a list of filesystem paths (relative) and a user query.\n"
    "Select up to {top_k} paths that best match the query intent, ordered from best to worst.\n"
    "Output ONLY the selected paths, one per line.\n"
    "Do not include explanation, markdown, code fences, or quotation marks.\n"
    "If nothing matches, output nothing."
)


def _check_model_available(base_url: str, model: str) -> None:
    """Verify the model is present in Ollama's tag list.

    Raises ValueError (no fallback) if the model is not found or the
    Ollama server cannot be reached.
    """
    tags_url = base_url.rstrip("/").removesuffix("/v1") + "/api/tags"
    try:
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ValueError(f"Cannot reach Ollama server at {tags_url}: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Unexpected error checking Ollama models: {exc}") from exc

    available = [m.get("name", "") for m in data.get("models", [])]
    if model not in available:
        raise ValueError(
            f"Model '{model}' is not available in Ollama. "
            f"Available models: {available or ['(none loaded)']}\n"
            "DO NOT fall back to a local model — fix your h8_model configuration."
        )


class LLMHandler(BaseHandler):
    """Direct LLM semantic path matcher. Confidence: 0.80."""

    name: str = "h8_llm"

    def match(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> MatchResult | None:
        results = self.match_all(query, candidates, context=context)
        if not results:
            return None
        return results[0]

    def match_all(
        self,
        query: str,
        candidates: list[Path],
        context: SearchContext | None = None,
    ) -> list[MatchResult]:
        """Ask the LLM to pick the best matching paths from ``candidates``."""
        raw_query = context.raw_query if context else self.config.get("_raw_query", query)
        if not raw_query or not candidates:
            return []

        from sempath.utils.logging import verbose_log

        handlers_cfg = self.config.get("handlers", {})
        model: str = handlers_cfg.get("h8_model", "minimax-m3:cloud")
        url: str = handlers_cfg.get("h8_url", "http://localhost:11434/v1")
        api_key: str = handlers_cfg.get("h8_api_key", "")
        exhaustive = self.config.get("exhaustive", False)
        # LLM safety: evaluate max 100 candidates in H8.
        candidates_to_use = candidates[:100]
        if exhaustive:
            top_k = len(candidates_to_use)
        else:
            if context:
                top_n_val = context.top_n
            else:
                try:
                    import click

                    ctx = click.get_current_context(silent=True)
                    top_n_val = ctx.obj.get("top_n") if (ctx and ctx.obj) else None
                except Exception:
                    top_n_val = None

            if top_n_val is not None:
                top_k = min(int(top_n_val), len(candidates_to_use))
            else:
                top_k = min(int(handlers_cfg.get("h8_top_k", 6)), len(candidates_to_use))

        # --- Resolve search root for relative path computation ---------------
        if context:
            search_root = context.search_root
        else:
            try:
                import click

                ctx = click.get_current_context(silent=True)
                search_root = ctx.obj.get("root", Path(".")) if (ctx and ctx.obj) else Path(".")
            except Exception:
                search_root = Path(".")

        # Build relative-path strings; fall back to absolute if not under root
        def _rel(p: Path) -> str:
            try:
                return str(p.relative_to(search_root))
            except ValueError:
                return str(p)

        rel_map: dict[str, Path] = {_rel(p): p for p in candidates_to_use}

        # Validate the model is available before making the real call
        verbose_log(f"[dim]H8: checking model '{model}' is available...[/]")
        try:
            _check_model_available(url, model)
        except ValueError as exc:
            err_console.print(f"[bold red]H8 LLM error:[/] {exc}")
            raise  # Do NOT swallow — propagate so the pipeline reports cleanly

        # --- Build prompt ----------------------------------------------------
        path_list = "\n".join(rel_map.keys())
        system_content = _SYSTEM_PROMPT.format(top_k=top_k)
        user_content = f"Paths:\n{path_list}\n\nQuery: {raw_query}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint = f"{url.rstrip('/')}/chat/completions"
        verbose_log(f"[bold cyan]H8 LLM query prompt:[/] '[bold]{raw_query}[/]'")
        verbose_log(f"[dim]H8: querying {model} at {endpoint} (top_k={top_k})...[/]")

        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30.0) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                raw_content: str = res_data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            verbose_log(f"[bold red]H8 LLM request failed:[/] {exc}")
            return []

        verbose_log(f"[bold cyan]H8 LLM raw response:\n[/][dim]{raw_content}[/]")

        # --- Parse response --------------------------------------------------
        results: list[MatchResult] = []
        rel_lower = {k.lower(): v for k, v in rel_map.items()}

        for line in raw_content.splitlines():
            line = line.strip().strip("\"'`-• ")
            if not line:
                continue
            # Try exact match first, then case-insensitive
            matched_path = rel_map.get(line) or rel_lower.get(line.lower())
            if matched_path is not None:
                results.append(MatchResult(matched_path, _CONFIDENCE, self.name))
            if len(results) >= top_k:
                break

        verbose_log(f"[dim]H8: matched {len(results)} path(s)[/]")
        return results
