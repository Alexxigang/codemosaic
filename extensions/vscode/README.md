# CodeMosaic VS Code Prototype

This folder contains a lightweight VS Code extension prototype for the local CodeMosaic workflow.

## Commands

- `CodeMosaic: Quick Workflow`
- `CodeMosaic: Initialize Secure Workspace`
- `CodeMosaic: Initialize Policy Preset`
- `CodeMosaic: Scan Workspace`
- `CodeMosaic: Analyze Semantic Leakage`
- `CodeMosaic: Mask Workspace`
- `CodeMosaic: Plan Segments`
- `CodeMosaic: Mask Segmented Workspace`
- `CodeMosaic: Safe Export Bundle`
- `CodeMosaic: Build AI Bundle`
- `CodeMosaic: Unmask Patch`
- `CodeMosaic: Rekey Mapping`
- `CodeMosaic: Rekey Recent Runs`
- `CodeMosaic: Show Encryption Providers`
- `CodeMosaic: Apply Patch`
- `CodeMosaic: Refresh Runs`

## Secure workspace bootstrap flow

`CodeMosaic: Initialize Secure Workspace` lets a team:

- choose a built-in policy preset
- write a workspace policy file
- generate managed mapping and signing keys
- register those keys for local CLI workflows
- update `codemosaic.policyPath` automatically
- open the generated file for immediate review

## Policy-only bootstrap flow

`CodeMosaic: Initialize Policy Preset` lets a team:

- choose a built-in policy preset
- write a workspace policy file
- update `codemosaic.policyPath` automatically
- open the generated file for immediate review

## Runs view

The Explorer includes a `CodeMosaic Runs` view for recent artifacts such as:

- latest `scan-report.json`
- latest `ai-bundle.md`
- latest leakage report and segment plan
- recent `.codemosaic/runs/<run-id>/` directories
- per-run mapping and report files

## Packaging

```bash
python scripts/package_vscode_extension.py --overwrite
```

The packaged `.vsix` file is written to `dist/` by default.
