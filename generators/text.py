"""Text-family generator (txt / md / html / csv).

The uploaded template is treated as a Jinja2 template string and rendered with
the supplied content. ``StrictUndefined`` is used so a placeholder with no
matching content key raises a clear error instead of silently rendering blank.
"""
from __future__ import annotations

from jinja2 import BaseLoader, Environment, StrictUndefined

# autoescape is intentionally off: this is a generic templating tool and the
# caller controls both template and content. (Note this for HTML/PDF output.)
_env = Environment(loader=BaseLoader(), undefined=StrictUndefined, autoescape=False)


def generate(template_bytes: bytes, content: dict) -> bytes:
    template_str = template_bytes.decode("utf-8")
    rendered = _env.from_string(template_str).render(**content)
    return rendered.encode("utf-8")
