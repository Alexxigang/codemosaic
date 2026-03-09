# Release Playbook

## Local dry run

```bash
python -m unittest discover -s tests -v
python scripts/generate_release_assets.py --encrypt-mapping --clean
```

This produces a release asset bundle under `dist/release-assets/` with:

- packaged VSIX
- demo outputs
- `release-manifest.json`
- `SHA256SUMS.txt`
- `release-summary.md`
- `release-page.md`
- `screenshot-manifest.json`

## Tag-based release

1. Review `RELEASE_CHECKLIST.md`
2. Commit final changes
3. Create a tag such as `v0.1.0`
4. Push the tag
5. GitHub Actions workflow `release-vscode-extension.yml` uploads:
   - VSIX
   - checksums
   - release summary

## Recommended release page attachments

- `dist/release-assets/vsix/*.vsix`
- `dist/release-assets/SHA256SUMS.txt`
- `dist/release-assets/release-summary.md`
- `dist/release-assets/release-page.md`
- `dist/release-assets/demo-output/demo-summary.md`

## Product narrative for release notes

Lead with this story:

1. Teams want to use external AI tools without sending raw proprietary code
2. Masking is necessary but not sufficient
3. CodeMosaic adds semantic leakage analysis and a policy gate before export
4. The VS Code prototype turns that into a visible developer workflow

## Demo checklist for launch material

- Show a masked workspace being generated
- Show a leakage report with highest-risk files
- Show `Build AI Bundle` succeeding
- Show `Safe Export Bundle` being blocked by policy
- Show the Runs view surfacing `Leakage gate: BLOCKED`

## Suggested visuals to pin on release notes

- `assets/demo/workflow-overview.svg`
- `assets/demo/vscode-runs-view.svg`
- `assets/demo/safe-export-gate.svg`
- `docs/landing-page.md`

## Static site note

The static site source lives in `docs/site` and can be validated locally with:

```bash
python scripts/build_site.py --clean-assets
```

Automated GitHub Pages deployment is intentionally paused for now in favor of a lighter `site-check` workflow. This keeps repository health stable while the product and release story continue to evolve.
