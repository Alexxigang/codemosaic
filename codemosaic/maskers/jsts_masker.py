from __future__ import annotations

import re
from collections import Counter

from codemosaic.mapping import MappingVault
from codemosaic.policy import MaskPolicy


IDENTIFIER_START_RE = re.compile(r"[A-Za-z_$]")
IDENTIFIER_BODY_RE = re.compile(r"[A-Za-z0-9_$]")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+?[\d\-\s()]{7,}$")
SECRET_RE = re.compile(r"(secret|token|passwd|password|api[_-]?key|client[_-]?secret)", re.IGNORECASE)
RESERVED_WORDS = {
    "abstract",
    "any",
    "as",
    "asserts",
    "async",
    "await",
    "boolean",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "constructor",
    "continue",
    "debugger",
    "declare",
    "default",
    "delete",
    "do",
    "else",
    "enum",
    "export",
    "extends",
    "false",
    "finally",
    "for",
    "from",
    "function",
    "get",
    "if",
    "implements",
    "import",
    "in",
    "infer",
    "instanceof",
    "interface",
    "is",
    "keyof",
    "let",
    "module",
    "namespace",
    "never",
    "new",
    "null",
    "number",
    "object",
    "of",
    "package",
    "private",
    "protected",
    "public",
    "readonly",
    "require",
    "return",
    "satisfies",
    "set",
    "static",
    "string",
    "super",
    "switch",
    "symbol",
    "this",
    "throw",
    "true",
    "try",
    "type",
    "typeof",
    "undefined",
    "unique",
    "unknown",
    "var",
    "void",
    "while",
    "with",
    "yield",
}
GLOBAL_PRESERVE = {
    "Array",
    "Boolean",
    "Date",
    "Error",
    "JSON",
    "Map",
    "Math",
    "Number",
    "Object",
    "Promise",
    "RegExp",
    "Set",
    "String",
    "console",
    "window",
    "document",
    "process",
}
JS_TS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}


def mask_jsts_source(
    text: str, vault: MappingVault, policy: MaskPolicy
) -> tuple[str, dict[str, int]]:
    counts: Counter[str] = Counter()
    masked, _ = _mask_expression(text, 0, vault, policy, counts, stop_char=None)
    return masked, dict(counts)


def _mask_expression(
    text: str,
    start: int,
    vault: MappingVault,
    policy: MaskPolicy,
    counts: Counter[str],
    stop_char: str | None,
) -> tuple[str, int]:
    parts: list[str] = []
    index = start
    while index < len(text):
        if stop_char is not None and text[index] == stop_char:
            return "".join(parts), index
        if text.startswith("//", index):
            end = text.find("\n", index)
            if end == -1:
                end = len(text)
            body = text[index + 2 : end].strip()
            parts.append(_render_comment(body, vault, policy, block=False))
            counts["comments"] += 1
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end == -1:
                end = len(text) - 2
            body = text[index + 2 : end].strip()
            parts.append(_render_comment(body, vault, policy, block=True))
            counts["comments"] += 1
            index = end + 2
            continue
        current = text[index]
        if current in {'"', "'"}:
            rendered, next_index = _mask_quoted_string(text, index, vault, counts)
            parts.append(rendered)
            index = next_index
            continue
        if current == "`":
            rendered, next_index = _mask_template_literal(text, index, vault, policy, counts)
            parts.append(rendered)
            index = next_index
            continue
        if current == "#" and index + 1 < len(text) and _is_identifier_start(text[index + 1]):
            token, next_index = _consume_identifier(text, index + 1)
            if policy.identifiers.enabled and token not in policy.identifiers.preserve:
                parts.append("#" + vault.mask_identifier(token))
                counts["identifiers"] += 1
            else:
                parts.append("#" + token)
            index = next_index
            continue
        if _is_identifier_start(current):
            token, next_index = _consume_identifier(text, index)
            previous_char = _previous_non_whitespace(text, index)
            next_char = text[next_index] if next_index < len(text) else ""
            if _should_preserve_identifier(token, previous_char, next_char, policy):
                parts.append(token)
            else:
                parts.append(vault.mask_identifier(token))
                counts["identifiers"] += 1
            index = next_index
            continue
        parts.append(current)
        index += 1
    return "".join(parts), index


def _mask_quoted_string(
    text: str,
    start: int,
    vault: MappingVault,
    counts: Counter[str],
) -> tuple[str, int]:
    quote = text[start]
    index = start + 1
    buffer: list[str] = []
    while index < len(text):
        current = text[index]
        if current == "\\" and index + 1 < len(text):
            buffer.append(current)
            buffer.append(text[index + 1])
            index += 2
            continue
        if current == quote:
            literal = "".join(buffer)
            placeholder = vault.mask_string(literal, _detect_string_category(literal))
            counts["strings"] += 1
            return f"{quote}{placeholder}{quote}", index + 1
        buffer.append(current)
        index += 1
    literal = "".join(buffer)
    placeholder = vault.mask_string(literal, _detect_string_category(literal))
    counts["strings"] += 1
    return f"{quote}{placeholder}{quote}", len(text)


