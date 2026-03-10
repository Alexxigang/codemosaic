from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PolicyPreset:
    preset_id: str
    filename: str
    description: str
    recommended_for: tuple[str, ...]

    @property
    def path(self) -> Path:
        return presets_root() / self.filename

    @property
    def aliases(self) -> tuple[str, ...]:
        stem = Path(self.filename).stem
        return (self.preset_id, self.filename, stem)


_PRESET_CATALOG: tuple[PolicyPreset, ...] = (
    PolicyPreset(
        preset_id='strict-ai-gateway',
        filename='strict-ai-gateway.yaml',
        description='Encrypted mappings plus near-zero leakage budgets for critical repositories.',
        recommended_for=('core algorithms', 'finance', 'security-sensitive services', 'internal platforms'),
    ),
    PolicyPreset(
        preset_id='balanced-ai-gateway',
        filename='balanced-ai-gateway.yaml',
        description='Default starting point for most application repositories using external AI tools.',
        recommended_for=('product apps', 'general services', 'pilot rollouts', 'cross-functional teams'),
    ),
    PolicyPreset(
        preset_id='public-sdk-ai-gateway',
        filename='public-sdk-ai-gateway.yaml',
        description='Looser leakage budget for SDKs, examples, and semi-public integration code.',
        recommended_for=('SDKs', 'sample repos', 'developer docs', 'integration examples'),
    ),
)


def presets_root() -> Path:
    return Path(__file__).resolve().parents[1] / 'presets'


def list_policy_presets() -> tuple[PolicyPreset, ...]:
    return _PRESET_CATALOG


def resolve_policy_preset(name: str) -> PolicyPreset:
    normalized = name.strip().lower()
    for preset in _PRESET_CATALOG:
        for alias in preset.aliases:
            if normalized == alias.lower():
                return preset
    available = ', '.join(preset.preset_id for preset in _PRESET_CATALOG)
    raise ValueError(f'unknown policy preset: {name}. available presets: {available}')


def init_policy_from_preset(
    preset_name: str,
    output_path: Path,
    *,
    force: bool = False,
) -> PolicyPreset:
    preset = resolve_policy_preset(preset_name)
    source_path = preset.path
    if not source_path.exists():
        raise FileNotFoundError(f'missing preset file: {source_path}')
    target_path = output_path.resolve()
    if target_path.exists() and not force:
        raise ValueError(f'output already exists: {target_path}')
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')
    return preset
