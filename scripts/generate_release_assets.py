from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.package_vscode_extension import package_extension
from scripts.run_demo_workflow import run_demo_workflow

DEFAULT_OUTPUT = ROOT / 'dist' / 'release-assets'
DEFAULT_DEMO_SOURCE = ROOT / 'examples' / 'demo-repo'
DEFAULT_EXTENSION_DIR = ROOT / 'extensions' / 'vscode'
DEFAULT_SCREENSHOT_ASSETS = [
    ROOT / 'assets' / 'demo' / 'workflow-overview.svg',
    ROOT / 'assets' / 'demo' / 'vscode-runs-view.svg',
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Generate a release asset bundle for CodeMosaic.')
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--demo-source', type=Path, default=DEFAULT_DEMO_SOURCE)
    parser.add_argument('--extension-dir', type=Path, default=DEFAULT_EXTENSION_DIR)
    parser.add_argument('--encrypt-mapping', action='store_true')
    parser.add_argument('--passphrase', type=str, default='release-demo-passphrase')
    parser.add_argument('--version-suffix', type=str, default=None)
    parser.add_argument('--clean', action='store_true')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = generate_release_assets(
        output_root=args.output_root.resolve(),
        demo_source=args.demo_source.resolve(),
        extension_dir=args.extension_dir.resolve(),
        encrypt_mapping=args.encrypt_mapping,
        passphrase=args.passphrase if args.encrypt_mapping else None,
        version_suffix=args.version_suffix,
        clean=args.clean,
    )
    print(output)
    return 0


def generate_release_assets(
    output_root: Path,
    demo_source: Path,
    extension_dir: Path,
    encrypt_mapping: bool = False,
    passphrase: str | None = None,
    version_suffix: str | None = None,
    clean: bool = False,
) -> Path:
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    demo_output_root = output_root / 'demo-output'
    vsix_output_root = output_root / 'vsix'
    manifest_path = output_root / 'release-manifest.json'
    checksums_path = output_root / 'SHA256SUMS.txt'
    summary_path = output_root / 'release-summary.md'
    release_page_path = output_root / 'release-page.md'
    screenshot_manifest_path = output_root / 'screenshot-manifest.json'

    demo_summary = run_demo_workflow(
        source_root=demo_source,
        output_root=demo_output_root,
        encrypt_mapping=encrypt_mapping,
        passphrase=passphrase,
        clean=True,
    )
    vsix_path = package_extension(
        extension_dir=extension_dir,
        output_dir=vsix_output_root,
        version_suffix=version_suffix,
        overwrite=True,
    )

    screenshot_manifest = build_screenshot_manifest(output_root)
    screenshot_manifest_path.write_text(
        json.dumps(screenshot_manifest, indent=2, ensure_ascii=False),
        encoding='utf-8',
        newline='\n',
    )

    asset_paths = collect_asset_paths(output_root, vsix_path, demo_summary)
    summary_manifest = {
        'release_assets_root': str(output_root),
        'vsix_file': str(vsix_path),
        'demo_summary': demo_summary,
        'assets': {key: str(value) for key, value in asset_paths.items()},
        'checksums': {},
        'screenshot_manifest': screenshot_manifest,
    }
    summary_path.write_text(render_release_summary(summary_manifest), encoding='utf-8', newline='\n')
    release_page_path.write_text(render_release_page(summary_manifest), encoding='utf-8', newline='\n')
    checksum_targets = {
        key: value
        for key, value in asset_paths.items()
        if key not in {'release_manifest', 'checksums'}
    }
    checksums = {relative_path: sha256_file(path) for relative_path, path in checksum_targets.items()}
    manifest = {
        'release_assets_root': str(output_root),
        'vsix_file': str(vsix_path),
        'demo_summary': demo_summary,
        'assets': {key: str(value) for key, value in asset_paths.items()},
        'checksums': checksums,
        'screenshot_manifest': screenshot_manifest,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8', newline='\n')
    checksums_path.write_text(render_checksums(checksums), encoding='utf-8', newline='\n')
    summary_path.write_text(render_release_summary(manifest), encoding='utf-8', newline='\n')
    release_page_path.write_text(render_release_page(manifest), encoding='utf-8', newline='\n')
    return output_root


def collect_asset_paths(output_root: Path, vsix_path: Path, demo_summary: dict[str, object]) -> dict[str, Path]:
    return {
        'vsix': vsix_path,
        'demo_summary_json': output_root / 'demo-output' / 'demo-summary.json',
        'demo_summary_md': output_root / 'demo-output' / 'demo-summary.md',
        'release_manifest': output_root / 'release-manifest.json',
        'release_summary': output_root / 'release-summary.md',
        'release_page': output_root / 'release-page.md',
        'screenshot_manifest': output_root / 'screenshot-manifest.json',
        'checksums': output_root / 'SHA256SUMS.txt',
        'demo_scan_report': Path(str(demo_summary['scan_report_file'])),
        'demo_mapping': Path(str(demo_summary['mapping_file'])),
        'demo_bundle': Path(str(demo_summary['bundle_file'])),
    }


def build_screenshot_manifest(output_root: Path) -> dict[str, object]:
    items: list[dict[str, str]] = []
    for asset in DEFAULT_SCREENSHOT_ASSETS:
        items.append(
            {
                'label': asset.stem,
                'path': str(asset),
                'recommended_usage': 'Release page / README / demo walkthrough',
            }
        )
    return {
        'output_root': str(output_root),
        'recommended_assets': items,
        'notes': [
            'SVG assets are safe to attach directly to GitHub releases.',
            'For real product screenshots, replace these placeholders with captured editor images.',
            'Use docs/demo-walkthrough.md as the speaking guide while preparing screenshots.',
        ],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def render_checksums(checksums: dict[str, str]) -> str:
    lines = [f"{value}  {key}" for key, value in sorted(checksums.items())]
    return '\n'.join(lines) + '\n'


def render_release_summary(manifest: dict[str, object]) -> str:
    demo_summary = manifest['demo_summary']
    lines = [
        '# Release Asset Summary',
        '',
        f"- VSIX: `{manifest['vsix_file']}`",
        f"- Release manifest: `{manifest['assets']['release_manifest']}`",
        f"- Checksums: `{manifest['assets']['checksums']}`",
        f"- Release page draft: `{manifest['assets']['release_page']}`",
        '',
        '## Demo Outputs',
        '',
        f"- Demo summary: `{manifest['assets']['demo_summary_md']}`",
        f"- Scan report: `{manifest['assets']['demo_scan_report']}`",
        f"- Mapping: `{manifest['assets']['demo_mapping']}`",
        f"- AI bundle: `{manifest['assets']['demo_bundle']}`",
        '',
        '## Suggested Release Attachments',
        '',
        f"- `{Path(str(manifest['vsix_file'])).name}`",
        '- `SHA256SUMS.txt`',
        '- `release-summary.md`',
        '- `release-page.md`',
        '',
        '## Demo Snapshot',
        '',
    ]
    if isinstance(demo_summary, dict):
        lines.append(f"- Run id: `{demo_summary.get('run_id', '')}`")
        lines.append(f"- Mask stats: `{json.dumps(demo_summary.get('stats', {}), ensure_ascii=False)}`")
        scan_summary = demo_summary.get('scan_summary', {})
        if isinstance(scan_summary, dict):
            lines.append(f"- Scan findings: `{json.dumps(scan_summary.get('finding_counts', {}), ensure_ascii=False)}`")
    lines.extend([
        '',
        '## Install',
        '',
        '1. Download the `.vsix` file from the release assets',
        '2. In VS Code run `Extensions: Install from VSIX...`',
        '3. Open a workspace and click the `CodeMosaic` status bar entry',
    ])
    return '\n'.join(lines) + '\n'


def render_release_page(manifest: dict[str, object]) -> str:
    demo_summary = manifest['demo_summary']
    scan_summary = demo_summary.get('scan_summary', {}) if isinstance(demo_summary, dict) else {}
    screenshot_manifest = manifest.get('screenshot_manifest', {})
    screenshot_lines = []
    if isinstance(screenshot_manifest, dict):
        for item in screenshot_manifest.get('recommended_assets', []):
            if isinstance(item, dict):
                screenshot_lines.append(f"- `{item.get('path', '')}` — {item.get('recommended_usage', '')}")
    lines = [
        '# CodeMosaic Release Draft',
        '',
        '## Highlights',
        '',
        '- Local-first source masking workflow for external AI coding tools',
        '- Python and JS/TS masking support with optional encrypted mapping vaults',
        '- VS Code prototype extension with runs explorer and quick workflow entry point',
        '- Automated demo workflow and release asset generation for repeatable demos',
        '',
        '## What ships in this release',
        '',
        f"- VSIX package: `{Path(str(manifest['vsix_file'])).name}`",
        '- Local scan, mask, bundle, unmask-patch, and apply CLI commands',
        '- VS Code prototype extension with status bar entry and runs explorer',
        '- Demo repo and release-ready walkthrough assets',
        '',
        '## Validation summary',
        '',
        f"- Demo run id: `{demo_summary.get('run_id', '') if isinstance(demo_summary, dict) else ''}`",
        f"- Scan findings: `{json.dumps(scan_summary.get('finding_counts', {}), ensure_ascii=False) if isinstance(scan_summary, dict) else '{}'}`",
        f"- Mask stats: `{json.dumps(demo_summary.get('stats', {}), ensure_ascii=False) if isinstance(demo_summary, dict) else '{}'}`",
        '',
        '## Installation',
        '',
        '1. Download the `.vsix` file from the release assets',
        '2. In VS Code run `Extensions: Install from VSIX...`',
        '3. Open a workspace and click the `CodeMosaic` status bar entry',
        '',
        '## Suggested screenshots / visuals',
        '',
    ]
    lines.extend(screenshot_lines or ['- Replace placeholder SVGs with real editor screenshots before broad promotion'])
    lines.extend([
        '',
        '## Known limitations',
        '',
        '- TypeScript masking is not AST-based yet',
        '- Mapping encryption is still a standard-library prototype',
        '- VS Code extension is still a prototype and not marketplace-published',
    ])
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    raise SystemExit(main())
