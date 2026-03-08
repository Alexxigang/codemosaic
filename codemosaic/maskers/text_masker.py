from __future__ import annotations

import re
from collections import Counter

from codemosaic.mapping import MappingVault
from codemosaic.policy import MaskPolicy


IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?[\d\-\s()]{7,}$")
SECRET_RE = re.compile(r"(secret|token|passwd|password|api[_-]?key|client[_-]?secret)", re.IGNORECASE)
RESERVED_WORDS = {
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "default",
    "def",
    "do",
    "else",
    "enum",
    "export",
    "extends",
    "false",
    "finally",
    "fn",
    "for",
    "function",
    "if",
    "impl",
    "import",
    "in",
    "interface",
    "let",
    "match",
    "mod",
    "new",
    "null",
    "package",
    "private",
    "protected",
    "public",
    "pub",
    "return",
    "static",
    "struct",
    "super",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "type",
    "use",
    "var",
    "void",
    "while",
}


def mask_text_source(
    text: str, vault: MappingVault, policy: MaskPolicy
) -> tuple[str, dict[str, int]]:
    counts: Counter[str] = Counter()
    parts: list[str] = []
    index = 0
    while index < len(text):
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end == -1:
                end = len(text) - 2
            body = text[index + 2 : end].strip()
            parts.append(_render_comment(body, vault, policy, block=True))
            counts["comments"] += 1
            index = end + 2
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            if end == -1:
                end = len(text)
            body = text[index + 2 : end].strip()
            parts.append(_render_comment(body, vault, policy, block=False))
            counts["comments"] += 1
            index = end
            continue
        if text[index] in {'"', "'", "`"}:
            end = _find_string_end(text, index)
            literal = text[index + 1 : end - 1] if end > index + 1 else ""
            category = _detect_string_category(literal)
            placeholder = vault.mask_string(literal, category)
            parts.append(f"{text[index]}{placeholder}{text[index]}")
            counts["strings"] += 1
            index = end
            continue
        next_positions = [pos for pos in (text.find("/*", index), text.find("//", index)) if pos != -1]
        quote_positions = [pos for pos in (text.find('"', index), text.find("'", index), text.find("`", index)) if pos != -1]
        if next_positions or quote_positions:
            next_break = min(next_positions + quote_positions)
        else:
            next_break = len(text)
        segment = text[index:next_break]
        parts.append(_mask_identifiers(segment, vault, policy, counts))
        index = next_break
    return "".join(parts), dict(counts)


def _mask_identifiers(
    segment: str, vault: MappingVault, policy: MaskPolicy, counts: Counter[str]
) -> str:
    if not policy.identifiers.enabled:
        return segment

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in RESERVED_WORDS or token in policy.identifiers.preserve:
            return token
        counts["identifiers"] += 1
        return vault.mask_identifier(token)

    return IDENTIFIER_RE.sub(replace, segment)


def _render_comment(body: str, vault: MappingVault, policy: MaskPolicy, block: bool) -> str:
    if policy.comments.mode == "remove":
        return ""
    placeholder = vault.mask_comment(body)
    if block:
        return f"/* {placeholder} */"
    return f"// {placeholder}"


def _find_string_end(text: str, start: int) -> int:
    quote = text[start]
    index = start + 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return index + 1
        index += 1
    return len(text)


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
