# CodeMosaic

Language: **English** | [Chinese (Simplified)](README.zh-CN.md)

CodeMosaic is a local-first AI code privacy gateway for teams that want external AI coding help without sending raw proprietary source code outside the workstation boundary.

It is not just a secret redaction script. The project is designed as a practical closed loop:

`scan -> mask -> leakage-report -> safe export -> AI patch -> unmask/apply`

## Why this project is different

Most tools stop at one of these points:

- secret scanning
- one-way redaction
- prompt packaging

CodeMosaic goes further in three ways:

1. **Reversible workflow**
   - Mask code before it leaves the machine
   - Keep mappings local
   - Translate AI-generated patches back onto the original repo

2. **Semantic leakage control**
   - Measure how much business meaning still leaks after masking
   - Score risky files and risky paths
   - Block exports that still reveal too much context

3. **Policy-based key and export governance**
   - Require encrypted mappings for sensitive paths
   - Resolve key material from managed sources like env vars or files
   - Record key IDs for audit-friendly rotation workflows

That product angle is the core differentiator: **not only "did we hide secrets?" but also "is this masked code still safe enough to send?"**

## What exists today

### Core CLI

- `scan` for likely sensitive markers
- `mask` for masked workspace generation
- `mask-segmented` for multi-segment masking based on policy rules
- `plan-segments` to preview policy-derived masking groups
- `leakage-report` for semantic leakage scoring and gating
- `bundle` for Markdown context export to external AI tools
- `unmask-patch` to translate masked diffs back to original symbols
- `apply` to apply translated patches with `git apply`
- `rekey-mapping` and `rekey-runs` for mapping re-protection
- `generate-key` to create high-entropy managed mapping keys
- `register-key-source` and `list-key-sources` for workspace key registry management
- `list-providers` to inspect mapping encryption providers

### Privacy controls

- Local mapping vault under `.codemosaic/runs/...`
- Optional passphrase-based mapping protection
- Managed-key workflow with `managed-v1`
- Policy-backed key source references from env vars or files
- Key IDs recorded in mapping metadata and encrypted envelope headers
- Leakage budget thresholds for total and per-file risk
- Segment-aware masking rules for tighter sharing boundaries

### Product surface

- Python package and CLI
- VS Code prototype extension under `extensions/vscode`
- Release packaging scripts and demo assets
- Static site source under `docs/site`

## Quick start

### Requirements

- Python `3.11+`
- Git available locally for patch application flows
- Optional: Node.js + VS Code if you want the extension prototype

### 1) Scan a repository

```bash
python -m codemosaic scan ./your-repo --policy policy.sample.yaml --output scan-report.json
```

### 2) Generate a managed mapping key

```bash
python -m codemosaic generate-key --output ./.codemosaic/keys/team-dev.key
```

PowerShell:

```powershell
$env:CODEMOSAIC_MAPPING_KEY = Get-Content ./.codemosaic/keys/team-dev.key
```

