from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codemosaic.mapping import rewrap_mapping_file


@dataclass(frozen=True, slots=True)
class RunMappingInfo:
    run_id: str
    run_directory: Path
    mapping_file: Path
    encrypted: bool
    sort_time: float



def list_run_mappings(workspace_root: Path) -> list[RunMappingInfo]:
    runs_root = workspace_root / '.codemosaic' / 'runs'
    if not runs_root.exists():
        return []
    items: list[RunMappingInfo] = []
    for entry in runs_root.iterdir():
        if not entry.is_dir():
            continue
        mapping_file = _find_mapping_file(entry)
        if mapping_file is None:
            continue
        items.append(
            RunMappingInfo(
                run_id=entry.name,
                run_directory=entry,
                mapping_file=mapping_file,
                encrypted=mapping_file.name.endswith('.enc.json'),
                sort_time=_safe_mtime(entry / 'report.json') or _safe_mtime(mapping_file) or _safe_mtime(entry),
            )
        )
    return sorted(items, key=lambda item: item.sort_time, reverse=True)



def rekey_run_mappings(
    workspace_root: Path,
    passphrase: str | None = None,
    new_passphrase: str | None = None,
    encryption_provider: str | None = None,
    limit: int | None = None,
    metadata_overrides: dict[str, object] | None = None,
) -> list[Path]:
    mappings = list_run_mappings(workspace_root)
    if limit is not None:
        mappings = mappings[:limit]
    if not mappings:
        return []
    outputs: list[Path] = []
    for mapping in mappings:
        outputs.append(
            rewrap_mapping_file(
                mapping.mapping_file,
                passphrase=passphrase if mapping.encrypted else None,
                new_passphrase=new_passphrase,
                encryption_provider=encryption_provider if new_passphrase else None,
                metadata_overrides=metadata_overrides,
            )
        )
    return outputs



def _find_mapping_file(run_directory: Path) -> Path | None:
    encrypted = run_directory / 'mapping.enc.json'
    if encrypted.exists():
        return encrypted
    plain = run_directory / 'mapping.json'
    if plain.exists():
        return plain
    return None



def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0