def _mask_template_literal(
    text: str,
    start: int,
    vault: MappingVault,
    policy: MaskPolicy,
    counts: Counter[str],
) -> tuple[str, int]:
    index = start + 1
    parts = ["`"]
    chunk: list[str] = []
    while index < len(text):
        current = text[index]
        if current == "\\" and index + 1 < len(text):
            chunk.append(current)
            chunk.append(text[index + 1])
            index += 2
            continue
        if text.startswith("${", index):
            if chunk:
                literal = "".join(chunk)
                placeholder = vault.mask_string(literal, _detect_string_category(literal))
                counts["strings"] += 1
                parts.append(placeholder)
                chunk = []
            inner, next_index = _consume_template_expression(text, index + 2, vault, policy, counts)
            parts.append("${")
            parts.append(inner)
            parts.append("}")
            index = next_index
            continue
        if current == "`":
            if chunk:
                literal = "".join(chunk)
                placeholder = vault.mask_string(literal, _detect_string_category(literal))
                counts["strings"] += 1
                parts.append(placeholder)
            parts.append("`")
            return "".join(parts), index + 1
        chunk.append(current)
        index += 1
    if chunk:
        literal = "".join(chunk)
        placeholder = vault.mask_string(literal, _detect_string_category(literal))
        counts["strings"] += 1
        parts.append(placeholder)
    parts.append("`")
    return "".join(parts), len(text)


def _consume_template_expression(
    text: str,
    start: int,
    vault: MappingVault,
    policy: MaskPolicy,
    counts: Counter[str],
) -> tuple[str, int]:
    depth = 1
    index = start
    inner_parts: list[str] = []
    while index < len(text):
        current = text[index]
        if current in {'"', "'"}:
            rendered, next_index = _mask_quoted_string(text, index, vault, counts)
            inner_parts.append(rendered)
            index = next_index
            continue
        if current == "`":
            rendered, next_index = _mask_template_literal(text, index, vault, policy, counts)
            inner_parts.append(rendered)
            index = next_index
            continue
        if text.startswith("//", index):
            end = text.find("\n", index)
            if end == -1:
                end = len(text)
            body = text[index + 2 : end].strip()
            inner_parts.append(_render_comment(body, vault, policy, block=False))
            counts["comments"] += 1
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end == -1:
                end = len(text) - 2
            body = text[index + 2 : end].strip()
            inner_parts.append(_render_comment(body, vault, policy, block=True))
            counts["comments"] += 1
            index = end + 2
            continue
        if text.startswith("${", index):
            depth += 1
            inner_parts.append("${")
            index += 2
            continue
        if current == "{":
            depth += 1
            inner_parts.append(current)
            index += 1
            continue
        if current == "}":
            depth -= 1
            if depth == 0:
                return "".join(inner_parts), index + 1
            inner_parts.append(current)
            index += 1
            continue
        if current == "#" and index + 1 < len(text) and _is_identifier_start(text[index + 1]):
            token, next_index = _consume_identifier(text, index + 1)
            if policy.identifiers.enabled and token not in policy.identifiers.preserve:
                inner_parts.append("#" + vault.mask_identifier(token))
                counts["identifiers"] += 1
            else:
                inner_parts.append("#" + token)
            index = next_index
            continue
        if _is_identifier_start(current):
            token, next_index = _consume_identifier(text, index)
            previous_char = _previous_non_whitespace(text, index)
            next_char = text[next_index] if next_index < len(text) else ""
            if _should_preserve_identifier(token, previous_char, next_char, policy):
                inner_parts.append(token)
            else:
                inner_parts.append(vault.mask_identifier(token))
                counts["identifiers"] += 1
            index = next_index
            continue
        inner_parts.append(current)
        index += 1
    return "".join(inner_parts), len(text)


def _consume_identifier(text: str, start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(text) and _is_identifier_body(text[index]):
        index += 1
    return text[start:index], index


def _is_identifier_start(char: str) -> bool:
    return bool(IDENTIFIER_START_RE.fullmatch(char))


def _is_identifier_body(char: str) -> bool:
    return bool(IDENTIFIER_BODY_RE.fullmatch(char))


def _previous_non_whitespace(text: str, index: int) -> str:
    cursor = index - 1
    while cursor >= 0 and text[cursor].isspace():
        cursor -= 1
    return text[cursor] if cursor >= 0 else ""


def _should_preserve_identifier(
    token: str,
    previous_char: str,
    next_char: str,
    policy: MaskPolicy,
) -> bool:
    if not policy.identifiers.enabled:
        return True
    if token in RESERVED_WORDS or token in GLOBAL_PRESERVE or token in policy.identifiers.preserve:
        return True
    if previous_char == ".":
        return True
    if previous_char in {"<", "/"} and token.islower():
        return True
    if next_char == ":" and token.islower():
        return True
    return False


def _render_comment(body: str, vault: MappingVault, policy: MaskPolicy, block: bool) -> str:
    if policy.comments.mode == "remove":
        return ""
    placeholder = vault.mask_comment(body)
    if block:
        return f"/* {placeholder} */"
    return f"// {placeholder}"


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
