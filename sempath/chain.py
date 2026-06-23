"""Handler chain builder for sempath.

Reads the ``handlers.enabled`` list from the config, instantiates each
handler, and wires them into a Chain of Responsibility via
:meth:`~sempath.handlers.base.BaseHandler.set_next`.
"""

from __future__ import annotations

from sempath.handlers import HANDLER_REGISTRY
from sempath.handlers.base import BaseHandler


def build_chain(config: dict) -> BaseHandler:
    """Build and return the head of the handler chain.

    Reads ``config["handlers"]["enabled"]`` (e.g. ``["h1", "h2", ...]``),
    instantiates the corresponding handler classes from the registry,
    and wires them in order via ``set_next()``.

    Args:
        config: The merged sempath configuration dictionary.

    Returns:
        The first handler in the chain.

    Raises:
        ValueError: If the enabled list is empty or contains unknown handler names.
    """
    enabled = config.get("handlers", {}).get("enabled", [])

    if not enabled:
        raise ValueError(
            "No handlers enabled in config. "
            "Set handlers.enabled to a non-empty list (e.g. ['h1', 'h2', ...])."
        )

    # Instantiate handlers in order
    handlers: list[BaseHandler] = []
    for name in enabled:
        handler_cls = HANDLER_REGISTRY.get(name)
        if handler_cls is None:
            raise ValueError(
                f"Unknown handler '{name}' in handlers.enabled. "
                f"Available: {sorted(HANDLER_REGISTRY.keys())}"
            )
        handlers.append(handler_cls(config))

    # Wire the chain: each handler points to the next
    for i in range(len(handlers) - 1):
        handlers[i].set_next(handlers[i + 1])

    return handlers[0]
