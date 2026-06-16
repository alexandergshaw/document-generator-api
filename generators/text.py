"""Text-family generator (txt / md / html / csv).

The uploaded (or pasted) template is treated as a Jinja2 template string and
rendered with the supplied content. Strictness is configurable; this family
defaults to strict (an undefined key is an error).
"""
from __future__ import annotations

from ._jinja import make_env, resolve_strict

# Historical behavior: text formats error on a missing key.
_DEFAULT_STRICT = True


def generate(template_bytes: bytes, content: dict, strict=None) -> bytes:
    env = make_env(resolve_strict(strict, _DEFAULT_STRICT))
    template_str = template_bytes.decode("utf-8")
    rendered = env.from_string(template_str).render(**content)
    return rendered.encode("utf-8")
