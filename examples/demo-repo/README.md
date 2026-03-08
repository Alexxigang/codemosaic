# Demo Repository

This sample repo is intentionally tiny and includes obviously sensitive-looking values so the CodeMosaic demo workflow has something realistic to scan, mask, and evaluate.

## What this repo is for

- Trigger `scan` findings such as internal URLs, support emails, and secret-like strings
- Produce a masked workspace that still leaks some business meaning
- Demonstrate that `Leakage Budget Gate` can block an export even after masking

## Demo expectation

The bundled demo policy intentionally sets a strict leakage budget. That means:

- a regular masked bundle can still be generated for inspection
- a safe export decision should be reported as `blocked`
- the `web/pricing.ts` path is expected to be one of the highest-risk files
