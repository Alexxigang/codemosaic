# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added
- Semantic leakage analysis after masking via `leakage-report`
- `Leakage Budget Gate` to block unsafe exports before sharing masked code with external AI
- VS Code command `CodeMosaic: Safe Export Bundle`
- Runs view gate status items such as `Leakage gate: PASS` and `Leakage gate: BLOCKED`
- Demo workflow outputs for leakage reports and safe export decisions
- Release asset narrative focused on `AI Code Privacy Gateway`
- Static product site under `docs/site/`
- GitHub Pages deployment workflow

### Changed
- Product positioning now emphasizes export governance, not only masking
- Demo and release assets now highlight blocked safe-export scenarios

## v0.1.0

### Added
- CLI prototype with `scan`, `mask`, `bundle`, `unmask-patch`, and `apply`
- JS/TS masking support in addition to Python masking
- Optional mapping encryption and rekey workflows
- VS Code prototype extension and VSIX packaging workflow
