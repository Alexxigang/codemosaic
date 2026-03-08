from __future__ import annotations

import ast
import io
import keyword
import re
import tokenize
from collections import Counter

from codemosaic.mapping import MappingVault
from codemosaic.policy import MaskPolicy


URL_RE = re.compile(r"^https?://", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?[\d\-\s()]{7,}$")
SECRET_RE = re.compile(r"(secret|token|passwd|password|api[_-]?key|client[_-]?secret)", re.IGNORECASE)


def mask_python_text(
    text: str, vault: MappingVault, policy: MaskPolicy
) -> tuple[str, dict[str, int]]:
    counts: Counter[str] = Counter()
    tokens: list[tokenize.TokenInfo] = []
    reader = io.StringIO(text).readline
    for token in tokenize.generate_tokens(reader):
        updated = token
        if (
            token.type == tokenize.NAME
            and policy.identifiers.enabled
            and not keyword.iskeyword(token.string)
            and token.string not in policy.identifiers.preserve
        ):
            updated = token._replace(string=vault.mask_identifier(token.string))
            counts["identifiers"] += 1
        elif token.type == tokenize.STRING and policy.strings.enabled:
            masked_literal = _mask_string_literal(token.string, vault)
            if masked_literal != token.string:
                updated = token._replace(string=masked_literal)
                counts["strings"] += 1
        elif token.type == tokenize.COMMENT:
            replacement = _mask_comment(token.string, vault, policy)
            if replacement != token.string:
                updated = token._replace(string=replacement)
                counts["comments"] += 1
        tokens.append(updated)
    return tokenize.untokenize(tokens), dict(counts)


def _mask_string_literal(token_string: str, vault: MappingVault) -> str:
    literal_value, is_bytes = _literal_value(token_string)
    if literal_value is None:
        literal_value = token_string
    category = _detect_string_category(literal_value)
    placeholder = vault.mask_string(literal_value, category)
    prefix = "b" if is_bytes else ""
    return f'{prefix}"{placeholder}"'


def _literal_value(token_string: str) -> tuple[str | None, bool]:
    try:
        value = ast.literal_eval(token_string)
    except (ValueError, SyntaxError):
        return None, False
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore"), True
    if isinstance(value, str):
        return value, False
    return None, False


def _detect_string_category(value: str) -> str:
    if URL_RE.search(value):
        return "url"
    if EMAIL_RE.search(value):
        return "email"
    if PHONE_RE.search(value):
        return "phone"
    if SECRET_RE.search(value):
        return "secret"
    return "generic"


def _mask_comment(comment: str, vault: MappingVault, policy: MaskPolicy) -> str:
    body = comment.lstrip("#/").strip()
    if policy.comments.mode == "remove":
        return ""
    placeholder = vault.mask_comment(body)
    return f"# {placeholder}"
