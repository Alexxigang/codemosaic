# Release Checklist

## Pre-release validation

- [ ] Run `python -m unittest discover -s tests -v`
- [ ] Run `node --check extensions/vscode/extension.js`
- [ ] Run `python scripts/package_vscode_extension.py --overwrite`
- [ ] Run `python scripts/generate_release_assets.py --encrypt-mapping --clean`
- [ ] Open `dist/release-assets/release-page.md`
- [ ] Open `dist/release-assets/demo-output/demo-summary.md`
- [ ] Confirm demo shows `Safe Export Bundle` blocked or passed as expected
- [ ] Review `docs/site/index.html` and `docs/landing-page.md`

## Release packaging

- [ ] Confirm the VSIX exists under `dist/release-assets/vsix/`
- [ ] Confirm `SHA256SUMS.txt` exists and includes the VSIX
- [ ] Confirm `release-summary.md` and `release-page.md` are current
- [ ] Update `CHANGELOG.md`
- [ ] Create a tag like `v0.1.0`
- [ ] Push the tag

## Post-release checks

- [ ] Confirm GitHub Actions uploaded release assets
- [ ] Confirm GitHub Pages deploy succeeded
- [ ] Verify the static site under `docs/site/` renders correctly on Pages
- [ ] Verify release notes mention `Leakage Budget Gate` and `Safe Export Bundle`
