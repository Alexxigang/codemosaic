from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from codemosaic.crypto import DEFAULT_PROVIDER_ID


@dataclass(slots=True)
class PathPolicy:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IdentifierPolicy:
    enabled: bool = True
    preserve: list[str] = field(default_factory=lambda: ['self', 'cls', '__name__'])


@dataclass(slots=True)
class StringPolicy:
    enabled: bool = True
    redact_patterns: list[str] = field(default_factory=lambda: ['url', 'email', 'phone', 'secret'])


@dataclass(slots=True)
class CommentPolicy:
    mode: str = 'placeholder'


@dataclass(slots=True)
class WorkspacePolicy:
    copy_unmatched: bool = False


@dataclass(slots=True)
class MappingRulePolicy:
    pattern: str
    require_encryption: bool | None = None
    encryption_provider: str | None = None
    order: int = 0


@dataclass(slots=True)
class MappingPolicy:
    require_encryption: bool = False
    encryption_provider: str | None = None
    rules: list[MappingRulePolicy] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EffectiveMappingPolicy:
    require_encryption: bool
    encryption_provider: str | None
    matched_patterns: tuple[str, ...] = ()


@dataclass(slots=True)
class MaskPolicy:
    paths: PathPolicy = field(default_factory=PathPolicy)
    identifiers: IdentifierPolicy = field(default_factory=IdentifierPolicy)
    strings: StringPolicy = field(default_factory=StringPolicy)
    comments: CommentPolicy = field(default_factory=CommentPolicy)
    workspace: WorkspacePolicy = field(default_factory=WorkspacePolicy)
    mapping: MappingPolicy = field(default_factory=MappingPolicy)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> 'MaskPolicy':
        paths = data.get('paths', {}) if isinstance(data, dict) else {}
        identifiers = data.get('identifiers', {}) if isinstance(data, dict) else {}
        strings = data.get('strings', {}) if isinstance(data, dict) else {}
        comments = data.get('comments', {}) if isinstance(data, dict) else {}
        workspace = data.get('workspace', {}) if isinstance(data, dict) else {}
        mapping = data.get('mapping', {}) if isinstance(data, dict) else {}
        return cls(
            paths=PathPolicy(
                include=list(paths.get('include', [])) if isinstance(paths, dict) else [],
                exclude=list(paths.get('exclude', [])) if isinstance(paths, dict) else [],
            ),
            identifiers=IdentifierPolicy(
                enabled=bool(identifiers.get('enabled', True)) if isinstance(identifiers, dict) else True,
                preserve=list(identifiers.get('preserve', ['self', 'cls', '__name__']))
                if isinstance(identifiers, dict)
                else ['self', 'cls', '__name__'],
            ),
            strings=StringPolicy(
                enabled=bool(strings.get('enabled', True)) if isinstance(strings, dict) else True,
                redact_patterns=list(strings.get('redact_patterns', ['url', 'email', 'phone', 'secret']))
                if isinstance(strings, dict)
                else ['url', 'email', 'phone', 'secret'],
            ),
            comments=CommentPolicy(
                mode=str(comments.get('mode', 'placeholder')) if isinstance(comments, dict) else 'placeholder'
            ),
            workspace=WorkspacePolicy(
                copy_unmatched=bool(workspace.get('copy_unmatched', False)) if isinstance(workspace, dict) else False
            ),
            mapping=MappingPolicy(
                require_encryption=bool(mapping.get('require_encryption', False)) if isinstance(mapping, dict) else False,
                encryption_provider=(
                    str(mapping.get('encryption_provider'))
                    if isinstance(mapping, dict) and mapping.get('encryption_provider') is not None
                    else None
                ),
                rules=_load_mapping_rules(mapping.get('rules', {})) if isinstance(mapping, dict) else [],
            ),
        )

    def resolve_mapping_policy(
        self,
        relative_paths: list[str],
        encryption_requested: bool = False,
        provider_override: str | None = None,
    ) -> EffectiveMappingPolicy:
        require_encryption = self.mapping.require_encryption
        matched_patterns: list[str] = []
        matched_specific_providers: set[str] = set()
        for relative_path in relative_paths:
            rule = _select_mapping_rule(self.mapping.rules, relative_path)
            if rule is None:
                continue
            matched_patterns.append(rule.pattern)
            if rule.require_encryption is True:
                require_encryption = True
            if rule.encryption_provider:
                matched_specific_providers.add(rule.encryption_provider)
        effective_encryption = encryption_requested or require_encryption
        policy_provider = _resolve_policy_provider(
            matched_specific_providers,
            self.mapping.encryption_provider,
            effective_encryption,
        )
        if provider_override:
            if effective_encryption and policy_provider and provider_override != policy_provider:
                raise ValueError(
                    f"provider override '{provider_override}' conflicts with policy-required provider '{policy_provider}'"
                )
            return EffectiveMappingPolicy(
                require_encryption=require_encryption,
                encryption_provider=provider_override,
                matched_patterns=tuple(sorted(set(matched_patterns))),
            )
        return EffectiveMappingPolicy(
            require_encryption=require_encryption,
            encryption_provider=policy_provider,
            matched_patterns=tuple(sorted(set(matched_patterns))),
        )