### 3) Register the key source for the workspace

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
```

### 4) Create a masked workspace

```bash
python -m codemosaic mask ./your-repo --policy policy.sample.yaml
```

By default this creates:

- masked source at `./your-repo.masked`
- run artifacts at `./your-repo/.codemosaic/runs/<run-id>/`

### 5) Fallback: use a legacy passphrase flow

```powershell
$env:CODEMOSAIC_PASSPHRASE="change-me"
python -m codemosaic mask ./your-repo --policy policy.sample.yaml --encrypt-mapping --passphrase-env CODEMOSAIC_PASSPHRASE
```

### 6) Measure semantic leakage

```bash
python -m codemosaic leakage-report ./your-repo.masked --policy policy.sample.yaml --output leakage-report.json
```

To fail the command when thresholds are exceeded:

```bash
python -m codemosaic leakage-report ./your-repo.masked --policy policy.sample.yaml --fail-on-threshold
```

### 7) Build an AI bundle

```bash
python -m codemosaic bundle ./your-repo.masked --policy policy.sample.yaml --output ai-bundle.md --max-files 20 --max-chars 12000
```

### 8) Block unsafe exports automatically

```bash
python -m codemosaic bundle ./your-repo.masked --policy policy.sample.yaml --output ai-bundle.md --leakage-report leakage-report.json --fail-on-threshold
```

### 9) Translate an AI patch back

```bash
python -m codemosaic unmask-patch ./masked-response.patch --mapping ./your-repo/.codemosaic/runs/<run-id>/mapping.enc.json --key-env CODEMOSAIC_MAPPING_KEY --output translated.patch
python -m codemosaic apply translated.patch --target ./your-repo --check
python -m codemosaic apply translated.patch --target ./your-repo
```

## Key management model

CodeMosaic now supports a more product-like key workflow instead of relying only on ad-hoc passphrases. It can also resolve `key_id` entries from a local workspace key registry.

### `managed-v1`

`managed-v1` is a built-in provider designed for high-entropy key material generated by `generate-key`.

Recommended pattern:

- generate a random key once
- store it in a local secret store, env var, or protected file
- reference that source in policy
- attach a logical `key_id` for rotation tracking

### Policy-driven key resolution

`policy.sample.yaml` style:

```yaml
mapping:
  require_encryption: false
  encryption_provider: managed-v1
  key_management:
    source: env
    reference: CODEMOSAIC_MAPPING_KEY
    key_id: team-dev-2026q1
  rules:
    src/secret/**:
      require_encryption: true
      encryption_provider: managed-v1
```

Supported key sources today:

- `env`
- `file`

### Workspace key registry

Teams can register reusable key-source references per workspace:

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
python -m codemosaic list-key-sources ./your-repo
```

Then policy can reference only the `key_id`, and `mask` resolves the source from `.codemosaic/key-registry.json`.

### Key rotation

Generate a new key:

```bash
python -m codemosaic generate-key --output ./.codemosaic/keys/team-dev-v2.key
```

Rewrap a single mapping:

```powershell
$env:OLD_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev.key
$env:NEW_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev-v2.key
python -m codemosaic rekey-mapping ./.codemosaic/runs/<run-id>/mapping.enc.json --key-env OLD_CODEMOSAIC_KEY --new-key-env NEW_CODEMOSAIC_KEY --new-key-id team-dev-2026q2 --encryption-provider managed-v1
```

Rewrap recent runs:

```powershell
python -m codemosaic rekey-runs ./your-repo --key-env OLD_CODEMOSAIC_KEY --new-key-env NEW_CODEMOSAIC_KEY --new-key-id team-dev-2026q2 --encryption-provider managed-v1
```

### Metadata and auditability

Encrypted mapping envelopes now keep safe header metadata such as:

- `run_id`
- `generated_at`
- `encryption_provider`
- `key_management.key_id`
- `key_management.source`

This makes operational inspection and key rotation easier without exposing the full decrypted mapping body.

## Policy highlights

The sample policy in `policy.sample.yaml` demonstrates the product direction.

### Managed mapping encryption by path

```yaml
mapping:
  require_encryption: false
  encryption_provider: managed-v1
  key_management:
    source: env
    reference: CODEMOSAIC_MAPPING_KEY
    key_id: team-dev-2026q1
  rules:
    src/secret/**:
      require_encryption: true
      encryption_provider: managed-v1
```

If a run includes `src/secret/**`, CodeMosaic can require encrypted mappings and reject plaintext output.

### Leakage budget gate

```yaml
leakage:
  max_total_score: 20
  max_file_score: 8
  rules:
    src/secret/**:
      max_total_score: 4
      max_file_score: 0
```

This is the core governance idea: a masked bundle can still be blocked if it leaks too much business meaning.

### Segment planning

Preview policy-driven segments:

```bash
python -m codemosaic plan-segments ./your-repo --policy policy.sample.yaml --output segment-plan.json
```

Generate segmented masked outputs:

```bash
python -m codemosaic mask-segmented ./your-repo --policy policy.sample.yaml --output ./segmented-output
```

## VS Code prototype

The repository includes a prototype extension in `extensions/vscode` that wraps common local workflows into editor commands and a runs view.

Useful packaging command:

```bash
python scripts/package_vscode_extension.py --overwrite
```

The extension is intentionally lightweight and prototype-grade, but it tells the product story well:

- scan workspace
- mask workspace
- inspect recent runs
- analyze leakage
- attempt safe export

## Docs index

- `docs/key-management.md` - managed key workflow, policy references, and rotation
- `docs/leakage-gate.md` - semantic leakage scoring and gate behavior
- `docs/ci-governance.md` - CI recipes for policy enforcement
- `docs/demo-walkthrough.md` - short demo flow for product storytelling
- `docs/landing-page.md` - launch/site messaging draft
- `docs/release-playbook.md` - local release steps and assets
- `docs/site/index.html` - static site source

## Static site and GitHub Pages

The static site source remains in `docs/site`, but automated GitHub Pages deployment is intentionally paused for now.

Reason: a broken public Pages pipeline is lower value than a stable repository and release flow. The repo keeps a lightweight site validation workflow instead of auto-deploying Pages on every change.

If you want to publish the site later, you still have everything needed:

- site source in `docs/site`
- asset sync script in `scripts/build_site.py`
- social card and demo visuals in `assets/demo`

## Security boundaries

CodeMosaic reduces exposure, but it is not magic.

- Masking does not guarantee zero semantic disclosure
- Prompt text can still leak business context
- Current leakage analysis is heuristic, not a full DLP system
- `managed-v1` is a stronger workflow for key handling, but it is still an open-source prototype and not a substitute for a formally audited enterprise key-management system
- For high-sensitivity environments, pair this with DLP, audit logging, minimal-context sharing, and self-hosted AI where possible

## Validation

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

Generate site assets locally:

```bash
python scripts/build_site.py --clean-assets
```

Generate release assets:

```bash
python scripts/generate_release_assets.py --encrypt-mapping --clean
```

## Roadmap direction

Near-term directions that keep the project differentiated:

- stronger AST-aware masking for more languages
- smarter semantic leakage scoring and explanations
- better review UX for blocked exports
- safer team workflows around approved policy presets
- richer managed-key providers and external secret-manager integrations
- CI and editor integrations that turn privacy policy into a normal developer workflow

## One-line pitch

**CodeMosaic helps teams use external AI coding tools without giving up control over what their code reveals.**
