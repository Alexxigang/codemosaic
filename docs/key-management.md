# Key Management

## Goal

CodeMosaic supports two mapping-secret styles today:

- legacy passphrase flow
- managed key flow

The managed flow is the recommended direction because it separates operational key material from ad-hoc command history and makes rotation easier.

## Recommended workflow

1. Generate a high-entropy key:

```bash
python -m codemosaic generate-key --output ./.codemosaic/keys/team-dev.key
```

2. Load it into a process environment or keep it in a protected file.

PowerShell:

```powershell
$env:CODEMOSAIC_MAPPING_KEY = Get-Content ./.codemosaic/keys/team-dev.key
```

3. Reference that source from policy:

```yaml
mapping:
  require_encryption: true
  encryption_provider: managed-v1
  key_management:
    source: env
    reference: CODEMOSAIC_MAPPING_KEY
    key_id: team-dev-2026q1
```

4. Optionally register that key source inside the workspace:

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
```

5. Run `mask` normally. If policy requires encrypted mappings, CodeMosaic resolves the key source automatically.

## Supported sources

### `env`

Use an environment variable for the current shell or CI job.

```yaml
key_management:
  source: env
  reference: CODEMOSAIC_MAPPING_KEY
  key_id: team-dev-2026q1
```

### `file`

Use a local protected file. Relative paths are resolved relative to the policy file location.

```yaml
key_management:
  source: file
  reference: ./.codemosaic/keys/team-dev.key
  key_id: team-dev-2026q1
```

## Workspace key registry

CodeMosaic supports a local workspace registry at `.codemosaic/key-registry.json`.

Register a source once:

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
```

List registered entries:

```bash
python -m codemosaic list-key-sources ./your-repo
```

Then policy may reference only the key ID:

```yaml
mapping:
  require_encryption: true
  key_management:
    key_id: team-dev-2026q1
```

## Providers

### `prototype-v1`

- default provider for backward compatibility
- passphrase-derived
- useful for early prototyping

### `managed-v1`

- built-in provider for high-entropy key material
- intended for env/file-managed secrets
- recommended for production-like local workflows

### `aesgcm-v1`

- optional provider when `cryptography` is available
- useful if you want AES-GCM envelopes specifically

## Rotation

Generate a new key and rewrap mappings:

```powershell
$env:OLD_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev.key
$env:NEW_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev-v2.key
python -m codemosaic rekey-runs ./your-repo --key-env OLD_CODEMOSAIC_KEY --new-key-env NEW_CODEMOSAIC_KEY --new-key-id team-dev-2026q2 --encryption-provider managed-v1
```

## Metadata

Encrypted mapping envelopes keep a safe header with selected metadata such as:

- `run_id`
- `generated_at`
- `encryption_provider`
- `key_management.key_id`
- `key_management.source`

This header is intentionally limited and does not expose the full decrypted mapping payload.

## Caveats

- This is still an open-source prototype, not a formally audited KMS
- Secret-manager integrations are not implemented yet
- High-sensitivity environments should still layer DLP, audit, and stronger enterprise key controls
