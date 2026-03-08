from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'docs' / 'site'
DEFAULT_ASSETS = [
    ROOT / 'assets' / 'demo' / 'workflow-overview.svg',
    ROOT / 'assets' / 'demo' / 'vscode-runs-view.svg',
    ROOT / 'assets' / 'demo' / 'safe-export-gate.svg',
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Sync static site assets for GitHub Pages.')
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--clean-assets', action='store_true')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_site(args.output_root.resolve(), clean_assets=args.clean_assets)
    print(args.output_root.resolve())
    return 0


def build_site(output_root: Path, clean_assets: bool = False) -> Path:
    assets_root = output_root / 'assets'
    output_root.mkdir(parents=True, exist_ok=True)
    assets_root.mkdir(parents=True, exist_ok=True)
    if clean_assets:
        for child in assets_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        assets_root.mkdir(parents=True, exist_ok=True)
    for source in DEFAULT_ASSETS:
        if not source.exists():
            raise FileNotFoundError(f'missing site asset source: {source}')
        target = assets_root / source.name
        shutil.copyfile(source, target)
    (output_root / '.nojekyll').write_text('', encoding='utf-8')
    return output_root


if __name__ == '__main__':
    raise SystemExit(main())
