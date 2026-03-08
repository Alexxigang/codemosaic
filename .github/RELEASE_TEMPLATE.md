# Release Notes Template

## Product Positioning

CodeMosaic is an **AI Code Privacy Gateway** for teams that want external AI coding help without sending raw proprietary code outside the workstation boundary.

## Highlights

- CLI improvements:
- Security/privacy improvements:
- VS Code extension improvements:
- Site / demo / release asset improvements:

## Why this release matters

- What changed in masking quality?
- What changed in semantic leakage analysis?
- What changed in `Leakage Budget Gate` or `Safe Export Bundle`?
- What changed in the product story, docs, or onboarding path?

## Included Capabilities

- Scan workspace for likely sensitive content
- Mask Python and JS/TS source before sharing with external AI tools
- Save mapping files locally, with optional passphrase protection
- Measure semantic leakage after masking
- Block unsafe exports with `Leakage Budget Gate`
- Use the VS Code prototype extension with runs explorer and safe export workflow
- Publish demo/release assets and GitHub Pages site

## Validation

- `python -m unittest discover -s tests -v`
- `python scripts/package_vscode_extension.py --overwrite`
- `python scripts/generate_release_assets.py --encrypt-mapping --clean`
- `python scripts/build_site.py --clean-assets`
- `node --check extensions/vscode/extension.js`

## Suggested attachments

- VSIX package
- `SHA256SUMS.txt`
- `release-summary.md`
- `release-page.md`
- `demo-summary.md`
- Site screenshots / social card

## Known Limitations

- No TypeScript AST masking yet
- Mapping encryption is still a standard-library prototype
- VS Code extension is still a prototype and not marketplace-published
