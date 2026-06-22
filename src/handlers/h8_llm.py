"""LLM handler — query translation and rewrite fallback.

Sends the user's natural language query to an LLM provider (Ollama or OpenAI)
to translate it into a canonical, structured search query. Then evaluates
the canonical query against the fast handlers (H1-H6) in a second cycle.
"""

from __future__ import annotations

import copy
import json
import urllib.error
import urllib.request
from pathlib import Path

import click

from src.handlers.base import BaseHandler
from src.models import MatchResult


class LLMHandler(BaseHandler):
    """LLM query translation rewriter. Confidence: inherited from second cycle."""

    name: str = "h8_llm"

    def match(self, query: str, candidates: list[Path]) -> MatchResult | None:
        """Attempt to translate the query via LLM and run the fast chain."""
        if not query or not candidates:
            return None

        # Check interactive mode / verbose from Click context
        ctx = click.get_current_context(silent=True)
        verbose = ctx.obj.get("verbose", False) if ctx else False

        # Load LLM configurations
        handlers_cfg = self.config.get("handlers", {})
        provider = handlers_cfg.get("h8_provider", "ollama")
        model = handlers_cfg.get("h8_model", "llama3")
        url = handlers_cfg.get("h8_url", "http://localhost:11434/v1")
        api_key = handlers_cfg.get("h8_api_key", "")

        # Format URL to target chat completions endpoint
        endpoint = f"{url.rstrip('/')}/chat/completions"

        # Construct prompt instructing model to output only keywords and markers
        system_instructions = (
            "You are a query translation assistant. Your task is to rewrite a vague, colloquial, "
            "or descriptive user search query into simple canonical keywords and markers. "
            "Keep the core folder/file names, and include temporal keywords ('yesterday', 'today', "
            "'last week', 'last month'), type keywords ('image', 'pic', 'photo', "
            "'document', 'doc', 'pdf'), "
            "or ordering keywords ('latest', 'newest') if described. "
            "Output ONLY the translated keywords separated by spaces. Do not include explanation, "
            "markdown, or quotes."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": query},
            ],
            "temperature": 0.0,
        }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if verbose:
            click.echo(f"[dim]Sending query translation request to LLM ({provider}/{model})...[/]")

        try:
            req = urllib.request.Request(
                endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
            )
            # Timeout set to 5 seconds to prevent blocking UI
            with urllib.request.urlopen(req, timeout=5.0) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                canonical_query = res_data["choices"][0]["message"]["content"].strip()
                # Clean up any surrounding quotes if returned by the LLM
                canonical_query = canonical_query.strip("'\"")
        except Exception as exc:
            if verbose:
                click.echo(f"[dim]LLM query translation failed: {exc}[/]", err=True)
            return None

        if verbose:
            click.echo(f"[dim]LLM canonical translation: '{canonical_query}'[/]")

        # Second Cycle execution: evaluate canonical query on H1 - H6 only
        from src.chain import build_chain

        fast_config = copy.deepcopy(self.config)
        enabled_handlers = fast_config.get("handlers", {}).get("enabled", [])
        fast_handlers = [h for h in enabled_handlers if h in ("h1", "h2", "h3", "h4", "h5", "h6")]
        fast_config["handlers"]["enabled"] = fast_handlers

        try:
            fast_chain = build_chain(fast_config)
            result = fast_chain.handle(canonical_query, candidates)
            if result is not None:
                # Wrap the match and indicate it resolved via H8 LLM rewrite
                return MatchResult(result.path, result.confidence, f"{self.name}({result.handler})")
        except Exception as exc:
            if verbose:
                click.echo(f"[dim]Second cycle fast chain execution failed: {exc}[/]", err=True)

        return None