def load_policy(path: Path | None) -> MaskPolicy:
    if path is None:
        return MaskPolicy()
    raw = path.read_text(encoding='utf-8')
    try:
        return MaskPolicy.from_dict(json.loads(raw))
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(raw) or {}
        return MaskPolicy.from_dict(parsed if isinstance(parsed, dict) else {})
    except ModuleNotFoundError:
        parsed = _load_simple_yaml(raw)
        return MaskPolicy.from_dict(parsed)



def _load_mapping_rules(raw_rules: object) -> list[MappingRulePolicy]:
    rules: list[MappingRulePolicy] = []
    if isinstance(raw_rules, dict):
        for index, (pattern, payload) in enumerate(raw_rules.items()):
            if not isinstance(payload, dict):
                continue
            rules.append(
                MappingRulePolicy(
                    pattern=_normalize_pattern(str(pattern)),
                    require_encryption=(
                        bool(payload.get('require_encryption')) if payload.get('require_encryption') is not None else None
                    ),
                    encryption_provider=(
                        str(payload.get('encryption_provider'))
                        if payload.get('encryption_provider') is not None
                        else None
                    ),
                    order=index,
                )
            )
        return rules
    if isinstance(raw_rules, list):
        for index, payload in enumerate(raw_rules):
            if not isinstance(payload, dict) or 'pattern' not in payload:
                continue
            rules.append(
                MappingRulePolicy(
                    pattern=_normalize_pattern(str(payload.get('pattern'))),
                    require_encryption=(
                        bool(payload.get('require_encryption')) if payload.get('require_encryption') is not None else None
                    ),
                    encryption_provider=(
                        str(payload.get('encryption_provider'))
                        if payload.get('encryption_provider') is not None
                        else None
                    ),
                    order=index,
                )
            )
    return rules




def _normalize_pattern(pattern: str) -> str:
    if pattern.startswith(("'", '"')) and pattern.endswith(("'", '"')) and len(pattern) >= 2:
        return pattern[1:-1]
    return pattern

def _resolve_policy_provider(
    matched_specific_providers: set[str],
    default_provider: str | None,
    effective_encryption: bool,
) -> str | None:
    if not effective_encryption:
        return next(iter(matched_specific_providers), default_provider)
    if len(matched_specific_providers) > 1:
        providers = ', '.join(sorted(matched_specific_providers))
        raise ValueError(f'conflicting mapping encryption providers required by policy: {providers}')
    if matched_specific_providers:
        return next(iter(matched_specific_providers))
    return default_provider or DEFAULT_PROVIDER_ID



def _select_mapping_rule(rules: list[MappingRulePolicy], relative_path: str) -> MappingRulePolicy | None:
    matched = [rule for rule in rules if _matches_path(relative_path, rule.pattern)]
    if not matched:
        return None
    return max(matched, key=lambda rule: (_pattern_specificity(rule.pattern), rule.order))



def _matches_path(relative_path: str, pattern: str) -> bool:
    path_name = Path(relative_path).name
    from fnmatch import fnmatch

    return (
        fnmatch(relative_path, pattern)
        or fnmatch(f'./{relative_path}', pattern)
        or ('/' not in pattern and fnmatch(path_name, pattern))
    )



def _pattern_specificity(pattern: str) -> int:
    return len(pattern.replace('*', '').replace('?', ''))



def _load_simple_yaml(raw: str) -> dict[str, object]:
    rows: list[tuple[int, str]] = []
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip(' '))
        rows.append((indent, line.strip()))
    if not rows:
        return {}
    parsed, _ = _parse_block(rows, 0, rows[0][0])
    return parsed if isinstance(parsed, dict) else {}



def _parse_block(rows: list[tuple[int, str]], start: int, indent: int) -> tuple[object, int]:
    if start >= len(rows):
        return {}, start
    if rows[start][1].startswith('- '):
        items: list[object] = []
        index = start
        while index < len(rows):
            current_indent, content = rows[index]
            if current_indent < indent or current_indent != indent or not content.startswith('- '):
                break
            payload = content[2:].strip()
            if not payload:
                child, index = _parse_block(rows, index + 1, indent + 2)
                items.append(child)
                continue
            items.append(_parse_scalar(payload))
            index += 1
        return items, index
    mapping: dict[str, object] = {}
    index = start
    while index < len(rows):
        current_indent, content = rows[index]
        if current_indent < indent or current_indent != indent or content.startswith('- '):
            break
        key, value = _split_key_value(content)
        if value is None:
            if index + 1 < len(rows) and rows[index + 1][0] > current_indent:
                child, index = _parse_block(rows, index + 1, rows[index + 1][0])
                mapping[key] = child
            else:
                mapping[key] = {}
                index += 1
            continue
        mapping[key] = _parse_scalar(value)
        index += 1
    return mapping, index



def _split_key_value(content: str) -> tuple[str, str | None]:
    if ':' not in content:
        return content, None
    key, value = content.split(':', 1)
    value = value.strip()
    return key.strip(), value if value else None



def _parse_scalar(value: str) -> object:
    lowered = value.lower()
    if lowered == 'true':
        return True
    if lowered == 'false':
        return False
    if lowered in {'null', 'none'}:
        return None
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
