"""Shared Jinja2 helpers for the generators.

Generic only — no document-domain logic. The single knob here is missing-key
*strictness*:

* ``StrictUndefined`` — an undefined key raises ``UndefinedError`` (surfaced by
  the app as a ``render_failed`` 500).
* default ``Undefined`` — an undefined key renders as an empty string.

Each format picks a default; the caller may override it per request via the
``strict`` form field (see ``resolve_strict``).
"""
from __future__ import annotations

from jinja2 import BaseLoader, Environment, StrictUndefined, Undefined


def resolve_strict(strict, default: bool) -> bool:
    """Resolve the tri-state ``strict`` to a bool.

    ``None`` means "no override" — use the format's ``default``.
    """
    return default if strict is None else bool(strict)


def make_env(strict: bool) -> Environment:
    """Build a string-template environment with the chosen strictness.

    autoescape stays off: this is a generic templating tool and the caller
    controls both template and content (matters for HTML/PDF output).
    """
    return Environment(
        loader=BaseLoader(),
        undefined=StrictUndefined if strict else Undefined,
        autoescape=False,
    )
