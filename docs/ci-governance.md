# CI Governance

## Goal

Use `CodeMosaic` as a policy gate in CI so teams can answer a concrete question:

> Is this masked code safe enough to export to an external AI tool?

## Recommended flow

1. Build a masked workspace in CI
2. Run `bundle --fail-on-threshold`
3. Fail the job if the leakage budget is exceeded
4. Save `leakage-report.json` as an artifact for review

## Example GitHub Actions workflow

See `examples/github-actions/leakage-gate.yml`.

Core command:

```bash
python -m codemosaic bundle ./.ci.masked \
  --policy presets/balanced-ai-gateway.yaml \
  --output ./ai-bundle.md \
  --leakage-report ./leakage-report.json \
  --fail-on-threshold
```

If the leakage budget is exceeded, the command exits with code `3`.

## Suggested preset starting points

- `presets/strict-ai-gateway.yaml`
- `presets/balanced-ai-gateway.yaml`
- `presets/public-sdk-ai-gateway.yaml`

## Choosing a preset

### `strict-ai-gateway.yaml`
- Use for internal platforms, core algorithms, finance, security-sensitive services
- Enforces encrypted mappings and near-zero semantic leakage on sensitive paths

### `balanced-ai-gateway.yaml`
- Use for most application repos
- Good default for first pilots with external AI tools

### `public-sdk-ai-gateway.yaml`
- Use for SDKs, sample repos, and semi-public integration code
- Keeps governance in place while allowing more context to remain useful

## Team rollout suggestion

1. Start with `balanced-ai-gateway.yaml`
2. Review leakage reports for one or two weeks
3. Tighten rules on the paths that repeatedly show high semantic leakage
4. Move critical repos to `strict-ai-gateway.yaml`

## Run audit

You can also audit stored masking runs before accepting AI-generated patches:

```bash
python -m codemosaic audit-runs ./repo --signing-key-env CODEMOSAIC_AUDIT_KEY --require-signature --output run-audit.json
```
