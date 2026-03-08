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
- optional: demo SVGs from `assets/demo/`

## Demo prep

Run:

```bash
python scripts/run_demo_workflow.py --encrypt-mapping --clean
```

Then use `docs/demo-walkthrough.md` for the live walkthrough.


## Mapping key rotation

When demo assets or local runs need a fresh passphrase, use:

```bash
python -m codemosaic rekey-mapping <mapping.enc.json> \
  --passphrase-env OLD_CODEMOSAIC_PASSPHRASE \
  --new-passphrase-env NEW_CODEMOSAIC_PASSPHRASE
```

If you omit the new passphrase options, the command writes a plaintext mapping file instead.
