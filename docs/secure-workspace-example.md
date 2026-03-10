# Secure Workspace Example

## What problem this solves

If you already know your team wants to use external AI coding tools, the fastest safe starting point is no longer:

1. write a policy by hand
2. generate keys separately
3. register key sources separately
4. hope the workspace is wired correctly

Now you can bootstrap a usable secure workspace in one command.

## Recommended command

```bash
python -m codemosaic setup-workspace ./your-repo --preset balanced-ai-gateway --key-prefix team-dev
```

## What it creates

After the command completes, the workspace contains:

- `policy.codemosaic.yaml`
- `.codemosaic/key-registry.json`
- `.codemosaic/keys/team-dev-mapping.key`
- `.codemosaic/keys/team-dev-signing.key`
- policy references to the local registry and managed key ids
- `require_encryption: true` for mapping persistence
- `require_signature_for_unmask: true` when signing is enabled

## What the effect is

The generated policy is immediately usable by normal CLI flows.

Example:

```bash
python -m codemosaic mask ./your-repo --policy ./your-repo/policy.codemosaic.yaml
```

Effect:

- CodeMosaic automatically resolves the mapping key from `.codemosaic/key-registry.json`
- the run writes `mapping.enc.json` instead of plain `mapping.json`
- later flows like `verify-mapping`, `audit-runs`, and guarded `unmask-patch` can use the same local setup

## End-to-end example

You can generate a complete demo output package locally:

```bash
python scripts/run_secure_onboarding_demo.py --clean
```

This writes a worked example under `dist/secure-onboarding-demo` including:

- `secure-onboarding-summary.json`
- `secure-onboarding-summary.md`
- a copied demo repo with generated onboarding files
- a masked workspace with encrypted mapping output
- a leakage report for the masked workspace

## Example interpretation

A typical successful run means:

- the repo is now policy-backed instead of ad-hoc
- key material remains local in the workspace vault area
- developers can run `mask` without remembering extra key arguments
- review and audit flows have stable key ids and local evidence

## VS Code version

If you prefer the editor flow, use:

- `CodeMosaic: Initialize Secure Workspace`

That guided flow asks for:

- the preset to start from
- the policy output path
- the managed key prefix
- whether to include signing keys

Then it updates `codemosaic.policyPath` automatically and opens the generated policy file.
