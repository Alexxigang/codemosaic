from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from codemosaic.crypto import DEFAULT_PROVIDER_ID, MANAGED_PROVIDER_ID


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
class MappingKeyManagementPolicy:
    source: str | None = None
    reference: str | None = None
    key_id: str | None = None


@dataclass(slots=True)
class MappingPolicy:
    require_encryption: bool = False
    encryption_provider: str | None = None
    key_management: MappingKeyManagementPolicy = field(default_factory=MappingKeyManagementPolicy)
    rules: list[MappingRulePolicy] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EffectiveMappingPolicy:
    require_encryption: bool
    encryption_provider: str | None
    matched_patterns: tuple[str, ...] = ()


@dataclass(slots=True)
class LeakageRulePolicy:
    pattern: str
    max_total_score: int | None = None
    max_file_score: int | None = None
    order: int = 0


@dataclass(slots=True)
class LeakagePolicy:
    max_total_score: int | None = None
    max_file_score: int | None = None
    rules: list[LeakageRulePolicy] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EffectiveLeakageFilePolicy:
    max_file_score: int | None
    matched_pattern: str | None = None


@dataclass(slots=True)
class MaskPolicy:
    paths: PathPolicy = field(default_factory=PathPolicy)
    identifiers: IdentifierPolicy = field(default_factory=IdentifierPolicy)
    strings: StringPolicy = field(default_factory=StringPolicy)
    comments: CommentPolicy = field(default_factory=CommentPolicy)
    workspace: WorkspacePolicy = field(default_factory=WorkspacePolicy)
    mapping: MappingPolicy = field(default_factory=MappingPolicy)
    leakage: LeakagePolicy = field(default_factory=LeakagePolicy)
    source_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> 'MaskPolicy':
        paths = data.get('paths', {}) if isinstance(data, dict) else {}
        identifiers = data.get('identifiers', {}) if isinstance(data, dict) else {}
        strings = data.get('strings', {}) if isinstance(data, dict) else {}
        comments = data.get('comments', {}) if isinstance(data, dict) else {}
        workspace = data.get('workspace', {}) if isinstance(data, dict) else {}
        mapping = data.get('mapping', {}) if isinstance(data, dict) else {}
        leakage = data.get('leakage', {}) if isinstance(data, dict) else {}
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
                key_management=MappingKeyManagementPolicy(
                    source=(
                        str(mapping.get('key_management', {}).get('source'))
                        if isinstance(mapping, dict)
                        and isinstance(mapping.get('key_management'), dict)
                        and mapping.get('key_management', {}).get('source') is not None
                        else None
                    ),
                    reference=(
                        str(mapping.get('key_management', {}).get('reference'))
                        if isinstance(mapping, dict)
                        and isinstance(mapping.get('key_management'), dict)
                        and mapping.get('key_management', {}).get('reference') is not None
                        else None
                    ),
                    key_id=(
                        str(mapping.get('key_management', {}).get('key_id'))
                        if isinstance(mapping, dict)
                        and isinstance(mapping.get('key_management'), dict)
                        and mapping.get('key_management', {}).get('key_id') is not None
                        else None
                    ),
                ),
                rules=_load_mapping_rules(mapping.get('rules', {})) if isinstance(mapping, dict) else [],
            ),
            leakage=LeakagePolicy(
                max_total_score=_optional_int(leakage.get('max_total_score')) if isinstance(leakage, dict) else None,
                max_file_score=_optional_int(leakage.get('max_file_score')) if isinstance(leakage, dict) else None,
                rules=_load_leakage_rules(leakage.get('rules', {})) if isinstance(leakage, dict) else [],
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
        effective_encryption = require_encryption or encryption_requested
        default_provider = provider_override or self.mapping.encryption_provider
        if default_provider is None and self.mapping.key_management.source:
            default_provider = MANAGED_PROVIDER_ID
        effective_provider = _resolve_policy_provider(
            matched_specific_providers,
            default_provider,
            effective_encryption,
        )
        if require_encryption and not encryption_requested:
            return EffectiveMappingPolicy(
                require_encryption=True,
                encryption_provider=effective_provider,
                matched_patterns=tuple(dict.fromkeys(matched_patterns)),
            )
        return EffectiveMappingPolicy(
            require_encryption=effective_encryption,
            encryption_provider=effective_provider,
            matched_patterns=tuple(dict.fromkeys(matched_patterns)),
        )

    def resolve_leakage_file_policy(self, relative_path: str) -> EffectiveLeakageFilePolicy:
        rule = _select_leakage_rule(self.leakage.rules, relative_path)
        max_file_score = self.leakage.max_file_score
        if rule is not None and rule.max_file_score is not None:
            max_file_score = rule.max_file_score
        return EffectiveLeakageFilePolicy(
            max_file_score=max_file_score,
            matched_pattern=rule.pattern if rule is not None else None,
        )

    def matching_leakage_rules(self, relative_path: str) -> tuple[LeakageRulePolicy, ...]:
        return tuple(rule for rule in self.leakage.rules if _matches_path(relative_path, rule.pattern))



def load_policy(path: Path | None) -> MaskPolicy:
    if path is None:
        return MaskPolicy()
    raw = path.read_text(encoding='utf-8')
    try:
        policy = MaskPolicy.from_dict(json.loads(raw))
    except json.JSONDecodeError:
        try:
            parsed = _load_simple_yaml(raw)
        except ValueError as exc:
            raise ValueError(f'failed to parse policy file {path}: {exc}') from exc
        if not isinstance(parsed, dict):
            raise ValueError(f'failed to parse policy file {path}: unsupported structure')
        policy = MaskPolicy.from_dict(parsed)
    policy.source_path = str(path.resolve())
    return policy



def _load_mapping_rules(data: object) -> list[MappingRulePolicy]:
    rules: list[MappingRulePolicy] = []
    if isinstance(data, dict):
        for index, (pattern, payload) in enumerate(data.items()):
            payload = payload if isinstance(payload, dict) else {}
            rules.append(
                MappingRulePolicy(
                    pattern=_normalize_pattern(str(pattern)),
                    require_encryption=(
                        bool(payload.get('require_encryption'))
                        if 'require_encryption' in payload
                        else None
                    ),
                    encryption_provider=(
                        str(payload.get('encryption_provider'))
                        if payload.get('encryption_provider') is not None
                        else None
                    ),
                    order=index,
                )
            )
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            pattern = item.get('pattern')
            if pattern is None:
                continue
            rules.append(
                MappingRulePolicy(
                    pattern=_normalize_pattern(str(pattern)),
                    require_encryption=(
                        bool(item.get('require_encryption'))
                        if 'require_encryption' in item
                        else None
                    ),
                    encryption_provider=(
                        str(item.get('encryption_provider'))
                        if item.get('encryption_provider') is not None
                        else None
                    ),
                    order=index,
                )
            )
    return rules



def _load_leakage_rules(data: object) -> list[LeakageRulePolicy]:
    rules: list[LeakageRulePolicy] = []
    if isinstance(data, dict):
        for index, (pattern, payload) in enumerate(data.items()):
            payload = payload if isinstance(payload, dict) else {}
            rules.append(
                LeakageRulePolicy(
                    pattern=_normalize_pattern(str(pattern)),
                    max_total_score=_optional_int(payload.get('max_total_score')),
                    max_file_score=_optional_int(payload.get('max_file_score')),
                    order=index,
                )
            )
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            pattern = item.get('pattern')
            if pattern is None:
                continue
            rules.append(
                LeakageRulePolicy(
                    pattern=_normalize_pattern(str(pattern)),
                    max_total_score=_optional_int(item.get('max_total_score')),
                    max_file_score=_optional_int(item.get('max_file_score')),
                    order=index,
                )
            )
    return rules



def _normalize_pattern(pattern: str) -> str:
    if pattern.startswith(("'", '"')) and pattern.endswith(("'", '"')) and len(pattern) >= 2:
        return pattern[1:-1]
    return pattern



def _optional_int(value: object) -> int | None:
    if value is None or value == '':
        return None
    return int(value)



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



def _select_leakage_rule(rules: list[LeakageRulePolicy], relative_path: str) -> LeakageRulePolicy | None:
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
