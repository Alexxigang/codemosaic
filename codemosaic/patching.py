from __future__ import annotations

import re
import subprocess
from pathlib import Path

from codemosaic.mapping import load_mapping_payload


def load_reverse_mapping(mapping_file: Path, passphrase: str | None = None) -> dict[str, str]:
    payload = load_mapping_payload(mapping_file, passphrase=passphrase)
    reverse = payload.get("masked_to_original", {})
    return {str(key): str(value) for key, value in reverse.items()} if isinstance(reverse, dict) else {}


def translate_patch_text(patch_text: str, reverse_mapping: dict[str, str]) -> str:
    if not reverse_mapping:
        return patch_text
    pattern = re.compile(
        "|".join(re.escape(token) for token in sorted(reverse_mapping, key=len, reverse=True))
    )
    return pattern.sub(lambda match: reverse_mapping[match.group(0)], patch_text)


def translate_patch_file(
    patch_file: Path,
    mapping_file: Path,
    output_file: Path,
    passphrase: str | None = None,
) -> Path:
    translated = translate_patch_text(
        patch_file.read_text(encoding="utf-8"),
        load_reverse_mapping(mapping_file, passphrase=passphrase),
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(translated, encoding="utf-8")
    return output_file


def apply_patch_file(
    patch_file: Path,
    target_root: Path,
    check_only: bool = False,
    three_way: bool = False,
) -> None:
    command = ["git", "-C", str(target_root), "apply"]
    if check_only:
        command.append("--check")
    if three_way:
        command.append("--3way")
    command.append(str(patch_file))
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git apply failed"
        raise RuntimeError(message)
