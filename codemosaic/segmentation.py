from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

from codemosaic.models import RunReport
from codemosaic.policy import EffectiveMappingPolicy, MaskPolicy
from codemosaic.workspace import collect_maskable_relative_paths, mask_workspace


@dataclass(frozen=True, slots=True)
class MaskSegment:
    segment_id: str
    label: str
    relative_paths: tuple[str, ...]
    effective_mapping: EffectiveMappingPolicy

    def to_dict(self) -> dict[str, object]:
        return {
            'segment_id': self.segment_id,
            'label': self.label,
            'file_count': len(self.relative_paths),
            'files': list(self.relative_paths),
            'mapping': {
                'require_encryption': self.effective_mapping.require_encryption,
                'encryption_provider': self.effective_mapping.encryption_provider,
                'matched_patterns': list(self.effective_mapping.matched_patterns),
            },
        }


@dataclass(frozen=True, slots=True)
class SegmentedMaskResult:
    source_root: str
    output_root: str
    segments: tuple[MaskSegment, ...]
    reports: tuple[RunReport, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            'source_root': self.source_root,
            'output_root': self.output_root,
            'segment_count': len(self.segments),
            'segments': [segment.to_dict() for segment in self.segments],
            'runs': [report.to_dict() for report in self.reports],
        }



def plan_mask_segments(source_root: Path, output_root: Path, policy: MaskPolicy) -> list[MaskSegment]:
    relative_paths = collect_maskable_relative_paths(source_root, output_root, policy)
    grouped: dict[tuple[bool, str | None, tuple[str, ...]], list[str]] = {}
    effective_by_key: dict[tuple[bool, str | None, tuple[str, ...]], EffectiveMappingPolicy] = {}
    for relative_path in relative_paths:
        effective = policy.resolve_mapping_policy([relative_path])
        key = (
            effective.require_encryption,
            effective.encryption_provider,
            tuple(effective.matched_patterns),
        )
        grouped.setdefault(key, []).append(relative_path)
        effective_by_key[key] = effective
    segments: list[MaskSegment] = []
    for index, key in enumerate(sorted(grouped, key=lambda item: (_segment_sort_key(item), item)), start=1):
        effective = effective_by_key[key]
        files = tuple(sorted(grouped[key]))
        label = _build_segment_label(index, effective)
        segments.append(
            MaskSegment(
                segment_id=label,
                label=label,
                relative_paths=files,
                effective_mapping=effective,
            )
        )
    return segments



def mask_segmented_workspace(
    source_root: Path,
    output_root: Path,
    policy: MaskPolicy,
    run_id_prefix: str | None = None,
    mapping_passphrase: str | None = None,
    mapping_encryption_provider: str | None = None,
) -> SegmentedMaskResult:
    segments = plan_mask_segments(source_root, output_root, policy)
    reports: list[RunReport] = []
    output_root.mkdir(parents=True, exist_ok=True)
    for index, segment in enumerate(segments, start=1):
        segment_policy = _build_segment_policy(policy, segment.relative_paths)
        run_id = f'{run_id_prefix or "segment"}-{index:02d}-{segment.segment_id}'
        segment_output_root = output_root / segment.segment_id
        segment_passphrase = mapping_passphrase if (mapping_passphrase or segment.effective_mapping.require_encryption) else None
        segment_provider = mapping_encryption_provider or segment.effective_mapping.encryption_provider
        report = mask_workspace(
            source_root,
            segment_output_root,
            segment_policy,
            run_id=run_id,
            mapping_passphrase=segment_passphrase,
            mapping_encryption_provider=segment_provider,
        )
        reports.append(report)
    return SegmentedMaskResult(
        source_root=str(source_root),
        output_root=str(output_root),
        segments=tuple(segments),
        reports=tuple(reports),
    )



def write_segment_plan(path: Path, source_root: Path, output_root: Path, segments: list[MaskSegment]) -> Path:
    payload = {
        'source_root': str(source_root),
        'output_root': str(output_root),
        'segment_count': len(segments),
        'segments': [segment.to_dict() for segment in segments],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return path



def _build_segment_policy(base_policy: MaskPolicy, relative_paths: tuple[str, ...]) -> MaskPolicy:
    policy = copy.deepcopy(base_policy)
    policy.paths.include = list(relative_paths)
    policy.workspace.copy_unmatched = False
    return policy



def _segment_sort_key(key: tuple[bool, str | None, tuple[str, ...]]) -> tuple[int, str, str]:
    requires_encryption, provider, patterns = key
    return (0 if requires_encryption else 1, provider or '', '|'.join(patterns))



def _build_segment_label(index: int, effective: EffectiveMappingPolicy) -> str:
    parts = [f'segment-{index:02d}']
    parts.append('enc' if effective.require_encryption else 'plain')
    if effective.encryption_provider:
        parts.append(effective.encryption_provider)
    elif not effective.require_encryption:
        parts.append('default')
    if effective.matched_patterns:
        parts.append(_slugify(effective.matched_patterns[0]))
    return '-'.join(part for part in parts if part)



def _slugify(value: str) -> str:
    normalized = re.sub(r'[^a-zA-Z0-9]+', '-', value).strip('-').lower()
    return normalized[:40] or 'rule'
