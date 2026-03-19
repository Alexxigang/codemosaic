# Internal AI Coding Playbook

## Goal

This playbook is for companies that want to let internal teams use external AI coding tools without treating the raw source repository as directly exportable.

The operating model is:

- raw code stays local
- CodeMosaic prepares a governed masked workspace
- external AI only sees the masked bundle or masked patch context
- mapping, keys, and audit evidence stay under local control

## Where this framework fits

Use CodeMosaic when you want to answer a narrower, safer question than:

> Can we send our internal repo to an external AI tool?

The question becomes:

> Can we send this masked, policy-gated, locally auditable representation of the repo to an external AI tool right now?

## Recommended repository tiers

### Tier 1: General internal application repos

Recommended preset:

```bash
python -m codemosaic setup-workspace ./repo --preset balanced-ai-gateway --key-prefix app-team
```

Use for:

- standard internal backend services
- internal admin tools
- front-end application repos
- non-critical automation

### Tier 2: Sensitive internal repos

Recommended preset:

```bash
python -m codemosaic setup-workspace ./repo --preset strict-ai-gateway --key-prefix sensitive-team
```

Use for:

- internal data services
- auth-adjacent modules
- finance-adjacent business logic
- higher-sensitivity shared libraries

### Tier 3: Core or algorithm-heavy repos

Recommended preset:

```bash
python -m codemosaic setup-workspace ./repo --preset enterprise-core-ai-gateway --key-prefix core-team
```

Use for:

- core algorithms
- pricing and risk logic
- internal platform control planes
- high-governance repositories that require encrypted mappings and signed unmask flows by default

## Standard operating flow

### 1) Bootstrap the workspace once

```bash
python -m codemosaic setup-workspace ./repo --preset enterprise-core-ai-gateway --key-prefix core-team
```

What this gives you:

- `policy.codemosaic.yaml`
- `.codemosaic/key-registry.json`
- local managed key files
- encrypted mapping as the default persistence mode
- signed unmask expectations for core workflows

### 2) Scan and mask before using external AI

```bash
python -m codemosaic scan ./repo --policy ./repo/policy.codemosaic.yaml --output scan-report.json
python -m codemosaic mask ./repo --policy ./repo/policy.codemosaic.yaml
```

### 3) Check semantic leakage before exporting

```bash
python -m codemosaic leakage-report ./repo.masked --policy ./repo/policy.codemosaic.yaml --output leakage-report.json
python -m codemosaic bundle ./repo.masked --policy ./repo/policy.codemosaic.yaml --output ai-bundle.md --leakage-report leakage-report.json --fail-on-threshold
```

Interpretation:

- if `bundle` succeeds, the current masked export is within the configured leakage budget
- if `bundle` fails with the leakage gate, the repo content is still too revealing under current policy

### 4) Use external AI on the masked representation only

Recommended uses:

- refactoring suggestions
- test generation
- patch drafting
- bug triage
- code explanation on masked files

Avoid sending directly:

- full core algorithm implementations
- internal secrets or live config
- raw infrastructure topology
- customer-sensitive transformation logic

### 5) Translate and review incoming AI patches locally

```bash
python -m codemosaic unmask-patch ./masked-response.patch --mapping ./repo/.codemosaic/runs/<run-id>/mapping.enc.json --policy ./repo/policy.codemosaic.yaml --output translated.patch
python -m codemosaic apply translated.patch --target ./repo --check
```

## What risk still remains

CodeMosaic reduces risk a lot, but does not remove it entirely.

### Residual risks

- semantic leakage can still remain even after masking
- repeated exports across multiple conversations can reveal more than one export alone
- AI-generated patches can contain bad assumptions or unsafe logic
- users can still bypass the process and paste raw code manually
- any external model call still sends some code-derived information to a third party

## Recommended company guardrails

For internal rollout, combine the tool with process rules:

- require policy-backed exports for approved repos
- block raw copy/paste into external AI tools for core repositories
- require human review before applying translated patches
- audit recent masking runs regularly with `audit-runs`
- keep key files and `.codemosaic/` artifacts out of normal sharing paths

## Example verification commands

Verify that the mapping used for patch translation is signed and valid:

```bash
python -m codemosaic verify-mapping ./.codemosaic/runs/<run-id>/mapping.enc.json --signing-key-id core-team-signing --signing-key-registry ./.codemosaic/key-registry.json --require-signature
```

Audit recent runs:

```bash
python -m codemosaic audit-runs ./repo --signing-key-id core-team-signing --signing-key-registry ./repo/.codemosaic/key-registry.json --output run-audit.json
```

Export local operator evidence:

```bash
python -m codemosaic audit-events ./repo --limit 50 --output audit-events.json
```

## Suggested rollout order

1. Start with one non-core repo using `balanced-ai-gateway`
2. Move to one sensitive repo using `strict-ai-gateway`
3. Introduce `enterprise-core-ai-gateway` for the highest-governance repositories
4. Add CI leakage gates for the repos that pass pilot review
5. Document who is allowed to export which masked contexts to which external AI tools
